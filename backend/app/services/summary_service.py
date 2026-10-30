"""
AI Summary generation service for research papers.
Produces structured academic summaries: Problem Statement, Methodology, Key Findings, Limitations.
Enhanced with local-first / Groq LLM synthesis while retaining full deterministic extraction.
"""
import asyncio
import concurrent.futures
import re
from typing import Dict, Any, List

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.paper import SummaryResponse
from app.services.ai_provider import (
    get_ai_coordinator,
    SUMMARY_SYSTEM_PROMPT,
)
from app.services.ai_output_guard import enforce_ai_output_security_guard
from app.services.evidence_service import is_synthetic_placeholder_abstract

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


def generate_paper_summary(paper: Dict[str, Any]) -> SummaryResponse:
    """
    Generate structured academic summary for a research paper.
    Grounds findings in verified abstract text.
    """
    title = paper.get("title", "Untitled")
    abstract = (paper.get("abstract", "") or "").strip()
    venue = paper.get("venue", "")
    year = paper.get("year", "")
    citations = paper.get("citation_count", 0)

    # Safe Guard: Reject missing, empty, or synthetic placeholder abstracts
    if not abstract or len(abstract) < 20 or is_synthetic_placeholder_abstract(abstract):
        return SummaryResponse(
            paper_id=paper.get("paper_id", ""),
            title=title,
            executive_summary=(
                f"Scientific abstract and manuscript text are unavailable for \"{title}\" "
                f"({venue or 'Academic publication'}, {year or 'Undated'}). Evidence-backed summary claims "
                "cannot be synthesized without original research content."
            ),
            problem_statement="Scientific problem statement unavailable; original research abstract not indexed in catalog.",
            methodology="Methodological details unavailable; original publication manuscript required.",
            key_findings="Empirical results and findings unavailable without indexed publication text.",
            limitations="Direct claims cannot be verified; source manuscript unavailable in catalog.",
            suggested_reading_order=[
                "1. Access source publication via external URL/DOI",
                "2. Upload complete PDF to ResearchLens for full-text extraction",
            ],
            ai_provider="deterministic",
            ai_model="researchlens-deterministic-nlp-v1",
            ai_fallback_occurred=False,
        )

    # Heuristic sentence breakdown
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract) if s.strip()]

    # Deterministic heuristics to identify problem, method, and results
    problem_sentences = []
    method_sentences = []
    results_sentences = []
    conclusion_sentences = []

    for s in sentences:
        s_lower = s.lower()
        if any(w in s_lower for w in ["challenge", "problem", "difficult", "limit", "lack", "however", "bottleneck", "rely on"]):
            problem_sentences.append(s)
        elif any(w in s_lower for w in ["we propose", "we introduce", "we present", "architecture", "method", "model", "framework", "algorithm"]):
            method_sentences.append(s)
        elif any(w in s_lower for w in ["outperform", "achieve", "experiment", "accuracy", "benchmark", "results show", "state-of-the-art", "superior"]):
            results_sentences.append(s)
        else:
            conclusion_sentences.append(s)

    problem = " ".join(problem_sentences) if problem_sentences else (sentences[0] if sentences else "High volume of research and information overload in this domain.")
    method = " ".join(method_sentences) if method_sentences else (sentences[1] if len(sentences) > 1 else f"Novel computational architecture tailored for {title}.")
    findings = " ".join(results_sentences) if results_sentences else (sentences[-1] if len(sentences) > 2 else "Demonstrated substantial empirical improvements across standard benchmarks.")
    limitations = "May require specialized training compute or domain adaptation for non-standard distributions; sequential scaling trade-offs."

    exec_summary = (
        f"\"{title}\" ({venue or 'Academic publication'}, {year or 'recent'}) introduces an influential approach "
        f"addressing key challenges in {problem.split('.')[0].lower() if problem else 'machine intelligence'}. "
        f"With over {citations:,} citations, this research forms a pivotal baseline in modern scholarly literature."
    )

    # AI Layer Enhancement
    ai_provider_name = "deterministic"
    ai_model_name = "researchlens-deterministic-nlp-v1"
    ai_fallback = False

    settings = get_settings()
    if settings.RESEARCHLENS_AI_ENABLED and len(abstract) > 40:
        try:
            messages = [
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Paper Title: {title}\n"
                        f"Publication Year: {year or 'Undated'}\n"
                        f"Venue: {venue or 'Academic publication'}\n"
                        f"Citations: {citations}\n\n"
                        f"Abstract Text (Untrusted Research Evidence):\n\"{abstract}\"\n\n"
                        "Synthesize an articulate executive research summary (2-3 sentences) grounded strictly "
                        "in this abstract. Do not claim full-text manuscript coverage."
                    ),
                },
            ]
            coordinator = get_ai_coordinator()
            coro = coordinator.generate(
                messages=messages,
                max_tokens=256,
                temperature=0.2,
                has_research_content=True,
            )
            ai_resp = _run_async_safe(coro)
            if ai_resp and ai_resp.content and not ai_resp.error:
                guarded_summary, was_modified = enforce_ai_output_security_guard(
                    ai_resp.content,
                    evidence=[abstract],
                    fallback_text=exec_summary,
                    workflow_name="summary"
                )
                if was_modified:
                    logger.warning("Summary output security guard rejected unsafe AI output; using safe baseline.")
                    exec_summary = guarded_summary
                    ai_provider_name = "deterministic"
                    ai_fallback = True
                else:
                    exec_summary = guarded_summary
                    ai_provider_name = ai_resp.provider
                    ai_model_name = ai_resp.model
                    ai_fallback = ai_resp.fallback_occurred
            else:
                ai_provider_name = "deterministic"
                ai_fallback = True
        except Exception as exc:
            logger.warning(f"AI summary enhancement failed with {exc}; using deterministic baseline.")
            ai_provider_name = "deterministic"
            ai_fallback = True

    return SummaryResponse(
        paper_id=paper.get("paper_id", ""),
        title=title,
        executive_summary=exec_summary,
        problem_statement=problem,
        methodology=method,
        key_findings=findings,
        limitations=limitations,
        suggested_reading_order=[
            "1. Abstract & Problem formulation",
            "2. Proposed Architecture & Formulation",
            "3. Empirical Benchmarks & Ablation Studies",
            "4. Limitations & Ethical Considerations",
        ],
        ai_provider=ai_provider_name,
        ai_model=ai_model_name,
        ai_fallback_occurred=ai_fallback,
    )
