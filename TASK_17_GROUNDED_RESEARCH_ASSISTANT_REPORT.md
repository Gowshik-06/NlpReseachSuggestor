# TASK-17 — Grounded Research Assistant & End-to-End Integration Report

**Project:** ResearchLens — NLP-Based Research Paper Recommendation System  
**Date:** 2026-10-10  
**Repository Path:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Git Branch:** `master`  
**Git Commit:** `c26cd6a16fd4de20a91cf10847ca6463dc2efc35`  
**Status:** COMPLETE (Focused Verification Passed)

---

## 1. Executive Summary

TASK-17 delivers the **Grounded Research Assistant**, unifying ResearchLens's scholarly intelligence capabilities (evidence extraction from TASK-13, structured paper comparison from TASK-14, DRIUT relationship classifications from TASK-15, and research evolution & gap exploration from TASK-16) into an interactive, evidence-backed conversational interface.

### Core Capabilities Delivered
1. **Scholarly Question Answering:** Answers questions regarding individual papers or selected subsets of papers without hallucinating citations, benchmarks, or results.
2. **Deterministic Evidence Grounding:** Maps every synthesized claim directly to verified evidence passages with exact 0-based character offsets (`text[char_start:char_end] == quote`).
3. **Multi-Faceted Inquiry Support:**
   - **Limitations & Challenges:** Summarizes explicit author-reported bottlenecks and architectural trade-offs.
   - **Future Work & Directions:** Details prospective research directions and converging goals.
   - **Method & Architecture Comparison:** Contrasts proposed approaches and objectives across papers.
   - **Datasets & Evaluation Protocols:** Details benchmark datasets and evaluation metrics with cross-benchmark comparability warnings.
   - **DRIUT & Inter-Paper Relationships:** Explains why papers are classified as Extensions, Improvements, Alternatives, or Thematic Proximity.
   - **Research Evolution & Timelines:** Traces chronological progression by publication year.
   - **Candidate Research Gaps:** Synthesizes local catalog boundaries and prospective research frontiers.
4. **Adversarial & Privacy Defenses:**
   - Prompt-injection safety: Treats retrieved paper text strictly as untrusted data, preventing instruction overrides.
   - Cross-user privacy: Never exposes private notes (`SavedPaper`) or alerts (`DRIUTAlert`).
5. **Truthfulness Disclosures:**
   - Returns explicit `status: "insufficient_evidence"` on sparse or non-existent topics instead of fabricating plausible answers.
   - Discloses local catalog boundaries versus global scientific novelty.

---

## 2. Architecture & Endpoint Design

### 2.1 Backend Endpoint
- **Route:** `POST /api/v1/research/assistant`
- **Controller:** `post_research_assistant` in `backend/app/api/v1/endpoints/research.py`
- **Service Layer:** `answer_research_question` in `backend/app/services/assistant_service.py`

### 2.2 Request Schema (`ResearchAssistantRequest`)
```json
{
  "question": "What limitations are reported for these pre-training approaches?",
  "paper_ids": ["arxiv:2106.08254v2", "arxiv:2202.09061v4"],
  "topic": "Transformers",
  "max_evidence_items": 8
}
```

### 2.3 Response Schema (`ResearchAssistantResponse`)
```json
{
  "question": "What limitations are reported for these pre-training approaches?",
  "answer": "Based on 2 paper(s) examined in the catalog, authors report the following primary limitations:\n• Vision Transformers: Architecture, Attention Mechanisms... [ev-1]: High computational cost...",
  "status": "complete",
  "evidence": [
    {
      "evidence_id": "ev-1",
      "paper_id": 266,
      "paper_code": "crossref:10.24108/preprints-3114040",
      "paper_title": "Vision Transformers: Architecture, Attention Mechanisms...",
      "authors": ["Author Name"],
      "year": 2025,
      "venue": "Preprints",
      "source_passage": "High computational cost and memory overhead...",
      "char_start": 5240,
      "char_end": 5406,
      "section_name": "Abstract",
      "source_type": "abstract",
      "category": "limitations",
      "confidence_score": 0.88,
      "url": "https://doi.org/10.24108/preprints-3114040",
      "doi": "10.24108/preprints-3114040"
    }
  ],
  "claims": [
    {
      "claim_id": "claim-1",
      "claim_text": "In Vision Transformers (2025), authors note high computational cost [ev-1].",
      "supporting_evidence_ids": ["ev-1"],
      "category": "limitation",
      "confidence": 0.88,
      "is_verified": true
    }
  ],
  "limitations": [
    "Limitations reflect explicit author statements in abstracts; unindexed experimental sections may note additional trade-offs."
  ],
  "corpus_scope": "Specified paper set: 2 paper(s) analyzed",
  "follow_up_questions": [
    "What future-work directions do these authors propose to mitigate these bottlenecks?",
    "Are there alternative architectures in the catalog that address these limitations?"
  ],
  "truthfulness_disclosure": "DISCLOSURE: Every answer claim is deterministically grounded in verified passages from the local catalog. Citations and offsets correspond to exact stored text. No statements or quotations are fabricated."
}
```

---

## 3. Grounding, Evidence Verification & Model Provider Inspection

### 3.1 Provider Configuration Status
- Inspection of `backend/app/core/config.py` and environment configuration confirmed **no external commercial LLM provider (OpenAI, Gemini, Anthropic) is configured or required**.
- Per safety requirement 5, the system implements a **deterministic, evidence-grounded response synthesis path**. This guarantees zero hallucination, instant response times, zero token fees, and mathematical substring offset integrity.

### 3.2 Evidence Verification Mechanism
- Claims are gathered using `_gather_paper_claims(p, db)` which checks PostgreSQL `paper_evidence` rows first, followed by in-memory sentence-level rule extraction directly against `(p.abstract or "").strip()`.
- Every evidence passage is mathematically checked against the stored paper text (`source_text[char_start:char_end] == source_passage`).
- Citations in the answer are strictly bounded to the set of returned evidence IDs (`ev-1`, `ev-2`, etc.).

### 3.3 Prompt-Injection & Privacy Protections
- **Prompt Injection:** Input questions and paper text are sanitized. Retrieved paper abstracts are treated purely as inert text data, never evaluated as execution instructions or prompt alterations.
- **Cross-User Isolation:** Public queries inspect only the `Paper` and `PaperEvidence` catalog tables. Private notes from `SavedPaper` and private alerts from `DRIUTAlert` are never queried or leaked.

---

## 4. Frontend Integration

### 4.1 UI Component Updates
- **Component:** `frontend/src/components/ResearchEvolutionView.tsx`
- **Sub-Tab:** Added `🤖 Assistant` alongside `📜 Timeline`, `🕸️ Relationship Graph`, and `💡 Gap Discovery`.
- **Features Included:**
  1. **Question Input & Submission:** Clean text input with submit button and keyboard Enter support.
  2. **Suggested Inquiries:** One-click chips for common scholarly inquiries (limitations, future work, comparative architecture, benchmark protocols, research gaps).
  3. **Structured Answer Presentation:** Formatted synthesis narrative with clickable inline citation badges `[ev-1]`.
  4. **Key Grounded Claims Checklist:** Lists discrete assertions with mapped evidence tags and verification status badges.
  5. **Verified Source Passages Card:** Expandable evidence entries showing paper title, authors, year, section name, exact character offsets `[char_start:char_end]`, source type badge, and external links.
  6. **Scientific Limitations Callout:** Highlights catalog boundaries, missing full text, or disparate protocol warnings.
  7. **Interactive Follow-Up Inquiries:** Clickable suggested questions that dynamically populate and submit follow-up searches.
  8. **Truthfulness Disclosure:** Persistent notification emphasizing local catalog boundaries.

---

## 5. Focused Verification Execution Results

In accordance with Section 2 and Section 9 execution policies, testing was narrowly focused on TASK-17 components and integration points.

### 5.1 Focused Backend Tests (Executed)
```bash
cd backend && ./venv/bin/pytest tests/test_research_assistant.py
```
- **Exit Code:** `0`
- **Execution Time:** 8.46s
- **Passed Tests (8 / 8):**
  - `test_assistant_limitations_query`: Verified author limitations with exact citations and character offset matching.
  - `test_assistant_comparison_query`: Verified comparative claims across multiple selected papers.
  - `test_assistant_future_work_query`: Verified future-work synthesis with grounded quotes.
  - `test_assistant_insufficient_evidence_nonexistent_topic`: Verified explicit `insufficient_evidence` status and follow-ups.
  - `test_assistant_invalid_paper_ids`: Verified safe handling of invalid IDs with explanatory limitations.
  - `test_assistant_prompt_injection_safety`: Verified adversarial queries do not execute instructions or leak secrets.
  - `test_assistant_privacy_isolation`: Verified confidential user notes and tags are not leaked.
  - `test_assistant_input_validation`: Verified schema validation (empty questions, invalid `max_evidence_items`).

### 5.2 Focused Regression Tests (Executed)
```bash
cd backend && ./venv/bin/pytest tests/test_research_evolution.py
```
- **Exit Code:** `0`
- **Execution Time:** 13.00s
- **Passed Tests (16 / 16):** All 16 existing timeline, graph, gap, and regression tests passed without regression.

### 5.3 Focused Frontend Tests (Executed)
```bash
cd frontend && npm test -- src/components/ResearchEvolutionView.test.tsx --run
```
- **Exit Code:** `0`
- **Execution Time:** 1.16s
- **Passed Tests (7 / 7):**
  - Includes new test: `switches to Assistant tab, asks question, and renders grounded answer with evidence passages`.

### 5.4 Frontend Production Build (Executed)
```bash
cd frontend && npm run build
```
- **Exit Code:** `0`
- **Tool:** `tsc -b && vite build`
- **Duration:** 726ms
- **Output Bundle:** `dist/assets/index-Bixd92pq.js` (276.28 kB)

### 5.5 Skipped Full Regression Suites (Explicit Disclosure)
In accordance with mandatory efficiency instructions, the following suites were **skipped (NOT RUN)** during TASK-17:
- `backend/tests/test_academic_sources.py` (SKIPPED / NOT RUN)
- `backend/tests/test_auth_and_isolation.py` (SKIPPED / NOT RUN)
- `backend/tests/test_driut_intelligence.py` (SKIPPED / NOT RUN)
- `backend/tests/test_driut_scheduler.py` (SKIPPED / NOT RUN)
- `backend/tests/test_embedding_and_sync.py` (SKIPPED / NOT RUN)
- `backend/tests/test_evidence_extraction.py` (SKIPPED / NOT RUN)
- `backend/tests/test_faiss_consistency.py` (SKIPPED / NOT RUN)
- `backend/tests/test_health.py` (SKIPPED / NOT RUN)
- `backend/tests/test_paper_comparison.py` (SKIPPED / NOT RUN)
- `backend/tests/test_papers_api.py` (SKIPPED / NOT RUN)
- `backend/tests/test_pdf_upload.py` (SKIPPED / NOT RUN)
- `backend/tests/test_rate_limiter.py` (SKIPPED / NOT RUN)
- `frontend/src/App.test.tsx` (SKIPPED / NOT RUN)
- `frontend/src/components/CompareModal.test.tsx` (SKIPPED / NOT RUN)
- `frontend/src/components/DriutAlertsView.test.tsx` (SKIPPED / NOT RUN)
- `frontend/src/components/EvidenceModal.test.tsx` (SKIPPED / NOT RUN)
- `frontend/src/services/api.test.ts` (SKIPPED / NOT RUN)

*Note: In accordance with audit standards, skipped tests are explicitly declared as NOT RUN and are not claimed as passed.*

---

## 6. Live Deployment & Runtime Parity Verification

Per Section 10 deployment policy, container/source parity was verified and safely updated without restarting unrelated services or deleting volumes:
1. **Backend Deployment:**
   - Source code updated in container: `podman cp backend/app research-paper-recommender-backend-1:/app/`
   - Process refreshed: `podman restart research-paper-recommender-backend-1`
   - Healthcheck status: **Up (healthy)** on `0.0.0.0:8000`
   - Live smoke probe:
     `POST http://localhost:8000/api/v1/research/assistant` with topic "Transformers" returned **HTTP 200 OK** with structured grounded response.
2. **Frontend Deployment:**
   - Static assets updated in container: `podman cp frontend/dist/. research-paper-recommender-frontend-1:/usr/share/nginx/html/`
   - Bundle check: Host `curl http://localhost:3000/` confirmed active bundle is `assets/index-Bixd92pq.js`.
3. **Database & FAISS Volume Preservation:**
   - PostgreSQL `papers` count: **132** (Unchanged)
   - PostgreSQL `paper_evidence` count: **1** (Unchanged)
   - PostgreSQL `users` count: **5** (Unchanged; test user cleaned)
   - PostgreSQL `saved_papers` count: **1** (Unchanged)
   - PostgreSQL `driut_alerts` count: **30** (Unchanged)
   - FAISS vector count (`ntotal`): **133** (Unchanged)
   - FAISS SHA-256: `580b4e459ab65a549fe75e71ee9d96c38e73596efd693e5c24a68e941cadf80a` (Identical byte-for-byte)
   - Metadata SHA-256: `6a5ca17649199c93118e46be26145b033f6660ca4a18d8a9fe5959fb98c94924` (Identical byte-for-byte)

---

## 7. Files Inspected and Modified

| File | Status | Nature of Changes |
| :--- | :--- | :--- |
| `backend/app/schemas/research.py` | Modified | Added `AssistantEvidenceItem`, `AssistantClaim`, `ResearchAssistantRequest`, `ResearchAssistantResponse`. |
| `backend/app/services/assistant_service.py` | Created | Deterministic evidence-grounded research assistant engine with intent classification, passage extraction, and offset verification. |
| `backend/app/api/v1/endpoints/research.py` | Modified | Registered `POST /api/v1/research/assistant` endpoint. |
| `backend/tests/test_research_assistant.py` | Created | Focused test suite covering 8 core assistant verification scenarios. |
| `frontend/src/types/research.ts` | Modified | Added TypeScript interfaces for assistant models. |
| `frontend/src/services/api.ts` | Modified | Added `askResearchAssistant` API client method. |
| `frontend/src/components/ResearchEvolutionView.tsx` | Modified | Integrated `🤖 Assistant` sub-tab, state, handler, suggestion chips, and structured answer cards. |
| `frontend/src/components/ResearchEvolutionView.test.tsx` | Modified | Added vitest coverage for Assistant tab interaction. |

---

## 8. Known Limitations & Recommendations

1. **Abstract vs. Full-Text Coverage:**
   - 131 out of 132 catalog papers currently have only abstract text stored. The assistant accurately discloses when claims are derived from abstracts and recommends full PDF upload for experimental appendices.
2. **Deterministic Synthesis:**
   - The assistant operates without external commercial LLMs, ensuring zero hallucination and high reliability. If a future task configures a self-hosted or API-based LLM, the existing `AssistantClaim` and `AssistantEvidenceItem` verification contract should be retained as an invariant validation gate.

---

## 9. Verification Matrix

| Acceptance Criterion | Verification Method | Result | Notes |
| :--- | :--- | :--- | :--- |
| **Grounded Question Answering** | `test_assistant_limitations_query` | **PASS** | Answers supported by verified catalog passages. |
| **Citation Correspondence** | ID lookup in evidence list | **PASS** | Every claim citation exists in returned evidence set. |
| **Offset Invariant** | `test_assistant_limitations_query` | **PASS** | `abstract[char_start:char_end] == quote` verified. |
| **Comparative Queries** | `test_assistant_comparison_query` | **PASS** | Contrasts methods and evaluation protocols. |
| **Insufficient Evidence Handling**| `test_assistant_insufficient_evidence...` | **PASS** | Explicit status returned; no fabrication. |
| **Prompt Injection Defense** | `test_assistant_prompt_injection_safety` | **PASS** | Adversarial text treated purely as inert search data. |
| **Cross-User Privacy** | `test_assistant_privacy_isolation` | **PASS** | Private notes and alerts never leaked. |
| **API Schema Validation** | `test_assistant_input_validation` | **PASS** | Bounded requests and 422 errors on invalid inputs. |
| **Frontend UI Integration** | `ResearchEvolutionView.test.tsx` | **PASS** | 7 vitest tests passed; clean production build. |
| **Live Runtime Parity** | Curl probe against live port 8000 | **PASS** | Container refreshed and serving assistant endpoint. |
| **Data & Vector Invariance** | SHA-256 and SQL row count audit | **PASS** | Zero mutations; hashes identical byte-for-byte. |
