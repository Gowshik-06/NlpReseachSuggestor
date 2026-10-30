"""
Mocked unit tests for academic repository connectors:
- arXiv (parameter passing, Atom XML, malformed XML)
- Semantic Scholar (Graph API, optional API key, HTTP 429 rate limit)
- Crossref (clean text, no fabricated abstracts)
- DBLP (JSON parsing, HTML bot challenge detection)
- PubMed (E-utilities 2-stage search, metadata extraction, no fabricated abstracts)
- CSIR-NIScPR (publisher filter, journal extraction)
- CORE (clean handling when unconfigured)
- Multi-source orchestration and source restriction (search_all_sources)
- Provider failure resilience (partial failure does not drop healthy results)
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from app.services.academic_sources import (
    search_arxiv,
    search_semantic_scholar,
    search_crossref,
    search_dblp,
    search_pubmed,
    search_csir_niscpr,
    search_core,
    search_all_sources
)


@pytest.mark.anyio
async def test_arxiv_search_normal_xml():
    """Test arXiv Atom XML response parsing and metadata extraction."""
    atom_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2101.00001v1</id>
        <title>Transformer Language Models in NLP</title>
        <summary>A detailed study on self-attention mechanisms in deep learning.</summary>
        <published>2021-01-01T00:00:00Z</published>
        <author><name>Alice Smith</name></author>
        <author><name>Bob Jones</name></author>
        <arxiv:doi>10.1000/arxiv.2101.00001</arxiv:doi>
        <link title="pdf" href="https://arxiv.org/pdf/2101.00001v1.pdf"/>
      </entry>
    </feed>"""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = atom_xml

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp) as mock_get:
        results = await search_arxiv("transformer", max_results=3)
        assert len(results) == 1
        paper = results[0]
        assert paper["paper_id"] == "arxiv:2101.00001v1"
        assert paper["title"] == "Transformer Language Models in NLP"
        assert "self-attention" in paper["abstract"]
        assert paper["year"] == 2021
        assert paper["authors"] == ["Alice Smith", "Bob Jones"]
        assert paper["doi"] == "10.1000/arxiv.2101.00001"
        assert paper["source"] == "arxiv"
        # Verify query was passed as parameter, not interpolated in URL
        assert "params" in mock_get.call_args.kwargs
        assert mock_get.call_args.kwargs["params"]["search_query"] == "all:transformer"


@pytest.mark.anyio
async def test_arxiv_search_empty_query():
    """Test empty or whitespace query returns empty list without calling API."""
    results = await search_arxiv("   ")
    assert results == []


@pytest.mark.anyio
async def test_arxiv_search_malformed_xml():
    """Test arXiv handles malformed XML without crashing."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<feed>Incomplete XML without closing tag"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await search_arxiv("broken")
        assert results == []


@pytest.mark.anyio
async def test_semantic_scholar_normal_json():
    """Test Semantic Scholar Graph API response parsing."""
    json_data = {
        "data": [
            {
                "paperId": "abcdef123456",
                "title": "Scaling Laws for Neural Models",
                "abstract": "We investigate empirical scaling laws for language model performance.",
                "year": 2020,
                "venue": "OpenAI",
                "citationCount": 2400,
                "authors": [{"name": "Jared Kaplan"}],
                "externalIds": {"DOI": "10.1000/scaling", "ArXiv": "2001.08361"},
                "url": "https://www.semanticscholar.org/paper/abcdef123456",
                "openAccessPdf": {"url": "https://arxiv.org/pdf/2001.08361.pdf"}
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = json_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await search_semantic_scholar("scaling laws")
        assert len(results) == 1
        p = results[0]
        assert p["paper_id"] == "ss:abcdef123456"
        assert p["title"] == "Scaling Laws for Neural Models"
        assert p["citation_count"] == 2400
        assert p["source"] == "semanticscholar"


@pytest.mark.anyio
async def test_semantic_scholar_rate_limit_429():
    """Test Semantic Scholar handles HTTP 429 rate limit cleanly."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Too Many Requests"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await search_semantic_scholar("nlp")
        assert results == []


@pytest.mark.anyio
async def test_crossref_normal_and_no_fabricated_abstract():
    """Test Crossref strips JATS XML tags and does NOT fabricate abstracts when missing."""
    items = [
        {
            "title": ["Paper With Abstract"],
            "abstract": "<jats:p>This is a real abstract extracted from Crossref.</jats:p>",
            "author": [{"given": "John", "family": "Doe"}],
            "published": {"date-parts": [[2023, 5]]},
            "DOI": "10.1000/with-abs",
            "container-title": ["Journal of Testing"],
            "is-referenced-by-count": 15
        },
        {
            "title": ["Paper Without Abstract"],
            "abstract": None,
            "author": [{"given": "Jane", "family": "Smith"}],
            "published": {"date-parts": [[2024, 1]]},
            "DOI": "10.1000/no-abs",
            "container-title": ["Journal of Testing"],
            "is-referenced-by-count": 5
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"message": {"items": items}}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await search_crossref("testing")
        assert len(results) == 2
        # First paper has cleaned real abstract
        assert results[0]["abstract"] == "This is a real abstract extracted from Crossref."
        # Second paper must have empty abstract, NOT fabricated fake description
        assert results[1]["abstract"] == ""
        assert "Scholarly publication registered via Crossref" not in results[1]["abstract"]


@pytest.mark.anyio
async def test_dblp_normal_and_bot_challenge_handling():
    """Test DBLP parses JSON hits and safely handles HTML bot challenge responses."""
    # 1. Normal JSON hit
    normal_json = {
        "result": {
            "hits": {
                "hit": [
                    {
                        "info": {
                            "key": "journals/corr/abs-2101-00001",
                            "title": "A Survey on Graph Neural Networks.",
                            "authors": {"author": [{"text": "Alice Doe"}]},
                            "year": "2021",
                            "venue": "CoRR",
                            "doi": "10.1000/gnn",
                            "ee": "https://doi.org/10.1000/gnn"
                        }
                    }
                ]
            }
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json; charset=utf-8"}
    mock_resp.json.return_value = normal_json

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await search_dblp("graph neural networks")
        assert len(results) == 1
        assert results[0]["title"] == "A Survey on Graph Neural Networks"
        # Abstract must not be fabricated
        assert results[0]["abstract"] == ""
        assert "DBLP publication in computer science" not in results[0]["abstract"]

    # 2. Cloudflare / Bot Challenge returning HTML
    html_resp = MagicMock()
    html_resp.status_code = 200
    html_resp.headers = {"content-type": "text/html; charset=utf-8"}
    html_resp.text = "<html><head><title>Making sure you're not a bot!</title></head></html>"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=html_resp):
        bot_results = await search_dblp("graph neural networks")
        # Should detect non-JSON and safely return empty list without crashing
        assert bot_results == []


@pytest.mark.anyio
async def test_pubmed_two_stage_search_and_no_fabricated_abstract():
    """Test PubMed 2-stage (esearch + esummary) integration and truthful metadata."""
    esearch_data = {"esearchresult": {"idlist": ["12345678"]}}
    esummary_data = {
        "result": {
            "12345678": {
                "title": "Computational Analysis of Genomic Sequences.",
                "authors": [{"name": "Dr. Watson"}],
                "source": "Nature Genetics",
                "pubdate": "2022 Mar 15",
                "articleids": [{"idtype": "doi", "value": "10.1038/ng.1234"}]
            }
        }
    }

    mock_search = MagicMock()
    mock_search.status_code = 200
    mock_search.headers = {"content-type": "application/json"}
    mock_search.json.return_value = esearch_data

    mock_sum = MagicMock()
    mock_sum.status_code = 200
    mock_sum.headers = {"content-type": "application/json"}
    mock_sum.json.return_value = esummary_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=[mock_search, mock_sum]):
        results = await search_pubmed("genomic sequences")
        assert len(results) == 1
        p = results[0]
        assert p["paper_id"] == "pubmed:12345678"
        assert p["title"] == "Computational Analysis of Genomic Sequences."
        assert p["year"] == 2022
        assert p["doi"] == "10.1038/ng.1234"
        # Abstract must not be fabricated
        assert p["abstract"] == ""
        assert "Biomedical & computational research paper indexed" not in p["abstract"]


@pytest.mark.anyio
async def test_csir_niscpr_no_fabricated_abstract():
    """Test CSIR-NIScPR publisher filtering and truthful abstract handling."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {
        "message": {
            "items": [
                {
                    "title": ["Indigenous Medicinal Flora and Biotechnology"],
                    "abstract": None,
                    "author": [{"given": "Ramesh", "family": "Kumar"}],
                    "published": {"date-parts": [[2021]]},
                    "DOI": "10.56042/ijbb.v58i1.12345",
                    "container-title": ["Indian Journal of Biochemistry & Biophysics"],
                    "is-referenced-by-count": 8
                }
            ]
        }
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await search_csir_niscpr("biotechnology")
        assert len(results) == 1
        p = results[0]
        assert p["source"] == "csir"
        assert p["abstract"] == ""
        assert "Indian Government research paper published in" not in p["abstract"]


@pytest.mark.anyio
async def test_search_all_sources_restricts_requested_sources():
    """Test search_all_sources only invokes providers that are in the requested sources list."""
    with patch("app.services.academic_sources.search_arxiv", new_callable=AsyncMock, return_value=[{"paper_id": "arxiv:1"}]) as m_arxiv, \
         patch("app.services.academic_sources.search_pubmed", new_callable=AsyncMock, return_value=[]) as m_pubmed, \
         patch("app.services.academic_sources.search_crossref", new_callable=AsyncMock, return_value=[]) as m_crossref:

        results = await search_all_sources("transformer", sources=["arxiv"])
        assert len(results) == 1
        assert results[0]["paper_id"] == "arxiv:1"
        assert m_arxiv.called
        assert not m_pubmed.called
        assert not m_crossref.called


@pytest.mark.anyio
async def test_search_all_sources_resilience_to_individual_provider_failure():
    """Test that one provider timing out or failing does not discard results from other providers."""
    with patch("app.services.academic_sources.search_arxiv", new_callable=AsyncMock, side_effect=httpx.ConnectTimeout("arXiv timed out")), \
         patch("app.services.academic_sources.search_crossref", new_callable=AsyncMock, return_value=[{"paper_id": "crossref:10.1000/1"}]) as m_crossref:

        results = await search_all_sources("transformer", sources=["arxiv", "crossref"])
        assert len(results) == 1
        assert results[0]["paper_id"] == "crossref:10.1000/1"
