"""
Migration script for TASK-04: User authentication, foreign keys, and isolation constraints.
Safe, idempotent, zero data loss, non-destructive migration.
Includes forward migration and documented rollback procedure.
"""
import secrets
from sqlalchemy import text
from app.db.session import engine, SessionLocal
from app.core.security import hash_password
from app.core.logging import get_logger

logger = get_logger(__name__)


def migrate_forward() -> None:
    """Apply TASK-04 schema changes without dropping or losing any data."""
    logger.info("Starting TASK-04 schema migration...")
    db = SessionLocal()
    try:
        # 1. Create users table if not exists
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                full_name VARCHAR(100),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superuser BOOLEAN NOT NULL DEFAULT FALSE;"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_users_id ON users (id);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);"))
        db.commit()

        # 2. Seed disabled default user if not exists to preserve compatibility with existing user_id references
        existing_default = db.execute(
            text("SELECT id FROM users WHERE username = :uname;"),
            {"uname": "default_user"}
        ).fetchone()

        if not existing_default:
            default_random_secret = secrets.token_urlsafe(32)
            default_pwd_hash = hash_password(default_random_secret)
            db.execute(
                text("""
                    INSERT INTO users (username, email, hashed_password, full_name, is_active)
                    VALUES (:username, :email, :hashed_password, :full_name, false);
                """),
                {
                    "username": "default_user",
                    "email": "default_user@research.local",
                    "hashed_password": default_pwd_hash,
                    "full_name": "Default Research User"
                }
            )
            db.commit()
            logger.info("Seeded deactivated default_user placeholder for backward compatibility.")

        # 3. Check for any existing orphaned user_ids in saved_papers or driut_alerts
        # and create placeholder users to preserve referential integrity without deleting data
        for table in ["saved_papers", "driut_alerts"]:
            user_ids = db.execute(text(f"SELECT DISTINCT user_id FROM {table};")).fetchall()
            for (uid,) in user_ids:
                if uid:
                    user_exists = db.execute(
                        text("SELECT id FROM users WHERE username = :uname;"),
                        {"uname": uid}
                    ).fetchone()
                    if not user_exists:
                        compat_random_secret = secrets.token_urlsafe(32)
                        pwd_hash = hash_password(compat_random_secret)
                        db.execute(
                            text("""
                                INSERT INTO users (username, email, hashed_password, full_name, is_active)
                                VALUES (:username, :email, :hashed_password, :full_name, false);
                            """),
                            {
                                "username": uid,
                                "email": f"{uid}@research.local",
                                "hashed_password": pwd_hash,
                                "full_name": f"Migrated User {uid}"
                            }
                        )
                        db.commit()
                        logger.info("Created deactivated compatibility user for existing user_id: %s", uid)

        # 4. Add foreign key on saved_papers.user_id -> users.username
        db.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_saved_papers_user_id'
                ) THEN
                    ALTER TABLE saved_papers
                    ADD CONSTRAINT fk_saved_papers_user_id
                    FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE;
                END IF;
            END $$;
        """))
        db.commit()

        # 5. Add unique constraint on saved_papers(user_id, paper_id)
        db.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'uq_user_saved_paper'
                ) THEN
                    ALTER TABLE saved_papers
                    ADD CONSTRAINT uq_user_saved_paper
                    UNIQUE (user_id, paper_id);
                END IF;
            END $$;
        """))
        db.commit()

        # 6. Add foreign key on driut_alerts.user_id -> users.username
        db.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_driut_alerts_user_id'
                ) THEN
                    ALTER TABLE driut_alerts
                    ADD CONSTRAINT fk_driut_alerts_user_id
                    FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE;
                END IF;
            END $$;
        """))
        db.commit()

        # 7. Add unique constraint on driut_alerts(user_id, saved_paper_id, trigger_paper_id)
        db.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'uq_user_driut_alert'
                ) THEN
                    ALTER TABLE driut_alerts
                    ADD CONSTRAINT uq_user_driut_alert
                    UNIQUE (user_id, saved_paper_id, trigger_paper_id);
                END IF;
            END $$;
        """))
        db.commit()

        # 8. Indexes for ownership-filtered queries
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_saved_papers_user_id ON saved_papers(user_id);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_driut_alerts_user_id ON driut_alerts(user_id);"))
        db.commit()

        logger.info("TASK-04 schema migration completed successfully.")
    except Exception as e:
        db.rollback()
        logger.error("Migration failed: %s", e)
        raise e
    finally:
        db.close()


def migrate_rollback() -> None:
    """Documented rollback procedure to remove constraints and user table if needed."""
    logger.info("Executing TASK-04 schema rollback...")
    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE saved_papers DROP CONSTRAINT IF EXISTS uq_user_saved_paper;"))
        db.execute(text("ALTER TABLE saved_papers DROP CONSTRAINT IF EXISTS fk_saved_papers_user_id;"))
        db.execute(text("ALTER TABLE driut_alerts DROP CONSTRAINT IF EXISTS uq_user_driut_alert;"))
        db.execute(text("ALTER TABLE driut_alerts DROP CONSTRAINT IF EXISTS fk_driut_alerts_user_id;"))
        db.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
        db.commit()
        logger.info("Rollback completed successfully.")
    except Exception as e:
        db.rollback()
        logger.error("Rollback failed: %s", e)
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    migrate_forward()
