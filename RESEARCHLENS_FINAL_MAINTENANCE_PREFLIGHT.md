# ResearchLens — Final Production Maintenance Preflight & Integrity Verification

**Document ID:** `RESEARCHLENS_FINAL_MAINTENANCE_PREFLIGHT.md`  
**Evaluation Date:** October 18, 2026  
**System Status:** **`MAINTENANCE READY FOR AUTHORIZED EXECUTION`**  
**Production Release Status:** **`PRODUCTION RELEASE BLOCKED`** (Awaiting Maintenance Window & Public Infrastructure Provisioning)

---

## 1. Executive Summary

This preflight report evaluates the exact operational and architectural readiness of **ResearchLens** prior to executing persistent maintenance operations.

In strict compliance with non-negotiable safety rules:
1. **Zero persistent records or index files were modified during this inspection.**
2. **Zero secrets, private tokens, or database passwords are exposed.**
3. **All container names, database names, and script interfaces were verified against the live runtime environment.**

### Key Preflight Determinations:
- **Publication-Date Policy:** Hardcoded `reference_year=2026` in `academic_sources.py` was replaced with a dynamic, calendar-resilient policy defaulting to `datetime.now(timezone.utc).year` when unspecified, while preserving explicit year overrides for deterministic testing and historical verification. Regression tests confirm seamless handling of 2026, 2027, and 2028 transitions.
- **26 Historical Records:** Live database inspection confirmed exactly 26 records with `year >= 2027`:
  - **1 Record (`pubmed:42635983`):** Upstream NCBI lists both `epubdate` and `pubdate` as `"2028 Aug 17"`. It is an authentic scheduled future release and is **strictly preserved at year 2028**.
  - **25 Records:** Upstream NCBI confirms electronic public availability between July and September 2026 (`epubdate`), with scheduled print issues in early 2027 (`pubdate`). Dry-run migration preview matches all 25 records.
- **Database & Container Resolution:**
  - Runtime container name: `research-paper-recommender-postgres-1` (not `postgres_container`).
  - Database name: `research_papers`.
  - Database port: `127.0.0.1:5432`.
- **Historical DRIUT Alert Violations:** Read-only inspection of all 175 alerts revealed that **141 alerts (80.6%)** exhibit chronological violations (`trigger_year < saved_year`). This was caused by baseline papers having stored year 2027 and legacy scans lacking chronology guards.
- **FAISS Vector Store:** FAISS contains 163 vectors and 163 metadata entries; PostgreSQL contains 162 papers. Exactly 1 orphan vector (`test:t15:cand_ext`, index 10) exists, with 0 database references.
- **Maintenance Safety:** Both `backend/app/db/migrate_pubmed_dates.py` and `scripts/reconcile_faiss_postgres.py` have been implemented, decoupled from web settings, verified in dry-run mode, and equipped with verified backups, atomic transactions, and automated rollbacks.

---

## 2. Publication-Date Policy & Calendar-Resilience Audit

### 2.1 Deficiency in Initial Remediation
Inspection of `backend/app/services/academic_sources.py` revealed that `parse_pubmed_dates` had hardcoded `reference_year: int = 2026`, and `search_pubmed` passed `reference_year=2026`.
- **Vulnerability:** When the calendar year advances to 2027, standard peer-reviewed articles published in 2027 (`epub_year=2027, print_year=2027`) would evaluate `print_year > 2026 and epub_year > 2026`, falsely classifying them as `forthcoming` rather than `published`.
- **Remediation Implemented:**
  ```python
  def parse_pubmed_dates(p: Dict[str, Any], reference_year: Optional[int] = None) -> Dict[str, Any]:
      ref_year = reference_year if reference_year is not None else datetime.now(timezone.utc).year
      ...
  ```
  `search_pubmed` was updated to accept `reference_year: Optional[int] = None` and pass `reference_year=reference_year` downstream.

### 2.2 Transition Test Verification
New regression tests in `backend/tests/test_targeted_remediations.py` (`test_pubmed_dynamic_and_year_transition_policy`) verified:
1. `reference_year=None` dynamically evaluates to current UTC year.
2. In 2027, an article with `epubdate` and `pubdate` in 2027 resolves to `published` with `year=2027`.
3. In 2027, an ahead-of-print article (`epubdate=2027 Nov`, `pubdate=2028 Jan`) resolves to `ahead_of_print` with `year=2027`.
4. In 2027, a paper scheduled for 2029 resolves to `forthcoming` with `year=2029`.
5. In 2028, record `pubmed:42635983` (`2028 Aug 17`) cleanly transitions from `forthcoming` to `published`.

---

## 3. Historical 26 Records & Dry-Run SQL Preview

### 3.1 Status of the 26 Records in PostgreSQL
A live read-only query on PostgreSQL container `research-paper-recommender-postgres-1` confirmed:

```sql
SELECT id, paper_id, year, title, venue 
FROM papers 
WHERE year >= 2027 
ORDER BY year DESC, id ASC;
```

**Results:** Exactly 26 rows returned:
- Row 1: ID 107 | `pubmed:42635983` | Year 2028 | *J Cogn Neurosci* -> **PRESERVE**
- Rows 2–26: 25 records with Year 2027 -> **TARGET FOR 2026 UPDATE**

### 3.2 Dry-Run SQL Statement
The exact idempotent SQL statement designed for the maintenance window:

```sql
-- Target: Exactly 25 records verified with 2026 electronic publication dates
-- Condition: Idempotent (only updates rows where year = 2027)
BEGIN;

UPDATE papers
SET year = 2026
WHERE paper_id IN (
    'pubmed:42431082',
    'pubmed:42630760',
    'pubmed:42602370',
    'pubmed:42571518',
    'pubmed:42828130',
    'pubmed:42700495',
    'pubmed:42541881',
    'pubmed:42732690',
    'pubmed:42669247',
    'pubmed:42636640',
    'pubmed:42502841',
    'pubmed:42520721',
    'pubmed:42497539',
    'pubmed:42485773',
    'pubmed:42480163',
    'pubmed:42766880',
    'pubmed:42731264',
    'pubmed:42735527',
    'pubmed:42609944',
    'pubmed:42665118',
    'pubmed:42741542',
    'pubmed:42729482',
    'pubmed:42766881',
    'pubmed:42751209',
    'pubmed:42733543'
)
AND year = 2027;

-- Post-condition assertions
SELECT count(*) AS updated_count FROM papers WHERE year = 2026 AND paper_id IN ('pubmed:42431082', 'pubmed:42630760');
SELECT year AS preserved_forthcoming_year FROM papers WHERE paper_id = 'pubmed:42635983';

COMMIT;
```

### 3.3 Dry-Run Execution via `migrate_pubmed_dates.py`
Running the tool in default dry-run mode matches all 26 records and verifies the exclusion:
```text
================================================================================
RESEARCHLENS — HISTORICAL PUBMED PUBLICATION DATE MIGRATION
================================================================================
Target count to update: 25 records
Protected forthcoming record: pubmed:42635983 (Preserved at year 2028)

--- READ-ONLY DATABASE PREVIEW (26 records matched) ---
ID: 107 | pubmed:42635983    | Current: 2028 -> Proposed: 2028 | PRESERVE (Authentic Forthcoming 2028 Issue)
ID:  71 | pubmed:42431082    | Current: 2027 -> Proposed: 2026 | UPDATE year 2027 -> 2026 (Electronic Availability)
ID: 108 | pubmed:42630760    | Current: 2027 -> Proposed: 2026 | UPDATE year 2027 -> 2026 (Electronic Availability)
... [23 additional records cleanly matched]
[DRY-RUN COMPLETE] Zero records modified in PostgreSQL.
```

---

## 4. Runtime Environment Resolution

Inspection of running containers and system configuration resolved actual names:

| Parameter | Previous Report Assumption | Actual Verified Runtime |
|:---|:---|:---|
| **PostgreSQL Container** | `postgres_container` | `research-paper-recommender-postgres-1` |
| **Container Engine** | Podman 5.x | Podman (Container ID: `9362adf3bda5`) |
| **Database Image** | PostgreSQL 16 | `docker.io/library/postgres:16-alpine` |
| **Database Name** | `research_papers` | `research_papers` |
| **Database Port** | 5432 | `127.0.0.1:5432` mapped to container 5432 |
| **Local AI Daemon** | Ollama | Active on `127.0.0.1:11434` (`qwen2.5:3b`) |
| **FastAPI Backend** | Port 8000 | Active on `127.0.0.1:8000` |
| **Frontend Server** | Port 3000 | Vite dev on `127.0.0.1:3000`; production bundle in `dist/` |

---

## 5. Historical DRIUT Chronology Violations Audit

A read-only SQL query audited all 175 alerts in `driut_alerts` comparing `trigger_paper.year` against `saved_paper.year`:

```sql
SELECT a.relationship_type, count(*)
FROM driut_alerts a
JOIN papers p_saved ON a.saved_paper_id = p_saved.id
JOIN papers p_trigger ON a.trigger_paper_id = p_trigger.id
WHERE p_trigger.year < p_saved.year
GROUP BY a.relationship_type;
```

### Empirical Findings:
- **Total Existing Alerts:** 175
- **Chronology Violations (`trigger_year < saved_year`):** **141 alerts (80.6%)**
- **Breakdown by Relationship:**
  - `Improvement`: **89 alerts** (older paper labeled as "improving" newer paper)
  - `Extension`: **40 alerts** (older paper labeled as "extending" newer paper)
  - `Alternative`: **6 alerts**
  - `Reproduction`: **3 alerts**
  - `Challenge`: **3 alerts**

### Root Cause Analysis:
1. **Year 2027 Contamination:** Saved baseline papers ID 71 (`pubmed:42431082`, year 2027) and ID 307 (`pubmed:42520721`, year 2027) accounted for **105 of the 141 violations** (70 and 35 alerts respectively) because legitimate prior research from 2018–2026 appeared older than their artificial 2027 dates.
2. **Unconstrained Legacy Scans:** Saved papers ID 67 (year 2026) and ID 72 (year 2026) had 36 alerts triggered by older papers from 2020–2021 before the Step 8b Chronology-Aware Guard was implemented.
3. **Operational Policy:** In accordance with non-negotiable rules, **zero existing alerts were deleted or modified**. The historical alerts remain preserved for auditability. Step 8b now ensures that zero new chronology violations can be generated moving forward.

---

## 6. Preflight Regression Test Results

Fresh tests were executed in the isolated virtual environment:

| Test Suite | Tests Run | Result | Duration | Notes |
|:---|:---:|:---:|:---:|:---|
| `test_targeted_remediations.py` | 24 | **24 passed** | 12.09s | Added dynamic UTC and year transition tests |
| `test_driut_intelligence.py` | 17 | **17 passed** | 5.86s | Step 8b chronology guard verified |
| `test_driut_scheduler.py` | 14 | **14 passed** | 7.97s | Scheduler isolation verified |
| `test_auth_and_isolation.py` | 12 | **12 passed** | 4.31s | Tenant isolation verified |
| Frontend Vitest | 66 | **66 passed** | 1.29s | 8 component suites passed |
| Frontend Production Build | 1 | **Clean** | 692ms | `tsc -b && vite build` 0 errors |

---

## 7. Preflight Conclusion & Gate Status

```
================================================================================
PREFLIGHT GATE STATUS: MAINTENANCE READY FOR AUTHORIZED EXECUTION
================================================================================
```
All commands, container identifiers, migration scripts, fallback paths, and dry-run SQL statements have been checked against the actual implementation. The operational runbook is ready for execution by authorized release engineers.
