"""Aggregates all v1 routers. New route modules are registered here."""
from fastapi import APIRouter

from app.api.v1 import health
from app.api.v1.endpoints import papers, auth, research

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(papers.router, prefix="/papers", tags=["papers"])
api_router.include_router(research.router, prefix="/research", tags=["research"])

