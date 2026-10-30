# ResearchLens — Developer & Collaborator Setup Guide

Welcome to **ResearchLens**! This guide provides comprehensive instructions for extracting, configuring, running, and testing ResearchLens on your local workstation.

---

## Table of Contents

1. [Extracting and Opening the Project](#1-extracting-and-opening-the-project)
2. [Prerequisites and System Requirements](#2-prerequisites-and-system-requirements)
3. [Backend Setup (Python Virtual Environment)](#3-backend-setup)
4. [Frontend Setup (React + Vite)](#4-frontend-setup)
5. [Starting Local PostgreSQL](#5-starting-local-postgresql)
6. [Applying Database Migrations & Initializing Catalog](#6-applying-database-migrations--initializing-catalog)
7. [Configuring Firebase Google Sign-In](#7-configuring-firebase-google-sign-in)
8. [Starting the Application](#8-starting-the-application)
9. [Health Verification & Automated Tests](#9-health-verification--automated-tests)
10. [AI Provider Configuration (Ollama, Groq, or Deterministic)](#10-ai-provider-configuration)
11. [Troubleshooting Common Issues](#11-troubleshooting-common-issues)

---

## 1. Extracting and Opening the Project

1. Extract the `ResearchLens-Share.zip` archive into your desired projects directory:
   ```bash
   unzip ResearchLens-Share.zip -d research-paper-recommender
   cd research-paper-recommender
   ```
2. Open the directory in **Antigravity IDE**:
   - Launch Antigravity.
   - Select **File → Open Folder...** and choose the `research-paper-recommender` folder.
   - Alternatively, from the terminal:
     ```bash
     agy .
     ```

---

## 2. Prerequisites and System Requirements

| Tool | Recommended Version | Purpose |
| :--- | :--- | :--- |
| **Operating System** | Linux (Fedora, Ubuntu, Debian), macOS, or WSL2 | Host development environment |
| **Python** | 3.10 – 3.14 (tested on 3.14 / 3.12) | FastAPI backend, NLP embeddings, FAISS |
| **Node.js** | >= 18.x (v20 or v22 LTS recommended) | React 18, Vite, Vitest |
| **npm** | >= 9.x | Frontend package manager |
| **Container Engine** | Podman or Docker (with Compose) | Local isolated PostgreSQL database |
| **Ollama** *(Optional)* | >= 0.3.x | Local privacy-first LLM inference (`qwen2.5:3b`) |

### Linux Package Dependencies (if building wheels from source):
On Fedora/RHEL:
```bash
sudo dnf install -y python3-devel gcc gcc-c++ make
```
On Ubuntu/Debian:
```bash
sudo apt update && sudo apt install -y python3-dev build-essential
```

---

## 3. Backend Setup

The FastAPI backend uses standard Python virtual environments.

1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. Return to the project root:
   ```bash
   cd ..
   ```

---

## 4. Frontend Setup

The frontend is built with React, TypeScript, and Vite.

1. Navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Install dependencies using the bundled lockfile:
   ```bash
   npm ci
   # or: npm install
   ```
3. Return to the project root:
   ```bash
   cd ..
   ```

---

## 5. Starting Local PostgreSQL

ResearchLens connects to PostgreSQL via the connection string:
```text
postgresql+psycopg2://postgres:postgres@localhost:5432/research_papers
```

Choose **one** of the following options to run PostgreSQL:

### Option A: Using Podman (Default)
```bash
podman compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres
```
*Or via direct podman command:*
```bash
podman run -d --name research-paper-recommender-postgres-1 \
  -p 127.0.0.1:5432:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=research_papers \
  postgres:16-alpine
```

### Option B: Using Docker
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres
```

### Option C: Using Native PostgreSQL Service
If you run PostgreSQL directly on your host:
```bash
# Verify it is listening on 127.0.0.1:5432
sudo systemctl start postgresql
# Create database and user if not already present:
psql -U postgres -c "CREATE DATABASE research_papers;"
psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';"
```

---

## 6. Applying Database Migrations & Initializing Catalog

With PostgreSQL running, initialize the database schema and public research catalog:

1. **Create database tables:**
   ```bash
   cd backend
   venv/bin/python -m app.db.init_db
   ```
   *This creates the `users`, `papers`, `saved_papers`, `driut_alerts`, and `paper_evidence` tables.*

2. **Seed public academic paper catalog:**
   ```bash
   venv/bin/python -m app.db.seed_catalog
   ```
   *This populates the 162 public academic research papers from `papers_meta.json` into PostgreSQL so that PostgreSQL and the pre-computed FAISS vector index are in 100% sync.*

3. **Verify FAISS & PostgreSQL consistency:**
   ```bash
   venv/bin/python ../scripts/reconcile_faiss_postgres.py
   ```
   *You should see `is_consistent: true` with 162 vectors and 162 database papers.*

4. Return to root:
   ```bash
   cd ..
   ```

---

## 7. Configuring Firebase Google Sign-In

ResearchLens includes pre-configured Firebase web client credentials in `frontend/.env` and `backend/.env`.

### Client Setup:
The frontend `.env` contains:
- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_PROJECT_ID`
- `VITE_FIREBASE_APP_ID`

The backend `.env` contains:
- `FIREBASE_AUTH_ENABLED=true`
- `FIREBASE_PROJECT_ID=...`

### Firebase Console Requirements:
If configuring your own Firebase project:
1. Go to [Firebase Console](https://console.firebase.google.com/).
2. Enable **Authentication → Sign-in method → Google**.
3. Under **Authentication → Settings → Authorized domains**, ensure:
   - `localhost`
   - `127.0.0.1`
4. Token validation uses Google's public cryptographic keys (`JWKS`) to verify Firebase ID tokens securely. No service-account private key file is needed on local developer machines.

---

## 8. Starting the Application

### Option A: One-Command Launcher (Recommended)
```bash
./start-researchlens.sh
```
- Performs 5-step automated preflight checks.
- Starts or verifies the PostgreSQL container.
- Starts FastAPI backend (`127.0.0.1:8000`) and Vite frontend (`127.0.0.1:3000`).
- Runs health checks and opens the app in your browser.
- *Flags:* `./start-researchlens.sh --no-browser` (skip browser launch), `./start-researchlens.sh --status` (inspect status).

To cleanly stop:
```bash
./stop-researchlens.sh
```

### Option B: Native Development Scripts
```bash
./scripts/dev-start.sh    # Start services in background
./scripts/dev-status.sh   # Check running status and ports
./scripts/dev-stop.sh     # Cleanly terminate services
```

### Option C: Manual Terminal Execution
**Terminal 1 (Backend):**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 (Frontend):**
```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 3000
```

Access the UI at **http://localhost:3000** and API docs at **http://localhost:8000/docs**.

---

## 9. Health Verification & Automated Tests

### 1. Health Endpoint Verification
```bash
curl -s http://127.0.0.1:8000/api/v1/health | jq .
```
Expected output:
```json
{
  "status": "ok",
  "service": "research-paper-recommender",
  "version": "0.1.0",
  "environment": "development",
  "database": "connected"
}
```

### 2. Backend Automated Test Suite
```bash
cd backend
venv/bin/pytest tests/test_firebase_auth.py tests/test_faiss_consistency.py tests/test_auth_and_isolation.py
```

### 3. Frontend Automated Test Suite
```bash
cd frontend
npm test -- --run
```

---

## 10. AI Provider Configuration

ResearchLens operates across three AI environments:

| Mode | Configuration | Description |
| :--- | :--- | :--- |
| **Local AI (Ollama)** | `RESEARCHLENS_AI_PROVIDER=local_first`<br>`RESEARCHLENS_OLLAMA_MODEL=qwen2.5:3b` | 100% private, runs entirely on your local GPU/CPU. |
| **Cloud AI (Groq)** | `RESEARCHLENS_AI_PROVIDER=local_first`<br>`GROQ_API_KEY=gsk_...`<br>`RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT=true` | Ultra-fast cloud inference fallback. |
| **Deterministic (Zero-AI)** | `RESEARCHLENS_AI_ENABLED=false` | Pure offline NLP extraction; zero API keys or LLM memory required. |

*See `COLLABORATOR_AI_SETUP_GUIDE.md` for full AI provider details and privacy controls.*

---

## 11. Troubleshooting Common Issues

### Port 5432, 8000, or 3000 already in use
Check what process is listening:
```bash
ss -tulpn | grep -E ':5432|:8000|:3000'
```
Stop lingering processes or containers before restarting.

### PostgreSQL Connection Refused
Ensure the container or service is active:
```bash
podman ps -a --filter name=postgres
# or: docker ps -a --filter name=postgres
```
Test direct connectivity:
```bash
nc -zv 127.0.0.1 5432
```

### Pydantic Settings Validation Error on `JWT_SECRET_KEY`
Ensure `ENVIRONMENT=development` in your `.env` or `backend/.env`. In production mode, Pydantic requires a 32+ character non-default secret key.

### Node / npm Module Issues
If you encounter module resolution issues in frontend:
```bash
cd frontend
rm -rf node_modules
npm ci
```

---

*HIP HIP HURRAY! You are all set to explore and research with ResearchLens.*
