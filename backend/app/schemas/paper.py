"""
Pydantic schemas for research paper APIs, search, recommendations, comparison, and DRIUT.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from urllib.parse import urlparse
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class PaperBase(BaseModel):
    paper_id: str
    title: str
    abstract: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    venue: Optional[str] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    source: str = "local"
    citation_count: int = 0
    categories: List[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Paper title cannot be empty.")
        if len(v) > 1000:
            raise ValueError("Paper title exceeds maximum allowed length of 1000 characters.")
        return v

    @field_validator("paper_id")
    @classmethod
    def validate_paper_id(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("paper_id cannot be empty.")
        if any(c in v for c in "\x00\r\n"):
            raise ValueError("paper_id cannot contain control characters.")
        if len(v) > 120:
            return v[:120]
        return v

    @field_validator("url", "pdf_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        parsed = urlparse(v)
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError(f"Unsafe URL scheme '{parsed.scheme}'. Only http and https are allowed.")
        return v

    @field_validator("abstract")
    @classmethod
    def validate_abstract(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if len(v) > 50000:
            return v[:50000]
        return v

    @field_validator("authors")
    @classmethod
    def validate_authors(cls, v: List[str]) -> List[str]:
        if not v:
            return []
        cleaned = [a.strip()[:200] for a in v if isinstance(a, str) and a.strip()]
        return cleaned[:50]

    @field_validator("doi")
    @classmethod
    def validate_doi(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 255:
            return v[:255]
        return v

    @field_validator("venue")
    @classmethod
    def validate_venue(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 255:
            return v[:255]
        return v


class PaperResponse(PaperBase):
    id: Optional[int] = None
    similarity_score: Optional[float] = None
    explanation: Optional[str] = None
    created_at: Optional[datetime] = None
    candidate_type: Optional[str] = None  # "catalog" or "transient"

    @model_validator(mode="after")
    def set_candidate_type(self) -> "PaperResponse":
        if self.candidate_type is None:
            self.candidate_type = "catalog" if self.id is not None else "transient"
        return self

    model_config = ConfigDict(from_attributes=True)


class SearchQueryRequest(BaseModel):
    query: str
    mode: str = "text"  # "text", "abstract", "keywords", "pdf"
    limit: int = 10
    sources: Optional[List[str]] = Field(
        default=None,
        description="Optional list of provenance filters: 'arxiv', 'pubmed', 'csir', 'local', etc. If omitted or empty, all matching catalog papers are returned."
    )
    enable_external_discovery: bool = Field(
        default=False,
        description="Explicitly query external academic APIs beyond local catalog. False by default."
    )
    sort_by: str = "relevance"  # "relevance" (cosine similarity / SPECTER2), "recency" (latest publication year first), "citations"
    min_year: Optional[int] = None
    max_year: Optional[int] = None
    min_citations: Optional[int] = None


class SearchResponse(BaseModel):
    query: str
    mode: str
    total_found: int
    results: List[PaperResponse]
    detected_keywords: List[str] = Field(default_factory=list)
    execution_time_seconds: float


class CompareRequest(BaseModel):
    paper_ids: Optional[List[Union[int, str]]] = Field(
        default=None,
        description="List of integer database IDs or string paper_ids to compare"
    )
    candidates: Optional[List[PaperBase]] = Field(
        default=None,
        description="List of transient external candidates to compare"
    )
    items: Optional[List[Union[int, str, PaperBase, Dict[str, Any]]]] = Field(
        default=None,
        description="Mixed list of IDs or candidate objects"
    )

    @model_validator(mode="after")
    def validate_comparison_counts(self) -> "CompareRequest":
        total_count = 0
        if self.paper_ids:
            total_count += len(self.paper_ids)
        if self.candidates:
            total_count += len(self.candidates)
        if self.items:
            total_count += len(self.items)

        if total_count < 2:
            raise ValueError("Please provide at least 2 papers or paper identifiers to compare.")
        if total_count > 12:
            raise ValueError("Comparison limit exceeded: maximum 12 papers allowed per comparison.")
        return self


class ComparisonCell(BaseModel):
    paper_id: str
    paper_title: str
    dimension_key: str
    dimension_label: str
    has_evidence: bool
    claim: Optional[str] = None
    source_passage: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    page_number: Optional[int] = None
    section_name: Optional[str] = None
    source_type: Optional[str] = None  # "full_text", "abstract", "metadata"
    confidence_score: Optional[float] = None
    status: str = "supported"  # "supported", "missing_evidence", "stale", "insufficient_text", "metadata_only", "untracked"
    status_note: Optional[str] = None


class ComparisonDimensionDetail(BaseModel):
    dimension_id: str
    dimension_title: str
    category: str  # "scientific_evidence", "publication_metadata", "evidence_provenance"
    cells: Dict[str, ComparisonCell]  # keyed by paper_id
    summary: Optional[str] = None
    comparability_status: str = "comparable"  # "comparable", "incomparable_protocols", "partial_evidence", "insufficient_evidence"
    comparability_note: Optional[str] = None


class PaperCoverageSummary(BaseModel):
    paper_id: str
    title: str
    source_type: str  # "full_text", "abstract", "unavailable"
    evidence_count: int
    categories_present: List[str]
    missing_categories: List[str]
    coverage_percentage: float
    coverage_level: str  # "Comprehensive (Full Text)", "Partial (Abstract Only)", "Minimal / Incomplete"
    is_stale: bool
    source_quality_warning: Optional[str] = None


class SupportedInsight(BaseModel):
    dimension: str
    insight_type: str  # "similarity" or "difference"
    statement: str
    involved_paper_ids: List[str]
    evidence_grounding: List[str] = Field(default_factory=list)
    caveat: Optional[str] = None


class IncomparableDimensionDetail(BaseModel):
    dimension: str
    reason: str
    affected_papers: List[str]


class PaperComparisonPoint(BaseModel):
    dimension: str
    values: Dict[str, str]  # paper_id / title -> description


class ComparisonStatistics(BaseModel):
    papers_compared: int
    year_distribution: Dict[str, int] = Field(default_factory=dict)
    methodology_distribution: Dict[str, int] = Field(default_factory=dict)
    dataset_distribution: Dict[str, int] = Field(default_factory=dict)
    model_distribution: Dict[str, int] = Field(default_factory=dict)
    shared_themes: List[str] = Field(default_factory=list)
    unique_approaches: List[Dict[str, str]] = Field(default_factory=list)
    common_limitations: List[str] = Field(default_factory=list)
    research_gaps: List[str] = Field(default_factory=list)
    has_sufficient_data: bool = True
    data_sufficiency_note: Optional[str] = None


class CompareResponse(BaseModel):
    papers: List[PaperResponse]
    comparison_points: List[PaperComparisonPoint]
    executive_summary: str
    dimensions: List[ComparisonDimensionDetail] = Field(default_factory=list)
    coverage_summary: List[PaperCoverageSummary] = Field(default_factory=list)
    supported_similarities: List[SupportedInsight] = Field(default_factory=list)
    supported_differences: List[SupportedInsight] = Field(default_factory=list)
    incomparable_dimensions: List[IncomparableDimensionDetail] = Field(default_factory=list)
    statistics: Optional[ComparisonStatistics] = None
    warnings: List[str] = Field(default_factory=list)
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    ai_fallback_occurred: bool = False


class SummaryResponse(BaseModel):
    paper_id: str
    title: str
    executive_summary: str
    problem_statement: str
    methodology: str
    key_findings: str
    limitations: str
    suggested_reading_order: List[str] = Field(default_factory=list)
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    ai_fallback_occurred: bool = False


class SavePaperRequest(BaseModel):
    paper_id: Optional[Union[int, str]] = None
    candidate: Optional[PaperBase] = None
    notes: Optional[str] = ""
    tags: List[str] = Field(default_factory=list)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> str:
        if v is None:
            return ""
        v = v.strip()
        if len(v) > 5000:
            raise ValueError("Notes cannot exceed 5000 characters.")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        if not v:
            return []
        if len(v) > 30:
            raise ValueError("Cannot specify more than 30 tags.")
        cleaned = [t.strip()[:50] for t in v if isinstance(t, str) and t.strip()]
        return cleaned

    @model_validator(mode="after")
    def validate_identifier_or_candidate(self) -> "SavePaperRequest":
        if self.paper_id is None and self.candidate is None:
            raise ValueError("Either paper_id or candidate payload must be provided to save paper.")
        return self


class PaperSummaryRequest(BaseModel):
    paper_id: Optional[Union[int, str]] = None
    candidate: Optional[PaperBase] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    venue: Optional[str] = None
    year: Optional[int] = None
    source: Optional[str] = "external"
    citation_count: int = 0


class TransientEvidenceRequest(BaseModel):
    paper_id: Optional[Union[int, str]] = None
    candidate: Optional[PaperBase] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    raw_text: Optional[str] = None
    source: Optional[str] = "external"
    category: Optional[str] = None


class SavedPaperResponse(BaseModel):
    id: int
    paper_id: int
    user_id: str
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    saved_at: datetime
    paper: PaperResponse

    model_config = ConfigDict(from_attributes=True)


class DRIUTClassificationResult(BaseModel):
    candidate_paper_id: str
    candidate_title: str
    saved_paper_id: str
    saved_title: str
    relationship_type: Optional[str] = None  # Extension, Improvement, Challenge, Reproduction, Alternative, Potential Replacement
    confidence_score: float = 0.0
    evidence_strength: str = "insufficient_evidence"  # strong_evidence, partial_evidence, tentative, insufficient_evidence
    explanation: str = ""
    evidence_passage: Optional[str] = None
    saved_evidence_passage: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    section_name: Optional[str] = None
    source_type: str = "abstract"  # abstract, full_text
    semantic_similarity: float = 0.0
    comparability_notes: Optional[str] = None
    uncertainty_warning: Optional[str] = None
    classification_version: str = "v2.0-evidence-grounded"
    is_supported: bool = False


class DRIUTAlertResponse(BaseModel):
    id: int
    user_id: str
    saved_paper_id: int
    trigger_paper_id: int
    relationship_type: str  # Extension, Improvement, Challenge, Reproduction, Alternative, Potential Replacement
    confidence_score: float
    explanation: str
    is_read: bool
    created_at: datetime
    saved_paper: PaperResponse
    trigger_paper: PaperResponse
    evidence_strength: Optional[str] = "tentative"
    evidence_passage: Optional[str] = None
    saved_evidence_passage: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    section_name: Optional[str] = None
    source_type: Optional[str] = "abstract"
    semantic_similarity: Optional[float] = None
    comparability_notes: Optional[str] = None
    uncertainty_warning: Optional[str] = None
    classification_version: Optional[str] = "v2.0-evidence-grounded"

    model_config = ConfigDict(from_attributes=True)


class DRIUTScanResponse(BaseModel):
    message: str
    new_alerts_count: int
    alerts: List[DRIUTAlertResponse]


class DRIUTStatusResponse(BaseModel):
    is_enabled: bool
    is_running_scan: bool
    interval_minutes: int
    last_run_time: Optional[datetime] = None
    last_run_duration_seconds: Optional[float] = None
    last_run_status: str
    total_scans_completed: int
    last_scan_metrics: Dict[str, Any] = Field(default_factory=dict)
    provider_status: Dict[str, str] = Field(default_factory=dict)
    provider_errors: Dict[str, str] = Field(default_factory=dict)


# ============================================================================
# TASK N2 — PDF Preview & Explicit Catalog Ingestion Schemas
# ============================================================================

class DuplicateMatchDetail(BaseModel):
    is_duplicate: bool = False
    match_type: Optional[str] = None  # "exact_doi", "exact_title", "high_title_similarity", "exact_paper_id"
    matched_paper_id: Optional[str] = None
    matched_catalog_id: Optional[int] = None
    matched_title: Optional[str] = None
    similarity_score: Optional[float] = None
    explanation: Optional[str] = None


class ExtractedMetadata(BaseModel):
    title: str
    abstract: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    venue: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)


class PdfPreviewResponse(BaseModel):
    filename: str
    status: str = "preview_ready"  # "preview_ready", "duplicate", "insufficient_text", "failed"
    extracted_metadata: ExtractedMetadata
    page_count: int
    raw_text_preview: str = ""
    raw_text_length: int = 0
    duplicate_check: DuplicateMatchDetail = Field(default_factory=DuplicateMatchDetail)
    allow_ingest: bool = True
    recommendations: List[PaperResponse] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class PdfIngestRequest(BaseModel):
    confirm_ingest: bool = False
    title: str
    abstract: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    venue: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    filename: Optional[str] = None
    add_to_library: bool = False

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Manuscript title cannot be empty.")
        if len(v) > 1000:
            raise ValueError("Manuscript title exceeds maximum allowed length of 1000 characters.")
        return v

    @field_validator("abstract")
    @classmethod
    def validate_abstract(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if len(v) > 50000:
            return v[:50000]
        return v


class PdfIngestResponse(BaseModel):
    status: str  # "success", "partial_success_faiss_pending", "duplicate", "failed"
    paper_id: str
    catalog_id: int
    title: str
    message: str
    faiss_indexed: bool
    duplicate_detected: bool = False
    saved_to_library: bool = False

