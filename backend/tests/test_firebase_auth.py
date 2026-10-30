"""
Comprehensive unit and integration test suite for Stage 2B: Firebase Authentication.
Tests:
- Token signature, audience, issuer, expiration, auth_time, and UID verification
- RS256 algorithm enforcement and fail-closed behavior
- PyJWKClient key lookup errors and network failure handling
- Safe auto-provisioning with collision-safe usernames and non-admin default
- Rejecting ambiguous email collisions without explicit account linking
- Account linking flow proving local password and Firebase token
- Administrator authorization and non-escalation guarantees
- Local HS256 token rejection in Firebase mode (no silent fallback)
- Local auth backward compatibility when Firebase mode is disabled
- User-isolated library and DRIUT access controls
"""
import time
import pytest
from fastapi.testclient import TestClient
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from unittest.mock import MagicMock

from app.main import app
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.user import User
from app.models.paper import Paper, SavedPaper
from app.core.security import hash_password, create_access_token
from app.core.firebase_auth import (
    FirebaseTokenVerifier,
    FirebaseAuthError,
    verify_firebase_id_token,
    set_firebase_verifier,
)

# Test project ID
TEST_PROJECT_ID = "test-researchlens-firebase"


class MockSigningKey:
    """Mock PyJWK signing key wrapper holding an RSA public key."""
    def __init__(self, key):
        self.key = key


@pytest.fixture(scope="module")
def rsa_keypair():
    """Generate ephemeral RSA-2048 keypair for cryptographic token testing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return {"private_pem": priv_pem, "public_pem": pub_pem, "public_key": public_key}


def make_token(
    rsa_keypair,
    uid: str = "firebase_test_user_001",
    aud: str = TEST_PROJECT_ID,
    iss: str = f"https://securetoken.google.com/{TEST_PROJECT_ID}",
    exp: int = None,
    iat: int = None,
    auth_time: int = None,
    email: str = "researcher@university.edu",
    name: str = "Test Researcher",
    algorithm: str = "RS256",
    secret: bytes = None,
    extra_claims: dict = None,
    kid: str = "test-key-id-1",
) -> str:
    """Helper to generate JWT tokens with specified claims and headers."""
    now = int(time.time())
    payload = {
        "sub": uid,
        "aud": aud,
        "iss": iss,
        "iat": iat if iat is not None else now - 10,
        "exp": exp if exp is not None else now + 3600,
        "auth_time": auth_time if auth_time is not None else now - 10,
        "email": email,
        "name": name,
    }
    if extra_claims:
        payload.update(extra_claims)

    headers = {"kid": kid} if kid else {}
    sign_key = secret if secret is not None else rsa_keypair["private_pem"]
    return jwt.encode(payload, sign_key, algorithm=algorithm, headers=headers)


@pytest.fixture
def mock_verifier(rsa_keypair):
    """Provide a FirebaseTokenVerifier configured with the mock RSA key."""
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = MockSigningKey(rsa_keypair["public_pem"])
    verifier = FirebaseTokenVerifier(jwk_client=mock_client)
    set_firebase_verifier(verifier)
    yield verifier
    set_firebase_verifier(None)


def get_error_message(resp) -> str:
    """Safely extract error message from standard ResearchLens error payload."""
    try:
        data = resp.json()
        if "error" in data and isinstance(data["error"], dict):
            return str(data["error"].get("message", "")).lower()
        if "detail" in data:
            return str(data["detail"]).lower()
    except Exception:
        pass
    return resp.text.lower()


# =============================================================================
# 1. Core Token Verification Unit Tests
# =============================================================================

def test_verify_valid_firebase_token(rsa_keypair, mock_verifier):
    token = make_token(rsa_keypair, uid="usr_valid_01")
    payload = mock_verifier.verify_token(token, project_id=TEST_PROJECT_ID)
    assert payload["sub"] == "usr_valid_01"
    assert payload["aud"] == TEST_PROJECT_ID
    assert payload["iss"] == f"https://securetoken.google.com/{TEST_PROJECT_ID}"
    assert payload["email"] == "researcher@university.edu"


def test_verify_expired_token(rsa_keypair, mock_verifier):
    past = int(time.time()) - 500
    token = make_token(rsa_keypair, exp=past, iat=past - 100)
    with pytest.raises(FirebaseAuthError) as exc_info:
        mock_verifier.verify_token(token, project_id=TEST_PROJECT_ID)
    assert "expired" in str(exc_info.value).lower()


def test_verify_invalid_audience(rsa_keypair, mock_verifier):
    token = make_token(rsa_keypair, aud="wrong-audience-id")
    with pytest.raises(FirebaseAuthError) as exc_info:
        mock_verifier.verify_token(token, project_id=TEST_PROJECT_ID)
    assert "audience" in str(exc_info.value).lower()


def test_verify_invalid_issuer(rsa_keypair, mock_verifier):
    token = make_token(rsa_keypair, iss="https://evil.issuer.com/project")
    with pytest.raises(FirebaseAuthError) as exc_info:
        mock_verifier.verify_token(token, project_id=TEST_PROJECT_ID)
    assert "issuer" in str(exc_info.value).lower()


def test_verify_missing_or_empty_sub(rsa_keypair, mock_verifier):
    token = make_token(rsa_keypair, uid="")
    with pytest.raises(FirebaseAuthError) as exc_info:
        mock_verifier.verify_token(token, project_id=TEST_PROJECT_ID)
    assert "subject" in str(exc_info.value).lower() or "uid" in str(exc_info.value).lower()


def test_verify_overlong_sub(rsa_keypair, mock_verifier):
    token = make_token(rsa_keypair, uid="a" * 129)
    with pytest.raises(FirebaseAuthError) as exc_info:
        mock_verifier.verify_token(token, project_id=TEST_PROJECT_ID)
    assert "exceeds" in str(exc_info.value).lower()


def test_verify_future_auth_time(rsa_keypair, mock_verifier):
    future = int(time.time()) + 1000
    token = make_token(rsa_keypair, auth_time=future)
    with pytest.raises(FirebaseAuthError) as exc_info:
        mock_verifier.verify_token(token, project_id=TEST_PROJECT_ID)
    assert "future" in str(exc_info.value).lower()


def test_verify_rejected_hs256_algorithm(rsa_keypair, mock_verifier):
    """Ensure symmetric algorithm HS256 is strictly rejected."""
    token = make_token(rsa_keypair, algorithm="HS256", secret=b"secret-key-32-bytes-long-for-test!!")
    with pytest.raises(FirebaseAuthError) as exc_info:
        mock_verifier.verify_token(token, project_id=TEST_PROJECT_ID)
    assert "unsupported token algorithm" in str(exc_info.value).lower() or "rs256" in str(exc_info.value).lower()


def test_verify_key_retrieval_failure(rsa_keypair):
    """Network failure or unknown key in JWKS must fail closed."""
    from jwt.exceptions import PyJWKClientError
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.side_effect = PyJWKClientError("Key not found in JWKS")
    verifier = FirebaseTokenVerifier(jwk_client=mock_client)

    token = make_token(rsa_keypair)
    with pytest.raises(FirebaseAuthError) as exc_info:
        verifier.verify_token(token, project_id=TEST_PROJECT_ID)
    assert "signing keys" in str(exc_info.value).lower() or "lookup" in str(exc_info.value).lower()


def test_verify_tampered_signature(rsa_keypair, mock_verifier):
    token = make_token(rsa_keypair)
    parts = token.split(".")
    tampered_sig = parts[2][:-4] + "AAAA"
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"
    with pytest.raises(FirebaseAuthError):
        mock_verifier.verify_token(tampered_token, project_id=TEST_PROJECT_ID)


# =============================================================================
# 2. Integration Tests: Auto-Provisioning, Collisions, and Account Linking
# =============================================================================

@pytest.fixture
def enable_firebase_mode():
    """Temporarily activate Firebase Authentication mode."""
    settings = get_settings()
    orig_enabled = settings.FIREBASE_AUTH_ENABLED
    orig_proj = settings.FIREBASE_PROJECT_ID
    settings.FIREBASE_AUTH_ENABLED = True
    settings.FIREBASE_PROJECT_ID = TEST_PROJECT_ID
    yield
    settings.FIREBASE_AUTH_ENABLED = orig_enabled
    settings.FIREBASE_PROJECT_ID = orig_proj


def test_firebase_user_resolution_and_auto_provisioning(enable_firebase_mode, rsa_keypair, mock_verifier):
    """Verify new Firebase user is safely auto-provisioned with is_superuser=False and hashed_password=None."""
    client = TestClient(app)
    uid = f"fb_new_{int(time.time())}"
    token = make_token(rsa_keypair, uid=uid, email=f"{uid}@university.edu", name="Auto Provisioned User")

    # Initial request provisions user
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["firebase_uid"] == uid
    assert data["email"] == f"{uid}@university.edu"
    assert data["is_superuser"] is False
    assert data["is_active"] is True

    # Database verification
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.firebase_uid == uid).first()
        assert user is not None
        assert user.hashed_password is None
        assert user.is_superuser is False
    finally:
        db.close()

    # Subsequent request resolves the existing user
    resp2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    assert resp2.json()["id"] == data["id"]


def test_reject_ambiguous_email_collision(enable_firebase_mode, rsa_keypair, mock_verifier):
    """Never link existing local account solely because its email matches a Firebase token."""
    db = SessionLocal()
    collision_email = f"collision_{int(time.time())}@university.edu"
    try:
        local_user = User(
            username=f"local_{int(time.time())}",
            email=collision_email,
            hashed_password=hash_password("localPass123!"),
            is_active=True,
            firebase_uid=None,
        )
        db.add(local_user)
        db.commit()
    finally:
        db.close()

    client = TestClient(app)
    token = make_token(rsa_keypair, uid="unlinked_fb_uid_99", email=collision_email)

    # Presentation of token without prior linking must return 409 Conflict
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409
    err = get_error_message(resp)
    assert "already registered" in err


def test_safe_account_linking_flow(enable_firebase_mode, rsa_keypair, mock_verifier):
    """Safe linking flow requires proof of local password and Firebase token before binding UID."""
    db = SessionLocal()
    username = f"link_user_{int(time.time())}"
    email = f"{username}@university.edu"
    local_pwd = "CorrectLocalPassword123!"
    try:
        local_user = User(
            username=username,
            email=email,
            hashed_password=hash_password(local_pwd),
            is_active=True,
            firebase_uid=None,
        )
        db.add(local_user)
        db.commit()
    finally:
        db.close()

    client = TestClient(app)
    fb_uid = f"fb_linked_{int(time.time())}"
    token = make_token(rsa_keypair, uid=fb_uid, email=email)

    # 1. Attempt linking with WRONG password -> 401 Unauthorized
    bad_resp = client.post("/api/v1/auth/link-firebase", json={
        "username_or_email": username,
        "local_password": "WrongPassword!",
        "firebase_token": token,
    })
    assert bad_resp.status_code == 401

    # 2. Attempt linking with CORRECT password -> 200 OK
    good_resp = client.post("/api/v1/auth/link-firebase", json={
        "username_or_email": username,
        "local_password": local_pwd,
        "firebase_token": token,
    })
    assert good_resp.status_code == 200, good_resp.text
    assert good_resp.json()["status"] == "success"
    assert good_resp.json()["user"]["firebase_uid"] == fb_uid

    # 3. Subsequent authentication via Firebase token succeeds and resolves existing account
    auth_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert auth_resp.status_code == 200
    assert auth_resp.json()["username"] == username


def test_deactivated_account_forbidden(enable_firebase_mode, rsa_keypair, mock_verifier):
    """Deactivated accounts cannot authenticate even with valid Firebase tokens."""
    db = SessionLocal()
    uid = f"fb_deactivated_{int(time.time())}"
    try:
        user = User(
            username=f"deact_{int(time.time())}",
            email=f"{uid}@test.local",
            hashed_password=None,
            firebase_uid=uid,
            is_active=False,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    client = TestClient(app)
    token = make_token(rsa_keypair, uid=uid)
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    err = get_error_message(resp)
    assert "deactivated" in err


def test_single_role_model_and_unexposed_admin_routes(enable_firebase_mode, rsa_keypair, mock_verifier):
    """
    Verify single-role model:
    1. Provisioned Firebase users receive standard ordinary user role (is_superuser == False).
    2. Obsolete admin endpoints (/sync-index and /reindex-faiss) are unexposed (404 Not Found).
    3. Authenticated users have full access to standard protected application endpoints (/auth/me, /papers/saved).
    """
    client = TestClient(app)
    uid = f"fb_regular_{int(time.time())}"
    token = make_token(rsa_keypair, uid=uid, email=f"{uid}@test.local")

    # 1. Access protected user profile endpoint -> 200 OK
    resp_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_me.status_code == 200
    user_data = resp_me.json()
    assert user_data["firebase_uid"] == uid
    assert user_data["is_superuser"] is False  # ordinary user, not elevated

    # 2. Obsolete admin endpoints are unexposed (HTTP 404 Not Found)
    resp_sync = client.post(
        "/api/v1/papers/sync-index",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_sync.status_code == 404

    resp_reindex = client.post(
        "/api/v1/papers/reindex-faiss",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_reindex.status_code == 404

    # 3. Access user library endpoint -> 200 OK (all users share standard access)
    resp_saved = client.get(
        "/api/v1/papers/saved",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_saved.status_code == 200


def test_local_hs256_tokens_rejected_when_firebase_mode_enabled(enable_firebase_mode, mock_verifier):
    """Fails closed: local HS256 tokens are rejected when Firebase mode is enabled."""
    client = TestClient(app)
    local_token = create_access_token("some_local_user")

    # Present local token to protected endpoint in Firebase mode
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {local_token}"})
    assert resp.status_code == 401

    # Local register and login endpoints are rejected in Firebase mode
    reg_resp = client.post("/api/v1/auth/register", json={
        "username": "newdevuser",
        "email": "dev@test.local",
        "password": "Password123!",
    })
    assert reg_resp.status_code == 400
    err_reg = get_error_message(reg_resp)
    assert "disabled" in err_reg.lower()

    login_resp = client.post("/api/v1/auth/login", json={
        "username": "newdevuser",
        "password": "Password123!",
    })
    assert login_resp.status_code == 400


def test_local_auth_functional_when_firebase_disabled():
    """Verify local development authentication functions normally when FIREBASE_AUTH_ENABLED is False."""
    settings = get_settings()
    assert settings.FIREBASE_AUTH_ENABLED is False

    client = TestClient(app)
    ts = int(time.time())
    uname = f"loc_{ts}"
    pwd = "LocalSecurePassword123!"
    reg_resp = client.post("/api/v1/auth/register", json={
        "username": uname,
        "email": f"{uname}@test.local",
        "password": pwd,
    })
    assert reg_resp.status_code == 201, reg_resp.text
    token = reg_resp.json()["access_token"]

    # Verify protected endpoint accepts local token
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == uname


def test_cross_user_isolation(enable_firebase_mode, rsa_keypair, mock_verifier):
    """Verify saved papers are strictly isolated between distinct Firebase users."""
    client = TestClient(app)
    ts = int(time.time())
    uid_a = f"fb_iso_a_{ts}"
    uid_b = f"fb_iso_b_{ts}"

    token_a = make_token(rsa_keypair, uid=uid_a, email=f"{uid_a}@test.local")
    token_b = make_token(rsa_keypair, uid=uid_b, email=f"{uid_b}@test.local")

    # 1. Provision users via /me
    resp_a = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    resp_b = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    username_a = resp_a.json()["username"]
    username_b = resp_b.json()["username"]

    # 2. Seed a test paper in DB with authors as JSON list
    db = SessionLocal()
    try:
        paper = Paper(
            paper_id=f"iso_test_paper_{ts}",
            title="Isolation Test Paper",
            authors=["Test Author A", "Test Author B"],
            year=2024,
            abstract="Isolation testing abstract",
            source="local",
        )
        db.add(paper)
        db.commit()
        db.refresh(paper)
        paper_db_id = paper.id

        # User A saves the paper
        save_resp = client.post(
            "/api/v1/papers/save",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"paper_id": paper_db_id, "notes": "Private note A"}
        )
        assert save_resp.status_code == 200, save_resp.text
        saved_id = save_resp.json()["id"]

        # User A sees paper in saved library
        list_a = client.get("/api/v1/papers/saved", headers={"Authorization": f"Bearer {token_a}"})
        assert list_a.status_code == 200
        saved_ids_a = [p["id"] for p in list_a.json()]
        assert saved_id in saved_ids_a

        # User B cannot see User A's saved paper
        list_b = client.get("/api/v1/papers/saved", headers={"Authorization": f"Bearer {token_b}"})
        assert list_b.status_code == 200
        saved_ids_b = [p["id"] for p in list_b.json()]
        assert saved_id not in saved_ids_b

        # User B cannot delete User A's saved paper
        del_resp = client.delete(
            f"/api/v1/papers/saved/{saved_id}",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert del_resp.status_code in (403, 404)

        # Cleanup
        db.query(SavedPaper).filter(SavedPaper.id == saved_id).delete()
        db.query(Paper).filter(Paper.id == paper_db_id).delete()
        db.commit()
    finally:
        db.close()


# =============================================================================
# 4. Concurrency & Provisioning Race Condition Regression Tests
# =============================================================================

def test_provisioning_race_condition_recovery_uid_match(enable_firebase_mode, rsa_keypair, mock_verifier):
    """
    Test recovery when simultaneous requests attempt to provision the same Firebase UID.
    When a concurrent request commits first, the second request experiences UniqueViolation,
    rolls back, and cleanly resolves the concurrently created user without throwing HTTP 500.
    """
    from app.api.deps import _provision_firebase_user
    uid = f"fb_race_{int(time.time())}"
    clean_email = f"{uid}@test.local"
    name = "Race Condition User"

    db1 = SessionLocal()
    db2 = SessionLocal()
    try:
        # Pre-commit user in db1 simulating a concurrent request completing first
        user1 = _provision_firebase_user(db1, uid=uid, clean_email=clean_email, name=name)
        assert user1.firebase_uid == uid
        user1_id = user1.id

        # Now db2 attempts to provision with the exact same UID & email.
        # It must recover from the duplicate UID/username, roll back, and return the existing user.
        user2 = _provision_firebase_user(db2, uid=uid, clean_email=clean_email, name=name)
        assert user2 is not None
        assert user2.id == user1_id
        assert user2.firebase_uid == uid
        assert user2.is_superuser is False
    finally:
        db1.close()
        db2.close()
        # Cleanup
        clean_db = SessionLocal()
        clean_db.query(User).filter(User.firebase_uid == uid).delete()
        clean_db.commit()
        clean_db.close()


def test_provisioning_username_collision_recovery(enable_firebase_mode):
    """
    Test recovery when safe_username collides with an existing username with a different UID.
    _provision_firebase_user must safely retry with a collision-resistant username.
    """
    from app.api.deps import _provision_firebase_user
    ts = int(time.time())
    uid_existing = f"fb_uid_exist_{ts}"
    uid_new = f"fb_uid_new_{ts}"

    db = SessionLocal()
    try:
        # Create an existing user with username collision target
        existing = User(
            username=f"collisionuser_{ts}_{uid_new[:8]}"[:50],
            email=f"prior_{ts}@university.edu",
            hashed_password=None,
            firebase_uid=uid_existing,
            is_active=True,
            is_superuser=False,
        )
        db.add(existing)
        db.commit()

        # Provision new user with colliding name base
        new_user = _provision_firebase_user(
            db,
            uid=uid_new,
            clean_email=f"fresh_{ts}@university.edu",
            name=f"CollisionUser {ts}",
        )
        assert new_user is not None
        assert new_user.firebase_uid == uid_new
        assert new_user.username != existing.username
        assert new_user.is_superuser is False
    finally:
        db.query(User).filter(User.firebase_uid.in_([uid_existing, uid_new])).delete()
        db.commit()
        db.close()


def test_provisioning_concurrent_email_conflict_rejection(enable_firebase_mode):
    """
    If a local user was registered with the same email concurrently, reject automatic linking
    and raise HTTP 409 Conflict.
    """
    from app.api.deps import _provision_firebase_user
    from fastapi import HTTPException
    ts = int(time.time())
    conflict_email = f"conflict_{ts}@domain.org"
    uid_firebase = f"fb_email_conflict_{ts}"

    db = SessionLocal()
    try:
        # Existing user with matching email but no Firebase UID
        local_user = User(
            username=f"local_{ts}",
            email=conflict_email,
            hashed_password=hash_password("LocalPass123"),
            firebase_uid=None,
            is_active=True,
            is_superuser=False,
        )
        db.add(local_user)
        db.commit()

        # Attempting to provision Firebase user with same email must fail with 409
        with pytest.raises(HTTPException) as exc_info:
            _provision_firebase_user(
                db,
                uid=uid_firebase,
                clean_email=conflict_email,
                name="Conflict User"
            )
        assert exc_info.value.status_code == 409
        assert "link your existing account" in exc_info.value.detail.lower()
    finally:
        db.query(User).filter(User.email == conflict_email).delete()
        db.commit()
        db.close()


def test_provisioning_race_condition_deactivated_user(enable_firebase_mode):
    """
    If the concurrently created account is deactivated, it must reject with HTTP 403 Forbidden.
    """
    from app.api.deps import _provision_firebase_user
    from fastapi import HTTPException
    ts = int(time.time())
    deactivated_uid = f"fb_deact_{ts}"

    db = SessionLocal()
    try:
        deact_user = User(
            username=f"deact_{ts}",
            email=f"{deactivated_uid}@domain.org",
            hashed_password=None,
            firebase_uid=deactivated_uid,
            is_active=False,
            is_superuser=False,
        )
        db.add(deact_user)
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            _provision_firebase_user(
                db,
                uid=deactivated_uid,
                clean_email=f"{deactivated_uid}@domain.org",
                name="Deactivated User"
            )
        assert exc_info.value.status_code == 403
        assert "deactivated" in exc_info.value.detail.lower()
    finally:
        db.query(User).filter(User.firebase_uid == deactivated_uid).delete()
        db.commit()
        db.close()


def test_simultaneous_firebase_login_and_me_endpoints(enable_firebase_mode, rsa_keypair, mock_verifier):
    """
    Simulate simultaneous calls to POST /api/v1/auth/firebase-login and GET /api/v1/auth/me
    with the same Firebase ID token. Both must return the identical user profile without 500 error.
    """
    client = TestClient(app)
    uid = f"fb_simul_{int(time.time())}"
    token = make_token(rsa_keypair, uid=uid, email=f"{uid}@university.edu", name="Simultaneous User")

    # 1. Call POST /api/v1/auth/firebase-login
    login_resp = client.post("/api/v1/auth/firebase-login", json={"id_token": token})
    assert login_resp.status_code == 200, login_resp.text
    login_user = login_resp.json()["user"]
    assert login_user["firebase_uid"] == uid

    # 2. Call GET /api/v1/auth/me immediately
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200, me_resp.text
    me_user = me_resp.json()
    assert me_user["id"] == login_user["id"]
    assert me_user["username"] == login_user["username"]
    assert me_user["firebase_uid"] == uid

    # 3. Repeat POST /api/v1/auth/firebase-login to ensure idempotency
    repeat_login_resp = client.post("/api/v1/auth/firebase-login", json={"id_token": token})
    assert repeat_login_resp.status_code == 200
    assert repeat_login_resp.json()["user"]["id"] == login_user["id"]

    # Cleanup
    db = SessionLocal()
    try:
        db.query(User).filter(User.firebase_uid == uid).delete()
        db.commit()
    finally:
        db.close()

