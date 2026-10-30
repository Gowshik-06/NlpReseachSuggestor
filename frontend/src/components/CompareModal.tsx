import React, { useEffect, useState } from "react";
import type {
  Paper,
  CompareResponse,
  ComparisonDimensionDetail,
  ComparisonCell,
} from "../types/paper";
import { comparePapers } from "../services/api";
import { DocumentIcon, SearchIcon } from "./icons/Icons";

interface CompareModalProps {
  papers: Paper[];
  onClose: () => void;
  onClear: () => void;
}

export default function CompareModal({ papers, onClose, onClear }: CompareModalProps) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [expandedPassages, setExpandedPassages] = useState<Record<string, boolean>>({});
  const [showInsights, setShowInsights] = useState(true);
  const [showStatistics, setShowStatistics] = useState(true);

  useEffect(() => {
    if (papers.length < 2) return;
    setLoading(true);
    setError(null);

    const validPapers = papers.filter(
      (p) => (p.paper_id && p.paper_id.trim().length > 0) || (p.id !== undefined && p.id !== null)
    );

    if (validPapers.length < 2) {
      setError("Please select at least 2 papers with valid identifiers to compare.");
      setLoading(false);
      return;
    }

    if (validPapers.length > 12) {
      setError("Comparison limit exceeded: maximum 12 papers allowed per comparison.");
      setLoading(false);
      return;
    }

    comparePapers(validPapers)
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to compare papers.");
        setLoading(false);
      });
  }, [papers]);

  useEffect(() => {
    if (papers.length < 2) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [papers.length, onClose]);

  const togglePassage = (key: string) => {
    setExpandedPassages((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (papers.length < 2) return null;

  const filteredDimensions: ComparisonDimensionDetail[] = (data?.dimensions || []).filter((d) => {
    if (selectedCategory === "all") return true;
    return d.category === selectedCategory;
  });

  const hasIncomparable = (data?.incomparable_dimensions || []).length > 0;
  const hasAbstractOnly = (data?.coverage_summary || []).some((c) => c.source_type === "abstract");
  const hasStale = (data?.coverage_summary || []).some((c) => c.is_stale);

  return (
    <div className="modal-backdrop" onClick={onClose} data-testid="compare-modal-backdrop">
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-label="Side-by-Side Paper Comparison Matrix"
        style={{
          maxWidth: "1240px",
          width: "95vw",
          maxHeight: "92vh",
          display: "flex",
          flexDirection: "column",
          padding: 0,
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="modal-header"
          style={{
            padding: "1.25rem 1.75rem",
            borderBottom: "1px solid var(--border-leaf)",
            background: "var(--bg-surface)",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span
                style={{
                  fontSize: "0.72rem",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--button-primary)",
                  fontWeight: 700,
                  background: "var(--bg-subtle)",
                  padding: "0.15rem 0.5rem",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-leaf)",
                }}
              >
                Evidence-Grounded Comparison
              </span>
              <span
                style={{
                  fontSize: "0.72rem",
                  color: "var(--text-muted)",
                  background: "var(--bg-subtle)",
                  padding: "0.15rem 0.5rem",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-leaf)",
                }}
              >
                {papers.length} Publications
              </span>
            </div>
            <h2 style={{ margin: "0.35rem 0 0", fontSize: "1.3rem", color: "var(--text-primary)", fontWeight: 700, fontFamily: "var(--font-serif)" }}>
              Structured Research Paper Comparison
            </h2>
          </div>

          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={onClear}
              style={{ fontSize: "0.8rem", color: "var(--berry)" }}
            >
              Clear Selection
            </button>
            <button
              type="button"
              className="modal-close-btn"
              onClick={onClose}
              title="Close"
              aria-label="Close Comparison"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Modal Scrollable Body */}
        <div style={{ padding: "1.5rem 1.75rem", overflowY: "auto", flex: 1, background: "#ffffff" }}>
          {loading && (
            <div
              data-testid="compare-loading-state"
              style={{ textAlign: "center", padding: "4rem 1rem", color: "#6b7280" }}
            >
              <div style={{ display: "flex", justifyContent: "center", marginBottom: "0.85rem", color: "var(--button-primary)" }}>
                <DocumentIcon size={40} />
              </div>
              <h3 style={{ color: "#1f2937", fontSize: "1.1rem", marginBottom: "0.5rem" }}>
                Analyzing Evidence & Comparing Dimensions…
              </h3>
              <p style={{ maxWidth: "540px", margin: "0 auto", fontSize: "0.88rem", lineHeight: 1.6 }}>
                Grounding scientific claims, verifying character spans, and cross-referencing experimental
                protocols across {papers.length} publications.
              </p>
            </div>
          )}

          {error && (
            <div
              data-testid="compare-error-state"
              style={{
                padding: "1.5rem",
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: "var(--radius-md)",
                color: "#b91c1c",
              }}
            >
              <strong style={{ display: "block", marginBottom: "0.35rem" }}>Comparison Failed:</strong>
              {error}
            </div>
          )}

          {!loading && data && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              {/* Scientific Warnings Banner: Incomparable Protocols or Stale Evidence */}
              {hasIncomparable && (
                <div
                  data-testid="incomparable-warning-banner"
                  style={{
                    background: "#fffbeb",
                    border: "1px solid #fde68a",
                    borderRadius: "var(--radius-md)",
                    padding: "1rem 1.25rem",
                    color: "#92400e",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "0.75rem",
                  }}
                >
                  <span style={{ fontSize: "1.4rem", lineHeight: 1 }}>⚠️</span>
                  <div>
                    <strong style={{ color: "#b45309", display: "block", marginBottom: "0.2rem" }}>
                      Disparate Experimental Protocols Guard:
                    </strong>
                    <p style={{ margin: 0, fontSize: "0.85rem", lineHeight: 1.55 }}>
                      Direct numerical result comparison between these publications is scientifically guarded.
                      The papers evaluate across different datasets, metrics, or experimental baselines.
                      Higher numerical values cannot be interpreted as methodological superiority.
                    </p>
                  </div>
                </div>
              )}

              {hasStale && (
                <div
                  style={{
                    background: "#fef2f2",
                    border: "1px solid #fecaca",
                    borderRadius: "var(--radius-md)",
                    padding: "0.85rem 1.15rem",
                    color: "#b91c1c",
                    fontSize: "0.85rem",
                  }}
                >
                  ⚠️ <strong>Stale Evidence Warning:</strong> One or more papers have been updated since initial
                  evidence extraction. Refreshing evidence is recommended.
                </div>
              )}

              {/* Executive Synthesis Card */}
              <div
                style={{
                  background: "#f9fafb",
                  border: "1px solid #e5e7eb",
                  borderRadius: "var(--radius-md)",
                  padding: "1.25rem 1.5rem",
                }}
              >
                <div
                  style={{
                    fontSize: "0.75rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    color: "#1f2937",
                    fontWeight: 700,
                    marginBottom: "0.4rem",
                  }}
                >
                  Executive Synthesis
                </div>
                <div style={{ color: "#374151", fontSize: "0.92rem", lineHeight: 1.65 }}>
                  {data.executive_summary}
                </div>
              </div>

              {/* Coverage Summary Cards (One per paper) */}
              <div>
                <div
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    color: "#6b7280",
                    marginBottom: "0.75rem",
                  }}
                >
                  Coverage & Provenance Overview
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: `repeat(${data.papers.length}, minmax(240px, 1fr))`,
                    gap: "1rem",
                    overflowX: "auto",
                  }}
                >
                  {(data.coverage_summary || []).map((cov) => {
                    const paper = data.papers.find((p) => p.paper_id === cov.paper_id);
                    const isAbstract = cov.source_type === "abstract";
                    const isFullText = cov.source_type === "full_text";

                    return (
                      <div
                        key={cov.paper_id}
                        style={{
                          background: "#ffffff",
                          border: "1px solid #e5e7eb",
                          borderRadius: "var(--radius-md)",
                          padding: "1rem",
                          display: "flex",
                          flexDirection: "column",
                          gap: "0.5rem",
                          boxShadow: "0 1px 2px rgba(0, 0, 0, 0.04)",
                        }}
                      >
                        <div style={{ fontWeight: 700, color: "#1f2937", fontSize: "0.92rem", lineHeight: 1.4 }}>
                          {cov.title}
                        </div>
                        <div style={{ fontSize: "0.78rem", color: "#4b5563" }}>
                          {paper?.authors?.slice(0, 2).join(", ") || "Unknown Authors"} (
                          {paper?.year || "Year N/A"})
                        </div>

                        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginTop: "0.25rem" }}>
                          <span
                            style={{
                              fontSize: "0.72rem",
                              fontWeight: 600,
                              padding: "0.15rem 0.5rem",
                              borderRadius: "9999px",
                              background: isFullText
                                ? "#ecfdf5"
                                : isAbstract
                                ? "#fffbeb"
                                : "#f3f4f6",
                              color: isFullText ? "#047857" : isAbstract ? "#b45309" : "#4b5563",
                              border: isFullText
                                ? "1px solid #a7f3d0"
                                : isAbstract
                                ? "1px solid #fde68a"
                                : "1px solid #e5e7eb",
                            }}
                          >
                            {isFullText
                              ? "📄 Full Text Provenance"
                              : isAbstract
                              ? "📑 Abstract Only"
                              : "⚠️ Unavailable Text"}
                          </span>

                          <span
                            style={{
                              fontSize: "0.72rem",
                              padding: "0.15rem 0.5rem",
                              borderRadius: "9999px",
                              background: "#f3f4f6",
                              color: "#4b5563",
                              border: "1px solid #e5e7eb",
                            }}
                          >
                            {cov.categories_present.length}/9 Dimensions Grounded
                          </span>
                        </div>

                        {cov.source_quality_warning && (
                          <div
                            style={{
                              fontSize: "0.75rem",
                              color: "#92400e",
                              background: "#fffbeb",
                              border: "1px solid #fde68a",
                              padding: "0.4rem 0.6rem",
                              borderRadius: "4px",
                              marginTop: "0.35rem",
                              lineHeight: 1.45,
                            }}
                          >
                            {cov.source_quality_warning}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Comparison Statistics & Distributions */}
              {data.statistics && (
                <div
                  data-testid="comparison-statistics-card"
                  style={{
                    background: "#f9fafb",
                    border: "1px solid #e5e7eb",
                    borderRadius: "var(--radius-md)",
                    padding: "1.25rem",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      cursor: "pointer",
                    }}
                    onClick={() => setShowStatistics(!showStatistics)}
                  >
                    <div style={{ fontWeight: 700, color: "#1f2937", fontSize: "0.95rem" }}>
                      📊 Comparison Statistics & Scientific Distributions ({showStatistics ? "Collapse" : "Expand"})
                    </div>
                    <span style={{ color: "#6b7280" }}>{showStatistics ? "▲" : "▼"}</span>
                  </div>

                  {showStatistics && (
                    <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
                      {/* Metric Badges Row */}
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center" }}>
                        <div
                          style={{
                            background: "#ffffff",
                            border: "1px solid #e5e7eb",
                            borderRadius: "6px",
                            padding: "0.5rem 0.85rem",
                            fontSize: "0.82rem",
                          }}
                        >
                          <span style={{ color: "#6b7280", marginRight: "0.35rem" }}>Papers Evaluated:</span>
                          <strong style={{ color: "#1f2937" }}>{data.statistics.papers_compared}</strong>
                        </div>

                        {/* Year Distribution */}
                        <div
                          style={{
                            background: "#ffffff",
                            border: "1px solid #e5e7eb",
                            borderRadius: "6px",
                            padding: "0.5rem 0.85rem",
                            fontSize: "0.82rem",
                            display: "flex",
                            gap: "0.4rem",
                            alignItems: "center",
                          }}
                        >
                          <span style={{ color: "#6b7280" }}>Publication Years:</span>
                          {Object.entries(data.statistics.year_distribution || {}).map(([yr, count]) => (
                            <span
                              key={yr}
                              style={{
                                background: "#eff6ff",
                                color: "#1d4ed8",
                                border: "1px solid #bfdbfe",
                                borderRadius: "4px",
                                padding: "0.1rem 0.45rem",
                                fontWeight: 600,
                                fontSize: "0.75rem",
                              }}
                            >
                              {yr} ({count})
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* Sufficiency Notice if Insufficient */}
                      {!data.statistics.has_sufficient_data && data.statistics.data_sufficiency_note && (
                        <div
                          style={{
                            fontSize: "0.8rem",
                            color: "#b45309",
                            background: "#fffbeb",
                            border: "1px solid #fde68a",
                            padding: "0.5rem 0.75rem",
                            borderRadius: "6px",
                          }}
                        >
                          ℹ {data.statistics.data_sufficiency_note}
                        </div>
                      )}

                      {/* Two Column Grid: Methodologies & Datasets / Models */}
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "1fr 1fr",
                          gap: "1.25rem",
                        }}
                      >
                        {/* Methodologies */}
                        <div
                          style={{
                            background: "#ffffff",
                            border: "1px solid #e5e7eb",
                            borderRadius: "6px",
                            padding: "0.85rem",
                          }}
                        >
                          <div
                            style={{
                              fontSize: "0.74rem",
                              fontWeight: 700,
                              textTransform: "uppercase",
                              letterSpacing: "0.06em",
                              color: "#4b5563",
                              marginBottom: "0.45rem",
                            }}
                          >
                            Methodology Distribution
                          </div>
                          {Object.keys(data.statistics.methodology_distribution || {}).length === 0 ? (
                            <div style={{ fontSize: "0.8rem", color: "#6b7280", fontStyle: "italic" }}>
                              Unreported in available metadata
                            </div>
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                              {Object.entries(data.statistics.methodology_distribution).map(([method, count]) => (
                                <div
                                  key={method}
                                  style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    fontSize: "0.8rem",
                                    color: "#374151",
                                  }}
                                >
                                  <span>{method}</span>
                                  <strong style={{ color: "#059669" }}>{count}</strong>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Datasets & Models */}
                        <div
                          style={{
                            background: "#ffffff",
                            border: "1px solid #e5e7eb",
                            borderRadius: "6px",
                            padding: "0.85rem",
                          }}
                        >
                          <div
                            style={{
                              fontSize: "0.74rem",
                              fontWeight: 700,
                              textTransform: "uppercase",
                              letterSpacing: "0.06em",
                              color: "#4b5563",
                              marginBottom: "0.45rem",
                            }}
                          >
                            Dataset & Model Distribution
                          </div>
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                            {Object.entries(data.statistics.dataset_distribution || {}).slice(0, 3).map(([ds, count]) => (
                              <div
                                key={ds}
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  fontSize: "0.8rem",
                                  color: "#374151",
                                }}
                              >
                                <span style={{ textTransform: "capitalize" }}>Benchmark: {ds}</span>
                                <strong style={{ color: "#2563eb" }}>{count}</strong>
                              </div>
                            ))}
                            {Object.entries(data.statistics.model_distribution || {}).slice(0, 3).map(([model, count]) => (
                              <div
                                key={model}
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  fontSize: "0.8rem",
                                  color: "#374151",
                                }}
                              >
                                <span>Architecture: {model}</span>
                                <strong style={{ color: "#7c3aed" }}>{count}</strong>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>

                      {/* Common Limitations & Research Gaps Row */}
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "1fr 1fr",
                          gap: "1.25rem",
                        }}
                      >
                        {/* Common Limitations */}
                        <div
                          style={{
                            background: "#ffffff",
                            border: "1px solid #e5e7eb",
                            borderRadius: "6px",
                            padding: "0.85rem",
                          }}
                        >
                          <div
                            style={{
                              fontSize: "0.74rem",
                              fontWeight: 700,
                              textTransform: "uppercase",
                              letterSpacing: "0.06em",
                              color: "#dc2626",
                              marginBottom: "0.45rem",
                            }}
                          >
                            Common Limitations & Validity Threats
                          </div>
                          <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: "0.8rem", color: "#4b5563", lineHeight: 1.5 }}>
                            {data.statistics.common_limitations.slice(0, 3).map((lim, i) => (
                              <li key={i}>{lim}</li>
                            ))}
                          </ul>
                        </div>

                        {/* Research Gaps */}
                        <div
                          style={{
                            background: "#ffffff",
                            border: "1px solid #e5e7eb",
                            borderRadius: "6px",
                            padding: "0.85rem",
                          }}
                        >
                          <div
                            style={{
                              fontSize: "0.74rem",
                              fontWeight: 700,
                              textTransform: "uppercase",
                              letterSpacing: "0.06em",
                              color: "#d97706",
                              marginBottom: "0.45rem",
                            }}
                          >
                            Research Gaps & Open Directions
                          </div>
                          <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: "0.8rem", color: "#4b5563", lineHeight: 1.5 }}>
                            {data.statistics.research_gaps.slice(0, 3).map((gap, i) => (
                              <li key={i}>{gap}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Supported Similarities & Differences */}
              {((data.supported_similarities || []).length > 0 ||
                (data.supported_differences || []).length > 0) && (
                <div
                  style={{
                    background: "#f9fafb",
                    border: "1px solid #e5e7eb",
                    borderRadius: "var(--radius-md)",
                    padding: "1.25rem",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      cursor: "pointer",
                    }}
                    onClick={() => setShowInsights(!showInsights)}
                  >
                    <div style={{ fontWeight: 700, color: "#1f2937", fontSize: "0.95rem" }}>
                      🔍 Grounded Similarities & Differences ({showInsights ? "Collapse" : "Expand"})
                    </div>
                    <span style={{ color: "#6b7280" }}>{showInsights ? "▲" : "▼"}</span>
                  </div>

                  {showInsights && (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr",
                        gap: "1.25rem",
                        marginTop: "1rem",
                      }}
                    >
                      {/* Similarities */}
                      <div>
                        <div
                          style={{
                            fontSize: "0.75rem",
                            fontWeight: 700,
                            textTransform: "uppercase",
                            letterSpacing: "0.06em",
                            color: "#059669",
                            marginBottom: "0.5rem",
                          }}
                        >
                          ✓ Supported Similarities
                        </div>
                        {(data.supported_similarities || []).length === 0 ? (
                          <div style={{ fontSize: "0.85rem", color: "#6b7280" }}>
                            No identical methodology or venue similarities verified.
                          </div>
                        ) : (
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                            {data.supported_similarities?.map((s, idx) => (
                              <div
                                key={idx}
                                style={{
                                  background: "#ffffff",
                                  border: "1px solid #e5e7eb",
                                  borderRadius: "6px",
                                  padding: "0.75rem",
                                  fontSize: "0.85rem",
                                  color: "#374151",
                                  boxShadow: "0 1px 2px rgba(0, 0, 0, 0.03)",
                                }}
                              >
                                <strong style={{ color: "#059669", display: "block", marginBottom: "0.2rem" }}>
                                  {s.dimension}
                                </strong>
                                <div>{s.statement}</div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Differences */}
                      <div>
                        <div
                          style={{
                            fontSize: "0.75rem",
                            fontWeight: 700,
                            textTransform: "uppercase",
                            letterSpacing: "0.06em",
                            color: "#2563eb",
                            marginBottom: "0.5rem",
                          }}
                        >
                          ⚡ Supported Differences
                        </div>
                        {(data.supported_differences || []).length === 0 ? (
                          <div style={{ fontSize: "0.85rem", color: "#6b7280" }}>
                            No conflicting methodology claims identified.
                          </div>
                        ) : (
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                            {data.supported_differences?.map((d, idx) => (
                              <div
                                key={idx}
                                style={{
                                  background: "#ffffff",
                                  border: "1px solid #e5e7eb",
                                  borderRadius: "6px",
                                  padding: "0.75rem",
                                  fontSize: "0.85rem",
                                  color: "#374151",
                                  boxShadow: "0 1px 2px rgba(0, 0, 0, 0.03)",
                                }}
                              >
                                <strong style={{ color: "#2563eb", display: "block", marginBottom: "0.2rem" }}>
                                  {d.dimension}
                                </strong>
                                <div>{d.statement}</div>
                                {d.caveat && (
                                  <div
                                    style={{
                                      fontSize: "0.75rem",
                                      color: "#b45309",
                                      marginTop: "0.35rem",
                                      fontStyle: "italic",
                                    }}
                                  >
                                    {d.caveat}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Category Filter Tabs */}
              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  flexWrap: "wrap",
                  borderBottom: "1px solid #e5e7eb",
                  paddingBottom: "0.75rem",
                }}
              >
                {[
                  { id: "all", label: "All Dimensions (12)" },
                  { id: "scientific_evidence", label: "Scientific Evidence (9)" },
                  { id: "publication_metadata", label: "Publication & Metadata (2)" },
                  { id: "evidence_provenance", label: "Coverage & Provenance (1)" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setSelectedCategory(tab.id)}
                    style={{
                      background: selectedCategory === tab.id ? "#1f2937" : "#ffffff",
                      color: selectedCategory === tab.id ? "#ffffff" : "#4b5563",
                      border: "1px solid " + (selectedCategory === tab.id ? "#1f2937" : "#e5e7eb"),
                      padding: "0.45rem 0.95rem",
                      borderRadius: "6px",
                      fontSize: "0.82rem",
                      fontWeight: selectedCategory === tab.id ? 700 : 500,
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Detailed Dimension Cards */}
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                {filteredDimensions.map((dim) => {
                  const isIncomparable = dim.comparability_status === "incomparable_protocols";

                  return (
                    <div
                      key={dim.dimension_id}
                      data-testid={`dimension-card-${dim.dimension_id}`}
                      style={{
                        background: "#ffffff",
                        border: "1px solid #e5e7eb",
                        borderRadius: "var(--radius-md)",
                        padding: "1.25rem",
                        boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
                      }}
                    >
                      {/* Dimension Title & Status */}
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "flex-start",
                          marginBottom: "1rem",
                          borderBottom: "1px solid #e5e7eb",
                          paddingBottom: "0.75rem",
                        }}
                      >
                        <div>
                          <h4 style={{ margin: 0, fontSize: "1.05rem", color: "#1f2937", fontWeight: 700 }}>
                            {dim.dimension_title}
                          </h4>
                          {dim.comparability_note && (
                            <div style={{ fontSize: "0.78rem", color: "#b45309", marginTop: "0.25rem" }}>
                              ⚠️ {dim.comparability_note}
                            </div>
                          )}
                        </div>

                        <span
                          style={{
                            fontSize: "0.72rem",
                            fontWeight: 600,
                            padding: "0.2rem 0.6rem",
                            borderRadius: "9999px",
                            background: isIncomparable
                              ? "#fffbeb"
                              : "#ecfdf5",
                            color: isIncomparable ? "#b45309" : "#047857",
                            border: isIncomparable
                              ? "1px solid #fde68a"
                              : "1px solid #a7f3d0",
                          }}
                        >
                          {isIncomparable ? "Incomparable Protocols" : "Comparable"}
                        </span>
                      </div>

                      {/* Side-by-Side Paper Columns */}
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: `repeat(${data.papers.length}, minmax(240px, 1fr))`,
                          gap: "1rem",
                          overflowX: "auto",
                        }}
                      >
                        {data.papers.map((p) => {
                          const cell: ComparisonCell | undefined = dim.cells[p.paper_id];
                          const hasEvidence = cell?.has_evidence;
                          const cellKey = `${dim.dimension_id}_${p.paper_id}`;
                          const isExpanded = !!expandedPassages[cellKey];

                          return (
                            <div
                              key={p.paper_id}
                              style={{
                                background: "#f9fafb",
                                border: hasEvidence
                                  ? "1px solid #e5e7eb"
                                  : "1px dashed #d1d5db",
                                borderRadius: "8px",
                                padding: "1rem",
                                display: "flex",
                                flexDirection: "column",
                                justifyContent: "space-between",
                              }}
                            >
                              <div>
                                <div
                                  style={{
                                    fontSize: "0.75rem",
                                    color: "#6b7280",
                                    fontWeight: 600,
                                    marginBottom: "0.4rem",
                                  }}
                                >
                                  {p.title}
                                </div>

                                {/* Status Badge */}
                                <div style={{ marginBottom: "0.6rem" }}>
                                  <span
                                    style={{
                                      fontSize: "0.68rem",
                                      fontWeight: 600,
                                      padding: "0.15rem 0.45rem",
                                      borderRadius: "4px",
                                      background:
                                        cell?.status === "supported"
                                          ? "#ecfdf5"
                                          : cell?.status === "missing_evidence"
                                          ? "#f3f4f6"
                                          : cell?.status === "stale"
                                          ? "#fef2f2"
                                          : "#eff6ff",
                                      color:
                                        cell?.status === "supported"
                                          ? "#047857"
                                          : cell?.status === "missing_evidence"
                                          ? "#6b7280"
                                          : cell?.status === "stale"
                                          ? "#b91c1c"
                                          : "#1d4ed8",
                                      border:
                                        cell?.status === "supported"
                                          ? "1px solid #a7f3d0"
                                          : cell?.status === "missing_evidence"
                                          ? "1px solid #e5e7eb"
                                          : cell?.status === "stale"
                                          ? "1px solid #fecaca"
                                          : "1px solid #bfdbfe",
                                    }}
                                  >
                                    {cell?.status === "supported"
                                      ? "✓ Grounded Claim"
                                      : cell?.status === "missing_evidence"
                                      ? "— Unreported in Text"
                                      : cell?.status === "stale"
                                      ? "⚠️ Stale Record"
                                      : "ℹ Metadata Fact"}
                                  </span>
                                </div>

                                {/* Claim Statement */}
                                {hasEvidence && cell?.claim ? (
                                  <div
                                    style={{
                                      color: "#1f2937",
                                      fontSize: "0.88rem",
                                      lineHeight: 1.6,
                                      marginBottom: "0.75rem",
                                    }}
                                  >
                                    “{cell.claim}”
                                  </div>
                                ) : (
                                  <div
                                    style={{
                                      color: "#6b7280",
                                      fontSize: "0.82rem",
                                      fontStyle: "italic",
                                      lineHeight: 1.5,
                                      marginBottom: "0.75rem",
                                    }}
                                  >
                                    {cell?.status_note || "Not reported in available text."}
                                  </div>
                                )}
                              </div>

                              {/* Supporting Passage Toggle */}
                              {cell?.source_passage && (
                                <div style={{ marginTop: "0.5rem" }}>
                                  <button
                                    onClick={() => togglePassage(cellKey)}
                                    style={{
                                      background: "#ffffff",
                                      border: "1px solid #d1d5db",
                                      color: "#1f2937",
                                      padding: "0.3rem 0.6rem",
                                      borderRadius: "4px",
                                      fontSize: "0.74rem",
                                      cursor: "pointer",
                                      display: "flex",
                                      alignItems: "center",
                                      gap: "0.3rem",
                                    }}
                                  >
                                    {isExpanded ? "▲ Hide Source Passage" : "▼ Inspect Supporting Passage"}
                                  </button>

                                  {isExpanded && (
                                    <div
                                      data-testid={`expanded-passage-${cellKey}`}
                                      style={{
                                        marginTop: "0.5rem",
                                        background: "#ffffff",
                                        border: "1px solid #e5e7eb",
                                        borderRadius: "6px",
                                        padding: "0.65rem 0.8rem",
                                        fontSize: "0.8rem",
                                        color: "#374151",
                                        lineHeight: 1.55,
                                        boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
                                      }}
                                    >
                                      <div
                                        style={{
                                          fontSize: "0.7rem",
                                          color: "#059669",
                                          fontWeight: 600,
                                          marginBottom: "0.25rem",
                                        }}
                                      >
                                        Exact Source Passage (
                                        {cell.source_type === "full_text" ? "Full Text" : "Abstract"}
                                        {cell.section_name ? ` • Section: ${cell.section_name}` : ""}
                                        {cell.page_number ? ` • Page: ${cell.page_number}` : ""})
                                      </div>
                                      <div style={{ fontStyle: "italic", marginBottom: "0.4rem" }}>
                                        “{cell.source_passage}”
                                      </div>
                                      <div style={{ fontSize: "0.68rem", color: "#6b7280" }}>
                                        Character Offsets: [{cell.char_start} : {cell.char_end}]
                                        {cell.confidence_score
                                          ? ` • Match Confidence: ${Math.round(cell.confidence_score * 100)}%`
                                          : ""}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
