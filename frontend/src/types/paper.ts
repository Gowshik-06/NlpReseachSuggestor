export interface Paper {
  id?: number | null;
  paper_id: string;
  title: string;
  abstract?: string;
  authors: string[];
  venue?: string;
  year?: number;
  doi?: string;
  url?: string;
  pdf_url?: string;
  source: string;
  citation_count: number;
  categories: string[];
  similarity_score?: number;
  explanation?: string;
  created_at?: string;
  candidate_type?: "catalog" | "transient";
}

export interface SearchQueryRequest {
  query: string;
  mode?: string;
  limit?: number;
  sources?: string[];
  enable_external_discovery?: boolean;
  sort_by?: "recency" | "relevance" | "citations";
  min_year?: number;
  max_year?: number;
  min_citations?: number;
}

export interface SearchResponse {
  query: string;
  mode: string;
  total_found: number;
  results: Paper[];
  detected_keywords: string[];
  execution_time_seconds: number;
}

export interface CompareRequest {
  paper_ids?: (number | string)[];
  candidates?: Paper[];
  items?: (number | string | Paper)[];
}

export interface SavePaperRequest {
  paper_id?: number | string;
  candidate?: Paper;
  notes?: string;
  tags?: string[];
}

export interface PaperSummaryRequest {
  paper_id?: string;
  candidate?: Paper;
  title?: string;
  abstract?: string;
  authors?: string[];
  venue?: string;
  year?: number;
  source?: string;
  citation_count?: number;
}

export interface TransientEvidenceRequest {
  paper_id?: string;
  candidate?: Paper;
  title?: string;
  abstract?: string;
  raw_text?: string;
  source?: string;
  category?: string;
}

export interface ComparisonCell {
  paper_id: string;
  paper_title: string;
  dimension_key: string;
  dimension_label: string;
  has_evidence: boolean;
  claim?: string | null;
  source_passage?: string | null;
  char_start?: number | null;
  char_end?: number | null;
  page_number?: number | null;
  section_name?: string | null;
  source_type?: string | null;
  confidence_score?: number | null;
  status: "supported" | "missing_evidence" | "stale" | "insufficient_text" | "metadata_only" | "untracked";
  status_note?: string | null;
}

export interface ComparisonDimensionDetail {
  dimension_id: string;
  dimension_title: string;
  category: "scientific_evidence" | "publication_metadata" | "evidence_provenance";
  cells: Record<string, ComparisonCell>;
  summary?: string | null;
  comparability_status: "comparable" | "incomparable_protocols" | "partial_evidence" | "insufficient_evidence";
  comparability_note?: string | null;
}

export interface PaperCoverageSummary {
  paper_id: string;
  title: string;
  source_type: string;
  evidence_count: number;
  categories_present: string[];
  missing_categories: string[];
  coverage_percentage: number;
  coverage_level: string;
  is_stale: boolean;
  source_quality_warning?: string | null;
}

export interface SupportedInsight {
  dimension: string;
  insight_type: "similarity" | "difference";
  statement: string;
  involved_paper_ids: string[];
  evidence_grounding: string[];
  caveat?: string | null;
}

export interface IncomparableDimensionDetail {
  dimension: string;
  reason: string;
  affected_papers: string[];
}

export interface PaperComparisonPoint {
  dimension: string;
  values: Record<string, string>;
}

export interface ComparisonStatistics {
  papers_compared: number;
  year_distribution: Record<string, number>;
  methodology_distribution: Record<string, number>;
  dataset_distribution: Record<string, number>;
  model_distribution: Record<string, number>;
  shared_themes: string[];
  unique_approaches: Array<{ paper_id: string; title: string; approach: string }>;
  common_limitations: string[];
  research_gaps: string[];
  has_sufficient_data: boolean;
  data_sufficiency_note?: string | null;
}

export interface CompareResponse {
  papers: Paper[];
  comparison_points: PaperComparisonPoint[];
  executive_summary: string;
  dimensions?: ComparisonDimensionDetail[];
  coverage_summary?: PaperCoverageSummary[];
  supported_similarities?: SupportedInsight[];
  supported_differences?: SupportedInsight[];
  incomparable_dimensions?: IncomparableDimensionDetail[];
  statistics?: ComparisonStatistics;
  warnings?: string[];
  ai_provider?: string;
  ai_model?: string;
  ai_fallback_occurred?: boolean;
}

export interface SummaryResponse {
  paper_id: string;
  title: string;
  executive_summary: string;
  problem_statement: string;
  methodology: string;
  key_findings: string;
  limitations: string;
  suggested_reading_order: string[];
}

export interface SavedPaper {
  id: number;
  paper_id: number;
  user_id: string;
  notes?: string;
  tags: string[];
  saved_at: string;
  paper: Paper;
}

export type DRIUTRelationshipType =
  | "Extension"
  | "Improvement"
  | "Challenge"
  | "Reproduction"
  | "Alternative"
  | "Potential Replacement";

export type DRIUTEvidenceStrength =
  | "strong_evidence"
  | "partial_evidence"
  | "tentative"
  | "insufficient_evidence";

export interface DRIUTAlert {
  id: number;
  user_id: string;
  saved_paper_id: number;
  trigger_paper_id: number;
  relationship_type: DRIUTRelationshipType;
  confidence_score: number;
  explanation: string;
  is_read: boolean;
  created_at: string;
  saved_paper: Paper;
  trigger_paper: Paper;
  evidence_strength?: DRIUTEvidenceStrength | string;
  evidence_passage?: string | null;
  saved_evidence_passage?: string | null;
  char_start?: number | null;
  char_end?: number | null;
  section_name?: string | null;
  source_type?: string | null;
  semantic_similarity?: number | null;
  comparability_notes?: string | null;
  uncertainty_warning?: string | null;
  classification_version?: string | null;
}

export interface DRIUTScanResponse {
  message: string;
  new_alerts_count: number;
  alerts: DRIUTAlert[];
}

export interface DRIUTStatus {
  is_enabled: boolean;
  is_running_scan: boolean;
  interval_minutes: number;
  last_run_time: string | null;
  last_run_duration_seconds: number | null;
  last_run_status: string;
  total_scans_completed: number;
  last_scan_metrics: {
    users_scanned?: number;
    saved_papers_monitored?: number;
    candidates_evaluated?: number;
    new_alerts_created?: number;
    execution_time_seconds?: number;
  };
  provider_status: Record<string, string>;
  provider_errors: Record<string, string>;
}

export interface PaperEvidenceItem {
  id?: number;
  paper_id: number;
  category: string;
  category_label?: string;
  claim: string;
  source_passage: string;
  char_start?: number;
  char_end?: number;
  page_number?: number;
  section_name?: string;
  source_type: "abstract" | "full_text" | "title";
  extraction_method: string;
  confidence_score?: number;
  is_verified: boolean;
  verification_notes?: string;
  source_hash?: string;
  created_at?: string;
  updated_at?: string;
}

export interface EvidenceVerificationSummary {
  total_evidence: number;
  verified_count: number;
  is_stale: boolean;
  source_type?: string;
  char_offsets_valid: boolean;
  nonempty_passages: boolean;
  verification_message: string;
}

export interface PaperEvidenceResponse {
  paper_id: string;
  paper_title: string;
  status: "extracted" | "not_extracted" | "unavailable_text" | "insufficient_text" | "partial_extraction" | "stale";
  source_type?: string;
  evidence_count: number;
  categories_present: string[];
  missing_categories: string[];
  evidence: PaperEvidenceItem[];
  verification_summary?: EvidenceVerificationSummary;
}

export interface DuplicateMatchDetail {
  is_duplicate: boolean;
  match_type?: string;
  matched_paper_id?: string;
  matched_catalog_id?: number;
  matched_title?: string;
  similarity_score?: number;
  explanation?: string;
}

export interface ExtractedMetadata {
  title: string;
  abstract?: string;
  authors: string[];
  year?: number;
  doi?: string;
  venue?: string;
  keywords: string[];
}

export interface PdfPreviewResponse {
  filename: string;
  status: string;
  extracted_metadata: ExtractedMetadata;
  page_count: number;
  raw_text_preview: string;
  raw_text_length: number;
  duplicate_check: DuplicateMatchDetail;
  allow_ingest: boolean;
  recommendations: Paper[];
  warnings: string[];
}

export interface PdfIngestRequest {
  confirm_ingest: boolean;
  title: string;
  abstract?: string;
  authors?: string[];
  year?: number;
  doi?: string;
  venue?: string;
  keywords?: string[];
  filename?: string;
  add_to_library?: boolean;
}

export interface PdfIngestResponse {
  status: string;
  paper_id: string;
  catalog_id: number;
  title: string;
  message: string;
  faiss_indexed: boolean;
  duplicate_detected: boolean;
  saved_to_library: boolean;
}


