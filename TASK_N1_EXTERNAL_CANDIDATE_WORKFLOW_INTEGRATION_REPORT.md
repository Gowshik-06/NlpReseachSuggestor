# TASK N1 — Complete External Candidate Workflow Integration Report

## Executive Summary

ResearchLens Task N1 has been successfully implemented and verified end-to-end. Externally discovered academic candidates (papers retrieved on-the-fly from arXiv, PubMed, Indian CSIR, Semantic Scholar, Crossref, and DBLP with `id: None` / `id: null` and repository-qualified identifiers) now operate seamlessly across all system workflows:

1. **Side-Effect-Free Search:** External academic searches discover live candidate papers without mutating PostgreSQL, FAISS, or DRIUT alert state.
2. **Explicit Save to Library:** Authenticated researchers can save transient external candidates directly to their private library using validated repository-qualified identifiers and metadata, preventing duplicate records while preserving ownership isolation.
3. **Paper Summaries:** Transient candidates generate deterministic, structured executive summaries without requiring prior catalog ingestion. Insufficient abstract text truthfully produces grounded disclosures rather than hallucinations.
4. **Evidence Retrieval:** Grounded evidence passages are dynamically extracted from available transient source text with strictly validated character offsets, leaving the production evidence table untouched.
5. **Mixed & Multi-Candidate Comparison:** Side-by-side comparison fully supports arbitrary combinations of catalog-backed and transient external candidates across all 12 analytical dimensions.
6. **Frontend Integration:** Card actions, loading spinners (`⏳ Saving…`), disabled states during in-flight mutations, summary panels, evidence modals, and comparison selection operate smoothly with no silent no-ops.
7. **Zero Regression & Safety Verification:** All 18 dedicated N1 tests, 71 regression tests, 55 frontend tests, and production frontend builds pass with 100% success. Live database row counts and FAISS index hashes remained byte-for-byte identical.

---

## A. Implementation Summary

### 1. Root Cause & Architecture Alignment

Previously, external academic search results returned `id: null` to keep search side-effect-free (Task 1B). However, downstream operations (save, summary, evidence, compare) assumed every paper had an integer catalog primary key `paper.id`. When a user attempted to bookmark, summarize, inspect evidence, or compare external papers:
- The frontend silently skipped actions via guards like `if (paper.id)`.
- Backend endpoints returned HTTP 404 when querying `db.query(Paper).filter(Paper.id == paper_id)` or HTTP 422 when integer IDs were expected.

The N1 solution establishes a **canonical dual-contract** for academic papers:
- **Catalog-Backed Paper:** Persistent in PostgreSQL (`id: int`, `paper_id: str`).
- **Transient External Candidate:** Discovered live (`id: None` / `null`, stable `paper_id: str`, e.g. `arxiv:2403.99001v1`, `crossref:10.1000/182`, `pubmed:38291024`).

### 2. Files Created and Modified

| File Path | Type | Summary of Changes |
|---|---|---|
| `backend/app/schemas/paper.py` | Modified | Added DOI/venue validation, bounded payload validators for `SavePaperRequest` (`notes` ≤ 5000 chars, `tags` ≤ 30 items), enabled `Union[int, str]` in requests, added `PaperSummaryRequest`, `TransientEvidenceRequest`, and `CandidateComparisonItem`. |
| `backend/app/api/v1/endpoints/papers.py` | Modified | Updated `POST /save` to accept external candidates and resolve identity; updated `POST /compare` to support mixed candidate objects; updated `GET/POST /summary` and `GET/POST /evidence` to dynamically process transient text without database or FAISS writes; enforced URL scheme validation. |
| `backend/tests/test_n1_external_workflows.py` | Created | Comprehensive 18-test regression and security test suite covering catalog/transient save, user sanctuary isolation, duplicate handling, transient summaries, grounded character spans, 12-dimension comparisons, and zero-mutation invariants. |
| `frontend/src/types/paper.ts` | Modified | Updated `Paper` interface to allow `id?: number \| null` explicitly. |
| `frontend/src/services/api.ts` | Modified | Updated `savePaper` to forward candidate payload; updated `getPaperSummary` and `getPaperEvidence` to route transient objects to dedicated POST endpoints; updated `comparePapers` to pass full paper objects when comparing transient items. |
| `frontend/src/services/api.test.ts` | Modified | Added unit test coverage for transient candidate API calls (`comparePapers`, `getPaperSummary`, `getPaperEvidence`, and `savePaper`). |
| `frontend/src/components/PaperCard.tsx` | Modified | Enabled Save button for external papers (`paper.id == null`); added `isSaving` prop and loading state (`⏳ Saving…`); disabled button during pending requests. |
| `frontend/src/components/SummaryModal.tsx` | Modified | Passed complete `paper` object to `getPaperSummary(paper)` so transient candidates resolve without 404s. |
| `frontend/src/components/EvidenceModal.tsx` | Modified | Passed `paper` to `getPaperEvidence(paper)`; disabled persistent extraction attempt for unpersisted transient papers. |
| `frontend/src/components/CompareModal.tsx` | Modified | Updated `validPapers` resolution to pass paper objects directly to `comparePapers(validPapers)`. |
| `frontend/src/components/SavedLibraryView.tsx` | Modified | Fixed comparison indicator check to evaluate both `paper.paper_id` and catalog `paper.id`. |
| `frontend/src/pages/HomePage.tsx` | Modified | Updated `handleToggleSave` to support transient candidates; added `savingPaperIds` state set to prevent concurrent requests and render in-flight loading states. |

### 3. API Request / Response Contract Changes

- **`POST /api/v1/papers/save`:**
  - *Request Body:* Now accepts optional `candidate: PaperBase` alongside `paper_id: Optional[Union[int, str]]`, `notes: str`, and `tags: List[str]`.
  - *Behavior:* If `candidate` is provided for a paper not yet in PostgreSQL, the paper is explicitly persisted to the catalog and linked to the authenticated user's `SavedPaper` entry with concurrency handling.
  - *Validation:* `notes` bounded to 5,000 characters; `tags` bounded to 30 items; `title` bounded to 1,000 characters. Unsafe URL schemes (e.g. `javascript:`) are rejected with HTTP 422.
- **`POST /api/v1/papers/summary` & `GET /api/v1/papers/{paper_id}/summary`:**
  - Added `POST /api/v1/papers/summary` accepting `{"candidate": {...}}` or `{"paper_id": "..."}`.
  - Resolves catalog database papers, vector metadata, or supplied candidate in-memory.
  - Returns deterministic `SummaryResponse`. Abstracts <20 characters return structured insufficient-content disclosures without hallucinating.
- **`POST /api/v1/papers/evidence` & `GET /api/v1/papers/{paper_id}/evidence`:**
  - Added `POST /api/v1/papers/evidence` accepting `{"candidate": {...}, "category": "..."}`.
  - Dynamically extracts evidence passages from the candidate abstract with exact character offsets (`char_start`, `char_end`) without writing to `paper_evidence`.
- **`POST /api/v1/papers/compare`:**
  - Updated payload schema to accept `{"items": [...]}` where elements can be integer IDs, repository-qualified string IDs, or complete `Paper` objects. Backward-compatible with `{"paper_ids": [...]}`.
  - Preserves all 12 dimensions (`Core Architecture`, `Methodology`, `Datasets Evaluated`, `Key Performance Metrics`, `Reported Limitations`, etc.). Dimensions lacking source text truthfully report insufficient evidence.

### 4. Frontend Behavior Changes

- **Save Action:** The Bookmark button on external search cards is no longer disabled or ignored when `paper.id` is null. Clicking it triggers an explicit save request with the candidate payload.
- **Loading & State Feedback:** In-flight bookmark operations display `⏳ Saving…` and prevent double-clicks.
- **Sanctuary Isolation:** Unauthenticated bookmark clicks open the login modal; bookmark removal updates the library immediately.
- **Modals:** Summary and Evidence modals open immediately for external results without generating 404 API errors.
- **Comparison Drawer:** Checking the compare checkbox on external cards retains the full paper candidate and submits it to the comparison matrix.

---

## B. Workflow Support Matrix

| Workflow | Catalog-Backed Papers | Transient External Candidates | Mixed Combinations | Side-Effect Free? |
|---|---|---|---|---|
| **Search** | ✅ Supported | ✅ Supported | ✅ Supported | **Yes** (zero DB/FAISS/DRIUT writes) |
| **Save to Library** | ✅ Supported | ✅ Supported | N/A (per-paper action) | **Controlled** (deliberate user action persists saved record to private library) |
| **Paper Summary** | ✅ Supported | ✅ Supported | N/A (per-paper action) | **Yes** (pure in-memory deterministic summary) |
| **Evidence Retrieval** | ✅ Supported | ✅ Supported | N/A (per-paper action) | **Yes** (in-memory span extraction; zero DB rows written) |
| **Paper Comparison** | ✅ Supported | ✅ Supported | ✅ Supported (Catalog + Transient) | **Yes** (deterministic 12-dimension matrix; zero mutations) |

*Search remains strictly decoupled and side-effect-free: external searching does not populate the catalog, add vectors to FAISS, or create DRIUT monitoring alerts.*

---

## C. Test Evidence

### 1. Dedicated N1 Test Suite (`backend/tests/test_n1_external_workflows.py`)

Executed using isolated SQLite test database and isolated FAISS test directory:
```bash
venv/bin/pytest tests/test_n1_external_workflows.py -v
```

**Results:**
```text
======================== 18 passed, 7 warnings in 8.81s ========================
tests/test_n1_external_workflows.py::test_1_save_catalog_paper_by_authenticated_user PASSED [  5%]
tests/test_n1_external_workflows.py::test_2_save_transient_external_candidate PASSED [ 11%]
tests/test_n1_external_workflows.py::test_3_unauthenticated_save_is_rejected PASSED [ 16%]
tests/test_n1_external_workflows.py::test_4_duplicate_external_save_handled_cleanly PASSED [ 22%]
tests/test_n1_external_workflows.py::test_5_user_isolation_for_saved_transient_paper PASSED [ 27%]
tests/test_n1_external_workflows.py::test_6_invalid_or_missing_external_identity_rejected PASSED [ 33%]
tests/test_n1_external_workflows.py::test_7_provider_qualified_ids_remain_stable PASSED [ 38%]
tests/test_n1_external_workflows.py::test_8_catalog_summary_still_works PASSED [ 44%]
tests/test_n1_external_workflows.py::test_9_transient_summary_works_without_catalog_persistence PASSED [ 50%]
tests/test_n1_external_workflows.py::test_10_insufficient_abstract_produces_grounded_response PASSED [ 55%]
tests/test_n1_external_workflows.py::test_11_catalog_evidence_retrieval PASSED [ 61%]
tests/test_n1_external_workflows.py::test_12_and_13_transient_evidence_offsets_and_grounding PASSED [ 66%]
tests/test_n1_external_workflows.py::test_14_catalog_to_catalog_comparison PASSED [ 72%]
tests/test_n1_external_workflows.py::test_15_and_17_catalog_to_transient_comparison PASSED [ 77%]
tests/test_n1_external_workflows.py::test_16_and_18_transient_to_transient_comparison_and_truthfulness PASSED [ 83%]
tests/test_n1_external_workflows.py::test_19_malformed_and_oversized_payloads_rejected PASSED [ 88%]
tests/test_n1_external_workflows.py::test_20_unsafe_url_schemes_rejected PASSED [ 94%]
tests/test_n1_external_workflows.py::test_21_to_24_zero_side_effects_on_readonly_workflows PASSED [100%]
```

### 2. Regression Test Suite

Executed all regression suites across Tasks 1A, 1B, 2, and 3:
```bash
venv/bin/pytest tests/test_search_ingestion_decoupling.py \
                tests/test_local_search_correctness.py \
                tests/test_isolation_verification.py \
                tests/test_cors_configuration.py \
                tests/test_auth_and_isolation.py \
                tests/test_paper_comparison.py \
                tests/test_evidence_extraction.py -v
```

**Results:**
```text
======================= 71 passed, 4 warnings in 12.90s ========================
```
- Task 1A Local Search Correctness: 6/6 passed.
- Task 1B Search-Ingestion Decoupling: 8/8 passed.
- Task 2 Test Isolation Shield: 7/7 passed.
- Task 3 CORS Alignment: 7/7 passed.
- Authentication & User Isolation: 8/8 passed.
- Paper Comparison Matrix: 12/12 passed.
- Grounded Evidence Extraction: 23/23 passed.

### 3. Frontend Unit Tests & Production Build

Executed frontend test suite and TypeScript production build:
```bash
cd frontend && npm test
```
**Results:**
```text
 Test Files  6 passed (6)
      Tests  55 passed (55)
   Duration  1.26s
```

```bash
cd frontend && npm run build
```
**Results:**
```text
> tsc -b && vite build
vite v5.4.21 building for production...
✓ 47 modules transformed.
dist/index.html                   0.95 kB │ gzip:  0.53 kB
dist/assets/index-DtwgOF85.css   14.37 kB │ gzip:  3.88 kB
dist/assets/index-y-ZS3yXX.js   277.16 kB │ gzip: 78.05 kB
✓ built in 647ms
```

### 4. Live Runtime Smoke-Test Results

Executed live against the running backend (`http://localhost:8000/api/v1`) using a real external paper discovered from Crossref (`crossref:10.4135/9781506368603.n9`):
1. **Live Discovery:** Successfully retrieved external paper without catalog persistence (`id: None`).
2. **Transient Summary:** Generated deterministic summary without 404 (`HTTP 200 OK`).
3. **Transient Evidence:** Evaluated available text, truthfully reporting `status: insufficient_text` due to lack of extractable abstract in Crossref metadata (`HTTP 200 OK`).
4. **Mixed Comparison:** Compared catalog paper `107` (`pubmed:42635983`) with transient candidate `crossref:10.4135/9781506368603.n9` across all 12 dimensions (`HTTP 200 OK`).
5. **Authentication Shield:** Confirmed unauthenticated save request is rejected with `HTTP 401 Unauthorized`.
6. **Zero Live Mutation:** Verified that the live PostgreSQL container, FAISS index, and DRIUT tables had zero changes.

---

## D. Persistence Invariants & Safety Baselines

| Resource / Metric | Pre-Implementation Baseline | Post-Implementation State | Delta | Status |
|---|---|---|---|---|
| **Users** (`users` table) | 6 | 6 | 0 | **Preserved** |
| **Catalog Papers** (`papers` table) | 158 | 158 | 0 | **Preserved** |
| **Saved Papers** (`saved_papers` table) | 1 | 1 | 0 | **Preserved** |
| **DRIUT Alerts** (`driut_alerts` table) | 31 | 31 | 0 | **Preserved** |
| **Paper Evidence** (`paper_evidence` table) | 1 | 1 | 0 | **Preserved** |
| **FAISS Vector Count** | 159 vectors | 159 vectors | 0 | **Preserved** |
| **FAISS Vector Dimension** | 768 | 768 | 0 | **Preserved** |
| **`research_index.faiss` SHA-256** | `e91a9e852bde2ade4555e5b45ae3477abca612f6909b2bd8fcacfdc79952ae30` | `e91a9e852bde2ade4555e5b45ae3477abca612f6909b2bd8fcacfdc79952ae30` | 0 | **Byte-for-byte identical** |
| **`papers_meta.json` SHA-256** | `a5f431dc3261c1da8290e3822773e21f439b9a0e216e418660a7ae9bafa7f4e8` | `a5f431dc3261c1da8290e3822773e21f439b9a0e216e418660a7ae9bafa7f4e8` | 0 | **Byte-for-byte identical** |

**Zero-polluting isolation confirmed:** No production test writes occurred; live database and FAISS index remained untouched throughout the entire implementation and testing process.

---

## E. Known Limitations

1. **Provider Metadata Completeness:** Certain upstream providers (e.g. Crossref book entries or metadata stubs) do not provide full abstracts. In these cases, evidence extraction and comparison dimensions truthfully return `insufficient_text` / `insufficient_evidence` disclosures rather than fabricating claims.
2. **Explicit PDF Ingestion (Task N2):** Ingesting arbitrary PDF files directly into the catalog and synchronizing FAISS vectors is explicitly part of the subsequent task (N2) and was deliberately excluded from N1.
3. **External Rate Limits:** External academic providers (e.g. arXiv and PubMed) occasionally enforce IP-level rate limits during rapid consecutive automated queries. The backend gracefully catches upstream timeouts and returns available local and cached results.

---

## F. Final Verdict

**PASS — N1 complete and verified**

All 7 required workflow domains are fully operational. External candidates operate seamlessly across search, bookmarking, summaries, evidence retrieval, and 12-dimensional comparisons. Backend and frontend tests are 100% green, and all safety and persistence invariants are rigorously satisfied.
