# TASK-18 — Native Application Runtime Migration & Recovery Report

**Project:** ResearchLens — NLP-Based Research Paper Recommendation System  
**Date:** 2026-10-11  
**Repository Path:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Git Branch:** `master`  
**Git Commit:** `c26cd6a16fd4de20a91cf10847ca6463dc2efc35`  
**Environment:** Fedora Linux 44 (x86_64), Hyprland (Wayland), Podman 5.x, Python 3.14 (Playwright 1.62.0), Node.js v22.x, Vite 5.4.5  
**Status:** **COMPLETE** (Native Runtime Restored, Verified, and Operational)

---

## 1. Executive Summary

TASK-18 successfully restores and validates the intended native development architecture for ResearchLens:
1. **Containerized Database:** PostgreSQL alone executes within the persistent Podman container (`research-paper-recommender-postgres-1`) with its original named volume (`research-paper-recommender_postgres_data`) bound to host port `127.0.0.1:5432`.
2. **Native Backend:** FastAPI executes natively on the Fedora host via Python virtual environment (`backend/venv`) on port `8000` with hot-reload enabled.
3. **Native Frontend:** React 18 + Vite executes natively on the Fedora host on port `3000` with HMR enabled.
4. **Data Invariance:** Zero database mutations, zero FAISS rebuilds, and zero metadata changes occurred. All 154 database papers, 31 DRIUT alerts, 5 users, and 155 FAISS vectors remain identical byte-for-byte.
5. **Decoupled Verification:** Avoided the stalled Antigravity `browser_subagent` by executing a standalone headless Python Playwright 1.62.0 smoke test in an isolated browser context, proving full UI mount, navigation accessibility, and zero page errors.

---

## 2. Git Baseline & Working-Tree Invariance

### Git Baseline State
- **Root:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`
- **Branch:** `master`
- **HEAD Commit:** `c26cd6a16fd4de20a91cf10847ca6463dc2efc35` (`phase-0-foundation`)

### Working-Tree Audit
In accordance with zero-mutation safety rules:
- **No destructive operations** (`git reset`, `git clean`, `git stash`, `git checkout`) were executed.
- **No commits** were created.
- All pre-existing 42 tracked modified/staged files and 41 untracked files (`??`) from Tasks 10–17 remain strictly preserved.
- `git diff --check` confirmed zero whitespace or corruption errors across active files.

---

## 3. Exact Recovery Commands Executed

The restoration proceeded through verified, bounded commands:

1. **PostgreSQL Container Recovery:**
   ```bash
   podman inspect research-paper-recommender-postgres-1 --format 'Name: {{.Name}} Mounts: {{json .Mounts}}'
   podman start research-paper-recommender-postgres-1
   ```
   *Result:* Verified container identity and volume attachment. Container transitioned from `exited (0)` to `Up (healthy)` on `127.0.0.1:5432->5432/tcp`.

2. **Native Environment Startup:**
   ```bash
   ./scripts/dev-start.sh
   ```
   *Result:* Executed cleanly (Exit Code 0). Verified PostgreSQL readiness on port 5432, launched native FastAPI backend via systemd user unit `researchlens-backend` on `0.0.0.0:8000`, and launched native React/Vite frontend via systemd user unit `researchlens-frontend` on `0.0.0.0:3000`.

3. **Status Probe:**
   ```bash
   ./scripts/dev-status.sh
   ```
   *Result:* Confirmed `ALL SERVICES OPERATIONAL (Native Dev + Containerized DB)`.

4. **Standalone Playwright Smoke Test:**
   ```bash
   python3 /home/tonystark/.gemini/antigravity-ide/brain/18c04529-3fd4-42bb-998b-b381cc640934/scratch/smoke_test.py
   ```
   *Result:* Headless Chromium launched in isolated context, loaded `http://localhost:3000`, verified DOM readiness, page title, navigation tabs, and verified `http://localhost:8000/api/v1/health`.

---

## 4. Container & Volume Identity Confirmation

| Property | Value | Verification Command / Evidence |
| :--- | :--- | :--- |
| **Container Name** | `research-paper-recommender-postgres-1` | `podman ps` -> Matched expected name |
| **Container Status** | `Up (healthy)` | `podman ps --filter name=research-paper-recommender-postgres-1` |
| **Exposed Port** | `127.0.0.1:5432 -> 5432/tcp` | `ss -tulpn` -> `LISTEN 127.0.0.1:5432` |
| **Persistent Volume** | `research-paper-recommender_postgres_data` | Volume type: `local`, attached to `/var/lib/postgresql/data` |
| **Host Storage Path** | `/home/tonystark/.local/share/containers/storage/volumes/research-paper-recommender_postgres_data/_data` | Verified via `podman inspect` |
| **Application Containers** | `research-paper-recommender-backend-1` (Exited 0)<br>`research-paper-recommender-frontend-1` (Exited 0) | Retained for rollback; NOT running; NOT deleted |

---

## 5. Runtime Architecture & Port Allocation

```
+---------------------------------------------------------------------------------+
|                               Fedora Host Machine                               |
|                                                                                 |
|  [Port 3000] React 18 + Vite Dev Server (Native Fedora)                         |
|              systemd user unit: researchlens-frontend (PID 8549)                |
|                                                                                 |
|  [Port 8000] FastAPI Application (Native Fedora)                                |
|              systemd user unit: researchlens-backend (PID 8489)                 |
|              Python Environment: backend/venv (Python 3.14)                     |
|                                                                                 |
|  [Port 5432] Podman Rootless Container                                         |
|              Container: research-paper-recommender-postgres-1                    |
|              Volume: research-paper-recommender_postgres_data                   |
+---------------------------------------------------------------------------------+
```

- **Listening Sockets Verified (`ss -tulpn`):**
  - `tcp LISTEN 127.0.0.1:5432`: Rootless Podman port forwarding to PostgreSQL container.
  - `tcp LISTEN 0.0.0.0:8000`: Native Uvicorn / Python FastAPI server.
  - `tcp LISTEN 0.0.0.0:3000`: Native Node.js / Vite development server.

---

## 6. HTTP & API Health-Check Verification

### 6.1 Backend Health Endpoint
```bash
curl -s http://localhost:8000/api/v1/health
```
```json
{
  "status": "ok",
  "service": "research-paper-recommender",
  "version": "0.1.0",
  "environment": "development",
  "database": "connected"
}
```
- **HTTP Status Code:** `200 OK`
- **Database Status:** `"database": "connected"`

### 6.2 Frontend Root Endpoint
```bash
curl -s -I http://localhost:3000
```
- **HTTP Status Code:** `200 OK`
- **Content-Type:** `text/html`
- **Vary:** `Origin`

### 6.3 Public Feature Endpoint Probe
```bash
curl -s "http://localhost:8000/api/v1/research/timeline?limit=2"
```
```json
{
  "topic": null,
  "start_year": null,
  "end_year": null,
  "total_papers_examined": 2,
  "total_dated_papers": 2,
  "total_undated_papers": 0,
  "status": "partial_coverage",
  "timeline": [
    {
      "year": 2027,
      "year_label": "2027",
      "paper_count": 1,
      "papers": [
        {
          "id": 918,
          "paper_id": "pubmed:42733543",
          "title": "Gas-propelled microneedles for..."
        }
      ]
    }
  ]
}
```
- **HTTP Status Code:** `200 OK`
- **Output:** Deterministic, evidence-grounded timeline response generated directly from native backend against containerized PostgreSQL.

### 6.4 Protected Endpoint Authentication Probe
```bash
curl -s http://localhost:8000/api/v1/papers/driut/status
```
```json
{
  "error": {
    "code": "HTTP_ERROR",
    "message": "Authentication required. Please provide a valid Bearer token."
  }
}
```
- **HTTP Status Code:** `401 Unauthorized`
- **Output:** Verified authentication enforcement and token security barriers operate as expected.

---

## 7. Standalone Playwright UI Smoke Test Results

Executed via isolated system Playwright 1.62.0 (`python3 /home/tonystark/.gemini/antigravity-ide/brain/18c04529-3fd4-42bb-998b-b381cc640934/scratch/smoke_test.py`):

| Test Metric | Observed Result | Verdict |
| :--- | :--- | :---: |
| **HTTP Navigation** | `http://localhost:3000` -> Status 200 OK | **PASS** |
| **Document ReadyState** | `document.readyState == "complete"` | **PASS** |
| **Page Title** | `'ResearchLens — Semantic Academic Discovery & Intelligence'` | **PASS** |
| **Top Headings** | `['ResearchLens', 'Live Academic Literature Observatory']` | **PASS** |
| **Main Navigation Items**| `['🔍 Explore', '📄 PDF Manuscript', '🔬 Evolution & Gaps', '🔖 Saved Library', '⚡ DRIUT Alerts', '🔑 Sign In']` | **PASS** |
| **UI Action Items** | Search modality tabs: `['💬 Research Query', '📝 Title & Abstract']` | **PASS** |
| **Backend Integration** | Client queried `api/v1/health` and displayed live status badge: `'Observatory Online'` | **PASS** |
| **Console Logs** | 7 entries: Vite connected, React Router v7 future flag warnings, expected 401s for unauthenticated background checks | **PASS** |
| **Page Errors** | 0 unhandled JavaScript exceptions | **PASS** |

---

## 8. Data Integrity & Invariance Verification

| Data Store | Entity / Artifact | Pre-Start Baseline | Post-Start Verification | Invariant Delta | Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **PostgreSQL** | `papers` table | 154 rows | 154 rows | 0 | **IDENTICAL** |
| **PostgreSQL** | `paper_evidence` table | 1 row | 1 row | 0 | **IDENTICAL** |
| **PostgreSQL** | `users` table | 5 rows | 5 rows | 0 | **IDENTICAL** |
| **PostgreSQL** | `saved_papers` table | 1 row | 1 row | 0 | **IDENTICAL** |
| **PostgreSQL** | `driut_alerts` table | 31 rows | 31 rows | 0 | **IDENTICAL** |
| **FAISS Index** | `research_index.faiss` | 155 vectors (dim 768) | 155 vectors (dim 768) | 0 | **IDENTICAL** |
| **FAISS Index** | SHA-256 Checksum | `7cee2bac09008...` | `7cee2bac09008...` | Byte-for-byte match | **IDENTICAL** |
| **FAISS Meta** | `papers_meta.json` | 155 entries | 155 entries | 0 | **IDENTICAL** |
| **FAISS Meta** | SHA-256 Checksum | `2c017fc8db3f5...` | `2c017fc8db3f5...` | Byte-for-byte match | **IDENTICAL** |

---

## 9. Script Review & Audit Findings

1. [`scripts/dev-start.sh`](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/scripts/dev-start.sh):
   - **Review:** Uses `systemd-run --user` for clean lifecycle management on Fedora, checks port availability before binding, and verifies `/health` endpoints with bounded timeouts.
   - **Execution:** Ran flawlessly without modification.
2. [`scripts/dev-status.sh`](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/scripts/dev-status.sh):
   - **Review:** Probes container health, systemd units / PIDs, and HTTP ports (5432, 8000, 3000) with safe curl flags. Never leaks credentials.
   - **Execution:** Accurately reported `ALL SERVICES OPERATIONAL`.
3. [`scripts/dev-stop.sh`](file:///home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/scripts/dev-stop.sh):
   - **Review:** Stops native frontend and backend units/PIDs only. Strictly avoids stopping or deleting the PostgreSQL container or volume.
   - **Status:** Inspected and retained without modification. Per task instructions, the services remain running.

---

## 10. Known Limitations & Disclosures

1. **Antigravity Browser Agent Blockage:**
   - Antigravity's internal `browser_subagent` tool relies on a bundled Go Playwright binary (`~/.cache/ms-playwright-go/1.57.0`) that stalled indefinitely.
   - In accordance with safety instructions, the built-in browser agent was completely bypassed in favor of a standalone Python script utilizing the host's installed Python Playwright 1.62.0.
2. **Catalog vs. Vector Invariance:**
   - The PostgreSQL catalog contains 154 papers, while the FAISS index contains 155 vectors. As documented in TASK-16A, the 1 vector delta represents an orphan test fixture (`test:t15:cand_ext`) generated during TASK-15 DRIUT integration testing. 100% of committed catalog papers (154/154) are mapped and indexed.
3. **Container Rollback Availability:**
   - Previous application containers (`research-paper-recommender-backend-1` and `research-paper-recommender-frontend-1`) remain in `Exited (0)` state and were intentionally not deleted.

---

## 11. Task Completion Verdict

**VERDICT: TASK-18 IS COMPLETE.**

- Target native development architecture is fully restored and operational.
- PostgreSQL is containerized in Podman with existing persistent storage and healthy connectivity.
- Native FastAPI and React/Vite development processes are serving traffic on ports 8000 and 3000.
- All verification gates passed.

---

## 12. Recommended Immediate Next Task

- **Recommended Task:** **TASK-19 — Native Playwright Verification Sprint & UI Validation**
- **Objective:** Utilize standalone Python Playwright 1.62.0 to perform end-to-end multi-page testing across:
  1. Explore & Semantic Recommendation Flow
  2. PDF Manuscript Upload & Extraction Flow
  3. Evolution Timeline & Relationship Graph Navigation
  4. Candidate Research-Gap Explorer
  5. Grounded Research Assistant Interactivity
  6. Side-by-Side Paper Comparison Matrix
  7. Saved Reading Library & User Isolation
  8. Browser Console Error Cleanliness & Network Status Code Validation
