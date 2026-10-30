# TASK-14 Completion Report: Structured, Evidence-Grounded Paper Comparison

**Project:** ResearchLens — NLP-Based Research Paper Recommendation System  
**Repository:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Workspace:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem`  
**Date:** October 10, 2026  
**Status:** COMPLETE (All Acceptance Criteria PASSED)  

---

## 1. Executive Summary

TASK-14 implements a structured, evidence-grounded research paper comparison system that enables researchers to evaluate 2 to 5 scientific papers side-by-side across 12 rigorous dimensions using real paper metadata and persisted evidence records from TASK-13.

### Core Architectural Principles & Truthfulness Guarantees:
1. **Evidence Grounding Over Speculation:** Every substantive comparison finding is mapped directly to author-reported text passages with validated character offset spans (`char_start`, `char_end`), provenance source labeling (`abstract` vs. `full_text`), and section/page indicators.
2. **Absence of Evidence != Absence of Capability:** Missing evidence is explicitly rendered with a dedicated `"missing_evidence"` status accompanied by an unambiguous scientific disclosure that absence of evidence in available text does not imply the authors or methodology lack that capability.
3. **Disparate Numerical Protocol Guard:** Prevents scientific misrepresentation by detecting non-aligned benchmarks or differing evaluation metrics across compared papers (e.g., GLUE vs. ImageNet, BLEU vs. Accuracy). Flagged dimensions are assigned `"incomparable_protocols"` status and marked with prominent alerts prohibiting claims of methodological superiority.
4. **Abstract-Only Disclosure:** When a paper's provenance is restricted to its abstract, a clear warning badge discloses that comprehensive limitation and experimental analyses require full-text access.
5. **Zero Fabrication:** Citation counts, publication venues, years, and performance values are strictly extracted from catalog metadata. Untracked metadata is transparently identified as such without synthetic interpolation.
6. **Zero Side-Effects:** The comparison service does not mutate database records (`paper_evidence`, `papers`, `saved_papers`) or FAISS index structures.

---

## 2. Initial vs. Final Baseline State

### Database Row Counts
| Entity | Initial Count | Final Count | Net Change |
| :--- | :---: | :---: | :---: |
| `papers` | 132 | 132 | 0 |
| `users` | 5 | 5 | 0 |
| `saved_papers` | 1 | 1 | 0 |
| `driut_alerts` | 27 | 27 | 0 |
| `paper_evidence` | 1 | 1 | 0 |

### FAISS Vector Database Baseline Hashes
- **Canonical Host Baseline Index:**
  - `research_index.faiss`: `5993254851aeb79869558a3ca25991aaa0db89adc5a1d3e3fb4c0e902440b4dc` (132 vectors, dim 768)
  - `papers_meta.json`: `f0275c278406c3168e39c40066b1a07233e7e05593b71a23ca1621f289869174` (132 metadata entries)
- **Container Volume Index:** 132 vectors, dim 768, 132 metadata entries.

### Git Status Summary
- **Branch:** `master` at commit `c26cd6a`
- All staged and uncommitted files from prior tasks were strictly preserved. No destructive git commands (`reset`, `clean`, `stash`, `checkout`, `commit`) were executed.

---

## 3. Files Modified and Purpose

1. **`backend/app/schemas/paper.py`**
   - Added structured Pydantic models: `ComparisonCell`, `ComparisonDimensionDetail`, `PaperCoverageSummary`, `SupportedInsight`, `IncomparableDimensionDetail`.
   - Updated `CompareRequest` with `min_length=2, max_length=5` validation.
   - Enriched `CompareResponse` with typed dimensions, coverage summaries, supported similarities/differences, incomparable dimensions, and warning lists while maintaining full backwards compatibility for legacy `comparison_points` and `executive_summary`.

2. **`backend/app/services/comparison_service.py`**
   - Completely overhauled comparison logic. Eliminated synthetic regex template heuristics.
   - Implemented dynamic evaluation across all 12 dimensions.
   - Reused `evidence_service` extraction patterns and verified existing `PaperEvidence` records without committing new rows (zero DB mutations).
   - Implemented protocol disparity detection (`_extract_dataset_keywords`, `_extract_metric_keywords`) and automated similarity/difference discovery.

3. **`backend/app/api/v1/endpoints/papers.py`**
   - Enforced maximum comparison limit (2 <= distinct papers <= 5).
   - Preserved `raw_text` in resolved paper payloads to enable full-text section tracking.
   - Passed `db` session into `compare_papers` for read-only evidence retrieval.

4. **`backend/app/services/vector_index.py`**
   - Re-ordered query vector dimension validation in `search()` to execute before empty-index returns, ensuring dimension mismatches always raise `ValueError`.

5. **`backend/tests/test_paper_comparison.py`** (New File)
   - Created 13 targeted tests covering two-paper, multi-paper (3-5 papers), limit enforcement (>5 papers), duplicate handling, 404 missing papers, abstract disclosure, full-text provenance, stale evidence, numerical comparability guards, untracked citations, cross-user isolation, and zero side-effects.

6. **`backend/tests/test_auth_and_isolation.py`**
   - Corrected test fixture teardown to invoke `idx._load_or_initialize()` consistently.

7. **`frontend/src/types/paper.ts`**
   - Added TypeScript interfaces matching backend comparison response schemas.

8. **`frontend/src/components/CompareModal.tsx`**
   - Upgraded modal to render the 12 structured dimensions in responsive side-by-side grids.
   - Added collapsible supporting passage inspection with exact offsets, section names, and page numbers.
   - Added prominent alert banners for disparate experimental protocols.
   - Added category filter tabs (`All Dimensions`, `Scientific Evidence`, `Publication & Metadata`, `Coverage & Provenance`).
   - Integrated coverage badges (`Full Text Provenance`, `Abstract Only`).

9. **`frontend/src/components/CompareModal.test.tsx`** (New File)
   - Created 8 Vitest unit tests covering modal rendering, loading states, error states, passage expansion, protocol warning banners, category filters, and action callbacks.

---

## 4. Supported Comparison Dimensions

The service compares papers across 12 structured dimensions:

| Dimension ID | Dimension Title | Category | Provenance / Data Source | Comparability Rules |
| :--- | :--- | :--- | :--- | :--- |
| `problem` | Research Problem & Motivation | Scientific Evidence | Grounded TASK-13 `problem` evidence passage | Comparable; author statement verified |
| `objective` | Objective & Research Questions | Scientific Evidence | Grounded TASK-13 `objective` evidence passage | Comparable; author statement verified |
| `method` | Methodology & Proposed Approach | Scientific Evidence | Grounded TASK-13 `method` evidence passage | Comparable; architecture claims quoted |
| `dataset` | Dataset & Experimental Setup | Scientific Evidence | Grounded TASK-13 `dataset` evidence passage | Evaluated for benchmark overlap |
| `metrics` | Evaluation Metrics | Scientific Evidence | Grounded TASK-13 `metrics` evidence passage | Evaluated for metric alignment |
| `results` | Reported Results & Findings | Scientific Evidence | Grounded TASK-13 `results` evidence passage | Marked `incomparable_protocols` if datasets/metrics diverge |
| `contributions` | Stated Contributions | Scientific Evidence | Grounded TASK-13 `contributions` evidence passage | Comparable; author claims quoted |
| `limitations` | Limitations & Threats to Validity | Scientific Evidence | Grounded TASK-13 `limitations` evidence passage | Absence disclaimed as reporting boundary |
| `future_work` | Future-Work Directions | Scientific Evidence | Grounded TASK-13 `future_work` evidence passage | Comparable; author plans quoted |
| `publication_metadata` | Publication Venue & Year | Publication Metadata | Catalog metadata (`venue`, `year`) | Real catalog records; zero synthetic data |
| `citation_metrics` | Citation Information | Publication Metadata | Catalog metadata (`citation_count`) | Tracked count or explicit untracked state |
| `evidence_coverage` | Evidence Coverage & Quality | Evidence Provenance | Category presence ratio & source type | High vs. partial coverage indicators |

---

## 5. API Specification

### Endpoint
`POST /api/v1/papers/compare`

### Request Payload
```json
{
  "paper_ids": ["arxiv:2609.35771v1", "arxiv:2609.35768v1"]
}
```
- **Constraint:** Minimum 2, maximum 5 valid integer IDs or string paper identifiers.

### Response Payload Structure
```json
{
  "papers": [
    {
      "id": 66,
      "paper_id": "arxiv:2609.35771v1",
      "title": "From Density to Mass: A New Parametrized Framework...",
      "authors": ["..."],
      "year": 2026,
      "venue": "arXiv Preprint",
      "citation_count": 0
    }
  ],
  "comparison_points": [
    {
      "dimension": "Proposed Architecture & Methodology",
      "values": {
        "arxiv:2609.35771v1": "[Abstract] We present a new parametrized framework...",
        "arxiv:2609.35768v1": "[Abstract] We introduce Projected Distribution Matching Distillation..."
      }
    }
  ],
  "executive_summary": "Structured evidence-grounded comparative evaluation of 2 research publications...",
  "dimensions": [
    {
      "dimension_id": "method",
      "dimension_title": "Methodology & Proposed Approach",
      "category": "scientific_evidence",
      "comparability_status": "comparable",
      "comparability_note": null,
      "cells": {
        "arxiv:2609.35771v1": {
          "paper_id": "arxiv:2609.35771v1",
          "paper_title": "From Density to Mass: A New Parametrized Framework...",
          "dimension_key": "method",
          "dimension_label": "Methodology & Proposed Approach",
          "has_evidence": true,
          "claim": "We present a new parametrized framework...",
          "source_passage": "We present a new parametrized framework...",
          "char_start": 142,
          "char_end": 218,
          "section_name": null,
          "page_number": null,
          "source_type": "abstract",
          "confidence_score": 0.95,
          "status": "supported",
          "status_note": "Exact passage verified in abstract"
        }
      }
    }
  ],
  "coverage_summary": [
    {
      "paper_id": "arxiv:2609.35771v1",
      "title": "From Density to Mass: A New Parametrized Framework...",
      "source_type": "abstract",
      "evidence_count": 2,
      "categories_present": ["problem", "method"],
      "missing_categories": ["objective", "dataset", "metrics", "results", "contributions", "limitations", "future_work"],
      "coverage_percentage": 22.2,
      "coverage_level": "Partial Coverage (Abstract Only)",
      "is_stale": false,
      "source_quality_warning": "Evaluated from abstract only. Full experimental setup, detailed methodology, and comprehensive limitation analysis require full-text access."
    }
  ],
  "supported_similarities": [],
  "supported_differences": [],
  "incomparable_dimensions": [],
  "warnings": [
    "Paper 'From Density to Mass...' is evaluated from abstract text only."
  ]
}
```

---

## 6. Verification and Test Results

### 1. Backend Regression Suite
Command: `./venv/bin/pytest tests/`  
**Result:** **119 PASSED, 0 FAILED** in 30.34s

Breakdown by test module:
- `tests/test_academic_sources.py`: 11 passed
- `tests/test_auth_and_isolation.py`: 8 passed
- `tests/test_driut_scheduler.py`: 16 passed
- `tests/test_embedding_and_sync.py`: 13 passed
- `tests/test_evidence_extraction.py`: 21 passed
- `tests/test_faiss_consistency.py`: 6 passed
- `tests/test_health.py`: 5 passed
- `tests/test_paper_comparison.py`: 13 passed
- `tests/test_papers_api.py`: 16 passed
- `tests/test_pdf_upload.py`: 6 passed
- `tests/test_rate_limiter.py`: 4 passed

### 2. Frontend Test Suite
Command: `npm test -- --run`  
**Result:** **37 PASSED, 0 FAILED** across 4 test suites in 1.01s
- `src/components/CompareModal.test.tsx`: 8 passed
- `src/components/EvidenceModal.test.tsx`: 10 passed
- `src/services/api.test.ts`: 15 passed
- `src/App.test.tsx`: 4 passed

### 3. Frontend Production Build
Command: `npm run build`  
**Result:** **SUCCESS** in 639ms
- `dist/index.html`: 0.95 kB (gzip: 0.53 kB)
- `dist/assets/index-DtwgOF85.css`: 14.37 kB (gzip: 3.88 kB)
- `dist/assets/index-DUQrqQoW.js`: 231.89 kB (gzip: 69.64 kB)

### 4. Containerized Runtime Verification
Live testing on container `research-paper-recommender-backend-1` (port 8000):
- `GET http://localhost:8000/api/v1/health` -> `200 OK {"status":"ok","database":"connected"}`
- `POST http://localhost:8000/api/v1/papers/compare` with 2 real papers -> `200 OK` (12 dimensions, coverage summary, non-empty cells)
- `POST http://localhost:8000/api/v1/papers/compare` with > 5 papers -> `422 Unprocessable Entity`
- `POST http://localhost:8000/api/v1/papers/compare` with missing ID -> `404 Not Found`

---

## 7. Acceptance Criteria Verification Matrix

| Criterion | Description | Status | Evidence / Verification |
| :---: | :--- | :---: | :--- |
| **AC-1** | Researchers can compare multiple existing papers (2-5) | **PASS** | Validated in `test_two_paper_structured_comparison`, `test_multi_paper_comparison_up_to_five`, and live curl |
| **AC-2** | Results use real metadata and TASK-13 evidence | **PASS** | `PaperEvidence` records and deterministic text NLP extraction reused without generative templates |
| **AC-3** | Each substantive finding can be traced to a source | **PASS** | Validated exact `char_start`, `char_end`, `source_type`, and expandable inspection in frontend |
| **AC-4** | Missing evidence is not misrepresented as a difference | **PASS** | Validated explicit `missing_evidence` status and disclaimer in backend and frontend tests |
| **AC-5** | Incompatible numerical results guarded from equivalence | **PASS** | Validated `incomparable_protocols` status, warning banners, and `test_disparate_numerical_results_marked_incomparable` |
| **AC-6** | API authorization and privacy protections intact | **PASS** | Validated public catalog access and cross-user note isolation in `test_authentication_and_user_isolation` |
| **AC-7** | Frontend supports evidence inspection & partial results | **PASS** | Validated in `CompareModal.test.tsx` (all 8 tests passing) and responsive card layout |
| **AC-8** | Backend regression suite passes | **PASS** | 119/119 backend tests passing in pytest |
| **AC-9** | Frontend build succeeds | **PASS** | Vite + TypeScript build succeeds with 0 errors |
| **AC-10** | Existing data, indexes, secrets, and Git work preserved | **PASS** | Database counts identical (132 papers, 1 evidence), canonical FAISS hashes intact, 0 destructive git ops |
| **AC-11** | Completion report records results and risks | **PASS** | Comprehensive report generated in repo and artifact dir |

---

## 8. Known Limitations & Future Work

1. **OCR-Free PDF Extraction:** Provenance for uploaded PDFs depends on extractable text layers generated by `pypdf`. Scanned non-OCR PDFs will have limited evidence coverage.
2. **Abstract-Only Literature:** Papers ingested from external feeds without uploaded PDFs only contain abstract text. The system explicitly discloses this limitation.
3. **External Citation Dynamic Sync:** Citations reflect the internal catalog metadata. External Google Scholar/Crossref live sync remains an asynchronous batch operation.
