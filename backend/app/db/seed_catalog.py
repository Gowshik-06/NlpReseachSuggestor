"""
Seed public academic paper catalog into PostgreSQL from precomputed FAISS metadata.
Safe, idempotent, zero data loss. Inserts missing papers without touching users or personal data.
"""
import os
import sys
import json
from typing import Optional
from sqlalchemy.orm import Session

# Ensure backend root is on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "../.."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.db.session import SessionLocal
from app.models.paper import Paper
from app.core.logging import get_logger

logger = get_logger(__name__)

FAISS_META_PATH = os.path.join(BACKEND_DIR, "data", "processed", "faiss", "papers_meta.json")


def seed_catalog_papers(session: Optional[Session] = None) -> int:
    """
    Populate papers table from papers_meta.json if papers are missing.
    Idempotent: skips papers that already exist in the database.
    """
    if not os.path.exists(FAISS_META_PATH):
        logger.warning("FAISS metadata file not found at %s. Skipping catalog seed.", FAISS_META_PATH)
        return 0

    with open(FAISS_META_PATH, "r", encoding="utf-8") as f:
        meta_json = json.load(f)

    meta_dict = meta_json.get("metadata", {})
    if not meta_dict:
        logger.info("No papers found in %s", FAISS_META_PATH)
        return 0

    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        existing_pids = set(r[0] for r in session.query(Paper.paper_id).filter(Paper.paper_id.isnot(None)).all())
        new_papers = []

        for pid, data in meta_dict.items():
            clean_pid = data.get("paper_id") or pid
            if clean_pid in existing_pids:
                continue

            authors = data.get("authors", [])
            if isinstance(authors, str):
                authors = [a.strip() for a in authors.split(",") if a.strip()]

            categories = data.get("categories", [])
            if isinstance(categories, str):
                categories = [c.strip() for c in categories.split(",") if c.strip()]

            year_val = None
            if data.get("year") is not None:
                try:
                    year_val = int(data["year"])
                except (ValueError, TypeError):
                    year_val = None

            citation_val = 0
            if data.get("citation_count") is not None:
                try:
                    citation_val = int(data["citation_count"])
                except (ValueError, TypeError):
                    citation_val = 0

            p = Paper(
                paper_id=clean_pid,
                title=data.get("title") or "Untitled Paper",
                abstract=data.get("abstract"),
                authors=authors,
                venue=data.get("venue"),
                year=year_val,
                doi=data.get("doi"),
                url=data.get("url"),
                pdf_url=data.get("pdf_url"),
                source=data.get("source") or "arxiv",
                citation_count=citation_val,
                categories=categories
            )
            new_papers.append(p)
            existing_pids.add(clean_pid)

        if new_papers:
            session.add_all(new_papers)
            session.commit()
            logger.info("Successfully seeded %d catalog papers into PostgreSQL.", len(new_papers))
            return len(new_papers)
        else:
            logger.info("All %d catalog papers are already present in PostgreSQL database.", len(meta_dict))
            return 0
    except Exception as e:
        session.rollback()
        logger.error("Failed to seed catalog papers: %s", e)
        raise e
    finally:
        if close_session:
            session.close()


if __name__ == "__main__":
    count = seed_catalog_papers()
    print(f"Catalog paper seeding complete. Added: {count} papers.")
