"""
Database connection and session management.

Phase 0 scope: connection lifecycle and a health-check capability only.
No application tables are defined here (those start in Phase 1).
"""
import os
import sys
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings


def is_protected_live_database(url_str: str) -> bool:
    """Determine whether a database URL targets the persistent production-like database."""
    s = str(url_str).lower()
    return "research_papers" in s and not any(k in s for k in ["test_isolated", "disposable", "sqlite"])


def assert_safe_test_database(url_str: str) -> None:
    """Raise error if test execution attempts to target the protected live application database."""
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        if is_protected_live_database(url_str):
            raise RuntimeError(
                "FAIL-CLOSED PROTECTION: Automated test execution cannot bind to the persistent "
                "application database 'research_papers'. Tests must use an isolated test database."
            )


settings = get_settings()

# Fail-closed guard: ensure tests never bind to the protected application database
assert_safe_test_database(settings.DATABASE_URL)

connect_args = {}
pool_pre_ping = True
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    pool_pre_ping = False

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=pool_pre_ping,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context-manager version of get_db, for use outside request handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """Lightweight connectivity check used by the health endpoint."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
