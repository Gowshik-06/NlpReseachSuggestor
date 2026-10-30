# ResearchLens — PPTX Presentation Evidence & Source Index
**Project:** ResearchLens — NLP-Based Research Paper Recommendation System  
**Repository:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Document Purpose:** Concise Evidence Index linking presentation claims to exact source files, line numbers, test suites, live measurements, and audit reports.  
**Date:** October 20, 2026

---

## 1. Core Architecture & NLP/ML Evidence Mapping

| Presentation Topic / Claim | Primary Source Implementation | Key Classes / Functions / Symbols | Direct Test Verification | Supporting Audit / Verification Report |
| :--- | :--- | :--- | :--- | :--- |
| **SPECTER2 768d Embeddings** | `backend/app/services/embedding_service.py` | `_MODEL_NAME = "allenai/specter2_base"`<br>`EXPECTED_EMBEDDING_DIMENSION = 768`<br>`generate_embedding()`, `get_embedding_model()` | `backend/tests/test_embedding_and_sync.py::test_specter2_loading_failure` | `TASK_13_EVIDENCE_GROUNDED_INTELLIGENCE_REPORT.md` |
| **FAISS Vector Index (`IndexFlatIP`)** | `backend/app/services/vector_index.py` | `faiss.IndexFlatIP`<br>`_INDEX_LOCK`, `REINDEX_ADVISORY_LOCK_KEY`<br>`FAISSIndex.search()`, `add_papers()` | `backend/tests/test_faiss_consistency.py`<br>`backend/tests/test_embedding_and_sync.py` | `RESEARCHLENS_FAISS_RECONCILIATION_EXECUTION_REPORT.md` |
| **Calibrated Semantic Relevance Floor ($0.835$)** | `backend/app/services/recommendation_engine.py` | `SEMANTIC_RELEVANCE_FLOOR = 0.835`<br>`_has_lexical_match()`<br>`execute_recommendation_search()` | `backend/tests/test_targeted_remediations.py::test_semantic_relevance_floor_value`<br>`test_unrelated_query_ancient_roman_architecture_filtered` | `RESEARCHLENS_COMPREHENSIVE_AUDIT_REPORT.md` |
| **Hybrid Scoring & Multi-Criteria Ranking** | `backend/app/services/recommendation_engine.py` | `generate_recommendation_explanation()`<br>Multi-mode sorting: `relevance`, `recency`, `citations` | `backend/tests/test_papers_api.py::test_semantic_search_returns_relevant_recommendations`<br>`test_search_with_recency_sorting` | `RESEARCHLENS_FINAL_NON_AI_AUDIT_REPORT.md` |
| **Evidence Extraction with Character Offsets** | `backend/app/services/evidence_service.py` | `split_text_into_sentences_with_spans()`<br>`extract_evidence_from_text()`<br>`ALL_EVIDENCE_CATEGORIES` (9 categories) | `backend/tests/test_evidence_extraction.py`<br>`backend/tests/test_targeted_remediations.py::test_synthetic_placeholder_detection` | `TASK_13_EVIDENCE_GROUNDED_INTELLIGENCE_REPORT.md` |
| **12-Dimension Multi-Paper Comparison** | `backend/app/services/comparison_service.py` | `compare_papers_structured()`<br>`DIMENSION_DEFINITIONS` (12 dimensions)<br>`IncomparableDimensionDetail` | `backend/tests/test_paper_comparison.py` (11 passing tests) | `TASK_14_STRUCTURED_PAPER_COMPARISON_REPORT.md` |
| **DRIUT 6-Tier Relationship Taxonomy** | `backend/app/services/driut_service.py` | `PATTERNS` (Extension, Improvement, Challenge, Reproduction, Alternative, Replacement)<br>`classify_relationship_evidence()` | `backend/tests/test_driut_intelligence.py` (10 passing tests) | `TASK_15_EVIDENCE_BACKED_DRIUT_REPORT.md` |
| **Step 8b DRIUT Chronology Guard** | `backend/app/services/driut_service.py:L409-441` | `extract_effective_publication_year()`<br>`DIRECTIONAL_CATEGORIES`<br>`candidate_year < saved_year` rejection | `backend/tests/test_targeted_remediations.py::test_driut_chronology_later_improves_earlier`<br>`test_driut_chronology_earlier_cannot_improve_later` | `RESEARCHLENS_DRIUT_HISTORICAL_CHRONOLOGY_AUDIT.md` |
| **DRIUT Background Scheduler** | `backend/app/services/driut_scheduler.py` | `DRIUTBackgroundScheduler`<br>`DRIUT_ADVISORY_LOCK_KEY = 7376232`<br>`run_driut_scan_workflow()` | `backend/tests/test_driut_scheduler.py` (7 passing tests) | `TASK_15_EVIDENCE_BACKED_DRIUT_REPORT.md` |
| **Longitudinal Evolution Timeline & Graph** | `backend/app/services/evolution_service.py` | `build_research_timeline()`<br>`build_relationship_graph()`<br>`explore_candidate_gaps()` | `backend/tests/test_research_evolution.py` (15 passing tests) | `TASK_16_RESEARCH_EVOLUTION_GAP_EXPLORER_REPORT.md` |
| **Grounded Scholarly Assistant** | `backend/app/services/assistant_service.py` | `answer_research_question()`<br>`_sanitize_input()`<br>`RESEARCH_ASSISTANT_SYSTEM_PROMPT` | `backend/tests/test_research_assistant.py` (12 passing tests) | `TASK_17_GROUNDED_RESEARCH_ASSISTANT_REPORT.md` |
| **Dual AI Provider Architecture** | `backend/app/services/ai_provider.py` | `AIServiceCoordinator`, `OllamaProvider`<br>`GroqProvider`, `DeterministicFallbackProvider`<br>`asyncio.Semaphore(4)`, 15s timeout | `backend/tests/test_ai_providers.py` (7 passing tests) | `RESEARCHLENS_AI_IMPLEMENTATION_REPORT.md`<br>`RESEARCHLENS_LOCAL_AI_ACTIVATION_REPORT.md` |
| **AI Output Security Guard & Anti-Injection** | `backend/app/services/ai_output_guard.py` | `enforce_ai_output_security_guard()`<br>`_RE_ATTACK_CANARY`, `_RE_CONNECTION_URI`<br>`_RE_CONFIG_IDENTIFIERS`, `_RE_JWT_TOKEN` | `backend/tests/test_assistant_security_guard.py` (8 passing tests) | `RESEARCHLENS_PROMPT_INJECTION_FIX_REPORT.md` |

---

## 2. Ingestion, Persistence, & Security Evidence Mapping

| Presentation Topic / Claim | Primary Source Implementation | Key Classes / Functions / Symbols | Direct Test Verification | Supporting Audit / Verification Report |
| :--- | :--- | :--- | :--- | :--- |
| **Two-Phase PDF Upload & Ingestion** | `backend/app/services/pdf_service.py`<br>`backend/app/api/v1/endpoints/papers.py` | `extract_text_from_pdf_bytes()`<br>`preview_pdf_manuscript()` (`POST /preview-pdf`)<br>`ingest_pdf_manuscript()` (`POST /ingest-pdf`) | `backend/tests/test_pdf_upload.py`<br>`backend/tests/test_n2_pdf_ingestion.py` (9 tests) | `TASK_N2_EXPLICIT_PDF_CATALOG_INGESTION_REPORT.md` |
| **Search Ingestion Decoupling** | `backend/app/services/recommendation_engine.py` | Read-only candidate resolution; zero `db.add()` or `faiss.add_papers()` in search flow | `backend/tests/test_search_ingestion_decoupling.py` (9 tests) | `TASK_1B_SEARCH_INGESTION_DECOUPLING_REPORT.md` |
| **Academic Sources: arXiv, PubMed, CSIR** | `backend/app/services/academic_sources.py` | `search_arxiv()`, `search_pubmed()`<br>`search_csir_niscpr()`, `search_crossref()`<br>`parse_pubmed_dates()` | `backend/tests/test_academic_sources.py`<br>`backend/tests/test_targeted_remediations.py` | `TASK_N1_EXTERNAL_CANDIDATE_WORKFLOW_INTEGRATION_REPORT.md` |
| **Database Relational Models** | `backend/app/models/` | `Paper` (`models/paper.py`)<br>`User` (`models/user.py`)<br>`SavedPaper` (`models/paper.py`)<br>`PaperEvidence` (`models/evidence.py`)<br>`DRIUTAlert` (`models/driut.py`) | Verified across entire test suite via `conftest.py` schema generation | `RESEARCHLENS_COMPREHENSIVE_AUDIT_REPORT.md` |
| **Authentication & Bcrypt Hashing** | `backend/app/core/security.py`<br>`backend/app/api/v1/endpoints/auth.py` | `get_password_hash()`, `verify_password()`<br>`create_access_token()`, `login()` | `backend/tests/test_auth_and_isolation.py` (10 tests) | `RESEARCHLENS_SECURITY_REVIEW.md` |
| **Fail-Closed Production JWT Secret** | `backend/app/core/config.py:L103-128` | `@model_validator(mode="after")`<br>`validate_jwt_secret_for_environment()`<br>Asserts secret not default and $\ge 32$ chars | `backend/tests/test_auth_and_isolation.py::test_jwt_secret_validation_in_production` | `RESEARCHLENS_SECURITY_REVIEW.md` |
| **User Library Isolation** | `backend/app/api/deps.py`<br>`backend/app/api/v1/endpoints/papers.py` | `get_current_active_user()`<br>Scoped queries: `.filter(SavedPaper.user_id == user.username)` | `backend/tests/test_auth_and_isolation.py::test_user_data_isolation_between_two_users` | `RESEARCHLENS_SECURITY_REVIEW.md` |
| **Tiered Rate Limiting & Proxy Trust** | `backend/app/core/rate_limit.py` | `get_remote_address()`<br>`TRUSTED_PROXIES` validation<br>`@limiter.limit("5/minute")` | `backend/tests/test_rate_limiter.py` (4 tests) | `RESEARCHLENS_SECURITY_REVIEW.md` |

---

## 3. Frontend Architecture & Design Evidence Mapping

| Presentation Topic / Claim | Primary Source Implementation | Key Components / Stylesheets | Direct Test Verification | Supporting Audit / Verification Report |
| :--- | :--- | :--- | :--- | :--- |
| **React 18 + TypeScript SPA** | `frontend/src/App.tsx`<br>`frontend/src/pages/HomePage.tsx` | Tab state: `explore`, `pdf`, `compare`, `saved`, `driut`, `evolution` | `frontend/src/App.test.tsx` (7 passed) | `TASK_18_NATIVE_RUNTIME_MIGRATION_REPORT.md` |
| **Vanilla CSS Design Tokens (No Tailwind)** | `frontend/src/index.css` | `:root` CSS variables (`--bg-main`, `--emerald`, `--text-primary`, `--font-sans`) | `frontend/src/index.css:L1-50` | `TASK_18_NATIVE_RUNTIME_MIGRATION_REPORT.md` |
| **Grounded Evidence Modal** | `frontend/src/components/EvidenceModal.tsx` | Exact sentence highlight, `[char_start, char_end]` badge, category tags | `frontend/src/components/EvidenceModal.test.tsx` (10 passed) | `TASK_13_EVIDENCE_GROUNDED_INTELLIGENCE_REPORT.md` |
| **12-Dimension Comparison Modal** | `frontend/src/components/CompareModal.tsx` | Side-by-side comparative table, incomparable dimension alerts | `frontend/src/components/CompareModal.test.tsx` (8 passed) | `TASK_14_STRUCTURED_PAPER_COMPARISON_REPORT.md` |
| **DRIUT Impact Feed UI** | `frontend/src/components/DriutAlertsView.tsx` | 6 category filters, badge colors, trigger scan button | `frontend/src/components/DriutAlertsView.test.tsx` (7 passed) | `TASK_15_EVIDENCE_BACKED_DRIUT_REPORT.md` |
| **Research Evolution Timeline & Graph UI** | `frontend/src/components/ResearchEvolutionView.tsx` | 4 sub-views: Timeline, Relationship Graph, Gap Discovery, Grounded Assistant | `frontend/src/components/ResearchEvolutionView.test.tsx` (7 passed) | `TASK_16_RESEARCH_EVOLUTION_GAP_EXPLORER_REPORT.md` |
| **Personal Library View** | `frontend/src/components/SavedLibraryView.tsx` | Bookmarked cards, user notes, tag filtering, delete | `frontend/src/components/SavedLibraryView.test.tsx` (3 passed) | `TASK_18_NATIVE_RUNTIME_MIGRATION_REPORT.md` |
| **User Authentication Modal** | `frontend/src/components/AuthModal.tsx` | Login, registration, token storage in localStorage | `frontend/src/components/AuthModal.test.tsx` (3 passed) | `RESEARCHLENS_SECURITY_REVIEW.md` |
| **Typed API Service Client** | `frontend/src/services/api.ts` | Axios/Fetch wrapper with JWT Bearer header interceptor | `frontend/src/services/api.test.ts` (21 passed) | `TASK_18_NATIVE_RUNTIME_MIGRATION_REPORT.md` |

---

## 4. Defect Remediation & Integrity Audit Evidence Mapping

| Audit & Remediation Event | Baseline Issue / Defect | Remediation Artifact & Implementation | Live Verification Command / Evidence | Status & Report |
| :--- | :--- | :--- | :--- | :--- |
| **PubMed Electronic Publication Year Fix** | 25 PubMed papers had stored year 2027 despite 2026 electronic publication. | `backend/app/db/migrate_pubmed_dates.py`<br>`backend/app/services/academic_sources.py:L279` (`parse_pubmed_dates`) | Database query: 25 records shifted to 2026; 1 forthcoming 2028 record preserved. | `RESEARCHLENS_PUBMED_YEAR_CORRECTION_REPORT.md`<br>`RESEARCHLENS_YEAR_DATE_FIX_VERIFICATION.md` |
| **FAISS Orphan Vector Purge (`test:t15:cand_ext`)** | FAISS held 163 vectors; PostgreSQL held 162 papers (1 orphan vector). | `scripts/reconcile_faiss_postgres.py`<br>Removed vector at index 10, shifted remaining, synchronized metadata. | `faiss.read_index().ntotal == 162`<br>`len(papers_meta.json['id_map']) == 162`<br>`SELECT COUNT(*) FROM papers == 162` | `RESEARCHLENS_FAISS_RECONCILIATION_EXECUTION_REPORT.md`<br>`RESEARCHLENS_FAISS_RECONCILIATION_PREFLIGHT.md` |
| **DRIUT Chronology Audit & Step 8b Guard** | 90 historical alerts in database violated temporal directionality (`new_year < saved_year`). | `backend/app/services/driut_service.py:L409-441`<br>Step 8b Chronology Guard prevents new directional violations. | Read-only audit completed: 90 invalid, 75 valid, 10 exempt.<br>Zero new violations permitted by guard. | `RESEARCHLENS_DRIUT_HISTORICAL_CHRONOLOGY_AUDIT.md`<br>`RESEARCHLENS_DRIUT_CHRONOLOGY_AUDIT.json` |
| **Synthetic Abstract Rejector** | PubMed records without abstracts indexed boilerplate NLM strings. | `backend/app/services/evidence_service.py:L43`<br>`is_synthetic_placeholder_abstract()` | `test_targeted_remediations.py::test_synthetic_placeholder_detection` PASSED. | `RESEARCHLENS_COMPREHENSIVE_AUDIT_REPORT.md` |

---

## 5. Live Runtime & System Status Evidence Mapping

| Runtime Subsystem | Host Environment / Port | Verification Command / Probe | Verified Runtime Output | Evidence Category |
| :--- | :--- | :--- | :--- | :--- |
| **PostgreSQL 16 Database** | `127.0.0.1:5432`<br>Podman Container | `podman ps` or `./scripts/dev-status.sh` | Container `research-paper-recommender-postgres-1` (healthy), Port 5432 connected. | Live System Runtime |
| **FastAPI Backend Service** | `127.0.0.1:8000`<br>Systemd User Unit | `curl -s http://127.0.0.1:8000/health` | `{"status":"ok","service":"research-paper-recommender","version":"0.1.0"}` | Live API Endpoint |
| **React/Vite Frontend** | `127.0.0.1:3000`<br>Systemd User Unit | `curl -s -I http://127.0.0.1:3000` | `HTTP/1.1 200 OK`, `Content-Type: text/html` | Live Web Server |
| **Local Ollama AI Instance** | `127.0.0.1:11434`<br>Native Host Process | `curl -s http://127.0.0.1:11434/api/tags` | Model available: `qwen2.5:3b` ($1.93$ GB GGUF Q4_K_M). | Live AI Service |
| **Backend Test Suite** | Isolated SQLite / FAISS | `backend/venv/bin/pytest backend/tests` | **329 passed in 102.30s (0 failures, 100% pass)** | Automated Test Suite |
| **Frontend Test Suite** | JSDOM / Vitest | `npm run test` (in `frontend/`) | **8 passed test files, 66 passed tests in 1.72s** | Automated Test Suite |
| **Frontend Production Build** | TypeScript Compiler + Vite | `npm run build` (in `frontend/`) | **Succeeded in 820ms (0 type errors, 0 build warnings)** | Production Build |
