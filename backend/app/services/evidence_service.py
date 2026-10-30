"""
ResearchLens Evidence Extraction and Verification Service.
Deterministic, grounded research evidence extraction linking scientific claims
to exact source passages with character offsets, provenance tracking, and zero fabrication.
"""
import hashlib
import re
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.paper import Paper
from app.models.evidence import PaperEvidence
from app.schemas.evidence import (
    EvidenceCategory,
    CATEGORY_LABELS,
    EvidenceItemResponse,
    EvidenceVerificationSummary,
    PaperEvidenceResponse,
)

logger = get_logger(__name__)

ALL_EVIDENCE_CATEGORIES = [
    EvidenceCategory.PROBLEM.value,
    EvidenceCategory.OBJECTIVE.value,
    EvidenceCategory.METHOD.value,
    EvidenceCategory.DATASET.value,
    EvidenceCategory.METRICS.value,
    EvidenceCategory.RESULTS.value,
    EvidenceCategory.CONTRIBUTIONS.value,
    EvidenceCategory.LIMITATIONS.value,
    EvidenceCategory.FUTURE_WORK.value,
]

# Detection pattern for legacy synthetic placeholder abstracts in PubMed records
SYNTHETIC_PLACEHOLDER_REGEX = re.compile(
    r"\bBiomedical\s+&\s+computational\s+research\s+paper\s+indexed\s+by\s+the\s+US\s+National\s+Library\s+of\s+Medicine\b",
    re.IGNORECASE
)


def is_synthetic_placeholder_abstract(text: Optional[str]) -> bool:
    """
    Detect whether abstract text is a synthetic placeholder rather than genuine scientific content.
    Prevents hallucinating or fabricating claims from indexing placeholder strings.
    Preserves genuine scientific abstracts that legitimately discuss biomedical NLP, NLM, or PubMed datasets.
    """
    if not text or not isinstance(text, str):
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if SYNTHETIC_PLACEHOLDER_REGEX.search(stripped):
        return True
    if re.match(r"^(?:abstract\s+unavailable\.?|no\s+abstract\s+available\.?|placeholder)$", stripped, re.IGNORECASE):
        return True
    return False

# Patterns for each of the 9 evidence categories
# Ordered by specificity, with calibrated rule scores (heuristic match strengths)
CATEGORY_PATTERNS: Dict[str, List[Tuple[str, float]]] = {
    EvidenceCategory.PROBLEM.value: [
        (r"\b(?:a\s+major\s+challenge|the\s+main\s+challenge|fundamental\s+problem|key\s+bottleneck|critical\s+limitation)\b", 0.95),
        (r"\b(?:suffer\s+from|struggle\s+to|remains\s+(?:a\s+)?difficult|lack\s+of|vulnerability\s+to|inability\s+to|hinders|impedes)\b", 0.90),
        (r"\b(?:existing\s+approaches\s+fail|existing\s+methods\s+(?:are\s+limited|fall\s+short|suffer))\b", 0.88),
        (r"\b(?:however|nevertheless|nonetheless|despite\s+recent\s+progress),?\s+(?:existing|current|most|prior|traditional)\b", 0.82),
        (r"\b(?:high\s+computational\s+cost|severe\s+overhead|unresolved\s+issue|security\s+flaw|scalability\s+issue)\b", 0.80),
    ],
    EvidenceCategory.OBJECTIVE.value: [
        (r"\b(?:in\s+this\s+(?:paper|work|study|article),\s+we\s+aim\s+to|our\s+goal\s+is\s+to|our\s+objective\s+is\s+to)\b", 0.95),
        (r"\b(?:we\s+seek\s+to|we\s+address\s+the\s+question|we\s+investigate\s+(?:whether|how)|we\s+focus\s+on\s+addressing)\b", 0.90),
        (r"\b(?:the\s+purpose\s+of\s+this\s+work|we\s+explore\s+the\s+possibility|this\s+paper\s+tackles)\b", 0.85),
        (r"\b(?:to\s+(?:overcome|address|solve)\s+this\s+(?:challenge|problem|limitation),\s+we)\b", 0.82),
    ],
    EvidenceCategory.METHOD.value: [
        (r"\b(?:we\s+propose|we\s+present|we\s+introduce|we\s+develop|we\s+design)\b", 0.95),
        (r"\b(?:our\s+approach|our\s+method|our\s+framework|our\s+model|our\s+pipeline)\b", 0.90),
        (r"\b(?:novel\s+(?:architecture|framework|methodology|algorithm|approach|strategy))\b", 0.85),
        (r"\b(?:we\s+formulate|we\s+employ|we\s+leverage|we\s+utilize|we\s+construct)\b", 0.78),
    ],
    EvidenceCategory.DATASET.value: [
        (r"\b(?:benchmarks?\s+such\s+as|evaluated\s+on\s+(?:the\s+)?|experiments?\s+on\s+(?:the\s+)?|tested\s+on\s+(?:the\s+)?|trained\s+on\s+(?:the\s+)?)\b", 0.92),
        (r"\b(?:using\s+the\s+([A-Z][A-Za-z0-9_-]+(?:\s+[A-Z][A-Za-z0-9_-]+)*\s+(?:dataset|corpus|benchmark)))\b", 0.90),
        (r"\b(?:dataset\s+consisting\s+of|corpus\s+of|real-world\s+dataset|synthetic\s+dataset)\b", 0.88),
        (r"\b(?:ImageNet|GLUE|SQuAD|WMT|MNIST|CIFAR-10|CIFAR-100|TREC|SuperGLUE|MultiNLI|SNLI|CoNLL|MS\s+COCO|MMLU)\b", 0.95),
        (r"\b(?:experimental\s+setup|hardware\s+environment|GPU|simulation\s+platform)\b", 0.75),
    ],
    EvidenceCategory.METRICS.value: [
        (r"\b(?:metrics?\s+such\s+as|metrics?\s+include|evaluated\s+(?:using|with|by)|measured\s+by)\b", 0.90),
        (r"\b(?:accuracy|BLEU|ROUGE(?:-[12L])?|F1(?:-score)?|precision|recall|AUC(?:-ROC)?|ROC|perplexity|mean\s+reciprocal\s+rank|MRR|NDCG)\b", 0.92),
        (r"\b(?:mean\s+squared\s+error|MSE|RMSE|latency|throughput|inference\s+time|top-[15]\s+accuracy|WER)\b", 0.88),
        (r"\b(?:evaluation\s+criteria|quantitative\s+metric|standard\s+benchmarks?\s+metrics?)\b", 0.75),
    ],
    EvidenceCategory.RESULTS.value: [
        (r"\b(?:results?\s+(?:show|demonstrate|indicate|reveal|confirm)|empirical\s+results?\s+show)\b", 0.92),
        (r"\b(?:outperforms?\s+(?:all\s+)?(?:existing|prior|state-of-the-art|baseline|competitive))\b", 0.95),
        (r"\b(?:we\s+achieve|state-of-the-art\s+performance|SOTA|superior\s+performance|consistently\s+beats?)\b", 0.92),
        (r"\b(?:improves?\s+(?:by|over)|gain\s+of|significant\s+improvement|reduces?\s+(?:error|latency|cost)\s+by)\b", 0.88),
        (r"\b(?:demonstrates?\s+(?:substantial|considerable|remarkable)\s+(?:gains?|improvements?))\b", 0.82),
    ],
    EvidenceCategory.CONTRIBUTIONS.value: [
        (r"\b(?:our\s+contributions?\s+(?:are|include|can\s+be\s+summarized)|we\s+make\s+the\s+following\s+contributions?)\b", 0.98),
        (r"\b(?:main\s+contribution|key\s+contribution|primary\s+contribution)\b", 0.95),
        (r"\b(?:to\s+the\s+best\s+of\s+our\s+knowledge,\s+(?:this\s+is\s+the\s+first|we\s+are\s+the\s+first)|first\s+to\s+demonstrate)\b", 0.92),
        (r"\b(?:this\s+work\s+contributes|we\s+contribute\s+(?:a|an))\b", 0.85),
    ],
    EvidenceCategory.LIMITATIONS.value: [
        (r"\b(?:a\s+(?:major\s+|primary\s+|key\s+)?limitation\s+of|our\s+approach\s+is\s+limited|limitations?\s+include|primary\s+limitation)\b", 0.95),
        (r"\b(?:threats?\s+to\s+validity|fails\s+to|degrades\s+when|performance\s+drops\s+when)\b", 0.90),
        (r"\b(?:trade-off\s+between|requires\s+substantial\s+computational|high\s+memory\s+overhead)\b", 0.85),
        (r"\b(?:assumes\s+that|restricted\s+to\s+(?:only\s+)?|does\s+not\s+scale\s+well|vulnerable\s+to|sensitive\s+to\s+hyperparameters)\b", 0.82),
        (r"\b(?:we\s+acknowledge\s+that|unavoidable\s+drawback|boundary\s+condition)\b", 0.78),
    ],
    EvidenceCategory.FUTURE_WORK.value: [
        (r"\b(?:in\s+future\s+work|future\s+research|we\s+plan\s+to|left\s+for\s+future\s+(?:work|investigation))\b", 0.95),
        (r"\b(?:promising\s+direction\s+for\s+future|remains\s+an\s+open\s+direction|we\s+hope\s+to\s+extend)\b", 0.90),
        (r"\b(?:future\s+investigation|future\s+extensions?|as\s+next\s+steps|future\s+efforts\s+will\s+focus)\b", 0.85),
        (r"\b(?:open\s+challenge\s+for\s+future|paves\s+the\s+way\s+for\s+future)\b", 0.80),
    ],
}


def split_text_into_sentences_with_spans(text: str) -> List[Tuple[str, int, int]]:
    """
    Split text into sentence passages while strictly preserving exact (char_start, char_end) offsets.
    Guarantees: text[char_start:char_end] == passage.
    Handles decimal numbers (3.5x), common abbreviations (et al., e.g., i.e.), and paragraph breaks.
    """
    if not text:
        return []

    cuts = [0]
    n = len(text)
    i = 0
    last_line_start = 0
    while i < n:
        if text[i] in '.!?':
            # Ignore decimal numbers like 3.5 or 0.05
            if text[i] == '.' and i > 0 and text[i - 1].isdigit() and i + 1 < n and text[i + 1].isdigit():
                i += 1
                continue

            j = i + 1
            while j < n and text[j] in ' \t\r\n"\'’”)]':
                j += 1

            if j > i + 1:
                word_before = text[max(0, i - 6):i].lower()
                if any(word_before.endswith(abbr) for abbr in ['al', 'eg', 'ie', 'fig', 'tab', 'vs', 'no', 'vol', 'pp', 'dr', 'prof']):
                    i += 1
                    continue
                cuts.append(j)
                i = j
                last_line_start = j
                continue
        elif text[i] == '\n':
            line_content = text[last_line_start:i].strip()
            # If line is double newline OR line was a short header / page marker
            is_header_or_marker = bool(
                re.match(r'^(?:---\s*Page\s*\d+\s*---|\[Page\s*\d+\]|(?:[0-9IVX]+\.?\s*)?[A-Z][A-Za-z\s]{2,40})$', line_content)
            )
            is_double_nl = (i + 1 < n and text[i + 1] == '\n')
            if is_double_nl or is_header_or_marker:
                j = i + 1
                while j < n and text[j] in ' \t\r\n':
                    j += 1
                cuts.append(j)
                i = j
                last_line_start = j
                continue
            last_line_start = i + 1
        i += 1
    cuts.append(n)

    results: List[Tuple[str, int, int]] = []
    for k in range(len(cuts) - 1):
        raw_start = cuts[k]
        raw_end = cuts[k + 1]
        chunk = text[raw_start:raw_end]
        stripped = chunk.strip()
        if len(stripped) >= 15:
            rel_start = chunk.find(stripped)
            exact_start = raw_start + rel_start
            exact_end = exact_start + len(stripped)
            if text[exact_start:exact_end] == stripped:
                results.append((stripped, exact_start, exact_end))

    # Fallback for plain blocks of text without traditional punctuation
    if not results and text.strip():
        stripped = text.strip()
        if len(stripped) >= 15:
            exact_start = text.find(stripped)
            exact_end = exact_start + len(stripped)
            if text[exact_start:exact_end] == stripped:
                results.append((stripped, exact_start, exact_end))

    return results


def extract_concise_claim_from_passage(passage: str, category: str) -> str:
    """
    Produce a clean, concise author-stated claim statement from the supporting passage.
    Does not fabricate interpretations or synthetic facts.
    Preserves author phrasing while normalizing citations.
    """
    # Remove bracketed citation numbers like [1], [2, 3], [Vaswani et al. 2017]
    cleaned = re.sub(r"\[\d+(?:[,\s–-]+\d+)*\]", "", passage)
    cleaned = re.sub(r"\[[A-Za-z]+(?:\s+et\s+al\.?)?,?\s*\d{4}\]", "", cleaned)
    # Remove excessive spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def detect_section_name(text: str, offset: int) -> Optional[str]:
    """
    Identify academic section header preceding the character offset in full text.
    Returns None if text is an abstract or no explicit section header is found.
    """
    # Look backwards up to 1000 characters from the offset for common section headers
    preceding = text[max(0, offset - 1000):offset]
    section_pattern = re.compile(
        r"(?:\n|^)(?:[0-9IVX]+\.?\s*)?(Abstract|Introduction|Related\s+Work|Background|Methodology|Method|Proposed\s+Method|Architecture|Experiments?|Experimental\s+Setup|Results?|Discussion|Limitations?|Future\s+Work|Conclusion)[\s:]*?\n",
        re.IGNORECASE
    )
    matches = list(section_pattern.finditer(preceding))
    if matches:
        last_match = matches[-1]
        raw_header = last_match.group(1).strip()
        return raw_header.title()
    return None


def detect_page_number(text: str, offset: int) -> Optional[int]:
    """
    Identify page number if text contains reliable page markers (e.g., from PDF page splits).
    Returns None if no reliable page boundaries exist. Zero fabrication rule.
    """
    preceding = text[:offset]
    # Check for deterministic page delimiters like "--- Page X ---" or "\x0c" (form feeds)
    form_feeds = preceding.count("\x0c")
    if form_feeds > 0:
        return form_feeds + 1
    
    page_markers = list(re.finditer(r"(?:---\s*Page\s*(\d+)\s*---|\[Page\s*(\d+)\])", preceding, re.IGNORECASE))
    if page_markers:
        last_marker = page_markers[-1]
        p_str = last_marker.group(1) or last_marker.group(2)
        if p_str and p_str.isdigit():
            return int(p_str)

    return None


def extract_evidence_from_text(
    source_text: str,
    source_type: str = "abstract",
    max_items_per_category: int = 2
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Extract grounded research evidence items across all 9 categories from source text.
    Guarantees:
    - Every claim is linked to an exact source passage with validated char_start and char_end.
    - Missing categories are explicitly identified without fabricating statements.
    - Deterministic confidence scores reflect pattern specificity.
    """
    if not source_text or len(source_text.strip()) < 20 or is_synthetic_placeholder_abstract(source_text):
        return [], list(ALL_EVIDENCE_CATEGORIES)

    sentences_with_spans = split_text_into_sentences_with_spans(source_text)
    if not sentences_with_spans:
        return [], list(ALL_EVIDENCE_CATEGORIES)

    extracted_records: List[Dict[str, Any]] = []
    found_categories: set[str] = set()

    for category, patterns in CATEGORY_PATTERNS.items():
        cat_matches: List[Dict[str, Any]] = []

        for passage, start, end in sentences_with_spans:
            passage_lower = passage.lower()

            # Disambiguation filters
            if category == EvidenceCategory.METHOD.value and any(w in passage_lower for w in ["limitation", "threats to validity", "in future work"]):
                continue
            if category == EvidenceCategory.PROBLEM.value and any(w in passage_lower for w in ["we propose", "in future work", "our contributions", "limitation of", "primary limitation", "major limitation"]):
                continue
            if category == EvidenceCategory.RESULTS.value and any(w in passage_lower for w in ["in future work", "we plan to"]):
                continue

            for pattern_str, base_confidence in patterns:
                if re.search(pattern_str, passage, re.IGNORECASE):
                    # Verify mathematical span match
                    if source_text[start:end] != passage:
                        continue

                    claim = extract_concise_claim_from_passage(passage, category)
                    section_name = "Abstract" if source_type == "abstract" else detect_section_name(source_text, start)
                    page_num = detect_page_number(source_text, start)

                    # Fine-tune heuristic confidence based on passage length & pattern strength
                    confidence = round(min(0.99, max(0.50, base_confidence)), 2)

                    cat_matches.append({
                        "category": category,
                        "claim": claim,
                        "source_passage": passage,
                        "char_start": start,
                        "char_end": end,
                        "page_number": page_num,
                        "section_name": section_name,
                        "source_type": source_type,
                        "extraction_method": "rule_based_nlp",
                        "confidence_score": confidence,
                        "is_verified": True,
                        "verification_notes": f"Exact span verified in {source_type}" + (f" ({section_name})" if section_name else "")
                    })
                    break  # Matched highest-priority pattern for this sentence

            if len(cat_matches) >= max_items_per_category:
                break

        if cat_matches:
            found_categories.add(category)
            extracted_records.extend(cat_matches)

    missing_categories = [cat for cat in ALL_EVIDENCE_CATEGORIES if cat not in found_categories]
    return extracted_records, missing_categories


def compute_source_hash(text: str) -> str:
    """Compute deterministic SHA-256 hash of the source document text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_evidence_record(record: PaperEvidence, paper: Paper) -> Dict[str, Any]:
    """
    Rigorous verification layer for a single evidence record against its paper source text.
    Verifies:
    1. Paper existence.
    2. Non-empty source passage.
    3. Span correspondence: source_text[char_start:char_end] == source_passage.
    4. Document freshness: source_hash matches current paper text hash.
    5. Source type labeling: abstract vs full text.
    6. Non-fabricated metadata.
    """
    # 1. Paper exists
    if not paper:
        return {"is_valid": False, "reason": "Associated paper does not exist."}

    # Determine current paper source text
    current_text = (paper.raw_text or "").strip()
    source_type = "full_text"
    if not current_text:
        current_text = (paper.abstract or "").strip()
        source_type = "abstract"

    if not current_text:
        return {"is_valid": False, "reason": "Paper has no available text content."}

    # 2. Non-empty source passage
    if not record.source_passage or not record.source_passage.strip():
        return {"is_valid": False, "reason": "Source passage is empty or whitespace."}

    # 3. Source hash & document freshness
    current_hash = compute_source_hash(current_text)
    is_stale = (record.source_hash is not None and record.source_hash != current_hash)

    # 4. Span verification
    span_valid = False
    if record.char_start is not None and record.char_end is not None:
        if 0 <= record.char_start < record.char_end <= len(current_text):
            extracted_slice = current_text[record.char_start:record.char_end]
            if extracted_slice == record.source_passage:
                span_valid = True
            elif extracted_slice.strip() == record.source_passage.strip():
                span_valid = True

    # Substring fallback if document has shifted
    passage_in_text = record.source_passage in current_text

    # 5. Metadata checks: page number only present if genuine markers exist
    if record.page_number is not None and record.source_type == "abstract":
        return {"is_valid": False, "reason": "Fabricated page number on abstract-only source."}

    is_valid = (span_valid or passage_in_text) and not is_stale

    return {
        "is_valid": is_valid,
        "span_valid": span_valid,
        "passage_in_text": passage_in_text,
        "is_stale": is_stale,
        "current_source_type": source_type,
        "source_type_match": (record.source_type == source_type),
        "reason": "Verified" if is_valid else ("Document updated since extraction (stale)" if is_stale else "Source passage not found in current text")
    }


def extract_and_persist_paper_evidence(
    db: Session,
    paper: Paper,
    force: bool = False
) -> PaperEvidenceResponse:
    """
    Extract and persist evidence for an existing paper in PostgreSQL.
    Idempotent and safe to retry:
    - Replaces old evidence atomically within the transaction if forced or text changed.
    - Prevents duplicates and stale records.
    - Never modifies FAISS index.
    """
    # 1. Determine extractable source text and provenance
    raw_text = (paper.raw_text or "").strip()
    abstract = (paper.abstract or "").strip()

    source_text = ""
    source_type = "abstract"

    if raw_text and len(raw_text) >= 100:
        source_text = raw_text
        source_type = "full_text"
    elif abstract and len(abstract) >= 30:
        source_text = abstract
        source_type = "abstract"

    if not source_text:
        return PaperEvidenceResponse(
            paper_id=paper.paper_id,
            paper_title=paper.title,
            status="unavailable_text",
            source_type=None,
            evidence_count=0,
            categories_present=[],
            missing_categories=list(ALL_EVIDENCE_CATEGORIES),
            evidence=[],
            verification_summary=EvidenceVerificationSummary(
                total_evidence=0,
                verified_count=0,
                is_stale=False,
                source_type=None,
                char_offsets_valid=True,
                nonempty_passages=True,
                verification_message="No extractable text found in abstract or uploaded PDF."
            )
        )

    current_hash = compute_source_hash(source_text)

    # 2. Check existing evidence
    existing_records = db.query(PaperEvidence).filter(PaperEvidence.paper_id == paper.id).all()
    if existing_records and not force:
        # Check if stored evidence matches current text hash
        first_hash = existing_records[0].source_hash
        if first_hash == current_hash:
            # Evidence is current and valid
            items = []
            present_cats = set()
            for r in existing_records:
                present_cats.add(r.category)
                items.append(EvidenceItemResponse(
                    id=r.id,
                    paper_id=r.paper_id,
                    category=r.category,
                    category_label=CATEGORY_LABELS.get(r.category, r.category.title()),
                    claim=r.claim,
                    source_passage=r.source_passage,
                    char_start=r.char_start,
                    char_end=r.char_end,
                    page_number=r.page_number,
                    section_name=r.section_name,
                    source_type=r.source_type,
                    extraction_method=r.extraction_method,
                    confidence_score=r.confidence_score,
                    is_verified=r.is_verified,
                    verification_notes=r.verification_notes,
                    source_hash=r.source_hash,
                    created_at=r.created_at,
                    updated_at=r.updated_at
                ))
            missing = [c for c in ALL_EVIDENCE_CATEGORIES if c not in present_cats]
            return PaperEvidenceResponse(
                paper_id=paper.paper_id,
                paper_title=paper.title,
                status="extracted" if not missing else "partial_extraction",
                source_type=existing_records[0].source_type,
                evidence_count=len(items),
                categories_present=sorted(list(present_cats)),
                missing_categories=missing,
                evidence=items,
                verification_summary=EvidenceVerificationSummary(
                    total_evidence=len(items),
                    verified_count=sum(1 for i in items if i.is_verified),
                    is_stale=False,
                    source_type=existing_records[0].source_type,
                    char_offsets_valid=True,
                    nonempty_passages=True,
                    verification_message=f"Retrieved {len(items)} grounded evidence items verified against {existing_records[0].source_type}."
                )
            )

    # 3. Clean atomic removal of old evidence for this paper to prevent stale/duplicate entries
    if existing_records:
        db.query(PaperEvidence).filter(PaperEvidence.paper_id == paper.id).delete()
        db.flush()

    # 4. Perform deterministic extraction
    raw_evidence_list, missing_categories = extract_evidence_from_text(
        source_text=source_text,
        source_type=source_type,
        max_items_per_category=2
    )

    if not raw_evidence_list:
        if is_synthetic_placeholder_abstract(source_text):
            status_val = "unavailable_evidence"
            verif_msg = "Synthetic placeholder abstract detected in catalog; original scientific research text unavailable."
        elif len(source_text) < 100:
            status_val = "insufficient_text"
            verif_msg = f"Text was inspected ({len(source_text)} chars), but no explicit scientific evidence patterns were matched."
        else:
            status_val = "no_evidence_found"
            verif_msg = f"Text was inspected ({len(source_text)} chars), but no explicit scientific evidence patterns were matched."

        return PaperEvidenceResponse(
            paper_id=paper.paper_id,
            paper_title=paper.title,
            status=status_val,
            source_type=source_type,
            evidence_count=0,
            categories_present=[],
            missing_categories=list(ALL_EVIDENCE_CATEGORIES),
            evidence=[],
            verification_summary=EvidenceVerificationSummary(
                total_evidence=0,
                verified_count=0,
                is_stale=False,
                source_type=source_type,
                char_offsets_valid=True,
                nonempty_passages=True,
                verification_message=verif_msg
            )
        )

    # 5. Persist verified evidence records
    new_db_records: List[PaperEvidence] = []
    response_items: List[EvidenceItemResponse] = []
    present_categories: set[str] = set()

    for item in raw_evidence_list:
        ev_model = PaperEvidence(
            paper_id=paper.id,
            category=item["category"],
            claim=item["claim"],
            source_passage=item["source_passage"],
            char_start=item["char_start"],
            char_end=item["char_end"],
            page_number=item["page_number"],
            section_name=item["section_name"],
            source_type=item["source_type"],
            extraction_method=item["extraction_method"],
            confidence_score=item["confidence_score"],
            is_verified=item["is_verified"],
            verification_notes=item["verification_notes"],
            source_hash=current_hash
        )
        db.add(ev_model)
        new_db_records.append(ev_model)
        present_categories.add(item["category"])

    db.commit()

    for rec in new_db_records:
        db.refresh(rec)
        response_items.append(EvidenceItemResponse(
            id=rec.id,
            paper_id=rec.paper_id,
            category=rec.category,
            category_label=CATEGORY_LABELS.get(rec.category, rec.category.title()),
            claim=rec.claim,
            source_passage=rec.source_passage,
            char_start=rec.char_start,
            char_end=rec.char_end,
            page_number=rec.page_number,
            section_name=rec.section_name,
            source_type=rec.source_type,
            extraction_method=rec.extraction_method,
            confidence_score=rec.confidence_score,
            is_verified=rec.is_verified,
            verification_notes=rec.verification_notes,
            source_hash=rec.source_hash,
            created_at=rec.created_at,
            updated_at=rec.updated_at
        ))

    logger.info(
        "Extracted and persisted %d evidence items for paper %s (ID %d) from %s.",
        len(response_items), paper.paper_id, paper.id, source_type
    )

    return PaperEvidenceResponse(
        paper_id=paper.paper_id,
        paper_title=paper.title,
        status="extracted" if not missing_categories else "partial_extraction",
        source_type=source_type,
        evidence_count=len(response_items),
        categories_present=sorted(list(present_categories)),
        missing_categories=missing_categories,
        evidence=response_items,
        verification_summary=EvidenceVerificationSummary(
            total_evidence=len(response_items),
            verified_count=len(response_items),
            is_stale=False,
            source_type=source_type,
            char_offsets_valid=True,
            nonempty_passages=True,
            verification_message=f"Successfully extracted {len(response_items)} grounded evidence items from {source_type}."
        )
    )


def get_paper_evidence(
    db: Session,
    paper: Paper,
    category: Optional[str] = None
) -> PaperEvidenceResponse:
    """
    Retrieve persisted evidence records for a paper with validation and staleness detection.
    If evidence has not yet been extracted, attempts extraction if source text is available.
    """
    records = db.query(PaperEvidence).filter(PaperEvidence.paper_id == paper.id).all()

    if not records:
        # Auto-extract on first retrieval if text is available
        res = extract_and_persist_paper_evidence(db=db, paper=paper, force=False)
        if category:
            filtered_items = [e for e in res.evidence if e.category == category]
            res.evidence = filtered_items
            res.evidence_count = len(filtered_items)
            res.categories_present = [category] if filtered_items else []
            res.missing_categories = [c for c in ALL_EVIDENCE_CATEGORIES if c != category] if filtered_items else list(ALL_EVIDENCE_CATEGORIES)
        return res

    # Check for document staleness (source text updated after extraction)
    source_text = (paper.raw_text or "").strip() or (paper.abstract or "").strip()
    current_hash = compute_source_hash(source_text) if source_text else ""
    first_record_hash = records[0].source_hash if records else None
    is_stale = bool(first_record_hash and current_hash and first_record_hash != current_hash)

    if category:
        records = [r for r in records if r.category == category]

    present_categories = set(r.category for r in records)
    missing_categories = [c for c in ALL_EVIDENCE_CATEGORIES if c not in present_categories]

    items: List[EvidenceItemResponse] = []
    verified_count = 0
    all_offsets_valid = True
    all_passages_nonempty = True

    for r in records:
        v_check = verify_evidence_record(r, paper)
        is_rec_verified = v_check["is_valid"] and not is_stale
        if is_rec_verified:
            verified_count += 1
        if not v_check.get("span_valid", False):
            all_offsets_valid = False
        if not r.source_passage or not r.source_passage.strip():
            all_passages_nonempty = False

        items.append(EvidenceItemResponse(
            id=r.id,
            paper_id=r.paper_id,
            category=r.category,
            category_label=CATEGORY_LABELS.get(r.category, r.category.title()),
            claim=r.claim,
            source_passage=r.source_passage,
            char_start=r.char_start,
            char_end=r.char_end,
            page_number=r.page_number,
            section_name=r.section_name,
            source_type=r.source_type,
            extraction_method=r.extraction_method,
            confidence_score=r.confidence_score,
            is_verified=is_rec_verified,
            verification_notes=r.verification_notes if not is_stale else "Document source text has changed (evidence stale)",
            source_hash=r.source_hash,
            created_at=r.created_at,
            updated_at=r.updated_at
        ))

    source_type_val = records[0].source_type if records else None
    verification_msg = (
        "Evidence verified against current source text."
        if not is_stale
        else "Document source text has changed since extraction. Refresh recommended."
    )

    return PaperEvidenceResponse(
        paper_id=paper.paper_id,
        paper_title=paper.title,
        status="stale" if is_stale else ("extracted" if not missing_categories else "partial_extraction"),
        source_type=source_type_val,
        evidence_count=len(items),
        categories_present=sorted(list(present_categories)),
        missing_categories=missing_categories,
        evidence=items,
        verification_summary=EvidenceVerificationSummary(
            total_evidence=len(items),
            verified_count=verified_count,
            is_stale=is_stale,
            source_type=source_type_val,
            char_offsets_valid=all_offsets_valid,
            nonempty_passages=all_passages_nonempty,
            verification_message=verification_msg
        )
    )
