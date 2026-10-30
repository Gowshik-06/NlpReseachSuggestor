"""
Targeted Regression Test Suite for ResearchLens Remediation:
1. DEFECT-01: Slash-containing paper IDs (Crossref/DOI) routing and resolution.
2. Issue 2: Evolution Timeline topic matching, acronym handling, undated papers, and date filters.
3. Issue 3: Search relevance vs recency ordering, future year preservation, and missing abstract integrity.

Runs with complete test isolation against temporary in-memory/SQLite fixtures.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import engine, SessionLocal, Base
from app.models.paper import Paper
from app.models.user import User
from app.core.security import create_access_token, hash_password
from app.services.evolution_service import build_research_timeline

client = TestClient(app)

CROSSREF_TEST_ID = "crossref:10.1017/9781108891530.011"
ARXIV_TEST_ID = "arxiv:2026.99999v1"


@pytest.fixture(scope="module", autouse=True)
def setup_remediation_test_fixtures():
    """Seed isolated synthetic test papers and test user in temporary database."""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    # Create test user for authenticated endpoints
    user = db.query(User).filter(User.username == "remediation_user").first()
    if not user:
        user = User(
            username="remediation_user",
            email="remediation@test.local",
            hashed_password=hash_password("SafeDevPassword123!"),
            full_name="Remediation Test User"
        )
        db.add(user)

    # Seed Crossref slash ID paper
    p_crossref = db.query(Paper).filter(Paper.paper_id == CROSSREF_TEST_ID).first()
    if not p_crossref:
        p_crossref = Paper(
            paper_id=CROSSREF_TEST_ID,
            title="Transformers in Language Processing",
            abstract="Foundational architecture of multi-head self-attention mechanisms in deep learning.",
            authors=["Alice Smith", "Bob Jones"],
            venue="Cambridge University Press",
            year=2022,
            doi="10.1017/9781108891530.011",
            source="crossref",
            citation_count=450
        )
        db.add(p_crossref)

    # Seed standard arXiv paper
    p_arxiv = db.query(Paper).filter(Paper.paper_id == ARXIV_TEST_ID).first()
    if not p_arxiv:
        p_arxiv = Paper(
            paper_id=ARXIV_TEST_ID,
            title="Deep Neural Networks for Sequence Modeling",
            abstract="An in-depth study of sequence modeling using recurrent neural networks and transformers.",
            authors=["Carol Danvers"],
            venue="arXiv",
            year=2023,
            source="arxiv",
            citation_count=120
        )
        db.add(p_arxiv)

    # Seed papers for timeline and relevance testing
    test_papers = [
        Paper(
            paper_id="test:aiml:1990",
            title="Interacting Neural Populations in Early Machine Learning",
            abstract="Mathematical models of neural networks and machine learning representations.",
            authors=["John Hopfield"],
            venue="Neural Computation",
            year=1990,
            source="local",
            citation_count=300
        ),
        Paper(
            paper_id="test:aiml:2018",
            title="BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
            abstract="We introduce a new language representation model for natural language processing and machine learning.",
            authors=["Jacob Devlin"],
            venue="NAACL",
            year=2018,
            source="arxiv",
            citation_count=15000
        ),
        Paper(
            paper_id="test:aiml:2026",
            title="Quantum Machine Learning and Artificial Intelligence Foundations",
            abstract="A comprehensive exploration of artificial intelligence algorithms deployed on quantum hardware.",
            authors=["David Deutsch"],
            venue="Nature AI",
            year=2026,
            source="local",
            citation_count=15
        ),
        Paper(
            paper_id="test:aiml:2027_empty_abs",
            title="Stage-Aware Deep Learning with Adversarial Data Synthesis",
            abstract="",  # Intentionally empty abstract (ahead-of-print PubMed style)
            authors=["Eve Online"],
            venue="PubMed Pre-Print",
            year=2027,  # Legitimate future publication year
            source="pubmed",
            citation_count=0
        ),
        Paper(
            paper_id="test:aiml:undated",
            title="Figure 3: Multi-Attention Structure in Machine Learning Models",
            abstract="Diagram of machine learning and neural network attention mechanism without publication date.",
            authors=[],
            venue="",
            year=None,  # Undated
            source="crossref",
            citation_count=0
        ),
        Paper(
            paper_id="test:unrelated:bio",
            title="Photosynthesis Dynamics in Extreme Desert Flora",
            abstract="Study of chlorophyll fluorescence and chloroplast dynamics in desert cacti.",
            authors=["Botanist Bob"],
            venue="Journal of Botany",
            year=2021,
            source="local",
            citation_count=42
        ),
    ]

    for tp in test_papers:
        if not db.query(Paper).filter(Paper.paper_id == tp.paper_id).first():
            db.add(tp)

    db.commit()
    db.close()
    yield


# ==============================================================================
# DEFECT-01: Slash-Containing Paper ID Tests
# ==============================================================================

def test_summary_with_percent_encoded_slash_id():
    """Verify that encoded slash IDs successfully route to summary endpoint."""
    encoded_id = "crossref%3A10.1017%2F9781108891530.011"
    resp = client.get(f"/api/v1/papers/{encoded_id}/summary")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["paper_id"] == CROSSREF_TEST_ID
    assert "Transformers" in data["title"]
    assert "executive_summary" in data


def test_summary_with_raw_slash_id():
    """Verify that raw unencoded slash IDs successfully route to summary endpoint."""
    resp = client.get(f"/api/v1/papers/{CROSSREF_TEST_ID}/summary")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["paper_id"] == CROSSREF_TEST_ID


def test_evidence_with_slash_id():
    """Verify that slash IDs successfully route to evidence endpoint."""
    encoded_id = "crossref%3A10.1017%2F9781108891530.011"
    resp = client.get(f"/api/v1/papers/{encoded_id}/evidence")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["paper_id"] == CROSSREF_TEST_ID
    assert "evidence" in data
    assert "verification_summary" in data


def test_evidence_verify_with_slash_id():
    """Verify that slash IDs route to /{paper_id:path}/evidence/verify without shadowing."""
    resp = client.get(f"/api/v1/papers/{CROSSREF_TEST_ID}/evidence/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == CROSSREF_TEST_ID
    assert "all_valid" in data


def test_evidence_extract_with_slash_id():
    """Verify that slash IDs route to /{paper_id:path}/evidence/extract with auth."""
    # Without auth -> 401
    resp_unauth = client.post(f"/api/v1/papers/{CROSSREF_TEST_ID}/evidence/extract")
    assert resp_unauth.status_code == 401

    # With auth -> 200
    token = create_access_token("remediation_user")
    resp_auth = client.post(
        f"/api/v1/papers/{CROSSREF_TEST_ID}/evidence/extract",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_auth.status_code == 200
    data = resp_auth.json()
    assert data["paper_id"] == CROSSREF_TEST_ID


def test_ordinary_paper_ids_unaffected():
    """Verify ordinary paper IDs without slashes continue to function identically."""
    resp_summary = client.get(f"/api/v1/papers/{ARXIV_TEST_ID}/summary")
    assert resp_summary.status_code == 200
    assert resp_summary.json()["paper_id"] == ARXIV_TEST_ID

    resp_evidence = client.get(f"/api/v1/papers/{ARXIV_TEST_ID}/evidence")
    assert resp_evidence.status_code == 200
    assert resp_evidence.json()["paper_id"] == ARXIV_TEST_ID


def test_nonexistent_paper_ids_return_clean_404():
    """Verify nonexistent IDs (both slash-containing and ordinary) return application 404."""
    resp_slash = client.get("/api/v1/papers/crossref:10.9999/nonexistent.doi/summary")
    assert resp_slash.status_code == 404
    assert "not found" in resp_slash.json().get("error", {}).get("message", "").lower()

    resp_ordinary = client.get("/api/v1/papers/arxiv:9999.00000/summary")
    assert resp_ordinary.status_code == 404
    assert "not found" in resp_ordinary.json().get("error", {}).get("message", "").lower()


def test_neighboring_routes_not_shadowed():
    """Verify neighboring endpoints under /papers/ remain reachable and unshadowed."""
    resp_search = client.post("/api/v1/papers/search", json={"query": "test"})
    assert resp_search.status_code == 200

    resp_saved = client.get("/api/v1/papers/saved")
    assert resp_saved.status_code == 401  # Authenticated route reachable

    resp_alerts = client.get("/api/v1/papers/driut/alerts")
    assert resp_alerts.status_code == 401  # Authenticated route reachable


# ==============================================================================
# Issue 2: Evolution Timeline Tests
# ==============================================================================

def test_evolution_timeline_aiml_topic():
    """Verify that topic 'aiml' matches relevant AI/ML papers and reports non-zero total."""
    db: Session = SessionLocal()
    try:
        timeline = build_research_timeline(db, topic="aiml", limit=20)
        assert timeline.total_papers_examined > 0, "Evolution timeline for 'aiml' should find relevant papers"
        assert timeline.status != "empty"
        assert timeline.total_dated_papers >= 1
        # Check that unrelated botany paper is excluded
        examined_titles = [
            p.title for period in timeline.timeline for p in period.papers
        ]
        assert not any("Photosynthesis" in t for t in examined_titles)
        # Check that AI papers are included
        assert any("Neural" in t or "Deep Learning" in t or "BERT" in t for t in examined_titles)
    finally:
        db.close()


def test_evolution_timeline_unrelated_topic():
    """Verify that an unrelated topic with zero matches cleanly returns empty status."""
    db: Session = SessionLocal()
    try:
        timeline = build_research_timeline(db, topic="astronomy", limit=20)
        assert timeline.total_papers_examined == 0
        assert timeline.status.value == "empty"
        assert len(timeline.timeline) == 0
    finally:
        db.close()


def test_evolution_timeline_date_range_filter():
    """Verify start_year and end_year filtering in evolution timeline."""
    db: Session = SessionLocal()
    try:
        timeline = build_research_timeline(db, topic="aiml", start_year=2020, end_year=2026, limit=20)
        for period in timeline.timeline:
            for p in period.papers:
                if p.year is not None:
                    assert 2020 <= p.year <= 2026, f"Paper year {p.year} outside [2020, 2026]"
    finally:
        db.close()


def test_evolution_timeline_handles_undated_papers():
    """Verify undated papers are classified transparently without crashing."""
    db: Session = SessionLocal()
    try:
        timeline = build_research_timeline(db, topic="aiml", limit=20)
        assert timeline.total_undated_papers >= 1
        assert timeline.total_papers_examined == timeline.total_dated_papers + timeline.total_undated_papers
    finally:
        db.close()


# ==============================================================================
# Issue 3: Search Relevance and Metadata Integrity Tests
# ==============================================================================

def test_search_sorting_recency_vs_relevance():
    """Verify recency sorts by year descending while relevance sorts by similarity score."""
    # 1. Recency sort
    resp_recency = client.post(
        "/api/v1/papers/search",
        json={"query": "deep learning", "sort_by": "recency", "limit": 10}
    )
    assert resp_recency.status_code == 200
    results = resp_recency.json()["results"]
    years = [r["year"] for r in results if r.get("year") is not None]
    assert years == sorted(years, reverse=True), "Recency sort must order publication years descending"

    # 2. Relevance sort
    resp_relevance = client.post(
        "/api/v1/papers/search",
        json={"query": "deep learning", "sort_by": "relevance", "limit": 10}
    )
    assert resp_relevance.status_code == 200
    results = resp_relevance.json()["results"]
    scores = [r["similarity_score"] for r in results if r.get("similarity_score") is not None]
    assert scores == sorted(scores, reverse=True), "Relevance sort must order similarity scores descending"


def test_search_preserves_future_year_and_empty_abstract():
    """Verify future publication years (2027) and genuinely empty abstracts are not fabricated."""
    resp = client.post(
        "/api/v1/papers/search",
        json={"query": "Stage-Aware Deep Learning", "limit": 5}
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    matched = [r for r in results if r["paper_id"] == "test:aiml:2027_empty_abs"]
    assert len(matched) == 1, "Should find the stage-aware paper"
    paper = matched[0]
    # Year must remain 2027 exactly
    assert paper["year"] == 2027
    # Abstract must remain empty string or None, NOT fabricated
    assert paper["abstract"] == "" or paper["abstract"] is None
