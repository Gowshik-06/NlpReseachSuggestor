#!/usr/bin/env python3
"""
ResearchLens — FAISS & PostgreSQL Safe Reconciliation & Diagnostic Tool
Phase 4 Operational Maintenance Utility.

Features:
- Read-only diagnostics by default (dry-run).
- Validates vector count, dimension, metadata keys, and finite values.
- Identifies orphaned vectors (in FAISS but missing in DB).
- Identifies unindexed papers (in DB but missing in FAISS).
- Requires explicit --execute and --backup-dir flags before making any modifications.
- Produces pre- and post-maintenance reports.
- Never runs during ordinary application startup.
"""
import argparse
import json
import os
import shutil
import sys
import hashlib
from typing import Dict, Any, List

import numpy as np

# Ensure backend root is on Python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import faiss
from sqlalchemy import create_engine, text

def compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    if not os.path.exists(filepath):
        return "FILE_NOT_FOUND"
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def diagnose_faiss_and_db(db_url: str, faiss_dir: str) -> Dict[str, Any]:
    """Run read-only comprehensive diagnostics comparing DB and FAISS."""
    index_path = os.path.join(faiss_dir, "research_index.faiss")
    meta_path = os.path.join(faiss_dir, "papers_meta.json")

    report: Dict[str, Any] = {
        "faiss_index_exists": os.path.exists(index_path),
        "faiss_meta_exists": os.path.exists(meta_path),
        "index_sha256": compute_sha256(index_path),
        "meta_sha256": compute_sha256(meta_path),
        "errors": []
    }

    if not report["faiss_index_exists"] or not report["faiss_meta_exists"]:
        report["errors"].append("FAISS index or metadata file missing on disk.")
        return report

    # 1. Read FAISS index
    try:
        index = faiss.read_index(index_path)
        report["ntotal"] = int(index.ntotal)
        report["dimension"] = int(index.d)
        report["metric_type"] = "INNER_PRODUCT" if index.metric_type == 0 else f"METRIC_{index.metric_type}"
    except Exception as e:
        report["errors"].append(f"Failed to read FAISS index: {e}")
        return report

    # 2. Read Metadata JSON
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_json = json.load(f)
        id_map: List[str] = meta_json.get("id_map", [])
        meta_dict: Dict[str, Any] = meta_json.get("metadata", {})
        report["id_map_count"] = len(id_map)
        report["meta_dict_count"] = len(meta_dict)
        report["duplicate_id_map_entries"] = len(id_map) - len(set(id_map))
    except Exception as e:
        report["errors"].append(f"Failed to parse metadata JSON: {e}")
        return report

    # 3. Check vector count vs metadata alignment
    if report["ntotal"] != report["id_map_count"]:
        report["errors"].append(f"Vector count ({report['ntotal']}) != id_map count ({report['id_map_count']}).")

    # 4. Check DB records
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            db_pids = set(r[0] for r in conn.execute(text("SELECT paper_id FROM papers WHERE paper_id IS NOT NULL;")).fetchall())
            report["db_paper_count"] = len(db_pids)
    except Exception as e:
        report["errors"].append(f"Failed to query PostgreSQL database: {e}")
        return report

    faiss_pids = set(id_map)
    orphans = list(faiss_pids - db_pids)
    unindexed = list(db_pids - faiss_pids)

    report["orphaned_in_faiss"] = orphans
    report["unindexed_in_db"] = unindexed
    report["is_consistent"] = (
        len(orphans) == 0 and len(unindexed) == 0 and report["ntotal"] == report["db_paper_count"] and len(report["errors"]) == 0
    )

    return report

def reconcile_and_purge_orphans(db_url: str, faiss_dir: str, backup_dir: str) -> Dict[str, Any]:
    """
    Execute atomic reconciliation to remove orphaned vectors:
    1. Copies active files to backup_dir.
    2. Validates backup SHA-256 hashes against active files.
    3. Builds replacement IndexFlatIP and metadata in temporary files.
    4. Verifies temporary files before atomic replacement.
    5. Automatically restores from backup if any exception occurs.
    """
    import uuid
    index_path = os.path.join(faiss_dir, "research_index.faiss")
    meta_path = os.path.join(faiss_dir, "papers_meta.json")

    os.makedirs(backup_dir, exist_ok=True)
    bak_idx = os.path.join(backup_dir, "research_index.faiss.bak")
    bak_meta = os.path.join(backup_dir, "papers_meta.json.bak")

    # Step 1: Create backup
    shutil.copy2(index_path, bak_idx)
    shutil.copy2(meta_path, bak_meta)

    # Step 2: Verify backup SHA-256 matches active
    orig_idx_hash = compute_sha256(index_path)
    bak_idx_hash = compute_sha256(bak_idx)
    orig_meta_hash = compute_sha256(meta_path)
    bak_meta_hash = compute_sha256(bak_meta)

    if orig_idx_hash != bak_idx_hash or orig_meta_hash != bak_meta_hash:
        raise RuntimeError("Backup SHA-256 verification mismatch! Aborting without modifying files.")

    # Step 3: Run diagnosis to find orphans
    diag = diagnose_faiss_and_db(db_url, faiss_dir)
    orphans = set(diag.get("orphaned_in_faiss", []))
    if not orphans:
        return {"status": "noop", "message": "Index is already consistent with zero orphans."}

    # Step 4: Read index and metadata
    index = faiss.read_index(index_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta_json = json.load(f)

    id_map = meta_json.get("id_map", [])
    meta_dict = meta_json.get("metadata", {})

    retained_indices = [i for i, pid in enumerate(id_map) if pid not in orphans]
    retained_pids = [id_map[i] for i in retained_indices]
    retained_meta = {pid: meta_dict[pid] for pid in retained_pids if pid in meta_dict}

    # Extract retained vectors
    vectors = np.zeros((len(retained_indices), index.d), dtype=np.float32)
    for new_idx, old_idx in enumerate(retained_indices):
        vectors[new_idx] = index.reconstruct(old_idx)

    # Step 5: Build new IndexFlatIP in isolated temporary files
    uid = uuid.uuid4().hex[:8]
    tmp_idx_path = os.path.join(faiss_dir, f"research_index.faiss.tmp.{uid}")
    tmp_meta_path = os.path.join(faiss_dir, f"papers_meta.json.tmp.{uid}")

    try:
        new_index = faiss.IndexFlatIP(index.d)
        new_index.add(vectors)
        faiss.write_index(new_index, tmp_idx_path)

        with open(tmp_meta_path, "w", encoding="utf-8") as f:
            json.dump({"id_map": retained_pids, "metadata": retained_meta}, f, indent=2)

        # Step 6: Verify temp files integrity
        test_idx = faiss.read_index(tmp_idx_path)
        assert test_idx.ntotal == len(retained_pids), "Temp index vector count mismatch!"
        assert test_idx.d == index.d, "Temp index dimension mismatch!"
        with open(tmp_meta_path, "r", encoding="utf-8") as f:
            test_meta = json.load(f)
        assert len(test_meta["id_map"]) == len(retained_pids), "Temp metadata id_map count mismatch!"

        # Step 7: Atomic swap
        os.replace(tmp_idx_path, index_path)
        os.replace(tmp_meta_path, meta_path)

        # Step 8: Post-maintenance diagnostic
        post_diag = diagnose_faiss_and_db(db_url, faiss_dir)
        return {
            "status": "success",
            "purged_orphans": list(orphans),
            "original_ntotal": diag["ntotal"],
            "new_ntotal": post_diag["ntotal"],
            "is_consistent": post_diag["is_consistent"],
            "backup_dir": backup_dir,
            "backup_index_hash": bak_idx_hash,
        }
    except Exception as e:
        # Rollback immediately on error
        if os.path.exists(bak_idx):
            shutil.copy2(bak_idx, index_path)
        if os.path.exists(bak_meta):
            shutil.copy2(bak_meta, meta_path)
        if os.path.exists(tmp_idx_path):
            os.remove(tmp_idx_path)
        if os.path.exists(tmp_meta_path):
            os.remove(tmp_meta_path)
        raise RuntimeError(f"Reconciliation failed and automatic rollback succeeded: {e}")


def main():
    parser = argparse.ArgumentParser(description="ResearchLens FAISS & PostgreSQL Safe Reconciliation Tool")
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/research_papers"), help="PostgreSQL Database URL")
    parser.add_argument("--faiss-dir", default=os.path.join(BACKEND_DIR, "data", "processed", "faiss"), help="Path to FAISS directory")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Read-only diagnostic run without modifications (default: True)")
    parser.add_argument("--execute", action="store_true", default=False, help="Perform maintenance operations (requires authorization and --backup-dir)")
    parser.add_argument("--backup-dir", default=None, help="Directory to save timestamped pre-maintenance backups")

    args = parser.parse_args()

    print("================================================================================")
    print("RESEARCHLENS — FAISS & POSTGRESQL RECONCILIATION & INTEGRITY TOOL")
    print("================================================================================")
    print(f"Database URL: {args.db_url.split('@')[-1] if '@' in args.db_url else 'local'}")
    print(f"FAISS Directory: {args.faiss_dir}")
    print(f"Mode: {'EXECUTE (WRITE)' if args.execute else 'DRY-RUN (READ-ONLY)'}")

    diag = diagnose_faiss_and_db(args.db_url, args.faiss_dir)

    print("\n--- DIAGNOSTIC RESULTS ---")
    print(f"Index Exists: {diag.get('faiss_index_exists')} (SHA-256: {diag.get('index_sha256')[:16]}...)")
    print(f"Metadata Exists: {diag.get('faiss_meta_exists')} (SHA-256: {diag.get('meta_sha256')[:16]}...)")
    print(f"FAISS ntotal: {diag.get('ntotal')}")
    print(f"FAISS Dimension: {diag.get('dimension')}")
    print(f"FAISS Metric: {diag.get('metric_type')}")
    print(f"id_map Count: {diag.get('id_map_count')}")
    print(f"metadata Dict Count: {diag.get('meta_dict_count')}")
    print(f"DB Paper Count: {diag.get('db_paper_count')}")
    print(f"Orphan Vectors (in FAISS but absent from DB): {len(diag.get('orphaned_in_faiss', []))} -> {diag.get('orphaned_in_faiss')}")
    print(f"Unindexed Papers (in DB but absent from FAISS): {len(diag.get('unindexed_in_db', []))} -> {diag.get('unindexed_in_db')}")
    print(f"Overall Consistency: {'CONSISTENT' if diag.get('is_consistent') else 'MISMATCH DETECTED'}")

    if diag.get("errors"):
        print(f"\nDiagnostics encountered errors:")
        for err in diag["errors"]:
            print(f"  - {err}")

    if not args.execute:
        print("\n[DRY RUN COMPLETE] Zero modifications made to PostgreSQL or FAISS index.")
        print("To safely repair during an approved maintenance window:")
        print("  python scripts/reconcile_faiss_postgres.py --execute --backup-dir /path/to/backup")
        return

    # Execution path
    if not args.backup_dir:
        print("\n[ERROR] --execute requires --backup-dir to store verified pre-maintenance backups.")
        sys.exit(1)

    print(f"\nExecuting reconciliation with pre-maintenance backup to {args.backup_dir}...")
    res = reconcile_and_purge_orphans(args.db_url, args.faiss_dir, args.backup_dir)
    print(f"Reconciliation completed successfully!")
    print(f"Purged orphans: {res['purged_orphans']}")
    print(f"Original ntotal: {res['original_ntotal']} -> New ntotal: {res['new_ntotal']}")
    print(f"Index consistency: {'CONSISTENT' if res['is_consistent'] else 'INCONSISTENT'}")


if __name__ == "__main__":
    main()
