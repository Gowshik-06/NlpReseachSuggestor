import React, { useEffect, useState } from "react";
import type { Paper, PaperEvidenceResponse, PaperEvidenceItem } from "../types/paper";
import { getPaperEvidence, extractPaperEvidence } from "../services/api";

interface EvidenceModalProps {
  paper: Paper | null;
  onClose: () => void;
}

const CATEGORY_META: Record<string, { label: string; icon: string; color: string }> = {
  problem: { label: "Research Problem & Motivation", icon: "🎯", color: "#fca5a5" },
  objective: { label: "Research Objective / Question", icon: "🧭", color: "#93c5fd" },
  method: { label: "Proposed Method / Architecture", icon: "⚙️", color: "#6ee7b7" },
  dataset: { label: "Dataset & Experimental Setup", icon: "📊", color: "#c4b5fd" },
  metrics: { label: "Evaluation Metrics", icon: "📏", color: "#fde047" },
  results: { label: "Reported Results & Findings", icon: "📈", color: "#bef264" },
  contributions: { label: "Stated Contributions", icon: "🏆", color: "#fdba74" },
  limitations: { label: "Limitations & Threats to Validity", icon: "⚠️", color: "#f87171" },
  future_work: { label: "Future Work Directions", icon: "🚀", color: "#38bdf8" },
};

export default function EvidenceModal({ paper, onClose }: EvidenceModalProps) {
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [evidenceData, setEvidenceData] = useState<PaperEvidenceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [expandedPassages, setExpandedPassages] = useState<Record<number, boolean>>({});

  const loadEvidence = (force: boolean = false) => {
    if (!paper) return;
    if (force) {
      setExtracting(true);
    } else {
      setLoading(true);
    }
    setError(null);

    const action = force && paper.id
      ? extractPaperEvidence(paper.paper_id, true)
      : getPaperEvidence(paper);

    action
      .then((data) => {
        setEvidenceData(data);
        setLoading(false);
        setExtracting(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to retrieve grounded evidence.");
        setLoading(false);
        setExtracting(false);
      });
  };

  useEffect(() => {
    if (paper) {
      loadEvidence(false);
    }
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

  const togglePassage = (idx: number) => {
    setExpandedPassages((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const filteredEvidence = evidenceData?.evidence.filter((item) =>
    selectedCategory === "all" ? true : item.category === selectedCategory
  ) ?? [];

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "940px" }}>
        {/* Header */}
        <div className="modal-header">
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.35rem" }}>
              <span
                style={{
                  fontSize: "0.74rem",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--button-primary)",
                  fontWeight: 700,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.35rem",
                }}
              >
                Grounded Research Intelligence
              </span>
              {evidenceData?.source_type && (
                <span
                  style={{
                    fontSize: "0.72rem",
                    padding: "0.15rem 0.55rem",
                    borderRadius: "999px",
                    fontWeight: 700,
                    background:
                      evidenceData.source_type === "full_text"
                        ? "#ecfdf5"
                        : "#fffbeb",
                    color: evidenceData.source_type === "full_text" ? "#047857" : "#b45309",
                    border: `1px solid ${
                      evidenceData.source_type === "full_text"
                        ? "#a7f3d0"
                        : "#fde68a"
                    }`,
                  }}
                >
                  {evidenceData.source_type === "full_text"
                    ? "📄 Full-Text Source"
                    : "📝 Abstract-Derived"}
                </span>
              )}
            </div>
            <h2 style={{ margin: 0, fontSize: "1.3rem", color: "#1f2937", lineHeight: 1.35 }}>
              {paper.title}
            </h2>
          </div>
          <button className="modal-close-btn" onClick={onClose} title="Close" aria-label="Close modal">
            ✕
          </button>
        </div>

        {/* Loading State */}
        {loading && (
          <div style={{ textAlign: "center", padding: "3.5rem 1rem", color: "#6b7280" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>🔬</div>
            <p style={{ margin: 0, fontSize: "0.95rem" }}>
              Grounding scientific claims and verifying exact passage spans…
            </p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div
            style={{
              padding: "1.25rem",
              background: "#fef2f2",
              border: "1px solid #fecaca",
              borderRadius: "var(--radius-md)",
              color: "#b91c1c",
              marginBottom: "1.5rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div>
              <strong>Extraction Error:</strong> {error}
            </div>
            <button
              className="btn-secondary"
              onClick={() => loadEvidence(true)}
              style={{ padding: "0.35rem 0.75rem", fontSize: "0.8rem" }}
            >
              🔄 Retry
            </button>
          </div>
        )}

        {/* Content */}
        {!loading && evidenceData && (
          <div>
            {/* Top Verification & Provenance Alert */}
            {evidenceData.source_type === "abstract" && (
              <div
                style={{
                  background: "#fffbeb",
                  border: "1px solid #fde68a",
                  padding: "0.85rem 1.15rem",
                  borderRadius: "var(--radius-md)",
                  marginBottom: "1.25rem",
                  fontSize: "0.83rem",
                  lineHeight: 1.5,
                  color: "#92400e",
                }}
              >
                ℹ️ <strong>Abstract-Derived Evidence:</strong> All claims below are grounded in the
                author-published abstract. They have not been independently verified against the full
                manuscript text.
              </div>
            )}

            {evidenceData.verification_summary?.is_stale && (
              <div
                style={{
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  padding: "0.85rem 1.15rem",
                  borderRadius: "var(--radius-md)",
                  marginBottom: "1.25rem",
                  fontSize: "0.83rem",
                  color: "#b91c1c",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span>
                  ⚠️ <strong>Document Modified:</strong> Paper text has been updated since previous
                  extraction. Evidence is marked stale.
                </span>
                <button
                  className="btn-secondary"
                  onClick={() => loadEvidence(true)}
                  disabled={extracting}
                  style={{ padding: "0.3rem 0.7rem", fontSize: "0.78rem" }}
                >
                  {extracting ? "Extracting…" : "🔄 Refresh Evidence"}
                </button>
              </div>
            )}

            {/* Unavailable Text Empty State */}
            {evidenceData.status === "unavailable_text" && (
              <div
                style={{
                  textAlign: "center",
                  padding: "3rem 1.5rem",
                  background: "#ffffff",
                  borderRadius: "var(--radius-md)",
                  border: "1px dashed #d1d5db",
                  color: "#6b7280",
                }}
              >
                <div style={{ fontSize: "2.2rem", marginBottom: "0.5rem" }}>📄</div>
                <h4 style={{ margin: "0 0 0.35rem", color: "#1f2937" }}>Source Text Unavailable</h4>
                <p style={{ margin: 0, fontSize: "0.86rem", maxWidth: "480px", marginInline: "auto" }}>
                  This publication does not contain an extractable abstract or full-text manuscript.
                  Upload a text-based PDF or enrich paper metadata to enable evidence extraction.
                </p>
              </div>
            )}

            {/* Category Filter Pills */}
            {evidenceData.status !== "unavailable_text" && (
              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  overflowX: "auto",
                  paddingBottom: "0.5rem",
                  marginBottom: "1.25rem",
                }}
              >
                <button
                  onClick={() => setSelectedCategory("all")}
                  style={{
                    background: selectedCategory === "all" ? "#1f2937" : "#ffffff",
                    color: selectedCategory === "all" ? "#fff" : "#4b5563",
                    border: "1px solid " + (selectedCategory === "all" ? "#1f2937" : "#e5e7eb"),
                    padding: "0.35rem 0.75rem",
                    borderRadius: "var(--radius-md)",
                    fontSize: "0.78rem",
                    fontWeight: 600,
                    whiteSpace: "nowrap",
                  }}
                >
                  All Evidence ({evidenceData.evidence.length})
                </button>

                {evidenceData.categories_present.map((cat) => {
                  const meta = CATEGORY_META[cat] || { label: cat, icon: "📌", color: "#1f2937" };
                  const count = evidenceData.evidence.filter((i) => i.category === cat).length;
                  const isSelected = selectedCategory === cat;
                  return (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(cat)}
                      style={{
                        background: isSelected ? "#1f2937" : "#ffffff",
                        color: isSelected ? "#ffffff" : "#4b5563",
                        border: "1px solid " + (isSelected ? "#1f2937" : "#e5e7eb"),
                        padding: "0.35rem 0.75rem",
                        borderRadius: "var(--radius-md)",
                        fontSize: "0.78rem",
                        fontWeight: 600,
                        whiteSpace: "nowrap",
                        display: "flex",
                        alignItems: "center",
                        gap: "0.35rem",
                      }}
                    >
                      <span>{meta.icon}</span>
                      <span>{meta.label.split("/")[0].split("&")[0].trim()}</span>
                      <span style={{ opacity: 0.7 }}>({count})</span>
                    </button>
                  );
                })}
              </div>
            )}

            {/* Evidence Cards */}
            {filteredEvidence.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginBottom: "1.5rem" }}>
                {filteredEvidence.map((item, idx) => {
                  const meta = CATEGORY_META[item.category] || { label: item.category, icon: "📌", color: "#6ee7b7" };
                  const isExpanded = expandedPassages[idx] ?? false;

                  return (
                    <div
                      key={item.id ?? idx}
                      style={{
                        background: "#ffffff",
                        border: "1px solid #e5e7eb",
                        borderRadius: "var(--radius-md)",
                        padding: "1.25rem",
                        position: "relative",
                        boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
                      }}
                    >
                      {/* Card Header */}
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: "0.6rem",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                          <span style={{ fontSize: "1.1rem" }}>{meta.icon}</span>
                          <span
                            style={{
                              fontWeight: 700,
                              fontSize: "0.86rem",
                              color: "#1f2937",
                            }}
                          >
                            {item.category_label || meta.label}
                          </span>
                        </div>

                        {/* Provenance Badges */}
                        <div style={{ display: "flex", gap: "0.45rem", fontSize: "0.72rem" }}>
                          {item.section_name && (
                            <span
                              style={{
                                background: "#f3f4f6",
                                padding: "0.15rem 0.5rem",
                                borderRadius: "4px",
                                color: "#4b5563",
                              }}
                            >
                              📑 {item.section_name}
                            </span>
                          )}
                          {item.page_number && (
                            <span
                              style={{
                                background: "#f3f4f6",
                                padding: "0.15rem 0.5rem",
                                borderRadius: "4px",
                                color: "#4b5563",
                              }}
                            >
                              📄 Page {item.page_number}
                            </span>
                          )}
                          {item.char_start !== undefined && item.char_end !== undefined && (
                            <span
                              style={{
                                background: "#f3f4f6",
                                padding: "0.15rem 0.5rem",
                                borderRadius: "4px",
                                color: "#6b7280",
                                fontFamily: "monospace",
                              }}
                            >
                              chars {item.char_start}–{item.char_end}
                            </span>
                          )}
                          {item.confidence_score && (
                            <span
                              style={{
                                background: "#ecfdf5",
                                padding: "0.15rem 0.5rem",
                                borderRadius: "4px",
                                color: "#047857",
                                fontWeight: 600,
                                border: "1px solid #a7f3d0",
                              }}
                              title="Rule-based linguistic pattern match score"
                            >
                              ✓ {Math.round(item.confidence_score * 100)}% Match
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Extracted Claim */}
                      <p
                        style={{
                          margin: "0 0 0.85rem",
                          fontSize: "0.9rem",
                          lineHeight: 1.55,
                          color: "#1f2937",
                          fontWeight: 500,
                        }}
                      >
                        {item.claim}
                      </p>

                      {/* Supporting Passage Collapsible */}
                      <div>
                        <button
                          onClick={() => togglePassage(idx)}
                          style={{
                            background: "none",
                            border: "none",
                            padding: 0,
                            fontSize: "0.78rem",
                            color: "#2563eb",
                            fontWeight: 600,
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "0.3rem",
                            cursor: "pointer",
                          }}
                        >
                          <span>{isExpanded ? "▲ Hide supporting source passage" : "▼ Inspect exact supporting source passage"}</span>
                        </button>

                        {isExpanded && (
                          <div
                            style={{
                              marginTop: "0.6rem",
                              padding: "0.85rem 1rem",
                              background: "#f9fafb",
                              borderLeft: "3px solid #1f2937",
                              borderTop: "1px solid #e5e7eb",
                              borderRight: "1px solid #e5e7eb",
                              borderBottom: "1px solid #e5e7eb",
                              borderRadius: "0 var(--radius-sm) var(--radius-sm) 0",
                              fontSize: "0.82rem",
                              lineHeight: 1.6,
                              color: "#374151",
                              fontStyle: "italic",
                            }}
                          >
                            "{item.source_passage}"
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Missing Categories Notice */}
            {evidenceData.missing_categories.length > 0 && (
              <div
                style={{
                  background: "#f9fafb",
                  border: "1px dashed #d1d5db",
                  padding: "1.1rem 1.35rem",
                  borderRadius: "var(--radius-md)",
                  marginBottom: "1.5rem",
                }}
              >
                <h4
                  style={{
                    margin: "0 0 0.5rem",
                    fontSize: "0.82rem",
                    color: "#6b7280",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                  }}
                >
                  🚫 Categories Not Stated in Available Text ({evidenceData.missing_categories.length})
                </h4>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.45rem", marginBottom: "0.45rem" }}>
                  {evidenceData.missing_categories.map((cat) => {
                    const meta = CATEGORY_META[cat] || { label: cat, icon: "📌" };
                    return (
                      <span
                        key={cat}
                        style={{
                          background: "#ffffff",
                          border: "1px solid #e5e7eb",
                          padding: "0.2rem 0.55rem",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          color: "#6b7280",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "0.3rem",
                        }}
                      >
                        {meta.icon} {meta.label}
                      </span>
                    );
                  })}
                </div>
                <p style={{ margin: 0, fontSize: "0.76rem", color: "#6b7280" }}>
                  Strict evidence grounding rule: missing categories are explicitly marked rather than fabricated.
                </p>
              </div>
            )}

            {/* Bottom Actions Bar */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                paddingTop: "1rem",
                borderTop: "1px solid #e5e7eb",
              }}
            >
              <div style={{ fontSize: "0.78rem", color: "#6b7280" }}>
                {evidenceData.verification_summary?.verification_message || "Evidence verified."}
              </div>

              <div style={{ display: "flex", gap: "0.6rem" }}>
                <button
                  className="btn-secondary"
                  onClick={() => loadEvidence(true)}
                  disabled={extracting}
                  style={{ fontSize: "0.82rem" }}
                >
                  {extracting ? "Extracting…" : "🔄 Re-Extract Evidence"}
                </button>
                <button
                  className="btn-secondary"
                  onClick={onClose}
                  style={{ fontSize: "0.82rem", background: "#ffffff" }}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
