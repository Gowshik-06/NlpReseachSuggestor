# ResearchLens — DRIUT Historical Chronology Remediation Execution Report

**Document ID:** `RESEARCHLENS-EXEC-DRIUT-REMEDIATION-20261020`  
**Execution Timestamp:** 2026-10-20T21:11:23+05:30 (15:41:23 UTC)  
**Execution Authorization:** User Explicit Authorization  
**Repository Root:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Remediation Utility:** [`scripts/remediate_driut_chronology.py`](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/scripts/remediate_driut_chronology.py)  
**Verified Backup Artifact:** `backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz`  
**Backup SHA-256 Checksum:** `4daec4d3737d89c7596b859a839847e39312ae19dff3b41e046b9803ecce806a`

---

## 1. Executive Summary & Operation Overview

On October 20, 2026, the approved historical DRIUT chronology remediation was executed against the live PostgreSQL database (`research_papers`). Exactly **90 historical invalid alert rows** violating directional temporal domain semantics ($\text{Year}_{\text{candidate}} < \text{Year}_{\text{baseline}}$) were permanently purged in a single atomic database transaction.

### Final Execution Highlights:
- **Transaction Outcome:** Succeeded with exit status `0`.
- **Pre-Execution Alerts Count:** Exactly **175 alerts** in PostgreSQL.
- **Affected Rows:** Exactly **90 rows deleted** inside the atomic transaction (`deleted_rows == 90`).
- **Post-Execution Alerts Count:** Exactly **85 alerts** remaining in PostgreSQL (75 valid same-year 2026 alerts + 10 exempt non-directional `Alternative` alerts).
- **Deleted Allowlist IDs:** 100% absent from live PostgreSQL and API responses.
- **Unrelated Tables Unchanged:**
  - `papers`: Exactly **162 rows** (unchanged).
  - `users`: Exactly **7 rows** (unchanged).
  - `saved_papers`: Exactly **5 rows** (unchanged).
  - `paper_evidence`: Exactly **3 rows** (unchanged).
- **FAISS Vector Index & Metadata:** Exactly **162 vectors** and **162 metadata entries** (unchanged).
- **Live HTTP API Verification:** `GET /api/v1/papers/driut/alerts` returned HTTP 200 OK with exactly 68 alerts for `admin` and 17 alerts for `testuser_task10` ($68 + 17 = 85$), with zero deleted IDs present.
- **Automated Test Verification:** **38 non-destructive DRIUT tests passed** with zero failures.

---

## 2. Pre-Execution Backup & Integrity Verification

Before the execution command was issued, the pre-remediation backup artifact was verified:
- **Backup File:** `backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz`
- **File Size:** 316,424 bytes uncompressed / 48,912 bytes compressed
- **Dump Completion Signature:** `"PostgreSQL database dump complete"` verified.
- **SHA-256 Checksum:** `4daec4d3737d89c7596b859a839847e39312ae19dff3b41e046b9803ecce806a` (matched approved hash exactly).
- **Prior Isolated Restore Verification:** Restored successfully into `restore_verify_20261020_200607` with identical record counts (162 papers, 7 users, 5 saved papers, 175 alerts, 3 evidence spans) prior to test database teardown.
- **Preservation Status:** Backup artifact preserved untouched in `backups/pg_20261020_200607/`.

---

## 3. Exact Execution Command & Output

The remediation utility was invoked using the exact documented virtual-environment binary and verified backup argument:

```bash
./backend/venv/bin/python scripts/remediate_driut_chronology.py \
  --execute \
  --backup-file backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz
```

### Complete Command Standard Output & JSON Payload:
```text
================================================================================
 ResearchLens — Safe DRIUT Chronology Remediation Utility
================================================================================
Mode: EXECUTE (DELETION ENABLED)
Ledger: /home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json
Backup File: backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz
[PREFLIGHT] Verifying database state against allowlist...
[PREFLIGHT OK] Total alerts: 175 (90 invalid, 75 valid, 10 exempt).
[TRANSACTION] Beginning atomic deletion transaction...
[TRANSACTION COMMITTED] Exactly 90 invalid alerts deleted. 85 compliant alerts remain.

Result Summary:
{
  "timestamp": "2026-10-20T15:41:23.020541+00:00",
  "ledger_path": "/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json",
  "backup_file": "backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz",
  "backup_sha256": "4daec4d3737d89c7596b859a839847e39312ae19dff3b41e046b9803ecce806a",
  "mode": "EXECUTE",
  "allowlist_count": 90,
  "status": "SUCCESS_COMMITTED",
  "pre_counts": {
    "total_alerts": 175,
    "papers": 162,
    "users": 7,
    "saved_papers": 5,
    "paper_evidence": 3
  },
  "deleted_rows": 90,
  "post_counts": {
    "total_alerts": 85,
    "papers": 162,
    "users": 7,
    "saved_papers": 5,
    "paper_evidence": 3
  }
}
```
**Exit Status Code:** `0` (Success).

---

## 4. Deleted Allowlist Ledger (Exact 90 Alert IDs Purged)

The 90 deleted rows matched the verified allowlist from [`RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json`](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json):

```text
631, 632, 633, 634, 635, 636, 637, 638, 639, 665, 
669, 753, 756, 757, 1101, 1132, 1312, 1313, 1314, 1316, 
1317, 1318, 1319, 1320, 1321, 1322, 1323, 1324, 1329, 1331, 
1332, 1333, 1343, 1344, 1345, 1346, 1347, 1348, 1349, 1350, 
1351, 1352, 1353, 1354, 1359, 1361, 1362, 1363, 1369, 1375, 
1376, 1377, 1378, 1379, 1380, 1381, 1382, 1383, 1384, 1385, 
1386, 1391, 1393, 1394, 1395, 1406, 1407, 1408, 1409, 1410, 
1411, 1412, 1413, 1414, 1415, 1416, 1417, 1422, 1424, 1425, 
1426, 1432, 1435, 1436, 1439, 1442, 1443, 1446, 1447, 1448
```

### Breakdown of Deleted Records:
- **By Category:**
  - `Improvement`: 65 rows deleted
  - `Extension`: 25 rows deleted
- **By User:**
  - `admin`: 72 rows deleted across 4 saved baseline papers (71, 67, 72, 307)
  - `testuser_task10`: 18 rows deleted on saved baseline paper 71
- **By Candidate Year:** All 90 rows involved candidate papers published between 2018 and 2025 claiming to extend or improve 2026 baseline papers.

---

## 5. Independent Post-Execution Database & Vector Verification

An independent Python verification script queried the live PostgreSQL database and FAISS index immediately following execution:

```python
# Verification query results:
driut_alerts = 85
papers = 162
users = 7
saved_papers = 5
paper_evidence = 3
faiss_vectors = 162
faiss_meta_entries = 162
```

### Invariant Checks Verified:
1. **Allowlist Non-Existence:** Confirmed that `allowlist_ids.intersection(remaining_ids) == set()`. Zero allowlisted IDs exist in the live database.
2. **Remaining Alerts Compliance:** Exactly **85 alerts** remain:
   - **`VALID` (75 alerts):** Same-year 2026 candidates evaluating 2026 baseline papers (`Improvement`: 40, `Extension`: 25, `Challenge`: 5, `Reproduction`: 5). Compliant under the Step 8b equal-year policy.
   - **`EXEMPT` (10 alerts):** `Alternative` paradigm alerts. Non-directional relationship category; exempt from directional temporal precedence.
   - **`INVALID` (0 alerts):** Zero residual chronology violations exist in the database.
3. **Database Integrity:** Zero changes occurred in `papers`, `users`, `saved_papers`, or `paper_evidence`.
4. **Vector Consistency:** The binary FAISS index (`research_index.faiss`) and ID mapping file (`papers_meta.json`) remain at exactly 162 entries, matching PostgreSQL `papers` 1:1:1.

---

## 6. Live API Endpoint Verification (`GET /api/v1/papers/driut/alerts`)

The live API endpoint was verified via HTTP requests using authenticated JWT Bearer tokens:
- **Unauthenticated Access (`GET /api/v1/papers/driut/alerts`):** Correctly rejected with HTTP 401 Unauthorized (`Authentication required`).
- **Authenticated `admin` Account:** Responded HTTP 200 OK with exactly **68 alerts** (previously 140).
- **Authenticated `testuser_task10` Account:** Responded HTTP 200 OK with exactly **17 alerts** (previously 35).
- **Total Alerts Exposed via API:** $68 + 17 = \mathbf{85}$ alerts.
- **Absence of Purged IDs:** Programmatically asserted that none of the 90 allowlisted IDs appear in API payloads.

---

## 7. Automated Non-Destructive Test Suite Results

Relevant, confirmed non-destructive DRIUT test suites were executed to verify recurrence prevention and scheduler stability:

### 1. Chronology Policy & Edge-Case Tests (`test_targeted_remediations.py`)
```bash
./backend/venv/bin/pytest backend/tests/test_targeted_remediations.py -k "driut" -v
```
**Results:** **7 passed, 17 deselected, 1 warning in 10.40s (100% pass rate)**
- `test_driut_effective_publication_year_extraction` — **PASSED**
- `test_driut_chronology_later_improves_earlier` — **PASSED**
- `test_driut_chronology_earlier_cannot_improve_later` — **PASSED**
- `test_driut_chronology_equal_publication_years` — **PASSED**
- `test_driut_chronology_missing_dates_handled` — **PASSED**
- `test_driut_chronology_advance_print_issue_preserves_valid_relationship` — **PASSED**
- `test_driut_legitimate_alternative_classification` — **PASSED**

### 2. DRIUT Background Scheduler & Lock Tests (`test_driut_scheduler.py`)
```bash
./backend/venv/bin/pytest backend/tests/test_driut_scheduler.py -v
```
**Results:** **16 passed, 2 warnings in 13.33s (100% pass rate)**
- Lifecycle, advisory locks ($7376232$), concurrency, and provider tolerance all verified.

### 3. DRIUT Relationship Intelligence Tests (`test_driut_intelligence.py`)
```bash
./backend/venv/bin/pytest backend/tests/test_driut_intelligence.py -v
```
**Results:** **15 passed, 2 warnings in 9.64s (100% pass rate)**
- 6 taxonomy categories, disparate metric protections, and evidence passage grounding verified.

**Total Tests Verified:** **38 passed, 0 failed.**

---

## 8. Artifact & Data Preservation Confirmation

The following repository artifacts were explicitly preserved and remain untouched:
1. `backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz` (Verified pre-remediation backup).
2. `RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json` (Machine-readable audit ledger of all 175 historical alerts).
3. `RESEARCHLENS_DRIUT_HISTORICAL_CHRONOLOGY_AUDIT.md` (Initial audit report).
4. `RESEARCHLENS_DRIUT_DELETION_PREFLIGHT.md` (Preflight safety gate report).
5. `RESEARCHLENS_COMPLETE_PROJECT_DOSSIER_FOR_PPTX.md` (Project dossier for presentation).
6. `RESEARCHLENS_PPTX_EVIDENCE_INDEX.md` (Presentation evidence index).
7. `backend/data/processed/faiss/research_index.faiss` and `papers_meta.json` (162 vectors, untouched).

---

## 9. Final Execution Verdict

```
REMEDIATION SUCCESSFUL — ALL POSTCONDITIONS VERIFIED
```

### Sign-off Details:
- **Historical Chronology Violations Remediated:** 90
- **Compliant Alerts Preserved:** 85
- **Pre-execution Alert Count:** 175
- **Post-execution Alert Count:** 85
- **Unrelated Entity Row Counts:** Papers (162), Users (7), Saved Papers (5), Evidence (3) — All 100% Identical.
- **Recurrence Protection:** Step 8b Chronology Guard active and passing all tests.
- **Database & Services Status:** PostgreSQL healthy; FastAPI backend running; React frontend operational.
