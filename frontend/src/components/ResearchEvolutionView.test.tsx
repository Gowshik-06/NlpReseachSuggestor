import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import ResearchEvolutionView from "./ResearchEvolutionView";
import * as api from "../services/api";
import type {
  TimelineResponse,
  RelationshipGraphResponse,
  GapExplorationResponse,
} from "../types/research";

const mockTimelineResponse: TimelineResponse = {
  topic: "Transformers",
  start_year: 2018,
  end_year: 2022,
  total_papers_examined: 2,
  total_dated_papers: 1,
  total_undated_papers: 1,
  status: "complete",
  timeline: [
    {
      year: 2018,
      year_label: "2018",
      paper_count: 1,
      papers: [
        {
          id: 1,
          paper_id: "paper:bert:2018",
          title: "BERT: Pre-training of Deep Bidirectional Transformers",
          authors: ["Jacob Devlin", "Ming-Wei Chang"],
          venue: "NAACL 2019",
          year: 2018,
          is_undated: false,
          problem_claims: [
            {
              category: "problem",
              claim: "Unidirectional language models limit pre-training representations.",
              source_passage: "Current techniques restrict the power of pre-trained representations.",
              char_start: 0,
              char_end: 67,
              section_name: "Abstract",
            },
          ],
          objective_claims: [],
          method_changes: [
            {
              category: "method",
              claim: "We propose masked language models with bidirectional context.",
              source_passage: "We introduce BERT using a masked language model objective.",
              char_start: 68,
              char_end: 126,
              section_name: "Abstract",
            },
          ],
          dataset_claims: [],
          metric_claims: [],
          findings_claims: [
            {
              category: "results",
              claim: "Substantial empirical improvements across GLUE tasks.",
              source_passage: "BERT advances state-of-the-art performance on eleven NLP tasks.",
              char_start: 127,
              char_end: 191,
              section_name: "Abstract",
            },
          ],
          limitation_claims: [
            {
              category: "limitations",
              claim: "High computational overhead during pre-training.",
              source_passage: "Pre-training requires substantial computational resources and TPU clusters.",
              char_start: 192,
              char_end: 267,
              section_name: "Abstract",
            },
          ],
          future_work_claims: [
            {
              category: "future_work",
              claim: "Extend to cross-lingual and edge devices.",
              source_passage: "In future work we plan to explore edge compression.",
              char_start: 268,
              char_end: 320,
              section_name: "Abstract",
            },
          ],
          related_links: [
            {
              target_paper_id: 2,
              target_paper_title: "Undated Attention Study",
              relationship_type: "Thematic Similarity",
              relationship_status: "thematic_only",
              is_author_stated: false,
            },
          ],
          provenance_source: "abstract",
        },
      ],
      key_themes: ["bidirectional", "masked"],
    },
    {
      year: null,
      year_label: "Undated / Uncertain Year",
      paper_count: 1,
      papers: [
        {
          id: 2,
          paper_id: "paper:undated:study",
          title: "Undated Attention Study",
          authors: ["Anonymous"],
          venue: "Workshop",
          year: null,
          is_undated: true,
          date_uncertainty_note: "Publication year unrecorded in catalog metadata.",
          problem_claims: [],
          objective_claims: [],
          method_changes: [],
          dataset_claims: [],
          metric_claims: [],
          findings_claims: [],
          limitation_claims: [],
          future_work_claims: [],
          related_links: [],
          provenance_source: "abstract",
        },
      ],
      key_themes: ["Uncertain Date"],
    },
  ],
  disclaimer: "Chronological sequence represents catalog publication dates, not causal lineage.",
  coverage_notes: "1 of 2 papers has uncertain publication date.",
};

const mockGraphResponse: RelationshipGraphResponse = {
  topic: "BERT",
  total_nodes: 2,
  total_edges: 1,
  edge_type_counts: { Extension: 1 },
  status: "complete",
  disclaimer: "Semantic similarity does not imply citation or scientific agreement.",
  nodes: [
    {
      id: 1,
      paper_id: "p1",
      label: "BERT: Pre-training",
      year: 2018,
      is_undated: false,
      venue: "NAACL",
      authors: ["Devlin"],
      citation_count: 80000,
    },
    {
      id: 2,
      paper_id: "p2",
      label: "RoBERTa: Robustly Optimized BERT",
      year: 2020,
      is_undated: false,
      venue: "arXiv",
      authors: ["Liu"],
      citation_count: 20000,
    },
  ],
  edges: [
    {
      source: 2,
      target: 1,
      source_paper_id: "p2",
      target_paper_id: "p1",
      source_title: "RoBERTa: Robustly Optimized BERT",
      target_title: "BERT: Pre-training",
      relationship_type: "Extension",
      relationship_status: "author_stated",
      is_author_stated: true,
      confidence_score: 0.95,
      evidence_strength: "strong_evidence",
      evidence_passage: "We extend BERT by training with larger batch sizes and more data.",
      char_start: 45,
      char_end: 112,
      section_name: "Abstract",
      semantic_similarity: 0.88,
      explanation: "RoBERTa explicitly builds upon the BERT pre-training architecture.",
    },
  ],
};

const mockGapResponse: GapExplorationResponse = {
  topic: "Transformers",
  total_papers_examined: 5,
  total_gaps_found: 2,
  status: "complete",
  candidate_gaps: [
    {
      gap_id: "gap-1",
      gap_type: "recurring_limitation",
      title: "Recurring Limitation: Prohibitive Computational Cost",
      concise_hypothesis: "Multiple studies report extreme GPU memory overhead during training.",
      evidence_strength: "strong_recurrence",
      confidence_score: 0.88,
      is_corpus_coverage_gap: false,
      motivating_evidence: [
        {
          paper_id: 1,
          paper_code: "p1",
          paper_title: "BERT: Pre-training",
          year: 2018,
          quote: "Pre-training requires 64 TPU chips for four days.",
          char_start: 10,
          char_end: 58,
          section_name: "Abstract",
          category: "limitations",
        },
      ],
      contradicting_evidence: [],
      relevant_papers_examined: 2,
      corpus_scope: "Local ResearchLens catalog: 'Transformers', N=5 papers examined",
      time_range: "2018 - 2022",
      limitations: "Derived from local catalog abstracts; external works may have proposed optimizations.",
      recommended_verification_steps: [
        "Search arXiv for recent parameter-efficient fine-tuning papers.",
        "Benchmark memory scaling curves across sequence lengths.",
      ],
      human_validation_required: true,
    },
    {
      gap_id: "gap-2",
      gap_type: "corpus_coverage_gap",
      title: "Local Catalog Boundary vs. Global Frontier",
      concise_hypothesis: "This analysis examined 5 papers currently cataloged in ResearchLens. Missing topics reflect catalog sampling, NOT worldwide research novelty.",
      evidence_strength: "preliminary_hypothesis",
      confidence_score: 0.99,
      is_corpus_coverage_gap: true,
      motivating_evidence: [],
      contradicting_evidence: [],
      relevant_papers_examined: 5,
      corpus_scope: "Local ResearchLens catalog: 'Transformers', N=5 papers",
      time_range: "2018 - 2022",
      limitations: "Local sample boundary.",
      recommended_verification_steps: ["Conduct comprehensive external literature review."],
      human_validation_required: true,
    },
  ],
  corpus_summary: { examined_papers_count: 5 },
  truthfulness_disclosure: "DISCLOSURE: Gaps identified are candidate hypotheses grounded strictly in local catalog.",
};

describe("ResearchEvolutionView Frontend Component", () => {
  beforeEach(() => {
    vi.spyOn(api, "getResearchTimeline").mockResolvedValue(mockTimelineResponse);
    vi.spyOn(api, "getRelationshipGraph").mockResolvedValue(mockGraphResponse);
    vi.spyOn(api, "postCandidateGaps").mockResolvedValue(mockGapResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders timeline view with chronological groups and undated paper isolation", async () => {
    render(<ResearchEvolutionView initialTopic="Transformers" />);

    expect(screen.getByText(/Research Evolution & Gap Explorer/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("2018")).toBeInTheDocument();
      expect(screen.getByText("Undated / Uncertain Year")).toBeInTheDocument();
      expect(screen.getByText("BERT: Pre-training of Deep Bidirectional Transformers")).toBeInTheDocument();
      expect(screen.getByText("Undated Attention Study")).toBeInTheDocument();
    });

    // Check undated label
    expect(screen.getByText(/Undated in catalog/i)).toBeInTheDocument();
    // Check disclaimer
    expect(screen.getByText(/Chronological sequence represents catalog publication dates/i)).toBeInTheDocument();
  });

  it("expands and inspects supporting evidence passages", async () => {
    render(<ResearchEvolutionView initialTopic="Transformers" />);

    await waitFor(() => {
      expect(screen.getByText("BERT: Pre-training of Deep Bidirectional Transformers")).toBeInTheDocument();
    });

    const expandBtns = screen.getAllByText(/Inspect exact supporting source passages/i);
    fireEvent.click(expandBtns[0]);

    await waitFor(() => {
      expect(screen.getByText(/Verified Source Passages:/i)).toBeInTheDocument();
      expect(screen.getByText(/"Pre-training requires substantial computational resources and TPU clusters."/i)).toBeInTheDocument();
    });
  });

  it("switches to Relationship Graph tab and displays inter-paper edges with provenance", async () => {
    render(<ResearchEvolutionView initialTopic="Transformers" />);

    const graphTabBtn = screen.getByText(/Relationship Graph/i);
    fireEvent.click(graphTabBtn);

    await waitFor(() => {
      expect(api.getRelationshipGraph).toHaveBeenCalled();
      expect(screen.getByText("RoBERTa: Robustly Optimized BERT")).toBeInTheDocument();
      expect(screen.getByText("Explicit Author Statement")).toBeInTheDocument();
      expect(screen.getByText(/"We extend BERT by training with larger batch sizes and more data."/i)).toBeInTheDocument();
    });

    // Toggle to matrix view mode
    const matrixBtn = screen.getByText(/🌐 Graph Matrix/i);
    fireEvent.click(matrixBtn);

    expect(screen.getByText(/Inter-Paper Relationship Connectivity Matrix/i)).toBeInTheDocument();
  });

  it("switches to Gap Discovery tab and displays candidate gaps and truthfulness disclosures", async () => {
    render(<ResearchEvolutionView initialTopic="Transformers" />);

    const gapTabBtn = screen.getByText(/Gap Discovery/i);
    fireEvent.click(gapTabBtn);

    await waitFor(() => {
      expect(api.postCandidateGaps).toHaveBeenCalled();
      expect(screen.getByText(/Essential Scientific Truthfulness & Discovery Disclosure/i)).toBeInTheDocument();
      expect(screen.getByText("Recurring Limitation: Prohibitive Computational Cost")).toBeInTheDocument();
      expect(screen.getByText("LOCAL CATALOG BOUNDARY")).toBeInTheDocument();
      expect(screen.getAllByText(/Recommended Verification Steps \(Human Review\):/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Human Validation Mandated/i).length).toBeGreaterThan(0);
    });
  });

  it("handles insufficient evidence state when corpus is too sparse", async () => {
    vi.spyOn(api, "postCandidateGaps").mockResolvedValueOnce({
      topic: "Obscure",
      total_papers_examined: 1,
      total_gaps_found: 0,
      status: "insufficient_evidence",
      candidate_gaps: [],
      corpus_summary: { examined_papers_count: 1 },
      truthfulness_disclosure: "INSUFFICIENT EVIDENCE: Only 1 paper found in selected corpus.",
    });

    render(<ResearchEvolutionView initialTopic="Obscure" />);
    fireEvent.click(screen.getByText(/Gap Discovery/i));

    await waitFor(() => {
      expect(screen.getByText(/Insufficient Catalog Evidence/i)).toBeInTheDocument();
      expect(screen.getAllByText(/INSUFFICIENT EVIDENCE: Only 1 paper found in selected corpus./i).length).toBe(2);
    });
  });

  it("handles loading and error states cleanly", async () => {
    vi.spyOn(api, "getResearchTimeline").mockRejectedValueOnce(new Error("Network connection lost"));

    render(<ResearchEvolutionView initialTopic="FailTest" />);

    await waitFor(() => {
      expect(screen.getByText(/Network connection lost/i)).toBeInTheDocument();
    });
  });

  it("switches to Assistant tab, asks question, and renders grounded answer with evidence passages", async () => {
    vi.spyOn(api, "askResearchAssistant").mockResolvedValueOnce({
      question: "What limitations are reported for these models?",
      answer: "Based on examined papers, authors report high computational cost and memory overhead during pre-training [ev-1].",
      status: "complete",
      evidence: [
        {
          evidence_id: "ev-1",
          paper_id: 1,
          paper_code: "paper:bert:2018",
          paper_title: "BERT: Pre-training of Deep Bidirectional Transformers",
          authors: ["Jacob Devlin"],
          year: 2018,
          source_passage: "A major limitation of our approach is the high computational cost and memory overhead required during pre-training.",
          char_start: 120,
          char_end: 220,
          section_name: "Abstract",
          source_type: "abstract",
          category: "limitations",
          confidence_score: 0.92,
        },
      ],
      claims: [
        {
          claim_id: "claim-1",
          claim_text: "High computational cost and memory overhead during pre-training [ev-1].",
          supporting_evidence_ids: ["ev-1"],
          confidence: 0.92,
          is_verified: true,
        },
      ],
      limitations: ["Limitations reflect explicit author statements in abstracts."],
      corpus_scope: "Local catalog search: topic 'Transformers', N=2 papers",
      follow_up_questions: ["What future-work directions do these authors propose?"],
      truthfulness_disclosure: "DISCLOSURE: Every answer claim is deterministically grounded in verified passages.",
    });

    render(<ResearchEvolutionView initialTopic="Transformers" />);

    const asstTabBtn = screen.getByText(/Assistant/i);
    fireEvent.click(asstTabBtn);

    expect(screen.getByText(/Grounded Scholarly Assistant/i)).toBeInTheDocument();
    expect(screen.getByText(/TASK-17 Evidence-Backed/i)).toBeInTheDocument();

    const input = screen.getByPlaceholderText(/Ask any question/i);
    fireEvent.change(input, { target: { value: "What limitations are reported for these models?" } });

    const submitBtn = screen.getByRole("button", { name: /Ask Assistant/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(api.askResearchAssistant).toHaveBeenCalled();
      expect(screen.getByText(/Evidence-Grounded Synthesis/i)).toBeInTheDocument();
      expect(screen.getByText(/Key Grounded Claims/i)).toBeInTheDocument();
      expect(screen.getByText(/Supporting Evidence Passages & Offsets/i)).toBeInTheDocument();
      expect(screen.getByText(/\[120:220\]/i)).toBeInTheDocument();
      expect(screen.getByText(/Scientific Disclosures & Limitations:/i)).toBeInTheDocument();
      expect(screen.getByText(/Suggested Follow-up Inquiries:/i)).toBeInTheDocument();
    });
  });
});

