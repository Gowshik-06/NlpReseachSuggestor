import React, { useEffect, useState } from "react";
import type { Paper, SummaryResponse } from "../types/paper";
import { getPaperSummary } from "../services/api";

interface SummaryModalProps {
  paper: Paper | null;
  onClose: () => void;
}

export default function SummaryModal({ paper, onClose }: SummaryModalProps) {
  const [loading, setLoading] = useState(true);
  const [summaryData, setSummaryData] = useState<SummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!paper) return;
    setLoading(true);
    setError(null);

    getPaperSummary(paper)
      .then((data) => {
        setSummaryData(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to generate AI summary.");
        setLoading(false);
      });
  }, [paper]);

  useEffect(() => {
    if (!paper) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [paper, onClose]);

  if (!paper) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-label={`Research Synthesis: ${paper.title}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <span style={{ fontSize: "0.74rem", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--button-primary)", fontWeight: 700 }}>
              ResearchLens Synthesis
            </span>
            <h2 style={{ margin: "0.25rem 0 0", fontSize: "1.25rem", color: "var(--text-primary)", fontFamily: "var(--font-serif)" }}>
              {paper.title}
            </h2>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} title="Close">
            ✕
          </button>
        </div>

        {loading && (
          <div className="loading-box">
            <p>Distilling paper structure, methodology, and empirical claims…</p>
          </div>
        )}

        {error && (
          <div className="error-box">
            {error}
          </div>
        )}

        {!loading && summaryData && (
          <div>
            <div className="summary-section">
              {summaryData.executive_summary}
            </div>

            <div className="grid-2col">
              <div className="card-white">
                <h4 style={{ margin: "0 0 0.5rem", color: "var(--berry)", fontSize: "0.88rem", fontWeight: 600 }}>
                  Problem Statement
                </h4>
                <p style={{ margin: 0, fontSize: "0.84rem", lineHeight: 1.55, color: "var(--text-secondary)" }}>
                  {summaryData.problem_statement}
                </p>
              </div>

              <div className="card-white">
                <h4 style={{ margin: "0 0 0.5rem", color: "var(--azure)", fontSize: "0.88rem", fontWeight: 600 }}>
                  Methodology &amp; Approach
                </h4>
                <p style={{ margin: 0, fontSize: "0.84rem", lineHeight: 1.55, color: "var(--text-secondary)" }}>
                  {summaryData.methodology}
                </p>
              </div>

              <div className="card-white">
                <h4 style={{ margin: "0 0 0.5rem", color: "var(--emerald)", fontSize: "0.88rem", fontWeight: 600 }}>
                  Key Findings &amp; Strengths
                </h4>
                <p style={{ margin: 0, fontSize: "0.84rem", lineHeight: 1.55, color: "var(--text-secondary)" }}>
                  {summaryData.key_findings}
                </p>
              </div>

              <div className="card-white">
                <h4 style={{ margin: "0 0 0.5rem", color: "var(--amber)", fontSize: "0.88rem", fontWeight: 600 }}>
                  Constraints &amp; Limitations
                </h4>
                <p style={{ margin: 0, fontSize: "0.84rem", lineHeight: 1.55, color: "var(--text-secondary)" }}>
                  {summaryData.limitations}
                </p>
              </div>
            </div>

            <div className="summary-section">
              <h4 style={{ margin: "0 0 0.45rem", color: "var(--text-primary)", fontSize: "0.86rem", fontWeight: 600 }}>
                Recommended Reading Strategy
              </h4>
              <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: "0.84rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                {summaryData.suggested_reading_order.map((step, idx) => (
                  <li key={idx}>{step}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
