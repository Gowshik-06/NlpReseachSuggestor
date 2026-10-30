"""
Migration script for TASK-15: ResearchLens Evidence-Backed DRIUT Intelligence Schema.
Safely adds evidence grounding, provenance, and comparability columns to driut_alerts table.
Idempotent, non-destructive, zero data loss migration.
"""
from sqlalchemy import text
from app.db.session import engine, SessionLocal
from app.core.logging import get_logger

logger = get_logger(__name__)


def migrate_driut_evidence_forward() -> None:
    """Add evidence grounding columns to driut_alerts table idempotently."""
    logger.info("Starting TASK-15 driut_alerts schema migration...")
    db = SessionLocal()
    try:
        # Check dialect
        dialect_name = engine.dialect.name
        if dialect_name == "postgresql":
            # Add columns using ADD COLUMN IF NOT EXISTS
            db.execute(text("""
                ALTER TABLE driut_alerts
                ADD COLUMN IF NOT EXISTS evidence_strength VARCHAR(50) DEFAULT 'tentative',
                ADD COLUMN IF NOT EXISTS evidence_passage TEXT,
                ADD COLUMN IF NOT EXISTS saved_evidence_passage TEXT,
                ADD COLUMN IF NOT EXISTS char_start INTEGER,
                ADD COLUMN IF NOT EXISTS char_end INTEGER,
                ADD COLUMN IF NOT EXISTS section_name VARCHAR(100),
                ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) DEFAULT 'abstract',
                ADD COLUMN IF NOT EXISTS semantic_similarity FLOAT,
                ADD COLUMN IF NOT EXISTS comparability_notes TEXT,
                ADD COLUMN IF NOT EXISTS uncertainty_warning TEXT,
                ADD COLUMN IF NOT EXISTS classification_version VARCHAR(50) DEFAULT 'v2.0-evidence-grounded';
            """))
            db.commit()

            # Create index on evidence_strength and classification_version
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_driut_alerts_evidence_strength ON driut_alerts(evidence_strength);"))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_driut_alerts_class_version ON driut_alerts(classification_version);"))
            db.commit()
            logger.info("PostgreSQL driut_alerts columns and indexes verified successfully.")
        else:
            # Fallback for SQLite in isolated tests
            columns_needed = [
                ("evidence_strength", "VARCHAR(50) DEFAULT 'tentative'"),
                ("evidence_passage", "TEXT"),
                ("saved_evidence_passage", "TEXT"),
                ("char_start", "INTEGER"),
                ("char_end", "INTEGER"),
                ("section_name", "VARCHAR(100)"),
                ("source_type", "VARCHAR(50) DEFAULT 'abstract'"),
                ("semantic_similarity", "FLOAT"),
                ("comparability_notes", "TEXT"),
                ("uncertainty_warning", "TEXT"),
                ("classification_version", "VARCHAR(50) DEFAULT 'v2.0-evidence-grounded'")
            ]
            for col_name, col_type in columns_needed:
                try:
                    db.execute(text(f"ALTER TABLE driut_alerts ADD COLUMN {col_name} {col_type};"))
                    db.commit()
                except Exception:
                    # Column likely exists in SQLite
                    db.rollback()
            logger.info("Non-PostgreSQL driut_alerts columns checked.")
    except Exception as e:
        db.rollback()
        logger.error("Migration failed: %s", e)
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    migrate_driut_evidence_forward()
