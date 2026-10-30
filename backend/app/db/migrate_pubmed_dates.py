"""
ResearchLens — Idempotent Historical PubMed Publication Date Migration
TASK: Safely update verified 2026 electronic publication dates for the 25 legacy PubMed records.
Preserves the authentic forthcoming 2028 record (pubmed:42635983).

Features:
- Default: Dry-run preview mode (zero writes).
- Atomic transaction boundaries with automatic rollback on any error.
- Idempotent: can be safely executed multiple times without unintended mutations.
- Exact target record verification (row count assertion).
- Rollback support (--rollback).
"""
import argparse
import sys
import os
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text

# Add backend directory to sys.path if not present
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

DEFAULT_DB_URL = os.environ.get("DATABASE_URL") or "postgresql+psycopg2://postgres:postgres@localhost:5432/research_papers"


def get_db_engine(db_url: Optional[str] = None):
    url = db_url or DEFAULT_DB_URL
    return create_engine(url)


# Exact 25 PubMed IDs verified to have epubdate in 2026 with scheduled print in 2027
TARGET_PMIDS_2026 = [
    "pubmed:42431082",
    "pubmed:42630760",
    "pubmed:42602370",
    "pubmed:42571518",
    "pubmed:42828130",
    "pubmed:42700495",
    "pubmed:42541881",
    "pubmed:42732690",
    "pubmed:42669247",
    "pubmed:42636640",
    "pubmed:42502841",
    "pubmed:42520721",
    "pubmed:42497539",
    "pubmed:42485773",
    "pubmed:42480163",
    "pubmed:42766880",
    "pubmed:42731264",
    "pubmed:42735527",
    "pubmed:42609944",
    "pubmed:42665118",
    "pubmed:42741542",
    "pubmed:42729482",
    "pubmed:42766881",
    "pubmed:42751209",
    "pubmed:42733543",
]

# Explicitly protected record: authentic forthcoming scheduled print article in 2028
EXCLUDED_FORTHCOMING_PMID = "pubmed:42635983"


def preview_migration(engine) -> List[Dict[str, Any]]:
    """Retrieve and display dry-run status of the 26 historical records."""
    preview_items = []
    with engine.connect() as conn:
        all_ids = TARGET_PMIDS_2026 + [EXCLUDED_FORTHCOMING_PMID]
        rows = conn.execute(
            text("""
                SELECT id, paper_id, title, year, venue, source
                FROM papers
                WHERE paper_id IN :pids
                ORDER BY year DESC, id ASC;
            """),
            {"pids": tuple(all_ids)}
        ).fetchall()

        for r in rows:
            db_id, pid, title, current_year, venue, source = r
            if pid == EXCLUDED_FORTHCOMING_PMID:
                action = "PRESERVE (Authentic Forthcoming 2028 Issue)"
                proposed_year = 2028
            else:
                action = "UPDATE year 2027 -> 2026 (Electronic Availability)"
                proposed_year = 2026

            preview_items.append({
                "db_id": db_id,
                "paper_id": pid,
                "title": title[:50] + "..." if len(title) > 50 else title,
                "current_year": current_year,
                "proposed_year": proposed_year,
                "action": action,
            })
    return preview_items


def execute_migration(engine, rollback: bool = False) -> Dict[str, Any]:
    """
    Execute atomic update within a strict transaction boundary.
    Rolls back automatically on exception or rowcount mismatch.
    """
    with engine.begin() as conn:
        if rollback:
            # Revert the 25 records from 2026 back to 2027
            result = conn.execute(
                text("""
                    UPDATE papers
                    SET year = 2027
                    WHERE paper_id IN :pids
                      AND year = 2026;
                """),
                {"pids": tuple(TARGET_PMIDS_2026)}
            )
            affected = result.rowcount
            # Verify 2028 record was NOT touched
            year_2028 = conn.execute(
                text("SELECT year FROM papers WHERE paper_id = :pid;"),
                {"pid": EXCLUDED_FORTHCOMING_PMID}
            ).scalar()
            assert year_2028 == 2028, f"Invariant violation: {EXCLUDED_FORTHCOMING_PMID} was modified!"
            _sync_metadata_json(2027)
            return {"status": "success", "mode": "rollback", "rows_updated": affected}
        else:
            # Forward migration: update 25 records from 2027 to 2026
            result = conn.execute(
                text("""
                    UPDATE papers
                    SET year = 2026
                    WHERE paper_id IN :pids
                      AND year = 2027;
                """),
                {"pids": tuple(TARGET_PMIDS_2026)}
            )
            affected = result.rowcount
            if affected != len(TARGET_PMIDS_2026) and affected != 0:
                raise RuntimeError(
                    f"Unexpected rowcount during migration: {affected} rows updated. "
                    f"Expected exactly {len(TARGET_PMIDS_2026)} (or 0 if already applied). Aborting transaction."
                )

            # Verify 2028 record was NOT touched
            year_2028 = conn.execute(
                text("SELECT year FROM papers WHERE paper_id = :pid;"),
                {"pid": EXCLUDED_FORTHCOMING_PMID}
            ).scalar()
            assert year_2028 == 2028, f"Invariant violation: {EXCLUDED_FORTHCOMING_PMID} was modified!"
            _sync_metadata_json(2026)
            return {"status": "success", "mode": "forward", "rows_updated": affected}


def _sync_metadata_json(target_year: int) -> None:
    """Synchronize year in papers_meta.json without touching FAISS vector index."""
    import json
    meta_path = os.path.join(BACKEND_DIR, "data", "processed", "faiss", "papers_meta.json")
    if not os.path.exists(meta_path):
        return

    with open(meta_path, "r", encoding="utf-8") as f:
        meta_data = json.load(f)

    meta_dict = meta_data.get("metadata", {})
    updated = 0
    for pid in TARGET_PMIDS_2026:
        if pid in meta_dict and meta_dict[pid].get("year") != target_year:
            meta_dict[pid]["year"] = target_year
            updated += 1

    if updated > 0:
        tmp_path = f"{meta_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2)
        os.replace(tmp_path, meta_path)



def main():
    parser = argparse.ArgumentParser(description="ResearchLens Historical PubMed Date Migration")
    parser.add_argument("--db-url", default=None, help="Database connection URL")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview changes without executing (default: True)")
    parser.add_argument("--execute", action="store_true", default=False, help="Execute migration forward (2027 -> 2026)")
    parser.add_argument("--rollback", action="store_true", default=False, help="Revert migration (2026 -> 2027)")
    args = parser.parse_args()

    engine = get_db_engine(args.db_url)

    print("================================================================================")
    print("RESEARCHLENS — HISTORICAL PUBMED PUBLICATION DATE MIGRATION")
    print("================================================================================")
    print(f"Target count to update: {len(TARGET_PMIDS_2026)} records")
    print(f"Protected forthcoming record: {EXCLUDED_FORTHCOMING_PMID} (Preserved at year 2028)")

    preview = preview_migration(engine)
    print(f"\n--- READ-ONLY DATABASE PREVIEW ({len(preview)} records matched) ---")
    for item in preview:
        print(f"ID: {item['db_id']:3d} | {item['paper_id']:18s} | Current: {item['current_year']} -> Proposed: {item['proposed_year']} | {item['action']}")

    if not args.execute and not args.rollback:
        print("\n[DRY-RUN COMPLETE] Zero records modified in PostgreSQL.")
        print("To apply during an approved maintenance window with verified backups:")
        print("  python backend/app/db/migrate_pubmed_dates.py --execute")
        return

    if args.execute:
        print("\nExecuting forward migration within transaction...")
        res = execute_migration(engine, rollback=False)
        print(f"Migration completed successfully. Rows updated: {res['rows_updated']}")
    elif args.rollback:
        print("\nExecuting rollback within transaction...")
        res = execute_migration(engine, rollback=True)
        print(f"Rollback completed successfully. Rows reverted: {res['rows_updated']}")


if __name__ == "__main__":
    main()
