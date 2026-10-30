# RESEARCHLENS TASK 3 — CORS CONFIGURATION ALIGNMENT REPORT

## 1. Executive Summary & Objective

**Task:** Configure the ResearchLens FastAPI backend to accept browser requests from both supported local frontend origins:
- `http://localhost:3000`
- `http://127.0.0.1:3000`

**Scope & Safety Adherence:**
- Repository: `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`
- Preserved all existing application behavior unrelated to CORS.
- Zero modifications, writes, or resets to PostgreSQL, FAISS index, or persistent storage.
- No Ollama installation; no model weights downloaded.
- Authentication, cookies, credentials, and authorization remained strictly intact.
- Wildcard CORS origins (`*`) were **not** used; explicit allowlists are strictly enforced.
- No destructive Git commands, stashes, resets, or commits.
- Healthy services preserved; backend reloaded seamlessly via native uvicorn hot-reload watcher (`WatchFiles`). PostgreSQL container was untouched.
- Zero secrets or credentials exposed.

**Result:** Both `http://localhost:3000` and `http://127.0.0.1:3000` now receive valid CORS preflight headers (`200 OK`, `access-control-allow-origin`, `access-control-allow-credentials: true`, `access-control-allow-methods`), while unapproved origins (e.g. `http://evil.com`, `http://attacker.org:3000`) are rejected (`400 Bad Request`, no `access-control-allow-origin` header).

---

## 2. Root Cause Analysis

1. **Origin Disparity in W3C Same-Origin Policy (RFC 6454):**
   In web browsers, `localhost` (hostname) and `127.0.0.1` (IPv4 loopback literal) are treated as distinct origins. Browser requests originating from a web page loaded at `http://127.0.0.1:3000` making requests to `http://localhost:8000` are cross-origin requests requiring CORS authorization.
2. **Hardcoded Single-Origin Configuration:**
   - In `backend/app/core/config.py`, the default setting was:
     `CORS_ORIGINS: List[str] = ["http://localhost:3000"]`
   - In `backend/.env`, `CORS_ORIGINS` was set to `["http://localhost:3000","http://localhost:5173"]` (missing `http://127.0.0.1:3000`).
   - In `.env`, `.env.example`, and `docker-compose.yml`, `CORS_ORIGINS` was set to `["http://localhost:3000"]`.
3. **Preflight Blockade:**
   When browser clients, Playwright tests, or local tools accessed ResearchLens via `http://127.0.0.1:3000`, browser preflight `OPTIONS` requests to `/api/v1/...` were rejected by FastAPI's `CORSMiddleware` with `400 Bad Request ("Disallowed CORS origin")`, causing frontend API calls to fail before execution.

---

## 3. Files Changed & Rationale

### 1. `backend/app/core/config.py`
- **Change:**
  - Added `http://127.0.0.1:3000` to the default `CORS_ORIGINS` list:
    ```python
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    ```
  - Added a Pydantic `field_validator` for `CORS_ORIGINS` with `mode="before"` (`assemble_cors_origins`).
- **Rationale:** Ensures that `CORS_ORIGINS` reliably parses JSON array strings (`'["http://localhost:3000", ...]'`), comma-separated strings (`"http://localhost:3000,http://127.0.0.1:3000"`), and standard Python lists without raising `SettingsError`.

### 2. `backend/.env`
- **Change:**
  - Updated `CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000","http://localhost:5173"]`
- **Rationale:** Aligns active native backend runtime configuration, preserving existing development ports while admitting `127.0.0.1:3000`.

### 3. `.env` & `.env.example`
- **Change:**
  - Updated `CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]`
- **Rationale:** Synchronizes repository root environment templates and developer examples.

### 4. `docker-compose.yml`
- **Change:**
  - Updated `CORS_ORIGINS: '["http://localhost:3000", "http://127.0.0.1:3000"]'`
- **Rationale:** Aligns containerized deployment configurations with the dual local origins.

### 5. `backend/tests/test_cors_configuration.py` (New Automated Test Suite)
- **Change:** Created 7 comprehensive automated tests verifying preflights, rejection of unapproved origins, simple GET header behavior, auth/authz invariants, and settings parsing.
- **Rationale:** Guarantees permanent regression protection against future origin drift.

---

## 4. Exact Allowed-Origin Behavior

| Request Type | Origin | Access-Control-Allow-Origin | Access-Control-Allow-Credentials | HTTP Status |
| :--- | :--- | :--- | :--- | :--- |
| `OPTIONS` preflight | `http://localhost:3000` | `http://localhost:3000` | `true` | `200 OK` |
| `OPTIONS` preflight | `http://127.0.0.1:3000` | `http://127.0.0.1:3000` | `true` | `200 OK` |
| `OPTIONS` preflight | `http://evil.com` | *None* | *N/A* | `400 Bad Request` |
| `OPTIONS` preflight | `http://attacker.org:3000`| *None* | *N/A* | `400 Bad Request` |
| `GET` request | `http://localhost:3000` | `http://localhost:3000` | `true` | `200 OK` |
| `GET` request | `http://127.0.0.1:3000` | `http://127.0.0.1:3000` | `true` | `200 OK` |
| `GET` request | `http://evil.com` | *None* | `true` | `200 OK` (No CORS access) |

---

## 5. Test Commands, Exit Codes, and Results

All tests executed using the project Python virtual environment (`backend/venv/bin/pytest`).

### 1. Dedicated CORS Test Suite
- **Command:** `venv/bin/pytest tests/test_cors_configuration.py -v`
- **Exit Code:** `0`
- **Results:**
  - `test_cors_preflight_localhost_3000`: **PASSED**
  - `test_cors_preflight_127_0_0_1_3000`: **PASSED**
  - `test_cors_preflight_unapproved_origins_rejected`: **PASSED**
  - `test_cors_simple_requests_header_behavior`: **PASSED**
  - `test_auth_and_authorization_behavior_unchanged`: **PASSED**
  - `test_health_endpoint_responds_successfully`: **PASSED**
  - `test_cors_settings_parsing_formats`: **PASSED**
  - **Summary:** 7 passed in 0.12s

### 2. Comprehensive Regression Suite (Tasks 1A, 1B, 2, and 3)
- **Command:** `venv/bin/pytest tests/test_cors_configuration.py tests/test_isolation_verification.py tests/test_local_search_correctness.py tests/test_search_ingestion_decoupling.py -v`
- **Exit Code:** `0`
- **Results:**
  - `tests/test_cors_configuration.py`: 7 passed
  - `tests/test_isolation_verification.py`: 7 passed
  - `tests/test_local_search_correctness.py`: 6 passed
  - `tests/test_search_ingestion_decoupling.py`: 9 passed
  - **Summary:** 29 passed in 8.35s

---

## 6. Live Service Probing Evidence

Direct read-only HTTP probes against the live running FastAPI native backend (`http://localhost:8000`) and Vite frontend (`http://localhost:3000`) confirm active behavior:

```bash
# 1. Backend Health Check
HTTP/1.1 200 OK
{"status":"ok","service":"research-paper-recommender","version":"0.1.0","environment":"development","database":"connected"}

# 2. Preflight for http://localhost:3000
HTTP/1.1 200 OK
access-control-allow-origin: http://localhost:3000
access-control-allow-credentials: true
access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT, QUERY

# 3. Preflight for http://127.0.0.1:3000
HTTP/1.1 200 OK
access-control-allow-origin: http://127.0.0.1:3000
access-control-allow-credentials: true
access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT, QUERY

# 4. Preflight for Unapproved Origin http://evil.com
HTTP/1.1 400 Bad Request
(access-control-allow-origin header NOT present)

# 5. Simple GET for http://127.0.0.1:3000
HTTP/1.1 200 OK
access-control-allow-origin: http://127.0.0.1:3000

# 6. Simple GET for http://evil.com
HTTP/1.1 200 OK
(access-control-allow-origin header NOT present)

# 7. Frontend Status
HTTP/1.1 200 OK on http://localhost:3000
```

---

## 7. Evidence of Database and FAISS Protection

Direct, read-only queries against live Podman PostgreSQL (`research_papers`) and live FAISS index files confirmed zero pollution:

| Resource | Baseline | After Task 3 Tests & Probes | Status |
| :--- | :--- | :--- | :--- |
| PostgreSQL `users` count | 6 | 6 | **Unchanged (0 new rows)** |
| PostgreSQL `papers` count | 158 | 158 | **Unchanged (0 new rows)** |
| PostgreSQL `saved_papers` count | 1 | 1 | **Unchanged (0 new rows)** |
| PostgreSQL `driut_alerts` count | 31 | 31 | **Unchanged (0 new rows)** |
| PostgreSQL `paper_evidence` count | 1 | 1 | **Unchanged (0 new rows)** |
| FAISS `research_index.faiss` SHA-256 | `e91a9e852bde...` | `e91a9e852bde...` | **Byte-for-byte identical** |
| FAISS `papers_meta.json` SHA-256 | `a5f431dc3261...` | `a5f431dc3261...` | **Byte-for-byte identical** |

**Verified Existing User Records (100% Intact):**
- `(1, 'default_user', 'default_user@research.local')`
- `(12, 'test_user', 'test_user@test.local')`
- `(75, 'testuser_task10', 'testuser_task10@example.com')`
- `(110, 'evidence_test_user', 'evidence_user@test.local')`
- `(111, 'isolated_user_b', 'user_b@test.local')`
- `(275, 'test_asst_user', 'test_asst_user@example.com')`

---

## 8. Non-Negotiable Safety Invariants Affirmation

1. **Database & Storage Invariants:** Zero database records created, modified, or deleted. No migrations, reseeding, truncations, or FAISS rebuilds.
2. **Authentication Security:** No wildcard origins permitted; authentication and authorization remain strictly enforced (unauthenticated access returns `401 Unauthorized`).
3. **No Ollama / Models:** No Ollama installation initiated; no model weights downloaded.
4. **Git State:** Untracked files and tracked modifications preserved; zero commits, stashes, or resets.
5. **Services Lifecycle:** Uvicorn hot-reloaded automatically via `WatchFiles`; Podman PostgreSQL container was never restarted.
6. **Task Scope Boundaries:** Task 3 is fully finished. Task 4 has not been started.
