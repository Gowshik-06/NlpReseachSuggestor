# ResearchLens — Historical PubMed Publication-Year Correction & Verification Report

**Document ID:** `RESEARCHLENS_PUBMED_YEAR_CORRECTION_REPORT.md`  
**Execution Date:** October 18, 2026  
**Final Status:** **`YEAR DATA CORRECTED AND VERIFIED`**

---

## 1. Executive Summary

This report documents the authorized execution and empirical verification of the historical PubMed publication-year correction for **ResearchLens — NLP-Based Research Paper Recommendation System**.

All operations strictly adhered to the mandatory safety protocols:
1. **Zero Data Loss:** All 162 research paper records, accounts, saved libraries, evidence spans, and historical alerts remain fully intact.
2. **Verified Backup Prerequisite:** A complete PostgreSQL backup was created and validated through an isolated restore test into a temporary test database before modifying persistent storage.
3. **Targeted Atomic Correction:** Only the 25 verified records whose electronic public availability (`epubdate`) was confirmed in 2026 with scheduled print issues in 2027 were updated.
4. **Authentic Forthcoming Record Preserved:** Paper `pubmed:42635983` (*Journal of Cognitive Neuroscience*) was explicitly preserved at `year = 2028`.
5. **Zero Unnecessary Vector Re-indexing:** The FAISS vector index (`research_index.faiss`) was not modified; metadata in `papers_meta.json` was updated in-place without vector regeneration.
6. **Empirical Verification:** The live PostgreSQL database and running search endpoints were queried post-migration, confirming that 25 records now reflect year 2026 and search results order correctly.

---

## 2. Pre-Maintenance Backup & Isolated Restore Verification

Before executing any write operation, Step B was executed using `scripts/verify_backup_restore.py`:

| Backup Metric / Step | Recorded Value | Verification Status |
|:---|:---|:---:|
| **Target Container** | `research-paper-recommender-postgres-1` | Verified Active |
| **Target Database** | `research_papers` | Verified Healthy |
| **Dump Output File** | `backups/pg_20261018_230610/research_papers_20261018_230610.sql.gz` | Created |
| **Raw Dump Size** | **316,424 bytes** (316 KB) | > 100 KB Threshold (**PASS**) |
| **Completion Signature** | `"PostgreSQL database dump complete"` present | Verified (**PASS**) |
| **Cryptographic Hash** | `b255b4ffbc3c56d3ad0b836a97dc019170829580e7250c0efbbaee50ac87192d` | SHA-256 Saved |
| **Isolated Test Database** | `restore_verify_20261018_230610` | Created & Dropped |
| **Restored Record Counts** | `papers`: 162, `users`: 7, `saved_papers`: 5, `driut_alerts`: 175, `evidence`: 3 | **100% Match (PASS)** |

---

## 3. Complete Before-and-After Record Table (26 Records)

The 26 records were queried before and after execution:

| DB ID | Paper Identifier | Journal / Venue | Upstream `epubdate` | Upstream `pubdate` | Before Year | After Year | Publication Status | Action Taken |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **107** | `pubmed:42635983` | *J Cogn Neurosci* | 2028 Aug 17 | 2028 Aug 17 | **2028** | **2028** | `forthcoming` | **PRESERVED (Authentic 2028)** |
| **71** | `pubmed:42431082` | *Neural Netw* | 2026 Jul 7 | 2027 Jan | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **108** | `pubmed:42630760` | *Synth Syst Biotechnol* | 2026 Aug 13 | 2027 Mar | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **109** | `pubmed:42602370` | *Synth Syst Biotechnol* | 2026 Aug 6 | 2027 Mar | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **110** | `pubmed:42571518` | *Infect Dis Model* | 2026 Jul 28 | 2027 Mar | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **111** | `pubmed:42828130` | *Bioact Mater* | 2026 Sep 22 | 2027 Feb | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **227** | `pubmed:42700495` | *Talanta* | 2026 Sep 4 | 2027 Feb 1 | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **228** | `pubmed:42541881` | *Talanta* | 2026 Jul 24 | 2027 Feb 1 | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **229** | `pubmed:42732690` | *Spectrochim Acta A* | 2026 Sep 10 | 2027 Jan 15 | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **230** | `pubmed:42669247` | *Spectrochim Acta A* | 2026 Aug 25 | 2027 Jan 5 | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **231** | `pubmed:42636640` | *Spectrochim Acta A* | 2026 Aug 20 | 2027 Jan 5 | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **306** | `pubmed:42502841` | *Synth Syst Biotechnol* | 2026 Jul 16 | 2027 Feb | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **307** | `pubmed:42520721` | *Spectrochim Acta A* | 2026 Jul 13 | 2027 Jan 5 | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **308** | `pubmed:42497539` | *Neural Netw* | 2026 Jul 22 | 2027 Jan | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **309** | `pubmed:42485773` | *Neural Netw* | 2026 Jul 20 | 2027 Jan | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **310** | `pubmed:42480163` | *Neural Netw* | 2026 Jul 18 | 2027 Jan | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **426** | `pubmed:42766880` | *Talanta* | 2026 Sep 18 | 2027 Feb 1 | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **427** | `pubmed:42731264` | *Talanta* | 2026 Sep 7 | 2027 Feb 1 | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **428** | `pubmed:42735527` | *Spectrochim Acta A* | 2026 Sep 11 | 2027 Jan 15 | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **907** | `pubmed:42609944` | *DEN Open* | 2026 Aug 17 | 2027 Apr | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **908** | `pubmed:42665118` | *Clin Chim Acta* | 2026 Aug 28 | 2027 Feb 15 | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **914** | `pubmed:42741542` | *DEN Open* | 2026 Sep 13 | 2027 Apr | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **915** | `pubmed:42729482` | *DEN Open* | 2026 Sep 10 | 2027 Apr | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **916** | `pubmed:42766881` | *Talanta* | 2026 Sep 19 | 2027 Feb 1 | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **917** | `pubmed:42751209` | *Bioact Mater* | 2026 Sep 7 | 2027 Feb | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |
| **918** | `pubmed:42733543` | *Bioact Mater* | 2026 Sep 3 | 2027 Feb | **2027** | **2026** | `ahead_of_print` | **UPDATED (E-pub in 2026)** |

---

## 4. Migration Execution & Transaction Safeguards

The migration script [`backend/app/db/migrate_pubmed_dates.py`](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backend/app/db/migrate_pubmed_dates.py) was executed:
- **Transaction Block:** All 25 updates executed within a single `engine.begin()` transaction.
- **Rowcount Assertion:** Verified that `rowcount == 25`.
- **Protected Record Assertion:** Asserted that `pubmed:42635983` remained at `year = 2028`.
- **Idempotency Verified:** Re-running the script executed cleanly with `Rows updated: 0`.
- **Metadata Synchronization:** Synchronized `papers_meta.json` in-place, updating the 25 metadata dictionary entries to `year = 2026`.

---

## 5. Post-Update Assertions & FAISS Impact Assessment

### 5.1 Database Assertions
1. **Total Papers:** Exactly **162** (0 records added, 0 deleted).
2. **Papers with `year >= 2027`:** Exactly **1** (`pubmed:42635983`, year 2028).
3. **Target Allowlisted Records with `year = 2026`:** Exactly **25**.
4. **Preserved Provenance:** Scheduled print issues remain explicitly preserved in the venue field and abstract text (e.g., `(2027 Jan)`).

### 5.2 FAISS Vector Store Impact
- **Vector Index (`research_index.faiss`):** Zero modifications. Embeddings represent semantic content (title + abstract) and are completely invariant to year changes. Rebuilding or re-indexing was completely avoided.
- **Metadata Store (`papers_meta.json`):** Synchronized atomically via temporary file swap (`papers_meta.json.tmp` -> `papers_meta.json`).

### 5.3 Live Search & Recommendation Behavior
Live query against `/api/v1/papers/search` for `"knowledge tracing framework"` returned:
- `pubmed:42431082` (Paper ID 71) returned with `year: 2026` (previously 2027) and annotated with `✨ 2026 Latest Breakthrough`.
- `pubmed:42502841` (Paper ID 306) returned with `year: 2026` (previously 2027).

---

## 6. Recalculation of Historical DRIUT Chronology Violations

A read-only query was executed across all 175 alerts in `driut_alerts`:
- **Original Chronology Violations:** **141 alerts (80.6%)**
- **Post-Update Chronology Violations:** **90 alerts (51.4%)**
  - **51 violations automatically resolved** because saved papers ID 71 and ID 307 are now accurately identified as published in 2026, meaning 2026 candidate research no longer violates chronological causality against them.
- **Remaining 90 Violations Breakdown:**
  - `Improvement`: **65 alerts** (legacy alerts where 2018–2025 papers triggered on 2026 baseline papers)
  - `Extension`: **25 alerts**
- **Affected Baseline Papers:**
  - Saved Paper ID 71 (`pubmed:42431082`, now Year 2026): 36 alerts
  - Saved Paper ID 67 (`arxiv:2609.35768v1`, Year 2026): 18 alerts
  - Saved Paper ID 72 (`pubmed:42659950`, Year 2026): 18 alerts
  - Saved Paper ID 307 (`pubmed:42520721`, now Year 2026): 18 alerts
- **Remediation Plan:** These remaining 90 alerts are legacy artifacts generated prior to the implementation of Step 8b Chronology Guard. They remain preserved for historical auditability. Moving forward, Step 8b permanently blocks any new alert where `new_year < saved_year`.

---

## 7. Test Verification Results

All relevant test suites were re-run post-migration:

| Test Suite | Tests Run | Result | Duration |
|:---|:---:|:---:|:---:|
| Targeted Publication-Date Suite (`test_targeted_remediations.py`) | 24 | **24 passed** | 12.09s |
| DRIUT Intelligence Suite (`test_driut_intelligence.py`) | 15 | **15 passed** | 5.86s |
| DRIUT Scheduler Suite (`test_driut_scheduler.py`) | 16 | **16 passed** | 7.97s |
| Local Search Correctness Suite (`test_local_search_correctness.py`) | 9 | **9 passed** | 10.32s |
| **Total Test Verification** | **64** | **64 passed (100%)** | **36.24s** |

---

## 8. Final Status Verdict

```
================================================================================
FINAL STATUS: YEAR DATA CORRECTED AND VERIFIED
================================================================================
```
All 25 target records in PostgreSQL and FAISS metadata now accurately record year 2026, the authentic 2028 forthcoming record is preserved, verified backups exist, and live search and recommendation engines reflect the corrected publication chronology with 100% test passage.
