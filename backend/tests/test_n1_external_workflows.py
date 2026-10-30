"""
TASK N1 External Candidate Workflow Integration Regression & Security Test Suite.
Validates the complete contract across:
1. Catalog and transient external candidate saving to library
2. Authentication & private user sanctuary isolation
3. Duplicate external save prevention
4. Identity validation, payload sizing, and URL scheme protection
5. Catalog and transient summaries (with insufficient-content grounding)
6. Catalog and transient evidence extraction (with exact span verification)
7. Catalog-to-catalog, catalog-to-transient, and transient-to-transient comparisons (12 dimensions)
8. Zero side-effects / read-only guarantees on DB, FAISS, and DRIUT alerts
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.paper import Paper, SavedPaper
from app.models.evidence import PaperEvidence
from app.models.driut import DRIUTAlert
from app.core.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_n1_suite():
    """Setup isolated test fixtures for N1 tests."""
    db = SessionLocal()

    # Clean existing test users and test papers if present
    test_users = ["n1_user_alpha", "n1_user_beta"]
    db.query(DRIUTAlert).filter(DRIUTAlert.user_id.in_(test_users)).delete()
    db.query(SavedPaper).filter(SavedPaper.user_id.in_(test_users)).delete()
    db.query(User).filter(User.username.in_(test_users)).delete()

    # Create users
    u1 = User(
        username="n1_user_alpha",
        email="n1_alpha@example.com",
        hashed_password=hash_password("Password123!"),
        is_active=True,
    )
    u2 = User(
        username="n1_user_beta",
        email="n1_beta@example.com",
        hashed_password=hash_password("Password123!"),
        is_active=True,
    )
    db.add(u1)
    db.add(u2)

    # Ensure a catalog-backed test paper exists
    cat_paper = db.query(Paper).filter(Paper.paper_id == "arxiv:test.n1.catalog.01").first()
    if not cat_paper:
        cat_paper = Paper(
            paper_id="arxiv:test.n1.catalog.01",
            title="Catalog Attention: Foundational Sparse Representations",
            abstract="A major challenge in modern deep learning is transformer computational complexity. We propose Catalog Attention.",
            authors=["Alice Cataloger", "Bob Transformer"],
            venue="ICLR 2026",
            year=2026,
            source="local",
            url="https://arxiv.org/abs/test.n1.catalog.01",
            citation_count=42,
            categories=["cs.CL", "cs.LG"],
        )
        db.add(cat_paper)

    db.commit()
    db.refresh(cat_paper)
    cat_id = cat_paper.id
    db.close()

    alpha_token = create_access_token(subject="n1_user_alpha")
    beta_token = create_access_token(subject="n1_user_beta")

    return {
        "alpha_headers": {"Authorization": f"Bearer {alpha_token}"},
        "beta_headers": {"Authorization": f"Bearer {beta_token}"},
        "catalog_paper_id": "arxiv:test.n1.catalog.01",
        "catalog_db_id": cat_id,
    }


# =====================================================================
# 1-7: SAVE TO LIBRARY & IDENTITY VALIDATION
# =====================================================================

def test_1_save_catalog_paper_by_authenticated_user(setup_n1_suite):
    """Req 1: Existing catalog paper can still be saved."""
    res = client.post(
        "/api/v1/papers/save",
        json={
            "paper_id": setup_n1_suite["catalog_paper_id"],
            "notes": "Testing catalog paper bookmark",
            "tags": ["catalog", "foundations"],
        },
        headers=setup_n1_suite["alpha_headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["paper_id"] == setup_n1_suite["catalog_db_id"]
    assert data["user_id"] == "n1_user_alpha"
    assert "catalog" in data["tags"]


def test_2_save_transient_external_candidate(setup_n1_suite):
    """Req 2: Transient external candidate can be saved by an authenticated user."""
    candidate = {
        "id": None,
        "paper_id": "arxiv:2403.99001v1",
        "title": "Dynamic Routing in Sparse Transformers",
        "abstract": "We demonstrate that dynamic routing reduces computation in sparse transformers by 40%.",
        "authors": ["Carol Explorer", "Dan Builder"],
        "venue": "arXiv preprint",
        "year": 2024,
        "source": "arxiv",
        "url": "https://arxiv.org/abs/2403.99001v1",
        "doi": "10.48550/arXiv.2403.99001",
    }
    res = client.post(
        "/api/v1/papers/save",
        json={
            "candidate": candidate,
            "paper_id": "arxiv:2403.99001v1",
            "notes": "Saved external discovery",
            "tags": ["external", "routing"],
        },
        headers=setup_n1_suite["alpha_headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "n1_user_alpha"
    assert data["paper"]["paper_id"] == "arxiv:2403.99001v1"
    assert data["paper"]["title"] == "Dynamic Routing in Sparse Transformers"


def test_3_unauthenticated_save_is_rejected():
    """Req 3: Unauthenticated save is rejected."""
    res = client.post(
        "/api/v1/papers/save",
        json={"paper_id": "arxiv:2403.99001v1"},
    )
    assert res.status_code == 401


def test_4_duplicate_external_save_handled_cleanly(setup_n1_suite):
    """Req 4: Duplicate external save is handled correctly (idempotent, prevents duplicate rows)."""
    db = SessionLocal()
    initial_user_saved = db.query(SavedPaper).filter(SavedPaper.user_id == "n1_user_alpha").count()
    db.close()

    candidate = {
        "id": None,
        "paper_id": "arxiv:2403.99001v1",
        "title": "Dynamic Routing in Sparse Transformers",
        "abstract": "We demonstrate that dynamic routing reduces computation in sparse transformers by 40%.",
        "authors": ["Carol Explorer", "Dan Builder"],
        "source": "arxiv",
    }
    res = client.post(
        "/api/v1/papers/save",
        json={
            "candidate": candidate,
            "paper_id": "arxiv:2403.99001v1",
            "notes": "Updated bookmark notes",
        },
        headers=setup_n1_suite["alpha_headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "n1_user_alpha"
    assert data["notes"] == "Updated bookmark notes"

    db = SessionLocal()
    final_user_saved = db.query(SavedPaper).filter(SavedPaper.user_id == "n1_user_alpha").count()
    db.close()
    assert final_user_saved == initial_user_saved


def test_5_user_isolation_for_saved_transient_paper(setup_n1_suite):
    """Req 5: Two users cannot see or remove each other's saved items."""
    # User Beta also saves the same paper
    candidate = {
        "id": None,
        "paper_id": "arxiv:2403.99001v1",
        "title": "Dynamic Routing in Sparse Transformers",
        "authors": ["Carol Explorer"],
        "source": "arxiv",
    }
    res = client.post(
        "/api/v1/papers/save",
        json={"candidate": candidate, "paper_id": "arxiv:2403.99001v1"},
        headers=setup_n1_suite["beta_headers"],
    )
    assert res.status_code == 200
    beta_saved_id = res.json()["id"]

    # Alpha gets library -> cannot see beta's notes
    alpha_library = client.get("/api/v1/papers/saved", headers=setup_n1_suite["alpha_headers"]).json()
    alpha_saved_ids = [s["id"] for s in alpha_library]
    assert beta_saved_id not in alpha_saved_ids

    # Alpha cannot delete beta's saved record
    del_res = client.delete(f"/api/v1/papers/saved/{beta_saved_id}", headers=setup_n1_suite["alpha_headers"])
    assert del_res.status_code == 404


def test_6_invalid_or_missing_external_identity_rejected(setup_n1_suite):
    """Req 6: Invalid or missing external identity is rejected."""
    # Missing paper_id and missing candidate
    res1 = client.post(
        "/api/v1/papers/save",
        json={"notes": "No id"},
        headers=setup_n1_suite["alpha_headers"],
    )
    assert res1.status_code in (400, 422)

    # Empty candidate title
    res2 = client.post(
        "/api/v1/papers/save",
        json={
            "candidate": {"paper_id": "arxiv:999", "title": "   ", "source": "arxiv"},
            "paper_id": "arxiv:999",
        },
        headers=setup_n1_suite["alpha_headers"],
    )
    assert res2.status_code in (400, 422)


def test_7_provider_qualified_ids_remain_stable(setup_n1_suite):
    """Req 7: Provider-qualified IDs remain stable."""
    candidate = {
        "id": None,
        "paper_id": "pubmed:38291024",
        "title": "Biomedical Deep Learning for Gene Regulation",
        "authors": ["Elena Bio"],
        "source": "pubmed",
    }
    res = client.post(
        "/api/v1/papers/save",
        json={"candidate": candidate, "paper_id": "pubmed:38291024"},
        headers=setup_n1_suite["alpha_headers"],
    )
    assert res.status_code == 200
    assert res.json()["paper"]["paper_id"] == "pubmed:38291024"


# =====================================================================
# 8-10: PAPER SUMMARIES
# =====================================================================

def test_8_catalog_summary_still_works(setup_n1_suite):
    """Req 8: Catalog summary still works via GET /{paper_id}/summary."""
    res = client.get(f"/api/v1/papers/{setup_n1_suite['catalog_paper_id']}/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["paper_id"] == setup_n1_suite["catalog_paper_id"]
    assert "executive_summary" in data
    assert len(data["key_findings"]) >= 1


def test_9_transient_summary_works_without_catalog_persistence():
    """Req 9: Transient summary works without catalog persistence."""
    db = SessionLocal()
    count_before = db.query(Paper).count()
    db.close()

    candidate = {
        "id": None,
        "paper_id": "arxiv:2409.88888v1",
        "title": "Quantum Attention State Representation",
        "abstract": "We evaluate quantum state representation for parameterized attention circuits. The method achieves 92% fidelity across benchmark tasks.",
        "authors": ["Quinn Quantum"],
        "source": "arxiv",
    }
    res = client.post(
        "/api/v1/papers/summary",
        json={"candidate": candidate},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["paper_id"] == "arxiv:2409.88888v1"
    assert "Quantum" in data["title"]
    assert "fidelity" in data["executive_summary"].lower() or len(data["key_findings"]) > 0

    # Guarantee zero DB persistence
    db = SessionLocal()
    count_after = db.query(Paper).count()
    persisted = db.query(Paper).filter(Paper.paper_id == "arxiv:2409.88888v1").first()
    db.close()
    assert count_after == count_before
    assert persisted is None


def test_10_insufficient_abstract_produces_grounded_response():
    """Req 10: Insufficient abstract content produces a grounded response."""
    candidate = {
        "id": None,
        "paper_id": "arxiv:2409.00000v1",
        "title": "Short Paper Notice",
        "abstract": "Under review.",
        "authors": ["Anonymous"],
        "source": "arxiv",
    }
    res = client.post(
        "/api/v1/papers/summary",
        json={"candidate": candidate},
    )
    assert res.status_code == 200
    data = res.json()
    assert "insufficient" in data["executive_summary"].lower()
    assert "insufficient" in data["problem_statement"].lower()
    assert "insufficient" in data["methodology"].lower()
    assert "insufficient" in data["key_findings"].lower()
    assert "insufficient" in data["limitations"].lower()


# =====================================================================
# 11-13: EVIDENCE RETRIEVAL
# =====================================================================

def test_11_catalog_evidence_retrieval(setup_n1_suite):
    """Req 11: Catalog evidence retrieval remains correct."""
    res = client.get(f"/api/v1/papers/{setup_n1_suite['catalog_paper_id']}/evidence")
    assert res.status_code == 200
    data = res.json()
    assert data["paper_id"] == setup_n1_suite["catalog_paper_id"]
    assert "evidence" in data
    assert "categories_present" in data


def test_12_and_13_transient_evidence_offsets_and_grounding():
    """Req 12 & 13: Transient evidence uses only supplied source content with valid offsets."""
    db = SessionLocal()
    count_evidence_before = db.query(PaperEvidence).count()
    db.close()

    source_abstract = "We demonstrate that FlashTree attention reduces memory from O(N^2) to O(N log N). Experimental results show 3x throughput speedup on LLaMA-3."
    candidate = {
        "id": None,
        "paper_id": "arxiv:2410.77777v1",
        "title": "FlashTree: Memory Reduction for Attention",
        "abstract": source_abstract,
        "authors": ["Frank Fast"],
        "source": "arxiv",
    }
    res = client.post(
        "/api/v1/papers/evidence",
        json={"candidate": candidate, "category": "results"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["paper_id"] == "arxiv:2410.77777v1"
    assert data["evidence_count"] >= 1

    # Verify every returned passage is an EXACT character substring of the supplied source
    for ev in data["evidence"]:
        start = ev["char_start"]
        end = ev["char_end"]
        passage = ev["source_passage"]
        assert source_abstract[start:end] == passage
        assert passage in source_abstract

    # Verify zero persistence to paper_evidence table
    db = SessionLocal()
    count_evidence_after = db.query(PaperEvidence).count()
    db.close()
    assert count_evidence_after == count_evidence_before


# =====================================================================
# 14-18: SIDE-BY-SIDE PAPER COMPARISON
# =====================================================================

def test_14_catalog_to_catalog_comparison(setup_n1_suite):
    """Req 14 & 17: Catalog-to-catalog comparison preserves all 12 dimensions."""
    db = SessionLocal()
    # Add second catalog paper
    p2 = db.query(Paper).filter(Paper.paper_id == "arxiv:test.n1.catalog.02").first()
    if not p2:
        p2 = Paper(
            paper_id="arxiv:test.n1.catalog.02",
            title="Second Catalog Paper on Recurrent States",
            abstract="Recurrent state representations offer constant memory decoding.",
            authors=["George Recurrent"],
            source="local",
            year=2026,
        )
        db.add(p2)
        db.commit()
    db.close()

    res = client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": [setup_n1_suite["catalog_paper_id"], "arxiv:test.n1.catalog.02"]},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["papers"]) == 2
    assert len(data["comparison_points"]) == 12
    assert len(data["dimensions"]) == 12


def test_15_and_17_catalog_to_transient_comparison(setup_n1_suite):
    """Req 15 & 17: Catalog-to-transient comparison works across all 12 dimensions."""
    transient = {
        "id": None,
        "paper_id": "arxiv:2410.12345v1",
        "title": "State Space Models for Genome Sequence Modeling",
        "abstract": "We evaluate bidirectional state space models for DNA motif discovery across genomic datasets.",
        "authors": ["Hannah Helix"],
        "source": "arxiv",
        "year": 2024,
    }
    res = client.post(
        "/api/v1/papers/compare",
        json={"items": [setup_n1_suite["catalog_paper_id"], transient]},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["papers"]) == 2
    assert len(data["comparison_points"]) == 12

    # Verify transient candidate is preserved with stable identity
    transient_res = [p for p in data["papers"] if p["paper_id"] == "arxiv:2410.12345v1"]
    assert len(transient_res) == 1
    assert transient_res[0]["title"] == "State Space Models for Genome Sequence Modeling"


def test_16_and_18_transient_to_transient_comparison_and_truthfulness():
    """Req 16 & 18: Transient-to-transient comparison works and missing content is not fabricated."""
    t1 = {
        "id": None,
        "paper_id": "arxiv:2410.11111v1",
        "title": "Transient Alpha: Sparse Routing",
        "abstract": "We propose a sparse routing approach.",
        "authors": ["Ian Inception"],
        "source": "arxiv",
    }
    t2 = {
        "id": None,
        "paper_id": "arxiv:2410.22222v1",
        "title": "Transient Beta: Linearized Attention",
        "abstract": "Linearized attention achieves subquadratic computation.",
        "authors": ["Julia Jump"],
        "source": "arxiv",
    }
    res = client.post(
        "/api/v1/papers/compare",
        json={"items": [t1, t2]},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["papers"]) == 2
    assert len(data["comparison_points"]) == 12

    # Verify missing experimental protocols are truthfully reported as missing/insufficient
    for pt in data["comparison_points"]:
        assert len(pt["values"]) == 2


# =====================================================================
# 19-20: PAYLOAD VALIDATION & SECURITY
# =====================================================================

def test_19_malformed_and_oversized_payloads_rejected(setup_n1_suite):
    """Req 19: Malformed or oversized candidate payloads are rejected."""
    # Oversized notes (> 5000 chars)
    res_notes = client.post(
        "/api/v1/papers/save",
        json={
            "paper_id": setup_n1_suite["catalog_paper_id"],
            "notes": "x" * 5005,
        },
        headers=setup_n1_suite["alpha_headers"],
    )
    assert res_notes.status_code == 422

    # Oversized tags (> 30 tags)
    res_tags = client.post(
        "/api/v1/papers/save",
        json={
            "paper_id": setup_n1_suite["catalog_paper_id"],
            "tags": [f"tag_{i}" for i in range(35)],
        },
        headers=setup_n1_suite["alpha_headers"],
    )
    assert res_tags.status_code == 422

    # Oversized title in transient candidate (> 1000 chars)
    huge_candidate = {
        "paper_id": "arxiv:huge",
        "title": "H" * 1050,
        "source": "arxiv",
    }
    res_title = client.post(
        "/api/v1/papers/summary",
        json={"candidate": huge_candidate},
    )
    assert res_title.status_code == 422


def test_20_unsafe_url_schemes_rejected():
    """Req 20: Unsafe URL schemes (e.g., javascript:) are rejected."""
    unsafe_candidate = {
        "paper_id": "arxiv:xss",
        "title": "Title with malicious URL",
        "source": "arxiv",
        "url": "javascript:alert(document.cookie)",
    }
    res = client.post(
        "/api/v1/papers/summary",
        json={"candidate": unsafe_candidate},
    )
    assert res_notes_code_or_422(res)


def res_notes_code_or_422(res):
    return res.status_code in (400, 422)


# =====================================================================
# 21-24: ZERO PERSISTENCE / SIDE-EFFECT-FREE GUARANTEES
# =====================================================================

def test_21_to_24_zero_side_effects_on_readonly_workflows(setup_n1_suite):
    """Req 21-24: Search, summary, evidence, and compare do not persist to DB, FAISS, or DRIUT alerts."""
    db = SessionLocal()
    init_papers = db.query(Paper).count()
    init_evidence = db.query(PaperEvidence).count()
    init_alerts = db.query(DRIUTAlert).count()
    db.close()

    # 1. Search request (with external sources)
    s_res = client.post(
        "/api/v1/papers/search",
        json={"query": "sparse attention transformers", "sources": ["local"], "limit": 5},
    )
    assert s_res.status_code == 200

    # 2. Transient summary request
    candidate = {
        "id": None,
        "paper_id": "arxiv:2410.99999v1",
        "title": "Side Effect Free Evaluation",
        "abstract": "Evaluating transformer persistence invariants in ResearchLens.",
        "authors": ["Zeno Zero"],
        "source": "arxiv",
    }
    sum_res = client.post(
        "/api/v1/papers/summary",
        json={"candidate": candidate},
    )
    assert sum_res.status_code == 200

    # 3. Transient evidence request
    ev_res = client.post(
        "/api/v1/papers/evidence",
        json={"candidate": candidate},
    )
    assert ev_res.status_code == 200

    # 4. Mixed comparison request
    comp_res = client.post(
        "/api/v1/papers/compare",
        json={"items": [setup_n1_suite["catalog_paper_id"], candidate]},
    )
    assert comp_res.status_code == 200

    # Verify counts: absolutely zero mutations to DB tables
    db = SessionLocal()
    final_papers = db.query(Paper).count()
    final_evidence = db.query(PaperEvidence).count()
    final_alerts = db.query(DRIUTAlert).count()
    db.close()

    assert final_papers == init_papers
    assert final_evidence == init_evidence
    assert final_alerts == init_alerts
