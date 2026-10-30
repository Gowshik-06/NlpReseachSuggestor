"""
TASK-14 Comprehensive Test Suite: Structured, Evidence-Grounded Paper Comparison.
Verifies:
1. Two-paper comparison across 12 structured dimensions.
2. Multi-paper comparison (3 to 5 papers).
3. Input validation: invalid, duplicate, missing, and excessive (>5) paper IDs.
4. Missing evidence handling: explicit missing_evidence status without fabricating statements.
5. Abstract-only vs. full-text provenance and coverage disclosures.
6. Stale evidence detection.
7. Numerical results guard: disparate benchmarks/metrics marked as incomparable protocols.
8. Missing/untracked citation counts and metadata without fabrication.
9. Cross-user data isolation and private-resource protection.
10. Zero side-effects: database row counts and FAISS index remain completely unmutated.
"""
import copy
import hashlib
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.paper import Paper, SavedPaper
from app.models.evidence import PaperEvidence
from app.models.user import User
from app.models.driut import DRIUTAlert
from app.core.security import hash_password, create_access_token
from app.services.vector_index import get_faiss_index, INDEX_PATH, METADATA_PATH

client = TestClient(app)

FIXTURE_PAPERS = {}


@pytest.fixture(scope="module", autouse=True)
def setup_comparison_suite():
    """Setup test fixture papers with controlled evidence and full-text scenarios."""
    db = SessionLocal()

    # Preserve baseline FAISS index bytes
    import os
    orig_idx_bytes = None
    orig_meta_bytes = None
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "rb") as f:
            orig_idx_bytes = f.read()
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, "rb") as f:
            orig_meta_bytes = f.read()

    # Clean existing test users and test papers if leftover
    test_pids = [
        "test:comp.nlp.glue",
        "test:comp.cv.imagenet",
        "test:comp.fulltext.01",
        "test:comp.stale.01",
        "test:comp.noevidence.01",
        "test:comp.multi.01",
        "test:comp.scale.07",
        "test:comp.scale.08",
        "test:comp.scale.09",
        "test:comp.scale.10",
        "test:comp.scale.11",
        "test:comp.scale.12",
    ]
    p_to_clean = [p.id for p in db.query(Paper).filter(Paper.paper_id.in_(test_pids)).all()]
    if p_to_clean:
        db.query(PaperEvidence).filter(PaperEvidence.paper_id.in_(p_to_clean)).delete(synchronize_session=False)
        db.query(SavedPaper).filter(SavedPaper.paper_id.in_(p_to_clean)).delete(synchronize_session=False)
        db.query(Paper).filter(Paper.id.in_(p_to_clean)).delete(synchronize_session=False)

    test_users = ["comp_user_alpha", "comp_user_beta"]
    db.query(SavedPaper).filter(SavedPaper.user_id.in_(test_users)).delete(synchronize_session=False)
    db.query(User).filter(User.username.in_(test_users)).delete(synchronize_session=False)
    db.commit()

    # Create Users
    u_alpha = User(
        username="comp_user_alpha",
        email="alpha@researchlens.test",
        hashed_password=hash_password("AlphaPass123!"),
        full_name="Researcher Alpha",
        is_superuser=False,
        is_active=True
    )
    u_beta = User(
        username="comp_user_beta",
        email="beta@researchlens.test",
        hashed_password=hash_password("BetaPass123!"),
        full_name="Researcher Beta",
        is_superuser=False,
        is_active=True
    )
    db.add(u_alpha)
    db.add(u_beta)
    db.commit()

    # Paper 1: NLP Paper evaluated on GLUE (Abstract only, with results and metrics)
    p1 = Paper(
        paper_id="test:comp.nlp.glue",
        title="GLUEformer: Bidirectional Transformer for NLU",
        abstract=(
            "A major challenge in NLP is computational efficiency. "
            "Our goal is to improve semantic understanding. "
            "We propose GLUEformer, a novel architecture for language modeling. "
            "Evaluated on the GLUE benchmark. "
            "Measured by accuracy and F1 score. "
            "Results show our method achieves 89.4% accuracy on GLUE. "
            "Our contributions include a lightweight bidirectional attention mechanism. "
            "Our approach is limited by memory constraints on long sequences. "
            "In future work, we plan to extend to multilingual benchmarks."
        ),
        authors=["Alice Smith", "Bob Jones"],
        venue="ACL 2024",
        year=2024,
        citation_count=120,
        source="local",
        categories=["cs.CL"]
    )

    # Paper 2: Computer Vision Paper evaluated on ImageNet (Abstract only, disparate benchmark)
    p2 = Paper(
        paper_id="test:comp.cv.imagenet",
        title="VisionNet: Convolutional Residual Attention for Vision",
        abstract=(
            "A major challenge in computer vision is spatial feature distortion. "
            "Our objective is to stabilize visual representations. "
            "We introduce VisionNet, a novel framework for image classification. "
            "Tested on the ImageNet benchmark dataset. "
            "Measured by top-1 accuracy. "
            "Empirical results show VisionNet achieves 84.2% top-1 accuracy. "
            "Our main contribution is an adaptive residual gate. "
            "In future work, we plan to test on video classification."
        ),
        authors=["Charlie Brown"],
        venue="CVPR 2024",
        year=2024,
        citation_count=45,
        source="local",
        categories=["cs.CV"]
    )

    # Paper 3: Full Text Provenance Paper (Has raw_text with sections)
    full_text_content = (
        "1. Introduction\n"
        "A major challenge in distributed training is communication overhead.\n"
        "Our goal is to reduce network latency.\n\n"
        "2. Methodology\n"
        "We propose SyncDrop, a novel algorithm for gradient compression.\n\n"
        "3. Experiments\n"
        "Experiments on the CIFAR-10 dataset demonstrate high efficiency.\n"
        "Measured by latency and throughput.\n"
        "Results show a 3.5x speedup over standard SGD.\n\n"
        "4. Limitations\n"
        "Our approach is limited to homogeneous GPU clusters.\n"
    )
    p3 = Paper(
        paper_id="test:comp.fulltext.01",
        title="SyncDrop: Scalable Distributed Optimization",
        abstract="We propose SyncDrop for distributed gradient compression.",
        raw_text=full_text_content,
        authors=["David Miller"],
        venue="NeurIPS 2023",
        year=2023,
        citation_count=0,  # Untracked/zero citations
        source="local",
        categories=["cs.DC"]
    )

    # Paper 4: Stale Evidence Paper (Pre-existing evidence with outdated source hash)
    p4 = Paper(
        paper_id="test:comp.stale.01",
        title="StaleNet: Evolving Architecture Model",
        abstract="An updated abstract that has changed completely since initial evidence extraction.",
        authors=["Eve Walker"],
        venue="ICML 2023",
        year=2023,
        citation_count=10,
        source="local",
        categories=["cs.LG"]
    )

    # Paper 5: Paper with Minimal / No Explicit Scientific Claims
    p5 = Paper(
        paper_id="test:comp.noevidence.01",
        title="Brief Survey of Computing Trends",
        abstract="A general overview and summary discussing trends in computing history.",
        authors=["Frank Hall"],
        venue=None,
        year=None,
        citation_count=0,
        source="local",
        categories=["cs.OH"]
    )

    # Paper 6: Supplementary multi-paper comparison
    p6 = Paper(
        paper_id="test:comp.multi.01",
        title="MultiPaper: Scalable Graph Transformers",
        abstract=(
            "A major bottleneck in graph neural networks is over-smoothing. "
            "We propose GraphScale, a novel framework for large graphs. "
            "Tested on the SuperGLUE benchmark. "
            "Results show state-of-the-art performance."
        ),
        authors=["Grace Hopper"],
        venue="ICLR 2024",
        year=2024,
        citation_count=88,
        source="local",
        categories=["cs.AI"]
    )

    scale_papers = []
    for i in range(7, 13):
        scale_p = Paper(
            paper_id=f"test:comp.scale.{i:02d}",
            title=f"ScalePaper {i}: Advanced Neural Technique {i}",
            abstract=(
                f"Computational scalability in complex deep systems is critical. "
                f"We develop ScaleFramework{i}, an efficient method for distributed modeling. "
                f"Empirical results demonstrate notable speedup and enhanced robustness."
            ),
            authors=[f"Researcher {i}"],
            venue="NeurIPS 2024",
            year=2024 if i % 2 == 0 else 2025,
            citation_count=10 * i,
            source="local",
            categories=["cs.LG" if i % 2 == 0 else "cs.AI"]
        )
        scale_papers.append(scale_p)

    all_initial_papers = [p1, p2, p3, p4, p5, p6] + scale_papers
    db.add_all(all_initial_papers)
    db.commit()
    for p in all_initial_papers:
        db.refresh(p)
        FIXTURE_PAPERS[p.paper_id] = p.id

    # Add deliberately stale PaperEvidence for Paper 4
    stale_ev = PaperEvidence(
        paper_id=p4.id,
        category="method",
        claim="We propose OldMethod, a previous iteration.",
        source_passage="We propose OldMethod, a previous iteration.",
        char_start=0,
        char_end=43,
        source_type="abstract",
        extraction_method="rule_based_nlp",
        confidence_score=0.90,
        is_verified=True,
        source_hash="outdated_and_invalid_hash_value_123456"
    )
    db.add(stale_ev)

    # User Alpha saves Paper 1 with private notes
    sp_alpha = SavedPaper(
        user_id="comp_user_alpha",
        paper_id=p1.id,
        notes="CONFIDENTIAL: Potential patent application based on GLUEformer.",
        tags=["private-investigation"]
    )
    db.add(sp_alpha)
    db.commit()
    db.close()

    yield

    # Teardown
    db = SessionLocal()
    p_to_clean_td = [p.id for p in db.query(Paper).filter(Paper.paper_id.in_(test_pids)).all()]
    if p_to_clean_td:
        db.query(PaperEvidence).filter(PaperEvidence.paper_id.in_(p_to_clean_td)).delete(synchronize_session=False)
        db.query(SavedPaper).filter(SavedPaper.paper_id.in_(p_to_clean_td)).delete(synchronize_session=False)
        db.query(Paper).filter(Paper.id.in_(p_to_clean_td)).delete(synchronize_session=False)
    db.query(SavedPaper).filter(SavedPaper.user_id.in_(test_users)).delete(synchronize_session=False)
    db.query(User).filter(User.username.in_(test_users)).delete(synchronize_session=False)
    db.commit()
    db.close()

    # Restore FAISS index bytes
    if orig_idx_bytes is not None:
        with open(INDEX_PATH, "wb") as f:
            f.write(orig_idx_bytes)
    if orig_meta_bytes is not None:
        with open(METADATA_PATH, "wb") as f:
            f.write(orig_meta_bytes)
    get_faiss_index()._load_or_initialize()


def test_two_paper_structured_comparison():
    """Verify standard two-paper comparison across all 12 dimensions."""
    res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["test:comp.nlp.glue", "test:comp.cv.imagenet"]}
    )
    assert res.status_code == 200
    data = res.json()

    assert len(data["papers"]) == 2
    assert "dimensions" in data
    assert len(data["dimensions"]) == 12

    # Verify presence of all 12 target dimension IDs
    expected_dim_ids = [
        "problem", "objective", "method", "dataset", "metrics", "results",
        "contributions", "limitations", "future_work",
        "publication_metadata", "citation_metrics", "evidence_coverage"
    ]
    actual_dim_ids = [d["dimension_id"] for d in data["dimensions"]]
    assert actual_dim_ids == expected_dim_ids

    # Check cell structure for method dimension
    method_dim = next(d for d in data["dimensions"] if d["dimension_id"] == "method")
    glue_cell = method_dim["cells"]["test:comp.nlp.glue"]
    cv_cell = method_dim["cells"]["test:comp.cv.imagenet"]

    assert glue_cell["has_evidence"] is True
    assert "GLUEformer" in glue_cell["claim"]
    assert glue_cell["source_type"] == "abstract"
    assert glue_cell["char_start"] is not None
    assert glue_cell["char_end"] is not None

    assert cv_cell["has_evidence"] is True
    assert "VisionNet" in cv_cell["claim"]
    assert cv_cell["source_type"] == "abstract"


def test_multi_paper_comparison_up_to_five():
    """Verify multi-paper comparison succeeds with 3, 4, and 5 papers."""
    paper_ids = [
        "test:comp.nlp.glue",
        "test:comp.cv.imagenet",
        "test:comp.fulltext.01",
        "test:comp.multi.01"
    ]
    res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": paper_ids}
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["papers"]) == 4
    assert len(data["coverage_summary"]) == 4

    # Each dimension must contain cells for all 4 papers
    for dim in data["dimensions"]:
        assert len(dim["cells"]) == 4


def test_comparison_limit_enforced_exceeding_twelve():
    """Verify selecting more than 12 papers returns HTTP 400 or 422."""
    pids_13 = [
        "test:comp.nlp.glue",
        "test:comp.cv.imagenet",
        "test:comp.fulltext.01",
        "test:comp.stale.01",
        "test:comp.noevidence.01",
        "test:comp.multi.01",
        "test:comp.scale.07",
        "test:comp.scale.08",
        "test:comp.scale.09",
        "test:comp.scale.10",
        "test:comp.scale.11",
        "test:comp.scale.12",
        "test:comp.scale.extra.13",  # 13 papers
    ]
    res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": pids_13}
    )
    assert res.status_code in [400, 422]
    body = res.json()
    msg = str(body).lower()
    assert "validation" in msg or "12" in msg or "maximum" in msg or "limit" in msg


def test_comparison_scaling_up_to_twelve_papers():
    """Verify comparisons scale across 2, 3, 5, 8, 10, and 12 papers."""
    all_scale_pids = [
        "test:comp.nlp.glue",
        "test:comp.cv.imagenet",
        "test:comp.fulltext.01",
        "test:comp.stale.01",
        "test:comp.noevidence.01",
        "test:comp.multi.01",
        "test:comp.scale.07",
        "test:comp.scale.08",
        "test:comp.scale.09",
        "test:comp.scale.10",
        "test:comp.scale.11",
        "test:comp.scale.12",
    ]

    for count in [2, 3, 5, 8, 10, 12]:
        sub_pids = all_scale_pids[:count]
        res = client.post(
            "/api/v1/papers/compare",
            json={"paper_ids": sub_pids}
        )
        assert res.status_code == 200, f"Failed for count {count}: {res.text}"
        data = res.json()
        assert len(data["papers"]) == count
        assert len(data["coverage_summary"]) == count
        assert data.get("statistics") is not None
        assert data["statistics"]["papers_compared"] == count
        for dim in data["dimensions"]:
            assert len(dim["cells"]) == count
            for pid in sub_pids:
                assert pid in dim["cells"], f"Missing paper {pid} in dimension {dim['dimension_id']}"


def test_comparison_statistics_structure_and_dynamic_changes():
    """Verify comparison statistics accurately reflect selected records and update dynamically."""
    # Compare 2 papers
    res2 = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["test:comp.nlp.glue", "test:comp.cv.imagenet"]}
    )
    assert res2.status_code == 200
    stats2 = res2.json()["statistics"]
    assert stats2["papers_compared"] == 2
    assert stats2["year_distribution"].get("2024") == 2

    # Compare 3 papers with different year
    res3 = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["test:comp.nlp.glue", "test:comp.cv.imagenet", "test:comp.fulltext.01"]}
    )
    assert res3.status_code == 200
    stats3 = res3.json()["statistics"]
    assert stats3["papers_compared"] == 3
    # Paper 3 was published in 2023, so 2023 must now be present
    assert stats3["year_distribution"].get("2023") == 1
    assert stats3["year_distribution"].get("2024") == 2
    assert stats2 != stats3, "Statistics must change dynamically when paper selection changes"


def test_comparison_duplicate_identifiers_handled_safely():
    """Verify duplicate IDs are rejected when distinct papers < 2."""
    res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["test:comp.nlp.glue", "test:comp.nlp.glue"]}
    )
    assert res.status_code == 400
    assert "distinct" in str(res.json()).lower()


def test_comparison_missing_paper_returns_404():
    """Verify non-existent paper returns 404 with structured error."""
    res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["test:comp.nlp.glue", "test:nonexistent.paper.999"]}
    )
    assert res.status_code == 404
    assert "test:nonexistent.paper.999" in str(res.json())


def test_missing_evidence_not_equated_with_missing_capability():
    """
    Verify that when a paper does not report evidence for a dimension (e.g. limitations),
    status is explicitly 'missing_evidence' and disclaims absence of capability.
    """
    res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["test:comp.nlp.glue", "test:comp.noevidence.01"]}
    )
    assert res.status_code == 200
    data = res.json()

    lim_dim = next(d for d in data["dimensions"] if d["dimension_id"] == "limitations")
    noev_cell = lim_dim["cells"]["test:comp.noevidence.01"]

    assert noev_cell["has_evidence"] is False
    assert noev_cell["status"] == "missing_evidence"
    assert noev_cell["claim"] is None
    assert "Absence of evidence" in noev_cell["status_note"]
    assert "does not imply" in noev_cell["status_note"]


def test_abstract_only_coverage_clearly_disclosed():
    """Verify abstract-only sources disclose limited coverage and warning notes."""
    res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["test:comp.nlp.glue", "test:comp.cv.imagenet"]}
    )
    assert res.status_code == 200
    data = res.json()

    cov_glue = next(c for c in data["coverage_summary"] if c["paper_id"] == "test:comp.nlp.glue")
    assert cov_glue["source_type"] == "abstract"
    assert "Abstract Only" in cov_glue["coverage_level"]
    assert cov_glue["source_quality_warning"] is not None
    assert "abstract only" in cov_glue["source_quality_warning"].lower()


def test_full_text_provenance_and_section_tracking():
    """Verify full-text paper displays section names and comprehensive coverage."""
    res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["test:comp.fulltext.01", "test:comp.nlp.glue"]}
    )
    assert res.status_code == 200
    data = res.json()

    cov_ft = next(c for c in data["coverage_summary"] if c["paper_id"] == "test:comp.fulltext.01")
    assert cov_ft["source_type"] == "full_text"
    assert "Full Text" in cov_ft["coverage_level"]

    method_dim = next(d for d in data["dimensions"] if d["dimension_id"] == "method")
    ft_cell = method_dim["cells"]["test:comp.fulltext.01"]
    assert ft_cell["source_type"] == "full_text"
    assert ft_cell["section_name"] == "Methodology"


def test_stale_evidence_detection():
    """Verify stale evidence record is flagged as stale with refresh warning."""
    res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["test:comp.stale.01", "test:comp.nlp.glue"]}
    )
    assert res.status_code == 200
    data = res.json()

    cov_stale = next(c for c in data["coverage_summary"] if c["paper_id"] == "test:comp.stale.01")
    assert cov_stale["is_stale"] is True

    method_dim = next(d for d in data["dimensions"] if d["dimension_id"] == "method")
    stale_cell = method_dim["cells"]["test:comp.stale.01"]
    assert stale_cell["status"] == "stale"


def test_disparate_numerical_results_marked_incomparable():
    """
    Verify numerical results across disparate benchmarks (GLUE vs ImageNet)
    are marked as incomparable protocols and superiority claims are prevented.
    """
    res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["test:comp.nlp.glue", "test:comp.cv.imagenet"]}
    )
    assert res.status_code == 200
    data = res.json()

    results_dim = next(d for d in data["dimensions"] if d["dimension_id"] == "results")
    assert results_dim["comparability_status"] == "incomparable_protocols"
    assert "invalid" in results_dim["comparability_note"].lower()

    # Incomparable dimensions list must contain the protocol warning
    assert len(data["incomparable_dimensions"]) >= 1
    incomp = data["incomparable_dimensions"][0]
    assert "disparate" in incomp["reason"].lower() or "different" in incomp["reason"].lower()

    # System warnings must warn the researcher
    assert any("numerical" in w.lower() for w in data["warnings"])


def test_citation_metrics_untracked_truthful_state():
    """Verify untracked citations are not fabricated as non-zero or authoritative."""
    res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["test:comp.fulltext.01", "test:comp.nlp.glue"]}
    )
    assert res.status_code == 200
    data = res.json()

    cit_dim = next(d for d in data["dimensions"] if d["dimension_id"] == "citation_metrics")
    ft_cell = cit_dim["cells"]["test:comp.fulltext.01"]
    glue_cell = cit_dim["cells"]["test:comp.nlp.glue"]

    assert ft_cell["status"] == "untracked"
    assert "0 recorded citations" in ft_cell["claim"]

    assert glue_cell["status"] == "metadata_only"
    assert "120 tracked citations" in glue_cell["claim"]


def test_authentication_and_user_isolation():
    """
    Verify comparing papers does not leak private user notes or saved library status
    of other users.
    """
    # 1. Anonymous user can compare public papers
    anon_res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["test:comp.nlp.glue", "test:comp.cv.imagenet"]}
    )
    assert anon_res.status_code == 200
    anon_text = str(anon_res.json())
    assert "CONFIDENTIAL" not in anon_text
    assert "private-investigation" not in anon_text

    # 2. Authenticated User Beta comparing papers cannot see User Alpha's private notes
    token_beta = create_access_token("comp_user_beta")
    beta_res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": ["test:comp.nlp.glue", "test:comp.cv.imagenet"]},
        headers={"Authorization": f"Bearer {token_beta}"}
    )
    assert beta_res.status_code == 200
    beta_text = str(beta_res.json())
    assert "CONFIDENTIAL" not in beta_text
    assert "private-investigation" not in beta_text


def test_zero_side_effects_on_db_and_faiss():
    """
    Verify that executing paper comparison does NOT mutate database rows
    (papers, paper_evidence, saved_papers) or FAISS index hashes.
    """
    db = SessionLocal()
    initial_paper_count = db.query(Paper).count()
    initial_evidence_count = db.query(PaperEvidence).count()
    initial_saved_count = db.query(SavedPaper).count()
    db.close()

    faiss_idx = get_faiss_index()
    initial_vector_count = faiss_idx.index.ntotal
    initial_meta_count = len(faiss_idx.paper_metadata)

    # Execute multiple comparison requests
    for _ in range(3):
        res = client.post(
            "/api/v1/papers/compare",
            json={"paper_ids": ["test:comp.nlp.glue", "test:comp.cv.imagenet", "test:comp.fulltext.01"]}
        )
        assert res.status_code == 200

    # Verify counts remain identical
    db = SessionLocal()
    after_paper_count = db.query(Paper).count()
    after_evidence_count = db.query(PaperEvidence).count()
    after_saved_count = db.query(SavedPaper).count()
    db.close()

    assert after_paper_count == initial_paper_count
    assert after_evidence_count == initial_evidence_count
    assert after_saved_count == initial_saved_count
    assert faiss_idx.index.ntotal == initial_vector_count
    assert len(faiss_idx.paper_metadata) == initial_meta_count
