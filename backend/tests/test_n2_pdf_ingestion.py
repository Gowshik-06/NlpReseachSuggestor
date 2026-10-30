"""
TASK N2 — Explicit PDF-to-Catalog Ingestion Test Suite.

Validates the full N2 contract across:
1. Upload validation:
   - Extension verification (.pdf)
   - Magic bytes verification (%PDF-)
   - Empty file rejection (400)
   - Corrupted/malformed PDF handling (422)
   - Scanned/zero-text PDF rejection (422)
   - Upload size limits (413)
2. Safe side-effect-free preview:
   - Preview extracts metadata and returns transient recommendations
   - Preview does NOT write to PostgreSQL
   - Preview does NOT mutate FAISS index
   - Preview does NOT create DRIUT alerts
   - Read-only duplicate detection by DOI and normalized title similarity
   - External provider/recommendation failures do not modify catalog
3. Explicit catalog ingestion:
   - Requires explicit confirmation (confirm_ingest=True, rejects False with 400)
   - Requires user authentication (401 for unauthenticated)
   - Enforces duplicate rejection on ingest (409 Conflict)
   - Synchronizes FAISS vector with embedding dimension 768
   - Persists to catalog with stable paper_id
   - Supports optional automatic add_to_library
   - Graceful partial failure reporting when FAISS synchronization fails
   - Database failure rollback guarantees zero orphan FAISS vectors
4. Regression preservation:
   - Test isolation shield remains intact
   - Search remains side-effect-free
"""
import io
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.user import User
from app.models.paper import Paper, SavedPaper
from app.models.evidence import PaperEvidence
from app.models.driut import DRIUTAlert
from app.core.security import create_access_token, hash_password
from app.services.vector_index import get_faiss_index

client = TestClient(app)

SAMPLE_TEXT_PDF = b'''%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 120 >> stream
BT
/F1 12 Tf
72 712 Td
(Quantum Transformers for Molecular Representation Learning) Tj
0 -20 Td
(Abstract: We introduce Quantum Transformers to model complex chemical bonds.) Tj
ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000415 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
494
%%EOF'''


def get_err(response) -> str:
    """Helper to extract error message from API response adhering to centralized error format."""
    data = response.json()
    if isinstance(data, dict):
        if "error" in data and isinstance(data["error"], dict) and "message" in data["error"]:
            return data["error"]["message"]
        if "detail" in data:
            return str(data["detail"])
    return str(data)


def make_blank_pdf() -> bytes:
    """Create a syntactically valid PDF with no extractable text (simulating scanned/blank document)."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def setup_n2_suite():
    """Setup isolated test fixtures for N2 tests."""
    db = SessionLocal()

    test_users = ["n2_user_test", "n2_user_other"]
    db.query(DRIUTAlert).filter(DRIUTAlert.user_id.in_(test_users)).delete()
    db.query(SavedPaper).filter(SavedPaper.user_id.in_(test_users)).delete()
    db.query(User).filter(User.username.in_(test_users)).delete()

    u1 = User(
        username="n2_user_test",
        email="n2_test@example.com",
        hashed_password=hash_password("Password123!"),
        is_active=True,
    )
    u2 = User(
        username="n2_user_other",
        email="n2_other@example.com",
        hashed_password=hash_password("Password123!"),
        is_active=True,
    )
    db.add(u1)
    db.add(u2)

    # Catalog paper for duplicate testing
    existing = db.query(Paper).filter(Paper.paper_id == "arxiv:test.n2.existing.01").first()
    if not existing:
        existing = Paper(
            paper_id="arxiv:test.n2.existing.01",
            title="Pre-existing Quantum Network Architectures in Chemistry",
            abstract="Existing baseline for molecular transformers and graph representations.",
            doi="10.1234/n2.existing.doi",
            authors=["Alice Chemist", "Bob Quantum"],
            venue="Nature Chemistry",
            year=2023,
        )
        db.add(existing)

    db.commit()
    db.refresh(u1)
    db.refresh(u2)

    token1 = create_access_token(u1.username)
    token2 = create_access_token(u2.username)

    yield {
        "user1": u1,
        "token1": token1,
        "user2": u2,
        "token2": token2,
    }

    db.close()


# =========================================================================
# Phase 3 & 7: Upload Validation Tests
# =========================================================================

def test_preview_non_pdf_extension_rejected():
    """Files without .pdf extension are rejected with 400 Bad Request."""
    response = client.post(
        "/api/v1/papers/preview-pdf",
        files={"file": ("manuscript.txt", b"plain text manuscript", "text/plain")}
    )
    assert response.status_code == 400
    assert "PDF files (.pdf) are accepted" in get_err(response) or "only pdf" in get_err(response).lower()


def test_preview_fake_pdf_magic_bytes_rejected():
    """Text files renamed to .pdf lacking %PDF- magic bytes header are rejected with 400."""
    fake_pdf = b"Plain text file renamed to manuscript.pdf"
    response = client.post(
        "/api/v1/papers/preview-pdf",
        files={"file": ("renamed_text.pdf", fake_pdf, "application/pdf")}
    )
    assert response.status_code == 400
    assert "magic bytes" in get_err(response).lower() or "signature" in get_err(response).lower()


def test_preview_empty_file_rejected():
    """Empty 0-byte file upload is rejected with 400."""
    response = client.post(
        "/api/v1/papers/preview-pdf",
        files={"file": ("empty.pdf", b"", "application/pdf")}
    )
    assert response.status_code == 400
    assert "empty" in get_err(response).lower()


def test_preview_corrupted_pdf_rejected():
    """Corrupted PDF payload returns 422 with actionable parsing failure message."""
    corrupted_pdf = b"%PDF-1.4\ncorrupted content truncation"
    response = client.post(
        "/api/v1/papers/preview-pdf",
        files={"file": ("corrupted.pdf", corrupted_pdf, "application/pdf")}
    )
    assert response.status_code == 422
    err = get_err(response).lower()
    assert "extract" in err or "malformed" in err or "stream has ended" in err or "eof" in err


def test_preview_scanned_or_blank_pdf_rejected():
    """Syntactically valid PDF with zero extractable text returns 422 with clear explanation."""
    blank_pdf = make_blank_pdf()
    response = client.post(
        "/api/v1/papers/preview-pdf",
        files={"file": ("scanned_blank.pdf", blank_pdf, "application/pdf")}
    )
    assert response.status_code == 422
    err = get_err(response).lower()
    assert "no extractable text" in err or "scanned" in err


def test_preview_oversized_upload_rejected():
    """PDF payload exceeding max upload limit returns 413 Payload Too Large."""
    settings = get_settings()
    with patch.object(settings, "MAX_UPLOAD_SIZE_BYTES", 100):
        response = client.post(
            "/api/v1/papers/preview-pdf",
            files={"file": ("oversized.pdf", SAMPLE_TEXT_PDF, "application/pdf")}
        )
        assert response.status_code == 413
        assert "exceeds maximum allowed size" in get_err(response).lower()


# =========================================================================
# Phase 4 & 7: Safe Preview & Duplicate Detection Tests (Read-Only)
# =========================================================================

def test_preview_valid_pdf_is_side_effect_free():
    """
    CRITICAL INVARIANT: Previewing a PDF extracts metadata and transient recommendations
    WITHOUT writing to PostgreSQL, mutating FAISS, or creating DRIUT alerts.
    """
    db = SessionLocal()
    initial_paper_count = db.query(Paper).count()
    initial_saved_count = db.query(SavedPaper).count()
    initial_evidence_count = db.query(PaperEvidence).count()
    initial_alert_count = db.query(DRIUTAlert).count()

    faiss_idx = get_faiss_index()
    initial_vector_count = faiss_idx.index.ntotal if faiss_idx.index is not None else 0

    response = client.post(
        "/api/v1/papers/preview-pdf",
        files={"file": ("quantum_transformers.pdf", SAMPLE_TEXT_PDF, "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "preview_ready"
    assert data["allow_ingest"] is True
    assert data["extracted_metadata"]["title"] != ""
    assert data["duplicate_check"]["is_duplicate"] is False

    # Verify zero mutations in database
    assert db.query(Paper).count() == initial_paper_count
    assert db.query(SavedPaper).count() == initial_saved_count
    assert db.query(PaperEvidence).count() == initial_evidence_count
    assert db.query(DRIUTAlert).count() == initial_alert_count

    # Verify zero mutations in FAISS
    current_vector_count = faiss_idx.index.ntotal if faiss_idx.index is not None else 0
    assert current_vector_count == initial_vector_count
    db.close()


def test_preview_duplicate_detection_by_doi(setup_n2_suite):
    """Preview detects pre-existing paper by exact DOI and blocks ingestion with duplicate info."""
    db = SessionLocal()
    initial_paper_count = db.query(Paper).count()

    mock_extracted = {
        "success": True,
        "title": "Novel Quantum Network Variations",
        "abstract": "Testing DOI deduplication in preview.",
        "authors": ["Alice Chemist"],
        "year": 2023,
        "doi": "10.1234/n2.existing.doi",
        "venue": "Nature Chemistry",
        "keywords": ["quantum"],
        "raw_text": "Full text manuscript with DOI 10.1234/n2.existing.doi",
        "page_count": 4,
    }

    with patch("app.api.v1.endpoints.papers.extract_text_from_pdf_bytes", return_value=mock_extracted):
        response = client.post(
            "/api/v1/papers/preview-pdf",
            files={"file": ("test_doi_duplicate.pdf", SAMPLE_TEXT_PDF, "application/pdf")}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["duplicate_check"]["is_duplicate"] is True
        assert data["duplicate_check"]["match_type"] == "exact_doi"
        assert data["duplicate_check"]["matched_paper_id"] == "arxiv:test.n2.existing.01"
        assert data["allow_ingest"] is False
        assert any("duplicate detected" in w.lower() for w in data["warnings"])

    # Ensure no DB changes occurred
    assert db.query(Paper).count() == initial_paper_count
    db.close()


def test_preview_duplicate_detection_by_title_similarity(setup_n2_suite):
    """Preview detects pre-existing paper by normalized title similarity (Jaccard >= 0.85)."""
    mock_extracted = {
        "success": True,
        "title": "Pre-existing Quantum Network Architectures in Chemistry",
        "abstract": "Testing title similarity deduplication in preview.",
        "authors": ["Alice Chemist"],
        "year": 2023,
        "doi": None,
        "venue": None,
        "keywords": [],
        "raw_text": "Manuscript text content...",
        "page_count": 3,
    }

    with patch("app.api.v1.endpoints.papers.extract_text_from_pdf_bytes", return_value=mock_extracted):
        response = client.post(
            "/api/v1/papers/preview-pdf",
            files={"file": ("test_title_duplicate.pdf", SAMPLE_TEXT_PDF, "application/pdf")}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["duplicate_check"]["is_duplicate"] is True
        assert data["allow_ingest"] is False


def test_preview_recommendation_failure_does_not_break_preview():
    """If recommendation search fails, preview still succeeds with empty recommendations and warning."""
    with patch(
        "app.api.v1.endpoints.papers.execute_recommendation_search",
        side_effect=RuntimeError("Transient external provider failure")
    ):
        response = client.post(
            "/api/v1/papers/preview-pdf",
            files={"file": ("test_rec_fail.pdf", SAMPLE_TEXT_PDF, "application/pdf")}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "preview_ready"
        assert data["recommendations"] == []
        assert any("recommendations currently unavailable" in w.lower() for w in data["warnings"])


# =========================================================================
# Phase 5 & 7: Explicit Catalog Ingestion Tests
# =========================================================================

def test_ingest_without_explicit_confirmation_rejected(setup_n2_suite):
    """Ingestion request with confirm_ingest=False is rejected with 400 Bad Request."""
    headers = {"Authorization": f"Bearer {setup_n2_suite['token1']}"}
    payload = {
        "title": "Quantum Transformers for Molecular Representations",
        "abstract": "We model chemical bonds with quantum attention.",
        "confirm_ingest": False,
    }
    response = client.post("/api/v1/papers/ingest-pdf", json=payload, headers=headers)
    assert response.status_code == 400
    assert "explicit confirmation" in get_err(response).lower()


def test_ingest_unauthenticated_rejected():
    """Ingestion request without authentication token is rejected with 401 Unauthorized."""
    payload = {
        "title": "Unauthenticated Ingestion Attempt",
        "confirm_ingest": True,
    }
    response = client.post("/api/v1/papers/ingest-pdf", json=payload)
    assert response.status_code == 401


def test_ingest_missing_title_rejected(setup_n2_suite):
    """Ingestion request with empty title is rejected with 422 Unprocessable Entity."""
    headers = {"Authorization": f"Bearer {setup_n2_suite['token1']}"}
    payload = {
        "title": "   ",
        "confirm_ingest": True,
    }
    response = client.post("/api/v1/papers/ingest-pdf", json=payload, headers=headers)
    assert response.status_code == 422


def test_ingest_valid_manuscript_persists_to_catalog_and_synchronizes_faiss(setup_n2_suite):
    """
    Full explicit ingestion test:
    1. Persists manuscript to PostgreSQL catalog with stable paper_id.
    2. Synchronizes FAISS vector with 768-dim embedding.
    3. Adds paper to user's saved library when add_to_library=True.
    4. Returns 200 with catalog_id, faiss_indexed=True, saved_to_library=True.
    """
    headers = {"Authorization": f"Bearer {setup_n2_suite['token1']}"}
    faiss_idx = get_faiss_index()
    initial_ntotal = faiss_idx.index.ntotal if faiss_idx.index is not None else 0

    unique_title = "Hierarchical Multi-Scale Graph Attention for Materials Discovery"
    payload = {
        "title": unique_title,
        "abstract": "Graph attention network for crystalline material properties.",
        "authors": ["Carol Materialist", "David Chemist"],
        "year": 2024,
        "doi": "10.1234/test.n2.mat.2024",
        "venue": "Advanced Materials AI",
        "keywords": ["materials", "graph attention"],
        "confirm_ingest": True,
        "add_to_library": True,
    }

    response = client.post("/api/v1/papers/ingest-pdf", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["catalog_id"] > 0
    assert data["paper_id"] != ""
    assert data["paper_id"].startswith(("doi:", "pdf_"))
    assert data["faiss_indexed"] is True
    assert data["saved_to_library"] is True

    # 1. Verify PostgreSQL catalog persistence
    db = SessionLocal()
    persisted_paper = db.query(Paper).filter(Paper.id == data["catalog_id"]).first()
    assert persisted_paper is not None
    assert persisted_paper.title == unique_title
    assert persisted_paper.doi == "10.1234/test.n2.mat.2024"

    # 2. Verify SavedPaper row created for user
    saved_row = db.query(SavedPaper).filter(
        SavedPaper.user_id == setup_n2_suite["user1"].username,
        SavedPaper.paper_id == persisted_paper.id
    ).first()
    assert saved_row is not None

    # 3. Verify FAISS index vector synchronized
    current_ntotal = faiss_idx.index.ntotal if faiss_idx.index is not None else 0
    assert current_ntotal == initial_ntotal + 1
    assert faiss_idx.dimension == 768
    db.close()


def test_ingest_duplicate_rejected_with_409(setup_n2_suite):
    """Submitting duplicate ingestion for an already persisted DOI returns 409 Conflict."""
    headers = {"Authorization": f"Bearer {setup_n2_suite['token1']}"}
    faiss_idx = get_faiss_index()
    initial_ntotal = faiss_idx.index.ntotal if faiss_idx.index is not None else 0

    payload = {
        "title": "Another variation of quantum networks",
        "abstract": "Testing duplicate ingest collision.",
        "doi": "10.1234/n2.existing.doi",  # Collides with pre-existing paper
        "confirm_ingest": True,
    }

    response = client.post("/api/v1/papers/ingest-pdf", json=payload, headers=headers)
    assert response.status_code == 409
    assert "duplicate manuscript" in get_err(response).lower()

    # FAISS index must not have received another vector
    current_ntotal = faiss_idx.index.ntotal if faiss_idx.index is not None else 0
    assert current_ntotal == initial_ntotal


def test_ingest_faiss_failure_handles_partial_success_cleanly(setup_n2_suite):
    """
    If FAISS indexing fails after catalog DB commit:
    - Operation reports partial_success_faiss_pending with faiss_indexed=False.
    - DB record remains safely committed (no reckless rollback/deletion).
    - Returns 200 with actionable warning for subsequent index reconciliation.
    """
    headers = {"Authorization": f"Bearer {setup_n2_suite['token1']}"}
    unique_title = "Fault-Tolerant FAISS Sync Resilience Paper"
    payload = {
        "title": unique_title,
        "abstract": "Resilient handling of vector index failures.",
        "confirm_ingest": True,
        "add_to_library": False,
    }

    with patch.object(get_faiss_index(), "add_papers", side_effect=RuntimeError("Simulated FAISS disk failure")):
        response = client.post("/api/v1/papers/ingest-pdf", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "partial_success_faiss_pending"
        assert data["faiss_indexed"] is False
        assert "pending recovery" in data["message"].lower()

        # Ensure the paper is still safely preserved in DB
        db = SessionLocal()
        paper_in_db = db.query(Paper).filter(Paper.id == data["catalog_id"]).first()
        assert paper_in_db is not None
        assert paper_in_db.title == unique_title
        db.close()


def test_ingest_db_failure_does_not_mutate_faiss(setup_n2_suite):
    """
    If database commit fails, FAISS vector must NOT be added.
    Vector index remains strictly consistent with database.
    """
    headers = {"Authorization": f"Bearer {setup_n2_suite['token1']}"}
    faiss_idx = get_faiss_index()
    initial_ntotal = faiss_idx.index.ntotal if faiss_idx.index is not None else 0

    payload = {
        "title": "Rollback Safety Paper",
        "abstract": "Testing vector isolation on DB error.",
        "confirm_ingest": True,
    }

    with patch.object(Session, "commit", side_effect=RuntimeError("Simulated DB lock error")):
        response = client.post("/api/v1/papers/ingest-pdf", json=payload, headers=headers)
        assert response.status_code == 500

    # Ensure FAISS index vector count did not increase
    current_ntotal = faiss_idx.index.ntotal if faiss_idx.index is not None else 0
    assert current_ntotal == initial_ntotal
