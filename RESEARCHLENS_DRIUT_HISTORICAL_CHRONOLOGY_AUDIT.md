# ResearchLens — Historical DRIUT Chronology Audit & Controlled Remediation Plan

**Document ID:** `RESEARCHLENS-AUDIT-DRIUT-CHRONOLOGY-20261020`  
**Audit Timestamp:** 2026-10-20T19:26:00+05:30  
**Repository Root:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Machine-Readable Ledger:** [`RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json`](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json)  
**Database URL:** `postgresql+psycopg2://postgres:postgres@localhost:5432/research_papers`  

---

## 1. Executive Summary & Current Live State

A comprehensive, read-only audit of the Dynamic Research Impact Update Tracker (DRIUT) historical alerts was conducted against the live PostgreSQL database.

### Verified Current State
- **Total Catalog Papers:** **162** (all with verified non-null `paper_id` and publication years).
- **Total Saved Papers:** **5** across 2 accounts:
  - `testuser_task10`: 1 saved paper (`pubmed:42431082`, Year: 2026).
  - `admin`: 4 saved papers (`pubmed:42431082`, `arxiv:2609.35768v1`, `pubmed:42659950`, `pubmed:42520721` — all Year: 2026).
- **Total Historical DRIUT Alerts:** **175** (created between Oct 9 and Oct 12, 2026).
- **Reported Chronology Violations:** Exactly **90** alerts violate the directional chronology requirement (`trigger_effective_year < saved_effective_year`).
- **Compliant Historical Alerts:** **85** alerts (75 contemporaneous same-year 2026 alerts + 10 non-directional alternative paradigm alerts).
- **FAISS Vector Index:** Reconciled at **162 vectors** (dimension 768, `METRIC_INNER_PRODUCT`), in exact 1:1 synchronization with PostgreSQL.

### Classification Summary
| Classification | Count | Percentage | Description |
| :--- | :---: | :---: | :--- |
| **`INVALID_CONFIRMED`** | **90** | 51.4% | Directional alerts (`Improvement`, `Extension`) where candidate paper published in 2018–2025 precedes baseline paper published in 2026. |
| **`VALID`** | **75** | 42.9% | Contemporaneous 2026 vs. 2026 alerts (`Improvement`, `Extension`, `Challenge`, `Reproduction`) valid under the equal-year policy. |
| **`EXEMPT`** | **10** | 5.7% | `Alternative` paradigm alerts; non-directional relationship category explicitly exempted by domain semantics. |
| **`REVIEW_REQUIRED`** | **0** | 0.0% | Zero alerts have missing years or ambiguous date provenance. All 175 records have verified publication dates. |
| **Total Alerts Audited** | **175** | **100.0%** | Comprehensive audit completed. |

---

## 2. Chronology Policy & Domain Semantics

### The Intended Chronology Policy (Step 8b)
In the scientific domain, research impact tracking reflects temporal progression:
1. **Directional Categories (`Improvement`, `Extension`, `Potential Replacement`, `Challenge`, `Reproduction`):**
   - **Requirement:** $\text{Year}_{\text{candidate}} \ge \text{Year}_{\text{baseline}}$
   - **Rationale:** A paper published in 2018–2025 cannot cite, improve upon, extend, challenge, or reproduce experimental findings from a work first published in 2026.
   - **Enforcement:** Enforced in [`backend/app/services/driut_service.py`](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backend/app/services/driut_service.py#L409-L435) via `extract_effective_publication_year`. If $\text{Year}_{\text{candidate}} < \text{Year}_{\text{baseline}}$, `base_res.is_supported = False` and `relationship_type = None`, completely rejecting alert creation.
2. **Non-Directional Category (`Alternative`):**
   - **Requirement:** Exempt from directional precedence.
   - **Rationale:** An "Alternative" represents an orthogonal computational paradigm addressing the same research objective without relying on the baseline architecture. Two alternative paradigms can be published at different times or contemporaneously.
3. **Contemporaneous Publications ($\text{Year}_{\text{candidate}} == \text{Year}_{\text{baseline}}$):**
   - **Policy:** Permitted with an uncertainty note (`"Both papers share publication year 2026; exact sub-year chronology cannot be verified from metadata."`).
   - **Rationale:** Conferences and journals often publish preprints and camera-ready articles within the same calendar year where day/month data is incomplete. Disqualifying same-year updates would erroneously suppress valid concurrent research.

### Origin of the 90 Historical Violations
- The 175 alerts in PostgreSQL were generated during initial automated scans on **October 9–12, 2026**, prior to the design and implementation of the Step 8b chronology guard (which was introduced on October 18, 2026).
- When the historical scanner ran, candidate papers from 2018–2025 matched lexical patterns (e.g., "outperforms", "extends") against the 2026 saved papers and were stored without temporal validation.
- All 90 violations involve exactly **18 candidate papers** evaluated across the **5 saved paper records** ($18 \times 5 = 90$ alerts).
- The earlier PubMed year correction (which corrected 25 papers from 2027 to electronic year 2026) resolved **51** previous violations; the remaining **90** violations involve true historical papers (2018–2025) and were unaffected by the date correction.

---

## 3. Detailed Audit Ledger & Violation Breakdown

### Violation Breakdown by Category & Source
All 90 `INVALID_CONFIRMED` alerts belong to strictly directional categories:
- **`Improvement`:** 65 alerts
- **`Extension`:** 25 alerts

### Candidate Papers Involved in the 90 Violations
The 90 invalid alerts originate from exactly 18 distinct pre-2026 candidate papers:

| Candidate Paper ID | Source | Year | Title | Invalid Alerts Generated |
| :--- | :---: | :---: | :--- | :---: |
| `arxiv:1809.04281v3` | arXiv | 2018 | Music Transformer | 5 |
| `arxiv:1901.09960v5` | arXiv | 2019 | Using Pre-Training Can Improve Model Robustness and Uncertainty | 5 |
| `driut:cand:roberta` | test | 2019 | RoBERTa: A Robustly Optimized BERT Approach | 5 |
| `arxiv:2008.13369v1` | arXiv | 2020 | Introducing Representations of Facial Affect in Automated Multimodal D... | 5 |
| `crossref:10.1093/oso/9780198854227.003.0015` | Crossref | 2020 | Quantum Computing I | 5 |
| `pubmed:99887766` | PubMed | 2020 | BioBERT: Extending Pre-trained BERT for Biomedical Applications | 5 |
| `arxiv:2104.11502v1` | arXiv | 2021 | Learning to Cluster Faces via Transformer | 5 |
| `arxiv:2111.01007v1` | arXiv | 2021 | Projected GANs Converge Faster | 5 |
| `arxiv:2201.00978v1` | arXiv | 2022 | PyramidTNT: Improved Transformer-in-Transformer Baselines with Pyramid... | 5 |
| `arxiv:2202.09061v4` | arXiv | 2022 | VLP: A Survey on Vision-Language Pre-training | 5 |
| `arxiv:2312.10045v2` | arXiv | 2023 | Interpretable Knowledge Tracing via Response Influence-based Counterfa... | 5 |
| `arxiv:2406.12896v1` | arXiv | 2024 | Leveraging Pedagogical Theories to Understand Student Learning Process... | 5 |
| `crossref:10.21203/rs.3.rs-3916608/v1` | Crossref | 2024 | The Triple Attention Transformer: Advancing Contextual Coherence in Tr... | 5 |
| `ss:46062a1225c3f9f178530020cdc35051e5682037` | Semantic Scholar | 2024 | A manufacturable platform for photonic quantum computing | 5 |
| `ss:c3a31fb3da7bcf9af102e8fb961652656949b8b0` | Semantic Scholar | 2024 | Transformers in Natural Language Processing: A Comprehensive Review | 5 |
| `ss:ed1c8676a7c13421afa315af9702fad182ee2347` | Semantic Scholar | 2024 | Quantum computing with Qiskit | 5 |
| `crossref:10.24108/preprints-3114040` | Crossref | 2025 | Vision Transformers: Architecture, Attention Mechanisms, and Perspecti... | 5 |
| `csir:10.36227/techrxiv.176240516.62721984/v1` | CSIR | 2025 | Attention-Driven Transformers | 5 |
| **Total** | | | **18 Distinct Trigger Papers** | **90 Alerts ($18 \times 5$)** |

### Saved Baseline Papers Targeted
Each of the 5 saved paper records received all 18 invalid historical alerts:
1. `pubmed:42431082` (User: `testuser_task10`) — 18 invalid alerts
2. `pubmed:42431082` (User: `admin`) — 18 invalid alerts
3. `arxiv:2609.35768v1` (User: `admin`) — 18 invalid alerts
4. `pubmed:42659950` (User: `admin`) — 18 invalid alerts
5. `pubmed:42520721` (User: `admin`) — 18 invalid alerts

---

## 4. Remediation Options & Risk Assessment

Three remediation strategies were evaluated to address the 90 `INVALID_CONFIRMED` alerts:

### Strategy 1: Controlled Database Purge (Recommended)
- **Mechanism:** Execute an atomic, allowlisted `DELETE FROM driut_alerts WHERE id IN (...90 IDs...);` inside an explicit transaction.
- **Preconditions:**
  1. Complete verified PostgreSQL dump taken (`pg_dump` with SHA-256 checksum).
  2. Complete machine-readable audit ledger exported and persisted (`RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json`).
- **Postconditions:**
  - `driut_alerts` total drops from 175 to **85**.
  - All 85 remaining alerts are 100% compliant with the v2.0 chronology policy.
  - Zero scientific falsehoods (e.g. RoBERTa 2019 "improving" a 2026 paper) presented in the researcher UI.
- **Risks & Mitigation:**
  - *Risk:* Deletion of historical database rows.
  - *Mitigation:* Mitigated 100% by the standalone machine-readable ledger preserving all 90 alert passages, character offsets, explanations, and metadata, backed by an immutable SQL dump.

### Strategy 2: In-Place Disqualification / Soft Annotation
- **Mechanism:** Retain the 90 database rows, but update fields in-place:
  - `uncertainty_warning`: Set to `"Historical chronology conflict: candidate paper (<title>, <year>) precedes baseline (<title>, <year>). Invalidated under v2.0 chronology guard."`
  - `evidence_strength`: Set to `"insufficient_evidence"`.
  - `classification_version`: Set to `"v2.0-chronology-invalidated"`.
- **Tradeoffs:**
  - *Advantage:* Zero row deletions; preserves raw row count.
  - *Disadvantage:* The existing UI query (`GET /api/v1/papers/driut/alerts`) does not filter by `classification_version`, so these 90 alerts would continue to clutter the user's alert dashboard.

### Strategy 3: Mark as Read (`is_read = true`)
- **Mechanism:** `UPDATE driut_alerts SET is_read = true WHERE id IN (...);`
- **Tradeoffs:**
  - *Disadvantage:* Does not remove them from the "All Impact Alerts" view; merely suppresses the unread badge. Unsuitable as a scientific integrity remediation.

---

## 5. Controlled Execution Allowlist (Exact 90 Alert IDs)

The exact allowlist of 90 alert IDs confirmed for remediation:

```json
[
  631, 632, 633, 634, 635, 636, 637, 638, 639, 665, 
  669, 753, 756, 757, 1101, 1132, 1312, 1313, 1314, 1316, 
  1317, 1318, 1319, 1320, 1321, 1322, 1323, 1324, 1329, 1331, 
  1332, 1333, 1343, 1344, 1345, 1346, 1347, 1348, 1349, 1350, 
  1351, 1352, 1353, 1354, 1359, 1361, 1362, 1363, 1369, 1375, 
  1376, 1377, 1378, 1379, 1380, 1381, 1382, 1383, 1384, 1385, 
  1386, 1391, 1393, 1394, 1395, 1406, 1407, 1408, 1409, 1410, 
  1411, 1412, 1413, 1414, 1415, 1416, 1417, 1422, 1424, 1425, 
  1426, 1432, 1435, 1436, 1439, 1442, 1443, 1446, 1447, 1448
]
```

### Breakdown by User:
- **`testuser_task10` (18 IDs):** `[631, 632, 633, 634, 635, 636, 637, 638, 639, 665, 669, 753, 756, 757, 1101, 1132, 1369, 1432]`
- **`admin` (72 IDs):** Remaining 72 IDs across `saved_paper_id` 71, 67, 72, and 307.

---

## 6. Phase D — Prevention Guard Verification & Test Evidence

The active chronology guard was independently verified through 23 non-destructive tests:

### 1. Chronology Guard Unit & Integration Tests
Command:
```bash
./backend/venv/bin/pytest backend/tests/test_targeted_remediations.py -k "driut" -v
```
**Results (7 passed in 10.79s):**
- `test_driut_effective_publication_year_extraction` — **PASSED** (handles advance articles, forthcoming issues, epub dates, standard years).
- `test_driut_chronology_later_improves_earlier` — **PASSED** (validates 2026 improving 2024).
- `test_driut_chronology_earlier_cannot_improve_later` — **PASSED** (asserts earlier candidate 2026 cannot improve scheduled 2027; rejects alert).
- `test_driut_chronology_equal_publication_years` — **PASSED** (validates contemporaneous 2026 vs 2026 with uncertainty warning).
- `test_driut_chronology_missing_dates_handled` — **PASSED** (missing publication year handled safely without crash).
- `test_driut_chronology_advance_print_issue_preserves_valid_relationship` — **PASSED** (electronic pub date 2025 preserved over 2027 scheduled print).
- `test_driut_legitimate_alternative_classification` — **PASSED** (validates non-directional Alternative paradigm classification).

### 2. Scheduler Lifecycle, Concurrency & Idempotency Tests
Command:
```bash
./backend/venv/bin/pytest backend/tests/test_driut_scheduler.py -v
```
**Results (16 passed in 16.07s):**
- Concurrency locks, advisory locking, idempotency (`test_driut_idempotency_and_is_read_preservation`), user isolation, and provider failure tolerance all verified.

---

## 7. Execution Protocol & Rollback Strategy

When explicit approval is granted, remediation will follow this strict protocol:

### Step 1: Pre-Remediation PostgreSQL Snapshot
```bash
BACKUP_DIR="backups/pg_driut_pre_remediation_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
podman exec -i research-paper-recommender-postgres-1 pg_dump -U postgres research_papers | gzip > "${BACKUP_DIR}/research_papers.sql.gz"
sha256sum "${BACKUP_DIR}/research_papers.sql.gz" > "${BACKUP_DIR}/checksums.sha256"
```

### Step 2: Atomic Remediation Script Execution
A dedicated Python maintenance script (`scripts/remediate_driut_chronology.py`) reading `RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json` will:
1. Open a single database transaction.
2. Assert that exactly 175 alerts exist before modification.
3. Assert that exactly 90 records match the allowlist IDs.
4. Execute the deletion (or annotation).
5. Assert that exactly 85 alerts remain.
6. Commit transaction.

### Step 3: Rollback Procedure (Zero Downtime)
If any postcondition check fails:
```bash
gunzip -c "${BACKUP_DIR}/research_papers.sql.gz" | podman exec -i research-paper-recommender-postgres-1 psql -U postgres -d research_papers
```

---

## 8. Confirmation of Current Non-Mutation

During this audit task:
- **Zero** database records in PostgreSQL were inserted, modified, or deleted.
- **Zero** papers, saved papers, evidence records, or DRIUT alerts were modified.
- **Zero** source code files or configuration files were changed.
- All live services remain healthy and operational.

---

## 9. Final Audit Verdict

```
AUDIT COMPLETE — REMEDIATION PLAN READY FOR APPROVAL
```
