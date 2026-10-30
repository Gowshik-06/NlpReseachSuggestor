import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import SavedLibraryView from "./SavedLibraryView";
import * as api from "../services/api";
import type { SavedPaper } from "../types/paper";

vi.mock("../services/api", () => ({
  deleteSavedPaper: vi.fn(),
}));

const mockSavedPapers: SavedPaper[] = [
  {
    id: 101,
    user_id: "test_researcher",
    paper_id: 1,
    saved_at: "2026-10-12T00:00:00Z",
    notes: "Crucial transformer baseline for benchmarking",
    tags: ["baseline", "nlp"],
    paper: {
      id: 1,
      paper_id: "arxiv:2101.00001",
      title: "Attention Foundations in Deep Representation Learning",
      abstract: "Abstract describing attention mechanisms.",
      authors: ["Alice Researcher", "Bob Scientist"],
      venue: "NeurIPS",
      year: 2026,
      source: "pubmed",
      citation_count: 42,
      categories: ["cs.AI"],
    },
  },
];

describe("SavedLibraryView Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders formatted source badge and private notes", () => {
    render(
      <SavedLibraryView
        savedPapers={mockSavedPapers}
        onLibraryUpdated={vi.fn()}
        onOpenSummary={vi.fn()}
        onToggleCompare={vi.fn()}
        comparedIds={new Set()}
        onTriggerDriutScan={vi.fn()}
        isAuthenticated={true}
      />
    );

    expect(screen.getByText("Attention Foundations in Deep Representation Learning")).toBeInTheDocument();
    expect(screen.getByText("🏛️ US Gov / PubMed")).toBeInTheDocument();
    expect(screen.getByText(/Crucial transformer baseline/)).toBeInTheDocument();
  });

  it("handles remove paper successfully and updates library", async () => {
    const onLibraryUpdated = vi.fn();
    vi.mocked(api.deleteSavedPaper).mockResolvedValueOnce({
      status: "success",
      message: "Deleted",
    });

    render(
      <SavedLibraryView
        savedPapers={mockSavedPapers}
        onLibraryUpdated={onLibraryUpdated}
        onOpenSummary={vi.fn()}
        onToggleCompare={vi.fn()}
        comparedIds={new Set()}
        onTriggerDriutScan={vi.fn()}
        isAuthenticated={true}
      />
    );

    const removeBtn = screen.getByText("Remove");
    fireEvent.click(removeBtn);

    await waitFor(() => {
      expect(api.deleteSavedPaper).toHaveBeenCalledWith(101);
      expect(onLibraryUpdated).toHaveBeenCalled();
    });
  });

  it("displays inline error banner and allows dismissing when remove fails", async () => {
    vi.mocked(api.deleteSavedPaper).mockRejectedValueOnce(new Error("Network timeout during removal"));

    render(
      <SavedLibraryView
        savedPapers={mockSavedPapers}
        onLibraryUpdated={vi.fn()}
        onOpenSummary={vi.fn()}
        onToggleCompare={vi.fn()}
        comparedIds={new Set()}
        onTriggerDriutScan={vi.fn()}
        isAuthenticated={true}
      />
    );

    const removeBtn = screen.getByText("Remove");
    fireEvent.click(removeBtn);

    await waitFor(() => {
      expect(screen.getByText(/Network timeout during removal/)).toBeInTheDocument();
    });

    // Dismiss error
    const dismissBtn = screen.getByText("✕");
    fireEvent.click(dismissBtn);
    expect(screen.queryByText(/Network timeout during removal/)).not.toBeInTheDocument();
  });
});
