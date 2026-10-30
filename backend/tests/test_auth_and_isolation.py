"""
Security and User Data Isolation Test Suite for TASK-04.
Verifies:
1. Authentication: registration, login, token validation, expiration, and password hashing security.
2. User isolation: User A vs User B boundaries across saved papers, notes, tags, and DRIUT alerts.
3. Defense against parameter tampering and identifier enumeration.
4. Public endpoints remain operational without credentials.
"""
from datetime import timedelta
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal, Base, engine
from app.models.user import User
from app.models.paper import Paper, SavedPaper
from app.models.driut import DRIUTAlert
from app.core.security import create_access_token, verify_password

client = TestClient(app)


def get_error_message(res) -> str:
    """Helper to extract error message from standard API error payload or detail."""
    data = res.json()
    if isinstance(data, dict):
        if "error" in data and isinstance(data["error"], dict) and "message" in data["error"]:
            return data["error"]["message"]
        if "detail" in data:
            return str(data["detail"])
    return str(data)


@pytest.fixture(scope="module")
def setup_security_suite():
    """Setup clean test users and fixture papers, ensuring isolated cleanup on exit."""
    from app.services.vector_index import INDEX_PATH, METADATA_PATH
    import os

    orig_idx_bytes = None
    orig_meta_bytes = None
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "rb") as f:
            orig_idx_bytes = f.read()
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, "rb") as f:
            orig_meta_bytes = f.read()

    db = SessionLocal()

    # Clean existing test users if leftover
    test_usernames = ["user_alpha", "user_beta", "temp_user"]
    db.query(DRIUTAlert).filter(DRIUTAlert.user_id.in_(test_usernames)).delete()
    db.query(SavedPaper).filter(SavedPaper.user_id.in_(test_usernames)).delete()
    db.query(User).filter(User.username.in_(test_usernames)).delete()
    db.commit()

    # Ensure reference test papers exist
    p1 = db.query(Paper).filter(Paper.paper_id == "arxiv:test.sec.01").first()
    if not p1:
        p1 = Paper(
            paper_id="arxiv:test.sec.01",
            title="Secure Foundations in Deep Representation Learning",
            abstract="A study on user data isolation and neural embeddings.",
            authors=["Security Researcher", "Alice"],
            year=2025,
            source="local"
        )
        db.add(p1)
        db.commit()
        db.refresh(p1)

    p2 = db.query(Paper).filter(Paper.paper_id == "arxiv:test.sec.02").first()
    if not p2:
        p2 = Paper(
            paper_id="arxiv:test.sec.02",
            title="Advances in Deep Representation Learning",
            abstract="Extending user data isolation techniques.",
            authors=["Security Researcher", "Bob"],
            year=2026,
            source="local"
        )
        db.add(p2)
        db.commit()
        db.refresh(p2)

    p1_id = p1.id
    p2_id = p2.id
    db.close()

    yield {
        "paper1_id": p1_id,
        "paper2_id": p2_id,
        "paper1_paper_id": "arxiv:test.sec.01",
        "paper2_paper_id": "arxiv:test.sec.02"
    }

    # Teardown
    db = SessionLocal()
    db.query(DRIUTAlert).filter(DRIUTAlert.user_id.in_(test_usernames)).delete()
    db.query(SavedPaper).filter(SavedPaper.user_id.in_(test_usernames)).delete()
    db.query(User).filter(User.username.in_(test_usernames)).delete()
    db.query(Paper).filter(Paper.paper_id.in_(["arxiv:test.sec.01", "arxiv:test.sec.02"])).delete()
    db.commit()
    db.close()

    # Restore FAISS to original baseline bytes
    if orig_idx_bytes is not None and os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "wb") as f:
            f.write(orig_idx_bytes)
    if orig_meta_bytes is not None and os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, "wb") as f:
            f.write(orig_meta_bytes)
    try:
        from app.services.vector_index import get_faiss_index
        idx = get_faiss_index()
        idx._load_or_initialize()
    except Exception:
        pass


def test_unauthenticated_access_rejected(setup_security_suite):
    """Protected saved-paper and DRIUT endpoints must reject unauthenticated requests with 401."""
    p_id = setup_security_suite["paper1_id"]

    # GET /saved
    res = client.get("/api/v1/papers/saved")
    assert res.status_code == 401
    assert "WWW-Authenticate" in res.headers

    # POST /save
    res = client.post("/api/v1/papers/save", json={"paper_id": p_id, "notes": "Secret notes"})
    assert res.status_code == 401

    # DELETE /saved/{id}
    res = client.delete("/api/v1/papers/saved/99999")
    assert res.status_code == 401

    # GET /driut/alerts
    res = client.get("/api/v1/papers/driut/alerts")
    assert res.status_code == 401

    # POST /driut/scan
    res = client.post("/api/v1/papers/driut/scan")
    assert res.status_code == 401

    # PATCH /driut/alerts/{id}/read
    res = client.patch("/api/v1/papers/driut/alerts/99999/read")
    assert res.status_code == 401

    # GET /auth/me
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_user_registration_and_validation(setup_security_suite):
    """Test user registration, duplicate prevention, and input validation."""
    # 1. Successful registration of User Alpha
    res = client.post(
        "/api/v1/auth/register",
        json={
            "username": "user_alpha",
            "email": "alpha@research.test",
            "password": "PasswordAlpha2026!",
            "full_name": "Alice Alpha"
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "user_alpha"
    assert data["user"]["email"] == "alpha@research.test"

    # 2. Duplicate username rejected
    res_dup_user = client.post(
        "/api/v1/auth/register",
        json={
            "username": "user_alpha",
            "email": "different_email@research.test",
            "password": "PasswordAlpha2026!"
        }
    )
    assert res_dup_user.status_code == 400
    assert "Username is already taken" in get_error_message(res_dup_user)

    # 3. Duplicate email rejected
    res_dup_email = client.post(
        "/api/v1/auth/register",
        json={
            "username": "another_user",
            "email": "alpha@research.test",
            "password": "PasswordAlpha2026!"
        }
    )
    assert res_dup_email.status_code == 400
    assert "Email address is already registered" in get_error_message(res_dup_email)

    # 4. Short password rejected
    res_short_pwd = client.post(
        "/api/v1/auth/register",
        json={
            "username": "short_pwd_user",
            "email": "short@research.test",
            "password": "123"
        }
    )
    assert res_short_pwd.status_code == 422

    # 5. Invalid email format rejected
    res_bad_email = client.post(
        "/api/v1/auth/register",
        json={
            "username": "bad_email_user",
            "email": "not-an-email",
            "password": "ValidPassword2026!"
        }
    )
    assert res_bad_email.status_code == 422


def test_user_login_and_token_verification(setup_security_suite):
    """Test login with valid/invalid credentials and token verification."""
    # 1. Valid login
    res = client.post(
        "/api/v1/auth/login",
        json={"username": "user_alpha", "password": "PasswordAlpha2026!"}
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    assert len(token) > 20

    # 2. Login with email
    res_email = client.post(
        "/api/v1/auth/login",
        json={"username": "alpha@research.test", "password": "PasswordAlpha2026!"}
    )
    assert res_email.status_code == 200

    # 3. Invalid password
    res_wrong_pw = client.post(
        "/api/v1/auth/login",
        json={"username": "user_alpha", "password": "WrongPassword123!"}
    )
    assert res_wrong_pw.status_code == 401
    assert "Invalid username or password" in get_error_message(res_wrong_pw)

    # 4. Non-existent username
    res_no_user = client.post(
        "/api/v1/auth/login",
        json={"username": "ghost_researcher", "password": "PasswordAlpha2026!"}
    )
    assert res_no_user.status_code == 401

    # 5. Access /me with valid token
    res_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["username"] == "user_alpha"

    # 6. Invalid token string rejected
    res_bad_tok = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.payload"})
    assert res_bad_tok.status_code == 401

    # 7. Expired token rejected
    expired_token = create_access_token("user_alpha", expires_delta=timedelta(seconds=-10))
    res_exp_tok = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res_exp_tok.status_code == 401


def test_passwords_never_stored_in_plaintext(setup_security_suite):
    """Verify in database that passwords are securely hashed using bcrypt."""
    db = SessionLocal()
    user = db.query(User).filter(User.username == "user_alpha").first()
    assert user is not None
    assert user.hashed_password != "PasswordAlpha2026!"
    assert user.hashed_password.startswith("$2b$")  # Bcrypt signature
    assert verify_password("PasswordAlpha2026!", user.hashed_password) is True
    assert verify_password("WrongPassword!", user.hashed_password) is False
    db.close()


def test_user_data_isolation_between_two_users(setup_security_suite):
    """
    Two-user isolation test:
    User A (Alice) and User B (Bob) operate simultaneously.
    Assert User B cannot view, modify, or delete User A's library, notes, or DRIUT alerts.
    """
    # 1. Register User B
    res_reg_b = client.post(
        "/api/v1/auth/register",
        json={
            "username": "user_beta",
            "email": "beta@research.test",
            "password": "PasswordBeta2026!",
            "full_name": "Bob Beta"
        }
    )
    assert res_reg_b.status_code == 201

    # Login both users to acquire valid tokens
    tok_a = client.post("/api/v1/auth/login", json={"username": "user_alpha", "password": "PasswordAlpha2026!"}).json()["access_token"]
    tok_b = client.post("/api/v1/auth/login", json={"username": "user_beta", "password": "PasswordBeta2026!"}).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {tok_a}"}
    headers_b = {"Authorization": f"Bearer {tok_b}"}

    paper1_id = setup_security_suite["paper1_id"]

    # Step A1: User A saves Paper 1 with private notes
    save_a = client.post(
        "/api/v1/papers/save",
        json={"paper_id": paper1_id, "notes": "Alice Confidential Notes: breakthrough idea", "tags": ["alice_tag"]},
        headers=headers_a
    )
    assert save_a.status_code == 200
    saved_paper_a_id = save_a.json()["id"]

    # Step A2: User A lists library -> sees Paper 1
    list_a = client.get("/api/v1/papers/saved", headers=headers_a)
    assert list_a.status_code == 200
    papers_a = list_a.json()
    assert len(papers_a) == 1
    assert papers_a[0]["id"] == saved_paper_a_id
    assert papers_a[0]["notes"] == "Alice Confidential Notes: breakthrough idea"

    # Step B1: User B lists library -> MUST BE EMPTY (cannot see User A's saved paper)
    list_b = client.get("/api/v1/papers/saved", headers=headers_b)
    assert list_b.status_code == 200
    papers_b = list_b.json()
    assert len(papers_b) == 0

    # Step B2: User B tries to delete User A's saved paper ID -> MUST RECEIVE 404
    del_b_try = client.delete(f"/api/v1/papers/saved/{saved_paper_a_id}", headers=headers_b)
    assert del_b_try.status_code == 404
    assert "Saved paper entry not found" in get_error_message(del_b_try)

    # Verify User A's saved paper was NOT deleted
    list_a_after = client.get("/api/v1/papers/saved", headers=headers_a)
    assert len(list_a_after.json()) == 1

    # Step B3: User B saves the SAME paper with their own distinct notes
    save_b = client.post(
        "/api/v1/papers/save",
        json={"paper_id": paper1_id, "notes": "Bob Public Notes: reviewing for seminar", "tags": ["bob_tag"]},
        headers=headers_b
    )
    assert save_b.status_code == 200
    saved_paper_b_id = save_b.json()["id"]
    assert saved_paper_b_id != saved_paper_a_id  # Independent rows in database

    # Step B4: Verify notes and tags are completely isolated
    list_a_check = client.get("/api/v1/papers/saved", headers=headers_a).json()
    list_b_check = client.get("/api/v1/papers/saved", headers=headers_b).json()

    assert list_a_check[0]["notes"] == "Alice Confidential Notes: breakthrough idea"
    assert list_a_check[0]["tags"] == ["alice_tag"]
    assert list_b_check[0]["notes"] == "Bob Public Notes: reviewing for seminar"
    assert list_b_check[0]["tags"] == ["bob_tag"]

    # Step B5: User B deletes their own saved paper -> succeeds
    del_b = client.delete(f"/api/v1/papers/saved/{saved_paper_b_id}", headers=headers_b)
    assert del_b.status_code == 200

    # User A's paper is STILL there!
    list_a_final = client.get("/api/v1/papers/saved", headers=headers_a).json()
    assert len(list_a_final) == 1
    assert list_a_final[0]["id"] == saved_paper_a_id


def test_parameter_tampering_ignored(setup_security_suite):
    """
    Verifies that client-supplied user_id query parameters or body attributes
    are ignored in favor of the authenticated JWT identity.
    """
    tok_b = client.post("/api/v1/auth/login", json={"username": "user_beta", "password": "PasswordBeta2026!"}).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {tok_b}"}

    # User B queries saved papers but attempts to inject user_id=user_alpha in query string
    res = client.get("/api/v1/papers/saved?user_id=user_alpha", headers=headers_b)
    assert res.status_code == 200
    # Must return User B's papers (0), NOT User A's papers
    assert len(res.json()) == 0

    # User B queries DRIUT alerts injecting user_id=user_alpha
    res_alerts = client.get("/api/v1/papers/driut/alerts?user_id=user_alpha", headers=headers_b)
    assert res_alerts.status_code == 200
    assert len(res_alerts.json()) == 0


def test_driut_alert_ownership_isolation(setup_security_suite):
    """
    Verify DRIUT alerts cannot be read or marked read across user boundaries.
    """
    tok_a = client.post("/api/v1/auth/login", json={"username": "user_alpha", "password": "PasswordAlpha2026!"}).json()["access_token"]
    tok_b = client.post("/api/v1/auth/login", json={"username": "user_beta", "password": "PasswordBeta2026!"}).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {tok_a}"}
    headers_b = {"Authorization": f"Bearer {tok_b}"}

    db = SessionLocal()
    # Create private alert for User Alpha
    alert_a = DRIUTAlert(
        user_id="user_alpha",
        saved_paper_id=setup_security_suite["paper1_id"],
        trigger_paper_id=setup_security_suite["paper2_id"],
        relationship_type="Extension",
        confidence_score=0.88,
        explanation="Direct extension of Alice's isolated work.",
        is_read=False
    )
    db.add(alert_a)
    db.commit()
    db.refresh(alert_a)
    alert_a_id = alert_a.id
    db.close()

    # User B lists alerts -> cannot see Alert A
    alerts_b = client.get("/api/v1/papers/driut/alerts", headers=headers_b).json()
    assert not any(a["id"] == alert_a_id for a in alerts_b)

    # User B attempts to mark Alert A as read -> receives 404
    mark_b = client.patch(f"/api/v1/papers/driut/alerts/{alert_a_id}/read", headers=headers_b)
    assert mark_b.status_code == 404

    # Verify Alert A remains unread in database
    db = SessionLocal()
    refreshed_alert = db.query(DRIUTAlert).filter(DRIUTAlert.id == alert_a_id).first()
    assert refreshed_alert.is_read is False
    db.close()

    # User A marks Alert A as read -> succeeds (200)
    mark_a = client.patch(f"/api/v1/papers/driut/alerts/{alert_a_id}/read", headers=headers_a)
    assert mark_a.status_code == 200
    assert mark_a.json()["is_read"] is True


def test_public_endpoints_accessible_without_authentication(setup_security_suite):
    """Public discovery, comparison, summary, and health endpoints remain accessible without auth."""
    # Health checks
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200

    # Public paper search (local sources to avoid mutating index or calling live APIs)
    search_res = client.post(
        "/api/v1/papers/search",
        json={"query": "neural", "limit": 3, "sources": ["local"]}
    )
    assert search_res.status_code == 200
    assert "results" in search_res.json()

    # Public summary for known fixture paper
    p1_paper_id = setup_security_suite["paper1_paper_id"]
    summary_res = client.get(f"/api/v1/papers/{p1_paper_id}/summary")
    assert summary_res.status_code == 200
    assert "executive_summary" in summary_res.json()

    # Public comparison for known fixture papers
    p2_paper_id = setup_security_suite["paper2_paper_id"]
    comp_res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": [p1_paper_id, p2_paper_id]}
    )
    assert comp_res.status_code == 200
    assert "comparison_points" in comp_res.json()
    assert "papers" in comp_res.json()


def test_token_invalid_signature_and_missing_claims_rejected(setup_security_suite):
    """Tokens with foreign signature or missing sub claim must fail fail-closed."""
    import jwt
    from app.core.config import get_settings
    settings = get_settings()

    # 1. Foreign secret key signature
    foreign_token = jwt.encode({"sub": "user_alpha"}, "completely_wrong_secret_key_12345", algorithm=settings.JWT_ALGORITHM)
    res_foreign = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {foreign_token}"})
    assert res_foreign.status_code == 401
    assert "Invalid or expired access token" in get_error_message(res_foreign)

    # 2. Missing 'sub' claim
    missing_sub_token = jwt.encode({"role": "researcher"}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    res_no_sub = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {missing_sub_token}"})
    assert res_no_sub.status_code == 401
    assert "Token missing valid subject identifier" in get_error_message(res_no_sub)


def test_deactivated_user_rejected(setup_security_suite):
    """Deactivated accounts cannot authenticate or access protected endpoints."""
    db = SessionLocal()
    user = db.query(User).filter(User.username == "user_alpha").first()
    assert user is not None
    user.is_active = False
    db.commit()
    db.close()

    try:
        # Login attempt
        res_login = client.post("/api/v1/auth/login", json={"username": "user_alpha", "password": "PasswordAlpha2026!"})
        assert res_login.status_code == 403
        assert "deactivated" in get_error_message(res_login).lower()

        # Bearer token attempt with valid token generated earlier
        token = create_access_token("user_alpha")
        res_token = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res_token.status_code == 403
        assert "deactivated" in get_error_message(res_token).lower()
    finally:
        # Re-activate user
        db = SessionLocal()
        user = db.query(User).filter(User.username == "user_alpha").first()
        if user:
            user.is_active = True
            db.commit()
        db.close()


# ==============================================================================
# Phase C: Authentication Hardening Regression Tests (ISSUE-04, 05, 06)
# ==============================================================================

def test_admin_seed_validation_and_safety():
    """
    ISSUE-04: Test administrator seed password validation, weak password rejection,
    production safeguard, and preservation of existing credentials.
    """
    from app.db.seed_admin import validate_admin_password, seed_admin_user
    import os

    # 1. Missing password
    with pytest.raises(ValueError) as exc_missing:
        validate_admin_password(None)
    assert "ADMIN_INITIAL_PASSWORD is required" in str(exc_missing.value)

    # 2. Too short
    with pytest.raises(ValueError) as exc_short:
        validate_admin_password("short")
    assert "between 8 and 128 characters" in str(exc_short.value)

    # 3. Known weak passwords rejected
    for weak in ["1234", "admin", "password", "12345678", "admin1234"]:
        with pytest.raises(ValueError) as exc_weak:
            validate_admin_password(weak)
        assert "too weak" in str(exc_weak.value)

    # 4. Strong synthetic password accepted
    strong = "SuperStrongSyntheticPass2026!#$"
    assert validate_admin_password(strong) == strong

    # 5. Production guard blocks execution without explicit authorization
    with patch.dict(os.environ, {
        "ENVIRONMENT": "production",
        "ALLOW_PRODUCTION_ADMIN_SEED": "",
        "ADMIN_INITIAL_PASSWORD": strong
    }):
        with pytest.raises(RuntimeError) as exc_prod:
            seed_admin_user(initial_password=strong)
        assert "Execution of administrator seed script in production is prohibited" in str(exc_prod.value)

    # 6. Existing administrator account is never overwritten
    db = SessionLocal()
    existing_admin = db.query(User).filter(User.username == "admin").first()
    if not existing_admin:
        from app.core.security import hash_password
        existing_admin = User(
            username="admin",
            email="admin@researchlens.local",
            hashed_password=hash_password("OriginalAdminPass2026!"),
            full_name="Existing Admin",
            is_active=True,
            is_superuser=True
        )
        db.add(existing_admin)
        db.commit()
    orig_pwd_hash = existing_admin.hashed_password
    db.close()

    # Run seed_admin_user with a different password
    seed_admin_user(initial_password="NewAttemptedPass2026!")

    db_check = SessionLocal()
    admin_after = db_check.query(User).filter(User.username == "admin").first()
    # Password hash must remain exactly unchanged!
    assert admin_after.hashed_password == orig_pwd_hash
    db_check.close()


def test_jwt_secret_validation_in_production():
    """
    ISSUE-05: Non-development environments reject predictable or inadequate JWT signing secrets.
    """
    from app.core.config import Settings

    # 1. Insecure dev default rejected in production
    with pytest.raises(ValueError) as exc_default:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="researchlens-secure-dev-secret-key-2026"
        )
    assert "Insecure or default JWT_SECRET_KEY rejected in 'production'" in str(exc_default.value)
    # Ensure secret value is not printed
    assert "researchlens-secure-dev-secret-key-2026" not in str(exc_default.value)

    # 2. Too short (<32 chars) rejected in production
    with pytest.raises(ValueError) as exc_short:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="a_short_key_under_32_chars"
        )
    assert "JWT_SECRET_KEY is too short" in str(exc_short.value)

    # 3. Valid strong synthetic key (>= 32 chars) accepted in production
    valid_prod_key = "a_sufficiently_long_and_cryptographically_secure_synthetic_jwt_secret_2026"
    prod_settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY=valid_prod_key
    )
    assert prod_settings.JWT_SECRET_KEY == valid_prod_key

    # 4. Development environment preserves default for local friction-free workflow
    dev_settings = Settings(
        ENVIRONMENT="development",
        JWT_SECRET_KEY="researchlens-secure-dev-secret-key-2026"
    )
    assert dev_settings.JWT_SECRET_KEY == "researchlens-secure-dev-secret-key-2026"


def test_compatibility_accounts_are_deactivated_and_unclaimable():
    """
    ISSUE-06: Compatibility accounts seeded for orphaned records must be deactivated
    and unclaimable via predictable passwords.
    """
    db = SessionLocal()
    compat_user = db.query(User).filter(User.username == "compat_orphan_test").first()
    if not compat_user:
        import secrets
        from app.core.security import hash_password
        compat_user = User(
            username="compat_orphan_test",
            email="compat_orphan_test@research.local",
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            full_name="Migrated Compatibility User",
            is_active=False
        )
        db.add(compat_user)
        db.commit()

    try:
        # Attempt to login with old predictable password pattern
        res = client.post("/api/v1/auth/login", json={
            "username": "compat_orphan_test",
            "password": "CompatPassword_compat_orphan_test_2026!"
        })
        # Rejected because password does not match random hash
        assert res.status_code == 401

        # Even with generated token, deactivated state blocks access
        token = create_access_token("compat_orphan_test")
        res_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res_me.status_code == 403
        assert "deactivated" in get_error_message(res_me).lower()
    finally:
        db.query(User).filter(User.username == "compat_orphan_test").delete()
        db.commit()
        db.close()


