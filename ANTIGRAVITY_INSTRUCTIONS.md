# Instructions for Antigravity AI Coding Assistant

When assisting the user with setting up, running, or developing in this repository, follow these operating principles:

## 1. Inspect Setup Guide Before Action
- Read and adhere to [`SETUP.md`](file:///./SETUP.md) for standard commands, dependency installation, and service management.
- Do not invent non-existent scripts, change port numbers, or reorganize repository files.

## 2. Environment & Dependency Bootstrapping
- **Backend**: Ensure Python virtual environment exists at `backend/venv`. If missing, create it (`python3 -m venv backend/venv`) and install dependencies from `backend/requirements.txt`.
- **Frontend**: Ensure `frontend/node_modules` exists. If missing, run `npm ci` (or `npm install`) inside `frontend/`.
- **Database**: Check if PostgreSQL is listening on `127.0.0.1:5432`. If not, start it using:
  ```bash
  podman compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres
  # or: docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres
  ```
- **Tables & Catalog**:
  - Run `python -m app.db.init_db` (from `backend/` with venv) to ensure tables exist.
  - Run `python -m app.db.seed_catalog` (from `backend/` with venv) to populate the 162 catalog papers if the database is newly created.
  - Do NOT reset or drop existing database tables.

## 3. Preserving Configuration & Credentials
- The included `.env`, `backend/.env`, and `frontend/.env` files contain approved working configurations (Firebase web settings, Groq API key, dev database URL).
- Do NOT overwrite existing `.env` files with empty placeholders.
- Do NOT print API keys, tokens, or credentials in chat output or logs.
- Never hardcode credentials into source code.

## 4. Service Lifecycle Management
- To start all services: `./start-researchlens.sh` (or `./start-researchlens.sh --no-browser`).
- To check running status: `./scripts/dev-status.sh` or `./start-researchlens.sh --status`.
- To cleanly stop services: `./stop-researchlens.sh`.
- Do NOT kill processes randomly or terminate system processes by arbitrary port kills.

## 5. Testing & Verification
- Backend tests: `cd backend && venv/bin/pytest tests/test_firebase_auth.py tests/test_faiss_consistency.py`
- Frontend tests: `cd frontend && npm test -- --run`
- Frontend build check: `cd frontend && npm run build`
