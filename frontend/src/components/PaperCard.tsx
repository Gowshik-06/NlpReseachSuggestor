import React, { useState } from "react";
import type { Paper } from "../types/paper";
import { BookmarkIcon, SparklesIcon, ExternalLinkIcon } from "./icons/Icons";

export interface PaperCardProps {
  paper: Paper;
  isSaved: boolean;
  isCompared: boolean;
  isSaving?: boolean;
  onToggleSave?: (paper: Paper) => void;
  onToggleCompare: (paper: Paper) => void;
  onOpenSummary: (paper: Paper) => void;
  onOpenEvidence?: (paper: Paper) => void;
  // Extended slots for Saved Library reuse
  onRemove?: (paper: Paper) => void;
  isRemoving?: boolean;
  notes?: string;
  savedAt?: string;
}

export default function PaperCard({
  paper,
  isSaved,
  isCompared,
  isSaving = false,
  onToggleSave,
  onToggleCompare,
  onOpenSummary,
  onOpenEvidence,
  onRemove,
  isRemoving = false,
  notes,
  savedAt,
}: PaperCardProps) {
  const [expanded, setExpanded] = useState(false);

  const abstractText = paper.abstract || "No abstract available for this publication.";
  const displayAbstract = expanded
    ? abstractText
    : abstractText.length > 280
    ? `${abstractText.slice(0, 280)}…`
    : abstractText;

  const scorePct = paper.similarity_score
    ? Math.round(paper.similarity_score * 100)
    : null;

  const paperUrl = paper.url || (paper.doi ? `https://doi.org/${paper.doi}` : null);

  return (
    <article className="paper-card">
      <div className="card-top-row">
        <h3 className="paper-title">
          {paperUrl ? (
            <a
              href={paperUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              {paper.title}
            </a>
          ) : (
            <span>{paper.title}</span>
          )}
        </h3>

        <div className="badges-group">
          {paper.year && paper.year >= 2026 && (
            <span className="badge-2026-fresh" title="Published in 2026 or Early Access Release">
              <SparklesIcon size={12} />
              <span>2026 Latest</span>
            </span>
          )}
          {scorePct !== null && (
            <span className="score-badge" title="Semantic Vector Match Score">
              ● {scorePct}% Match
            </span>
          )}
          <span className={`source-badge ${paper.source}`}>
            {paper.source === "pubmed"
              ? "🏛️ US Gov / PubMed"
              : paper.source === "csir"
              ? "🇮🇳 Indian Gov / CSIR"
              : paper.source === "semanticscholar"
              ? "Semantic Scholar"
              : paper.source === "local"
              ? "Local Archive"
              : paper.source.toUpperCase()}
          </span>
          {onRemove && (
            <button
              type="button"
              className="btn-secondary"
              style={{
                color: "var(--berry)",
                background: "var(--berry-bg)",
                borderColor: "var(--berry-border)",
                padding: "0.2rem 0.55rem",
                fontSize: "0.74rem",
              }}
              disabled={isRemoving}
              onClick={() => onRemove(paper)}
            >
              {isRemoving ? "Removing…" : "Remove"}
            </button>
          )}
        </div>
      </div>

      <div className="paper-authors-row">
        {paper.authors && paper.authors.length > 0
          ? paper.authors.slice(0, 5).join(", ") + (paper.authors.length > 5 ? " et al." : "")
          : "Authors unlisted"}
      </div>

      <div className="paper-meta-row">
        <span>{paper.venue || "Academic Publication"}</span>
        <span>•</span>
        <span>{paper.year || "Recent"}</span>
        {paper.citation_count > 0 && (
          <>
            <span>•</span>
            <span>{paper.citation_count.toLocaleString()} citations</span>
          </>
        )}
        {savedAt && (
          <>
            <span>•</span>
            <span>Added {new Date(savedAt).toLocaleDateString()}</span>
          </>
        )}
      </div>

      {notes && (
        <div
          style={{
            background: "var(--bg-subtle)",
            border: "1px solid var(--border-leaf)",
            borderRadius: "var(--radius-sm)",
            padding: "0.55rem 0.85rem",
            fontSize: "0.82rem",
            color: "var(--text-primary)",
            marginBottom: "0.85rem",
          }}
        >
          <strong>Note:</strong> {notes}
        </div>
      )}

      <p className="paper-abstract">
        {displayAbstract}
        {abstractText.length > 280 && (
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="link-button"
            style={{ marginLeft: "0.45rem" }}
          >
            {expanded ? "Show less" : "Read more"}
          </button>
        )}
      </p>

      {paper.explanation && (
        <div className="explain-callout">
          <div>{paper.explanation}</div>
        </div>
      )}

      <div className="card-actions-bar">
        <div className="compare-actions">
          <label className="compare-label">
            <input
              type="checkbox"
              checked={isCompared}
              onChange={() => onToggleCompare(paper)}
              className="compare-checkbox"
            />
            <span>Compare</span>
          </label>

          {onToggleSave && (
            <button
              type="button"
              className={`btn-secondary btn-save ${isSaved ? "saved" : ""}`}
              onClick={() => onToggleSave(paper)}
              disabled={isSaving}
            >
              <BookmarkIcon size={13} />
              <span>{isSaving ? "Saving…" : isSaved ? "In Library" : "Save Paper"}</span>
            </button>
          )}
        </div>

        <div className="action-group">
          {onOpenEvidence && (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => onOpenEvidence(paper)}
              title="Inspect grounded scientific claims and supporting passages"
            >
              Evidence
            </button>
          )}

          <button
            type="button"
            className="btn-secondary"
            onClick={() => onOpenSummary(paper)}
          >
            AI Summary
          </button>

          {paper.pdf_url && (
            <a
              href={paper.pdf_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary"
            >
              <ExternalLinkIcon size={12} />
              <span>PDF</span>
            </a>
          )}
        </div>
      </div>
    </article>
  );
}
