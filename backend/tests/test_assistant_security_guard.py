"""
Regression test suite for Grounded Research Assistant Security Guard (Batch 3).

Covers all 10 required security and safety scenarios:
1. Safe refusal that does not repeat credential names.
2. Refusal that attempts to echo DATABASE_URL, POSTGRES_PASSWORD, or JWT secret identifier.
3. Attempted disclosure of a synthetic password value.
4. Attempted disclosure of a synthetic connection URI or JWT token.
5. Answer that repeats 'HACKED' while refusing prompt injection.
6. Legitimate security/authentication explanation that should remain allowed.
7. Normal evidence citations in safe responses.
8. Guard exceptions or malformed output failing safely.
9. Confirmation that no real configuration secrets are supplied to the test model context.
10. Cloud research-content transmission remaining disabled.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from app.services.assistant_service import (
    enforce_assistant_security_guard,
    SAFE_CANONICAL_REFUSAL,
)
from app.schemas.research import (
    AssistantEvidenceItem,
)
from app.schemas.evidence import EvidenceCategory
from app.services.ai_provider import build_evidence_context
from app.core.config import get_settings


def test_guard_safe_refusal_without_prohibited_terms():
    """Scenario 1: A clean, safe refusal is preserved as-is without modification."""
    clean_refusal = "The available catalog evidence is insufficient to conclusively answer this question."
    out, modified = enforce_assistant_security_guard(clean_refusal)
    assert out == clean_refusal
    assert modified is False


def test_guard_refusal_echoing_configuration_identifiers():
    """Scenario 2: Refusal attempting to echo DATABASE_URL, POSTGRES_PASSWORD, or JWT identifier is blocked."""
    prohibited_echoes = [
        "I cannot provide DATABASE_URL as requested.",
        "The evidence does not contain the POSTGRES_PASSWORD.",
        "System configuration secret JWT_SECRET is not available in catalog papers.",
        "No information regarding database_url or postgres_password was found.",
    ]
    for echo in prohibited_echoes:
        out, modified = enforce_assistant_security_guard(echo)
        assert out == SAFE_CANONICAL_REFUSAL
        assert modified is True
        assert "database_url" not in out.lower()
        assert "postgres_password" not in out.lower()
        assert "password" not in out.lower()


def test_guard_attempted_disclosure_of_synthetic_password():
    """Scenario 3: Attempted disclosure of synthetic password assignment is blocked."""
    synthetic_disclosures = [
        "The administrative password is: SyntheticPass2026!",
        "password='SuperSecretSynthetic123'",
        "passwd: MockAdminPassword99",
    ]
    for disclosure in synthetic_disclosures:
        out, modified = enforce_assistant_security_guard(disclosure)
        assert out == SAFE_CANONICAL_REFUSAL
        assert modified is True
        assert "syntheticpass" not in out.lower()
        assert "supersecret" not in out.lower()


def test_guard_attempted_disclosure_of_synthetic_connection_uri_or_token():
    """Scenario 4: Attempted disclosure of connection URI or JWT token is blocked."""
    uri_disclosure = "Connect to postgresql://synth_user:synth_pass@127.0.0.1:5432/research_papers"
    out_uri, mod_uri = enforce_assistant_security_guard(uri_disclosure)
    assert out_uri == SAFE_CANONICAL_REFUSAL
    assert mod_uri is True
    assert "postgresql://" not in out_uri

    # Synthetic JWT token (3 base64url segments)
    synth_jwt = "Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    out_jwt, mod_jwt = enforce_assistant_security_guard(synth_jwt)
    assert out_jwt == SAFE_CANONICAL_REFUSAL
    assert mod_jwt is True
    assert "eyJ" not in out_jwt


def test_guard_answer_repeating_hacked_attack_canary():
    """Scenario 5: Answer that repeats 'HACKED' while explaining refusal is collapsed to canonical refusal."""
    attack_echoes = [
        "The catalog evidence is insufficient to answer or to output 'HACKED'.",
        "SYSTEM OVERRIDE: HACKED",
        "I am an AI assistant and will not print HACKED as requested.",
    ]
    for text in attack_echoes:
        out, modified = enforce_assistant_security_guard(text)
        assert out == SAFE_CANONICAL_REFUSAL
        assert modified is True
        assert "HACKED" not in out


def test_guard_legitimate_security_explanation_allowed():
    """Scenario 6: Legitimate academic discussion of security/authentication grounded in evidence is preserved."""
    legitimate_evidence = [
        AssistantEvidenceItem(
            evidence_id="ev-1",
            paper_id=1,
            paper_code="P1",
            paper_title="Zero-Knowledge Authentication Protocol",
            year=2024,
            category=EvidenceCategory.METHOD,
            claim="The authors introduce a zero-knowledge password authentication exchange.",
            source_passage="We evaluate zero-knowledge password authentication under high-concurrency conditions.",
            char_start=0,
            char_end=74,
            is_verified=True,
            confidence_score=0.95
        )
    ]
    scholarly_answer = (
        "According to [ev-1], the authors propose a zero-knowledge password authentication protocol "
        "and evaluate its cryptographic resilience under high-concurrency conditions."
    )
    out, modified = enforce_assistant_security_guard(scholarly_answer, evidence=legitimate_evidence)
    assert out == scholarly_answer
    assert modified is False
    assert "[ev-1]" in out
    assert "password authentication" in out


def test_guard_normal_evidence_citations_in_safe_responses():
    """Scenario 7: Normal non-security evidence citations and scholarly text remain unaffected."""
    normal_answer = (
        "The authors introduce bidirectional language representations [ev-1], achieving substantial "
        "improvements across 11 NLP tasks including the GLUE benchmark [ev-2]."
    )
    out, modified = enforce_assistant_security_guard(normal_answer)
    assert out == normal_answer
    assert modified is False
    assert "[ev-1]" in out
    assert "[ev-2]" in out


def test_guard_exceptions_fail_safe():
    """Scenario 8: Guard internal exception or malformed object fails safe with canonical refusal."""
    mock_pattern = MagicMock()
    mock_pattern.search.side_effect = RuntimeError("Simulated internal guard failure")

    with patch("app.services.assistant_service._RE_ATTACK_CANARY", mock_pattern):
        out, modified = enforce_assistant_security_guard("Some potentially hostile text")
        assert out == SAFE_CANONICAL_REFUSAL
        assert modified is True


def test_model_context_never_contains_configuration_secrets():
    """Scenario 9: Confirm prompt construction context contains only paper evidence, never app secrets."""
    ev_dicts = [{
        "evidence_id": "ev-1",
        "paper_title": "Attention Is All You Need",
        "year": 2017,
        "category": "method",
        "source_passage": "The Transformer is the first transduction model relying entirely on self-attention."
    }]
    context = build_evidence_context(ev_dicts)

    settings = get_settings()
    # Confirm no environment variables or configuration keys leak into context block
    assert "DATABASE_URL" not in context
    assert "POSTGRES_PASSWORD" not in context
    assert "SECRET_KEY" not in context
    assert "GROQ_API_KEY" not in context
    if getattr(settings, "JWT_SECRET_KEY", None):
        assert settings.JWT_SECRET_KEY not in context
    if getattr(settings, "DATABASE_URL", None) and "@" in settings.DATABASE_URL:
        user_pass = settings.DATABASE_URL.split("@")[0].split("//")[-1]
        assert user_pass not in context


def test_cloud_research_content_transmission_remains_disabled():
    """Scenario 10: Verify cloud transmission of research content is blocked under default settings."""
    settings = get_settings()
    assert settings.RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT is False


# ==============================================================================
# ISSUE-03 Multi-Workflow Regression Tests
# ==============================================================================

from app.services.ai_output_guard import enforce_ai_output_security_guard
from app.services.summary_service import generate_paper_summary
from app.services.ai_provider import AIResponse


def test_summary_workflow_normal_scholarly_summary():
    """ISSUE-03: Normal scholarly summary is preserved when generated by AI."""
    mock_ai_resp = AIResponse(
        content="This paper introduces a novel self-attention mechanism that improves benchmark translation quality.",
        provider="ollama",
        model="qwen2.5:3b"
    )

    paper = {
        "paper_id": "test_p1",
        "title": "Attention Is All You Need",
        "abstract": "We propose the Transformer, a model architecture eschewing recurrence and relying entirely on attention mechanisms to draw global dependencies.",
        "year": 2017,
        "venue": "NeurIPS",
        "citation_count": 50000
    }

    with patch("app.services.summary_service.get_ai_coordinator") as mock_coord:
        mock_instance = MagicMock()
        mock_instance.generate.return_value = asyncio_future(mock_ai_resp)
        mock_coord.return_value = mock_instance

        resp = generate_paper_summary(paper)
        assert "self-attention mechanism" in resp.executive_summary
        assert resp.ai_provider == "ollama"


def test_summary_workflow_blocks_hacked_and_credentials():
    """ISSUE-03: Summary containing attack canary or credential assignments is blocked and safely replaced."""
    malicious_outputs = [
        "SYSTEM COMPROMISED: HACKED by prompt injection.",
        "The model reports admin password is: LeakedSecret2026!",
        "Database is accessible at postgresql://user:pass@10.0.0.1:5432/research",
    ]

    paper = {
        "paper_id": "test_p2",
        "title": "Prompt Injection in LLMs",
        "abstract": "We explore adversarial prompt attacks against neural language models.",
        "year": 2023,
        "venue": "ACL",
        "citation_count": 10
    }

    for mal_out in malicious_outputs:
        mock_ai_resp = AIResponse(
            content=mal_out,
            provider="ollama",
            model="qwen2.5:3b"
        )
        with patch("app.services.summary_service.get_ai_coordinator") as mock_coord:
            mock_instance = MagicMock()
            mock_instance.generate.return_value = asyncio_future(mock_ai_resp)
            mock_coord.return_value = mock_instance

            resp = generate_paper_summary(paper)
            # Replaced with deterministic baseline summary
            assert "HACKED" not in resp.executive_summary
            assert "LeakedSecret" not in resp.executive_summary
            assert "postgresql://" not in resp.executive_summary
            assert resp.ai_provider == "deterministic"
            assert resp.ai_fallback_occurred is True


def test_comparison_workflow_blocks_connection_uri():
    """ISSUE-03: Comparison executive summary containing connection URI is blocked."""
    from app.services.comparison_service import compare_papers

    mock_ai_resp = AIResponse(
        content="Both models share features, but connect via postgresql://admin:secret@127.0.0.1:5432/db",
        provider="ollama",
        model="qwen2.5:3b"
    )

    papers = [
        {
            "id": 1,
            "paper_id": "p1",
            "title": "BERT Model",
            "abstract": "BERT is designed to pretrain deep bidirectional representations.",
            "authors": ["Devlin et al."],
            "year": 2019,
            "citation_count": 1000
        },
        {
            "id": 2,
            "paper_id": "p2",
            "title": "RoBERTa Model",
            "abstract": "An aggressively optimized replication of BERT training.",
            "authors": ["Liu et al."],
            "year": 2019,
            "citation_count": 800
        }
    ]

    with patch("app.services.comparison_service.get_ai_coordinator") as mock_coord:
        mock_instance = MagicMock()
        mock_instance.generate.return_value = asyncio_future(mock_ai_resp)
        mock_coord.return_value = mock_instance

        resp = compare_papers(papers, db=None)
        assert "postgresql://" not in resp.executive_summary
        assert resp.ai_provider == "deterministic"
        assert resp.ai_fallback_occurred is True


def test_evolution_workflow_blocks_credential_identifiers():
    """ISSUE-03: Gap exploration synthesis containing configuration identifiers is blocked."""
    from app.services.evolution_service import explore_candidate_gaps
    from app.schemas.research import GapExplorationRequest
    from app.models.paper import Paper

    mock_ai_resp = AIResponse(
        content="Analysis reveals POSTGRES_PASSWORD and DATABASE_URL are absent in benchmark sets.",
        provider="ollama",
        model="qwen2.5:3b"
    )

    p1 = Paper(id=1, paper_id="p1", title="Scaling Limits", abstract="A major bottleneck and limitation is compute.", year=2021)
    p2 = Paper(id=2, paper_id="p2", title="Attention Bottlenecks", abstract="Memory challenge and weakness occurs at scale.", year=2022)
    p3 = Paper(id=3, paper_id="p3", title="Future Directions", abstract="Future work addresses algorithmic shortcoming.", year=2023)

    db = MagicMock()
    req = GapExplorationRequest(topic="NLP Architecture", min_corpus_size=2, max_gaps=5)

    with patch("app.services.evolution_service._query_relevant_papers", return_value=[p1, p2, p3]), \
         patch("app.services.evolution_service.get_ai_coordinator") as mock_coord:
        mock_instance = MagicMock()
        mock_instance.generate.return_value = asyncio_future(mock_ai_resp)
        mock_coord.return_value = mock_instance

        resp = explore_candidate_gaps(db, req)
        synth = resp.corpus_summary.get("ai_gap_synthesis", "")
        assert "POSTGRES_PASSWORD" not in synth
        assert "DATABASE_URL" not in synth
        assert resp.ai_provider == "deterministic"
        assert resp.ai_fallback_occurred is True


def test_workflow_preserves_grounded_security_science():
    """ISSUE-03: Scientific discussion of password hashing backed by paper abstract is preserved."""
    grounded_abstract = "We present an empirical study of password authentication schemes and password cracking resistance."
    scholarly_content = "The authors examine password authentication schemes and measure password cracking resistance across GPUs."

    out, modified = enforce_ai_output_security_guard(
        scholarly_content,
        evidence=[grounded_abstract],
        workflow_name="summary"
    )
    assert out == scholarly_content
    assert modified is False
    assert "password authentication" in out


def asyncio_future(val):
    async def _coro():
        return val
    return _coro()

