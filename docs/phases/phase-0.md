# Phase 0 — Project Foundation

## Objective

Establish a clean, stable, extensible development foundation for the
NLP-Based Research Paper Recommendation System: backend foundation,
frontend foundation, PostgreSQL, Docker development environment,
configuration, logging, API structure, frontend↔backend communication,
basic health monitoring, testing foundation, documentation foundation, and
a Git-ready project structure. No NLP/embeddings/FAISS/academic-source
integrations/recommendation logic are implemented.

## Implemented

- FastAPI backend with versioned API (`/api/v1`), CORS, centralized JSON
  error handling, structured logging, and environment-based configuration.
- `GET /health` (lightweight, no DB dependency) and `GET /api/v1/health`
  (application + real PostgreSQL connectivity check).
- SQLAlchemy engine/session lifecycle and a connection health-check
  function. No application tables created (correctly deferred to Phase 1).
- React + TypeScript frontend (Vite) with a routing foundation, a
  centralized API service layer (no scattered `fetch()` calls), a loading
  state, an error state, and a home page showing backend/database/version
  status.
- Docker Compose environment: `postgres` (with a named volume for
  persistence), `backend`, `frontend`.
- Backend test suite (pytest) and frontend test suite (Vitest + React
  Testing Library).
- `docs/architecture.md`, this phase-tracking document, and READMEs for
  the root, backend, and frontend.

## Files created

```
.env.example
.gitignore
LICENSE
README.md
docker-compose.yml
docs/architecture.md
docs/phases/phase-0.md
data/raw/.gitkeep
data/processed/.gitkeep
data/local/.gitkeep
docker/.gitkeep
scripts/.gitkeep
tests/.gitkeep

backend/Dockerfile
backend/README.md
backend/requirements.txt
backend/pytest.ini
backend/app/main.py
backend/app/core/config.py
backend/app/core/logging.py
backend/app/core/errors.py
backend/app/db/session.py
backend/app/schemas/health.py
backend/app/api/v1/health.py
backend/app/api/v1/api.py
backend/app/{__init__.py and package __init__.py files under api/, api/v1/, core/, db/, models/, schemas/, services/, repositories/, utils/}
backend/app/models/.gitkeep
backend/app/services/.gitkeep
backend/app/repositories/.gitkeep
backend/app/utils/.gitkeep
backend/tests/__init__.py
backend/tests/test_health.py

frontend/Dockerfile
frontend/README.md
frontend/package.json
frontend/tsconfig.json
frontend/vite.config.ts
frontend/index.html
frontend/.env.example
frontend/public/.gitkeep
frontend/src/vite-env.d.ts
frontend/src/index.css
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/App.test.tsx
frontend/src/setupTests.ts
frontend/src/layouts/MainLayout.tsx
frontend/src/components/StatusRow.tsx
frontend/src/pages/HomePage.tsx
frontend/src/hooks/useHealthStatus.ts
frontend/src/services/api.ts
frontend/src/types/health.ts
frontend/src/utils/.gitkeep
```

## Files modified

None — this phase was built from an empty repository (no pre-existing
frontend, backend, configuration, database setup, documentation, tests, or
HTML prototype were found during inspection).

## Tests

**Backend (pytest, run in the development sandbox without a live
Postgres):**

```
5 passed
- test_app_starts
- test_root_health_check_returns_200
- test_api_v1_health_check
- test_invalid_endpoint_returns_structured_error
- test_configuration_loads_correctly
```

**Frontend (Vitest):**

```
1 test file passed, 2 tests passed
- App > renders the application shell
- App > shows a loading state before the health check resolves
```

TypeScript compiles cleanly (`tsc -b`, zero errors).

The backend was also started directly (`uvicorn`) and manually verified:
`GET /health` → 200, `GET /api/v1/health` → 200 with
`"database": "unavailable"` (correctly degrades rather than crashing,
since no Postgres was running in the sandbox), `GET /docs` → 200,
`GET /openapi.json` → 200, and an invalid route returned the structured
`{"error": {...}}` shape.

## Known issues

- The end-to-end `docker compose up --build` workflow (all three
  containers together, with the frontend calling the backend calling a
  live containerized Postgres) has **not** been executed in this sandbox
  — this environment has no Docker daemon and no long-lived Postgres
  server available. Each piece was verified independently instead:
  backend against a real (if unreachable-in-sandbox) `DATABASE_URL`
  config, and frontend against a mocked backend. Run
  `docker compose up --build` in a Docker-capable environment to complete
  the full end-to-end acceptance check.
- No pre-existing project or HTML prototype was found to inspect or
  preserve; this phase was built from scratch.

## Acceptance criteria

| Criterion | Status |
|---|---|
| Project structure created | ✓ |
| Backend starts, exposes versioned API, CORS, logging, error handling | ✓ (verified directly) |
| `GET /health` returns 200 | ✓ (verified directly) |
| `GET /api/v1/health` confirms app + DB status | ✓ (verified directly) |
| PostgreSQL configured with persistent volume | ✓ (configuration in place; not run live in this sandbox) |
| Docker Compose file for backend + frontend + postgres | ✓ (not executed live in this sandbox — no Docker daemon here) |
| Frontend renders home/status page via centralized API client | ✓ (verified directly, backend mocked) |
| Backend tests pass | ✓ (5/5) |
| Frontend tests pass | ✓ (2/2) |
| `/docs` and `/redoc` accessible | ✓ (`/docs` verified directly; `/redoc` ships automatically from the same FastAPI app) |
| README, architecture doc, phase-0 doc present | ✓ |
| Git-ready structure (`.gitignore`, no secrets committed) | ✓ |

## Next phase

**Phase 1 — Database + Research Repository**
