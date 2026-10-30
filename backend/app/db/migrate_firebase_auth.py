"""
Migration script for Stage 2B: Firebase Authentication User Schema Integration.
Safely adds nullable firebase_uid column and unique index to the users table,
and makes hashed_password nullable for Firebase-only authenticated accounts.
Preserves existing usernames, primary keys, passwords, foreign keys, and ownership relations.
Idempotent, non-destructive, zero data loss migration with verification and rollback.
"""
import sys
from typing import Dict, Any, Optional
from sqlalchemy import text, inspect
from sqlalchemy.exc import OperationalError
from app.db.session import engine, SessionLocal
from app.core.logging import get_logger

logger = get_logger(__name__)


def check_database_accessible(engine_to_use=None) -> bool:
    """Check if target database is reachable."""
    eng = engine_to_use or engine
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1;"))
            return True
    except OperationalError as e:
        logger.warning("Target database connection failed: %s", e)
        return False
    except Exception as e:
        logger.warning("Database accessibility check failed: %s", e)
        return False


def get_table_row_counts(db) -> Dict[str, int]:
    """Retrieve row counts for critical application tables to enforce invariant preservation."""
    tables = ["users", "papers", "saved_papers", "paper_evidence", "driut_alerts"]
    counts = {}
    for tbl in tables:
        try:
            res = db.execute(text(f"SELECT COUNT(*) FROM {tbl};")).scalar()
            counts[tbl] = res
        except Exception:
            # Table might not exist in a sparse test environment
            counts[tbl] = -1
    return counts


def migrate_firebase_auth_forward(db_session=None, engine_to_use=None) -> Dict[str, Any]:
    """
    Idempotently apply Stage 2B schema modifications to the users table:
    1. Add nullable firebase_uid VARCHAR(128).
    2. Make hashed_password nullable (to support Firebase-only users).
    3. Add unique index ix_users_firebase_uid for non-null firebase_uids.
    4. Validate schema and table invariant counts.
    """
    eng = engine_to_use or engine
    if not check_database_accessible(eng):
        msg = f"Database at {eng.url} is not accessible. Migration cannot proceed."
        logger.error(msg)
        return {"success": False, "status": "blocked", "error": msg}

    owns_session = False
    if db_session is None:
        db = SessionLocal()
        owns_session = True
    else:
        db = db_session

    try:
        logger.info("Starting Stage 2B Firebase user schema migration on dialect: %s", eng.dialect.name)
        before_counts = get_table_row_counts(db)

        # Confirm users table exists
        inspector = inspect(eng)
        table_names = inspector.get_table_names()
        if "users" not in table_names:
            raise RuntimeError("Required table 'users' does not exist in target database.")

        dialect_name = eng.dialect.name

        if dialect_name == "postgresql":
            # 1. Add firebase_uid column if not exists
            db.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR(128);
            """))
            db.commit()

            # 2. Make hashed_password nullable for Firebase accounts
            db.execute(text("""
                ALTER TABLE users
                ALTER COLUMN hashed_password DROP NOT NULL;
            """))
            db.commit()

            # 3. Create unique index for non-null firebase_uid
            db.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS ix_users_firebase_uid
                ON users (firebase_uid)
                WHERE firebase_uid IS NOT NULL;
            """))
            db.commit()
            logger.info("PostgreSQL users table updated with firebase_uid and nullable hashed_password.")

        else:
            # SQLite / Test dialect support
            columns = [c["name"] for c in inspector.get_columns("users")]
            if "firebase_uid" not in columns:
                db.execute(text("ALTER TABLE users ADD COLUMN firebase_uid VARCHAR(128);"))
                db.commit()

            # Create unique index in SQLite
            db.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS ix_users_firebase_uid
                ON users (firebase_uid);
            """))
            db.commit()
            logger.info("SQLite users table updated with firebase_uid column and unique index.")

        # Post-migration invariant verification
        after_counts = get_table_row_counts(db)
        for tbl, count in before_counts.items():
            if count >= 0 and after_counts.get(tbl) != count:
                raise RuntimeError(
                    f"CRITICAL: Row count mismatch in table {tbl} after migration! "
                    f"Before: {count}, After: {after_counts.get(tbl)}"
                )

        logger.info("Stage 2B migration completed successfully with row count invariants verified: %s", after_counts)
        return {
            "success": True,
            "status": "applied",
            "dialect": dialect_name,
            "counts": after_counts,
        }

    except Exception as e:
        db.rollback()
        logger.error("Stage 2B migration failed: %s", e)
        raise e
    finally:
        if owns_session:
            db.close()


def rollback_firebase_auth(db_session=None, engine_to_use=None) -> Dict[str, Any]:
    """Roll back Stage 2B schema modifications."""
    eng = engine_to_use or engine
    if not check_database_accessible(eng):
        msg = f"Database at {eng.url} is not accessible. Rollback cannot proceed."
        logger.error(msg)
        return {"success": False, "status": "blocked", "error": msg}

    owns_session = False
    if db_session is None:
        db = SessionLocal()
        owns_session = True
    else:
        db = db_session

    try:
        logger.info("Starting rollback of Stage 2B Firebase user schema migration...")
        dialect_name = eng.dialect.name

        if dialect_name == "postgresql":
            db.execute(text("DROP INDEX IF EXISTS ix_users_firebase_uid;"))
            db.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS firebase_uid;"))
            db.commit()
            logger.info("PostgreSQL firebase_uid column and index removed.")
        else:
            # SQLite does not support DROP COLUMN cleanly in older versions, but drops index
            db.execute(text("DROP INDEX IF EXISTS ix_users_firebase_uid;"))
            db.commit()
            logger.info("SQLite ix_users_firebase_uid index dropped.")

        return {"success": True, "status": "rolled_back", "dialect": dialect_name}
    except Exception as e:
        db.rollback()
        logger.error("Stage 2B rollback failed: %s", e)
        raise e
    finally:
        if owns_session:
            db.close()


def verify_schema_invariants(db_session=None, engine_to_use=None) -> Dict[str, Any]:
    """Verify that users table schema contains expected columns and index."""
    eng = engine_to_use or engine
    if not check_database_accessible(eng):
        return {"accessible": False, "error": f"Database at {eng.url} unreachable"}

    inspector = inspect(eng)
    columns = {c["name"]: c for c in inspector.get_columns("users")}
    indexes = [idx["name"] for idx in inspector.get_indexes("users")]

    has_firebase_uid = "firebase_uid" in columns
    has_index = "ix_users_firebase_uid" in indexes
    hashed_pwd_nullable = columns.get("hashed_password", {}).get("nullable", True)

    return {
        "accessible": True,
        "has_firebase_uid": has_firebase_uid,
        "has_index": has_index,
        "hashed_password_nullable": hashed_pwd_nullable,
        "ready": has_firebase_uid and has_index,
    }


def link_admin_firebase_identity(firebase_uid: str, db_session=None, engine_to_use=None) -> Dict[str, Any]:
    """
    Safely link an existing administrator account (username='admin', is_superuser=True)
    to a verified Firebase UID via explicit administrative action.
    """
    if not firebase_uid or not isinstance(firebase_uid, str) or not firebase_uid.strip():
        raise ValueError("Non-empty Firebase UID must be provided.")

    clean_uid = firebase_uid.strip()
    owns_session = False
    if db_session is None:
        db = SessionLocal()
        owns_session = True
    else:
        db = db_session

    try:
        from app.models.user import User
        # 1. Check if UID is already linked to another account
        existing_uid_user = db.query(User).filter(User.firebase_uid == clean_uid).first()
        if existing_uid_user:
            return {
                "success": False,
                "error": f"Firebase UID '{clean_uid}' is already linked to user '{existing_uid_user.username}' (id={existing_uid_user.id})."
            }

        # 2. Find local admin account
        admin_user = db.query(User).filter(User.username == "admin", User.is_superuser == True).first()
        if not admin_user:
            return {"success": False, "error": "Local administrator account ('admin' with is_superuser=True) not found."}

        admin_user.firebase_uid = clean_uid
        db.commit()
        db.refresh(admin_user)
        logger.info("Successfully bound Firebase UID %s to administrator account %s", clean_uid, admin_user.username)
        return {
            "success": True,
            "username": admin_user.username,
            "id": admin_user.id,
            "is_superuser": admin_user.is_superuser,
            "firebase_uid": admin_user.firebase_uid,
        }
    except Exception as e:
        db.rollback()
        logger.error("Failed to link admin account: %s", e)
        raise e
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "--forward"
    if action == "--forward":
        res = migrate_firebase_auth_forward()
        print(f"Migration result: {res}")
    elif action == "--rollback":
        res = rollback_firebase_auth()
        print(f"Rollback result: {res}")
    elif action == "--verify":
        res = verify_schema_invariants()
        print(f"Verification result: {res}")
    elif action == "--link-admin":
        if len(sys.argv) < 3:
            print("Usage: python -m app.db.migrate_firebase_auth --link-admin <FIREBASE_UID>")
            sys.exit(1)
        res = link_admin_firebase_identity(sys.argv[2])
        print(f"Link admin result: {res}")
    else:
        print("Usage: python -m app.db.migrate_firebase_auth [--forward|--rollback|--verify|--link-admin <UID>]")
