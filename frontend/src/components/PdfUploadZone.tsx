import React, { useState, useRef } from "react";
import type { Paper, SearchResponse, PdfPreviewResponse, PdfIngestResponse } from "../types/paper";
import { previewPdf, ingestPdf } from "../services/api";
import PaperCard from "./PaperCard";
import { UploadIcon, DocumentIcon } from "./icons/Icons";

interface PdfUploadZoneProps {
  onResultsExtracted?: (response: SearchResponse) => void;
  isAuthenticated?: boolean;
  onOpenAuth?: (mode?: "login" | "register") => void;
  onOpenSummary?: (paper: Paper) => void;
  onOpenEvidence?: (paper: Paper) => void;
  onToggleSave?: (paper: Paper) => void;
  onToggleCompare?: (paper: Paper) => void;
  savedPaperIds?: Set<string>;
  savingPaperIds?: Set<string>;
  comparedIds?: Set<string | number>;
  onCatalogIngested?: (paperId: string, catalogId: number) => void;
}

export default function PdfUploadZone({
  onResultsExtracted,
  isAuthenticated = false,
  onOpenAuth,
  onOpenSummary,
  onOpenEvidence,
  onToggleSave,
  onToggleCompare,
  savedPaperIds = new Set(),
  savingPaperIds = new Set(),
  comparedIds = new Set(),
  onCatalogIngested,
}: PdfUploadZoneProps) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [preview, setPreview] = useState<PdfPreviewResponse | null>(null);
  const [ingestResult, setIngestResult] = useState<PdfIngestResponse | null>(null);
  const [addToLibrary, setAddToLibrary] = useState(true);
  const [showRawText, setShowRawText] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please upload a valid PDF research manuscript.");
      return;
    }

    setUploading(true);
    setError(null);
    setIngestError(null);
    setIngestResult(null);
    setPreview(null);
    setUploadedFileName(file.name);

    try {
      const res = await previewPdf(file, 10);
      setUploading(false);
      setPreview(res);
    } catch (err: any) {
      setError(err.message || "Failed to parse PDF and extract manuscript metadata.");
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleConfirmIngest = async () => {
    if (!preview) return;

    if (!isAuthenticated) {
      if (onOpenAuth) {
        onOpenAuth("login");
      } else {
        alert("Authentication required to add manuscripts to the catalog.");
      }
      return;
    }

    setIngesting(true);
    setIngestError(null);

    try {
      const meta = preview.extracted_metadata;
      const res = await ingestPdf({
        confirm_ingest: true,
        title: meta.title,
        abstract: meta.abstract,
        authors: meta.authors,
        year: meta.year,
        doi: meta.doi,
        venue: meta.venue,
        keywords: meta.keywords,
        filename: preview.filename,
        add_to_library: addToLibrary,
      });

      setIngestResult(res);
      setIngesting(false);
      if (onCatalogIngested) {
        onCatalogIngested(res.paper_id, res.catalog_id);
      }
    } catch (err: any) {
      setIngestError(err.message || "Failed to ingest manuscript into catalog.");
      setIngesting(false);
    }
  };

  const handleReset = () => {
    setPreview(null);
    setIngestResult(null);
    setError(null);
    setIngestError(null);
    setUploadedFileName(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div style={{ maxWidth: preview ? "100%" : "900px", margin: "0 auto 3rem" }}>
      <input
        type="file"
        ref={fileInputRef}
        accept="application/pdf"
        style={{ display: "none" }}
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            handleFile(e.target.files[0]);
          }
        }}
      />

      {/* 1. DROPZONE (Visible when no preview or when resetting) */}
      {!preview && (
        <div
          className={`dropzone ${dragging ? "dragging" : ""}`}
          style={{
            cursor: uploading ? "wait" : "pointer",
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => !uploading && fileInputRef.current?.click()}
        >
          <div className="dropzone-icon">
            <UploadIcon size={40} />
          </div>
          <h3 style={{ margin: "0 0 0.5rem", color: "var(--text-primary)", fontSize: "1.2rem", fontWeight: 700 }}>
            {uploading
              ? "Parsing PDF Structure & Extracting Metadata…"
              : uploadedFileName
              ? `Uploaded: ${uploadedFileName}`
              : "Drop Research Paper PDF to Analyze"}
          </h3>
          <p style={{ margin: "0 0 1.25rem", color: "var(--text-muted)", fontSize: "0.88rem", lineHeight: 1.5, maxWidth: "560px", marginLeft: "auto", marginRight: "auto" }}>
            Extracts title, abstract, authors, and keywords via PyPDF. Computes SPECTER2 semantic query vectors to discover closely aligned literature in preview mode.
          </p>
          <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center", alignItems: "center" }}>
            <button
              type="button"
              className="btn-primary"
              disabled={uploading}
            >
              {uploading ? "Extracting Embeddings…" : "Browse Manuscript File"}
            </button>
          </div>
          <div style={{ marginTop: "1rem", fontSize: "0.78rem", color: "var(--text-muted)" }}>
            Format: .pdf only • Max size: 20MB • Side-effect-free preview
          </div>
        </div>
      )}

      {error && (
        <div
          style={{
            marginTop: "1.25rem",
            padding: "1rem 1.25rem",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "var(--radius-md)",
            color: "#b91c1c",
            fontSize: "0.88rem",
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {/* 2. PREVIEW & INGESTION STAGE */}
      {preview && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.75rem" }}>
          {/* Header Action Bar */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <DocumentIcon size={18} />
              <span style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "1.05rem" }}>
                {preview.filename}
              </span>
              <span
                style={{
                  fontSize: "0.74rem",
                  padding: "0.15rem 0.5rem",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--bg-subtle)",
                  color: "var(--text-secondary)",
                  fontWeight: 600,
                  border: "1px solid var(--border-leaf)",
                }}
              >
                {preview.page_count} Pages • {preview.raw_text_length.toLocaleString()} Chars
              </span>
            </div>

            <button
              type="button"
              className="btn-secondary"
              onClick={handleReset}
            >
              Upload Different PDF
            </button>
          </div>

          {/* Duplicate Notice Banner */}
          {preview.duplicate_check.is_duplicate && (
            <div
              style={{
                padding: "1.1rem 1.25rem",
                background: "#fffbeb",
                border: "1px solid #fde68a",
                borderRadius: "var(--radius-md)",
                color: "#92400e",
                fontSize: "0.9rem",
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: "0.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span>⚠️</span> Catalog Duplicate Detected
              </div>
              <div>{preview.duplicate_check.explanation}</div>
              {preview.duplicate_check.matched_title && (
                <div style={{ marginTop: "0.35rem", fontSize: "0.82rem", color: "#b45309" }}>
                  Existing Catalog Match: <strong>{preview.duplicate_check.matched_title}</strong> (ID #{preview.duplicate_check.matched_catalog_id})
                </div>
              )}
            </div>
          )}

          {/* Ingested Success Confirmation Banner */}
          {ingestResult && (
            <div
              style={{
                padding: "1.25rem 1.5rem",
                background: "#ecfdf5",
                border: "1px solid #a7f3d0",
                borderRadius: "var(--radius-md)",
                color: "#065f46",
              }}
            >
              <div style={{ fontWeight: 700, fontSize: "1.1rem", marginBottom: "0.35rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span>✓</span> Manuscript Ingestion Confirmed!
              </div>
              <p style={{ margin: "0 0 0.75rem", fontSize: "0.9rem", color: "#047857" }}>
                {ingestResult.message}
              </p>
              <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", fontSize: "0.82rem" }}>
                <span style={{ padding: "0.2rem 0.6rem", background: "#ffffff", border: "1px solid #a7f3d0", borderRadius: "var(--radius-sm)" }}>
                  Catalog DB ID: <strong>#{ingestResult.catalog_id}</strong>
                </span>
                <span style={{ padding: "0.2rem 0.6rem", background: "#ffffff", border: "1px solid #a7f3d0", borderRadius: "var(--radius-sm)" }}>
                  Repository ID: <strong>{ingestResult.paper_id}</strong>
                </span>
                <span style={{ padding: "0.2rem 0.6rem", background: "#ffffff", border: "1px solid #a7f3d0", borderRadius: "var(--radius-sm)" }}>
                  FAISS Index: <strong>{ingestResult.faiss_indexed ? "✅ Synchronized" : "⚠️ Pending"}</strong>
                </span>
                {ingestResult.saved_to_library && (
                  <span style={{ padding: "0.2rem 0.6rem", background: "#ffffff", border: "1px solid #a7f3d0", borderRadius: "var(--radius-sm)" }}>
                    Personal Library: <strong>⭐ Bookmarked</strong>
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Ingest Error Banner */}
          {ingestError && (
            <div
              style={{
                padding: "1rem 1.25rem",
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: "var(--radius-md)",
                color: "#b91c1c",
                fontSize: "0.9rem",
              }}
            >
              ⚠️ {ingestError}
            </div>
          )}

          {/* Extracted Metadata Card */}
          <div
            style={{
              padding: "1.5rem",
              background: "#ffffff",
              border: "1px solid #e5e7eb",
              borderRadius: "var(--radius-md)",
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem", marginBottom: "0.75rem" }}>
              <h3 style={{ margin: 0, color: "#1f2937", fontSize: "1.25rem", fontWeight: 700, lineHeight: 1.4 }}>
                {preview.extracted_metadata.title}
              </h3>
              <span
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  padding: "0.2rem 0.6rem",
                  borderRadius: "999px",
                  background: preview.duplicate_check.is_duplicate ? "#fffbeb" : "#f3f4f6",
                  color: preview.duplicate_check.is_duplicate ? "#b45309" : "#4b5563",
                  border: `1px solid ${preview.duplicate_check.is_duplicate ? "#fde68a" : "#e5e7eb"}`,
                  whiteSpace: "nowrap",
                }}
              >
                {preview.duplicate_check.is_duplicate ? "⚠️ Duplicate in Catalog" : "Unpersisted Preview"}
              </span>
            </div>

            {/* Metadata Tags Row */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginBottom: "1rem" }}>
              {preview.extracted_metadata.authors.length > 0 && (
                <span className="metadata-badge">
                  👥 {preview.extracted_metadata.authors.join(", ")}
                </span>
              )}
              {preview.extracted_metadata.year && (
                <span className="metadata-badge">
                  📅 {preview.extracted_metadata.year}
                </span>
              )}
              {preview.extracted_metadata.doi && (
                <span className="metadata-badge">
                  🔗 DOI: {preview.extracted_metadata.doi}
                </span>
              )}
              {preview.extracted_metadata.venue && (
                <span className="metadata-badge">
                  🏛️ {preview.extracted_metadata.venue}
                </span>
              )}
              {preview.extracted_metadata.keywords.map((kw, i) => (
                <span key={i} className="keyword-tag">
                  #{kw}
                </span>
              ))}
            </div>

            {/* Abstract */}
            <div style={{ color: "var(--text-muted)", fontSize: "0.92rem", lineHeight: 1.6, marginBottom: "1.25rem" }}>
              {preview.extracted_metadata.abstract || (
                <span style={{ fontStyle: "italic", color: "var(--text-dim)" }}>
                  No explicit abstract detected. The raw text snippet below was used for vector recommendation search.
                </span>
              )}
            </div>

            {/* Toggle Raw Text Drawer */}
            <div style={{ borderTop: "1px solid #e5e7eb", paddingTop: "0.85rem", marginBottom: "1.25rem" }}>
              <button
                type="button"
                onClick={() => setShowRawText((prev) => !prev)}
                style={{
                  background: "none",
                  border: "none",
                  color: "#2563eb",
                  cursor: "pointer",
                  fontSize: "0.82rem",
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  gap: "0.35rem",
                  padding: 0,
                }}
              >
                <span>{showRawText ? "▼" : "▶"}</span>
                <span>{showRawText ? "Hide Extracted Manuscript Text Snippet" : "Inspect Extracted Manuscript Text Snippet"}</span>
              </button>

              {showRawText && (
                <div
                  style={{
                    marginTop: "0.75rem",
                    padding: "0.85rem 1rem",
                    background: "#f9fafb",
                    border: "1px solid #e5e7eb",
                    borderRadius: "var(--radius-sm)",
                    color: "#4b5563",
                    fontSize: "0.8rem",
                    lineHeight: 1.5,
                    fontFamily: "monospace",
                    maxHeight: "220px",
                    overflowY: "auto",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {preview.raw_text_preview}…
                </div>
              )}
            </div>

            {/* Explicit Confirmation Action Box */}
            <div
              style={{
                padding: "1rem 1.25rem",
                background: "#f9fafb",
                border: "1px solid #e5e7eb",
                borderRadius: "var(--radius-md)",
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
                <div>
                  <div style={{ fontWeight: 600, color: "#1f2937", fontSize: "0.95rem" }}>
                    Explicit Catalog Persistence
                  </div>
                  <div style={{ fontSize: "0.82rem", color: "#6b7280" }}>
                    Permanently stores manuscript metadata in PostgreSQL and computes a 768-dim SPECTER2 embedding in FAISS.
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  {isAuthenticated && (
                    <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.82rem", color: "#4b5563", cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={addToLibrary}
                        onChange={(e) => setAddToLibrary(e.target.checked)}
                        disabled={ingesting || !!ingestResult}
                        style={{ accentColor: "#1f2937" }}
                      />
                      Save to My Library
                    </label>
                  )}

                  <button
                    type="button"
                    className="btn-primary"
                    onClick={handleConfirmIngest}
                    disabled={ingesting || !!ingestResult || preview.duplicate_check.is_duplicate}
                  >
                    {ingesting
                      ? "Ingesting & Indexing FAISS…"
                      : ingestResult
                      ? "Added to Catalog"
                      : preview.duplicate_check.is_duplicate
                      ? "Duplicate (Already in Catalog)"
                      : "Add Manuscript to Catalog"}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Related Recommendations Section */}
          {preview.recommendations.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
                <div>
                  <h3 style={{ margin: "0 0 0.25rem", fontSize: "1.2rem", color: "#1f2937" }}>
                    🎯 Literature Recommendations ({preview.recommendations.length} Papers)
                  </h3>
                  <div style={{ fontSize: "0.82rem", color: "var(--text-dim)" }}>
                    Computed via SPECTER2 cosine similarity against live academic repositories & local FAISS index.
                  </div>
                </div>

                {onResultsExtracted && (
                  <button
                    type="button"
                    className="btn-secondary"
                    style={{ padding: "0.35rem 0.85rem", fontSize: "0.82rem" }}
                    onClick={() => {
                      onResultsExtracted({
                        query: preview.extracted_metadata.title,
                        mode: "pdf",
                        total_found: preview.recommendations.length,
                        results: preview.recommendations,
                        detected_keywords: preview.extracted_metadata.keywords,
                        execution_time_seconds: 0.1,
                      });
                    }}
                  >
                    Open in Explore Tab →
                  </button>
                )}
              </div>

              <div className="paper-cards-grid">
                {preview.recommendations.map((paper) => (
                  <PaperCard
                    key={paper.paper_id}
                    paper={paper}
                    isSaved={savedPaperIds.has(paper.paper_id)}
                    isSaving={savingPaperIds.has(paper.paper_id)}
                    isCompared={comparedIds.has(paper.paper_id)}
                    onToggleSave={onToggleSave || (() => {})}
                    onToggleCompare={onToggleCompare || (() => {})}
                    onOpenSummary={onOpenSummary || (() => {})}
                    onOpenEvidence={onOpenEvidence || (() => {})}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
