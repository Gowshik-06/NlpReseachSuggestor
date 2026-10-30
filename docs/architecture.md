# Architecture — Phase 0

This document describes **only what is currently implemented**. It is
updated as each phase lands; it does not describe planned future work in
technical detail (see the root [`README.md`](../README.md) for the phase
list).

## Current architecture

```
                 React Frontend (Vite, TypeScript)
                       |
                       | HTTP (fetch), JSON
                       v
                 FastAPI Backend
                       |
                       | SQLAlchemy (psycopg2)
                       v
                  PostgreSQL
```

- The frontend calls `GET /api/v1/health` through a single centralized API
  client (`frontend/src/services/api.ts`) and renders the result on the
  home page.
- The backend is a FastAPI application with versioned routes under
  `/api/v1`, centralized CORS configuration, centralized JSON error
  handling, and structured logging.
- The database layer establishes a SQLAlchemy engine, session lifecycle,
  and a connectivity check (`SELECT 1`) used by the health endpoint. No
  application tables exist yet.
- All three services run under Docker Compose for local development, with
  PostgreSQL data persisted in a named Docker volume.

## Explicitly not implemented yet

The following are architectural components planned for later phases and
**do not exist in this codebase**:

- NLP processing / Sentence Transformers
- Embeddings generation
- FAISS / vector search
- Academic-source integrations (arXiv, Semantic Scholar, Crossref, CORE,
  DBLP, OpenAlex)
- Hybrid / semantic search
- Recommendation engine
- Duplicate detection
- AI summaries or paper comparison
- DRIUT
- Continuous research updates / notification engine
- Citation graph
- Personalization
- Multilingual support, voice search, collaboration features
- Advanced analytics
- Production deployment configuration

## Data flow (Phase 0 only)

1. Frontend loads and immediately requests `GET /api/v1/health`.
2. Backend receives the request, checks database connectivity via
   SQLAlchemy, and returns a JSON status payload.
3. Frontend renders "Backend: Connected" / "Database: Connected" (or the
   corresponding failure state) along with the app version and
   environment.

## Configuration

All configuration is environment-variable driven (see `.env.example` at
the repository root and in `frontend/`). No credentials or secrets are
hard-coded anywhere in the codebase.
