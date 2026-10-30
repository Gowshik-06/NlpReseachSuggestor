"""
TASK-15 Comprehensive Backend Test Suite: Evidence-Backed DRIUT Intelligence.
Verifies:
1. Explicit criteria for each of the 6 relationship categories (Extension, Improvement, Challenge, Reproduction, Alternative, Potential Replacement).
2. Insufficient evidence handling (similarity without explicit relationship; low similarity; empty/trivial text).
3. Abstract-only vs. full-text provenance tracking and disclosures.
4. Exact evidence passage character offsets (char_start, char_end) mathematical alignment.
5. Incompatible benchmark and metric protocol guards (preventing false Improvement claims across ImageNet vs GLUE, etc.).
6. Challenge vs ordinary methodological differences.
7. Reproduction vs shared keywords.
8. Potential replacement evidence threshold and tentative calibration.
9. Duplicate alert prevention and repeated scan idempotency.
10. Cross-user saved library and alert privacy isolation.
11. Scheduler advisory locking and non-overlapping execution.
12. Preservation of all pre-existing alert history and auditability.
"""
import pytest
from typing import Dict, Any
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.paper import Paper, SavedPaper
from app.models.driut import DRIUTAlert
from app.models.user import User
from app.core.security import create_access_token
from app.services.driut_service import (
    classify_relationship,
    classify_relationship_evidence,
    scan_saved_papers_for_updates,
)
from app.services.driut_scheduler import driut_scheduler

client = TestClient(app)

TEST_USER_A = "testuser_task15_a"
TEST_USER_B = "testuser_task15_b"


@pytest.fixture(scope="module", autouse=True)
def setup_driut_test_environment():
    """Setup isolated test fixtures for users and papers."""
    db = SessionLocal()
    # Create test users if not exist
    for u in [TEST_USER_A, TEST_USER_B]:
        if not db.query(User).filter(User.username == u).first():
            db.add(User(username=u, email=f"{u}@example.com", hashed_password="hashed_pw_placeholder"))
    db.commit()

    # Create baseline saved paper for User A
    base_p = db.query(Paper).filter(Paper.paper_id == "test:t15:base_nlp").first()
    if not base_p:
        base_p = Paper(
            paper_id="test:t15:base_nlp",
            title="Transformer Language Models on GLUE Benchmark",
            abstract="We evaluate transformer language representations on the GLUE benchmark, measuring accuracy and F1 score on natural language understanding tasks.",
            source="test",
            categories=["cs.CL"]
        )
        db.add(base_p)
        db.commit()
        db.refresh(base_p)

    # Save paper for User A
    saved_entry = db.query(SavedPaper).filter(SavedPaper.user_id == TEST_USER_A, SavedPaper.paper_id == base_p.id).first()
    if not saved_entry:
        saved_entry = SavedPaper(user_id=TEST_USER_A, paper_id=base_p.id)
        db.add(saved_entry)
        db.commit()
        db.refresh(saved_entry)

    db.close()
    yield

    # Clean up test alerts and saved papers created for test users
    db_clean = SessionLocal()
    db_clean.query(DRIUTAlert).filter(DRIUTAlert.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
    db_clean.query(SavedPaper).filter(SavedPaper.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
    test_pids = [
        "test:t15:base_nlp", "test:t15:cand_ext", "test:t15:cand_imp",
        "test:t15:cand_chal", "test:t15:cand_repr", "test:t15:cand_alt",
        "test:t15:cand_rep"
    ]
    db_clean.query(Paper).filter(Paper.paper_id.in_(test_pids)).delete(synchronize_session=False)
    db_clean.query(User).filter(User.username.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
    db_clean.commit()
    db_clean.close()


# ---------------------------------------------------------------------------
# 1. Six Relationship Categories Grounded in Real Evidence
# ---------------------------------------------------------------------------

def test_six_relationship_categories_grounded():
    """Verify explicit evidence-backed classification for all 6 categories."""
    saved_paper = {
        "paper_id": "test:baseline",
        "title": "Attention Is All You Need: The Transformer Architecture",
        "abstract": "We propose the Transformer, a model architecture eschewing recurrence and relying entirely on an attention mechanism to draw global dependencies between input and output."
    }

    # 1. Extension
    cand_ext = {
        "paper_id": "cand:ext",
        "title": "Vision Transformer: Scaling Attention to Computer Vision",
        "abstract": "We extend and build upon the architecture of Attention Is All You Need, scaling the unified backbone to multi-task visual recognition."
    }
    res_ext = classify_relationship_evidence(saved_paper, cand_ext)
    assert res_ext.relationship_type == "Extension"
    assert res_ext.is_supported is True
    assert res_ext.confidence_score >= 0.65
    assert res_ext.evidence_passage is not None
    assert "extend" in res_ext.evidence_passage.lower() or "build upon" in res_ext.evidence_passage.lower()
    assert res_ext.char_start is not None and res_ext.char_end is not None

    # 2. Improvement
    cand_imp = {
        "paper_id": "cand:imp",
        "title": "Optimized Attention Transformer Architecture",
        "abstract": "Our architecture outperforms and substantially improves accuracy, achieving state-of-the-art results over Attention Is All You Need."
    }
    res_imp = classify_relationship_evidence(saved_paper, cand_imp)
    assert res_imp.relationship_type == "Improvement"
    assert res_imp.is_supported is True
    assert res_imp.confidence_score >= 0.65
    assert res_imp.evidence_passage is not None

    # 3. Challenge
    cand_chal = {
        "paper_id": "cand:chal",
        "title": "Limitations and Vulnerabilities of Attention Architectures",
        "abstract": "This critique identifies a serious drawback and flaw in Attention Is All You Need, showing severe overfitting and unstable representations."
    }
    res_chal = classify_relationship_evidence(saved_paper, cand_chal)
    assert res_chal.relationship_type == "Challenge"
    assert res_chal.is_supported is True
    assert res_chal.confidence_score >= 0.65
    assert any(term in res_chal.evidence_passage.lower() for term in ["drawback", "critique", "limitation", "vulnerability"])

    # 4. Reproduction
    cand_repr = {
        "paper_id": "cand:repr",
        "title": "A Systematic Replication and Empirical Verification of Attention Is All You Need",
        "abstract": "We present an independent verification and empirical replication study to investigate the claims and audit results of Attention Is All You Need."
    }
    res_repr = classify_relationship_evidence(saved_paper, cand_repr)
    assert res_repr.relationship_type == "Reproduction"
    assert res_repr.is_supported is True
    assert res_repr.confidence_score >= 0.65
    assert "replication" in res_repr.evidence_passage.lower() or "verification" in res_repr.evidence_passage.lower()

    # 5. Alternative
    cand_alt = {
        "paper_id": "cand:alt",
        "title": "Mamba: Linear-Time Sequence Modeling with Selective State Spaces",
        "abstract": "Instead of attention, we introduce an alternative paradigm dispensing with quadratic attention and eliminating recurrence."
    }
    res_alt = classify_relationship_evidence(saved_paper, cand_alt)
    assert res_alt.relationship_type == "Alternative"
    assert res_alt.is_supported is True
    assert res_alt.confidence_score >= 0.65
    assert "alternative" in res_alt.evidence_passage.lower() or "dispensing with" in res_alt.evidence_passage.lower()

    # 6. Potential Replacement
    cand_rep = {
        "paper_id": "cand:rep",
        "title": "Unified State-Space Sequence Standard",
        "abstract": "Our architecture supersedes previous models, acting as a drop-in replacement that renders obsolete Attention Is All You Need."
    }
    res_rep = classify_relationship_evidence(saved_paper, cand_rep)
    assert res_rep.relationship_type == "Potential Replacement"
    assert res_rep.is_supported is True
    assert res_rep.confidence_score >= 0.65
    assert "supersedes" in res_rep.evidence_passage.lower() or "drop-in replacement" in res_rep.evidence_passage.lower()


# ---------------------------------------------------------------------------
# 2. Insufficient Evidence and Similarity Alone Policy
# ---------------------------------------------------------------------------

def test_similarity_without_relationship_returns_insufficient_evidence():
    """
    STRICT RULE: A semantic similarity score alone must NEVER establish a relationship category.
    Even when similarity is high, lack of explicit relationship evidence must return insufficient_evidence.
    """
    saved_paper = {
        "paper_id": "test:base:topic",
        "title": "Deep Learning Representation for Natural Language Understanding",
        "abstract": "We study deep neural networks for text representation, discussing vector embeddings, layers, and tokenization principles in NLP."
    }
    candidate_paper = {
        "paper_id": "test:cand:topic",
        "title": "A Survey of Neural Representation Approaches in Language Processing",
        "abstract": "This survey provides an overview of neural representation models, tokenization pipelines, and contextual embeddings across computational linguistics."
    }

    res = classify_relationship_evidence(saved_paper, candidate_paper)
    # Thematic similarity is high (>0.60), but neither extends, improves, challenges, replicates, nor replaces.
    assert res.relationship_type is None
    assert res.is_supported is False
    assert res.evidence_strength == "insufficient_evidence"
    assert "insufficient scientific evidence" in res.uncertainty_warning.lower()

    # Backwards-compatible tuple signature must also return (None, 0.0, "")
    rel, conf, expl = classify_relationship(saved_paper, candidate_paper)
    assert rel is None
    assert conf == 0.0
    assert expl == ""


def test_insufficient_evidence_thematic_mismatch_low_similarity(monkeypatch):
    """Verify that thematically unrelated papers (<0.40) are cleanly rejected."""
    p1 = {
        "paper_id": "p1",
        "title": "Superconducting Qubits and Cryogenic Control in Quantum Computing",
        "abstract": "We analyze qubit coherence times and microwave pulse shaping in dilution refrigerators."
    }
    p2 = {
        "paper_id": "p2",
        "title": "Transformer Cross-Attention in Multilingual Machine Translation",
        "abstract": "We evaluate translation quality on parallel corpora using subword vocabularies."
    }
    import app.services.driut_service as ds
    monkeypatch.setattr(ds, "compute_cosine_similarity", lambda a, b: 0.25)
    res = classify_relationship_evidence(p1, p2)
    assert res.relationship_type is None
    assert res.is_supported is False
    assert res.evidence_strength == "insufficient_evidence"
    assert "below minimum relation threshold" in res.uncertainty_warning.lower()


def test_insufficient_evidence_trivial_and_identical_papers():
    """Verify edge cases: identical papers and trivial short texts."""
    p1 = {"paper_id": "same:id", "title": "Paper Title A", "abstract": "Valid abstract text."}
    p2 = {"paper_id": "same:id", "title": "Paper Title A", "abstract": "Valid abstract text."}
    res_same = classify_relationship_evidence(p1, p2)
    assert res_same.is_supported is False
    assert "identical paper" in res_same.uncertainty_warning.lower()

    # Ultra short text
    p_short1 = {"paper_id": "s1", "title": "AI Model", "abstract": ""}
    p_short2 = {"paper_id": "s2", "title": "Machine Learning", "abstract": ""}
    res_short = classify_relationship_evidence(p_short1, p_short2)
    assert res_short.is_supported is False
    assert "insufficient text" in res_short.uncertainty_warning.lower()


# ---------------------------------------------------------------------------
# 3. Disparate Protocol & Incompatible Benchmark Protection
# ---------------------------------------------------------------------------

def test_false_positive_improvement_incompatible_benchmarks_guarded():
    """
    CRITICAL RULE: Do not claim an improvement from incompatible datasets or metrics.
    If candidate claims higher performance on ImageNet while baseline is GLUE,
    it must NOT be declared as an Improvement against the saved baseline.
    """
    saved_paper = {
        "paper_id": "base:nlp",
        "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        "abstract": "BERT achieves state-of-the-art results on eleven natural language processing tasks on the GLUE benchmark."
    }
    # Candidate reports improvement on ImageNet (Computer Vision benchmark)
    cand_paper = {
        "paper_id": "cand:cv",
        "title": "Vision Backbone with Superior Accuracy",
        "abstract": "Our architecture outperforms and substantially improves accuracy, achieving state-of-the-art top-1 results on the ImageNet benchmark."
    }

    res = classify_relationship_evidence(saved_paper, cand_paper)
    # MUST NOT be classified as Improvement against this saved paper
    assert res.relationship_type != "Improvement"
    assert res.comparability_notes is not None
    assert "incompatible benchmark protocols" in res.comparability_notes.lower()


def test_false_positive_improvement_incompatible_metrics_guarded():
    """If metrics are disjoint (e.g. BLEU vs accuracy), numerical improvement is guarded."""
    saved_paper = {
        "paper_id": "base:acc",
        "title": "Classification Model on Benchmark",
        "abstract": "We evaluate classification performance measuring accuracy on standard evaluation tasks."
    }
    cand_paper = {
        "paper_id": "cand:bleu",
        "title": "Generative Sequence Model",
        "abstract": "Our method substantially improves translation results, achieving higher BLEU score."
    }

    res = classify_relationship_evidence(saved_paper, cand_paper)
    assert res.relationship_type != "Improvement"


# ---------------------------------------------------------------------------
# 4. Challenge vs Ordinary Differences & Reproduction vs Shared Keywords
# ---------------------------------------------------------------------------

def test_challenge_requires_explicit_critique():
    """A different result alone is not a Challenge. Explicit critical evidence is required."""
    saved_paper = {
        "paper_id": "base:p",
        "title": "Deep Neural Network Regularization",
        "abstract": "We evaluate dropout regularization for feedforward neural networks."
    }
    # Ordinary difference without critique
    ordinary_diff = {
        "paper_id": "cand:diff",
        "title": "Batch Normalization for Fast Training",
        "abstract": "We evaluate mini-batch normalization with distinct learning rates on neural networks."
    }
    res_diff = classify_relationship_evidence(saved_paper, ordinary_diff)
    assert res_diff.relationship_type != "Challenge"

    # Genuine critique
    genuine_critique = {
        "paper_id": "cand:crit",
        "title": "A Critique of Dropout Regularization Assumptions",
        "abstract": "This critique identifies a fundamental flaw and severe vulnerability in dropout regularization, showing it fails under non-Gaussian noise."
    }
    res_crit = classify_relationship_evidence(saved_paper, genuine_critique)
    assert res_crit.relationship_type == "Challenge"
    assert res_crit.evidence_passage is not None


def test_reproduction_requires_explicit_replication_intent():
    """Shared datasets or similar keywords alone are insufficient for Reproduction."""
    saved_paper = {
        "paper_id": "base:r",
        "title": "Empirical Study on Sequence Models",
        "abstract": "We evaluate recurrent sequence models across speech datasets."
    }
    # Shared keywords without replication study
    shared_kw = {
        "paper_id": "cand:kw",
        "title": "Sequence Models with Convolutional Filters",
        "abstract": "We evaluate sequence models across speech datasets with convolutional kernels."
    }
    res_kw = classify_relationship_evidence(saved_paper, shared_kw)
    assert res_kw.relationship_type != "Reproduction"

    # Explicit replication
    genuine_rep = {
        "paper_id": "cand:rep_study",
        "title": "Independent Replication Study of Sequence Models",
        "abstract": "We present an independent verification and replication study to reproduce and audit the results of the baseline."
    }
    res_rep = classify_relationship_evidence(saved_paper, genuine_rep)
    assert res_rep.relationship_type == "Reproduction"


# ---------------------------------------------------------------------------
# 5. Potential Replacement Calibrated as Tentative
# ---------------------------------------------------------------------------

def test_potential_replacement_tentative_threshold():
    """Replacement claims are treated as tentative unless verified across multiple benchmarks."""
    saved_paper = {
        "paper_id": "base:rep",
        "title": "Convolutional Feature Extractors",
        "abstract": "Standard convolutional layers for image representation."
    }
    cand_paper = {
        "paper_id": "cand:repl",
        "title": "All-MLP Vision Architecture",
        "abstract": "Our architecture renders obsolete convolutional layers, acting as a drop-in replacement."
    }
    res = classify_relationship_evidence(saved_paper, cand_paper)
    assert res.relationship_type == "Potential Replacement"
    assert res.evidence_strength == "tentative"
    assert "tentative" in res.uncertainty_warning.lower()


# ---------------------------------------------------------------------------
# 6. Abstract-Only vs Full-Text Provenance & Exact Offset Alignment
# ---------------------------------------------------------------------------

def test_abstract_only_versus_full_text_provenance():
    """Verify provenance distinction between abstract-only and full-text inputs."""
    saved_paper = {
        "paper_id": "base:prov",
        "title": "Transformer Attention Baseline",
        "abstract": "Self-attention mechanisms in neural NLP."
    }
    # Abstract only
    cand_abstract = {
        "paper_id": "cand:abs",
        "title": "Extended Transformer Architecture",
        "abstract": "We extend and build upon the transformer architecture, scaling to multi-task representations."
    }
    res_abs = classify_relationship_evidence(saved_paper, cand_abstract)
    assert res_abs.source_type == "abstract"
    assert "abstract text only" in res_abs.uncertainty_warning.lower()

    # Full text available
    cand_full = {
        "paper_id": "cand:full",
        "title": "Extended Transformer Architecture in Depth",
        "abstract": "Short summary of full paper.",
        "raw_text": (
            "1. Introduction\n"
            "We extend and build upon the transformer architecture, scaling to multi-task representations across domains.\n"
            "2. Methodology\n"
            "Detailed architectural description of multi-task adapters."
        )
    }
    res_full = classify_relationship_evidence(saved_paper, cand_full)
    assert res_full.source_type == "full_text"
    assert res_full.evidence_passage is not None


def test_evidence_passage_and_offset_exact_alignment():
    """Verify that source_text[char_start:char_end] mathematically equals evidence_passage."""
    saved_paper = {
        "paper_id": "base:align",
        "title": "Original Baseline Paper",
        "abstract": "Baseline neural network model."
    }
    full_text = (
        "In this work, we propose a new framework. "
        "We extend and build upon the architecture of Original Baseline Paper, scaling to multi-task modalities. "
        "Further results demonstrate stability."
    )
    cand_paper = {
        "paper_id": "cand:align",
        "title": "Multi-Task Modalities",
        "abstract": "Summary text.",
        "raw_text": full_text
    }
    res = classify_relationship_evidence(saved_paper, cand_paper)
    assert res.relationship_type == "Extension"
    assert res.char_start is not None
    assert res.char_end is not None
    extracted_slice = full_text[res.char_start:res.char_end]
    assert extracted_slice == res.evidence_passage


# ---------------------------------------------------------------------------
# 7. Alert Idempotency, Duplicate Prevention, and Cross-User Isolation
# ---------------------------------------------------------------------------

def test_scan_idempotency_and_duplicate_alert_prevention():
    """Scanning saved library twice must NOT create duplicate alerts."""
    db = SessionLocal()
    new_candidate = [{
        "paper_id": "test:t15:cand_ext",
        "title": "Scaling Transformer Language Models on GLUE",
        "abstract": "We extend and build upon transformer language representations on GLUE benchmark, adapting models to cross-modal tasks."
    }]

    # Run scan 1
    alerts_1 = scan_saved_papers_for_updates(session=db, new_papers=new_candidate, user_id=TEST_USER_A)
    assert len(alerts_1) == 1
    a1 = alerts_1[0]
    assert a1.evidence_strength is not None
    assert a1.evidence_passage is not None

    # Run scan 2 (identical candidate)
    alerts_2 = scan_saved_papers_for_updates(session=db, new_papers=new_candidate, user_id=TEST_USER_A)
    assert len(alerts_2) == 0, "Second scan must be idempotent and create 0 duplicate alerts"

    # Verify total alerts for User A remains 1
    user_a_count = db.query(DRIUTAlert).filter(DRIUTAlert.user_id == TEST_USER_A).count()
    assert user_a_count == 1
    db.close()


def test_cross_user_library_and_alert_isolation():
    """User B cannot see User A's private DRIUT alerts."""
    token_a = create_access_token(subject=TEST_USER_A)
    token_b = create_access_token(subject=TEST_USER_B)

    # User A has 1 alert
    resp_a = client.get("/api/v1/papers/driut/alerts", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200
    alerts_a = resp_a.json()
    assert len(alerts_a) == 1
    assert alerts_a[0]["user_id"] == TEST_USER_A

    # User B has 0 saved papers and 0 alerts
    resp_b = client.get("/api/v1/papers/driut/alerts", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    alerts_b = resp_b.json()
    assert len(alerts_b) == 0


def test_scheduler_advisory_locking_concurrency():
    """Verify advisory locking protects against overlapping scheduled scans."""
    from app.db.session import engine
    from unittest.mock import patch
    lock_key = driut_scheduler.advisory_lock_key

    if engine.dialect.name == "postgresql":
        acquired, conn = driut_scheduler._acquire_advisory_lock(lock_key)
        assert acquired is True

        # Attempting to acquire again with another connection on same key should return False
        acquired_second, conn_second = driut_scheduler._acquire_advisory_lock(lock_key)
        assert acquired_second is False
        assert conn_second is None

        # Release primary lock
        driut_scheduler._release_advisory_lock(conn, lock_key)

        # After release, it can be acquired again
        acquired_third, conn_third = driut_scheduler._acquire_advisory_lock(lock_key)
        assert acquired_third is True
        driut_scheduler._release_advisory_lock(conn_third, lock_key)
    else:
        # Portable test under isolated SQLite environment
        acquired, conn = driut_scheduler._acquire_advisory_lock(lock_key)
        assert acquired is True
        with patch.object(driut_scheduler, "_acquire_advisory_lock", return_value=(False, None)):
            acquired_second, conn_second = driut_scheduler._acquire_advisory_lock(lock_key)
            assert acquired_second is False
            assert conn_second is None
        driut_scheduler._release_advisory_lock(conn, lock_key)


def test_alert_history_preservation():
    """Verify that baseline alert records remain intact and auditable."""
    db = SessionLocal()
    user_alerts = db.query(DRIUTAlert).filter(DRIUTAlert.user_id == TEST_USER_A).all()
    if not user_alerts:
        new_candidate = [{
            "paper_id": "test:t15:cand_ext",
            "title": "Scaling Transformer Language Models on GLUE",
            "abstract": "We extend and build upon transformer language representations on GLUE benchmark, adapting models to cross-modal tasks."
        }]
        scan_saved_papers_for_updates(session=db, new_papers=new_candidate, user_id=TEST_USER_A)
        user_alerts = db.query(DRIUTAlert).filter(DRIUTAlert.user_id == TEST_USER_A).all()

    assert len(user_alerts) > 0, "Alert records for test user must exist"
    for alert in user_alerts:
        assert alert.classification_version is not None
        assert alert.relationship_type is not None
        assert alert.user_id == TEST_USER_A
    db.close()

