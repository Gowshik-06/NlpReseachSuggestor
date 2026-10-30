"""
FAISS Vector Index Service for semantic similarity search.
Uses faiss.IndexFlatIP for cosine similarity on L2-normalized embeddings.

Includes safe, atomic re-indexing, recoverable backups, dimension validation,
concurrency protection against concurrent re-indexing, and incremental
database synchronization.
"""
import os
import json
import shutil
import threading
import uuid
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import faiss
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import engine

from app.core.logging import get_logger
from app.services.embedding_service import (
    generate_embedding,
    generate_batch_embeddings,
    EXPECTED_EMBEDDING_DIMENSION
)

logger = get_logger(__name__)

INDEX_DIR = os.environ.get("FAISS_INDEX_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "processed", "faiss")
INDEX_PATH = os.environ.get("FAISS_INDEX_PATH") or os.path.join(INDEX_DIR, "research_index.faiss")
METADATA_PATH = os.environ.get("FAISS_METADATA_PATH") or os.path.join(INDEX_DIR, "papers_meta.json")


def get_backup_paths(index_path: Optional[str] = None, meta_path: Optional[str] = None) -> Tuple[str, str]:
    """
    Resolve backup file paths dynamically paired with the active index and metadata paths.
    Guarantees backups are co-located with their active files and never leak across tests
    or custom index locations.
    """
    idx_p = index_path or globals().get("INDEX_PATH") or os.path.join(INDEX_DIR, "research_index.faiss")
    meta_p = meta_path or globals().get("METADATA_PATH") or os.path.join(INDEX_DIR, "papers_meta.json")

    # If INDEX_PATH_BAK is patched in globals AND its directory matches idx_p's directory, respect it.
    # Otherwise, derive directly from idx_p and meta_p to prevent cross-directory state pollution.
    custom_bak_idx = globals().get("INDEX_PATH_BAK")
    custom_bak_meta = globals().get("METADATA_PATH_BAK")

    if custom_bak_idx and os.path.dirname(os.path.abspath(custom_bak_idx)) == os.path.dirname(os.path.abspath(idx_p)):
        bak_idx = custom_bak_idx
    else:
        bak_idx = f"{idx_p}.bak"

    if custom_bak_meta and os.path.dirname(os.path.abspath(custom_bak_meta)) == os.path.dirname(os.path.abspath(meta_p)):
        bak_meta = custom_bak_meta
    else:
        bak_meta = f"{meta_p}.bak"

    return bak_idx, bak_meta


INDEX_PATH_BAK, METADATA_PATH_BAK = get_backup_paths(INDEX_PATH, METADATA_PATH)

# Thread safety lock for index reads, writes, and reloads
_INDEX_LOCK = threading.RLock()

# Full reindexing concurrency controls
_REINDEX_LOCK = threading.Lock()
REINDEX_ADVISORY_LOCK_KEY = 7376233


class ReindexInProgressError(Exception):
    """Raised when another FAISS vector database re-indexing operation is already executing."""
    pass


class FAISSCorruptedIndexError(RuntimeError):
    """Raised when existing FAISS index files on disk are corrupted/inconsistent and recovery fails, protecting files from silent overwrites."""
    pass


def _acquire_reindex_locks() -> Tuple[bool, Optional[Any]]:
    """
    Acquire both process-level thread lock and cross-process PostgreSQL advisory lock.
    Uses an autocommit connection for the advisory lock so no transaction is held.
    Returns: (acquired: bool, lock_connection: Optional[Connection])
    """
    if not _REINDEX_LOCK.acquire(blocking=False):
        return False, None

    conn = None
    try:
        if engine.dialect.name == "postgresql":
            conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
            acquired = conn.execute(
                text("SELECT pg_try_advisory_lock(:key)"),
                {"key": REINDEX_ADVISORY_LOCK_KEY}
            ).scalar()
            if not acquired:
                conn.close()
                _REINDEX_LOCK.release()
                return False, None
        return True, conn
    except Exception as e:
        logger.error("Failed to acquire PostgreSQL advisory lock for reindex: %s", e)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        _REINDEX_LOCK.release()
        return False, None


def _release_reindex_locks(conn: Optional[Any]) -> None:
    """Release PostgreSQL advisory lock and process-level thread lock."""
    if conn is not None:
        try:
            conn.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": REINDEX_ADVISORY_LOCK_KEY}
            )
            conn.close()
        except Exception as e:
            logger.error("Error releasing PostgreSQL advisory lock for reindex: %s", e)
    if _REINDEX_LOCK.locked():
        try:
            _REINDEX_LOCK.release()
        except RuntimeError:
            pass



def validate_embeddings(
    embeddings: Any,
    expected_dimension: Optional[int] = None
) -> np.ndarray:
    """
    Validate embedding array before insertion or indexing in FAISS.
    Requirements:
    - Must be a numpy array or convertible to one.
    - Must have numeric dtype.
    - Must be 2-dimensional (shape: [N, D]).
    - Must not be empty (N > 0 and D > 0).
    - If expected_dimension is specified, D must match expected_dimension.
    - Must not contain NaN (Not a Number) values.
    - Must not contain infinite values (positive or negative infinity).
    Returns the validated, float32 contiguous numpy array.
    Raises ValueError or TypeError on validation failure.
    """
    if embeddings is None:
        raise ValueError("Embeddings array cannot be None.")

    if not isinstance(embeddings, np.ndarray):
        try:
            embeddings = np.asarray(embeddings, dtype=np.float32)
        except Exception as e:
            raise TypeError(f"Invalid embedding format: unable to convert to numpy array ({e}).")

    if not np.issubdtype(embeddings.dtype, np.number):
        raise TypeError(f"Embeddings must be numeric, got dtype {embeddings.dtype}.")

    if embeddings.ndim != 2:
        raise ValueError(
            f"Invalid embedding dimensions: expected 2D array (samples, dimension), "
            f"got {embeddings.ndim}D array with shape {embeddings.shape}."
        )

    n_samples, dim = embeddings.shape
    if n_samples == 0 or dim == 0:
        raise ValueError(f"Empty embedding array: shape is {embeddings.shape}.")

    if expected_dimension is not None and dim != expected_dimension:
        raise ValueError(
            f"Vector dimension mismatch: expected {expected_dimension}, got {dim}. "
            "Cannot mix embeddings from different models."
        )

    if np.isnan(embeddings).any():
        raise ValueError("Embeddings contain NaN (Not a Number) values. Vectors must be finite.")

    if np.isinf(embeddings).any():
        raise ValueError("Embeddings contain infinite (Inf/-Inf) values. Vectors must be finite.")

    if embeddings.dtype != np.float32:
        embeddings = embeddings.astype(np.float32)

    return np.ascontiguousarray(embeddings)


def validate_index_pair_files(
    index_file: str,
    meta_file: str,
    expected_dim: Optional[int] = None
) -> Tuple[bool, str, Optional[faiss.IndexFlatIP], Optional[List[str]], Optional[Dict[str, Any]]]:
    """
    Validate that an on-disk FAISS index and metadata JSON file pair is mutually consistent.
    Checks:
    1. Both files exist and are non-empty.
    2. FAISS index file is readable.
    3. Metadata JSON is parseable with valid 'id_map' and 'metadata'.
    4. Index vector count equals ID map length.
    5. ID map length equals metadata dictionary length.
    6. All entries in ID map exist in metadata dictionary.
    7. No duplicate IDs exist in ID map.
    8. Index dimensionality matches expected dimension (if specified).
    Returns: (is_valid, reason, index_obj, id_map, metadata_dict)
    """
    if not os.path.exists(index_file):
        return False, f"Index file does not exist: {index_file}", None, None, None
    if not os.path.exists(meta_file):
        return False, f"Metadata file does not exist: {meta_file}", None, None, None

    try:
        if os.path.getsize(index_file) == 0:
            return False, f"Index file is empty (0 bytes): {index_file}", None, None, None
        if os.path.getsize(meta_file) == 0:
            return False, f"Metadata file is empty (0 bytes): {meta_file}", None, None, None
    except OSError as e:
        return False, f"Error inspecting file size: {e}", None, None, None

    try:
        idx = faiss.read_index(index_file)
    except Exception as e:
        return False, f"Corrupted or unreadable FAISS index file: {e}", None, None, None

    try:
        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, f"Corrupted or invalid JSON metadata file: {e}", None, None, None

    if not isinstance(data, dict):
        return False, "Metadata root is not a JSON object", None, None, None

    id_map = data.get("id_map")
    meta_dict = data.get("metadata")

    if not isinstance(id_map, list):
        return False, "Metadata 'id_map' is not a list", None, None, None
    if not isinstance(meta_dict, dict):
        return False, "Metadata 'metadata' is not a dictionary", None, None, None

    if idx.ntotal != len(id_map):
        return False, f"Vector count mismatch: index.ntotal={idx.ntotal} vs id_map={len(id_map)}", None, None, None

    if len(id_map) != len(meta_dict):
        return False, f"ID map count mismatch: id_map={len(id_map)} vs metadata={len(meta_dict)}", None, None, None

    if len(set(id_map)) != len(id_map):
        return False, "Duplicate paper IDs detected in id_map", None, None, None

    missing_in_meta = [pid for pid in id_map if pid not in meta_dict]
    if missing_in_meta:
        return False, f"{len(missing_in_meta)} IDs in id_map not found in metadata dictionary", None, None, None

    if expected_dim is not None and idx.d != expected_dim:
        return False, f"Dimension mismatch: index.d={idx.d} != expected={expected_dim}", None, None, None

    return True, "Consistent", idx, id_map, meta_dict


class FAISSVectorIndex:
    def __init__(self, dimension: int = 768, raise_on_degraded: bool = False):
        self.dimension = dimension
        self.index: Optional[faiss.IndexFlatIP] = None
        self.paper_id_map: List[str] = []  # Maps FAISS index position i to paper_id
        self.paper_metadata: Dict[str, Dict[str, Any]] = {}
        self.is_degraded: bool = False
        self.degradation_reason: Optional[str] = None
        self.raise_on_degraded: bool = raise_on_degraded
        os.makedirs(INDEX_DIR, exist_ok=True)
        self._load_or_initialize()

    def _load_or_initialize(self):
        """
        Load index from disk if present and consistent, else attempt backup recovery.
        If files exist on disk but both active pair and backup pair are corrupted,
        enters DEGRADED state and blocks vector writes to prevent silent data destruction.
        """
        with _INDEX_LOCK:
            bak_idx, bak_meta = get_backup_paths(INDEX_PATH, METADATA_PATH)
            active_exists = os.path.exists(INDEX_PATH) or os.path.exists(METADATA_PATH)
            backup_exists = os.path.exists(bak_idx) or os.path.exists(bak_meta)

            # 1. Check active pair
            if os.path.exists(INDEX_PATH) and os.path.exists(METADATA_PATH):
                is_valid, reason, loaded_index, loaded_map, loaded_meta = validate_index_pair_files(
                    INDEX_PATH, METADATA_PATH, expected_dim=self.dimension
                )
                if is_valid:
                    self.index = loaded_index
                    self.paper_id_map = loaded_map
                    self.paper_metadata = loaded_meta
                    self.dimension = self.index.d
                    self.is_degraded = False
                    self.degradation_reason = None
                    logger.info("Loaded FAISS index from %s with %d entries (dimension=%d)", INDEX_PATH, self.index.ntotal, self.dimension)
                    return
                else:
                    logger.warning(
                        "Active FAISS index/metadata files on disk are inconsistent (%s). Checking backup recovery...",
                        reason
                    )
            elif active_exists:
                reason = "Partial active pair on disk (one file missing)"
                logger.warning("%s. Checking backup recovery...", reason)
            else:
                reason = None

            # 2. If active pair is missing or inconsistent, attempt recovery from backups if available
            if os.path.exists(bak_idx) and os.path.exists(bak_meta):
                bak_valid, bak_reason, bak_index, bak_map, bak_meta_data = validate_index_pair_files(
                    bak_idx, bak_meta, expected_dim=self.dimension
                )
                if bak_valid:
                    logger.info("Recovering consistent FAISS index from backup files (%d entries)...", bak_index.ntotal)
                    try:
                        shutil.copy2(bak_idx, INDEX_PATH)
                        shutil.copy2(bak_meta, METADATA_PATH)
                        self.index = bak_index
                        self.paper_id_map = bak_map
                        self.paper_metadata = bak_meta_data
                        self.dimension = self.index.d
                        self.is_degraded = False
                        self.degradation_reason = None
                        return
                    except Exception as e:
                        logger.error("Failed to restore FAISS index from backup files: %s", e)
                        bak_reason = f"Backup restoration error: {e}"
                else:
                    logger.warning("Backup FAISS files are also invalid or inconsistent: %s", bak_reason)
            else:
                bak_reason = "No backup files available"

            # 3. Check if this is a genuine first run (neither active nor backup files exist)
            if not active_exists and not backup_exists:
                logger.info("Initializing fresh empty FAISS index (dimension=%d) on first run", self.dimension)
                self.index = faiss.IndexFlatIP(self.dimension)
                self.paper_id_map = []
                self.paper_metadata = {}
                self.is_degraded = False
                self.degradation_reason = None
                return

            # 4. Existing data was corrupted and recovery failed: Enter DEGRADED state
            failure_detail = f"Active index corrupted ({reason or 'unreadable'}) and recovery failed ({bak_reason})."
            self.is_degraded = True
            self.degradation_reason = failure_detail
            self.index = faiss.IndexFlatIP(self.dimension)
            self.paper_id_map = []
            self.paper_metadata = {}
            logger.critical(
                "FAISS vector index entering DEGRADED state: %s. Writes are blocked to protect corrupted disk artifacts.",
                failure_detail
            )
            if self.raise_on_degraded:
                raise FAISSCorruptedIndexError(failure_detail)

    def save(self):
        """Persist FAISS index and metadata mapping to disk using atomic rename with unique staging files."""
        with _INDEX_LOCK:
            if self.is_degraded:
                raise FAISSCorruptedIndexError(
                    f"Blocked save on degraded FAISS index: {self.degradation_reason}. "
                    "Cannot overwrite damaged on-disk artifacts without explicit administrative recovery."
                )
            if self.index is None:
                return

            bak_idx, bak_meta = get_backup_paths(INDEX_PATH, METADATA_PATH)
            unique_tag = uuid.uuid4().hex[:8]
            tmp_index_path = f"{INDEX_PATH}.tmp.{unique_tag}"
            tmp_meta_path = f"{METADATA_PATH}.tmp.{unique_tag}"
            index_replaced = False

            try:
                faiss.write_index(self.index, tmp_index_path)
                with open(tmp_meta_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "id_map": self.paper_id_map,
                        "metadata": self.paper_metadata
                    }, f, indent=2)

                # Validate staged files before replacement
                is_staged_valid, staged_reason, _, _, _ = validate_index_pair_files(
                    tmp_index_path, tmp_meta_path, expected_dim=self.dimension
                )
                if not is_staged_valid:
                    raise AssertionError(f"Staged index files failed integrity validation: {staged_reason}")

                # Create backup of current active files if both exist and are consistent
                if os.path.exists(INDEX_PATH) and os.path.exists(METADATA_PATH):
                    is_cur_valid, _, _, _, _ = validate_index_pair_files(INDEX_PATH, METADATA_PATH)
                    if is_cur_valid:
                        shutil.copy2(INDEX_PATH, bak_idx)
                        shutil.copy2(METADATA_PATH, bak_meta)

                # Two-step replacement
                os.replace(tmp_index_path, INDEX_PATH)
                index_replaced = True
                os.replace(tmp_meta_path, METADATA_PATH)
                logger.info("Atomically saved FAISS index with %d items to %s", self.index.ntotal, INDEX_PATH)
            except Exception as e:
                logger.error("Failed to atomically save FAISS index: %s", e)
                if index_replaced and os.path.exists(bak_idx):
                    try:
                        shutil.copy2(bak_idx, INDEX_PATH)
                        logger.warning("Restored INDEX_PATH from backup following save failure.")
                    except Exception as rb_err:
                        logger.error("Failed to restore INDEX_PATH from backup: %s", rb_err)
                for tmp_f in [tmp_index_path, tmp_meta_path, f"{INDEX_PATH}.tmp", f"{METADATA_PATH}.tmp"]:
                    if os.path.exists(tmp_f):
                        try:
                            os.remove(tmp_f)
                        except OSError:
                            pass
                raise

    def add_papers(self, papers: List[Dict[str, Any]]):
        """
        Compute embeddings and add papers to FAISS index.
        Validates dimensions, non-finiteness (NaN/Inf), and numeric suitability.
        """
        if not papers:
            return

        with _INDEX_LOCK:
            if self.is_degraded:
                raise FAISSCorruptedIndexError(
                    f"Blocked add_papers on degraded FAISS index: {self.degradation_reason}."
                )
            texts = []
            new_papers = []
            for p in papers:
                pid = p.get("paper_id")
                if pid and pid not in self.paper_metadata:
                    title = p.get("title", "")
                    abstract = p.get("abstract", "") or ""
                    text = f"{title}. {abstract}".strip()
                    if len(text) >= 5:
                        texts.append(text)
                        new_papers.append(p)

            if not texts:
                return

            embeddings = generate_batch_embeddings(texts)
            embeddings = validate_embeddings(embeddings, expected_dimension=self.dimension)

            if self.index is None:
                self.index = faiss.IndexFlatIP(self.dimension)

            self.index.add(embeddings)
            for p in new_papers:
                pid = p.get("paper_id")
                self.paper_id_map.append(pid)
                self.paper_metadata[pid] = p

            self.save()

    def search(self, query_text: str, top_k: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        """
        Query the FAISS index with semantic vector.
        Protected by concurrency lock to prevent reading half-written indices.
        Returns list of (paper_metadata, cosine_similarity_score).
        Raises ValueError if query vector dimension does not match index dimension.
        """
        with _INDEX_LOCK:
            if self.is_degraded:
                logger.warning(
                    "FAISS vector index is in DEGRADED state: %s. Returning empty search results.",
                    self.degradation_reason
                )
                return []
            if self.index is None:
                self._load_or_initialize()
            if self.is_degraded or self.index is None:
                return []

            query_vec = generate_embedding(query_text).reshape(1, -1)
            if query_vec.shape[1] != self.index.d:
                logger.error("Vector dimension mismatch: query=%d, index=%d", query_vec.shape[1], self.index.d)
                raise ValueError(
                    f"Vector dimension mismatch: query vector dimension {query_vec.shape[1]} "
                    f"does not match index dimension {self.index.d}. Cannot search incompatible embedding spaces."
                )

            if self.index.ntotal == 0:
                return []

            k = min(top_k, self.index.ntotal)
            scores, indices = self.index.search(query_vec, k)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if 0 <= idx < len(self.paper_id_map):
                    pid = self.paper_id_map[idx]
                    meta = self.paper_metadata.get(pid, {})
                    results.append((meta, float(score)))

            return results


# Global singleton instance
_FAISS_INDEX_INSTANCE = None


def get_faiss_index() -> FAISSVectorIndex:
    global _FAISS_INDEX_INSTANCE
    with _INDEX_LOCK:
        if _FAISS_INDEX_INSTANCE is None:
            _FAISS_INDEX_INSTANCE = FAISSVectorIndex()
        return _FAISS_INDEX_INSTANCE


def reset_faiss_index_instance() -> None:
    """Reset global FAISS instance, allowing re-initialization with active paths."""
    global _FAISS_INDEX_INSTANCE
    with _INDEX_LOCK:
        _FAISS_INDEX_INSTANCE = None


def sync_unindexed_papers(session: Session, paper_ids: Optional[List[str]] = None) -> int:
    """
    Synchronize unindexed database papers into the FAISS vector index.
    
    - Idempotent: checks whether paper_id is already in faiss_index.paper_metadata.
    - Safe: only operates on committed records in PostgreSQL.
    - Durable: can be called post-commit by DRIUT or on startup/scheduler recovery.
    - Atomically persists the updated FAISS index upon completion.
    
    Returns count of newly indexed papers.
    """
    from app.models.paper import Paper

    faiss_idx = get_faiss_index()
    with _INDEX_LOCK:
        indexed_pids = set(faiss_idx.paper_metadata.keys())

    query = session.query(Paper)
    if paper_ids:
        query = query.filter(Paper.paper_id.in_(paper_ids))

    db_papers = query.all()
    eligible_to_add = []

    for p in db_papers:
        pid = (p.paper_id or "").strip()
        if not pid or pid in indexed_pids:
            continue
        title = (p.title or "").strip()
        abstract = (p.abstract or "").strip()
        text = f"{title}. {abstract}".strip()
        if len(text) < 5:
            continue

        eligible_to_add.append({
            "paper_id": pid,
            "title": title,
            "abstract": abstract,
            "authors": p.authors or [],
            "venue": p.venue or "",
            "year": p.year,
            "doi": p.doi,
            "url": p.url,
            "pdf_url": p.pdf_url,
            "source": p.source or "local",
            "citation_count": p.citation_count or 0,
            "categories": p.categories or []
        })

    if not eligible_to_add:
        return 0

    faiss_idx.add_papers(eligible_to_add)
    logger.info("Successfully synchronized %d unindexed papers into FAISS index.", len(eligible_to_add))
    return len(eligible_to_add)


def get_index_consistency_status(session: Session) -> Dict[str, Any]:
    """
    Evaluate synchronization between PostgreSQL paper database and FAISS vector index.
    Returns audit statistics without modifying records.
    """
    from app.models.paper import Paper

    faiss_idx = get_faiss_index()
    with _INDEX_LOCK:
        vector_count = faiss_idx.index.ntotal if faiss_idx.index else 0
        id_map_count = len(faiss_idx.paper_id_map)
        meta_count = len(faiss_idx.paper_metadata)
        indexed_pids = set(faiss_idx.paper_id_map)

    db_papers = session.query(Paper.paper_id).all()
    total_db_papers = len(db_papers)
    valid_db_pids = set(p[0] for p in db_papers if p[0])

    missing_in_faiss = list(valid_db_pids - indexed_pids)
    orphaned_in_faiss = list(indexed_pids - valid_db_pids)

    pair_consistent = (vector_count == id_map_count == meta_count)

    bak_idx, bak_meta = get_backup_paths(INDEX_PATH, METADATA_PATH)
    is_degraded = getattr(faiss_idx, "is_degraded", False)
    deg_reason = getattr(faiss_idx, "degradation_reason", None)

    return {
        "is_consistent": (
            not is_degraded
            and len(missing_in_faiss) == 0
            and len(orphaned_in_faiss) == 0
            and vector_count == total_db_papers
            and pair_consistent
        ),
        "is_degraded": is_degraded,
        "degradation_reason": deg_reason,
        "total_db_papers": total_db_papers,
        "faiss_vector_count": vector_count,
        "faiss_id_map_count": id_map_count,
        "faiss_metadata_count": meta_count,
        "dimension": faiss_idx.dimension,
        "missing_vectors_count": len(missing_in_faiss),
        "orphaned_metadata_count": len(orphaned_in_faiss),
        "has_backup_index": os.path.exists(bak_idx),
        "has_backup_metadata": os.path.exists(bak_meta),
        "backup_index_path": bak_idx,
        "backup_metadata_path": bak_meta,
        "index_path": INDEX_PATH,
        "metadata_path": METADATA_PATH
    }


def reindex_vector_database(session: Session, force: bool = False) -> Dict[str, Any]:
    """
    Administrative safe re-indexing workflow:
    1. Acquires operation-level guard (thread lock & PostgreSQL advisory lock).
    2. Extracts all candidate papers from PostgreSQL into memory (no long open transaction).
    3. Filters eligible papers (valid non-empty paper_id, non-empty substantive text, deduplicated).
    4. Builds replacement FAISS index and metadata in isolated unique temporary files.
    5. Validates vector count, dimensions, ID mapping, and file readability before activation.
    6. Preserves existing index and metadata in recoverable (.bak) copies.
    7. Atomically activates replacement via os.replace under concurrency lock.
    8. Guarantees that failure at any stage leaves the existing active index 100% intact.
    9. Records complete audit summary of processed, indexed, skipped, and failed records.
    """
    from app.models.paper import Paper

    acquired, lock_conn = _acquire_reindex_locks()
    if not acquired:
        logger.warning("Rejecting re-indexing request: another re-indexing operation is in progress.")
        raise ReindexInProgressError(
            "A vector database re-indexing operation is already in progress. Please wait for it to complete."
        )

    logger.info("Starting safe FAISS re-indexing procedure (force=%s)...", force)
    
    unique_tag = uuid.uuid4().hex[:8]
    tmp_index_path = f"{INDEX_PATH}.tmp.{unique_tag}"
    tmp_meta_path = f"{METADATA_PATH}.tmp.{unique_tag}"

    try:
        all_papers = session.query(Paper).all()
        total_db_records = len(all_papers)

        eligible_papers: List[Dict[str, Any]] = []
        eligible_texts: List[str] = []
        seen_pids = set()
        skipped_items: List[Dict[str, str]] = []

        for p in all_papers:
            pid = (p.paper_id or "").strip()
            if not pid:
                skipped_items.append({"id": str(p.id), "paper_id": "", "reason": "missing_paper_id"})
                continue

            if pid in seen_pids:
                skipped_items.append({"id": str(p.id), "paper_id": pid, "reason": "duplicate_paper_id"})
                continue

            title = (p.title or "").strip()
            abstract = (p.abstract or "").strip()
            text = f"{title}. {abstract}".strip()

            if len(text) < 5:
                skipped_items.append({"id": str(p.id), "paper_id": pid, "reason": "insufficient_text"})
                continue

            seen_pids.add(pid)
            eligible_papers.append({
                "paper_id": pid,
                "title": title,
                "abstract": abstract,
                "authors": p.authors or [],
                "venue": p.venue or "",
                "year": p.year,
                "doi": p.doi,
                "url": p.url,
                "pdf_url": p.pdf_url,
                "source": p.source or "local",
                "citation_count": p.citation_count or 0,
                "categories": p.categories or []
            })
            eligible_texts.append(text)

        if not eligible_papers:
            logger.warning("Safe FAISS re-indexing aborted: No eligible papers found in database.")
            return {
                "status": "skipped",
                "reason": "No eligible paper records found in database.",
                "total_db_records": total_db_records,
                "indexed_count": 0,
                "skipped_count": len(skipped_items),
                "skipped_details": skipped_items
            }

        # Step 1: Batch generate embeddings in chunks to avoid memory bottlenecks
        batch_size = 32
        all_embeddings_list = []
        for i in range(0, len(eligible_texts), batch_size):
            chunk = eligible_texts[i:i + batch_size]
            emb_chunk = generate_batch_embeddings(chunk)
            all_embeddings_list.append(emb_chunk)

        embeddings = np.vstack(all_embeddings_list)
        configured_dim = EXPECTED_EMBEDDING_DIMENSION
        embeddings = validate_embeddings(embeddings, expected_dimension=configured_dim)
        vector_count, actual_dimension = embeddings.shape

        # Step 2: Build new isolated FAISS index in memory
        new_index = faiss.IndexFlatIP(configured_dim)
        new_index.add(embeddings)

        new_id_map = [p["paper_id"] for p in eligible_papers]
        new_metadata = {p["paper_id"]: p for p in eligible_papers}

        # Step 3: Validate in-memory structures
        if new_index.ntotal != len(new_id_map):
            raise AssertionError(f"Index vector count ({new_index.ntotal}) != ID map count ({len(new_id_map)})")
        if len(new_id_map) != len(new_metadata):
            raise AssertionError(f"ID map count ({len(new_id_map)}) != metadata count ({len(new_metadata)})")

        # Step 4: Write to isolated temporary files
        faiss.write_index(new_index, tmp_index_path)
        with open(tmp_meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "id_map": new_id_map,
                "metadata": new_metadata
            }, f, indent=2)

        # Step 5: Validate written temporary files by reading them back
        is_tmp_valid, tmp_reason, verify_idx, _, _ = validate_index_pair_files(
            tmp_index_path, tmp_meta_path, expected_dim=configured_dim
        )
        if not is_tmp_valid:
            raise AssertionError(f"Verification of temporary index/metadata files failed: {tmp_reason}")

        # Step 6: Create recoverable backups of current active files if both exist
        bak_idx, bak_meta = get_backup_paths(INDEX_PATH, METADATA_PATH)
        if os.path.exists(INDEX_PATH) and os.path.exists(METADATA_PATH):
            shutil.copy2(INDEX_PATH, bak_idx)
            shutil.copy2(METADATA_PATH, bak_meta)

        # Step 7: Atomic replacement and hot reload under global lock
        index_replaced = False
        with _INDEX_LOCK:
            try:
                os.replace(tmp_index_path, INDEX_PATH)
                index_replaced = True
                os.replace(tmp_meta_path, METADATA_PATH)

                active_singleton = get_faiss_index()
                active_singleton.index = new_index
                active_singleton.paper_id_map = new_id_map
                active_singleton.paper_metadata = new_metadata
                active_singleton.dimension = configured_dim
                active_singleton.is_degraded = False
                active_singleton.degradation_reason = None
            except Exception as publish_err:
                logger.error("Error during index/metadata replacement: %s", publish_err)
                if index_replaced and os.path.exists(bak_idx):
                    try:
                        shutil.copy2(bak_idx, INDEX_PATH)
                        logger.warning("Restored active FAISS index from backup after partial replacement failure.")
                    except Exception as rb_err:
                        logger.error("Failed to restore INDEX_PATH from backup: %s", rb_err)
                raise publish_err

        logger.info(
            "Safe FAISS re-indexing completed successfully: %d vectors indexed (skipped: %d).",
            len(new_id_map), len(skipped_items)
        )

        return {
            "status": "success",
            "message": f"Successfully re-indexed {len(new_id_map)} papers into FAISS vector database.",
            "total_db_records": total_db_records,
            "indexed_count": len(new_id_map),
            "skipped_count": len(skipped_items),
            "failed_count": 0,
            "dimension": configured_dim,
            "backup_created": os.path.exists(bak_idx),
            "atomic_activation": True,
            "skipped_details": skipped_items
        }

    except Exception as exc:
        logger.error("Safe FAISS re-indexing aborted due to error: %s. Active index preserved.", exc, exc_info=True)
        # Clean up temporary files on failure so active index remains untouched
        for tmp_f in [tmp_index_path, tmp_meta_path, f"{INDEX_PATH}.tmp", f"{METADATA_PATH}.tmp"]:
            if os.path.exists(tmp_f):
                try:
                    os.remove(tmp_f)
                except OSError:
                    pass

        return {
            "status": "failed",
            "error": str(exc),
            "active_index_preserved": True,
            "total_db_records": total_db_records if 'total_db_records' in locals() else 0,
            "indexed_count": 0,
            "skipped_count": len(skipped_items) if 'skipped_items' in locals() else 0,
            "failed_count": len(eligible_papers) if 'eligible_papers' in locals() else 0
        }
    finally:
        _release_reindex_locks(lock_conn)


def reset_degraded_index(force: bool = False) -> bool:
    """
    Explicit administrative recovery/reset for a degraded FAISS index.
    Requires force=True to re-initialize a fresh empty index and clear the degraded state.
    """
    if not force:
        raise ValueError("force=True is required to reset a degraded FAISS index.")
    idx = get_faiss_index()
    with _INDEX_LOCK:
        idx.index = faiss.IndexFlatIP(idx.dimension)
        idx.paper_id_map = []
        idx.paper_metadata = {}
        idx.is_degraded = False
        idx.degradation_reason = None
        logger.warning("FAISS vector index explicitly reset from degraded state by administrator (force=True).")
        return True
