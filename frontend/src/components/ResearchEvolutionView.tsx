import React, { useState, useEffect } from "react";
import type {
  TimelineResponse,
  TimelinePaper,
  RelationshipGraphResponse,
  GraphEdge,
  GapExplorationResponse,
  CandidateGap,
  ResearchAssistantResponse,
  AssistantEvidenceItem,
  AssistantClaim,
  AIProviderStatus,
} from "../types/research";
import {
  getResearchTimeline,
  getRelationshipGraph,
  postCandidateGaps,
  askResearchAssistant,
  getAIStatus,
} from "../services/api";
import { SearchIcon, EvolutionIcon } from "./icons/Icons";

interface ResearchEvolutionViewProps {
  initialTopic?: string;
  onOpenCompare?: (paperIds: (number | string)[]) => void;
}

export default function ResearchEvolutionView({
  initialTopic = "",
  onOpenCompare,
}: ResearchEvolutionViewProps) {
  // Navigation & Sub-views
  const [activeSubTab, setActiveSubTab] = useState<"timeline" | "graph" | "gaps" | "assistant">("timeline");

  // Filters & Parameters
  const [topic, setTopic] = useState<string>(initialTopic);
  const [startYear, setStartYear] = useState<string>("");
  const [endYear, setEndYear] = useState<string>("");
  const [minSimilarity, setMinSimilarity] = useState<number>(0.45);
  const [maxNodes, setMaxNodes] = useState<number>(20);
  const [minCorpusSize, setMinCorpusSize] = useState<number>(3);

  // Data states
  const [timelineData, setTimelineData] = useState<TimelineResponse | null>(null);
  const [graphData, setGraphData] = useState<RelationshipGraphResponse | null>(null);
  const [gapData, setGapData] = useState<GapExplorationResponse | null>(null);

  // Assistant states (TASK-17)
  const [assistantQuestion, setAssistantQuestion] = useState<string>("");
  const [assistantData, setAssistantData] = useState<ResearchAssistantResponse | null>(null);
  const [assistantLoading, setAssistantLoading] = useState<boolean>(false);
  const [assistantError, setAssistantError] = useState<string | null>(null);
  const [aiStatus, setAiStatus] = useState<AIProviderStatus | null>(null);

  useEffect(() => {
    getAIStatus().then(setAiStatus).catch(() => {});
  }, []);

  // UI interaction states
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedQuotes, setExpandedQuotes] = useState<Record<string, boolean>>({});
  const [edgeFilter, setEdgeFilter] = useState<string>("ALL");
  const [graphViewMode, setGraphViewMode] = useState<"list" | "matrix">("list");

  // Toggle quote expansion
  const toggleQuote = (key: string) => {
    setExpandedQuotes((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Assistant submit handler (TASK-17)
  const handleAskAssistant = async (customQ?: string) => {
    const q = (customQ !== undefined ? customQ : assistantQuestion).trim();
    if (!q) return;
    if (customQ !== undefined) {
      setAssistantQuestion(customQ);
    }
    setAssistantLoading(true);
    setAssistantError(null);
    try {
      const resp = await askResearchAssistant({
        question: q,
        topic: topic || undefined,
        max_evidence_items: 8,
      });
      setAssistantData(resp);
    } catch (err: any) {
      setAssistantError(err.message || "Failed to query Grounded Research Assistant");
    } finally {
      setAssistantLoading(false);
    }
  };

  // Fetch data for the active sub-tab
  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const sYear = startYear ? parseInt(startYear, 10) : undefined;
      const eYear = endYear ? parseInt(endYear, 10) : undefined;

      if (activeSubTab === "timeline") {
        const res = await getResearchTimeline({
          topic: topic.trim() || undefined,
          start_year: sYear,
          end_year: eYear,
          limit: 40,
        });
        setTimelineData(res);
      } else if (activeSubTab === "graph") {
        const res = await getRelationshipGraph({
          topic: topic.trim() || undefined,
          start_year: sYear,
          end_year: eYear,
          min_similarity: minSimilarity,
          max_nodes: maxNodes,
        });
        setGraphData(res);
      } else if (activeSubTab === "gaps") {
        const res = await postCandidateGaps({
          topic: topic.trim() || undefined,
          start_year: sYear,
          end_year: eYear,
          min_corpus_size: minCorpusSize,
          max_gaps: 12,
        });
        setGapData(res);
      }
    } catch (err: any) {
      setError(err.message || "Failed to retrieve research evolution data.");
    } finally {
      setLoading(false);
    }
  };

  // Load when active tab or search trigger changes
  useEffect(() => {
    fetchData();
  }, [activeSubTab]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchData();
  };

  // Filter edges for relationship explorer
  const filteredEdges = (graphData?.edges || []).filter((edge) => {
    if (edgeFilter === "ALL") return true;
    if (edgeFilter === "AUTHOR_STATED") return edge.is_author_stated;
    if (edgeFilter === "INFERRED") return edge.relationship_status === "inferred_evidence";
    if (edgeFilter === "THEMATIC_ONLY") return edge.relationship_status === "thematic_only";
    return edge.relationship_type.toUpperCase() === edgeFilter.toUpperCase();
  });

  return (
    <div className="research-evolution-container" style={{ padding: "1.5rem 0", maxWidth: "1200px", margin: "0 auto" }}>
      {/* Header Banner */}
      <div
        style={{
          background: "#ffffff",
          border: "1px solid #e5e7eb",
          borderRadius: "var(--radius-lg)",
          padding: "1.75rem",
          marginBottom: "1.75rem",
          boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
              <h2 style={{ margin: 0, color: "var(--text-primary)", fontSize: "1.45rem", fontWeight: 700, fontFamily: "var(--font-serif)" }}>
                Research Evolution &amp; Gap Explorer
              </h2>
            </div>
            <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "0.88rem", maxWidth: "780px", lineHeight: 1.5 }}>
              Chronological methodological lineages, inter-paper relationship discovery, and grounded research-gap exploration.
              Strictly separates observed source evidence from candidate hypotheses.
            </p>
          </div>

          {/* Sub-view Navigation Tabs */}
          <div
            className="nav-tabs"
            style={{
              display: "flex",
              background: "var(--bg-subtle)",
              padding: "0.25rem",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-leaf)",
              gap: "0.25rem",
            }}
          >
            <button
              type="button"
              onClick={() => setActiveSubTab("timeline")}
              className={`nav-tab-btn ${activeSubTab === "timeline" ? "active" : ""}`}
              style={{ padding: "0.4rem 0.85rem", fontSize: "0.84rem", cursor: "pointer" }}
            >
              Timeline
            </button>
            <button
              type="button"
              onClick={() => setActiveSubTab("graph")}
              className={`nav-tab-btn ${activeSubTab === "graph" ? "active" : ""}`}
              style={{ padding: "0.4rem 0.85rem", fontSize: "0.84rem", cursor: "pointer" }}
            >
              Relationship Graph
            </button>
            <button
              type="button"
              onClick={() => setActiveSubTab("gaps")}
              className={`nav-tab-btn ${activeSubTab === "gaps" ? "active" : ""}`}
              style={{ padding: "0.4rem 0.85rem", fontSize: "0.84rem", cursor: "pointer" }}
            >
              Gap Discovery
            </button>
            <button
              type="button"
              onClick={() => setActiveSubTab("assistant")}
              className={`nav-tab-btn ${activeSubTab === "assistant" ? "active" : ""}`}
              style={{ padding: "0.4rem 0.85rem", fontSize: "0.84rem", cursor: "pointer" }}
            >
              Assistant
            </button>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <form
          onSubmit={handleSearchSubmit}
          style={{
            marginTop: "1.25rem",
            display: "flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "0.75rem",
            background: "var(--bg-subtle)",
            padding: "0.75rem 1rem",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-leaf)",
          }}
        >
          <div style={{ flex: "1 1 240px", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ color: "var(--text-muted)", display: "flex", alignItems: "center" }}><SearchIcon size={14} /></span>
            <input
              type="text"
              placeholder="Topic or methodology (e.g. Transformers, BERT, Vision)..."
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              style={{
                width: "100%",
                background: "transparent",
                border: "none",
                color: "#1f2937",
                fontSize: "0.88rem",
                outline: "none",
              }}
            />
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <label style={{ fontSize: "0.78rem", color: "#4b5563" }}>Years:</label>
            <input
              type="number"
              placeholder="From (1900)"
              value={startYear}
              onChange={(e) => setStartYear(e.target.value)}
              style={{
                width: "90px",
                background: "#ffffff",
                border: "1px solid #d1d5db",
                color: "#1f2937",
                fontSize: "0.82rem",
                padding: "0.3rem 0.5rem",
                borderRadius: "var(--radius-sm)",
              }}
            />
            <span style={{ color: "#9ca3af" }}>–</span>
            <input
              type="number"
              placeholder="To (2030)"
              value={endYear}
              onChange={(e) => setEndYear(e.target.value)}
              style={{
                width: "90px",
                background: "#ffffff",
                border: "1px solid #d1d5db",
                color: "#1f2937",
                fontSize: "0.82rem",
                padding: "0.3rem 0.5rem",
                borderRadius: "var(--radius-sm)",
              }}
            />
          </div>

          {activeSubTab === "graph" && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <label style={{ fontSize: "0.78rem", color: "#4b5563" }}>
                Sim &gt;= {(minSimilarity * 100).toFixed(0)}%:
              </label>
              <input
                type="range"
                min="0.30"
                max="0.80"
                step="0.05"
                value={minSimilarity}
                onChange={(e) => setMinSimilarity(parseFloat(e.target.value))}
                style={{ width: "80px", accentColor: "#1f2937" }}
              />
            </div>
          )}

          {activeSubTab === "gaps" && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <label style={{ fontSize: "0.78rem", color: "#4b5563" }}>Min Corpus:</label>
              <select
                value={minCorpusSize}
                onChange={(e) => setMinCorpusSize(parseInt(e.target.value, 10))}
                style={{
                  background: "#ffffff",
                  border: "1px solid #d1d5db",
                  color: "#1f2937",
                  fontSize: "0.82rem",
                  padding: "0.3rem 0.5rem",
                  borderRadius: "var(--radius-sm)",
                }}
              >
                <option value={2}>2 papers</option>
                <option value={3}>3 papers (default)</option>
                <option value={5}>5 papers (strict)</option>
              </select>
            </div>
          )}

          <button
            type="submit"
            className="btn-primary"
            disabled={loading}
            style={{
              padding: "0.4rem 1rem",
              fontSize: "0.85rem",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              cursor: "pointer",
            }}
          >
            {loading ? "Searching..." : "Apply Filter"}
          </button>
        </form>

        {/* Quick Topic Chips */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>Suggestions:</span>
          {["BERT", "Transformers", "Pre-training", "GLUE", "Genomics", "All"].map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => {
                const val = chip === "All" ? "" : chip;
                setTopic(val);
              }}
              style={{
                background: "#f3f4f6",
                border: "1px solid #e5e7eb",
                color: "#374151",
                fontSize: "0.72rem",
                padding: "0.2rem 0.5rem",
                borderRadius: "999px",
                cursor: "pointer",
              }}
            >
              {chip}
            </button>
          ))}
        </div>
      </div>

      {/* Loading & Error States */}
      {loading && (
        <div style={{ textAlign: "center", padding: "3rem", color: "#4b5563" }}>
          <div className="spinner" style={{ margin: "0 auto 1rem", width: "32px", height: "32px" }}></div>
          <p style={{ margin: 0, fontSize: "0.95rem" }}>Analyzing research lineage and synthesizing grounded claims...</p>
        </div>
      )}

      {error && (
        <div
          style={{
            background: "#fef2f2",
            border: "1px solid #fecaca",
            color: "#b91c1c",
            padding: "1rem",
            borderRadius: "var(--radius-md)",
            marginBottom: "1.5rem",
          }}
        >
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* ===================================================================== */}
      {/* 1. TIMELINE SUB-VIEW */}
      {/* ===================================================================== */}
      {!loading && activeSubTab === "timeline" && timelineData && (
        <div>
          {/* Disclaimer & Summary Banner */}
          <div
            style={{
              background: "#f9fafb",
              border: "1px solid #e5e7eb",
              borderRadius: "var(--radius-md)",
              padding: "0.85rem 1.25rem",
              marginBottom: "1.5rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <div style={{ fontSize: "0.85rem", color: "#4b5563" }}>
              <span>Total Papers: <strong>{timelineData.total_papers_examined}</strong></span>
              <span style={{ margin: "0 0.5rem" }}>•</span>
              <span>Dated: <strong>{timelineData.total_dated_papers}</strong></span>
              <span style={{ margin: "0 0.5rem" }}>•</span>
              <span>Undated: <strong>{timelineData.total_undated_papers}</strong></span>
              {timelineData.coverage_notes && (
                <span style={{ display: "block", marginTop: "0.25rem", color: "#6b7280", fontSize: "0.78rem" }}>
                  ℹ️ {timelineData.coverage_notes}
                </span>
              )}
            </div>
            <div
              style={{
                fontSize: "0.75rem",
                color: "#4b5563",
                background: "#ffffff",
                border: "1px solid #e5e7eb",
                padding: "0.3rem 0.6rem",
                borderRadius: "var(--radius-sm)",
                maxWidth: "500px",
                lineHeight: 1.4,
              }}
            >
              ⚠️ {timelineData.disclaimer}
            </div>
          </div>

          {timelineData.timeline.length === 0 ? (
            <div style={{ textAlign: "center", padding: "3rem", color: "#6b7280" }}>
              <span style={{ fontSize: "2rem" }}>📭</span>
              <p style={{ marginTop: "0.5rem" }}>No papers found in local catalog matching this criteria.</p>
            </div>
          ) : (
            <div className="timeline-stream" style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
              {timelineData.timeline.map((group, gIdx) => (
                <div key={group.year_label || gIdx} className="timeline-year-block">
                  {/* Year Header Marker */}
                  <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1rem" }}>
                    <div
                      style={{
                        background: group.year ? "#1f2937" : "#6b7280",
                        color: "#ffffff",
                        fontWeight: 700,
                        fontSize: "1rem",
                        padding: "0.3rem 0.9rem",
                        borderRadius: "999px",
                        boxShadow: "0 1px 3px rgba(0, 0, 0, 0.1)",
                      }}
                    >
                      {group.year_label}
                    </div>
                    <div style={{ fontSize: "0.85rem", color: "#6b7280" }}>
                      {group.paper_count} paper{group.paper_count !== 1 ? "s" : ""}
                    </div>
                    {group.key_themes.length > 0 && (
                      <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                        {group.key_themes.map((th) => (
                          <span
                            key={th}
                            style={{
                              fontSize: "0.72rem",
                              background: "#f3f4f6",
                              color: "#374151",
                              border: "1px solid #e5e7eb",
                              padding: "0.15rem 0.45rem",
                              borderRadius: "4px",
                            }}
                          >
                            #{th}
                          </span>
                        ))}
                      </div>
                    )}
                    <div style={{ flex: 1, height: "1px", background: "#e5e7eb" }}></div>
                  </div>

                  {/* Papers under this year group */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", paddingLeft: "1.5rem", borderLeft: "2px dashed #d1d5db" }}>
                    {group.papers.map((paper: TimelinePaper) => (
                      <div
                        key={paper.id}
                        className="timeline-paper-card"
                        style={{
                          background: "#ffffff",
                          border: "1px solid #e5e7eb",
                          borderRadius: "var(--radius-md)",
                          padding: "1.25rem",
                          boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
                        }}
                      >
                        {/* Title, Authors, Venue */}
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem" }}>
                          <div>
                            <h4 style={{ margin: "0 0 0.35rem", color: "#1f2937", fontSize: "1.05rem", fontWeight: 600 }}>
                              {paper.title}
                            </h4>
                            <div style={{ fontSize: "0.82rem", color: "#6b7280", display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                              <span>👥 {paper.authors.length > 0 ? paper.authors.join(", ") : "Authors Unrecorded"}</span>
                              {paper.venue && <span>🏛️ {paper.venue}</span>}
                              {paper.is_undated && (
                                <span style={{ color: "#d97706", fontWeight: 600 }}>
                                  ⚠️ Undated in catalog
                                </span>
                              )}
                            </div>
                          </div>
                          <span
                            style={{
                              fontSize: "0.72rem",
                              padding: "0.2rem 0.5rem",
                              borderRadius: "4px",
                              background: paper.provenance_source === "full_text" ? "#ecfdf5" : "#f3f4f6",
                              color: paper.provenance_source === "full_text" ? "#047857" : "#4b5563",
                              border: `1px solid ${paper.provenance_source === "full_text" ? "#a7f3d0" : "#e5e7eb"}`,
                              fontWeight: 600,
                            }}
                          >
                            {paper.provenance_source === "full_text" ? "Full Text Provenance" : "Abstract Verified"}
                          </span>
                        </div>

                        {/* Claims Grid */}
                        <div
                          style={{
                            marginTop: "1rem",
                            display: "grid",
                            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                            gap: "0.85rem",
                          }}
                        >
                          {/* Methodological Changes */}
                          {paper.method_changes.length > 0 && (
                            <div style={{ background: "#f9fafb", border: "1px solid #e5e7eb", padding: "0.75rem", borderRadius: "6px" }}>
                              <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#1f2937", marginBottom: "0.3rem" }}>
                                🛠️ Proposed Method &amp; Approach:
                              </div>
                              {paper.method_changes.slice(0, 2).map((m, idx) => (
                                <div key={idx} style={{ fontSize: "0.8rem", color: "#374151", marginBottom: "0.25rem" }}>
                                  • {m.claim}
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Findings & Results */}
                          {paper.findings_claims.length > 0 && (
                            <div style={{ background: "#f9fafb", border: "1px solid #e5e7eb", padding: "0.75rem", borderRadius: "6px" }}>
                              <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#047857", marginBottom: "0.3rem" }}>
                                📈 Reported Results &amp; Findings:
                              </div>
                              {paper.findings_claims.slice(0, 2).map((r, idx) => (
                                <div key={idx} style={{ fontSize: "0.8rem", color: "#374151", marginBottom: "0.25rem" }}>
                                  • {r.claim}
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Limitations */}
                          {paper.limitation_claims.length > 0 && (
                            <div style={{ background: "#fffbeb", border: "1px solid #fde68a", padding: "0.75rem", borderRadius: "6px" }}>
                              <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#b45309", marginBottom: "0.3rem" }}>
                                ⚠️ Stated Limitations:
                              </div>
                              {paper.limitation_claims.slice(0, 2).map((l, idx) => (
                                <div key={idx} style={{ fontSize: "0.8rem", color: "#92400e", marginBottom: "0.25rem" }}>
                                  • {l.claim}
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Future Work */}
                          {paper.future_work_claims.length > 0 && (
                            <div style={{ background: "#f0f9ff", border: "1px solid #bae6fd", padding: "0.75rem", borderRadius: "6px" }}>
                              <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#0284c7", marginBottom: "0.3rem" }}>
                                🔭 Future Work Directions:
                              </div>
                              {paper.future_work_claims.slice(0, 2).map((fw, idx) => (
                                <div key={idx} style={{ fontSize: "0.8rem", color: "#0369a1", marginBottom: "0.25rem" }}>
                                  • {fw.claim}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Expandable Source Evidence Passages */}
                        <div style={{ marginTop: "0.75rem" }}>
                          <button
                            type="button"
                            onClick={() => toggleQuote(`paper-${paper.id}`)}
                            style={{
                              background: "none",
                              border: "none",
                              color: "#1f2937",
                              fontSize: "0.78rem",
                              cursor: "pointer",
                              padding: 0,
                              fontWeight: 600,
                            }}
                          >
                            {expandedQuotes[`paper-${paper.id}`] ? "▲ Hide supporting source passages" : "▼ Inspect exact supporting source passages"}
                          </button>

                          {expandedQuotes[`paper-${paper.id}`] && (
                            <div
                              style={{
                                marginTop: "0.5rem",
                                padding: "0.75rem",
                                background: "#f9fafb",
                                borderRadius: "4px",
                                border: "1px solid #e5e7eb",
                                borderLeft: "3px solid #1f2937",
                                fontSize: "0.8rem",
                                color: "#374151",
                                lineHeight: 1.5,
                              }}
                            >
                              <div style={{ fontWeight: 600, color: "#1f2937", marginBottom: "0.25rem" }}>
                                Verified Source Passages:
                              </div>
                              {[...paper.method_changes, ...paper.findings_claims, ...paper.limitation_claims, ...paper.future_work_claims].slice(0, 4).map((c, cIdx) => (
                                <div key={cIdx} style={{ marginBottom: "0.5rem" }}>
                                  <span style={{ color: "#6b7280", fontSize: "0.72rem" }}>
                                    [{c.category.toUpperCase()}] {c.section_name ? `(${c.section_name})` : ""}
                                    {c.char_start !== null ? ` [offset: ${c.char_start}-${c.char_end}]` : ""}:
                                  </span>
                                  <div style={{ fontStyle: "italic", color: "#374151" }}>"{c.source_passage}"</div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Related Paper Links */}
                        {paper.related_links.length > 0 && (
                          <div
                            style={{
                              marginTop: "0.75rem",
                              paddingTop: "0.75rem",
                              borderTop: "1px solid #e5e7eb",
                              display: "flex",
                              alignItems: "center",
                              gap: "0.5rem",
                              flexWrap: "wrap",
                            }}
                          >
                            <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>Linked to:</span>
                            {paper.related_links.map((link, lIdx) => (
                              <span
                                key={lIdx}
                                style={{
                                  fontSize: "0.75rem",
                                  padding: "0.2rem 0.5rem",
                                  borderRadius: "4px",
                                  background: link.is_author_stated ? "#ecfdf5" : "#f3f4f6",
                                  color: link.is_author_stated ? "#047857" : "#4b5563",
                                  border: `1px solid ${link.is_author_stated ? "#a7f3d0" : "#e5e7eb"}`,
                                }}
                                title={link.evidence_quote || "Related via topical affinity"}
                              >
                                {link.relationship_type} → {link.target_paper_title.slice(0, 35)}...
                                <span style={{ fontSize: "0.68rem", opacity: 0.8, marginLeft: "4px" }}>
                                  ({link.relationship_status === "author_stated" ? "Author-Stated" : "Inferred"})
                                </span>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ===================================================================== */}
      {/* 2. RELATIONSHIP GRAPH & EXPLORER SUB-VIEW */}
      {/* ===================================================================== */}
      {!loading && activeSubTab === "graph" && graphData && (
        <div>
          {/* Disclaimer Banner */}
          <div
            style={{
              background: "#f9fafb",
              border: "1px solid #e5e7eb",
              borderRadius: "var(--radius-md)",
              padding: "0.85rem 1.25rem",
              marginBottom: "1.25rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <div style={{ fontSize: "0.85rem", color: "#4b5563" }}>
              <span>Catalog Nodes: <strong>{graphData.total_nodes}</strong></span>
              <span style={{ margin: "0 0.5rem" }}>•</span>
              <span>Discovered Edges: <strong>{graphData.total_edges}</strong></span>
              {graphData.coverage_notes && (
                <span style={{ display: "block", marginTop: "0.25rem", color: "#6b7280", fontSize: "0.78rem" }}>
                  ℹ️ {graphData.coverage_notes}
                </span>
              )}
            </div>
            <div
              style={{
                fontSize: "0.75rem",
                color: "#4b5563",
                background: "#ffffff",
                border: "1px solid #e5e7eb",
                padding: "0.3rem 0.6rem",
                borderRadius: "var(--radius-sm)",
                maxWidth: "520px",
                lineHeight: 1.4,
              }}
            >
              ⚠️ {graphData.disclaimer}
            </div>
          </div>

          {/* Relationship Filter Bar */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "1rem",
              flexWrap: "wrap",
              gap: "0.5rem",
            }}
          >
            <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
              {[
                { label: "All Edges", val: "ALL" },
                { label: "Author-Stated", val: "AUTHOR_STATED" },
                { label: "Inferred Evidence", val: "INFERRED" },
                { label: "Thematic Only", val: "THEMATIC_ONLY" },
                { label: "Extension", val: "EXTENSION" },
                { label: "Improvement", val: "IMPROVEMENT" },
                { label: "Alternative", val: "ALTERNATIVE" },
              ].map((f) => (
                <button
                  key={f.val}
                  type="button"
                  onClick={() => setEdgeFilter(f.val)}
                  style={{
                    background: edgeFilter === f.val ? "#1f2937" : "#ffffff",
                    color: edgeFilter === f.val ? "#ffffff" : "#4b5563",
                    border: `1px solid ${edgeFilter === f.val ? "#1f2937" : "#d1d5db"}`,
                    fontSize: "0.75rem",
                    padding: "0.25rem 0.65rem",
                    borderRadius: "999px",
                    fontWeight: edgeFilter === f.val ? 700 : 500,
                    cursor: "pointer",
                  }}
                >
                  {f.label}
                </button>
              ))}
            </div>

            <div style={{ display: "flex", gap: "0.4rem" }}>
              <button
                type="button"
                onClick={() => setGraphViewMode("list")}
                style={{
                  background: graphViewMode === "list" ? "#1f2937" : "#ffffff",
                  border: `1px solid ${graphViewMode === "list" ? "#1f2937" : "#d1d5db"}`,
                  color: graphViewMode === "list" ? "#ffffff" : "#4b5563",
                  fontSize: "0.78rem",
                  padding: "0.25rem 0.5rem",
                  borderRadius: "4px",
                  cursor: "pointer",
                }}
              >
                🗂️ Relational Cards
              </button>
              <button
                type="button"
                onClick={() => setGraphViewMode("matrix")}
                style={{
                  background: graphViewMode === "matrix" ? "#1f2937" : "#ffffff",
                  border: `1px solid ${graphViewMode === "matrix" ? "#1f2937" : "#d1d5db"}`,
                  color: graphViewMode === "matrix" ? "#ffffff" : "#4b5563",
                  fontSize: "0.78rem",
                  padding: "0.25rem 0.5rem",
                  borderRadius: "4px",
                  cursor: "pointer",
                }}
              >
                🌐 Graph Matrix
              </button>
            </div>
          </div>

          {filteredEdges.length === 0 ? (
            <div style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
              <div style={{ display: "flex", justifyContent: "center", marginBottom: "0.5rem", color: "var(--text-muted)" }}>
                <EvolutionIcon size={36} />
              </div>
              <p style={{ marginTop: "0.5rem" }}>No relationship edges match current filter criteria.</p>
            </div>
          ) : graphViewMode === "list" ? (
            /* Accessible Relational List Cards */
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {filteredEdges.map((edge: GraphEdge, eIdx: number) => {
                const isAuthor = edge.is_author_stated;
                const isThematic = edge.relationship_status === "thematic_only";

                return (
                  <div
                    key={`${edge.source}-${edge.target}-${eIdx}`}
                    className="relationship-edge-card"
                    style={{
                      background: "#ffffff",
                      border: "1px solid #e5e7eb",
                      borderRadius: "var(--radius-md)",
                      padding: "1.25rem",
                      boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "0.5rem" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                        <span
                          style={{
                            fontSize: "0.75rem",
                            fontWeight: 700,
                            padding: "0.2rem 0.6rem",
                            borderRadius: "999px",
                            background: isAuthor ? "#ecfdf5" : isThematic ? "#f3f4f6" : "#fffbeb",
                            color: isAuthor ? "#047857" : isThematic ? "#4b5563" : "#b45309",
                            border: `1px solid ${isAuthor ? "#a7f3d0" : isThematic ? "#e5e7eb" : "#fde68a"}`,
                          }}
                        >
                          {edge.relationship_type}
                        </span>
                        <span
                          style={{
                            fontSize: "0.72rem",
                            padding: "0.15rem 0.5rem",
                            borderRadius: "4px",
                            background: "#f9fafb",
                            color: "#4b5563",
                            border: "1px solid #e5e7eb",
                          }}
                        >
                          {isAuthor ? "Explicit Author Statement" : isThematic ? "Thematic Proximity Only" : "Inferred Scientific Evidence"}
                        </span>
                      </div>

                      <div style={{ fontSize: "0.78rem", color: "#6b7280" }}>
                        Topical Similarity: <strong>{(edge.semantic_similarity * 100).toFixed(1)}%</strong>
                        <span style={{ margin: "0 0.4rem" }}>•</span>
                        Confidence: <strong>{(edge.confidence_score * 100).toFixed(0)}%</strong>
                      </div>
                    </div>

                    {/* Source and Target Nodes */}
                    <div style={{ marginTop: "0.85rem", display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
                      <div style={{ flex: 1, minWidth: "220px", background: "#f9fafb", border: "1px solid #e5e7eb", padding: "0.6rem", borderRadius: "6px" }}>
                        <div style={{ fontSize: "0.7rem", color: "#6b7280", textTransform: "uppercase" }}>Candidate / Subject Paper:</div>
                        <div style={{ fontSize: "0.88rem", color: "#1f2937", fontWeight: 600 }}>{edge.source_title}</div>
                      </div>

                      <span style={{ fontSize: "1.2rem", color: "#1f2937" }}>➔</span>

                      <div style={{ flex: 1, minWidth: "220px", background: "#f9fafb", border: "1px solid #e5e7eb", padding: "0.6rem", borderRadius: "6px" }}>
                        <div style={{ fontSize: "0.7rem", color: "#6b7280", textTransform: "uppercase" }}>Baseline / Target Paper:</div>
                        <div style={{ fontSize: "0.88rem", color: "#1f2937", fontWeight: 600 }}>{edge.target_title}</div>
                      </div>
                    </div>

                    {/* Explanation */}
                    <p style={{ margin: "0.75rem 0 0.5rem", fontSize: "0.84rem", color: "#374151", lineHeight: 1.5 }}>
                      {edge.explanation}
                    </p>

                    {/* Grounded Evidence Passage if available */}
                    {edge.evidence_passage && (
                      <div
                        style={{
                          marginTop: "0.5rem",
                          padding: "0.6rem 0.8rem",
                          background: "#f9fafb",
                          border: "1px solid #e5e7eb",
                          borderLeft: "3px solid #1f2937",
                          borderRadius: "4px",
                          fontSize: "0.8rem",
                          color: "#374151",
                          fontStyle: "italic",
                        }}
                      >
                        "{edge.evidence_passage}"
                        <div style={{ fontSize: "0.7rem", color: "#6b7280", marginTop: "0.25rem", fontStyle: "normal" }}>
                          Verified in {edge.section_name || "Abstract"}
                          {edge.char_start !== null ? ` (char offsets: ${edge.char_start}-${edge.char_end})` : ""}
                        </div>
                      </div>
                    )}

                    {/* Warnings & Incompatibility Notes */}
                    {edge.uncertainty_warning && (
                      <div style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "#b45309" }}>
                        ⚠️ {edge.uncertainty_warning}
                      </div>
                    )}
                    {edge.comparability_notes && (
                      <div style={{ marginTop: "0.25rem", fontSize: "0.75rem", color: "#dc2626" }}>
                        ℹ️ {edge.comparability_notes}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            /* Graph Matrix Overview */
            <div
              style={{
                background: "#ffffff",
                border: "1px solid #e5e7eb",
                borderRadius: "var(--radius-md)",
                padding: "1.25rem",
                overflowX: "auto",
                boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
              }}
            >
              <h4 style={{ margin: "0 0 1rem", color: "#1f2937" }}>Inter-Paper Relationship Connectivity Matrix</h4>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e5e7eb", color: "#4b5563" }}>
                    <th style={{ textAlign: "left", padding: "0.5rem" }}>Candidate Paper</th>
                    <th style={{ textAlign: "left", padding: "0.5rem" }}>Relationship</th>
                    <th style={{ textAlign: "left", padding: "0.5rem" }}>Target Paper</th>
                    <th style={{ textAlign: "left", padding: "0.5rem" }}>Status</th>
                    <th style={{ textAlign: "right", padding: "0.5rem" }}>Similarity</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEdges.map((e, idx) => (
                    <tr key={idx} style={{ borderBottom: "1px solid #f3f4f6" }}>
                      <td style={{ padding: "0.5rem", color: "#1f2937", maxWidth: "250px" }}>{e.source_title}</td>
                      <td style={{ padding: "0.5rem", color: "#1f2937", fontWeight: 600 }}>{e.relationship_type}</td>
                      <td style={{ padding: "0.5rem", color: "#4b5563", maxWidth: "250px" }}>{e.target_title}</td>
                      <td style={{ padding: "0.5rem", color: e.is_author_stated ? "#047857" : "#4b5563" }}>
                        {e.is_author_stated ? "Author Stated" : e.relationship_status === "thematic_only" ? "Thematic Only" : "Inferred"}
                      </td>
                      <td style={{ padding: "0.5rem", textAlign: "right", color: "#6b7280" }}>
                        {(e.semantic_similarity * 100).toFixed(0)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ===================================================================== */}
      {/* 3. CANDIDATE RESEARCH-GAP DISCOVERY SUB-VIEW */}
      {/* ===================================================================== */}
      {!loading && activeSubTab === "gaps" && gapData && (
        <div>
          {/* Prominent Truthfulness Disclosure */}
          <div
            style={{
              background: "#fffbeb",
              border: "1px solid #fde68a",
              borderRadius: "var(--radius-md)",
              padding: "1rem 1.25rem",
              marginBottom: "1.5rem",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.35rem" }}>
              <span style={{ fontSize: "1.2rem" }}>⚖️</span>
              <h4 style={{ margin: 0, color: "#92400e", fontSize: "0.95rem", fontWeight: 700 }}>
                Essential Scientific Truthfulness &amp; Discovery Disclosure
              </h4>
            </div>
            <p style={{ margin: 0, color: "#78350f", fontSize: "0.82rem", lineHeight: 1.5 }}>
              {gapData.truthfulness_disclosure}
            </p>
          </div>

          {/* Insufficient Evidence State */}
          {gapData.status === "insufficient_evidence" ? (
            <div
              style={{
                textAlign: "center",
                padding: "3rem 1.5rem",
                background: "var(--bg-surface)",
                border: "1px dashed var(--border-leaf)",
                borderRadius: "var(--radius-md)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "center", marginBottom: "0.5rem", color: "var(--button-primary)" }}>
                <SearchIcon size={36} />
              </div>
              <h3 style={{ margin: "0.75rem 0 0.5rem", color: "#1f2937" }}>Insufficient Catalog Evidence</h3>
              <p style={{ margin: "0 auto", color: "#6b7280", fontSize: "0.9rem", maxWidth: "550px", lineHeight: 1.5 }}>
                {gapData.truthfulness_disclosure}
              </p>
              <div style={{ marginTop: "1.25rem", display: "flex", justifyContent: "center", gap: "0.5rem" }}>
                <button
                  type="button"
                  onClick={() => {
                    setTopic("");
                    fetchData();
                  }}
                  className="btn-secondary"
                  style={{ fontSize: "0.85rem", padding: "0.4rem 1rem", cursor: "pointer" }}
                >
                  Clear Topic Filter to Examine Broader Catalog
                </button>
              </div>
            </div>
          ) : (
            <div>
              {/* Gap Summary Metrics */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "0.75rem",
                  marginBottom: "1.25rem",
                  fontSize: "0.85rem",
                  color: "#6b7280",
                }}
              >
                <div>
                  Examined Papers: <strong>{gapData.total_papers_examined}</strong> | Candidate Gaps: <strong>{gapData.total_gaps_found}</strong>
                </div>
                <div style={{ fontSize: "0.78rem", color: "#047857" }}>
                  ● All suggestions marked as testable hypotheses requiring human validation
                </div>
              </div>

              {/* Candidate Gap Cards */}
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                {gapData.candidate_gaps.map((gap: CandidateGap) => {
                  const isCatalogBoundary = gap.is_corpus_coverage_gap;
                  const isStrong = gap.evidence_strength === "strong_recurrence";

                  return (
                    <div
                      key={gap.gap_id}
                      className="candidate-gap-card"
                      style={{
                        background: "#ffffff",
                        border: "1px solid #e5e7eb",
                        borderRadius: "var(--radius-md)",
                        padding: "1.5rem",
                        boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
                      }}
                    >
                      {/* Gap Header */}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "0.75rem" }}>
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.35rem" }}>
                            <span
                              style={{
                                fontSize: "0.72rem",
                                fontWeight: 700,
                                padding: "0.15rem 0.55rem",
                                borderRadius: "999px",
                                background: isCatalogBoundary ? "#fffbeb" : isStrong ? "#ecfdf5" : "#f3f4f6",
                                color: isCatalogBoundary ? "#b45309" : isStrong ? "#047857" : "#374151",
                                border: `1px solid ${isCatalogBoundary ? "#fde68a" : isStrong ? "#a7f3d0" : "#e5e7eb"}`,
                              }}
                            >
                              {isCatalogBoundary ? "LOCAL CATALOG BOUNDARY" : gap.evidence_strength.replace("_", " ").toUpperCase()}
                            </span>
                            <span style={{ fontSize: "0.72rem", color: "#6b7280" }}>
                              Corpus Scope: {gap.corpus_scope}
                            </span>
                          </div>
                          <h3 style={{ margin: 0, color: "#1f2937", fontSize: "1.15rem", fontWeight: 700 }}>
                            {gap.title}
                          </h3>
                        </div>

                        <div style={{ textAlign: "right" }}>
                          <span
                            style={{
                              fontSize: "0.75rem",
                              fontWeight: 700,
                              padding: "0.25rem 0.6rem",
                              borderRadius: "4px",
                              background: "#f3f4f6",
                              color: isStrong ? "#047857" : "#b45309",
                              border: "1px solid #e5e7eb",
                            }}
                          >
                            Confidence: {(gap.confidence_score * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>

                      {/* Concise Hypothesis Box */}
                      <div
                        style={{
                          marginTop: "1rem",
                          background: "#f9fafb",
                          border: "1px solid #e5e7eb",
                          borderLeft: `4px solid ${isCatalogBoundary ? "#b45309" : "#1f2937"}`,
                          padding: "0.85rem 1rem",
                          borderRadius: "4px",
                        }}
                      >
                        <div style={{ fontSize: "0.72rem", color: "#6b7280", textTransform: "uppercase", fontWeight: 700, marginBottom: "0.25rem" }}>
                          Concise Research Hypothesis:
                        </div>
                        <p style={{ margin: 0, fontSize: "0.9rem", color: "#1f2937", lineHeight: 1.5, fontWeight: 500 }}>
                          {gap.concise_hypothesis}
                        </p>
                      </div>

                      {/* Motivating Evidence Passages */}
                      {gap.motivating_evidence.length > 0 && (
                        <div style={{ marginTop: "1rem" }}>
                          <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#1f2937", marginBottom: "0.4rem" }}>
                            Motivating Grounded Source Evidence ({gap.motivating_evidence.length} paper passages):
                          </div>
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                            {gap.motivating_evidence.map((ev, evIdx) => (
                              <div
                                key={evIdx}
                                style={{
                                  background: "#f9fafb",
                                  border: "1px solid #e5e7eb",
                                  padding: "0.6rem 0.8rem",
                                  borderRadius: "4px",
                                  fontSize: "0.8rem",
                                }}
                              >
                                <div style={{ display: "flex", justifyContent: "space-between", color: "#6b7280", fontSize: "0.72rem", marginBottom: "0.2rem" }}>
                                  <span>📄 {ev.paper_title} ({ev.year || "Undated"})</span>
                                  {ev.section_name && <span>Section: {ev.section_name}</span>}
                                </div>
                                <div style={{ color: "#374151", fontStyle: "italic" }}>
                                  "{ev.quote}"
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Recommended Human Verification Steps */}
                      {gap.recommended_verification_steps.length > 0 && (
                        <div style={{ marginTop: "1rem", background: "#f0f9ff", border: "1px solid #bae6fd", padding: "0.85rem", borderRadius: "6px" }}>
                          <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#0369a1", marginBottom: "0.35rem" }}>
                            📋 Recommended Verification Steps (Human Review):
                          </div>
                          <ol style={{ margin: 0, paddingLeft: "1.25rem", fontSize: "0.8rem", color: "#0c4a6e", lineHeight: 1.5 }}>
                            {gap.recommended_verification_steps.map((step, sIdx) => (
                              <li key={sIdx} style={{ marginBottom: "0.2rem" }}>
                                {step}
                              </li>
                            ))}
                          </ol>
                        </div>
                      )}

                      {/* Limitations Disclosure */}
                      <div style={{ marginTop: "0.75rem", fontSize: "0.75rem", color: "#6b7280", display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
                        <span>⚠️ Limitations: {gap.limitations}</span>
                        <span style={{ color: "#b45309", fontWeight: 600 }}>Human Validation Mandated</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ===================================================================== */}
      {/* 4. GROUNDED RESEARCH ASSISTANT SUB-VIEW (TASK-17) */}
      {/* ===================================================================== */}
      {activeSubTab === "assistant" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* Assistant Query Bar */}
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e5e7eb",
              borderRadius: "var(--radius-md)",
              padding: "1.25rem 1.5rem",
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem", flexWrap: "wrap", gap: "0.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span style={{ fontSize: "1.2rem" }}>🤖</span>
                <span style={{ fontWeight: 700, color: "#1f2937", fontSize: "1rem" }}>
                  Grounded Scholarly Assistant
                </span>
                <span
                  style={{
                    fontSize: "0.7rem",
                    padding: "0.15rem 0.5rem",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--bg-subtle)",
                    color: "var(--text-secondary)",
                    border: "1px solid var(--border-leaf)",
                    fontWeight: 600,
                  }}
                >
                  TASK-17 Evidence-Backed
                </span>
                {aiStatus && (
                  <span
                    style={{
                      fontSize: "0.7rem",
                      padding: "0.15rem 0.55rem",
                      borderRadius: "999px",
                      background: aiStatus.ai_enabled
                        ? aiStatus.active_provider === "ollama"
                          ? "#ecfdf5"
                          : aiStatus.active_provider === "groq"
                          ? "#f0f9ff"
                          : "#fffbeb"
                        : "#f3f4f6",
                      color: aiStatus.ai_enabled
                        ? aiStatus.active_provider === "ollama"
                          ? "#047857"
                          : aiStatus.active_provider === "groq"
                          ? "#0284c7"
                          : "#b45309"
                        : "#6b7280",
                      border: `1px solid ${
                        aiStatus.ai_enabled
                          ? aiStatus.active_provider === "ollama"
                            ? "#a7f3d0"
                            : aiStatus.active_provider === "groq"
                            ? "#bae6fd"
                            : "#fde68a"
                          : "#e5e7eb"
                      }`,
                      fontWeight: 600,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.3rem",
                    }}
                  >
                    <span>{aiStatus.active_provider === "ollama" ? "🤖" : aiStatus.active_provider === "groq" ? "⚡" : "🛡️"}</span>
                    <span>
                      {aiStatus.ai_enabled
                        ? `AI: ${aiStatus.active_provider.toUpperCase()} (${aiStatus.active_provider === "ollama" ? aiStatus.ollama_model : aiStatus.active_provider === "groq" ? aiStatus.groq_model : "Deterministic NLP"})`
                        : "Deterministic Mode (AI Disabled)"}
                    </span>
                    {aiStatus.deterministic_fallback_active && aiStatus.ai_enabled && (
                      <span style={{ color: "#b45309" }}>[Fallback Active]</span>
                    )}
                  </span>
                )}
              </div>
              <div style={{ fontSize: "0.78rem", color: "#6b7280" }}>
                {topic ? `Scope: Filtered to '${topic}'` : "Scope: Entire Local Catalog"}
              </div>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleAskAssistant();
              }}
              style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}
            >
              <input
                type="text"
                placeholder="Ask any question (e.g. 'What limitations do these models report about computational cost?')..."
                value={assistantQuestion}
                onChange={(e) => setAssistantQuestion(e.target.value)}
                style={{
                  flex: "1 1 320px",
                  background: "#ffffff",
                  border: "1px solid #d1d5db",
                  borderRadius: "var(--radius-sm)",
                  padding: "0.6rem 0.9rem",
                  color: "#1f2937",
                  fontSize: "0.9rem",
                  outline: "none",
                }}
              />
              <button
                type="submit"
                disabled={assistantLoading || !assistantQuestion.trim()}
                className="btn-primary"
                style={{
                  padding: "0.6rem 1.4rem",
                  fontSize: "0.88rem",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                }}
              >
                {assistantLoading ? "Synthesizing..." : "Ask Assistant"}
              </button>
            </form>

            {/* Quick Suggested Questions Chips */}
            <div style={{ marginTop: "1rem", display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
              <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>Example Inquiries:</span>
              {[
                "What are the main limitations reported in this catalog?",
                "What future-work directions do authors propose?",
                "Compare BERT and RoBERTa architectures and training datasets",
                "What evaluation benchmarks and datasets are reported?",
                "What candidate research gaps emerge from these papers?",
              ].map((suggestion, sIdx) => (
                <button
                  key={sIdx}
                  type="button"
                  onClick={() => handleAskAssistant(suggestion)}
                  style={{
                    background: "#f3f4f6",
                    border: "1px solid #e5e7eb",
                    color: "#374151",
                    fontSize: "0.72rem",
                    padding: "0.25rem 0.6rem",
                    borderRadius: "999px",
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  💬 {suggestion}
                </button>
              ))}
            </div>
          </div>

          {/* Assistant Loading State */}
          {assistantLoading && (
            <div style={{ textAlign: "center", padding: "3rem", color: "#4b5563" }}>
              <div className="spinner" style={{ margin: "0 auto 1rem", width: "32px", height: "32px" }}></div>
              <p style={{ margin: 0, fontSize: "0.95rem" }}>
                Querying verified catalog evidence and synthesizing grounded claims...
              </p>
            </div>
          )}

          {/* Assistant Error State */}
          {assistantError && (
            <div
              style={{
                background: "#fef2f2",
                border: "1px solid #fecaca",
                color: "#b91c1c",
                padding: "1rem",
                borderRadius: "var(--radius-md)",
              }}
            >
              <strong>Error:</strong> {assistantError}
            </div>
          )}

          {/* Assistant Response Card */}
          {!assistantLoading && assistantData && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              {/* Header Status & Scope */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "0.5rem",
                  background: "#f9fafb",
                  padding: "0.75rem 1.25rem",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid #e5e7eb",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
                  <span
                    style={{
                      fontSize: "0.75rem",
                      padding: "0.2rem 0.6rem",
                      borderRadius: "999px",
                      fontWeight: 700,
                      background:
                        assistantData.status === "complete"
                          ? "#ecfdf5"
                          : assistantData.status === "insufficient_evidence"
                          ? "#fef2f2"
                          : "#fffbeb",
                      color:
                        assistantData.status === "complete"
                          ? "#047857"
                          : assistantData.status === "insufficient_evidence"
                          ? "#b91c1c"
                          : "#b45309",
                      border: `1px solid ${
                        assistantData.status === "complete"
                          ? "#a7f3d0"
                          : assistantData.status === "insufficient_evidence"
                          ? "#fecaca"
                          : "#fde68a"
                      }`,
                    }}
                  >
                    Status: {assistantData.status.toUpperCase()}
                  </span>
                  {assistantData.ai_provider && (
                    <span
                      style={{
                        fontSize: "0.75rem",
                        padding: "0.2rem 0.6rem",
                        borderRadius: "999px",
                        fontWeight: 700,
                        background:
                          assistantData.ai_provider === "ollama"
                            ? "#ecfdf5"
                            : assistantData.ai_provider === "groq"
                            ? "#f0f9ff"
                            : "#fffbeb",
                        color:
                          assistantData.ai_provider === "ollama"
                            ? "#047857"
                            : assistantData.ai_provider === "groq"
                            ? "#0284c7"
                            : "#b45309",
                        border: `1px solid ${
                          assistantData.ai_provider === "ollama"
                            ? "#a7f3d0"
                            : assistantData.ai_provider === "groq"
                            ? "#bae6fd"
                            : "#fde68a"
                        }`,
                      }}
                    >
                      {assistantData.ai_provider === "ollama"
                        ? `🤖 Local: ${assistantData.ai_model || "qwen2.5:3b"}`
                        : assistantData.ai_provider === "groq"
                        ? `⚡ Groq: ${assistantData.ai_model || "llama-3.3"}`
                        : "🛡️ Deterministic NLP Engine"}
                      {assistantData.ai_fallback_occurred && " (Failover)"}
                      {assistantData.ai_latency_ms ? ` • ${assistantData.ai_latency_ms}ms` : ""}
                    </span>
                  )}
                  <span style={{ fontSize: "0.8rem", color: "#6b7280" }}>
                    Corpus: {assistantData.corpus_scope}
                  </span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>
                  Verified Passages: <strong>{assistantData.evidence.length}</strong> | Claims: <strong>{assistantData.claims.length}</strong>
                </div>
              </div>

              {/* Grounded Answer Narrative */}
              <div
                style={{
                  background: "#ffffff",
                  border: "1px solid #e5e7eb",
                  borderRadius: "var(--radius-md)",
                  padding: "1.5rem",
                  boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
                }}
              >
                <div style={{ fontSize: "0.82rem", fontWeight: 700, color: "#1f2937", marginBottom: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  📖 Evidence-Grounded Synthesis
                </div>
                <div style={{ color: "#1f2937", fontSize: "0.92rem", lineHeight: 1.65, whiteSpace: "pre-line" }}>
                  {assistantData.answer}
                </div>
              </div>

              {/* Key Grounded Claims Checklist */}
              {assistantData.claims.length > 0 && (
                <div
                  style={{
                    background: "#ffffff",
                    border: "1px solid #e5e7eb",
                    borderRadius: "var(--radius-md)",
                    padding: "1.25rem",
                    boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
                  }}
                >
                  <div style={{ fontSize: "0.82rem", fontWeight: 700, color: "#1f2937", marginBottom: "0.75rem" }}>
                    ✓ Key Grounded Claims ({assistantData.claims.length})
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                    {assistantData.claims.map((clm) => (
                      <div
                        key={clm.claim_id}
                        style={{
                          background: "#f9fafb",
                          padding: "0.65rem 0.9rem",
                          borderRadius: "6px",
                          border: "1px solid #e5e7eb",
                          fontSize: "0.84rem",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "flex-start",
                          gap: "0.75rem",
                        }}
                      >
                        <div style={{ color: "#1f2937", lineHeight: 1.45, flex: "1 1 auto" }}>
                          {clm.claim_text}
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.3rem", flexShrink: 0 }}>
                          {clm.supporting_evidence_ids.map((refId) => (
                            <span
                              key={refId}
                              style={{
                                background: "#ecfdf5",
                                color: "#047857",
                                border: "1px solid #a7f3d0",
                                padding: "0.15rem 0.45rem",
                                borderRadius: "4px",
                                fontSize: "0.72rem",
                                fontWeight: 700,
                              }}
                            >
                              [{refId}]
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Verified Source Passages & Character Offsets */}
              {assistantData.evidence.length > 0 && (
                <div
                  style={{
                    background: "#ffffff",
                    border: "1px solid #e5e7eb",
                    borderRadius: "var(--radius-md)",
                    padding: "1.25rem",
                    boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
                  }}
                >
                  <div style={{ fontSize: "0.82rem", fontWeight: 700, color: "#1f2937", marginBottom: "0.75rem" }}>
                    📑 Supporting Evidence Passages &amp; Offsets ({assistantData.evidence.length})
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    {assistantData.evidence.map((ev) => (
                      <div
                        key={ev.evidence_id}
                        style={{
                          background: "#f9fafb",
                          padding: "0.85rem 1rem",
                          borderRadius: "6px",
                          border: "1px solid #e5e7eb",
                          fontSize: "0.83rem",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.4rem" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <span
                              style={{
                                background: "#ecfdf5",
                                color: "#047857",
                                border: "1px solid #a7f3d0",
                                padding: "0.1rem 0.4rem",
                                borderRadius: "4px",
                                fontSize: "0.72rem",
                                fontWeight: 700,
                              }}
                            >
                              [{ev.evidence_id}]
                            </span>
                            <span style={{ fontWeight: 600, color: "#1f2937" }}>
                              {ev.paper_title} ({ev.year || "Undated"})
                            </span>
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.74rem", color: "#6b7280" }}>
                            <span style={{ textTransform: "capitalize", background: "#f3f4f6", border: "1px solid #e5e7eb", padding: "0.1rem 0.4rem", borderRadius: "3px" }}>
                              {ev.category}
                            </span>
                            <span>{ev.section_name || "Abstract"}</span>
                            {ev.char_start !== null && ev.char_end !== null && (
                              <span style={{ fontFamily: "monospace", color: "#047857", fontWeight: 600 }}>
                                [{ev.char_start}:{ev.char_end}]
                              </span>
                            )}
                            <span style={{ color: "#2563eb", fontWeight: 500 }}>{ev.source_type}</span>
                          </div>
                        </div>
                        <div style={{ color: "#374151", fontStyle: "italic", lineHeight: 1.5, background: "#ffffff", padding: "0.5rem 0.75rem", borderRadius: "4px", border: "1px solid #e5e7eb", borderLeft: "3px solid #1f2937" }}>
                          "{ev.source_passage}"
                        </div>
                        {ev.url && (
                          <div style={{ marginTop: "0.4rem", textAlign: "right" }}>
                            <a
                              href={ev.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ color: "#2563eb", fontSize: "0.74rem", textDecoration: "none" }}
                            >
                              🔗 View Source Document →
                            </a>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Scientific Caveats & Limitations */}
              {assistantData.limitations.length > 0 && (
                <div
                  style={{
                    background: "#fffbeb",
                    border: "1px solid #fde68a",
                    borderRadius: "var(--radius-md)",
                    padding: "0.9rem 1.25rem",
                    fontSize: "0.8rem",
                    color: "#92400e",
                  }}
                >
                  <div style={{ fontWeight: 700, marginBottom: "0.3rem" }}>⚠️ Scientific Disclosures &amp; Limitations:</div>
                  <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
                    {assistantData.limitations.map((lim, lIdx) => (
                      <li key={lIdx} style={{ marginBottom: "0.2rem" }}>
                        {lim}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Follow-up Questions Suggestions */}
              {assistantData.follow_up_questions.length > 0 && (
                <div style={{ background: "#f9fafb", padding: "1rem 1.25rem", borderRadius: "var(--radius-md)", border: "1px solid #e5e7eb" }}>
                  <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#1f2937", marginBottom: "0.5rem" }}>
                    💡 Suggested Follow-up Inquiries:
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    {assistantData.follow_up_questions.map((fu, fuIdx) => (
                      <button
                        key={fuIdx}
                        type="button"
                        onClick={() => handleAskAssistant(fu)}
                        style={{
                          background: "#ffffff",
                          border: "1px solid #d1d5db",
                          color: "#1f2937",
                          fontSize: "0.78rem",
                          padding: "0.35rem 0.75rem",
                          borderRadius: "999px",
                          cursor: "pointer",
                          textAlign: "left",
                        }}
                      >
                        ➡️ {fu}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Truthfulness Disclosure Banner */}
              <div
                style={{
                  fontSize: "0.75rem",
                  color: "#6b7280",
                  textAlign: "center",
                  padding: "0.5rem",
                  borderTop: "1px solid #e5e7eb",
                }}
              >
                {assistantData.truthfulness_disclosure}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
