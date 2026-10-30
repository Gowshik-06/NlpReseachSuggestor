"""
Pydantic schemas for research evidence extraction, retrieval, and verification.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class EvidenceCategory(str, Enum):
    PROBLEM = "problem"
    OBJECTIVE = "objective"
    METHOD = "method"
    DATASET = "dataset"
    METRICS = "metrics"
    RESULTS = "results"
    CONTRIBUTIONS = "contributions"
    LIMITATIONS = "limitations"
    FUTURE_WORK = "future_work"

ALL_EVIDENCE_CATEGORIES: List[str] = [e.value for e in EvidenceCategory]


CATEGORY_LABELS: Dict[str, str] = {
    "problem": "Research Problem & Motivation",
    "objective": "Research Objective / Question",
    "method": "Proposed Method / Approach",
    "dataset": "Dataset & Experimental Setup",
    "metrics": "Evaluation Metrics",
    "results": "Reported Results & Findings",
    "contributions": "Stated Contributions",
    "limitations": "Limitations & Threats to Validity",
    "future_work": "Future Work Directions",
}


class EvidenceItemResponse(BaseModel):
    id: Optional[int] = None
    paper_id: int
    category: str
    category_label: Optional[str] = None
    claim: str
    source_passage: str
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    page_number: Optional[int] = None
    section_name: Optional[str] = None
    source_type: str = "abstract"  # abstract, full_text, title
    extraction_method: str = "rule_based_nlp"
    confidence_score: Optional[float] = None
    is_verified: bool = True
    verification_notes: Optional[str] = None
    source_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EvidenceVerificationSummary(BaseModel):
    total_evidence: int = 0
    verified_count: int = 0
    is_stale: bool = False
    source_type: Optional[str] = None
    char_offsets_valid: bool = True
    nonempty_passages: bool = True
    verification_message: str = "Evidence verified against source document."


class PaperEvidenceResponse(BaseModel):
    paper_id: str
    paper_title: str
    status: str = "extracted"  # extracted, not_extracted, unavailable_text, insufficient_text, partial_extraction
    source_type: Optional[str] = None
    evidence_count: int = 0
    categories_present: List[str] = Field(default_factory=list)
    missing_categories: List[str] = Field(default_factory=list)
    evidence: List[EvidenceItemResponse] = Field(default_factory=list)
    verification_summary: Optional[EvidenceVerificationSummary] = None


class EvidenceExtractionRequest(BaseModel):
    force: bool = Field(default=False, description="Force re-extraction even if evidence already exists and text is unchanged")
