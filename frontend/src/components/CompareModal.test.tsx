import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";
import CompareModal from "./CompareModal";
import type { Paper, CompareResponse } from "../types/paper";
import * as api from "../services/api";

const mockPaper1: Paper = {
  id: 1,
  paper_id: "test:comp.nlp.glue",
  title: "GLUEformer: Bidirectional Transformer for NLU",
  abstract: "We propose GLUEformer evaluated on the GLUE benchmark.",
  authors: ["Alice Smith", "Bob Jones"],
  venue: "ACL 2024",
  year: 2024,
  citation_count: 120,
  source: "local",
  categories: ["cs.CL"],
};

const mockPaper2: Paper = {
  id: 2,
  paper_id: "test:comp.cv.imagenet",
  title: "VisionNet: Convolutional Residual Attention for Vision",
  abstract: "We introduce VisionNet tested on ImageNet.",
  authors: ["Charlie Brown"],
  venue: "CVPR 2024",
  year: 2024,
  citation_count: 45,
  source: "local",
  categories: ["cs.CV"],
};

const mockCompareResponse: CompareResponse = {
  papers: [mockPaper1, mockPaper2],
  comparison_points: [
    {
      dimension: "Problem Addressed",
      values: {
        "test:comp.nlp.glue": "[Abstract] Computational efficiency in language representations.",
        "test:comp.cv.imagenet": "[Abstract] Spatial distortion in convolutional networks.",
      },
    },
    {
      dimension: "Proposed Architecture & Methodology",
      values: {
        "test:comp.nlp.glue": "[Abstract] We propose GLUEformer, a novel architecture for language modeling.",
        "test:comp.cv.imagenet": "[Abstract] We introduce VisionNet, a novel framework for image classification.",
      },
    },
  ],
  executive_summary:
    "Structured evidence-grounded comparative evaluation of 2 research publications across 12 dimensions.",
  coverage_summary: [
    {
      paper_id: "test:comp.nlp.glue",
      title: "GLUEformer: Bidirectional Transformer for NLU",
      source_type: "abstract",
      evidence_count: 8,
      categories_present: ["problem", "objective", "method", "dataset", "metrics", "results", "contributions", "limitations"],
      missing_categories: ["future_work"],
      coverage_percentage: 88.9,
      coverage_level: "Partial Coverage (Abstract Only)",
      is_stale: false,
      source_quality_warning:
        "Evaluated from abstract only. Full experimental setup, detailed methodology, and comprehensive limitation analysis require full-text access.",
    },
    {
      paper_id: "test:comp.cv.imagenet",
      title: "VisionNet: Convolutional Residual Attention for Vision",
      source_type: "full_text",
      evidence_count: 9,
      categories_present: ["problem", "objective", "method", "dataset", "metrics", "results", "contributions", "limitations", "future_work"],
      missing_categories: [],
      coverage_percentage: 100.0,
      coverage_level: "Comprehensive (Full Text Provenance)",
      is_stale: false,
      source_quality_warning: null,
    },
  ],
  incomparable_dimensions: [
    {
      dimension: "Reported Results & Benchmark Metrics",
      reason:
        "Direct numerical comparison is scientifically invalid: papers evaluate on disparate datasets, evaluation protocols, or metric definitions.",
      affected_papers: ["test:comp.nlp.glue", "test:comp.cv.imagenet"],
    },
  ],
  warnings: [
    "Scientific Caution: Evaluated papers report results under different experimental datasets or metrics. Direct numerical comparisons are invalid.",
  ],
  supported_similarities: [
    {
      dimension: "Publication Venue & Year",
      insight_type: "similarity",
      statement: "All compared papers were published in 2024.",
      involved_paper_ids: ["test:comp.nlp.glue", "test:comp.cv.imagenet"],
      evidence_grounding: ["test:comp.nlp.glue: Year 2024", "test:comp.cv.imagenet: Year 2024"],
    },
  ],
  supported_differences: [
    {
      dimension: "Methodology & Proposed Approach",
      insight_type: "difference",
      statement: "Papers propose distinct methodological architectures and algorithmic approaches.",
      involved_paper_ids: ["test:comp.nlp.glue", "test:comp.cv.imagenet"],
      evidence_grounding: [
        'test:comp.nlp.glue: "We propose GLUEformer, a novel architecture for language modeling."',
        'test:comp.cv.imagenet: "We introduce VisionNet, a novel framework for image classification."',
      ],
    },
  ],
  dimensions: [
    {
      dimension_id: "method",
      dimension_title: "Methodology & Proposed Approach",
      category: "scientific_evidence",
      comparability_status: "comparable",
      cells: {
        "test:comp.nlp.glue": {
          paper_id: "test:comp.nlp.glue",
          paper_title: "GLUEformer: Bidirectional Transformer for NLU",
          dimension_key: "method",
          dimension_label: "Methodology & Proposed Approach",
          has_evidence: true,
          claim: "We propose GLUEformer, a novel architecture for language modeling.",
          source_passage: "We propose GLUEformer, a novel architecture for language modeling.",
          char_start: 35,
          char_end: 105,
          source_type: "abstract",
          confidence_score: 0.95,
          status: "supported",
          status_note: "Exact passage verified in abstract",
        },
        "test:comp.cv.imagenet": {
          paper_id: "test:comp.cv.imagenet",
          paper_title: "VisionNet: Convolutional Residual Attention for Vision",
          dimension_key: "method",
          dimension_label: "Methodology & Proposed Approach",
          has_evidence: true,
          claim: "We introduce VisionNet, a novel framework for image classification.",
          source_passage: "We introduce VisionNet, a novel framework for image classification.",
          char_start: 40,
          char_end: 110,
          section_name: "Methodology",
          source_type: "full_text",
          confidence_score: 0.95,
          status: "supported",
          status_note: "Exact passage verified in full text (Methodology)",
        },
      },
    },
    {
      dimension_id: "results",
      dimension_title: "Reported Results & Benchmark Findings",
      category: "scientific_evidence",
      comparability_status: "incomparable_protocols",
      comparability_note:
        "Direct numerical comparison is scientifically invalid: papers evaluate on disparate datasets.",
      cells: {
        "test:comp.nlp.glue": {
          paper_id: "test:comp.nlp.glue",
          paper_title: "GLUEformer: Bidirectional Transformer for NLU",
          dimension_key: "results",
          dimension_label: "Reported Results & Benchmark Findings",
          has_evidence: true,
          claim: "Results show our method achieves 89.4% accuracy on GLUE.",
          source_passage: "Results show our method achieves 89.4% accuracy on GLUE.",
          char_start: 110,
          char_end: 170,
          source_type: "abstract",
          confidence_score: 0.92,
          status: "supported",
          status_note: "Verified in abstract",
        },
        "test:comp.cv.imagenet": {
          paper_id: "test:comp.cv.imagenet",
          paper_title: "VisionNet: Convolutional Residual Attention for Vision",
          dimension_key: "results",
          dimension_label: "Reported Results & Benchmark Findings",
          has_evidence: true,
          claim: "Empirical results show VisionNet achieves 84.2% top-1 accuracy on ImageNet.",
          source_passage: "Empirical results show VisionNet achieves 84.2% top-1 accuracy on ImageNet.",
          char_start: 120,
          char_end: 195,
          section_name: "Results",
          source_type: "full_text",
          confidence_score: 0.92,
          status: "supported",
          status_note: "Verified in full text (Results)",
        },
      },
    },
    {
      dimension_id: "limitations",
      dimension_title: "Limitations & Threats to Validity",
      category: "scientific_evidence",
      comparability_status: "comparable",
      cells: {
        "test:comp.nlp.glue": {
          paper_id: "test:comp.nlp.glue",
          paper_title: "GLUEformer: Bidirectional Transformer for NLU",
          dimension_key: "limitations",
          dimension_label: "Limitations & Threats to Validity",
          has_evidence: true,
          claim: "Our approach is limited by memory constraints on long sequences.",
          source_passage: "Our approach is limited by memory constraints on long sequences.",
          char_start: 180,
          char_end: 245,
          source_type: "abstract",
          confidence_score: 0.95,
          status: "supported",
          status_note: "Verified in abstract",
        },
        "test:comp.cv.imagenet": {
          paper_id: "test:comp.cv.imagenet",
          paper_title: "VisionNet: Convolutional Residual Attention for Vision",
          dimension_key: "limitations",
          dimension_label: "Limitations & Threats to Validity",
          has_evidence: false,
          claim: null,
          source_passage: null,
          source_type: "full_text",
          status: "missing_evidence",
          status_note:
            "Evidence not reported in available text. Absence of evidence does not imply the methodology lacks this capability.",
        },
      },
    },
  ],
  statistics: {
    papers_compared: 2,
    year_distribution: { "2024": 2 },
    methodology_distribution: { "Transformer & Attention": 1, "Convolutional Residual Attention": 1 },
    dataset_distribution: { "GLUE": 1, "ImageNet": 1 },
    model_distribution: { "GLUEformer": 1, "VisionNet": 1 },
    shared_themes: ["Deep Learning"],
    unique_approaches: [
      { paper_id: "test:comp.nlp.glue", title: "GLUEformer", approach: "We propose GLUEformer" }
    ],
    common_limitations: ["Limited by memory constraints"],
    research_gaps: ["Extend to multimodal"],
    has_sufficient_data: true,
  },
};

describe("CompareModal Component (TASK-14)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders loading state initially while comparing papers", () => {
    vi.spyOn(api, "comparePapers").mockReturnValue(new Promise(() => {}));

    render(
      <CompareModal
        papers={[mockPaper1, mockPaper2]}
        onClose={vi.fn()}
        onClear={vi.fn()}
      />
    );

    expect(screen.getByTestId("compare-loading-state")).toBeDefined();
    expect(screen.getByText(/Analyzing Evidence & Comparing Dimensions/i)).toBeDefined();
  });

  it("renders structured dimensions, executive synthesis, and coverage badges upon load", async () => {
    vi.spyOn(api, "comparePapers").mockResolvedValue(mockCompareResponse);

    render(
      <CompareModal
        papers={[mockPaper1, mockPaper2]}
        onClose={vi.fn()}
        onClear={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Structured Research Paper Comparison/i)).toBeDefined();
    });

    expect(screen.getByText(/Structured evidence-grounded comparative evaluation/i)).toBeDefined();
    expect(screen.getAllByText(/Methodology & Proposed Approach/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Reported Results & Benchmark Findings/i).length).toBeGreaterThan(0);

    // Verify source badges
    expect(screen.getAllByText(/Abstract Only/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Full Text Provenance/i).length).toBeGreaterThan(0);
  });

  it("renders the incomparable experimental protocols warning banner when present", async () => {
    vi.spyOn(api, "comparePapers").mockResolvedValue(mockCompareResponse);

    render(
      <CompareModal
        papers={[mockPaper1, mockPaper2]}
        onClose={vi.fn()}
        onClear={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("incomparable-warning-banner")).toBeDefined();
    });

    expect(screen.getByText(/Disparate Experimental Protocols Guard/i)).toBeDefined();
    expect(
      screen.getByText(
        /Higher numerical values cannot be interpreted as methodological superiority/i
      )
    ).toBeDefined();
  });

  it("expands supporting source passage when inspection button is clicked", async () => {
    vi.spyOn(api, "comparePapers").mockResolvedValue(mockCompareResponse);

    render(
      <CompareModal
        papers={[mockPaper1, mockPaper2]}
        onClose={vi.fn()}
        onClear={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getAllByText(/Methodology & Proposed Approach/i).length).toBeGreaterThan(0);
    });

    const inspectButtons = screen.getAllByText(/Inspect Supporting Passage/i);
    expect(inspectButtons.length).toBeGreaterThan(0);

    // Click to expand first passage
    fireEvent.click(inspectButtons[0]);

    await waitFor(() => {
      expect(screen.getAllByText(/Character Offsets:/i).length).toBeGreaterThan(0);
    });

    expect(screen.getAllByText(/Exact Source Passage/i).length).toBeGreaterThan(0);
  });

  it("explicitly displays missing evidence without equating it to missing capability", async () => {
    vi.spyOn(api, "comparePapers").mockResolvedValue(mockCompareResponse);

    render(
      <CompareModal
        papers={[mockPaper1, mockPaper2]}
        onClose={vi.fn()}
        onClear={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getAllByText(/Limitations & Threats to Validity/i).length).toBeGreaterThan(0);
    });

    expect(screen.getByText(/— Unreported in Text/i)).toBeDefined();
    expect(
      screen.getByText(/Absence of evidence does not imply the methodology lacks this capability/i)
    ).toBeDefined();
  });

  it("filters dimensions when category filter tabs are clicked", async () => {
    vi.spyOn(api, "comparePapers").mockResolvedValue(mockCompareResponse);

    render(
      <CompareModal
        papers={[mockPaper1, mockPaper2]}
        onClose={vi.fn()}
        onClear={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getAllByText(/Methodology & Proposed Approach/i).length).toBeGreaterThan(0);
    });

    // Click 'Coverage & Provenance' filter tab
    const provTab = screen.getByRole("button", { name: /Coverage & Provenance/i });
    fireEvent.click(provTab);

    // Method dimension should no longer be visible under Coverage category
    expect(screen.queryByTestId("dimension-card-method")).toBeNull();
  });

  it("handles API comparison errors gracefully with error state", async () => {
    vi.spyOn(api, "comparePapers").mockRejectedValue(new Error("Network connection lost"));

    render(
      <CompareModal
        papers={[mockPaper1, mockPaper2]}
        onClose={vi.fn()}
        onClear={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("compare-error-state")).toBeDefined();
    });

    expect(screen.getByText(/Network connection lost/i)).toBeDefined();
  });

  it("calls onClose and onClear when action buttons are clicked", async () => {
    vi.spyOn(api, "comparePapers").mockResolvedValue(mockCompareResponse);
    const onCloseMock = vi.fn();
    const onClearMock = vi.fn();

    render(
      <CompareModal
        papers={[mockPaper1, mockPaper2]}
        onClose={onCloseMock}
        onClear={onClearMock}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Structured Research Paper Comparison/i)).toBeDefined();
    });

    const closeBtn = screen.getByLabelText(/Close Comparison/i);
    fireEvent.click(closeBtn);
    expect(onCloseMock).toHaveBeenCalledTimes(1);

    const clearBtn = screen.getByText(/Clear Selection/i);
    fireEvent.click(clearBtn);
    expect(onClearMock).toHaveBeenCalledTimes(1);
  });

  it("renders comparison statistics card with papers evaluated and distributions", async () => {
    vi.spyOn(api, "comparePapers").mockResolvedValue(mockCompareResponse);

    render(
      <CompareModal
        papers={[mockPaper1, mockPaper2]}
        onClose={vi.fn()}
        onClear={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("comparison-statistics-card")).toBeDefined();
    });

    expect(screen.getByText(/Comparison Statistics & Scientific Distributions/i)).toBeDefined();
    expect(screen.getByText(/Papers Evaluated:/i)).toBeDefined();
    expect(screen.getByText("2024 (2)")).toBeDefined();
  });

  it("enforces comparison limit of 12 papers and rejects 13 papers with error", async () => {
    const papers13 = Array.from({ length: 13 }, (_, i) => ({
      ...mockPaper1,
      id: i + 1,
      paper_id: `test:paper.${i + 1}`,
      title: `Paper ${i + 1}`,
    }));

    render(
      <CompareModal
        papers={papers13}
        onClose={vi.fn()}
        onClear={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("compare-error-state")).toBeDefined();
    });

    expect(screen.getByText(/maximum 12 papers allowed/i)).toBeDefined();
  });
});
