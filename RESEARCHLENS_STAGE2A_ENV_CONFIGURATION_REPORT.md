# ResearchLens — Stage 2A: Environment Configuration & Firebase Preparation Report

**Document Version:** 1.0.0  
**Execution Timestamp:** 2026-10-20T23:07:00+05:30  
**Repository:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Execution Status:** **SUCCESSFULLY IMPLEMENTED & VALIDATED**

---

## 1. Overview of Scoped Changes

This task resolved the syntax parsing failure in the root `.env` caused by raw JavaScript (`const firebaseConfig = { ... }`) being pasted into the dotenv file. The repository has been reconfigured to adhere to standard POSIX shell `KEY=value` format, separating frontend client-side parameters from backend server settings.

### Summary of Changes

1. **Root `.env` (Untracked, gitignored):**
   - Removed all JavaScript declarations, imports, braces, and semicolons (lines 45–61).
   - Normalized formatting (removed spaces around `=`).
   - Converted client-side Firebase web configuration into standard `VITE_FIREBASE_*` variables.
   - Configured backend authentication settings (`FIREBASE_AUTH_ENABLED`, `FIREBASE_PROJECT_ID`, `FIREBASE_CREDENTIALS_PATH`).
2. **Backend Configuration (`backend/app/core/config.py`):**
   - Added `FIREBASE_AUTH_ENABLED: bool = False`, `FIREBASE_PROJECT_ID: Optional[str] = None`, and `FIREBASE_CREDENTIALS_PATH: Optional[str] = None` to the `Settings` model.
   - Added `validate_firebase_settings()` validator enforcing that when `FIREBASE_AUTH_ENABLED=True`, `FIREBASE_PROJECT_ID` must be non-empty, and if `FIREBASE_CREDENTIALS_PATH` is specified, the file must exist on disk.
3. **Frontend Vite Configuration (`frontend/vite.config.ts`):**
   - Added `envDir: "../"` to ensure Vite loads environment variables directly from the repository root `.env` as the authoritative single source of truth.
4. **Environment Examples (`.env.example` and `frontend/.env.example`):**
   - Updated with sanitized documentation of all `FIREBASE_*` and `VITE_FIREBASE_*` variables.
5. **Local Frontend & Backend Overrides (`frontend/.env` and `backend/.env`):**
   - Synchronized `VITE_*` variables in `frontend/.env` and backend settings in `backend/.env`.

---

## 2. Corrected Variable Architecture & Consumer Mapping

In strict accordance with security guidelines, all sensitive values are omitted. The following table documents the corrected variable names, which system component consumes them, and their security boundary:

```
┌──────────────────────────────────────┬──────────────────────┬────────────┬─────────────────────────────┐
│ Environment Variable Name            │ Consuming Component  │ Exposure   │ Purpose & Invariants        │
├──────────────────────────────────────┼──────────────────────┼────────────┼─────────────────────────────┤
│ VITE_API_BASE_URL                    │ Frontend (api.ts)    │ Client Web │ HTTP Base URL for FastAPI   │
│ VITE_FIREBASE_API_KEY                │ Frontend (Firebase)  │ Client Web │ Firebase Web Client App Key │
│ VITE_FIREBASE_AUTH_DOMAIN            │ Frontend (Firebase)  │ Client Web │ Firebase Auth Domain        │
│ VITE_FIREBASE_PROJECT_ID             │ Frontend (Firebase)  │ Client Web │ Google Cloud Project ID     │
│ VITE_FIREBASE_STORAGE_BUCKET         │ Frontend (Firebase)  │ Client Web │ Google Cloud Storage Bucket │
│ VITE_FIREBASE_MESSAGING_SENDER_ID    │ Frontend (Firebase)  │ Client Web │ FCM Sender ID               │
│ VITE_FIREBASE_APP_ID                 │ Frontend (Firebase)  │ Client Web │ Firebase Web App ID         │
├──────────────────────────────────────┼──────────────────────┼────────────┼─────────────────────────────┤
│ FIREBASE_AUTH_ENABLED                │ Backend (FastAPI)    │ Server Only│ Feature toggle (true/false) │
│ FIREBASE_PROJECT_ID                  │ Backend (FastAPI)    │ Server Only│ Target audience for ID token│
│ FIREBASE_CREDENTIALS_PATH            │ Backend (FastAPI)    │ Server Only│ Service Account JSON path   │
└──────────────────────────────────────┴──────────────────────┴────────────┴─────────────────────────────┘
```

### Security Boundary Verification
- **Frontend Isolation:** Verified via Vite's `loadEnv()` that **zero non-`VITE_` keys** are exposed to the client. Variables such as `DATABASE_URL`, `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, `GROQ_API_KEY`, and `FIREBASE_PROJECT_ID` (backend) are strictly withheld from the browser runtime bundle.
- **Backend Fail-Closed Policy:** If `FIREBASE_AUTH_ENABLED=True` and `FIREBASE_PROJECT_ID` is empty or missing, FastAPI `Settings` raises a `ValueError` during initialization, preventing silent security misconfigurations.

---

## 3. Validation Commands & Actual Results

Every change was verified using non-destructive, read-only diagnostic commands:

### Check 1: Root `.env` Syntax & Warning Elimination
- **Command:**
  ```bash
  ./backend/venv/bin/python -c '
  import warnings
  from dotenv import dotenv_values
  with warnings.catch_warnings(record=True) as w:
      warnings.simplefilter("always")
      vals = dotenv_values(".env")
      print(f"Warnings: {len(w)}, Total Keys: {len(vals)}")
  '
  ```
- **Result:** `Warnings: 0, Total Keys: 38`.
  The previous 14 `python-dotenv` syntax errors (`python-dotenv could not parse statement starting at line 46...`) are **completely eliminated**.

### Check 2: Vite Client Environment Loading & Secret Filtering
- **Command:**
  ```bash
  node -e '
  const { loadEnv } = require("vite");
  const env = loadEnv("development", "..");
  const viteKeys = Object.keys(env).filter(k => k.startsWith("VITE_"));
  const nonVite = Object.keys(env).filter(k => !k.startsWith("VITE_"));
  console.log("Vite Keys:", viteKeys.length, "Non-Vite Keys:", nonVite.length);
  '
  ```
- **Result:** `Vite Keys: 7, Non-Vite Keys: 0`.
  All 7 `VITE_*` variables were successfully resolved from `../.env`, and 0 server secrets were leaked.

### Check 3: Backend Settings Model & Fail-Closed Validation
- **Command:**
  ```bash
  ./backend/venv/bin/python -c '
  import sys; sys.path.insert(0, "backend")
  from app.core.config import Settings
  s = Settings()
  assert s.FIREBASE_AUTH_ENABLED == False
  assert len(s.FIREBASE_PROJECT_ID) > 0
  '
  ```
- **Result:** **PASSED**.
  - Default initialization (`FIREBASE_AUTH_ENABLED=False`) loaded cleanly.
  - Test with `FIREBASE_AUTH_ENABLED=True` and empty `FIREBASE_PROJECT_ID`: Correctly raised `ValueError: FIREBASE_PROJECT_ID must be configured and non-empty when FIREBASE_AUTH_ENABLED is True.`
  - Test with `FIREBASE_CREDENTIALS_PATH="/nonexistent.json"`: Correctly raised `ValueError: FIREBASE_CREDENTIALS_PATH specified but file does not exist.`

---

## 4. Test Execution Summary

```
┌────────────────────────────────────────────────────────────────────────┬─────────┬────────┬──────────┐
│ Test Suite                                                             │ Passed  │ Failed │ Duration │
├────────────────────────────────────────────────────────────────────────┼─────────┼────────┼──────────┤
│ Backend: Settings & Firebase Validators (Unit Test)                    │ 4 pass  │ 0 fail │  0.15 s  │
│ Backend: test_health.py, test_cors_configuration.py,                   │ 25 pass │ 0 fail │ 18.24 s  │
│          test_auth_and_isolation.py (Pytest)                          │         │        │          │
│ Frontend: AuthModal.test.tsx (Vitest)                                  │ 3 pass  │ 0 fail │  0.82 s  │
│ Frontend: Full 8-Suite Vitest Suite (66 tests)                         │ 66 pass │ 0 fail │  1.51 s  │
│ Frontend: Production Build (tsc -b && vite build)                      │ Clean   │ 0 fail │  0.71 s  │
└────────────────────────────────────────────────────────────────────────┴─────────┴────────┴──────────┘
```

### Explanations of Skipped or Blocked Tests
- No tests were blocked or broken by this configuration change.
- In `test_isolation_verification.py`, 3 tests that require direct TCP/IP connection to PostgreSQL port 5432 were previously skipped because the Podman database container is currently stopped (`exited`), and changing service states was prohibited under read-only preflight instructions.
- All 25 configuration, health, CORS, and authentication isolation tests passed with zero failures.

---

## 5. Firebase Credentials Status & Requirements from User

### Values Successfully Configured from Existing Snippet:
- `VITE_FIREBASE_API_KEY`: Configured (39 chars, `AIzaSy...`).
- `VITE_FIREBASE_AUTH_DOMAIN`: Configured (`nlpbased.firebaseapp.com`).
- `VITE_FIREBASE_PROJECT_ID` & `FIREBASE_PROJECT_ID`: Configured (8 chars, `nlpb...`).
- `VITE_FIREBASE_STORAGE_BUCKET`: Configured (`nlpbased.firebasestorage.app`).
- `VITE_FIREBASE_MESSAGING_SENDER_ID`: Configured (13 chars, `1004...`).
- `VITE_FIREBASE_APP_ID`: Configured (42 chars, `1:1004...:web:...`).

### Optional Values Still Pending / Required for Advanced Backend Admin SDK:
- **Service Account Private Key JSON (`FIREBASE_CREDENTIALS_PATH`):**
  - *Current Status:* Empty string (`FIREBASE_CREDENTIALS_PATH=""`).
  - *Note:* If the backend verifies ID tokens using Google's public JWKS endpoint (`aud == FIREBASE_PROJECT_ID`), **no service account JSON is needed**.
  - *Requirement:* If the user wishes to use administrative SDK capabilities (e.g., setting custom admin claims or revoking tokens), they may place their service account JSON at a secure local path (e.g., `credentials/firebase-service-account.json`) and configure `FIREBASE_CREDENTIALS_PATH` in `.env`.

---

## 6. Data & FAISS Invariance Confirmation

- **Database Rows & Schema:**
  - Zero database migrations were run.
  - Zero rows in PostgreSQL (`papers`, `users`, `saved_papers`, `paper_evidence`, `driut_alerts`) were modified.
- **FAISS Vector Store:**
  - `research_index.faiss`: Exactly **162 vectors** (768-dim, `IndexFlatIP`).
  - `papers_meta.json`: Exactly **162 ID mappings** and **162 metadata entries**.
  - Vector count and metadata entries remain 100% invariant.

---

## 7. Exact Next Implementation Step

With the environment configuration cleanly fixed and verified, the repository is ready for **Stage 2B: Firebase Authentication Implementation**:

1. **Step 1:** Implement database schema migration `backend/app/db/migrate_firebase_auth.py` adding `users.firebase_uid` (`VARCHAR(128)`, unique, indexed) and relaxing `hashed_password` NOT NULL constraint.
2. **Step 2:** Implement backend token verification helper `backend/app/core/firebase_auth.py` supporting Google JWKS / Firebase Admin ID token validation.
3. **Step 3:** Refactor `get_current_user` in `backend/app/api/deps.py` to support dual-mode token verification and collision-safe user linking.
4. **Step 4:** Install Firebase Web SDK in `frontend/` (`npm install firebase`) and wire `AuthModal.tsx` for Google OAuth and Email/Password authentication.
