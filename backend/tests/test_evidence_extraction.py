"""
Comprehensive test suite for TASK-13: ResearchLens Evidence-Grounded Research Intelligence.
Covers deterministic extraction, all 9 categories, exact span verification,
database persistence, API endpoints, error handling, idempotency, and security.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import engine, SessionLocal, Base
from app.models.paper import Paper, SavedPaper
from app.models.evidence import PaperEvidence
from app.models.user import User
from app.core.security import create_access_token, hash_password
from app.schemas.evidence import ALL_EVIDENCE_CATEGORIES, EvidenceCategory
from app.services.evidence_service import (
    extract_evidence_from_text,
    verify_evidence_record,
    extract_and_persist_paper_evidence,
    get_paper_evidence,
    compute_source_hash,
)

client = TestClient(app)

SAMPLE_RICH_ACADEMIC_TEXT = (
    "A major challenge in modern deep learning is the severe computational cost and memory footprint of large transformers. "
    "In this paper, we aim to design an efficient sparse attention mechanism for long contexts. "
    "We propose FlashTree, a novel architecture that dynamically prunes attention heads. "
    "We evaluated on the GLUE benchmark and the SQuAD dataset using an NVIDIA A100 GPU cluster. "
    "Evaluation metrics include BLEU-4, F1-score, and inference latency measured in milliseconds. "
    "Our results show that FlashTree outperforms all existing baselines, achieving state-of-the-art performance with a 3.5x speedup. "
    "Our main contribution is the first demonstration of sub-quadratic attention with provable error bounds. "
    "A primary limitation of our approach is that performance degrades when sequence length exceeds 64k tokens. "
    "In future work, we plan to extend FlashTree to autoregressive multimodal models."
)


@pytest.fixture(scope="module")
def auth_headers():
    """Ensure test users and return valid JWT auth headers."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "evidence_test_user").first()
        if not user:
            user = User(
                username="evidence_test_user",
                email="evidence_user@test.local",
                hashed_password=hash_password("EvidencePassword2026!"),
                full_name="Evidence Tester",
                is_active=True
            )
            db.add(user)
            db.commit()
    finally:
        db.close()
    token = create_access_token("evidence_test_user")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def db_session():
    """Provide a transactional DB session that cleans up created evidence test papers."""
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def test_paper(db_session):
    """Create a persistent test paper with rich academic abstract."""
    paper = Paper(
        paper_id="test:flashtree_2026",
        title="FlashTree: Dynamic Sparse Attention for Efficient Transformers",
        abstract=SAMPLE_RICH_ACADEMIC_TEXT,
        authors=["Alice Smith", "Bob Jones"],
        venue="ICLR 2026",
        year=2026,
        source="local"
    )
    db_session.add(paper)
    db_session.commit()
    db_session.refresh(paper)

    yield paper

    # Teardown
    db_session.query(PaperEvidence).filter(PaperEvidence.paper_id == paper.id).delete()
    db_session.query(Paper).filter(Paper.id == paper.id).delete()
    db_session.commit()


# ---------------------------------------------------------------------------
# 1. Deterministic Extraction & Grounded Spans
# ---------------------------------------------------------------------------

def test_extract_evidence_all_nine_categories():
    """Verify that all 9 categories are extracted from rich academic prose with exact spans."""
    evidence, missing = extract_evidence_from_text(SAMPLE_RICH_ACADEMIC_TEXT, source_type="abstract")
    assert len(missing) == 0, f"Expected 0 missing categories, got: {missing}"
    
    extracted_categories = {e["category"] for e in evidence}
    assert extracted_categories == set(ALL_EVIDENCE_CATEGORIES)

    for item in evidence:
        # Strict span correspondence
        start = item["char_start"]
        end = item["char_end"]
        assert SAMPLE_RICH_ACADEMIC_TEXT[start:end] == item["source_passage"]
        assert item["claim"]
        assert item["confidence_score"] >= 0.70
        assert item["is_verified"] is True
        assert item["source_type"] == "abstract"
        assert item["page_number"] is None  # Never fabricated for abstract


def test_missing_or_empty_paper_text():
    """Empty or whitespace text must return 0 evidence and explicitly mark all categories missing."""
    evidence, missing = extract_evidence_from_text("", source_type="abstract")
    assert len(evidence) == 0
    assert len(missing) == 9
    assert set(missing) == set(ALL_EVIDENCE_CATEGORIES)

    evidence_ws, missing_ws = extract_evidence_from_text("   \n\t  ", source_type="abstract")
    assert len(evidence_ws) == 0
    assert len(missing_ws) == 9


def test_malformed_or_insufficient_text():
    """Insufficient text (<20 characters) must return missing categories and zero fabricated claims."""
    evidence, missing = extract_evidence_from_text("Deep learning.", source_type="abstract")
    assert len(evidence) == 0
    assert len(missing) == 9


def test_partial_extraction_no_hallucination():
    """Text mentioning only method and results must not fabricate problem, dataset, or limitations."""
    partial_text = (
        "We propose a novel recurrent framework for speech enhancement. "
        "Our empirical results show that the model outperforms competitive baselines with 95% accuracy."
    )
    evidence, missing = extract_evidence_from_text(partial_text, source_type="abstract")
    found_cats = {e["category"] for e in evidence}

    assert "method" in found_cats
    assert "results" in found_cats
    assert "problem" in missing
    assert "dataset" in missing
    assert "limitations" in missing
    assert "future_work" in missing
    assert "contributions" in missing


# ---------------------------------------------------------------------------
# 2. Verification Layer
# ---------------------------------------------------------------------------

def test_verify_evidence_record_valid_span(db_session, test_paper):
    """Valid evidence record matches exact source text slice."""
    res = extract_and_persist_paper_evidence(db_session, test_paper, force=True)
    assert res.evidence_count > 0

    record = db_session.query(PaperEvidence).filter(PaperEvidence.paper_id == test_paper.id).first()
    assert record is not None

    verification = verify_evidence_record(record, test_paper)
    assert verification["is_valid"] is True
    assert verification["span_valid"] is True
    assert verification["is_stale"] is False


def test_verify_evidence_record_rejects_corrupted_span(db_session, test_paper):
    """Verification layer flags corrupted or shifted spans."""
    res = extract_and_persist_paper_evidence(db_session, test_paper, force=True)
    record = db_session.query(PaperEvidence).filter(PaperEvidence.paper_id == test_paper.id).first()

    # Tamper with the char_start/end so it points to the wrong text slice
    record.char_start = 0
    record.char_end = 10  # Slice text: "A major ch"
    # But source passage is the full sentence

    verification = verify_evidence_record(record, test_paper)
    assert verification["span_valid"] is False


def test_verify_evidence_record_rejects_empty_passage(db_session, test_paper):
    """Verification layer rejects records with empty or whitespace passage."""
    record = PaperEvidence(
        paper_id=test_paper.id,
        category="method",
        claim="Claim with empty passage",
        source_passage="",
        source_type="abstract"
    )
    verification = verify_evidence_record(record, test_paper)
    assert verification["is_valid"] is False
    assert "empty" in verification["reason"].lower()


def test_staleness_detection_on_source_text_change(db_session, test_paper):
    """Updating a paper's text marks previously persisted evidence as stale."""
    extract_and_persist_paper_evidence(db_session, test_paper, force=True)
    
    # Check initial retrieval is fresh
    initial_res = get_paper_evidence(db_session, test_paper)
    assert initial_res.verification_summary.is_stale is False

    # Update paper text to simulate modified document version
    test_paper.abstract = "Completely updated research abstract with different content."
    db_session.commit()

    # Retrieval should detect stale evidence
    stale_res = get_paper_evidence(db_session, test_paper)
    assert stale_res.verification_summary.is_stale is True
    assert stale_res.status == "stale"


# ---------------------------------------------------------------------------
# 3. Database Persistence & Idempotency
# ---------------------------------------------------------------------------

def test_extract_and_persist_idempotency(db_session, test_paper):
    """Repeated extraction calls must be idempotent and not accumulate duplicate records."""
    res1 = extract_and_persist_paper_evidence(db_session, test_paper, force=True)
    initial_count = db_session.query(PaperEvidence).filter(PaperEvidence.paper_id == test_paper.id).count()
    assert initial_count >= 8

    # Second extraction without force
    res2 = extract_and_persist_paper_evidence(db_session, test_paper, force=False)
    count_after = db_session.query(PaperEvidence).filter(PaperEvidence.paper_id == test_paper.id).count()
    assert count_after == initial_count

    # Third extraction with force=True
    res3 = extract_and_persist_paper_evidence(db_session, test_paper, force=True)
    count_forced = db_session.query(PaperEvidence).filter(PaperEvidence.paper_id == test_paper.id).count()
    assert count_forced == initial_count


def test_re_extraction_updates_cleanly_after_text_edit(db_session, test_paper):
    """Re-extraction after a text update cleans old evidence and extracts fresh records."""
    extract_and_persist_paper_evidence(db_session, test_paper, force=True)
    
    # New text with only 2 categories
    new_text = (
        "We propose FastLinear, a novel sub-quadratic architecture for sequence modeling. "
        "In future work, we plan to validate this on audio synthesis."
    )
    test_paper.abstract = new_text
    db_session.commit()

    fresh_res = extract_and_persist_paper_evidence(db_session, test_paper, force=True)
    assert fresh_res.status == "partial_extraction"
    assert "method" in fresh_res.categories_present
    assert "future_work" in fresh_res.categories_present
    assert fresh_res.verification_summary.is_stale is False

    # Check database records match new text
    records = db_session.query(PaperEvidence).filter(PaperEvidence.paper_id == test_paper.id).all()
    assert len(records) == 2
    for r in records:
        assert new_text[r.char_start:r.char_end] == r.source_passage


# ---------------------------------------------------------------------------
# 4. API Endpoints, Authentication & Validation
# ---------------------------------------------------------------------------

def test_api_get_evidence_success(test_paper):
    """GET /api/v1/papers/{paper_id}/evidence returns structured evidence."""
    response = client.get(f"/api/v1/papers/{test_paper.paper_id}/evidence")
    assert response.status_code == 200
    data = response.json()
    assert data["paper_id"] == test_paper.paper_id
    assert data["evidence_count"] >= 8
    assert "evidence" in data
    assert "verification_summary" in data
    assert data["verification_summary"]["verified_count"] >= 8


def test_api_get_evidence_by_numeric_id(test_paper):
    """GET /api/v1/papers/{id}/evidence works with numeric database ID."""
    response = client.get(f"/api/v1/papers/{test_paper.id}/evidence")
    assert response.status_code == 200
    data = response.json()
    assert data["paper_id"] == test_paper.paper_id


def test_api_get_evidence_category_filter(test_paper):
    """GET /api/v1/papers/{paper_id}/evidence?category=method filters by category."""
    response = client.get(f"/api/v1/papers/{test_paper.paper_id}/evidence?category=method")
    assert response.status_code == 200
    data = response.json()
    assert data["evidence_count"] >= 1
    for item in data["evidence"]:
        assert item["category"] == "method"


def test_api_get_evidence_invalid_category(test_paper):
    """GET /api/v1/papers/{paper_id}/evidence with bad category returns 400."""
    response = client.get(f"/api/v1/papers/{test_paper.paper_id}/evidence?category=invalid_cat_xyz")
    assert response.status_code == 400
    data = response.json()
    err_msg = data.get("detail") or data.get("error", {}).get("message", "")
    assert "invalid evidence category" in err_msg.lower()


def test_api_get_evidence_missing_paper_404():
    """GET /api/v1/papers/nonexistent_id/evidence returns 404."""
    response = client.get("/api/v1/papers/nonexistent_paper_999999/evidence")
    assert response.status_code == 404
    data = response.json()
    err_msg = data.get("detail") or data.get("error", {}).get("message", "")
    assert "not found" in err_msg.lower()


def test_api_extract_evidence_requires_auth(test_paper):
    """POST /api/v1/papers/{paper_id}/evidence/extract without token returns 401."""
    response = client.post(f"/api/v1/papers/{test_paper.paper_id}/evidence/extract", json={"force": True})
    assert response.status_code == 401


def test_api_extract_evidence_authenticated(test_paper, auth_headers):
    """POST /api/v1/papers/{paper_id}/evidence/extract with token returns 200 and refreshes evidence."""
    response = client.post(
        f"/api/v1/papers/{test_paper.paper_id}/evidence/extract",
        json={"force": True},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["evidence_count"] >= 8
    assert data["verification_summary"]["verified_count"] >= 8


def test_api_verify_endpoint(test_paper, auth_headers):
    """GET /api/v1/papers/{paper_id}/evidence/verify returns detailed audit report."""
    # Ensure evidence extracted
    client.post(
        f"/api/v1/papers/{test_paper.paper_id}/evidence/extract",
        json={"force": True},
        headers=auth_headers
    )

    response = client.get(f"/api/v1/papers/{test_paper.paper_id}/evidence/verify")
    assert response.status_code == 200
    data = response.json()
    assert data["paper_id"] == test_paper.paper_id
    assert data["total_records"] >= 8
    assert data["all_valid"] is True
    assert len(data["audit_results"]) == data["total_records"]
    for audit in data["audit_results"]:
        assert audit["verification"]["is_valid"] is True
        assert audit["verification"]["span_valid"] is True


def test_api_unavailable_text_handling(db_session, auth_headers):
    """Paper with no abstract and no raw_text returns status unavailable_text."""
    empty_paper = Paper(
        paper_id="test:empty_paper_2026",
        title="Paper With No Text Available",
        abstract="",
        raw_text="",
        source="local"
    )
    db_session.add(empty_paper)
    db_session.commit()
    db_session.refresh(empty_paper)

    try:
        response = client.get(f"/api/v1/papers/{empty_paper.paper_id}/evidence")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unavailable_text"
        assert data["evidence_count"] == 0
        assert len(data["missing_categories"]) == 9
    finally:
        db_session.query(Paper).filter(Paper.id == empty_paper.id).delete()
        db_session.commit()


def test_full_text_provenance_and_page_detection(db_session, auth_headers):
    """Verify that full-text extraction detects sections, page numbers, and sets source_type='full_text'."""
    full_text_content = (
        "--- Page 1 ---\n"
        "1. Introduction\n"
        "A major challenge in quantum machine learning is the noise in NISQ devices.\n"
        "In this paper, we aim to design fault-tolerant quantum error mitigation protocols.\n\n"
        "--- Page 2 ---\n"
        "3. Methodology\n"
        "We propose QuantumShield, a novel architecture that mitigates decoherence.\n\n"
        "--- Page 3 ---\n"
        "5. Limitations\n"
        "A primary limitation of our approach is that circuit depth is restricted to 100 gates.\n"
    )
    paper = Paper(
        paper_id="test:quantum_full_2026",
        title="QuantumShield: Fault-Tolerant Mitigation for NISQ Devices",
        abstract="Brief abstract.",
        raw_text=full_text_content,
        source="local"
    )
    db_session.add(paper)
    db_session.commit()
    db_session.refresh(paper)

    try:
        res = extract_and_persist_paper_evidence(db_session, paper, force=True)
        assert res.source_type == "full_text"
        assert res.evidence_count >= 3

        records = db_session.query(PaperEvidence).filter(PaperEvidence.paper_id == paper.id).all()
        for r in records:
            assert r.source_type == "full_text"
            assert r.page_number in [1, 2, 3]
            # Exact span slice verification against raw_text
            assert full_text_content[r.char_start:r.char_end] == r.source_passage

        # Check section detection for limitation record
        lim_rec = next((r for r in records if r.category == "limitations"), None)
        assert lim_rec is not None
        assert lim_rec.section_name == "Limitations"
        assert lim_rec.page_number == 3
    finally:
        db_session.query(PaperEvidence).filter(PaperEvidence.paper_id == paper.id).delete()
        db_session.query(Paper).filter(Paper.id == paper.id).delete()
        db_session.commit()


def test_cross_user_isolation_private_resources(db_session, test_paper, auth_headers):
    """Verify that user isolation protects private resources (SavedPaper) across distinct researchers."""
    # Ensure second user exists
    user_b = db_session.query(User).filter(User.username == "isolated_user_b").first()
    if not user_b:
        user_b = User(
            username="isolated_user_b",
            email="user_b@test.local",
            hashed_password=hash_password("UserBPass2026!"),
            full_name="Isolated User B",
            is_active=True
        )
        db_session.add(user_b)
        db_session.commit()
    token_b = create_access_token("isolated_user_b")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B saves the test paper
    save_resp = client.post("/api/v1/papers/save", json={"paper_id": test_paper.id, "notes": "User B private note"}, headers=headers_b)
    assert save_resp.status_code == 200
    saved_id = save_resp.json()["id"]

    try:
        # User A (evidence_test_user) attempts to delete User B's saved paper -> must return 404
        del_resp = client.delete(f"/api/v1/papers/saved/{saved_id}", headers=auth_headers)
        assert del_resp.status_code == 404

        # User A checks their saved library -> User B's saved paper is not visible
        lib_resp = client.get("/api/v1/papers/saved", headers=auth_headers)
        assert lib_resp.status_code == 200
        user_a_saved_ids = [item["id"] for item in lib_resp.json()]
        assert saved_id not in user_a_saved_ids
    finally:
        # Clean up
        db_session.query(SavedPaper).filter(SavedPaper.id == saved_id).delete()
        db_session.commit()
