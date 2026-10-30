"""
Hybrid Recommendation Engine combining Semantic Vector Search (FAISS) with
Multi-source Repository Ingestion and Explainable Ranking.
"""
import time
import math
from typing import List, Dict, Any, Optional, Set
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Paper
from app.services.academic_sources import search_all_sources
from app.services.deduplication import deduplicate_papers
from app.services.embedding_service import compute_cosine_similarity, generate_embedding
from app.services.vector_index import get_faiss_index
from app.services.text_processor import extract_keywords_from_text
from app.schemas.paper import SearchQueryRequest, SearchResponse, PaperResponse

logger = get_logger(__name__)

# Calibrated relevance floor for pure semantic search without lexical match (SPECTER2 inner-product / cosine similarity)
# Empirical measurements show in-domain relevant queries score >= 0.844 (top scores 0.863 - 0.937),
# while out-of-domain queries (e.g. "ancient Roman architecture") score <= 0.817.
SEMANTIC_RELEVANCE_FLOOR = 0.835

GENERIC_SEARCH_TERMS = {
    "architecture", "architectures", "system", "systems", "model", "models",
    "method", "methods", "approach", "approaches", "framework", "frameworks",
    "analysis", "study", "paper", "learning", "network", "networks", "based",
    "using", "novel", "new", "via", "towards", "evaluation", "survey"
}


def _has_lexical_match(paper_meta: Dict[str, Any], query_lower: str, keywords: List[str]) -> bool:
    """Check if paper has lexical match with query or distinctive keywords in title or abstract."""
    title_lower = (paper_meta.get("title") or "").lower()
    abstract_lower = (paper_meta.get("abstract") or "").lower()
    full_text = f"{title_lower} {abstract_lower}"

    # Exact full query match
    if len(query_lower) >= 3 and query_lower in full_text:
        return True

    # Check distinctive keywords (excluding common academic stopwords)
    distinctive = [kw.lower().strip() for kw in keywords if kw.lower().strip() not in GENERIC_SEARCH_TERMS and len(kw.strip()) >= 3]
    if distinctive:
        return any(kw in full_text for kw in distinctive)

    # Fallback if query only consisted of generic terms
    for kw in keywords:
        kw_lower = kw.lower().strip()
        if len(kw_lower) >= 3 and kw_lower in full_text:
            return True
    return False


def generate_recommendation_explanation(query: str, paper: Dict[str, Any], similarity_score: float) -> str:
    """Generate explainable recommendation rationale."""
    title = paper.get("title", "")
    abstract = paper.get("abstract", "") or ""
    citations = paper.get("citation_count", 0)
    year = paper.get("year")
    source = paper.get("source", "local").capitalize()
    if source.lower() == "pubmed":
        source = "PubMed (US Gov / NIH)"
    elif source.lower() == "csir":
        source = "CSIR-NIScPR (Indian Gov)"
    
    query_keywords = set(extract_keywords_from_text(query, top_k=6))
    paper_keywords = set(extract_keywords_from_text(f"{title} {abstract}", top_k=8))
    shared = list(query_keywords.intersection(paper_keywords))

    reasons = []
    if year and year >= 2026:
        reasons.append("✨ 2026 Latest Breakthrough")
    elif year and year == 2025:
        reasons.append("Recent 2025 publication")

    if similarity_score >= 0.85:
        reasons.append(f"Very strong conceptual alignment ({similarity_score:.0%})")
    elif similarity_score >= 0.80:
        reasons.append(f"Strong semantic relevance ({similarity_score:.0%})")
    elif shared:
        reasons.append(f"Keyword match in title/abstract ({similarity_score:.0%})")
    else:
        reasons.append(f"Contextual proximity ({similarity_score:.0%})")

    if shared:
        reasons.append(f"shared concepts: {', '.join(shared[:3])}")
    
    if citations > 1000:
        reasons.append(f"highly cited landmark study ({citations:,} citations)")
    elif citations > 100:
        reasons.append(f"influential work ({citations:,} citations)")

    return f"Recommended via {source}: " + "; ".join(reasons) + "."


async def execute_recommendation_search(session: Session, req: SearchQueryRequest) -> SearchResponse:
    """
    Complete hybrid recommendation search workflow:
    1. Retrieve targeted local candidate papers from PostgreSQL via FAISS vector matches and indexed SQL filters
    2. Retrieve external papers from arXiv, PubMed (US Gov), Semantic Scholar, Crossref, DBLP (read-only)
    3. Deduplicate across repositories in-memory
    4. Resolve persistent primary keys read-only if candidates already exist in the catalog
    5. Perform read-only semantic vector search against existing FAISS index
    6. Compute transient in-memory semantic scores for external / unindexed candidates
    7. Rank, score, and attach explainability according to sort_by (recency, relevance, citations)
    """
    start_time = time.time()
    query = req.query.strip()
    if not query:
        return SearchResponse(
            query="",
            mode=req.mode,
            total_found=0,
            results=[],
            detected_keywords=[],
            execution_time_seconds=0.0
        )

    detected_keywords = extract_keywords_from_text(query, top_k=8)
    query_lower = query.lower()
    sort_mode = getattr(req, "sort_by", "relevance")
    enable_external = getattr(req, "enable_external_discovery", False)

    # Resolve provenance filter targets
    PROVENANCE_ALIASES = {
        "local": {"local", "pdf_upload"},
        "pdf_upload": {"local", "pdf_upload"},
        "arxiv": {"arxiv"},
        "pubmed": {"pubmed"},
        "csir": {"csir"},
        "semanticscholar": {"semanticscholar", "s2"},
        "crossref": {"crossref"},
        "dblp": {"dblp"},
    }

    target_provenances: Optional[Set[str]] = None
    if req.sources:
        target_provenances = set()
        for s in req.sources:
            norm_s = s.strip().lower()
            if norm_s:
                target_provenances.update(PROVENANCE_ALIASES.get(norm_s, {norm_s}))

    # 1. Gather targeted candidates from local database (always queried as primary catalog)
    all_candidates: List[Dict[str, Any]] = []
    local_pids = set()

    faiss_index = get_faiss_index()
    # Semantic pre-search in FAISS to find top vector matches among existing index
    semantic_matches = faiss_index.search(query, top_k=max(req.limit * 5, 50))
    semantic_pids = [
        meta["paper_id"] for meta, score in semantic_matches
        if meta.get("paper_id") and (score >= SEMANTIC_RELEVANCE_FLOOR or _has_lexical_match(meta, query_lower, detected_keywords))
    ]

    base_filter = []
    if req.min_year is not None:
        base_filter.append(Paper.year >= req.min_year)
    if req.max_year is not None:
        base_filter.append(Paper.year <= req.max_year)
    if req.min_citations is not None:
        base_filter.append(Paper.citation_count >= req.min_citations)
    if target_provenances is not None:
        base_filter.append(func.lower(Paper.source).in_(list(target_provenances)))

    distinctive_keywords = [
        kw for kw in detected_keywords
        if kw.lower().strip() not in GENERIC_SEARCH_TERMS and len(kw.strip()) >= 3
    ]
    search_keywords = distinctive_keywords if distinctive_keywords else detected_keywords

    text_clauses = []
    if query:
        text_clauses.append(Paper.title.ilike(f"%{query}%"))
        text_clauses.append(Paper.abstract.ilike(f"%{query}%"))
    for kw in search_keywords:
        text_clauses.append(Paper.title.ilike(f"%{kw}%"))
        text_clauses.append(Paper.abstract.ilike(f"%{kw}%"))

    candidate_map: Dict[str, Paper] = {}

    # 1a. Targeted query by indexed paper_ids from FAISS semantic search
    if semantic_pids:
        q_sem = session.query(Paper).filter(Paper.paper_id.in_(semantic_pids))
        if base_filter:
            q_sem = q_sem.filter(*base_filter)
        for p in q_sem.all():
            candidate_map[p.paper_id] = p

    # 1b. Targeted query by keywords/title with ordering aligned to sort_by
    if text_clauses:
        q_text = session.query(Paper).filter(or_(*text_clauses))
        if base_filter:
            q_text = q_text.filter(*base_filter)
        if sort_mode == "recency":
            q_text = q_text.order_by(Paper.year.desc().nullslast())
        elif sort_mode == "citations":
            q_text = q_text.order_by(Paper.citation_count.desc().nullslast())

        for p in q_text.limit(max(req.limit * 5, 50)).all():
            candidate_map[p.paper_id] = p

    # 1c. Bounded fallback ONLY for empty queries or explicit browse mode
    if not candidate_map and (not query or getattr(req, "mode", "") == "browse"):
        q_fallback = session.query(Paper)
        if base_filter:
            q_fallback = q_fallback.filter(*base_filter)
        if sort_mode == "recency":
            q_fallback = q_fallback.order_by(Paper.year.desc().nullslast())
        elif sort_mode == "citations":
            q_fallback = q_fallback.order_by(Paper.citation_count.desc().nullslast())
        for p in q_fallback.limit(max(req.limit * 3, 30)).all():
            candidate_map[p.paper_id] = p

    local_pids = set(candidate_map.keys())

    for lp in candidate_map.values():
        all_candidates.append({
            "id": lp.id,
            "paper_id": lp.paper_id,
            "title": lp.title,
            "abstract": lp.abstract,
            "authors": lp.authors,
            "venue": lp.venue,
            "year": lp.year,
            "doi": lp.doi,
            "url": lp.url,
            "pdf_url": lp.pdf_url,
            "source": lp.source,
            "citation_count": lp.citation_count,
            "categories": lp.categories or []
        })

    # 2. Gather candidates from external sources ONLY if explicitly requested
    new_external_papers = []
    if enable_external and len(query) > 2:
        if req.sources:
            external_sources = [s for s in req.sources if s.lower() not in ("local", "pdf_upload")]
        else:
            external_sources = ["arxiv", "semanticscholar", "crossref", "dblp", "pubmed", "csir"]

        if external_sources:
            try:
                sort_by_date = (sort_mode == "recency")
                external_papers = await search_all_sources(
                    query, limit_per_source=5, sort_by_date=sort_by_date, sources=external_sources
                )
                filtered_external = [
                    p for p in external_papers
                    if target_provenances is None or (p.get("source") or "").lower() in target_provenances
                ]
                all_candidates.extend(filtered_external)
                new_external_papers = filtered_external
            except Exception as e:
                logger.warning("External repository search exception: %s", e)

    # 3. Deduplicate
    unique_candidates = deduplicate_papers(all_candidates, similarity_threshold=0.85)

    # 4. Read-only resolution of existing database primary keys for external candidates
    # Ordinary search MUST NOT insert unpersisted papers into PostgreSQL
    unresolved = [p for p in unique_candidates if not p.get("id")]
    if unresolved:
        unresolved_pids = [p["paper_id"] for p in unresolved if p.get("paper_id")]
        if unresolved_pids:
            existing_db = session.query(Paper.id, Paper.paper_id).filter(Paper.paper_id.in_(unresolved_pids)).all()
            existing_map = {p.paper_id: p.id for p in existing_db}
            for paper in unresolved:
                pid = paper.get("paper_id")
                if pid and pid in existing_map:
                    paper["id"] = existing_map[pid]
                else:
                    paper["id"] = None

    # 5. Semantic Vector Search (Read-only FAISS index query; NO mutation)
    faiss_index = get_faiss_index()
    score_map: Dict[str, float] = {}
    try:
        faiss_results = faiss_index.search(query, top_k=max(req.limit * 3, 30))
        score_map = {p.get("paper_id"): score for p, score in faiss_results if p.get("paper_id")}
    except Exception as e:
        logger.warning("FAISS vector search exception: %s", e)

    # 6. Transient in-memory semantic scoring for candidates not indexed in FAISS
    unscored_candidates = [p for p in unique_candidates if p.get("paper_id") not in score_map]
    if unscored_candidates and query:
        try:
            query_emb = generate_embedding(query)
            for p in unscored_candidates:
                pid = p.get("paper_id")
                p_text = f"{p.get('title', '')}. {p.get('abstract', '')}".strip()
                if len(p_text) >= 5:
                    p_emb = generate_embedding(p_text)
                    sim = compute_cosine_similarity(query_emb, p_emb)
                    score_map[pid] = sim
        except Exception as emb_err:
            logger.debug("Transient embedding calculation skipped: %s", emb_err)

    # 7. Rank candidates
    ranked = []
    for paper in unique_candidates:
        pid = paper.get("paper_id")
        base_sim = score_map.get(pid, 0.0)

        # Evaluate lexical match
        has_lexical = _has_lexical_match(paper, query_lower, detected_keywords)

        # Fallback keyword match if vector score missing
        if base_sim == 0.0:
            title_match = any(kw in paper.get("title", "").lower() for kw in detected_keywords)
            abs_match = any(kw in (paper.get("abstract") or "").lower() for kw in detected_keywords)
            if title_match:
                base_sim = 0.65
            elif abs_match:
                base_sim = 0.50
            elif has_lexical:
                base_sim = 0.50
            else:
                base_sim = 0.30

        # Evidence-based relevance floor:
        # Pure semantic candidates (no lexical match in title/abstract) MUST meet the empirical relevance floor.
        # Candidates with keyword matches are preserved regardless of pure vector score.
        if not has_lexical and base_sim < SEMANTIC_RELEVANCE_FLOOR:
            continue

        # Filters
        if req.min_year and paper.get("year") and paper.get("year") < req.min_year:
            continue
        if req.max_year and paper.get("year") and paper.get("year") > req.max_year:
            continue
        if req.min_citations and paper.get("citation_count", 0) < req.min_citations:
            continue
        if target_provenances is not None:
            p_source = (paper.get("source") or "local").lower()
            if p_source not in target_provenances:
                continue

        # Explainable rationale and semantic score
        similarity_score = round(base_sim, 2)
        explanation = generate_recommendation_explanation(query, paper, similarity_score)

        paper_resp = PaperResponse(
            **paper,
            similarity_score=similarity_score,
            explanation=explanation
        )
        ranked.append(paper_resp)

    # Multi-mode Sorting: Recency (2026 First), Relevance (SPECTER2), or Citations
    if sort_mode == "recency":
        ranked.sort(
            key=lambda x: (
                x.year if x.year is not None else 0,
                x.similarity_score or 0.0,
                x.citation_count or 0
            ),
            reverse=True
        )
    elif sort_mode == "citations":
        ranked.sort(
            key=lambda x: (
                x.citation_count or 0,
                x.similarity_score or 0.0,
                x.year if x.year is not None else 0
            ),
            reverse=True
        )
    else:  # "relevance"
        ranked.sort(
            key=lambda x: (
                x.similarity_score or 0.0,
                x.year if x.year is not None else 0,
                x.citation_count or 0
            ),
            reverse=True
        )

    top_results = ranked[:req.limit]
    execution_time = round(time.time() - start_time, 3)

    return SearchResponse(
        query=query,
        mode=req.mode,
        total_found=len(ranked),
        results=top_results,
        detected_keywords=detected_keywords,
        execution_time_seconds=execution_time
    )
