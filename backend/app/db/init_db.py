"""
Database initialization and table creation.
"""
from app.db.session import engine, Base
from app.models import User, Paper, SavedPaper, DRIUTAlert, PaperEvidence
from app.core.logging import get_logger

logger = get_logger(__name__)


def init_db() -> None:
    """Create all application tables if they do not exist."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Successfully initialized database tables: %s", list(Base.metadata.tables.keys()))
    except Exception as e:
        logger.error("Failed to initialize database tables: %s", e)
        raise e


if __name__ == "__main__":
    init_db()
