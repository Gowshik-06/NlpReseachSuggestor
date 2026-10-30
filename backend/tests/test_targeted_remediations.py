"""
Targeted regression tests for the 6 ResearchLens remediations:
1. PubMed electronic vs. scheduled print publication date interpretation.
2. Search ordering defaults (relevance vs. recency).
3. Chronology-aware DRIUT relationship classification.
4. Forthcoming / scheduled publication handling in research timelines.
5. Synthetic placeholder abstract detection and summary evidence safety.
6. Semantic search relevance floor and out-of-domain query filtration.

Reference Date for deterministic evaluation: 2026-10-18.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from app.services.academic_sources import parse_pubmed_dates, search_pubmed
from app.schemas.paper import SearchQueryRequest
from app.services.recommendation_engine import (
    SEMANTIC_RELEVANCE_FLOOR,
    _has_lexical_match,
    generate_recommendation_explanation,
    execute_recommendation_search,
)
from app.services.driut_service import (
    extract_effective_publication_year,
    classify_relationship_evidence,
)
from app.services.evidence_service import (
    is_synthetic_placeholder_abstract,
    extract_evidence_from_text,
    extract_and_persist_paper_evidence,
)
from app.services.summary_service import generate_paper_summary
from app.services.evolution_service import build_research_timeline
from app.models.paper import Paper
from app.db.session import SessionLocal


# ==============================================================================
# FIX 1: PubMed Publication Date Interpretation
# ==============================================================================

def test_pubmed_advance_article_epub_before_print():
    """
    Paper electronically published in 2026 but assigned to a 2027 print issue.
    Must use 2026 electronic publication year for ranking while preserving 2027 print date.
    """
    p = {
        "pubdate": "2027 Jan",
        "epubdate": "2026 Jul 15",
        "source": "Neural Networks",
    }
    date_info = parse_pubmed_dates(p, reference_year=2026)
    assert date_info["year"] == 2026
    assert date_info["epub_year"] == 2026
    assert date_info["print_year"] == 2027
    assert date_info["publication_status"] == "ahead_of_print"
    assert date_info["pubdate"] == "2027 Jan"
    assert date_info["epubdate"] == "2026 Jul 15"


def test_pubmed_forthcoming_scheduled_publication():
    """
    Legitimate future publication scheduled for 2027 with no prior electronic release.
    Preserves forthcoming classification without treating as elapsed history.
    """
    p = {
        "pubdate": "2027 Mar",
        "epubdate": "",
        "source": "Nature Medicine",
    }
    date_info = parse_pubmed_dates(p, reference_year=2026)
    assert date_info["year"] == 2027
    assert date_info["print_year"] == 2027
    assert date_info["publication_status"] == "forthcoming"


def test_pubmed_standard_completed_publication():
    """Standard past publication has status 'published'."""
    p = {
        "pubdate": "2023 Oct",
        "epubdate": "2023 Sep 10",
        "source": "Cell",
    }
    date_info = parse_pubmed_dates(p, reference_year=2026)
    assert date_info["year"] == 2023
    assert date_info["publication_status"] == "published"


def test_pubmed_missing_and_malformed_dates():
    """Safe fallback on missing, incomplete, or malformed date fields without crash."""
    # Malformed strings
    p_malformed = {"pubdate": "Spring/Summer", "epubdate": "InvalidDate"}
    info1 = parse_pubmed_dates(p_malformed, reference_year=2026)
    assert info1["year"] is None
    assert info1["publication_status"] == "unknown"

    # Completely missing dates
    p_empty = {}
    info2 = parse_pubmed_dates(p_empty, reference_year=2026)
    assert info2["year"] is None
    assert info2["publication_status"] == "unknown"


@pytest.mark.anyio
async def test_search_pubmed_advance_venue_annotation():
    """Async search_pubmed annotates Advance Article venue and returns provenance."""
    mock_search = MagicMock()
    mock_search.status_code = 200
    mock_search.headers = {"content-type": "application/json"}
    mock_search.json.return_value = {"esearchresult": {"idlist": ["99999999"]}}

    mock_sum = MagicMock()
    mock_sum.status_code = 200
    mock_sum.headers = {"content-type": "application/json"}
    mock_sum.json.return_value = {
        "result": {
            "99999999": {
                "title": "Bioinformatics Innovations in 2026",
                "authors": [{"name": "Smith J"}],
                "source": "Bioinformatics",
                "pubdate": "2027 Feb",
                "epubdate": "2026 Aug 20",
                "articleids": [{"idtype": "doi", "value": "10.1093/bioinf/999"}],
            }
        }
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=[mock_search, mock_sum]):
        results = await search_pubmed("bioinformatics innovations")
        assert len(results) == 1
        item = results[0]
        assert item["year"] == 2026
        assert item["publication_status"] == "ahead_of_print"
        assert "Advance Article; Scheduled Print: 2027 Feb" in item["venue"]
        assert item["pubdate"] == "2027 Feb"
        assert item["epubdate"] == "2026 Aug 20"


def test_pubmed_dynamic_and_year_transition_policy():
    """
    Test that parse_pubmed_dates dynamically uses current year when reference_year is None,
    and correctly handles calendar year transitions without hardcoded ceilings.
    """
    from datetime import datetime, timezone
    current_utc_year = datetime.now(timezone.utc).year

    # 1. Calling with reference_year=None dynamically resolves to current UTC year
    p_now = {"pubdate": f"{current_utc_year} May", "epubdate": f"{current_utc_year} Apr 1"}
    info_now = parse_pubmed_dates(p_now, reference_year=None)
    assert info_now["reference_year"] == current_utc_year
    assert info_now["year"] == current_utc_year
    assert info_now["publication_status"] == "published"

    # 2. Simulated transition to year 2027:
    # An article with epub in 2027 and print in 2027 should be 'published', NOT 'forthcoming'
    p_2027 = {"pubdate": "2027 May 10", "epubdate": "2027 Feb 1"}
    info_2027 = parse_pubmed_dates(p_2027, reference_year=2027)
    assert info_2027["year"] == 2027
    assert info_2027["publication_status"] == "published"

    # 3. In 2027, an article with epub in 2027 and print in 2028 is 'ahead_of_print'
    p_2027_aop = {"pubdate": "2028 Jan", "epubdate": "2027 Nov 15"}
    info_aop = parse_pubmed_dates(p_2027_aop, reference_year=2027)
    assert info_aop["year"] == 2027
    assert info_aop["publication_status"] == "ahead_of_print"

    # 4. In 2027, an article scheduled for 2029 is 'forthcoming'
    p_2029 = {"pubdate": "2029 Mar", "epubdate": "2029 Mar"}
    info_2029 = parse_pubmed_dates(p_2029, reference_year=2027)
    assert info_2029["year"] == 2029
    assert info_2029["publication_status"] == "forthcoming"

    # 5. Transition to year 2028:
    # Article pubmed:42635983 (epub 2028 Aug 17, print 2028 Aug 17) transitions from 'forthcoming' to 'published'
    p_42635983 = {"pubdate": "2028 Aug 17", "epubdate": "2028 Aug 17"}
    info_in_2026 = parse_pubmed_dates(p_42635983, reference_year=2026)
    assert info_in_2026["publication_status"] == "forthcoming"
    info_in_2028 = parse_pubmed_dates(p_42635983, reference_year=2028)
    assert info_in_2028["publication_status"] == "published"
    assert info_in_2028["year"] == 2028


# ==============================================================================
# FIX 2 & FIX 6: Default Search Ordering & Semantic Relevance Floor
# ==============================================================================

def test_search_query_request_defaults_to_relevance():
    """Default sort_by parameter in SearchQueryRequest must be 'relevance'."""
    req = SearchQueryRequest(query="machine learning")
    assert req.sort_by == "relevance"


def test_has_lexical_match_helper():
    """Test lexical matching preserves query words in title and abstract."""
    paper = {
        "title": "A Survey of Graph Neural Networks",
        "abstract": "We review deep learning approaches for graphs.",
    }
    assert _has_lexical_match(paper, "graph neural networks", ["graph", "neural"]) is True
    assert _has_lexical_match(paper, "ancient roman architecture", ["ancient", "roman", "architecture"]) is False


def test_semantic_relevance_floor_value():
    """Relevance floor for pure semantic retrieval must be set to 0.835."""
    assert SEMANTIC_RELEVANCE_FLOOR == 0.835


@pytest.mark.anyio
async def test_empty_query_returns_immediately():
    """Empty search input returns an empty response immediately without DB/FAISS overhead."""
    session = SessionLocal()
    try:
        req = SearchQueryRequest(query="   ")
        resp = await execute_recommendation_search(session, req)
        assert resp.total_found == 0
        assert resp.results == []
        assert resp.query == ""
    finally:
        session.close()


@pytest.mark.anyio
async def test_unrelated_query_ancient_roman_architecture_filtered():
    """
    Unrelated query 'ancient Roman architecture' with no keyword match and sub-floor vector similarity
    must return an empty or zero-result response rather than dumping irrelevant papers.
    """
    session = SessionLocal()
    try:
        mock_faiss = MagicMock()
        mock_faiss.search.return_value = [
            ({"paper_id": "test:math01", "title": "Indian Mathematical Astronomy", "abstract": "Ancient calculations"}, 0.817),
            ({"paper_id": "test:math02", "title": "Historical Numerical Tables", "abstract": "Calculus history"}, 0.803),
        ]

        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss):
            req = SearchQueryRequest(query="ancient Roman architecture", sort_by="relevance")
            resp = await execute_recommendation_search(session, req)
            assert resp.total_found == 0
            assert len(resp.results) == 0
    finally:
        session.close()


@pytest.mark.anyio
async def test_lexical_match_preserved_below_semantic_floor():
    """
    A paper with a verified keyword match in title/abstract is preserved even if semantic score is 0.65.
    Distinguishes pure semantic retrieval from hybrid keyword/semantic search.
    """
    session = SessionLocal()
    try:
        test_paper = Paper(
            paper_id="test:chem_gnn_001",
            title="Graph Neural Networks for Molecular Chemistry",
            abstract="We evaluate message-passing GNNs on chemical benchmarks.",
            authors=["Alice Chemist"],
            venue="J. Chem. Inf.",
            year=2024,
            source="local",
            citation_count=45,
        )
        session.add(test_paper)
        session.commit()

        mock_faiss = MagicMock()
        mock_faiss.search.return_value = [
            ({"paper_id": "test:chem_gnn_001", "title": test_paper.title, "abstract": test_paper.abstract}, 0.65)
        ]

        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss):
            req = SearchQueryRequest(query="Graph Neural Networks Chemistry", sort_by="relevance")
            resp = await execute_recommendation_search(session, req)
            assert resp.total_found >= 1
            assert any(p.paper_id == "test:chem_gnn_001" for p in resp.results)
    finally:
        session.query(Paper).filter(Paper.paper_id == "test:chem_gnn_001").delete()
        session.commit()
        session.close()


# ==============================================================================
# FIX 3: Chronology-Aware DRIUT Relationships
# ==============================================================================

def test_driut_effective_publication_year_extraction():
    """Test extract_effective_publication_year across various formats."""
    p_adv = {
        "year": 2026,
        "venue": "🏛️ PubMed: Neural Netw (Advance Article; Scheduled Print: 2027 Jan)",
    }
    y1, is_sched1, _ = extract_effective_publication_year(p_adv)
    assert y1 == 2026
    assert is_sched1 is False

    p_sched = {
        "year": 2027,
        "venue": "🏛️ PubMed: Neural Netw (Forthcoming Issue: 2027 Jan)",
    }
    y2, is_sched2, _ = extract_effective_publication_year(p_sched)
    assert y2 == 2027
    assert is_sched2 is True

    p_epub = {"year": 2027, "epub_year": 2026}
    y3, is_sched3, _ = extract_effective_publication_year(p_epub)
    assert y3 == 2026
    assert is_sched3 is False

    p_none = {"year": None}
    y4, is_sched4, _ = extract_effective_publication_year(p_none)
    assert y4 is None


def test_driut_chronology_later_improves_earlier():
    """Scenario 1: Later candidate (2026) improving earlier baseline (2024). Valid!"""
    saved = {
        "paper_id": "base:001",
        "title": "Baseline Convolutional Architecture for Image Processing",
        "abstract": "We introduce CNN baseline achieving 82% accuracy on ImageNet.",
        "year": 2024,
    }
    cand = {
        "paper_id": "cand:001",
        "title": "Improved Residual Attention Architecture for Image Processing",
        "abstract": "Our approach outperforms the baseline method by 8% accuracy on ImageNet.",
        "year": 2026,
    }
    res = classify_relationship_evidence(saved, cand)
    assert res.is_supported is True
    assert res.relationship_type in ["Improvement", "Extension"]


def test_driut_chronology_earlier_cannot_improve_later():
    """Scenario 2: Earlier candidate (2026) incorrectly appearing to improve later baseline (2027). Must be rejected!"""
    saved_future = {
        "paper_id": "future:001",
        "title": "Scheduled 2027 Quantum Attention Neural Network",
        "abstract": "We develop a quantum neural framework for complex physics simulations.",
        "year": 2027,
        "publication_status": "forthcoming",
    }
    cand_past = {
        "paper_id": "past:001",
        "title": "Faster Quantum Computing Implementation in 2026",
        "abstract": "Our model outperforms prior quantum methods with significant performance gains.",
        "year": 2026,
    }
    res = classify_relationship_evidence(saved_future, cand_past)
    assert res.is_supported is False
    assert res.relationship_type is None
    assert "Chronological conflict" in (res.uncertainty_warning or "")


def test_driut_chronology_equal_publication_years():
    """Scenario 3: Equal publication years (2026 vs 2026) with incomplete dates permitted with uncertainty note."""
    saved = {
        "paper_id": "same:001",
        "title": "Deep Transformer Foundations in 2026",
        "abstract": "We evaluate transformer architectures on standard benchmarks.",
        "year": 2026,
    }
    cand = {
        "paper_id": "same:002",
        "title": "Sparse Attention Transformer Extension in 2026",
        "abstract": "We extend the deep transformer architecture with linear sparse attention mechanisms.",
        "year": 2026,
    }
    res = classify_relationship_evidence(saved, cand)
    assert res.is_supported is True
    assert res.relationship_type == "Extension"
    assert "Both papers share publication year 2026" in (res.uncertainty_warning or "")


def test_driut_chronology_missing_dates_handled():
    """Scenario 4: Missing publication dates handled safely without crash and with transparent uncertainty."""
    saved = {
        "paper_id": "nodate:001",
        "title": "Foundational Graph Representation Learning",
        "abstract": "Graph embedding framework evaluated across citation networks.",
        "year": None,
    }
    cand = {
        "paper_id": "nodate:002",
        "title": "Scalable Graph Neural Networks for Large Graphs",
        "abstract": "We extend foundational graph representation models to billion-edge graphs.",
        "year": None,
    }
    res = classify_relationship_evidence(saved, cand)
    assert res.is_supported is True
    assert res.relationship_type == "Extension"
    assert "Publication date is unrecorded in catalog metadata" in (res.uncertainty_warning or "")


def test_driut_chronology_advance_print_issue_preserves_valid_relationship():
    """
    Scenario 5: Baseline has scheduled print year 2027, but was published electronically in 2025.
    Candidate (2026) improving baseline must NOT be rejected merely because of scheduled print date.
    """
    saved_advance = {
        "paper_id": "adv:001",
        "title": "Early Electronic Release of Biomedical Language Model",
        "abstract": "We introduce a biomedical pretrained language model evaluated on PubMedQA.",
        "year": 2025,
        "epub_year": 2025,
        "venue": "🏛️ PubMed: Comput Biol (Advance Article; Scheduled Print: 2027 Jan)",
    }
    cand = {
        "paper_id": "cand:002",
        "title": "Enhanced Biomedical Language Model with Clinical Knowledge",
        "abstract": "We extend the biomedical pretrained language model with clinical structured ontologies.",
        "year": 2026,
    }
    res = classify_relationship_evidence(saved_advance, cand)
    assert res.is_supported is True
    assert res.relationship_type in ["Extension", "Improvement"]


def test_driut_legitimate_alternative_classification():
    """Scenario 6: Legitimate Alternative classification across concurrent paradigms."""
    paper1 = {
        "paper_id": "alt:001",
        "title": "State Space Models for Sequential Language Modeling",
        "abstract": "We propose state-space models as an alternative architecture to self-attention.",
        "year": 2026,
    }
    paper2 = {
        "paper_id": "alt:002",
        "title": "Linear Recurrent Units for Long Context Sequences",
        "abstract": "An alternative paradigm replacing quadratic attention with linear recurrent recurrence.",
        "year": 2026,
    }
    res = classify_relationship_evidence(paper1, paper2)
    assert res.is_supported is True
    assert res.relationship_type == "Alternative"


# ==============================================================================
# FIX 4: Timeline Handling for Forthcoming Publications
# ==============================================================================

def test_timeline_forthcoming_publication_qualifications():
    """
    Deterministic tests using reference date 2026-10-18.
    Years > 2026 must be labeled '(Forthcoming / Scheduled Issue)' and annotated with date uncertainty notes.
    """
    session = SessionLocal()
    try:
        p_future = Paper(
            paper_id="test:future_paper_2027",
            title="Future Advances in Holographic Neural Interfaces",
            abstract="We develop theoretical frameworks for holographic neural interfaces.",
            authors=["Dr. Future"],
            venue="IEEE Trans. Cybernetics",
            year=2027,
            source="local",
            citation_count=0,
        )
        p_current = Paper(
            paper_id="test:current_paper_2026",
            title="Current Advances in Transformer Quantization",
            abstract="We present 4-bit transformer quantization achieving 99% accuracy.",
            authors=["Dr. Current"],
            venue="NeurIPS 2026",
            year=2026,
            source="local",
            citation_count=12,
        )
        session.add_all([p_future, p_current])
        session.commit()

        timeline = build_research_timeline(session, topic="Neural", limit=10)
        
        # Check year groups
        year_labels = {g.year: g.year_label for g in timeline.timeline}
        assert 2027 in year_labels
        assert year_labels[2027] == "2027 (Forthcoming / Scheduled Issue)"
        if 2026 in year_labels:
            assert year_labels[2026] == "2026"

        # Check paper uncertainty note
        future_tp = next((p for g in timeline.timeline for p in g.papers if p.paper_id == "test:future_paper_2027"), None)
        assert future_tp is not None
        assert future_tp.date_uncertainty_note is not None
        assert "Forthcoming / Scheduled publication" in future_tp.date_uncertainty_note
    finally:
        session.query(Paper).filter(Paper.paper_id.in_(["test:future_paper_2027", "test:current_paper_2026"])).delete()
        session.commit()
        session.close()


# ==============================================================================
# FIX 5: Synthetic Placeholder Abstract Guard & Summary Safety
# ==============================================================================

def test_synthetic_placeholder_detection():
    """Detect known legacy PubMed synthetic placeholder patterns accurately."""
    placeholder_text1 = "Biomedical & computational research paper indexed by the US National Library of Medicine (PubMed / NIH). Published in Neural Netw (2027 Jan)."
    placeholder_text2 = "Biomedical & computational research paper indexed by the US National Library of Medicine (PubMed / NIH). Published in Comput Biol Chem (2026 Dec)."
    assert is_synthetic_placeholder_abstract(placeholder_text1) is True
    assert is_synthetic_placeholder_abstract(placeholder_text2) is True
    assert is_synthetic_placeholder_abstract("Abstract unavailable.") is True
    assert is_synthetic_placeholder_abstract("No abstract available") is True


def test_genuine_abstracts_not_flagged_as_placeholders():
    """Ensure genuine scientific abstracts mentioning PubMed, NLM, or biomedical computing are NOT flagged."""
    genuine_nlp = (
        "We evaluate pretrained language models on medical question answering datasets from PubMed and the "
        "US National Library of Medicine. Our experiments show state-of-the-art accuracy of 89.2% on PubMedQA."
    )
    genuine_ml = "In this work, we propose a novel transformer architecture for sparse graph representation."
    assert is_synthetic_placeholder_abstract(genuine_nlp) is False
    assert is_synthetic_placeholder_abstract(genuine_ml) is False
    assert is_synthetic_placeholder_abstract("") is False
    assert is_synthetic_placeholder_abstract(None) is False


def test_evidence_extraction_rejects_placeholder_abstract():
    """extract_evidence_from_text must extract 0 claims from synthetic placeholder text."""
    placeholder_text = "Biomedical & computational research paper indexed by the US National Library of Medicine (PubMed / NIH). Published in Neural Netw (2027 Jan)."
    claims, missing = extract_evidence_from_text(placeholder_text, source_type="abstract")
    assert len(claims) == 0
    assert len(missing) == 9


def test_paper_summary_rejects_placeholder_abstract():
    """generate_paper_summary returns honest unavailable-evidence summary without hallucinating claims."""
    paper = {
        "paper_id": "pubmed:33333333",
        "title": "A Computational Analysis of Neural Networks",
        "abstract": "Biomedical & computational research paper indexed by the US National Library of Medicine (PubMed / NIH). Published in Neural Netw (2027 Jan).",
        "venue": "Neural Netw",
        "year": 2027,
        "citation_count": 0,
    }
    summary = generate_paper_summary(paper)
    assert "unavailable" in summary.executive_summary.lower()
    assert "unavailable" in summary.problem_statement.lower()
    assert "unavailable" in summary.methodology.lower()
    assert "unavailable" in summary.key_findings.lower()
    # Ensure AI fallback did not fabricate claims
    assert summary.ai_provider == "deterministic"
