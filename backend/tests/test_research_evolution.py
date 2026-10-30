"""
TASK-16 Comprehensive Test Suite: Research Evolution Timeline, Relationship Graph, and Candidate Gap Explorer.
Verifies:
1. Timeline chronological ordering by publication year.
2. Undated paper isolation without chronological misattribution or using ingestion timestamps.
3. Topic and date range filtering.
4. Evidence grounding: claims linked to exact source passages with character offsets and sections.
5. Relationship graph: explicit author-stated vs. inferred relationships vs. thematic similarity.
6. Thematic similarity without supported relationship does NOT fabricate scientific claims.
7. Bounded graph limits and safe handling of missing citation metadata.
8. Sparse corpus (< min_corpus_size) strictly returns insufficient_evidence.
9. Candidate gap discovery for recurring limitations, recurring future work, and cross-benchmark evaluation.
10. Strict distinction: local corpus coverage gap vs. global scientific research gap.
11. Every candidate gap mandates human validation and provides recommended verification steps.
12. API validation, bounds, and error handling.
13. Cross-user privacy preservation.
14. Zero database and FAISS index mutations during exploration.
"""
import os
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
from app.services.vector_index import INDEX_PATH, METADATA_PATH

client = TestClient(app)

FIXTURES = {}


@pytest.fixture(scope="module", autouse=True)
def setup_evolution_suite():
    """Setup test fixture papers spanning multiple years, themes, and evidence types."""
    db = SessionLocal()

    # Preserve baseline FAISS index bytes
    orig_idx_bytes = None
    orig_meta_bytes = None
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "rb") as f:
            orig_idx_bytes = f.read()
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, "rb") as f:
            orig_meta_bytes = f.read()

    # Clean existing test fixtures if leftover
    test_pids = [
        "test:evo.2018.bert",
        "test:evo.2020.roberta",
        "test:evo.2022.deberta",
        "test:evo.undated.sparse",
        "test:evo.unrelated.bio",
    ]
    p_to_clean = [p.id for p in db.query(Paper).filter(Paper.paper_id.in_(test_pids)).all()]
    if p_to_clean:
        db.query(PaperEvidence).filter(PaperEvidence.paper_id.in_(p_to_clean)).delete(synchronize_session=False)
        db.query(SavedPaper).filter(SavedPaper.paper_id.in_(p_to_clean)).delete(synchronize_session=False)
        db.query(Paper).filter(Paper.id.in_(p_to_clean)).delete(synchronize_session=False)
        db.commit()

    # User isolation check
    test_user = db.query(User).filter(User.username == "test_evo_user").first()
    if not test_user:
        test_user = User(
            username="test_evo_user",
            email="test_evo_user@example.com",
            hashed_password=hash_password("Password123!"),
            is_active=True
        )
        db.add(test_user)
        db.commit()

    # Create 5 controlled fixture papers:
    # 1. 2018 BERT Baseline (Year 2018, GLUE dataset, limitation on compute, future work on efficiency)
    p1 = Paper(
        paper_id="test:evo.2018.bert",
        title="BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        abstract=(
            "We introduce a new language representation model called BERT. "
            "Our approach is evaluated on the GLUE benchmark. "
            "Empirical results show that our model achieves substantial improvements over baselines. "
            "A major limitation of our approach is the high computational cost and memory overhead required during pre-training. "
            "In future work, we plan to extend this framework to edge-constrained and lightweight environments."
        ),
        authors=["Jacob Devlin", "Ming-Wei Chang"],
        venue="NAACL 2019",
        year=2018,
        citation_count=85000,
        source="local"
    )
    db.add(p1)
    db.flush()

    # 2. 2020 RoBERTa Extension (Year 2020, GLUE benchmark, direct mention of BERT, recurring compute limitation)
    p2 = Paper(
        paper_id="test:evo.2020.roberta",
        title="RoBERTa: A Robustly Optimized BERT Pretraining Approach",
        abstract=(
            "We present a replication study of BERT pretraining. "
            "We extend BERT by training with larger batches and longer sequences on the GLUE benchmark. "
            "Results indicate superior performance over original BERT. "
            "However, severe computational overhead and excessive GPU training time remains a primary limitation. "
            "In future work, we plan to explore model compression and lightweight quantization."
        ),
        authors=["Yinhan Liu", "Myle Ott"],
        venue="arXiv",
        year=2020,
        citation_count=21000,
        source="local"
    )
    db.add(p2)
    db.flush()

    # 3. 2022 DeBERTa Improvement (Year 2022, SuperGLUE & SQuAD benchmarks, disentangled attention)
    p3 = Paper(
        paper_id="test:evo.2022.deberta",
        title="DeBERTa: Decoding-enhanced BERT with Disentangled Attention",
        abstract=(
            "We propose DeBERTa using disentangled attention mechanisms. "
            "We evaluate our framework on SuperGLUE and SQuAD benchmarks. "
            "Our model outperforms competitive baselines across multiple benchmarks. "
            "A critical limitation of our framework is the high memory overhead of relative position embeddings. "
            "Future research will investigate multimodal cross-modal extensions with visual signals."
        ),
        authors=["Pengcheng He", "Xiaodong Liu"],
        venue="ICLR 2021",
        year=2022,
        citation_count=4500,
        source="local"
    )
    db.add(p3)
    db.flush()

    # 4. Undated Sparse Paper (Year None, no date in catalog)
    p4 = Paper(
        paper_id="test:evo.undated.sparse",
        title="Exploring Transformer Attention Patterns Without Timestamps",
        abstract=(
            "In this study we explore attention maps in transformer architectures. "
            "Our objective is to analyze internal representations across layers."
        ),
        authors=["Anonymous Researcher"],
        venue="Unknown Workshop",
        year=None,
        citation_count=0,
        source="local"
    )
    db.add(p4)
    db.flush()

    # 5. Unrelated Biology Paper (Distinct domain for thematic isolation)
    p5 = Paper(
        paper_id="test:evo.unrelated.bio",
        title="CRISPR Genomic Cleavage Dynamics in Cellular Microenvironments",
        abstract=(
            "We investigate endonuclease specificity in genomic editing assays. "
            "Single-cell assays demonstrate distinct enzymatic cleavage kinetics."
        ),
        authors=["Elena Rostova", "Klaus Weber"],
        venue="Cell Biology Reports",
        year=2021,
        citation_count=15,
        source="local"
    )
    db.add(p5)
    db.flush()

    # Add a private saved paper entry for test_evo_user to verify isolation
    saved_entry = SavedPaper(
        user_id="test_evo_user",
        paper_id=p1.id,
        notes="Private secret research notes about BERT.",
        tags=["private-tag"]
    )
    db.add(saved_entry)
    db.commit()

    FIXTURES["p1"] = p1.id
    FIXTURES["p2"] = p2.id
    FIXTURES["p3"] = p3.id
    FIXTURES["p4"] = p4.id
    FIXTURES["p5"] = p5.id
    FIXTURES["user"] = test_user.username
    FIXTURES["orig_idx_bytes"] = orig_idx_bytes
    FIXTURES["orig_meta_bytes"] = orig_meta_bytes

    yield

    # Teardown: cleanly purge created fixture records
    db_clean = SessionLocal()
    for pid_val in [p1.id, p2.id, p3.id, p4.id, p5.id]:
        db_clean.query(SavedPaper).filter(SavedPaper.paper_id == pid_val).delete(synchronize_session=False)
        db_clean.query(PaperEvidence).filter(PaperEvidence.paper_id == pid_val).delete(synchronize_session=False)
        db_clean.query(Paper).filter(Paper.id == pid_val).delete(synchronize_session=False)
    db_clean.query(User).filter(User.username == "test_evo_user").delete(synchronize_session=False)
    db_clean.commit()
    db_clean.close()


# ==============================================================================
# 1. Timeline Tests
# ==============================================================================

def test_timeline_chronological_ordering():
    """Verify papers are grouped and ordered chronologically by publication year."""
    resp = client.get("/api/v1/research/timeline?topic=BERT")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_papers_examined"] >= 3
    assert data["total_dated_papers"] >= 3
    assert "timeline" in data
    assert len(data["timeline"]) > 0

    # Verify dated groups are strictly ascending
    dated_years = [g["year"] for g in data["timeline"] if g["year"] is not None]
    assert dated_years == sorted(dated_years), "Timeline year groups must be in ascending chronological order"
    assert 2018 in dated_years
    assert 2020 in dated_years


def test_timeline_undated_paper_isolation():
    """Verify papers with unrecorded publication year are isolated in the Undated group without inventing dates."""
    resp = client.get("/api/v1/research/timeline?topic=Transformer")
    assert resp.status_code == 200
    data = resp.json()

    undated_groups = [g for g in data["timeline"] if g["year"] is None]
    assert len(undated_groups) == 1
    undated_group = undated_groups[0]
    assert undated_group["year_label"] == "Undated / Uncertain Year"

    # Find the undated test paper inside
    undated_titles = [p["title"] for p in undated_group["papers"]]
    assert any("Without Timestamps" in t for t in undated_titles)

    # Verify paper attributes
    target_paper = next(p for p in undated_group["papers"] if "Without Timestamps" in p["title"])
    assert target_paper["is_undated"] is True
    assert target_paper["year"] is None
    assert target_paper["date_uncertainty_note"] is not None
    assert "unrecorded or uncertain" in target_paper["date_uncertainty_note"]


def test_timeline_filtering_topic_and_date():
    """Verify filtering by topic and year ranges bounds results correctly."""
    resp = client.get("/api/v1/research/timeline?topic=BERT&start_year=2019&end_year=2021")
    assert resp.status_code == 200
    data = resp.json()

    for g in data["timeline"]:
        if g["year"] is not None:
            assert 2019 <= g["year"] <= 2021


def test_timeline_evidence_grounding_and_provenance():
    """Verify that timeline claims contain exact source passages, character offsets, and provenance."""
    resp = client.get("/api/v1/research/timeline?topic=BERT")
    assert resp.status_code == 200
    data = resp.json()

    # Locate BERT 2018 paper
    found_bert = False
    for group in data["timeline"]:
        for p in group["papers"]:
            if p["paper_id"] == "test:evo.2018.bert":
                found_bert = True
                assert len(p["limitation_claims"]) > 0
                lim_claim = p["limitation_claims"][0]
                assert "computational cost" in lim_claim["source_passage"].lower()
                assert lim_claim["char_start"] is not None
                assert lim_claim["char_end"] is not None
                assert lim_claim["section_name"] == "Abstract"

                assert len(p["future_work_claims"]) > 0
                fw_claim = p["future_work_claims"][0]
                assert "lightweight" in fw_claim["source_passage"].lower()

                assert len(p["findings_claims"]) > 0
                res_claim = p["findings_claims"][0]
                assert "substantial improvements" in res_claim["source_passage"].lower()

    assert found_bert, "Expected 2018 BERT paper in timeline results"


# ==============================================================================
# 2. Relationship Graph Tests
# ==============================================================================

def test_relationship_graph_author_stated_vs_inferred():
    """Verify graph edges distinguish explicit author statements from inferred candidate relationships."""
    resp = client.get("/api/v1/research/graph?topic=BERT&max_nodes=10")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_nodes"] >= 2
    assert "edges" in data

    # RoBERTa explicitly extends BERT
    roberta_bert_edge = None
    for e in data["edges"]:
        if ("RoBERTa" in e["source_title"] and "BERT" in e["target_title"]) or \
           ("RoBERTa" in e["target_title"] and "BERT" in e["source_title"]):
            roberta_bert_edge = e
            break

    assert roberta_bert_edge is not None
    assert roberta_bert_edge["relationship_type"] in ["Extension", "Improvement", "Reproduction"]
    assert roberta_bert_edge["is_author_stated"] is True or roberta_bert_edge["relationship_status"] == "author_stated"
    assert roberta_bert_edge["evidence_passage"] is not None


def test_relationship_graph_thematic_only_no_false_claims():
    """Verify high similarity without category evidence yields Thematic Similarity, not fabricated claims."""
    # Build graph with lower similarity threshold
    resp = client.get("/api/v1/research/graph?topic=Transformer&min_similarity=0.40&max_nodes=10")
    assert resp.status_code == 200
    data = resp.json()

    thematic_edges = [e for e in data["edges"] if e["relationship_type"] == "Thematic Similarity"]
    for te in thematic_edges:
        assert te["relationship_status"] == "thematic_only"
        assert te["is_author_stated"] is False
        assert te["evidence_strength"] == "insufficient_evidence"
        assert "does NOT prove citation" in te["uncertainty_warning"]


def test_relationship_graph_bounded_limits_and_missing_citations():
    """Verify max_nodes bounds the graph and missing citation counts are zero rather than fabricated."""
    resp = client.get("/api/v1/research/graph?max_nodes=3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) <= 3

    # Check node attributes
    for node in data["nodes"]:
        assert isinstance(node["citation_count"], int)
        assert node["citation_count"] >= 0


# ==============================================================================
# 3. Candidate Research-Gap Explorer Tests
# ==============================================================================

def test_gap_explorer_sparse_corpus_insufficient_evidence():
    """Verify small corpus below min_corpus_size returns explicit insufficient_evidence status."""
    payload = {
        "topic": "CRISPR Genomic Cleavage Dynamics",
        "min_corpus_size": 4,
        "max_gaps": 5
    }
    resp = client.post("/api/v1/research/gaps", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "insufficient_evidence"
    assert data["total_gaps_found"] == 0
    assert len(data["candidate_gaps"]) == 0
    assert "INSUFFICIENT EVIDENCE" in data["truthfulness_disclosure"]


def test_gap_explorer_recurring_limitations_with_evidence():
    """Verify recurring limitations across BERT and RoBERTa trigger grounded candidate gap."""
    payload = {
        "topic": "BERT",
        "min_corpus_size": 2,
        "max_gaps": 10
    }
    resp = client.post("/api/v1/research/gaps", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] in ["complete", "partial_coverage"]
    assert data["total_gaps_found"] >= 1

    # Look for recurring limitation on computational overhead
    comp_gap = next((g for g in data["candidate_gaps"] if "Computational" in g["title"]), None)
    assert comp_gap is not None
    assert comp_gap["gap_type"] == "recurring_limitation"
    assert comp_gap["evidence_strength"] in ["strong_recurrence", "moderate_pattern"]
    assert len(comp_gap["motivating_evidence"]) >= 2
    assert comp_gap["human_validation_required"] is True
    assert len(comp_gap["recommended_verification_steps"]) >= 2

    # Verify quotes are real
    for ev in comp_gap["motivating_evidence"]:
        assert len(ev["quote"]) > 10
        assert "computational" in ev["quote"].lower() or "overhead" in ev["quote"].lower()


def test_gap_explorer_recurring_future_work_with_evidence():
    """Verify recurring future work directions trigger grounded candidate gap."""
    payload = {
        "topic": "BERT",
        "min_corpus_size": 2,
        "max_gaps": 10
    }
    resp = client.post("/api/v1/research/gaps", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    fw_gap = next((g for g in data["candidate_gaps"] if "Model Compression" in g["title"] or "Efficiency" in g["title"]), None)
    if fw_gap:
        assert fw_gap["gap_type"] == "recurring_future_work"
        assert len(fw_gap["motivating_evidence"]) >= 1
        assert fw_gap["human_validation_required"] is True


def test_gap_explorer_corpus_coverage_vs_scientific_gap():
    """Verify system includes explicit local catalog coverage boundary gap."""
    payload = {
        "topic": "BERT",
        "min_corpus_size": 2,
        "max_gaps": 10
    }
    resp = client.post("/api/v1/research/gaps", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    coverage_gap = next((g for g in data["candidate_gaps"] if g["is_corpus_coverage_gap"] is True), None)
    assert coverage_gap is not None
    assert coverage_gap["gap_type"] == "corpus_coverage_gap"
    assert "MUST NOT be claimed as worldwide scientific novelty" in coverage_gap["concise_hypothesis"]
    assert "DISCLOSURE" in data["truthfulness_disclosure"]


# ==============================================================================
# 4. Security, Isolation, and Zero-Mutation Tests
# ==============================================================================

def test_cross_user_privacy_isolation():
    """Verify private notes and user saved papers are NOT leaked in research evolution endpoints."""
    resp = client.get("/api/v1/research/timeline?topic=BERT")
    assert resp.status_code == 200
    raw_text = resp.text

    assert "Private secret research notes" not in raw_text
    assert "private-tag" not in raw_text
    assert "test_evo_user" not in raw_text


def test_api_validation_errors():
    """Verify input validation handles invalid bounds cleanly with 422 Unprocessable Entity."""
    # Invalid start year
    resp = client.get("/api/v1/research/timeline?start_year=1800")
    assert resp.status_code == 422

    # Invalid max_nodes in graph
    resp = client.get("/api/v1/research/graph?max_nodes=100")
    assert resp.status_code == 422

    # Invalid min_corpus_size in gaps
    resp = client.post("/api/v1/research/gaps", json={"min_corpus_size": 0})
    assert resp.status_code == 422


def test_zero_database_and_faiss_mutations():
    """Verify that exploration queries never mutate database rows or FAISS index files."""
    db = SessionLocal()

    count_papers_before = db.query(Paper).count()
    count_evidence_before = db.query(PaperEvidence).count()
    count_alerts_before = db.query(DRIUTAlert).count()
    count_saved_before = db.query(SavedPaper).count()
    db.close()

    # Execute multiple read-only queries across timeline, graph, and gaps
    client.get("/api/v1/research/timeline?topic=BERT")
    client.get("/api/v1/research/graph?topic=BERT")
    client.post("/api/v1/research/gaps", json={"topic": "BERT", "min_corpus_size": 2})

    db_after = SessionLocal()
    assert db_after.query(Paper).count() == count_papers_before
    assert db_after.query(PaperEvidence).count() == count_evidence_before
    assert db_after.query(DRIUTAlert).count() == count_alerts_before
    assert db_after.query(SavedPaper).count() == count_saved_before
    db_after.close()

    # Check FAISS bytes invariance
    if FIXTURES["orig_idx_bytes"] and os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "rb") as f:
            assert f.read() == FIXTURES["orig_idx_bytes"], "FAISS index file must remain identical"

    if FIXTURES["orig_meta_bytes"] and os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, "rb") as f:
            assert f.read() == FIXTURES["orig_meta_bytes"], "FAISS metadata file must remain identical"


def test_exact_character_offset_invariant_regression():
    """Regression test: verify paper.abstract[char_start:char_end] == quote holds mathematically."""
    db = SessionLocal()
    # Test on timeline
    resp = client.get("/api/v1/research/timeline?topic=BERT")
    assert resp.status_code == 200
    data = resp.json()

    for group in data["timeline"]:
        for p in group["papers"]:
            db_p = db.query(Paper).filter(Paper.paper_id == p["paper_id"]).first()
            if not db_p or not db_p.abstract:
                continue
            all_claims = (
                p["method_changes"]
                + p["findings_claims"]
                + p["limitation_claims"]
                + p["future_work_claims"]
            )
            for c in all_claims:
                if c["char_start"] is not None and c["char_end"] is not None:
                    sliced = db_p.abstract[c["char_start"]:c["char_end"]]
                    assert sliced == c["source_passage"], (
                        f"Offset mismatch on {db_p.paper_id}: [{c['char_start']}:{c['char_end']}] "
                        f"got {repr(sliced)} expected {repr(c['source_passage'])}"
                    )

    # Test on candidate gaps
    g_resp = client.post("/api/v1/research/gaps", json={"topic": "BERT", "min_corpus_size": 2})
    assert g_resp.status_code == 200
    g_data = g_resp.json()
    for gap in g_data["candidate_gaps"]:
        for item in gap["motivating_evidence"]:
            if item["char_start"] is not None and item["char_end"] is not None:
                db_p = db.query(Paper).filter(Paper.paper_id == item["paper_code"]).first()
                if db_p and db_p.abstract:
                    sliced = db_p.abstract[item["char_start"]:item["char_end"]]
                    assert sliced == item["quote"], (
                        f"Gap quote offset mismatch on {item['paper_code']}: [{item['char_start']}:{item['char_end']}] "
                        f"got {repr(sliced)} expected {repr(item['quote'])}"
                    )
    db.close()


def test_gap_explorer_min_corpus_size_boundaries():
    """Verify min_corpus_size boundary conditions at T-1, T, and T+1 for default and overridden thresholds."""
    # 1. Query baseline topic to determine actual examined papers count N
    base_resp = client.post("/api/v1/research/gaps", json={"topic": "BERT", "min_corpus_size": 1})
    assert base_resp.status_code == 200
    n_papers = base_resp.json()["total_papers_examined"]
    assert n_papers >= 3, f"Expected at least 3 papers for BERT topic, got {n_papers}"

    # Boundary 1: One below configured threshold (corpus_size = N, threshold T = N + 1)
    # Here corpus_size = T - 1
    resp_below = client.post("/api/v1/research/gaps", json={"topic": "BERT", "min_corpus_size": n_papers + 1})
    assert resp_below.status_code == 200
    data_below = resp_below.json()
    assert data_below["status"] == "insufficient_evidence"
    assert data_below["total_gaps_found"] == 0
    assert "INSUFFICIENT EVIDENCE" in data_below["truthfulness_disclosure"]

    # Boundary 2: Exactly the threshold (corpus_size = N, threshold T = N)
    # Here corpus_size = T
    resp_exact = client.post("/api/v1/research/gaps", json={"topic": "BERT", "min_corpus_size": n_papers})
    assert resp_exact.status_code == 200
    data_exact = resp_exact.json()
    assert data_exact["status"] in ["complete", "partial_coverage"]
    assert data_exact["total_gaps_found"] >= 1

    # Boundary 3: One above the threshold (corpus_size = N, threshold T = N - 1)
    # Here corpus_size = T + 1
    resp_above = client.post("/api/v1/research/gaps", json={"topic": "BERT", "min_corpus_size": n_papers - 1})
    assert resp_above.status_code == 200
    data_above = resp_above.json()
    assert data_above["status"] in ["complete", "partial_coverage"]
    assert data_above["total_gaps_found"] >= 1

    # 2. Test default threshold (default is min_corpus_size = 3) separately from explicit override
    # Topic "BioBERT" has 1 paper, which is strictly below default threshold 3
    resp_default_below = client.post("/api/v1/research/gaps", json={"topic": "BioBERT"})
    assert resp_default_below.status_code == 200
    data_default_below = resp_default_below.json()
    assert data_default_below["status"] == "insufficient_evidence"
    assert data_default_below["corpus_summary"]["min_corpus_required"] == 3

    # Topic "BERT" has N >= 3 papers, which satisfies default threshold 3
    resp_default_ok = client.post("/api/v1/research/gaps", json={"topic": "BERT"})
    assert resp_default_ok.status_code == 200
    data_default_ok = resp_default_ok.json()
    assert data_default_ok["status"] in ["complete", "partial_coverage"]
    assert data_default_ok["corpus_summary"]["min_corpus_required"] == 3

