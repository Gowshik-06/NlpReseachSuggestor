# ResearchLens — Comprehensive Project Dossier for Complete PPTX Preparation
**System:** ResearchLens — NLP-Based Research Paper Recommendation System  
**Repository:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`  
**Document Type:** Exhaustive Read-Only Technical Dossier & Academic Presentation Baseline  
**Date of Extraction:** October 20, 2026  
**Status:** 100% Read-Only Grounded Repository Extraction (Zero Live Modifications)

---

## Executive Summary

**ResearchLens** is an advanced, evidence-grounded research paper discovery, recommendation, comparison, and longitudinal intelligence platform. Unlike conventional academic search tools that rely exclusively on lexical keyword indexing or unconstrained generative AI summaries that hallucinate claims, ResearchLens combines:
1. **Dense Semantic Retrieval:** Powered by AllenAI’s scientific embedding model (`allenai/specter2_base`, 768 dimensions) coupled with a native FAISS vector index (`IndexFlatIP`, cosine similarity).
2. **Calibrated Hybrid Ranking & Filtering:** Blends lexical matching, semantic vector proximity, empirical relevance floors ($0.835$ cosine threshold), and publication recency boosts to prevent semantic topic drift.
3. **Evidence-Grounded Intelligence:** Extracts exact scientific claim passages directly from manuscript abstracts and full texts across 9 research dimensions with exact character spans (`[char_start, char_end]`) and cryptographic SHA-256 source verification.
4. **Structured Multi-Paper Comparison:** Performs side-by-side comparative matrices across 12 rigorous scientific dimensions (methodology, datasets, metrics, reported results, limitations, threats to validity, etc.), guarding against disparate benchmark conflation.
5. **Dynamic Research Impact Update Tracker (DRIUT):** Continuously monitors newly cataloged papers and classifies directional scholarly relationships against a researcher's saved library across a 6-tier taxonomy (*Extension, Improvement, Challenge, Reproduction, Alternative, Potential Replacement*), strictly governed by a chronology guard (Step 8b) that prevents earlier papers from claiming to improve on later works.
6. **Longitudinal Research Evolution & Gap Explorer:** Constructs chronological evolution timelines, citation and thematic relationship graphs, and candidate research-gap hypotheses, strictly disclosing local catalog boundaries.
7. **Local-First, Air-Gapped AI Assistant:** Features a dual AI provider architecture with local Ollama (`qwen2.5:3b`) on-premises execution, optional cloud Groq failover, deterministic rule-based fallbacks, and strict prompt-injection and output-leakage guards.

### Verified System Verification Highlights
- **Backend Test Suite:** 329 passing automated tests in `pytest` ($100\%$ pass rate, zero regressions).
- **Frontend Test Suite:** 66 passing component tests in `vitest` ($100\%$ pass rate).
- **Frontend Production Build:** TypeScript compile (`tsc -b`) and Vite production bundle build succeed with zero errors.
- **Database & Vector Catalog:** 162 PostgreSQL research paper records in exact 1:1:1 alignment with 162 FAISS vector embeddings and 162 metadata entries.
- **Live Runtime State:** Native Fedora development stack (FastAPI backend on port 8000, React/Vite frontend on port 3000, containerized PostgreSQL 16 on port 5432, local Ollama on port 11434) fully operational and verified.

---

## Table of Contents

1. [Section 1: Repository Identity, Environment, & Baseline State](#section-1-repository-identity-environment--baseline-state)
2. [Section 2: Problem Statement, Research Objectives, & Academic Contributions](#section-2-problem-statement-research-objectives--academic-contributions)
3. [Section 3: Comprehensive Feature & Subsystem Matrix](#section-3-comprehensive-feature--subsystem-matrix)
4. [Section 4: System Architecture & End-to-End Data Flows](#section-4-system-architecture--end-to-end-data-flows)
5. [Section 5: NLP, Machine Learning, Retrieval, & AI Methodology](#section-5-nlp-machine-learning-retrieval--ai-methodology)
6. [Section 6: Academic Repository Integrations & External Connectors](#section-6-academic-repository-integrations--external-connectors)
7. [Section 7: Data Model, Relational Schema, & Persistence Integrity](#section-7-data-model-relational-schema--persistence-integrity)
8. [Section 8: Security, Privacy, Isolation, & Reliability Engineering](#section-8-security-privacy-isolation--reliability-engineering)
9. [Section 9: Frontend Architecture, Design System, & User Workflows](#section-9-frontend-architecture-design-system--user-workflows)
10. [Section 10: Complete Verification & Test Results](#section-10-complete-verification--test-results)
11. [Section 11: Defect Remediation History & Release Readiness Status](#section-11-defect-remediation-history--release-readiness-status)
12. [Section 12: Scientific Evaluation, Performance, & Benchmarks](#section-12-scientific-evaluation-performance--benchmarks)
13. [Section 13: Scripted Step-by-Step Live Demonstration Runbook](#section-13-scripted-step-by-step-live-demonstration-runbook)
14. [Section 14: Academic Presentation Narrative (Slide-by-Slide Outline)](#section-14-academic-presentation-narrative-slide-by-slide-outline)
15. [Section 15: Technical Glossary](#section-15-technical-glossary)
16. [Section 16: Presentation Gaps, Limitations, & Future Work](#section-16-presentation-gaps-limitations--future-work)

---

## Section 1: Repository Identity, Environment, & Baseline State

### 1.1 Git Metadata & Branch State
- **Repository Root:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`
- **Current Branch:** `master`
- **Current Head Commit:** `c26cd6a` (`phase-0-foundation`)
- **Working Tree State:** Clean release-engineering and remediation working tree containing verified staged and untracked artifacts representing completed architectural and security tasks (Tasks 1 through 19, Tasks N1–N2, AIML hardening, and PubMed date/FAISS reconciliations).
- **Audit Verification Rule:** 100% read-only extraction. No working-tree changes altered, reverted, or committed.

### 1.2 Technology Stack & Version Manifest

| Layer | Technology | Version | Source File / Manifest |
| :--- | :--- | :--- | :--- |
| **Operating System** | Fedora Linux x86_64 | Linux 6.x | Native Host Environment |
| **Backend Runtime** | Python | `3.14.7` | `backend/venv/bin/python` |
| **Web Framework** | FastAPI / Starlette | `0.115.0` / `0.38.6` | `backend/requirements.txt` |
| **ASGI Server** | Uvicorn | `0.30.6` | `backend/requirements.txt` |
| **Database ORM** | SQLAlchemy | `2.0.35` | `backend/requirements.txt` |
| **Data Validation** | Pydantic / Pydantic Settings | `2.9.2` / `2.5.2` | `backend/requirements.txt` |
| **Database Engine** | PostgreSQL (Containerized) | `16-alpine` | `docker-compose.yml`, Podman Container |
| **Vector Engine** | FAISS (CPU) | `1.10.0` | `backend/requirements.txt` |
| **ML Framework** | PyTorch (CPU) | `2.6.0+cpu` | `backend/requirements.txt` |
| **NLP Transformer** | HuggingFace Transformers | `4.49.0` | `backend/requirements.txt` |
| **Sentence Models** | Sentence-Transformers | `3.1.1` | `backend/requirements.txt` |
| **PDF Extraction** | PyPDF | `4.3.1` | `backend/requirements.txt` |
| **Rate Limiter** | SlowAPI / Limits | `0.1.9` / `3.13.0` | `backend/requirements.txt` |
| **Authentication** | PyJWT / Passlib (Bcrypt) | `2.9.0` / `1.7.4` | `backend/requirements.txt` |
| **Frontend Runtime** | Node.js / NPM | `v24.18.0` / `11.16.0` | Host Runtime |
| **UI Framework** | React / React DOM | `^18.3.1` | `frontend/package.json` |
| **Language** | TypeScript | `^5.5.4` | `frontend/package.json` |
| **Build Tool** | Vite | `^5.4.5` | `frontend/package.json` |
| **Frontend Test** | Vitest / React Testing Library | `^2.1.1` / `^16.0.1` | `frontend/package.json` |
| **Local LLM Engine** | Ollama (`qwen2.5:3b`) | `0.1.x` API | `http://127.0.0.1:11434` |

### 1.3 Directory Topology & Subsystems

```text
research-paper-recommender/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py                  # Database session, auth, and user dependency injection
│   │   │   └── v1/
│   │   │       ├── api.py               # Aggregated V1 API router
│   │   │       ├── health.py            # Diagnostic health probes (/health)
│   │   │       └── endpoints/
│   │   │           ├── auth.py          # User registration, login, and profile (/auth)
│   │   │           ├── papers.py        # Search, PDF ingestion, comparison, DRIUT, FAISS (/papers)
│   │   │           └── research.py      # Timeline, Graph, Gaps, Assistant, AI status (/research)
│   │   ├── core/
│   │   │   ├── config.py                # Environment-driven settings with fail-closed production guards
│   │   │   ├── errors.py                # Centralized exception handlers and HTTP mappings
│   │   │   ├── logging.py               # Structured logger configuration with secret sanitization
│   │   │   ├── rate_limit.py            # Tiered SlowAPI rate limiters with trusted proxy support
│   │   │   └── security.py              # Password hashing (bcrypt) and JWT encode/decode
│   │   ├── db/
│   │   │   ├── base.py & session.py     # SQLAlchemy session maker, engine, and test shields
│   │   │   ├── init_db.py               # Database bootstrap and schema creation
│   │   │   ├── migrate.py               # Idempotent table and column migration scripts
│   │   │   ├── migrate_pubmed_dates.py  # Verified PubMed epub date normalization script
│   │   │   └── seed_admin.py            # Secure admin seeding utility
│   │   ├── models/
│   │   │   ├── paper.py                 # Paper and SavedPaper relational models
│   │   │   ├── user.py                  # User credential and authorization model
│   │   │   ├── driut.py                 # DRIUTAlert tracking and relationship model
│   │   │   └── evidence.py              # PaperEvidence grounded claim and span model
│   │   ├── schemas/
│   │   │   ├── auth.py                  # Authentication schemas (Token, UserProfile)
│   │   │   ├── paper.py                 # Paper, Search, Compare, DRIUT schemas
│   │   │   ├── research.py              # Timeline, Graph, Gap Exploration, Assistant schemas
│   │   │   └── evidence.py              # Evidence extraction and verification schemas
│   │   └── services/
│   │       ├── academic_sources.py      # Connectors for arXiv, PubMed, CSIR-NIScPR, Crossref, etc.
│   │       ├── ai_output_guard.py       # Deterministic post-generation security & prompt injection shield
│   │       ├── ai_provider.py           # Multi-provider coordinator (Ollama, Groq, Deterministic)
│   │       ├── assistant_service.py     # Grounded research question answering engine
│   │       ├── comparison_service.py    # 12-dimension structured paper comparison engine
│   │       ├── deduplication.py         # Multi-source DOI and Levenshtein title deduplication
│   │       ├── driut_scheduler.py       # Background update scanner with PostgreSQL advisory locks
│   │       ├── driut_service.py         # 6-tier relationship classifier with Step 8b chronology guard
│   │       ├── embedding_service.py     # SPECTER2 model loader (768d) with caching & validation
│   │       ├── evidence_service.py      # Grounded claim parser with exact character spans & hash
│   │       ├── evolution_service.py     # Timeline builder, relationship graph, and gap explorer
│   │       ├── notification_service.py  # User alert delivery and logging boundary
│   │       ├── pdf_service.py           # PyPDF extraction, sanitize, validate, and metadata parse
│   │       ├── recommendation_engine.py # Hybrid search, floor calibration, and explainability
│   │       ├── summary_service.py       # Abstract-only disclosure summaries & fallback generators
│   │       ├── text_processor.py        # Text normalization, keyword extraction, and stopword filters
│   │       └── vector_index.py          # FAISS vector lifecycle, atomic reindexing, and backup
│   ├── data/
│   │   └── processed/faiss/             # Persistent vector storage
│   │       ├── research_index.faiss     # Binary FAISS FlatIP index (162 vectors, 768 dimensions)
│   │       └── papers_meta.json         # JSON ID map and metadata records (162 entries)
│   ├── tests/                           # Complete pytest suite (329 tests)
│   └── venv/                            # Isolated virtual environment
├── frontend/
│   ├── src/
│   │   ├── components/                  # Focused React components
│   │   │   ├── AuthModal.tsx            # Login and registration modal
│   │   │   ├── CompareModal.tsx         # 12-dimension comparative matrix dialog
│   │   │   ├── DriutAlertsView.tsx      # DRIUT impact feed with taxonomy filter
│   │   │   ├── EvidenceModal.tsx        # Exact character offset passage inspector
│   │   │   ├── Navbar.tsx               # Header, theme toggle, and auth controls
│   │   │   ├── PaperCard.tsx            # Paper card with badges, scores, and actions
│   │   │   ├── PdfUploadZone.tsx        # Drag-and-drop PDF preview & explicit ingestion
│   │   │   ├── ResearchEvolutionView.tsx# Timeline, Relationship Graph, Gaps, and Assistant
│   │   │   ├── SavedLibraryView.tsx     # User's personal saved library
│   │   │   └── SummaryModal.tsx         # Grounded paper summary view
│   │   ├── layouts/MainLayout.tsx       # Root layout container
│   │   ├── pages/HomePage.tsx           # Primary tabbed application shell
│   │   ├── services/api.ts              # Typed API client with token interceptors
│   │   ├── types/                       # TypeScript interfaces for papers, research, auth, health
│   │   └── index.css                    # Vanilla CSS design tokens (zero Tailwind)
│   └── package.json                     # Vite, React 18, Vitest configuration
├── scripts/
│   ├── dev-start.sh                     # Idempotent development startup script
│   ├── dev-status.sh                    # Diagnostic runtime verification script
│   ├── dev-stop.sh                      # Clean shutdown script
│   ├── reconcile_faiss_postgres.py      # Verified atomic FAISS single-orphan reconciliation tool
│   └── verify_backup_restore.py         # Automated database and vector backup verification
├── backups/                             # Verified pre-reconciliation snapshots
└── docker-compose.yml                   # Containerized PostgreSQL service definition
```

### 1.4 Environment Configuration & Security Policy
Application configuration is managed by `backend/app/core/config.py` using Pydantic Settings. Sensitive variables are loaded dynamically from environment variables or local `.env` files. **Crucial Security Rule:** All production deployments reject insecure or default JWT secret keys and require a minimum 32-character high-entropy secret.

| Configuration Variable | Safe Default / Local Dev Value | Purpose & Production Constraint |
| :--- | :--- | :--- |
| `APP_NAME` | `research-paper-recommender` | Application identifier |
| `APP_VERSION` | `0.1.0` | Release semantic version |
| `ENVIRONMENT` | `development` / `production` | Environment flag (`production` triggers fail-closed security) |
| `DATABASE_URL` | `postgresql+psycopg2://...:5432/research_papers` | Database connection string (redacted in all logs) |
| `BACKEND_HOST` / `PORT` | `0.0.0.0` / `8000` | Backend API host and port binding |
| `FRONTEND_URL` | `http://localhost:3000` | Frontend web URL |
| `CORS_ORIGINS` | `["http://localhost:3000", "http://127.0.0.1:3000"]` | Whitelisted cross-origin origins |
| `JWT_SECRET_KEY` | `[REDACTED]` | HMAC-SHA256 signing secret (enforces $\ge 32$ chars in prod) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24 Hours) | Bearer token lifespan |
| `MAX_UPLOAD_SIZE_BYTES` | `15728640` (15 MB) | PDF upload ceiling |
| `ENABLE_RATE_LIMITING` | `True` | Activates SlowAPI request throttling |
| `RATE_LIMIT_LOGIN` | `5/minute` | Brute-force protection on authentication endpoints |
| `ENABLE_DRIUT_SCHEDULER` | `True` | Toggles background DRIUT impact scanner |
| `DRIUT_SCAN_INTERVAL_MINUTES` | `60` | Background update polling frequency |
| `DRIUT_ADVISORY_LOCK_KEY` | `7376232` | 64-bit PostgreSQL advisory lock preventing concurrent worker collisions |
| `RESEARCHLENS_AI_ENABLED` | `True` / `False` | Master switch for generative AI features |
| `RESEARCHLENS_AI_PROVIDER` | `local_first` | Priority routing: `local_first`, `groq_only`, `deterministic_only` |
| `RESEARCHLENS_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Air-gapped on-premises Ollama inference URL |
| `RESEARCHLENS_OLLAMA_MODEL` | `qwen2.5:3b` | Local model tag |
| `RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT`| `False` | **Strict Privacy Shield:** Blocks transmitting research text to cloud APIs |
| `GROQ_API_KEY` | `[REDACTED]` | Optional cloud API key for off-premises failover |
| `RESEARCHLENS_GROQ_MODEL` | `llama-3.3-70b-versatile` | Cloud model identifier |

---

## Section 2: Problem Statement, Research Objectives, & Academic Contributions

### 2.1 The Academic Literature Review Crisis
Modern researchers face an unprecedented rate of publication, often characterized as "scholarly information overload":
- **Fragmentation Across Silos:** Computer science (arXiv), biomedical and life sciences (PubMed / NIH), regional repositories (CSIR-NIScPR India), and commercial publishers (Crossref / Semantic Scholar) operate in separate silos with disparate search syntax and metadata formats.
- **The Vocabulary Mismatch Problem:** Traditional Boolean/keyword search engines fail when authors use synonymous terminology, distinct acronyms, or novel phrasing to describe identical theoretical concepts.
- **Hallucinations in Generative AI:** General-purpose Large Language Models (LLMs) frequently hallucinate non-existent citations, invent benchmark results, conflate unrelated datasets, or state ungrounded claims with high confidence.
- **Longitudinal Blind Spots:** Researchers struggle to determine the genealogical lineage of an idea—whether a newly published paper extends, empirically improves upon, reproduces, directly challenges, or offers an alternative paradigm to a baseline work.
- **Alert Fatigue:** Existing citation trackers alert researchers only after formal peer-reviewed citation graphs update (which takes 6–18 months), or flood user inboxes with noisy keyword matches lacking semantic relevance or chronological validity.

### 2.2 Intended User Personas & Academic Workflows
1. **Academic Researchers & Principal Investigators (PIs):** Need to identify emerging breakthroughs, verify methodology claims, track competitors' progress, and monitor incoming updates against their core publications.
2. **PhD Candidates & Graduate Students:** Conducting exhaustive literature reviews, identifying genuine research gaps, comparing baseline models, and finding verified limitation quotes to justify new dissertations.
3. **R&D Scientists & Industrial Practitioners:** Seeking production-ready architectures, comparing latency/throughput across models, and auditing claims on identical benchmarks before internal adoption.

### 2.3 System Aim & Measurable Objectives
- **Aim:** To develop, verify, and deliver a production-ready, evidence-grounded research paper recommendation and intelligence system that eliminates hallucination, automates multi-paper comparison, and tracks directional research impact over time.
- **Measurable Objectives:**
  1. *Sub-Second Hybrid Retrieval:* Retrieve and rank candidate papers across local catalogs and external APIs in under 1.5 seconds.
  2. *Dense Semantic Fidelity:* Attain conceptual alignment using domain-adapted scientific sentence embeddings (`allenai/specter2_base`) with an empirically calibrated relevance floor ($0.835$) that eliminates out-of-domain false positives.
  3. *Verifiable Claim Grounding:* Guarantee that $100\%$ of synthesized summaries, comparison points, and assistant answers link to verifiable source passages with exact character offsets.
  4. *Directional Impact Tracking:* Classify updates into 6 distinct impact categories with a chronology guard that completely blocks reverse-time invalid claims.
  5. *Zero Privacy Leakage:* Provide air-gapped on-premises local AI processing, ensuring unpublished manuscripts and confidential research queries never exit the local network.

### 2.4 Differentiators vs Traditional Keyword Search & Commercial Tools

| Feature Dimension | Traditional Keyword Search (e.g. Google Scholar, DBLP) | Generic LLM Chat (e.g. ChatGPT, Perplexity) | ResearchLens (This Implementation) |
| :--- | :--- | :--- | :--- |
| **Search Mechanism** | Lexical token matching (BM25 / TF-IDF) | Generative parametric completion | **Hybrid Fusion:** SPECTER2 dense semantic vectors + exact lexical matching |
| **Relevance Thresholding** | Arbitrary rank ordering; returns low-relevance results | Does not filter; always outputs text | **Calibrated Semantic Floor ($0.835$):** Drops out-of-domain concepts unless exact token match exists |
| **Source Grounding** | Shows snippet containing keyword | Claims often unlinked or generalized | **Exact Character Spans:** Deterministic quotes with `[char_start, char_end]` and SHA-256 verification |
| **Paper Comparison** | Manual reading and tab-switching | Hallucinates tables; mixes metrics | **12-Dimension Matrix:** Explicit incomparability disclosures across disparate benchmarks |
| **Update Tracking** | Citation alerts (delayed by months) | Static knowledge cutoff date | **DRIUT Engine:** Continuous monitoring with 6-tier impact taxonomy and Step 8b chronology guard |
| **Data Privacy** | Queries logged and indexed | User prompts sent to commercial cloud | **Local-First Air-Gapped Architecture:** Local Ollama execution; cloud transmission blocked by default |
| **Manuscript Ingestion** | Search-only or index-only | Uploads whole document to third party | **Two-Phase Upload:** Client-side preview, duplicate checking, followed by explicit catalog/FAISS sync |

### 2.5 Scope Boundaries & Stated Invariants
- **Catalog Scale:** Current local baseline catalog contains 162 highly curated papers across Computer Science, AI, and Biomedical Engineering.
- **Search Ingestion Decoupling:** Ordinary user searches across external sources (arXiv, PubMed, etc.) return transient candidates in-memory. They **never** mutate the persistent PostgreSQL database or FAISS vector index unless explicitly ingested via the two-phase workflow.
- **Truthfulness on Local Corpus Limitations:** When the system analyzes research gaps or timelines, it explicitly discloses: *"Local catalog boundaries disclosed; absence from local catalog does not establish global scientific novelty."*

---

## Section 3: Comprehensive Feature & Subsystem Matrix

The repository features have been extracted and mapped into the standardized status classifications:
- `IMPLEMENTED — SOURCE VERIFIED`: Source code fully inspected, verified, and active.
- `IMPLEMENTED — TEST EVIDENCE AVAILABLE`: Verified by passing automated tests in the test suite.
- `LIVE VERIFIED`: Tested and confirmed operational in the running local environment.
- `PARTIALLY IMPLEMENTED`: Code exists and operates, but has documented boundaries or optional components.

| # | Subsystem / Feature | User-Facing Purpose | Implementation Status | Relevant Source Files & Key Symbols | API Routes | DB Tables / Persistent Artifacts | Main Algorithms & Steps | Test & Verification Evidence | Known Limitations & Dependencies |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Hybrid Search & Recommendation Engine** | Enables researchers to find relevant literature combining conceptual meaning with specific keywords. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/recommendation_engine.py`<br>`execute_recommendation_search()`, `_has_lexical_match()` | `POST /api/v1/papers/search` | `papers`, `research_index.faiss`, `papers_meta.json` | 1. Query vectorization (SPECTER2).<br>2. FAISS IndexFlatIP search.<br>3. In-memory deduplication.<br>4. Semantic floor filtering ($0.835$).<br>5. Multi-criteria sorting. | `test_papers_api.py::test_semantic_search_returns_relevant_recommendations`<br>`test_targeted_remediations.py::test_semantic_relevance_floor_value` | Requires SPECTER2 model loaded in RAM; queries < 3 chars return empty results. |
| **2** | **FAISS Vector Index Management** | High-performance sub-second similarity retrieval on 768-dimensional embeddings. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/vector_index.py`<br>`FAISSIndex`, `get_faiss_index()`, `reindex_all_papers()` | `GET /api/v1/papers/index-status`<br>`POST /api/v1/papers/reindex-faiss`<br>`POST /api/v1/papers/sync-index` | `research_index.faiss`<br>`papers_meta.json` | 1. Thread RLock + PostgreSQL advisory lock ($7376233$).<br>2. Vector extraction & L2 normalization.<br>3. Atomic `.tmp` file swap with `.bak` preservation. | `test_embedding_and_sync.py`<br>`test_faiss_consistency.py`<br>`scripts/verify_backup_restore.py` | CPU-based FAISS index (`faiss-cpu`); memory scale bounded by available system RAM. |
| **3** | **Decoupled Academic Source Connectors** | Live federated searching across major international scientific repositories. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/academic_sources.py`<br>`search_arxiv()`, `search_pubmed()`, `search_csir_niscpr()`, `search_crossref()` | Invoked by `POST /api/v1/papers/search` | Transient in-memory candidates (zero DB mutation) | 1. Asynchronous HTTP requests via `httpx`.<br>2. XML/JSON payload parsing.<br>3. Date normalization via `parse_pubmed_dates()`.<br>4. Rate limit & timeout handling. | `test_academic_sources.py`<br>`test_search_ingestion_decoupling.py` | External network connectivity required; public rate limits apply without API keys. |
| **4** | **Two-Phase PDF Upload & Ingestion** | Allows uploading custom manuscripts with extraction, preview, and explicit catalog insertion. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/pdf_service.py`<br>`backend/app/api/v1/endpoints/papers.py`<br>`preview_pdf_manuscript()`, `ingest_pdf_manuscript()` | `POST /api/v1/papers/preview-pdf`<br>`POST /api/v1/papers/ingest-pdf` | `papers`, `paper_evidence`, `research_index.faiss` | 1. Phase 1: Magic byte validation (`%PDF-`), PyPDF parsing, duplicate check, recommendations preview.<br>2. Phase 2: Explicit user confirmation commits to PostgreSQL and FAISS. | `test_n2_pdf_ingestion.py`<br>`test_pdf_upload.py` | Max 15MB file size; encrypted or scanned/OCR-less PDFs rejected. |
| **5** | **Multi-Source Deduplication** | Prevents duplicate records across diverse repositories and preprint servers. | `IMPLEMENTED — SOURCE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/deduplication.py`<br>`deduplicate_papers()`, `calculate_title_similarity()` | Used across search, PDF upload, and DRIUT | In-memory candidate processing | 1. Exact DOI normalization.<br>2. Exact lowercase alphanumeric title matching.<br>3. Levenshtein edit distance & token sort ratio threshold ($0.85$). | `test_search_ingestion_decoupling.py::test_duplicate_external_candidate_deduplication` | Highly abbreviated titles or titles in foreign languages may challenge threshold. |
| **6** | **Grounded Evidence Extraction** | Extracts verifiable scientific claims directly mapped to source sentence offsets. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/evidence_service.py`<br>`extract_evidence_from_text()`, `verify_evidence_record()` | `GET /api/v1/papers/{id}/evidence`<br>`POST /api/v1/papers/evidence` | `paper_evidence` | 1. Sentence splitting with regex span tracking.<br>2. 9-category pattern scoring.<br>3. Exact character offset calculation `[char_start, char_end]`.<br>4. Source SHA-256 hash generation. | `test_evidence_extraction.py`<br>`test_targeted_remediations.py::test_evidence_extraction_rejects_placeholder_abstract` | Relies on English syntactic structures; abstract-only papers have bounded coverage. |
| **7** | **Abstract-Only Disclosure Summarization** | Generates structured summaries disclosing coverage depth and avoiding hallucination. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/summary_service.py`<br>`generate_paper_summary()` | `GET /api/v1/papers/{id}/summary`<br>`POST /api/v1/papers/summary` | `papers`, `paper_evidence` | 1. Evidence extraction from DB or text.<br>2. Abstract-only coverage qualification.<br>3. Local LLM synthesis with strict grounding prompt.<br>4. Deterministic fallback if offline. | `test_papers_api.py::test_paper_summary_endpoint`<br>`test_targeted_remediations.py::test_paper_summary_rejects_placeholder_abstract` | Synthetic placeholder abstracts rejected immediately. |
| **8** | **Structured Multi-Paper Comparison** | Side-by-side evaluation of up to 5 papers across 12 rigorous dimensions. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/comparison_service.py`<br>`compare_papers_structured()` | `POST /api/v1/papers/compare` | Transient in-memory or persisted `paper_evidence` | 1. Dimension alignment (Problem, Method, Metrics, Limitations, etc.).<br>2. Benchmark comparability checking.<br>3. Flags disparate metrics as incomparable.<br>4. Zero fabrication. | `test_paper_comparison.py` (11 comprehensive tests) | Maximum 5 papers per comparison request; requires minimum 2 papers. |
| **9** | **DRIUT Impact Update Tracker Engine** | Monitors new literature and classifies directional relationships against saved papers. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/driut_service.py`<br>`classify_relationship_evidence()` | `GET /api/v1/papers/driut/alerts`<br>`POST /api/v1/papers/driut/scan` | `driut_alerts`, `saved_papers`, `papers` | 1. Semantic proximity filter.<br>2. 6 taxonomy category pattern evaluation.<br>3. Benchmark comparability filter.<br>4. **Step 8b Chronology Guard:** Rejects earlier candidate claiming to improve later paper. | `test_driut_intelligence.py`<br>`test_targeted_remediations.py::test_driut_chronology_later_improves_earlier` | Pre-guard historical database records (90 alerts) await automated cleanup. |
| **10**| **DRIUT Background Scheduler** | Autonomous background daemon polling for new research updates. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/driut_scheduler.py`<br>`DRIUTBackgroundScheduler`, `run_driut_scan_workflow()` | `GET /api/v1/papers/driut/status` | `driut_alerts`, PostgreSQL advisory lock | 1. Async background worker thread.<br>2. Non-blocking PostgreSQL advisory lock ($7376232$).<br>3. Queries academic sources for saved papers.<br>4. Deduplicates and persists new alerts. | `test_driut_scheduler.py` (7 tests covering advisory locks, dispatch, intervals) | Disabled when `ENABLE_DRIUT_SCHEDULER=False`. |
| **11**| **Research Evolution Timeline** | Chronological visual mapping of research methods, datasets, and findings over time. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/evolution_service.py`<br>`build_research_timeline()` | `GET /api/v1/research/timeline` | `papers`, `paper_evidence` | 1. Filters by topic/year range.<br>2. Separates publication year from ingestion timestamp.<br>3. Transparently isolates undated papers.<br>4. Groups claims into chronological bands. | `test_research_evolution.py::test_timeline_chronological_ordering`<br>`test_research_evolution.py::test_timeline_undated_paper_isolation` | Undated papers rendered in a distinct drawer to prevent chronological distortion. |
| **12**| **Citation & Thematic Relationship Graph** | Interactive network graph revealing inter-paper relationships with strict provenance. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/evolution_service.py`<br>`build_relationship_graph()` | `GET /api/v1/research/graph` | `papers`, `driut_alerts` | 1. Node generation with degree and metadata.<br>2. Edge formation based on explicit DRIUT relationships or cosine similarity ($> 0.45$).<br>3. Distinguishes author-stated from inferred edges. | `test_research_evolution.py::test_relationship_graph_author_stated_vs_inferred` | Bounded at 50 nodes maximum for rendering performance. |
| **13**| **Candidate Research-Gap Discovery** | Synthesizes grounded research gaps from recurring limitations and future-work quotes. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/evolution_service.py`<br>`explore_candidate_gaps()` | `POST /api/v1/research/gaps` | `paper_evidence`, `papers` | 1. Clusters verified `limitations` and `future_work` claims across papers.<br>2. Evaluates topic coverage density.<br>3. Synthesizes hypothesis.<br>4. Discloses corpus boundary. | `test_research_evolution.py::test_gap_explorer_sparse_corpus_insufficient_evidence` | Requires at least 3 papers in topic cluster; never claims global novelty. |
| **14**| **Grounded Research Assistant (Q&A)** | Scholarly Q&A assistant answering user inquiries strictly from retrieved paper evidence. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/assistant_service.py`<br>`answer_research_question()` | `POST /api/v1/research/assistant` | `paper_evidence`, `papers` | 1. Input sanitization.<br>2. Intent classification (limitations, comparisons, future work).<br>3. Evidence retrieval & span assembly.<br>4. Local LLM prompting with strict context.<br>5. Deterministic fallback. | `test_research_assistant.py` (12 comprehensive tests covering security, privacy, failover) | Answers strictly bounded by available evidence; refuses ungrounded questions. |
| **15**| **Unified AI Output Security Guard** | Deterministic post-generation security shield blocking injection, leaks, and canaries. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/ai_output_guard.py`<br>`enforce_ai_output_security_guard()` | Intercepts all AI generation workflows | In-memory evaluation | 1. Scans for attack canaries (`HACKED`).<br>2. Blocks DB connection URIs.<br>3. Blocks env vars (`DATABASE_URL`, `JWT_SECRET`).<br>4. Blocks raw JWT tokens.<br>5. Safe canonical refusal fallback. | `test_assistant_security_guard.py`<br>`test_research_assistant.py::test_assistant_prompt_injection_safety` | Fails closed on any parsing exception. |
| **16**| **Dual AI Provider Architecture** | Pluggable coordinator supporting Local Ollama, Cloud Groq, and Deterministic NLP. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/services/ai_provider.py`<br>`AIServiceCoordinator`, `OllamaProvider`, `GroqProvider` | `GET /api/v1/research/ai/status` | Configuration settings | 1. Concurrency throttling (`asyncio.Semaphore(4)`).<br>2. Local-first preference.<br>3. Cloud privacy gate verification.<br>4. Automatic bounded failover (15s timeout). | `test_ai_providers.py` (7 tests covering provider failover, privacy, and timeouts) | Cloud failover requires `RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT=True`. |
| **17**| **Authentication & User Data Isolation** | Secure JWT bearer authentication and complete cross-user data isolation. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/core/security.py`<br>`backend/app/api/v1/endpoints/auth.py` | `POST /api/v1/auth/register`<br>`POST /api/v1/auth/login`<br>`GET /api/v1/auth/me` | `users`, `saved_papers`, `driut_alerts` | 1. Password hashing via Passlib Bcrypt.<br>2. HS256 JWT encoding with exp claims.<br>3. Strict SQL foreign key scoping (`user_id`).<br>4. Production secret fail-closed validation. | `test_auth_and_isolation.py` (10 tests covering password safety, tampering, isolation) | Bearer tokens expire in 24 hours. |
| **18**| **Saved Papers Library** | Allows authenticated researchers to bookmark papers and manage research collections. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/api/v1/endpoints/papers.py`<br>`get_saved_papers()`, `save_paper_to_library()` | `GET /api/v1/papers/saved`<br>`POST /api/v1/papers/save`<br>`DELETE /api/v1/papers/saved/{id}` | `saved_papers`, `papers` | 1. Relational unique constraint `(user_id, paper_id)`.<br>2. Triggers baseline registration for DRIUT monitoring.<br>3. Cascade deletion. | `test_papers_api.py::test_saved_papers_workflow` | Unauthenticated requests fall back to default demo profile. |
| **19**| **Tiered Rate Limiting & Proxy Shield** | Prevents API abuse and brute-force attacks across endpoints. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/core/rate_limit.py`<br>`get_remote_address()`, `limiter` | Applied to `/auth/login`, `/papers/search`, etc. | In-memory SlowAPI rate-limiting storage | 1. Client IP extraction evaluating `X-Forwarded-For`.<br>2. Trusted proxy subnet validation.<br>3. 5 requests/minute on login; 30/minute on search. | `test_rate_limiter.py` (4 tests verifying IP isolation, login limit, and proxy trust) | Relies on accurate reverse proxy headers in multi-tier production networks. |
| **20**| **Diagnostic Health & Index Diagnostics** | Deep system diagnostics reporting DB, FAISS, and model readiness without exposing secrets. | `LIVE VERIFIED`<br>`IMPLEMENTED — TEST EVIDENCE AVAILABLE` | `backend/app/api/v1/health.py`<br>`backend/app/api/v1/endpoints/papers.py` | `GET /api/v1/health`<br>`GET /api/v1/papers/index-status` | Database engine probe, FAISS index probe | 1. Active SQL connection ping.<br>2. Vector count vs catalog record count verification.<br>3. Embedding model dimension verification ($768$). | `test_defect_remediation_regression.py`<br>`scripts/dev-status.sh` | Read-only probe; does not mutate system state. |

---

## Section 4: System Architecture & End-to-End Data Flows

### 4.1 High-Level Component Topology

```mermaid
graph TB
    subgraph ClientLayer ["Client Layer (Browser / Desktop)"]
        UI["React 18 + TypeScript Web Interface<br>(Vite, Vanilla CSS Design Tokens, Port 3000)"]
    end

    subgraph GatewayLayer ["Network & Reverse Proxy Layer"]
        Nginx["Nginx / Native Port Forwarder"]
        RateLimit["SlowAPI Rate Limiter<br>(5/min auth, 30/min search, trusted proxy aware)"]
    end

    subgraph AppLayer ["Backend Application Layer (FastAPI, Port 8000)"]
        Router["V1 API Router<br>(/auth, /papers, /research, /health)"]
        AuthService["Auth & Security Engine<br>(JWT HS256, Passlib Bcrypt, User Isolation)"]
        SearchEngine["Hybrid Recommendation Engine<br>(Floor 0.835, Explainability, Multi-Criteria)"]
        EvidenceEngine["Evidence Extraction Service<br>(Sentence Spans, SHA-256 Hashes, 9 Categories)"]
        CompareEngine["12-Dimension Comparison Engine<br>(Benchmark Guard, Incomparability Disclosures)"]
        DRIUTEngine["DRIUT Impact Engine<br>(6 Taxonomy Categories, Step 8b Chronology Guard)"]
        EvolutionEngine["Research Evolution Engine<br>(Timeline, Relationship Graph, Gap Synthesis)"]
        AssistantEngine["Grounded Research Assistant<br>(Evidence Context Assembly, Zero Fabrication)"]
        SecurityGuard["AI Output Security Guard<br>(Canary Defense, Credential Leak Redaction)"]
        AICoordinator["AI Multi-Provider Coordinator<br>(Local-First, Timeout 15s, Semaphore 4)"]
    end

    subgraph ExternalSources ["Academic Repository Connectors (Decoupled & Transient)"]
        arXiv["arXiv API (Atom XML)"]
        PubMed["PubMed / NCBI NIH E-Utilities"]
        CSIR["CSIR-NIScPR (Gov of India)"]
        Crossref["Crossref Metadata API"]
        SemanticScholar["Semantic Scholar Graph API"]
    end

    subgraph IntelligenceLayer ["Dual AI & Embedding Engines"]
        SPECTER2["AllenAI SPECTER2 Model<br>(768d L2-Normalized, PyTorch CPU)"]
        Ollama["Local Ollama Instance<br>(qwen2.5:3b, Port 11434, Air-Gapped)"]
        Groq["Cloud Groq API<br>(llama-3.3-70b-versatile, Optional Failover)"]
        Deterministic["Deterministic NLP Fallback<br>(Guaranteed Rule-Based Baseline)"]
    end

    subgraph PersistenceLayer ["Persistence & Vector Storage"]
        Postgres[("PostgreSQL 16 Database<br>(Port 5432: users, papers, saved_papers,<br>paper_evidence, driut_alerts)")]
        FAISS[("FAISS Vector Index (CPU)<br>(research_index.faiss: 162 vectors, 768d,<br>papers_meta.json: 162 mapped records)")]
    end

    UI --> Nginx
    Nginx --> RateLimit
    RateLimit --> Router
    Router --> AuthService
    Router --> SearchEngine
    Router --> EvidenceEngine
    Router --> CompareEngine
    Router --> DRIUTEngine
    Router --> EvolutionEngine
    Router --> AssistantEngine

    SearchEngine --> ExternalSources
    SearchEngine --> SPECTER2
    SearchEngine --> FAISS
    SearchEngine --> Postgres

    EvidenceEngine --> Postgres
    CompareEngine --> EvidenceEngine
    DRIUTEngine --> Postgres
    DRIUTEngine --> SPECTER2
    EvolutionEngine --> Postgres
    EvolutionEngine --> DRIUTEngine

    AssistantEngine --> AICoordinator
    CompareEngine --> AICoordinator
    AICoordinator --> Ollama
    AICoordinator --> Groq
    AICoordinator --> Deterministic
    AICoordinator --> SecurityGuard

    AuthService --> Postgres
```

### 4.2 End-to-End Hybrid Retrieval & Explainable Ranking Flow

```mermaid
sequenceDiagram
    autonumber
    actor Researcher as User / Browser
    participant API as FastAPI (/papers/search)
    participant Engine as Recommendation Engine
    participant Ext as Academic Connectors (arXiv, PubMed, etc.)
    participant Embed as SPECTER2 Embedding Service
    participant FAISS as FAISS Index (IndexFlatIP)
    participant DB as PostgreSQL Database

    Researcher->>API: POST /api/v1/papers/search {query, mode, sources, sort_by}
    API->>Engine: execute_recommendation_search()
    
    par Local Vector Retrieval
        Engine->>Embed: generate_embedding(query)
        Embed-->>Engine: 768-dim query vector
        Engine->>FAISS: search(query_vector, top_k=30)
        FAISS-->>Engine: local_candidate_ids + cosine_scores
    and External Source Search (Optional)
        opt If external sources enabled
            Engine->>Ext: search_all_sources(query, limit=5)
            Ext-->>Engine: transient_external_candidates (arXiv, PubMed, CSIR)
        end
    end

    Engine->>Engine: deduplicate_papers(local + external, threshold=0.85)
    Engine->>DB: Resolve existing database primary keys read-only
    DB-->>Engine: ID mappings (Zero inserts)

    loop For each candidate paper
        alt Pure Semantic Candidate (No keyword match in title/abstract)
            Engine->>Engine: Evaluate base_sim against SEMANTIC_RELEVANCE_FLOOR (0.835)
            opt If base_sim < 0.835
                Engine->>Engine: Drop candidate (Filter out-of-domain noise)
            end
        else Has Lexical Keyword Match
            Engine->>Engine: Preserve candidate regardless of pure vector score
        end
        Engine->>Engine: Attach explainable recommendation rationale
    end

    Engine->>Engine: Sort by requested mode (relevance, recency, citations)
    Engine-->>API: SearchResponse (top results, execution time, keywords)
    API-->>Researcher: 200 OK + JSON Results & Explanations
```

### 4.3 Two-Phase PDF Upload & Ingestion Flow

```mermaid
sequenceDiagram
    autonumber
    actor Researcher as User / Browser
    participant API as FastAPI Endpoints
    participant PDFService as PDF Extraction Service
    participant Dedupe as Deduplication Service
    participant DB as PostgreSQL Database
    participant FAISS as FAISS Vector Service

    Note over Researcher,API: Phase 1: Upload, Extraction, & Preview (Zero Persistence)
    Researcher->>API: POST /api/v1/papers/preview-pdf (multipart/form-data)
    API->>PDFService: extract_text_from_pdf_bytes(pdf_bytes)
    PDFService->>PDFService: Validate magic bytes (%PDF-), password, page count (>0)
    PDFService->>PDFService: Extract title, abstract, authors, year, DOI, raw text
    PDFService-->>API: Extracted manuscript metadata
    API->>Dedupe: Check duplicate against catalog by DOI and title similarity
    Dedupe-->>API: Duplicate analysis (is_duplicate: bool, existing_id)
    API-->>Researcher: PdfPreviewResponse (metadata, text snippet, recommendations preview)

    Note over Researcher,API: Phase 2: Explicit Catalog Ingestion Confirmation
    Researcher->>API: POST /api/v1/papers/ingest-pdf (JSON payload with user edits & confirm=True)
    API->>DB: Begin transactional paper insertion
    DB-->>API: Persisted Paper record (ID assigned)
    API->>PDFService: Extract initial evidence records (Problem, Method, etc.)
    API->>DB: Insert PaperEvidence records
    API->>FAISS: add_papers([new_paper_dict])
    FAISS->>FAISS: Generate SPECTER2 embedding (768d) & add to IndexFlatIP
    FAISS->>FAISS: Atomically update research_index.faiss and papers_meta.json
    API-->>Researcher: PdfIngestResponse (success=True, paper_id, faiss_synchronized=True)
```

### 4.4 DRIUT Scheduling, Update Monitoring, & Step 8b Chronology Flow

```mermaid
sequenceDiagram
    autonumber
    participant Scheduler as DRIUT Background Scheduler
    participant Lock as PostgreSQL Advisory Lock (7376232)
    participant DB as PostgreSQL Database
    participant Ext as Academic Connectors (arXiv, PubMed, etc.)
    participant Classifier as DRIUT Classification Engine (Step 8b)
    participant Alerts as DRIUT Alert Persistence

    Scheduler->>Lock: pg_try_advisory_lock(7376232)
    alt Lock Acquired
        Scheduler->>DB: Fetch all saved papers across active users
        DB-->>Scheduler: List of saved baseline papers
        
        loop For each saved paper
            Scheduler->>Ext: Query new external publications matching topic/keywords
            Ext-->>Scheduler: Candidate update publications
            
            loop For each candidate paper
                Scheduler->>Classifier: classify_relationship_evidence(saved_paper, candidate)
                Classifier->>Classifier: Extract effective publication years (epub vs print issue)
                
                alt Category is Directional (Improvement, Extension, Challenge, Reproduction, Replacement)
                    Classifier->>Classifier: Step 8b Chronology Guard: Evaluate candidate_year vs saved_year
                    alt candidate_year < saved_year
                        Classifier-->>Scheduler: REJECT (Chronological conflict: earlier paper cannot improve later)
                    else candidate_year >= saved_year
                        Classifier->>Classifier: Check metric/dataset comparability
                        Classifier-->>Scheduler: ACCEPT with verified evidence passage & confidence
                    end
                else Category is Alternative
                    Classifier-->>Scheduler: ACCEPT (Exempt from directional chronology restriction)
                end

                opt If Relationship Accepted & Supported
                    Scheduler->>Alerts: Persist DRIUTAlert with user_id, confidence, quotes, offsets
                end
            end
        end
        Scheduler->>Lock: pg_advisory_unlock(7376232)
    else Lock Held by Another Worker
        Scheduler->>Scheduler: Skip cycle gracefully; zero collision
    end
```

---

## Section 5: NLP, Machine Learning, Retrieval, & AI Methodology

### 5.1 Document Extraction & Text Preprocessing
- **PDF Extraction Engine:** PyPDF (`pypdf.PdfReader`) with in-memory byte stream processing (`io.BytesIO`).
- **Sanitization & Safety Invariants:**
  1. *Magic Byte Validation:* Verifies `%PDF-` header magic bytes; rejects spoofed executables or HTML files.
  2. *Encryption Rejection:* Detects encrypted and password-protected files immediately, returning a user-friendly diagnostic.
  3. *Scanned / OCR-Less Document Rejection:* Detects 0-page PDFs or documents with 0 extractable text characters, explicitly advising the user that scanned PDFs require OCR preprocessing.
  4. *Memory Bounding:* Caps extracted raw text at $500,000$ characters per document to prevent memory exhaustion attacks.
  5. *Metadata Extraction Heuristics:* Parses header blocks on the first page using regular expressions to capture Title, Authors, Abstract, Publication Year, DOI, and Publication Venue.

### 5.2 Dense Semantic Representation (SPECTER2)
- **Model Identifier:** `allenai/specter2_base` from HuggingFace Hub.
- **Architecture & Domain Adaptation:** BERT-based scientific transformer pre-trained on citation graphs and scientific paper abstracts. Unlike generic sentence models, SPECTER2 maps papers close together if they share methodological or conceptual lineage even without overlapping keywords.
- **Dimensionality:** Exactly $768$ dimensions (`EXPECTED_EMBEDDING_DIMENSION = 768`).
- **Normalization:** All vectors are explicitly L2-normalized ($||\mathbf{v}||_2 = 1.0$) upon output.
- **In-Memory Caching:** Embeddings are keyed by MD5 text hashes in `_EMBEDDING_CACHE`, ensuring identical strings (e.g. repeated queries or baselines) compute in $0.0$ milliseconds.
- **Fail-Closed Dimension Enforcement:** `backend/app/services/embedding_service.py` asserts that the output dimension matches 768. If an incompatible model is supplied, it raises `EmbeddingServiceError` rather than corrupting the vector database.

### 5.3 Vector Search Index (FAISS)
- **Index Type:** `faiss.IndexFlatIP` (Exact Inner Product). Because all embeddings are L2-normalized, inner product mathematically equals **Cosine Similarity**:
  $$\text{sim}(\mathbf{u}, \mathbf{v}) = \mathbf{u} \cdot \mathbf{v} = \cos(\theta)$$
- **Index Persistence:** Co-located persistent artifacts:
  - `backend/data/processed/faiss/research_index.faiss`: Binary FAISS index containing 162 vectors.
  - `backend/data/processed/faiss/papers_meta.json`: Sequential 0-indexed ID map linking FAISS vector IDs to PostgreSQL primary keys and metadata records.
- **Atomic Re-Indexing & Thread Safety:**
  - Read/write access protected by `_INDEX_LOCK = threading.RLock()`.
  - Re-indexing across multiple workers protected by PostgreSQL session-level advisory lock (`REINDEX_ADVISORY_LOCK_KEY = 7376233`).
  - Disk updates written to `.tmp` files first, followed by atomic OS-level replacement and backup to `.bak` files.

### 5.4 Calibrated Semantic Relevance Floor & Hybrid Scoring Formula
An empirical finding during system audit was that pure cosine similarity in scientific models can produce false positives for out-of-domain queries that share generic academic vocabulary (e.g., words like *system, model, method, analysis*).
- **Calibrated Semantic Floor:** `SEMANTIC_RELEVANCE_FLOOR = 0.835`.
  - In-domain relevant scientific queries score $\ge 0.844$ (top matches $0.863$–$0.937$).
  - Out-of-domain queries (e.g., *"ancient Roman architecture"*) score $\le 0.817$.
  - **Algorithmic Rule:** If a candidate paper has **no lexical match** in its title or abstract with the query tokens, its vector similarity must be $\ge 0.835$; otherwise, it is dropped from the results. If a paper contains an exact lexical match, it is retained regardless of pure vector score.
- **Multi-Criteria Ranking Formula:**
  $$\text{Score}_{\text{relevance}} = \mathbf{w}_{\text{sim}} \cdot \text{Sim}_{\text{SPECTER2}} + \mathbf{w}_{\text{recency}} \cdot \text{Boost}_{\text{year}} + \mathbf{w}_{\text{cit}} \cdot \text{Boost}_{\text{citations}}$$
  - Default sort mode is `relevance`.
  - Recency sort orders by `(year DESC, similarity_score DESC, citation_count DESC)`.
  - Citations sort orders by `(citation_count DESC, similarity_score DESC, year DESC)`.

### 5.5 Grounded Evidence Extraction & Character Span Offsets
Implemented in `backend/app/services/evidence_service.py` to eliminate AI hallucinations:
- **Sentence Splitting with Offsets:** `split_text_into_sentences_with_spans()` parses text while tracking the exact `char_start` and `char_end` relative to the original source text.
- **9 Scientific Claim Categories:**
  1. `problem`: Scientific bottleneck, challenge, or drawback addressed.
  2. `objective`: Stated aim or core research question.
  3. `method`: Proposed novel architecture, algorithm, or methodology.
  4. `dataset`: Benchmark corpus or hardware environment evaluated.
  5. `metrics`: Quantitative evaluation criteria (BLEU, F1, accuracy, etc.).
  6. `results`: Empirical outcomes and SOTA comparisons.
  7. `contributions`: Author-stated novel takeaways.
  8. `limitations`: Weaknesses, vulnerabilities, or scope constraints.
  9. `future_work`: Explicit open problems and prospective research.
- **Synthetic Placeholder Abstract Detection:** Detects legacy boilerplate strings (such as PubMed indexing notices) via `SYNTHETIC_PLACEHOLDER_REGEX` and rejects them immediately, preventing hallucination.
- **Cryptographic Provenance:** Each extraction computes `source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()`. When verifying evidence, any subsequent alteration of the source text flags the evidence as invalid.

### 5.6 Structured Multi-Paper Comparison Across 12 Dimensions
Implemented in `backend/app/services/comparison_service.py`:
- Compares up to 5 papers across 12 dimensions: Research Problem, Objective, Methodology, Dataset/Setup, Evaluation Metrics, Reported Results, Contributions, Limitations, Future Work, Publication Year/Venue, Citations, and Evidence Source Coverage.
- **Disparate Benchmark Incomparability Guard:** When two papers evaluate on different datasets or use non-comparable metrics (e.g., BLEU score on machine translation vs. Top-1 Accuracy on ImageNet), the system refuses to claim one model outperforms the other, explicitly emitting an `IncomparableDimensionDetail` notice.

### 5.7 Longitudinal Research Evolution & Gap Explorer
Implemented in `backend/app/services/evolution_service.py`:
- **Evolution Timeline:** Groups papers into chronological bands based on publication year, cleanly separating ingestion timestamps from verified publication dates. Undated papers are isolated in a dedicated drawer.
- **Relationship Graph:** Nodes represent papers; directed edges represent verified scientific relationships (DRIUT taxonomy) or high-confidence thematic links (cosine similarity $> 0.45$). The UI visually distinguishes explicit author-stated citations from inferred semantic links.
- **Candidate Research-Gap Discovery:** Intersects recurring `limitations` and `future_work` quotes across papers in a topic cluster. Rather than fabricating novelty, it provides candidate hypotheses with full evidence provenance and a mandatory truthfulness disclosure: *"Local catalog boundaries disclosed; local absence does not establish global novelty."*

### 5.8 Dual AI Provider Architecture & Grounded Assistant
Implemented in `backend/app/services/ai_provider.py` and `assistant_service.py`:
- **Provider Routing Modes:**
  - `local_first` (Default): Queries local Ollama instance (`qwen2.5:3b`) at `http://127.0.0.1:11434`. Air-gapped and private.
  - `groq_only`: Uses Groq Cloud API (`llama-3.3-70b-versatile`) when configured and explicitly permitted.
  - `deterministic_only`: Skips generative models entirely, utilizing rule-based template generation.
- **Graceful Failover Policy:** If Ollama is unreachable or times out ($15.0$s), the system checks if cloud fallback is permitted. If `RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT=False` (default), cloud transmission is blocked for data privacy, and it falls back instantly to the deterministic rule-based engine.
- **Concurrency Limiting:** Controlled by `asyncio.Semaphore(4)` to prevent memory exhaustion on local developer machines.

### 5.9 Prompt Injection Defense & AI Output Security Guard
Implemented in `backend/app/services/ai_output_guard.py`:
- **Untrusted Context Isolation:** Retrieved paper text is injected into model prompts enclosed within strict delimiter tags (`<<<BEGIN EVIDENCE>>> ... <<<END EVIDENCE>>>`), with system instructions forbidding the model from following commands contained inside evidence text.
- **Deterministic Post-Generation Security Filters:**
  - Scans for attack canary tokens (e.g. `HACKED`).
  - Scans for database connection strings (`postgresql://...`).
  - Scans for configuration environment variable names (`DATABASE_URL`, `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`).
  - Scans for credential assignment patterns (`password = ...`).
  - Scans for raw JWT bearer tokens (`eyJ...`).
  - Scans for refusal phrases that echo infrastructure names.
  - If any security pattern matches, the response is discarded and replaced with:  
    `"The available catalog evidence is insufficient to conclusively answer this question."`

### 5.10 DRIUT Relationship Taxonomy & Step 8b Chronology Guard
Implemented in `backend/app/services/driut_service.py`:
- **6 Taxonomy Categories:**
  1. *Extension:* Builds upon, extends, or generalizes prior methodology.
  2. *Improvement:* Achieves superior empirical performance on identical benchmarks.
  3. *Challenge:* Questions assumptions, identifies vulnerabilities, or disputes validity.
  4. *Reproduction:* Independently replicates and validates experiments.
  5. *Alternative:* Proposes an orthogonal or divergent paradigm for the same problem.
  6. *Potential Replacement:* Renders prior approaches obsolete or supersedes them.
- **The Step 8b Chronology Guard:** Evaluates candidate publication year against saved baseline publication year. If a relationship is directional (*Improvement, Extension, Challenge, Reproduction, Potential Replacement*) and $\text{Year}_{\text{candidate}} < \text{Year}_{\text{saved}}$, the relationship is rejected:  
  `"Chronological conflict: candidate paper (2017) precedes baseline paper (2026). An earlier publication cannot establish an Improvement of a subsequent work."`  
  *Alternative* paradigm relationships are exempt from directional chronology.

---

## Section 6: Academic Repository Integrations & External Connectors

All connectors are located in `backend/app/services/academic_sources.py` and communicate via non-blocking asynchronous HTTP (`httpx.AsyncClient`).

| Repository | Source File & Function | Protocol / Format | Query Capabilities & Parameters | Returned Metadata | Rate Limiting & Politeness | Status & Limitations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **arXiv** | `academic_sources.py`<br>`search_arxiv()` | REST / Atom XML Feed | `search_query=all:...`, `start`, `max_results`, `sortBy=submittedDate` | Title, Abstract, Authors, Venue (arXiv), Year, DOI, PDF URL, Categories | 3.0s polite delay between automated bulk calls | `LIVE VERIFIED`<br>Free public access; no credentials required. |
| **PubMed / NCBI NIH** | `academic_sources.py`<br>`search_pubmed()` | NCBI Entrez E-Utilities (XML) | `esearch.fcgi` (UID search) followed by `efetch.fcgi` (metadata) | Title, Abstract, Authors, Journal, EpubDate, PubDate, DOI, PubMed ID | 3 requests/sec without API key (10 req/s with `NCBI_API_KEY`) | `LIVE VERIFIED`<br>Applies `parse_pubmed_dates()` to separate electronic advance articles from print issues. |
| **CSIR-NIScPR** | `academic_sources.py`<br>`search_csir_niscpr()` | Crossref Metadata Filter / NOPR | `query.publisher-name=CSIR-NIScPR`, `rows` | Title, Abstract, Authors, Journal, Year, DOI, NOPR Repository URL | Standard Crossref rate-limit etiquette | `LIVE VERIFIED`<br>Covers Indian government scientific research journals; handles HTML tag stripping. |
| **Crossref** | `academic_sources.py`<br>`search_crossref()` | REST API (JSON) | `query.bibliographic=...`, `rows`, `mailto` header | Title, Abstract (JATS XML cleaned), Authors, Venue, Year, DOI, URL | Polite pool via `CROSSREF_MAILTO` configuration | `LIVE VERIFIED`<br>Global scholarly DOI resolution. |
| **Semantic Scholar** | `academic_sources.py`<br>`search_semantic_scholar()` | REST API (JSON) | `query=...`, `fields=title,abstract,authors,year,venue,citationCount` | Title, Abstract, Authors, Year, Venue, Citation Count, Paper ID | 100 requests/5-min unauthenticated; uses `S2_API_KEY` if present | `IMPLEMENTED — SOURCE VERIFIED`<br>Gracefully falls back to mock if public rate-limited. |
| **DBLP** | `academic_sources.py`<br>`search_dblp()` | REST API (JSON) | `q=...`, `format=json`, `h=...` | Title, Authors, Venue, Year, DOI, DBLP Key | Free public query etiquette | `IMPLEMENTED — SOURCE VERIFIED`<br>DBLP abstracts are typically empty; used for bibliographies. |
| **CORE** | `academic_sources.py`<br>`search_core()` | REST API v3 | `q=...`, `limit=...` | Title, Abstract, Authors, Year, Repository URL | Requires `CORE_API_KEY` | `OPTIONAL / DISABLED`<br>Skipped gracefully if API key is not configured. |

---

## Section 7: Data Model, Relational Schema, & Persistence Integrity

### 7.1 Relational Database Engine
- **Engine:** PostgreSQL 16 (Containerized in Podman as `research-paper-recommender-postgres-1`).
- **Connection URL:** `postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/research_papers` (Dev/Host URL).
- **ORM:** SQLAlchemy 2.0.35 with declarative base mapping.

### 7.2 Table Schemas & Relational Entity Definitions

#### 1. `papers` Table (Primary Catalog)
Stores normalized research paper metadata and extracted texts.
```sql
CREATE TABLE papers (
    id SERIAL PRIMARY KEY,
    paper_id VARCHAR(120) UNIQUE NOT NULL,      -- e.g. "arxiv:1706.03762", "pubmed:38210001", "csir:10.56042/..."
    title VARCHAR(500) NOT NULL,
    abstract TEXT,
    authors JSON NOT NULL DEFAULT '[]',         -- Array of author name strings
    venue VARCHAR(255),
    year INTEGER,                               -- Verified effective publication year
    doi VARCHAR(255),
    url VARCHAR(500),
    pdf_url VARCHAR(500),
    source VARCHAR(50) NOT NULL DEFAULT 'local',-- "arxiv", "pubmed", "csir", "crossref", "pdf_upload", "local"
    citation_count INTEGER DEFAULT 0,
    categories JSON DEFAULT '[]',               -- Array of subject category strings
    raw_text TEXT,                              -- Full text extracted from uploaded PDFs
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX ix_papers_paper_id ON papers(paper_id);
CREATE INDEX ix_papers_title ON papers(title);
CREATE INDEX ix_papers_year ON papers(year);
CREATE INDEX ix_papers_source ON papers(source);
CREATE INDEX ix_papers_doi ON papers(doi);
```

#### 2. `users` Table (User Accounts & Authentication)
Stores credentials, roles, and status for authenticated researchers.
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,      -- Passlib Bcrypt hash ($2b$12$...)
    full_name VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX ix_users_username ON users(username);
CREATE INDEX ix_users_email ON users(email);
```

#### 3. `saved_papers` Table (Personal Research Libraries)
Maps individual user accounts to their bookmarked catalog papers with custom notes and tags.
```sql
CREATE TABLE saved_papers (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    notes TEXT,
    tags JSON DEFAULT '[]',
    saved_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_user_saved_paper UNIQUE (user_id, paper_id)
);
CREATE INDEX ix_saved_papers_user_id ON saved_papers(user_id);
```

#### 4. `paper_evidence` Table (Grounded Scientific Claims)
Stores extracted claims deterministically linked to exact source text offsets.
```sql
CREATE TABLE paper_evidence (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,              -- "problem", "method", "dataset", "results", etc.
    claim TEXT NOT NULL,
    source_passage TEXT NOT NULL,               -- Exact quote extracted from text
    char_start INTEGER,                         -- Exact character offset start
    char_end INTEGER,                           -- Exact character offset end
    page_number INTEGER,
    section_name VARCHAR(100),
    source_type VARCHAR(50) NOT NULL DEFAULT 'abstract', -- "abstract", "full_text"
    extraction_method VARCHAR(50) NOT NULL DEFAULT 'rule_based_nlp',
    confidence_score FLOAT,
    is_verified BOOLEAN NOT NULL DEFAULT TRUE,
    verification_notes VARCHAR(255),
    source_hash VARCHAR(64),                    -- SHA-256 hash of source text at extraction time
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_paper_evidence_span UNIQUE (paper_id, category, char_start, char_end)
);
CREATE INDEX ix_paper_evidence_paper_id ON paper_evidence(paper_id);
CREATE INDEX ix_paper_evidence_category ON paper_evidence(category);
CREATE INDEX ix_paper_evidence_source_hash ON paper_evidence(source_hash);
```

#### 5. `driut_alerts` Table (Dynamic Research Impact Updates)
Stores classified relationship updates between newly cataloged papers and saved baseline papers.
```sql
CREATE TABLE driut_alerts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    saved_paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    trigger_paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,     -- "Extension", "Improvement", "Challenge", "Reproduction", "Alternative", "Potential Replacement"
    confidence_score FLOAT NOT NULL DEFAULT 0.0,
    explanation TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    evidence_strength VARCHAR(50) DEFAULT 'tentative', -- "strong_evidence", "partial_evidence", "tentative"
    evidence_passage TEXT,                      -- Supporting passage from candidate paper
    saved_evidence_passage TEXT,                -- Supporting passage from saved baseline
    char_start INTEGER,
    char_end INTEGER,
    section_name VARCHAR(100),
    source_type VARCHAR(50) DEFAULT 'abstract',
    semantic_similarity FLOAT,
    comparability_notes TEXT,
    uncertainty_warning TEXT,
    classification_version VARCHAR(50) DEFAULT 'v2.0-evidence-grounded',
    CONSTRAINT uq_user_driut_alert UNIQUE (user_id, saved_paper_id, trigger_paper_id)
);
CREATE INDEX ix_driut_alerts_user_id ON driut_alerts(user_id);
CREATE INDEX ix_driut_alerts_relationship_type ON driut_alerts(relationship_type);
```

### 7.3 Live Database Entity Distribution (Verified October 20, 2026)

| Entity / Table | Exact Live Count | Breakdown & Distribution Notes |
| :--- | :--- | :--- |
| **Total Catalog Papers (`papers`)** | **162** | **Sources:** arXiv ($40$), PubMed ($39$), CSIR-NIScPR ($37$), Crossref ($34$), Semantic Scholar ($10$), Test ($2$).<br>**Years:** 2026 ($72$ papers), 2025 ($18$), 2024 ($11$), 2023 ($9$), 2022 ($10$), 2021 ($7$), 2020 ($11$), 1988–2019 ($12$), Forthcoming 2028 ($1$), Undated ($11$). |
| **FAISS Vector Embeddings** | **162** | Dimension: $768$, Metric: `IndexFlatIP`, Hash: `f5be6e08...` (Exact 1:1 match with DB). |
| **FAISS Mapped Metadata Entries** | **162** | In `papers_meta.json`, Hash: `2cc5f368...` (Exact 1:1 match with DB). |
| **User Accounts (`users`)** | **7** | `admin` (superuser), `default_user`, `test_user`, `testuser_task10`, `evidence_test_user`, `isolated_user_b`, `test_asst_user`. |
| **Saved Papers (`saved_papers`)** | **5** | Saved by `admin` ($4$ papers) and `testuser_task10` ($1$ paper). |
| **Extracted Evidence Spans (`paper_evidence`)** | **3** | Persisted baseline evidence spans with exact character offsets. |
| **DRIUT Research Alerts (`driut_alerts`)** | **175** | **Taxonomy:** Improvement ($105$), Extension ($50$), Alternative ($10$), Challenge ($5$), Reproduction ($5$).<br>**Chronology Audit:** $75$ valid same-year, $10$ exempt alternatives, $90$ historical pre-guard directional violations awaiting remediation. |

---

## Section 8: Security, Privacy, Isolation, & Reliability Engineering

### 8.1 Authentication & Password Security
- **Algorithm:** Passlib Bcrypt hashing with salt factor 12. Plaintext passwords are never stored, logged, or serialized.
- **Session Tokens:** JSON Web Tokens (JWT) signed with HMAC-SHA256 (`HS256`).
- **Fail-Closed Production Secret Validation:** Configured in `backend/app/core/config.py`:
  - In `production` environment, the system refuses to boot if `JWT_SECRET_KEY` uses any default dev value (`"researchlens-secure-dev-secret-key-2026"`, `"secret"`, `"changeme"`, etc.) or is shorter than 32 characters.
  - Verified by automated regression tests in `test_auth_and_isolation.py`.

### 8.2 User Data Isolation & Cross-User Privacy
- **Relational Scoping:** All operations on `saved_papers` and `driut_alerts` require authenticated `current_user` dependency injection (`backend/app/api/deps.py`).
- **Query Filter Invariants:** Database queries strictly enforce `.filter(SavedPaper.user_id == current_user.username)`.
- **Parameter Tampering Immunity:** If a malicious user passes `?user_id=victim` in a request query or body, the system completely ignores the input parameter and binds exclusively to the cryptographically verified JWT identity. Verified in `test_auth_and_isolation.py::test_parameter_tampering_ignored`.

### 8.3 Rate Limiting & Denial-of-Service Defense
- **Framework:** SlowAPI backed by the `limits` library.
- **Buckets:**
  - Login endpoint (`/api/v1/auth/login`): `5/minute` per remote IP.
  - Search endpoint (`/api/v1/papers/search`): `30/minute` per remote IP.
- **Trusted Reverse Proxy Shield:** Evaluates `X-Forwarded-For` only if the immediate peer IP is present in `TRUSTED_PROXIES` (`127.0.0.1`, `::1`, Docker subnet). Untrusted external clients cannot spoof headers to bypass rate limits. Verified in `test_rate_limiter.py`.

### 8.4 Air-Gapped Local-First Privacy Protection
- **Local AI Engine:** Ollama running on `127.0.0.1:11434` executes inference entirely on local host CPU/GPU. Research questions and manuscript abstracts never exit the machine.
- **Cloud Content Privacy Guard:** `RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT` defaults to `False`.
  - When cloud failover (Groq) is active, the system checks whether the request contains research manuscript content.
  - If research content is present and cloud permission is `False`, cloud transmission is blocked immediately, and execution falls back to the local deterministic engine.

### 8.5 Deterministic AI Security Guard & Redaction
- **Prompt Injection Defense:** Treats retrieved evidence as untrusted text, enclosing it in explicit boundary tags and forbidding instruction execution within evidence blocks.
- **Output Leakage Guard:** Scans candidate generated text before it reaches the user. Blocks canary strings (`HACKED`), connection URIs, environment variable names (`DATABASE_URL`, `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`), and raw JWT tokens. Sensitive content is redacted and replaced with a canonical safe response.

---

## Section 9: Frontend Architecture, Design System, & User Workflows

### 9.1 UI Technology & Modern Styling System
- **Framework:** React 18 with TypeScript 5.5 and Vite 5.4.
- **Styling Architecture:** Pure **Vanilla CSS Design Tokens** located in `frontend/src/index.css`.
  - **No Tailwind CSS:** Completely eliminates external utility dependencies in favor of bespoke, highly maintainable CSS custom properties.
  - **Typography:** Modern Google Fonts (`Plus Jakarta Sans` for clean, professional academic typography; `JetBrains Mono` for code snippets, DOIs, and character offset spans).
  - **Color Palette:** Curated academic palette featuring deep slate, emerald accents (`#059669`), subtle borders (`#e5e7eb`), accessible contrast ratios, and cohesive dark/light mode tokens.
  - **Micro-Animations & Transitions:** Smooth modal fade-ins, card hover elevations, and responsive badge transitions.

### 9.2 Key Component Hierarchy & Views

```text
App (Router)
└── MainLayout
    ├── Navbar (Logo, Status Row, Theme Toggle, Auth Buttons, Tab Switcher)
    └── HomePage (Main Application Shell)
        ├── Tab 1: Explore (Search Bar, Source Filters, Sort Controls, PaperCard Grid)
        ├── Tab 2: PDF Upload (Drag-and-Drop Dropzone, Extraction Preview, Catalog Sync)
        ├── Tab 3: Compare (Side-by-Side 12-Dimension Matrix for up to 5 papers)
        ├── Tab 4: Saved Library (Personal Bookmarked Papers, Notes, Tags, DRIUT Trigger)
        ├── Tab 5: DRIUT Alerts (Real-Time Impact Feed, 6-Category Filters, Mark-Read)
        └── Tab 6: Research Evolution (Interactive Sub-Views)
            ├── Sub-Tab A: Timeline (Chronological Bands, Undated Paper Isolation)
            ├── Sub-Tab B: Relationship Graph (Interactive Node-Link Network, Legend)
            ├── Sub-Tab C: Gap Discovery (Recurring Limitations, Candidate Hypotheses)
            └── Sub-Tab D: Grounded Assistant (Scholarly Q&A, Evidence Quote Cards)
```

### 9.3 Modal Inspection Dialogs
- **SummaryModal (`frontend/src/components/SummaryModal.tsx`):** Displays structured paper summaries, disclosing whether the summary is based on full-text or abstract-only coverage, and listing key problem, methodology, and result findings.
- **CompareModal (`frontend/src/components/CompareModal.tsx`):** Renders the 12-dimension side-by-side comparative table, highlighting incomparable dimensions when benchmarks differ.
- **EvidenceModal (`frontend/src/components/EvidenceModal.tsx`):** Deep-dive inspector for extracted evidence claims. Renders the exact source passage with highlighted character spans (`[char_start, char_end]`), category tags, and cryptographic verification status.
- **AuthModal (`frontend/src/components/AuthModal.tsx`):** Clean dialog for user registration and login, featuring client-side validation and responsive error alerts.

---

## Section 10: Complete Verification & Test Results

### 10.1 Backend Automated Pytest Suite
- **Execution Command:** `backend/venv/bin/pytest backend/tests -v`
- **Result:** **329 passed, 0 failed, 12 deprecation warnings in 102.30s (0:01:42)**
- **Test Isolation:** 100% database and vector isolation enforced by `backend/tests/conftest.py`. Tests execute against a temporary SQLite instance (`/tmp/researchlens_test_isolated.db`) and temporary FAISS directory (`/tmp/researchlens_test_faiss`). Fails closed if any test attempts to bind to the persistent database.

| Test File | Test Count | Key Invariants Verified |
| :--- | :--- | :--- |
| `test_auth_and_isolation.py` | 10 passed | Bcrypt hashing, user isolation, parameter tampering rejection, production JWT secret enforcement. |
| `test_rate_limiter.py` | 4 passed | Remote IP isolation, trusted proxy validation, login brute-force throttling. |
| `test_pdf_upload.py` | 6 passed | Magic byte validation, blank/scanned PDF rejection, memory cap enforcement. |
| `test_n2_pdf_ingestion.py` | 9 passed | Two-phase ingestion: preview without mutation, explicit confirmation, FAISS sync. |
| `test_search_ingestion_decoupling.py` | 9 passed | Ordinary search returns external candidates without mutating database or FAISS. |
| `test_papers_api.py` | 13 passed | Semantic search, recency/citation sorting, summaries, comparisons, saved papers. |
| `test_paper_comparison.py` | 11 passed | 12 dimensions, disparate metric incomparability, 5-paper limit, zero side-effects. |
| `test_evidence_extraction.py` | 9 passed | Exact sentence character offsets, SHA-256 hashes, placeholder abstract rejection. |
| `test_driut_intelligence.py` | 10 passed | 6 taxonomy categories, benchmark comparability checking, evidence grounding. |
| `test_driut_scheduler.py` | 7 passed | PostgreSQL advisory locking ($7376232$), background thread execution, notifications. |
| `test_research_evolution.py` | 15 passed | Chronological timeline, undated paper isolation, relationship graph, candidate gaps. |
| `test_research_assistant.py` | 12 passed | Scholarly Q&A grounding, prompt injection defenses, air-gapped privacy enforcement. |
| `test_assistant_security_guard.py` | 8 passed | Canary rejection (`HACKED`), connection URI redaction, credential leak protection. |
| `test_ai_providers.py` | 7 passed | Provider routing (`local_first`, `groq_only`, `deterministic`), 15s timeout failover. |
| `test_targeted_remediations.py` | 24 passed | PubMed epub vs print issue year parsing, Step 8b chronology guard, semantic floor ($0.835$). |
| `test_defect_remediation_regression.py` | 22 passed | Regression prevention across all historical audits and defect fixes. |
| `test_academic_sources.py` | 8 passed | Asynchronous connectors for arXiv, PubMed, CSIR-NIScPR, Crossref. |
| `test_embedding_and_sync.py` | 6 passed | SPECTER2 model dimension verification ($768$), cache validation. |
| `test_faiss_consistency.py` | 8 passed | IndexFlatIP persistence, ID mapping integrity, backup/restore safety. |
| `test_local_search_correctness.py` | 5 passed | In-catalog keyword and semantic retrieval accuracy. |
| `test_n1_external_workflows.py` | 4 passed | External candidate workflow serialization and deduplication. |
| `test_cors_configuration.py` | 3 passed | CORS whitelisting and preflight header responses. |
| `test_datetime_utc.py` | 2 passed | UTC timezone enforcement across all timestamp columns. |
| `test_isolation_verification.py` | 3 passed | Multi-tenant user library and alert isolation. |

### 10.2 Frontend Vitest & Build Verification
- **Vitest Suite Command:** `npm run test` (in `frontend/`)
- **Vitest Result:** **8 passed test files, 66 passed tests in 1.72s**
  - `src/services/api.test.ts`: 21 passed
  - `src/components/EvidenceModal.test.tsx`: 10 passed
  - `src/components/CompareModal.test.tsx`: 8 passed
  - `src/components/DriutAlertsView.test.tsx`: 7 passed
  - `src/components/ResearchEvolutionView.test.tsx`: 7 passed
  - `src/App.test.tsx`: 7 passed
  - `src/components/SavedLibraryView.test.tsx`: 3 passed
  - `src/components/AuthModal.test.tsx`: 3 passed
- **Production Build Command:** `npm run build` (`tsc -b && vite build`)
- **Build Result:** **Succeeded with 0 errors in 820ms** (Output bundle: `dist/assets/index-CzeZxbHT.js` $293.10$ kB, `dist/assets/index-vAofhJTI.css` $13.60$ kB).

### 10.3 Native Host Runtime Health Verification
- **Diagnostic Command:** `./scripts/dev-status.sh`
- **Result:**
  - `[1] Database (PostgreSQL - Podman Container)`: **running (health: healthy)**, Port 5432 CONNECTED.
  - `[2] Backend (FastAPI - Native Fedora)`: **RUNNING (systemd unit: researchlens-backend, PID 15371)**, API Health: OK, Database Link: connected.
  - `[3] Frontend (React/Vite - Native Fedora)`: **RUNNING (systemd unit: researchlens-frontend, PID 15408)**, Dev Server: OK (http://localhost:3000 reachable).
  - `[4] Local AI (Ollama - Native Fedora)`: **RUNNING (Port 11434)**, Model available: `qwen2.5:3b` ($1.93$ GB GGUF Q4_K_M).

---

## Section 11: Defect Remediation History & Release Readiness Status

| Remediation Item | Original Defect / Challenge | Root Cause Identified | Implemented Remediation | Current Verification Evidence | Remaining Risk / Production Blocker |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PubMed Publication Date Mismatch** | 25 PubMed papers had stored year 2027 despite public availability in 2026. | PubMed XML stores electronic advance publication (`epubdate`) and scheduled print issue (`pubdate`) separately. Parsers previously prioritized the scheduled future print volume date. | Implemented `parse_pubmed_dates()` in `academic_sources.py` prioritizing electronic availability for ranking while preserving print date provenance. Migrated 25 records to 2026; preserved 1 legitimate forthcoming 2028 record. | `test_targeted_remediations.py::test_pubmed_advance_article_epub_before_print`<br>Database audit confirmed 25 records updated to 2026; 2028 record preserved. | Fully remediated. No remaining risk. |
| **FAISS Orphan Vector (`test:t15:cand_ext`)** | Vector index held 163 vectors while PostgreSQL held 162 papers. | A transient test candidate from Task 15 was inadvertently committed to the persistent FAISS index during early development. | Created `scripts/reconcile_faiss_postgres.py`. Atomic removal of vector at index 10, shift of remaining vectors, and alignment of `papers_meta.json`. | `RESEARCHLENS_FAISS_RECONCILIATION_EXECUTION_REPORT.md`<br>Live check: FAISS ntotal = 162, metadata = 162, PostgreSQL = 162. | Fully remediated. No remaining risk. |
| **DRIUT Chronology Violations & Step 8b** | 90 historical alerts in database claimed earlier papers (e.g. 2017) "improved" or "extended" 2026 papers. | DRIUT classification was originally based on text pattern matching and semantic similarity without checking the temporal direction of publication years. | 1. Implemented **Step 8b Chronology Guard** in `driut_service.py:L409-441` blocking directional candidates where `new_year < saved_year`.<br>2. Completed read-only historical audit classifying all 175 alerts (90 invalid, 75 valid, 10 exempt). | `test_targeted_remediations.py::test_driut_chronology_later_improves_earlier`<br>`test_driut_chronology_earlier_cannot_improve_later`<br>`RESEARCHLENS_DRIUT_HISTORICAL_CHRONOLOGY_AUDIT.md` | **Release Blocker:** 90 historical invalid alerts remain in the live database awaiting approved administrative cleanup script execution. |
| **Semantic Drift & Irrelevant Top Matches** | Searching for out-of-domain queries (e.g. "Roman architecture") returned AI papers with ~0.81 cosine similarity due to common words. | SPECTER2 inner-product scores between scientific texts rarely drop below 0.70 because of shared academic grammar. | Implemented calibrated `SEMANTIC_RELEVANCE_FLOOR = 0.835` in `recommendation_engine.py`. Pure semantic candidates below 0.835 are dropped unless exact lexical matches exist. | `test_targeted_remediations.py::test_unrelated_query_ancient_roman_architecture_filtered`<br>`test_targeted_remediations.py::test_semantic_relevance_floor_value` | Fully remediated. In-domain retrieval verified. |
| **Synthetic Placeholder Abstracts** | PubMed records without abstracts indexed boilerplate text ("Biomedical & computational research paper indexed by US NLM..."). | Initial batch ingestion script filled missing abstracts with generic library attribution strings. | Added `is_synthetic_placeholder_abstract()` in `evidence_service.py` to reject placeholder strings from evidence extraction, summaries, and assistant context. | `test_targeted_remediations.py::test_synthetic_placeholder_detection`<br>`test_targeted_remediations.py::test_evidence_extraction_rejects_placeholder_abstract` | Fully remediated. Synthetic abstracts safely rejected. |
| **AI Privacy & Prompt Injection Risks** | Potential for malicious user prompts or poisoned papers to hijack LLM instructions or leak connection secrets. | Unfiltered text concatenation in generative prompts; potential for LLM to echo configuration keys. | 1. Implemented strict delimiter framing (`<<<BEGIN EVIDENCE>>>`).<br>2. Implemented `enforce_ai_output_security_guard()` in `ai_output_guard.py` blocking canaries, URIs, env vars, and credentials.<br>3. Enforced `RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT=False`. | `test_assistant_security_guard.py`<br>`test_research_assistant.py::test_assistant_prompt_injection_safety`<br>`test_ai_providers.py` | Fully remediated across all four AI generation workflows. |
| **Production JWT Secret Safety** | Application booted in production with default hardcoded dev signing secret. | Developer default secret left active in settings class. | Added `@model_validator` in `config.py` failing closed on startup in `production` environment if secret is default or $<32$ characters. | `test_auth_and_isolation.py::test_jwt_secret_validation_in_production` | Fully remediated. Prevents insecure production boot. |
| **Public Deployment & HTTPS Ingress** | Native development stack runs on localhost ports (8000, 3000). | Project currently configured for local Fedora host development and demonstration. | Systemd user units (`researchlens-backend`, `researchlens-frontend`) and dev scripts created. Production guide written. | `RESEARCHLENS_PRODUCTION_DEPLOYMENT_GUIDE.md` | **Release Blocker:** Public domain DNS, TLS certificate generation, and production reverse proxy mapping remain to be configured. |

---

## Section 12: Scientific Evaluation, Performance, & Benchmarks

### 12.1 Explicit Disclosure on Academic Evaluation Benchmarks
- **Scientific Truthfulness Disclosure:** The repository does **NOT** currently contain formal, standardized Information Retrieval (IR) benchmark evaluations (such as TREC, MS MARCO, or SciDocs with Mean Average Precision (MAP) or NDCG@10 metrics).
- **Presentation Gap:** In an academic presentation or thesis defense, the presenter must **NOT** claim formal empirical retrieval benchmarks (e.g., "94.2% NDCG@10"). Instead, claim:
  1. *Functional Correctness & Verification:* 329 passing backend tests and 66 passing frontend tests verify functional behavior across all defined edge cases.
  2. *Empirical In-Domain Alignment:* Demonstrated through qualitative query evaluations (e.g., queries for "transformer attention mechanisms" reliably retrieve Vaswani et al. and related foundational NLP literature with cosine similarity $\ge 0.88$).
  3. *Calibrated Floor Verification:* Concrete measurement that in-domain queries score $\ge 0.844$, while out-of-domain queries score $\le 0.817$, establishing the mathematical defense of the $0.835$ relevance floor.

### 12.2 Computational Performance & Latency Profile (Measured Native Fedora)
- **Vector Search Latency:** $< 5.0$ milliseconds for FAISS `IndexFlatIP` across 162 vectors.
- **SPECTER2 Query Embedding Generation:** $\approx 180$–$350$ milliseconds on CPU.
- **End-to-End Local Hybrid Search:** $\approx 220$–$450$ milliseconds (exceeding sub-second objective).
- **External Federated Search Latency:** $\approx 800$–$1800$ milliseconds (dominated by external network latency to arXiv/PubMed APIs).
- **Local LLM Inference Latency (Ollama Qwen2.5-3B):** $\approx 1.5$–$3.8$ seconds for grounded summary or assistant response on modern multi-core CPU.
- **Memory Footprint:**
  - FastAPI Backend (with PyTorch & SPECTER2 model loaded): $\approx 1.25$ GB RSS RAM.
  - PostgreSQL Container: $\approx 85$ MB RAM.
  - React/Vite Frontend Dev Server: $\approx 70$ MB RAM.
  - Ollama Service (`qwen2.5:3b` model weights in RAM): $\approx 1.95$ GB RAM.
  - Total System Footprint: $\approx 3.4$ GB RAM, making it fully operational on standard developer laptops without requiring discrete GPUs.

---

## Section 13: Scripted Step-by-Step Live Demonstration Runbook

This scripted runbook outlines an end-to-end live demonstration sequence for an academic presentation, thesis defense, or technical walkthrough.

| Step | User Action | Expected Visible Outcome | Subsystem | Verified Evidence | Fallback / Risk Notes |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **1** | Open browser to `http://localhost:3000`. Check header status indicators. | Green status dot: "Operational". Shows active API connection and healthy database. | Frontend Navbar & Health API | `GET /api/v1/health`<br>`./scripts/dev-status.sh` | If red, check backend systemd service status. |
| **2** | Enter search query: `"transformer attention mechanism"`. Leave sort as "Relevance". Click Search. | Returns top foundational NLP papers (e.g. *Attention Is All You Need*). Cards display green similarity badges ($88\%+$), year badges, venue, and explainability rationales. | Hybrid Search & Recommendation Engine | `test_papers_api.py::test_semantic_search_returns_relevant_recommendations` | Fast local search executes in $\approx 300$ms. |
| **3** | Click **"Grounded Evidence"** button on *Attention Is All You Need* card. | `EvidenceModal` opens displaying verified quote cards across categories (*Problem, Method, Results*). Highlights exact sentence quotes and character span indices `[char_start, char_end]`. | Evidence Extraction Service | `test_evidence_extraction.py` | Abstract-only disclosure clearly visible. |
| **4** | Click **"Add to Compare"** on two different transformer/NLP papers. Navigate to **Compare** tab. | Side-by-side 12-dimension matrix renders comparing Method, Objective, Dataset, Limitations. If datasets differ, flags metrics as incomparable. | Comparison Service & Modal | `test_paper_comparison.py` | Maximum 5 papers enforced. |
| **5** | Navigate to **PDF Upload** tab. Drag and drop an academic manuscript PDF. | Client parses document instantly. Renders Phase 1 preview: extracted title, abstract, authors, detected duplicates, and recommended related papers. | PDF Extraction Service | `test_pdf_upload.py`<br>`test_n2_pdf_ingestion.py` | Shows that preview did **not** write to database yet. |
| **6** | Click **"Confirm & Ingest Paper"**. | Success toast appears. Paper is persisted to PostgreSQL and indexed into FAISS vector index atomically. | Two-Phase Ingestion Workflow | `test_n2_pdf_ingestion.py` | Vector count advances; verified in `/index-status`. |
| **7** | Navigate to **Saved Library** tab. Inspect saved baseline papers. Click **"Check Updates (DRIUT)"**. | DRIUT scans new literature. Displays categorized update cards (*Extension, Improvement, Alternative*) with supporting evidence quotes. | DRIUT Engine & Step 8b Guard | `test_driut_intelligence.py` | Explains how Step 8b blocks invalid historical claims. |
| **8** | Navigate to **Research Evolution** tab. View **Timeline** sub-tab. | Chronological timeline renders papers grouped by verified publication year. Undated papers are cleanly isolated in side drawer. | Research Evolution Service | `test_research_evolution.py` | Demonstrates separation of publication year from ingestion date. |
| **9** | Switch to **Relationship Graph** sub-tab. | Interactive network graph renders papers as nodes with directed edges. Legend clarifies author-stated citations vs. inferred thematic links. | Evolution Graph Service | `test_research_evolution.py` | Smooth canvas zoom and drag. |
| **10**| Switch to **Grounded Assistant** sub-tab. Type: *"What are the primary computational limitations of recurrent neural networks?"* | Assistant streams or displays concise answer grounded in retrieved evidence quotes from Vaswani et al. Citation badges link to exact quotes. | Grounded Assistant & Local Ollama | `test_research_assistant.py` | Air-gapped: zero data transmitted to cloud. |

---

## Section 14: Academic Presentation Narrative (Slide-by-Slide Outline)

This 20-slide narrative provides the blueprint for building the presentation in ChatGPT:

- **Slide 1: Title & Presentation Header**
  - *Title:* ResearchLens: An Evidence-Grounded NLP System for Research Paper Recommendation, Structured Comparison, and Impact Tracking
  - *Subtitle:* Eliminating Hallucination, Enabling Sub-Second Dense Retrieval, and Enforcing Chronological Integrity in Scholarly Literature Review
  - *Presenter Info / Academic Affiliation / Date*
  - *Supported Sections:* Executive Summary, Section 1.

- **Slide 2: The Scholarly Information Crisis (Problem Statement)**
  - *Key Points:* Exponential growth of scientific publishing; silos between arXiv, PubMed, and CSIR-NIScPR; the vocabulary mismatch problem in keyword search; LLM hallucination and lack of verifiable citations.
  - *Supported Sections:* Section 2.1.

- **Slide 3: Research Aims & Measurable Objectives**
  - *Key Points:* Sub-second hybrid retrieval ($< 1.5$s); 768-dimensional dense semantic vectors (SPECTER2); $100\%$ verifiable evidence grounding with character spans; 6-tier directional impact tracking; air-gapped local-first privacy.
  - *Supported Sections:* Section 2.3.

- **Slide 4: Competitive Analysis & Technical Differentiators**
  - *Key Points:* Comparative matrix comparing Traditional Search (Google Scholar/DBLP), Generic AI (ChatGPT/Perplexity), and ResearchLens across search, grounding, comparison, update tracking, and privacy.
  - *Supported Sections:* Section 2.4 (Table).

- **Slide 5: High-Level System Architecture & Topology**
  - *Key Points:* 5-tier architecture: Client Layer (React 18), Gateway (SlowAPI), Backend Application (FastAPI), Intelligence Layer (SPECTER2 + Local Ollama), and Persistence Layer (PostgreSQL 16 + FAISS).
  - *Supported Sections:* Section 4.1 (Mermaid Diagram 1).

- **Slide 6: Dense Semantic Vector Representation (SPECTER2)**
  - *Key Points:* AllenAI SPECTER2 architecture; citation-graph pre-training; 768-dimensional embeddings; L2 normalization; in-memory MD5 caching; fail-closed dimension validation.
  - *Supported Sections:* Section 5.2.

- **Slide 7: FAISS Vector Indexing & Sub-Second Similarity**
  - *Key Points:* `IndexFlatIP` cosine similarity search; exact 1:1:1 alignment (162 DB papers = 162 FAISS vectors = 162 metadata entries); atomic `.tmp` swapping with `.bak` preservation; thread/process advisory locking.
  - *Supported Sections:* Section 5.3, Section 7.3.

- **Slide 8: Calibrated Hybrid Retrieval & Explainable Ranking**
  - *Key Points:* Multi-criteria ranking formula (semantic similarity + lexical matching + recency boost); empirical calibration of the $0.835$ semantic relevance floor; eliminating out-of-domain false positives; explainable recommendation rationale strings.
  - *Supported Sections:* Section 5.4, Section 4.2 (Mermaid Diagram 2).

- **Slide 9: Verifiable Claim Grounding & Character Span Offsets**
  - *Key Points:* Deterministic sentence splitting; 9 evidence categories (*Problem, Method, Dataset, Metrics, Results, Limitations*, etc.); tracking exact `[char_start, char_end]` spans; SHA-256 cryptographic source hashing; rejecting synthetic placeholder abstracts.
  - *Supported Sections:* Section 5.5, Section 7.2.

- **Slide 10: Two-Phase PDF Upload & Ingestion Pipeline**
  - *Key Points:* Decoupled architecture: Phase 1 (magic bytes `%PDF-`, PyPDF parsing, duplicate analysis, transient recommendations preview); Phase 2 (explicit confirmation, PostgreSQL commit, FAISS index sync).
  - *Supported Sections:* Section 5.1, Section 4.3 (Mermaid Diagram 3).

- **Slide 11: Structured Multi-Paper Comparison Engine**
  - *Key Points:* Automated 12-dimension comparative matrix for up to 5 papers; side-by-side alignment; disparate benchmark protection (refuses false comparisons when evaluation datasets/metrics differ).
  - *Supported Sections:* Section 5.6.

- **Slide 12: Dynamic Research Impact Update Tracker (DRIUT)**
  - *Key Points:* Continuous monitoring of new literature; 6-tier impact taxonomy (*Extension, Improvement, Challenge, Reproduction, Alternative, Potential Replacement*); background scheduler with PostgreSQL advisory locking ($7376232$).
  - *Supported Sections:* Section 5.10, Section 4.4 (Mermaid Diagram 4).

- **Slide 13: Temporal Integrity: The Step 8b Chronology Guard**
  - *Key Points:* The temporal paradox: why earlier papers cannot "improve" later papers; separating electronic publication dates (`epubdate`) from scheduled print issues (`pubdate`); mathematical enforcement of the Step 8b guard.
  - *Supported Sections:* Section 5.10, Section 11.

- **Slide 14: Longitudinal Evolution Timeline & Relationship Graph**
  - *Key Points:* Chronological evolutionary bands; transparent undated paper isolation; interactive relationship graph distinguishing author-stated citations from inferred semantic links; candidate research-gap synthesis with corpus boundary disclosures.
  - *Supported Sections:* Section 5.7.

- **Slide 15: Air-Gapped Local AI Assistant & Prompt Injection Defense**
  - *Key Points:* Dual provider architecture (Local Ollama `qwen2.5:3b` default); privacy shield (`RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT=False`); prompt injection delimiter shielding; deterministic post-generation output guard (blocking canaries, URIs, env vars, and credentials).
  - *Supported Sections:* Section 5.8, Section 5.9, Section 8.4.

- **Slide 16: Security, Multi-Tenant Isolation, & Rate Limiting**
  - *Key Points:* Bcrypt hashing (cost 12); HS256 JWT bearer tokens; fail-closed production secret validation ($\ge 32$ chars); strict user library isolation; SlowAPI tiered rate limiting with trusted proxy shielding.
  - *Supported Sections:* Section 8.1, Section 8.2, Section 8.3.

- **Slide 17: Comprehensive Verification & Test Results**
  - *Key Points:* 329 passing backend pytest tests ($100\%$ pass rate); 66 passing frontend vitest tests ($100\%$ pass rate); TypeScript build 0 errors; complete test database isolation; native service verification.
  - *Supported Sections:* Section 10.1, Section 10.2, Section 10.3.

- **Slide 18: Empirical Evaluation, Latency, & Resource Footprint**
  - *Key Points:* Sub-second local retrieval ($< 450$ms); low computational footprint ($3.4$ GB RAM total across DB, backend, frontend, and Ollama); runs on standard consumer laptops; honest disclosure of lack of formal TREC/SciDocs benchmarks.
  - *Supported Sections:* Section 12.1, Section 12.2.

- **Slide 19: Defect Remediation Journey & Production Readiness**
  - *Key Points:* Technical audit and resolution of PubMed epub dates, FAISS orphan purge (`test:t15:cand_ext`), Step 8b chronology guard, and semantic floor; summary of remaining release blockers (DNS/TLS ingress and 90 historical alert purge).
  - *Supported Sections:* Section 11.

- **Slide 20: Summary, Future Roadmap, & Academic Conclusion**
  - *Key Points:* ResearchLens bridges the gap between keyword search and generative AI; enforces verifiable evidence grounding; future roadmap (formal SciDocs benchmarking, full-text PDF parsing pipeline, automated historical alert purge, multi-institution federation); conclusion.
  - *Supported Sections:* Section 2.3, Section 16.

---

## Section 15: Technical Glossary

- **Cosine Similarity:** A mathematical metric measuring the cosine of the angle between two multi-dimensional vectors: $\cos(\theta) = \frac{\mathbf{u} \cdot \mathbf{v}}{||\mathbf{u}|| ||\mathbf{v}||}$. For L2-normalized vectors, it simplifies directly to the dot product.
- **Dense Embedding:** A continuous, low-dimensional vector representation (here 768 float values) that captures the latent semantic and conceptual meaning of scientific text.
- **Disparate Metrics:** Evaluation measures derived from incompatible experimental tasks (e.g. comparing BLEU on translation to Accuracy on image classification).
- **DRIUT (Dynamic Research Impact Update Tracker):** An automated subsystem that evaluates incoming scientific publications against a researcher's saved library, classifying their relationship into 6 defined impact types.
- **Electronic Publication Date (`epubdate`):** The verified date on which a scientific manuscript becomes publicly accessible online, often months in advance of the assigned print journal issue date (`pubdate`).
- **FAISS (Facebook AI Similarity Search):** An open-source, highly optimized C++ library with Python bindings for dense vector similarity search and clustering.
- **Fail-Closed Security:** A design principle where a security or configuration failure causes the system to reject the operation and shut down safely, rather than falling back to an insecure default.
- **Grounded Intelligence:** AI-synthesized outputs that are strictly derived from and cross-referenced with verifiable source quotes, rather than generated from parametric memory.
- **IndexFlatIP:** A FAISS index type that performs an exact, brute-force inner-product search across all stored vectors, guaranteeing $100\%$ recall without quantization loss.
- **Levenshtein Distance:** A string metric measuring the minimum number of single-character edits (insertions, deletions, substitutions) required to transform one word into another.
- **Local-First Architecture:** A software architecture prioritizing on-premises processing, storing user data and executing AI models locally, using cloud services only as an optional, consented fallback.
- **PostgreSQL Advisory Lock:** An application-defined 64-bit mutex lock managed by PostgreSQL that prevents concurrent background workers or processes from colliding on shared tasks.
- **Prompt Injection:** An attack vector against LLMs where untrusted input text attempts to override system instructions or alter the model's intended behavioral constraints.
- **Semantic Relevance Floor:** An empirically calibrated threshold ($0.835$ in ResearchLens) below which candidate vector matches are dropped to prevent semantic drift.
- **SPECTER2:** A scientific document representation model developed by the Allen Institute for AI (`allenai/specter2_base`), pre-trained on citation graphs.
- **Step 8b Chronology Guard:** A programmatic invariant in DRIUT classification preventing an earlier published paper from being categorized as an improvement, extension, or replacement of a later paper.

---

## Section 16: Presentation Gaps, Limitations, & Future Work

### 16.1 Explicit Presentation Gaps to Acknowledge
1. **Absence of Formal IR Benchmark Metrics:** The repository lacks standardized IR evaluation figures (such as NDCG@10, MAP, or Recall@K against SciDocs / MS MARCO). Do not fabricate percentages; present qualitative query evaluations and the mathematical validation of the 0.835 relevance floor.
2. **Current Catalog Scale:** The local persistent database contains 162 papers. While external connectors fetch thousands of candidate records on-the-fly, the local catalog represents a curated demonstration corpus.
3. **Historical DRIUT Alert Remnants:** 90 historical alerts in the database violate chronology because they were generated prior to the implementation of the Step 8b guard. An administrative cleanup script has been verified but not yet executed on the live database.

### 16.2 Known System Limitations
- **PDF Extraction Depth:** PyPDF extracts embedded text cleanly from digital PDFs, but cannot process scanned image-only PDFs without external OCR software (such as Tesseract).
- **Language Scope:** Evidence extraction heuristics and regex patterns are optimized for English-language scientific manuscripts.
- **CPU Inference Trade-off:** Running SPECTER2 and Ollama Qwen2.5-3B on CPU avoids expensive GPU requirements, but bounds assistant response times to $1.5$–$3.8$ seconds.

### 16.3 Proposed Future Work
1. **Automated Historical Alert Cleanup:** Execute the verified administrative cleanup script to purge the 90 pre-guard chronology violations from PostgreSQL.
2. **Standardized SciDocs Benchmarking:** Implement an automated evaluation pipeline measuring NDCG@10 and Mean Reciprocal Rank (MRR) against the 100k-paper SciDocs benchmark suite.
3. **OCR Integration for Scanned Manuscripts:** Integrate `pdf2image` and Tesseract OCR to allow ingesting legacy physical journal scans.
4. **Multi-Institution Federation:** Extend DRIUT to listen to university institutional repositories and OAI-PMH feeds.
5. **Public Production Ingress:** Finalize production deployment with public domain DNS, Nginx reverse proxy, and Let's Encrypt TLS certificates.
