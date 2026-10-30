import React from "react";
import type { SavedPaper, Paper } from "../types/paper";
import { deleteSavedPaper } from "../services/api";
import PaperCard from "./PaperCard";
import { BookmarkIcon, ActivityIcon, KeyIcon } from "./icons/Icons";

interface SavedLibraryViewProps {
  savedPapers: SavedPaper[];
  onLibraryUpdated: () => void;
  onOpenSummary: (paper: Paper) => void;
  onOpenEvidence?: (paper: Paper) => void;
  onToggleCompare: (paper: Paper) => void;
  comparedIds: Set<number | string>;
  onTriggerDriutScan: () => void;
  isAuthenticated?: boolean;
  onOpenAuth?: () => void;
}

export default function SavedLibraryView({
  savedPapers,
  onLibraryUpdated,
  onOpenSummary,
  onOpenEvidence,
  onToggleCompare,
  comparedIds,
  onTriggerDriutScan,
  isAuthenticated = false,
  onOpenAuth,
}: SavedLibraryViewProps) {
  const [deletingId, setDeletingId] = React.useState<number | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  const handleDelete = async (id: number) => {
    if (deletingId !== null) return;
    setDeletingId(id);
    setActionError(null);
    try {
      await deleteSavedPaper(id);
      onLibraryUpdated();
    } catch (err: any) {
      setActionError(err.message || "Failed to remove paper from library.");
    } finally {
      setDeletingId(null);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="auth-container">
        <div style={{ display: "flex", justifyContent: "center", marginBottom: "0.85rem", color: "var(--button-primary)" }}>
          <BookmarkIcon size={36} />
        </div>
        <h3>Private Literature Sanctuary</h3>
        <p>
          Your bookmarked papers, custom tags, and private notes are cryptographically isolated per user. Sign in to access your curated collection.
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

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.35rem", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h2 style={{ margin: "0 0 0.25rem", color: "var(--text-primary)", fontSize: "1.35rem", fontWeight: 700, fontFamily: "var(--font-serif)" }}>
            Saved Literature Library ({savedPapers.length})
          </h2>
          <p style={{ margin: 0, fontSize: "0.86rem", color: "var(--text-muted)" }}>
            Curated research papers actively monitored by the ResearchLens Dynamic Impact Tracker (DRIUT).
          </p>
        </div>

        <button
          type="button"
          className="btn-primary"
          onClick={onTriggerDriutScan}
        >
          <ActivityIcon size={15} />
          <span>Scan for Impact Updates</span>
        </button>
      </div>

      {actionError && (
        <div className="error-box" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>{actionError}</span>
          <button
            type="button"
            onClick={() => setActionError(null)}
            style={{
              background: "transparent",
              border: "none",
              color: "inherit",
              cursor: "pointer",
              fontSize: "1rem",
              padding: "0 0.25rem",
            }}
            title="Dismiss error"
          >
            ✕
          </button>
        </div>
      )}

      {savedPapers.length === 0 ? (
        <div className="empty-state">
          <div style={{ display: "flex", justifyContent: "center", marginBottom: "0.75rem", color: "var(--text-muted)" }}>
            <BookmarkIcon size={32} />
          </div>
          <h3>Your library is currently empty</h3>
          <p>
            Explore publications in the <strong>Explore</strong> tab or parse a PDF draft to bookmark papers.
            Bookmarked literature is monitored for citations, code releases, rebuttals, and extensions.
          </p>
        </div>
      ) : (
        <div className="paper-cards-grid saved-library-grid">
          {savedPapers.map((entry) => {
            const paper = entry.paper;
            const isCompared = comparedIds.has(paper.paper_id) || (typeof paper.id === "number" && comparedIds.has(paper.id));

            return (
              <PaperCard
                key={entry.id}
                paper={paper}
                isSaved={true}
                isCompared={isCompared}
                onToggleCompare={onToggleCompare}
                onOpenSummary={onOpenSummary}
                onOpenEvidence={onOpenEvidence}
                onRemove={() => handleDelete(entry.id)}
                isRemoving={deletingId === entry.id}
                notes={entry.notes}
                savedAt={entry.saved_at}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
