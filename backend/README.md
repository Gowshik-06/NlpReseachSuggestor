# Backend — Research Paper Recommendation System

FastAPI service. Phase 0 scope only: application scaffolding, configuration,
logging, error handling, API versioning, and a real health check
(application + PostgreSQL connectivity).

## Run independently (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example ../.env        # then edit DATABASE_URL etc. as needed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

A local PostgreSQL instance must be reachable at the `DATABASE_URL` you
configure (or start just the `postgres` service from the root
`docker-compose.yml`: `docker compose up postgres`).

## Endpoints

- `GET /health` — lightweight liveness check (no DB dependency), useful
  for container/orchestrator health checks.
- `GET /api/v1/health` — application + database connectivity status.
- `GET /docs` — interactive OpenAPI (Swagger) docs.
- `GET /redoc` — ReDoc API docs.

## Tests

```bash
pip install -r requirements.txt
pytest
```

## Project layout

```
app/
├── api/v1/       # versioned API routes
├── core/         # config, logging, error handling
├── db/           # SQLAlchemy engine/session, connection health check
├── models/       # SQLAlchemy models (empty in Phase 0)
├── schemas/      # Pydantic request/response models
├── services/     # business logic (empty in Phase 0)
├── repositories/ # data-access layer (empty in Phase 0)
├── utils/        # shared helpers
└── main.py       # application entrypoint
```

`models/`, `services/`, and `repositories/` are intentionally empty
placeholders in Phase 0 — no application tables or business logic exist
yet. They establish extension points for Phase 1 onward.
