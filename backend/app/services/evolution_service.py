"""
ResearchLens Research Evolution and Gap Explorer Service.
Builds evidence-grounded research timelines, inter-paper relationship graphs,
and testable candidate research-gap hypotheses from actual catalog metadata and verified quotes.

Enforces strict truthfulness:
- Local catalog absence is NEVER claimed as global scientific novelty.
- System inferences are strictly distinguished from explicit author claims.
- Every claim is linked to exact source passages with character offsets.
- Read-only exploration: zero database or FAISS mutations.
"""
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, asc

from app.core.logging import get_logger
from app.models.paper import Paper
from app.models.evidence import PaperEvidence
from app.schemas.research import (
    EvolutionStatus,
    GapConfidence,
    RelationshipStatus,
    TimelineEvidenceClaim,
    RelatedPaperLink,
    TimelinePaper,
    TimelineYearGroup,
    TimelineResponse,
    GraphNode,
    GraphEdge,
    RelationshipGraphResponse,
    GapEvidenceItem,
    CandidateGap,
    GapExplorationRequest,
    GapExplorationResponse,
)
from app.services.evidence_service import (
    extract_evidence_from_text,
    split_text_into_sentences_with_spans,
    is_synthetic_placeholder_abstract,
    ALL_EVIDENCE_CATEGORIES,
    CATEGORY_LABELS,
)
from app.services.driut_service import (
    classify_relationship_evidence,
    extract_effective_publication_year,
    _extract_dataset_keywords,
    _extract_metric_keywords,
    _gather_paper_evidence_for_driut,
)
from app.services.embedding_service import (
    generate_embedding,
    compute_cosine_similarity,
)
from app.services.vector_index import get_faiss_index
from app.core.config import get_settings
from app.services.ai_provider import (
    get_ai_coordinator,
    RESEARCH_GAP_SYSTEM_PROMPT,
)
from app.services.ai_output_guard import enforce_ai_output_security_guard
import asyncio
import concurrent.futures

logger = get_logger(__name__)


def _run_async_safe(coro):
    """Safely execute coroutine whether inside or outside an active asyncio event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


# ==============================================================================
# Helper Utilities (Zero-Mutation)
# ==============================================================================

def _paper_to_dict(p: Paper) -> Dict[str, Any]:
    """Convert Paper model to dictionary representation without mutating session."""
    return {
        "id": p.id,
        "paper_id": p.paper_id,
        "title": p.title or "",
        "abstract": p.abstract or "",
        "authors": p.authors or [],
        "venue": p.venue or "",
        "year": p.year,
        "doi": p.doi,
        "url": p.url,
        "raw_text": p.raw_text or "",
    }


def _gather_paper_claims(p: Paper, db: Session) -> Tuple[Dict[str, List[TimelineEvidenceClaim]], str]:
    """
    Extract grounded evidence claims for a paper.
    Reuses existing PaperEvidence records if available; otherwise performs
    in-memory extraction with zero database writes.
    """
    claims_by_category: Dict[str, List[TimelineEvidenceClaim]] = defaultdict(list)
    source_type = "abstract"

    # 1. Try DB records
    existing_records = db.query(PaperEvidence).filter(PaperEvidence.paper_id == p.id).all()
    if existing_records:
        for r in existing_records:
            source_type = r.source_type or source_type
            claims_by_category[r.category].append(TimelineEvidenceClaim(
                category=r.category,
                claim=r.claim,
                source_passage=r.source_passage,
                char_start=r.char_start,
                char_end=r.char_end,
                section_name=r.section_name or ("Abstract" if source_type == "abstract" else None),
                confidence_score=r.confidence_score or 0.85
            ))
        return claims_by_category, source_type

    # 2. In-memory extraction (zero DB write)
    text = (p.raw_text or "").strip()
    if text and len(text) > len(p.abstract or "") + 50:
        source_type = "full_text"
    else:
        text = (p.abstract or "").strip()
        source_type = "abstract"

    if is_synthetic_placeholder_abstract(text) and source_type == "abstract":
        return claims_by_category, "unavailable"

    if text and len(text) >= 20:
        raw_items, _ = extract_evidence_from_text(text, source_type=source_type, max_items_per_category=3)
        for item in raw_items:
            claims_by_category[item["category"]].append(TimelineEvidenceClaim(
                category=item["category"],
                claim=item["claim"],
                source_passage=item["source_passage"],
                char_start=item.get("char_start"),
                char_end=item.get("char_end"),
                section_name=item.get("section_name"),
                confidence_score=item.get("confidence_score", 0.80)
            ))

    return claims_by_category, source_type


def _query_relevant_papers(
    db: Session,
    topic: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    limit: int = 50
) -> List[Paper]:
    """
    Retrieve candidate papers matching topic and date range.
    Uses FAISS vector search when topic is provided and index is ready,
    combined with SQL text search to ensure comprehensive coverage.
    """
    paper_ids_ordered: List[int] = []

    if topic and topic.strip():
        clean_topic = topic.strip()
        COMMON_TOPIC_EXPANSIONS = {
            "aiml": ["artificial intelligence", "machine learning", "deep learning"],
            "ai/ml": ["artificial intelligence", "machine learning", "deep learning"],
            "ai": ["artificial intelligence"],
            "ml": ["machine learning"],
            "nlp": ["natural language processing"],
            "llm": ["large language model", "language model"],
            "cv": ["computer vision"],
            "rl": ["reinforcement learning"],
        }
        topic_lower = clean_topic.lower()
        expanded_terms = COMMON_TOPIC_EXPANSIONS.get(topic_lower, [])

        # 1. Exact title matches have highest priority
        title_clauses = [Paper.title.ilike(f"%{clean_topic}%")]
        for exp in expanded_terms:
            title_clauses.append(Paper.title.ilike(f"%{exp}%"))
        title_ids = [row[0] for row in db.query(Paper.id).filter(or_(*title_clauses)).limit(limit).all()]
        for pid in title_ids:
            if pid not in paper_ids_ordered:
                paper_ids_ordered.append(pid)

        # 2. Semantic search via FAISS guarded by topical keywords
        topic_keywords = [
            w.lower() for w in re.findall(r"\b[A-Za-z0-9_-]{3,}\b", clean_topic)
            if w.lower() not in {"the", "and", "for", "with", "from", "that", "this", "model", "study", "using", "based"}
        ]
        for exp in expanded_terms:
            topic_keywords.extend([
                w.lower() for w in re.findall(r"\b[A-Za-z0-9_-]{3,}\b", exp)
                if w.lower() not in {"the", "and", "for", "with", "from", "that", "this", "model", "study", "using", "based"}
            ])

        try:
            faiss_index = get_faiss_index()
            if faiss_index and faiss_index.index and faiss_index.index.ntotal > 0:
                vector_results = faiss_index.search(clean_topic, top_k=limit * 2)
                # Resolve DB paper IDs for candidates where meta.get("id") is unpopulated
                unresolved_pids = [
                    meta["paper_id"] for meta, _ in vector_results
                    if not meta.get("id") and meta.get("paper_id")
                ]
                db_id_map = {}
                if unresolved_pids:
                    id_rows = db.query(Paper.paper_id, Paper.id).filter(Paper.paper_id.in_(unresolved_pids)).all()
                    db_id_map = {row[0]: row[1] for row in id_rows}

                for meta, score in vector_results:
                    meta_text = f"{meta.get('title', '')} {meta.get('abstract', '')}".lower()
                    has_kw = any(kw in meta_text for kw in topic_keywords) if topic_keywords else True
                    pid = meta.get("id") or db_id_map.get(meta.get("paper_id"))
                    if (has_kw or score >= 0.85) and pid:
                        pid = int(pid)
                        if pid not in paper_ids_ordered:
                            paper_ids_ordered.append(pid)
        except Exception as e:
            logger.warning("FAISS vector search failed during topic query (%s); using SQL search", e)

        # 3. SQL keyword search in abstract and venue
        search_clauses = [
            Paper.abstract.ilike(f"%{clean_topic}%"),
            Paper.venue.ilike(f"%{clean_topic}%")
        ]
        for exp in expanded_terms:
            search_clauses.append(Paper.abstract.ilike(f"%{exp}%"))
        kw_query = db.query(Paper.id).filter(or_(*search_clauses))
        sql_ids = [row[0] for row in kw_query.limit(limit * 2).all()]
        for pid in sql_ids:
            if pid not in paper_ids_ordered:
                paper_ids_ordered.append(pid)

        if paper_ids_ordered:
            # Filter papers by date and preserve top matches
            q = db.query(Paper).filter(Paper.id.in_(paper_ids_ordered))
            if start_year is not None:
                q = q.filter(or_(Paper.year >= start_year, Paper.year.is_(None)))
            if end_year is not None:
                q = q.filter(or_(Paper.year <= end_year, Paper.year.is_(None)))
            fetched = q.all()
            id_to_paper = {p.id: p for p in fetched}
            ordered_papers = [id_to_paper[pid] for pid in paper_ids_ordered if pid in id_to_paper]
            return ordered_papers[:limit]

        # Specific topic provided but no catalog papers matched: return empty list
        return []

    # No topic provided: return catalog papers sorted by publication year
    q = db.query(Paper)
    if start_year is not None:
        q = q.filter(or_(Paper.year >= start_year, Paper.year.is_(None)))
    if end_year is not None:
        q = q.filter(or_(Paper.year <= end_year, Paper.year.is_(None)))
    # Place dated papers first, then undated
    papers = q.order_by(Paper.year.desc().nullslast(), Paper.id.desc()).limit(limit).all()
    return papers


# ==============================================================================
# 1. Research Evolution Timeline Implementation
# ==============================================================================

def build_research_timeline(
    db: Session,
    topic: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    limit: int = 50
) -> TimelineResponse:
    """
    Constructs an evidence-backed chronological research timeline.
    Separates publication dates from ingestion times; isolates undated papers transparently;
    links claims to exact source passages.
    """
    papers = _query_relevant_papers(db, topic=topic, start_year=start_year, end_year=end_year, limit=limit)

    if not papers:
        return TimelineResponse(
            topic=topic,
            start_year=start_year,
            end_year=end_year,
            total_papers_examined=0,
            total_dated_papers=0,
            total_undated_papers=0,
            status=EvolutionStatus.EMPTY,
            timeline=[],
            coverage_notes="No papers found matching the specified topic and date criteria in the local catalog."
        )

    # Convert to TimelinePaper models
    timeline_papers: List[TimelinePaper] = []
    dated_count = 0
    undated_count = 0

    # Cache for pairwise relations among timeline papers
    paper_dicts = [_paper_to_dict(p) for p in papers]

    for p, p_dict in zip(papers, paper_dicts):
        claims_map, src_type = _gather_paper_claims(p, db)

        # Year validation: distinguish real publication year from scheduled future issue and ingestion time
        is_undated = False
        date_note = None
        assigned_year = p.year

        if assigned_year is None or assigned_year <= 1900 or assigned_year > 2035:
            is_undated = True
            undated_count += 1
            date_note = "Publication year unrecorded or uncertain in catalog metadata."
            assigned_year = None
        else:
            # Check effective electronic vs print publication year
            eff_year, is_scheduled, src_note = extract_effective_publication_year(p_dict)
            if eff_year is not None and eff_year <= 2026:
                if assigned_year > 2026:
                    date_note = f"Published electronically in {eff_year}; scheduled print issue in {assigned_year}."
                assigned_year = eff_year
                dated_count += 1
            elif assigned_year > 2026:
                dated_count += 1
                date_note = f"Forthcoming / Scheduled publication ({assigned_year}). Advance research preprint or ahead-of-print article."
            else:
                dated_count += 1

        # Check relationships with chronologically preceding papers (up to 3 closest)
        related_links: List[RelatedPaperLink] = []
        for other_p, other_dict in zip(papers, paper_dicts):
            if other_p.id == p.id:
                continue
            # Only connect if there's topical affinity
            if assigned_year and other_p.year and assigned_year >= other_p.year:
                try:
                    rel_res = classify_relationship_evidence(other_dict, p_dict, db=db)
                    if rel_res.is_supported and rel_res.relationship_type:
                        is_author = (rel_res.evidence_strength == "strong_evidence" and rel_res.evidence_passage is not None)
                        related_links.append(RelatedPaperLink(
                            target_paper_id=other_p.id,
                            target_paper_title=other_p.title,
                            relationship_type=rel_res.relationship_type,
                            relationship_status=RelationshipStatus.AUTHOR_STATED.value if is_author else RelationshipStatus.INFERRED_EVIDENCE.value,
                            is_author_stated=is_author,
                            evidence_quote=rel_res.evidence_passage
                        ))
                    elif rel_res.semantic_similarity >= 0.65:
                        related_links.append(RelatedPaperLink(
                            target_paper_id=other_p.id,
                            target_paper_title=other_p.title,
                            relationship_type="Thematic Similarity",
                            relationship_status=RelationshipStatus.THEMATIC_ONLY.value,
                            is_author_stated=False,
                            evidence_quote=None
                        ))
                except Exception as e:
                    logger.debug("Relationship check skipped for timeline papers %s and %s: %s", p.id, other_p.id, e)

            if len(related_links) >= 3:
                break

        tp = TimelinePaper(
            id=p.id,
            paper_id=p.paper_id,
            title=p.title,
            authors=p.authors or [],
            venue=p.venue,
            year=assigned_year,
            is_undated=is_undated,
            date_uncertainty_note=date_note,
            doi=p.doi,
            url=p.url,
            problem_claims=claims_map.get("problem", []),
            objective_claims=claims_map.get("objective", []),
            method_changes=claims_map.get("method", []) + claims_map.get("contributions", []),
            dataset_claims=claims_map.get("dataset", []),
            metric_claims=claims_map.get("metrics", []),
            findings_claims=claims_map.get("results", []),
            limitation_claims=claims_map.get("limitations", []),
            future_work_claims=claims_map.get("future_work", []),
            related_links=related_links,
            provenance_source=src_type
        )
        timeline_papers.append(tp)

    # Group by publication year chronologically
    year_map: Dict[Optional[int], List[TimelinePaper]] = defaultdict(list)
    for tp in timeline_papers:
        year_map[tp.year].append(tp)

    year_groups: List[TimelineYearGroup] = []
    # 1. Sorted dated groups (ascending chronological order)
    dated_years = sorted([y for y in year_map.keys() if y is not None])
    for y in dated_years:
        group_papers = year_map[y]
        # Extract prominent keywords/themes for this year
        themes = set()
        for gp in group_papers:
            for c in gp.method_changes[:2]:
                words = [w for w in re.findall(r"\b[A-Za-z]{4,}\b", c.claim) if w.lower() not in {"this", "that", "with", "from", "were", "have"}]
                themes.update(words[:2])
        label = f"{y} (Forthcoming / Scheduled Issue)" if y > 2026 else str(y)
        year_groups.append(TimelineYearGroup(
            year=y,
            year_label=label,
            paper_count=len(group_papers),
            papers=group_papers,
            key_themes=sorted(list(themes))[:4]
        ))

    # 2. Undated group (at the end with transparent disclosure)
    if None in year_map:
        undated_papers = year_map[None]
        year_groups.append(TimelineYearGroup(
            year=None,
            year_label="Undated / Uncertain Year",
            paper_count=len(undated_papers),
            papers=undated_papers,
            key_themes=["Uncertain Publication Date"]
        ))

    status = EvolutionStatus.COMPLETE if len(timeline_papers) >= 5 else EvolutionStatus.PARTIAL_COVERAGE
    coverage_note = None
    if undated_count > 0:
        coverage_note = f"{undated_count} of {len(timeline_papers)} papers have unrecorded publication years and are listed in the 'Undated / Uncertain Year' group."

    return TimelineResponse(
        topic=topic,
        start_year=start_year,
        end_year=end_year,
        total_papers_examined=len(timeline_papers),
        total_dated_papers=dated_count,
        total_undated_papers=undated_count,
        status=status,
        timeline=year_groups,
        coverage_notes=coverage_note
    )


# ==============================================================================
# 2. Research Relationship Graph Implementation
# ==============================================================================

def build_relationship_graph(
    db: Session,
    topic: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    min_similarity: float = 0.45,
    max_nodes: int = 25
) -> RelationshipGraphResponse:
    """
    Constructs an interactive research relationship graph.
    Distinguishes author-stated relations, evidence-grounded inferences,
    and thematic proximity. Never invents citation links.
    """
    bounded_max_nodes = max(2, min(max_nodes, 40))
    papers = _query_relevant_papers(
        db,
        topic=topic,
        start_year=start_year,
        end_year=end_year,
        limit=bounded_max_nodes
    )

    if not papers:
        return RelationshipGraphResponse(
            topic=topic,
            nodes=[],
            edges=[],
            total_nodes=0,
            total_edges=0,
            edge_type_counts={},
            status=EvolutionStatus.EMPTY,
            coverage_notes="No papers found matching criteria."
        )

    # 1. Build Nodes
    nodes: List[GraphNode] = []
    p_dicts: List[Dict[str, Any]] = []
    for p in papers:
        is_undated = (p.year is None or p.year <= 1900 or p.year > 2035)
        nodes.append(GraphNode(
            id=p.id,
            paper_id=p.paper_id,
            label=p.title,
            year=p.year if not is_undated else None,
            is_undated=is_undated,
            venue=p.venue,
            authors=p.authors or [],
            citation_count=p.citation_count or 0
        ))
        p_dicts.append(_paper_to_dict(p))

    # 2. Build Edges (Pairwise relationship exploration)
    edges: List[GraphEdge] = []
    edge_counts: Dict[str, int] = defaultdict(int)
    n = len(papers)

    for i in range(n):
        for j in range(i + 1, n):
            p1_dict = p_dicts[i]
            p2_dict = p_dicts[j]

            try:
                # Classify relationship in both directions to detect directional claims (e.g. A improves upon B)
                # First direction: p2 vs p1 (p2 candidate, p1 baseline)
                rel_forward = classify_relationship_evidence(p1_dict, p2_dict, db=db)
                # Reverse direction: p1 vs p2 (p1 candidate, p2 baseline)
                rel_reverse = classify_relationship_evidence(p2_dict, p1_dict, db=db)

                # Pick the more strongly supported direction
                chosen_rel = rel_forward
                src_dict, tgt_dict = p2_dict, p1_dict
                if not rel_forward.is_supported and rel_reverse.is_supported:
                    chosen_rel = rel_reverse
                    src_dict, tgt_dict = p1_dict, p2_dict
                elif rel_reverse.is_supported and rel_reverse.confidence_score > rel_forward.confidence_score:
                    chosen_rel = rel_reverse
                    src_dict, tgt_dict = p1_dict, p2_dict

                sim = chosen_rel.semantic_similarity or 0.0

                if chosen_rel.is_supported and chosen_rel.relationship_type:
                    is_author = (chosen_rel.evidence_strength == "strong_evidence" and chosen_rel.evidence_passage is not None)
                    rel_status = RelationshipStatus.AUTHOR_STATED if is_author else RelationshipStatus.INFERRED_EVIDENCE
                    
                    edge = GraphEdge(
                        source=src_dict["id"],
                        target=tgt_dict["id"],
                        source_paper_id=src_dict["paper_id"],
                        target_paper_id=tgt_dict["paper_id"],
                        source_title=src_dict["title"],
                        target_title=tgt_dict["title"],
                        relationship_type=chosen_rel.relationship_type,
                        relationship_status=rel_status,
                        is_author_stated=is_author,
                        confidence_score=chosen_rel.confidence_score,
                        evidence_strength=chosen_rel.evidence_strength,
                        evidence_passage=chosen_rel.evidence_passage,
                        char_start=chosen_rel.char_start,
                        char_end=chosen_rel.char_end,
                        section_name=chosen_rel.section_name,
                        semantic_similarity=sim,
                        explanation=chosen_rel.explanation,
                        comparability_notes=chosen_rel.comparability_notes,
                        uncertainty_warning=chosen_rel.uncertainty_warning
                    )
                    edges.append(edge)
                    edge_counts[chosen_rel.relationship_type] += 1

                elif sim >= min_similarity:
                    # Thematic similarity edge without proof of stronger relationship
                    edge = GraphEdge(
                        source=p1_dict["id"],
                        target=p2_dict["id"],
                        source_paper_id=p1_dict["paper_id"],
                        target_paper_id=p2_dict["paper_id"],
                        source_title=p1_dict["title"],
                        target_title=p2_dict["title"],
                        relationship_type="Thematic Similarity",
                        relationship_status=RelationshipStatus.THEMATIC_ONLY,
                        is_author_stated=False,
                        confidence_score=round(sim, 2),
                        evidence_strength="insufficient_evidence",
                        evidence_passage=None,
                        char_start=None,
                        char_end=None,
                        section_name=None,
                        semantic_similarity=sim,
                        explanation=(
                            f"Papers exhibit semantic similarity ({sim:.1%}) within the corpus space, "
                            "but source texts contain insufficient scientific evidence to establish an explicit "
                            "extension, improvement, alternative, or contradiction."
                        ),
                        comparability_notes=None,
                        uncertainty_warning="Thematic proximity does NOT prove citation, direct influence, or agreement."
                    )
                    edges.append(edge)
                    edge_counts["Thematic Similarity"] += 1

            except Exception as e:
                logger.debug("Graph edge evaluation error between %s and %s: %s", p1_dict["id"], p2_dict["id"], e)

    # Bound edge count to prevent graph clutter (keep top 60 edges by confidence)
    edges.sort(key=lambda e: (e.relationship_status != RelationshipStatus.THEMATIC_ONLY, e.confidence_score), reverse=True)
    bounded_edges = edges[:60]

    status = EvolutionStatus.COMPLETE if len(nodes) >= 4 else EvolutionStatus.PARTIAL_COVERAGE

    return RelationshipGraphResponse(
        topic=topic,
        nodes=nodes,
        edges=bounded_edges,
        total_nodes=len(nodes),
        total_edges=len(bounded_edges),
        edge_type_counts=dict(edge_counts),
        status=status,
        coverage_notes=f"Examined {len(nodes)} papers in local catalog. Evaluated {len(bounded_edges)} inter-paper relationships."
    )


# ==============================================================================
# 3. Candidate Research-Gap Explorer Implementation
# ==============================================================================

# Common Bottleneck Clusters for Author Limitations
LIMITATION_THEMES = [
    {
        "id": "comp_overhead",
        "title": "Computational Overhead & Scalability Bottlenecks",
        "keywords": ["computational", "overhead", "memory", "gpu", "latency", "throughput", "scale", "cost", "hardware", "expensive"],
        "hypothesis_tmpl": "Recurring Bottleneck: Authors report prohibitive computational/memory overhead. Developing lightweight architectures or sub-quadratic approximations remains an open challenge under this topic."
    },
    {
        "id": "data_scarcity",
        "title": "Data Scarcity & High Annotation Dependency",
        "keywords": ["annotation", "scarcity", "labeled", "supervision", "few-shot", "sample", "imbalance", "labeling"],
        "hypothesis_tmpl": "Supervision Bottleneck: Multiple studies highlight reliance on extensive ground-truth annotations. Unsupervised, self-supervised, or active-learning adaptations represent high-impact candidate directions."
    },
    {
        "id": "robustness_ood",
        "title": "Out-of-Distribution Vulnerability & Robustness Degradation",
        "keywords": ["robustness", "vulnerability", "out-of-distribution", "generalization", "domain shift", "adversarial", "sensitive", "degrades"],
        "hypothesis_tmpl": "Generalization Fragility: Authors independently observe performance drops under domain shifts or distribution drift. Robustness-certified frameworks warrant structured validation."
    },
    {
        "id": "interpretability",
        "title": "Black-Box Opacity & Interpretability Constraints",
        "keywords": ["interpretability", "explainability", "opaque", "black-box", "transparency", "reasoning", "uninterpretable"],
        "hypothesis_tmpl": "Interpretability Deficit: Stated limitations emphasize a lack of faithful explanation mechanisms. Mechanistic interpretability or concept-bottleneck approaches are strongly indicated."
    }
]

# Common Future Work Clusters
FUTURE_WORK_THEMES = [
    {
        "id": "multimodal",
        "title": "Cross-Modal & Multimodal Integration",
        "keywords": ["multimodal", "vision", "audio", "cross-modal", "multi-modal", "video", "sensor", "speech"],
        "hypothesis_tmpl": "Converging Direction: Authors independently propose extending these approaches to multimodal inputs. Fusing textual and perceptual signals offers an articulated path for follow-up work."
    },
    {
        "id": "efficiency",
        "title": "Model Compression, Quantization & Edge Deployment",
        "keywords": ["quantization", "pruning", "distillation", "edge", "mobile", "real-time", "lightweight", "compact"],
        "hypothesis_tmpl": "Efficiency Push: Independent proposals converge on quantization, pruning, or knowledge distillation for edge-constrained execution."
    },
    {
        "id": "cross_lingual",
        "title": "Low-Resource & Cross-Lingual Generalization",
        "keywords": ["cross-lingual", "low-resource", "multilingual", "dialects", "zero-shot", "transfer"],
        "hypothesis_tmpl": "Inclusive Evaluation: Recurring future-work goals stress evaluation on low-resource and non-English corpora to mitigate language bias."
    }
]


def explore_candidate_gaps(
    db: Session,
    request: GapExplorationRequest
) -> GapExplorationResponse:
    """
    Synthesizes grounded research-gap candidate hypotheses.
    Strictly follows truthfulness rules:
    - Never declares global novelty from local absence.
    - Explicitly separates local corpus coverage gaps from potential scientific gaps.
    - Requires human validation for all suggestions.
    - Returns INSUFFICIENT_EVIDENCE if corpus is too small or metadata sparse.
    """
    papers = _query_relevant_papers(
        db,
        topic=request.topic,
        start_year=request.start_year,
        end_year=request.end_year,
        limit=50
    )

    corpus_size = len(papers)
    corpus_summary = {
        "examined_papers_count": corpus_size,
        "topic_filter": request.topic,
        "start_year": request.start_year,
        "end_year": request.end_year,
        "min_corpus_required": request.min_corpus_size,
    }

    # Strict Rule 6: If corpus too small, return insufficient evidence rather than confident claims
    if corpus_size < request.min_corpus_size:
        return GapExplorationResponse(
            topic=request.topic,
            total_papers_examined=corpus_size,
            total_gaps_found=0,
            status=EvolutionStatus.INSUFFICIENT_EVIDENCE,
            candidate_gaps=[],
            corpus_summary=corpus_summary,
            truthfulness_disclosure=(
                f"INSUFFICIENT EVIDENCE: Only {corpus_size} paper(s) found in the selected corpus "
                f"(minimum {request.min_corpus_size} required). Formulating research gap hypotheses "
                "on a tiny or sparse catalog risks high false-discovery rates. Please broaden your search filter "
                "or ingest additional papers before gap analysis."
            )
        )

    # Gather evidence and extracted metadata for all papers in corpus
    all_limitations: List[Tuple[Paper, TimelineEvidenceClaim]] = []
    all_future_work: List[Tuple[Paper, TimelineEvidenceClaim]] = []
    paper_datasets: Dict[int, Set[str]] = {}
    paper_methods: Dict[int, Set[str]] = {}
    paper_results: List[Tuple[Paper, TimelineEvidenceClaim]] = []

    for p in papers:
        claims_map, _ = _gather_paper_claims(p, db)
        for lim in claims_map.get("limitations", []):
            all_limitations.append((p, lim))
        for fw in claims_map.get("future_work", []):
            all_future_work.append((p, fw))
        for res in claims_map.get("results", []):
            paper_results.append((p, res))

        # Extract dataset keywords
        text = f"{p.title} {p.abstract or ''}"
        dsets = _extract_dataset_keywords(text)
        paper_datasets[p.id] = dsets

        # Extract method phrases
        m_terms = set()
        for mc in claims_map.get("method", [])[:2]:
            m_terms.add(mc.claim[:40].strip())
        paper_methods[p.id] = m_terms

    candidate_gaps: List[CandidateGap] = []
    scope_str = f"Local ResearchLens catalog: '{request.topic or 'all topics'}', N={corpus_size} papers examined"
    years = [p.year for p in papers if p.year and p.year > 1900]
    time_range_str = f"{min(years)} - {max(years)}" if years else "Unrecorded / Diverse Years"

    # --------------------------------------------------------------------------
    # Signal 1: Recurring Limitations across multiple papers
    # --------------------------------------------------------------------------
    for theme in LIMITATION_THEMES:
        motivating_items: List[GapEvidenceItem] = []
        seen_papers = set()

        for p, lim in all_limitations:
            quote_lower = lim.source_passage.lower()
            if any(kw in quote_lower for kw in theme["keywords"]):
                if p.id not in seen_papers:
                    seen_papers.add(p.id)
                    motivating_items.append(GapEvidenceItem(
                        paper_id=p.id,
                        paper_code=p.paper_id,
                        paper_title=p.title,
                        year=p.year,
                        quote=lim.source_passage,
                        char_start=lim.char_start,
                        char_end=lim.char_end,
                        section_name=lim.section_name,
                        category="limitations",
                        context_note=f"Reported limitation matching theme: {theme['title']}"
                    ))

        if len(seen_papers) >= 2:
            confidence = min(0.92, 0.65 + (len(seen_papers) * 0.08))
            gap = CandidateGap(
                gap_id=f"gap-lim-{theme['id']}",
                gap_type="recurring_limitation",
                title=f"Recurring Limitation: {theme['title']}",
                concise_hypothesis=theme["hypothesis_tmpl"],
                evidence_strength=GapConfidence.STRONG_RECURRENCE if len(seen_papers) >= 3 else GapConfidence.MODERATE_PATTERN,
                confidence_score=round(confidence, 2),
                is_corpus_coverage_gap=False,
                motivating_evidence=motivating_items[:4],
                contradicting_evidence=[],
                relevant_papers_examined=len(seen_papers),
                corpus_scope=scope_str,
                time_range=time_range_str,
                limitations="Synthesized from explicit limitation statements in the local catalog. External unindexed papers may already address this bottleneck.",
                recommended_verification_steps=[
                    "Conduct a targeted literature search on Google Scholar / arXiv using the bottleneck keywords.",
                    "Review recent survey papers published after the examined dates to verify if scalable solutions emerged.",
                    "Benchmark candidate baseline methods under resource-constrained conditions."
                ],
                human_validation_required=True
            )
            candidate_gaps.append(gap)

    # --------------------------------------------------------------------------
    # Signal 2: Converging Future-Work Directions
    # --------------------------------------------------------------------------
    for fw_theme in FUTURE_WORK_THEMES:
        fw_items: List[GapEvidenceItem] = []
        seen_fw_papers = set()

        for p, fw in all_future_work:
            fw_lower = fw.source_passage.lower()
            if any(kw in fw_lower for kw in fw_theme["keywords"]):
                if p.id not in seen_fw_papers:
                    seen_fw_papers.add(p.id)
                    fw_items.append(GapEvidenceItem(
                        paper_id=p.id,
                        paper_code=p.paper_id,
                        paper_title=p.title,
                        year=p.year,
                        quote=fw.source_passage,
                        char_start=fw.char_start,
                        char_end=fw.char_end,
                        section_name=fw.section_name,
                        category="future_work",
                        context_note=f"Explicit future-work statement targeting: {fw_theme['title']}"
                    ))

        if len(seen_fw_papers) >= 2:
            confidence = min(0.88, 0.60 + (len(seen_fw_papers) * 0.07))
            gap = CandidateGap(
                gap_id=f"gap-fw-{fw_theme['id']}",
                gap_type="recurring_future_work",
                title=f"Converging Future Direction: {fw_theme['title']}",
                concise_hypothesis=fw_theme["hypothesis_tmpl"],
                evidence_strength=GapConfidence.STRONG_RECURRENCE if len(seen_fw_papers) >= 3 else GapConfidence.MODERATE_PATTERN,
                confidence_score=round(confidence, 2),
                is_corpus_coverage_gap=False,
                motivating_evidence=fw_items[:4],
                contradicting_evidence=[],
                relevant_papers_examined=len(seen_fw_papers),
                corpus_scope=scope_str,
                time_range=time_range_str,
                limitations="Based on author aspirations in catalog papers. May already be actively explored in subsequent publications.",
                recommended_verification_steps=[
                    "Verify whether follow-up works by the citing authors implemented the proposed extensions.",
                    "Search conference proceedings for recent workshops focused specifically on this sub-direction."
                ],
                human_validation_required=True
            )
            candidate_gaps.append(gap)

    # --------------------------------------------------------------------------
    # Signal 3: Cross-Dataset / Benchmark Evaluation Gap
    # --------------------------------------------------------------------------
    # Identify prominent benchmarks in the corpus that are only evaluated by a subset of methods
    benchmark_counts = defaultdict(list)
    for pid, dsets in paper_datasets.items():
        for d in dsets:
            benchmark_counts[d].append(pid)

    # If benchmark D is evaluated by >= 2 papers, but other topically close papers lack it
    for benchmark, eval_pids in benchmark_counts.items():
        if len(eval_pids) >= 2 and len(eval_pids) < corpus_size:
            unevaluated_pids = [p.id for p in papers if p.id not in eval_pids][:2]
            unevaluated_papers = [p for p in papers if p.id in unevaluated_pids]
            eval_papers = [p for p in papers if p.id in eval_pids][:2]

            motivating_items = []
            for ep in eval_papers:
                ep_text = (ep.abstract or "").strip()
                spans = split_text_into_sentences_with_spans(ep_text)
                matched_passage = None
                matched_s = None
                matched_e = None
                for passage, s_start, s_end in spans:
                    if re.search(r"\b" + re.escape(benchmark) + r"\b", passage, re.IGNORECASE):
                        matched_passage = passage
                        matched_s = s_start
                        matched_e = s_end
                        break
                if not matched_passage:
                    if re.search(r"\b" + re.escape(benchmark) + r"\b", ep.title or "", re.IGNORECASE):
                        matched_passage = ep.title
                        matched_s = 0
                        matched_e = len(ep.title)
                        sec_name = "Title"
                    else:
                        matched_passage = ep_text[:200] if ep_text else ep.title
                        matched_s = 0 if matched_passage else None
                        matched_e = len(matched_passage) if matched_passage else None
                        sec_name = "Abstract"
                else:
                    sec_name = "Abstract"

                motivating_items.append(GapEvidenceItem(
                    paper_id=ep.id,
                    paper_code=ep.paper_id,
                    paper_title=ep.title,
                    year=ep.year,
                    quote=matched_passage,
                    char_start=matched_s,
                    char_end=matched_e,
                    section_name=sec_name,
                    category="dataset",
                    context_note=f"Establishes '{benchmark.upper()}' as a key benchmark in this corpus."
                ))

            candidate_gaps.append(CandidateGap(
                gap_id=f"gap-eval-{benchmark}",
                gap_type="cross_dataset_method_gap",
                title=f"Cross-Benchmark Evaluation Gap: '{benchmark.upper()}' Benchmark",
                concise_hypothesis=(
                    f"The '{benchmark.upper()}' benchmark is used for standard evaluation in several corpus papers, "
                    f"yet key methods such as '{unevaluated_papers[0].title[:50]}...' lack reported evaluation on it. "
                    f"A standardized comparative evaluation on '{benchmark.upper()}' would clarify relative generalizability."
                ),
                evidence_strength=GapConfidence.MODERATE_PATTERN,
                confidence_score=0.75,
                is_corpus_coverage_gap=False,
                motivating_evidence=motivating_items,
                contradicting_evidence=[],
                relevant_papers_examined=len(eval_pids) + len(unevaluated_pids),
                corpus_scope=scope_str,
                time_range=time_range_str,
                limitations="Analysis limited to benchmark citations within local catalog abstracts. Full papers may contain supplementary evaluations.",
                recommended_verification_steps=[
                    f"Inspect the full text of unevaluated papers to verify if '{benchmark}' was evaluated in an appendix.",
                    f"Search Papers With Code to check current leaderboards for '{benchmark}'."
                ],
                human_validation_required=True
            ))
            break  # Limit to 1 prominent cross-benchmark gap to prevent redundancy

    # --------------------------------------------------------------------------
    # Signal 4: Local Corpus Coverage Disclosures (Strict Truthfulness)
    # --------------------------------------------------------------------------
    # Always include a clear corpus coverage disclosure gap to ensure researchers
    # never conflate local catalog boundaries with global scientific novelty
    candidate_gaps.append(CandidateGap(
        gap_id="gap-coverage-catalog-boundary",
        gap_type="corpus_coverage_gap",
        title="Local Catalog Boundary vs. Global Research Frontier",
        concise_hypothesis=(
            f"This analysis examined {corpus_size} papers currently cataloged in ResearchLens under '{request.topic or 'all'}'. "
            "Apparent thematic voids or missing combinations in this local index represent catalog coverage boundaries, "
            "and MUST NOT be claimed as worldwide scientific novelty without comprehensive external systematic literature review."
        ),
        evidence_strength=GapConfidence.PRELIMINARY_HYPOTHESIS,
        confidence_score=0.99,
        is_corpus_coverage_gap=True,
        motivating_evidence=[],
        contradicting_evidence=[],
        relevant_papers_examined=corpus_size,
        corpus_scope=scope_str,
        time_range=time_range_str,
        limitations="Corpus represents a curated local sample; arXiv, Semantic Scholar, and ACM Digital Library contain millions of broader works.",
        recommended_verification_steps=[
            "Always corroborate candidate gaps via Google Scholar, arXiv, and Semantic Scholar API searches.",
            "Import missing landmark papers into ResearchLens to expand coverage before finalizing research questions.",
            "Consult domain experts to identify unindexed foundational literature."
        ],
        human_validation_required=True
    ))

    # Bound gap results
    bounded_gaps = candidate_gaps[:request.max_gaps]

    # AI Layer Enhancement (Grounded Gap Explanation)
    ai_provider_name = "deterministic"
    ai_model_name = "researchlens-deterministic-nlp-v1"
    ai_fallback = False

    settings = get_settings()
    if settings.RESEARCHLENS_AI_ENABLED and bounded_gaps:
        try:
            gap_summaries = []
            for g in bounded_gaps[:4]:
                gap_summaries.append(f"Title: {g.title}\nHypothesis: {g.concise_hypothesis}")
            user_msg = (
                f"Topic: {request.topic or 'General Catalog'}\n"
                f"Corpus Examined: {corpus_size} papers\n\n"
                f"Candidate Research Gaps:\n" + "\n\n".join(gap_summaries)
                + "\n\nProvide an articulate executive synthesis (3-4 sentences) explaining the converging research gap "
                + "directions and technical bottlenecks. Emphasize that candidate gaps reflect catalog boundaries."
            )
            messages = [
                {"role": "system", "content": RESEARCH_GAP_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ]
            coordinator = get_ai_coordinator()
            coro = coordinator.generate(
                messages=messages,
                max_tokens=300,
                temperature=0.2,
                has_research_content=True,
            )
            ai_resp = _run_async_safe(coro)
            if ai_resp and ai_resp.content and not ai_resp.error:
                gap_evidence = [g.concise_hypothesis for g in bounded_gaps]
                safe_fallback_synth = corpus_summary.get(
                    "ai_gap_synthesis",
                    "Catalog analysis reveals emergent research opportunities across boundaries."
                )
                guarded_gap, was_modified = enforce_ai_output_security_guard(
                    ai_resp.content,
                    evidence=gap_evidence,
                    fallback_text=safe_fallback_synth,
                    workflow_name="evolution"
                )
                if was_modified:
                    logger.warning("Evolution gap synthesis security guard rejected unsafe AI output; using safe baseline.")
                    ai_provider_name = "deterministic"
                    ai_fallback = True
                    corpus_summary["ai_gap_synthesis"] = guarded_gap
                else:
                    corpus_summary["ai_gap_synthesis"] = guarded_gap
                    ai_provider_name = ai_resp.provider
                    ai_model_name = ai_resp.model
                    ai_fallback = ai_resp.fallback_occurred
            else:
                ai_provider_name = "deterministic"
                ai_fallback = True
        except Exception as exc:
            logger.warning(f"AI gap exploration enhancement failed with {exc}; using deterministic baseline.")
            ai_provider_name = "deterministic"
            ai_fallback = True

    return GapExplorationResponse(
        topic=request.topic,
        total_papers_examined=corpus_size,
        total_gaps_found=len(bounded_gaps),
        status=EvolutionStatus.COMPLETE if len(bounded_gaps) >= 2 else EvolutionStatus.PARTIAL_COVERAGE,
        candidate_gaps=bounded_gaps,
        corpus_summary=corpus_summary,
        truthfulness_disclosure=(
            "DISCLOSURE: Gaps identified are candidate hypotheses grounded strictly in ResearchLens's local catalog. "
            "An absence of papers or methods in this catalog does NOT imply novelty or global research absence. "
            "Human review and comprehensive external literature search are required before pursuing any hypothesis."
        ),
        ai_provider=ai_provider_name,
        ai_model=ai_model_name,
        ai_fallback_occurred=ai_fallback,
    )
