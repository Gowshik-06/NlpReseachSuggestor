# ResearchLens — Intelligent Research Paper Assistant

**ResearchLens** is a modern, privacy-first research discovery and recommendation platform combining NLP embeddings, FAISS vector search, dynamic academic source integration (arXiv, PubMed, Crossref, Semantic Scholar, CSIR-NIScPR, DBLP), multi-paper structured comparison, and continuous evidence-backed intelligence (DRIUT).

---

## Key Features

- **Semantic & Hybrid Search**: High-performance semantic vector search powered by SPECTER2 / SentenceTransformers and FAISS, alongside keyword and metadata filters.
- **Dynamic Academic Ingestion**: Live search and catalog ingestion from arXiv, PubMed, Semantic Scholar, Crossref, and DBLP.
- **Evidence-Backed Intelligence (DRIUT)**: Dynamic Research Intelligence & Update Tracker continuously analyzes literature shifts and evidence evolution.
- **Multi-Paper Comparison**: Structured matrix comparison across research methodologies, datasets, findings, and trade-offs.
- **Flexible AI Integration**:
  - **Local-First AI**: 100% private on-device inference with Ollama (`qwen2.5:3b` or `llama3.2:3b`).
  - **Cloud AI Failover**: Fast synthesis via Groq cloud API.
  - **Deterministic Baseline**: High-precision rule-based NLP extraction when running offline without LLMs.
- **Secure Authentication**: Firebase Google Sign-In with cryptographic token verification, single `user` role enforcement, and concurrency-safe account provisioning.
- **Modern Responsive UI**: React 18, TypeScript, and Vite with clean design, dark/light aesthetic tokens, and zero visual clutter.

---

## Quickstart

For full prerequisite details, dependency installation, and troubleshooting, see the [Developer Setup Guide](SETUP.md).

### 1. Start Local PostgreSQL
```bash
podman compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres
# or: docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres
```

### 2. Initialize Database & Catalog
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m app.db.init_db
python -m app.db.seed_catalog
cd ..
```

### 3. Install Frontend Dependencies
```bash
cd frontend
npm ci
cd ..
```

### 4. Launch ResearchLens
```bash
./start-researchlens.sh
```
- Frontend: **http://localhost:3000**
- Backend API Docs: **http://localhost:8000/docs**

To stop services:
```bash
./stop-researchlens.sh
```

---

## Technology Stack

- **Frontend**: React 18, TypeScript, Vite, Vitest, Vanilla CSS Design System
- **Backend**: FastAPI, Python 3.12+, SQLAlchemy 2.0, Pydantic v2
- **Vector Database**: FAISS (IndexFlatIP with cosine similarity)
- **Database**: PostgreSQL 16
- **Authentication**: Firebase Auth (Google Sign-In) + JWT
- **Containerization**: Podman / Docker Compose

---

## Documentation

- [Developer & Collaborator Setup Guide](SETUP.md)
- [Antigravity Instructions](ANTIGRAVITY_INSTRUCTIONS.md)
- [Collaborator AI Architecture & Setup Guide](COLLABORATOR_AI_SETUP_GUIDE.md)
- [Startup & Launcher Guide](RESEARCHLENS_STARTUP_GUIDE.md)
- [Architecture Overview](docs/architecture.md)

---

## License

See [LICENSE](LICENSE) for details.
