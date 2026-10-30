"""
Unit and integration tests for DRIUT Background Scheduler, Automated Research Impact Monitoring,
Taxonomy Classification, Idempotency, and Provider Failure Tolerance.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import engine, SessionLocal, Base
from app.models.paper import Paper, SavedPaper
from app.models.driut import DRIUTAlert
from app.models.user import User
from app.core.security import create_access_token, hash_password
from app.services.driut_scheduler import DRIUTScheduler
from app.services.driut_service import (
    classify_relationship,
    generate_driut_explanation,
    scan_research_impact_updates,
    PATTERNS
)
from app.services.notification_service import notification_dispatcher

client = TestClient(app)

TEST_USER_A = "user_alpha_driut"
TEST_USER_B = "user_beta_driut"


@pytest.fixture(scope="module", autouse=True)
def setup_driut_test_db():
    """Setup isolated test database users and papers for DRIUT tests."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Clean existing test data
    for u in [TEST_USER_A, TEST_USER_B]:
        db.query(DRIUTAlert).filter(DRIUTAlert.user_id == u).delete()
        db.query(SavedPaper).filter(SavedPaper.user_id == u).delete()
        user_obj = db.query(User).filter(User.username == u).first()
        if user_obj:
            db.delete(user_obj)
    db.commit()

    # Create test users
    user_a = User(
        username=TEST_USER_A,
        email="alpha_driut@test.local",
        hashed_password=hash_password("PasswordAlpha123!"),
        full_name="Alpha Researcher"
    )
    user_b = User(
        username=TEST_USER_B,
        email="beta_driut@test.local",
        hashed_password=hash_password("PasswordBeta123!"),
        full_name="Beta Researcher"
    )
    db.add_all([user_a, user_b])

    # Ensure baseline test papers exist
    p_orig = db.query(Paper).filter(Paper.paper_id == "driut:orig:bert").first()
    if not p_orig:
        p_orig = Paper(
            paper_id="driut:orig:bert",
            title="BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
            abstract="We introduce BERT, a language representation model using bidirectional transformer architectures.",
            authors=["Jacob Devlin", "Ming-Wei Chang"],
            venue="NAACL 2019",
            year=2019,
            source="test"
        )
        db.add(p_orig)

    p_new = db.query(Paper).filter(Paper.paper_id == "driut:cand:roberta").first()
    if not p_new:
        p_new = Paper(
            paper_id="driut:cand:roberta",
            title="RoBERTa: A Robustly Optimized BERT Approach",
            abstract="We find that BERT was undertrained. RoBERTa substantially improves accuracy and outperforms BERT across benchmarks.",
            authors=["Yinhan Liu", "Myle Ott"],
            venue="arXiv 2019",
            year=2019,
            source="test"
        )
        db.add(p_new)

    db.commit()
    db.close()

    yield

    # Teardown
    db_clean = SessionLocal()
    for u in [TEST_USER_A, TEST_USER_B]:
        db_clean.query(DRIUTAlert).filter(DRIUTAlert.user_id == u).delete()
        db_clean.query(SavedPaper).filter(SavedPaper.user_id == u).delete()
        user_obj = db_clean.query(User).filter(User.username == u).first()
        if user_obj:
            db_clean.delete(user_obj)
    db_clean.commit()
    db_clean.close()


def get_token(username: str) -> str:
    return create_access_token(subject=username)


# ---------------------------------------------------------------------------
# 1. Scheduler Lifecycle & Concurrency Lock
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_scheduler_lifecycle():
    """Verify scheduler startup, background task loop lifecycle, and graceful shutdown."""
    scheduler = DRIUTScheduler()
    assert scheduler.is_enabled is True
    assert scheduler.is_running is False

    await scheduler.start()
    assert scheduler.is_running is True

    # Calling start again when already running should be idempotent
    await scheduler.start()
    assert scheduler.is_running is True

    await scheduler.stop()
    assert scheduler.is_running is False


@pytest.mark.anyio
async def test_scheduler_disabled_mode():
    """Verify scheduler does not launch background loop when disabled by configuration."""
    scheduler = DRIUTScheduler()
    scheduler._is_enabled = False

    await scheduler.start()
    assert scheduler.is_running is False
    assert scheduler._task is None


@pytest.mark.anyio
async def test_scheduler_concurrency_lock():
    """Verify that concurrent or overlapping scan requests are skipped safely."""
    scheduler = DRIUTScheduler()
    scheduler._is_running_scan = True  # Simulate active running scan

    res = await scheduler.run_scan_job(user_id=TEST_USER_A, query_academic=False)
    assert res["status"] == "skipped"
    assert "currently running" in res["reason"]


# ---------------------------------------------------------------------------
# 2. Taxonomy Classification across all 6 categories
# ---------------------------------------------------------------------------

def test_taxonomy_classification_all_categories():
    """Verify classification logic accurately categorizes all 6 DRIUT relationship types."""
    saved_paper = {
        "paper_id": "orig:101",
        "title": "Attention Is All You Need",
        "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks."
    }

    # 1. Improvement
    p_improvement = {
        "paper_id": "cand:imp",
        "title": "Optimized Attention Transformer Architecture",
        "abstract": "Our architecture outperforms and substantially improves accuracy, achieving state-of-the-art results over Attention Is All You Need."
    }
    rel, conf, expl = classify_relationship(saved_paper, p_improvement)
    assert rel == "Improvement"
    assert conf >= 0.65
    assert "improves" in expl.lower() or "benchmark" in expl.lower()

    # 2. Extension
    p_extension = {
        "paper_id": "cand:ext",
        "title": "Vision Transformer: Scaling Attention to Computer Vision",
        "abstract": "We extend and build upon the architecture of Attention Is All You Need, scaling the unified backbone to multi-task visual recognition."
    }
    rel, conf, expl = classify_relationship(saved_paper, p_extension)
    assert rel == "Extension"
    assert conf >= 0.65
    assert "extends" in expl.lower()

    # 3. Challenge
    p_challenge = {
        "paper_id": "cand:chal",
        "title": "Limitations and Vulnerabilities of Attention Architectures",
        "abstract": "This critique identifies a serious drawback and flaw in Attention Is All You Need, showing severe overfitting and unstable representations."
    }
    rel, conf, expl = classify_relationship(saved_paper, p_challenge)
    assert rel == "Challenge"
    assert conf >= 0.65
    assert "questions assumptions" in expl.lower() or "limitation" in expl.lower()

    # 4. Reproduction
    p_reproduction = {
        "paper_id": "cand:repr",
        "title": "A Systematic Replication and Empirical Verification of Attention Is All You Need",
        "abstract": "We present an independent verification and empirical replication study to investigate the claims and audit results of Attention Is All You Need."
    }
    rel, conf, expl = classify_relationship(saved_paper, p_reproduction)
    assert rel == "Reproduction"
    assert conf >= 0.65
    assert "replication" in expl.lower() or "empirical" in expl.lower()

    # 5. Alternative
    p_alternative = {
        "paper_id": "cand:alt",
        "title": "Mamba: Linear-Time Sequence Modeling with Selective State Spaces",
        "abstract": "Instead of attention, we introduce an alternative paradigm dispensing with quadratic attention and eliminating recurrence."
    }
    rel, conf, expl = classify_relationship(saved_paper, p_alternative)
    assert rel == "Alternative"
    assert conf >= 0.65
    assert "alternative" in expl.lower()

    # 6. Potential Replacement
    p_replacement = {
        "paper_id": "cand:rep",
        "title": "Unified State-Space Sequence Standard",
        "abstract": "Our architecture supersedes previous models, acting as a drop-in replacement that renders obsolete Attention Is All You Need."
    }
    rel, conf, expl = classify_relationship(saved_paper, p_replacement)
    assert rel == "Potential Replacement"
    assert conf >= 0.65
    assert "replacement" in expl.lower() or "supercedes" in expl.lower()


# ---------------------------------------------------------------------------
# 3. Academic Source Discovery & Tolerance to Partial Provider Failures
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_partial_provider_failure_tolerance():
    """
    Verify that when one academic provider fails (e.g. arXiv timeout), the scan
    records the failure, continues with other providers and local papers, and succeeds.
    """
    db = SessionLocal()
    orig_p = db.query(Paper).filter(Paper.paper_id == "driut:orig:bert").first()

    # Save paper for User Alpha
    saved = SavedPaper(user_id=TEST_USER_A, paper_id=orig_p.id)
    db.add(saved)
    db.commit()

    mock_pubmed_result = [{
        "paper_id": "pubmed:99887766",
        "title": "BioBERT: Extending Pre-trained BERT for Biomedical Applications",
        "abstract": "BioBERT extends BERT architectures and achieves superior biomedical domain performance over standard BERT.",
        "authors": ["Jinhyuk Lee"],
        "venue": "Bioinformatics",
        "year": 2020,
        "source": "pubmed"
    }]

    # Patch arXiv to raise an exception, and PubMed to return candidates
    with patch("app.services.academic_sources.search_arxiv", side_effect=RuntimeError("arXiv API 503 Service Unavailable")), \
         patch("app.services.academic_sources.search_pubmed", new_callable=AsyncMock, return_value=mock_pubmed_result), \
         patch("app.services.academic_sources.search_csir_niscpr", new_callable=AsyncMock, return_value=[]), \
         patch("app.services.academic_sources.search_crossref", new_callable=AsyncMock, return_value=[]):

        res = await scan_research_impact_updates(session=db, user_id=TEST_USER_A, query_academic=True)

        # Provider errors captured cleanly
        assert "arxiv" in res["provider_errors"]
        assert "503 Service Unavailable" in res["provider_errors"]["arxiv"]
        assert res["provider_status"]["arxiv"] == "error"
        assert res["provider_status"]["pubmed"] == "healthy"

        # The scan nevertheless completed and created alerts from PubMed/local DB
        assert res["new_alerts_created"] >= 1

    db.close()


# ---------------------------------------------------------------------------
# 4. Idempotency & Alert Preservation
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_driut_idempotency_and_is_read_preservation():
    """
    Verify that repeated scans do not create duplicate alerts and never reset
    existing is_read=True status back to False.
    """
    db = SessionLocal()
    orig_p = db.query(Paper).filter(Paper.paper_id == "driut:orig:bert").first()

    # Ensure saved paper exists
    saved = db.query(SavedPaper).filter(
        SavedPaper.user_id == TEST_USER_A,
        SavedPaper.paper_id == orig_p.id
    ).first()
    if not saved:
        saved = SavedPaper(user_id=TEST_USER_A, paper_id=orig_p.id)
        db.add(saved)
        db.commit()

    # First scan
    res1 = await scan_research_impact_updates(session=db, user_id=TEST_USER_A, query_academic=False)
    alerts1 = db.query(DRIUTAlert).filter(DRIUTAlert.user_id == TEST_USER_A).all()
    assert len(alerts1) > 0

    first_alert = alerts1[0]
    # Mark alert as read
    first_alert.is_read = True
    db.commit()

    initial_alert_count = db.query(DRIUTAlert).filter(DRIUTAlert.user_id == TEST_USER_A).count()

    # Second scan on identical data
    res2 = await scan_research_impact_updates(session=db, user_id=TEST_USER_A, query_academic=False)
    assert res2["new_alerts_created"] == 0

    # Total alert count unchanged
    final_alert_count = db.query(DRIUTAlert).filter(DRIUTAlert.user_id == TEST_USER_A).count()
    assert final_alert_count == initial_alert_count

    # Alert remains is_read == True!
    db.refresh(first_alert)
    assert first_alert.is_read is True

    db.close()


# ---------------------------------------------------------------------------
# 5. User Data Isolation
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_driut_user_isolation():
    """
    Verify that User A's DRIUT monitoring and alerts are strictly isolated
    from User B.
    """
    db = SessionLocal()

    # Ensure User B has NO saved papers
    db.query(SavedPaper).filter(SavedPaper.user_id == TEST_USER_B).delete()
    db.query(DRIUTAlert).filter(DRIUTAlert.user_id == TEST_USER_B).delete()
    db.commit()

    # Scan for User B
    res_b = await scan_research_impact_updates(session=db, user_id=TEST_USER_B, query_academic=False)
    assert res_b["new_alerts_created"] == 0
    assert db.query(DRIUTAlert).filter(DRIUTAlert.user_id == TEST_USER_B).count() == 0

    # API verification: User B requesting alerts sees empty list
    token_b = get_token(TEST_USER_B)
    api_res = client.get("/api/v1/papers/driut/alerts", headers={"Authorization": f"Bearer {token_b}"})
    assert api_res.status_code == 200
    assert len(api_res.json()) == 0

    # User A requesting alerts sees their own alerts
    token_a = get_token(TEST_USER_A)
    api_res_a = client.get("/api/v1/papers/driut/alerts", headers={"Authorization": f"Bearer {token_a}"})
    assert api_res_a.status_code == 200
    assert len(api_res_a.json()) > 0
    for a in api_res_a.json():
        assert a["user_id"] == TEST_USER_A

    db.close()


# ---------------------------------------------------------------------------
# 6. Notification Boundary Dispatch
# ---------------------------------------------------------------------------

def test_notification_boundary_dispatch():
    """Verify that NotificationDispatcher records dispatch event without external side-effects."""
    prev_count = notification_dispatcher.dispatched_count

    success = notification_dispatcher.dispatch_alert_notification(
        user_id="test_notif_user",
        saved_paper_title="Original Baseline Study",
        trigger_paper_title="New Follow-up Extension",
        relationship_type="Extension",
        confidence_score=0.91,
        explanation="Extends baseline capabilities."
    )

    assert success is True
    assert notification_dispatcher.dispatched_count == prev_count + 1


# ---------------------------------------------------------------------------
# 7. Real API Endpoints: GET /driut/status & POST /driut/scan
# ---------------------------------------------------------------------------

def test_api_driut_status_endpoint():
    """Verify GET /api/v1/papers/driut/status returns valid scheduler state."""
    token = get_token(TEST_USER_A)
    resp = client.get("/api/v1/papers/driut/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()

    assert "is_enabled" in data
    assert "is_running_scan" in data
    assert "interval_minutes" in data
    assert "last_run_status" in data
    assert "provider_status" in data
    assert isinstance(data["provider_status"], dict)


def test_api_driut_scan_endpoint_authenticated():
    """Verify POST /api/v1/papers/driut/scan triggers scan and returns DRIUTScanResponse."""
    token = get_token(TEST_USER_A)
    resp = client.post("/api/v1/papers/driut/scan", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()

    assert "message" in data
    assert "new_alerts_count" in data
    assert "alerts" in data
    assert isinstance(data["alerts"], list)


# ---------------------------------------------------------------------------
# 8. PostgreSQL Advisory Locking Concurrency Tests (TASK-07B)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_advisory_lock_contention_skips_cleanly():
    """
    Verify that if another application worker holds the advisory lock,
    a scheduled execution skips cleanly without throwing errors or running.
    """
    from sqlalchemy import text
    scheduler = DRIUTScheduler()
    lock_key = scheduler.advisory_lock_key

    if engine.dialect.name == "postgresql":
        # Real PostgreSQL advisory lock contention
        conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        try:
            acquired = conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key}).scalar()
            assert acquired is True, "Test connection should acquire advisory lock"

            # Scheduled scan (user_id=None) attempts to run while lock is held
            res = await scheduler.run_scan_job(user_id=None, query_academic=False)
            assert res["status"] == "skipped"
            assert "advisory lock" in res["reason"]
            assert res["new_alerts_created"] == 0
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
            conn.close()
    else:
        # Portable test: simulate contention via _acquire_advisory_lock returning (False, None)
        with patch.object(scheduler, "_acquire_advisory_lock", return_value=(False, None)):
            res = await scheduler.run_scan_job(user_id=None, query_academic=False)
            assert res["status"] == "skipped"
            assert "advisory lock" in res["reason"]
            assert res["new_alerts_created"] == 0


@pytest.mark.anyio
async def test_advisory_lock_released_after_execution_and_exceptions():
    """
    Verify that the advisory lock is released reliably after both normal completion
    and unhandled exceptions in the scan routine.
    """
    from sqlalchemy import text
    scheduler = DRIUTScheduler()
    lock_key = scheduler.advisory_lock_key

    if engine.dialect.name == "postgresql":
        # 1. Normal execution release
        res_normal = await scheduler.run_scan_job(user_id=None, query_academic=False)
        assert res_normal["status"] in ["success", "partial_failure"]

        # Verify lock is free by acquiring it
        conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        try:
            acquired = conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key}).scalar()
            assert acquired is True, "Lock should be released after normal execution"
            conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
        finally:
            conn.close()

        # 2. Execution with exception inside scan
        with patch("app.services.driut_scheduler.scan_research_impact_updates", side_effect=RuntimeError("Simulated scan failure")):
            res_err = await scheduler.run_scan_job(user_id=None, query_academic=False)
            assert res_err["status"] == "error"

        # Verify lock was released even after exception
        conn2 = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        try:
            acquired2 = conn2.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key}).scalar()
            assert acquired2 is True, "Lock should be released after exception in scan job"
            conn2.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
        finally:
            conn2.close()
    else:
        # Portable test: verify acquire and release lifecycle executed properly
        dummy_conn = MagicMock()
        with patch.object(scheduler, "_acquire_advisory_lock", return_value=(True, dummy_conn)):
            with patch.object(scheduler, "_release_advisory_lock", wraps=scheduler._release_advisory_lock) as mock_release:
                res_normal = await scheduler.run_scan_job(user_id=None, query_academic=False)
                assert res_normal["status"] in ["success", "partial_failure"]
                assert mock_release.called
                mock_release.assert_called_with(dummy_conn, lock_key)

        with patch("app.services.driut_scheduler.scan_research_impact_updates", side_effect=RuntimeError("Simulated scan failure")):
            with patch.object(scheduler, "_acquire_advisory_lock", return_value=(True, dummy_conn)):
                with patch.object(scheduler, "_release_advisory_lock", wraps=scheduler._release_advisory_lock) as mock_release_err:
                    res_err = await scheduler.run_scan_job(user_id=None, query_academic=False)
                    assert res_err["status"] == "error"
                    assert mock_release_err.called
                    mock_release_err.assert_called_with(dummy_conn, lock_key)


# ---------------------------------------------------------------------------
# 9. DRIUT Extension Grounding & Boundary Tests (TASK-07C)
# ---------------------------------------------------------------------------

def test_extension_grounding_positive_fallback():
    """
    Verify that when no explicit lexical regex matches, a paper with high
    cosine similarity AND at least two shared domain keyphrases is classified as Extension.
    """
    saved_paper = {
        "paper_id": "test:grounded:base",
        "title": "Self-Supervised Contrastive Learning for Biomedical Text Representation",
        "abstract": "We present biomedical text representations trained using contrastive learning objectives on clinical datasets."
    }
    candidate_paper = {
        "paper_id": "test:grounded:cand",
        "title": "Adapting Biomedical Contrastive Learning to Clinical Genomic Sequences",
        "abstract": "We investigate biomedical contrastive learning methods on genomic datasets, evaluating clinical representations across cross-modal tasks."
    }

    rel, conf, expl = classify_relationship(saved_paper, candidate_paper)
    assert rel in ["Extension", "Improvement"]
    assert conf >= 0.65
    assert len(expl) > 0


def test_extension_grounding_negative_insufficient_grounding():
    """
    Verify that two papers lacking lexical patterns and lacking shared domain keyphrases
    are NOT classified as Extension solely due to embedding similarity.
    """
    saved_paper = {
        "paper_id": "test:ungrounded:base",
        "title": "Quantum Computing Algorithms in High Energy Physics",
        "abstract": "We analyze qubit simulation routines for particle collision events."
    }
    candidate_paper = {
        "paper_id": "test:ungrounded:cand",
        "title": "Deep Neural Network Optimization on Mobile Hardware",
        "abstract": "We evaluate kernel scheduling routines for edge computing deployment."
    }

    rel, conf, expl = classify_relationship(saved_paper, candidate_paper)
    # Must reject due to lack of domain grounding or low thematic relationship
    assert rel is None
    assert conf == 0.0
    assert expl == ""


def test_classify_relationship_missing_ids_not_treated_as_identical():
    """
    Verify that two records with paper_id=None are NEVER treated as identical
    merely because both IDs are missing.
    """
    p1 = {
        "paper_id": None,
        "title": "Transformer Attention Mechanisms in Natural Language Processing",
        "abstract": "Comprehensive study of self-attention multi-head transformer networks."
    }
    p2 = {
        "paper_id": None,
        "title": "Efficient Sparse Attention Transformers for Long Sequences",
        "abstract": "We improve upon transformer attention mechanisms, reducing quadratic memory overhead for language processing."
    }

    rel, conf, expl = classify_relationship(p1, p2)
    # Because titles are different and substantive content exists with improvement/extension lexical marker,
    # it must NOT be short-circuited as identical.
    assert rel is not None
    assert conf > 0.0


def test_classify_relationship_short_trivial_texts_rejected():
    """
    Verify that trivial short texts without sufficient scientific content are rejected.
    """
    p1 = {"paper_id": "short1", "title": "AI models", "abstract": ""}
    p2 = {"paper_id": "short2", "title": "Deep learning", "abstract": ""}

    rel, conf, expl = classify_relationship(p1, p2)
    assert rel is None
    assert conf == 0.0
    assert expl == ""

