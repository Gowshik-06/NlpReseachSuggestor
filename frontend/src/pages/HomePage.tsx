import React, { useState, useEffect } from "react";
import type { Paper, SearchResponse, SavedPaper, DRIUTAlert } from "../types/paper";
import type { User } from "../types/auth";
import {
  searchPapers,
  getSavedPapers,
  savePaper,
  deleteSavedPaper,
  getDriutAlerts,
  getHealth,
  triggerDriutScan,
  getCurrentUser,
  logoutUser,
} from "../services/api";
import type { HealthStatus } from "../types/health";
import Navbar from "../components/Navbar";
import PaperCard from "../components/PaperCard";
import SummaryModal from "../components/SummaryModal";
import CompareModal from "../components/CompareModal";
import PdfUploadZone from "../components/PdfUploadZone";
import DriutAlertsView from "../components/DriutAlertsView";
import SavedLibraryView from "../components/SavedLibraryView";
import AuthModal from "../components/AuthModal";
import EvidenceModal from "../components/EvidenceModal";
import ResearchEvolutionView from "../components/ResearchEvolutionView";
import { SearchIcon, SparklesIcon } from "../components/icons/Icons";
import { onFirebaseAuthStateChanged } from "../services/firebase";

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<"explore" | "pdf" | "compare" | "saved" | "driut" | "evolution">("explore");
  const [query, setQuery] = useState("");
  const [searchMode, setSearchMode] = useState<"text" | "abstract" | "keywords">("text");
  const [sortBy, setSortBy] = useState<"recency" | "relevance" | "citations">("relevance");
  const [selectedSources, setSelectedSources] = useState<string[]>([
    "local",
    "arxiv",
    "pubmed",
    "csir",
    "semanticscholar",
    "crossref",
    "dblp",
  ]);
  const [enableExternalDiscovery, setEnableExternalDiscovery] = useState(false);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [savedList, setSavedList] = useState<SavedPaper[]>([]);
  const [alerts, setAlerts] = useState<DRIUTAlert[]>([]);
  const [comparedPapers, setComparedPapers] = useState<Paper[]>([]);
  const [summaryPaper, setSummaryPaper] = useState<Paper | null>(null);
  const [evidencePaper, setEvidencePaper] = useState<Paper | null>(null);
  const [compareModalOpen, setCompareModalOpen] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [savingPaperIds, setSavingPaperIds] = useState<Set<string>>(new Set());

  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const showToast = (message: string, type: "success" | "error" = "success") => {
    setToast({ message, type });
  };

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  const loadUserData = async () => {
    try {
      const user = await getCurrentUser();
      setCurrentUser(user);
      const [saved, alt] = await Promise.all([
        getSavedPapers().catch(() => []),
        getDriutAlerts().catch(() => []),
      ]);
      setSavedList(saved);
      setAlerts(alt);
    } catch {
      setCurrentUser(null);
      setSavedList([]);
      setAlerts([]);
    }
  };

  const loadInitialData = async () => {
    try {
      const h = await getHealth().catch(() => null);
      if (h) setHealth(h);
      await loadUserData();
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    loadInitialData();
    const onAuthChange = () => {
      loadUserData();
    };
    window.addEventListener("auth-state-change", onAuthChange);
    const unsubscribeFirebase = onFirebaseAuthStateChanged(() => {
      loadUserData();
    });
    return () => {
      window.removeEventListener("auth-state-change", onAuthChange);
      unsubscribeFirebase();
    };
  }, []);

  const handleOpenAuth = (mode: "login" | "register" = "login") => {
    setAuthMode(mode);
    setAuthModalOpen(true);
  };

  const handleLogout = async () => {
    await logoutUser();
    setCurrentUser(null);
    setSavedList([]);
    setAlerts([]);
  };

  const performSearch = async (
    q: string,
    mode: string = searchMode,
    srcs: string[] = selectedSources,
    sort: "recency" | "relevance" | "citations" = sortBy,
    extDiscovery: boolean = enableExternalDiscovery
  ) => {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await searchPapers({
        query: q,
        mode: mode,
        limit: 12,
        sources: srcs,
        sort_by: sort,
        enable_external_discovery: extDiscovery,
      });
      setResults(res);
      setLoading(false);
    } catch (err: any) {
      setError(err.message || "Search failed.");
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    performSearch(query, searchMode, selectedSources, sortBy, enableExternalDiscovery);
  };

  const handleSourceToggle = (sourceName: string) => {
    setSelectedSources((prev) =>
      prev.includes(sourceName)
        ? prev.filter((s) => s !== sourceName)
        : [...prev, sourceName]
    );
  };

  const handleToggleSave = async (paper: Paper) => {
    if (!currentUser) {
      handleOpenAuth("login");
      return;
    }

    if (savingPaperIds.has(paper.paper_id)) {
      return;
    }

    const existing = savedList.find((s) => s.paper.paper_id === paper.paper_id);
    setSavingPaperIds((prev) => new Set(prev).add(paper.paper_id));

    if (existing) {
      // Remove
      try {
        await deleteSavedPaper(existing.id);
        const updated = await getSavedPapers();
        setSavedList(updated);
        showToast(`Removed "${paper.title.slice(0, 42)}…" from library.`, "success");
      } catch (err: any) {
        showToast(err.message || "Failed to remove paper.", "error");
      } finally {
        setSavingPaperIds((prev) => {
          const next = new Set(prev);
          next.delete(paper.paper_id);
          return next;
        });
      }
    } else {
      // Save (works for both catalog-backed and transient candidate)
      try {
        await savePaper(paper.id, "Saved via ResearchLens Observatory", ["research"], paper);
        const updated = await getSavedPapers();
        setSavedList(updated);
        showToast(`Bookmarked "${paper.title.slice(0, 42)}…" to library.`, "success");
      } catch (err: any) {
        showToast(err.message || "Failed to bookmark paper.", "error");
      } finally {
        setSavingPaperIds((prev) => {
          const next = new Set(prev);
          next.delete(paper.paper_id);
          return next;
        });
      }
    }
  };

  const handleToggleCompare = (paper: Paper) => {
    setComparedPapers((prev) => {
      const exists = prev.some((p) => p.paper_id === paper.paper_id);
      if (exists) {
        return prev.filter((p) => p.paper_id !== paper.paper_id);
      } else {
        return [...prev, paper];
      }
    });
  };

  const handleComparePair = (p1: Paper, p2: Paper) => {
    setComparedPapers([p1, p2]);
    setCompareModalOpen(true);
  };

  const savedPaperIds = new Set(savedList.map((s) => s.paper.paper_id));
  const comparedIds = new Set(comparedPapers.map((p) => p.paper_id));
  const unreadAlerts = alerts.filter((a) => !a.is_read).length;

  return (
    <div className="app-container">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        savedCount={savedList.length}
        driutUnreadCount={unreadAlerts}
        compareCount={comparedPapers.length}
        onOpenCompare={() => setCompareModalOpen(true)}
        health={health}
        currentUser={currentUser}
        onOpenAuth={handleOpenAuth}
        onLogout={handleLogout}
      />

      <main className="main-wrapper">
        {activeTab === "explore" && (
          <div>
            <div className="search-hero">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem", marginBottom: "0.75rem" }}>
                <div className="search-mode-selector" style={{ marginBottom: 0 }}>
                  <button
                    type="button"
                    className={`mode-chip ${searchMode === "text" ? "active" : ""}`}
                    onClick={() => setSearchMode("text")}
                  >
                    Research Query
                  </button>
                  <button
                    type="button"
                    className={`mode-chip ${searchMode === "abstract" ? "active" : ""}`}
                    onClick={() => setSearchMode("abstract")}
                  >
                    Title &amp; Abstract
                  </button>
                  <button
                    type="button"
                    className={`mode-chip ${searchMode === "keywords" ? "active" : ""}`}
                    onClick={() => setSearchMode("keywords")}
                  >
                    Keywords
                  </button>
                </div>

                <div className="sort-segmented-control">
                  <span className="sort-label">Sort:</span>
                  <button
                    type="button"
                    id="sort-relevance-btn"
                    className={`sort-pill ${sortBy === "relevance" ? "active" : ""}`}
                    onClick={() => {
                      setSortBy("relevance");
                      performSearch(query, searchMode, selectedSources, "relevance");
                    }}
                  >
                    Relevance
                  </button>
                  <button
                    type="button"
                    id="sort-recency-btn"
                    className={`sort-pill ${sortBy === "recency" ? "active" : ""}`}
                    onClick={() => {
                      setSortBy("recency");
                      performSearch(query, searchMode, selectedSources, "recency");
                    }}
                  >
                    2026 Latest First
                  </button>
                  <button
                    type="button"
                    id="sort-citations-btn"
                    className={`sort-pill ${sortBy === "citations" ? "active" : ""}`}
                    onClick={() => {
                      setSortBy("citations");
                      performSearch(query, searchMode, selectedSources, "citations");
                    }}
                  >
                    Citations
                  </button>
                </div>
              </div>

              <form onSubmit={handleSearchSubmit}>
                <div className="search-input-box">
                  {searchMode === "abstract" ? (
                    <textarea
                      className="main-search-input search-textarea"
                      placeholder="Paste your research draft abstract, methodology description, or hypothesis here…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  ) : (
                    <input
                      type="text"
                      className="main-search-input"
                      placeholder={
                        searchMode === "keywords"
                          ? "Enter comma-separated keywords (e.g. transformers, attention, citation analysis)"
                          : "Enter natural language research question or problem statement…"
                      }
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  )}

                  <button
                    type="submit"
                    className="search-action-btn"
                    disabled={loading || !query.trim()}
                  >
                    {loading ? "Searching…" : "Search"}
                  </button>
                </div>

                <div className="filter-bar">
                  <div className="source-toggles">
                    <span style={{ fontWeight: 600, marginRight: "0.25rem" }}>
                      Catalog Provenance Filters:
                    </span>
                    {[
                      { id: "local", label: "Local Database (Uploads)" },
                      { id: "arxiv", label: "arXiv" },
                      { id: "pubmed", label: "🏛️ US Gov / PubMed" },
                      { id: "csir", label: "🇮🇳 Indian Gov / CSIR" },
                      { id: "semanticscholar", label: "Semantic Scholar" },
                      { id: "crossref", label: "Crossref" },
                      { id: "dblp", label: "DBLP" },
                    ].map((src) => (
                      <label key={src.id} className="source-checkbox-label">
                        <input
                          type="checkbox"
                          checked={selectedSources.includes(src.id)}
                          onChange={() => handleSourceToggle(src.id)}
                        />
                        {src.label}
                      </label>
                    ))}
                    <span style={{ margin: "0 0.5rem", color: "var(--border-leaf)" }}>|</span>
                    <label className="source-checkbox-label" style={{ fontWeight: 600, color: "var(--azure)" }}>
                      <input
                        type="checkbox"
                        checked={enableExternalDiscovery}
                        onChange={(e) => setEnableExternalDiscovery(e.target.checked)}
                      />
                      <SearchIcon size={13} />
                      <span>Live Remote Discovery</span>
                    </label>
                  </div>

                  <div style={{ fontSize: "0.8rem", color: "var(--text-dim)" }}>
                    FAISS Vector Engine • SPECTER2 Embeddings
                  </div>
                </div>
              </form>
            </div>

            {loading && (
              <div className="loading-box">
                <h3 style={{ margin: "0 0 0.5rem", color: "var(--text-primary)" }}>Computing SPECTER2 Vector Embeddings…</h3>
                <p style={{ margin: 0, fontSize: "0.88rem", color: "var(--text-muted)" }}>
                  Querying FAISS vector index, querying hybrid external repositories, and eliminating duplicates…
                </p>
              </div>
            )}

            {error && (
              <div className="error-box">
                {error}
              </div>
            )}

            {!loading && results && (
              <section>
                <div className="results-header">
                  <div>
                    <h2 style={{ margin: "0 0 0.25rem", fontSize: "1.25rem", color: "var(--text-primary)", fontFamily: "var(--font-serif)" }}>
                      Recommended Academic Literature ({results.total_found} Papers)
                    </h2>
                    <div className="results-stats">
                      Retrieved in {results.execution_time_seconds}s across hybrid repositories
                    </div>
                    {results.detected_keywords && results.detected_keywords.length > 0 && (
                      <div className="detected-tags-row">
                        <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Keywords:</span>
                        {results.detected_keywords.map((kw, i) => (
                          <span key={i} className="keyword-tag">#{kw}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div className="paper-cards-grid">
                  {results.results.map((paper) => (
                    <PaperCard
                      key={paper.paper_id}
                      paper={paper}
                      isSaved={savedPaperIds.has(paper.paper_id)}
                      isSaving={savingPaperIds.has(paper.paper_id)}
                      isCompared={comparedIds.has(paper.paper_id)}
                      onToggleSave={handleToggleSave}
                      onToggleCompare={handleToggleCompare}
                      onOpenSummary={(p) => setSummaryPaper(p)}
                      onOpenEvidence={(p) => setEvidencePaper(p)}
                    />
                  ))}
                </div>
              </section>
            )}

            {!loading && !results && !error && (
              <div
                style={{
                  marginTop: "1.5rem",
                  padding: "2rem 1.75rem",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-leaf)",
                  borderRadius: "var(--radius-lg)",
                  boxShadow: "var(--shadow-card)",
                }}
              >
                <div style={{ textAlign: "center", maxWidth: "680px", margin: "0 auto 2rem" }}>
                  <div
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.45rem",
                      padding: "0.25rem 0.75rem",
                      background: "var(--bg-subtle)",
                      border: "1px solid var(--border-leaf)",
                      borderRadius: "var(--radius-sm)",
                      color: "var(--text-secondary)",
                      fontSize: "0.78rem",
                      fontWeight: 600,
                      marginBottom: "0.85rem",
                    }}
                  >
                    Zero Pre-seeded Static Data • 100% Live Repositories Active
                  </div>
                  <h2 style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 0.5rem", fontFamily: "var(--font-serif)" }}>
                    Live Academic Literature Observatory
                  </h2>
                  <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--text-muted)", lineHeight: 1.55 }}>
                    Query real-time publications across arXiv, PubMed, Indian CSIR-NIScPR, Semantic Scholar, Crossref, and DBLP. Select a live trending domain below or enter your research hypothesis above.
                  </p>
                </div>

                <div className="domain-presets-grid">
                  {[
                    {
                      tag: "AI Frontier",
                      title: "Reasoning & Agentic LLMs",
                      desc: "Chain-of-thought, test-time compute scaling, and autonomous multi-agent reasoning systems.",
                      query: "reasoning and test-time compute foundation models 2026",
                    },
                    {
                      tag: "Indian CSIR",
                      title: "CSIR-NIScPR Science",
                      desc: "Indian national laboratory publications spanning renewable materials, bio-sciences, and clean tech.",
                      query: "renewable energy nanomaterials biotechnology",
                    },
                    {
                      tag: "Biomedical NLP",
                      title: "PubMed Biomedical NLP",
                      desc: "Clinical biomedical deep learning, therapeutic discovery, and molecular sequence modeling.",
                      query: "deep learning genomics clinical biomarkers pubmed",
                    },
                    {
                      tag: "Foundations",
                      title: "Sparse & Efficient Attention",
                      desc: "Linearized transformers, state-space models, and long-context architecture advancements.",
                      query: "efficient attention linear transformers state space models",
                    },
                    {
                      tag: "Computational Biology",
                      title: "Protein Structure & Folding",
                      desc: "AlphaFold advances, de novo protein design, and molecular dynamics with deep learning.",
                      query: "protein structure prediction de novo design deep learning",
                    },
                    {
                      tag: "Physics & Compute",
                      title: "Quantum Neural Networks",
                      desc: "Parameterized quantum circuits, quantum advantage, and hybrid quantum-classical algorithms.",
                      query: "quantum neural networks parameterized circuits machine learning",
                    },
                  ].map((card, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className="domain-preset-card"
                      onClick={() => {
                        setQuery(card.query);
                        performSearch(card.query, "text", selectedSources, sortBy);
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span className="domain-preset-tag">
                          {card.tag}
                        </span>
                      </div>
                      <div style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "0.98rem" }}>
                        {card.title}
                      </div>
                      <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.5, flex: 1 }}>
                        {card.desc}
                      </div>
                      <div
                        style={{
                          marginTop: "0.35rem",
                          fontSize: "0.78rem",
                          color: "var(--button-primary)",
                          fontWeight: 600,
                          display: "flex",
                          alignItems: "center",
                          gap: "0.25rem",
                        }}
                      >
                        <span>Query live repositories</span>
                        <span>→</span>
                      </div>
                    </button>
                  ))}
                </div>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    flexWrap: "wrap",
                    gap: "1.25rem",
                    paddingTop: "1.25rem",
                    borderTop: "1px solid var(--border-leaf)",
                    fontSize: "0.8rem",
                    color: "var(--text-muted)",
                  }}
                >
                  <span>● arXiv Open Access</span>
                  <span>● US NIH PubMed</span>
                  <span>● Indian CSIR-NIScPR</span>
                  <span>● Semantic Scholar &amp; Crossref</span>
                  <span>● DBLP Computer Science</span>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "pdf" && (
          <div>
            <div style={{ textAlign: "center", marginBottom: "2rem" }}>
              <h2 style={{ margin: "0 0 0.5rem", color: "var(--text-primary)", fontFamily: "var(--font-serif)" }}>
                Multi-modal Research Paper Ingestion
              </h2>
              <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "0.95rem" }}>
                Upload an academic manuscript (PDF) to automatically extract text, title, abstract,
                and retrieve related research using semantic similarity.
              </p>
            </div>

            <PdfUploadZone
              onResultsExtracted={(res) => {
                setResults(res);
                setActiveTab("explore");
              }}
              isAuthenticated={!!currentUser}
              onOpenAuth={handleOpenAuth}
              onOpenSummary={(p) => setSummaryPaper(p)}
              onOpenEvidence={(p) => setEvidencePaper(p)}
              onToggleSave={handleToggleSave}
              onToggleCompare={handleToggleCompare}
              savedPaperIds={savedPaperIds}
              savingPaperIds={savingPaperIds}
              comparedIds={comparedIds}
              onCatalogIngested={() => loadUserData()}
            />
          </div>
        )}

        {activeTab === "saved" && (
          <SavedLibraryView
            savedPapers={savedList}
            onLibraryUpdated={loadUserData}
            onOpenSummary={(p) => setSummaryPaper(p)}
            onOpenEvidence={(p) => setEvidencePaper(p)}
            onToggleCompare={handleToggleCompare}
            comparedIds={comparedIds}
            onTriggerDriutScan={async () => {
              try {
                const res = await triggerDriutScan();
                await loadUserData();
                setActiveTab("driut");
                showToast(
                  res.new_alerts_count > 0
                    ? `DRIUT scan complete: discovered ${res.new_alerts_count} new research alerts.`
                    : "DRIUT scan complete: all library papers are up to date.",
                  "success"
                );
              } catch (err: any) {
                showToast(err.message || "Failed to trigger DRIUT scan.", "error");
              }
            }}
            isAuthenticated={!!currentUser}
            onOpenAuth={() => handleOpenAuth("login")}
          />
        )}

        {activeTab === "driut" && (
          <DriutAlertsView
            alerts={alerts}
            onAlertsUpdated={loadUserData}
            onComparePair={handleComparePair}
            isAuthenticated={!!currentUser}
            onOpenAuth={() => handleOpenAuth("login")}
          />
        )}

        {activeTab === "evolution" && (
          <ResearchEvolutionView
            initialTopic={query}
          />
        )}
      </main>

      <footer className="app-footer">
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
          <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>ResearchLens System</span>
          <span>•</span>
          <span>Semantic Academic Discovery &amp; Intelligence Observatory</span>
        </div>
        <div style={{ marginTop: "0.25rem", color: "var(--text-muted)", fontSize: "0.78rem" }}>
          FastAPI • React + TypeScript + Vite • PostgreSQL • AllenAI SPECTER2 &amp; FAISS Vector Index
        </div>
      </footer>

      {summaryPaper && (
        <SummaryModal
          paper={summaryPaper}
          onClose={() => setSummaryPaper(null)}
        />
      )}

      {evidencePaper && (
        <EvidenceModal
          paper={evidencePaper}
          onClose={() => setEvidencePaper(null)}
        />
      )}

      {compareModalOpen && (
        <CompareModal
          papers={comparedPapers}
          onClose={() => setCompareModalOpen(false)}
          onClear={() => setComparedPapers([])}
        />
      )}

      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onAuthSuccess={(user) => {
          setCurrentUser(user);
          loadUserData();
        }}
        initialMode={authMode}
      />

      {toast && (
        <div
          role="status"
          aria-live="polite"
          className={`toast-notification ${toast.type}`}
        >
          <span>{toast.message}</span>
          <button
            type="button"
            onClick={() => setToast(null)}
            style={{
              background: "transparent",
              border: "none",
              color: "inherit",
              cursor: "pointer",
              marginLeft: "0.5rem",
              padding: "2px 4px",
              fontSize: "0.85rem",
            }}
            title="Dismiss notification"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
