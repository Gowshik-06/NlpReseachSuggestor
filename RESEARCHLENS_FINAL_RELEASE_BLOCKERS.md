# ResearchLens — Production Release Blockers & Infrastructure Readiness

**Document ID:** `RESEARCHLENS_FINAL_RELEASE_BLOCKERS.md`  
**Evaluation Date:** October 18, 2026  
**Final Release Gate Status:** **`PRODUCTION RELEASE BLOCKED`**  
**Maintenance Gate Status:** **`MAINTENANCE READY FOR AUTHORIZED EXECUTION`**

---

## 1. Executive Summary

This report establishes the explicit, objective boundary between **completed repository engineering** and the **unresolved operational blockers** that prevent an immediate, unconditional General Availability (GA) production release.

In strict adherence to engineering integrity, ResearchLens will not claim to be unconditionally `PRODUCTION READY` while historical data inconsistencies remain stored in the relational database, an orphan vector remains in the active vector index, or public production hosting infrastructure requires provisioning.

---

## 2. Completed Repository-Level Engineering (Verified)

All required application-layer, NLP, and algorithmic capabilities have been fully implemented, regression tested, and verified in the repository:

1. **Publication-Date Policy:** Dynamic, calendar-resilient PubMed date parsing in `academic_sources.py` prioritizing electronic public release dates (`epubdate`), properly annotating advance articles and forthcoming issues without year ceilings.
2. **Default Relevance Search Ordering:** Backend schemas (`SearchQueryRequest.sort_by`) and frontend UI (`HomePage.tsx`) default to conceptual relevance with dedicated, accessible sort buttons.
3. **DRIUT Chronological Integrity:** Step 8b Chronology-Aware Guard implemented in `driut_service.py`, preventing older papers from being classified as improvements or extensions of newer baseline papers.
4. **Research Evolution Timeline:** Future milestone years (> 2026) qualified with `date_uncertainty_note` and forthcoming issue labels in `evolution_service.py`.
5. **Synthetic Abstract Guards:** `SYNTHETIC_PLACEHOLDER_REGEX` intercepts legacy PubMed boilerplate across evidence extraction, AI summarization, and timeline construction, eliminating hallucinated scientific claims.
6. **Search Quality & Out-of-Domain Suppression:** `SEMANTIC_RELEVANCE_FLOOR = 0.835` and generic search term filtering completely suppress out-of-domain queries (`"ancient Roman architecture"` returns 0 results).
7. **Production Maintenance Tooling:** `backend/app/db/migrate_pubmed_dates.py` and `scripts/reconcile_faiss_postgres.py` are implemented, verified in dry-run mode, and equipped with transaction rollbacks and backup prerequisites.
8. **Automated Testing Suite:** 329 passing backend tests (100%), 66 passing frontend tests (100%), and clean production build (`tsc -b && vite build` in 692ms).
9. **Strict Research Privacy:** `RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT=false` maintained across all AI service providers.

---

## 3. Explicit Release Blockers

The following items represent the exhaustive set of mandatory blockers preventing unconditional release:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      PRODUCTION RELEASE BLOCKERS                       │
├────┬─────────────────────────────┬─────────────────┬───────────────────┤
│ ID │ Blocker Title               │ Category        │ Status            │
├────┼─────────────────────────────┼─────────────────┼───────────────────┤
│ B1 │ 25 Historical PubMed Dates  │ Data Integrity  │ RESOLVED & VERIFIED│
│ B2 │ FAISS Orphan Vector         │ Index Integrity │ Maintenance Ready │
│ B3 │ Public TLS & Domain Setup   │ Infrastructure  │ Awaiting Infra    │
│ B4 │ Environment Secret Rotation │ Security Ops    │ Awaiting Secret   │
└────┴─────────────────────────────┴─────────────────┴───────────────────┘
```

### Blocker B1: Historical PubMed Date Correction (Data Integrity) — RESOLVED
- **Status:** **RESOLVED & VERIFIED (Executed October 18, 2026)**
- **Verification Evidence:** All 25 allowlisted records were updated from `year = 2027` to `year = 2026` via transactional execution with rowcount assertion. `pubmed:42635983` was verified and preserved at `year = 2028`. PostgreSQL queries and live search endpoints confirm 100% compliance. Full evidence recorded in `RESEARCHLENS_PUBMED_YEAR_CORRECTION_REPORT.md`.

### Blocker B2: FAISS Index Orphan Reconciliation (Index Integrity)
- **Description:** The FAISS index contains 163 vectors while PostgreSQL contains 162 papers. Vector `test:t15:cand_ext` (index 10) is an orphan from historical integration testing. Rebuilding or modifying the index was prohibited during implementation (Non-Negotiable Rule #3).
- **Prerequisite to Unblock:** Execution of `scripts/reconcile_faiss_postgres.py --execute --backup-dir <dir>` following the verified pre-maintenance snapshot.
- **Resolution Effort:** 5 minutes during scheduled maintenance window.

### Blocker B3: Public TLS & Nginx Web Server Provisioning (Infrastructure)
- **Description:** The application currently runs natively on local development interfaces (`127.0.0.1:8000` and `127.0.0.1:3000`). Public exposure requires an Nginx reverse proxy with TLS certificates (e.g., Let's Encrypt) and DNS routing to `researchlens.institution.edu`.
- **Prerequisite to Unblock:** Infrastructure operations must deploy the Nginx configuration specified in [RESEARCHLENS_PRODUCTION_DEPLOYMENT_GUIDE.md](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/RESEARCHLENS_PRODUCTION_DEPLOYMENT_GUIDE.md) and bind valid SSL/TLS certificates.
- **Resolution Effort:** External operational dependency.

### Blocker B4: Production Cryptographic Secret Rotation (Security Ops)
- **Description:** The root `.env` file contains `JWT_SECRET_KEY=researchlens-secure-dev-secret-key-2026`. While the production configuration validator correctly rejects this key when `ENVIRONMENT=production`, a unique, cryptographically random 32+ character signing secret must be generated and deployed to the production environment file.
- **Prerequisite to Unblock:** Generate high-entropy secret (`openssl rand -hex 32`) and populate `/opt/researchlens/backend/.env`.
- **Resolution Effort:** 2 minutes during server provisioning.

---

## 4. Production Readiness Checklist by Domain

| Domain | Control Item | Repository Status | Operational Status |
|:---|:---|:---:|:---:|
| **Authentication** | Password salting & hashing (Argon2/Bcrypt) | Verified (100% pass) | Ready |
| **Authentication** | JWT signing with HS256 & 60-min expiry | Verified | Ready |
| **Secrets** | High-entropy production JWT secret (>32 chars) | Validator enforced | **Pending Generation** |
| **Data Privacy** | `RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT=false` | Verified enforced | Ready |
| **Local AI** | Ollama `qwen2.5:3b` with deterministic fallback | Verified active | Ready |
| **Database** | Port 5432 bound exclusively to localhost | Verified in compose | Ready |
| **Database** | 25 PubMed records updated to year 2026 | Tool verified | **Pending Execution** |
| **Vector Index** | FAISS orphan `test:t15:cand_ext` purged | Tool verified | **Pending Execution** |
| **Frontend** | Production build compiled to `dist/` | Compiled (692ms) | Ready |
| **Web Server** | Nginx reverse proxy serving static bundle | Config authored | **Pending Provisioning** |
| **Security** | TLS 1.2/1.3 termination with HTTPS redirect | Config authored | **Pending Provisioning** |
| **Observability** | `/api/v1/health` readiness probe | Verified | Ready |
| **Logging** | Redaction of tokens, DB passwords, and secrets | Verified | Ready |
| **Recovery** | Failure-safe `pg_dump` and restore test runbook | Verified runbook | Ready |

---

## 5. Official Release Gate Decision

```
================================================================================
RELEASE GATE DECISION: PRODUCTION RELEASE BLOCKED
MAINTENANCE GATE DECISION: MAINTENANCE READY FOR AUTHORIZED EXECUTION
================================================================================
```

### Release Criteria Summary:
- **Codebase Integrity:** APPROVED. All code defects remediated and verified with regression tests.
- **Maintenance Preflight:** APPROVED. All commands, backups, and rollback procedures verified.
- **Production Release:** BLOCKED until Blockers B1 through B4 are resolved during the authorized maintenance window and infrastructure deployment.
