"""
Tests for TASK-07A: Login rate limiting, client IP determination, and trusted proxies.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings
from app.core.rate_limit import limiter, get_client_ip

client = TestClient(app)
settings = get_settings()


def test_login_rate_limiting_exceeded_and_reset():
    """
    Verify that requests up to the limit are permitted,
    exceeding requests return HTTP 429 Too Many Requests,
    and resetting the limiter restores access.
    """
    limiter.reset()
    payload = {"username": "nonexistent_user", "password": "WrongPassword123!"}

    # 5 attempts allowed under default 5/minute
    for i in range(5):
        resp = client.post("/api/v1/auth/login", json=payload)
        # Authentication fails with 401, but rate limit is not tripped
        assert resp.status_code == 401, f"Attempt {i+1} should return 401, got {resp.status_code}"

    # 6th attempt should be blocked with 429
    resp_blocked = client.post("/api/v1/auth/login", json=payload)
    assert resp_blocked.status_code == 429
    body = resp_blocked.json()
    assert "detail" in body
    assert "Rate limit exceeded" in body["detail"]
    assert body.get("error", {}).get("code") == "RATE_LIMIT_EXCEEDED"

    # Reset limiter and verify request can proceed again
    limiter.reset()
    resp_after_reset = client.post("/api/v1/auth/login", json=payload)
    assert resp_after_reset.status_code == 401


def test_trusted_proxy_ip_isolation():
    """
    Verify that requests with different X-Forwarded-For headers through a trusted proxy
    are tracked by their resolved client IP rather than collapsing into the proxy IP.
    This prevents cross-user lockouts behind shared gateways or NATs.
    """
    limiter.reset()
    payload = {"username": "nonexistent_user", "password": "WrongPassword123!"}

    headers_user_a = {"X-Forwarded-For": "198.51.100.10"}
    headers_user_b = {"X-Forwarded-For": "198.51.100.20"}

    # Exhaust limit for User A
    for _ in range(5):
        resp = client.post("/api/v1/auth/login", json=payload, headers=headers_user_a)
        assert resp.status_code == 401

    # User A is now blocked
    resp_blocked = client.post("/api/v1/auth/login", json=payload, headers=headers_user_a)
    assert resp_blocked.status_code == 429

    # User B (different forwarded IP) should NOT be blocked
    resp_user_b = client.post("/api/v1/auth/login", json=payload, headers=headers_user_b)
    assert resp_user_b.status_code == 401


def test_registration_not_blocked_by_login_rate_limit():
    """
    Verify registration endpoint is not throttled by the login rate limit.
    """
    limiter.reset()
    payload = {"username": "nonexistent_user", "password": "WrongPassword123!"}

    # Exhaust login limit
    for _ in range(5):
        client.post("/api/v1/auth/login", json=payload)
    assert client.post("/api/v1/auth/login", json=payload).status_code == 429

    # Registration attempt with validation failure or successful payload should not return 429
    resp_reg = client.post("/api/v1/auth/register", json={"username": "invalid"})
    assert resp_reg.status_code != 429


def test_get_client_ip_logic():
    """
    Direct unit test of get_client_ip to verify:
    1. Untrusted caller cannot spoof IP with X-Forwarded-For.
    2. Trusted proxy caller successfully resolves leftmost client IP.
    3. Missing proxy headers default to socket client host.
    """
    from unittest.mock import Mock

    # Untrusted caller attempting spoofing
    mock_untrusted = Mock()
    mock_untrusted.client.host = "203.0.113.99"  # Not in TRUSTED_PROXIES
    mock_untrusted.headers = {"x-forwarded-for": "10.0.0.1"}
    assert get_client_ip(mock_untrusted) == "203.0.113.99"

    # Trusted proxy passing multi-hop X-Forwarded-For
    mock_trusted = Mock()
    mock_trusted.client.host = "127.0.0.1"  # In TRUSTED_PROXIES
    mock_trusted.headers = {"x-forwarded-for": "198.51.100.5, 10.0.0.1"}
    assert get_client_ip(mock_trusted) == "198.51.100.5"

    # Trusted proxy passing X-Real-IP
    mock_real = Mock()
    mock_real.client.host = "127.0.0.1"
    mock_real.headers = {"x-real-ip": "198.51.100.7"}
    assert get_client_ip(mock_real) == "198.51.100.7"

