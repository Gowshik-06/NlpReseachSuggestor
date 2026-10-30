import React, { useState, useEffect } from "react";
import type { DRIUTAlert, DRIUTRelationshipType, DRIUTStatus, Paper } from "../types/paper";
import { triggerDriutScan, markAlertRead, getDriutStatus } from "../services/api";
import { ActivityIcon, KeyIcon } from "./icons/Icons";

interface DriutAlertsViewProps {
  alerts: DRIUTAlert[];
  onAlertsUpdated: () => void;
  onComparePair: (p1: Paper, p2: Paper) => void;
  isAuthenticated?: boolean;
  onOpenAuth?: () => void;
}

const CATEGORIES: DRIUTRelationshipType[] = [
  "Improvement",
  "Extension",
  "Challenge",
  "Reproduction",
  "Alternative",
  "Potential Replacement",
];

export default function DriutAlertsView({
  alerts,
  onAlertsUpdated,
  onComparePair,
  isAuthenticated = false,
  onOpenAuth,
}: DriutAlertsViewProps) {
  const [filter, setFilter] = useState<string>("All");
  const [scanning, setScanning] = useState(false);
  const [scanMessage, setScanMessage] = useState<string | null>(null);
  const [status, setStatus] = useState<DRIUTStatus | null>(null);

  const fetchStatus = async () => {
    try {
      const s = await getDriutStatus();
      setStatus(s);
    } catch {
      // ignore if unauthenticated or network error
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchStatus();
    }
  }, [isAuthenticated]);

  const handleScan = async () => {
    setScanning(true);
    setScanMessage(null);
    try {
      const res = await triggerDriutScan();
      setScanMessage(
        res.new_alerts_count > 0
          ? `Discovered ${res.new_alerts_count} new research relationship alerts!`
          : "Scan complete. All saved library papers are currently up to date."
      );
      setScanning(false);
      onAlertsUpdated();
      fetchStatus();
    } catch (err: any) {
      setScanMessage(err.message || "Failed to execute DRIUT scan.");
      setScanning(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="auth-container">
        <div style={{ display: "flex", justifyContent: "center", marginBottom: "0.85rem", color: "var(--button-primary)" }}>
          <ActivityIcon size={36} />
        </div>
        <h3>Dynamic Research Impact Update Tracker (DRIUT)</h3>
        <p>
          DRIUT scans incoming literature against your private saved papers to alert you to extensions, challenges, and improvements. Sign in to monitor your field.
        </p>
        {onOpenAuth && (
          <button
            type="button"
            onClick={onOpenAuth}
            className="btn-primary"
          >
            <KeyIcon size={15} />
            <span>Sign In / Register</span>
          </button>
        )}
      </div>
    );
  }

  const handleMarkRead = async (alertId: number) => {
    try {
      await markAlertRead(alertId);
      onAlertsUpdated();
    } catch {
      // ignore
    }
  };

  const [expandedAlerts, setExpandedAlerts] = useState<Record<number, boolean>>({});

  const toggleExpanded = (id: number) => {
    setExpandedAlerts((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const renderEvidenceStrengthBadge = (strength?: string | null) => {
    if (strength === "strong_evidence") {
      return (
        <span
          style={{
            fontSize: "0.75rem",
            padding: "0.2rem 0.55rem",
            borderRadius: "999px",
            background: "#ecfdf5",
            color: "#047857",
            border: "1px solid #a7f3d0",
            fontWeight: 600,
          }}
        >
          🛡️ Verified Evidence
        </span>
      );
    }
    if (strength === "partial_evidence") {
      return (
        <span
          style={{
            fontSize: "0.75rem",
            padding: "0.2rem 0.55rem",
            borderRadius: "999px",
            background: "#eff6ff",
            color: "#1d4ed8",
            border: "1px solid #bfdbfe",
            fontWeight: 600,
          }}
        >
          🔍 Grounded Claims
        </span>
      );
    }
    return (
      <span
        style={{
          fontSize: "0.75rem",
          padding: "0.2rem 0.55rem",
          borderRadius: "999px",
          background: "#fffbeb",
          color: "#b45309",
          border: "1px solid #fde68a",
          fontWeight: 600,
        }}
      >
        ⚠️ Tentative Inference
      </span>
    );
  };

  const filteredAlerts =
    filter === "All"
      ? alerts
      : alerts.filter((a) => a.relationship_type === filter);

  return (
    <div>
      <div className="driut-banner">
        <div className="driut-info">
          <h2>Dynamic Research Impact Update Tracker (DRIUT)</h2>
          <p>
            ResearchLens continuously examines newly indexed literature to detect conceptual
            evolution against your reading library. Automatically identifies <strong>Extension, Improvement, Challenge, Reproduction, Alternative</strong>, and <strong>Potential Replacement</strong> relationships supported by grounded evidence.
          </p>

          {/* Automated Monitoring Status Strip */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.85rem", flexWrap: "wrap", marginTop: "0.75rem", fontSize: "0.82rem" }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.45rem",
                padding: "0.22rem 0.65rem",
                borderRadius: "var(--radius-sm)",
                background: status?.is_enabled ? "var(--emerald-bg)" : "var(--bg-subtle)",
                color: status?.is_enabled ? "var(--emerald)" : "var(--text-muted)",
                border: `1px solid ${status?.is_enabled ? "var(--emerald-border)" : "var(--border-leaf)"}`,
                fontWeight: 600,
              }}
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: status?.is_enabled ? "var(--emerald)" : "var(--text-muted)",
                }}
              />
              {status?.is_enabled
                ? `Automated Background Monitoring: Active (${status.interval_minutes}m interval)`
                : "Automated Background Monitoring: Disabled"}
            </span>

            {status?.last_run_time && (
              <span style={{ color: "var(--text-muted)" }}>
                Last live scan: {new Date(status.last_run_time).toLocaleTimeString()}
                {status.last_run_duration_seconds != null ? ` (${status.last_run_duration_seconds}s)` : ""}
              </span>
            )}

            {status?.total_scans_completed != null && status.total_scans_completed > 0 && (
              <span style={{ color: "var(--text-muted)" }}>
                • Scans completed: {status.total_scans_completed}
              </span>
            )}
          </div>

          {/* Upstream Provider Notification if any provider experienced issues */}
          {status?.provider_errors && Object.keys(status.provider_errors).length > 0 && (
            <div
              style={{
                marginTop: "0.85rem",
                padding: "0.5rem 0.85rem",
                background: "#fffbeb",
                border: "1px solid #fde68a",
                borderRadius: "var(--radius-sm)",
                color: "#92400e",
                fontSize: "0.8rem",
              }}
            >
              ⚠️ <strong>Upstream Provider Notice:</strong> Academic source limits detected ({Object.keys(status.provider_errors).join(", ")}). Local database papers and remaining providers were evaluated normally.
            </div>
          )}
        </div>

        <button
          type="button"
          className="driut-scan-btn"
          onClick={handleScan}
          disabled={scanning}
        >
          <ActivityIcon size={16} />
          <span>{scanning ? "Scanning Literature…" : "Run Live Impact Scan"}</span>
        </button>
      </div>

      {scanMessage && (
        <div
          style={{
            marginBottom: "1.5rem",
            padding: "0.9rem 1.35rem",
            background: "var(--emerald-bg)",
            border: "1px solid var(--emerald-border)",
            borderRadius: "var(--radius-md)",
            color: "var(--emerald)",
            fontSize: "0.9rem",
            fontWeight: 500,
          }}
        >
          {scanMessage}
        </div>
      )}

      {/* Filter Tabs */}
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1.5rem" }}>
        <button
          className={`mode-chip ${filter === "All" ? "active" : ""}`}
          onClick={() => setFilter("All")}
        >
          All Impact Alerts ({alerts.length})
        </button>
        {CATEGORIES.map((cat) => {
          const count = alerts.filter((a) => a.relationship_type === cat).length;
          return (
            <button
              key={cat}
              className={`mode-chip ${filter === cat ? "active" : ""}`}
              onClick={() => setFilter(cat)}
            >
              {cat} ({count})
            </button>
          );
        })}
      </div>

      {filteredAlerts.length === 0 ? (
        <div className="empty-state">
          <div style={{ display: "flex", justifyContent: "center", marginBottom: "0.75rem", color: "var(--text-muted)" }}>
            <ActivityIcon size={32} />
          </div>
          <h3>No research alerts in this category</h3>
          <p>
            As you bookmark papers and newly published literature is discovered across arXiv and academic sources,
            DRIUT will alert you to meaningful impacts.
          </p>
          <div style={{ marginTop: "1rem" }}>
            <button type="button" className="btn-secondary" onClick={handleScan}>
              Trigger Live Literature Scan
            </button>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          {filteredAlerts.map((alert) => {
            const relKey = alert.relationship_type.replace(/\s+/g, "");
            const isExpanded = !!expandedAlerts[alert.id];
            return (
              <div
                key={alert.id}
                className={`driut-alert-card ${!alert.is_read ? "unread" : ""}`}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.85rem", flexWrap: "wrap", gap: "0.5rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
                    <span className={`rel-badge ${relKey}`}>
                      ● {alert.relationship_type}
                    </span>
                    {renderEvidenceStrengthBadge(alert.evidence_strength)}
                    <span
                      style={{
                        fontSize: "0.72rem",
                        padding: "0.15rem 0.5rem",
                        borderRadius: "4px",
                        background: alert.source_type === "full_text" ? "#eff6ff" : "#f3f4f6",
                        color: alert.source_type === "full_text" ? "#1d4ed8" : "#4b5563",
                        border: `1px solid ${alert.source_type === "full_text" ? "#bfdbfe" : "#e5e7eb"}`,
                      }}
                    >
                      {alert.source_type === "full_text" ? "📄 Full Text Provenance" : "📑 Abstract Only"}
                    </span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <span style={{ fontSize: "0.8rem", color: "#1f2937", fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                      Match Confidence: {Math.round(alert.confidence_score * 100)}%
                    </span>
                    <span style={{ fontSize: "0.78rem", color: "#6b7280" }}>
                      {new Date(alert.created_at).toLocaleDateString()}
                    </span>
                    {!alert.is_read && (
                      <button
                        className="btn-secondary"
                        style={{ fontSize: "0.75rem", padding: "0.22rem 0.65rem", borderColor: "#d1d5db", color: "#1f2937", background: "#ffffff" }}
                        onClick={() => handleMarkRead(alert.id)}
                      >
                        Mark as Read
                      </button>
                    )}
                  </div>
                </div>

                <div className="alert-comparison-box">
                  <div className="alert-subpaper">
                    <div className="alert-subpaper-label">Saved Baseline in Your Library</div>
                    <div className="alert-subpaper-title">
                      {alert.saved_paper?.title || "Saved Paper"}
                    </div>
                  </div>

                  <div className="alert-arrow">➔</div>

                  <div className="alert-subpaper">
                    <div className="alert-subpaper-label">Newly Detected Research</div>
                    <div className="alert-subpaper-title" style={{ color: "#2563eb" }}>
                      {alert.trigger_paper?.title || "New Publication"}
                    </div>
                  </div>
                </div>

                <p style={{ margin: "0.85rem 0 0.5rem", fontSize: "0.92rem", lineHeight: 1.6, color: "#374151" }}>
                  {alert.explanation}
                </p>

                {/* Similarity attribution notice */}
                <div style={{ fontSize: "0.78rem", color: "#6b7280", marginBottom: "0.75rem", fontStyle: "italic" }}>
                  Note: Semantic similarity indicates topical relation, not scientific equivalence or superiority.
                  {alert.semantic_similarity != null && (
                    <span style={{ marginLeft: "0.35rem", color: "#1f2937" }}>
                      (Topical affinity: {(alert.semantic_similarity * 100).toFixed(0)}%)
                    </span>
                  )}
                </div>

                {/* Collapsible Grounded Evidence Inspection Card */}
                {alert.evidence_passage && (
                  <div style={{ marginTop: "0.5rem", marginBottom: "0.75rem" }}>
                    <button
                      onClick={() => toggleExpanded(alert.id)}
                      style={{
                        background: "none",
                        border: "none",
                        color: "#2563eb",
                        fontSize: "0.82rem",
                        cursor: "pointer",
                        padding: "0.25rem 0",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.35rem",
                        fontWeight: 500,
                      }}
                    >
                      <span>{isExpanded ? "▲ Hide Supporting Evidence" : "▼ Inspect Supporting Evidence & Offsets"}</span>
                    </button>

                    {isExpanded && (
                      <div
                        style={{
                          marginTop: "0.5rem",
                          padding: "0.85rem",
                          background: "#f9fafb",
                          border: "1px solid #e5e7eb",
                          borderRadius: "var(--radius-sm)",
                          fontSize: "0.84rem",
                          lineHeight: 1.55,
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.45rem", color: "#6b7280", fontSize: "0.78rem" }}>
                          <span>
                            <strong>Candidate Evidence Passage</strong> {alert.section_name ? `(${alert.section_name})` : ""}
                          </span>
                          {alert.char_start != null && alert.char_end != null && (
                            <span style={{ fontFamily: "var(--font-mono)" }}>
                              Offsets: [{alert.char_start}:{alert.char_end}]
                            </span>
                          )}
                        </div>

                        <div
                          style={{
                            padding: "0.5rem 0.75rem",
                            background: "#ffffff",
                            border: "1px solid #e5e7eb",
                            borderLeft: "3px solid #059669",
                            color: "#1f2937",
                            borderRadius: "2px",
                            fontStyle: "italic",
                          }}
                        >
                          "{alert.evidence_passage}"
                        </div>

                        {alert.saved_evidence_passage && (
                          <div style={{ marginTop: "0.75rem" }}>
                            <div style={{ color: "#6b7280", fontSize: "0.78rem", marginBottom: "0.35rem" }}>
                              <strong>Baseline Saved Paper Passage</strong>
                            </div>
                            <div
                              style={{
                                padding: "0.5rem 0.75rem",
                                background: "#ffffff",
                                border: "1px solid #e5e7eb",
                                borderLeft: "3px solid #2563eb",
                                color: "#1f2937",
                                borderRadius: "2px",
                                fontStyle: "italic",
                              }}
                            >
                              "{alert.saved_evidence_passage}"
                            </div>
                          </div>
                        )}

                        {alert.comparability_notes && (
                          <div
                            style={{
                              marginTop: "0.65rem",
                              padding: "0.4rem 0.65rem",
                              background: "#fffbeb",
                              border: "1px solid #fde68a",
                              borderRadius: "4px",
                              color: "#92400e",
                              fontSize: "0.78rem",
                            }}
                          >
                            ⚠️ <strong>Protocol Caution:</strong> {alert.comparability_notes}
                          </div>
                        )}

                        {alert.uncertainty_warning && (
                          <div
                            style={{
                              marginTop: "0.5rem",
                              color: "#4b5563",
                              fontSize: "0.76rem",
                            }}
                          >
                            ℹ️ {alert.uncertainty_warning}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                  {alert.saved_paper && alert.trigger_paper && (
                    <button
                      className="btn-secondary"
                      style={{
                        borderColor: "#d1d5db",
                        color: "#1f2937",
                        fontSize: "0.82rem",
                        background: "#ffffff",
                      }}
                      onClick={() => onComparePair(alert.saved_paper, alert.trigger_paper)}
                    >
                      📑 Compare New vs. Saved Paper
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
