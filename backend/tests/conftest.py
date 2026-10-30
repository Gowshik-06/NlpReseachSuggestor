"""
Pytest configuration and shared fixtures for ResearchLens.
Enforces zero-pollution test isolation:
- Redirects all test database operations to an isolated temporary SQLite database by default.
- Redirects all test FAISS operations to an isolated temporary directory.
- Fails closed immediately if tests attempt to bind to the persistent live database.
- Guarantees clean rate-limiter and application state across tests.
"""
import os
import sys
import shutil
import pytest

# Default paths for isolated test resources
_DEFAULT_TEST_DB = "/tmp/researchlens_test_isolated.db"
_DEFAULT_FAISS_DIR = "/tmp/researchlens_test_faiss"

# 1. Enforce isolated test environment variables BEFORE application modules are imported
os.environ["ENVIRONMENT"] = "test"

if not os.environ.get("DATABASE_URL") or "research_papers" in os.environ.get("DATABASE_URL", "").lower():
    os.environ["DATABASE_URL"] = f"sqlite:///{_DEFAULT_TEST_DB}"

if not os.environ.get("FAISS_INDEX_DIR"):
    os.environ["FAISS_INDEX_DIR"] = _DEFAULT_FAISS_DIR
    os.environ["FAISS_INDEX_PATH"] = os.path.join(_DEFAULT_FAISS_DIR, "test_index.faiss")
    os.environ["FAISS_METADATA_PATH"] = os.path.join(_DEFAULT_FAISS_DIR, "test_meta.json")

# 2. Clear settings cache so application settings read the test environment variables
from app.core.config import get_settings
get_settings.cache_clear()

from app.db.session import engine, SessionLocal, Base, get_db, assert_safe_test_database
from app.services.vector_index import reset_faiss_index_instance
from app.core.rate_limit import limiter
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_isolated_test_suite():
    """
    Session-level fixture that initializes isolated SQLite database tables and FAISS directory.
    Guarantees that tests never touch the live PostgreSQL database or production FAISS index files.
    """
    # 1. Fail-closed safety verification
    assert_safe_test_database(engine.url)

    # 2. Prepare isolated SQLite tables
    Base.metadata.create_all(bind=engine)

    # 3. Prepare isolated FAISS test directory
    faiss_dir = os.environ.get("FAISS_INDEX_DIR", _DEFAULT_FAISS_DIR)
    os.makedirs(faiss_dir, exist_ok=True)
    reset_faiss_index_instance()

    yield

    # Teardown: purge temporary test files
    reset_faiss_index_instance()
    if os.path.exists(_DEFAULT_TEST_DB):
        try:
            os.remove(_DEFAULT_TEST_DB)
        except OSError:
            pass
    if os.path.exists(_DEFAULT_FAISS_DIR):
        try:
            shutil.rmtree(_DEFAULT_FAISS_DIR, ignore_errors=True)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def reset_limiter_state():
    """
    Ensure each test starts with an isolated, clean rate-limiter state
    so tests remain deterministic and do not interfere with one another.
    """
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def verify_live_database_shield():
    """
    Autouse safety assertion executing before every test:
    Guarantees the active database target is NEVER the protected live database.
    """
    url_str = str(engine.url).lower()
    assert "sqlite" in url_str or "test" in url_str, (
        f"CRITICAL: Unsafe test database target detected: {url_str}"
    )
    assert not ("research_papers" in url_str and "sqlite" not in url_str), (
        f"CRITICAL: Test attempted to bind to persistent database 'research_papers': {url_str}"
    )


@pytest.fixture(autouse=True)
def override_app_db_dependency():
    """
    Ensure FastAPI TestClient automatically uses the isolated test database session.
    """
    def _test_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _test_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def db_session():
    """Provide an isolated database session for a test function."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
