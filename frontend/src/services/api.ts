/**
 * Centralized API service layer.
 * All backend calls go through here.
 */
import type { HealthStatus } from "../types/health";
import type {
  Paper,
  SearchQueryRequest,
  SearchResponse,
  CompareResponse,
  SummaryResponse,
  SavedPaper,
  DRIUTAlert,
  DRIUTScanResponse,
  DRIUTStatus,
  PaperEvidenceResponse,
  PdfPreviewResponse,
  PdfIngestRequest,
  PdfIngestResponse,
} from "../types/paper";
import type {
  User,
  UserLoginRequest,
  UserRegisterRequest,
  TokenResponse,
  FirebaseLoginRequest,
  LinkFirebaseAccountRequest,
  LinkFirebaseAccountResponse,
} from "../types/auth";
import {
  getFirebaseIdToken,
  signOutFirebase,
  isFirebaseConfigured,
} from "./firebase";
import type {
  TimelineResponse,
  RelationshipGraphResponse,
  GapExplorationRequest,
  GapExplorationResponse,
  ResearchAssistantRequest,
  ResearchAssistantResponse,
  AIProviderStatus,
} from "../types/research";

const RAW_API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_BASE_URL: string = RAW_API_BASE_URL.replace(/\/+$/, "");

const TOKEN_STORAGE_KEY = "research_auth_token";
let inMemoryToken: string | null = null;

export function getAuthToken(): string | null {
  if (inMemoryToken) return inMemoryToken;
  try {
    inMemoryToken = sessionStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    inMemoryToken = null;
  }
  return inMemoryToken;
}

/**
 * Dynamically resolves the active Bearer token.
 * Uses the live Firebase ID token when Firebase is configured and active,
 * falling back to local storage only for local development/testing.
 */
export async function getActiveBearerToken(): Promise<string | null> {
  if (isFirebaseConfigured()) {
    try {
      const fbToken = await getFirebaseIdToken();
      if (fbToken) return fbToken;
    } catch {
      // ignore
    }
  }
  return getAuthToken();
}

export function setAuthToken(token: string | null): void {
  inMemoryToken = token;
  try {
    if (token) {
      sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // sessionStorage unavailable
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("auth-state-change", { detail: { token } }));
  }
}

export function clearAuthToken(): void {
  setAuthToken(null);
}

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Safely parse error messages from various backend error formats:
 * - Structured backend contract: {"error": {"code": "...", "message": "..."}}
 * - FastAPI HTTPExceptions: {"detail": "..."}
 * - FastAPI validation errors: {"detail": [{"loc": [...], "msg": "..."}]}
 * - Simple JSON: {"message": "..."}
 * - Plain-text fallback without exposing HTML/traces
 */
export function parseErrorData(data: unknown, status: number): string {
  if (!data || (typeof data !== "object" && typeof data !== "string")) {
    return `Request failed with status ${status}`;
  }

  if (typeof data === "string") {
    const trimmed = data.trim();
    if (trimmed.length > 0 && !trimmed.startsWith("<") && !trimmed.includes("Traceback")) {
      return trimmed.slice(0, 300);
    }
    return `Request failed with status ${status}`;
  }

  const record = data as Record<string, unknown>;

  // 1. Structured backend error contract: {"error": {"code": "...", "message": "..."}}
  if (record.error && typeof record.error === "object") {
    const errObj = record.error as Record<string, unknown>;
    if (typeof errObj.message === "string" && errObj.message.trim().length > 0) {
      return errObj.message.trim();
    }
  }

  // 2. FastAPI detail format: string or validation error list
  if (record.detail !== undefined && record.detail !== null) {
    if (typeof record.detail === "string" && record.detail.trim().length > 0) {
      return record.detail.trim();
    }
    if (Array.isArray(record.detail)) {
      const msgs = record.detail
        .map((item) => {
          if (item && typeof item === "object") {
            const errItem = item as Record<string, unknown>;
            const loc = Array.isArray(errItem.loc)
              ? errItem.loc.filter((part) => part !== "body").join(".")
              : "";
            const msg = typeof errItem.msg === "string" ? errItem.msg : String(item);
            return loc ? `${loc}: ${msg}` : msg;
          }
          return String(item);
        })
        .filter(Boolean);
      if (msgs.length > 0) {
        return msgs.join("; ");
      }
    }
  }

  // 3. Fallback message property: {"message": "..."}
  if (typeof record.message === "string" && record.message.trim().length > 0) {
    return record.message.trim();
  }

  return `Request failed with status ${status}`;
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  let response: Response;
  const token = await getActiveBearerToken();
  const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        ...(options.body instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
        ...authHeaders,
        ...options.headers,
      },
    });
  } catch (err) {
    throw new ApiError(
      "Backend unavailable. Please check that the API server is running."
    );
  }

  if (!response.ok) {
    if (response.status === 401 && token) {
      clearAuthToken();
      try {
        await signOutFirebase();
      } catch {
        // ignore
      }
    }

    let errMsg = `Request failed with status ${response.status}`;
    try {
      const text = await response.text();
      if (text && text.trim().length > 0) {
        try {
          const json = JSON.parse(text);
          errMsg = parseErrorData(json, response.status);
        } catch {
          errMsg = parseErrorData(text, response.status);
        }
      }
    } catch {
      // ignore
    }
    throw new ApiError(errMsg);
  }

  try {
    return (await response.json()) as T;
  } catch (err) {
    throw new ApiError("Received a malformed response from the server.");
  }
}

export function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>("/api/v1/health");
}

export function searchPapers(req: SearchQueryRequest): Promise<SearchResponse> {
  return request<SearchResponse>("/api/v1/papers/search", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function uploadPdf(file: File, limit: number = 10): Promise<SearchResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("limit", limit.toString());

  return request<SearchResponse>("/api/v1/papers/upload", {
    method: "POST",
    body: formData,
  });
}

export function previewPdf(file: File, limit: number = 10): Promise<PdfPreviewResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return request<PdfPreviewResponse>(`/api/v1/papers/preview-pdf?limit=${limit}`, {
    method: "POST",
    body: formData,
  });
}

export function ingestPdf(req: PdfIngestRequest): Promise<PdfIngestResponse> {
  return request<PdfIngestResponse>("/api/v1/papers/ingest-pdf", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function comparePapers(itemsOrIds: (number | string | Paper)[]): Promise<CompareResponse> {
  const hasObject = itemsOrIds.some((item) => typeof item === "object" && item !== null);
  const body = hasObject ? { items: itemsOrIds } : { paper_ids: itemsOrIds };
  return request<CompareResponse>("/api/v1/papers/compare", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getPaperSummary(paperOrId: string | Paper): Promise<SummaryResponse> {
  if (typeof paperOrId === "object" && paperOrId !== null) {
    if (paperOrId.id) {
      return request<SummaryResponse>(`/api/v1/papers/${encodeURIComponent(paperOrId.paper_id || String(paperOrId.id))}/summary`);
    } else {
      return request<SummaryResponse>("/api/v1/papers/summary", {
        method: "POST",
        body: JSON.stringify({ candidate: paperOrId }),
      });
    }
  }
  return request<SummaryResponse>(`/api/v1/papers/${encodeURIComponent(paperOrId)}/summary`);
}

export function getPaperEvidence(paperOrId: string | Paper, category?: string): Promise<PaperEvidenceResponse> {
  if (typeof paperOrId === "object" && paperOrId !== null) {
    if (paperOrId.id) {
      const query = category ? `?category=${encodeURIComponent(category)}` : "";
      return request<PaperEvidenceResponse>(`/api/v1/papers/${encodeURIComponent(paperOrId.paper_id || String(paperOrId.id))}/evidence${query}`);
    } else {
      return request<PaperEvidenceResponse>("/api/v1/papers/evidence", {
        method: "POST",
        body: JSON.stringify({ candidate: paperOrId, category }),
      });
    }
  }
  const query = category ? `?category=${encodeURIComponent(category)}` : "";
  return request<PaperEvidenceResponse>(`/api/v1/papers/${encodeURIComponent(paperOrId)}/evidence${query}`);
}

export function extractPaperEvidence(paperId: string, force: boolean = false): Promise<PaperEvidenceResponse> {
  return request<PaperEvidenceResponse>(`/api/v1/papers/${encodeURIComponent(paperId)}/evidence/extract`, {
    method: "POST",
    body: JSON.stringify({ force }),
  });
}

export function verifyPaperEvidence(paperId: string): Promise<any> {
  return request<any>(`/api/v1/papers/${encodeURIComponent(paperId)}/evidence/verify`);
}

// --- Authentication API Methods ---

export async function registerUser(req: UserRegisterRequest): Promise<TokenResponse> {
  const data = await request<TokenResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(req),
  });
  setAuthToken(data.access_token);
  return data;
}

export async function loginUser(req: UserLoginRequest): Promise<TokenResponse> {
  const data = await request<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(req),
  });
  setAuthToken(data.access_token);
  return data;
}

export async function getCurrentUser(): Promise<User> {
  const token = await getActiveBearerToken();
  if (!token) {
    return Promise.reject(new ApiError("No active authentication token."));
  }
  return request<User>("/api/v1/auth/me");
}

export function logoutUser(): void {
  clearAuthToken();
  if (isFirebaseConfigured()) {
    signOutFirebase().catch(() => {});
  }
}

export function firebaseLogin(idToken: string): Promise<TokenResponse> {
  return request<TokenResponse>("/api/v1/auth/firebase-login", {
    method: "POST",
    body: JSON.stringify({ id_token: idToken }),
  });
}

export function linkFirebaseAccount(
  payload: LinkFirebaseAccountRequest
): Promise<LinkFirebaseAccountResponse> {
  return request<LinkFirebaseAccountResponse>("/api/v1/auth/link-firebase", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// --- Authenticated & User-Isolated Library & DRIUT ---

export function getSavedPapers(): Promise<SavedPaper[]> {
  return request<SavedPaper[]>("/api/v1/papers/saved");
}

export function savePaper(
  paperId?: number | string | null,
  notes: string = "",
  tags: string[] = [],
  candidate?: Paper
): Promise<SavedPaper> {
  const payload: Record<string, unknown> = { notes, tags };
  if (candidate) {
    payload.candidate = candidate;
    payload.paper_id = candidate.paper_id;
  } else if (paperId !== undefined) {
    payload.paper_id = paperId;
  }
  return request<SavedPaper>("/api/v1/papers/save", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteSavedPaper(savedId: number): Promise<{ status: string; message: string }> {
  return request<{ status: string; message: string }>(`/api/v1/papers/saved/${savedId}`, {
    method: "DELETE",
  });
}

export function getDriutAlerts(): Promise<DRIUTAlert[]> {
  return request<DRIUTAlert[]>("/api/v1/papers/driut/alerts");
}

export function getDriutStatus(): Promise<DRIUTStatus> {
  return request<DRIUTStatus>("/api/v1/papers/driut/status");
}

export function triggerDriutScan(): Promise<DRIUTScanResponse> {
  return request<DRIUTScanResponse>("/api/v1/papers/driut/scan", {
    method: "POST",
  });
}

export function markAlertRead(alertId: number): Promise<{ status: string; alert_id: number; is_read: boolean }> {
  return request<{ status: string; alert_id: number; is_read: boolean }>(
    `/api/v1/papers/driut/alerts/${alertId}/read`,
    { method: "PATCH" }
  );
}

// ============================================================================
// TASK-16: Research Evolution Timeline, Relationship Graph, and Gap Explorer
// ============================================================================

export function getResearchTimeline(params?: {
  topic?: string;
  start_year?: number;
  end_year?: number;
  limit?: number;
}): Promise<TimelineResponse> {
  const query = new URLSearchParams();
  if (params?.topic) query.set("topic", params.topic);
  if (params?.start_year) query.set("start_year", String(params.start_year));
  if (params?.end_year) query.set("end_year", String(params.end_year));
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return request<TimelineResponse>(`/api/v1/research/timeline${qs ? `?${qs}` : ""}`);
}

export function getRelationshipGraph(params?: {
  topic?: string;
  start_year?: number;
  end_year?: number;
  min_similarity?: number;
  max_nodes?: number;
}): Promise<RelationshipGraphResponse> {
  const query = new URLSearchParams();
  if (params?.topic) query.set("topic", params.topic);
  if (params?.start_year) query.set("start_year", String(params.start_year));
  if (params?.end_year) query.set("end_year", String(params.end_year));
  if (params?.min_similarity !== undefined) query.set("min_similarity", String(params.min_similarity));
  if (params?.max_nodes !== undefined) query.set("max_nodes", String(params.max_nodes));
  const qs = query.toString();
  return request<RelationshipGraphResponse>(`/api/v1/research/graph${qs ? `?${qs}` : ""}`);
}

export function postCandidateGaps(payload: GapExplorationRequest): Promise<GapExplorationResponse> {
  return request<GapExplorationResponse>("/api/v1/research/gaps", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function askResearchAssistant(payload: ResearchAssistantRequest): Promise<ResearchAssistantResponse> {
  return request<ResearchAssistantResponse>("/api/v1/research/assistant", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAIStatus(): Promise<AIProviderStatus> {
  return request<AIProviderStatus>("/api/v1/research/ai/status");
}



