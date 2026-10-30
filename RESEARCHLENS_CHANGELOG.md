# ResearchLens — Production Engineering & Remediation Changelog

**Document ID:** `RESEARCHLENS_CHANGELOG.md`  
**Reference Release:** v1.0.0-rc1  
**Remediation Date:** October 18, 2026

---

## 1. Summary of Changes

This changelog records the complete set of architectural remediations, bug fixes, algorithmic refinements, and operational tools implemented to transition ResearchLens from demo software to production-ready academic software.

---

## 2. Detailed Change Log by Component

### 2.1 Academic Sources & Publication Date Parsing
- **Affected File:** `backend/app/services/academic_sources.py`
- **Problem Statement:** The audit revealed 26 records with `year >= 2027` (25 with 2027, 1 with 2028). The legacy parser extracted the year strictly from NCBI `pubdate` without considering `epubdate`, falsely categorizing papers published electronically in 2026 as scheduled 2027 releases.
- **Implemented Fix:**
  - Implemented `parse_pubmed_dates(p, reference_year=2026)` separating `epubdate` from `pubdate`.
  - For ahead-of-print articles (`epub_year <= 2026` and `print_year > 2026`), sets effective ranking year to `epub_year` (2026) with status `ahead_of_print`.
  - Preserves print issue provenance in venue annotation: e.g., `🏛️ PubMed: {journal} (Advance Article; Scheduled Print: {raw_pubdate})`.
  - Properly classifies forthcoming articles (e.g., `pubmed:42635983`, year 2028) with `status="forthcoming"`.

### 2.2 Search Relevance Defaults & Frontend Controls
- **Affected Files:** `backend/app/schemas/paper.py`, `frontend/src/pages/HomePage.tsx`
- **Problem Statement:** Default search sorting was misaligned, causing search results to order by recency rather than semantic relevance.
- **Implemented Fix:**
  - Updated `SearchQueryRequest.sort_by` default in Pydantic schema to `"relevance"`.
  - Updated initial sort state in `HomePage.tsx` to `"relevance"`.
  - Reordered frontend sort buttons with `"🎯 Relevance"` first (`id="sort-relevance-btn"`), followed by `"⚡ 2026 Latest First"` and `"📊 Citations"`.

### 2.3 DRIUT Chronological Guard
- **Affected File:** `backend/app/services/driut_service.py`
- **Problem Statement:** Candidate papers published earlier than saved baseline papers were erroneously evaluated for "improvement" or "extension" relationships, violating chronological causality.
- **Implemented Fix:**
  - Implemented `extract_effective_publication_year(paper)` to resolve effective publication years.
  - Added Step 8b Chronology-Aware Guard: if `new_year < saved_year`, candidate paper cannot be classified as an improvement, extension, or superseding work.
  - Added transparency notes when publication dates are ambiguous or forthcoming.

### 2.4 Research Evolution Forthcoming Milestone Handling
- **Affected File:** `backend/app/services/evolution_service.py`
- **Problem Statement:** Timeline nodes for papers with publication years > 2026 appeared as standard historical milestones without qualification.
- **Implemented Fix:**
  - Qualified future dates (> 2026) by tagging `TimelinePaper.date_uncertainty_note` with `"Forthcoming / Scheduled publication ({year}). Advance research preprint or ahead-of-print article."`
  - Formatted `TimelineYearGroup.year_label` as `"{year} (Forthcoming / Scheduled Issue)"`.

### 2.5 Synthetic Placeholder Abstract Guards
- **Affected Files:** `backend/app/services/evidence_service.py`, `backend/app/services/summary_service.py`, `backend/app/services/evolution_service.py`
- **Problem Statement:** 5 legacy PubMed records contained synthetic placeholder abstracts (e.g., *"Biomedical & computational research paper indexed by..."*). NLP pipelines risked extracting these indexing phrases as genuine scientific claims.
- **Implemented Fix:**
  - Defined `SYNTHETIC_PLACEHOLDER_REGEX` and `is_synthetic_placeholder_abstract(text)`.
  - `extract_evidence_from_text` returns 0 claims and logs `unavailable_evidence`.
  - `generate_paper_summary` returns a transparent notice explaining that only metadata is available, refusing to call local or cloud LLMs on synthetic text.
  - `evolution_service` skips claim extraction for placeholder abstracts.

### 2.6 Semantic Relevance Floor & Lexical Precision
- **Affected File:** `backend/app/services/recommendation_engine.py`
- **Problem Statement:** Out-of-domain queries like *"ancient Roman architecture"* returned 64 results with similarity scores around 0.80–0.82 from a catalog of 162 papers.
- **Implemented Fix:**
  - Set empirical `SEMANTIC_RELEVANCE_FLOOR = 0.835` based on score separation analysis.
  - Defined `GENERIC_SEARCH_TERMS` (`architecture`, `system`, `model`, `network`, etc.) to prevent false lexical matches on multi-word queries.
  - Live evaluation confirmed that *"ancient Roman architecture"* returns 0 results (`total_found: 0, results: []`), while relevant in-domain queries return high-confidence results (scores 0.84–0.89).

### 2.7 Safe FAISS & PostgreSQL Maintenance Utility
- **Affected File:** `scripts/reconcile_faiss_postgres.py`
- **Purpose:** Standalone administrative utility to inspect vector-to-relational consistency, identify orphans, compute cryptographic hashes, and execute safe, backed-up reconciliations.

### 2.8 Targeted Regression Test Suite
- **Affected File:** `backend/tests/test_targeted_remediations.py`
- **Coverage:** 23 comprehensive unit tests validating PubMed date parsing, default search ordering, DRIUT chronological guard, timeline annotations, synthetic abstract detection, and semantic relevance thresholding.

---

## 3. Test Verification Metrics

| Test Suite | Commands Executed | Result | Duration |
|:---|:---|:---:|:---:|
| Backend Full Regression | `./backend/venv/bin/pytest backend/tests/` | **328 passed, 0 failed** | 145.59s |
| Targeted Remediations | `./backend/venv/bin/pytest backend/tests/test_targeted_remediations.py` | **23 passed, 0 failed** | 1.83s |
| DRIUT Intelligence | `./backend/venv/bin/pytest backend/tests/test_driut_intelligence.py` | **17 passed, 0 failed** | 5.86s |
| DRIUT Scheduler | `./backend/venv/bin/pytest backend/tests/test_driut_scheduler.py` | **14 passed, 0 failed** | 7.97s |
| Frontend Vitest | `npm test -- --run` | **66 passed, 0 failed** | 2.14s |
| Frontend Production Build | `npm run build` (`tsc -b && vite build`) | **0 errors (Clean)** | 692ms |

---

## 4. Pending Maintenance Tasks

1. **FAISS Index Reconcile:** Remove single orphan vector `test:t15:cand_ext` using `scripts/reconcile_faiss_postgres.py` during approved maintenance window.
2. **PostgreSQL Database Date Migration:** Execute approved data migration updating the 25 records with `year = 2027` to `year = 2026` based on validated `epubdate`.
