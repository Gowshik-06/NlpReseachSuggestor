# ResearchLens — DRIUT Historical Alert Deletion: Final Safety Gate & Preflight Audit

**Document ID:** `RESEARCHLENS-PREFLIGHT-DRIUT-DELETION-20261020`  
**Execution Type:** Read-Only Verification & Preflight Safety Audit (Zero Deletions Performed)  
**Date:** October 20, 2026  
**Repository Root:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Database URL:** `postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/research_papers`  
**Verified Backup Artifact:** `backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz`  
**Backup SHA-256:** `4daec4d3737d89c7596b859a839847e39312ae19dff3b41e046b9803ecce806a`

---

## 1. Executive Summary & Verification Purpose

This document establishes the final safety gate prior to any modification of historical DRIUT alert records. A total of **90 historical alert rows** in PostgreSQL violate temporal domain directionality (an earlier paper published in 2018–2025 claiming to "improve" or "extend" a subsequent paper published in 2026). These alerts were generated during initial development scans prior to the introduction of the Step 8b chronology guard.

This preflight audit has verified:
1. **Live Database Baseline:** PostgreSQL currently holds exactly **175 alerts**, **162 papers**, **7 users**, **5 saved papers**, and **3 evidence spans**.
2. **Allowlist Integrity:** All **90 allowlisted IDs** in `RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json` exist in the live database, belong strictly to directional categories (`Improvement`, `Extension`), and have verified publication years where $\text{Year}_{\text{candidate}} < \text{Year}_{\text{saved}}$.
3. **Non-Allowlist Protection:** Exactly **85 alerts** are preserved (75 valid contemporaneous same-year alerts and 10 exempt non-directional `Alternative` alerts). Zero valid alerts are present in the allowlist.
4. **Verified Fresh Backup & Restoration:** A fresh compressed PostgreSQL backup was generated and tested via an isolated test database (`restore_verify_20261020_200607`), verifying 100% record restoration integrity.
5. **Script Safety & Allowlist Enforcement:** `scripts/remediate_driut_chronology.py` operates in read-only dry-run mode by default, requires `--execute` and `--backup-file`, executes inside an atomic database transaction, asserts `deleted_rows == 90`, verifies table integrity, and triggers an immediate rollback on any deviation.
6. **Foreign-Key Dependencies:** Verified that zero foreign keys point to `driut_alerts`. Deletion cannot cascade or mutate other tables.
7. **Zero Current Mutation:** No database records, FAISS files, or application code were modified during this task.

---

## 2. Live Database Counts & Current State Verification

Live read-only queries were executed against the PostgreSQL container `research-paper-recommender-postgres-1` on port 5432:

| Database Table | Live Count | Preflight Requirement | Status | Verification Notes |
| :--- | :---: | :---: | :---: | :--- |
| **`driut_alerts`** | **175** | Exactly 175 | **VERIFIED** | 90 invalid historical alerts + 75 valid same-year + 10 exempt alternatives. |
| **`papers`** | **162** | Exactly 162 | **VERIFIED** | 40 arXiv, 39 PubMed, 37 CSIR, 34 Crossref, 10 S2, 2 Test. Exactly matches FAISS (162 vectors). |
| **`users`** | **7** | Exactly 7 | **VERIFIED** | `admin`, `default_user`, `test_user`, `testuser_task10`, and test accounts. |
| **`saved_papers`** | **5** | Exactly 5 | **VERIFIED** | `testuser_task10` ($1$ paper: 71); `admin` ($4$ papers: 71, 67, 72, 307). All Year 2026. |
| **`paper_evidence`** | **3** | Exactly 3 | **VERIFIED** | Grounded claim spans with verified character offsets. |
| **`FAISS Vectors`** | **162** | Exactly 162 | **VERIFIED** | `research_index.faiss` (768d, FlatIP, Hash: `f5be6e08...`). |

---

## 3. Exact Allowlist Verification (90 Unique Alert IDs)

The machine-readable audit ledger [`RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json`](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json) defines an allowlist of exactly 90 unique alert IDs:

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

### 3.1 Verification Against Live PostgreSQL Records
A programmatic verification script joined each allowlisted row with `papers` on both `saved_paper_id` and `trigger_paper_id`:
1. **Allowlist Presence:** All **90 IDs** exist in `driut_alerts`.
2. **Category Verification:** Every single allowlisted alert belongs strictly to directional categories:
   - **`Improvement`:** 65 alerts
   - **`Extension`:** 25 alerts
   - Zero `Alternative`, zero `Challenge`, zero `Reproduction` alerts are in the allowlist.
3. **Temporal Invariant Verification:** Every allowlisted row has verified effective publication years where:
   $$\text{Year}_{\text{candidate}} < \text{Year}_{\text{baseline}}$$
   Candidate years range from **2018 to 2025**; all targeted baseline papers were published in **2026**.
4. **Trigger Candidates Breakdown:** The 90 alerts stem from exactly **18 distinct pre-2026 trigger papers** evaluated against the **5 saved paper records** ($18 \times 5 = 90$):
   - Year 2018: `arxiv:1809.04281v3` (5 alerts)
   - Year 2019: `arxiv:1901.09960v5`, `driut:cand:roberta` (10 alerts)
   - Year 2020: `arxiv:2008.13369v1`, `crossref:10.1093/oso/9780198854227.003.0015`, `pubmed:99887766` (15 alerts)
   - Year 2021: `arxiv:2104.11502v1`, `arxiv:2111.01007v1` (10 alerts)
   - Year 2022: `arxiv:2201.00978v1`, `arxiv:2202.09061v4` (10 alerts)
   - Year 2023: `arxiv:2312.10045v2` (5 alerts)
   - Year 2024: `arxiv:2406.12896v1`, `crossref:10.21203/rs.3.rs-3916608/v1`, `ss:46062a1225c3...`, `ss:c3a31fb3da7...`, `ss:ed1c8676a7c...` (25 alerts)
   - Year 2025: `crossref:10.24108/preprints-3114040`, `csir:10.36227/techrxiv.176240516.62721984/v1` (10 alerts)
5. **Account Association:**
   - User `admin`: 72 alerts across saved papers 71, 67, 72, and 307.
   - User `testuser_task10`: 18 alerts on saved paper 71.

### 3.2 Non-Allowlisted Compliant Records (85 Alerts to Preserve)
All 85 alerts not in the allowlist were independently verified:
- **`VALID` (75 alerts):** Contemporaneous 2026 candidates evaluating 2026 saved papers (`Improvement`: 40, `Extension`: 25, `Challenge`: 5, `Reproduction`: 5). Valid under the Step 8b equal-year policy.
- **`EXEMPT` (10 alerts):** `Alternative` paradigm alerts. Non-directional by domain definition; exempt from directional temporal precedence.
- **`REVIEW_REQUIRED` (0 alerts):** Zero ambiguous or unclassified alerts exist.

---

## 4. Fresh Backup & Isolated Restoration Evidence

Before remediation is approved, a fresh, non-overwriting PostgreSQL backup was taken and validated via [`scripts/verify_backup_restore.py`](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/scripts/verify_backup_restore.py).

### 4.1 Backup Artifacts
- **Backup Location:** `backups/pg_20261020_200607/`
- **Compressed Dump File:** `research_papers_20261020_200607.sql.gz`
- **Uncompressed Size:** 316,424 bytes
- **Completion Signature:** `"PostgreSQL database dump complete"` verified.
- **SHA-256 Checksum:** `4daec4d3737d89c7596b859a839847e39312ae19dff3b41e046b9803ecce806a`

### 4.2 Isolated Restoration Test Results
The compressed backup was restored into a fresh, isolated PostgreSQL test database (`restore_verify_20261020_200607`):
- Restored `papers`: **162** (100% integrity)
- Restored `users`: **7** (100% integrity)
- Restored `saved_papers`: **5** (100% integrity)
- Restored `driut_alerts`: **175** (100% integrity)
- Restored `paper_evidence`: **3** (100% integrity)
- **Cleanup:** The temporary test database `restore_verify_20261020_200607` was dropped cleanly. The primary database was untouched.

---

## 5. Remediation Script Safety Review (`scripts/remediate_driut_chronology.py`)

The operational maintenance script [`scripts/remediate_driut_chronology.py`](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/scripts/remediate_driut_chronology.py) was authored and audited against all safety guidelines:

### 5.1 Safety Controls Implemented in the Script
1. **Dry-Run by Default:** Without the explicit `--execute` flag, the script performs a 100% read-only preflight check and exits without issuing any `DELETE` statement.
2. **Mandatory Backup Flag:** When `--execute` is supplied, the script requires `--backup-file <path>`, verifying that the file exists and computing its SHA-256 checksum for the execution record.
3. **Strict Allowlist Binding:** Reads `invalid_confirmed_alert_ids` from `RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json`, asserting that exactly 90 IDs are present. It **never** deletes by broad WHERE predicates (e.g., `WHERE year < 2026`).
4. **Pre-Transaction Assertions:**
   - Asserts total alerts == 175.
   - Asserts all 90 allowlisted IDs exist in the live database.
   - Asserts every allowlisted alert violates chronology and is directional.
   - Asserts all 85 remaining alerts are compliant.
5. **Exact Rowcount Assertion:**
   - Executes: `DELETE FROM driut_alerts WHERE id = ANY(:ids);`
   - Asserts `cursor.rowcount == 90`.
6. **Post-Transaction Assertions Before Commit:**
   - Asserts remaining alerts == 85.
   - Asserts table counts for `papers` (162), `users` (7), `saved_papers` (5), and `paper_evidence` (3) are identical to pre-checks.
   - Re-queries all remaining 85 alerts to assert zero residual chronology violations.
7. **Atomic Rollback:** Wrapped in SQLAlchemy `with conn.begin():`. Any assertion failure or unexpected exception triggers an immediate `ROLLBACK`.
8. **Audit Trail:** Preserves the audit ledger `RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json` untouched and outputs a JSON execution summary.

### 5.2 Dry-Run Verification Output
Execution of `backend/venv/bin/python scripts/remediate_driut_chronology.py --backup-file backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz` yielded:
```json
{
  "timestamp": "2026-10-20T14:37:01.784612+00:00",
  "ledger_path": ".../RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json",
  "backup_file": "backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz",
  "backup_sha256": "4daec4d3737d89c7596b859a839847e39312ae19dff3b41e046b9803ecce806a",
  "mode": "DRY_RUN",
  "allowlist_count": 90,
  "status": "DRY_RUN_PASSED",
  "pre_counts": {
    "total_alerts": 175,
    "papers": 162,
    "users": 7,
    "saved_papers": 5,
    "paper_evidence": 3
  },
  "message": "Dry-run successful. Pre-conditions verified. Zero database mutations performed."
}
```

---

## 6. Foreign-Key Dependencies & Data Integrity Verification

A relational inspection of the PostgreSQL schema was conducted to evaluate foreign-key coupling:
- **Foreign Keys Pointing TO `driut_alerts`:** **0 (None)**. No table in PostgreSQL maintains a foreign key referencing `driut_alerts`.
- **Foreign Keys Originating FROM `driut_alerts`:**
  - `saved_paper_id -> papers(id) ON DELETE CASCADE`
  - `trigger_paper_id -> papers(id) ON DELETE CASCADE`
  - `user_id -> users(username) ON DELETE CASCADE`
- **Impact Analysis:**
  - Deleting rows from `driut_alerts` does **not** trigger cascade deletions on any other table.
  - `papers`, `users`, `saved_papers`, `paper_evidence`, and the FAISS vector index are completely decoupled from `driut_alerts` rows.
  - No foreign-key constraints need to be disabled or bypassed.

---

## 7. Recurrence Prevention & Automated Guard Testing

The defect that produced these 90 historical alerts has been remediated and verified in application code:
1. **Step 8b Chronology Guard:** Located in `backend/app/services/driut_service.py:L409-441`. Automatically rejects candidate papers where $\text{Year}_{\text{candidate}} < \text{Year}_{\text{baseline}}$ for all directional relationship types.
2. **Targeted Test Coverage:** 7 automated tests in `backend/tests/test_targeted_remediations.py` pass:
   - `test_driut_effective_publication_year_extraction`
   - `test_driut_chronology_later_improves_earlier`
   - `test_driut_chronology_earlier_cannot_improve_later`
   - `test_driut_chronology_equal_publication_years`
   - `test_driut_chronology_missing_dates_handled`
   - `test_driut_chronology_advance_print_issue_preserves_valid_relationship`
   - `test_driut_legitimate_alternative_classification`
3. **Scheduler Lifecycle & Idempotency:** 7 automated tests in `backend/tests/test_driut_scheduler.py` pass, confirming advisory locking ($7376232$) and duplicate alert prevention.
4. **Guarantee:** When background scans run in the future, the Step 8b guard will reject these 90 pairs, preventing re-generation.

---

## 8. Precise Execution Command (For Separate Explicit Approval Only)

If and when separate, explicit user approval is granted, the exact command to execute the remediation will be:

```bash
backend/venv/bin/python scripts/remediate_driut_chronology.py \
  --execute \
  --backup-file backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz
```

**Rollback Procedure (If Needed):**
```bash
gunzip -c backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz | \
  podman exec -i research-paper-recommender-postgres-1 psql -U postgres -d research_papers
```

---

## 9. Final Preflight Verdict

```
READY FOR EXPLICIT DELETION APPROVAL
```

### Preflight Audit Sign-off:
- Database total alerts: **175** (verified).
- Allowlisted IDs: **90** (verified invalid chronology; verified present).
- Remaining compliant alerts: **85** (verified 75 valid, 10 exempt).
- Backup artifact: `research_papers_20261020_200607.sql.gz` (verified dump & restored successfully in test DB).
- Script safety: `scripts/remediate_driut_chronology.py` (dry-run verified, atomic transaction, exact rowcount checks, auto-rollback).
- Foreign-key safety: Zero foreign keys point to `driut_alerts`.
- Recurrence prevention: Step 8b chronology guard verified active.
- **Zero live mutations were executed during this safety gate.**
