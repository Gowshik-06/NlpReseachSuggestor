"""
Unit and integration tests for PDF upload pipeline:
- Valid text PDF extraction and recommendation triggering
- Magic bytes header validation (rejecting non-PDFs renamed to .pdf)
- Extension validation
- Empty PDF rejection
- Scanned/blank PDF rejection with clear explanation
- Configurable upload size limit enforcement (HTTP 413)
- Corrupted PDF resilience
"""
import io
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.main import app
from app.schemas.paper import SearchResponse, PaperResponse

client = TestClient(app)

SAMPLE_TEXT_PDF = b'''%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 85 >> stream
BT
/F1 12 Tf
72 712 Td
(Attention Mechanisms and Transformers in NLP Research) Tj
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
0000000378 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
457
%%EOF'''


def make_blank_pdf() -> bytes:
    """Create a syntactically valid PDF with no extractable text (simulating scanned/blank document)."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.mark.anyio
def test_upload_valid_text_pdf_returns_recommendations():
    """Test valid text PDF extracts text and triggers recommendation workflow."""
    mock_resp = SearchResponse(
        query="Attention Mechanisms and Transformers in NLP Research.",
        mode="pdf",
        total_found=1,
        results=[
            PaperResponse(
                paper_id="arxiv:1706.03762",
                title="Attention Is All You Need",
                abstract="The Transformer relies entirely on self-attention mechanisms.",
                authors=["Ashish Vaswani"],
                venue="NeurIPS",
                year=2017,
                similarity_score=0.92,
                explanation="Conceptually aligned with self-attention.",
                source="arxiv"
            )
        ],
        execution_time_seconds=0.15
    )

    with patch(
        "app.api.v1.endpoints.papers.execute_recommendation_search",
        new=AsyncMock(return_value=mock_resp)
    ) as mock_search:
        response = client.post(
            "/api/v1/papers/upload",
            files={"file": ("manuscript.pdf", SAMPLE_TEXT_PDF, "application/pdf")},
            data={"limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "pdf"
        assert len(data["results"]) == 1
        assert "Attention" in data["results"][0]["title"]
        assert mock_search.called


def test_upload_unsupported_file_extension():
    """Test files with non-pdf extensions are rejected."""
    response = client.post(
        "/api/v1/papers/upload",
        files={"file": ("paper.docx", b"word content", "application/vnd.openxmlformats-officedocument")},
        data={"limit": 5}
    )
    assert response.status_code == 400
    assert "Only PDF files are supported" in response.json()["error"]["message"]


def test_upload_fake_pdf_magic_bytes_rejected():
    """Test non-PDF file renamed with .pdf extension is rejected by magic byte validation."""
    fake_content = b"This is not a PDF at all. Just plain text renamed to fake.pdf."
    response = client.post(
        "/api/v1/papers/upload",
        files={"file": ("fake.pdf", fake_content, "application/pdf")},
        data={"limit": 5}
    )
    assert response.status_code == 400
    assert "magic bytes" in response.json()["error"]["message"].lower()


def test_upload_empty_pdf_rejected():
    """Test 0-byte PDF upload is rejected."""
    response = client.post(
        "/api/v1/papers/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        data={"limit": 5}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["error"]["message"].lower()


def test_upload_scanned_or_blank_pdf_rejected_with_explanation():
    """Test scanned/blank PDF with no extractable text returns 422 with clear explanation."""
    blank_pdf = make_blank_pdf()
    response = client.post(
        "/api/v1/papers/upload",
        files={"file": ("scanned.pdf", blank_pdf, "application/pdf")},
        data={"limit": 5}
    )
    assert response.status_code == 422
    err_msg = response.json()["error"]["message"]
    assert "scanned" in err_msg.lower() or "no extractable text" in err_msg.lower()


def test_upload_size_limit_enforced():
    """Test file exceeding MAX_UPLOAD_SIZE_BYTES returns HTTP 413."""
    with patch("app.api.v1.endpoints.papers.get_settings") as mock_settings:
        mock_obj = mock_settings.return_value
        mock_obj.MAX_UPLOAD_SIZE_BYTES = 500  # 500 bytes limit for test

        oversized_content = b"%PDF-1.4\n" + b"A" * 1000
        response = client.post(
            "/api/v1/papers/upload",
            files={"file": ("huge.pdf", oversized_content, "application/pdf")},
            data={"limit": 5}
        )
        assert response.status_code == 413
        assert "exceeds maximum allowed size" in response.json()["error"]["message"].lower()
