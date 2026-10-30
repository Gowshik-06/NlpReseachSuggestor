# TASK-15 Completion Report: Evidence-Backed DRIUT Intelligence

**Project:** ResearchLens — NLP-Based Research Paper Recommendation System  
**Repository:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Workspace:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem`  
**Date:** October 10, 2026  
**Status:** COMPLETE (All Acceptance Criteria PASSED)  

---

## 1. Executive Summary

TASK-15 delivers a major scientific intelligence upgrade to DRIUT (Dynamic Research Impact Update Tracker). Prior versions relied heavily on raw cosine similarity fallbacks that guessed relationship categories (such as defaulting high-similarity pairs to "Improvement" or "Extension" without text grounding). TASK-15 transforms DRIUT into a deterministic, evidence-grounded research intelligence engine where every substantive relationship category is strictly grounded in verified source passages, explicit character offsets, provenance tracking, and scientific protocol comparability guards.

### Core Truthfulness Guarantees & Architectural Principles:
1. **Source Evidence Over Similarity:** A semantic similarity score alone must never establish a relationship category. When high thematic similarity exists without author-stated relationship claims, DRIUT transparently reports `insufficient_evidence` and refrains from creating spurious alerts.
2. **Disparate Numerical Protocol Guard:** Prevents scientific misrepresentation by checking evaluation benchmarks and metrics. If a candidate paper reports performance gains on ImageNet while the saved paper evaluated on GLUE (or BLEU vs. Accuracy), DRIUT strictly prohibits declaring an "Improvement" and downgrades the relationship to "Alternative" or flags it with an explicit protocol warning.
3. **Explicit Category Criteria:** Concrete, testable rules and lexical-semantic patterns govern all six PPTX taxonomy categories: *Extension*, *Improvement*, *Challenge*, *Reproduction*, *Alternative*, and *Potential Replacement*.
4. **Calibrated Evidence Strength:** Every classification is labeled with a calibrated strength indicator: `strong_evidence` (direct baseline citation + verified claim), `partial_evidence` (grounded pattern + shared domain keyphrases), `tentative` (abstract-only or replacement claim requiring multi-benchmark verification), or `insufficient_evidence`.
5. **Traceable Explanations & Provenance:** Alert cards display exact candidate evidence passages, offsets (`[char_start:char_end]`), section name, baseline passage from the saved paper, source provenance (`Full Text Provenance` vs. `Abstract Only`), and protocol uncertainty disclosures.
6. **Non-Destructive Alert Persistence & Idempotency:** All 27 pre-existing DRIUT alerts are 100% preserved with backward compatibility. Database migrations added nullable evidence columns without dropping or modifying legacy rows. Repeated scans are fully idempotent, and scans coordinate across worker processes using PostgreSQL advisory locking.

---

## 2. Initial vs. Final Baseline State

### Database Row Counts
| Entity | Initial Count | Final Count | Net Change | Notes |
| :--- | :---: | :---: | :---: | :--- |
| `papers` | 132 | 132 | 0 | Baseline catalog intact |
| `users` | 5 | 5 | 0 | All existing user accounts preserved |
| `saved_papers` | 1 | 1 | 0 | Researcher libraries untouched |
| `driut_alerts` | 27 | 30 | +3 | 27 pre-existing alerts 100% preserved; 3 test trigger alerts created with new evidence schema |
| `paper_evidence` | 1 | 1 | 0 | Existing evidence records intact |

### FAISS Vector Database Baseline Hashes
- **Host Canonical Baseline Index:**
  - `research_index.faiss`: `5993254851aeb79869558a3ca25991aaa0db89adc5a1d3e3fb4c0e902440b4dc` (132 vectors, dim 768)
  - `papers_meta.json`: `f0275c278406c3168e39c40066b1a07233e7e05593b71a23ca1621f289869174` (132 metadata entries)
- **Container Volume Index (`/app/data/processed/faiss/`):**
  - Vectors: 132 | Metadata entries: 132 | Consistency status: `is_consistent: true`

### Git Status Summary
- **Branch:** `master` at commit `c26cd6a`
- All staged, unstaged, and untracked files from prior tasks were strictly preserved. No destructive git commands (`reset`, `clean`, `stash`, `checkout`, `commit`) were executed.

---

## 3. Files Modified and Purpose

1. **`backend/app/db/migrate_driut_evidence.py`** (New File)
   - Idempotent, non-destructive migration script using `ALTER TABLE driut_alerts ADD COLUMN IF NOT EXISTS ...`.
   - Added columns: `evidence_strength`, `evidence_passage`, `saved_evidence_passage`, `char_start`, `char_end`, `section_name`, `source_type`, `semantic_similarity`, `comparability_notes`, `uncertainty_warning`, `classification_version`.
   - Added indexes on `evidence_strength` and `classification_version`.

2. **`backend/app/models/driut.py`**
   - Updated `DRIUTAlert` SQLAlchemy model with the 11 new evidence grounding, provenance, and comparability columns while preserving the unique constraint `uq_user_driut_alert` and foreign keys.

3. **`backend/app/schemas/paper.py`**
   - Added `DRIUTClassificationResult` Pydantic schema for structured, reusable relationship evaluation.
   - Extended `DRIUTAlertResponse` schema with optional evidence grounding fields for backwards-compatible API serialization.

4. **`backend/app/services/driut_service.py`**
   - Completely overhauled relationship classification. Eliminated all raw cosine similarity guessing fallbacks.
   - Implemented `classify_relationship_evidence(saved_paper, new_paper, db=None) -> DRIUTClassificationResult`.
   - Integrated sentence-level passage extraction with exact character offsets (`split_text_into_sentences_with_spans`).
   - Implemented benchmark and metric comparability guards (`_extract_dataset_keywords`, `_extract_metric_keywords`) guarding against false "Improvement" claims across disparate protocols.
   - Updated `scan_saved_papers_for_updates` and `scan_research_impact_updates` to populate all evidence columns on new alerts while preserving idempotency and auditability.
   - Maintained 100% backwards-compatible `classify_relationship(saved_paper, new_paper)` tuple wrapper.

5. **`backend/tests/test_driut_intelligence.py`** (New File)
   - Created 15 targeted tests covering all six relationship categories, insufficient evidence, similarity without relationship, abstract-only vs. full-text, evidence offsets, incompatible benchmark guards, challenge vs. ordinary differences, reproduction vs. shared keywords, potential replacement thresholds, idempotency, cross-user privacy, advisory locking, and legacy alert preservation.

6. **`frontend/src/types/paper.ts`**
   - Added `DRIUTEvidenceStrength` type.
   - Extended `DRIUTAlert` interface with evidence grounding, offset, section, and comparability fields.

7. **`frontend/src/components/DriutAlertsView.tsx`**
   - Added evidence strength badges (`🛡️ Verified Evidence`, `🔍 Grounded Claims`, `⚠️ Tentative Inference`).
   - Added provenance badges (`📄 Full Text Provenance`, `📑 Abstract Only`).
   - Implemented collapsible supporting evidence inspection card displaying exact offsets (`[char_start:char_end]`), section name, candidate passage, and saved baseline passage.
   - Added protocol caution banners and topical similarity disclosures.

8. **`frontend/src/components/DriutAlertsView.test.tsx`** (New File)
   - Created 7 Vitest unit tests covering unauthenticated prompt, filter chips, evidence badges, passage expansion, compare action callbacks, empty state, and live literature scan triggers.

---

## 4. Classification Rules & Semantics for the Six DRIUT Categories

| Category | Explicit Testable Criteria | Grounding Requirement | Uncertainty & Guard Policy |
| :--- | :--- | :--- | :--- |
| **Extension** | Candidate explicitly builds on, extends, generalizes, or adapts baseline architecture or method. | Matches extension phrasing (`extends`, `builds upon`, `scaled to`, `adapting to`, `modular adapters`, `cross-modal`, `unified backbone`). Exact sentence extracted with offsets. | Requires verified passage. If evaluated from abstract only, labeled with abstract-only disclosure. |
| **Improvement** | Candidate demonstrates higher performance, lower latency, or improved efficiency under comparable conditions. | Matches performance phrasing (`outperforms`, `superior accuracy`, `more efficient`, `substantially improves`, `reduces error by`). | **Guarded against disparate protocols:** If candidate evaluates on ImageNet while baseline evaluates on GLUE (or BLEU vs. Accuracy), Improvement is PROHIBITED; downgraded to Alternative or flagged as insufficient evidence. |
| **Challenge** | Candidate explicitly critiques, disputes, questions validity, or identifies fundamental flaws in baseline. | Matches critical phrasing (`critique`, `fails to`, `limitation of`, `disputes`, `flaw`, `vulnerability`, `questions the validity`, `overfitting in`). | A different numerical result alone is NOT a challenge. Requires explicit author critique or identified vulnerability. |
| **Reproduction** | Candidate explicitly replicates, reproduces, or empirically validates baseline findings. | Matches replication phrasing (`replication study`, `reproduce`, `reproducibility`, `empirical verification`, `audit`, `independent verification`). | Shared keywords or shared datasets alone are INSUFFICIENT. Requires explicit replication/audit intent. |
| **Alternative** | Candidate proposes a meaningfully different computational paradigm for the same research objective. | Matches divergence phrasing (`dispensing with`, `instead of`, `alternative paradigm`, `without relying on`, `substitute for`, `orthogonal approach`). | Can also be assigned when two papers share the domain problem but neither extends nor disputes the other, and protocols differ. |
| **Potential Replacement** | Candidate claims drop-in replacement, superseding capability, or rendering baseline obsolete. | Matches replacement phrasing (`supersedes`, `drop-in replacement`, `replaces`, `new standard`, `renders obsolete`). | **Calibrated as Tentative:** Replacement claims without multi-benchmark comparative verification are labeled as tentative inferences. |

### The Uncertainty Policy (`insufficient_evidence`)
- When candidate and saved paper exhibit high semantic similarity (e.g., >70%) but lack author-stated relationship claims, DRIUT returns `relationship_type = None`, `evidence_strength = "insufficient_evidence"`, and `is_supported = False`.
- Spurious alerts are never generated on similarity alone.

---

## 5. Test Execution and Results

### Backend Test Suite
```bash
./venv/bin/pytest tests/
```
**Results:** **134 PASSED**, 0 FAILED in 33.94s.
- `tests/test_driut_intelligence.py`: **15 passed**
- `tests/test_driut_scheduler.py`: **16 passed**
- `tests/test_paper_comparison.py`: **13 passed**
- `tests/test_evidence_extraction.py`: **21 passed**
- `tests/test_auth_and_isolation.py`: **8 passed**
- `tests/test_embedding_and_sync.py`: **13 passed**
- `tests/test_faiss_consistency.py`: **6 passed**
- `tests/test_academic_sources.py`: **11 passed**
- `tests/test_papers_api.py`: **16 passed**
- `tests/test_pdf_upload.py`: **6 passed**
- `tests/test_rate_limiter.py`: **4 passed**
- `tests/test_health.py`: **5 passed**

### Frontend Test Suite
```bash
npm test -- --run
```
**Results:** **44 PASSED**, 0 FAILED across 5 test files in 1.39s.
- `src/components/DriutAlertsView.test.tsx`: **7 passed**
- `src/components/CompareModal.test.tsx`: **8 passed**
- `src/components/EvidenceModal.test.tsx`: **10 passed**
- `src/services/api.test.ts`: **15 passed**
- `src/App.test.tsx`: **4 passed**

### Frontend Production Build
```bash
npm run build
```
**Result:** **SUCCESS** (TypeScript compilation passed; Vite built bundle in 773ms).

---

## 6. Live Runtime Verification

The live stack was verified using the running Podman containers:
1. **Container Health:**
   - `research-paper-recommender-backend-1`: `Up 47 minutes (healthy)`
   - `research-paper-recommender-frontend-1`: `Up About an hour`
   - `research-paper-recommender-postgres-1`: `Up About an hour (healthy)`
2. **Live DRIUT Monitoring Status (`GET /api/v1/papers/driut/status`):**
   - HTTP 200 OK
   - `is_enabled: true`, `interval_minutes: 60`, `last_run_status: "idle"`, all 4 academic providers (`arxiv`, `pubmed`, `csir`, `crossref`) healthy/idle.
3. **Live DRIUT Alerts (`GET /api/v1/papers/driut/alerts`):**
   - HTTP 200 OK
   - Returned 30 alerts (all 27 pre-existing alerts intact + 3 evidence-grounded alerts).
   - Verified new schema fields: `evidence_strength: "tentative"`, `source_type: "abstract"`, `semantic_similarity: 0.8327`, `char_start: 342`, `char_end: 405`, `evidence_passage: "So can such pre-trained models be applied to multi-modal tasks?"`, `classification_version: "v2.0-evidence-grounded"`.
4. **Live Manual Scan (`POST /api/v1/papers/driut/scan`):**
   - HTTP 200 OK: Evaluated 131 papers against saved library; 0 duplicate alerts created (100% idempotent).
5. **Vector Index Consistency (`GET /api/v1/papers/index-status`):**
   - HTTP 200 OK: `is_consistent: true`, 132 DB papers, 132 vectors, 132 metadata entries, dim 768.

---

## 7. Known Limitations and False-Positive Risks

1. **Abstract-Only Extraction:**
   - Most external discovery sources provide abstracts rather than full PDF text. Abstract-only evidence cannot inspect detailed experimental hyperparameters, hardware setups, or appendix tables.
   - *Mitigation:* Clear disclosure badge (`📑 Abstract Only`) and uncertainty warning on every abstract-derived alert.
2. **Benchmark Keyword Ambiguity:**
   - Heuristic dataset detection searches for standard benchmark names (e.g., ImageNet, GLUE, SQuAD). If a paper introduces a brand-new unnamed dataset, dataset overlap cannot be determined.
   - *Mitigation:* When datasets are unknown or ambiguous, numerical improvements are marked as unverified protocols with caution notes.
3. **Linguistic Sarcasm or Idiomatic Claims:**
   - Author statements praising a baseline before demonstrating a flaw could trigger multiple category patterns.
   - *Mitigation:* Priority disambiguation filters ensure critical critique language overrides ordinary positive mentions.

---

## 8. Acceptance Criteria Matrix (Definition of Done)

| Acceptance Criterion | Status | Evidence / Verification Method |
| :--- | :---: | :--- |
| **1. Explicit Criteria for All 6 Categories** | **PASS** | Implemented in `driut_service.py`; tested in `test_six_relationship_categories_grounded` across all 6 categories. |
| **2. Real Evidence Grounding** | **PASS** | Sentence-level extraction with character offsets (`char_start`, `char_end`) verified mathematically in `test_evidence_passage_and_offset_exact_alignment`. |
| **3. Similarity Alone Rejection** | **PASS** | Replaced guessing fallback with `insufficient_evidence` policy; tested in `test_similarity_without_relationship_returns_insufficient_evidence`. |
| **4. Transparent Inadequate Evidence** | **PASS** | Alerts disclose missing evidence, abstract-only provenance, and uncertainty warnings in backend response and frontend UI. |
| **5. Disparate Numerical Protocol Guard** | **PASS** | ImageNet vs. GLUE and BLEU vs. Accuracy tested in `test_false_positive_improvement_incompatible_benchmarks_guarded`. Improvement strictly prohibited. |
| **6. Traceable User-Facing Explanations** | **PASS** | `DriutAlertsView.tsx` updated with expandable passages, offsets, section provenance, baseline passages, and caution banners. 7 Vitest tests passing. |
| **7. Idempotent & Recoverable Alert Persistence** | **PASS** | Tested in `test_scan_idempotency_and_duplicate_alert_prevention`; live `POST /driut/scan` verified 0 duplicate alerts. |
| **8. Scheduler & Advisory Lock Concurrency** | **PASS** | Session-level PostgreSQL advisory locking tested in `test_scheduler_advisory_locking_concurrency`; non-overlapping execution verified. |
| **9. Cross-User Privacy & Isolation** | **PASS** | Tested in `test_cross_user_library_and_alert_isolation`; alerts strictly filtered by authenticated `user_id`. |
| **10. Comprehensive Backend & Frontend Tests** | **PASS** | Backend: 134/134 passed (`pytest tests/`). Frontend: 44/44 passed (`npm test -- --run`). Build: passed (`npm run build`). |
| **11. Production Build & Runtime Validation** | **PASS** | Podman containers verified healthy; live endpoints tested via HTTPX and curl; vector index consistent (132/132). |
| **12. Zero Destructive Actions** | **PASS** | All 27 pre-existing alerts preserved (total 30); Git status intact; FAISS baseline hashes verified (`59932548...` and `f0275c27...`). |

---

## 9. Conclusion

TASK-15 is complete. DRIUT now provides trustworthy, scientifically defensible literature intelligence grounded in source passages and protected against disparate benchmark fallacies. All regression tests, frontend tests, and production checks pass. Ready for user review before proceeding to TASK-16.
