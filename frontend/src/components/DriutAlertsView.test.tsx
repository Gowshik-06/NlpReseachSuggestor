import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";
import DriutAlertsView from "./DriutAlertsView";
import type { DRIUTAlert, Paper } from "../types/paper";
import * as api from "../services/api";

const mockSavedPaper: Paper = {
  id: 1,
  paper_id: "test:saved.1",
  title: "Attention Is All You Need",
  abstract: "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
  authors: ["Ashish Vaswani", "Noam Shazeer"],
  venue: "NeurIPS 2017",
  year: 2017,
  citation_count: 50000,
  source: "local",
  categories: ["cs.CL"],
};

const mockTriggerPaper: Paper = {
  id: 2,
  paper_id: "test:trigger.2",
  title: "Vision Transformer for Visual Recognition",
  abstract: "We extend and build upon the transformer architecture, adapting it to image patch tokens.",
  authors: ["Alexey Dosovitskiy"],
  venue: "ICLR 2021",
  year: 2021,
  citation_count: 15000,
  source: "local",
  categories: ["cs.CV"],
};

const mockAlerts: DRIUTAlert[] = [
  {
    id: 101,
    user_id: "test_researcher",
    saved_paper_id: 1,
    trigger_paper_id: 2,
    relationship_type: "Extension",
    confidence_score: 0.88,
    explanation: "'Vision Transformer' extends the architecture of your saved paper 'Attention Is All You Need'.",
    is_read: false,
    created_at: "2026-10-10T12:00:00Z",
    saved_paper: mockSavedPaper,
    trigger_paper: mockTriggerPaper,
    evidence_strength: "strong_evidence",
    evidence_passage: "We extend and build upon the transformer architecture, adapting it to image patch tokens.",
    saved_evidence_passage: "We propose the Transformer, relying entirely on an attention mechanism.",
    char_start: 120,
    char_end: 215,
    section_name: "Abstract",
    source_type: "abstract",
    semantic_similarity: 0.82,
    comparability_notes: null,
    uncertainty_warning: "Evaluated from abstract text only. Full-text provenance required for complete experimental protocol validation.",
    classification_version: "v2.0-evidence-grounded",
  },
  {
    id: 102,
    user_id: "test_researcher",
    saved_paper_id: 1,
    trigger_paper_id: 2,
    relationship_type: "Improvement",
    confidence_score: 0.91,
    explanation: "Achieves higher accuracy under aligned evaluation protocols.",
    is_read: true,
    created_at: "2026-10-09T14:30:00Z",
    saved_paper: mockSavedPaper,
    trigger_paper: mockTriggerPaper,
    evidence_strength: "partial_evidence",
    evidence_passage: "Our model outperforms prior baselines with 3.2% higher top-1 accuracy on ImageNet.",
    saved_evidence_passage: null,
    char_start: 350,
    char_end: 432,
    section_name: "Results",
    source_type: "full_text",
    semantic_similarity: 0.79,
    comparability_notes: "Benchmark verified under identical image resolution.",
    uncertainty_warning: null,
    classification_version: "v2.0-evidence-grounded",
  },
  {
    id: 103,
    user_id: "test_researcher",
    saved_paper_id: 1,
    trigger_paper_id: 2,
    relationship_type: "Challenge",
    confidence_score: 0.75,
    explanation: "Identifies quadratic computational bottlenecks under long contexts.",
    is_read: true,
    created_at: "2026-10-08T10:00:00Z",
    saved_paper: mockSavedPaper,
    trigger_paper: mockTriggerPaper,
    evidence_strength: "tentative",
    evidence_passage: "We critique the quadratic attention assumption, showing instability on ultra-long sequences.",
    saved_evidence_passage: null,
    char_start: 85,
    char_end: 180,
    section_name: "Introduction",
    source_type: "abstract",
    semantic_similarity: 0.71,
    comparability_notes: null,
    uncertainty_warning: "Evaluated from abstract text only.",
    classification_version: "v2.0-evidence-grounded",
  },
];

describe("DriutAlertsView Component", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders unauthenticated prompt when isAuthenticated is false", () => {
    const handleAuth = vi.fn();
    render(
      <DriutAlertsView
        alerts={[]}
        onAlertsUpdated={vi.fn()}
        onComparePair={vi.fn()}
        isAuthenticated={false}
        onOpenAuth={handleAuth}
      />
    );

    expect(screen.getByText(/Dynamic Research Impact Update Tracker \(DRIUT\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Sign In \/ Register/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/Sign In \/ Register/i));
    expect(handleAuth).toHaveBeenCalledTimes(1);
  });

  it("renders authenticated header, monitoring status, and filter tabs", async () => {
    vi.spyOn(api, "getDriutStatus").mockResolvedValueOnce({
      is_enabled: true,
      is_running_scan: false,
      interval_minutes: 60,
      last_run_time: "2026-10-10T12:00:00Z",
      last_run_duration_seconds: 4.5,
      last_run_status: "success",
      total_scans_completed: 12,
      last_scan_metrics: {
        users_scanned: 1,
        saved_papers_monitored: 1,
        candidates_evaluated: 50,
        new_alerts_created: 2,
      },
      provider_status: {},
      provider_errors: {},
    });

    render(
      <DriutAlertsView
        alerts={mockAlerts}
        onAlertsUpdated={vi.fn()}
        onComparePair={vi.fn()}
        isAuthenticated={true}
      />
    );

    expect(screen.getByText(/All Impact Alerts \(3\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Extension \(1\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Improvement \(1\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Challenge \(1\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Reproduction \(0\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Alternative \(0\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Potential Replacement \(0\)/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/Automated Background Monitoring: Active/i)).toBeInTheDocument();
    });
  });

  it("displays evidence strength badges and provenance indicators", () => {
    render(
      <DriutAlertsView
        alerts={mockAlerts}
        onAlertsUpdated={vi.fn()}
        onComparePair={vi.fn()}
        isAuthenticated={true}
      />
    );

    expect(screen.getByText(/🛡️ Verified Evidence/i)).toBeInTheDocument();
    expect(screen.getByText(/🔍 Grounded Claims/i)).toBeInTheDocument();
    expect(screen.getByText(/⚠️ Tentative Inference/i)).toBeInTheDocument();

    expect(screen.getAllByText(/📑 Abstract Only/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/📄 Full Text Provenance/i)).toBeInTheDocument();
  });

  it("toggles expandable supporting evidence section with exact offsets", () => {
    render(
      <DriutAlertsView
        alerts={mockAlerts}
        onAlertsUpdated={vi.fn()}
        onComparePair={vi.fn()}
        isAuthenticated={true}
      />
    );

    const inspectButtons = screen.getAllByText(/Inspect Supporting Evidence & Offsets/i);
    expect(inspectButtons.length).toBeGreaterThan(0);

    // Expand first alert
    fireEvent.click(inspectButtons[0]);

    expect(screen.getByText(/Candidate Evidence Passage/i)).toBeInTheDocument();
    expect(screen.getByText(/Offsets: \[120:215\]/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /"We extend and build upon the transformer architecture, adapting it to image patch tokens."/i
      )
    ).toBeInTheDocument();

    // Baseline passage
    expect(screen.getByText(/Baseline Saved Paper Passage/i)).toBeInTheDocument();
    expect(
      screen.getByText(/"We propose the Transformer, relying entirely on an attention mechanism."/i)
    ).toBeInTheDocument();

    // Collapse
    const hideButton = screen.getByText(/Hide Supporting Evidence/i);
    fireEvent.click(hideButton);
    expect(screen.queryByText(/Offsets: \[120:215\]/i)).not.toBeInTheDocument();
  });

  it("triggers comparison callback when Compare button is clicked", () => {
    const handleCompare = vi.fn();
    render(
      <DriutAlertsView
        alerts={mockAlerts}
        onAlertsUpdated={vi.fn()}
        onComparePair={handleCompare}
        isAuthenticated={true}
      />
    );

    const compareButtons = screen.getAllByText(/Compare New vs. Saved Paper/i);
    fireEvent.click(compareButtons[0]);

    expect(handleCompare).toHaveBeenCalledTimes(1);
    expect(handleCompare).toHaveBeenCalledWith(mockSavedPaper, mockTriggerPaper);
  });

  it("displays empty state when filter matches no alerts", () => {
    render(
      <DriutAlertsView
        alerts={mockAlerts}
        onAlertsUpdated={vi.fn()}
        onComparePair={vi.fn()}
        isAuthenticated={true}
      />
    );

    const reproductionTab = screen.getByText(/Reproduction \(0\)/i);
    fireEvent.click(reproductionTab);

    expect(screen.getByText(/No research alerts in this category/i)).toBeInTheDocument();
  });

  it("triggers manual literature scan and updates status banner", async () => {
    const mockUpdated = vi.fn();
    vi.spyOn(api, "triggerDriutScan").mockResolvedValueOnce({
      message: "DRIUT scan completed.",
      new_alerts_count: 2,
      alerts: mockAlerts,
    });
    vi.spyOn(api, "getDriutStatus").mockResolvedValue({
      is_enabled: true,
      is_running_scan: false,
      interval_minutes: 60,
      last_run_time: "2026-10-10T12:05:00Z",
      last_run_duration_seconds: 3.2,
      last_run_status: "success",
      total_scans_completed: 13,
      last_scan_metrics: {},
      provider_status: {},
      provider_errors: {},
    });

    render(
      <DriutAlertsView
        alerts={mockAlerts}
        onAlertsUpdated={mockUpdated}
        onComparePair={vi.fn()}
        isAuthenticated={true}
      />
    );

    const scanBtn = screen.getByText(/Run Live Impact Scan/i);
    fireEvent.click(scanBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/Discovered 2 new research relationship alerts!/i)
      ).toBeInTheDocument();
    });
    expect(mockUpdated).toHaveBeenCalledTimes(1);
  });
});
