"""
FastAPI application entrypoint — Phase 0.

This application intentionally implements ONLY the Phase 0 foundation:
API scaffolding, CORS, configuration, logging, error handling, and a
health endpoint backed by a real PostgreSQL connectivity check.

Do not add NLP / embeddings / FAISS / academic-source integrations /
recommendation logic here. Those belong to later phases.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger

settings = get_settings()

configure_logging()
logger = get_logger(__name__)


from app.services.driut_scheduler import driut_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting %s v%s in %s mode",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
    )
    # Startup recovery: synchronize any unindexed committed papers in PostgreSQL to FAISS
    try:
        from app.db.session import SessionLocal
        from app.services.vector_index import sync_unindexed_papers
        with SessionLocal() as db_session:
            recovered_count = sync_unindexed_papers(session=db_session)
            if recovered_count > 0:
                logger.info("Startup recovery: synchronized %d unindexed papers into FAISS index.", recovered_count)
    except Exception as rec_err:
        logger.warning("Startup FAISS unindexed paper recovery encountered an error: %s", rec_err)

    # Warm up semantic embedding model so first search request never blocks
    try:
        from app.services.embedding_service import get_embedding_model
        get_embedding_model()
    except Exception as emb_err:
        logger.warning("Startup embedding model pre-warming encountered an issue: %s", emb_err)

    if settings.ENABLE_DRIUT_SCHEDULER:
        await driut_scheduler.start()
    yield
    if settings.ENABLE_DRIUT_SCHEDULER:
        await driut_scheduler.stop()
    logger.info("Shutting down %s", settings.APP_NAME)



app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="NLP-Based Research Paper Recommendation System — Phase 0 foundation.",
    lifespan=lifespan,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Centralized error handling ---
register_exception_handlers(app)

from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from fastapi import Request
from app.core.rate_limit import limiter

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Too many requests: {exc.detail}. Please try again later."
            },
            "detail": f"Rate limit exceeded: {exc.detail}"
        }
    )

# --- API versioning ---
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
def root_health_check():
    """Simple, dependency-light endpoint for container/orchestrator health checks."""
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }

