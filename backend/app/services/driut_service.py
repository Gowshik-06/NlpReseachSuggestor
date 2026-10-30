"""
DRIUT — Dynamic Research Impact Update Tracker Service.
Monitors newly indexed research papers and classifies relationships with a researcher's saved papers.
Implements the 6 relationship taxonomy classifications from PPTX:
1. Extension
2. Improvement
3. Challenge
4. Reproduction
5. Alternative
6. Potential Replacement
"""
import re
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Paper, SavedPaper, DRIUTAlert
from app.models.evidence import PaperEvidence
from app.schemas.paper import DRIUTClassificationResult
from app.services.embedding_service import compute_cosine_similarity, generate_embedding
from app.services.text_processor import extract_keywords_from_text, clean_text
from app.services.evidence_service import (
    split_text_into_sentences_with_spans,
    extract_evidence_from_text,
    compute_source_hash,
    ALL_EVIDENCE_CATEGORIES
)

logger = get_logger(__name__)

# Explicit lexical and semantic patterns for 6 DRIUT relationship categories
PATTERNS = {
    "Improvement": [
        r"\b(?:outperforms?|superior\s+performance|superior|higher\s+accuracy|state-of-the-art|sota|more\s+efficient|better\s+results|significant\s+gains?|matches\s+or\s+exceeds?|beats?|substantially\s+improves?|improves?\s+(?:upon|on|over)|improving\s+(?:upon|on|over)|improved\s+(?:upon|on|over)|achieves?\s+new\s+(?:records?|benchmarks?)|reduces?\s+(?:error|latency|cost|overhead|memory\s+overhead)\s*(?:by)?|reducing\s+(?:\w+\s+)?overhead)\b",
        r"\b(?:robustly\s+optimized|consistently\s+beats?|advances\s+beyond|surpasses?|undertrained|faster|lower\s+overhead|efficiency\s+gains?)\b"
    ],
    "Extension": [
        r"\b(?:extends?|extending|builds?\s+upon|builds?\s+on|generalizes?|incorporates?|scaled\s+to|modular\s+adapters?|unified\s+backbone|expanded|adapting|adapted\s+to|version\s+2\.0|multitask|multi-task|cross-modal|applies?\s+to|applied\s+to)\b",
        r"\b(?:derived\s+from|further\s+development|follow-up|prolonged|tailored\s+extension|subsequent\s+extension)\b"
    ],
    "Challenge": [
        r"\b(?:critique|critiques?|fails?\s+to|limitation\s+of|disputes?|drawbacks?|flaw|contrary\s+to|overestimates?|unstable|vulnerab\w+|re-evaluat\w+|questions?\s+the\s+validity)\b",
        r"\b(?:fall\s+short|shortcoming|incorrect\s+assumption|overfitting\s+in|overfitting|bias\s+in|critical\s+weakness|invalidates?)\b"
    ],
    "Reproduction": [
        r"\b(?:replication\s+study|reproduce|reproduces?|reproducibility|replicate|replications?|empirical\s+verification|investigate\s+the\s+claims|audit|validating\s+results)\b",
        r"\b(?:independent\s+verification|benchmarking\s+study|replicating\s+experiments?|re-execut\w+)\b"
    ],
    "Alternative": [
        r"\b(?:dispensing\s+with|instead\s+of|alternative\s+(?:to|approach|paradigm)|without\s+relying\s+on|substitute\s+(?:for)?|different\s+paradigm|parallel\s+approach|contrast\s+with|eliminating\s+recurrence|orthogonal\s+approach|orthogonal)\b",
        r"\b(?:divergent\s+formulation|unconventional\s+alternative|distinct\s+methodology)\b"
    ],
    "Potential Replacement": [
        r"\b(?:supersedes?|replaces?|replacement\s+for|new\s+standard|obviates?|no\s+longer\s+(?:needed|necessary)|drop-in\s+replacement|successor\s+to|renders?\s+obsolete|serves\s+as\s+a\s+suitable\s+replacement)\b"
    ]
}

GENERIC_RESEARCH_TERMS = {
    "deep", "learning", "neural", "network", "networks", "model", "models",
    "system", "systems", "computing", "algorithm", "algorithms", "approach",
    "approaches", "method", "methods", "analysis", "study", "using", "based",
    "high", "energy", "data", "information", "research", "paper", "papers",
    "representation", "representations", "evaluation", "performance",
    "optimization", "overview", "introduction", "efficient", "novel"
}


def _extract_dataset_keywords(text: str) -> set:
    """Extract known benchmark and dataset keywords for comparability analysis."""
    benchmarks = [
        "imagenet", "glue", "squad", "superglue", "wmt", "mnist", "cifar-10", "cifar-100",
        "multinli", "snli", "trec", "mmlu", "ms coco", "coco", "wikitext", "conll", "squad v2"
    ]
    found = set()
    text_lower = text.lower()
    for b in benchmarks:
        if b in text_lower:
            found.add(b)
    return found


def _extract_metric_keywords(text: str) -> set:
    """Extract known metric keywords for comparability analysis."""
    metrics = [
        "accuracy", "bleu", "rouge", "f1", "precision", "recall", "auc", "roc",
        "mrr", "ndcg", "perplexity", "mse", "rmse", "latency", "wer"
    ]
    found = set()
    text_lower = text.lower()
    for m in metrics:
        if m in text_lower:
            found.add(m)
    return found


def _gather_paper_evidence_for_driut(p_dict: Dict[str, Any], db: Optional[Session] = None) -> Tuple[List[Dict[str, Any]], str]:
    """Retrieve verified evidence records from DB or run in-memory extraction with zero mutations."""
    paper_id_val = p_dict.get("id")
    raw_text = (p_dict.get("raw_text") or "").strip()
    abstract = (p_dict.get("abstract") or "").strip()
    title = (p_dict.get("title") or "").strip()

    if raw_text and len(raw_text) > len(abstract) + 50:
        source_text = raw_text
        source_type = "full_text"
    elif abstract:
        source_text = f"{title}. {abstract}"
        source_type = "abstract"
    else:
        source_text = title
        source_type = "abstract"

    if db and paper_id_val is not None and isinstance(paper_id_val, int):
        records = db.query(PaperEvidence).filter(PaperEvidence.paper_id == paper_id_val).all()
        if records:
            items = []
            for r in records:
                items.append({
                    "category": r.category,
                    "claim": r.claim,
                    "source_passage": r.source_passage,
                    "char_start": r.char_start,
                    "char_end": r.char_end,
                    "section_name": r.section_name,
                    "source_type": r.source_type or source_type,
                    "confidence_score": r.confidence_score,
                })
            return items, records[0].source_type or source_type

    if source_text and len(source_text.strip()) >= 20:
        raw_items, _ = extract_evidence_from_text(source_text, source_type=source_type, max_items_per_category=2)
        return raw_items, source_type

def extract_effective_publication_year(paper: Dict[str, Any]) -> Tuple[Optional[int], bool, Optional[str]]:
    """
    Extract the effective publication year for chronological validation.
    Returns:
        (effective_year, is_scheduled_future_issue_only, source_note)
    Distinguishes verified electronic availability from scheduled future print volume issues.
    """
    venue_str = str(paper.get("venue") or "")
    pub_status = str(paper.get("publication_status") or "").lower()

    # 1. Direct electronic publication year if explicitly provided
    epub_year = paper.get("epub_year")
    if epub_year is not None:
        try:
            ey = int(epub_year)
            if 1900 <= ey <= 2035:
                return ey, False, f"electronic publication year {ey}"
        except (ValueError, TypeError):
            pass

    # 2. Extract from epubdate string
    epubdate_str = str(paper.get("epubdate") or "").strip()
    if epubdate_str:
        m = re.search(r"\b(19\d\d|20\d\d)\b", epubdate_str)
        if m:
            ey = int(m.group(1))
            return ey, False, f"electronic publication date ({epubdate_str})"

    # 3. Check for advance article annotation in venue string
    # e.g. "(Advance Article; Scheduled Print: 2027 Jan)"
    adv_match = re.search(r"Advance Article;\s*Scheduled Print:\s*(?:19\d\d|20\d\d)", venue_str)
    if adv_match:
        raw_year = paper.get("year")
        if raw_year is not None:
            try:
                y = int(raw_year)
                return y, False, f"advance electronic publication ({y})"
            except (ValueError, TypeError):
                pass

    # 4. Check for explicit forthcoming issue annotation
    forthcoming_match = re.search(r"Forthcoming(?: / Scheduled)? Issue:\s*(\b(?:19\d\d|20\d\d)\b)", venue_str)
    if forthcoming_match or pub_status == "forthcoming":
        fy = None
        if forthcoming_match:
            fy = int(forthcoming_match.group(1))
        elif paper.get("year"):
            try:
                fy = int(paper["year"])
            except (ValueError, TypeError):
                pass
        return fy, True, f"scheduled forthcoming print issue ({fy})"

    # 5. Standard paper year
    raw_year = paper.get("year")
    if raw_year is not None:
        try:
            y = int(raw_year)
            if 1900 <= y <= 2035:
                is_future = (y > 2026)
                note = f"scheduled publication year {y}" if is_future else f"publication year {y}"
                return y, is_future, note
        except (ValueError, TypeError):
            pass

    # 6. Parse pubdate if available
    pubdate_str = str(paper.get("pubdate") or "").strip()
    if pubdate_str:
        m = re.search(r"\b(19\d\d|20\d\d)\b", pubdate_str)
        if m:
            py = int(m.group(1))
            is_future = (py > 2026)
            return py, is_future, f"print date ({pubdate_str})"

    return None, False, None


def classify_relationship_evidence(
    saved_paper: Dict[str, Any],
    new_paper: Dict[str, Any],
    db: Optional[Session] = None
) -> DRIUTClassificationResult:
    """
    Evidence-backed scientific relationship classification between candidate paper and saved baseline.
    Evaluates:
    - 6 taxonomy categories (Extension, Improvement, Challenge, Reproduction, Alternative, Potential Replacement)
    - Grounded source passages with exact character offsets and section provenance
    - Disparate benchmark/metric protection (guards against invalid Improvement claims)
    - Distinguishes strong evidence, partial evidence, tentative inferences, and insufficient evidence.
    - Zero fabrication; deterministic output.
    """
    saved_title = (saved_paper.get("title") or "").strip()
    new_title = (new_paper.get("title") or "").strip()
    saved_abstract = (saved_paper.get("abstract") or "").strip()
    new_abstract = (new_paper.get("abstract") or "").strip()

    saved_pid = str(saved_paper.get("paper_id") or saved_paper.get("id") or "")
    new_pid = str(new_paper.get("paper_id") or new_paper.get("id") or "")

    # Base result structure
    base_res = DRIUTClassificationResult(
        candidate_paper_id=new_pid,
        candidate_title=new_title,
        saved_paper_id=saved_pid,
        saved_title=saved_title,
        relationship_type=None,
        confidence_score=0.0,
        evidence_strength="insufficient_evidence",
        explanation="",
        source_type="abstract",
        classification_version="v2.0-evidence-grounded",
        is_supported=False
    )

    # 1. Sanity checks: reject empty titles or comparing paper to itself
    if not saved_title or not new_title:
        base_res.uncertainty_warning = "Paper title is missing; classification cannot proceed."
        return base_res

    orig_saved_pid = saved_paper.get("paper_id")
    orig_new_pid = new_paper.get("paper_id")
    is_same_id = (orig_saved_pid is not None and orig_new_pid is not None and str(orig_saved_pid) == str(orig_new_pid))
    is_same_title = (saved_title.lower() == new_title.lower())

    if is_same_id or is_same_title:
        base_res.uncertainty_warning = "Identical paper detected; cannot classify a paper against itself."
        return base_res

    combined_saved = f"{saved_title} {saved_abstract}".strip()
    combined_new = f"{new_title} {new_abstract}".strip()
    if len(combined_saved.split()) < 4 or len(combined_new.split()) < 4:
        base_res.uncertainty_warning = "Insufficient text available for automated evidence extraction."
        return base_res

    # 2. Semantic Similarity Signal (Labelled as topical proximity, NOT proof of relationship)
    emb_saved = generate_embedding(f"{saved_title}. {saved_abstract}")
    emb_new = generate_embedding(f"{new_title}. {new_abstract}")
    cosine_sim = float(compute_cosine_similarity(emb_saved, emb_new))
    base_res.semantic_similarity = round(cosine_sim, 4)

    if cosine_sim < 0.40:
        base_res.uncertainty_warning = (
            f"Thematic similarity ({cosine_sim:.0%}) is below minimum relation threshold (40%). "
            "Papers address distinct research domains."
        )
        return base_res

    # 3. Source text, source type, and evidence retrieval
    cand_evidence, cand_source_type = _gather_paper_evidence_for_driut(new_paper, db=db)
    saved_evidence, saved_source_type = _gather_paper_evidence_for_driut(saved_paper, db=db)
    base_res.source_type = cand_source_type

    cand_text = (new_paper.get("raw_text") or "").strip()
    if not cand_text or len(cand_text) < len(new_abstract) + 50:
        cand_text = f"{new_title}. {new_abstract}".strip()

    # 4. Keyword and direct citation detection
    kw_saved = set(extract_keywords_from_text(f"{saved_title} {saved_abstract}", top_k=10))
    kw_new = set(extract_keywords_from_text(f"{new_title} {new_abstract}", top_k=10))
    shared_kw = sorted(list(kw_saved.intersection(kw_new)))

    saved_core_name = saved_title.split(":")[0].strip()
    direct_mention = False
    cand_lower = cand_text.lower()

    if len(saved_core_name) >= 6 and saved_core_name.lower() in cand_lower:
        direct_mention = True
    else:
        for token in saved_core_name.split():
            clean_tok = token.strip(",:()[]\"'")
            if clean_tok.lower() in GENERIC_RESEARCH_TERMS or len(clean_tok) < 3:
                continue
            if clean_tok.isupper() and len(clean_tok) >= 3:
                if re.search(r"\b" + re.escape(clean_tok.lower()) + r"\b", cand_lower):
                    direct_mention = True
                    break

    # 5. Benchmark & Metric Comparability Guard (Preventing false Improvement on disparate protocols)
    saved_datasets = _extract_dataset_keywords(f"{saved_title} {saved_abstract}")
    new_datasets = _extract_dataset_keywords(cand_text)
    saved_metrics = _extract_metric_keywords(f"{saved_title} {saved_abstract}")
    new_metrics = _extract_metric_keywords(cand_text)

    protocols_incompatible = False
    comparability_note = None

    if saved_datasets and new_datasets and not (saved_datasets & new_datasets):
        protocols_incompatible = True
        comparability_note = (
            f"Incompatible benchmark protocols: candidate evaluates on {list(new_datasets)[:2]}, "
            f"while baseline evaluates on {list(saved_datasets)[:2]}. Direct numerical improvement is invalid."
        )
    elif saved_metrics and new_metrics and not (saved_metrics & new_metrics):
        protocols_incompatible = True
        comparability_note = (
            f"Incompatible evaluation metrics: candidate reports {list(new_metrics)[:2]}, "
            f"while baseline reports {list(saved_metrics)[:2]}. Superiority cannot be scientifically established."
        )

    # 6. Sentence-Level Grounded Pattern Matching across the 6 Categories
    sentences_with_spans = split_text_into_sentences_with_spans(cand_text)
    category_matches: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in PATTERNS}

    for passage, s_start, s_end in sentences_with_spans:
        passage_clean = passage.strip()
        if len(passage_clean) < 10:
            continue

        for cat, regex_list in PATTERNS.items():
            for regex in regex_list:
                m = re.search(regex, passage_clean, re.IGNORECASE)
                if m:
                    section = "Abstract" if cand_source_type == "abstract" else ("Full Text" if s_start > 500 else "Introduction")
                    category_matches[cat].append({
                        "passage": passage_clean,
                        "char_start": s_start,
                        "char_end": s_end,
                        "section_name": section,
                        "matched_term": m.group(0),
                    })
                    break

    # Score each category
    category_scores = {cat: len(matches) for cat, matches in category_matches.items()}
    best_cat, best_count = max(category_scores.items(), key=lambda x: x[1])

    # 7. Apply Specificity and Disparate Protocol Rules
    chosen_cat: Optional[str] = None
    supporting_match: Optional[Dict[str, Any]] = None
    uncertainty_warnings: List[str] = []

    if cand_source_type == "abstract":
        uncertainty_warnings.append("Evaluated from abstract text only. Full-text provenance required for complete experimental protocol validation.")

    if best_count > 0:
        chosen_cat = best_cat
        supporting_match = category_matches[best_cat][0]

        # Guard Improvement against incompatible protocols
        if chosen_cat == "Improvement" and protocols_incompatible:
            # Downgrade or reject: numerical improvement under disparate protocols is invalid
            if category_scores.get("Extension", 0) > 0:
                chosen_cat = "Extension"
                supporting_match = category_matches["Extension"][0]
                uncertainty_warnings.append(
                    f"Improvement claim downgraded to Extension: {comparability_note}"
                )
            elif category_scores.get("Alternative", 0) > 0 or len(shared_kw) >= 2:
                chosen_cat = "Alternative"
                supporting_match = category_matches["Alternative"][0] if category_matches["Alternative"] else supporting_match
                uncertainty_warnings.append(
                    f"Improvement claim downgraded to Alternative: {comparability_note}"
                )
            else:
                # Unsupported improvement claim across disparate benchmarks
                base_res.uncertainty_warning = (
                    f"Candidate reports performance gains, but evaluation benchmarks/metrics differ from saved paper. "
                    f"{comparability_note}"
                )
                base_res.comparability_notes = comparability_note
                base_res.evidence_strength = "insufficient_evidence"
                return base_res

    # 8. Handle Cases with No Category Pattern Matched (best_count == 0)
    if not chosen_cat or best_count == 0:
        # STRICT RULE: A semantic similarity score alone must NEVER establish a relationship category!
        # If no explicit category pattern exists, do NOT guess Improvement or Extension.
        base_res.uncertainty_warning = (
            f"Thematic similarity ({cosine_sim:.0%}) detected, but source text contains insufficient scientific evidence "
            "to establish an Extension, Improvement, Challenge, Reproduction, Alternative, or Potential Replacement."
        )
        base_res.evidence_strength = "insufficient_evidence"
        base_res.is_supported = False
        return base_res

    # 8b. Chronology-Aware Relationship Guard
    # Prevents an earlier publication from being classified as an improvement, extension, challenge, or replacement of a later work.
    new_year, new_is_scheduled, new_note = extract_effective_publication_year(new_paper)
    saved_year, saved_is_scheduled, saved_note = extract_effective_publication_year(saved_paper)

    DIRECTIONAL_CATEGORIES = {"Improvement", "Extension", "Potential Replacement", "Challenge", "Reproduction"}

    if chosen_cat in DIRECTIONAL_CATEGORIES:
        if new_year is not None and saved_year is not None:
            if new_year < saved_year:
                # Chronological conflict: candidate precedes baseline
                base_res.uncertainty_warning = (
                    f"Chronological conflict: candidate paper ({new_note}) precedes baseline paper ({saved_note}). "
                    f"An earlier publication cannot establish an {chosen_cat} of a subsequent work."
                )
                base_res.evidence_strength = "insufficient_evidence"
                base_res.is_supported = False
                base_res.relationship_type = None
                return base_res
            elif new_year == saved_year:
                uncertainty_warnings.append(
                    f"Both papers share publication year {new_year}; exact sub-year chronology cannot be verified from metadata."
                )
        elif new_year is None or saved_year is None:
            uncertainty_warnings.append(
                "Publication date is unrecorded in catalog metadata; chronological directionality cannot be independently verified from dates."
            )
    elif chosen_cat == "Alternative":
        if new_year is not None and saved_year is not None and new_year != saved_year:
            uncertainty_warnings.append(
                f"Alternative paradigm comparison across publication timeline ({new_year} vs {saved_year})."
            )

    # 9. Calibrate Confidence & Evidence Strength
    has_explicit_grounding = (supporting_match is not None)
    
    if direct_mention and has_explicit_grounding:
        strength = "strong_evidence"
        confidence = min(0.98, 0.75 + (cosine_sim * 0.15) + (best_count * 0.05))
    elif has_explicit_grounding and len(shared_kw) >= 2:
        strength = "partial_evidence"
        confidence = min(0.92, 0.65 + (cosine_sim * 0.15) + (best_count * 0.05))
    else:
        strength = "tentative"
        confidence = min(0.85, 0.55 + (cosine_sim * 0.20))

    if chosen_cat == "Potential Replacement" and strength != "strong_evidence":
        # Replacement claims without direct baseline mention are tentative
        strength = "tentative"
        confidence = min(0.78, confidence)
        uncertainty_warnings.append("Potential replacement claim is tentative; multi-benchmark comparative verification recommended.")

    # 10. Locate Saved Paper Baseline Passage
    saved_baseline_passage = None
    if saved_evidence:
        # Prefer method or problem claim
        for ev in saved_evidence:
            if ev.get("category") in ["method", "problem", "contributions", "results"]:
                saved_baseline_passage = ev.get("source_passage") or ev.get("claim")
                break
    if not saved_baseline_passage and saved_abstract:
        saved_baseline_passage = saved_abstract[:250].strip()

    # 11. Synthesize Traceable Structured Explanation
    explanation = generate_driut_explanation(
        cat_type=chosen_cat,
        saved_title=saved_title,
        new_title=new_title,
        similarity=cosine_sim,
        shared_keywords=shared_kw,
        direct_mention=direct_mention
    )

    return DRIUTClassificationResult(
        candidate_paper_id=new_pid,
        candidate_title=new_title,
        saved_paper_id=saved_pid,
        saved_title=saved_title,
        relationship_type=chosen_cat,
        confidence_score=float(round(confidence, 2)),
        evidence_strength=strength,
        explanation=explanation,
        evidence_passage=supporting_match.get("passage") if supporting_match else None,
        saved_evidence_passage=saved_baseline_passage,
        char_start=supporting_match.get("char_start") if supporting_match else None,
        char_end=supporting_match.get("char_end") if supporting_match else None,
        section_name=supporting_match.get("section_name") if supporting_match else ("Abstract" if cand_source_type == "abstract" else None),
        source_type=cand_source_type,
        semantic_similarity=round(cosine_sim, 4),
        comparability_notes=comparability_note,
        uncertainty_warning=" | ".join(uncertainty_warnings) if uncertainty_warnings else None,
        classification_version="v2.0-evidence-grounded",
        is_supported=True
    )


def classify_relationship(saved_paper: Dict[str, Any], new_paper: Dict[str, Any]) -> Tuple[Optional[str], float, str]:
    """
    Backwards-compatible wrapper returning (relationship_type, confidence_score, explanation).
    Preserves exact signature for existing tests and endpoints while delegating to
    evidence-backed classification.
    """
    res = classify_relationship_evidence(saved_paper, new_paper)
    if not res.is_supported or res.evidence_strength == "insufficient_evidence" or not res.relationship_type:
        return None, 0.0, ""
    return res.relationship_type, res.confidence_score, res.explanation


def generate_driut_explanation(
    cat_type: str,
    saved_title: str,
    new_title: str,
    similarity: float,
    shared_keywords: List[str],
    direct_mention: bool
) -> str:
    """Generate structured human-readable explanation for DRIUT alert with explicit similarity attribution."""
    kw_str = ", ".join(shared_keywords[:4]) if shared_keywords else "domain methodology"
    mention_str = " Directly references and evaluates the original baseline." if direct_mention else ""

    explanations = {
        "Extension": f"'{new_title}' extends the architecture of your saved paper '{saved_title}', expanding capabilities and adapting it to new modalities around {kw_str} (Topical match: {similarity:.0%}).{mention_str}",
        "Improvement": f"'{new_title}' achieves higher benchmark performance and addresses efficiency limitations found in '{saved_title}' across {kw_str} under aligned evaluation (Topical match: {similarity:.0%}).{mention_str}",
        "Challenge": f"'{new_title}' questions assumptions or identifies vulnerabilities/limitations in the approach introduced by '{saved_title}' regarding {kw_str} (Topical match: {similarity:.0%}).{mention_str}",
        "Reproduction": f"'{new_title}' conducts a systematic replication and empirical evaluation of results published in '{saved_title}' on {kw_str} (Topical match: {similarity:.0%}).{mention_str}",
        "Alternative": f"'{new_title}' introduces an alternative computational paradigm solving the same underlying objective as '{saved_title}' without depending on its primary architecture (Topical match: {similarity:.0%}).{mention_str}",
        "Potential Replacement": f"'{new_title}' supercedes previous approaches including '{saved_title}', providing a drop-in replacement with state-of-the-art results on {kw_str} (Topical match: {similarity:.0%}).{mention_str}"
    }

    return explanations.get(cat_type, f"Identified meaningful {cat_type.lower()} relationship with '{saved_title}' with {similarity:.0%} semantic similarity.")


def scan_saved_papers_for_updates(session: Session, new_papers: List[Dict[str, Any]], user_id: str = "default_user") -> List[DRIUTAlert]:
    """
    Scan all user's saved papers against incoming papers and create evidence-backed DRIUT alerts.
    Idempotent: preserves existing alerts and never creates duplicates.
    """
    saved_entries = session.query(SavedPaper).filter(SavedPaper.user_id == user_id).all()
    created_alerts: List[DRIUTAlert] = []
    newly_inserted_pids: List[str] = []

    for saved in saved_entries:
        saved_paper = saved.paper
        saved_dict = {
            "id": saved_paper.id,
            "paper_id": saved_paper.paper_id,
            "title": saved_paper.title,
            "abstract": saved_paper.abstract or ""
        }

        for new_p in new_papers:
            candidate_id = new_p.get("paper_id")
            if not candidate_id or candidate_id == saved_paper.paper_id:
                continue

            classification = classify_relationship_evidence(saved_dict, new_p, db=session)
            if classification.is_supported and classification.relationship_type and classification.confidence_score >= 0.65:
                # Find or ensure trigger paper is in DB
                db_trigger = session.query(Paper).filter(Paper.paper_id == candidate_id).first()
                if not db_trigger:
                    paper_cols = Paper.__table__.columns.keys()
                    clean_data = {k: v for k, v in new_p.items() if k in paper_cols and k != "id"}
                    if "title" not in clean_data or not clean_data["title"]:
                        clean_data["title"] = "Untitled Paper"
                    if "source" not in clean_data or not clean_data["source"]:
                        clean_data["source"] = "academic"
                    db_trigger = Paper(**clean_data)
                    session.add(db_trigger)
                    session.flush()
                    newly_inserted_pids.append(candidate_id)

                # Check if alert already exists for (user_id, saved_paper_id, trigger_paper_id)
                existing_alert = session.query(DRIUTAlert).filter(
                    DRIUTAlert.user_id == user_id,
                    DRIUTAlert.saved_paper_id == saved_paper.id,
                    DRIUTAlert.trigger_paper_id == db_trigger.id
                ).first()

                if not existing_alert:
                    alert = DRIUTAlert(
                        user_id=user_id,
                        saved_paper_id=saved_paper.id,
                        trigger_paper_id=db_trigger.id,
                        relationship_type=classification.relationship_type,
                        confidence_score=classification.confidence_score,
                        explanation=classification.explanation,
                        is_read=False,
                        evidence_strength=classification.evidence_strength,
                        evidence_passage=classification.evidence_passage,
                        saved_evidence_passage=classification.saved_evidence_passage,
                        char_start=classification.char_start,
                        char_end=classification.char_end,
                        section_name=classification.section_name,
                        source_type=classification.source_type,
                        semantic_similarity=classification.semantic_similarity,
                        comparability_notes=classification.comparability_notes,
                        uncertainty_warning=classification.uncertainty_warning,
                        classification_version=classification.classification_version,
                    )
                    session.add(alert)
                    created_alerts.append(alert)
                    try:
                        from app.services.notification_service import notification_dispatcher
                        notification_dispatcher.dispatch_alert_notification(
                            user_id=user_id,
                            saved_paper_title=saved_paper.title,
                            trigger_paper_title=db_trigger.title,
                            relationship_type=classification.relationship_type,
                            confidence_score=classification.confidence_score,
                            explanation=classification.explanation
                        )
                    except Exception as ne:
                        logger.warning("Error dispatching DRIUT notification: %s", ne)

    session.commit()
    logger.info("DRIUT scan completed: generated %d new research update alerts.", len(created_alerts))

    # Post-commit durable synchronization to FAISS
    if newly_inserted_pids:
        try:
            from app.services.vector_index import sync_unindexed_papers
            synced_cnt = sync_unindexed_papers(session=session, paper_ids=newly_inserted_pids)
            logger.info("Synchronized %d newly ingested DRIUT trigger papers into FAISS vector index.", synced_cnt)
        except Exception as sync_err:
            logger.error("Error synchronizing DRIUT papers to FAISS (will be retried on next recovery): %s", sync_err)

    return created_alerts


async def scan_research_impact_updates(
    session: Session,
    user_id: Optional[str] = None,
    query_academic: bool = True
) -> Dict[str, Any]:
    """
    Automated research impact monitoring for researcher libraries.
    Discovers new/related literature across academic sources (arXiv, PubMed, CSIR-NIScPR, Crossref)
    and local database papers, classifies conceptual relationships across the 6 taxonomy categories,
    and creates persistent evidence-backed alerts strictly scoped to each paper's owner.
    
    Tolerates partial provider failures without aborting the scan.
    Guarantees idempotency (never creates duplicate alerts or resets is_read status).
    """
    from app.services.academic_sources import (
        search_arxiv, search_pubmed, search_csir_niscpr, search_crossref
    )
    from app.services.notification_service import notification_dispatcher

    # 1. Determine target users to monitor
    if user_id:
        target_users = [user_id]
    else:
        target_users = [r[0] for r in session.query(SavedPaper.user_id).distinct().all()]

    if not target_users:
        logger.info("DRIUT automated scan: No active saved papers found to monitor.")
        return {
            "users_scanned": 0,
            "saved_papers_monitored": 0,
            "candidates_evaluated": 0,
            "new_alerts_created": 0,
            "new_alerts": [],
            "provider_status": {},
            "provider_errors": {}
        }

    provider_status: Dict[str, str] = {}
    provider_errors: Dict[str, str] = {}
    total_candidates_evaluated = 0
    total_saved_papers_monitored = 0
    created_alerts: List[DRIUTAlert] = []

    # Get local papers once
    local_papers = session.query(Paper).all()
    local_paper_dicts = [{
        "paper_id": p.paper_id,
        "title": p.title,
        "abstract": p.abstract or "",
        "authors": p.authors or [],
        "venue": p.venue or "",
        "year": p.year,
        "doi": p.doi,
        "url": p.url,
        "pdf_url": p.pdf_url,
        "source": p.source or "local",
        "citation_count": p.citation_count or 0,
        "categories": p.categories or []
    } for p in local_papers]

    newly_inserted_pids: List[str] = []

    for uid in target_users:
        saved_entries = session.query(SavedPaper).filter(SavedPaper.user_id == uid).all()
        if not saved_entries:
            continue
        total_saved_papers_monitored += len(saved_entries)

        for saved in saved_entries:
            saved_paper = saved.paper
            saved_dict = {
                "id": saved_paper.id,
                "paper_id": saved_paper.paper_id,
                "title": saved_paper.title,
                "abstract": saved_paper.abstract or ""
            }

            # Candidate pool starts with local database papers
            candidates_by_id: Dict[str, Dict[str, Any]] = {}
            for lp in local_paper_dicts:
                if lp["paper_id"] != saved_paper.paper_id:
                    candidates_by_id[lp["paper_id"]] = lp

            # 2. Query academic sources if enabled
            if query_academic:
                keywords = extract_keywords_from_text(saved_paper.title, top_k=3)
                search_query = " ".join(keywords) if keywords else saved_paper.title[:60].strip()

                providers = [
                    ("arxiv", search_arxiv),
                    ("pubmed", search_pubmed),
                    ("csir", search_csir_niscpr),
                    ("crossref", search_crossref),
                ]

                for pname, pfn in providers:
                    try:
                        results = await pfn(search_query, max_results=3)
                        provider_status[pname] = "healthy"
                        for res_item in results:
                            pid = res_item.get("paper_id")
                            if pid and pid != saved_paper.paper_id and pid not in candidates_by_id:
                                candidates_by_id[pid] = res_item
                    except Exception as p_err:
                        provider_status[pname] = "error"
                        provider_errors[pname] = str(p_err)
                        logger.warning(
                            "Academic provider '%s' failed during DRIUT scan for query '%s': %s",
                            pname, search_query, p_err
                        )

            # 3. Classify relationships against candidates
            for candidate_id, candidate in candidates_by_id.items():
                if candidate.get("title", "").lower() == saved_paper.title.lower():
                    continue

                total_candidates_evaluated += 1
                classification = classify_relationship_evidence(saved_dict, candidate, db=session)

                if classification.is_supported and classification.relationship_type and classification.confidence_score >= 0.65:
                    # Ensure candidate paper exists in DB
                    db_trigger = session.query(Paper).filter(Paper.paper_id == candidate_id).first()
                    if not db_trigger:
                        paper_cols = Paper.__table__.columns.keys()
                        clean_data = {
                            k: v for k, v in candidate.items()
                            if k in paper_cols and k != "id"
                        }
                        if "title" not in clean_data or not clean_data["title"]:
                            clean_data["title"] = "Untitled Paper"
                        if "source" not in clean_data or not clean_data["source"]:
                            clean_data["source"] = "academic"
                        db_trigger = Paper(**clean_data)
                        session.add(db_trigger)
                        session.flush()
                        newly_inserted_pids.append(candidate_id)

                    # Idempotency check: look up existing alert
                    existing_alert = session.query(DRIUTAlert).filter(
                        DRIUTAlert.user_id == uid,
                        DRIUTAlert.saved_paper_id == saved_paper.id,
                        DRIUTAlert.trigger_paper_id == db_trigger.id
                    ).first()

                    if not existing_alert:
                        alert = DRIUTAlert(
                            user_id=uid,
                            saved_paper_id=saved_paper.id,
                            trigger_paper_id=db_trigger.id,
                            relationship_type=classification.relationship_type,
                            confidence_score=classification.confidence_score,
                            explanation=classification.explanation,
                            is_read=False,
                            evidence_strength=classification.evidence_strength,
                            evidence_passage=classification.evidence_passage,
                            saved_evidence_passage=classification.saved_evidence_passage,
                            char_start=classification.char_start,
                            char_end=classification.char_end,
                            section_name=classification.section_name,
                            source_type=classification.source_type,
                            semantic_similarity=classification.semantic_similarity,
                            comparability_notes=classification.comparability_notes,
                            uncertainty_warning=classification.uncertainty_warning,
                            classification_version=classification.classification_version,
                        )
                        session.add(alert)
                        created_alerts.append(alert)
                        try:
                            notification_dispatcher.dispatch_alert_notification(
                                user_id=uid,
                                saved_paper_title=saved_paper.title,
                                trigger_paper_title=db_trigger.title,
                                relationship_type=classification.relationship_type,
                                confidence_score=classification.confidence_score,
                                explanation=classification.explanation
                            )
                        except Exception as ne:
                            logger.warning("Error dispatching DRIUT notification: %s", ne)
                    else:
                        # Existing alert: NEVER overwrite or reset is_read
                        pass

    session.commit()
    logger.info(
        "Automated DRIUT scan completed: %d users, %d saved papers, %d candidates evaluated, %d new alerts created.",
        len(target_users), total_saved_papers_monitored, total_candidates_evaluated, len(created_alerts)
    )

    # Post-commit durable synchronization to FAISS
    if newly_inserted_pids:
        try:
            from app.services.vector_index import sync_unindexed_papers
            synced_cnt = sync_unindexed_papers(session=session, paper_ids=newly_inserted_pids)
            logger.info("Synchronized %d newly ingested DRIUT trigger papers into FAISS vector index.", synced_cnt)
        except Exception as sync_err:
            logger.error("Error synchronizing DRIUT papers to FAISS (will be retried on next recovery): %s", sync_err)


    return {
        "users_scanned": len(target_users),
        "saved_papers_monitored": total_saved_papers_monitored,
        "candidates_evaluated": total_candidates_evaluated,
        "new_alerts_created": len(created_alerts),
        "new_alerts": created_alerts,
        "provider_status": provider_status,
        "provider_errors": provider_errors
    }

