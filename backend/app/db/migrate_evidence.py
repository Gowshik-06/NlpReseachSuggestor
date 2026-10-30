"""
Migration script for TASK-13: ResearchLens Evidence Grounding Schema.
Safely creates paper_evidence table, indexes, and constraints.
Idempotent, non-destructive, zero data loss migration with documented rollback.
"""
from sqlalchemy import text
from app.db.session import engine, SessionLocal
from app.core.logging import get_logger

logger = get_logger(__name__)


def migrate_evidence_forward() -> None:
    """Create paper_evidence table and associated indexes idempotently."""
    logger.info("Starting TASK-13 paper_evidence schema migration...")
    db = SessionLocal()
    try:
        # 1. Create paper_evidence table
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS paper_evidence (
                id SERIAL PRIMARY KEY,
                paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                category VARCHAR(50) NOT NULL,
                claim TEXT NOT NULL,
                source_passage TEXT NOT NULL,
                char_start INTEGER,
                char_end INTEGER,
                page_number INTEGER,
                section_name VARCHAR(100),
                source_type VARCHAR(50) NOT NULL DEFAULT 'abstract',
                extraction_method VARCHAR(50) NOT NULL DEFAULT 'rule_based_nlp',
                confidence_score FLOAT,
                is_verified BOOLEAN NOT NULL DEFAULT TRUE,
                verification_notes VARCHAR(255),
                source_hash VARCHAR(64),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """))
        db.commit()

        # 2. Add unique constraint on (paper_id, category, char_start, char_end) if not exists
        db.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'uq_paper_evidence_span'
                ) THEN
                    ALTER TABLE paper_evidence
                    ADD CONSTRAINT uq_paper_evidence_span
                    UNIQUE (paper_id, category, char_start, char_end);
                END IF;
            END $$;
        """))
        db.commit()

        # 3. Create indexes for fast lookup and filtering
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_paper_evidence_paper_id ON paper_evidence(paper_id);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_paper_evidence_category ON paper_evidence(category);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_paper_evidence_source_type ON paper_evidence(source_type);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_paper_evidence_source_hash ON paper_evidence(source_hash);"))
        db.commit()

        logger.info("TASK-13 paper_evidence schema migration applied successfully.")
    except Exception as e:
        db.rollback()
        logger.error("Evidence migration failed: %s", e)
        raise e
    finally:
        db.close()


def migrate_evidence_rollback() -> None:
    """Documented rollback procedure to remove paper_evidence table if needed."""
    logger.info("Executing TASK-13 paper_evidence schema rollback...")
    db = SessionLocal()
    try:
        db.execute(text("DROP TABLE IF EXISTS paper_evidence CASCADE;"))
        db.commit()
        logger.info("TASK-13 paper_evidence schema rollback completed successfully.")
    except Exception as e:
        db.rollback()
        logger.error("Evidence rollback failed: %s", e)
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    migrate_evidence_forward()
