export interface TimelineEvidenceClaim {
  category: string;
  claim: string;
  source_passage: string;
  char_start?: number | null;
  char_end?: number | null;
  section_name?: string | null;
  confidence_score?: number | null;
}

export interface RelatedPaperLink {
  target_paper_id: number;
  target_paper_title: string;
  relationship_type: string;
  relationship_status: "author_stated" | "inferred_evidence" | "thematic_only";
  is_author_stated: boolean;
  evidence_quote?: string | null;
}

export interface TimelinePaper {
  id: number;
  paper_id: string;
  title: string;
  authors: string[];
  venue?: string | null;
  year?: number | null;
  is_undated: boolean;
  date_uncertainty_note?: string | null;
  doi?: string | null;
  url?: string | null;
  problem_claims: TimelineEvidenceClaim[];
  objective_claims: TimelineEvidenceClaim[];
  method_changes: TimelineEvidenceClaim[];
  dataset_claims: TimelineEvidenceClaim[];
  metric_claims: TimelineEvidenceClaim[];
  findings_claims: TimelineEvidenceClaim[];
  limitation_claims: TimelineEvidenceClaim[];
  future_work_claims: TimelineEvidenceClaim[];
  related_links: RelatedPaperLink[];
  provenance_source: "abstract" | "full_text" | "metadata_only";
}

export interface TimelineYearGroup {
  year?: number | null;
  year_label: string;
  paper_count: number;
  papers: TimelinePaper[];
  key_themes: string[];
}

export interface TimelineResponse {
  topic?: string | null;
  start_year?: number | null;
  end_year?: number | null;
  total_papers_examined: number;
  total_dated_papers: number;
  total_undated_papers: number;
  status: "complete" | "partial_coverage" | "insufficient_evidence" | "empty";
  timeline: TimelineYearGroup[];
  disclaimer: string;
  coverage_notes?: string | null;
}

export interface GraphNode {
  id: number;
  paper_id: string;
  label: string;
  year?: number | null;
  is_undated: boolean;
  venue?: string | null;
  authors: string[];
  citation_count: number;
}

export interface GraphEdge {
  source: number;
  target: number;
  source_paper_id: string;
  target_paper_id: string;
  source_title: string;
  target_title: string;
  relationship_type: string;
  relationship_status: "author_stated" | "inferred_evidence" | "thematic_only";
  is_author_stated: boolean;
  confidence_score: number;
  evidence_strength: "strong_evidence" | "moderate_evidence" | "tentative" | "insufficient_evidence";
  evidence_passage?: string | null;
  char_start?: number | null;
  char_end?: number | null;
  section_name?: string | null;
  semantic_similarity: number;
  explanation: string;
  comparability_notes?: string | null;
  uncertainty_warning?: string | null;
}

export interface RelationshipGraphResponse {
  topic?: string | null;
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
  edge_type_counts: Record<string, number>;
  status: "complete" | "partial_coverage" | "insufficient_evidence" | "empty";
  disclaimer: string;
  coverage_notes?: string | null;
}

export interface GapEvidenceItem {
  paper_id: number;
  paper_code: string;
  paper_title: string;
  year?: number | null;
  quote: string;
  char_start?: number | null;
  char_end?: number | null;
  section_name?: string | null;
  category: string;
  context_note?: string | null;
}

export interface CandidateGap {
  gap_id: string;
  gap_type: string;
  title: string;
  concise_hypothesis: string;
  evidence_strength: "strong_recurrence" | "moderate_pattern" | "preliminary_hypothesis" | "insufficient_evidence";
  confidence_score: number;
  is_corpus_coverage_gap: boolean;
  motivating_evidence: GapEvidenceItem[];
  contradicting_evidence: GapEvidenceItem[];
  relevant_papers_examined: number;
  corpus_scope: string;
  time_range?: string | null;
  limitations: string;
  recommended_verification_steps: string[];
  human_validation_required: boolean;
}

export interface GapExplorationRequest {
  topic?: string | null;
  start_year?: number | null;
  end_year?: number | null;
  min_corpus_size?: number;
  max_gaps?: number;
}

export interface GapExplorationResponse {
  topic?: string | null;
  total_papers_examined: number;
  total_gaps_found: number;
  status: "complete" | "partial_coverage" | "insufficient_evidence" | "empty";
  candidate_gaps: CandidateGap[];
  corpus_summary: Record<string, any>;
  truthfulness_disclosure: string;
}

// ============================================================================
// TASK-17: Grounded Research Assistant Types
// ============================================================================

export interface AssistantEvidenceItem {
  evidence_id: string;
  paper_id: number;
  paper_code: string;
  paper_title: string;
  authors: string[];
  year?: number | null;
  venue?: string | null;
  source_passage: string;
  char_start?: number | null;
  char_end?: number | null;
  section_name?: string | null;
  source_type: "abstract" | "full_text";
  category: string;
  confidence_score?: number | null;
  url?: string | null;
  doi?: string | null;
}

export interface AssistantClaim {
  claim_id: string;
  claim_text: string;
  supporting_evidence_ids: string[];
  category?: string | null;
  confidence: number;
  is_verified: boolean;
}

export interface ResearchAssistantRequest {
  question: string;
  paper_ids?: string[] | null;
  topic?: string | null;
  max_evidence_items?: number;
}

export interface ResearchAssistantResponse {
  question: string;
  answer: string;
  status: "complete" | "partial" | "insufficient_evidence";
  evidence: AssistantEvidenceItem[];
  claims: AssistantClaim[];
  limitations: string[];
  corpus_scope: string;
  follow_up_questions: string[];
  truthfulness_disclosure: string;
  ai_provider?: string | null;
  ai_model?: string | null;
  ai_fallback_occurred?: boolean;
  ai_latency_ms?: number | null;
}

export interface AIProviderStatus {
  ai_enabled: boolean;
  configured_mode: string;
  active_provider: string;
  ollama_available: boolean;
  ollama_model: string;
  ollama_endpoint: string;
  groq_configured: boolean;
  groq_available: boolean;
  groq_model: string;
  cloud_fallback_enabled: boolean;
  cloud_privacy_allowed: boolean;
  deterministic_fallback_active: boolean;
  timeout_seconds: number;
  max_output_tokens: number;
}

