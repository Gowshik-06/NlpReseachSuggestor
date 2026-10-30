"""
Application configuration.

Loads settings from environment variables (and a local .env file during
development). Nothing sensitive is hard-coded here.
"""
import json
from functools import lru_cache
from typing import Any, List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Application ---
    APP_NAME: str = "research-paper-recommender"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"

    # --- Database ---
    DATABASE_URL: str = (
        "postgresql+psycopg2://postgres:postgres@postgres:5432/research_papers"
    )

    # --- Backend server ---
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # --- Frontend / CORS ---
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    # --- Authentication & Security ---
    JWT_SECRET_KEY: str = "researchlens-secure-dev-secret-key-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # --- File Uploads ---
    MAX_UPLOAD_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB

    # --- Optional Academic API Credentials ---
    SEMANTIC_SCHOLAR_API_KEY: Optional[str] = None
    S2_API_KEY: Optional[str] = None
    CROSSREF_MAILTO: Optional[str] = None
    CORE_API_KEY: Optional[str] = None
    NCBI_API_KEY: Optional[str] = None

    # --- DRIUT Background Scheduler ---
    ENABLE_DRIUT_SCHEDULER: bool = True
    DRIUT_SCAN_INTERVAL_MINUTES: int = 60
    DRIUT_QUERY_ACADEMIC_SOURCES: bool = True
    DRIUT_ADVISORY_LOCK_KEY: int = 7376232  # Stable 64-bit PostgreSQL advisory lock key

    # --- Rate Limiting ---
    ENABLE_RATE_LIMITING: bool = True
    RATE_LIMIT_LOGIN: str = "5/minute"
    TRUSTED_PROXIES: List[str] = ["127.0.0.1", "::1", "testclient"]

    # --- AI Providers & Local-First Intelligence ---
    RESEARCHLENS_AI_ENABLED: bool = False
    RESEARCHLENS_AI_PROVIDER: str = "local_first"  # "local_first", "groq_only", "deterministic_only"
    RESEARCHLENS_AI_CLOUD_FALLBACK: bool = True
    RESEARCHLENS_OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    RESEARCHLENS_OLLAMA_MODEL: str = "qwen2.5:3b"
    GROQ_API_KEY: Optional[str] = None
    RESEARCHLENS_GROQ_MODEL: str = "llama-3.3-70b-versatile"
    RESEARCHLENS_AI_TIMEOUT_SECONDS: float = 15.0
    RESEARCHLENS_AI_MAX_OUTPUT_TOKENS: int = 1024
    RESEARCHLENS_AI_MAX_CONCURRENT_REQUESTS: int = 4
    RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT: bool = False

    @field_validator("RESEARCHLENS_AI_PROVIDER")
    @classmethod
    def validate_ai_provider(cls, v: str) -> str:
        valid_modes = {"local_first", "groq_only", "deterministic_only"}
        normalized = (v or "local_first").strip().lower()
        if normalized not in valid_modes:
            return "local_first"
        return normalized

    @model_validator(mode="after")
    def validate_jwt_secret_for_environment(self) -> "Settings":
        env = (self.ENVIRONMENT or "").strip().lower()
        secret = self.JWT_SECRET_KEY
        insecure_defaults = {
            "researchlens-secure-dev-secret-key-2026",
            "secret",
            "changeme",
            "jwt-secret",
            "default",
            "secretkey",
            "admin",
        }
        is_dev = env in ["development", "dev", "test", "testing"]
        if not is_dev:
            if not secret or secret in insecure_defaults:
                raise ValueError(
                    f"Insecure or default JWT_SECRET_KEY rejected in '{self.ENVIRONMENT}' environment. "
                    "A strong, unique signing secret (min 32 characters) must be configured."
                )
            if len(secret) < 32:
                raise ValueError(
                    f"JWT_SECRET_KEY is too short ({len(secret)} characters) for '{self.ENVIRONMENT}' environment. "
                    "Signing secret must be at least 32 characters."
                )
        return self

    # --- Firebase Authentication ---
    FIREBASE_AUTH_ENABLED: bool = False
    FIREBASE_PROJECT_ID: Optional[str] = None
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None

    @model_validator(mode="after")
    def validate_firebase_settings(self) -> "Settings":
        if self.FIREBASE_AUTH_ENABLED:
            if not self.FIREBASE_PROJECT_ID or not self.FIREBASE_PROJECT_ID.strip():
                raise ValueError(
                    "FIREBASE_PROJECT_ID must be configured and non-empty when FIREBASE_AUTH_ENABLED is True."
                )
            if self.FIREBASE_CREDENTIALS_PATH and self.FIREBASE_CREDENTIALS_PATH.strip():
                import os
                cred_path = os.path.expanduser(self.FIREBASE_CREDENTIALS_PATH.strip())
                if not os.path.exists(cred_path):
                    raise ValueError(
                        f"FIREBASE_CREDENTIALS_PATH specified but file does not exist: {cred_path}"
                    )
        return self


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()
