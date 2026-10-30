# ResearchLens — Data Integrity, Index Consistency & Metadata Quality Report

**Document ID:** `RESEARCHLENS_DATA_INTEGRITY_REPORT.md`  
**Evaluation Date:** October 18, 2026  
**System Components:** PostgreSQL 16, FAISS `IndexFlatIP`, `papers_meta.json`, `evidence_service.py`, `summary_service.py`  
**Status:** **AUDITED, HARDENED & RECONCILIATION TOOLING READY**

---

## 1. Executive Summary

This report documents the empirical state of ResearchLens data storage layers as of October 18, 2026:
1. **Relational Database (PostgreSQL):** 162 total catalog papers across 7 user accounts, 5 saved papers, 175 DRIUT alerts, 3 verified evidence items.
2. **Vector Index (FAISS):** 163 total vectors (`IndexFlatIP`, dimension 768), 163 `id_map` entries, 163 `papers_meta.json` entries.
3. **Consistency Discrepancy:** Exactly **1 orphaned vector** in FAISS (`test:t15:cand_ext`) absent from PostgreSQL. Zero PostgreSQL papers are missing from FAISS.
4. **Metadata Quality:** 97 papers have missing or empty abstracts; 5 legacy records contain synthetic placeholder abstracts.
5. **Operational Safety Invariant:** In accordance with non-negotiable engineering rules, **zero live records were modified, deleted, or silently re-indexed**.

---

## 2. PostgreSQL & FAISS Consistency Audit

### 2.1 Empirical Counts and Characteristics

| Metric / Dimension | PostgreSQL | FAISS Vector Store | Variance / Status |
|:---|:---:|:---:|:---:|
| **Total Items** | 162 papers | 163 vectors | +1 vector in FAISS |
| **Identifier Map (`id_map`)** | N/A | 163 string keys | Aligned with vectors |
| **Metadata Dictionary** | 162 records | 163 dictionary entries | Aligned with vectors |
| **Vector Dimension** | N/A | 768 (`float32`) | Exactly matches SPECTER2 |
| **Metric Type** | N/A | `INNER_PRODUCT` (0) | Cosine similarity on normalized vectors |
| **Index File Path** | N/A | `backend/data/processed/faiss/research_index.faiss` | Present (`19fbb3c2...`) |
| **Metadata File Path** | N/A | `backend/data/processed/faiss/papers_meta.json` | Present (`ded1f80d...`) |
| **Unindexed Papers (in DB, missing in FAISS)** | 0 | 0 | **0 Missing** |
| **Orphaned Vectors (in FAISS, missing in DB)** | 0 | 1 | **1 Orphan (`test:t15:cand_ext`)** |

### 2.2 Deep-Dive Investigation: Orphan Vector `test:t15:cand_ext`

Inspection of `papers_meta.json` at index position 10 revealed:
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

#### Provenance and Database Impact:
- **Origin:** Injected into `papers_meta.json` during historical integration testing (Test T15) prior to test database isolation.
- **Relational Integrity Check:**
  - `papers` table: 0 matches for `paper_id = 'test:t15:cand_ext'`.
  - `saved_papers` table: 0 foreign key references (uses integer `paper_id` FK).
  - `driut_alerts` table: 0 foreign key references (uses integer `saved_paper_id` / `trigger_paper_id`).
  - `paper_evidence` table: 0 foreign key references (uses integer `paper_id`).
- **Consumer Impact:** Vector search (`execute_recommendation_search`) filters candidate vectors against PostgreSQL database papers when hydrating results or joins against `papers.id`. Because `test:t15:cand_ext` is not in the database, it is safely omitted from relational query hydration unless queried via transient paper endpoints.
- **Remediation Action:** Per Non-Negotiable Rule #3, **the index was not rebuilt or modified**. A safe, standalone maintenance script was developed to remove the orphan under an approved maintenance window.

---

## 3. Metadata Quality & Synthetic Placeholder Abstract Guards

### 3.1 Catalog Abstract Completeness
- **Total Papers:** 162
- **Substantive Abstracts:** 65 papers (40.1%)
- **Missing / Empty Abstracts:** 97 papers (59.9%)
- **Synthetic Placeholder Abstracts:** 5 legacy PubMed papers contain generated placeholder text:
  > *"Biomedical & computational research paper indexed by the US National Library of Medicine (PubMed / NIH). Published in..."*

### 3.2 Implemented Placeholder Detection Guards
To prevent synthetic boilerplate text from being treated as genuine scientific claims or hallucinated evidence, rigorous guards were implemented across all AI and NLP services:

#### Pattern Definition (`evidence_service.py` & `summary_service.py`):
```python
SYNTHETIC_PLACEHOLDER_REGEX = re.compile(
    r"(?:biomedical\s*&\s*computational\s*research\s*paper\s*indexed\s*by\s*the\s*us\s*national\s*library\s*of\s*medicine|"
    r"published\s*in\s*[\w\s\(\)\.-]+\s*\((?:19\d\d|20\d\d)[^\)]*\))",
    re.IGNORECASE
)

def is_synthetic_placeholder_abstract(abstract: Optional[str]) -> bool:
    if not abstract or not abstract.strip():
        return True
    text = abstract.strip()
    if len(text) < 40:
        return True
    if SYNTHETIC_PLACEHOLDER_REGEX.search(text) and len(text) < 300:
        return True
    return False
```

#### Service Behavior When Placeholder Detected:
1. **Evidence Extraction (`evidence_service.py`):**
   - Returns `0 claims` and records `status="unavailable_evidence"`.
   - Never extracts fabricated sentences or creates invalid evidence passages.
2. **AI Summarization (`summary_service.py`):**
   - Transparently responds:
     > *"No substantive scientific abstract is available for this paper. The catalog entry contains only indexing metadata or a title-only record. Substantive research evidence cannot be extracted without an authentic paper abstract or full text."*
   - Avoids calling local Ollama or cloud providers on synthetic text.
3. **Research Evolution (`evolution_service.py`):**
   - Skips claim gathering for synthetic abstracts during milestone timeline construction.

---

## 4. Safe Reconciliation Maintenance Tooling

A production-grade reconciliation utility was created at `scripts/reconcile_faiss_postgres.py`.

### 4.1 Safety Architecture
1. **Dry-Run by Default:** Without explicit flags, executes read-only comparisons, computes cryptographic SHA-256 hashes, and reports mismatches without modifying disks.
2. **Backup Prerequisite:** Requires `--backup-dir` when running with `--execute`. Backs up both `research_index.faiss` and `papers_meta.json` before touching files.
3. **Rollback Strategy:** If an atomic write fails, the previous `.bak` files are restored immediately.
4. **Separation from Startup:** The tool is strictly isolated from application startup (`start-researchlens.sh`) to prevent accidental indexing during boot.

### 4.2 Dry-Run Verification Output
```bash
$ ./backend/venv/bin/python scripts/reconcile_faiss_postgres.py
================================================================================
RESEARCHLENS — FAISS & POSTGRESQL RECONCILIATION & INTEGRITY TOOL
================================================================================
Database URL: localhost:5432/research_papers
FAISS Directory: .../backend/data/processed/faiss
Mode: DRY-RUN (READ-ONLY)

--- DIAGNOSTIC RESULTS ---
Index Exists: True (SHA-256: 19fbb3c21e69c02a...)
Metadata Exists: True (SHA-256: ded1f80d846c7c38...)
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
To safely repair, an approved maintenance window must execute:
  python scripts/reconcile_faiss_postgres.py --execute --backup-dir /path/to/backup
```

---

## 5. Historical Data Migration Plan (Pending Approval)

When an authorized maintenance window is scheduled, the following two operations will be executed:

### Phase A: Reconcile FAISS Orphan
1. Take cold filesystem snapshot of `backend/data/processed/faiss/`.
2. Execute:
   ```bash
   ./backend/venv/bin/python scripts/reconcile_faiss_postgres.py --execute --backup-dir /backups/faiss/20261018/
   ```
3. Verify `ntotal == 162`, `id_map == 162`, `papers_meta.json == 162`.

### Phase B: Correct 25 PubMed Year 2027 Records in PostgreSQL
1. Verify database backup using Podman volume snapshot:
   ```bash
   podman exec -t postgres_container pg_dump -U postgres research_papers > /backups/postgres_20261018.sql
   ```
2. Execute targeted idempotent SQL migration updating the 25 records to `year = 2026` based on their validated `epubdate`.
3. Synchronize `papers_meta.json` entries for those 25 records.
4. Run regression test suite to confirm zero regressions.
