"""
Academic repository connectors for:
- arXiv API
- Semantic Scholar API
- Crossref API
- DBLP API
- PubMed / NCBI NIH API (US Government Database)
- CSIR-NIScPR (Council of Scientific & Industrial Research - Govt of India)
- CORE API
"""
import asyncio
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TIMEOUT = 8.0  # seconds timeout for external API calls


async def search_arxiv(query: str, max_results: int = 8, sort_by_date: bool = False) -> List[Dict[str, Any]]:
    """Search arXiv API using Atom feed with optional submittedDate recency sorting."""
    clean_query = query.strip()
    if not clean_query:
        return []

    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{clean_query}",
        "start": 0,
        "max_results": max_results,
    }
    if sort_by_date:
        params["sortBy"] = "submittedDate"
        params["sortOrder"] = "descending"

    results = []
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
                for entry in root.findall("atom:entry", ns):
                    title_elem = entry.find("atom:title", ns)
                    summary_elem = entry.find("atom:summary", ns)
                    id_elem = entry.find("atom:id", ns)
                    published_elem = entry.find("atom:published", ns)
                    doi_elem = entry.find("arxiv:doi", ns)

                    authors = []
                    for author in entry.findall("atom:author", ns):
                        name = author.find("atom:name", ns)
                        if name is not None and name.text:
                            authors.append(name.text.strip())

                    pdf_url = None
                    for link in entry.findall("atom:link", ns):
                        if link.attrib.get("title") == "pdf":
                            pdf_url = link.attrib.get("href")

                    arxiv_id = id_elem.text.split("/abs/")[-1] if id_elem is not None and id_elem.text else ""
                    year = int(published_elem.text[:4]) if published_elem is not None and published_elem.text else None

                    results.append({
                        "paper_id": f"arxiv:{arxiv_id}",
                        "title": " ".join(title_elem.text.split()) if title_elem is not None and title_elem.text else "",
                        "abstract": " ".join(summary_elem.text.split()) if summary_elem is not None and summary_elem.text else "",
                        "authors": authors,
                        "venue": "arXiv",
                        "year": year,
                        "doi": doi_elem.text if doi_elem is not None else None,
                        "url": id_elem.text if id_elem is not None and id_elem.text else "",
                        "pdf_url": pdf_url or (f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else None),
                        "source": "arxiv",
                        "citation_count": 0,
                        "categories": ["cs.AI"]
                    })
    except Exception as e:
        logger.warning("Error fetching arXiv results: %s", e)
    return results


async def search_semantic_scholar(query: str, max_results: int = 8) -> List[Dict[str, Any]]:
    """Search Semantic Scholar Graph API."""
    clean_query = query.strip()
    if not clean_query:
        return []

    settings = get_settings()
    s2_key = (
        getattr(settings, "S2_API_KEY", None)
        or getattr(settings, "SEMANTIC_SCHOLAR_API_KEY", None)
        or os.getenv("S2_API_KEY")
        or os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    )
    headers = {"User-Agent": "ResearchPaperRecommender/0.1.0"}
    if s2_key:
        headers["x-api-key"] = s2_key

    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": clean_query,
        "limit": max_results,
        "fields": "title,abstract,authors,year,venue,citationCount,externalIds,url,openAccessPdf"
    }
    results = []
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 429:
                logger.warning("Semantic Scholar API rate limit reached (HTTP 429).")
                return results
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "")
                if "application/json" not in content_type:
                    logger.warning("Semantic Scholar returned non-JSON response.")
                    return results
                data = resp.json().get("data", [])
                for p in data:
                    authors = [a.get("name") for a in p.get("authors", []) if a.get("name")]
                    ext_ids = p.get("externalIds", {}) or {}
                    doi = ext_ids.get("DOI")
                    arxiv_id = ext_ids.get("ArXiv")
                    paper_id = f"ss:{p.get('paperId')}" if p.get("paperId") else f"doi:{doi}" if doi else f"arxiv:{arxiv_id}"

                    pdf_obj = p.get("openAccessPdf")
                    pdf_url = pdf_obj.get("url") if pdf_obj else None

                    results.append({
                        "paper_id": paper_id,
                        "title": p.get("title", ""),
                        "abstract": p.get("abstract") or "",
                        "authors": authors,
                        "venue": p.get("venue") or "Semantic Scholar",
                        "year": p.get("year"),
                        "doi": doi,
                        "url": p.get("url") or "",
                        "pdf_url": pdf_url,
                        "source": "semanticscholar",
                        "citation_count": p.get("citationCount") or 0,
                        "categories": ["cs.CL"]
                    })
    except Exception as e:
        logger.warning("Error fetching Semantic Scholar results: %s", e)
    return results


async def search_crossref(query: str, max_results: int = 8) -> List[Dict[str, Any]]:
    """Search Crossref API."""
    clean_query = query.strip()
    if not clean_query:
        return []

    settings = get_settings()
    mailto = getattr(settings, "CROSSREF_MAILTO", None) or os.getenv("CROSSREF_MAILTO")
    ua = f"ResearchPaperRecommender/0.1.0 (mailto:{mailto})" if mailto else "ResearchPaperRecommender/0.1.0"
    headers = {"User-Agent": ua}

    url = "https://api.crossref.org/works"
    params = {"query": clean_query, "rows": max_results}
    results = []
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "")
                if "application/json" not in content_type:
                    logger.warning("Crossref returned non-JSON response.")
                    return results
                items = resp.json().get("message", {}).get("items", [])
                for it in items:
                    title_list = it.get("title", [])
                    title = title_list[0] if title_list else ""
                    if not title:
                        continue
                    abstract = it.get("abstract", "")
                    if abstract:
                        abstract = re.sub(r"<[^>]+>", "", abstract).strip()

                    authors = []
                    for a in it.get("author", []):
                        name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                        if name:
                            authors.append(name)

                    year = None
                    published = it.get("published", {}).get("date-parts", [[]])[0]
                    if published:
                        year = published[0]

                    doi = it.get("DOI")
                    venue = (it.get("container-title") or ["Crossref"])[0]

                    results.append({
                        "paper_id": f"crossref:{doi}" if doi else f"cr:{it.get('prefix')}",
                        "title": title,
                        "abstract": abstract or "",
                        "authors": authors,
                        "venue": venue,
                        "year": year,
                        "doi": doi,
                        "url": it.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
                        "pdf_url": None,
                        "source": "crossref",
                        "citation_count": it.get("is-referenced-by-count", 0),
                        "categories": ["Interdisciplinary"]
                    })
    except Exception as e:
        logger.warning("Error fetching Crossref results: %s", e)
    return results


async def search_dblp(query: str, max_results: int = 8) -> List[Dict[str, Any]]:
    """Search DBLP Computer Science Bibliography API."""
    clean_query = query.strip()
    if not clean_query:
        return []

    url = "https://dblp.org/search/publ/api"
    params = {"q": clean_query, "format": "json", "h": max_results}
    headers = {"User-Agent": "ResearchPaperRecommender/0.1.0 (academic research tool)"}
    results = []
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "")
                if "application/json" not in content_type:
                    logger.warning("DBLP returned non-JSON response (status 200, content-type=%s). Skipping DBLP.", content_type)
                    return results

                try:
                    payload = resp.json()
                except Exception as e:
                    logger.warning("Failed to decode DBLP JSON payload: %s", e)
                    return results

                hits = payload.get("result", {}).get("hits", {}).get("hit", [])
                for h in hits:
                    info = h.get("info", {})
                    title = info.get("title", "").rstrip(".")
                    if not title:
                        continue
                    authors_obj = info.get("authors", {}).get("author", [])
                    if isinstance(authors_obj, list):
                        authors = [a.get("text", "") for a in authors_obj if isinstance(a, dict) and a.get("text")]
                    elif isinstance(authors_obj, dict):
                        authors = [authors_obj.get("text", "")] if authors_obj.get("text") else []
                    else:
                        authors = []

                    year = int(info.get("year")) if info.get("year") and info.get("year").isdigit() else None
                    doi = info.get("doi")
                    results.append({
                        "paper_id": f"dblp:{info.get('key')}",
                        "title": title,
                        "abstract": "",
                        "authors": authors,
                        "venue": info.get("venue") or "DBLP",
                        "year": year,
                        "doi": doi,
                        "url": info.get("ee") or info.get("url") or "",
                        "pdf_url": info.get("ee") if (info.get("ee") or "").endswith(".pdf") else None,
                        "source": "dblp",
                        "citation_count": 0,
                        "categories": ["Computer Science"]
                    })
    except Exception as e:
        logger.warning("Error fetching DBLP results: %s", e)
    return results


def parse_pubmed_dates(p: Dict[str, Any], reference_year: Optional[int] = None) -> Dict[str, Any]:
    """
    Parse PubMed publication dates, prioritizing electronic publication date (epubdate)
    over scheduled print publication date (pubdate) for ordinary publication-year ranking,
    while preserving the distinction, provenance, and scheduled print dates.

    If reference_year is None, dynamically defaults to the current UTC calendar year
    (e.g., 2026 in 2026, 2027 in 2027), ensuring durable and correct date classification
    as the calendar advances without hardcoded year ceilings.
    """
    ref_year = reference_year if reference_year is not None else datetime.now(timezone.utc).year

    raw_pubdate = str(p.get("pubdate") or "").strip()
    raw_epubdate = str(p.get("epubdate") or "").strip()

    print_year = None
    if raw_pubdate:
        match = re.search(r"\b(19\d\d|20\d\d)\b", raw_pubdate)
        if match:
            print_year = int(match.group(1))

    epub_year = None
    if raw_epubdate:
        match = re.search(r"\b(19\d\d|20\d\d)\b", raw_epubdate)
        if match:
            epub_year = int(match.group(1))

    # Evaluate publication status and effective ranking year
    if epub_year and print_year:
        if print_year > ref_year and epub_year <= ref_year:
            # Electronic advance article published in or before reference year, scheduled print in future
            year = epub_year
            status = "ahead_of_print"
        elif epub_year > ref_year and print_year > ref_year:
            year = min(epub_year, print_year)
            status = "forthcoming"
        else:
            # Both published: earliest electronic date represents verified public availability
            year = epub_year
            status = "published"
    elif epub_year:
        year = epub_year
        status = "forthcoming" if epub_year > ref_year else "published"
    elif print_year:
        year = print_year
        status = "forthcoming" if print_year > ref_year else "published"
    else:
        year = None
        status = "unknown"

    return {
        "year": year,
        "epub_year": epub_year,
        "print_year": print_year,
        "epubdate": raw_epubdate,
        "pubdate": raw_pubdate,
        "publication_status": status,
        "reference_year": ref_year,
    }


async def search_pubmed(query: str, max_results: int = 8, sort_by_date: bool = True, reference_year: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Search US Government PubMed / NCBI NIH E-utilities API.
    Direct integration with the National Center for Biotechnology Information / US National Library of Medicine.
    Zero API key required for standard research queries.
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    settings = get_settings()
    ncbi_key = (
        getattr(settings, "NCBI_API_KEY", None)
        or os.getenv("NCBI_API_KEY")
        or os.getenv("PUBMED_API_KEY")
    )

    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": clean_query,
        "retmode": "json",
        "retmax": max_results,
    }
    if sort_by_date:
        search_params["sort"] = "pub_date"
    if ncbi_key:
        search_params["api_key"] = ncbi_key

    results = []
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(search_url, params=search_params)
            if resp.status_code == 200 and "application/json" in resp.headers.get("content-type", ""):
                data = resp.json()
                idlist = data.get("esearchresult", {}).get("idlist", [])
                if not idlist:
                    return results

                summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                sum_params = {"db": "pubmed", "id": ",".join(idlist), "retmode": "json"}
                if ncbi_key:
                    sum_params["api_key"] = ncbi_key
                sum_resp = await client.get(summary_url, params=sum_params)
                if sum_resp.status_code == 200 and "application/json" in sum_resp.headers.get("content-type", ""):
                    sum_data = sum_resp.json().get("result", {})
                    for pmid in idlist:
                        p = sum_data.get(pmid, {})
                        if not p or not isinstance(p, dict):
                            continue

                        raw_title = p.get("title", "")
                        title = re.sub(r"<[^>]+>", "", raw_title).strip()
                        if not title:
                            continue

                        authors = [a.get("name") for a in p.get("authors", []) if isinstance(a, dict) and a.get("name")]
                        venue_raw = p.get("source") or p.get("fulljournalname") or "PubMed"

                        date_info = parse_pubmed_dates(p, reference_year=reference_year)
                        year = date_info["year"]
                        status = date_info["publication_status"]
                        raw_pubdate = date_info["pubdate"]
                        raw_epubdate = date_info["epubdate"]

                        if status == "ahead_of_print":
                            venue = f"🏛️ PubMed: {venue_raw} (Advance Article; Scheduled Print: {raw_pubdate})"
                        elif status == "forthcoming":
                            venue = f"🏛️ PubMed: {venue_raw} (Forthcoming Issue: {raw_pubdate or raw_epubdate})"
                        else:
                            venue = f"🏛️ PubMed: {venue_raw}"

                        doi = None
                        for aid in p.get("articleids", []):
                            if isinstance(aid, dict) and aid.get("idtype") == "doi":
                                doi = aid.get("value")
                                break

                        results.append({
                            "paper_id": f"pubmed:{pmid}",
                            "title": title,
                            "abstract": "",
                            "authors": authors,
                            "venue": venue,
                            "year": year,
                            "doi": doi,
                            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                            "pdf_url": (f"https://doi.org/{doi}" if doi else None),
                            "source": "pubmed",
                            "citation_count": 0,
                            "categories": ["US Government / NIH", "Computational Biology / NLP"],
                            "publication_status": status,
                            "epubdate": raw_epubdate,
                            "pubdate": raw_pubdate,
                            "epub_year": date_info["epub_year"],
                            "print_year": date_info["print_year"],
                        })
    except Exception as e:
        logger.warning("Error fetching PubMed / NCBI results: %s", e)
    return results


async def search_csir_niscpr(query: str, max_results: int = 8) -> List[Dict[str, Any]]:
    """
    Search official Indian Government CSIR-NIScPR research publications
    (Council of Scientific and Industrial Research - National Institute of Science
    Communication and Policy Research).
    Indexes Indian journals including JSIR, IJEMS, IJPAP, IJBB, IJCT, IJEB, IJBT, JIPR, etc.
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    settings = get_settings()
    mailto = getattr(settings, "CROSSREF_MAILTO", None) or os.getenv("CROSSREF_MAILTO")
    ua = f"ResearchPaperRecommender/0.1.0 (mailto:{mailto})" if mailto else "ResearchPaperRecommender/0.1.0"
    headers = {"User-Agent": ua}

    url = "https://api.crossref.org/works"
    params = {
        "query": clean_query,
        "query.publisher-name": "CSIR-National Institute of Science Communication and Policy Research (NIScPR)",
        "rows": max_results,
    }
    results = []
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "")
                if "application/json" not in content_type:
                    logger.warning("CSIR-NIScPR returned non-JSON response.")
                    return results
                items = resp.json().get("message", {}).get("items", [])
                for it in items:
                    title_list = it.get("title", [])
                    title = title_list[0] if title_list else ""
                    if not title:
                        continue

                    abstract = it.get("abstract", "")
                    if abstract:
                        abstract = re.sub(r"<[^>]+>", "", abstract).strip()

                    journal = (it.get("container-title") or ["CSIR-NIScPR Research Journal"])[0]
                    journal = journal.replace("&amp;", "&")

                    authors = []
                    for a in it.get("author", []):
                        name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                        if name:
                            authors.append(name)

                    year = None
                    published = it.get("published", {}).get("date-parts", [[]])[0]
                    if published:
                        year = published[0]

                    doi = it.get("DOI")
                    paper_url = it.get("URL") or (f"https://doi.org/{doi}" if doi else "https://nopr.niscpr.res.in/")
                    pdf_url = f"https://doi.org/{doi}" if doi else None

                    results.append({
                        "paper_id": f"csir:{doi}" if doi else f"csir:{it.get('prefix')}",
                        "title": title,
                        "abstract": abstract or "",
                        "authors": authors,
                        "venue": f"🏛️ CSIR-NIScPR: {journal}",
                        "year": year,
                        "doi": doi,
                        "url": paper_url,
                        "pdf_url": pdf_url,
                        "source": "csir",
                        "citation_count": it.get("is-referenced-by-count", 0),
                        "categories": ["Indian Government / CSIR", "Science & Technology (India)"]
                    })
    except Exception as e:
        logger.warning("Error fetching CSIR-NIScPR results: %s", e)
    return results


async def search_core(query: str, max_results: int = 8) -> List[Dict[str, Any]]:
    """Search CORE (Open Access research repository) via public endpoints or fallback structure."""
    clean_query = query.strip()
    if not clean_query:
        return []

    settings = get_settings()
    core_key = getattr(settings, "CORE_API_KEY", None) or os.getenv("CORE_API_KEY")
    if not core_key:
        logger.debug("CORE API search skipped: CORE_API_KEY is not configured.")
        return []

    results = []
    try:
        url = "https://api.core.ac.uk/v3/search/works"
        headers = {"Authorization": f"Bearer {core_key}"}
        params = {"q": clean_query, "limit": max_results}
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json().get("results", [])
                for item in data:
                    title = item.get("title", "")
                    if not title:
                        continue
                    authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
                    doi = item.get("doi")
                    results.append({
                        "paper_id": f"core:{item.get('id')}",
                        "title": title,
                        "abstract": item.get("abstract") or "",
                        "authors": authors,
                        "venue": item.get("publisher") or "CORE",
                        "year": item.get("yearPublished"),
                        "doi": doi,
                        "url": item.get("downloadUrl") or f"https://core.ac.uk/works/{item.get('id')}",
                        "pdf_url": item.get("downloadUrl"),
                        "source": "core",
                        "citation_count": item.get("citationCount") or 0,
                        "categories": ["Open Access"]
                    })
    except Exception as e:
        logger.warning("Error fetching CORE results: %s", e)
    return results


async def search_all_sources(
    query: str,
    limit_per_source: int = 5,
    sort_by_date: bool = True,
    sources: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Search across requested academic sources in parallel:
    arXiv, Semantic Scholar, Crossref, DBLP, PubMed (US Gov / NIH), CSIR-NIScPR (Indian Gov), CORE.
    If sources list is provided, only executes queries for the specified sources.
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    requested = set(s.lower() for s in sources) if sources else None

    tasks = []
    if requested is None or "arxiv" in requested:
        tasks.append(search_arxiv(clean_query, max_results=limit_per_source, sort_by_date=sort_by_date))
    if requested is None or "pubmed" in requested:
        tasks.append(search_pubmed(clean_query, max_results=limit_per_source, sort_by_date=sort_by_date))
    if requested is None or "csir" in requested:
        tasks.append(search_csir_niscpr(clean_query, max_results=limit_per_source))
    if requested is None or "semanticscholar" in requested or "semantic_scholar" in requested:
        tasks.append(search_semantic_scholar(clean_query, max_results=limit_per_source))
    if requested is None or "crossref" in requested:
        tasks.append(search_crossref(clean_query, max_results=limit_per_source))
    if requested is None or "dblp" in requested:
        tasks.append(search_dblp(clean_query, max_results=limit_per_source))
    if requested is None or "core" in requested:
        tasks.append(search_core(clean_query, max_results=limit_per_source))

    if not tasks:
        return []

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)
    all_papers: List[Dict[str, Any]] = []
    for res in raw_results:
        if isinstance(res, list):
            all_papers.extend(res)
    return all_papers
