"""
Health-check endpoint.

Intentionally has no dependency on NLP, embeddings, FAISS, or any
academic-source integration — those belong to later phases.
"""
from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import check_database_connection
from app.schemas.health import DetailedHealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=DetailedHealthResponse)
def health_check() -> DetailedHealthResponse:
    settings = get_settings()
    db_ok = check_database_connection()

    return DetailedHealthResponse(
        status="ok" if db_ok else "degraded",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        database="connected" if db_ok else "unavailable",
    )
