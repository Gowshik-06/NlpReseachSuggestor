#!/usr/bin/env python3
"""
scripts/remediate_driut_chronology.py — Safe, Controlled DRIUT Chronology Remediation Utility.

Operational Maintenance Utility for purging the 90 audited historical DRIUT chronology violations.

Safety Invariants:
1. Read-only (dry-run) by default. Requires explicit '--execute' flag.
2. Requires explicit '--backup-file' flag referencing a verified PostgreSQL backup file.
3. Enforces strict allowlist from RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json:
   - Exactly 90 alert IDs.
   - Never deletes by broad WHERE predicates (e.g. 'WHERE year < 2026').
   - Never dynamically expands or infers IDs.
4. Executes within a single atomic database transaction.
5. Strict Pre-conditions asserted before mutation:
   - Total alerts in database must equal exactly 175.
   - Exactly 90 target rows match the allowlist IDs.
   - Every target row must satisfy: candidate_year < saved_year AND relationship_type IN ('Improvement', 'Extension').
   - Exactly 85 non-target rows must be compliant (75 valid, 10 exempt).
6. Strict Post-conditions asserted before commit:
   - Exactly 90 rows deleted (cursor.rowcount == 90).
   - Exactly 85 alerts remain in database.
   - Table counts for papers (162), users (7), saved_papers (5), and paper_evidence (3) unchanged.
7. Any assertion or database error triggers an immediate ROLLBACK.
8. Preserves the audit ledger and outputs a structured execution report.
"""
import argparse
import json
import os
import sys
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Set

from sqlalchemy import create_engine, text

# Setup project paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
LEDGER_PATH = os.path.join(PROJECT_ROOT, "RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json")

DEFAULT_DB_URL = "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/research_papers"


def compute_sha256(filepath: str) -> str:
    """Compute SHA-256 checksum of a file."""
    if not os.path.exists(filepath):
        return "FILE_NOT_FOUND"
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def load_audit_allowlist(ledger_path: str) -> Set[int]:
    """Load and validate the 90 approved alert IDs from the audit ledger."""
    if not os.path.exists(ledger_path):
        raise FileNotFoundError(f"Audit ledger file not found at: {ledger_path}")

    with open(ledger_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_ids = data.get("invalid_confirmed_alert_ids", [])
    if not isinstance(raw_ids, list):
        raise ValueError("Audit ledger 'invalid_confirmed_alert_ids' must be a JSON array.")

    allowlist: Set[int] = set(int(x) for x in raw_ids)
    if len(allowlist) != 90:
        raise ValueError(f"Allowlist must contain exactly 90 unique alert IDs; found {len(allowlist)}.")

    # Cross-check with ledger entries
    ledger_entries = data.get("ledger", [])
    ledger_invalid_ids = set(
        int(e["alert_id"]) for e in ledger_entries if e.get("classification") == "INVALID_CONFIRMED"
    )
    if allowlist != ledger_invalid_ids:
        raise ValueError("Mismatch between 'invalid_confirmed_alert_ids' and 'INVALID_CONFIRMED' ledger entries.")

    return allowlist


def verify_database_state(conn, allowlist: Set[int]) -> Dict[str, Any]:
    """
    Verify live database state and confirm every allowlist ID exists and violates chronology.
    Returns diagnostic snapshot.
    """
    # 1. Total count checks
    total_alerts = conn.execute(text("SELECT count(*) FROM driut_alerts;")).scalar()
    paper_count = conn.execute(text("SELECT count(*) FROM papers;")).scalar()
    user_count = conn.execute(text("SELECT count(*) FROM users;")).scalar()
    saved_count = conn.execute(text("SELECT count(*) FROM saved_papers;")).scalar()
    evidence_count = conn.execute(text("SELECT count(*) FROM paper_evidence;")).scalar()

    counts = {
        "total_alerts": total_alerts,
        "papers": paper_count,
        "users": user_count,
        "saved_papers": saved_count,
        "paper_evidence": evidence_count,
    }

    if total_alerts != 175:
        raise RuntimeError(f"Database pre-check failed: Expected 175 driut_alerts, found {total_alerts}.")

    # 2. Detailed alert rows
    query = text("""
        SELECT 
            a.id, a.user_id, a.relationship_type,
            sp.year AS saved_year,
            tp.year AS trigger_year
        FROM driut_alerts a
        JOIN papers sp ON a.saved_paper_id = sp.id
        JOIN papers tp ON a.trigger_paper_id = tp.id;
    """)
    rows = conn.execute(query).fetchall()

    live_ids = set(r[0] for r in rows)
    missing_ids = allowlist - live_ids
    if missing_ids:
        raise RuntimeError(f"Database pre-check failed: {len(missing_ids)} allowlisted IDs are missing: {sorted(missing_ids)}")

    # Verify each row
    invalid_found = 0
    valid_found = 0
    exempt_found = 0

    for r in rows:
        aid, user_id, rel_type, saved_year, trigger_year = r[0], r[1], r[2], r[3], r[4]
        if aid in allowlist:
            if rel_type not in ("Improvement", "Extension"):
                raise RuntimeError(f"Allowlisted alert {aid} has unexpected relationship type '{rel_type}'.")
            if trigger_year is None or saved_year is None or trigger_year >= saved_year:
                raise RuntimeError(f"Allowlisted alert {aid} does not violate chronology: trigger {trigger_year} >= saved {saved_year}.")
            invalid_found += 1
        else:
            if rel_type == "Alternative":
                exempt_found += 1
            else:
                if trigger_year is not None and saved_year is not None and trigger_year < saved_year:
                    raise RuntimeError(f"Unallowlisted alert {aid} violates chronology but is missing from allowlist: {trigger_year} < {saved_year}.")
                valid_found += 1

    if invalid_found != 90:
        raise RuntimeError(f"Expected exactly 90 verified invalid alerts, matched {invalid_found}.")
    if valid_found != 75:
        raise RuntimeError(f"Expected exactly 75 verified valid alerts, matched {valid_found}.")
    if exempt_found != 10:
        raise RuntimeError(f"Expected exactly 10 exempt alternative alerts, matched {exempt_found}.")

    return counts


def execute_remediation(db_url: str, ledger_path: str, backup_file: str, execute: bool) -> Dict[str, Any]:
    """Execute or simulate the allowlisted remediation."""
    allowlist = load_audit_allowlist(ledger_path)
    engine = create_engine(db_url)

    report: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ledger_path": ledger_path,
        "backup_file": backup_file,
        "backup_sha256": compute_sha256(backup_file) if backup_file else "NOT_PROVIDED",
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "allowlist_count": len(allowlist),
        "status": "INITIALIZING"
    }

    if execute and (not backup_file or not os.path.exists(backup_file)):
        raise RuntimeError("Execution requires a valid, existing backup file passed via --backup-file.")

    with engine.connect() as conn:
        # Pre-execution verification
        print("[PREFLIGHT] Verifying database state against allowlist...")
        pre_counts = verify_database_state(conn, allowlist)
        report["pre_counts"] = pre_counts
        print(f"[PREFLIGHT OK] Total alerts: {pre_counts['total_alerts']} (90 invalid, 75 valid, 10 exempt).")

        if not execute:
            report["status"] = "DRY_RUN_PASSED"
            report["message"] = "Dry-run successful. Pre-conditions verified. Zero database mutations performed."
            return report

        # Execution inside transaction
        conn.commit()  # Close the autobegun read-only preflight transaction
        print("[TRANSACTION] Beginning atomic deletion transaction...")
        trans = conn.begin()
        try:
            # Strict allowlisted deletion
            del_stmt = text("DELETE FROM driut_alerts WHERE id = ANY(:ids);")
            res = conn.execute(del_stmt, {"ids": list(allowlist)})
            deleted_rows = res.rowcount

            if deleted_rows != 90:
                raise RuntimeError(f"Rowcount assertion failed: expected 90 deletions, deleted {deleted_rows}. Aborting.")

            # Post-deletion verification
            post_alerts = conn.execute(text("SELECT count(*) FROM driut_alerts;")).scalar()
            if post_alerts != 85:
                raise RuntimeError(f"Post-condition failed: expected exactly 85 alerts, found {post_alerts}. Aborting.")

            # Verify unrelated tables unchanged
            post_papers = conn.execute(text("SELECT count(*) FROM papers;")).scalar()
            post_users = conn.execute(text("SELECT count(*) FROM users;")).scalar()
            post_saved = conn.execute(text("SELECT count(*) FROM saved_papers;")).scalar()
            post_evidence = conn.execute(text("SELECT count(*) FROM paper_evidence;")).scalar()

            if post_papers != pre_counts["papers"]:
                raise RuntimeError(f"Integrity violation: papers count changed from {pre_counts['papers']} to {post_papers}!")
            if post_users != pre_counts["users"]:
                raise RuntimeError(f"Integrity violation: users count changed from {pre_counts['users']} to {post_users}!")
            if post_saved != pre_counts["saved_papers"]:
                raise RuntimeError(f"Integrity violation: saved_papers count changed from {pre_counts['saved_papers']} to {post_saved}!")
            if post_evidence != pre_counts["paper_evidence"]:
                raise RuntimeError(f"Integrity violation: paper_evidence count changed from {pre_counts['paper_evidence']} to {post_evidence}!")

            # Verify all remaining alerts are compliant
            remaining = conn.execute(text("""
                SELECT a.id, a.relationship_type, sp.year, tp.year
                FROM driut_alerts a
                JOIN papers sp ON a.saved_paper_id = sp.id
                JOIN papers tp ON a.trigger_paper_id = tp.id;
            """)).fetchall()

            for r in remaining:
                aid, rel_type, sy, ty = r[0], r[1], r[2], r[3]
                if rel_type != "Alternative" and ty is not None and sy is not None and ty < sy:
                    raise RuntimeError(f"Integrity violation: alert {aid} remains invalid after deletion!")

            # Commit transaction
            trans.commit()
            print("[TRANSACTION COMMITTED] Exactly 90 invalid alerts deleted. 85 compliant alerts remain.")

            report["deleted_rows"] = deleted_rows
            report["post_counts"] = {
                "total_alerts": post_alerts,
                "papers": post_papers,
                "users": post_users,
                "saved_papers": post_saved,
                "paper_evidence": post_evidence,
            }
            report["status"] = "SUCCESS_COMMITTED"
            return report

        except Exception as e:
            trans.rollback()
            print(f"[TRANSACTION ROLLED BACK] An error occurred: {e}")
            report["status"] = "FAILED_ROLLED_BACK"
            report["error"] = str(e)
            raise


def main():
    parser = argparse.ArgumentParser(description="Remediate 90 historical DRIUT chronology violations safely.")
    parser.add_argument("--execute", action="store_true", help="Execute deletion (default is read-only dry run).")
    parser.add_argument("--backup-file", type=str, help="Path to verified full PostgreSQL backup file.")
    parser.add_argument("--db-url", type=str, default=DEFAULT_DB_URL, help="Database connection URL.")
    parser.add_argument("--ledger-path", type=str, default=LEDGER_PATH, help="Path to audit ledger JSON.")
    args = parser.parse_args()

    print("=" * 80)
    print(" ResearchLens — Safe DRIUT Chronology Remediation Utility")
    print("=" * 80)
    print(f"Mode: {'EXECUTE (DELETION ENABLED)' if args.execute else 'DRY RUN (READ-ONLY)'}")
    print(f"Ledger: {args.ledger_path}")
    print(f"Backup File: {args.backup_file or 'None'}")

    try:
        res = execute_remediation(
            db_url=args.db_url,
            ledger_path=args.ledger_path,
            backup_file=args.backup_file,
            execute=args.execute
        )
        print("\nResult Summary:")
        print(json.dumps(res, indent=2))
        sys.exit(0)
    except Exception as exc:
        print(f"\n[ERROR] Remediation stopped: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
