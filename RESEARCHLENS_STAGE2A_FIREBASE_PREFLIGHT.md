# ResearchLens — Stage 2A: Firebase Authentication Preflight & Architecture Blueprint

**Document Version:** 1.0.0  
**Audit Timestamp:** 2026-10-20T22:46:00+05:30  
**Repository:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Evaluation Mode:** STRICTLY READ-ONLY (Zero source, schema, service, or database mutations)  
**Preflight Gate Decision:** **`READY AFTER SPECIFIED BLOCKERS`**

---

## 1. Executive Summary & Preflight Findings

This preflight audit establishes the definitive, repository-grounded technical blueprint for migrating ResearchLens from its current local symmetric JWT (`HS256`) authentication to **Firebase Authentication (Stage 2)**.

The audit was conducted strictly in read-only mode. In accordance with required safety constraints, no database records were modified, no migrations were executed, no packages were installed, and no running services were altered.

### Critical Preflight Discoveries

1. **Firebase Configuration in `.env` Identified:**
   - Inspection of `.env` revealed that a client-side JavaScript snippet (`const firebaseConfig = { ... }`) was recently pasted into lines 45–61.
   - **Syntax Anomaly:** Because this snippet is written in JavaScript rather than standard shell `KEY=VALUE` format, `python-dotenv` emits 14 syntax parsing warnings on every backend boot.
   - **SDK Scope Distinction:** The pasted parameters (`apiKey`, `authDomain`, `projectId`, `storageBucket`, `messagingSenderId`, `appId`) represent the **Firebase Web Client SDK configuration** (for browser authentication). They do not constitute a **Firebase Admin SDK Service Account JSON key** (which provides privileged server-side access). The preflight blueprint resolves this distinction cleanly.
2. **Relational Foreign Key Binding to `users.username`:**
   - In PostgreSQL, `saved_papers.user_id` and `driut_alerts.user_id` have formal foreign key constraints referencing `users.username` (`VARCHAR(100)`), NOT an integer `users.id`.
   - A naive migration replacing `username` with Firebase `uid` would invalidate all existing user bookmarks and cascade-delete all 85 DRIUT alerts.
   - The blueprint specifies a non-destructive **Federation Bridging Schema** that adds `users.firebase_uid` while strictly preserving `users.username` as the relational foreign key anchor.
3. **Runtime Service Baseline at Audit Time:**
   - Following a host server restart, the Podman container `research-paper-recommender-postgres-1` is in an `exited` state, and native systemd units for FastAPI (`PID 12414`) and Vite (`PID 12454`) are stopped.
   - In adherence to strict read-only execution ("Do not change running services"), services were not restarted during this audit.
   - Vector index on disk (`backend/data/processed/faiss/`) was directly verified at **162 vectors**, **162 ID mappings**, and **162 metadata entries**.
   - Database record invariants from the pre-restart audit baseline: **162 papers**, **7 users**, **5 saved papers**, **3 evidence rows**, **85 DRIUT alerts** (75 valid same-year + 10 exempt Alternative), and verified backup `backups/pg_20261020_200607/` (SHA-256: `4daec4d3...`).
4. **Preflight Readiness Determination:**
   - The architectural design, security boundaries, and migration plans are fully verified and implementation-ready.
   - The project is classified as **`READY AFTER SPECIFIED BLOCKERS`** pending:
     - Formatting the `.env` Firebase credentials into valid environment variables (`VITE_FIREBASE_*` and `FIREBASE_*`).
     - Provisioning the backend Firebase Admin credentials or public JWKS configuration.
     - Starting development services (`./scripts/dev-start.sh`) under authorized execution.

---

## 2. Verified Current Architecture & Source File Index

Every component of the current authentication, credential storage, and authorization subsystem was inspected against the live repository code:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                CURRENT AUTHENTICATION ARCHITECTURE                             │
├──────────────────────────┬─────────────────────────────────────────────────────────────────────┤
│ Component                │ Implementation Details & Exact File Paths                           │
├──────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ Web Client UI Modal      │ frontend/src/components/AuthModal.tsx                               │
│ Client API Service Layer │ frontend/src/services/api.ts (getAuthToken, setAuthToken, request)  │
│ Token Storage            │ Browser sessionStorage (Key: research_auth_token)                   │
│ API Router Binding       │ backend/app/api/v1/endpoints/auth.py                                │
│ Password Hashing         │ backend/app/core/security.py (bcrypt.gensalt(12), verify_password)  │
│ JWT Issuance & Signing   │ backend/app/core/security.py (HS256, create_access_token)           │
│ JWT Validation & Decod   │ backend/app/core/security.py (decode_access_token)                  │
│ Auth Dependency Guard    │ backend/app/api/deps.py (get_current_user, HTTPBearer)              │
│ Admin Privilege Guard    │ backend/app/api/deps.py (get_current_admin_user, is_superuser flag) │
│ Login Rate Limiter       │ backend/app/core/rate_limit.py (SlowAPI, 5/min, reverse proxy IP)   │
│ User Relational Model    │ backend/app/models/user.py (User class, users table)                │
│ Saved Paper Ownership    │ backend/app/models/paper.py (SavedPaper.user_id -> users.username)  │
│ DRIUT Alert Ownership    │ backend/app/models/driut.py (DRIUTAlert.user_id -> users.username)  │
│ Schema Migrations        │ backend/app/db/migrate.py (Idempotent raw SQL DO $$ blocks)         │
│ Admin User Seeding       │ backend/app/db/seed_admin.py (seed_admin_user with strength check)  │
│ Configuration Settings   │ backend/app/core/config.py (Settings, SettingsConfigDict)           │
└──────────────────────────┴─────────────────────────────────────────────────────────────────────┘
```

### Detailed Component Analysis

#### 1. Authentication Endpoints (`backend/app/api/v1/endpoints/auth.py`)
- `POST /api/v1/auth/register`: Accepts `UserRegisterRequest` (`username`, `email`, `password`, `full_name`). Validates case-insensitive uniqueness of username and email against PostgreSQL. Hashes password using bcrypt. Issues a signed HS256 JWT token with `sub: user.username`.
- `POST /api/v1/auth/login`: Accepts `UserLoginRequest` (`username`, `password`). Queries `User` matching username or email. Enforces SlowAPI rate limit (`5/minute` per IP). Verifies password with `verify_password()`. Issues HS256 JWT token.
- `GET /api/v1/auth/me`: Protected route returning `UserResponse` for the caller resolved by `get_current_user`.

#### 2. Security Utilities (`backend/app/core/security.py`)
- `hash_password(password: str) -> str`: Uses `bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12))`.
- `verify_password(plain: str, hashed: str) -> bool`: Safe comparison using `bcrypt.checkpw()`.
- `create_access_token(subject: str, expires_delta: Optional[timedelta]) -> str`: Encodes payload `{"sub": subject, "iat": now, "exp": expire}` signed with `settings.JWT_SECRET_KEY` via `settings.JWT_ALGORITHM` (`HS256`).
- `decode_access_token(token: str) -> Optional[Dict[str, Any]]`: Decodes and validates signature and expiration using `jwt.decode(..., algorithms=["HS256"])`.

#### 3. Authentication Dependency Injection (`backend/app/api/deps.py`)
- `get_current_user(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()), db: Session = Depends(get_db)) -> User`:
  1. Validates presence of Bearer credentials (HTTP 401 if missing).
  2. Calls `decode_access_token(token)` (HTTP 401 if invalid or expired).
  3. Extracts subject: `username = payload.get("sub")` (HTTP 401 if missing).
  4. Queries relational database: `user = db.query(User).filter(User.username == username).first()` (HTTP 401 if not found).
  5. Asserts `user.is_active` (HTTP 403 Forbidden if deactivated).
- `get_current_admin_user(current_user: User = Depends(get_current_active_user)) -> User`:
  1. Inspects `bool(getattr(current_user, "is_superuser", False))`.
  2. Rejects non-admin users with HTTP 403 Forbidden.

#### 4. Rate Limiting (`backend/app/core/rate_limit.py`)
- Configured via SlowAPI using `get_client_ip`.
- Reverse-proxy aware: inspects `X-Forwarded-For` and `X-Real-IP` ONLY if the connecting socket originates from `TRUSTED_PROXIES` (`127.0.0.1`, `::1`, `testclient`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
- Defends against spoofed header lockouts.

#### 5. Frontend Client Implementation (`frontend/src/`)
- `AuthModal.tsx`: Pure React controlled modal toggling between `"login"` and `"register"`. Submits form payloads to `loginUser()` or `registerUser()`. Dispatches `onAuthSuccess(res.user)`.
- `api.ts`:
  - Token stored in `sessionStorage` under key `research_auth_token`.
  - In-memory cached token variable `inMemoryToken` minimizes storage reads.
  - Centralized `request<T>()` attaches `Authorization: Bearer ${token}` to every outgoing HTTP request.
  - Automatically intercepts HTTP 401 responses and purges `sessionStorage` via `clearAuthToken()`.
  - Dispatches global `"auth-state-change"` event on token updates for reactive UI synchronization.

---

## 3. Inspection of `.env` and Firebase Configuration Details

Live read-only inspection of `.env` identified the following Firebase configuration block (sensitive strings redacted):

```javascript
// Lines 50-58 of .env (Live Snapshot)
// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSy*******************************",      // 39 chars, standard Google API Key
  authDomain: "nlpbased.firebaseapp.com",               // Verified Firebase Auth Domain
  projectId: "nlpb****",                                // 8 chars, Project ID
  storageBucket: "nlpbased.firebasestorage.app",         // Google Cloud Storage Bucket
  messagingSenderId: "1004*********",                   // 13 chars, Cloud Messaging Sender
  appId: "1:1004********:web:********************"      // 42 chars, Web Application ID
};
```

### Architectural Implications of Current `.env` State

1. **Parser Incompatibility:** Python's `dotenv.dotenv_values()` expects POSIX shell assignments (`KEY="value"`). The raw JavaScript syntax causes warning messages: `python-dotenv could not parse statement starting at line 46...`.
2. **Missing Frontend Environment Prefix:** Vite requires client-accessible environment variables to be prefixed with `VITE_` (e.g., `VITE_FIREBASE_API_KEY`). Without this prefix, `import.meta.env` in React cannot read them.
3. **Client vs Server Key Distinction:**
   - The credentials in `.env` are **public client identifiers** designed for browser distribution. In Firebase's security model, `apiKey` is an app identifier, not a secret.
   - For backend token verification, the backend requires the **Firebase Project ID** (`projectId`) to verify that the token's audience (`aud`) matches `nlpb****`.
   - If the backend uses the official `firebase-admin` Python SDK for administrative functions (e.g., setting custom claims or revoking tokens), a **Service Account JSON Key** must be provisioned.
   - Alternatively, if the backend uses public JWKS verification (via PyJWT / cryptography), it only requires `FIREBASE_PROJECT_ID` and verifies signatures directly against Google's public certificate endpoint (`https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com`). This avoids managing a sensitive private key file entirely.

---

## 4. Proposed Authentication & Account-Linking Design

To achieve enterprise-grade security without risking data loss or account hijacking, ResearchLens will implement a **Hybrid Federated Identity Architecture**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                      HYBRID FEDERATED IDENTITY ARCHITECTURE                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   [ React 19 Frontend Client ]                                                         │
│         │                                                                              │
│         │ 1. Authenticate via Google OAuth or Email/Password                          │
│         ▼                                                                              │
│   [ Google Firebase Auth Service ]                                                     │
│         │                                                                              │
│         │ 2. Issue RS256 Signed ID Token (JWT)                                         │
│         ▼                                                                              │
│   [ Frontend: api.ts ] ─── 3. Header: "Authorization: Bearer <id_token>" ───┐          │
│                                                                             │          │
│   ┌─────────────────────────────────────────────────────────────────────────┘          │
│   ▼                                                                                    │
│   [ FastAPI Backend: deps.py::get_current_user ]                                       │
│         │                                                                              │
│         │ 4. Cryptographic Verification (Firebase Admin SDK or Google JWKS)             │
│         │    - Assert iss == "https://securetoken.google.com/<PROJECT_ID>"             │
│         │    - Assert aud == "<PROJECT_ID>"                                            │
│         │    - Assert exp > now and auth_time < now                                    │
│         │    - Extract: uid, email, email_verified                                     │
│         ▼                                                                              │
│   [ Collision-Safe Account Resolver ]                                                  │
│         │                                                                              │
│         ├── A. Query by `users.firebase_uid == uid`                                    │
│         │      └─ Found: Return user (Immediate fast path)                             │
│         │                                                                              │
│         └── B. Not found by `firebase_uid`:                                            │
│                ├── Check if `email_verified == True`                                   │
│                │     ├─ Yes & `users.email == email` exists:                           │
│                │     │    ├─ User has no `firebase_uid`: Link safely & set UID         │
│                │     │    └─ User has different `firebase_uid`: REJECT (409 Conflict)  │
│                │     │                                                                 │
│                │     └─ No existing email or new user:                                 │
│                │          └─ Auto-provision new User record:                           │
│                │             username = derive_collision_free_handle(email, uid)       │
│                │             firebase_uid = uid                                        │
│                │             email = email                                             │
│                │             hashed_password = NULL (or "!federated")                  │
│                │             is_superuser = False                                      │
│                │                                                                       │
│                └─ `email_verified == False`: REJECT (403 Unverified Email)             │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Core Security Rules for Account Linking

1. **Zero Client Trust:**
   The backend will never accept a client-asserted `uid`, `email`, or `username`. All identity attributes are derived strictly from the cryptographically verified claims of the Firebase ID token.
2. **Strict Email-Verification Prerequisite for Linking:**
   An existing local account will **never** be linked to a Firebase identity unless `email_verified == True` in the token. This completely prevents account takeover attacks where an adversary registers a Firebase account using a target researcher's email.
3. **No Cross-Linking Collisions:**
   If a local user account already has an assigned `firebase_uid` (`user.firebase_uid is not None`), and a different Firebase UID claims that email, the request is rejected with `HTTP 409 Conflict`.
4. **Preservation of Relational Identifiers:**
   When a user links their Firebase account, their `users.username` and `users.id` remain unchanged. Because `saved_papers.user_id` and `driut_alerts.user_id` store `username`, all bookmarks and DRIUT alerts remain associated with the researcher without any cascading updates.
5. **Fail-Closed Dual-Mode Switch:**
   The system will support a configuration toggle: `FIREBASE_AUTH_ENABLED: bool`.
   - When `FIREBASE_AUTH_ENABLED=False` (Development / Test): Decodes local HS256 JWTs using `JWT_SECRET_KEY`.
   - When `FIREBASE_AUTH_ENABLED=True` (Production): Strictly validates Firebase RS256 tokens. Local HS256 tokens are rejected with `HTTP 401 Unauthorized`.
   - In production (`ENVIRONMENT=production`), if `FIREBASE_AUTH_ENABLED=True` but Firebase configuration is invalid, the backend **fails closed on startup** with `RuntimeError` rather than silently degrading.

---

## 5. Schema & Migration Impact Table

The proposed migration requires modifying only the `users` table, leaving all research data, vectors, evidence, and alerts completely untouched.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   SCHEMA IMPACT ANALYSIS                                       │
├───────────────────┬──────────────────────┬──────────────────────┬──────────────────────────────┤
│ Table / Relation  │ Current Column State │ Proposed Migration   │ Backward Compatibility Notes │
├───────────────────┼──────────────────────┼──────────────────────┼──────────────────────────────┤
│ users             │ id (SERIAL PK)       │ No change            │ Preserves integer ID         │
│                   │ username (VARCHAR 50)│ No change            │ Foreign key anchor preserved │
│                   │ email (VARCHAR 255)  │ No change            │ Preserves unique email       │
│                   │ hashed_password (255)│ ALTER COLUMN NULLABLE│ Allows federated users with  │
│                   │                      │                      │ no local password            │
│                   │ is_active (BOOLEAN)  │ No change            │ Preserves deactivation guard │
│                   │ is_superuser (BOOL)  │ No change            │ Preserves admin authorization│
│                   │ [NEW COLUMN]         │ ADD COLUMN           │ Indexed, unique, maps to     │
│                   │                      │ firebase_uid VARCHAR │ Firebase UID (28-128 chars)  │
├───────────────────┼──────────────────────┼──────────────────────┼──────────────────────────────┤
│ saved_papers      │ user_id (VARCHAR 100)│ ZERO CHANGES         │ Foreign key to users.username│
│                   │ paper_id (INTEGER FK)│                      │ remains 100% intact; 5 saved │
│                   │ notes, tags, created │                      │ papers completely preserved  │
├───────────────────┼──────────────────────┼──────────────────────┼──────────────────────────────┤
│ driut_alerts      │ user_id (VARCHAR 100)│ ZERO CHANGES         │ Foreign key to users.username│
│                   │ saved_paper_id (FK)  │                      │ remains 100% intact; 85 live │
│                   │ trigger_paper_id (FK)│                      │ alerts completely preserved  │
├───────────────────┼──────────────────────┼──────────────────────┼──────────────────────────────┤
│ papers            │ 162 catalog records  │ ZERO CHANGES         │ Zero metadata or schema      │
│                   │                      │                      │ modifications                │
├───────────────────┼──────────────────────┼──────────────────────┼──────────────────────────────┤
│ paper_evidence    │ 3 evidence rows      │ ZERO CHANGES         │ Zero metadata or schema      │
│                   │                      │                      │ modifications                │
├───────────────────┼──────────────────────┼──────────────────────┼──────────────────────────────┤
│ FAISS Vector Store│ 162 vectors, 768-dim │ ZERO CHANGES         │ No re-indexing or rebuild;   │
│                   │ IndexFlatIP          │                      │ embeddings remain bit-exact  │
└───────────────────┴──────────────────────┴──────────────────────┴──────────────────────────────┘
```

### Planned Migration Script (`backend/app/db/migrate_firebase_auth.py`)

In keeping with repository conventions (`migrate.py`, `migrate_pubmed_dates.py`), the migration will be an idempotent, transactional Python script using raw SQL:

```sql
-- Forward Migration DDL (Idempotent)
BEGIN;

-- 1. Add firebase_uid column if not exists
ALTER TABLE users ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR(128);

-- 2. Create unique index on firebase_uid
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_firebase_uid ON users (firebase_uid);

-- 3. Relax NOT NULL constraint on hashed_password for federated OAuth users
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

COMMIT;
```

```sql
-- Rollback DDL (If emergency rollback is required)
BEGIN;
DROP INDEX IF EXISTS ix_users_firebase_uid;
ALTER TABLE users DROP COLUMN IF EXISTS firebase_uid;
-- Note: hashed_password remains nullable or can be repopulated with dummy hashes
COMMIT;
```

---

## 6. Phased Implementation Plan & Acceptance Tests

The implementation is broken into four sequential phases, each with explicit acceptance tests:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             STAGE 2 IMPLEMENTATION PHASES                              │
├───────┬───────────────────────────────┬────────────────────────────┬───────────────────┤
│ Phase │ Description                   │ Files Modified / Created   │ Acceptance Gate   │
├───────┼───────────────────────────────┼────────────────────────────┼───────────────────┤
│ P1    │ Configuration & SDK Setup     │ .env, .env.example,        │ Clean dotenv parse│
│       │                               │ backend/requirements.txt,  │ with zero syntax  │
│       │                               │ backend/app/core/config.py │ warnings; boot OK │
├───────┼───────────────────────────────┼────────────────────────────┼───────────────────┤
│ P2    │ Database Schema Migration     │ backend/app/models/user.py │ `firebase_uid`    │
│       │                               │ migrate_firebase_auth.py   │ added; row counts │
│       │                               │                            │ 100% invariant    │
├───────┼───────────────────────────────┼────────────────────────────┼───────────────────┤
│ P3    │ Backend Token & Auth Guards   │ backend/app/core/auth.py,  │ Pytest suite with │
│       │                               │ backend/app/api/deps.py,   │ mock Firebase ID  │
│       │                               │ endpoints/auth.py          │ tokens (100% pass)│
├───────┼───────────────────────────────┼────────────────────────────┼───────────────────┤
│ P4    │ Frontend Client Integration   │ frontend/package.json,     │ Live login via    │
│       │                               │ frontend/src/services/     │ Firebase; session │
│       │                               │ firebase.ts, AuthModal.tsx │ saved & reactive  │
└───────┴───────────────────────────────┴────────────────────────────┴───────────────────┘
```

### Phase Details

#### Phase 1: Environment & Dependency Normalization
- Format `.env` to convert the JavaScript object into valid shell environment variables:
  ```bash
  # Client-side Firebase Configuration (Vite)
  VITE_FIREBASE_API_KEY="AIzaSy..."
  VITE_FIREBASE_AUTH_DOMAIN="nlpbased.firebaseapp.com"
  VITE_FIREBASE_PROJECT_ID="nlpb..."
  VITE_FIREBASE_STORAGE_BUCKET="nlpbased.firebasestorage.app"
  VITE_FIREBASE_MESSAGING_SENDER_ID="1004..."
  VITE_FIREBASE_APP_ID="1:1004...:web:..."

  # Backend Firebase Configuration (FastAPI)
  FIREBASE_AUTH_ENABLED=false  # Toggle to true during testing
  FIREBASE_PROJECT_ID="nlpb..."
  FIREBASE_CREDENTIALS_PATH="" # Optional service account JSON
  ```
- Add `firebase-admin>=6.4.0` or `PyJWT[crypto]>=2.9.0` to `backend/requirements.txt`.
- Add Firebase settings to `Settings` in `backend/app/core/config.py`.

#### Phase 2: Database Schema Migration
- Update `backend/app/models/user.py` to add `firebase_uid = Column(String(128), unique=True, index=True, nullable=True)`.
- Make `hashed_password` nullable.
- Author `backend/app/db/migrate_firebase_auth.py` and run dry-run verification against an isolated test database.
- Execute forward migration against PostgreSQL, verifying `papers=162`, `users=7`, `saved_papers=5`, `driut_alerts=85`.

#### Phase 3: Backend Token Verification & Auth Guards
- Create `backend/app/core/firebase_auth.py` with `verify_firebase_id_token(token: str) -> Dict[str, Any]`.
  - Supports verification via `firebase_admin.auth.verify_id_token(token)` OR direct Google JWKS verification (`https://www.googleapis.com/service_accounts/v1/jwk/...`).
- Refactor `get_current_user` in `backend/app/api/deps.py`:
  - When `settings.FIREBASE_AUTH_ENABLED` is active, verify Firebase ID token.
  - Execute collision-safe user lookup and auto-provisioning.
- Refactor `get_current_admin_user` in `backend/app/api/deps.py`:
  - Check Firebase custom claim `admin == True` OR local `user.is_superuser == True`.
- Update backend unit tests in `backend/tests/test_auth_and_isolation.py` with mock Firebase token generator fixtures.

#### Phase 4: Frontend Client & Modal Integration
- Run `npm install firebase` in `frontend/`.
- Author `frontend/src/services/firebase.ts` exporting initialized `auth` and provider instances (`googleProvider`).
- Update `frontend/src/components/AuthModal.tsx`:
  - Add "Sign in with Google" button with clean SVG branding.
  - Implement Email/Password login via `signInWithEmailAndPassword(auth, email, password)`.
  - Implement Email/Password registration via `createUserWithEmailAndPassword(auth, email, password)`.
  - On auth state resolution, retrieve token: `const idToken = await user.getIdToken()`.
  - Store token in `sessionStorage` via `setAuthToken(idToken)`.
- Update Vitest suites in `frontend/src/components/AuthModal.test.tsx` and `frontend/src/services/api.test.ts`.

---

## 7. Security Risks, Rollback Requirements & Unresolved Decisions

### Security Risks & Defenses

1. **Risk: Unverified Email Hijacking**
   - *Threat:* An attacker creates a Firebase Email/Password account with `victim@institution.edu` without verifying the email, then logs in to hijack the victim's existing local ResearchLens account.
   - *Defense:* The backend resolver strictly enforces `decoded_token.get("email_verified") is True` before allowing any account linking. If `email_verified` is False, the backend returns `HTTP 403 Forbidden: Email address unverified`.
2. **Risk: Privilege Escalation via User-Controlled Claims**
   - *Threat:* A malicious user sets client-side metadata or attempts to inject `admin: true` in their token.
   - *Defense:* Firebase custom claims can only be written using the Firebase Admin SDK on a trusted server, never by the client SDK. The backend authorization guard (`get_current_admin_user`) relies strictly on verified server-side claims or the local database `is_superuser` column.
3. **Risk: Silent Fallback to Weak Security**
   - *Threat:* In production, a misconfiguration or network failure causes the system to accept default local JWTs.
   - *Defense:* The configuration validator asserts that when `ENVIRONMENT=production`, `FIREBASE_AUTH_ENABLED` must be strictly validated. If token verification fails, it fails closed with HTTP 401; no fallback token decoding is attempted.

### Rollback Requirements

If unexpected issues arise during Stage 2 implementation:
1. **Instant Application Rollback:** Set `FIREBASE_AUTH_ENABLED=false` in `.env` and restart the backend. The backend immediately reverts to local HS256 JWT decoding with zero downtime and zero database mutations.
2. **Schema Rollback:** If the `firebase_uid` column must be removed, execute the rollback script `backend/app/db/migrate_firebase_auth.py --rollback`. Because `firebase_uid` is an independent nullable column with no foreign key dependencies, dropping it does not affect any other table.
3. **Database Snapshot:** The pre-remediation backup `backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz` remains intact and provides a complete recovery baseline.

### Unresolved Decisions for User Review

1. **Admin User Linking Strategy:**
   - How should the existing local `admin` account (username: `admin`, email: `admin@research.local`) be linked to Firebase?
   - *Option A (Recommended):* When the administrator logs in via Firebase Google OAuth with their real institutional email (e.g., `admin@institution.edu`), an operator runs a one-line CLI utility:
     `./backend/venv/bin/python backend/app/db/link_admin_firebase.py --email admin@institution.edu --username admin`
   - *Option B:* Set a custom claim `admin: true` on the Firebase user in the Firebase Console.
2. **Local Password Login in Development:**
   - Should local username/password registration remain available in development mode (`ENVIRONMENT=development`) for offline coding when internet access to Google is unavailable?
   - *Recommendation:* Keep dual-mode support in development (`FIREBASE_AUTH_ENABLED=false`), while enforcing strict Firebase-only authentication when `FIREBASE_AUTH_ENABLED=true`.

---

## 8. Baseline Test Commands & Results

To establish an authoritative pre-migration baseline, automated test suites were freshly executed during this preflight session.

### Freshly Executed Test Runs (October 20, 2026, 22:44–22:45 IST)

```
┌────────────────────────────────────────────────────────┬─────────┬──────────┬──────────┐
│ Test Command                                           │ Passed  │ Failed   │ Duration │
├────────────────────────────────────────────────────────┼─────────┼──────────┼──────────┤
│ pytest backend/tests/test_auth_and_isolation.py -q     │ 13 pass │ 0 fail   │ 18.74 s  │
│ pytest backend/tests/test_isolation_verification.py -q │ 4 pass* │ 0 fail   │  8.39 s  │
│ vitest run src/components/AuthModal.test.tsx           │ 3 pass  │ 0 fail   │  0.82 s  │
└────────────────────────────────────────────────────────┴─────────┴──────────┴──────────┘
* Note: 3 tests in test_isolation_verification.py were skipped due to live DB service in exited state.
```

### Cumulative Automated Test Baseline (Historical Report Claims)
- Full Backend Pytest Suite: **329 passed, 0 failed** in 101.01s across 24 test modules (`RESEARCHLENS_STAGE1_COMPLETION_AUDIT.md`).
- Full Frontend Vitest Suite: **66 passed, 0 failed** in 1.52s across 8 test suites (`App.test.tsx`, `api.test.ts`, etc.).
- Frontend Production Build: `tsc -b && vite build` compiled in 752ms.

---

## 9. Data-Preservation Invariants & Safe Validation Plan

### Live State Invariants

```
┌─────────────────────────────────┬───────────────────┬──────────────────────────────────────────┐
│ Entity / Store                  │ Baseline Value    │ Verification Method & Source             │
├─────────────────────────────────┼───────────────────┼──────────────────────────────────────────┤
│ PostgreSQL `papers`             │ 162 records       │ Verified pre-restart live query; backup  │
│ PostgreSQL `users`              │ 7 users           │ Verified pre-restart live query; backup  │
│ PostgreSQL `saved_papers`       │ 5 records         │ Verified pre-restart live query; backup  │
│ PostgreSQL `paper_evidence`     │ 3 records         │ Verified pre-restart live query; backup  │
│ PostgreSQL `driut_alerts`       │ 85 alerts         │ Verified post-remediation query; backup  │
│ FAISS Vectors (`IndexFlatIP`)   │ 162 vectors       │ Live disk inspection (ntotal=162, d=768) │
│ FAISS Metadata (`id_map`)       │ 162 entries       │ Live disk inspection (len=162)           │
│ FAISS Metadata (`metadata`)     │ 162 entries       │ Live disk inspection (len=162)           │
│ Verified SQL Backup Checksum    │ 4daec4d3...       │ backups/pg_20261020_200607/ (SHA-256)    │
└─────────────────────────────────┴───────────────────┴──────────────────────────────────────────┘
```

*Note on Live Service State:* At the time of this audit, direct TCP/IP database queries to `localhost:5432` returned `Connection refused` because the Podman container `research-paper-recommender-postgres-1` is in an `exited` state following the host system restart. Under the strict read-only execution constraint ("Do not change running services"), the container was not started. FAISS files on disk were directly inspected and verified at 162 vectors.

### Safe Validation Plan for Implementation
1. **Pre-Execution Snapshot:** Before executing any migration, generate an updated database dump:
   ```bash
   pg_dump -h localhost -U postgres research_papers | gzip > backups/pg_pre_firebase_$(date +%Y%m%d_%H%M%S).sql.gz
   ```
2. **Schema Invariant Assertion:** After applying the forward migration, assert that:
   - `SELECT count(*) FROM papers` == 162
   - `SELECT count(*) FROM saved_papers` == 5
   - `SELECT count(*) FROM driut_alerts` == 85
   - `SELECT count(*) FROM paper_evidence` == 3
3. **Vector Invariant Assertion:** Assert that `research_index.faiss` vector count remains exactly 162 with identical SHA-256 hash.

---

## 10. Preflight Gate Recommendation

```
================================================================================
PREFLIGHT DECISION: READY AFTER SPECIFIED BLOCKERS
================================================================================
```

### Specified Blockers to Resolve Before Code Implementation Begins:

1. **Blocker 1: Normalize `.env` Firebase Credentials Format**
   - *Requirement:* Convert the raw JavaScript object snippet in `.env` into valid shell environment variables:
     - Prefix frontend variables with `VITE_FIREBASE_*` for Vite client consumption.
     - Add `FIREBASE_PROJECT_ID` and `FIREBASE_AUTH_ENABLED` for FastAPI backend consumption.
     - Eliminate the JavaScript `const firebaseConfig = { ... }` syntax to silence `python-dotenv` warnings.
2. **Blocker 2: Determine Backend Verification Mode**
   - *Requirement:* Confirm whether the backend will verify ID tokens via:
     - **Option A (Simpler, zero secret files):** Public Google JWKS endpoint matching `aud == FIREBASE_PROJECT_ID` (uses standard `PyJWT[crypto]` or `cryptography`).
     - **Option B (Full Firebase Admin):** Service Account JSON private key file configured via `FIREBASE_CREDENTIALS_PATH`.
3. **Blocker 3: Authorized Service Startup**
   - *Requirement:* Under explicit user authorization, run `./scripts/dev-start.sh` to start PostgreSQL, FastAPI, and Vite for live integration testing.

Once these three operational prerequisites are addressed, implementation may proceed immediately according to the phased work breakdown in Section 6.
