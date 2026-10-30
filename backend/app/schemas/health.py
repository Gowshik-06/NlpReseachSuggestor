"""Pydantic schemas for health-check responses."""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class DetailedHealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    database: str
