"""
Automated verification tests for CORS Configuration Alignment (TASK 3).
Proves:
1. An OPTIONS preflight from http://localhost:3000 receives expected CORS headers.
2. An OPTIONS preflight from http://127.0.0.1:3000 receives expected CORS headers.
3. An unapproved origin is rejected / not granted access.
4. Simple requests from approved origins receive appropriate access-control headers while unapproved origins do not.
5. Existing authentication and authorization behavior remains unchanged.
6. The health endpoint responds successfully.
7. CORS_ORIGINS settings parsing handles JSON strings, CSV strings, and lists.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import Settings, get_settings


@pytest.fixture
def client():
    return TestClient(app)


def test_cors_preflight_localhost_3000(client):
    """
    1. An OPTIONS preflight from http://localhost:3000 receives the expected CORS headers.
    """
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "GET" in response.headers.get("access-control-allow-methods", "")


def test_cors_preflight_127_0_0_1_3000(client):
    """
    2. An OPTIONS preflight from http://127.0.0.1:3000 receives the expected CORS headers.
    """
    headers = {
        "Origin": "http://127.0.0.1:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "POST" in response.headers.get("access-control-allow-methods", "")


def test_cors_preflight_unapproved_origins_rejected(client):
    """
    3. An unapproved origin is not granted CORS access (preflight fails or lacks allow-origin).
    """
    unapproved = [
        "http://evil.com",
        "http://attacker.org:3000",
        "http://localhost:8080",
        "https://random-site.net",
    ]
    for origin in unapproved:
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        }
        response = client.options("/api/v1/health", headers=headers)
        # CORSMiddleware responds with 400 Bad Request for disallowed origins on preflight
        assert response.status_code == 400 or "access-control-allow-origin" not in response.headers
        assert response.headers.get("access-control-allow-origin") != origin


def test_cors_simple_requests_header_behavior(client):
    """
    4. Simple GET requests from approved origins receive access-control-allow-origin;
       unapproved origins receive no access-control-allow-origin header.
    """
    # Approved origins
    for approved in ["http://localhost:3000", "http://127.0.0.1:3000"]:
        resp = client.get("/api/v1/health", headers={"Origin": approved})
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == approved

    # Unapproved origin
    resp_evil = client.get("/api/v1/health", headers={"Origin": "http://evil.com"})
    assert resp_evil.status_code == 200
    assert "access-control-allow-origin" not in resp_evil.headers


def test_auth_and_authorization_behavior_unchanged(client):
    """
    5. Existing authentication and authorization behavior remains unchanged.
    """
    # Protected endpoint without auth header returns 401 Unauthorized
    resp_unauth = client.get("/api/v1/papers/saved")
    assert resp_unauth.status_code == 401
    assert "error" in resp_unauth.json() or "detail" in resp_unauth.json()

    # Login with non-existent / invalid credentials returns 401 Unauthorized
    resp_bad_login = client.post("/api/v1/auth/login", json={
        "username": "non_existent_cors_test_user",
        "password": "WrongPassword123!"
    })
    assert resp_bad_login.status_code == 401
    assert "error" in resp_bad_login.json() or "detail" in resp_bad_login.json()


def test_health_endpoint_responds_successfully(client):
    """
    6. Health endpoint responds successfully with intact schema and connectivity.
    """
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert data.get("service") == "research-paper-recommender"
    assert data.get("database") == "connected"


def test_cors_settings_parsing_formats():
    """
    7. CORS_ORIGINS parsing supports default list, JSON arrays, and comma-separated strings.
    """
    # Default
    s_default = Settings(CORS_ORIGINS=["http://localhost:3000", "http://127.0.0.1:3000"])
    assert "http://localhost:3000" in s_default.CORS_ORIGINS
    assert "http://127.0.0.1:3000" in s_default.CORS_ORIGINS

    # JSON String
    s_json = Settings(CORS_ORIGINS='["http://localhost:3000", "http://127.0.0.1:3000"]')
    assert s_json.CORS_ORIGINS == ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Comma-separated string
    s_csv = Settings(CORS_ORIGINS="http://localhost:3000, http://127.0.0.1:3000")
    assert s_csv.CORS_ORIGINS == ["http://localhost:3000", "http://127.0.0.1:3000"]
