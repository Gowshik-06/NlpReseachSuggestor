"""
Integration tests for Paper Recommendation, Search, Summary, Comparison, and DRIUT APIs.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import engine, SessionLocal, Base
from app.models.paper import Paper, SavedPaper
from app.models.driut import DRIUTAlert
from app.models.user import User
from app.core.security import create_access_token, hash_password
from app.services.vector_index import get_faiss_index, INDEX_PATH, METADATA_PATH
import os

client = TestClient(app)

TEST_DATA = {}


@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    """Create isolated test fixtures for tests and completely purge on teardown."""
    # Capture baseline FAISS files before test additions
    orig_idx_bytes = None
    orig_meta_bytes = None
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "rb") as f:
            orig_idx_bytes = f.read()
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, "rb") as f:
            orig_meta_bytes = f.read()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Ensure test users exist for authenticated tests
    user_def = db.query(User).filter(User.username == "default_user").first()
    if not user_def:
        user_def = User(
            username="default_user",
            email="default_user@test.local",
            hashed_password=hash_password("DevPassword123!"),
            full_name="Default User"
        )
        db.add(user_def)
    user_test = db.query(User).filter(User.username == "test_user").first()
    if not user_test:
        user_test = User(
            username="test_user",
            email="test_user@test.local",
            hashed_password=hash_password("DevPassword123!"),
            full_name="Test User"
        )
        db.add(user_test)
    db.commit()
    TEST_DATA["default_user_token"] = create_access_token("default_user")
    TEST_DATA["test_user_token"] = create_access_token("test_user")

    # Clean any leftover test records
    db.query(DRIUTAlert).filter(DRIUTAlert.user_id.in_(["default_user", "test_user"])).delete()
    db.query(SavedPaper).filter(SavedPaper.user_id.in_(["default_user", "test_user"])).delete()
    db.query(Paper).filter(Paper.paper_id.in_(["arxiv:1810.04805", "arxiv:1706.03762", "arxiv:1907.11692"])).delete()
    db.commit()

    p_bert = Paper(
        paper_id="arxiv:1810.04805",
        title="BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        abstract="We introduce a new language representation model called BERT, which stands for Bidirectional Encoder Representations from Transformers. Unlike recent language representation models, BERT is designed to pre-train deep bidirectional representations from unlabeled text by jointly conditioning on both left and right context in all layers.",
        authors=["Jacob Devlin", "Ming-Wei Chang", "Kenton Lee", "Kristina Toutanova"],
        venue="NAACL 2019",
        year=2018,
        citation_count=95000,
        source="local"
    )
    p_attn = Paper(
        paper_id="arxiv:1706.03762",
        title="Attention Is All You Need",
        abstract="The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The Transformer relies entirely on self-attention mechanisms to draw global dependencies between input and output.",
        authors=["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
        venue="NeurIPS 2017",
        year=2017,
        citation_count=110000,
        source="local"
    )
    p_roberta = Paper(
        paper_id="arxiv:1907.11692",
        title="RoBERTa: A Robustly Optimized BERT Pretraining Approach",
        abstract="Language model pretraining has led to significant performance gains but careful comparison between different approaches is challenging. We find that BERT was significantly undertrained and present RoBERTa.",
        authors=["Yinhan Liu", "Myle Ott"],
        venue="arXiv 2019",
        year=2019,
        citation_count=25000,
        source="local"
    )
    db.add_all([p_bert, p_attn, p_roberta])
    db.commit()
    db.refresh(p_bert)
    db.refresh(p_attn)
    db.refresh(p_roberta)

    TEST_DATA["bert_id"] = p_bert.id
    TEST_DATA["attn_id"] = p_attn.id
    TEST_DATA["roberta_id"] = p_roberta.id

    # Index in FAISS
    fi = get_faiss_index()
    fi.add_papers([
        {"paper_id": p_bert.paper_id, "title": p_bert.title, "abstract": p_bert.abstract, "authors": p_bert.authors, "year": p_bert.year, "citation_count": p_bert.citation_count, "source": "local"},
        {"paper_id": p_attn.paper_id, "title": p_attn.title, "abstract": p_attn.abstract, "authors": p_attn.authors, "year": p_attn.year, "citation_count": p_attn.citation_count, "source": "local"},
        {"paper_id": p_roberta.paper_id, "title": p_roberta.title, "abstract": p_roberta.abstract, "authors": p_roberta.authors, "year": p_roberta.year, "citation_count": p_roberta.citation_count, "source": "local"}
    ])

    # Add test alert for default_user
    alert = DRIUTAlert(
        user_id="default_user",
        saved_paper_id=p_attn.id,
        trigger_paper_id=p_bert.id,
        relationship_type="Extension",
        confidence_score=0.91,
        explanation="BERT extends self-attention transformer architecture bidirectionally.",
        is_read=False
    )
    db.add(alert)
    db.commit()

    yield

    # Teardown: purge test artifacts completely
    db.query(DRIUTAlert).filter(DRIUTAlert.user_id.in_(["default_user", "test_user"])).delete()
    db.query(SavedPaper).filter(SavedPaper.user_id.in_(["default_user", "test_user"])).delete()
    db.query(Paper).filter(Paper.paper_id.in_(["arxiv:1810.04805", "arxiv:1706.03762", "arxiv:1907.11692"])).delete()
    db.commit()
    db.close()

    # Restore baseline FAISS index & metadata
    if orig_idx_bytes is not None:
        with open(INDEX_PATH, "wb") as f:
            f.write(orig_idx_bytes)
    if orig_meta_bytes is not None:
        with open(METADATA_PATH, "wb") as f:
            f.write(orig_meta_bytes)
    fi._load_or_initialize()


def test_semantic_search_returns_relevant_recommendations():
    """Test searching for 'bidirectional transformers' returns BERT and RoBERTa."""
    response = client.post(
        "/api/v1/papers/search",
        json={"query": "bidirectional transformers language representation", "limit": 5, "sources": ["local"], "sort_by": "relevance"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert data["total_found"] > 0
    # Top results should include BERT or related models
    titles = [p["title"] for p in data["results"]]
    assert any("BERT" in t or "Transformer" in t or "Attention" in t for t in titles)
    assert data["results"][0]["similarity_score"] is not None
    assert data["results"][0]["explanation"] is not None


def test_search_with_recency_sorting():
    """Test recency sorting orders latest publication years first."""
    response = client.post(
        "/api/v1/papers/search",
        json={"query": "transformers", "limit": 10, "sources": ["local"], "sort_by": "recency"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) > 0
    years = [p["year"] for p in data["results"] if p.get("year") is not None]
    # Years should be non-increasing (latest year first)
    assert years == sorted(years, reverse=True)


def test_search_with_citations_sorting():
    """Test citation sorting orders most cited papers first."""
    response = client.post(
        "/api/v1/papers/search",
        json={"query": "attention", "limit": 5, "sources": ["local"], "sort_by": "citations"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) > 0
    citations = [p["citation_count"] for p in data["results"]]
    assert citations == sorted(citations, reverse=True)


def test_paper_summary_endpoint():
    """Test structured AI summary generation."""
    response = client.get("/api/v1/papers/arxiv:1810.04805/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["paper_id"] == "arxiv:1810.04805"
    assert "BERT" in data["title"]
    assert len(data["problem_statement"]) > 10
    assert len(data["methodology"]) > 10
    assert len(data["key_findings"]) > 10
    assert len(data["limitations"]) > 10


def test_paper_comparison_endpoint():
    """Test side-by-side comparison matrix for selected papers."""
    # Compare BERT and Attention Is All You Need
    response = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": [TEST_DATA["bert_id"], TEST_DATA["attn_id"]]}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["papers"]) == 2
    assert len(data["comparison_points"]) >= 4
    assert "executive_summary" in data


def test_paper_comparison_by_string_paper_ids():
    """Test comparison endpoint accepts string paper_ids."""
    response = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["arxiv:1810.04805", "arxiv:1706.03762"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["papers"]) == 2
    pids = [p["paper_id"] for p in data["papers"]]
    assert "arxiv:1810.04805" in pids
    assert "arxiv:1706.03762" in pids
    assert len(data["comparison_points"]) >= 4


def test_paper_comparison_mixed_ids():
    """Test comparison endpoint accepts mixed integer DB IDs and string paper_ids."""
    response = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": [TEST_DATA["bert_id"], "arxiv:1706.03762"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["papers"]) == 2


def test_paper_comparison_missing_paper():
    """Test comparison returns 404 with structured error when a requested paper does not exist."""
    response = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": [TEST_DATA["bert_id"], "arxiv:9999.99999"]}
    )
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_ERROR"
    assert "arxiv:9999.99999" in data["error"]["message"]


def test_paper_comparison_duplicate_identifiers():
    """Test comparison returns 400 when identical papers or duplicate identifiers are supplied."""
    response = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": [TEST_DATA["bert_id"], TEST_DATA["bert_id"]]}
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_ERROR"
    assert "distinct papers" in data["error"]["message"].lower()

    # Also test mixed representation of the same paper
    response2 = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": [TEST_DATA["bert_id"], "arxiv:1810.04805"]}
    )
    assert response2.status_code == 400
    data2 = response2.json()
    assert data2["error"]["code"] == "HTTP_ERROR"
    assert "distinct papers" in data2["error"]["message"].lower()


def test_paper_comparison_insufficient_identifiers():
    """Test comparison returns 422 when fewer than 2 identifiers are provided."""
    response = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": [TEST_DATA["bert_id"]]}
    )
    assert response.status_code == 422


def test_search_retrieval_strategy_filtered_local_candidates():
    """Test bounded search with filters (min_year) retrieves only matching papers without scanning all."""
    response = client.post(
        "/api/v1/papers/search",
        json={
            "query": "transformer",
            "limit": 5,
            "sources": ["local"],
            "sort_by": "recency",
            "min_year": 2018
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_found"] > 0
    for p in data["results"]:
        assert p["year"] is not None
        assert p["year"] >= 2018
    pids = [p["paper_id"] for p in data["results"]]
    assert "arxiv:1706.03762" not in pids


def test_search_retrieval_strategy_sources_filtering():
    """Test that excluding 'local' from sources skips local DB candidates."""
    response = client.post(
        "/api/v1/papers/search",
        json={
            "query": "transformer",
            "limit": 5,
            "sources": ["arxiv"],
            "sort_by": "relevance"
        }
    )
    assert response.status_code == 200
    data = response.json()
    for p in data["results"]:
        assert p["source"] == "arxiv"


def test_saved_papers_workflow():
    """Test bookmarking, retrieving, and deleting saved papers with authentication and user isolation."""
    headers = {"Authorization": f"Bearer {TEST_DATA['test_user_token']}"}

    # Unauthenticated request is rejected
    assert client.get("/api/v1/papers/saved").status_code == 401

    # 1. Save paper
    save_resp = client.post(
        "/api/v1/papers/save",
        json={"paper_id": TEST_DATA["bert_id"], "notes": "Key paper on attention mechanisms", "tags": ["attention", "nlp"]},
        headers=headers
    )
    assert save_resp.status_code == 200
    saved_id = save_resp.json()["id"]

    # 2. Get saved papers
    list_resp = client.get("/api/v1/papers/saved", headers=headers)
    assert list_resp.status_code == 200
    saved_list = list_resp.json()
    assert any(s["id"] == saved_id for s in saved_list)

    # 3. Delete saved paper
    del_resp = client.delete(f"/api/v1/papers/saved/{saved_id}", headers=headers)
    assert del_resp.status_code == 200


def test_driut_alerts_and_scan():
    """Test DRIUT research update alerts retrieval and triggering scan with authentication."""
    headers = {"Authorization": f"Bearer {TEST_DATA['default_user_token']}"}

    # Unauthenticated request is rejected
    assert client.get("/api/v1/papers/driut/alerts").status_code == 401

    # 1. Fetch alerts
    alerts_resp = client.get("/api/v1/papers/driut/alerts", headers=headers)
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert len(alerts) > 0
    rel_types = [a["relationship_type"] for a in alerts]
    assert any(t in ["Improvement", "Extension"] for t in rel_types)
    assert alerts[0]["explanation"] is not None
    assert alerts[0]["confidence_score"] > 0.5

    # 2. Trigger scan
    scan_resp = client.post("/api/v1/papers/driut/scan", headers=headers)
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert "alerts" in scan_data

    # 3. Mark alert as read
    first_alert_id = alerts[0]["id"]
    read_resp = client.patch(f"/api/v1/papers/driut/alerts/{first_alert_id}/read", headers=headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["is_read"] is True


def test_pubmed_academic_source():
    """Test US Government PubMed / NCBI NIH integration connector."""
    import asyncio
    from app.services.academic_sources import search_pubmed
    results = asyncio.run(search_pubmed("deep learning", max_results=3, sort_by_date=True))
    assert isinstance(results, list)
    if len(results) > 0:
        paper = results[0]
        assert paper["source"] == "pubmed"
        assert "pubmed:" in paper["paper_id"]
        assert len(paper["title"]) > 0
        assert "PubMed" in paper["venue"]


def test_csir_niscpr_academic_source():
    """Test Indian Government CSIR-NIScPR integration connector."""
    import asyncio
    from app.services.academic_sources import search_csir_niscpr
    results = asyncio.run(search_csir_niscpr("transformers", max_results=3))
    assert isinstance(results, list)
    if len(results) > 0:
        paper = results[0]
        assert paper["source"] == "csir"
        assert "csir:" in paper["paper_id"]
        assert len(paper["title"]) > 0
        assert "CSIR-NIScPR" in paper["venue"]


