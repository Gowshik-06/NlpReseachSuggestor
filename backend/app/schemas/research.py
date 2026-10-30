"""
Pydantic schemas for Research Evolution, Paper Relationship Graph, and Candidate Gap Explorer.
Enforces rigorous truthfulness, provenance tracking, and explicit uncertainty disclosures.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class EvolutionStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL_COVERAGE = "partial_coverage"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    EMPTY = "empty"


class GapConfidence(str, Enum):
    STRONG_RECURRENCE = "strong_recurrence"
    MODERATE_PATTERN = "moderate_pattern"
    PRELIMINARY_HYPOTHESIS = "preliminary_hypothesis"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class RelationshipStatus(str, Enum):
    AUTHOR_STATED = "author_stated"
    INFERRED_EVIDENCE = "inferred_evidence"
    THEMATIC_ONLY = "thematic_only"


# ==============================================================================
# 1. Research Evolution Timeline Schemas
# ==============================================================================

class TimelineEvidenceClaim(BaseModel):
    category: str
    claim: str
    source_passage: str
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    section_name: Optional[str] = None
    confidence_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class RelatedPaperLink(BaseModel):
    target_paper_id: int
    target_paper_title: str
    relationship_type: str
    relationship_status: str  # author_stated, inferred_evidence, thematic_only
    is_author_stated: bool = False
    evidence_quote: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TimelinePaper(BaseModel):
    id: int
    paper_id: str
    title: str
    authors: List[str] = []
    venue: Optional[str] = None
    year: Optional[int] = None
    is_undated: bool = False
    date_uncertainty_note: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    problem_claims: List[TimelineEvidenceClaim] = []
    objective_claims: List[TimelineEvidenceClaim] = []
    method_changes: List[TimelineEvidenceClaim] = []
    dataset_claims: List[TimelineEvidenceClaim] = []
    metric_claims: List[TimelineEvidenceClaim] = []
    findings_claims: List[TimelineEvidenceClaim] = []
    limitation_claims: List[TimelineEvidenceClaim] = []
    future_work_claims: List[TimelineEvidenceClaim] = []
    related_links: List[RelatedPaperLink] = []
    provenance_source: str = "abstract"  # abstract, full_text, or metadata_only

    model_config = ConfigDict(from_attributes=True)


class TimelineYearGroup(BaseModel):
    year: Optional[int] = None
    year_label: str  # e.g., "2023" or "Undated / Uncertain Year"
    paper_count: int
    papers: List[TimelinePaper]
    key_themes: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class TimelineResponse(BaseModel):
    topic: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    total_papers_examined: int
    total_dated_papers: int
    total_undated_papers: int
    status: EvolutionStatus
    timeline: List[TimelineYearGroup]
    disclaimer: str = (
        "Chronological ordering reflects publication years recorded in the catalog, not ingestion order. "
        "Chronological succession does not establish causal lineage or global scientific priority. "
        "All claims are linked to verified source passages."
    )
    coverage_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 2. Research Relationship Graph Schemas
# ==============================================================================

class GraphNode(BaseModel):
    id: int
    paper_id: str
    label: str  # title
    year: Optional[int] = None
    is_undated: bool = False
    venue: Optional[str] = None
    authors: List[str] = []
    citation_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class GraphEdge(BaseModel):
    source: int
    target: int
    source_paper_id: str
    target_paper_id: str
    source_title: str
    target_title: str
    relationship_type: str  # Extension, Improvement, Challenge, Reproduction, Alternative, Potential Replacement, Thematic Similarity
    relationship_status: RelationshipStatus
    is_author_stated: bool = False
    confidence_score: float
    evidence_strength: str  # strong_evidence, moderate_evidence, tentative, insufficient_evidence
    evidence_passage: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    section_name: Optional[str] = None
    semantic_similarity: float
    explanation: str
    comparability_notes: Optional[str] = None
    uncertainty_warning: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RelationshipGraphResponse(BaseModel):
    topic: Optional[str] = None
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    total_nodes: int
    total_edges: int
    edge_type_counts: Dict[str, int] = {}
    status: EvolutionStatus
    disclaimer: str = (
        "Semantic similarity does NOT imply citation, influence, or scientific agreement. "
        "Edges strictly distinguish explicit author statements from system-generated candidate relationships. "
        "No artificial citation links are generated."
    )
    coverage_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 3. Candidate Research-Gap Explorer Schemas
# ==============================================================================

class GapEvidenceItem(BaseModel):
    paper_id: int
    paper_code: str
    paper_title: str
    year: Optional[int] = None
    quote: str
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    section_name: Optional[str] = None
    category: str = "limitation"
    context_note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CandidateGap(BaseModel):
    gap_id: str
    gap_type: str  # recurring_limitation, recurring_future_work, cross_dataset_method_gap, underrepresented_evaluation, conflicting_findings, corpus_coverage_gap
    title: str
    concise_hypothesis: str
    evidence_strength: GapConfidence
    confidence_score: float
    is_corpus_coverage_gap: bool = False
    motivating_evidence: List[GapEvidenceItem] = []
    contradicting_evidence: List[GapEvidenceItem] = []
    relevant_papers_examined: int
    corpus_scope: str
    time_range: Optional[str] = None
    limitations: str
    recommended_verification_steps: List[str] = []
    human_validation_required: bool = True

    model_config = ConfigDict(from_attributes=True)


class GapExplorationRequest(BaseModel):
    topic: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    min_corpus_size: int = Field(default=3, ge=1, le=50)
    max_gaps: int = Field(default=15, ge=1, le=50)


class GapExplorationResponse(BaseModel):
    topic: Optional[str] = None
    total_papers_examined: int
    total_gaps_found: int
    status: EvolutionStatus
    candidate_gaps: List[CandidateGap]
    corpus_summary: Dict[str, Any] = {}
    truthfulness_disclosure: str = (
        "DISCLOSURE: Gaps identified are candidate hypotheses grounded strictly in ResearchLens's local catalog. "
        "An absence of papers or methods in this catalog does NOT imply novelty or global research absence. "
        "Human review and comprehensive external literature search are required before pursuing any hypothesis."
    )
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    ai_fallback_occurred: bool = False

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 4. Grounded Research Assistant Schemas (TASK-17)
# ==============================================================================

class AssistantStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AssistantEvidenceItem(BaseModel):
    evidence_id: str  # e.g. "ev-1", "ev-2"
    paper_id: int  # Database integer ID
    paper_code: str  # e.g. "arxiv:2106.08254v2"
    paper_title: str
    authors: List[str] = []
    year: Optional[int] = None
    venue: Optional[str] = None
    source_passage: str
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    section_name: Optional[str] = None
    source_type: str = "abstract"  # "abstract" vs "full_text"
    category: str = "method"  # method, problem, dataset, metrics, results, limitations, future_work
    confidence_score: Optional[float] = None
    url: Optional[str] = None
    doi: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AssistantClaim(BaseModel):
    claim_id: str  # e.g. "claim-1"
    claim_text: str
    supporting_evidence_ids: List[str]  # e.g. ["ev-1", "ev-2"]
    category: Optional[str] = None
    confidence: float = 0.85
    is_verified: bool = True

    model_config = ConfigDict(from_attributes=True)


class ResearchAssistantRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    paper_ids: Optional[List[str]] = Field(default=None, max_length=20)
    topic: Optional[str] = Field(default=None, max_length=200)
    max_evidence_items: int = Field(default=8, ge=1, le=25)
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Optional prior conversational turns to maintain contextual continuity"
    )


class ResearchAssistantResponse(BaseModel):
    question: str
    answer: str
    status: AssistantStatus
    evidence: List[AssistantEvidenceItem]
    claims: List[AssistantClaim]
    limitations: List[str] = []
    corpus_scope: str
    follow_up_questions: List[str] = []
    truthfulness_disclosure: str = (
        "DISCLOSURE: Every answer claim is deterministically grounded in verified passages "
        "from the local catalog. Citations and offsets correspond to exact stored text. "
        "No statements or quotations are fabricated."
    )
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    ai_fallback_occurred: bool = False
    ai_latency_ms: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

