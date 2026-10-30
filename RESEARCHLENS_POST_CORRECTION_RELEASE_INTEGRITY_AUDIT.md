# ResearchLens — Post-Correction Read-Only Release Integrity Audit

**Document ID:** `RESEARCHLENS_POST_CORRECTION_RELEASE_INTEGRITY_AUDIT.md`  
**Audit Timestamp:** October 18, 2026  
**Auditor:** Senior Software Architect, Security & Release Engineer  
**Audit Scope:** Independent Read-Only Integrity Verification of PubMed Year Correction, PostgreSQL/FAISS Consistency, DRIUT Chronology, and Release Blockers  
**Final Verdict:** **`READ-ONLY AUDIT PASSED — READY FOR TARGETED REMEDIATION`**

---

## 1. Executive Summary & Audit Mandate

In strict accordance with the read-only audit charter:
- **Zero persistent database records, FAISS files, metadata entries, user accounts, or environment configurations were modified during this audit.**
- **Zero destructive commands, cleanup utilities, migrations, or reconciliation scripts were executed.**
- **Zero credentials, secrets, tokens, or plaintext passwords are exposed in this report.**
- **Claims are rigorously categorized into (A) Independently Verified Facts, (B) Report-Only Supported Claims, and (C) Unverified Claims.**

---

## 2. Evidence Categorization Matrix

| Category | Description | Scope in this Audit |
|:---|:---|:---|
| **Category A: Independently Verified Facts** | Directly inspected via live read-only system queries, filesystem cryptographic hashes, active process probes, or live API responses. | Live PostgreSQL record counts (162), year distributions (25 updated to 2026, 1 at 2028), FAISS `research_index.faiss` SHA-256 match, `papers_meta.json` years (2026), backup archive existence and SHA-256 checksum match, live backend API response, remaining DRIUT chronology count (90). |
| **Category B: Report-Only Supported Claims** | Documented in prior execution logs and runbooks, plausible and consistent, but not re-executed during this audit to prevent system mutation. | The execution of the isolated database restoration test inside container `research-paper-recommender-postgres-1` (recorded in `scripts/verify_backup_restore.py` log and `RESEARCHLENS_PUBMED_YEAR_CORRECTION_REPORT.md`). |
| **Category C: Unverified Claims** | External dependencies or operational assertions outside the workspace boundary. | Production domain DNS routing, external public TLS certificate issuance, and production-grade hardware cluster provisioning. |

---

## 3. Task 1: Verification of PubMed Year Correction

### 3.1 Live Database Inspection (PostgreSQL)
A read-only query was executed against `research-paper-recommender-postgres-1` via SQLAlchemy connection:

```sql
SELECT year, count(*) FROM papers GROUP BY year ORDER BY year DESC;
```

**Empirical Results:**
1. **Total Catalog Papers:** Exactly **162** (Unchanged; zero papers added or deleted).
2. **Target Allowlist PMIDs (25 Records):** All **25 approved records** (`pubmed:42431082`, `pubmed:42630760`, etc.) now possess `year = 2026`. Querying `WHERE paper_id IN (:target_25) AND year != 2026` returned **0 rows**.
3. **Preserved Forthcoming Record (`pubmed:42635983`):** Verified at ID 107 with `year = 2028`, journal *J Cogn Neurosci*. Both upstream `epubdate` and `pubdate` confirm authentic 2028 availability.
4. **Other Future Records:** Querying `WHERE year >= 2027 AND paper_id != 'pubmed:42635983'` returned **0 rows**.
5. **Complete Catalog Year Distribution (162 Total):**
   - 2028: **1** (`pubmed:42635983`)
   - 2026: **72** (previously 47; increased by exactly 25)
   - 2025: **18**
   - 2024: **11**
   - 2023: **9**
   - 2022: **10**
   - 2021: **7**
   - 2020: **11**
   - 2019: **3**
   - 2018: **3**
   - 2017: **1**
   - 2014: **2**
   - 2012: **1**
   - 2011: **1**
   - 1988: **1**
   - `None`: **11**
   - *Sum:* $1 + 72 + 18 + 11 + 9 + 10 + 7 + 11 + 3 + 3 + 1 + 2 + 1 + 1 + 1 + 11 = 162$.
   - **Conclusion:** Zero unrelated papers were modified.

### 3.2 Parser Resilience & Dynamic UTC Year Policy
Inspection of `backend/app/services/academic_sources.py` confirmed:
- `parse_pubmed_dates` defaults `reference_year` to `datetime.now(timezone.utc).year` when unspecified, removing the previous hardcoded ceiling of 2026.
- In 2027, advance articles with print in 2028 evaluate to `ahead_of_print`, while standard 2027 articles evaluate to `published`.
- `search_pubmed` passes `reference_year=reference_year` downstream.
- Regression suite `backend/tests/test_targeted_remediations.py` passes all transition scenarios.

### 3.3 Live Backend Search Endpoint Verification
Querying `POST /api/v1/papers/search` for `"knowledge tracing framework"` returned:
- Paper ID 71 (`pubmed:42431082`): Returned with `year: 2026` and badge `✨ 2026 Latest Breakthrough`.
- Paper ID 306 (`pubmed:42502841`): Returned with `year: 2026`.
- Scheduled print dates remain preserved in venue strings: `(2027 Jan)`.

---

## 4. Task 2: PostgreSQL Backup & Restore Verification

### 4.1 Backup Artifact Cryptographic Verification
Read-only inspection of the filesystem confirmed:
- **Backup File:** `backups/pg_20261018_230610/research_papers_20261018_230610.sql.gz`
- **File Size:** **65,161 bytes** (compressed from 316,424 bytes uncompressed SQL).
- **Checksum Verification:**
  ```bash
  $ cd backups/pg_20261018_230610 && sha256sum -c research_papers_20261018_230610.sql.gz.sha256
  research_papers_20261018_230610.sql.gz: OK
  ```
  Verified SHA-256: `b255b4ffbc3c56d3ad0b836a97dc019170829580e7250c0efbbaee50ac87192d`.
- **Gzip Stream Validation:** `gzip -t` completed with exit code 0, verifying archive structural integrity without decompression.

### 4.2 Independent Verification Status of Restore Claims
- **Independently Verified:** Backup artifact existence, file size, gzip integrity, and SHA-256 cryptographic match.
- **Report-Supported (Not Re-executed):** The isolated database restoration test into container test database `restore_verify_20261018_230610` was executed and logged in Step B of the prior migration run. It was **deliberately not re-executed** during this audit to adhere to the zero-mutation restriction.

---

## 5. Task 3: FAISS Vector Store Integrity Audit

### 5.1 File Timestamps and Cryptographic Hashes
Read-only inspection of `backend/data/processed/faiss/`:

| File | Timestamp | SHA-256 Checksum | Invariant Status |
|:---|:---:|:---|:---:|
| `research_index.faiss` | **Oct 12 15:13** | `19fbb3c21e69c02ad060f272b7367ca23f3cb57f4fc28619c1854a0cc0a8dda8` | **UNTOUCHED (100% Intact)** |
| `papers_meta.json` | **Oct 18 23:08** | `6a3b759544d96bf03860f921a43ab23734d2b5eb7cb6745c4b3f0db72b5c4c1e` | **Synchronized (Metadata Only)** |

**Critical Audit Finding:** The vector index file (`research_index.faiss`) has a modification timestamp of October 12, 2026 and an identical SHA-256 hash to the pre-migration baseline. This proves that **zero vector recalculations or index rebuilds occurred**. Only metadata attributes (`year`) were synchronized.

### 5.2 Vector Count & Identifier Mapping
- **FAISS Vectors (`index.ntotal`):** **163**
- **FAISS Dimension (`index.d`):** **768** (`float32`)
- **Metric Type:** `0` (`INNER_PRODUCT`)
- **`id_map` Entries:** **163** (163 unique strings; **0 duplicate IDs**)
- **`metadata` Dictionary Entries:** **163**
- **Orphan Vector Analysis:**
  - Exactly **1 orphan vector** in FAISS: `test:t15:cand_ext` (index position 10 in `id_map`).
  - Present in FAISS: Yes (`test:t15:cand_ext`).
  - Present in PostgreSQL: **No** (0 records).
  - Referenced in PostgreSQL tables (`saved_papers`, `driut_alerts`, `paper_evidence`): **0 references**.
  - Unindexed papers (in PostgreSQL but absent from FAISS): **0**.
  - All 162 PostgreSQL catalog papers are indexed in FAISS.
- **Target 25 Metadata Records:** All 25 records in `papers_meta.json` have `"year": 2026`.
- **Protected Record in Metadata:** `pubmed:42635983` has `"year": 2028`.

---

## 6. Task 4: DRIUT Chronology Verification

### 6.1 Chronology Guard Implementation (`driut_service.py`)
Step 8b in `backend/app/services/driut_service.py` was inspected:
- Evaluates `extract_effective_publication_year(new_paper)` and `extract_effective_publication_year(saved_paper)`.
- If `new_year < saved_year`, directional categories (`Improvement`, `Extension`, `Potential Replacement`, `Challenge`, `Reproduction`) are strictly rejected with:
  > *"Chronological conflict: candidate paper ({new_note}) precedes baseline paper ({saved_note}). An earlier publication cannot establish an {chosen_cat} of a subsequent work."*
- Regression tests in `test_driut_intelligence.py` confirm the guard functions as expected.

### 6.2 Recalculation of Historical Chronology Violations
A read-only SQL query audited all 175 alerts in `driut_alerts`:

```sql
SELECT count(*) 
FROM driut_alerts a
JOIN papers p_saved ON a.saved_paper_id = p_saved.id
JOIN papers p_trigger ON a.trigger_paper_id = p_trigger.id
WHERE p_trigger.year < p_saved.year;
```

**Empirical Results:**
- **Pre-Correction Violations:** **141 alerts (80.6%)**
- **Post-Correction Violations:** **90 alerts (51.4%)**
- **Change:** **51 chronology violations automatically cleared** because saved papers ID 71 and ID 307 are now accurately recorded as 2026 publications in PostgreSQL.
- **Remaining 90 Violations:**
  - `Improvement`: **65 alerts**
  - `Extension`: **25 alerts**
  - Affected saved baselines:
    - Saved Paper ID 71 (`pubmed:42431082`, Year 2026): **36 alerts** (triggered by papers from 2018–2025)
    - Saved Paper ID 67 (`arxiv:2609.35768v1`, Year 2026): **18 alerts** (triggered by papers from 2020–2021)
    - Saved Paper ID 72 (`pubmed:42659950`, Year 2026): **18 alerts** (triggered by papers from 2020–2021)
    - Saved Paper ID 307 (`pubmed:42520721`, Year 2026): **18 alerts** (triggered by papers from 2018–2025)
- **Status:** These 90 alerts are legacy records generated prior to the Step 8b Chronology Guard. They remain preserved for historical auditability and require a separate approved remediation procedure.

---

## 7. Task 5: Security & Deployment Blocker Review

| Security & Ops Domain | Inspected Implementation | Current Status | Risk / Blocker Assessment |
|:---|:---|:---:|:---|
| **JWT Signing Secret** | `backend/app/core/config.py` validator | **SAFEGUARDED** | Config rejects weak/default secrets in production. A cryptographically random secret must be provisioned in `/opt/researchlens/backend/.env`. |
| **Authentication Boundaries** | `backend/app/api/deps.py`, `auth.py` | **SECURE** | Password salting with Argon2/Bcrypt; tenant library isolation verified. |
| **Cloud AI Privacy Fence** | `backend/app/services/ai_provider.py` | **SECURE** | `RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT=false` enforced. Cloud transmission completely disabled. |
| **Local AI Daemon** | Ollama on `127.0.0.1:11434` (`qwen2.5:3b`) | **ACTIVE** | Local inference verified with deterministic offline fallbacks. |
| **Database Port Exposure** | `docker-compose.yml` | **SECURE** | Port 5432 bound to `127.0.0.1` (localhost only). |
| **Startup / Shutdown Reliability** | `scripts/dev-start.sh`, `dev-stop.sh` | **VERIFIED** | Idempotent startup; port checks and readiness probes. |
| **Nginx / TLS / DNS** | `frontend/nginx.conf` | **CONFIGURED (PENDING PROVISIONING)** | Nginx config authored. External domain DNS, hosting server, and TLS certs require operational provisioning. |

---

## 8. Task 6: Regression Test Evidence

Fresh test executions confirm full operational stability:

| Test Suite | Tests Run | Result | Notes |
|:---|:---:|:---:|:---|
| **Targeted Remediations** (`test_targeted_remediations.py`) | 24 | **24 passed** | Date policy, transitions, search thresholds verified |
| **DRIUT Intelligence** (`test_driut_intelligence.py`) | 15 | **15 passed** | Step 8b chronology guard verified |
| **DRIUT Scheduler** (`test_driut_scheduler.py`) | 16 | **16 passed** | Isolated scheduler lifecycle verified |
| **Local Search Correctness** (`test_local_search_correctness.py`) | 9 | **9 passed** | Relevance ranking & candidate hydration verified |
| **Frontend Vitest Suite** | 66 | **66 passed** | 8 component suites passed |
| **Frontend Production Build** | 1 | **Clean in 692ms** | `tsc -b && vite build` completed with 0 errors |

---

## 9. Prioritized Production Release Blockers

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        PRIORITIZED PRODUCTION RELEASE BLOCKERS                         │
├────┬───────┬────────────────────────────┬─────────────────────────────┬────────────────┤
│ ID │ Pri.  │ Blocker Title              │ Operational Risk            │ Safest Next    │
│    │       │                            │                             │ Action         │
├────┼───────┼────────────────────────────┼─────────────────────────────┼────────────────┤
│ B1 │ HIGH  │ FAISS Orphan Vector        │ Vector store contains 1     │ Run reconcile  │
│    │       │ (`test:t15:cand_ext`)      │ test vector absent from DB  │ script with bak│
├────┼───────┼────────────────────────────┼─────────────────────────────┼────────────────┤
│ B2 │ MED   │ 90 Historical DRIUT        │ Historical alert log        │ Author separate│
│    │       │ Chronology Violations      │ contains pre-guard alerts   │ audit review   │
├────┼───────┼────────────────────────────┼─────────────────────────────┼────────────────┤
│ B3 │ MED   │ Production JWT Secret      │ Root .env contains dev key  │ Generate 32+   │
│    │       │ Generation                 │ rejected by prod validator  │ char hex secret│
├────┼───────┼────────────────────────────┼─────────────────────────────┼────────────────┤
│ B4 │ LOW   │ Public Nginx TLS & DNS     │ Localhost dev bind only;    │ Provision certs│
│    │       │ Deployment                 │ no public HTTPS endpoint    │ & domain DNS   │
└────┴───────┴────────────────────────────┴─────────────────────────────┴────────────────┘
```

---

## 10. Audit Verdict & Confirmation

```
================================================================================
FINAL VERDICT: READ-ONLY AUDIT PASSED — READY FOR TARGETED REMEDIATION
================================================================================
```

### Invariant Audit Confirmation:
- **Database Records:** Zero records added, deleted, or unapproved. Exactly 25 PubMed records confirmed at year 2026; exactly 1 at year 2028. Total: 162.
- **FAISS Vectors:** Zero vectors modified, deleted, or re-indexed. `research_index.faiss` SHA-256 is 100% identical to baseline.
- **Metadata:** Synchronized accurately.
- **Accounts & Secrets:** Zero accounts created or modified; zero credentials exposed.
- **Infrastructure:** Unaltered.

### Next Recommended Single Action:
Execute the standalone FAISS orphan reconciliation utility in an authorized maintenance window:
```bash
./backend/venv/bin/python scripts/reconcile_faiss_postgres.py --execute --backup-dir /var/backups/researchlens/faiss_pre_reconcile
```
This will safely remove orphan vector `test:t15:cand_ext` (index position 10), reducing FAISS vector count from 163 to 162 and achieving 100% database-vector alignment.
