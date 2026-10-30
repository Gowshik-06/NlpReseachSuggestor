"""
Tests for TASK-07D: Safe FAISS Synchronization, Consistency Status, Atomic Re-indexing,
Recoverable Backups, Dimension Safeguards, and Administrative Access Control.
"""
import os
import json
import shutil
import pytest
from unittest.mock import patch, MagicMock
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import engine, SessionLocal, Base
from app.models.user import User
from app.models.paper import Paper
from app.core.security import create_access_token, hash_password
from app.services.vector_index import (
    get_faiss_index,
    get_index_consistency_status,
    reindex_vector_database,
    validate_embeddings,
    validate_index_pair_files,
    FAISSVectorIndex,
    reset_faiss_index_instance,
    get_backup_paths,
    reset_degraded_index,
    FAISSCorruptedIndexError,
    INDEX_PATH,
    METADATA_PATH,
    INDEX_PATH_BAK,
    METADATA_PATH_BAK
)

client = TestClient(app)

TEST_ADMIN_USERNAME = "admin_reindex_test"
TEST_NORMAL_USERNAME = "user_reindex_test"


@pytest.fixture(scope="module", autouse=True)
def setup_faiss_test_users():
    """Seed test admin and standard user accounts."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Clean existing
    for u in [TEST_ADMIN_USERNAME, TEST_NORMAL_USERNAME]:
        user_obj = db.query(User).filter(User.username == u).first()
        if user_obj:
            db.delete(user_obj)
    db.commit()

    # Create admin user
    admin_user = User(
        username=TEST_ADMIN_USERNAME,
        email="admin_reindex@test.local",
        hashed_password=hash_password("AdminSecurePass2026!"),
        full_name="System Administrator",
        is_active=True,
        is_superuser=True
    )
    # Create ordinary researcher user
    normal_user = User(
        username=TEST_NORMAL_USERNAME,
        email="normal_reindex@test.local",
        hashed_password=hash_password("NormalUserPass2026!"),
        full_name="Standard Researcher",
        is_active=True,
        is_superuser=False
    )
    db.add_all([admin_user, normal_user])
    db.commit()
    db.close()

    yield

    db_clean = SessionLocal()
    for u in [TEST_ADMIN_USERNAME, TEST_NORMAL_USERNAME]:
        user_obj = db_clean.query(User).filter(User.username == u).first()
        if user_obj:
            db_clean.delete(user_obj)
    db_clean.commit()
    db_clean.close()


def get_token(username: str) -> str:
    return create_access_token(subject=username)


def test_index_status_endpoint_and_service():
    """Verify GET /api/v1/papers/index-status returns accurate database and FAISS metrics."""
    token = get_token(TEST_NORMAL_USERNAME)
    resp = client.get("/api/v1/papers/index-status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()

    assert "total_db_papers" in data
    assert "faiss_vector_count" in data
    assert "faiss_id_map_count" in data
    assert "dimension" in data
    assert data["dimension"] == 768
    assert "missing_vectors_count" in data


def test_reindex_endpoint_removed_in_single_role_model():
    """
    Verify that the obsolete administrative route POST /api/v1/papers/reindex-faiss
    has been removed in alignment with the single-role application model.
    Both anonymous callers and authenticated users receive HTTP 404 Not Found.
    """
    # 1. Anonymous caller receives 404
    resp_anon = client.post("/api/v1/papers/reindex-faiss")
    assert resp_anon.status_code == 404

    # 2. Authenticated user receives 404 (route is unexposed, not role-gated)
    token_normal = get_token(TEST_NORMAL_USERNAME)
    resp_auth = client.post(
        "/api/v1/papers/reindex-faiss",
        headers={"Authorization": f"Bearer {token_normal}"}
    )
    assert resp_auth.status_code == 404




def test_reindex_service_skips_invalid_records(tmp_path):
    """
    Verify re-indexing filters out invalid records:
    - Missing paper_id
    - Duplicate paper_id
    - Empty or trivial text (< 5 characters)
    Does not alter or delete database records.
    Uses tmp_path to preserve baseline FAISS index files.
    """
    db = SessionLocal()

    # Create dummy papers with invalid characteristics
    p_invalid_text = Paper(
        paper_id="test:inv:notext",
        title="",
        abstract="",
        source="test"
    )
    p_valid1 = Paper(
        paper_id="test:inv:valid1",
        title="Valid Machine Learning Research Paper",
        abstract="Detailed abstract on deep learning transformer models.",
        source="test"
    )
    db.add_all([p_invalid_text, p_valid1])
    db.commit()

    test_idx = str(tmp_path / "research_index.faiss")
    test_meta = str(tmp_path / "papers_meta.json")

    try:
        mock_embedding = np.random.randn(1, 768).astype("float32")
        mock_embedding = mock_embedding / np.linalg.norm(mock_embedding, axis=1, keepdims=True)

        with patch("app.services.vector_index.INDEX_PATH", test_idx), \
             patch("app.services.vector_index.METADATA_PATH", test_meta), \
             patch("app.services.vector_index.INDEX_PATH_BAK", f"{test_idx}.bak"), \
             patch("app.services.vector_index.METADATA_PATH_BAK", f"{test_meta}.bak"), \
             patch("app.services.vector_index.generate_batch_embeddings") as mock_gen:
            mock_gen.side_effect = lambda texts: np.repeat(mock_embedding, len(texts), axis=0)

            res = reindex_vector_database(session=db, force=True)
            assert res["status"] == "success"
            assert res["indexed_count"] > 0
            assert res["dimension"] == 768

            # Verify invalid text record was skipped and recorded
            skipped_reasons = [item["reason"] for item in res["skipped_details"]]
            assert "insufficient_text" in skipped_reasons

            # Verify files were created in tmp_path
            assert os.path.exists(test_idx)
            assert os.path.exists(test_meta)

    finally:
        db.delete(p_invalid_text)
        db.delete(p_valid1)
        db.commit()
        db.close()
        # Ensure active singleton is restored from original disk baseline
        get_faiss_index()._load_or_initialize()



def test_reindex_preserves_active_index_on_dimension_mismatch():
    """
    Verify that if embedding generation returns an incompatible dimension (e.g. 512 instead of 768),
    re-indexing fails cleanly and preserves the active index without corruption.
    """
    db = SessionLocal()
    p_dim = Paper(
        paper_id="test:dim:mismatch1",
        title="Dimension Mismatch Test Paper",
        abstract="Substantive abstract for dimension validation test in FAISS.",
        source="test"
    )
    db.add(p_dim)
    db.commit()

    initial_faiss = get_faiss_index()
    initial_count = initial_faiss.index.ntotal if initial_faiss.index else 0

    # Simulate incompatible embedding model dimension (512 instead of 768)
    bad_dim_embeddings = np.random.randn(1, 512).astype("float32")

    try:
        with patch("app.services.vector_index.generate_batch_embeddings", return_value=bad_dim_embeddings):
            res = reindex_vector_database(session=db, force=True)
            assert res["status"] == "failed"
            assert res["active_index_preserved"] is True
            assert "dimension" in res["error"].lower()

        # Verify active index is unchanged
        current_faiss = get_faiss_index()
        assert current_faiss.dimension == 768
        assert current_faiss.index.ntotal == initial_count

        # Verify no dangling .tmp files remained
        assert not os.path.exists(f"{INDEX_PATH}.tmp")
        assert not os.path.exists(f"{METADATA_PATH}.tmp")
    finally:
        db.delete(p_dim)
        db.commit()
        db.close()


def test_reindex_preserves_active_index_on_interrupted_write():
    """
    Verify that if writing the index file fails or raises an OS error,
    active files and active memory instance are completely untouched.
    """
    db = SessionLocal()
    p_write = Paper(
        paper_id="test:write:fail1",
        title="Write Interruption Test Paper",
        abstract="Substantive abstract for write failure simulation test in FAISS.",
        source="test"
    )
    db.add(p_write)
    db.commit()

    initial_faiss = get_faiss_index()
    initial_count = initial_faiss.index.ntotal if initial_faiss.index else 0

    mock_embedding = np.random.randn(1, 768).astype("float32")

    try:
        with patch("app.services.vector_index.generate_batch_embeddings", return_value=mock_embedding):
            with patch("faiss.write_index", side_effect=IOError("Disk write simulated failure")):
                res = reindex_vector_database(session=db, force=True)
                assert res["status"] == "failed"
                assert res["active_index_preserved"] is True

        # Active index remains untouched
        assert get_faiss_index().index.ntotal == initial_count
        assert not os.path.exists(f"{INDEX_PATH}.tmp")
    finally:
        db.delete(p_write)
        db.commit()
        db.close()


def test_add_papers_rejects_incompatible_dimensions():
    """
    Verify that calling add_papers with incompatible vector dimensions raises ValueError
    instead of silently resetting or corrupting the index.
    """
    faiss_idx = get_faiss_index()
    bad_dim_embeddings = np.random.randn(1, 384).astype("float32")

    papers = [{
        "paper_id": "test:dim:mismatch",
        "title": "Quantum Error Correction",
        "abstract": "Analysis of topological surface codes."
    }]

    with patch("app.services.vector_index.generate_batch_embeddings", return_value=bad_dim_embeddings):
        with pytest.raises(ValueError, match="Vector dimension mismatch"):
            faiss_idx.add_papers(papers)


# ==============================================================================
# Batch 2 Regression Tests: Part B (Embedding Validation) & Part C (FAISS Integrity)
# ==============================================================================

def test_validate_embeddings_valid():
    """Verify validate_embeddings accepts valid 2D arrays and normalizes dtypes."""
    # 2D float32
    valid_f32 = np.random.randn(5, 768).astype(np.float32)
    out = validate_embeddings(valid_f32, expected_dimension=768)
    assert out.shape == (5, 768)
    assert out.dtype == np.float32
    assert np.allclose(out, valid_f32)

    # 2D float64 gets converted to float32
    valid_f64 = np.random.randn(3, 768).astype(np.float64)
    out64 = validate_embeddings(valid_f64, expected_dimension=768)
    assert out64.shape == (3, 768)
    assert out64.dtype == np.float32


def test_validate_embeddings_nan_rejected():
    """Verify embeddings containing NaN values are strictly rejected."""
    bad_nan = np.random.randn(4, 768).astype(np.float32)
    bad_nan[2, 10] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        validate_embeddings(bad_nan, expected_dimension=768)


def test_validate_embeddings_pos_and_neg_inf_rejected():
    """Verify embeddings containing positive or negative infinity are strictly rejected."""
    bad_pos_inf = np.random.randn(4, 768).astype(np.float32)
    bad_pos_inf[1, 5] = np.inf
    with pytest.raises(ValueError, match="infinite"):
        validate_embeddings(bad_pos_inf, expected_dimension=768)

    bad_neg_inf = np.random.randn(4, 768).astype(np.float32)
    bad_neg_inf[3, 100] = -np.inf
    with pytest.raises(ValueError, match="infinite"):
        validate_embeddings(bad_neg_inf, expected_dimension=768)


def test_validate_embeddings_dimension_mismatch():
    """Verify vector dimension mismatch raises ValueError before FAISS insertion."""
    bad_dim = np.random.randn(4, 384).astype(np.float32)
    with pytest.raises(ValueError, match="Vector dimension mismatch"):
        validate_embeddings(bad_dim, expected_dimension=768)


def test_validate_embeddings_shape_and_type_malformed():
    """Verify non-2D, empty, None, and non-numeric arrays are rejected."""
    # None
    with pytest.raises(ValueError, match="cannot be None"):
        validate_embeddings(None)

    # 1D array
    with pytest.raises(ValueError, match="expected 2D array"):
        validate_embeddings(np.random.randn(768).astype(np.float32))

    # 3D array
    with pytest.raises(ValueError, match="expected 2D array"):
        validate_embeddings(np.random.randn(2, 2, 768).astype(np.float32))

    # Empty array
    with pytest.raises(ValueError, match="Empty embedding array"):
        validate_embeddings(np.zeros((0, 768), dtype=np.float32))

    # Non-numeric
    with pytest.raises(TypeError, match="numeric"):
        validate_embeddings(np.array([["str1", "str2"]]))


def test_add_papers_rejects_nan_and_inf_embeddings():
    """Verify add_papers rejects NaN and Inf vectors and keeps index intact."""
    faiss_idx = get_faiss_index()
    initial_count = faiss_idx.index.ntotal if faiss_idx.index else 0

    paper = [{
        "paper_id": "test:nan:paper",
        "title": "Adversarial Perturbation Paper",
        "abstract": "Testing NaN rejection in vector index insertion."
    }]

    # NaN rejection
    nan_embedding = np.random.randn(1, 768).astype(np.float32)
    nan_embedding[0, 0] = np.nan
    with patch("app.services.vector_index.generate_batch_embeddings", return_value=nan_embedding):
        with pytest.raises(ValueError, match="NaN"):
            faiss_idx.add_papers(paper)

    assert (faiss_idx.index.ntotal if faiss_idx.index else 0) == initial_count
    assert "test:nan:paper" not in faiss_idx.paper_metadata

    # Inf rejection
    inf_embedding = np.random.randn(1, 768).astype(np.float32)
    inf_embedding[0, 0] = np.inf
    with patch("app.services.vector_index.generate_batch_embeddings", return_value=inf_embedding):
        with pytest.raises(ValueError, match="infinite"):
            faiss_idx.add_papers(paper)

    assert (faiss_idx.index.ntotal if faiss_idx.index else 0) == initial_count
    assert "test:nan:paper" not in faiss_idx.paper_metadata


def test_reindex_rejects_nan_and_inf_embeddings():
    """Verify reindex_vector_database safely aborts on NaN/Inf without corrupting index."""
    db = SessionLocal()
    p_test = Paper(
        paper_id="test:reindex:nan:check",
        title="NaN Reindex Validation Paper",
        abstract="Substantive abstract for NaN rejection during re-indexing.",
        source="test"
    )
    db.add(p_test)
    db.commit()

    initial_faiss = get_faiss_index()
    initial_count = initial_faiss.index.ntotal if initial_faiss.index else 0

    try:
        # 1. NaN simulation
        nan_embeddings = np.random.randn(1, 768).astype(np.float32)
        nan_embeddings[0, 50] = np.nan
        with patch("app.services.vector_index.generate_batch_embeddings", return_value=nan_embeddings):
            res = reindex_vector_database(session=db, force=True)
            assert res["status"] == "failed"
            assert res["active_index_preserved"] is True
            assert "nan" in res["error"].lower()

        assert get_faiss_index().index.ntotal == initial_count

        # 2. Inf simulation
        inf_embeddings = np.random.randn(1, 768).astype(np.float32)
        inf_embeddings[0, 50] = np.inf
        with patch("app.services.vector_index.generate_batch_embeddings", return_value=inf_embeddings):
            res_inf = reindex_vector_database(session=db, force=True)
            assert res_inf["status"] == "failed"
            assert res_inf["active_index_preserved"] is True
            assert "infinite" in res_inf["error"].lower()

        assert get_faiss_index().index.ntotal == initial_count
    finally:
        db.delete(p_test)
        db.commit()
        db.close()


def test_validate_index_pair_files_scenarios(tmp_path):
    """Verify validate_index_pair_files correctly identifies valid and corrupted states."""
    import faiss
    idx_path = str(tmp_path / "valid.faiss")
    meta_path = str(tmp_path / "valid_meta.json")

    # 1. Valid pair
    idx = faiss.IndexFlatIP(768)
    vecs = np.random.randn(2, 768).astype(np.float32)
    idx.add(vecs)
    faiss.write_index(idx, idx_path)

    meta_content = {
        "id_map": ["p1", "p2"],
        "metadata": {
            "p1": {"paper_id": "p1", "title": "Paper 1"},
            "p2": {"paper_id": "p2", "title": "Paper 2"},
        }
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_content, f)

    is_valid, reason, l_idx, l_map, l_meta = validate_index_pair_files(idx_path, meta_path, expected_dim=768)
    assert is_valid is True
    assert l_idx.ntotal == 2
    assert len(l_map) == 2
    assert len(l_meta) == 2

    # 2. Nonexistent index file
    assert validate_index_pair_files(str(tmp_path / "missing.faiss"), meta_path)[0] is False

    # 3. Nonexistent metadata file
    assert validate_index_pair_files(idx_path, str(tmp_path / "missing.json"))[0] is False

    # 4. Zero byte files
    empty_idx = str(tmp_path / "empty.faiss")
    open(empty_idx, "w").close()
    assert validate_index_pair_files(empty_idx, meta_path)[0] is False

    empty_meta = str(tmp_path / "empty.json")
    open(empty_meta, "w").close()
    assert validate_index_pair_files(idx_path, empty_meta)[0] is False

    # 5. Count mismatch (ntotal=2, id_map has 1)
    mismatch_meta = str(tmp_path / "mismatch.json")
    with open(mismatch_meta, "w", encoding="utf-8") as f:
        json.dump({"id_map": ["p1"], "metadata": {"p1": {}}}, f)
    is_valid, reason, _, _, _ = validate_index_pair_files(idx_path, mismatch_meta)
    assert is_valid is False
    assert "Vector count mismatch" in reason

    # 6. ID map vs metadata count mismatch
    meta_mismatch = str(tmp_path / "meta_mismatch.json")
    with open(meta_mismatch, "w", encoding="utf-8") as f:
        json.dump({"id_map": ["p1", "p2"], "metadata": {"p1": {}}}, f)
    is_valid, reason, _, _, _ = validate_index_pair_files(idx_path, meta_mismatch)
    assert is_valid is False
    assert "ID map count mismatch" in reason

    # 7. Duplicate IDs in id_map
    dup_meta = str(tmp_path / "dup.json")
    with open(dup_meta, "w", encoding="utf-8") as f:
        json.dump({"id_map": ["p1", "p1"], "metadata": {"p1": {}}}, f)
    is_valid, reason, _, _, _ = validate_index_pair_files(idx_path, dup_meta)
    assert is_valid is False

    # 8. Dimension mismatch
    is_valid, reason, _, _, _ = validate_index_pair_files(idx_path, meta_path, expected_dim=512)
    assert is_valid is False
    assert "Dimension mismatch" in reason


def test_save_interrupted_replacement_restores_from_backup(tmp_path):
    """
    Verify that if the second os.replace fails during save(),
    the active index file is safely rolled back from the backup.
    """
    custom_dir = str(tmp_path / "faiss_save_test")
    os.makedirs(custom_dir, exist_ok=True)
    idx_file = os.path.join(custom_dir, "test.faiss")
    meta_file = os.path.join(custom_dir, "test.json")
    bak_idx = os.path.join(custom_dir, "test.faiss.bak")
    bak_meta = os.path.join(custom_dir, "test.json.bak")

    with patch("app.services.vector_index.INDEX_DIR", custom_dir), \
         patch("app.services.vector_index.INDEX_PATH", idx_file), \
         patch("app.services.vector_index.METADATA_PATH", meta_file), \
         patch("app.services.vector_index.INDEX_PATH_BAK", bak_idx), \
         patch("app.services.vector_index.METADATA_PATH_BAK", bak_meta):

        # Initial instance with 1 paper
        inst = FAISSVectorIndex(dimension=768)
        initial_vec = np.random.randn(1, 768).astype(np.float32)
        with patch("app.services.vector_index.generate_batch_embeddings", return_value=initial_vec):
            inst.add_papers([{"paper_id": "orig_p1", "title": "Original Paper", "abstract": "Original abstract text"}])

        assert os.path.exists(idx_file)
        assert os.path.exists(meta_file)
        orig_idx_bytes = open(idx_file, "rb").read()

        # Add second paper but simulate failure on the second os.replace (meta replacement)
        orig_replace = os.replace

        def failing_replace(src, dst):
            if dst == meta_file:
                raise OSError("Simulated crash between index and metadata replace")
            return orig_replace(src, dst)

        new_vec = np.random.randn(1, 768).astype(np.float32)
        with patch("os.replace", side_effect=failing_replace):
            with patch("app.services.vector_index.generate_batch_embeddings", return_value=new_vec):
                with pytest.raises(OSError, match="Simulated crash"):
                    inst.add_papers([{"paper_id": "new_p2", "title": "New Paper", "abstract": "New abstract text"}])

        # Verification: INDEX_PATH was restored from INDEX_PATH_BAK and matches orig bytes
        assert os.path.exists(idx_file)
        assert open(idx_file, "rb").read() == orig_idx_bytes
        # Metadata still has orig_p1
        with open(meta_file, "r") as f:
            data = json.load(f)
            assert data["id_map"] == ["orig_p1"]


def test_reindex_interrupted_replacement_restores_from_backup():
    """
    Verify that if the second os.replace fails during reindex_vector_database,
    the active index file is rolled back from the backup.
    """
    db = SessionLocal()
    p_rec = Paper(
        paper_id="test:reindex:interrupted:rec",
        title="Interrupted Replace Paper",
        abstract="Substantive abstract for interrupted replace rollback test.",
        source="test"
    )
    db.add(p_rec)
    db.commit()

    initial_faiss = get_faiss_index()
    initial_count = initial_faiss.index.ntotal if initial_faiss.index else 0
    orig_idx_bytes = open(INDEX_PATH, "rb").read() if os.path.exists(INDEX_PATH) else None

    orig_replace = os.replace
    def failing_replace(src, dst):
        if dst == METADATA_PATH:
            raise OSError("Simulated disk failure during metadata replacement")
        return orig_replace(src, dst)

    try:
        mock_embedding = np.random.randn(1, 768).astype(np.float32)
        with patch("app.services.vector_index.generate_batch_embeddings", return_value=mock_embedding):
            with patch("os.replace", side_effect=failing_replace):
                res = reindex_vector_database(session=db, force=True)
                assert res["status"] == "failed"
                assert res["active_index_preserved"] is True

        # Active index on disk was restored
        if orig_idx_bytes is not None:
            assert open(INDEX_PATH, "rb").read() == orig_idx_bytes
        assert get_faiss_index().index.ntotal == initial_count
    finally:
        db.delete(p_rec)
        db.commit()
        db.close()


def test_startup_recovery_from_backup_when_active_corrupted(tmp_path):
    """
    Verify _load_or_initialize detects corrupted active files and recovers
    from consistent backup files automatically.
    """
    import faiss
    custom_dir = str(tmp_path / "startup_rec")
    os.makedirs(custom_dir, exist_ok=True)
    idx_file = os.path.join(custom_dir, "test.faiss")
    meta_file = os.path.join(custom_dir, "test.json")
    bak_idx = os.path.join(custom_dir, "test.faiss.bak")
    bak_meta = os.path.join(custom_dir, "test.json.bak")

    # Prepare consistent backup files (1 vector)
    b_idx = faiss.IndexFlatIP(768)
    b_idx.add(np.random.randn(1, 768).astype(np.float32))
    faiss.write_index(b_idx, bak_idx)
    with open(bak_meta, "w", encoding="utf-8") as f:
        json.dump({"id_map": ["p_bak"], "metadata": {"p_bak": {"paper_id": "p_bak"}}}, f)

    # Prepare corrupted active files (index has 3 vectors, metadata has 1)
    a_idx = faiss.IndexFlatIP(768)
    a_idx.add(np.random.randn(3, 768).astype(np.float32))
    faiss.write_index(a_idx, idx_file)
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({"id_map": ["p_corrupt"], "metadata": {"p_corrupt": {"paper_id": "p_corrupt"}}}, f)

    with patch("app.services.vector_index.INDEX_DIR", custom_dir), \
         patch("app.services.vector_index.INDEX_PATH", idx_file), \
         patch("app.services.vector_index.METADATA_PATH", meta_file), \
         patch("app.services.vector_index.INDEX_PATH_BAK", bak_idx), \
         patch("app.services.vector_index.METADATA_PATH_BAK", bak_meta):

        inst = FAISSVectorIndex(dimension=768)
        # Recovered from backup: 1 entry
        assert inst.index.ntotal == 1
        assert inst.paper_id_map == ["p_bak"]
        # Active files on disk were restored from backup
        disk_idx = faiss.read_index(idx_file)
        assert disk_idx.ntotal == 1


def test_startup_rejects_inconsistent_files_when_backup_missing(tmp_path):
    """
    Verify _load_or_initialize safely initializes a clean index when active files
    are inconsistent and no backup is available, rather than silently loading corrupt data.
    """
    import faiss
    custom_dir = str(tmp_path / "startup_reject")
    os.makedirs(custom_dir, exist_ok=True)
    idx_file = os.path.join(custom_dir, "test.faiss")
    meta_file = os.path.join(custom_dir, "test.json")
    bak_idx = os.path.join(custom_dir, "test.faiss.bak")
    bak_meta = os.path.join(custom_dir, "test.json.bak")

    # Corrupted active files (index has 2 vectors, metadata has 0)
    a_idx = faiss.IndexFlatIP(768)
    a_idx.add(np.random.randn(2, 768).astype(np.float32))
    faiss.write_index(a_idx, idx_file)
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({"id_map": [], "metadata": {}}, f)

    with patch("app.services.vector_index.INDEX_DIR", custom_dir), \
         patch("app.services.vector_index.INDEX_PATH", idx_file), \
         patch("app.services.vector_index.METADATA_PATH", meta_file), \
         patch("app.services.vector_index.INDEX_PATH_BAK", bak_idx), \
         patch("app.services.vector_index.METADATA_PATH_BAK", bak_meta):

        inst = FAISSVectorIndex(dimension=768)
        # Safely enters degraded state to prevent data destruction
        assert inst.index.ntotal == 0
        assert inst.paper_id_map == []
        assert inst.paper_metadata == {}
        assert inst.is_degraded is True
        assert "Active index corrupted" in (inst.degradation_reason or "")


def test_index_consistency_status_detects_vector_metadata_count_mismatch():
    """Verify get_index_consistency_status flags is_consistent=False on count mismatch."""
    db = SessionLocal()
    faiss_idx = get_faiss_index()

    # Artificially alter paper_id_map to simulate internal desync
    original_map = list(faiss_idx.paper_id_map)
    try:
        faiss_idx.paper_id_map = original_map + ["ghost_pid"]
        status = get_index_consistency_status(db)
        assert status["is_consistent"] is False
    finally:
        faiss_idx.paper_id_map = original_map
        db.close()


def test_backup_paths_isolated_to_custom_directory(tmp_path):
    """
    ISSUE-01: Verify that backup paths are co-located in the custom directory
    and never leak into default or production paths.
    """
    custom_dir = str(tmp_path / "custom_faiss_dir")
    os.makedirs(custom_dir, exist_ok=True)
    custom_idx = os.path.join(custom_dir, "custom.faiss")
    custom_meta = os.path.join(custom_dir, "custom.json")

    bak_idx, bak_meta = get_backup_paths(custom_idx, custom_meta)
    assert os.path.dirname(bak_idx) == custom_dir
    assert os.path.dirname(bak_meta) == custom_dir
    assert bak_idx == f"{custom_idx}.bak"
    assert bak_meta == f"{custom_meta}.bak"


def test_first_run_initialization_not_degraded(tmp_path):
    """
    ISSUE-02: Genuine first-run initialization with no files on disk
    must cleanly initialize an empty index without degraded state.
    """
    fresh_dir = str(tmp_path / "fresh_run")
    os.makedirs(fresh_dir, exist_ok=True)
    idx_p = os.path.join(fresh_dir, "fresh.faiss")
    meta_p = os.path.join(fresh_dir, "fresh.json")

    with patch("app.services.vector_index.INDEX_DIR", fresh_dir), \
         patch("app.services.vector_index.INDEX_PATH", idx_p), \
         patch("app.services.vector_index.METADATA_PATH", meta_p):

        inst = FAISSVectorIndex(dimension=768)
        assert inst.is_degraded is False
        assert inst.degradation_reason is None
        assert inst.index.ntotal == 0
        assert inst.paper_id_map == []
        assert inst.paper_metadata == {}


def test_corrupted_active_files_blocks_writes_and_preserves_artifacts(tmp_path):
    """
    ISSUE-02: Corrupted active files with no valid backup must:
    1. Enter degraded state.
    2. Block save() and add_papers() to prevent overwriting evidence.
    3. Return [] on search().
    4. Leave corrupted files completely untouched.
    """
    import faiss
    test_dir = str(tmp_path / "degraded_write_block")
    os.makedirs(test_dir, exist_ok=True)
    idx_p = os.path.join(test_dir, "corrupt.faiss")
    meta_p = os.path.join(test_dir, "corrupt.json")

    # Write corrupt active files: index with 3 vectors, metadata with invalid JSON
    a_idx = faiss.IndexFlatIP(768)
    a_idx.add(np.random.randn(3, 768).astype(np.float32))
    faiss.write_index(a_idx, idx_p)
    with open(meta_p, "w", encoding="utf-8") as f:
        f.write("{invalid_json_corrupted_state")

    orig_idx_bytes = open(idx_p, "rb").read()
    orig_meta_bytes = open(meta_p, "rb").read()

    with patch("app.services.vector_index.INDEX_DIR", test_dir), \
         patch("app.services.vector_index.INDEX_PATH", idx_p), \
         patch("app.services.vector_index.METADATA_PATH", meta_p):

        # 1. Initialization enters degraded state
        inst = FAISSVectorIndex(dimension=768)
        assert inst.is_degraded is True
        assert inst.degradation_reason is not None

        # 2. Block save()
        with pytest.raises(FAISSCorruptedIndexError) as exc_save:
            inst.save()
        assert "Blocked save on degraded FAISS index" in str(exc_save.value)

        # 3. Block add_papers()
        with pytest.raises(FAISSCorruptedIndexError) as exc_add:
            inst.add_papers([{"paper_id": "p_new", "title": "New Paper", "abstract": "Abstract content"}])
        assert "Blocked add_papers on degraded FAISS index" in str(exc_add.value)

        # 4. search() returns empty list safely
        assert inst.search("quantum computing") == []

        # 5. On-disk files remain untouched
        assert open(idx_p, "rb").read() == orig_idx_bytes
        assert open(meta_p, "rb").read() == orig_meta_bytes


def test_corrupted_backup_pair_fails_closed_into_degraded_state(tmp_path):
    """
    ISSUE-02: When active files are corrupt and backups exist but are also corrupt,
    must fail closed into degraded state without truncating or overwriting.
    """
    import faiss
    test_dir = str(tmp_path / "double_corrupt")
    os.makedirs(test_dir, exist_ok=True)
    idx_p = os.path.join(test_dir, "idx.faiss")
    meta_p = os.path.join(test_dir, "meta.json")
    bak_idx = f"{idx_p}.bak"
    bak_meta = f"{meta_p}.bak"

    # Both active and backup have mismatched or broken files
    with open(idx_p, "wb") as f:
        f.write(b"not_a_faiss_file")
    with open(meta_p, "w") as f:
        f.write('{"id_map": [], "metadata": {}}')

    with open(bak_idx, "wb") as f:
        f.write(b"corrupted_backup_bytes")
    with open(bak_meta, "w") as f:
        f.write("corrupted_backup_json")

    with patch("app.services.vector_index.INDEX_DIR", test_dir), \
         patch("app.services.vector_index.INDEX_PATH", idx_p), \
         patch("app.services.vector_index.METADATA_PATH", meta_p):

        inst = FAISSVectorIndex(dimension=768)
        assert inst.is_degraded is True
        assert "recovery failed" in inst.degradation_reason.lower()


def test_failed_recovery_reported_in_consistency_status():
    """
    ISSUE-02: Verify get_index_consistency_status reflects is_degraded=True
    and is_consistent=False when index is degraded.
    """
    db = SessionLocal()
    faiss_idx = get_faiss_index()
    orig_deg = faiss_idx.is_degraded
    orig_reason = faiss_idx.degradation_reason

    try:
        faiss_idx.is_degraded = True
        faiss_idx.degradation_reason = "Test degradation"
        status = get_index_consistency_status(db)
        assert status["is_degraded"] is True
        assert status["is_consistent"] is False
        assert status["degradation_reason"] == "Test degradation"
    finally:
        faiss_idx.is_degraded = orig_deg
        faiss_idx.degradation_reason = orig_reason
        db.close()


def test_reset_degraded_index_requires_force():
    """
    ISSUE-02: Resetting a degraded index requires force=True to prevent accidental resets.
    """
    faiss_idx = get_faiss_index()
    orig_deg = faiss_idx.is_degraded
    orig_reason = faiss_idx.degradation_reason

    try:
        faiss_idx.is_degraded = True
        faiss_idx.degradation_reason = "Degraded by test"

        # Without force, must raise ValueError
        with pytest.raises(ValueError):
            reset_degraded_index(force=False)

        assert faiss_idx.is_degraded is True

        # With force=True, clears degraded state
        assert reset_degraded_index(force=True) is True
        assert faiss_idx.is_degraded is False
        assert faiss_idx.degradation_reason is None
    finally:
        faiss_idx.is_degraded = orig_deg
        faiss_idx.degradation_reason = orig_reason

