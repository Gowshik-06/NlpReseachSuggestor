# RESEARCHLENS TASK 1A — LOCAL DATABASE SEARCH FIX REPORT

## Executive Summary

TASK 1A resolved the Local Database search defect in ResearchLens. Prior to this fix, submitting `POST /api/v1/papers/search` with `sources: ["local"]` returned zero results from the 158-paper catalog because the query engine incorrectly demanded that each database record's `source` column equal `"local"`. In reality, the catalog's records reflect their academic ingestion origin (`arxiv`, `pubmed`, `csir`, `crossref`, `semanticscholar`, `test`).

By decoupling catalog query semantics from paper provenance filtering in `backend/app/services/recommendation_engine.py`, selecting Local Database now reliably queries and returns matching papers from PostgreSQL and FAISS regardless of provenance, while leaving external provider filtering and live invariants intact.

All non-negotiable safety constraints were strictly preserved:
- Zero database writes, schema migrations, table truncations, or FAISS rebuilds were executed.
- Live database row counts (158 papers, 6 users, 1 saved paper, 31 DRIUT alerts, 1 paper evidence) and FAISS index counts (159 entries) remained identical before and after.
- Ollama was not installed; no external model weights were downloaded.
- No Git commits, stashes, resets, or discards were executed.

---

## 1. Root Cause Analysis

1. **SQL Filter Provenance Conflation**:
   In `backend/app/services/recommendation_engine.py` (lines 90–92 prior to fix):
   ```python
   base_filter = []
   if req.sources:
       base_filter.append(Paper.source.in_(req.sources))
   ```
   When `req.sources` contained `["local"]`, the query builder appended `WHERE papers.source IN ('local')`. The live PostgreSQL database contains 158 research papers with origin distribution:
   - `arxiv`: 37
   - `pubmed`: 39
   - `csir`: 37
   - `crossref`: 33
   - `semanticscholar`: 10
   - `test`: 2
   - `local`: 0
   Because zero catalog records had provenance `"local"`, SQL candidate filtering returned 0 rows.

2. **Ranking/Scoring Filter Provenance Conflation**:
   In `backend/app/services/recommendation_engine.py` (lines 263–264 prior to fix):
   ```python
   if req.sources and paper.get("source") not in req.sources:
       continue
   ```
   Even when vector search or keyword queries identified local candidate papers, this condition dropped all candidates whose `source` was not `"local"`.

3. **Masked Integration Tests**:
   In `backend/tests/test_papers_api.py`, earlier test fixtures hardcoded `source="local"` on synthetic test fixtures (`p_bert`, `p_attn`, `p_roberta`), which masked the defect during prior test runs. Furthermore, running `test_papers_api.py` directly against the live database would mutate/delete live records (`DRIUTAlert.user_id == 'default_user'`), necessitating strict test isolation.

---

## 2. Files Changed and Rationale

### A. [`backend/app/services/recommendation_engine.py`](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backend/app/services/recommendation_engine.py)
- **Lines 82–98**:
  - Initialized `local_pids: set = set()`.
  - Removed `base_filter.append(Paper.source.in_(req.sources))` from SQL candidate retrieval. Selecting the "Local Database" source requests papers stored in the local catalog; filtering by `Paper.source` was conflating the catalog storage location with original paper provenance.
- **Lines 140–145**:
  - Captured `local_pids = set(candidate_map.keys())` to identify all papers retrieved from the local database catalog.
- **Lines 160–165**:
  - Guarded external source parsing: `external_sources = [s for s in (req.sources or []) if s != "local"]`. When only `sources: ["local"]` is specified, `external_sources` is empty and no external network calls occur.
- **Lines 260–270**:
  - Replaced naive `paper.get("source") not in req.sources` with:
    ```python
    if req.sources:
        is_local_match = "local" in req.sources and (paper.get("paper_id") in local_pids or paper.get("source") == "local")
        is_source_match = paper.get("source") in req.sources
        if not (is_local_match or is_source_match):
            continue
    ```
    This ensures that when `"local"` is selected, any paper retrieved from the local catalog is retained. When external sources (e.g. `["arxiv"]`) are selected without `"local"`, non-arXiv papers remain excluded as designed.

### B. [`backend/tests/test_local_search_correctness.py`](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backend/tests/test_local_search_correctness.py) *(New isolated test file)*
- Created isolated, mock-backed unit tests using in-memory SQLite and mock FAISS to verify all 6 required behaviors without mutating PostgreSQL or production FAISS indices.

---

## 3. Exact Implementation Behavior

| Request Payload | Local DB Searched | External APIs Called | Candidate Provenance Retained |
| :--- | :---: | :---: | :--- |
| `sources: ["local"]` | **Yes** (all catalog papers) | **No** | `arxiv`, `pubmed`, `csir`, `crossref`, etc. |
| `sources: ["arxiv"]` | **No** | **Yes** (arXiv only) | `arxiv` only |
| `sources: ["local", "arxiv"]` | **Yes** (all catalog papers) | **Yes** (arXiv) | All local catalog + external arXiv |
| `sources: []` or omitted | **Yes** (default behavior) | **No** (if empty) / **All** (if default) | Preserves existing contract |

When searching locally:
- Local database candidates already possess persistent primary keys (`id`), so `unpersisted = [p for p in unique_candidates if not p.get("id")]` evaluates to empty; zero database inserts occur.
- Existing FAISS indexing skips already indexed `paper_id` entries; zero vector additions occur.

---

## 4. Test Evidence and Commands

### A. Focused Isolated Unit Tests (Pytest)
Command:
```bash
cd backend && ./venv/bin/pytest tests/test_local_search_correctness.py -v
```
Output:
```
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backend
configfile: pytest.ini
plugins: anyio-4.15.1
collected 6 items

tests/test_local_search_correctness.py::test_local_search_returns_all_provenance_types PASSED [ 16%]
tests/test_local_search_correctness.py::test_local_search_specific_queries PASSED [ 33%]
tests/test_local_search_correctness.py::test_local_only_search_does_not_invoke_external_providers PASSED [ 50%]
tests/test_local_search_correctness.py::test_local_search_does_not_mutate_records_or_faiss PASSED [ 66%]
tests/test_local_search_correctness.py::test_external_source_filtering_behavior PASSED [ 83%]
tests/test_local_search_correctness.py::test_empty_result_behavior_well_defined PASSED [100%]

============================== 6 passed in 0.38s ===============================
```
**Exit Code**: 0. 6 tests passed, 0 failed, 0 skipped.

### B. Live Backend API Verification (Read-Only Probes)
1. **Query**: `"Transformer"` with `sources: ["local"]`
   ```bash
   curl -s -X POST http://localhost:8000/api/v1/papers/search \
     -H "Content-Type: application/json" \
     -d '{"query": "Transformer", "sources": ["local"], "limit": 5, "sort_by": "relevance"}'
   ```
   **Result**: Returned `total_found: 69`. Top 5 returned include Crossref and PubMed catalog records (`crossref:10.1017/9781108891530.011`, `pubmed:41094848`).

2. **Query**: `"Neural"` with `sources: ["local"]`
   ```bash
   curl -s -X POST http://localhost:8000/api/v1/papers/search \
     -H "Content-Type: application/json" \
     -d '{"query": "Neural", "sources": ["local"], "limit": 5, "sort_by": "relevance"}'
   ```
   **Result**: Returned `total_found: 61`. Top 5 returned include Crossref neural network records (`crossref:10.1016/s0893-6080(11)00319-4`, `similarity_score: 0.94`).

3. **Query**: `"Diffusion"` with `sources: ["local"]`
   ```bash
   curl -s -X POST http://localhost:8000/api/v1/papers/search \
     -H "Content-Type: application/json" \
     -d '{"query": "Diffusion", "sources": ["local"], "limit": 5, "sort_by": "relevance"}'
   ```
   **Result**: Returned `total_found: 57`. Top 5 returned include fractional diffusion equations (`crossref:10.1017/9781316534649.005`).

4. **Query**: `"Dark Matter Environment Around Black Holes"` with `sources: ["local"]`
   ```bash
   curl -s -X POST http://localhost:8000/api/v1/papers/search \
     -H "Content-Type: application/json" \
     -d '{"query": "Dark Matter Environment Around Black Holes", "sources": ["local"], "limit": 5, "sort_by": "relevance"}'
   ```
   **Result**: Returned `arxiv:2609.35771v1` (`source: arxiv`) as rank 1 alongside CSIR and Crossref catalog papers.

### C. Live Browser UI Verification (Playwright)
Executed headless Playwright verification against `http://localhost:3000`:
- Unchecked all external repositories (`arXiv`, `PubMed`, `CSIR`, `Semantic Scholar`, `Crossref`, `DBLP`).
- Verified only `Local Database` remained checked.
- Executed query `"Transformer Attention Mechanism"`.
- Verified that the UI rendered **12 paper cards** with semantic metadata and similarity scores.
- **Exit Code**: 0.

---

## 5. Data Preservation and Integrity Audit

### Baseline vs. Post-Fix Database & FAISS Invariants

| Metric | Baseline (Pre-Task 1A) | Post-Fix (After Verification) | Change |
| :--- | :---: | :---: | :---: |
| **PostgreSQL `papers`** | 158 | 158 | 0 |
| **PostgreSQL `users`** | 6 | 6 | 0 |
| **PostgreSQL `saved_papers`** | 1 | 1 | 0 |
| **PostgreSQL `driut_alerts`** | 31 | 31 | 0 |
| **PostgreSQL `paper_evidence`** | 1 | 1 | 0 |
| **FAISS Index `ntotal`** | 159 | 159 | 0 |
| **FAISS `paper_metadata` entries** | 159 | 159 | 0 |

### Git State and SHA256 Checksums

- **Git Branch**: `master` (commit `c26cd6a16fd4de20a91cf10847ca6463dc2efc35`)
- **Git Status Summary**: Pre-existing modified/untracked files preserved untouched. Only `backend/app/services/recommendation_engine.py` was modified, and isolated test file `backend/tests/test_local_search_correctness.py` was created.

#### Checksums:
- `backend/app/services/recommendation_engine.py`:
  - Before: `e41940e049aa43b831f63ddc875b9109fbabacddbcd566f9fced4025e35a20ac`
  - After:  `6733c091236eb6d59edcb936b3e4d84a9f9aafcc41e0ae96e2d1acdca03d3861`
- `backend/app/api/v1/endpoints/papers.py`:
  - `014fa0722f5fd07b633c7d5728bd916836d952f3d15a87bdd4e61b3041326899` (Unmodified)
- `backend/app/schemas/paper.py`:
  - `b9d86ef8aeaf7068c860de1f53bed0f9def9ccc4adcf61a50bf9e006237f1eb1` (Unmodified)
- `backend/app/models/paper.py`:
  - `5a1783f22bd2c5a0b6e9d0bf0f5f2152bf9610d479616d56b3ac5b31be0c0438` (Unmodified)
- `backend/tests/test_papers_api.py`:
  - `2c4036fd3f6f5a722628f24b67fde2795cda114a16d19b7f85ab2f897fd8d1c2` (Unmodified)
- `backend/tests/test_local_search_correctness.py`:
  - Created: `19c8bd976b30eda1b0c0d1c0d46874d0f532eeca3e16804d5bb979d80b5de037`

---

## 6. Safety Affirmations

1. **Ollama / Model Weights**: No Ollama instances or local LLM models were installed, downloaded, or invoked.
2. **Database Integrity**: No migrations, resets, truncations, reseeding, or write operations were executed against PostgreSQL.
3. **FAISS Index Integrity**: No rebuilds, index replacements, or additions were performed on FAISS vector storage.
4. **Git Discipline**: No `git reset`, `git clean`, `git stash`, or `git commit` commands were run.
5. **Scope Isolation**: No changes were made to external provider ingestion, PDF upload handling, or subsequent roadmap items.

---

## 7. Remaining Risks & Next Steps

- **Risk**: Legacy test file `backend/tests/test_papers_api.py` still contains fixtures that wipe `default_user` DRIUT alerts if executed directly against a live database. Future roadmap tasks should isolate that fixture to SQLite or a separate test database before running full backend test suites.
- **Next Step**: Task 1A is complete and ready for review. Awaiting instructions before proceeding to subsequent roadmap tasks.
