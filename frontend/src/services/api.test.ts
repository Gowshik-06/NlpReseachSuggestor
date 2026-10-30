import { describe, expect, it, vi, afterEach } from "vitest";
import {
  parseErrorData,
  comparePapers,
  ApiError,
  getAuthToken,
  setAuthToken,
  clearAuthToken,
  loginUser,
  logoutUser,
  getSavedPapers,
  getDriutStatus,
  savePaper,
  getPaperSummary,
  getPaperEvidence,
  previewPdf,
  ingestPdf,
} from "./api";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("API Error Parser (parseErrorData)", () => {
  it("parses structured backend error format: { error: { code, message } }", () => {
    const errorBody = {
      error: {
        code: "PAPER_NOT_FOUND",
        message: "Paper with identifier arxiv:9999.99999 not found",
      },
    };
    const message = parseErrorData(errorBody, 404);
    expect(message).toBe("Paper with identifier arxiv:9999.99999 not found");
  });

  it("parses FastAPI HTTPException string detail: { detail: '...' }", () => {
    const errorBody = { detail: "At least 2 unique papers must be selected for comparison" };
    const message = parseErrorData(errorBody, 400);
    expect(message).toBe("At least 2 unique papers must be selected for comparison");
  });

  it("parses FastAPI validation error array: { detail: [{ loc, msg }] }", () => {
    const errorBody = {
      detail: [
        {
          loc: ["body", "paper_ids"],
          msg: "List should have at least 2 items after validation",
          type: "too_short",
        },
      ],
    };
    const message = parseErrorData(errorBody, 422);
    expect(message).toBe("paper_ids: List should have at least 2 items after validation");
  });

  it("parses standard message object: { message: '...' }", () => {
    const errorBody = { message: "Resource temporarily unavailable" };
    const message = parseErrorData(errorBody, 503);
    expect(message).toBe("Resource temporarily unavailable");
  });

  it("handles plain-text error messages safely", () => {
    const message = parseErrorData("Bad Gateway: Upstream timed out", 504);
    expect(message).toBe("Bad Gateway: Upstream timed out");
  });

  it("sanitizes HTML responses without leaking HTML markup or stack traces", () => {
    const htmlResponse = "<html><body><h1>500 Internal Server Error</h1>Traceback (most recent call last): ...</body></html>";
    const message = parseErrorData(htmlResponse, 500);
    expect(message).toBe("Request failed with status 500");
  });

  it("handles empty or null response bodies gracefully", () => {
    expect(parseErrorData(null, 502)).toBe("Request failed with status 502");
    expect(parseErrorData(undefined, 404)).toBe("Request failed with status 404");
    expect(parseErrorData("", 500)).toBe("Request failed with status 500");
  });
});

describe("comparePapers API Service", () => {
  it("supports both integer database IDs and string paper_ids", async () => {
    const mockResponse = {
      papers: [
        { id: 1, paper_id: "arxiv:1810.04805", title: "BERT" },
        { id: 2, paper_id: "arxiv:1706.03762", title: "Attention" },
      ],
      comparison_points: [
        { dimension: "Core Architecture", points: { 1: "Bidirectional", 2: "Transformer" } },
      ],
      executive_summary: "Both papers explore attention.",
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(mockResponse),
      text: vi.fn().mockResolvedValue(JSON.stringify(mockResponse)),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await comparePapers([1, "arxiv:1706.03762"]);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/papers/compare"),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: [1, "arxiv:1706.03762"] }),
      })
    );
    expect(result.papers).toHaveLength(2);
    expect(result.executive_summary).toBe("Both papers explore attention.");
  });

  it("throws ApiError with parsed message on backend error", async () => {
    const errorPayload = {
      error: {
        code: "INVALID_IDENTIFIERS",
        message: "At least 2 unique papers must be selected for comparison",
      },
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: vi.fn().mockResolvedValue(errorPayload),
      text: vi.fn().mockResolvedValue(JSON.stringify(errorPayload)),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(comparePapers([1, 1])).rejects.toThrow(ApiError);
    await expect(comparePapers([1, 1])).rejects.toThrow(
      "At least 2 unique papers must be selected for comparison"
    );
  });

  it("handles network failures when backend is unavailable", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(comparePapers([1, 2])).rejects.toThrow(ApiError);
    await expect(comparePapers([1, 2])).rejects.toThrow(
      "Backend unavailable. Please check that the API server is running."
    );
  });
});

describe("Authentication & Session Management Service", () => {
  it("stores, retrieves, and clears authentication tokens in sessionStorage", () => {
    clearAuthToken();
    expect(getAuthToken()).toBeNull();

    setAuthToken("jwt.mock.token.123");
    expect(getAuthToken()).toBe("jwt.mock.token.123");

    clearAuthToken();
    expect(getAuthToken()).toBeNull();
  });

  it("attaches Bearer authorization header to protected requests when authenticated", async () => {
    setAuthToken("jwt.sample.token.456");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue([]),
    });
    vi.stubGlobal("fetch", fetchMock);

    await getSavedPapers();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/papers/saved"),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer jwt.sample.token.456",
        }),
      })
    );
    clearAuthToken();
  });

  it("automatically invalidates and clears expired token when backend returns 401 Unauthorized", async () => {
    setAuthToken("jwt.expired.token");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: vi.fn().mockResolvedValue({ detail: "Invalid or expired access token." }),
      text: vi.fn().mockResolvedValue(JSON.stringify({ detail: "Invalid or expired access token." })),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getSavedPapers()).rejects.toThrow(ApiError);
    expect(getAuthToken()).toBeNull();
  });

  it("stores token upon successful login and removes it on logout", async () => {
    clearAuthToken();

    const mockAuthResponse = {
      access_token: "jwt.login.success.token",
      token_type: "bearer",
      user: {
        id: 1,
        username: "testuser",
        email: "test@domain.com",
        is_active: true,
      },
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(mockAuthResponse),
    });
    vi.stubGlobal("fetch", fetchMock);

    const res = await loginUser({ username: "testuser", password: "Password123!" });
    expect(res.access_token).toBe("jwt.login.success.token");
    expect(getAuthToken()).toBe("jwt.login.success.token");

    logoutUser();
    expect(getAuthToken()).toBeNull();
  });

  it("fetches background monitoring status successfully via getDriutStatus", async () => {
    const mockStatus = {
      is_enabled: true,
      is_running_scan: false,
      interval_minutes: 60,
      last_run_time: "2026-10-09T15:00:00Z",
      last_run_duration_seconds: 1.25,
      last_run_status: "success",
      total_scans_completed: 5,
      last_scan_metrics: {
        users_scanned: 1,
        saved_papers_monitored: 3,
        candidates_evaluated: 15,
        new_alerts_created: 2,
        execution_time_seconds: 1.25,
      },
      provider_status: { arxiv: "healthy", pubmed: "healthy" },
      provider_errors: {},
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(mockStatus),
    });
    vi.stubGlobal("fetch", fetchMock);

    const res = await getDriutStatus();
    expect(res.is_enabled).toBe(true);
    expect(res.interval_minutes).toBe(60);
    expect(res.last_run_status).toBe("success");
    expect(res.provider_status.arxiv).toBe("healthy");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/papers/driut/status"),
      expect.any(Object)
    );
  });
});

describe("Transient External Candidate API Service (Task N1)", () => {
  const transientPaper = {
    id: null,
    paper_id: "arxiv:2401.99999",
    title: "Transient Attention Optimization",
    abstract: "We propose a transient memory attention optimization technique.",
    authors: ["Jane Doe", "John Smith"],
    venue: "arXiv preprint",
    year: 2024,
    source: "arxiv",
    url: "https://arxiv.org/abs/2401.99999",
    citation_count: 0,
    categories: ["cs.CL"],
  };

  it("comparePapers sends { items: ... } when Paper objects are provided", async () => {
    const mockResponse = {
      papers: [transientPaper],
      comparison_points: [],
      executive_summary: "Summary",
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(mockResponse),
      text: vi.fn().mockResolvedValue(JSON.stringify(mockResponse)),
    });
    vi.stubGlobal("fetch", fetchMock);

    await comparePapers([transientPaper, 42]);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/papers/compare"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ items: [transientPaper, 42] }),
      })
    );
  });

  it("getPaperSummary calls POST /api/v1/papers/summary with candidate for transient paper", async () => {
    const mockSummary = {
      paper_id: "arxiv:2401.99999",
      title: "Transient Attention Optimization",
      executive_summary: "Overview of transient attention",
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(mockSummary),
      text: vi.fn().mockResolvedValue(JSON.stringify(mockSummary)),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getPaperSummary(transientPaper as any);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/papers/summary"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ candidate: transientPaper }),
      })
    );
    expect(result.paper_id).toBe("arxiv:2401.99999");
  });

  it("getPaperEvidence calls POST /api/v1/papers/evidence with candidate for transient paper", async () => {
    const mockEvidence = {
      paper_id: "arxiv:2401.99999",
      paper_title: "Transient Attention Optimization",
      evidence_count: 1,
      evidence: [],
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(mockEvidence),
      text: vi.fn().mockResolvedValue(JSON.stringify(mockEvidence)),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getPaperEvidence(transientPaper as any, "method");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/papers/evidence"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ candidate: transientPaper, category: "method" }),
      })
    );
    expect(result.paper_id).toBe("arxiv:2401.99999");
  });

  it("savePaper attaches candidate payload when saving transient external candidate", async () => {
    const mockSaved = {
      id: 99,
      paper_id: 100,
      user_id: 1,
      paper: transientPaper,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(mockSaved),
      text: vi.fn().mockResolvedValue(JSON.stringify(mockSaved)),
    });
    vi.stubGlobal("fetch", fetchMock);

    await savePaper(null, "Notes on transient paper", ["ai", "nlp"], transientPaper as any);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/papers/save"),
      expect.objectContaining({
        method: "POST",
      })
    );
    const sentBody = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(sentBody).toEqual({
      candidate: transientPaper,
      paper_id: "arxiv:2401.99999",
      notes: "Notes on transient paper",
      tags: ["ai", "nlp"],
    });
  });
});

describe("Task N2: PDF Preview and Explicit Ingestion APIs", () => {
  it("previewPdf sends multipart/form-data to /papers/preview-pdf without persisting", async () => {
    const mockPreviewResponse = {
      filename: "test_manuscript.pdf",
      status: "preview_ready",
      extracted_metadata: {
        title: "Advances in Neural Architectures",
        abstract: "A study on transformers.",
        authors: ["Jane Doe"],
        year: 2024,
        doi: "10.1234/test.doi",
        venue: "NeurIPS",
        keywords: ["deep learning"],
      },
      page_count: 5,
      raw_text_preview: "Advances in Neural Architectures...",
      raw_text_length: 500,
      duplicate_check: {
        is_duplicate: false,
      },
      recommendations: [],
      warnings: [],
      allow_ingest: true,
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(mockPreviewResponse),
      text: vi.fn().mockResolvedValue(JSON.stringify(mockPreviewResponse)),
    });
    vi.stubGlobal("fetch", fetchMock);

    const dummyFile = new File(["%PDF-1.4 dummy"], "test_manuscript.pdf", { type: "application/pdf" });
    const res = await previewPdf(dummyFile, 5);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/papers/preview-pdf?limit=5"),
      expect.objectContaining({
        method: "POST",
      })
    );
    expect(res.status).toBe("preview_ready");
    expect(res.allow_ingest).toBe(true);
    expect(res.extracted_metadata.title).toBe("Advances in Neural Architectures");
  });

  it("ingestPdf sends explicit confirmation payload to /papers/ingest-pdf", async () => {
    const mockIngestResponse = {
      status: "success",
      paper_id: "pdf_advances_in_neural_architectures",
      catalog_id: 160,
      title: "Advances in Neural Architectures",
      faiss_indexed: true,
      saved_to_library: true,
      message: "Manuscript successfully ingested into catalog and index synchronized.",
      duplicate_detected: false,
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(mockIngestResponse),
      text: vi.fn().mockResolvedValue(JSON.stringify(mockIngestResponse)),
    });
    vi.stubGlobal("fetch", fetchMock);

    setAuthToken("fake-jwt-token");
    const res = await ingestPdf({
      title: "Advances in Neural Architectures",
      abstract: "A study on transformers.",
      authors: ["Jane Doe"],
      year: 2024,
      doi: "10.1234/test.doi",
      venue: "NeurIPS",
      keywords: ["deep learning"],
      confirm_ingest: true,
      add_to_library: true,
    });
    clearAuthToken();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/papers/ingest-pdf"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer fake-jwt-token",
          "Content-Type": "application/json",
        }),
      })
    );
    expect(res.status).toBe("success");
    expect(res.catalog_id).toBe(160);
    expect(res.faiss_indexed).toBe(true);
  });
});



