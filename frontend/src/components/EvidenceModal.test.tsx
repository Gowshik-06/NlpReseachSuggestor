import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";
import EvidenceModal from "./EvidenceModal";
import type { Paper, PaperEvidenceResponse } from "../types/paper";
import * as api from "../services/api";

const mockPaper: Paper = {
  id: 1,
  paper_id: "test:flashtree_2026",
  title: "FlashTree: Dynamic Sparse Attention for Efficient Transformers",
  abstract: "A major challenge in transformers is quadratic complexity. We propose FlashTree.",
  authors: ["Alice Smith"],
  venue: "ICLR 2026",
  year: 2026,
  source: "local",
  citation_count: 42,
  categories: ["cs.CL"],
};

const mockEvidenceResponse: PaperEvidenceResponse = {
  paper_id: "test:flashtree_2026",
  paper_title: "FlashTree: Dynamic Sparse Attention for Efficient Transformers",
  status: "partial_extraction",
  source_type: "abstract",
  evidence_count: 2,
  categories_present: ["problem", "method"],
  missing_categories: [
    "objective",
    "dataset",
    "metrics",
    "results",
    "contributions",
    "limitations",
    "future_work",
  ],
  evidence: [
    {
      id: 101,
      paper_id: 1,
      category: "problem",
      category_label: "Research Problem & Motivation",
      claim: "A major challenge in transformers is quadratic complexity.",
      source_passage: "A major challenge in transformers is quadratic complexity.",
      char_start: 0,
      char_end: 58,
      source_type: "abstract",
      extraction_method: "rule_based_nlp",
      confidence_score: 0.95,
      is_verified: true,
      verification_notes: "Exact span verified in abstract",
    },
    {
      id: 102,
      paper_id: 1,
      category: "method",
      category_label: "Proposed Method / Architecture",
      claim: "We propose FlashTree, a dynamic attention mechanism.",
      source_passage: "We propose FlashTree, a dynamic attention mechanism.",
      char_start: 59,
      char_end: 112,
      source_type: "abstract",
      extraction_method: "rule_based_nlp",
      confidence_score: 0.92,
      is_verified: true,
      verification_notes: "Exact span verified in abstract",
    },
  ],
  verification_summary: {
    total_evidence: 2,
    verified_count: 2,
    is_stale: false,
    source_type: "abstract",
    char_offsets_valid: true,
    nonempty_passages: true,
    verification_message: "Evidence verified against abstract.",
  },
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("EvidenceModal Component", () => {
  it("renders loading state initially while fetching evidence", () => {
    vi.spyOn(api, "getPaperEvidence").mockImplementation(
      () => new Promise(() => {})
    );

    render(<EvidenceModal paper={mockPaper} onClose={vi.fn()} />);
    expect(screen.getByText(/Grounding scientific claims and verifying exact passage spans/)).toBeInTheDocument();
  });

  it("renders paper title, claims, and badges upon successful load", async () => {
    vi.spyOn(api, "getPaperEvidence").mockResolvedValue(mockEvidenceResponse);

    render(<EvidenceModal paper={mockPaper} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(mockPaper.title)).toBeInTheDocument();
      expect(screen.getByText("A major challenge in transformers is quadratic complexity.")).toBeInTheDocument();
      expect(screen.getByText("We propose FlashTree, a dynamic attention mechanism.")).toBeInTheDocument();
      expect(screen.getByText("📝 Abstract-Derived")).toBeInTheDocument();
    });
  });

  it("displays explicit abstract-derived warning note for abstract provenance", async () => {
    vi.spyOn(api, "getPaperEvidence").mockResolvedValue(mockEvidenceResponse);

    render(<EvidenceModal paper={mockPaper} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/Abstract-Derived Evidence:/)).toBeInTheDocument();
      expect(
        screen.getByText(/All claims below are grounded in the author-published abstract/)
      ).toBeInTheDocument();
    });
  });

  it("displays character offset spans and match scores", async () => {
    vi.spyOn(api, "getPaperEvidence").mockResolvedValue(mockEvidenceResponse);

    render(<EvidenceModal paper={mockPaper} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("chars 0–58")).toBeInTheDocument();
      expect(screen.getByText("chars 59–112")).toBeInTheDocument();
      expect(screen.getByText("✓ 95% Match")).toBeInTheDocument();
      expect(screen.getByText("✓ 92% Match")).toBeInTheDocument();
    });
  });

  it("expands supporting source passage when inspection button is clicked", async () => {
    vi.spyOn(api, "getPaperEvidence").mockResolvedValue(mockEvidenceResponse);

    render(<EvidenceModal paper={mockPaper} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("A major challenge in transformers is quadratic complexity.")).toBeInTheDocument();
    });

    const inspectButtons = screen.getAllByText("▼ Inspect exact supporting source passage");
    expect(inspectButtons.length).toBe(2);

    fireEvent.click(inspectButtons[0]);

    expect(screen.getByText("▲ Hide supporting source passage")).toBeInTheDocument();
    expect(
      screen.getByText('"A major challenge in transformers is quadratic complexity."')
    ).toBeInTheDocument();
  });

  it("filters evidence by category when category filter button is clicked", async () => {
    vi.spyOn(api, "getPaperEvidence").mockResolvedValue(mockEvidenceResponse);

    render(<EvidenceModal paper={mockPaper} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("All Evidence (2)")).toBeInTheDocument();
    });

    // Click on Problem filter
    const problemBtn = screen.getByText("Research Problem");
    fireEvent.click(problemBtn);

    expect(screen.getByText("A major challenge in transformers is quadratic complexity.")).toBeInTheDocument();
    expect(screen.queryByText("We propose FlashTree, a dynamic attention mechanism.")).not.toBeInTheDocument();
  });

  it("explicitly displays missing/unreported categories without fabricating claims", async () => {
    vi.spyOn(api, "getPaperEvidence").mockResolvedValue(mockEvidenceResponse);

    render(<EvidenceModal paper={mockPaper} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(
        screen.getByText(/Categories Not Stated in Available Text \(7\)/)
      ).toBeInTheDocument();
      expect(screen.getByText(/Limitations & Threats to Validity/)).toBeInTheDocument();
      expect(screen.getByText(/Future Work Directions/)).toBeInTheDocument();
      expect(
        screen.getByText(/missing categories are explicitly marked rather than fabricated/)
      ).toBeInTheDocument();
    });
  });

  it("displays unavailable text state when paper has no extractable content", async () => {
    const emptyResponse: PaperEvidenceResponse = {
      paper_id: "empty:paper",
      paper_title: "Paper Without Text",
      status: "unavailable_text",
      evidence_count: 0,
      categories_present: [],
      missing_categories: [
        "problem",
        "objective",
        "method",
        "dataset",
        "metrics",
        "results",
        "contributions",
        "limitations",
        "future_work",
      ],
      evidence: [],
    };
    vi.spyOn(api, "getPaperEvidence").mockResolvedValue(emptyResponse);

    render(<EvidenceModal paper={mockPaper} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("Source Text Unavailable")).toBeInTheDocument();
      expect(
        screen.getByText(/This publication does not contain an extractable abstract or full-text manuscript/)
      ).toBeInTheDocument();
    });
  });

  it("handles API failure and triggers re-extraction on retry", async () => {
    vi.spyOn(api, "getPaperEvidence").mockRejectedValue(new Error("Network connection error"));
    const extractSpy = vi.spyOn(api, "extractPaperEvidence").mockResolvedValue(mockEvidenceResponse);

    render(<EvidenceModal paper={mockPaper} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/Network connection error/)).toBeInTheDocument();
    });

    const retryBtn = screen.getByText("🔄 Retry");
    fireEvent.click(retryBtn);

    expect(extractSpy).toHaveBeenCalledWith(mockPaper.paper_id, true);
  });

  it("closes modal when close button is clicked", async () => {
    vi.spyOn(api, "getPaperEvidence").mockResolvedValue(mockEvidenceResponse);
    const closeSpy = vi.fn();

    render(<EvidenceModal paper={mockPaper} onClose={closeSpy} />);

    await waitFor(() => {
      expect(screen.getByText(mockPaper.title)).toBeInTheDocument();
    });

    const closeBtn = screen.getByLabelText("Close modal");
    fireEvent.click(closeBtn);

    expect(closeSpy).toHaveBeenCalledTimes(1);
  });
});
