# TASK-13 — ResearchLens Evidence-Grounded Research Intelligence Report

**Date of Execution:** 2026-10-10  
**Implementation Priority:** High (Grounding, Evidence Traceability, and Scientific Provenance)  
**Implementation Status:** Complete & Verified  
**System Evaluated:** ResearchLens NLP-Based Research Paper Recommendation System  
**Workspace Path:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem`  
**Repository Path:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Reference Report:** `TASK_12_EMBEDDING_AND_INDEX_SYNC_REPORT.md`  

---

## 1. Executive Summary

TASK-13 established a trustworthy, evidence-grounded research intelligence layer for ResearchLens. Rather than relying on generative hallucinations or synthetic template responses, the new evidence layer extracts and grounds scientific claims in real source passages across 9 academic categories with deterministic span offsets, provenance metadata, document freshness hashing, and atomic database persistence.

### Key Deliverables Implemented & Validated:
1. **Deterministic Scientific Evidence Extraction Engine:** Implemented [backend/app/services/evidence_service.py](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backend/app/services/evidence_service.py) supporting all 9 required academic categories (`problem`, `objective`, `method`, `dataset`, `metrics`, `results`, `contributions`, `limitations`, `future_work`). Preserves exact character offsets (`char_start`, `char_end`), disambiguates author claims, and marks missing information as unstated rather than fabricating assertions.
2. **Reusable Provenance & Verification Layer:** Stored evidence records track source type (`abstract` vs `full_text`), section names, and page numbers when reliably available (zero fabrication). Features SHA-256 source document hashing (`source_hash`) that automatically flags stale evidence when paper text is edited.
3. **Relational Persistence & Safe Migration:** Created the `paper_evidence` PostgreSQL model and idempotent migration in [backend/app/db/migrate_evidence.py](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backend/app/db/migrate_evidence.py). Re-extraction is atomic and idempotent, preventing duplicate or orphaned records.
4. **FastAPI Endpoints:** Versioned endpoints in [backend/app/api/v1/endpoints/papers.py](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backend/app/api/v1/endpoints/papers.py):
   - `POST /api/v1/papers/{paper_id}/evidence/extract` (authenticated with JWT Bearer token)
   - `GET /api/v1/papers/{paper_id}/evidence` (retrieval with category filtering)
   - `GET /api/v1/papers/{paper_id}/evidence/verify` (source-span and freshness audit)
5. **Frontend Evidence UI:** Built [frontend/src/components/EvidenceModal.tsx](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/frontend/src/components/EvidenceModal.tsx) integrating category tabs, concise claims, collapsible source passage inspections, provenance badges, abstract-derived warnings, missing-evidence notices, and re-extraction controls into [frontend/src/components/PaperCard.tsx](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/frontend/src/components/PaperCard.tsx) and [frontend/src/pages/HomePage.tsx](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/frontend/src/pages/HomePage.tsx).
6. **Zero Regression & Absolute Preservation:** Baseline host FAISS indexes (`research_index.faiss`, `papers_meta.json`) preserved byte-for-byte. Container FAISS index synchronized to 132/132 papers. All 106 backend tests and 29 frontend tests pass with 100% success.

---

## 2. Git Status and Repository Integrity

### Initial Status
- **Branch:** `master` at commit `c26cd6a`
- **Working Tree:** 37 staged files, 23 unstaged files, 19 untracked files. All strictly preserved.

### Final Status
- **Working Tree:** All 37 staged files and pre-existing unstaged/untracked files preserved intact. Zero git resets, cleans, stashes, checkouts, or commits executed.
- **Files Modified / Added:**
  - `backend/app/models/evidence.py` (New: `PaperEvidence` SQLAlchemy model)
  - `backend/app/models/paper.py` (Modified: added `evidence_records` relationship to `Paper`)
  - `backend/app/models/__init__.py` (Modified: exported `PaperEvidence`)
  - `backend/app/db/migrate_evidence.py` (New: idempotent database migration script)
  - `backend/app/db/init_db.py` (Modified: registered `PaperEvidence` in database initialization)
  - `backend/app/schemas/evidence.py` (New: typed Pydantic evidence schemas)
  - `backend/app/services/evidence_service.py` (New: extraction, span validation, and freshness service)
  - `backend/app/api/v1/endpoints/papers.py` (Modified: registered extract, get, and verify endpoints)
  - `backend/tests/test_evidence_extraction.py` (New: 21 comprehensive backend tests)
  - `frontend/src/types/paper.ts` (Modified: added `PaperEvidenceItem`, `PaperEvidenceResponse`, `EvidenceVerificationSummary`)
  - `frontend/src/services/api.ts` (Modified: added `getPaperEvidence`, `extractPaperEvidence`, `verifyPaperEvidence`)
  - `frontend/src/components/EvidenceModal.tsx` (New: React component for evidence inspection)
  - `frontend/src/components/EvidenceModal.test.tsx` (New: 10 frontend unit/component tests)
  - `frontend/src/components/PaperCard.tsx` (Modified: added `🔬 Evidence` action button and prop)
  - `frontend/src/components/SavedLibraryView.tsx` (Modified: added `🔬 Evidence` action button and prop)
  - `frontend/src/pages/HomePage.tsx` (Modified: wired `evidencePaper` state, props, and modal)

---

## 3. Evidence Extraction & Verification Architecture

```
                               ┌──────────────────────────────────────────────┐
                               │             Paper Input Source               │
                               │  (abstract: str, raw_text: Optional[str])    │
                               └──────────────────────┬───────────────────────┘
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       ▼                                                             ▼
         ┌───────────────────────────┐                                 ┌───────────────────────────┐
         │     Abstract Source       │                                 │    Full-Text Manuscript   │
         │  (source_type="abstract") │                                 │ (source_type="full_text") │
         └─────────────┬─────────────┘                                 └─────────────┬─────────────┘
                       │                                                             │
                       └──────────────────────────────┬──────────────────────────────┘
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │     Scientific Sentence & Span Scanner       │
                               │     - Decimal-aware boundaries (e.g., 3.5x)  │
                               │     - Abbreviation safe (et al., e.g., i.e.) │
                               │     - Header & page boundary detection       │
                               │     Guarantees: text[start:end] == passage   │
                               └──────────────────────┬───────────────────────┘
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │   Pattern-Matching & Disambiguation Engine   │
                               │   Evaluates 9 Categories:                    │
                               │   • problem        • results                 │
                               │   • objective      • contributions           │
                               │   • method         • limitations             │
                               │   • dataset        • future_work             │
                               │   • metrics                                  │
                               │   Extracts author claims (zero fabrication)  │
                               └──────────────────────┬───────────────────────┘
                                                      ▼
                       ┌──────────────────────────────┴──────────────────────────────┐
                       │                                                             │
                       ▼                                                             ▼
        [ Categories Present ]                                         [ Missing Categories ]
        - Exact source passage                                         - Explicitly listed as unstated
        - char_start, char_end                                         - Zero synthetic statements
        - Calibrated confidence score                                  - Cleanly returned to client
        - Provenance (section, page)                                                 │
                       │                                                             │
                       └──────────────────────────────┬──────────────────────────────┘
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │       Verification & Integrity Layer         │
                               │  - Mathematical span matching in source text │
                               │  - SHA-256 document freshness hashing        │
                               │  - Provenance & metadata validity checks     │
                               └──────────────────────┬───────────────────────┘
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │    Atomic PostgreSQL Persistence & Cache     │
                               │      (paper_evidence table via SQLAlchemy)   │
                               └──────────────────────────────────────────────┘
```

### The 9 Supported Evidence Categories
1. **`problem`:** Research problem and motivation (e.g., computational bottlenecks, vulnerabilities, limitations of prior work).
2. **`objective`:** Research objective or research question (e.g., goals, investigated hypotheses, focal tasks).
3. **`method`:** Proposed method or architecture (e.g., introduced algorithms, neural network modules, frameworks).
4. **`dataset`:** Dataset and experimental setup (e.g., benchmarks, evaluation corpora, compute environments).
5. **`metrics`:** Evaluation metrics (e.g., BLEU, F1, accuracy, throughput, AUC-ROC, latency).
6. **`results`:** Reported results and findings (e.g., empirical improvements, outperformance over baselines, SOTA achievements).
7. **`contributions`:** Authors' stated contributions (e.g., primary theoretical or empirical advancements).
8. **`limitations`:** Limitations and threats to validity (e.g., sequence length constraints, assumptions, computational overhead).
9. **`future_work`:** Future work directions (e.g., planned extensions, open questions, future investigations).

---

## 4. Database Schema and Migration Details

The `paper_evidence` table was added via [backend/app/db/migrate_evidence.py](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backend/app/db/migrate_evidence.py):

```sql
CREATE TABLE IF NOT EXISTS paper_evidence (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    claim TEXT NOT NULL,
    source_passage TEXT NOT NULL,
    char_start INTEGER,
    char_end INTEGER,
    page_number INTEGER,
    section_name VARCHAR(100),
    source_type VARCHAR(50) NOT NULL DEFAULT 'abstract',
    extraction_method VARCHAR(50) NOT NULL DEFAULT 'rule_based_nlp',
    confidence_score FLOAT,
    is_verified BOOLEAN NOT NULL DEFAULT TRUE,
    verification_notes VARCHAR(255),
    source_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Unique constraint ensuring span idempotency
ALTER TABLE paper_evidence
ADD CONSTRAINT uq_paper_evidence_span
UNIQUE (paper_id, category, char_start, char_end);

-- Query and filtering indexes
CREATE INDEX IF NOT EXISTS ix_paper_evidence_paper_id ON paper_evidence(paper_id);
CREATE INDEX IF NOT EXISTS ix_paper_evidence_category ON paper_evidence(category);
CREATE INDEX IF NOT EXISTS ix_paper_evidence_source_type ON paper_evidence(source_type);
CREATE INDEX IF NOT EXISTS ix_paper_evidence_source_hash ON paper_evidence(source_hash);
```

### Rollback Procedure
If required, the rollback procedure in `migrate_evidence_rollback()` cleanly executes:
```sql
DROP TABLE IF EXISTS paper_evidence CASCADE;
```
Zero data in pre-existing tables (`papers`, `users`, `saved_papers`, `driut_alerts`) is touched or modified.

---

## 5. API Endpoints and Example Responses

### 1. `POST /api/v1/papers/{paper_id}/evidence/extract`
Extracts or refreshes grounded evidence for a paper. Requires authentication via JWT Bearer token.
- **Request:**
  ```http
  POST /api/v1/papers/67/evidence/extract HTTP/1.1
  Host: localhost:8000
  Authorization: Bearer <access_token>
  Content-Type: application/json

  {"force": true}
  ```
- **Response (HTTP 200 OK):**
  ```json
  {
    "paper_id": "arxiv:2609.35768v1",
    "paper_title": "PDMD: Projected Distribution Matching Distillation for Video Diffusion Models",
    "status": "partial_extraction",
    "source_type": "abstract",
    "evidence_count": 1,
    "categories_present": ["method"],
    "missing_categories": [
      "problem",
      "objective",
      "dataset",
      "metrics",
      "results",
      "contributions",
      "limitations",
      "future_work"
    ],
    "evidence": [
      {
        "id": 519,
        "paper_id": 67,
        "category": "method",
        "category_label": "Proposed Method / Approach",
        "claim": "We introduce Projected Distribution Matching Distillation (PDMD) to filter critic errors.",
        "source_passage": "We introduce Projected Distribution Matching Distillation (PDMD) to filter critic errors.",
        "char_start": 427,
        "char_end": 516,
        "page_number": null,
        "section_name": "Abstract",
        "source_type": "abstract",
        "extraction_method": "rule_based_nlp",
        "confidence_score": 0.95,
        "is_verified": true,
        "verification_notes": "Exact span verified in abstract (Abstract)",
        "source_hash": "8c398dbe7e9cc3515dac082ada81b8fdceb00d88e5e11dd5d94cc361ac487830",
        "created_at": "2026-10-09T21:55:02.204048Z",
        "updated_at": "2026-10-09T21:55:02.204048Z"
      }
    ],
    "verification_summary": {
      "total_evidence": 1,
      "verified_count": 1,
      "is_stale": false,
      "source_type": "abstract",
      "char_offsets_valid": true,
      "nonempty_passages": true,
      "verification_message": "Successfully extracted 1 grounded evidence items from abstract."
    }
  }
  ```

### 2. `GET /api/v1/papers/{paper_id}/evidence`
Retrieves evidence records with optional category filtering (`?category=method`).
- **Response (HTTP 200 OK):** Same structure as above.
- **Unauthenticated Extract Behavior:** Returns HTTP 401:
  ```json
  {"error": {"code": "HTTP_ERROR", "message": "Authentication required. Please provide a valid Bearer token."}}
  ```
- **Invalid Category Filter:** Returns HTTP 400:
  ```json
  {"error": {"code": "HTTP_ERROR", "message": "Invalid evidence category 'invalid_cat'. Valid categories: ['problem', 'objective', 'method', 'dataset', 'metrics', 'results', 'contributions', 'limitations', 'future_work']"}}
  ```
- **Nonexistent Paper:** Returns HTTP 404:
  ```json
  {"error": {"code": "HTTP_ERROR", "message": "Paper with identifier '999999' not found."}}
  ```

### 3. `GET /api/v1/papers/{paper_id}/evidence/verify`
Runs an automated integrity and source-span verification audit.
- **Response (HTTP 200 OK):**
  ```json
  {
    "paper_id": "arxiv:2609.35768v1",
    "paper_title": "PDMD: Projected Distribution Matching Distillation for Video Diffusion Models",
    "total_records": 1,
    "all_valid": true,
    "audit_results": [
      {
        "evidence_id": 519,
        "category": "method",
        "claim": "We introduce Projected Distribution Matching Distillation (PDMD) to filter critic errors.",
        "source_passage": "We introduce Projected Distribution Matching Distillation (PDMD) to filter critic errors.",
        "char_start": 427,
        "char_end": 516,
        "source_type": "abstract",
        "verification": {
          "is_valid": true,
          "span_valid": true,
          "passage_in_text": true,
          "is_stale": false,
          "current_source_type": "abstract",
          "source_type_match": true,
          "reason": "Verified"
        }
      }
    ]
  }
  ```

---

## 6. Frontend Integration Details

The frontend integration adheres to the dark forest glassmorphic theme:
1. **Modal Architecture ([EvidenceModal.tsx](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/frontend/src/components/EvidenceModal.tsx)):**
   - **Header:** Displays paper title, source provenance badges (`📄 Full-Text Source` vs `📝 Abstract-Derived`).
   - **Provenance Banner:** When evidence is derived from an abstract, explicitly warns researchers that claims have not been verified against full text.
   - **Staleness Notice:** Alerts users when a paper's text has changed since extraction and provides a 1-click refresh action.
   - **Category Navigation Tabs:** Filter evidence items by category with real-time item counts.
   - **Grounded Evidence Cards:** Displays category icons, concise claims, collapsible verbatim source passages with quotes, exact character offsets (`chars 427–516`), section names (`📑 Methodology`), page numbers (`📄 Page 2`), and linguistic match indicators (`✓ 95% Match`).
   - **Missing Categories Section:** Lists all categories not stated in the source text, explicitly stating that zero synthetic claims were fabricated.
   - **Loading, Empty, & Error States:** Clear visual indicators for pending extraction, unavailable text, and network retries.
2. **Card Actions Integration ([PaperCard.tsx](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/frontend/src/components/PaperCard.tsx), [SavedLibraryView.tsx](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/frontend/src/components/SavedLibraryView.tsx)):** Added `🔬 Evidence` button beside `🧠 AI Summary`, opening the modal on click.

---

## 7. Verification and Testing Results

### Backend Automated Test Suite
Executed command:
```bash
./venv/bin/pytest tests/
```

**Results:**
- Total tests executed: **106 tests**
- Passed: **106 passed** (100% pass rate)
- Warnings: 5 deprecation warnings from dependencies (Starlette / SlowAPI)
- Execution time: **27.69s**

**Breakdown of Test Modules:**
- `tests/test_evidence_extraction.py`: **21 passed** (New: covers all 15 backend criteria from Section 9)
  - `test_extract_evidence_all_nine_categories` (Passed)
  - `test_missing_or_empty_paper_text` (Passed)
  - `test_malformed_or_insufficient_text` (Passed)
  - `test_partial_extraction_no_hallucination` (Passed)
  - `test_verify_evidence_record_valid_span` (Passed)
  - `test_verify_evidence_record_rejects_corrupted_span` (Passed)
  - `test_verify_evidence_record_rejects_empty_passage` (Passed)
  - `test_staleness_detection_on_source_text_change` (Passed)
  - `test_extract_and_persist_idempotency` (Passed)
  - `test_re_extraction_updates_cleanly_after_text_edit` (Passed)
  - `test_api_get_evidence_success` (Passed)
  - `test_api_get_evidence_by_numeric_id` (Passed)
  - `test_api_get_evidence_category_filter` (Passed)
  - `test_api_get_evidence_invalid_category` (Passed)
  - `test_api_get_evidence_missing_paper_404` (Passed)
  - `test_api_extract_evidence_requires_auth` (Passed)
  - `test_api_extract_evidence_authenticated` (Passed)
  - `test_api_verify_endpoint` (Passed)
  - `test_api_unavailable_text_handling` (Passed)
  - `test_full_text_provenance_and_page_detection` (Passed)
  - `test_cross_user_isolation_private_resources` (Passed)
- `tests/test_academic_sources.py`: **11 passed**
- `tests/test_auth_and_isolation.py`: **8 passed**
- `tests/test_driut_scheduler.py`: **16 passed**
- `tests/test_embedding_and_sync.py`: **13 passed**
- `tests/test_faiss_consistency.py`: **6 passed**
- `tests/test_health.py`: **5 passed**
- `tests/test_papers_api.py`: **16 passed**
- `tests/test_pdf_upload.py`: **6 passed**
- `tests/test_rate_limiter.py`: **4 passed**

---

### Frontend Automated Test Suite
Executed command:
```bash
npm test -- --run
```

**Results:**
- Total test files: **3 passed**
- Total tests: **29 passed** (100% pass rate)
  - `src/components/EvidenceModal.test.tsx`: **10 passed**
  - `src/services/api.test.ts`: **15 passed**
  - `src/App.test.tsx`: **4 passed**
- Execution time: **949ms**

---

### Frontend Production Build
Executed command:
```bash
npm run build
```

**Results:**
- TypeScript typecheck (`tsc -b`): Passed (0 errors)
- Vite build: Completed in **669ms**
- Output artifacts generated in `dist/`:
  - `dist/index.html`: 0.95 kB (gzip: 0.53 kB)
  - `dist/assets/index-DtwgOF85.css`: 14.37 kB (gzip: 3.88 kB)
  - `dist/assets/index-BWkrUf_O.js`: 219.99 kB (gzip: 66.96 kB)

---

## 8. Database and FAISS Provenance Counts

| Metric | Before TASK-13 | After TASK-13 | Change | Status |
| :--- | :--- | :--- | :--- | :--- |
| **PostgreSQL `papers`** | 114 | 132 | +18 (live search ingestion) | Preserved |
| **PostgreSQL `users`** | 3 | 5 | +2 (test users) | Preserved |
| **PostgreSQL `saved_papers`** | 1 | 1 | 0 | Preserved |
| **PostgreSQL `driut_alerts`** | 18 | 23 | +5 | Preserved |
| **PostgreSQL `paper_evidence`** | 0 | 1 | +1 (live test extraction) | Verified |
| **Host FAISS vectors** | 10 | 10 | 0 | Unmodified |
| **Host `research_index.faiss` SHA-256** | `59932548...` | `59932548...` | Identical | Preserved |
| **Host `papers_meta.json` SHA-256** | `f0275c27...` | `f0275c27...` | Identical | Preserved |
| **Container FAISS vectors** | 114 | 132 | +18 | Synchronized (100%) |
| **Vector Dimension** | 768 | 768 | 0 | Verified Invariant |
| **Index Consistency Status** | 100% Sync | 100% Sync | 0 orphans, 0 missing | Verified |

---

## 9. Known Limitations and False-Positive Risks

1. **Linguistic Heuristic Extraction:** The extraction engine uses pattern-based linguistic rules and syntactic span boundaries rather than large generative LLMs. While this ensures deterministic reproducibility and prevents hallucinations, complex or atypically phrased academic sentences may not match patterns, leading to missing categories (`status: partial_extraction`).
2. **Abstract-Only Coverage:** Papers ingested via external APIs (arXiv, PubMed, CSIR) typically only have title and abstract available unless a full PDF is uploaded. Abstract-derived evidence is clearly marked as such, but cannot provide detailed experimental setup tables or multi-page methodology discussions.
3. **Text-Based PDF Requirement:** As specified in Section 3, only text-based PDFs are supported. Scanned PDFs without embedded text or OCR return `unavailable_text`.
4. **Limits of Automated Verification:** The verification layer verifies mathematical span correspondence (`source_text[start:end] == passage`) and document hash consistency. It confirms that the extracted claim is grounded in real text, but does not claim full philosophical semantic validation of author truthfulness.

---

## 10. Acceptance Criteria Evaluation

| # | Acceptance Criterion | Evaluation | Verification Evidence |
| :---: | :--- | :---: | :--- |
| 1 | Reusable evidence-extraction service exists | **PASS** | `app/services/evidence_service.py` implements `extract_evidence_from_text` and `extract_and_persist_paper_evidence` |
| 2 | Claims are linked to real source passages | **PASS** | Strict span invariant `source_text[char_start:char_end] == passage` verified in 21 tests and live requests |
| 3 | Source type and provenance are represented accurately | **PASS** | `source_type` (`abstract` vs `full_text`), section names, and page numbers accurately labeled |
| 4 | Missing information is not fabricated | **PASS** | Missing categories explicitly returned in `missing_categories`; zero synthetic fallback text generated |
| 5 | Evidence can be persisted and retrieved reliably | **PASS** | PostgreSQL `paper_evidence` table with foreign key to `papers.id` and index on `paper_id` |
| 6 | API endpoints follow existing security conventions | **PASS** | FastAPI routes under `/api/v1/papers/{paper_id}/evidence`, JWT auth on extract, typed Pydantic models |
| 7 | Frontend exposes evidence in an understandable form | **PASS** | `EvidenceModal.tsx` provides category grouping, claims, quotes, offsets, badges, and refresh button |
| 8 | Repeated extraction is safe | **PASS** | Idempotent extraction; atomic replacement within transactions prevents duplicate rows |
| 9 | Source changes cannot silently leave stale evidence | **PASS** | SHA-256 document hashing flags `is_stale=True` when text changes |
| 10 | Focused tests and regression suites executed with real results | **PASS** | Backend: 106/106 passed; Frontend: 29/29 passed; exact command outputs recorded |
| 11 | Application builds successfully | **PASS** | `npm run build` completed cleanly; container deployment healthy |
| 12 | Existing data, authentication, Git work, FAISS indexes preserved | **PASS** | Canonical FAISS hashes preserved; DB records intact; all Git working tree changes preserved |
| 13 | All criteria labelled PASS/FAIL/BLOCKED | **PASS** | Evaluated truthfully against real runtime evidence |
