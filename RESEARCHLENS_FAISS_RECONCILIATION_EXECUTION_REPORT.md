# ResearchLens — FAISS Orphan Reconciliation Execution & Verification Report

**Document ID:** `RESEARCHLENS-EXEC-FAISS-20261018-01`  
**Execution Timestamp:** 2026-10-18T23:52:00+05:30  
**Target Orphan:** `test:t15:cand_ext` (Index 10 in pre-reconcile `id_map`)  
**Repository Root:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Verified Preflight Backup:** `backups/faiss_pre_reconcile_20261018_234205/`  

---

## 1. Executive Summary

On October 18, 2026, the approved single-vector reconciliation was executed on the ResearchLens FAISS vector database to permanently remove the sole confirmed orphan vector (`test:t15:cand_ext`) without regenerating embeddings or rebuilding legitimate vectors.

The operation successfully transitioned the vector store from **163 vectors to exactly 162 vectors**, achieving 100% exact alignment with the 162 research papers in PostgreSQL. All 162 legitimate vector representations were extracted and re-indexed in their original form down to the exact bit (`max_diff = 0.00e+00`), and all ID-to-metadata associations were preserved.

The backend FastAPI process was gracefully restarted under systemd (`researchlens-backend.service`), immediately loading the new 162-vector index. Live HTTP API verification and 73 non-destructive regression tests confirmed full system health, flawless semantic search, and zero data loss.

---

## 2. Pre-Execution Hashes and Backup Verification

Before modifying any files, active and preflight backup checksums were verified:

| File Artifact | Active / Backup Location | File Size | SHA-256 Digest | Match |
| :--- | :--- | :---: | :--- | :---: |
| **Active FAISS Index** | `backend/data/processed/faiss/research_index.faiss` | 500,781 B | `19fbb3c21e69c02ad060f272b7367ca23f3cb57f4fc28619c1854a0cc0a8dda8` | **EXACT** |
| **Active FAISS Meta** | `backend/data/processed/faiss/papers_meta.json` | 204,112 B | `6a3b759544d96bf03860f921a43ab23734d2b5eb7cb6745c4b3f0db72b5c4c1e` | **EXACT** |
| **Preflight Backup Index** | `backups/faiss_pre_reconcile_20261018_234205/research_index.faiss` | 500,781 B | `19fbb3c21e69c02ad060f272b7367ca23f3cb57f4fc28619c1854a0cc0a8dda8` | **EXACT** |
| **Preflight Backup Meta** | `backups/faiss_pre_reconcile_20261018_234205/papers_meta.json` | 204,112 B | `6a3b759544d96bf03860f921a43ab23734d2b5eb7cb6745c4b3f0db72b5c4c1e` | **EXACT** |

The preflight dry-run confirmed:
- PostgreSQL contains 162 unique paper IDs.
- FAISS and metadata each contained 163 entries.
- The sole orphan was `test:t15:cand_ext`.
- 0 unindexed database papers.

---

## 3. Reconciliation Execution & Console Output

The approved maintenance utility was executed with explicit flags:

```bash
./backend/venv/bin/python scripts/reconcile_faiss_postgres.py \
  --execute \
  --backup-dir backups/faiss_pre_reconcile_20261018_234205
```

### Complete Console Output & Exit Code
```text
================================================================================
RESEARCHLENS — FAISS & POSTGRESQL RECONCILIATION & INTEGRITY TOOL
================================================================================
Database URL: localhost:5432/research_papers
FAISS Directory: /home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backend/data/processed/faiss
Mode: EXECUTE (WRITE)

--- DIAGNOSTIC RESULTS ---
Index Exists: True (SHA-256: 19fbb3c21e69c02a...)
Metadata Exists: True (SHA-256: 6a3b759544d96bf0...)
FAISS ntotal: 163
FAISS Dimension: 768
FAISS Metric: INNER_PRODUCT
id_map Count: 163
metadata Dict Count: 163
DB Paper Count: 162
Orphan Vectors (in FAISS but absent from DB): 1 -> ['test:t15:cand_ext']
Unindexed Papers (in DB but absent from FAISS): 0 -> []
Overall Consistency: MISMATCH DETECTED

Executing reconciliation with pre-maintenance backup to backups/faiss_pre_reconcile_20261018_234205...
Reconciliation completed successfully!
Purged orphans: ['test:t15:cand_ext']
Original ntotal: 163 -> New ntotal: 162
Index consistency: CONSISTENT
```

**Exit Status:** `0` (Success)

---

## 4. Before-and-After Metrics & Checksums

### Metric Comparison
| Component / Metric | Before Execution | After Execution | Delta | Target Alignment |
| :--- | :---: | :---: | :---: | :---: |
| **PostgreSQL `papers` Count** | 162 | 162 | 0 | **EXACT** |
| **PostgreSQL Unique `paper_id`** | 162 | 162 | 0 | **EXACT** |
| **FAISS Vector Count (`ntotal`)** | 163 | **162** | **-1** | **EXACT (162 = 162)** |
| **FAISS Vector Dimension** | 768 | 768 | 0 | **PRESERVED** |
| **FAISS Metric Type** | 0 (`IndexFlatIP`) | 0 (`IndexFlatIP`) | 0 | **PRESERVED** |
| **Metadata `id_map` Count** | 163 | **162** | **-1** | **EXACT (162 = 162)** |
| **Metadata `metadata` Keys** | 163 | **162** | **-1** | **EXACT (162 = 162)** |
| **Orphan Vectors in FAISS** | 1 (`test:t15:cand_ext`) | **0** | **-1** | **RESOLVED** |
| **Unindexed Papers in DB** | 0 | **0** | 0 | **RESOLVED** |
| **Index Consistency Status** | `MISMATCH DETECTED` | **`CONSISTENT`** | N/A | **100% SYNCHRONIZED** |

### File Checksum Transition
| File Path | Status | Size | SHA-256 Digest |
| :--- | :---: | :---: | :--- |
| `backend/data/processed/faiss/research_index.faiss` | **Before** | 500,781 B | `19fbb3c21e69c02ad060f272b7367ca23f3cb57f4fc28619c1854a0cc0a8dda8` |
| `backend/data/processed/faiss/research_index.faiss` | **After** | 497,709 B | `f5be6e08da83c755cb0879a01fd7e25922ea8dcb46004e4fa46983fc0feaa02f` |
| `backend/data/processed/faiss/papers_meta.json` | **Before** | 204,112 B | `6a3b759544d96bf03860f921a43ab23734d2b5eb7cb6745c4b3f0db72b5c4c1e` |
| `backend/data/processed/faiss/papers_meta.json` | **After** | 203,613 B | `2cc5f36840a360937689e2d97f56ce04e647389b5ac8dea55ce0444321aa6d24` |

---

## 5. Verification of Vector Values and Identity Associations

An independent vector-by-vector numerical audit was performed comparing the post-execution index against the preflight backup:

1. **Mapping Sequence:**
   - Pre-execution indices `0..9` $\rightarrow$ Post-execution indices `0..9` (IDs identical).
   - Pre-execution index `10` (`test:t15:cand_ext`) $\rightarrow$ Omitted.
   - Pre-execution indices `11..162` $\rightarrow$ Post-execution indices `10..161` (IDs identical).
2. **Numerical Vector Verification:**
   - For all 162 retained vectors, `diff = np.max(np.abs(new_vec - old_vec))` was evaluated.
   - **Maximum vector difference across all 162 vectors:** **`0.00e+00`** (Bit-identical).
   - All 162 vectors contain only finite values (0 NaNs, 0 Infs, L2 norm $\in [0.9999, 1.0001]$).
3. **No Model Re-embedding:**
   - The SPECTER2 neural network was never invoked. Vector weights were extracted purely in-memory via `index.reconstruct(old_idx)` and serialized into the new `IndexFlatIP`.
4. **PostgreSQL Immutability:**
   - `SELECT count(*) FROM papers;` = 162.
   - Database tables `papers`, `saved_papers`, `driut_alerts`, and `paper_evidence` had zero inserts, updates, or deletes.

---

## 6. Backend Cache Refresh & Lifecycle Management

Following persistent file replacement, the backend process was safely refreshed:

```bash
systemctl --user restart researchlens-backend
```

### Startup Verification
- Backend service restarted under systemd unit `researchlens-backend.service` (PID 102267).
- Startup log from `logs/backend.log`:
  ```text
  2026-10-18 23:52:38 | INFO | app.main | Starting research-paper-recommender v0.1.0 in development mode
  2026-10-18 23:52:38 | INFO | app.services.vector_index | Loaded FAISS index from /home/tonystark/.../research_index.faiss with 162 entries (dimension=768)
  2026-10-18 23:52:38 | INFO | app.services.driut_scheduler | DRIUT background scheduler started (interval: 60 minutes, academic queries: True).
  INFO: Application startup complete.
  ```
- Dev environment status (`scripts/dev-status.sh`): **ALL SERVICES OPERATIONAL**.

---

## 7. Live Functional API Verification

### 1. Health Endpoint (`GET /api/v1/health`)
```json
{
  "status": "ok",
  "service": "research-paper-recommender",
  "version": "0.1.0",
  "environment": "development",
  "database": "connected"
}
```
**Status:** HTTP 200 OK.

### 2. Consistency Status Endpoint (`GET /api/v1/papers/index-status`)
Verified with authorized Bearer token:
```json
{
  "is_consistent": true,
  "is_degraded": false,
  "degradation_reason": null,
  "total_db_papers": 162,
  "faiss_vector_count": 162,
  "faiss_id_map_count": 162,
  "faiss_metadata_count": 162,
  "dimension": 768,
  "missing_vectors_count": 0,
  "orphaned_metadata_count": 0,
  "has_backup_index": false,
  "has_backup_metadata": false
}
```
**Status:** HTTP 200 OK — Confirms active in-memory cache reports 162 vectors with 0 orphans and `is_consistent: true`.

### 3. Semantic Search (`POST /api/v1/papers/search`)
Querying the target's former title `"Scaling Transformer Language Models on GLUE"`:
- Total matching catalog papers found: 54.
- Top ranked candidates returned: `driut:orig:bert` (score: 0.90), `pubmed:41606105` (score: 0.89), `crossref:10.1017/9781108891530.011` (score: 0.89).
- **Result:** `test:t15:cand_ext` is completely absent from all search results. All returned paper IDs resolve to accurate metadata.

---

## 8. Regression Test Suite Execution

All relevant non-destructive regression test suites were executed against the reconciled state:

| Test Suite File | Scope | Tests Run | Result | Duration |
| :--- | :--- | :---: | :---: | :---: |
| `backend/tests/test_local_search_correctness.py` | Provenance filters, local paper discovery, ranking, FAISS immutability | 9 | **9 PASSED** | 8.28s |
| `backend/tests/test_targeted_remediations.py` | PubMed advance epub, lexical fallbacks, DRIUT chronology, synthetic detection | 24 | **24 PASSED** | 8.31s |
| `backend/tests/test_datetime_utc.py` | Timezone-aware UTC datetimes in transient endpoints | 1 | **1 PASSED** | 0.40s |
| `backend/tests/test_defect_remediation_regression.py` | Slash ID decoding, route shadowing, evolution timeline, sort orders | 14 | **14 PASSED** | 14.80s |
| `backend/tests/test_faiss_consistency.py` | Consistency status, backup recovery, corrupted pair protection, dimension safety | 25 | **25 PASSED** | 0.55s |
| **Total Regression Coverage** | | **73** | **73 PASSED (0 Failed)** | **32.34s** |

---

## 9. Backup Location & Disaster Recovery Runbook

The pre-reconciliation backup remains completely intact and verified:
- **Directory:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backups/faiss_pre_reconcile_20261018_234205/`
- **Files:** `research_index.faiss` (SHA-256: `19fbb3c21...`), `papers_meta.json` (SHA-256: `6a3b75954...`), `checksums.sha256`.

### Verified Disaster Recovery Procedure
If ever needed to revert to the 163-vector baseline:
```bash
BACKUP_DIR="backups/faiss_pre_reconcile_20261018_234205"
FAISS_DIR="backend/data/processed/faiss"

# 1. Verify backup integrity
(cd "$BACKUP_DIR" && sha256sum -c checksums.sha256)

# 2. Restore paired files atomically
cp -p "${BACKUP_DIR}/research_index.faiss" "${FAISS_DIR}/research_index.faiss.tmp"
cp -p "${BACKUP_DIR}/papers_meta.json" "${FAISS_DIR}/papers_meta.json.tmp"
mv -f "${FAISS_DIR}/research_index.faiss.tmp" "${FAISS_DIR}/research_index.faiss"
mv -f "${FAISS_DIR}/papers_meta.json.tmp" "${FAISS_DIR}/papers_meta.json"

# 3. Reload backend cache
systemctl --user restart researchlens-backend
```

---

## 10. Explicit Statement of Files and Systems Modified

### Files Modified on Disk:
1. `backend/data/processed/faiss/research_index.faiss` (Active vector store transitioned from 163 to 162 vectors).
2. `backend/data/processed/faiss/papers_meta.json` (Active metadata store transitioned from 163 to 162 entries; `test:t15:cand_ext` removed).

### New Artifacts Created:
1. `backups/faiss_pre_reconcile_20261018_234205/research_index.faiss.bak` (Automated pre-maintenance copy generated by the reconciliation script).
2. `backups/faiss_pre_reconcile_20261018_234205/papers_meta.json.bak` (Automated pre-maintenance copy generated by the reconciliation script).
3. `RESEARCHLENS_FAISS_RECONCILIATION_EXECUTION_REPORT.md` (This document).

### Systems / Stores Untouched:
- **PostgreSQL Database:** 0 rows modified, 0 schema changes. Total papers: 162.
- **Frontend Code & Configuration:** 0 files modified.
- **Backend Application Code & Dependencies:** 0 source files modified.
- **Authentication, Secrets & Credentials:** 0 tokens, users, or secrets modified.
- **Ollama / Local AI:** Unchanged.

---

## 11. Final Verdict

```
RECONCILIATION SUCCESSFUL — ALL INVARIANTS VERIFIED
```
