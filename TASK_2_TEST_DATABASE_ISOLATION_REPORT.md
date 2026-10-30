# RESEARCHLENS TASK 2 — TEST DATABASE ISOLATION & ZERO-POLLUTION FIXTURES REPORT

## 1. Executive Summary & Objective

**Task:** Audit and correct the test configuration for ResearchLens so automated tests cannot accidentally write test users, papers, saved papers, evidence, or DRIUT alerts into the persistent PostgreSQL database (`research_papers`) or mutate the production FAISS index and metadata.

**Scope:**
- Repository: `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`
- Scope constraints: Strict adherence to Task 2 only; zero destructive database operations; zero record cleanup without separate explicit authorization; no migrations; no FAISS rebuilds; no Ollama installation; no Git commits/stashes/resets.

**Result:**
- **Zero Pollution Enforced:** Test runs now automatically redirect to an isolated temporary SQLite database (`sqlite:////tmp/researchlens_test_isolated.db`) and an isolated temporary FAISS directory (`/tmp/researchlens_test_faiss`).
- **Fail-Closed Shield:** Attempting to run automated tests against the protected live database (`research_papers`) raises an immediate, unhandled `RuntimeError` before any connection or write can occur.
- **Verification Suites Executed & Passed (Exit Code 0):**
  - `backend/tests/test_isolation_verification.py`: 7/7 passed
  - `backend/tests/test_local_search_correctness.py` (Task 1A regression): 6/6 passed
  - `backend/tests/test_search_ingestion_decoupling.py` (Task 1B regression): 9/9 passed
  - Combined suite: 22/22 passed in 8.47s
  - `backend/tests/test_papers_api.py`: 16/16 passed
  - `backend/tests/test_health.py` & `backend/tests/test_rate_limiter.py`: 9/9 passed
- **Live Invariants Preserved:**
  - PostgreSQL users count: **6** (IDs 1, 12, 75, 110, 111, 275 - 100% intact, no deletions, no new rows)
  - PostgreSQL papers count: **158** (100% intact)
  - FAISS index SHA-256: `e91a9e852bde2ade4555e5b45ae3477abca612f6909b2bd8fcacfdc79952ae30` (100% unchanged)
  - FAISS metadata SHA-256: `a5f431dc3261c1da8290e3822773e21f439b9a0e216e418660a7ae9bafa7f4e8` (100% unchanged)
  - Native services (`http://localhost:8000/api/v1/health` and `http://localhost:3000`) verified fully healthy and operational.

---

## 2. Root Cause Analysis: Persistent Test-User Leaks

An audit of the existing codebase and database history revealed why test records (such as `testuser_task10`, `isolated_user_b`, `evidence_test_user`, and `test_asst_user`) previously leaked into the persistent PostgreSQL database:

1. **Unconditional Live Database Binding at Import Time:**
   `backend/app/db/session.py` initialized SQLAlchemy's `engine` and `SessionLocal` at module import time using `settings.DATABASE_URL`. Unless overridden prior to import, `settings.DATABASE_URL` resolved to the persistent database (`postgresql+psycopg2://postgres:postgres@localhost:5432/research_papers`).
2. **Missing Database Isolation in Pytest Configuration:**
   `backend/tests/conftest.py` previously only contained a single rate-limiter fixture (`reset_limiter_state`). It had no test database overrides, no database URL redirection, no database mocking, and no fail-closed guard.
3. **Integration Test Fixtures Committed Directly to `SessionLocal`:**
   Integration test modules (such as `test_auth_and_isolation.py`, `test_driut_intelligence.py`, `test_embedding_and_sync.py`, `test_evidence_extraction.py`, and `test_papers_api.py`) directly called `db = SessionLocal()`, inserted real test records, and invoked `db.commit()`.
4. **Fragile Teardown Blocks:**
   The integration tests relied on post-test teardown logic (`finally:` blocks or fixture post-yield blocks) to delete the inserted test records. Whenever a test failed assertion, raised an unhandled exception, timed out, or was aborted by SIGINT/SIGTERM, the teardown block was bypassed or failed, permanently stranding committed test users and papers in the live PostgreSQL catalog.
5. **Direct Mutation of Production FAISS Files:**
   `backend/app/services/vector_index.py` hardcoded `INDEX_DIR` to `backend/data/processed/faiss`. Tests that called `faiss_index.add_papers()` or reloaded the index directly modified the production `.faiss` and `.json` files on disk, relying on error-prone teardown routines that read file bytes into memory and wrote them back on exit.

---

## 3. Audit Findings: Risky Fixtures & Test Paths

| File | Risk Identified | Mechanism of Pollution |
| :--- | :--- | :--- |
| `backend/tests/test_papers_api.py` | `setup_test_database` fixture | Inserted `default_user` and `test_user` into `SessionLocal()`, committed to live DB. Read production FAISS bytes into memory and wrote them back during teardown. |
| `backend/tests/test_auth_and_isolation.py` | Per-test user creation | Committed `isolated_user_a`, `isolated_user_b` directly to database. Leaked `isolated_user_b` when run against live DB. |
| `backend/tests/test_driut_scheduler.py` | `setup_driut_test_db` module fixture | Created and committed `user_alpha_driut` and `user_beta_driut` into live DB. Executed `SELECT pg_try_advisory_lock(:key)`. |
| `backend/tests/test_evidence_extraction.py` | Module fixture | Created and committed `evidence_test_user` and evidence records into live DB. |
| `backend/tests/test_research_assistant.py` | Module fixture | Created and committed `test_asst_user` into live DB. |
| `backend/app/services/vector_index.py` | Hardcoded production paths | `INDEX_PATH` and `METADATA_PATH` directly pointed to production files with no environment override mechanism. |

---

## 4. Test Isolation Design & Implementation

To solve this systematically and prevent test pollution under all circumstances, a three-tier isolation architecture was implemented:

### Tier 1: Early Test Environment Pre-Configuration (`conftest.py`)
In `backend/tests/conftest.py`, before any application module (`app.db.session`, `app.main`, `app.services`) is imported:
- If `DATABASE_URL` is unset or points to `research_papers`, it is forcefully set to `sqlite:////tmp/researchlens_test_isolated.db`.
- `FAISS_INDEX_DIR`, `FAISS_INDEX_PATH`, and `FAISS_METADATA_PATH` are directed to `/tmp/researchlens_test_faiss`.
- `get_settings.cache_clear()` is called to flush any cached settings singleton.
- SQLite schema tables are prepared via `Base.metadata.create_all(bind=engine)` in a session-scoped fixture and cleaned up on session exit.

### Tier 2: Fail-Closed Protection Guard (`session.py` & `conftest.py`)
In `backend/app/db/session.py`:
- Added `is_protected_live_database(url_str)`: Identifies if any database URL targets `research_papers` (without an explicit `test_isolated` or `disposable` qualification).
- Added `assert_safe_test_database(url_str)`: Inspects `sys.modules` and `PYTEST_CURRENT_TEST`. If automated tests are active and the target is `research_papers`, it immediately raises:
  `RuntimeError: FAIL-CLOSED PROTECTION: Automated test execution cannot bind to the persistent application database 'research_papers'. Tests must use an isolated test database.`
- In `conftest.py`, an autouse fixture `verify_live_database_shield` executes before every single test to guarantee the active database engine is never pointing to `research_papers`.

### Tier 3: Isolated Dependency Overrides & FAISS Override (`conftest.py` & `vector_index.py`)
- In `backend/tests/conftest.py`, `override_app_db_dependency` automatically overrides FastAPI's `get_db` dependency in `app.dependency_overrides` so that `TestClient(app)` requests resolve to the isolated SQLite session rather than any persistent connection.
- In `backend/app/services/vector_index.py`, `INDEX_DIR`, `INDEX_PATH`, and `METADATA_PATH` check `os.environ.get("FAISS_INDEX_DIR")`, etc., allowing complete relocation to temporary directories during tests.
- Added `reset_faiss_index_instance()` to cleanly reset the in-memory singleton between test runs.

---

## 5. Files Changed & Rationale

### 1. `backend/app/db/session.py`
- **Changes:**
  - Added `is_protected_live_database(url_str: str) -> bool`
  - Added `assert_safe_test_database(url_str: str) -> None`
  - Added fail-closed check at module load: `assert_safe_test_database(settings.DATABASE_URL)`
  - Added SQLite thread-safety handling: `connect_args={"check_same_thread": False}` and `pool_pre_ping=False` when using SQLite under tests.
- **Rationale:** Ensures that automated test execution can never bind to the live database under any circumstances, failing loudly and immediately before any write.

### 2. `backend/app/services/vector_index.py`
- **Changes:**
  - Added environment variable overrides for `INDEX_DIR`, `INDEX_PATH`, and `METADATA_PATH`.
  - Added `reset_faiss_index_instance()` to clear the global singleton `_FAISS_INDEX_INSTANCE`.
- **Rationale:** Prevents tests from reading or mutating the production FAISS index files on disk and eliminates cross-test in-memory state pollution.

### 3. `backend/tests/conftest.py`
- **Changes:**
  - Pre-configures `DATABASE_URL` and `FAISS_INDEX_DIR` before application module imports.
  - Added `setup_isolated_test_suite` session fixture (creates schema in isolated SQLite, cleans up temporary files on exit).
  - Added `reset_limiter_state` autouse fixture.
  - Added `verify_live_database_shield` autouse fixture.
  - Added `override_app_db_dependency` autouse fixture for FastAPI `TestClient`.
  - Added `db_session` fixture.
- **Rationale:** Provides zero-pollution isolation for all pytest runs by default without requiring test-by-test boilerplate.

### 4. `backend/tests/test_isolation_verification.py` (New Test File)
- **Changes:** Created comprehensive verification test suite verifying all 9 isolation requirements.
- **Rationale:** Provides verifiable proof that test sessions are isolated, commits do not reach PostgreSQL, FAISS mutations do not reach disk, fail-closed guards trigger properly, and existing endpoints remain intact.

---

## 6. Configuration & Fixture File Hashes

| File | SHA-256 Hash |
| :--- | :--- |
| `backend/app/db/session.py` | `ddba5228736a1cb0e06ba71e2a09a57cf327c107395ffc7ce8084b06add10040` |
| `backend/app/services/vector_index.py` | `76e286f8837f025f4d3e7ab8b989b21821631e6b3e37b1cbdec8a702c7dbedf0` |
| `backend/tests/conftest.py` | `34dc5a466a619430f72be8fd593a4a60a381da97a83d2ce7eef9a1a1ff439d47` |
| `backend/tests/test_isolation_verification.py` | `6d0a17eaa0db94dec1d75a9e1f6ace54032dae334ac8375d9f7efdc5c8c2a381` |

---

## 7. Commands & Actual Test Outcomes

All tests executed using the project Python virtual environment (`backend/venv/bin/pytest`).

### Suite 1: Isolation Verification Suite
- **Command:** `venv/bin/pytest tests/test_isolation_verification.py -v`
- **Exit Code:** `0`
- **Database Target:** `sqlite:////tmp/researchlens_test_isolated.db`
- **Results:**
  - `test_test_session_uses_intended_isolated_database`: **PASSED**
  - `test_user_insertion_and_commit_does_not_persist_to_live_db`: **PASSED**
  - `test_paper_saved_evidence_driut_fixtures_do_not_pollute_live_db`: **PASSED**
  - `test_search_does_not_invoke_live_external_providers_or_persist`: **PASSED**
  - `test_faiss_tests_cannot_mutate_production_index`: **PASSED**
  - `test_protected_database_target_fails_closed_before_writes`: **PASSED**
  - `test_running_application_endpoints_remain_healthy_and_unchanged`: **PASSED**
  - **Summary:** 7 passed in 7.84s

### Suite 2: Regression Suites (Tasks 1A & 1B)
- **Command:** `venv/bin/pytest tests/test_local_search_correctness.py tests/test_search_ingestion_decoupling.py -v`
- **Exit Code:** `0`
- **Database Target:** `sqlite:////tmp/researchlens_test_isolated.db`
- **Results:**
  - `tests/test_local_search_correctness.py`: 6 passed
  - `tests/test_search_ingestion_decoupling.py`: 9 passed
  - **Summary:** 15 passed in 8.20s

### Suite 3: Combined Full Verification Suite
- **Command:** `venv/bin/pytest tests/test_isolation_verification.py tests/test_local_search_correctness.py tests/test_search_ingestion_decoupling.py -v`
- **Exit Code:** `0`
- **Database Target:** `sqlite:////tmp/researchlens_test_isolated.db`
- **Summary:** 22 passed in 8.47s

### Suite 4: Paper API Integration Suite
- **Command:** `venv/bin/pytest tests/test_papers_api.py -v`
- **Exit Code:** `0`
- **Database Target:** `sqlite:////tmp/researchlens_test_isolated.db`
- **Summary:** 16 passed in 11.40s

### Suite 5: Health & Rate Limiter Suites
- **Command:** `venv/bin/pytest tests/test_health.py tests/test_rate_limiter.py -v`
- **Exit Code:** `0`
- **Database Target:** `sqlite:////tmp/researchlens_test_isolated.db`
- **Summary:** 9 passed in 0.14s

---

## 8. Evidence of Live Database and FAISS Protection

Direct, read-only queries executed against the live Podman PostgreSQL database (`research_papers`) and live FAISS filesystem before and after all test suites confirmed zero pollution:

### Live PostgreSQL Invariant Verification

| Table | Baseline Before Tests | Count After All Tests | Status |
| :--- | :--- | :--- | :--- |
| `users` | 6 | 6 | **Unchanged (0 new rows)** |
| `papers` | 158 | 158 | **Unchanged (0 new rows)** |
| `saved_papers` | 1 | 1 | **Unchanged (0 new rows)** |
| `driut_alerts` | 31 | 31 | **Unchanged (0 new rows)** |
| `paper_evidence` | 1 | 1 | **Unchanged (0 new rows)** |

**Verified Existing User Records (100% Intact):**
- `(1, 'default_user', 'default_user@research.local')`
- `(12, 'test_user', 'test_user@test.local')`
- `(75, 'testuser_task10', 'testuser_task10@example.com')`
- `(110, 'evidence_test_user', 'evidence_user@test.local')`
- `(111, 'isolated_user_b', 'user_b@test.local')`
- `(275, 'test_asst_user', 'test_asst_user@example.com')`

### Live FAISS Index & Metadata Invariant Verification

| File | SHA-256 Checksum | Paper Count | Status |
| :--- | :--- | :--- | :--- |
| `research_index.faiss` | `e91a9e852bde2ade4555e5b45ae3477abca612f6909b2bd8fcacfdc79952ae30` | 159 vectors | **Byte-for-byte identical** |
| `papers_meta.json` | `a5f431dc3261c1da8290e3822773e21f439b9a0e216e418660a7ae9bafa7f4e8` | 2 metadata records | **Byte-for-byte identical** |

### Live Application Health Check
- `http://localhost:8000/api/v1/health`: `{"status":"ok","service":"research-paper-recommender","version":"0.1.0","environment":"development","database":"connected"}`
- `http://localhost:3000`: `HTTP/1.1 200 OK`

---

## 9. Remaining PostgreSQL-Specific Test Gaps

During the audit, the following test suite was identified as requiring PostgreSQL-specific features:
- `backend/tests/test_driut_scheduler.py`: Exercises PostgreSQL advisory locks via raw SQL (`SELECT pg_try_advisory_lock(:key)`). SQLite does not support advisory locks and will raise an operational error if invoked.
- **Status:** In strict compliance with Task 2 safety rules, `test_driut_scheduler.py` was **documented and left unexecuted** against the live application database. It will remain unexecuted until a dedicated, isolated PostgreSQL test container or separate disposable database instance (e.g. `research_papers_test_isolated`) is provisioned.
- No production schemas, tables, or configurations were modified to accommodate this test.

---

## 10. Non-Negotiable Safety Invariants Affirmation

1. **Database Preservation:** All 6 users and 158 papers in PostgreSQL were preserved intact. No records were deleted, cleaned up, updated, or truncated.
2. **No Migrations or Reseeding:** No Alembic migrations, schema resets, truncations, or reseeding scripts were run.
3. **No FAISS Rebuilds:** The live FAISS index and metadata files were neither rebuilt nor mutated.
4. **No Ollama / Models:** No Ollama installation was initiated; no model weights were downloaded.
5. **No Destructive Git Commands:** No commits, stashes, resets, or discards were executed. Unrelated tracked modifications and untracked files were preserved.
6. **No Secret Leaks:** No credentials or environment secrets were printed.
7. **Task Scope Boundaries:** Work completed strictly covers Task 2. Task 3 has not been started.
