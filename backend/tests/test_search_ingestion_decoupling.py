"""
Focused, isolated unit tests for Search-to-Ingestion Decoupling (TASK 1B).
Verifies that ordinary research search queries never write to PostgreSQL or FAISS,
while properly handling transient external candidates, hybrid combinations,
and preserving explicit intentional ingestion workflows.
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
from app.services.vector_index import sync_unindexed_papers


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

    sample_papers = [
        Paper(
            id=1,
            paper_id="arxiv:1706.03762",
            title="Attention Is All You Need",
            abstract="The Transformer model architecture relies entirely on self-attention.",
            authors=["Ashish Vaswani", "Noam Shazeer"],
            year=2017,
            doi="10.48550/arxiv.1706.03762",
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
            doi="10.1038/s41586-021-00001",
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
            doi="10.56042/jsir.v79i2",
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
            doi="10.1017/transformers",
            citation_count=350,
            source="crossref"
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
    Mock FAISS index with pre-existing catalog metadata to test read-only FAISS interactions.
    """
    mock_idx = MagicMock()
    mock_idx.search.return_value = [
        ({"paper_id": "arxiv:1706.03762", "title": "Attention Is All You Need"}, 0.95),
        ({"paper_id": "crossref:10.1017/transformers", "title": "Transformers and Neural Attention"}, 0.88),
    ]
    mock_idx.paper_metadata = {
        "arxiv:1706.03762": {"paper_id": "arxiv:1706.03762", "title": "Attention Is All You Need"},
        "crossref:10.1017/transformers": {"paper_id": "crossref:10.1017/transformers", "title": "Transformers and Neural Attention"},
    }
    mock_idx.add_papers = MagicMock()
    return mock_idx


def test_local_only_search_continues_to_return_catalog_records(isolated_db_session, mock_faiss):
    """
    1. Local-only search continues to return stored catalog records without persistent writes.
    """
    async def _run():
        init_count = isolated_db_session.query(Paper).count()
        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock) as mock_external:

            req = SearchQueryRequest(query="Transformer", sources=["arxiv"], limit=5)
            response = await execute_recommendation_search(isolated_db_session, req)

            assert response.total_found > 0
            assert any(p.paper_id == "arxiv:1706.03762" for p in response.results)
            # Ensure all returned local papers have their integer primary keys
            for p in response.results:
                assert p.id is not None
            mock_external.assert_not_called()

        assert isolated_db_session.query(Paper).count() == init_count
        assert len(isolated_db_session.new) == 0
        mock_faiss.add_papers.assert_not_called()

    asyncio.run(_run())


def test_external_only_search_returns_transient_candidates_without_writes(isolated_db_session, mock_faiss):
    """
    2. External-only search returns external candidates with id=None without writing to PostgreSQL or FAISS.
    """
    async def _run():
        init_count = isolated_db_session.query(Paper).count()
        mock_external_data = [
            {
                "paper_id": "arxiv:2401.55555",
                "title": "Novel Video Diffusion Transformers",
                "abstract": "We introduce video diffusion transformers with multi-head cross attention.",
                "authors": ["External Researcher"],
                "year": 2024,
                "source": "arxiv",
                "citation_count": 5
            }
        ]

        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock, return_value=mock_external_data) as mock_external:

            req = SearchQueryRequest(query="Video Diffusion Transformers", sources=["arxiv"], enable_external_discovery=True, limit=5)
            response = await execute_recommendation_search(isolated_db_session, req)

            assert any(p.paper_id == "arxiv:2401.55555" for p in response.results)
            ext_paper = next(p for p in response.results if p.paper_id == "arxiv:2401.55555")
            assert ext_paper.source == "arxiv"
            # Transient external candidates must have id=None (not assigned a fake DB key)
            assert ext_paper.id is None
            assert ext_paper.similarity_score is not None
            assert ext_paper.explanation is not None

        # Verify zero database rows were inserted
        assert isolated_db_session.query(Paper).count() == init_count
        assert isolated_db_session.query(Paper).filter(Paper.paper_id == "arxiv:2401.55555").first() is None
        # Verify FAISS add_papers was never called
        mock_faiss.add_papers.assert_not_called()

    asyncio.run(_run())


def test_hybrid_search_combines_local_and_external_without_writes(isolated_db_session, mock_faiss):
    """
    3. Hybrid search combines local and external candidates without persistent writes.
    """
    async def _run():
        init_count = isolated_db_session.query(Paper).count()
        mock_external_data = [
            {
                "paper_id": "arxiv:2402.77777",
                "title": "Scaling Law for Autoregressive Transformers",
                "abstract": "Empirical study on scaling transformers.",
                "authors": ["External Researcher"],
                "year": 2024,
                "source": "arxiv",
                "citation_count": 10
            }
        ]

        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock, return_value=mock_external_data):

            req = SearchQueryRequest(query="Transformers", sources=["arxiv"], enable_external_discovery=True, limit=10)
            response = await execute_recommendation_search(isolated_db_session, req)

            assert response.total_found >= 2
            pids = [p.paper_id for p in response.results]
            assert "arxiv:2402.77777" in pids  # Transient external
            assert "arxiv:1706.03762" in pids  # Local persisted

            # Local paper has integer id, transient external has None
            local_res = next(p for p in response.results if p.paper_id == "arxiv:1706.03762")
            ext_res = next(p for p in response.results if p.paper_id == "arxiv:2402.77777")
            assert local_res.id is not None
            assert ext_res.id is None

        # Verify database remained untouched
        assert isolated_db_session.query(Paper).count() == init_count
        mock_faiss.add_papers.assert_not_called()

    asyncio.run(_run())


def test_duplicate_external_candidate_deduplication(isolated_db_session, mock_faiss):
    """
    4. Existing duplicate external candidates are deduplicated and safely resolve existing DB id read-only.
    """
    async def _run():
        init_count = isolated_db_session.query(Paper).count()
        # External returns an exact duplicate of local paper (same paper_id and doi)
        mock_external_data = [
            {
                "paper_id": "arxiv:1706.03762",
                "title": "Attention Is All You Need",
                "abstract": "The Transformer model architecture relies entirely on self-attention.",
                "authors": ["Ashish Vaswani"],
                "year": 2017,
                "doi": "10.48550/arxiv.1706.03762",
                "source": "arxiv",
                "citation_count": 110000
            }
        ]

        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock, return_value=mock_external_data):

            req = SearchQueryRequest(query="Attention Is All You Need", sources=["arxiv"], enable_external_discovery=True, limit=5)
            response = await execute_recommendation_search(isolated_db_session, req)

            # Deduplication collapses to a single entry
            matches = [p for p in response.results if p.paper_id == "arxiv:1706.03762"]
            assert len(matches) == 1
            assert matches[0].id == 1  # Resolves to existing local DB primary key

        assert isolated_db_session.query(Paper).count() == init_count
        mock_faiss.add_papers.assert_not_called()

    asyncio.run(_run())


def test_provider_errors_do_not_trigger_unintended_writes(isolated_db_session, mock_faiss):
    """
    5. Provider network/parsing errors do not cause unhandled crashes or database mutations.
    """
    async def _run():
        init_count = isolated_db_session.query(Paper).count()
        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock, side_effect=RuntimeError("Provider 503 Service Unavailable")):

            req = SearchQueryRequest(query="Transformer", sources=["arxiv"], enable_external_discovery=True, limit=5)
            response = await execute_recommendation_search(isolated_db_session, req)

            # Local candidates still returned successfully
            assert response.total_found > 0
            assert any(p.paper_id == "arxiv:1706.03762" for p in response.results)

        assert isolated_db_session.query(Paper).count() == init_count
        mock_faiss.add_papers.assert_not_called()

    asyncio.run(_run())


def test_ranking_and_response_serialization(isolated_db_session, mock_faiss):
    """
    6. Ranking and response serialization work seamlessly for both persisted and transient candidates across sort modes.
    """
    async def _run():
        mock_external_data = [
            {
                "paper_id": "arxiv:2601.11111",
                "title": "2026 Breakthrough on Transformers",
                "abstract": "Frontier architecture.",
                "authors": ["Author 2026"],
                "year": 2026,
                "source": "arxiv",
                "citation_count": 10
            },
            {
                "paper_id": "pubmed:2020.22222",
                "title": "Highly Cited Biological Transformers",
                "abstract": "Biological analysis.",
                "authors": ["Author Bio"],
                "year": 2020,
                "source": "pubmed",
                "citation_count": 999999
            }
        ]

        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock, return_value=mock_external_data):

            # Test recency sort (2026 first)
            req_rec = SearchQueryRequest(query="Transformers", sources=["arxiv", "pubmed"], enable_external_discovery=True, sort_by="recency", limit=5)
            res_rec = await execute_recommendation_search(isolated_db_session, req_rec)
            assert res_rec.results[0].year == 2026

            # Test citations sort (999999 first)
            req_cit = SearchQueryRequest(query="Transformers", sources=["arxiv", "pubmed"], enable_external_discovery=True, sort_by="citations", limit=5)
            res_cit = await execute_recommendation_search(isolated_db_session, req_cit)
            assert res_cit.results[0].citation_count >= 999999

            # Verify response schema contract
            assert isinstance(res_rec, SearchResponse)
            for p in res_rec.results:
                assert p.title
                assert p.paper_id
                assert p.source

    asyncio.run(_run())


def test_search_never_invokes_faiss_add_papers(isolated_db_session, mock_faiss):
    """
    7. Under any source selection configuration, search never invokes faiss_index.add_papers.
    """
    async def _run():
        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock, return_value=[]):

            configs = [
                ["local"],
                ["arxiv"],
                ["local", "arxiv"],
                ["pubmed", "csir"],
                [],
            ]
            for cfg in configs:
                req = SearchQueryRequest(query="Neural Transformers", sources=cfg, limit=5)
                await execute_recommendation_search(isolated_db_session, req)
                mock_faiss.add_papers.assert_not_called()

    asyncio.run(_run())


def test_external_source_filtering_retains_compatibility(isolated_db_session, mock_faiss):
    """
    8. Source filtering ensures only requested providers are included in final response.
    """
    async def _run():
        mock_external_data = [
            {"paper_id": "arxiv:1", "title": "Arxiv Paper", "abstract": "Test", "year": 2024, "source": "arxiv"},
            {"paper_id": "pubmed:2", "title": "PubMed Paper", "abstract": "Test", "year": 2024, "source": "pubmed"},
        ]

        with patch("app.services.recommendation_engine.get_faiss_index", return_value=mock_faiss), \
             patch("app.services.recommendation_engine.search_all_sources", new_callable=AsyncMock, return_value=mock_external_data):

            req = SearchQueryRequest(query="Test", sources=["arxiv"], limit=5)
            response = await execute_recommendation_search(isolated_db_session, req)

            assert len(response.results) == 1
            assert response.results[0].source == "arxiv"

    asyncio.run(_run())


def test_explicit_ingestion_workflow_retains_intended_behavior(isolated_db_session):
    """
    9. Verify intentional ingestion functions (e.g. sync_unindexed_papers) still work as intended.
    Decoupling search did not disable intentional database-to-FAISS ingestion.
    """
    mock_active_faiss = MagicMock()
    mock_active_faiss.paper_metadata = {}
    mock_active_faiss.add_papers = MagicMock()

    # Add a new unindexed paper to the isolated database
    new_paper = Paper(
        id=99,
        paper_id="intentional:ingest:001",
        title="Intentional Ingestion Paper",
        abstract="Explicitly ingested paper for index synchronization.",
        authors=["Catalog Curator"],
        year=2024,
        source="arxiv"
    )
    isolated_db_session.add(new_paper)
    isolated_db_session.commit()

    with patch("app.services.vector_index.get_faiss_index", return_value=mock_active_faiss):
        synced_count = sync_unindexed_papers(session=isolated_db_session, paper_ids=["intentional:ingest:001"])

        assert synced_count == 1
        mock_active_faiss.add_papers.assert_called_once()
        added_arg = mock_active_faiss.add_papers.call_args[0][0]
        assert len(added_arg) == 1
        assert added_arg[0]["paper_id"] == "intentional:ingest:001"
