# ResearchLens — Stage 2B: Database Migration & Authentication Activation Completion Report

**Document ID:** `RESEARCHLENS-STAGE2B-COMPLETION-20261020`  
**Execution Timestamp:** 2026-10-20T23:45:00+05:30 (18:15:00 UTC)  
**Repository:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Phase:** Stage 2B — Database Migration, Administrator Security & Controlled Activation  
**Status:** **DATABASE MIGRATION COMPLETED & VERIFIED; RECOVERABLE BACKUP CREATED; AWAITING FIREBASE CONSOLE PROVIDER ENABLING BEFORE ACTIVATION**

---

## 1. Executive Summary

This report documents the completion of the database migration and the validation of existing-user, administrator, and Firebase authentication mechanisms for ResearchLens Stage 2B.

1. **Database Restoration:** The existing Podman PostgreSQL container `research-paper-recommender-postgres-1` was safely started without recreation, parameter alteration, or volume reset. The target database `research_papers` was confirmed.
2. **Fresh Verified Backup:** A fresh, compressed backup was generated and cryptographically verified:
   - **Artifact:** `backups/pg_20261020_234051/research_papers_20261020_234051.sql.gz`
   - **SHA-256 Checksum:** `6e63c7979c796414da1876614930be5524a0a9b570f1bcc28c3a4286d7b8f295`
   - **Restore Validation:** Successfully restored and verified in isolated database `restore_verify_20261020_234051` prior to database teardown.
3. **Firebase Schema Migration:** Executed `migrate_firebase_auth_forward` against the live PostgreSQL database. The migration succeeded with 100% data preservation and row-count invariant verification:
   - Added `users.firebase_uid VARCHAR(128)` with unique partial index `ix_users_firebase_uid`.
   - Made `users.hashed_password` nullable for Firebase-only accounts.
   - Re-running forward migration proved complete idempotency with zero duplicate objects.
4. **Administrator Account Protection:** The existing administrator account (`username: admin`, `id: 276`, `is_superuser: true`) was verified and preserved. In accordance with safety rules, **no automatic linking to an unverified email was performed**. A dual-proof linking procedure (via API and CLI) is implemented and ready.
5. **Live Firebase Integration Check:** A probe against the live Google Identity Toolkit API using configured credentials revealed `CONFIGURATION_NOT_FOUND`. This indicates that the **Email/Password sign-in provider has not yet been enabled in the Firebase Console**.
6. **Controlled Activation Status:** In accordance with Step 6 safety instructions, **`FIREBASE_AUTH_ENABLED` remains `false`** in the active environment. Activation instructions and a robust rollback procedure are documented awaiting the user's provider activation and explicit approval.

---

## 2. Step 1 — Local Database Restoration & Confirmation

### Container Inspection & Lifecycle
- **Container Name:** `research-paper-recommender-postgres-1`
- **Container ID:** `9362adf3bda5`
- **Image:** `docker.io/library/postgres:16-alpine`
- **Volume Mount:** `research-paper-recommender_postgres_data -> /var/lib/postgresql/data`
- **Initial State:** `Exited (0) 47 hours ago`

### Command Executed:
```bash
podman start research-paper-recommender-postgres-1
```
*Result:* Container started with exit code `0`.

### Health & Database Confirmation:
```bash
podman exec research-paper-recommender-postgres-1 pg_isready -U postgres
# Output: /var/run/postgresql:5432 - accepting connections

podman exec research-paper-recommender-postgres-1 psql -U postgres -l
# Output confirmed database: research_papers (Owner: postgres, Encoding: UTF8)
```

---

## 3. Step 2 — Fresh Recoverable Backup & Pre-Migration Invariants

### Execution Command:
```bash
python3 scripts/verify_backup_restore.py
```

### Actual Execution Output:
```
================================================================================
STEP B: FAILURE-SAFE BACKUP & RESTORATION TEST
================================================================================
Container: research-paper-recommender-postgres-1
Database: research_papers
Backup Directory: /home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backups/pg_20261020_234051
Running pg_dump...
pg_dump output size: 247,727 bytes
Dump completion signature verified successfully.
Compressed backup saved: .../backups/pg_20261020_234051/research_papers_20261020_234051.sql.gz
SHA-256: 6e63c7979c796414da1876614930be5524a0a9b570f1bcc28c3a4286d7b8f295

--- TESTING RESTORATION INTO ISOLATED DATABASE: restore_verify_20261020_234051 ---
CREATE DATABASE
Restored counts in isolated test database:
  papers: 162
  users: 7
  saved_papers: 5
  driut_alerts: 85
  paper_evidence: 3
DROP DATABASE
Isolated test database restore_verify_20261020_234051 cleanly dropped.

[STEP B PASSED] Verified failure-safe backup created and restored with 100% data integrity.
```

### Backup Artifact Details:
- **File:** `backups/pg_20261020_234051/research_papers_20261020_234051.sql.gz`
- **SHA-256:** `6e63c7979c796414da1876614930be5524a0a9b570f1bcc28c3a4286d7b8f295`
- **Integrity Marker:** Verified `"PostgreSQL database dump complete"` signature.
- **Previous Backup Preserved:** `backups/pg_20261020_200607/research_papers_20261020_200607.sql.gz` remains intact.

### Pre-Migration Database Invariants:
| Entity / Table | Pre-Migration Count | Status |
| :--- | :--- | :--- |
| `papers` | **162** | Preserved |
| `users` | **7** | Preserved |
| `saved_papers` | **5** | Preserved |
| `paper_evidence` | **3** | Preserved |
| `driut_alerts` | **85** | Preserved (75 same-year + 10 Alternative) |
| FAISS Vectors (`research_index.faiss`) | **162** (dim: 768) | Unchanged |
| FAISS Metadata (`papers_meta.json`) | **162** entries | Unchanged |

---

## 4. Step 3 — Firebase Schema Migration Execution & Verification

### A. Pre-Migration Verification
```bash
venv/bin/python -m app.db.migrate_firebase_auth --verify
```
**Pre-migration result:**
```json
{
  "accessible": true,
  "has_firebase_uid": false,
  "has_index": false,
  "hashed_password_nullable": false,
  "ready": false
}
```

### B. Forward Migration Execution
```bash
venv/bin/python -m app.db.migrate_firebase_auth --forward
```
**Actual output:**
```json
{
  "success": true,
  "status": "applied",
  "dialect": "postgresql",
  "counts": {
    "users": 7,
    "papers": 162,
    "saved_papers": 5,
    "paper_evidence": 3,
    "driut_alerts": 85
  }
}
```

### C. Post-Migration Verification
```bash
venv/bin/python -m app.db.migrate_firebase_auth --verify
```
**Post-migration result:**
```json
{
  "accessible": true,
  "has_firebase_uid": true,
  "has_index": true,
  "hashed_password_nullable": true,
  "ready": true
}
```

### D. Idempotency Test
Running `migrate_firebase_auth --forward` a second time against the live database returned identical status `applied` with identical counts, confirming complete idempotency without generating duplicate objects.

### E. Direct PostgreSQL Schema Inspection (`\d users`):
```
                                         Table "public.users"
     Column      |           Type           | Collation | Nullable |              Default              
-----------------+--------------------------+-----------+----------+-----------------------------------
 id              | integer                  |           | not null | nextval('users_id_seq'::regclass)
 username        | character varying(50)    |           | not null | 
 email           | character varying(255)   |           | not null | 
 hashed_password | character varying(255)   |           |          | 
 full_name       | character varying(100)   |           |          | 
 is_active       | boolean                  |           | not null | true
 created_at      | timestamp with time zone |           |          | now()
 updated_at      | timestamp with time zone |           |          | now()
 is_superuser    | boolean                  |           | not null | false
 firebase_uid    | character varying(128)   |           |          | 
Indexes:
    "users_pkey" PRIMARY KEY, btree (id)
    "ix_users_email" btree (email)
    "ix_users_firebase_uid" UNIQUE, btree (firebase_uid) WHERE firebase_uid IS NOT NULL
    "ix_users_id" btree (id)
    "ix_users_username" btree (username)
    "users_email_key" UNIQUE CONSTRAINT, btree (email)
    "users_username_key" UNIQUE CONSTRAINT, btree (username)
Referenced by:
    TABLE "driut_alerts" CONSTRAINT "fk_driut_alerts_user_id" FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
    TABLE "saved_papers" CONSTRAINT "fk_saved_papers_user_id" FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
```

### F. Post-Migration Before/After Invariant Comparison:
| Table / Artifact | Pre-Migration Count | Post-Migration Count | Delta | Invariant Status |
| :--- | :--- | :--- | :--- | :--- |
| `papers` | 162 | 162 | 0 | **VERIFIED INTACT** |
| `users` | 7 | 7 | 0 | **VERIFIED INTACT** |
| `saved_papers` | 5 | 5 | 0 | **VERIFIED INTACT** |
| `paper_evidence` | 3 | 3 | 0 | **VERIFIED INTACT** |
| `driut_alerts` | 85 | 85 | 0 | **VERIFIED INTACT** |
| `faiss_index` vectors | 162 | 162 | 0 | **VERIFIED INTACT** |

All foreign key relationships (`saved_papers.user_id -> users.username` and `driut_alerts.user_id -> users.username`) remain valid and intact.

---

## 5. Step 4 — Administrator Account Status & Linking Procedure

### Current Administrator State in PostgreSQL:
```
 id  | username |          email           | is_active | is_superuser | firebase_uid
-----+----------+--------------------------+-----------+--------------+--------------
 276 | admin    | admin@researchlens.local | t         | t            | NULL
```
- The local administrator `admin` retains `is_superuser = true`.
- Password hash (`$2b$12$...`) is preserved.
- `firebase_uid` is currently `NULL`.

### Account Linking Policy Compliance:
- **No Automatic Linking:** The administrator account was **not** linked automatically to any external email address.
- **No Privilege Elevation:** Auto-provisioning of Firebase accounts explicitly assigns `is_superuser = false`.
- **Verified Dual-Proof Linking Procedure:** To link the administrator account to a real Firebase identity, two secure paths are available:

#### Option 1: Via Secure API (`POST /api/v1/auth/link-firebase`)
```bash
curl -X POST http://localhost:8000/api/v1/auth/link-firebase \
  -H "Content-Type: application/json" \
  -d '{
    "username_or_email": "admin",
    "local_password": "<ADMIN_PASSWORD>",
    "firebase_token": "<ADMIN_FIREBASE_ID_TOKEN>"
  }'
```
*Verification enforced by backend:*
1. Validates local account password via `bcrypt.checkpw`.
2. Cryptographically verifies Firebase ID token signature and claims via `verify_firebase_id_token`.
3. Verifies Firebase UID is not bound to any other account.
4. Binds `admin.firebase_uid = token.sub` while preserving `is_superuser = true`.

#### Option 2: Via Dedicated Migration Utility CLI
```bash
venv/bin/python -m app.db.migrate_firebase_auth --link-admin "<ADMIN_FIREBASE_UID>"
```
*Verification enforced by CLI:*
1. Finds `User` where `username == "admin"` and `is_superuser == true`.
2. Verifies `<ADMIN_FIREBASE_UID>` is not already bound to another account.
3. Sets `admin.firebase_uid = clean_uid` and commits atomically.

---

## 6. Step 5 — Test Verification & Results

### A. Backend Test Suites (56 Passed)
```bash
backend/venv/bin/pytest backend/tests/test_firebase_auth.py \
                        backend/tests/test_firebase_migration.py \
                        backend/tests/test_auth_and_isolation.py \
                        backend/tests/test_papers_api.py \
                        backend/tests/test_cors_configuration.py
```
**Output:** `56 passed, 4 warnings in 28.86s`

#### Key Verified Test Cases:
- **Cryptographic Token Verification:** RS256 signature, Google JWKS retrieval, expired token rejection, invalid audience rejection, invalid issuer rejection, and overlong UID rejection.
- **Algorithm Enforcement:** Symmetric `HS256` tokens rejected when Firebase mode is enabled (`test_verify_rejected_hs256_algorithm`).
- **Fail-Closed Verification:** Network failure during JWKS key retrieval fails closed with HTTP 401 (`test_verify_key_retrieval_failure`).
- **Safe Auto-Provisioning:** Non-admin user created with collision-safe username and `hashed_password=None` (`test_firebase_user_resolution_and_auto_provisioning`).
- **Email Collision Shield:** Rejects automatic linking when local user has matching email (`HTTP 409 Conflict`) (`test_reject_ambiguous_email_collision`).
- **Account Linking:** Proof of password + token required; UID collision rejected (`test_safe_account_linking_flow`).
- **Deactivated Users:** Inactive accounts rejected (`HTTP 403 Forbidden`) (`test_deactivated_account_forbidden`).
- **Admin Isolation:** Ordinary Firebase users rejected (`HTTP 403 Forbidden`) from maintenance endpoints (`/api/v1/papers/sync-index`), while superuser accounts succeed (`HTTP 200 OK`) (`test_ordinary_firebase_user_cannot_access_admin_endpoints`).
- **Local Fallback Mode:** Full local registration, password authentication, and session tokens function normally when `FIREBASE_AUTH_ENABLED=false`.
- **Cross-User Isolation:** Saved library entries and DRIUT alerts are strictly isolated between distinct users.

### B. Frontend Test Suites (72 Passed)
```bash
npm test  # in frontend/
```
**Output:** `72 passed across 9 test files in 1.47s`
- Firebase initialization, configuration detection, error formatting, and auth-state listener verified (`src/services/firebase.test.ts`).
- Dynamic Bearer token attachment without insecure `localStorage` caching verified (`src/services/api.test.ts`).
- AuthModal dialog, mode switching, and Escape handling verified (`src/components/AuthModal.test.tsx`).
- Component regression tests (CompareModal, DriutAlertsView, EvidenceModal, ResearchEvolutionView, SavedLibraryView, App) all passed.

### C. Frontend Production Build (0 Errors)
```bash
npm run build  # in frontend/
```
**Output:** Built in 903ms with zero TypeScript or bundling errors.

---

## 7. Live Firebase Integration Probe & Console Requirement

### Probe Execution:
Direct network probes were executed against the Google Identity Toolkit API using the configured project credentials:
```python
# Target: https://identitytoolkit.googleapis.com/v1/accounts:...
# API Key: AIzaSyDf3UCj3bxxKEywUCXTHKu1oX3yHhbmgEY
# Project: nlpbased
```

### Actual Probe Response:
```json
{
  "error": {
    "code": 400,
    "message": "CONFIGURATION_NOT_FOUND",
    "errors": [
      {
        "message": "CONFIGURATION_NOT_FOUND",
        "domain": "global",
        "reason": "invalid"
      }
    ]
  }
}
```

### Diagnostic Finding:
1. Google's JWKS public certificates endpoint (`https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com`) is **online and returning 4 active signing keys**.
2. However, the client sign-in endpoint returns `CONFIGURATION_NOT_FOUND`.
3. In Google Firebase Identity Platform, this error occurs when **Firebase Authentication has not been initialized or no sign-in providers have been enabled** in the project console.

### Required User Action in Firebase Console:
Before a real end-to-end Firebase sign-in can succeed:
1. Open the [Firebase Console](https://console.firebase.google.com/project/nlpbased/authentication).
2. Under **Build** -> **Authentication**, click **Get started** (if not already started).
3. Under the **Sign-in method** tab:
   - Click **Email/Password** -> Toggle **Enable** -> Click **Save**.
   - (Optional) Click **Google** -> Toggle **Enable** -> Select project support email -> Click **Save**.
4. Under the **Settings** -> **Authorized domains** tab:
   - Ensure `localhost` and `127.0.0.1` are present.

---

## 8. Step 6 — Controlled Activation Status & Next Steps

### Current Environment State:
- **`FIREBASE_AUTH_ENABLED=false`** remains set in `.env` and `backend/.env`.
- Database migration is **already executed and active** on PostgreSQL.
- Local authentication continues to service all active sessions without interruption.

### Emergency Rollback & Recovery Procedures:
1. **Revert Authentication Mode:**
   If Firebase authentication encounters issues after activation, simply change `.env`:
   ```env
   FIREBASE_AUTH_ENABLED=false
   ```
   Restart backend. Local HS256 tokens and local password authentication immediately resume handling requests.
2. **Database Schema Rollback:**
   If reverting the database schema is ever required:
   ```bash
   venv/bin/python -m app.db.migrate_firebase_auth --rollback
   ```
   Removes `ix_users_firebase_uid` index and drops `firebase_uid` column.
3. **Database Restoration from Fresh Backup:**
   To restore the verified pre-migration state:
   ```bash
   gunzip -c backups/pg_20261020_234051/research_papers_20261020_234051.sql.gz | \
     podman exec -i research-paper-recommender-postgres-1 psql -U postgres -d research_papers
   ```

---

## 9. Final Pre-Activation Checklist & Approval Step

| Item | Status | Verification Detail |
| :--- | :--- | :--- |
| **PostgreSQL Container** | **RUNNING** | Podman container listening on `127.0.0.1:5432`. |
| **Fresh Backup Created** | **VERIFIED** | `pg_20261020_234051` (SHA-256: `6e63c797...`). |
| **Isolated Restore Test** | **VERIFIED** | Clean restore into `restore_verify_20261020_234051`. |
| **Database Migration** | **APPLIED & VERIFIED** | `firebase_uid` and `ix_users_firebase_uid` present in PostgreSQL. |
| **Row Count Invariants** | **VERIFIED** | 162 papers, 7 users, 5 saved papers, 3 evidence, 85 alerts. |
| **Administrator Protected** | **VERIFIED** | `admin` (id: 276) retains `is_superuser = true`. |
| **Backend Test Suite** | **PASSED** | 56 tests passed, 0 failed. |
| **Frontend Test Suite** | **PASSED** | 72 tests passed, 0 failed. |
| **Frontend Build** | **PASSED** | `tsc -b && vite build` clean in 903ms. |
| **Firebase Console Setup** | **AWAITING USER ACTION** | Enable "Email/Password" in Firebase Console for `nlpbased`. |
| **Activation Toggle** | **AWAITING APPROVAL** | Change `FIREBASE_AUTH_ENABLED=true` in `.env`. |

### Exact Command Awaiting Approval to Complete Activation:
Once the Email/Password provider is enabled in the Firebase Console, run:
```bash
sed -i 's/FIREBASE_AUTH_ENABLED=false/FIREBASE_AUTH_ENABLED=true/' .env backend/.env
```
Followed by starting/restarting the backend process to begin enforcing Firebase ID tokens.
