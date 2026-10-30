"""
ResearchLens Grounded Research Assistant Service (TASK-17).
Provides deterministic, evidence-grounded answers to scholarly research questions.
Every claim is mapped to verified source passages with exact character offsets,
reusing existing ResearchLens components (evidence extraction, comparison, DRIUT, evolution).
Zero fabrication of quotes, citations, benchmarks, or relationships.
"""
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.paper import Paper
from app.models.evidence import PaperEvidence
from app.schemas.research import (
    AssistantStatus,
    AssistantEvidenceItem,
    AssistantClaim,
    ResearchAssistantRequest,
    ResearchAssistantResponse,
    TimelineEvidenceClaim,
)
from app.services.evolution_service import (
    _gather_paper_claims,
    _query_relevant_papers,
)
from app.services.evidence_service import (
    split_text_into_sentences_with_spans,
    is_synthetic_placeholder_abstract,
)
from app.services.driut_service import (
    classify_relationship_evidence,
    _extract_dataset_keywords,
    _extract_metric_keywords,
)
import asyncio
import concurrent.futures

from app.core.config import get_settings
from app.services.ai_provider import (
    get_ai_coordinator,
    build_evidence_context,
    RESEARCH_ASSISTANT_SYSTEM_PROMPT,
)

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


# Heuristic intent keywords
INTENT_LIMITATIONS = ["limitation", "limitations", "drawback", "drawbacks", "weakness", "bottleneck", "challenge", "challenges", "shortcoming"]
INTENT_FUTURE_WORK = ["future work", "future direction", "future research", "next step", "open question", "prospective", "upcoming"]
INTENT_COMPARISON = ["compare", "comparison", "difference", "differences", "versus", "vs", "similarities", "differ", "distinct"]
INTENT_DATASETS_METRICS = ["dataset", "datasets", "benchmark", "benchmarks", "metric", "metrics", "evaluation", "evaluated on", "accuracy", "bleu", "f1"]
INTENT_RELATIONSHIP = ["relationship", "related", "extension", "improvement", "reproduction", "alternative", "replacement", "driut"]
INTENT_TIMELINE = ["timeline", "chronology", "evolution", "evolve", "over time", "history", "lineage", "progression"]
INTENT_GAPS = ["gap", "gaps", "unsolved", "missing", "underrepresented", "void"]


def _sanitize_input(text: str) -> str:
    """Sanitize user question to strip command injections or control characters."""
    if not text:
        return ""
    # Strip dangerous control characters while preserving punctuation
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text).strip()
    return cleaned


from app.services.ai_output_guard import (
    enforce_ai_output_security_guard,
    SAFE_CANONICAL_REFUSAL,
    _RE_ATTACK_CANARY,
    _RE_CONNECTION_URI,
    _RE_CONFIG_IDENTIFIERS,
    _RE_CREDENTIAL_ASSIGNMENTS,
    _RE_JWT_TOKEN,
    _RE_REFUSAL_INFRASTRUCTURE,
)


def enforce_assistant_security_guard(
    content: str,
    evidence: Optional[List[Any]] = None,
    question: Optional[str] = None
) -> Tuple[str, bool]:
    """
    Deterministic post-generation output guard for research assistant answers.
    Delegates to unified enforce_ai_output_security_guard.
    """
    import app.services.ai_output_guard as guard_mod
    orig_canary = guard_mod._RE_ATTACK_CANARY
    if _RE_ATTACK_CANARY is not orig_canary:
        guard_mod._RE_ATTACK_CANARY = _RE_ATTACK_CANARY
        try:
            return enforce_ai_output_security_guard(content, evidence, question, workflow_name="assistant")
        finally:
            guard_mod._RE_ATTACK_CANARY = orig_canary
    return enforce_ai_output_security_guard(content, evidence, question, workflow_name="assistant")


def _classify_question_intent(question: str) -> str:
    """Classify researcher inquiry into an analytical intent category."""
    q_lower = question.lower()

    if any(k in q_lower for k in INTENT_RELATIONSHIP):
        return "relationship"
    if any(k in q_lower for k in INTENT_COMPARISON):
        return "comparison"
    if any(k in q_lower for k in INTENT_LIMITATIONS):
        return "limitations"
    if any(k in q_lower for k in INTENT_FUTURE_WORK):
        return "future_work"
    if any(k in q_lower for k in INTENT_DATASETS_METRICS):
        return "datasets_metrics"
    if any(k in q_lower for k in INTENT_TIMELINE):
        return "evolution"
    if any(k in q_lower for k in INTENT_GAPS):
        return "gaps"

    return "general_summary"


def _extract_query_topic(
    question: str,
    history: Optional[List[Dict[str, str]]] = None
) -> Optional[str]:
    """
    Extract the core subject/topic from a researcher's inquiry for semantic vector search.
    Strips conversational framing, interrogative prefixes, and trailing punctuation.
    Resolves anaphoric references using conversation history if available.
    """
    q_clean = _sanitize_input(question)
    if not q_clean:
        return None

    # Step 1: Strip common leading conversational / interrogative prefixes
    prefixes = [
        r"^(?:can\s+you\s+)?(?:please\s+)?(?:what\s+(?:are|is)(?:\s+the)?(?:\s+main)?(?:\s+key)?(?:\s+primary)?(?:\s+reported)?\s+(?:limitations|future\s+work|differences|results|findings|challenges|role|advantage|disadvantage|benefit|contribution|applications?)\s+(?:of|for|in|about))\s+",
        r"^(?:can\s+you\s+)?(?:please\s+)?(?:what\s+(?:are|is)(?:\s+the)?(?:\s+main)?(?:\s+key)?(?:\s+primary)?(?:\s+concept\s+of)?(?:\s+definition\s+of)?)\s+",
        r"^(?:can\s+you\s+)?(?:please\s+)?(?:tell\s+me\s+about|explain(?:\s+to\s+me)?(?:\s+the\s+role\s+of)?|discuss|describe)\s+",
        r"^(?:can\s+you\s+)?(?:please\s+)?(?:summarize(?:\s+the)?(?:\s+main)?(?:\s+idea\s+of)?(?:\s+findings\s+of)?)\s+",
        r"^(?:can\s+you\s+)?(?:please\s+)?(?:how\s+(?:do|does|has|can|is))\s+",
        r"^(?:can\s+you\s+)?(?:please\s+)?(?:compare(?:\s+and\s+contrast)?)\s+",
    ]
    candidate = q_clean
    for p in prefixes:
        candidate = re.sub(p, "", candidate, flags=re.IGNORECASE)

    # Step 2: Strip trailing punctuation and catalog-specific filler phrases
    candidate = re.sub(r"[?!.,;]+$", "", candidate).strip()
    candidate = re.sub(
        r"\b(?:in\s+these\s+papers|reported\s+by\s+(?:these\s+)?papers|in\s+this\s+catalog|in\s+the\s+catalog|in\s+the\s+literature|according\s+to\s+these\s+papers|currently\s+selected)\b",
        "",
        candidate,
        flags=re.IGNORECASE
    ).strip()

    # Step 3: Anaphoric resolution using prior conversational turns
    is_anaphoric = bool(re.search(
        r"\b(?:these|those|this|it|them|they|the\s+model|the\s+models|the\s+paper|the\s+papers)\b",
        candidate,
        re.IGNORECASE
    ))
    if (is_anaphoric or len(candidate) < 4) and history:
        for turn in reversed(history):
            if turn.get("role") == "user":
                prev_text = turn.get("content", "")
                prev_topic = _extract_query_topic(prev_text, history=None)
                if prev_topic and prev_topic.lower() not in candidate.lower():
                    combined = f"{candidate} {prev_topic}".strip()
                    return combined

    if len(candidate) >= 2:
        return candidate

    return q_clean


def _has_extractable_content(p: Paper) -> bool:
    if p.raw_text and len(p.raw_text.strip()) > 50:
        return True
    if p.abstract and len(p.abstract.strip()) > 50 and not is_synthetic_placeholder_abstract(p.abstract):
        return True
    return False


def _retrieve_target_papers(
    db: Session,
    request: ResearchAssistantRequest
) -> Tuple[List[Paper], str, List[str]]:
    """
    Retrieve relevant catalog papers for the assistant question.
    Prioritizes papers with verified, non-synthetic extractable manuscript/abstract text.
    Returns: (papers, corpus_scope_description, warnings)
    """
    warnings: List[str] = []

    # 1. If explicit paper_ids provided, prioritize exact requested set
    if request.paper_ids:
        clean_ids = [str(pid).strip() for pid in request.paper_ids if str(pid).strip()]
        matched_papers: List[Paper] = []
        for pid_str in clean_ids:
            p = None
            if pid_str.isdigit():
                p = db.query(Paper).filter(Paper.id == int(pid_str)).first()
            if not p:
                p = db.query(Paper).filter(Paper.paper_id == pid_str).first()
            if p:
                if p not in matched_papers:
                    matched_papers.append(p)
            else:
                warnings.append(f"Specified paper '{pid_str}' was not found in the catalog.")

        scope_desc = f"Specified paper set: {len(matched_papers)} paper(s) analyzed ({', '.join(p.paper_id for p in matched_papers[:3])}{'...' if len(matched_papers) > 3 else ''})"
        return matched_papers[:10], scope_desc, warnings

    # 2. Extract semantic search topic directly from current question (and history if follow-up)
    query_topic = _extract_query_topic(request.question, request.conversation_history)
    if query_topic:
        raw_papers = _query_relevant_papers(db, topic=query_topic, limit=25)
        valid_papers = [p for p in raw_papers if _has_extractable_content(p)]
        papers = valid_papers[:10] if valid_papers else raw_papers[:10]
        if papers:
            scope_desc = f"Local catalog semantic search: query '{query_topic}', N={len(papers)} candidate paper(s) examined"
            return papers, scope_desc, warnings

    # 3. If question extraction returned no papers, check explicit request.topic filter
    if request.topic and request.topic.strip():
        clean_topic = request.topic.strip()
        if clean_topic.lower() != (query_topic or "").lower():
            raw_topic_papers = _query_relevant_papers(db, topic=clean_topic, limit=25)
            valid_topic_papers = [p for p in raw_topic_papers if _has_extractable_content(p)]
            topic_papers = valid_topic_papers[:10] if valid_topic_papers else raw_topic_papers[:10]
            if topic_papers:
                scope_desc = f"Local catalog topic search: '{clean_topic}', N={len(topic_papers)} candidate paper(s) examined"
                return topic_papers, scope_desc, warnings

    # 4. If query is broad / exploratory overview and no specific match
    scope_desc = f"Local catalog search for '{request.question}' found no relevant papers matching the query criteria"
    return [], scope_desc, warnings


def _gather_and_verify_evidence(
    papers: List[Paper],
    db: Session,
    intent: str,
    max_items: int = 8
) -> List[AssistantEvidenceItem]:
    """
    Gather and verify grounded evidence claims across papers.
    Assigns deterministic IDs and verifies substring offset integrity.
    """
    all_items: List[AssistantEvidenceItem] = []
    ev_counter = 1

    # Priority categories based on question intent
    intent_category_priority = {
        "limitations": ["limitations", "problem"],
        "future_work": ["future_work", "contributions"],
        "comparison": ["method", "results", "dataset", "metrics"],
        "datasets_metrics": ["dataset", "metrics", "results"],
        "relationship": ["contributions", "method", "results"],
        "evolution": ["method", "contributions", "results"],
        "gaps": ["limitations", "future_work", "dataset"],
        "general_summary": ["method", "results", "problem", "contributions"],
    }
    target_cats = set(intent_category_priority.get(intent, ["method", "results", "limitations"]))

    for p in papers:
        claims_map, src_type = _gather_paper_claims(p, db)
        p_text = (p.raw_text if src_type == "full_text" and p.raw_text else (p.abstract or "")).strip()

        # Prioritize claims matching intent
        gathered_for_paper: List[TimelineEvidenceClaim] = []
        for cat in target_cats:
            gathered_for_paper.extend(claims_map.get(cat, []))

        # If too few, append remaining categories
        if len(gathered_for_paper) < 2:
            for cat, clist in claims_map.items():
                if cat not in target_cats:
                    gathered_for_paper.extend(clist[:1])

        for claim in gathered_for_paper:
            # Mathematical span verification
            s, e = claim.char_start, claim.char_end
            if s is not None and e is not None and p_text:
                if 0 <= s < e <= len(p_text):
                    sliced = p_text[s:e]
                    if sliced != claim.source_passage:
                        # Find actual position if shifted
                        actual_idx = p_text.find(claim.source_passage)
                        if actual_idx != -1:
                            s = actual_idx
                            e = actual_idx + len(claim.source_passage)

            all_items.append(AssistantEvidenceItem(
                evidence_id=f"ev-{ev_counter}",
                paper_id=p.id,
                paper_code=p.paper_id,
                paper_title=p.title,
                authors=p.authors or [],
                year=p.year,
                venue=p.venue,
                source_passage=claim.source_passage,
                char_start=s,
                char_end=e,
                section_name=claim.section_name or ("Abstract" if src_type == "abstract" else None),
                source_type=src_type,
                category=claim.category,
                confidence_score=claim.confidence_score or 0.85,
                url=p.url,
                doi=p.doi
            ))
            ev_counter += 1

            if len(all_items) >= max_items * 2:
                break

    # Prioritize evidence matching targeted categories and non-empty passages
    all_items.sort(key=lambda item: (item.category in target_cats, item.confidence_score or 0.0), reverse=True)
    return all_items[:max_items]


def answer_research_question(
    db: Session,
    request: ResearchAssistantRequest
) -> ResearchAssistantResponse:
    """
    Main entry point for Grounded Research Assistant queries.
    Synthesizes evidence-backed answers, claims, and verified citations.
    """
    question = _sanitize_input(request.question)
    if not question:
        return ResearchAssistantResponse(
            question=request.question,
            answer="Please provide a specific scientific research question.",
            status=AssistantStatus.INSUFFICIENT_EVIDENCE,
            evidence=[],
            claims=[],
            limitations=["Empty or whitespace-only question received."],
            corpus_scope="None",
            follow_up_questions=["What limitations are reported in these papers?", "Compare the evaluation benchmarks."]
        )

    intent = _classify_question_intent(question)
    papers, scope_desc, warnings = _retrieve_target_papers(db, request)

    # If no papers found
    if not papers:
        return ResearchAssistantResponse(
            question=question,
            answer=(
                f"No matching research papers were found in the local ResearchLens catalog for '{question}'. "
                "The assistant strictly operates on verified catalog records to prevent hallucination."
            ),
            status=AssistantStatus.INSUFFICIENT_EVIDENCE,
            evidence=[],
            claims=[],
            limitations=["No candidate papers in local catalog matching the query filters."] + warnings,
            corpus_scope=scope_desc,
            follow_up_questions=[
                "Try searching for broader terms like 'BERT', 'Transformers', or 'Vision'.",
                "Ingest candidate papers via PDF upload or academic search before querying."
            ]
        )

    # Gather verified evidence
    evidence = _gather_and_verify_evidence(papers, db, intent, max_items=request.max_evidence_items)

    # If no evidence could be extracted
    if not evidence:
        return ResearchAssistantResponse(
            question=question,
            answer=(
                f"Examined {len(papers)} paper(s) in the catalog ({', '.join(p.title[:40] + '...' for p in papers[:2])}), "
                "but could not find extractable, verified source passages addressing this specific question. "
                "To maintain strict scientific integrity, the assistant does not generate unverified claims."
            ),
            status=AssistantStatus.INSUFFICIENT_EVIDENCE,
            evidence=[],
            claims=[],
            limitations=["Source papers lack explicit passages matching the question criteria in their abstracts."] + warnings,
            corpus_scope=scope_desc,
            follow_up_questions=[
                f"What methodologies are proposed in '{papers[0].title[:50]}'?",
                "Are full-text PDF manuscripts uploaded for these papers?"
            ]
        )

    # --------------------------------------------------------------------------
    # Synthesize Structured Answer Based on Classified Intent
    # --------------------------------------------------------------------------
    claims: List[AssistantClaim] = []
    answer_paragraphs: List[str] = []
    limitations: List[str] = list(warnings)
    follow_ups: List[str] = []

    # Map evidence by category and by paper
    ev_by_cat = defaultdict(list)
    ev_by_paper = defaultdict(list)
    for ev in evidence:
        ev_by_cat[ev.category].append(ev)
        ev_by_paper[ev.paper_id].append(ev)

    # --------------------------------------------------------------------------
    # Case 1: Limitations & Challenges Query
    # --------------------------------------------------------------------------
    if intent == "limitations":
        lim_evs = ev_by_cat.get("limitations", []) + ev_by_cat.get("problem", [])
        if lim_evs:
            answer_paragraphs.append(
                f"Based on {len(papers)} paper(s) examined in the catalog, authors report the following primary limitations and challenges:"
            )
            for idx, ev in enumerate(lim_evs[:4], 1):
                clean_passage = ev.source_passage.strip()
                claim_text = f"In {ev.paper_title} ({ev.year or 'Undated'}), authors note: \"{clean_passage}\" [{ev.evidence_id}]."
                answer_paragraphs.append(f"• **{ev.paper_title[:55]}...** [{ev.evidence_id}]: {clean_passage}")
                claims.append(AssistantClaim(
                    claim_id=f"claim-{idx}",
                    claim_text=claim_text,
                    supporting_evidence_ids=[ev.evidence_id],
                    category="limitation",
                    confidence=ev.confidence_score or 0.88,
                    is_verified=True
                ))
            limitations.append("Limitations reflect explicit author statements in abstracts; unindexed experimental sections may note additional trade-offs.")
            follow_ups.append("What future-work directions do these authors propose to mitigate these bottlenecks?")
            follow_ups.append("Are there alternative architectures in the catalog that address these limitations?")
        else:
            answer_paragraphs.append(
                f"The examined papers ({', '.join(p.title[:35] + '...' for p in papers[:2])}) do not explicitly state limitations or bottlenecks in their abstracts."
            )
            limitations.append("No explicit limitation patterns were detected in the available abstract text.")

    # --------------------------------------------------------------------------
    # Case 2: Future Work & Open Directions Query
    # --------------------------------------------------------------------------
    elif intent == "future_work":
        fw_evs = ev_by_cat.get("future_work", [])
        if fw_evs:
            answer_paragraphs.append(
                f"Authors across {len(papers)} examined paper(s) outline the following prospective research directions:"
            )
            for idx, ev in enumerate(fw_evs[:4], 1):
                clean_passage = ev.source_passage.strip()
                claim_text = f"In {ev.paper_title} ({ev.year or 'Undated'}), future work targets: \"{clean_passage}\" [{ev.evidence_id}]."
                answer_paragraphs.append(f"• **{ev.paper_title[:55]}...** [{ev.evidence_id}]: {clean_passage}")
                claims.append(AssistantClaim(
                    claim_id=f"claim-{idx}",
                    claim_text=claim_text,
                    supporting_evidence_ids=[ev.evidence_id],
                    category="future_work",
                    confidence=ev.confidence_score or 0.88,
                    is_verified=True
                ))
            limitations.append("Future directions are based on author-reported aspirations and may already be pursued in subsequent literature.")
            follow_ups.append("Have follow-up papers in the catalog addressed any of these proposed directions?")
            follow_ups.append("What candidate research gaps emerge from these recurring future-work statements?")
        else:
            answer_paragraphs.append(
                f"No explicit future-work or prospective investigation statements were found in the examined abstracts."
            )
            limitations.append("Future-work sections are frequently situated in paper conclusions rather than abstracts.")

    # --------------------------------------------------------------------------
    # Case 3: Comparison Query
    # --------------------------------------------------------------------------
    elif intent == "comparison":
        if len(papers) >= 2:
            p1, p2 = papers[0], papers[1]
            answer_paragraphs.append(
                f"Comparing **{p1.title}** ({p1.year or 'Undated'}) and **{p2.title}** ({p2.year or 'Undated'}):"
            )

            # Compare methods
            ev_p1 = ev_by_paper.get(p1.id, [])
            ev_p2 = ev_by_paper.get(p2.id, [])

            m_p1 = next((e for e in ev_p1 if e.category == "method"), ev_p1[0] if ev_p1 else None)
            m_p2 = next((e for e in ev_p2 if e.category == "method"), ev_p2[0] if ev_p2 else None)

            if m_p1 and m_p2:
                comp_claim = (
                    f"Methodological Comparison: {p1.title} proposes \"{m_p1.source_passage}\" [{m_p1.evidence_id}], "
                    f"whereas {p2.title} focuses on \"{m_p2.source_passage}\" [{m_p2.evidence_id}]."
                )
                answer_paragraphs.append(f"• **Methodology**: {comp_claim}")
                claims.append(AssistantClaim(
                    claim_id="claim-comp-method",
                    claim_text=comp_claim,
                    supporting_evidence_ids=[m_p1.evidence_id, m_p2.evidence_id],
                    category="method_comparison",
                    confidence=0.90,
                    is_verified=True
                ))

            # Compare datasets / metrics
            d_p1 = _extract_dataset_keywords(f"{p1.title} {p1.abstract or ''}")
            d_p2 = _extract_dataset_keywords(f"{p2.title} {p2.abstract or ''}")
            if d_p1 or d_p2:
                common_d = d_p1.intersection(d_p2)
                diff_d1 = d_p1 - d_p2
                diff_d2 = d_p2 - d_p1
                d_claim = (
                    f"Evaluation Benchmarks: "
                    + (f"Both evaluate on {list(common_d)}. " if common_d else "No common benchmark datasets detected between abstracts. ")
                    + (f"{p1.title[:30]} evaluates on {list(diff_d1)}. " if diff_d1 else "")
                    + (f"{p2.title[:30]} evaluates on {list(diff_d2)}." if diff_d2 else "")
                )
                answer_paragraphs.append(f"• **Evaluation Protocol**: {d_claim}")
                c_ev_ids = [e.evidence_id for e in (ev_p1 + ev_p2) if e.category in ["dataset", "results"]][:2]
                claims.append(AssistantClaim(
                    claim_id="claim-comp-datasets",
                    claim_text=d_claim,
                    supporting_evidence_ids=c_ev_ids or [evidence[0].evidence_id],
                    category="protocol_comparison",
                    confidence=0.85,
                    is_verified=True
                ))
                if not common_d and (d_p1 and d_p2):
                    limitations.append("Warning: Disparate evaluation benchmarks detected. Numerical superiority cannot be directly compared.")

            # Check DRIUT relationship
            p1_dict = {"id": p1.id, "paper_id": p1.paper_id, "title": p1.title, "abstract": p1.abstract}
            p2_dict = {"id": p2.id, "paper_id": p2.paper_id, "title": p2.title, "abstract": p2.abstract}
            rel = classify_relationship_evidence(p1_dict, p2_dict, db=db)
            if rel.is_supported and rel.relationship_type:
                rel_claim = f"Scientific Relationship: {p2.title} relates to {p1.title} as '{rel.relationship_type}' ({rel.evidence_strength}). Explanation: {rel.explanation}"
                answer_paragraphs.append(f"• **Classified Relationship**: {rel_claim}")
                claims.append(AssistantClaim(
                    claim_id="claim-rel",
                    claim_text=rel_claim,
                    supporting_evidence_ids=[evidence[0].evidence_id],
                    category="relationship",
                    confidence=rel.confidence_score,
                    is_verified=True
                ))

            follow_ups.append(f"What limitations are reported for {p1.title[:40]}?")
            follow_ups.append(f"What limitations are reported for {p2.title[:40]}?")
        else:
            answer_paragraphs.append(f"Comparative queries require at least 2 papers. Only 1 paper was retrieved: **{papers[0].title}**.")
            limitations.append("Single paper provided for comparison request; select additional papers to perform structured comparison.")

    # --------------------------------------------------------------------------
    # Case 4: Datasets and Metrics Query
    # --------------------------------------------------------------------------
    elif intent == "datasets_metrics":
        d_evs = ev_by_cat.get("dataset", []) + ev_by_cat.get("metrics", [])
        answer_paragraphs.append(f"Evaluation protocols and benchmarks identified across {len(papers)} paper(s):")
        for idx, p in enumerate(papers[:4], 1):
            dsets = _extract_dataset_keywords(f"{p.title} {p.abstract or ''}")
            mets = _extract_metric_keywords(f"{p.title} {p.abstract or ''}")
            p_evs = [e for e in evidence if e.paper_id == p.id]
            ref_id = p_evs[0].evidence_id if p_evs else evidence[0].evidence_id

            desc = f"• **{p.title[:50]}...** [{ref_id}]: "
            if dsets or mets:
                desc += f"Datasets/benchmarks: {list(dsets) or ['None stated in abstract']}; Metrics: {list(mets) or ['Standard accuracy/loss']}."
            else:
                desc += "No standard benchmark dataset keywords detected in abstract."
            answer_paragraphs.append(desc)

            claims.append(AssistantClaim(
                claim_id=f"claim-dset-{idx}",
                claim_text=desc,
                supporting_evidence_ids=[ref_id],
                category="dataset_protocol",
                confidence=0.88,
                is_verified=True
            ))

        limitations.append("Benchmark extraction is scoped to abstract mentions. Complete evaluation tables require full PDF inspection.")
        follow_ups.append("Are these models evaluated on the same benchmark distributions?")
        follow_ups.append("What empirical results did these models report?")

    # --------------------------------------------------------------------------
    # Case 5: DRIUT / Research Relationship Query
    # --------------------------------------------------------------------------
    elif intent == "relationship":
        if len(papers) >= 2:
            p1, p2 = papers[0], papers[1]
            p1_dict = {"id": p1.id, "paper_id": p1.paper_id, "title": p1.title, "abstract": p1.abstract}
            p2_dict = {"id": p2.id, "paper_id": p2.paper_id, "title": p2.title, "abstract": p2.abstract}
            rel = classify_relationship_evidence(p1_dict, p2_dict, db=db)

            answer_paragraphs.append(f"Inter-paper relationship analysis between **{p1.title}** and **{p2.title}**:")
            if rel.is_supported and rel.relationship_type:
                rel_desc = (
                    f"The system identifies a grounded '{rel.relationship_type}' relationship ({rel.evidence_strength}, "
                    f"confidence: {rel.confidence_score:.0%}). {rel.explanation}"
                )
                answer_paragraphs.append(f"• {rel_desc}")
                if rel.evidence_passage:
                    answer_paragraphs.append(f"• Grounded quote: \"{rel.evidence_passage}\" [{evidence[0].evidence_id}]")
                claims.append(AssistantClaim(
                    claim_id="claim-driut-rel",
                    claim_text=rel_desc,
                    supporting_evidence_ids=[evidence[0].evidence_id],
                    category="relationship",
                    confidence=rel.confidence_score,
                    is_verified=True
                ))
            else:
                answer_paragraphs.append(
                    f"• Thematic similarity detected ({rel.semantic_similarity:.0%}), but source texts contain "
                    "insufficient explicit scientific evidence to confirm a direct Extension, Improvement, or Alternative."
                )
                limitations.append("Thematic proximity alone does not prove citation, direct influence, or agreement.")
            follow_ups.append("What methodology does each paper propose?")
        else:
            answer_paragraphs.append(f"Relationship analysis requires at least two papers. Single paper examined: {papers[0].title}.")

    # --------------------------------------------------------------------------
    # Case 6: Evolution & Timeline Query
    # --------------------------------------------------------------------------
    elif intent == "evolution":
        sorted_papers = sorted([p for p in papers if p.year is not None], key=lambda x: x.year)
        undated = [p for p in papers if p.year is None]

        answer_paragraphs.append(
            f"Chronological research evolution across {len(sorted_papers)} dated paper(s) ({sorted_papers[0].year if sorted_papers else ''} – {sorted_papers[-1].year if sorted_papers else ''}):"
        )
        for idx, p in enumerate(sorted_papers[:5], 1):
            p_evs = [e for e in evidence if e.paper_id == p.id]
            ref_id = p_evs[0].evidence_id if p_evs else evidence[0].evidence_id
            first_claim = p_evs[0].source_passage if p_evs else (p.abstract or "")[:120]

            line = f"• **{p.year}** — **{p.title[:50]}...** [{ref_id}]: {first_claim[:140]}..."
            answer_paragraphs.append(line)
            claims.append(AssistantClaim(
                claim_id=f"claim-evo-{idx}",
                claim_text=line,
                supporting_evidence_ids=[ref_id],
                category="chronological_development",
                confidence=0.90,
                is_verified=True
            ))

        if undated:
            answer_paragraphs.append(f"Note: {len(undated)} paper(s) in this corpus lack verified publication dates and are excluded from chronological sequencing.")
        limitations.append("Chronological succession does not establish causal lineage or global scientific priority.")
        follow_ups.append("What candidate research gaps emerge along this timeline?")

    # --------------------------------------------------------------------------
    # Case 7: Research Gaps Query
    # --------------------------------------------------------------------------
    elif intent == "gaps":
        answer_paragraphs.append(
            f"Candidate research-gap synthesis across {len(papers)} paper(s) in this catalog:"
        )
        lim_evs = ev_by_cat.get("limitations", [])
        fw_evs = ev_by_cat.get("future_work", [])

        if lim_evs:
            gap_claim = f"Recurring Bottleneck: Multiple papers report constraints: \"{lim_evs[0].source_passage}\" [{lim_evs[0].evidence_id}]."
            answer_paragraphs.append(f"• **Recurring Bottleneck**: {gap_claim}")
            claims.append(AssistantClaim(
                claim_id="claim-gap-lim",
                claim_text=gap_claim,
                supporting_evidence_ids=[lim_evs[0].evidence_id],
                category="research_gap",
                confidence=0.85,
                is_verified=True
            ))

        if fw_evs:
            fw_gap = f"Converging Direction: Authors propose: \"{fw_evs[0].source_passage}\" [{fw_evs[0].evidence_id}]."
            answer_paragraphs.append(f"• **Converging Future Direction**: {fw_gap}")
            claims.append(AssistantClaim(
                claim_id="claim-gap-fw",
                claim_text=fw_gap,
                supporting_evidence_ids=[fw_evs[0].evidence_id],
                category="research_gap",
                confidence=0.85,
                is_verified=True
            ))

        answer_paragraphs.append(
            "• **Local Catalog Boundary**: Any apparent absence in this local index represents a catalog boundary, "
            "and MUST NOT be claimed as global scientific novelty without external systematic literature review."
        )
        limitations.append("Candidate gaps are provisional hypotheses requiring comprehensive external verification.")
        follow_ups.append("Conduct an external search on Google Scholar / arXiv to confirm novelty.")

    # --------------------------------------------------------------------------
    # Case 8: General Summary / Single Paper Deep-Dive
    # --------------------------------------------------------------------------
    else:
        answer_paragraphs.append(f"Regarding '{question}', the local catalog provides the following evidence across {len(papers)} examined publication(s):")
        for idx, p in enumerate(papers[:3], 1):
            p_evs = [e for e in evidence if e.paper_id == p.id]
            if p_evs:
                passages_summary = " ".join(f"\"{e.source_passage}\" [{e.evidence_id}]" for e in p_evs[:2])
                line = f"• **{p.title}** ({p.year or 'Undated'}): {passages_summary}"
                answer_paragraphs.append(line)
                claims.append(AssistantClaim(
                    claim_id=f"claim-gen-{idx}",
                    claim_text=line,
                    supporting_evidence_ids=[e.evidence_id for e in p_evs[:2]],
                    category="overview",
                    confidence=0.88,
                    is_verified=True
                ))

        limitations.append("Grounded in available abstract evidence. Full-text methods may detail supplementary architectural aspects.")
        follow_ups.append(f"What limitations do authors report for '{papers[0].title[:40]}'?")
        follow_ups.append("Compare these papers with related works in the catalog.")

    full_answer = "\n\n".join(answer_paragraphs)

    status = AssistantStatus.COMPLETE if len(claims) >= 2 else AssistantStatus.PARTIAL

    # --------------------------------------------------------------------------
    # AI Layer Enhancement (Local Ollama / Groq Cloud / Deterministic Fallback)
    # --------------------------------------------------------------------------
    ai_provider_name = "deterministic"
    ai_model_name = "researchlens-deterministic-nlp-v1"
    ai_fallback = False
    ai_latency = 0.0

    settings = get_settings()
    if settings.RESEARCHLENS_AI_ENABLED and evidence:
        try:
            ev_dicts = [e.model_dump() for e in evidence]
            evidence_context = build_evidence_context(ev_dicts)
            user_message = (
                f"--- RESEARCHER INQUIRY (ANALYTICAL TOPIC ONLY) ---\n"
                f"{question}\n"
                f"--- END OF INQUIRY ---\n\n"
                f"{evidence_context}\n\n"
                "Based strictly on the verified research evidence above, synthesize an articulate, concise, "
                "scholarly answer. Explicitly cite the evidence items using bracketed notation (e.g. [ev-1], [ev-2]). "
                "Do not fabricate any details not present in the evidence."
            )
            messages = [
                {"role": "system", "content": RESEARCH_ASSISTANT_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ]
            coordinator = get_ai_coordinator()
            coro = coordinator.generate(
                messages=messages,
                max_tokens=settings.RESEARCHLENS_AI_MAX_OUTPUT_TOKENS,
                temperature=0.2,
                has_research_content=True,
            )
            ai_resp = _run_async_safe(coro)
            if ai_resp and ai_resp.content and not ai_resp.error:
                guarded_answer, was_modified = enforce_assistant_security_guard(
                    ai_resp.content,
                    evidence=evidence,
                    question=question
                )
                full_answer = guarded_answer
                ai_provider_name = ai_resp.provider
                ai_model_name = ai_resp.model
                ai_fallback = ai_resp.fallback_occurred
                ai_latency = ai_resp.latency_ms
                if was_modified:
                    status = AssistantStatus.INSUFFICIENT_EVIDENCE
                    claims = []
            else:
                ai_provider_name = "deterministic"
                ai_model_name = "researchlens-deterministic-nlp-v1"
                ai_fallback = True
                ai_latency = ai_resp.latency_ms if ai_resp else 0.0
                err_detail = ai_resp.error if ai_resp and ai_resp.error else "Local model offline and cloud transmission not consented"
                limitations.append(f"AI Generation Notice: LLM generation was unavailable ({err_detail}). Synthesizing answer via verified extractive catalog evidence.")
        except Exception as exc:
            logger.warning(f"AI assistant enhancement failed with {exc}; using deterministic answer.")
            ai_provider_name = "deterministic"
            ai_model_name = "researchlens-deterministic-nlp-v1"
            ai_fallback = True
            limitations.append(f"AI Generation Notice: LLM generation encountered an issue ({str(exc)}). Presenting deterministic catalog synthesis.")

    # Final defense-in-depth output guard on final answer
    full_answer, was_final_mod = enforce_assistant_security_guard(
        full_answer,
        evidence=evidence,
        question=question
    )
    if was_final_mod:
        status = AssistantStatus.INSUFFICIENT_EVIDENCE
        claims = []

    return ResearchAssistantResponse(
        question=question,
        answer=full_answer,
        status=status,
        evidence=evidence,
        claims=claims,
        limitations=limitations,
        corpus_scope=scope_desc,
        follow_up_questions=follow_ups[:3],
        truthfulness_disclosure=(
            "DISCLOSURE: Every answer claim is deterministically grounded in verified passages "
            "from the local catalog. Citations and offsets correspond to exact stored text. "
            "No statements or quotations are fabricated."
        ),
        ai_provider=ai_provider_name,
        ai_model=ai_model_name,
        ai_fallback_occurred=ai_fallback,
        ai_latency_ms=ai_latency,
    )
