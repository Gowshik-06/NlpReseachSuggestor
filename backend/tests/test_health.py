"""
Phase 0 test suite.

Covers only what Phase 0 promises:
1. the app starts and is importable
2. GET /health returns 200
3. GET /api/v1/health returns 200 and the expected shape
4. an invalid endpoint returns a well-formed error
5. configuration loads correctly
"""
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_app_starts():
    assert app is not None


def test_root_health_check_returns_200():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "service" in body
    assert "version" in body


def test_api_v1_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert body["service"]
    assert body["version"]
    assert "database" in body


def test_invalid_endpoint_returns_structured_error():
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["error"]["code"]
    assert body["error"]["message"]


def test_configuration_loads_correctly():
    settings = get_settings()
    assert settings.APP_NAME
    assert settings.APP_VERSION
    assert settings.DATABASE_URL
