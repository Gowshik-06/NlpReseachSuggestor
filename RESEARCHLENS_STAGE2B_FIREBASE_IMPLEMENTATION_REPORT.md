# ResearchLens — Stage 2B: Firebase Authentication Implementation Report

**Date:** 2026-10-20  
**Repository:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Phase:** Stage 2B — Firebase Authentication Integration  
**Status:** Implementation Complete & Validated in Isolated Test Environment; Live Database Migration Staged (Deferred per Safety Protocol)

---

## Executive Summary

Firebase Authentication has been integrated end-to-end into ResearchLens. The implementation fulfills all architectural, security, and migration safety mandates specified in the Stage 2B brief:
- **Backend Token Verification:** A focused, dependency-safe module (`backend/app/core/firebase_auth.py`) cryptographically validates Firebase ID tokens using RS256 signatures against Google's public JWKS certificates with bounded in-memory caching and fail-closed error handling.
- **Fail-Closed Dual Mode:** When `FIREBASE_AUTH_ENABLED=true`, the backend strictly enforces RS256 Firebase tokens and rejects local HS256 tokens and direct registration/login endpoints. When disabled, local HS256 authentication remains operational for development.
- **Safe Identity Mapping & Account Linking:** New Firebase users are auto-provisioned with non-admin privileges (`is_superuser=False`), collision-safe usernames, and `hashed_password=None`. Ambiguous email collisions are blocked with HTTP 409 Conflict. A dedicated linking endpoint (`/api/v1/auth/link-firebase`) requires proof of local account control (password) and Firebase identity before binding the `firebase_uid`.
- **Database Schema Migration:** An idempotent migration script (`backend/app/db/migrate_firebase_auth.py`) adds `firebase_uid VARCHAR(128)` with a partial unique index and makes `hashed_password` nullable while preserving foreign keys and table invariants. Per the mandatory safety rules, **live execution on PostgreSQL was safely deferred** because the container is currently stopped.
- **Frontend Integration:** Installed the official Firebase Web SDK, created a client initialization module (`frontend/src/services/firebase.ts`), updated `api.ts` to attach live Firebase ID tokens via `currentUser.getIdToken()` (avoiding insecure token storage), enhanced `AuthModal.tsx` for Email/Password and Google sign-in with account-linking support, and verified a production build.
- **Test Verification:** 56 targeted backend tests passed (including 18 new Firebase auth tests and 2 migration tests); 72 frontend vitest tests passed; and the production frontend build passed in 903ms.

---

## 1. Files Changed & Implementation Details

| Component | Path | Action | Description |
| :--- | :--- | :--- | :--- |
| **Backend Dependencies** | `backend/requirements.txt` | Modified | Added `cryptography>=42.0.0` to enable RS256 token decoding in PyJWT. |
| **Backend Core** | `backend/app/core/firebase_auth.py` | Created | `FirebaseTokenVerifier`, `verify_firebase_id_token`, and `FirebaseAuthError` implementing Google JWKS key retrieval, bounded caching, RS256 verification, and claim validation. |
| **Database Migration** | `backend/app/db/migrate_firebase_auth.py` | Created | Idempotent migration adding `firebase_uid`, unique index `ix_users_firebase_uid`, dropping NOT NULL on `hashed_password`, invariant checks, and rollback logic. |
| **User Model** | `backend/app/models/user.py` | Modified | Added `firebase_uid = Column(String(128), unique=True, index=True, nullable=True)` and set `hashed_password` to `nullable=True`. |
| **Auth Schemas** | `backend/app/schemas/auth.py` | Modified | Updated `UserResponse` with `is_superuser` and `firebase_uid`; added `FirebaseLoginRequest`, `LinkFirebaseAccountRequest`, `LinkFirebaseAccountResponse`. |
| **API Dependencies** | `backend/app/api/deps.py` | Modified | Refactored `get_current_user` to verify Firebase ID tokens in Firebase mode, resolve by `firebase_uid`, auto-provision unprivileged users, reject email collisions, and reject local tokens. Enforced database-driven `get_current_admin_user`. |
| **Auth Endpoints** | `backend/app/api/v1/endpoints/auth.py` | Modified | Added `POST /api/v1/auth/firebase-login`, added `POST /api/v1/auth/link-firebase`, guarded `/register` and `/login` against direct unverified access in Firebase mode. |
| **Backend Tests** | `backend/tests/test_firebase_auth.py` | Created | 18 unit and integration tests for cryptographic token validation, auto-provisioning, collision rejection, account linking, admin isolation, deactivated accounts, and cross-user isolation. |
| **Migration Tests** | `backend/tests/test_firebase_migration.py` | Created | 2 integration tests for forward migration, schema verification, unique constraint enforcement, and idempotency. |
| **Frontend Dependencies** | `frontend/package.json` | Modified | Installed official `firebase` Web SDK (`firebase@11.x`). |
| **Frontend Types** | `frontend/src/types/auth.ts` | Modified | Added `is_superuser` and `firebase_uid` to `User`; added `FirebaseLoginRequest`, `LinkFirebaseAccountRequest`, `LinkFirebaseAccountResponse`. |
| **Frontend Firebase** | `frontend/src/services/firebase.ts` | Created | Reusable Firebase initialization using `VITE_FIREBASE_*`, configuration detection, email/password auth, Google popup sign-in, token retrieval, error formatting, and auth-state listener. |
| **Frontend API** | `frontend/src/services/api.ts` | Modified | Added `getActiveBearerToken()` pulling live ID tokens from Firebase observer, updated `request()`, `getCurrentUser()`, `logoutUser()`, added `firebaseLogin()` and `linkFirebaseAccount()`. |
| **Frontend Modal** | `frontend/src/components/AuthModal.tsx` | Modified | Supported Firebase email/password sign-in, registration, Google sign-in, account-linking UI for email collisions (409), error mapping, and local fallback. |
| **Frontend Pages** | `frontend/src/pages/HomePage.tsx` | Modified | Wired `onFirebaseAuthStateChanged` listener to trigger `loadUserData()`, made logout asynchronous. |
| **Frontend Tests** | `frontend/src/services/firebase.test.ts` | Created | 6 unit tests for config detection, error formatting, token retrieval, auth state subscriptions, and sign-out. |

---

## 2. Authentication and Token-Verification Architecture

```
[ Browser / React Frontend ]
         │
         ├─ 1. Sign In (Email/Password or Google Popup) ────────► [ Google Firebase Auth ]
         │                                                                   │
         │◄─ 2. Returns Firebase ID Token (RS256 JWT) ───────────────────────┘
         │
         ├─ 3. API Request with Header: "Authorization: Bearer <id_token>"
         ▼
[ FastAPI Backend /deps.py ]
         │
         ├─ 4. Passes token to backend/app/core/firebase_auth.py
         │       │
         │       ├─ Checks unverified header (alg == "RS256", kid present)
         │       ├─ Retrieves signing key from Google JWKS (cached in memory, max 32 keys, 1h TTL)
         │       ├─ Decodes and verifies RS256 signature against Google public key
         │       ├─ Enforces aud == FIREBASE_PROJECT_ID
         │       ├─ Enforces iss == https://securetoken.google.com/{FIREBASE_PROJECT_ID}
         │       ├─ Enforces exp > now, iat <= now, auth_time <= now
         │       └─ Enforces valid, non-empty sub (UID) <= 128 characters
         │
         ├─ 5. Query PostgreSQL users table: WHERE firebase_uid = token.sub
         │       │
         │       ├─ [Found & Active] ──────────────────────────► Grant access, return User record
         │       ├─ [Found & Deactivated] ─────────────────────► HTTP 403 Forbidden
         │       │
         │       └─ [Not Found] -> Safe Auto-Provisioning
         │               ├─ Check if local user exists with token.email:
         │               │     └─ YES: HTTP 409 Conflict ("Account exists; link via password")
         │               └─ NO: Create User record
         │                     - username = collision_safe_username (max 50 chars)
         │                     - email = token.email
         │                     - hashed_password = NULL (no fabricated password)
         │                     - firebase_uid = token.sub
         │                     - is_superuser = FALSE (never elevated)
         │                     - is_active = TRUE
         │                     └─ Return newly created User record
         ▼
[ Protected Endpoint / Database Queries ] (Isolated by user.username)
```

### Key Security & Architectural Properties:
1. **Public Key Verification Only:** The backend uses Google's published JWKS endpoint (`https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com`). No private service account key was added or needed for ID token verification.
2. **Fail-Closed Algorithm Enforcement:** Tokens with `alg: "HS256"`, `alg: "none"`, or any algorithm other than `RS256` are rejected before key retrieval.
3. **No Credential Logging:** Error messages and debug logs sanitize input; raw tokens and user passwords are never written to server logs.
4. **No Insecure Storage:** The frontend retrieves the current token dynamically via `currentUser.getIdToken()` from the Firebase client SDK. Tokens are not mirrored to `localStorage` or `sessionStorage` in Firebase mode.

---

## 3. Schema Migration Details & Execution Status

### Migration Script: `backend/app/db/migrate_firebase_auth.py`

#### Changes Implemented:
```sql
-- 1. Add nullable firebase_uid column
ALTER TABLE users ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR(128);

-- 2. Make hashed_password nullable for Firebase accounts
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

-- 3. Create unique index on non-null Firebase UIDs
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_firebase_uid
ON users (firebase_uid)
WHERE firebase_uid IS NOT NULL;
```

#### Multi-Dialect & Test Support:
- Supports PostgreSQL DDL syntax (`IF NOT EXISTS`, partial unique indexes).
- Supports SQLite DDL for isolated in-memory/file test harnesses.
- Built-in verification (`verify_schema_invariants`) and rollback (`rollback_firebase_auth`).

### Execution Status: **DEFERRED ON LIVE DATABASE**
- **Reason:** The PostgreSQL Podman container `research-paper-recommender-postgres-1` is in an `exited` state (`Exited (0) 47 hours ago`).
- **Safety Directive Compliance:** Per Section 3 (*"If PostgreSQL is stopped or the backup cannot be verified, implement the migration and tests but do not start services or execute the migration automatically. Report the exact blocker so execution can be completed safely later"*), the migration was **not** run against the stopped PostgreSQL database.
- **Verification in Test Environment:** The migration script was executed and validated against an isolated test database in `backend/tests/test_firebase_migration.py`. It confirmed:
  - Idempotent execution (running multiple times succeeds with zero side effects).
  - Uniqueness enforcement on non-null `firebase_uid`.
  - Permission of multiple `NULL` `firebase_uid` entries for local accounts.
  - Retention of all existing columns, constraints, and relationships.

---

## 4. Backup Verification and Baseline Database Invariants

### Existing Recoverable Backup Verified on Disk:
- **Location:** `backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz`
- **Checksum File:** `backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz.sha256`
- **SHA-256 Checksum:** `4daec4d3737d89c7596b859a839847e39312ae19dff3b41e046b9803ecce806a`
- **Size:** 127,786 bytes (compressed, containing verified `PostgreSQL database dump complete` signature).

### Baseline Database Records (To be Verified After Live Migration):
| Table | Baseline Count | Target Invariant |
| :--- | :--- | :--- |
| `papers` | 162 | Must remain exactly 162 |
| `faiss_index` (vectors) | 162 | Must remain exactly 162 (dimension 768) |
| `users` | 4 | Must remain exactly 4 (identities and hashes intact) |
| `saved_papers` | 5 | Must remain exactly 5 (ownership mapped to username) |
| `paper_evidence` | 3 | Must remain exactly 3 |
| `driut_alerts` | 85 | Must remain exactly 85 (post-chronology remediation) |

The migration script includes `get_table_row_counts()` which records counts prior to executing DDL and asserts exact count matching post-migration, raising a fatal exception if any count shifts.

---

## 5. Account-Linking and Administrator-Security Behavior

### Safe Account Linking Flow (`POST /api/v1/auth/link-firebase`)
To protect existing accounts from takeover via email spoofing:
1. **Never Link Solely by Email:** If a user signs in with a Firebase account whose email matches an existing local user (`User.email`), the backend returns `HTTP 409 Conflict`:
   > *"An existing account is already registered with this email address. Please sign in with your local password to link your Firebase account."*
2. **Proof of Existing Control:** The user is prompted in the UI to enter their local password.
3. **Dual Verification:**
   - The local password is confirmed via `bcrypt.checkpw(local_password, user.hashed_password)`.
   - The Firebase token is verified cryptographically via `verify_firebase_id_token`.
4. **Collision & Conflict Checks:**
   - Rejects if the Firebase UID is already associated with another user (`HTTP 409 Conflict`).
   - Rejects if the local user is already bound to a different Firebase UID (`HTTP 409 Conflict`).
5. **Atomic Binding:** Upon dual verification, `user.firebase_uid = target_uid` is saved. The local username, primary key `id`, permissions, and foreign key references remain unchanged.

### Administrator Security Guarantees
1. **Single Source of Truth:** `User.is_superuser` in PostgreSQL is the sole authority for administrative privilege.
2. **No Elevation on Registration:** Auto-provisioning always sets `is_superuser = False`.
3. **No Elevation via Client Claims:** Firebase tokens, email patterns, usernames, or unverified claims cannot elevate a user to admin.
4. **Admin Endpoint Protection:** Administrative endpoints (such as `/api/v1/papers/sync-index` and `/api/v1/papers/reindex-faiss`) use `get_current_admin_user`, which strictly verifies `current_user.is_superuser == True`, returning `HTTP 403 Forbidden` for normal Firebase users.

---

## 6. Test and Build Results

### A. Backend Test Suites
Targeted execution command:
```bash
backend/venv/bin/pytest backend/tests/test_firebase_auth.py \
                        backend/tests/test_firebase_migration.py \
                        backend/tests/test_auth_and_isolation.py \
                        backend/tests/test_papers_api.py \
                        backend/tests/test_cors_configuration.py
```
**Results:** **56 passed, 0 failed, 4 deprecation warnings in 28.86s.**

#### Firebase Specific Test Breakdown:
- `backend/tests/test_firebase_auth.py` (18 passed):
  - `test_verify_valid_firebase_token`: Valid RS256 token verified against JWKS.
  - `test_verify_expired_token`: Expired token rejected.
  - `test_verify_invalid_audience`: Wrong audience rejected.
  - `test_verify_invalid_issuer`: Wrong issuer rejected.
  - `test_verify_missing_or_empty_sub`: Empty UID rejected.
  - `test_verify_overlong_sub`: UID > 128 characters rejected.
  - `test_verify_future_auth_time`: Future `auth_time` rejected.
  - `test_verify_rejected_hs256_algorithm`: Symmetric HS256 rejected.
  - `test_verify_key_retrieval_failure`: PyJWKClient lookup error fails closed.
  - `test_verify_tampered_signature`: Corrupted signature rejected.
  - `test_firebase_user_resolution_and_auto_provisioning`: Provisions non-admin user with null password.
  - `test_reject_ambiguous_email_collision`: Unlinked matching email rejected (409 Conflict).
  - `test_safe_account_linking_flow`: Validates dual-control proof and binds UID.
  - `test_deactivated_account_forbidden`: Inactive user blocked (403 Forbidden).
  - `test_ordinary_firebase_user_cannot_access_admin_endpoints`: Non-admin blocked from `/sync-index` (403); superuser permitted (200).
  - `test_local_hs256_tokens_rejected_when_firebase_mode_enabled`: Fail-closed check against local tokens in Firebase mode.
  - `test_local_auth_functional_when_firebase_disabled`: Local dev registration/login preserved when Firebase mode disabled.
  - `test_cross_user_isolation`: Saved paper libraries isolated between distinct Firebase users.
- `backend/tests/test_firebase_migration.py` (2 passed):
  - `test_migration_forward_and_idempotency`: DDL application and double-execution idempotency verified.
  - `test_unique_firebase_uid_constraint`: Enforces uniqueness on non-null UIDs; permits multiple NULL UIDs.

### B. Frontend Test Suites
Execution command: `npm test` in `frontend/`
**Results:** **72 passed, 0 failed across 9 test files in 1.48s.**

- `src/services/firebase.test.ts` (6 tests passed):
  - Configuration detection (recognizes placeholder vs valid config).
  - Error formatting (maps error codes to user-friendly messages).
  - Token retrieval from active `currentUser`.
  - Auth state change subscriptions.
  - Sign-out execution.
- `src/services/api.test.ts` (21 tests passed):
  - Token storage, retrieval, clearance.
  - Dynamic bearer token attachment.
  - Auto-invalidation on 401.
  - Error parser validation.
  - API endpoint bindings.
- `src/components/AuthModal.test.tsx` (3 tests passed):
  - Role dialog and accessibility.
  - Escape key handling.
  - Mode synchronization.
- `src/components/CompareModal.test.tsx` (8 passed)
- `src/components/DriutAlertsView.test.tsx` (7 passed)
- `src/components/EvidenceModal.test.tsx` (10 passed)
- `src/components/ResearchEvolutionView.test.tsx` (7 passed)
- `src/components/SavedLibraryView.test.tsx` (3 passed)
- `src/App.test.tsx` (7 passed)

### C. Frontend Production Build
Execution command: `npm run build` in `frontend/`
```
> research-paper-recommender-frontend@0.1.0 build
> tsc -b && vite build

vite v5.4.21 building for production...
✓ 59 modules transformed.
dist/index.html                   0.95 kB │ gzip:   0.53 kB
dist/assets/index-vAofhJTI.css   13.60 kB │ gzip:   3.47 kB
dist/assets/index-QRVMtWU-.js   471.12 kB │ gzip: 118.02 kB
✓ built in 903ms
```
**Result:** Clean build in 903ms with zero TypeScript or bundling errors.

---

## 7. Remaining Firebase Console Setup & Requirements

Before enabling live Firebase Authentication in a production environment:

1. **Enable Email/Password Provider:**
   - In Firebase Console: Navigate to **Authentication** -> **Sign-in method**.
   - Click **Email/Password** -> Enable the toggle -> Click **Save**.
   - Do *not* enable Email link (passwordless) unless explicitly required.
2. **Enable Google Provider (Optional):**
   - Click **Add new provider** -> Select **Google** -> Enable toggle.
   - Configure public-facing project name and project support email -> Click **Save**.
3. **Verify Authorized Domains:**
   - In **Authentication** -> **Settings** -> **Authorized domains**.
   - Ensure `localhost` and `127.0.0.1` are present for local testing.
4. **Project Consistency:**
   - Confirm `FIREBASE_PROJECT_ID` in `.env` matches `VITE_FIREBASE_PROJECT_ID` in `frontend/.env`.

---

## 8. Exact Steps to Execute Live Migration & Test Real Sign-In Safely

When authorized to start services and apply the migration to the live PostgreSQL database:

### Step 1: Start PostgreSQL Container
```bash
podman start research-paper-recommender-postgres-1
```

### Step 2: Create a Fresh Pre-Migration Database Backup
```bash
python3 scripts/verify_backup_restore.py
```
Verify the backup file is non-empty, contains `PostgreSQL database dump complete`, and has an accompanying `.sha256` checksum.

### Step 3: Run the Schema Migration
```bash
backend/venv/bin/python -m app.db.migrate_firebase_auth --forward
```
Confirm the output reports `status: "applied"` and row count invariants are preserved.

### Step 4: Verify Migration Invariants
```bash
backend/venv/bin/python -m app.db.migrate_firebase_auth --verify
```
Confirm `ready: true`, `has_firebase_uid: true`, `has_index: true`.

### Step 5: Enable Firebase Mode in `.env`
Edit root `.env`:
```env
FIREBASE_AUTH_ENABLED=true
```

### Step 6: Start Services & Test Real Sign-In
1. Launch development servers or start containers via `scripts/dev-start.sh`.
2. Open `http://localhost:3000` in a web browser.
3. Click **🔑 Sign In** in the header navigation.
4. In the dialog, click **Register**, enter an email and password (min 8 characters), and submit.
5. In browser Developer Tools (Network tab), inspect requests to `/api/v1/auth/firebase-login` or `/api/v1/auth/me`. Verify:
   - Header contains `Authorization: Bearer eyJhbGci...`.
   - Response returns HTTP 200 with user profile containing `firebase_uid`.
   - Local storage does not store raw ID tokens.
6. Test signing out: click `(Sign Out)` in the navbar, verify token is invalidated and session cleared.
7. Test account linking: attempt to sign in with an email matching an existing local account; confirm the modal transitions to the linking prompt and successfully binds upon password entry.

---

## 9. Blockers & Pre-Release Checklist

| Item | Status | Action Required |
| :--- | :--- | :--- |
| **Backend Code Integration** | Complete | None. All modules implemented and passing tests. |
| **Frontend Code Integration** | Complete | None. All components updated and passing tests. |
| **Live Database Migration** | **Pending Service Start** | Start PostgreSQL container (`podman start ...`), create fresh backup, and run `python -m app.db.migrate_firebase_auth --forward`. |
| **Firebase Console Providers** | **User Action Required** | User must enable Email/Password provider in the Firebase project console. |
| **Production Activation** | **Pending Acceptance** | Flip `FIREBASE_AUTH_ENABLED=true` in `.env` after database migration is applied. |

---

*Report prepared by Antigravity Agent for ResearchLens Stage 2B.*
