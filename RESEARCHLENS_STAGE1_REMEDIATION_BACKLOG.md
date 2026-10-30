# ResearchLens — Stage 1: Remediation & Integration Backlog

**Document Version:** 1.0.0  
**Audit Date:** October 20, 2026  
**Auditor:** Antigravity Autonomous Systems Engineering  
**System:** ResearchLens — NLP-Based Research Paper Recommendation System  
**Repository:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`

---

## 1. Backlog Architecture & Sequencing Principles

This remediation backlog organizes all identified technical debt, upcoming feature integrations, user interface enhancements, and production requirements into an ordered, dependency-aware hierarchy.

### Sequencing Principles

1. **Core Feature Gate Passed:** The Stage 1 completion audit confirmed that all 28 core research, NLP, retrieval, comparison, evolution, DRIUT, and local AI capabilities are 100% complete, fully verified, and free of blocking defects. No core algorithmic rewrites are required before authentication work begins.
2. **Strict Separation of Concerns:** Work is partitioned into four independent, sequential tracks:
   - **Track 1:** Pre-Firebase Core Hygiene (Minor non-blocking deprecation cleanups).
   - **Track 2:** Firebase Authentication Integration Blueprint (Stage 2 Primary Focus).
   - **Track 3:** UI Completion & Ergonomic Polish (Stage 3 Post-Auth Refinements).
   - **Track 4:** Production Deployment & Infrastructure Operations (Stage 4 Release Gate).
3. **Data Preservation Invariant:** Every phase must strictly preserve existing database records (162 papers, 85 DRIUT alerts, 5 saved papers, 3 evidence rows), FAISS vector representations (162 vectors), and working-tree changes.

---

## 2. Priority & Dependency Matrix

```
┌──────┬──────────────────────────────────────────┬──────────┬──────────┬─────────────┬──────────┐
│ ID   │ Task Title                               │ Track    │ Severity │ Dependency  │ Effort   │
├──────┼──────────────────────────────────────────┼──────────┼──────────┼─────────────┼──────────┤
│ T1.1 │ Deprecation Warning Hygiene              │ Track 1  │ Low      │ None        │ 0.5 day  │
│ T1.2 │ Connector Latency User Feedback Toast    │ Track 1  │ Low      │ None        │ 0.5 day  │
├──────┼──────────────────────────────────────────┼──────────┼──────────┼─────────────┼──────────┤
│ T2.1 │ Firebase Admin SDK & Config Wiring       │ Track 2  │ High     │ Stage 1 Gate│ 1.0 day  │
│ T2.2 │ Database Schema Federation Bridging      │ Track 2  │ High     │ T2.1        │ 1.0 day  │
│ T2.3 │ Backend Token Dependency Overhaul        │ Track 2  │ Critical │ T2.1, T2.2  │ 1.5 days │
│ T2.4 │ Frontend Firebase Client SDK & AuthModal │ Track 2  │ High     │ T2.3        │ 1.5 days │
│ T2.5 │ Admin Role Mapping & Superuser Bridge    │ Track 2  │ Medium   │ T2.3        │ 0.5 day  │
│ T2.6 │ Auth & Isolation Regression Test Suite   │ Track 2  │ High     │ T2.3, T2.4  │ 1.0 day  │
├──────┼──────────────────────────────────────────┼──────────┼──────────┼─────────────┼──────────┤
│ T3.1 │ Interactive Onboarding Tour (Feature E.5)│ Track 3  │ Medium   │ Stage 2     │ 1.5 days │
│ T3.2 │ Mobile Comparison Matrix Ergonomics      │ Track 3  │ Medium   │ None        │ 1.0 day  │
│ T3.3 │ Live Observatory UI Status Indicators    │ Track 3  │ Low      │ None        │ 0.5 day  │
├──────┼──────────────────────────────────────────┼──────────┼──────────┼─────────────┼──────────┤
│ T4.1 │ Production Secret Key Rotation (Blocker) │ Track 4  │ High     │ Stage 2     │ 0.2 day  │
│ T4.2 │ Nginx Reverse Proxy Deployment           │ Track 4  │ High     │ Stage 2, 3  │ 1.0 day  │
│ T4.3 │ Public TLS / Let's Encrypt Provisioning  │ Track 4  │ High     │ T4.2        │ 0.5 day  │
│ T4.4 │ Automated Daily Backup Cron Job          │ Track 4  │ Medium   │ Stage 2     │ 0.5 day  │
└──────┴──────────────────────────────────────────┴──────────┴──────────┴─────────────┴──────────┘
```

---

## 3. Track 1: Pre-Firebase Core Hygiene (Non-Blocking)

These items address minor deprecation warnings observed during test suite execution. They do not impair runtime correctness and may be completed opportunistically.

### Task T1.1: Starlette & FastAPI Deprecation Warning Hygiene
- **Severity:** Low (Code Hygiene)
- **Problem Statement:** During Pytest execution, 12 deprecation warnings are emitted:
  - `StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.`
  - `DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead` in SlowAPI.
- **Action Items:**
  1. Update exception handlers in `backend/app/core/errors.py` and `backend/app/main.py` to use `status.HTTP_422_UNPROCESSABLE_ENTITY` compatible aliases or import `HTTP_422_UNPROCESSABLE_CONTENT`.
  2. Pin or update `slowapi` dependency to the latest release compatible with Python 3.14/3.16.
- **Acceptance Criteria:** Backend pytest suite executes with 0 deprecation warnings.

### Task T1.2: External Connector Latency User Feedback Toast
- **Severity:** Low (UX Improvement)
- **Problem Statement:** When external academic APIs (e.g., arXiv or Semantic Scholar) experience network congestion approaching the 8-second timeout limit, users only see a generic loading indicator.
- **Action Items:**
  1. Add a non-blocking toast notification in `frontend/src/pages/HomePage.tsx` when an external search takes longer than 4.0 seconds, alerting the user: *"Retrieving federated literature from external repositories (arXiv, PubMed, Semantic Scholar)..."*.
- **Acceptance Criteria:** Search query gracefully informs the user during slow external API responses without freezing the UI.

---

## 4. Track 2: Firebase Authentication Integration Blueprint (Stage 2)

This track represents the immediate primary engineering focus: replacing the local relational JWT system with Firebase Authentication while preserving existing user data, foreign keys, and cryptographic library isolation.

### Task T2.1: Firebase Admin SDK & Backend Configuration Wiring
- **Severity:** High
- **Dependencies:** Stage 1 Audit Gate Approval
- **Detailed Action Items:**
  1. Add `firebase-admin>=6.4.0` to `backend/requirements.txt` and install into `backend/venv`.
  2. Update `backend/app/core/config.py` with optional Firebase configuration settings:
     ```python
     FIREBASE_PROJECT_ID: Optional[str] = None
     FIREBASE_CREDENTIALS_PATH: Optional[str] = None
     FIREBASE_AUTH_ENABLED: bool = False  # Feature toggle for smooth migration
     ```
  3. Author initialization module `backend/app/core/firebase.py` that initializes the Firebase Admin app using either explicit service account credentials or Google Application Default Credentials (ADC).
- **Acceptance Criteria:** Backend boots cleanly with Firebase credentials validated; fails gracefully if credentials are missing when `FIREBASE_AUTH_ENABLED=True`.

### Task T2.2: Database User Model Federation Bridging
- **Severity:** High
- **Dependencies:** T2.1
- **Problem Statement:** Existing `saved_papers` (5 records) and `driut_alerts` (85 records) store foreign keys referencing `users.username` (`String(100)`). A naive replacement of `User.username` with Firebase `uid` would break existing relational integrity and cascade-delete alerts.
- **Detailed Action Items:**
  1. Add `firebase_uid` column to `backend/app/models/user.py`:
     ```python
     firebase_uid = Column(String(128), unique=True, index=True, nullable=True)
     ```
  2. Make `hashed_password` nullable in `User` model (`nullable=True`) so that federated OAuth users who authenticate via Google/Firebase do not require dummy password hashes.
  3. Create an idempotent migration script `backend/app/db/migrate_firebase_auth.py` that adds the column using `ALTER TABLE users ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR(128);`.
  4. Ensure existing records (`admin`, `default_user`, `testuser_task10`) retain their usernames and primary keys.
- **Acceptance Criteria:** Existing table row counts and foreign keys remain 100% intact; new column indexed and ready for identity federation.

### Task T2.3: Backend Authentication Dependency Overhaul (`deps.py`)
- **Severity:** Critical (Security Core)
- **Dependencies:** T2.1, T2.2
- **Detailed Action Items:**
  1. Refactor `backend/app/api/deps.py::get_current_user`:
     - If `FIREBASE_AUTH_ENABLED` is `True`:
       - Extract Bearer token from `Authorization` header.
       - Verify token using `firebase_admin.auth.verify_id_token(token)`.
       - Extract `uid = decoded_token["uid"]` and `email = decoded_token.get("email")`.
       - Query `User` where `User.firebase_uid == uid`.
       - If user record does not exist: auto-provision local `User` record with `username = email.split("@")[0] + "_" + uid[:6]`, `email = email`, `firebase_uid = uid`.
     - If `FIREBASE_AUTH_ENABLED` is `False`: retain existing local HS256 JWT decoding for backwards compatibility and offline development.
  2. Maintain strict HTTP 401 Unauthorized responses for invalid, expired, or revoked tokens.
- **Acceptance Criteria:** Valid Firebase ID token resolves to an active local `User` record; user library endpoints (`/saved`, `/driut/alerts`) filter correctly by the federated user.

### Task T2.4: Frontend Firebase Web Client SDK & AuthModal Integration
- **Severity:** High
- **Dependencies:** T2.3
- **Detailed Action Items:**
  1. Install Firebase Web SDK: `npm install firebase` in `frontend/`.
  2. Create `frontend/src/services/firebase.ts` initializing the Firebase client app with configuration loaded from Vite environment variables (`VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`).
  3. Update `frontend/src/components/AuthModal.tsx`:
     - Support Email/Password sign-in via `signInWithEmailAndPassword`.
     - Support Email/Password registration via `createUserWithEmailAndPassword`.
     - Support Google Sign-In via `signInWithPopup(auth, new GoogleAuthProvider())`.
     - On successful authentication, call `await user.getIdToken()` and pass the token to the parent application state.
  4. Update `frontend/src/services/api.ts` to supply the Firebase ID token in the `Authorization: Bearer <token>` header for all authenticated requests.
  5. Implement token refresh listener (`onIdTokenChanged`) to ensure long-running sessions refresh tokens automatically before the 60-minute expiry.
- **Acceptance Criteria:** Researchers can register and log in using either Email/Password or Google OAuth; session persists across browser page reloads.

### Task T2.5: Admin Authorization & Role Mapping Bridge
- **Severity:** Medium
- **Dependencies:** T2.3
- **Detailed Action Items:**
  1. Update `backend/app/api/deps.py::get_current_admin_user`:
     - Check for Firebase Custom Claim `decoded_token.get("admin") is True`.
     - OR verify if the federated `User.is_superuser` column is `True` in PostgreSQL.
  2. Provide an administrative CLI command `backend/app/db/set_admin_claim.py` allowing operators to assign the admin claim to a given Firebase UID.
- **Acceptance Criteria:** Reindexing endpoints (`/reindex-faiss`, `/sync-index`) remain restricted strictly to authorized administrative accounts.

### Task T2.6: Automated Auth & Isolation Regression Test Suite
- **Severity:** High
- **Dependencies:** T2.3, T2.4
- **Detailed Action Items:**
  1. Update `backend/tests/test_auth_and_isolation.py` with mocked Firebase token verification fixtures (`unittest.mock.patch("firebase_admin.auth.verify_id_token")`).
  2. Assert that User A cannot view, modify, or delete User B's saved papers or DRIUT alerts.
  3. Update frontend tests `AuthModal.test.tsx` and `SavedLibraryView.test.tsx` to mock Firebase client calls.
- **Acceptance Criteria:** 100% test pass rate across backend and frontend test suites with zero database mutations.

---

## 5. Track 3: UI Completion & Polish Backlog (Stage 3)

These enhancements address interface polish without modifying core research algorithms or disrupting existing workflows.

### Task T3.1: Interactive Onboarding Guided Tour (Feature E.5)
- **Severity:** Medium
- **Dependencies:** Stage 2 Completion
- **Action Items:**
  1. Implement a lightweight, accessible onboarding walkthrough component (`frontend/src/components/OnboardingTour.tsx`).
  2. Guide new researchers through key touchpoints:
     - Step 1: Multi-Modal Search Bar (Natural language, Abstract, Keywords).
     - Step 2: Two-Phase PDF Upload & Duplicate Preview.
     - Step 3: Verifiable Evidence Modal with exact character offsets.
     - Step 4: 12-Dimension Multi-Paper Comparison Matrix.
     - Step 5: DRIUT Dynamic Impact Tracker and Chronological Evolution Timeline.
  3. Store tour completion state in `localStorage` (`researchlens_tour_dismissed: true`) with an option to replay the tour from the Navbar help button.
- **Acceptance Criteria:** First-time visitors are presented with the tour; can dismiss or step through; zero layout shifts.

### Task T3.2: Mobile Ergonomics for 12-Dimension Comparison Matrix
- **Severity:** Medium
- **Action Items:**
  1. Add a responsive CSS breakpoint (`@media (max-width: 640px)`) to `frontend/src/components/CompareModal.tsx`.
  2. On narrow screens, transform the multi-column comparison table into a stacked dimensional card accordion, allowing researchers to expand individual dimensions (e.g., Methodology, Dataset, Limitations) one at a time.
- **Acceptance Criteria:** Mobile viewports (375px width) display comparison data without horizontal clipping or unscrollable overflow.

### Task T3.3: Live Observatory UI Status Indicators
- **Severity:** Low
- **Action Items:**
  1. Enhance `frontend/src/components/Navbar.tsx` observatory health badge:
     - Display a tooltip indicating active Ollama model name (`qwen2.5:3b`), host inference device (NVIDIA GPU), and total indexed catalog papers (162).
- **Acceptance Criteria:** Provides transparent system telemetry directly to researchers in the UI.

---

## 6. Track 4: Production Deployment & Infrastructure Operations (Stage 4)

These tasks address the operational prerequisites required for public institutional deployment.

### Task T4.1: Production Secret Key Rotation (Mandatory Release Blocker)
- **Severity:** High (Security Release Blocker)
- **Dependencies:** Deployment Environment Allocation
- **Action Items:**
  1. Generate a high-entropy 64-character hexadecimal cryptographic secret:
     ```bash
     openssl rand -hex 32
     ```
  2. Inject the generated secret into `/opt/researchlens/backend/.env` as `JWT_SECRET_KEY`.
  3. Verify that `Settings()` in `backend/app/core/config.py` boots successfully with `ENVIRONMENT=production`.
- **Acceptance Criteria:** Production application boots cleanly without triggering the fail-closed default secret validator.

### Task T4.2: Nginx Reverse Proxy Deployment & Configuration
- **Severity:** High
- **Dependencies:** Stage 2 & Stage 3 Completion
- **Action Items:**
  1. Deploy the Nginx configuration specified in `RESEARCHLENS_PRODUCTION_DEPLOYMENT_GUIDE.md` to `/etc/nginx/conf.d/researchlens.conf`.
  2. Configure proxy passes:
     - `/api/` -> `http://127.0.0.1:8000/`
     - `/` -> `http://127.0.0.1:3000/` (or serve precompiled `dist/` static bundle directly).
  3. Configure client max body size: `client_max_body_size 20M;` for PDF uploads.
- **Acceptance Criteria:** Nginx syntax check passes (`nginx -t`); routes requests accurately to backend and frontend.

### Task T4.3: Public TLS Termination & DNS Binding
- **Severity:** High
- **Dependencies:** T4.2, Public Domain Name
- **Action Items:**
  1. Point DNS A-record `researchlens.institution.edu` to production server public IP.
  2. Provision TLS certificates via Certbot / Let's Encrypt:
     ```bash
     certbot --nginx -d researchlens.institution.edu
     ```
  3. Enforce HTTP to HTTPS automatic redirection and configure HSTS security headers.
- **Acceptance Criteria:** HTTPS connection verified with A+ SSL Labs rating and valid certificate chain.

### Task T4.4: Automated Daily Database Backup Cron Job
- **Severity:** Medium
- **Action Items:**
  1. Deploy an automated cron job executing `scripts/verify_backup_restore.py` daily at 02:00 UTC.
  2. Store compressed dumps in `/var/backups/researchlens/` with 14-day automated retention rotation per `RESEARCHLENS_DATABASE_MAINTENANCE_RUNBOOK.md`.
- **Acceptance Criteria:** Daily automated backups verified with zero disruption to database availability.
