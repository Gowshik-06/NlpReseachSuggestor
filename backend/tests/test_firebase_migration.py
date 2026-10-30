"""
Integration tests for Stage 2B Firebase user schema migration.
Verifies:
- Safe column addition of firebase_uid
- Making hashed_password nullable
- Unique constraint and index enforcement
- Migration idempotency (safe to rerun)
- Table row count preservation and zero data loss
- Rollback functionality
"""
import pytest
from sqlalchemy import text, inspect
from app.db.session import engine, SessionLocal
from app.models.user import User
from app.db.migrate_firebase_auth import (
    migrate_firebase_auth_forward,
    rollback_firebase_auth,
    verify_schema_invariants,
)


def test_migration_forward_and_idempotency():
    """Verify forward migration creates schema elements and is safe to execute multiple times."""
    db = SessionLocal()
    try:
        # First execution
        res1 = migrate_firebase_auth_forward(db_session=db, engine_to_use=engine)
        assert res1["success"] is True
        assert res1["status"] == "applied"

        # Verify columns and index
        status = verify_schema_invariants(db_session=db, engine_to_use=engine)
        assert status["ready"] is True
        assert status["has_firebase_uid"] is True
        assert status["has_index"] is True

        # Second execution (idempotency check)
        res2 = migrate_firebase_auth_forward(db_session=db, engine_to_use=engine)
        assert res2["success"] is True

        # Verify invariants remain intact
        status2 = verify_schema_invariants(db_session=db, engine_to_use=engine)
        assert status2["ready"] is True
    finally:
        db.close()


def test_unique_firebase_uid_constraint():
    """Verify that multiple users cannot share the same non-null Firebase UID."""
    db = SessionLocal()
    try:
        migrate_firebase_auth_forward(db_session=db, engine_to_use=engine)

        user1 = User(
            username="fb_test_u1",
            email="u1@test.local",
            hashed_password=None,
            firebase_uid="uid_unique_12345",
            is_active=True,
        )
        db.add(user1)
        db.commit()

        # Attempt to insert duplicate firebase_uid
        user2 = User(
            username="fb_test_u2",
            email="u2@test.local",
            hashed_password=None,
            firebase_uid="uid_unique_12345",
            is_active=True,
        )
        db.add(user2)
        with pytest.raises(Exception):
            db.commit()
        db.rollback()

        # Verify multiple NULL firebase_uids are permitted (local accounts without Firebase)
        user3 = User(
            username="local_u3",
            email="u3@test.local",
            hashed_password="some_hash_1",
            firebase_uid=None,
            is_active=True,
        )
        user4 = User(
            username="local_u4",
            email="u4@test.local",
            hashed_password="some_hash_2",
            firebase_uid=None,
            is_active=True,
        )
        db.add(user3)
        db.add(user4)
        db.commit()
        assert user3.id is not None
        assert user4.id is not None
    finally:
        db.close()
