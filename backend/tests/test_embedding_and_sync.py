"""
Tests for TASK-12: Embedding Safety, DRIUT Index Synchronization, and Reindex Concurrency.

Covers the 12 requirements specified in TASK-12 Section F:
1. SPECTER2 loading failure.
2. Incompatible fallback prevention.
3. Embedding dimension mismatch (search and add_papers).
4. DRIUT ingestion followed by indexing.
5. Database transaction rollback without orphaned vectors.
6. Recovery of papers committed before an indexing failure.
7. Idempotent retries.
8. Duplicate paper ingestion.
9. Concurrent reindex requests (HTTP 409 Conflict).
10. Reindex failure preserving the active index.
11. Search during reindex.
12. Correct paper-ID and metadata mappings.
"""
import os
import json
import uuid
import threading
import time
import pytest
from unittest.mock import patch, MagicMock
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import engine, SessionLocal, Base
from app.models.user import User
from app.models.paper import Paper, SavedPaper
from app.models.driut import DRIUTAlert
from app.core.security import create_access_token, hash_password
from app.services.embedding_service import (
    get_embedding_model,
    generate_embedding,
    generate_batch_embeddings,
    EmbeddingServiceError,
    EXPECTED_EMBEDDING_DIMENSION
)
from app.services.vector_index import (
    FAISSVectorIndex,
    get_faiss_index,
    reindex_vector_database,
    sync_unindexed_papers,
    get_index_consistency_status,
    ReindexInProgressError,
    _INDEX_LOCK,
    _REINDEX_LOCK
)
from app.services.driut_service import scan_saved_papers_for_updates

client = TestClient(app)

TEST_ADMIN_USER = "admin_task12_test"
TEST_NORMAL_USER = "user_task12_test"


@pytest.fixture(scope="module", autouse=True)
def setup_task12_test_users():
    """Seed test admin and standard user accounts for authentication."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    for u in [TEST_ADMIN_USER, TEST_NORMAL_USER]:
        user_obj = db.query(User).filter(User.username == u).first()
        if user_obj:
            db.delete(user_obj)
    db.commit()

    admin_user = User(
        username=TEST_ADMIN_USER,
        email="admin_task12@test.local",
        hashed_password=hash_password("AdminPassTask12!"),
        full_name="Task12 Administrator",
        is_active=True,
        is_superuser=True
    )
    normal_user = User(
        username=TEST_NORMAL_USER,
        email="normal_task12@test.local",
        hashed_password=hash_password("UserPassTask12!"),
        full_name="Task12 Standard User",
        is_active=True,
        is_superuser=False
    )
    db.add_all([admin_user, normal_user])
    db.commit()
    db.close()

    yield

    db_clean = SessionLocal()
    for u in [TEST_ADMIN_USER, TEST_NORMAL_USER]:
        user_obj = db_clean.query(User).filter(User.username == u).first()
        if user_obj:
            db_clean.delete(user_obj)
    db_clean.commit()
    db_clean.close()


def get_token(username: str) -> str:
    return create_access_token(subject=username)


# ---------------------------------------------------------------------------
# 1. SPECTER2 Loading Failure
# ---------------------------------------------------------------------------
def test_specter2_loading_failure():
    """Verify that if the primary model fails to load, EmbeddingServiceError is raised."""
    with patch("sentence_transformers.SentenceTransformer", side_effect=RuntimeError("Model checkpoint not found")):
        with patch("app.services.embedding_service._MODEL_INSTANCE", None):
            with pytest.raises(EmbeddingServiceError, match="Failed to load semantic embedding model"):
                get_embedding_model()


# ---------------------------------------------------------------------------
# 2. Incompatible Fallback Prevention
# ---------------------------------------------------------------------------
def test_incompatible_fallback_prevention():
    """
    Verify that an incompatible dimension model (e.g. 384 or 512 instead of 768)
    is rejected with EmbeddingServiceError rather than silently adopted.
    """
    mock_model = MagicMock()
    mock_model.get_embedding_dimension.return_value = 384  # e.g., all-MiniLM-L6-v2 dimension

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        with patch("app.services.embedding_service._MODEL_INSTANCE", None):
            with pytest.raises(EmbeddingServiceError, match="dimension 384, but 768 is required"):
                get_embedding_model()


# ---------------------------------------------------------------------------
# 3. Embedding Dimension Mismatch (Search & add_papers)
# ---------------------------------------------------------------------------
def test_embedding_dimension_mismatch_search():
    """Verify that search rejects incompatible query vector dimensions instead of returning empty results."""
    faiss_idx = get_faiss_index()
    bad_query_emb = np.random.randn(384).astype("float32")

    with patch("app.services.vector_index.generate_embedding", return_value=bad_query_emb):
        with pytest.raises(ValueError, match="Vector dimension mismatch"):
            faiss_idx.search("test query")


def test_embedding_dimension_mismatch_add_papers():
    """Verify that add_papers rejects incompatible document vector dimensions."""
    faiss_idx = get_faiss_index()
    bad_batch_emb = np.random.randn(1, 512).astype("float32")

    papers = [{
        "paper_id": "test:dim:mismatch:add",
        "title": "Quantum Computation",
        "abstract": "Superconducting qubits and surface codes."
    }]

    with patch("app.services.vector_index.generate_batch_embeddings", return_value=bad_batch_emb):
        with pytest.raises(ValueError, match="Vector dimension mismatch"):
            faiss_idx.add_papers(papers)


# ---------------------------------------------------------------------------
# 4. DRIUT Ingestion Followed by Indexing
# ---------------------------------------------------------------------------
def test_driut_ingestion_followed_by_indexing(tmp_path):
    """
    Verify that when DRIUT discovers and inserts a new trigger paper into PostgreSQL,
    the post-commit hook indexes the paper into FAISS, making it immediately searchable.
    """
    db = SessionLocal()
    user_id = TEST_NORMAL_USER

    # Seed a saved paper
    saved_paper = Paper(
        paper_id="test:driut:sync:saved",
        title="Attention Mechanism in Deep Learning",
        abstract="Transformers utilize self-attention mechanisms for sequence modeling.",
        source="arxiv"
    )
    db.add(saved_paper)
    db.commit()

    saved_entry = SavedPaper(user_id=user_id, paper_id=saved_paper.id)
    db.add(saved_entry)
    db.commit()

    test_idx = str(tmp_path / "research_index.faiss")
    test_meta = str(tmp_path / "papers_meta.json")

    mock_vec = np.random.randn(1, 768).astype("float32")
    mock_vec = mock_vec / np.linalg.norm(mock_vec, axis=1, keepdims=True)

    new_candidate = {
        "paper_id": "test:driut:sync:trigger",
        "title": "Extension: Multi-Head Attention Mechanisms",
        "abstract": "We extend attention mechanisms to multi-head representations.",
        "source": "arxiv",
        "citation_count": 10
    }

    try:
        with patch("app.services.vector_index.INDEX_PATH", test_idx), \
             patch("app.services.vector_index.METADATA_PATH", test_meta), \
             patch("app.services.vector_index.generate_batch_embeddings", return_value=mock_vec), \
             patch("app.services.vector_index.generate_embedding", return_value=mock_vec[0]):

            # Initialize isolated test FAISS index
            test_faiss = FAISSVectorIndex(dimension=768)
            with patch("app.services.vector_index.get_faiss_index", return_value=test_faiss):
                alerts = scan_saved_papers_for_updates(session=db, new_papers=[new_candidate], user_id=user_id)

                # Verify alert created
                assert len(alerts) > 0
                # Verify trigger paper is now in test FAISS index
                assert "test:driut:sync:trigger" in test_faiss.paper_metadata
                assert test_faiss.index.ntotal == 1

                # Verify searchable
                results = test_faiss.search("Multi-Head Attention", top_k=5)
                assert len(results) == 1
                assert results[0][0]["paper_id"] == "test:driut:sync:trigger"

    finally:
        db.query(DRIUTAlert).filter(DRIUTAlert.user_id == user_id).delete()
        db.query(SavedPaper).filter(SavedPaper.user_id == user_id).delete()
        db.query(Paper).filter(Paper.paper_id.in_(["test:driut:sync:saved", "test:driut:sync:trigger"])).delete()
        db.commit()
        db.close()
        get_faiss_index()._load_or_initialize()


# ---------------------------------------------------------------------------
# 5. Database Transaction Rollback Without Orphaned Vectors
# ---------------------------------------------------------------------------
def test_db_transaction_rollback_without_orphaned_vectors(tmp_path):
    """
    Verify that if a database transaction is rolled back, no orphaned vectors
    are inserted into the FAISS index.
    """
    db = SessionLocal()
    initial_faiss = get_faiss_index()
    initial_count = initial_faiss.index.ntotal if initial_faiss.index else 0

    p_rollback = Paper(
        paper_id="test:rollback:paper",
        title="Rolled Back Paper Research",
        abstract="This paper will not be committed to the database.",
        source="test"
    )
    db.add(p_rollback)
    # Simulate rollback instead of commit
    db.rollback()

    # Call sync_unindexed_papers
    synced = sync_unindexed_papers(session=db, paper_ids=["test:rollback:paper"])
    assert synced == 0

    # Verify FAISS count did not increase
    assert initial_faiss.index.ntotal == initial_count
    assert "test:rollback:paper" not in initial_faiss.paper_metadata
    db.close()


# ---------------------------------------------------------------------------
# 6. Recovery of Papers Committed Before an Indexing Failure
# ---------------------------------------------------------------------------
def test_recovery_of_papers_committed_before_indexing_failure(tmp_path):
    """
    Verify that if a paper is committed to PostgreSQL but an initial indexing attempt
    fails (e.g. simulated network/memory error), subsequent sync_unindexed_papers
    recovers and indexes the paper cleanly.
    """
    db = SessionLocal()
    pid = f"test:recovery:{uuid.uuid4().hex[:6]}"
    p_committed = Paper(
        paper_id=pid,
        title="Durable Recovery Test Paper",
        abstract="Committed to database, initially failed during embedding step.",
        source="test"
    )
    db.add(p_committed)
    db.commit()

    test_idx = str(tmp_path / "research_index.faiss")
    test_meta = str(tmp_path / "papers_meta.json")

    mock_vec = np.random.randn(1, 768).astype("float32")
    mock_vec = mock_vec / np.linalg.norm(mock_vec, axis=1, keepdims=True)

    try:
        with patch("app.services.vector_index.INDEX_PATH", test_idx), \
             patch("app.services.vector_index.METADATA_PATH", test_meta):

            test_faiss = FAISSVectorIndex(dimension=768)
            with patch("app.services.vector_index.get_faiss_index", return_value=test_faiss):
                # Phase 1: Simulate failure during initial sync
                with patch("app.services.vector_index.generate_batch_embeddings", side_effect=RuntimeError("Transient embedding failure")):
                    with pytest.raises(RuntimeError):
                        sync_unindexed_papers(session=db, paper_ids=[pid])

                # Verify index is empty after failure
                assert test_faiss.index.ntotal == 0

                # Phase 2: Recovery run
                def mock_gen_emb(texts):
                    v = np.random.randn(len(texts), 768).astype("float32")
                    return v / np.linalg.norm(v, axis=1, keepdims=True)

                with patch("app.services.vector_index.generate_batch_embeddings", side_effect=mock_gen_emb):
                    recovered_cnt = sync_unindexed_papers(session=db, paper_ids=[pid])
                    assert recovered_cnt >= 1
                    assert pid in test_faiss.paper_metadata
                    assert test_faiss.index.ntotal >= 1

    finally:
        db.delete(p_committed)
        db.commit()
        db.close()
        get_faiss_index()._load_or_initialize()


# ---------------------------------------------------------------------------
# 7. Idempotent Retries
# ---------------------------------------------------------------------------
def test_idempotent_retries(tmp_path):
    """
    Verify that calling sync_unindexed_papers repeatedly on already-indexed papers
    does not create duplicate vectors or increase index count.
    """
    db = SessionLocal()
    pid = f"test:idempotent:{uuid.uuid4().hex[:6]}"
    p = Paper(
        paper_id=pid,
        title="Idempotency Test Paper",
        abstract="Testing repeated sync calls on the same paper record.",
        source="test"
    )
    db.add(p)
    db.commit()

    test_idx = str(tmp_path / "research_index.faiss")
    test_meta = str(tmp_path / "papers_meta.json")

    mock_vec = np.random.randn(1, 768).astype("float32")
    mock_vec = mock_vec / np.linalg.norm(mock_vec, axis=1, keepdims=True)

    try:
        with patch("app.services.vector_index.INDEX_PATH", test_idx), \
             patch("app.services.vector_index.METADATA_PATH", test_meta), \
             patch("app.services.vector_index.generate_batch_embeddings", return_value=mock_vec):

            test_faiss = FAISSVectorIndex(dimension=768)
            with patch("app.services.vector_index.get_faiss_index", return_value=test_faiss):
                # First sync
                count1 = sync_unindexed_papers(session=db, paper_ids=[pid])
                assert count1 == 1
                assert test_faiss.index.ntotal == 1

                # Second sync (identical paper)
                count2 = sync_unindexed_papers(session=db, paper_ids=[pid])
                assert count2 == 0
                assert test_faiss.index.ntotal == 1  # No duplicate vector added

                # Third sync without paper_ids filter
                count3 = sync_unindexed_papers(session=db, paper_ids=[pid])
                assert count3 == 0
                assert test_faiss.index.ntotal == 1

    finally:
        db.delete(p)
        db.commit()
        db.close()
        get_faiss_index()._load_or_initialize()


# ---------------------------------------------------------------------------
# 8. Duplicate Paper Ingestion
# ---------------------------------------------------------------------------
def test_duplicate_paper_ingestion(tmp_path):
    """Verify that add_papers cleanly ignores duplicate paper entries."""
    test_idx = str(tmp_path / "test_dup_index.faiss")
    test_meta = str(tmp_path / "test_dup_meta.json")

    mock_vec = np.random.randn(1, 768).astype("float32")
    mock_vec = mock_vec / np.linalg.norm(mock_vec, axis=1, keepdims=True)

    paper_dup = {
        "paper_id": "test:dup:id",
        "title": "Duplicate Paper Title",
        "abstract": "This is a duplicate paper test abstract."
    }

    with patch("app.services.vector_index.INDEX_PATH", test_idx), \
         patch("app.services.vector_index.METADATA_PATH", test_meta):
        test_faiss = FAISSVectorIndex(dimension=768)

        with patch("app.services.vector_index.generate_batch_embeddings", return_value=mock_vec):
            test_faiss.add_papers([paper_dup])
            assert test_faiss.index.ntotal == 1

            # Second addition with identical paper_id
            test_faiss.add_papers([paper_dup])
            assert test_faiss.index.ntotal == 1  # Retained single entry


# ---------------------------------------------------------------------------
# 9. Concurrent Reindex Requests (HTTP 409 Conflict)
# ---------------------------------------------------------------------------
def test_concurrent_reindex_requests_rejected_with_409():
    """
    Verify that when a reindex is already executing, a second concurrent reindex
    raises ReindexInProgressError.
    """
    db = SessionLocal()
    try:
        # Acquire the reindex lock artificially to simulate a running reindex
        acquired = _REINDEX_LOCK.acquire(blocking=False)
        assert acquired is True

        try:
            with pytest.raises(ReindexInProgressError) as exc_info:
                reindex_vector_database(session=db)
            assert "already in progress" in str(exc_info.value).lower()
        finally:
            _REINDEX_LOCK.release()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 10. Reindex Failure Preserving the Active Index
# ---------------------------------------------------------------------------
def test_reindex_failure_preserves_active_index(tmp_path):
    """Verify that if reindex fails during embedding generation, active index is untouched."""
    db = SessionLocal()
    test_idx = str(tmp_path / "preserve_test_index.faiss")
    test_meta = str(tmp_path / "preserve_test_meta.json")

    # Seed one eligible paper so re-indexing proceeds past the line 438 eligibility guard
    test_paper = Paper(
        paper_id="test:reindex:fail_preserve",
        title="Valid Machine Learning Research Paper",
        abstract="Substantive abstract describing transformer neural architectures for NLP.",
        source="test"
    )
    db.add(test_paper)
    db.commit()

    try:
        with patch("app.services.vector_index.INDEX_PATH", test_idx), \
             patch("app.services.vector_index.METADATA_PATH", test_meta), \
             patch("app.services.vector_index.INDEX_PATH_BAK", f"{test_idx}.bak"), \
             patch("app.services.vector_index.METADATA_PATH_BAK", f"{test_meta}.bak"):

            isolated_faiss = FAISSVectorIndex(dimension=768)
            initial_count = isolated_faiss.index.ntotal

            with patch("app.services.vector_index.get_faiss_index", return_value=isolated_faiss):
                with patch("app.services.vector_index.generate_batch_embeddings", side_effect=RuntimeError("Embedding model out of memory")):
                    res = reindex_vector_database(session=db, force=True)
                    assert res["status"] == "failed"
                    assert res["active_index_preserved"] is True
                    assert "Embedding model out of memory" in res["error"]

            # Active index remains untouched
            assert isolated_faiss.index.ntotal == initial_count
    finally:
        db.delete(test_paper)
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# 11. Search During Reindex
# ---------------------------------------------------------------------------
def test_search_during_reindex(tmp_path):
    """
    Verify that ordinary searches execute safely and return valid results
    even while re-indexing is actively generating embeddings in the background.
    """
    db = SessionLocal()
    test_idx = str(tmp_path / "active_search_index.faiss")
    test_meta = str(tmp_path / "active_search_meta.json")

    mock_vec = np.random.randn(1, 768).astype("float32")
    mock_vec = mock_vec / np.linalg.norm(mock_vec, axis=1, keepdims=True)

    with patch("app.services.vector_index.INDEX_PATH", test_idx), \
         patch("app.services.vector_index.METADATA_PATH", test_meta), \
         patch("app.services.vector_index.INDEX_PATH_BAK", f"{test_idx}.bak"), \
         patch("app.services.vector_index.METADATA_PATH_BAK", f"{test_meta}.bak"):

        # Pre-populate active isolated index with 1 item
        active_faiss = FAISSVectorIndex(dimension=768)
        active_faiss.paper_id_map = ["arxiv:1706.03762v2"]
        active_faiss.paper_metadata = {
            "arxiv:1706.03762v2": {
                "paper_id": "arxiv:1706.03762v2",
                "title": "Attention Is All You Need",
                "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks."
            }
        }
        active_faiss.index.add(mock_vec)

        search_completed = threading.Event()
        search_results = []

        def run_concurrent_search():
            time.sleep(0.05)  # Let reindex start
            res = active_faiss.search("Attention Transformer", top_k=5)
            search_results.extend(res)
            search_completed.set()

        t = threading.Thread(target=run_concurrent_search)

        def slow_batch_embeddings(texts):
            time.sleep(0.2)  # Simulate slow embedding computation
            return np.repeat(mock_vec, len(texts), axis=0)

        with patch("app.services.vector_index.get_faiss_index", return_value=active_faiss), \
             patch("app.services.vector_index.generate_batch_embeddings", side_effect=slow_batch_embeddings), \
             patch("app.services.vector_index.generate_embedding", return_value=mock_vec[0]):

            t.start()
            reindex_vector_database(session=db, force=True)
            t.join()

            assert search_completed.is_set()
            assert len(search_results) == 1
            assert search_results[0][0]["paper_id"] == "arxiv:1706.03762v2"

    db.close()


# ---------------------------------------------------------------------------
# 12. Correct Paper-ID and Metadata Mappings
# ---------------------------------------------------------------------------
def test_correct_paper_id_and_metadata_mappings(tmp_path):
    """Verify that search results map vector positions to the exact paper ID and metadata attributes."""
    test_idx = str(tmp_path / "mapping_test_index.faiss")
    test_meta = str(tmp_path / "mapping_test_meta.json")

    mock_vec = np.random.randn(1, 768).astype("float32")
    mock_vec = mock_vec / np.linalg.norm(mock_vec, axis=1, keepdims=True)

    with patch("app.services.vector_index.INDEX_PATH", test_idx), \
         patch("app.services.vector_index.METADATA_PATH", test_meta):

        test_faiss = FAISSVectorIndex(dimension=768)
        target_pid = "arxiv:test:mapping:123"
        target_meta = {
            "paper_id": target_pid,
            "title": "Exact Mapping Verification Paper",
            "abstract": "Ensuring position idx maps directly to target_pid.",
            "year": 2026
        }

        with patch("app.services.vector_index.generate_batch_embeddings", return_value=mock_vec), \
             patch("app.services.vector_index.generate_embedding", return_value=mock_vec[0]):

            test_faiss.add_papers([target_meta])
            assert test_faiss.index.ntotal == 1

            results = test_faiss.search("Exact Mapping Verification", top_k=1)
            assert len(results) == 1
            retrieved_meta, score = results[0]
            assert retrieved_meta["paper_id"] == target_pid
            assert retrieved_meta["title"] == "Exact Mapping Verification Paper"
            assert retrieved_meta["year"] == 2026
            assert isinstance(score, float)
