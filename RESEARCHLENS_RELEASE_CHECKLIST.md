# ResearchLens — Production Release & Go/No-Go Acceptance Checklist

**Document ID:** `RESEARCHLENS_RELEASE_CHECKLIST.md`  
**Target Release:** v1.0.0-rc1  
**Evaluation Date:** October 18, 2026  
**Final Release Decision:** **`CONDITIONALLY READY`**

---

## 1. Release Approval Gates

| Gate # | Quality & Verification Gate | Acceptance Criteria | Current Result | Gate Status |
|:---:|:---|:---|:---:|:---:|
| **Gate 1** | **Backend Regression Testing** | 100% test pass rate across all unit and integration test suites | 328 passed, 0 failed (145.59s) | **PASSED** |
| **Gate 2** | **Frontend Regression Testing** | 100% test pass rate across all component and service test suites | 66 passed, 0 failed (8 suites) | **PASSED** |
| **Gate 3** | **Production Compilation** | Clean TypeScript compilation and asset bundling with zero errors | `tsc -b && vite build` (692ms) | **PASSED** |
| **Gate 4** | **Publication-Year Semantics** | PubMed parser distinguishes electronic availability from future print issues | `parse_pubmed_dates` verified; 26 records evaluated | **PASSED** |
| **Gate 5** | **Historical Database State** | Live database preserved without unreviewed or unbacked-up mutation | Zero live database mutations executed | **PENDING MAINT.** |
| **Gate 6** | **DRIUT Chronological Integrity** | Chronology guard prevents older papers from being labeled improvements of newer papers | Step 8b chronology guard verified | **PASSED** |
| **Gate 7** | **Search Relevance & Out-of-Domain Suppression** | Empirical threshold suppresses semantically irrelevant queries | "ancient Roman architecture" returns 0 results | **PASSED** |
| **Gate 8** | **Synthetic Placeholder Abstract Guards** | Placeholder boilerplate abstracts are never treated as scientific evidence | `SYNTHETIC_PLACEHOLDER_REGEX` and guards verified | **PASSED** |
| **Gate 9** | **Vector Store Consistency** | FAISS index, metadata, and database alignment verified; orphan isolated | Read-only tool created; orphan `test:t15:cand_ext` isolated | **PENDING MAINT.** |
| **Gate 10** | **Cloud Privacy Controls** | Cloud AI transmission remains disabled by default | `RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT=false` | **PASSED** |
| **Gate 11** | **Authentication & Isolation** | Cryptographic token signing and cross-user library isolation | HS256, >=32 char secret, user isolation verified | **PASSED** |
| **Gate 12** | **Deployment Configuration** | Multi-worker Gunicorn/Uvicorn, systemd, and Nginx reverse proxy documented | Production deployment guide and configs ready | **PASSED** |

---

## 2. Pre-Deployment Verification Protocol

Before initiating traffic redirection to the production cluster, release engineers must complete each item:

### 2.1 Code & Environment Verification
- [x] Git working tree state recorded; no uncommitted changes discarded.
- [x] Environment files verified: root and backend `.env` files aligned.
- [x] High-entropy `JWT_SECRET_KEY` (minimum 32 characters) configured in production environment.
- [x] `RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT=false` confirmed in production config.
- [x] Local Ollama service active on `http://127.0.0.1:11434` with model `qwen2.5:3b` pulled.

### 2.2 Functional & NLP Verification
- [x] Execute backend test suite:
  ```bash
  ./backend/venv/bin/pytest backend/tests/
  # Expected: 328 passed, 0 failed
  ```
- [x] Execute targeted remediation tests:
  ```bash
  ./backend/venv/bin/pytest backend/tests/test_targeted_remediations.py
  # Expected: 23 passed, 0 failed
  ```
- [x] Execute frontend tests:
  ```bash
  cd frontend && npm test -- --run
  # Expected: 66 passed, 0 failed
  ```
- [x] Execute production frontend build:
  ```bash
  cd frontend && npm run build
  # Expected: Clean build with zero TypeScript errors
  ```
- [x] Verify live search relevance:
  - Query `"ancient Roman architecture"` returns 0 results.
  - Query `"AI and machine learning"` returns conceptually relevant papers with scores >= 0.84.

### 2.3 Data Integrity & Backup Verification
- [x] Run read-only FAISS/DB diagnostic:
  ```bash
  ./backend/venv/bin/python scripts/reconcile_faiss_postgres.py
  # Verify 162 DB papers, 163 FAISS vectors, 1 orphan identified
  ```
- [ ] Create pre-deployment PostgreSQL database dump:
  ```bash
  podman exec -t postgres_container pg_dump -U postgres research_papers > /backups/postgres_pre_release.sql
  ```
- [ ] Create cold snapshot of FAISS vector directory:
  ```bash
  cp -rp backend/data/processed/faiss /backups/faiss_pre_release
  ```

---

## 3. Maintenance Window Operations (Scheduled)

The following two operations are scheduled for execution during the authorized maintenance window:

1. **FAISS Index Orphan Reconciliation:**
   - Command:
     ```bash
     ./backend/venv/bin/python scripts/reconcile_faiss_postgres.py --execute --backup-dir /backups/faiss_pre_reconcile
     ```
   - Target Outcome: FAISS vector count reduces from 163 to 162, exactly matching PostgreSQL.

2. **Historical PubMed Date Correction:**
   - Execute approved SQL migration updating 25 records with `year = 2027` to `year = 2026` based on validated `epubdate`.
   - Leave `pubmed:42635983` at `year = 2028` (verified authentic upstream scheduled release).

---

## 4. Final Go/No-Go Decision

### Sign-Off Assessment
- **Code Readiness:** 100% COMPLETE. All verified defects, date parsing, DRIUT chronology, search relevance floors, synthetic placeholder abstract filters, and security isolation are implemented and tested.
- **Operational Data Invariants:** 100% MAINTAINED. Zero unauthorized live database mutations or FAISS overwrites occurred.
- **Pending Maintenance:** Historical database records and the single FAISS test orphan await execution during the scheduled maintenance window.

### Official Release Status
```
================================================================================
RELEASE DECISION: CONDITIONALLY READY
================================================================================
```
**Condition:** System is authorized for deployment to staging and controlled production release. Full general availability (GA) sign-off will occur upon completion of the scheduled database and FAISS reconciliation maintenance window.
