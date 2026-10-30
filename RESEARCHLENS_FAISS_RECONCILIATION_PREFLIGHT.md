# ResearchLens — FAISS Orphan Reconciliation Pre-Execution Safety Gate Report

**Document ID:** `RESEARCHLENS-PREFLIGHT-FAISS-20261018-01`  
**Execution Timestamp:** 2026-10-18T23:45:00+05:30  
**Repository:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Target Orphan:** `test:t15:cand_ext` (Index position 10 in FAISS `id_map`)  
**Objective:** Safely evaluate pre-execution safety invariants, inspect backup and recovery capabilities, execute read-only dry-run diagnostics, and confirm readiness to reconcile FAISS to exact PostgreSQL alignment without data loss or re-embedding.

---

## 1. Executive Summary

A comprehensive pre-execution safety gate audit was conducted on the ResearchLens FAISS vector store and PostgreSQL database to prepare for purging the single orphan vector `test:t15:cand_ext`.

### Key Verification Findings
1. **Zero Database Drift:** PostgreSQL contains exactly **162 legitimate research papers** across all tables.
2. **FAISS Discrepancy:** The active FAISS vector index contains **163 vectors**, with 163 entries in `id_map` and 163 entries in `papers_meta.json`.
3. **Exact Target Identification:** `test:t15:cand_ext` is confirmed as the **sole orphan** in FAISS (set difference `faiss_pids - db_pids = ['test:t15:cand_ext']`).
4. **Zero Collateral Database Impact:** There are **0 references** to `test:t15:cand_ext` in PostgreSQL `papers`, `saved_papers`, `driut_alerts`, or `paper_evidence`.
5. **Exact Target Location:** The orphan is situated at **index position 10** in `id_map`. All 162 legitimate database records map 1:1 with remaining vector indices.
6. **Vector Integrity:** All 163 vectors in FAISS were verified to be reconstructible, finite, non-NaN, and unit-norm L2 normalized (dimension 768, `METRIC_INNER_PRODUCT`).
7. **Permission Constraint Identified:** The proposed backup directory `/var/backups/researchlens/faiss_pre_reconcile` cannot be written by the runtime user `tonystark` (uid=1000) without `sudo` privileges because `/var/backups` does not exist on Fedora Linux and `/var` is `root:root` (0755).
8. **Verified Backup Created:** An immutable, verified, user-owned pre-execution backup was established at `backups/faiss_pre_reconcile_20261018_234205/` with byte-identical SHA-256 hashes.
9. **Zero Persistent Mutation:** No persistent database records, FAISS vectors, or application configuration files were modified during this audit.

---

## 2. Phase 1 — Code & Function Inspection

The following files, components, and functions were thoroughly inspected:

| File Path | Component / Function | Purpose & Inspection Finding |
| :--- | :--- | :--- |
| `scripts/reconcile_faiss_postgres.py` | `compute_sha256(filepath)` | Computes chunked SHA-256 digest of FAISS index and metadata files. |
| `scripts/reconcile_faiss_postgres.py` | `diagnose_faiss_and_db(db_url, faiss_dir)` | Read-only inspection comparing PostgreSQL `papers.paper_id` against FAISS `id_map` and metadata. Confirms counts, dimensions, orphans, and unindexed records. |
| `scripts/reconcile_faiss_postgres.py` | `reconcile_and_purge_orphans(db_url, faiss_dir, backup_dir)` | Execution routine: enforces pre-maintenance `.bak` copies, verifies SHA-256 hashes, extracts retained vectors via `index.reconstruct(old_idx)`, generates new `IndexFlatIP`, stages in unique `.tmp.{uid}` files, asserts count/dimension integrity, and performs atomic `os.replace`. Provides automated rollback if any step raises an error. |
| `scripts/reconcile_faiss_postgres.py` | `main()` | CLI entry point: defaults to safe `--dry-run` (read-only); strictly requires explicit `--execute` and `--backup-dir` flags to proceed with any disk writes. |
| `backend/app/services/vector_index.py` | `validate_index_pair_files(...)` | Production pair-consistency validator: verifies readability, non-zero file sizes, `ntotal == len(id_map)`, `len(id_map) == len(meta_dict)`, set inclusion, uniqueness, and dimension alignment. |
| `backend/app/services/vector_index.py` | `FAISSVectorIndex._load_or_initialize()` | Startup loader: checks active file pair; attempts fallback to `.bak` files if active files are corrupted; enters protected `DEGRADED` state if both fail to prevent silent overwrites. |
| `backend/app/services/vector_index.py` | `FAISSVectorIndex.save()` | Persists vector index via unique staging files (`.tmp.{uuid}`), validates staged files, creates `.bak` copies, and performs atomic `os.replace`. |
| `backend/app/services/vector_index.py` | `get_index_consistency_status(session)` | Internal status inspection service: queries PostgreSQL and FAISS singleton to report real-time consistency metrics without mutation. |
| `backend/app/models/paper.py` | `Paper`, `SavedPaper` | Canonical schema: `Paper.paper_id` is the external unique string key (`String(120)`) used across FAISS and DRIUT. Foreign keys in dependent tables reference `papers.id` with `ondelete="CASCADE"`. |
| `backend/tests/test_faiss_consistency.py` | Test suite (TASK-07D) | Confirms consistency checks, degraded index blocking, backup recovery mechanics, and atomic save semantics. |

### Technical Mechanics of Vector Removal
- **No Model Re-embedding:** The index is `faiss.IndexFlatIP`. Native flat inner-product indices store raw normalized embedding vectors. The utility uses `index.reconstruct(old_idx)` to extract the exact 768-dimensional float32 vector for each retained index position, completely avoiding the need to run SPECTER2 inference or recompute embeddings.
- **Index-to-Metadata Preservation:** `retained_indices` preserves the deterministic order `[i for i, pid in enumerate(id_map) if pid not in orphans]`. Vector `new_idx` is mapped from `old_idx`, and `retained_pids` is indexed from `id_map[old_idx]`. Vector position `i` in the newly constructed `IndexFlatIP` matches position `i` in `retained_pids` exactly.
- **Staging and Atomic Renaming:** Staging writes to unique temporary files (`research_index.faiss.tmp.{uid}` and `papers_meta.json.tmp.{uid}`). Files are read back and validated (`ntotal == 162`, `d == 768`, `len(id_map) == 162`) prior to issuing `os.replace`, guaranteeing POSIX filesystem atomicity.

---

## 3. Phase 2 — Verified Initial State & Safety Invariants

All 7 mandated safety invariants were inspected directly against the live PostgreSQL database and active FAISS filesystem artifacts.

| # | Safety Invariant | Expected Condition | Verified State | Status |
| :---: | :--- | :--- | :--- | :---: |
| **1** | PostgreSQL Paper Count | Exactly 162 papers | **162 papers** (`SELECT count(*) FROM papers;` = 162; unique `paper_id` = 162) | **PASSED** |
| **2** | FAISS Vector Count | Exactly 163 vectors | **163 vectors** (`index.ntotal` = 163, `id_map` count = 163, `metadata` dict count = 163) | **PASSED** |
| **3** | Sole Target Orphan Isolation | `test:t15:cand_ext` is the only orphan with zero DB references | **Zero DB references:** `papers` = 0, `saved_papers` = 0, `driut_alerts` = 0, `paper_evidence` = 0. Set difference `faiss_pids - db_pids = ['test:t15:cand_ext']` (len = 1) | **PASSED** |
| **4** | Target Position & Metadata | Target unique in metadata at index 10 | `id_map.index("test:t15:cand_ext")` = **10**. Target frequency in `id_map` = **1**. Present in `metadata` dictionary. | **PASSED** |
| **5** | DB Paper Coverage | All 162 DB papers present in FAISS | All 162 PostgreSQL `paper_id` values exist in `id_map` and `metadata`. Set difference `db_pids - faiss_pids` = `[]` (0 unindexed). | **PASSED** |
| **6** | Vector Alignment & Norms | No missing, duplicate, or corrupted vectors | Exactly 163 reconstructible vectors in active index. Zero NaNs, zero Infs, all float32, all L2 norms $\in [0.9999, 1.0001]$. Zero duplicate IDs. | **PASSED** |
| **7** | Index Format & Dimension | Dimension 768, Inner Product preserved | `d = 768`, `metric_type = 0` (`METRIC_INNER_PRODUCT` / `IndexFlatIP`). JSON schema `{"id_map": [...], "metadata": {...}}` verified. | **PASSED** |

### Orphan Metadata Inspection
```json
{
  "paper_id": "test:t15:cand_ext",
  "title": "Scaling Transformer Language Models on GLUE",
  "abstract": "We extend and build upon transformer language representations on GLUE benchmark, adapting models to cross-modal tasks.",
  "authors": [],
  "venue": "",
  "year": null,
  "doi": null,
  "url": null,
  "pdf_url": null,
  "source": "academic",
  "citation_count": 0,
  "categories": []
}
```
*Origin Analysis:* Injected during historical Task 15/16 candidate testing prior to strict test fixture isolation. Confirmed non-production artifact with no bibliographic citation or database backing.

---

## 4. Phase 3 — Backup and Rollback Assessment

### Permission & Directory Feasibility Check
- **User Environment:** `uid=1000(tonystark)`, `gid=1000(tonystark)`.
- **Target Path Tested:** `/var/backups/researchlens/faiss_pre_reconcile`.
- **Inspection Result:** 
  - Directory `/var/backups` **does not exist** on this system (Fedora Linux).
  - Parent directory `/var` is owned by `root:root` with permissions `0755` (`drwxr-xr-x`).
  - Executing user `tonystark` lacks write permissions to `/var` and cannot create `/var/backups` without `sudo`.
  - In accordance with security instructions ("Do not weaken permissions or use broad privilege escalation to force access"), `/var/backups` is **ineligible** for direct unprivileged execution.

### Pre-Execution Verified Backup
An immutable pre-execution backup was created in the user-owned repository backups directory:
- **Backup Directory:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backups/faiss_pre_reconcile_20261018_234205`
- **Ownership / Permissions:** `tonystark:tonystark` (0755)

#### Checksum & Size Verification
| Artifact | Active Path | Backup Path | File Size | SHA-256 Digest | Match |
| :--- | :--- | :--- | :---: | :--- | :---: |
| **FAISS Index** | `backend/data/processed/faiss/research_index.faiss` | `backups/faiss_pre_reconcile_20261018_234205/research_index.faiss` | 500,781 B | `19fbb3c21e69c02ad060f272b7367ca23f3cb57f4fc28619c1854a0cc0a8dda8` | **EXACT** |
| **FAISS Metadata** | `backend/data/processed/faiss/papers_meta.json` | `backups/faiss_pre_reconcile_20261018_234205/papers_meta.json` | 204,112 B | `6a3b759544d96bf03860f921a43ab23734d2b5eb7cb6745c4b3f0db72b5c4c1e` | **EXACT** |

Checksum file `checksums.sha256` was generated and verified:
```bash
$ sha256sum -c checksums.sha256
research_index.faiss: OK
papers_meta.json: OK
```

### Rollback & Disaster Recovery Procedure
Should any failure or unexpected behavior occur during or after reconciliation, the exact baseline pair can be immediately restored via:

```bash
# Emergency Rollback Procedure (Zero Downtime / Deterministic)
BACKUP_DIR="/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backups/faiss_pre_reconcile_20261018_234205"
FAISS_DIR="/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backend/data/processed/faiss"

# 1. Verify backup file integrity
(cd "$BACKUP_DIR" && sha256sum -c checksums.sha256)

# 2. Restore paired files atomically
cp -p "${BACKUP_DIR}/research_index.faiss" "${FAISS_DIR}/research_index.faiss.tmp"
cp -p "${BACKUP_DIR}/papers_meta.json" "${FAISS_DIR}/papers_meta.json.tmp"
mv -f "${FAISS_DIR}/research_index.faiss.tmp" "${FAISS_DIR}/research_index.faiss"
mv -f "${FAISS_DIR}/papers_meta.json.tmp" "${FAISS_DIR}/papers_meta.json"

# 3. Verify restored active files match preflight hashes
sha256sum "${FAISS_DIR}/research_index.faiss" "${FAISS_DIR}/papers_meta.json"
```

---

## 5. Phase 4 — Dry-Run Execution Results

The dry-run diagnostic was executed using the project virtual environment:

```bash
./backend/venv/bin/python scripts/reconcile_faiss_postgres.py --dry-run
```

### Captured Console Output
```text
================================================================================
RESEARCHLENS — FAISS & POSTGRESQL RECONCILIATION & INTEGRITY TOOL
================================================================================
Database URL: localhost:5432/research_papers
FAISS Directory: /home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backend/data/processed/faiss
Mode: DRY-RUN (READ-ONLY)

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

[DRY RUN COMPLETE] Zero modifications made to PostgreSQL or FAISS index.
To safely repair during an approved maintenance window:
  python scripts/reconcile_faiss_postgres.py --execute --backup-dir /path/to/backup
```

### Dry-Run Assessment
- Confirms exactly **1 orphan** (`test:t15:cand_ext`).
- Confirms **0 unindexed** papers in PostgreSQL.
- Confirms that running the utility without `--execute` produces zero file writes or database queries beyond a single `SELECT`.

---

## 6. Execution Impact Analysis

When approved execution is triggered via:
```bash
./backend/venv/bin/python scripts/reconcile_faiss_postgres.py \
  --execute \
  --backup-dir ./backups/faiss_pre_reconcile_20261018_234205
```

### Expected State Changes
1. **`research_index.faiss`:**
   - Vector count drops from **163 to 162**.
   - Dimension remains **768**.
   - Metric remains **`METRIC_INNER_PRODUCT`** (`IndexFlatIP`).
   - File size will reduce by exactly one 768-float32 vector block plus FAISS header delta (~3,072 bytes).
2. **`papers_meta.json`:**
   - `id_map` length drops from **163 to 162**.
   - `metadata` dictionary keys drop from **163 to 162**.
   - Key `"test:t15:cand_ext"` is purged; all other 162 metadata records remain untouched.
3. **PostgreSQL Database:**
   - **0 modifications.** Table `papers` remains at 162 rows.
4. **Application Consistency:**
   - `get_index_consistency_status()` will transition from `is_consistent: False` to `is_consistent: True`.
   - `orphaned_metadata_count` drops from 1 to 0.

### Operational Notice on Running Backend Services
The backend uvicorn service is actively running on `127.0.0.1:8000` (PID 80975 / 30747). The backend caches the FAISS index instance in memory (`_FAISS_INDEX_INSTANCE`). Following execution, the backend service should be restarted (or reloaded) so that the in-memory singleton loads the new 162-vector index from disk.

---

## 7. Explicit Confirmation of Immutability

It is explicitly confirmed that during this pre-execution safety gate audit:
- **No FAISS index files** (`research_index.faiss`) were modified or overwritten.
- **No metadata files** (`papers_meta.json`) were altered or updated.
- **No PostgreSQL database tables or records** were inserted, updated, deleted, or truncated.
- **No user accounts or security tokens** were changed.
- **No embeddings** were recomputed or regenerated.

---

## 8. Final Gate Status

```
READY FOR EXPLICIT EXECUTION APPROVAL
```

*(Prerequisite Note: Approved execution must supply a user-writable directory path such as `./backups/faiss_pre_reconcile_20261018_234205` rather than root-owned `/var/backups`.)*
