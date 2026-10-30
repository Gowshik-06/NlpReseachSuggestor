"""
Focused, isolated regression tests for Local Catalog vs Academic Provenance filter semantics (ISSUE-07).
Validates that:
1. The local PostgreSQL catalog is the primary store of already indexed papers.
2. Provenance filters ('arxiv', 'pubmed', 'csir', 'local') select the matching subsets from the catalog
   without invoking remote external APIs.
3. Multiple provenance filters return the deduplicated union of intended subsets.
4. Omitting provenance filters searches all catalog candidates.
5. External repository discovery is decoupled and only invoked when explicitly requested.
6. Zero mutation to persistent database or FAISS records.
"""
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.paper import Paper
from app.schemas.paper import SearchQueryRequest, SearchResponse
from app.services.recommendation_engine import execute_recommendation_search


@pytest.fixture
def isolated_db_session():
    """
    Creates an isolated in-memory SQLite database and session.
    Guarantees zero writes to PostgreSQL.
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed representative catalog papers across diverse provenance types
    sample_papers = [
        Paper(
            id=1,
            paper_id="arxiv:1706.03762",
            title="Attention Is All You Need",
            abstract="The Transformer model architecture relies entirely on self-attention.",
            authors=["Ashish Vaswani", "Noam Shazeer"],
            year=2017,
            citation_count=110000,
            source="arxiv"
        ),
        Paper(
            id=2,
            paper_id="pubmed:41094848",
            title="Neural Mechanisms in Deep Learning",
            abstract="An in-depth study of neural circuit representations and deep learning.",
            authors=["Jane Doe"],
            year=2021,
            citation_count=500,
            source="pubmed"
        ),
        Paper(
            id=3,
            paper_id="csir:10.56042/jsir.v79i2",
            title="Diffusion Models for Scientific Modeling",
            abstract="Investigation of fractional diffusion processes in complex systems.",
            authors=["R. Sharma"],
            year=2022,
            citation_count=120,
            source="csir"
        ),
        Paper(
            id=4,
            paper_id="crossref:10.1017/transformers",
            title="Transformers and Neural Attention",
            abstract="Foundations of transformer attention mechanisms.",
            authors=["A. Author"],
            year=2023,
            citation_count=350,
            source="crossref"
        ),
        Paper(
            id=5,
            paper_id="local:pdf_upload_001",
            title="Internal Lab Notes on Transformers and Attention",
            abstract="Local uploaded analysis on transformer fine-tuning.",
            authors=["Local Team"],
            year=2024,
            citation_count=5,
            source="local"
        ),
    ]
    session.add_all(sample_papers)
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_faiss():
    """
    Mock FAISS index to ensure zero interaction with production FAISS indices on disk.
    """
    mock_idx = MagicMock()
    mock_idx.search.return_value = []
    mock_idx.add_papers.return_value = None
    return mock_idx


def test_arxiv_provenance_filter_returns_arxiv_without_network_call(isolated_db_session, mock_faiss):
    """
    1. Local catalog contains arXiv papers; selecting 'arxiv' provenance returns them
    from the local catalog WITHOUT invoking external APIs.
    """
    async def _run():
        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock) as mock_external:

            req = SearchQueryRequest(
                query="Attention Transformer",
                sources=["arxiv"],
                limit=10,
                sort_by="relevance"
            )
            response = await execute_recommendation_search(isolated_db_session, req)

            assert response.total_found >= 1
            for p in response.results:
                assert p.source.lower() == "arxiv"
            assert any(p.paper_id == "arxiv:1706.03762" for p in response.results)
            # Ensure external search was NOT invoked
            mock_external.assert_not_called()

    asyncio.run(_run())


def test_pubmed_and_csir_provenance_filters_return_correct_subsets(isolated_db_session, mock_faiss):
    """
    2. Local catalog contains PubMed and CSIR papers; provenance filters return the correct subsets.
    """
    async def _run():
        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock) as mock_external:

            # PubMed subset
            req_pubmed = SearchQueryRequest(query="Neural", sources=["pubmed"], limit=5)
            res_pubmed = await execute_recommendation_search(isolated_db_session, req_pubmed)
            assert res_pubmed.total_found >= 1
            assert all(p.source.lower() == "pubmed" for p in res_pubmed.results)
            assert any(p.paper_id == "pubmed:41094848" for p in res_pubmed.results)

            # CSIR subset
            req_csir = SearchQueryRequest(query="Diffusion", sources=["csir"], limit=5)
            res_csir = await execute_recommendation_search(isolated_db_session, req_csir)
            assert res_csir.total_found >= 1
            assert all(p.source.lower() == "csir" for p in res_csir.results)
            assert any(p.paper_id == "csir:10.56042/jsir.v79i2" for p in res_csir.results)

            # External provider must not be called
            mock_external.assert_not_called()

    asyncio.run(_run())


def test_local_upload_papers_selected_consistently(isolated_db_session, mock_faiss):
    """
    3. Locally uploaded papers (source='local' or 'pdf_upload') are selected consistently
    when 'local' provenance is requested.
    """
    async def _run():
        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock) as mock_external:

            req_local = SearchQueryRequest(query="Transformers", sources=["local"], limit=5)
            res_local = await execute_recommendation_search(isolated_db_session, req_local)

            assert res_local.total_found >= 1
            assert all(p.source.lower() in ("local", "pdf_upload") for p in res_local.results)
            assert any(p.paper_id == "local:pdf_upload_001" for p in res_local.results)
            mock_external.assert_not_called()

    asyncio.run(_run())


def test_multiple_provenance_filters_return_union_without_duplicates(isolated_db_session, mock_faiss):
    """
    4. Selecting multiple provenance filters returns the deduplicated union of the intended subsets.
    """
    async def _run():
        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock) as mock_external:

            req_multi = SearchQueryRequest(
                query="Attention Neural",
                sources=["arxiv", "pubmed"],
                limit=10
            )
            res_multi = await execute_recommendation_search(isolated_db_session, req_multi)

            assert res_multi.total_found >= 2
            sources = {p.source.lower() for p in res_multi.results}
            assert "arxiv" in sources
            assert "pubmed" in sources
            assert "csir" not in sources
            # Verify no duplicate paper IDs
            pids = [p.paper_id for p in res_multi.results]
            assert len(pids) == len(set(pids))
            mock_external.assert_not_called()

    asyncio.run(_run())


def test_no_source_selection_does_not_discard_valid_local_candidates(isolated_db_session, mock_faiss):
    """
    5. Omitting sources (None or empty) searches the full catalog without discarding candidates.
    """
    async def _run():
        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock) as mock_external:

            req_none = SearchQueryRequest(query="Attention Neural Diffusion", sources=None, limit=10)
            res_none = await execute_recommendation_search(isolated_db_session, req_none)

            returned_sources = {p.source.lower() for p in res_none.results}
            assert "arxiv" in returned_sources
            assert "pubmed" in returned_sources
            assert "csir" in returned_sources
            mock_external.assert_not_called()

            req_empty = SearchQueryRequest(query="Attention Neural Diffusion", sources=[], limit=10)
            res_empty = await execute_recommendation_search(isolated_db_session, req_empty)
            assert res_empty.total_found == res_none.total_found
            mock_external.assert_not_called()

    asyncio.run(_run())


def test_external_discovery_invoked_only_when_explicitly_requested(isolated_db_session, mock_faiss):
    """
    6. External discovery is invoked only when enable_external_discovery=True is passed.
    """
    async def _run():
        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock) as mock_external:

            mock_external.return_value = [
                {
                    "paper_id": "arxiv:2401.99999",
                    "title": "Fresh Remote Preprint on Diffusion",
                    "abstract": "Live external discovery paper.",
                    "authors": ["Remote Author"],
                    "year": 2026,
                    "source": "arxiv",
                    "citation_count": 0
                }
            ]

            # Without explicit flag: external discovery NOT called
            req_default = SearchQueryRequest(query="Diffusion", sources=["arxiv"], enable_external_discovery=False)
            res_default = await execute_recommendation_search(isolated_db_session, req_default)
            mock_external.assert_not_called()
            assert not any(p.paper_id == "arxiv:2401.99999" for p in res_default.results)

            # With explicit flag: external discovery called
            req_live = SearchQueryRequest(query="Diffusion", sources=["arxiv"], enable_external_discovery=True)
            res_live = await execute_recommendation_search(isolated_db_session, req_live)
            mock_external.assert_called_once()
            assert any(p.paper_id == "arxiv:2401.99999" for p in res_live.results)

    asyncio.run(_run())


def test_pagination_and_ranking_remain_correct(isolated_db_session, mock_faiss):
    """
    7. Multi-mode sorting and pagination limit contracts remain intact.
    """
    async def _run():
        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock):

            # Limit contract
            req_limit = SearchQueryRequest(query="Transformers", limit=1)
            res_limit = await execute_recommendation_search(isolated_db_session, req_limit)
            assert len(res_limit.results) == 1

            # Recency sort (2024 first, then 2023, 2017)
            req_rec = SearchQueryRequest(query="Transformers", sort_by="recency", limit=5)
            res_rec = await execute_recommendation_search(isolated_db_session, req_rec)
            years = [p.year for p in res_rec.results if p.year is not None]
            assert years == sorted(years, reverse=True)

            # Citations sort (110000 first)
            req_cit = SearchQueryRequest(query="Transformers", sort_by="citations", limit=5)
            res_cit = await execute_recommendation_search(isolated_db_session, req_cit)
            cits = [p.citation_count for p in res_cit.results if p.citation_count is not None]
            assert cits == sorted(cits, reverse=True)

    asyncio.run(_run())


def test_empty_results_and_invalid_source_values(isolated_db_session, mock_faiss):
    """
    8. Unmatched queries or unknown provenance filters handle gracefully without errors.
    """
    async def _run():
        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock):

            # Nonexistent provenance
            req_invalid = SearchQueryRequest(query="Attention", sources=["unknown_repo_99"], limit=5)
            res_invalid = await execute_recommendation_search(isolated_db_session, req_invalid)
            assert res_invalid.total_found == 0
            assert res_invalid.results == []

            # Unmatched query with restrictive filter that excludes all candidates
            req_unmatched = SearchQueryRequest(query="zzzznonexistenttoken9999", min_year=2099, limit=5)
            res_unmatched = await execute_recommendation_search(isolated_db_session, req_unmatched)
            assert res_unmatched.total_found == 0
            assert res_unmatched.results == []

    asyncio.run(_run())


def test_local_search_does_not_mutate_records_or_faiss(isolated_db_session, mock_faiss):
    """
    9. Verify local search strictly does not add, update, or delete DB records or FAISS vectors.
    """
    async def _run():
        initial_count = isolated_db_session.query(Paper).count()
        assert initial_count == 5

        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock):

            req = SearchQueryRequest(query="Attention Transformer", sources=["arxiv", "local"], limit=5)
            await execute_recommendation_search(isolated_db_session, req)

        final_count = isolated_db_session.query(Paper).count()
        assert final_count == initial_count, "Database paper count must not change during search."
        assert len(isolated_db_session.new) == 0
        assert len(isolated_db_session.deleted) == 0
        mock_faiss.add_papers.assert_not_called()

    asyncio.run(_run())
