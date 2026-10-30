# ResearchLens — AI Integration Readiness & Architectural Handoff
**Document Version:** 1.0.0 — Post-Non-AI Stabilization Baseline  
**Date:** October 12, 2026  
**Repository:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`

---

## 1. Executive Summary

This handoff specification prepares ResearchLens for the upcoming **AI Integration Phase**. 

The non-AI foundation is fully stabilized, verified, and locked:
- **Test Isolation:** 100% isolated test runs with zero production database writes (PostgreSQL 16 in Podman) and zero FAISS index mutations. All 222 backend pytest tests and 63 frontend Vitest tests pass cleanly.
- **Authentication & User Isolation:** Full JWT Bearer authentication, bcrypt hashing, per-user private literature library isolation, and DRIUT ownership controls are operating and verified.
- **Deterministic Research Intelligence:** The baseline system features robust, deterministic NLP for character-offset evidence extraction, structured comparison matrices, chronological research evolution, and grounded citation synthesis.
- **Native Runtime Health:** Native Fedora systemd services (`researchlens-backend.service`, `researchlens-frontend.service`) and the Podman PostgreSQL database are running smoothly.

This document defines the exact architectural boundaries, hardware capacity, integration interfaces, and regression guards required before introducing local AI/LLM components.

---

## 2. Verified Host Hardware & Resource Capacity

The following hardware specifications were verified directly on the host system:

| Hardware Component | Verified Specification | Allocation Guidance for AI Phase |
| :--- | :--- | :--- |
| **CPU** | 11th Gen Intel(R) Core(TM) i7-11800H @ 2.30GHz (8 physical cores, 16 logical threads) | High performance for CPU token generation (llama.cpp) and concurrent SPECTER2 embedding inferences. |
| **System RAM** | 15.0 GiB Physical Memory (4.7 GiB free / available under current idle load), 8.0 GiB Swap | Sufficient for in-memory quantized models (up to 7B parameters at Q4_K_M quantization = ~4.2 GB RAM). |
| **Discrete GPU** | NVIDIA GeForce RTX 3050 Ti Laptop GPU (4,096 MiB / 4 GB Dedicated VRAM) | **VRAM is the primary constraint.** Small 1.5B–3.8B parameter models can run fully offloaded in VRAM (requiring 1.8–3.2 GB). 7B/8B models require hybrid GPU/CPU layer offloading or pure CPU inference. |
| **OS & Display** | Fedora Linux 44 (`x86_64`), Wayland / Hyprland | Native Linux execution with CUDA / cuDNN drivers available. |

### Recommended Model Profiles for AI Phase
1. **Ultra-Fast Edge Profile (Fully GPU VRAM Offloaded, 0 CPU bottleneck):**
   - **Recommended Models:** `Qwen2.5-Coder-1.5B-Instruct` (Q4_K_M / Q8_0), `Llama-3.2-1B-Instruct` (Q4_K_M), `Llama-3.2-3B-Instruct` (Q4_K_M).
   - **VRAM Footprint:** ~1.5 GB to 2.8 GB VRAM.
   - **Inference Speed:** ~45–65 tokens/second.
   - **Role:** Instant evidence synthesis, query refinement, keyphrase summarization.
2. **High-Accuracy Balanced Profile (Hybrid Offload / CPU fallback):**
   - **Recommended Models:** `Phi-3.5-mini-instruct-3.8B` (Q4_K_M) or `Mistral-7B-Instruct-v0.3` (Q4_K_M via partial GPU offload).
   - **Memory Footprint:** ~3.0 GB VRAM + 2.5 GB System RAM.
   - **Inference Speed:** ~18–28 tokens/second.
   - **Role:** Complex comparative synthesis, research gap formulation, scientific claim verification.

---

## 3. Existing Architecture: SPECTER2 & FAISS Foundation

ResearchLens already possesses an enterprise-grade vector embedding and semantic search pipeline:

```
[User Query / PDF Text]
        │
        ▼
[allenai/specter2_base] (HuggingFace Transformers, dim=768)
        │
        ├─► Local MD5 Cache (backend/data/processed/cache/)
        │
        ▼
[faiss.IndexFlatIP] (Inner Product on L2-Normalized Vectors)
        │
        ├─► Persistent File: backend/data/processed/faiss/research_index.faiss (159 vectors)
        └─► Metadata Store: backend/data/processed/faiss/papers_meta.json
```

### Invariants for the AI Phase
1. **Do Not Replace SPECTER2 with an LLM for Vector Retrieval:**
   - SPECTER2 was trained explicitly on citation graphs and scientific literature abstracts. It outperforms general-purpose LLMs on scholarly semantic proximity.
   - All vector retrieval, nearest-neighbor searches, and candidate ranking must remain with SPECTER2 + FAISS.
2. **Preserve FAISS Dimensionality & Normalization:**
   - FAISS dimension is strictly `768`. Vectors are strictly L2-normalized so inner product equals cosine similarity.
   - Live production vectors must never be overwritten or deleted.
3. **Recovery Synchronization (`sync_unindexed_papers`):**
   - The AI phase must respect the atomic vector synchronization contract established in `vector_index.py`.

---

## 4. Deterministic Intelligence vs. AI Integration Boundaries

To maintain high scientific integrity, avoid hallucinations, and preserve auditability, ResearchLens maintains a strict separation between deterministic rules and generative models.

### Features That MUST Remain Deterministic
1. **Evidence Span Extraction & Character Offsets:**
   - Extracting exact character slices (`char_start`, `char_end`) from papers must remain deterministic via `evidence_service.py`. Generative models must not fabricate offsets or alter verbatim text.
2. **Catalog Duplicate Detection:**
   - Exact DOI equality and Jaccard token set similarity (> 0.85) in `deduplication.py` must remain deterministic to ensure catalog integrity.
3. **DRIUT Taxonomy Classification Baselines:**
   - The 6 impact categories (`Extension`, `Improvement`, `Challenge`, `Reproduction`, `Alternative`, `Potential Replacement`) rely on precise lexical patterns and grounded evidence strength. LLMs should only augment explanation phrasing, never override deterministic evidence disqualification (such as metric incompatibility or missing comparative baselines).
4. **Authentication & Authorization:**
   - Security policies, JWT verification, and SQL filtering must remain purely algorithmic and immune to prompt injection.

### Features That Will Benefit from Optional Local LLM Augmentation
1. **Research Assistant Q&A Synthesis (`assistant_service.py`):**
   - Currently uses deterministic template synthesis over retrieved evidence passages.
   - *AI Enhancement:* Feed the top-3 retrieved evidence passages into a local LLM prompt as context, producing flowing natural language answers with strict bracketed citations (e.g. `[Paper 1]`).
2. **Executive Synthesis in Comparison Matrix (`comparison_service.py`):**
   - Currently uses multi-dimensional rule-based summaries.
   - *AI Enhancement:* Generate an executive synthesis paragraph contrasting methodologies while preserving the 12 deterministic comparison dimensions.
3. **Research Gap Formulation (`evolution_service.py`):**
   - Currently extracts unexplored methodological intersections via keyphrase graph analysis.
   - *AI Enhancement:* Generate compelling hypothesis proposals based on identified topological gaps in the citation network.

---

## 5. Local-First & Privacy Requirements

1. **Zero Cloud LLM Data Leakage:**
   - Under no circumstances should user manuscripts, draft abstracts, notes, or research queries be transmitted to third-party cloud LLM APIs (OpenAI, Anthropic, Google Gemini, etc.) unless an explicit enterprise opt-in is configured by the user.
   - All AI inference must run locally on the user's host (e.g. via local Ollama or llama.cpp backend).
2. **Graceful Fallback When AI Is Disabled:**
   - If the local LLM server is offline, out of memory, or uninstalled, ResearchLens must continue operating seamlessly using its existing deterministic services without raising 500 errors.
   - Health endpoints should report AI readiness status as an optional capability (`"ai_provider": "available" | "disabled"`).

---

## 6. Target API & Interface Boundaries for AI Integration

When implementing the local AI provider, integrate via a clean pluggable interface:

```python
# Proposed: backend/app/services/ai_provider.py

class BaseLLMProvider(ABC):
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if local AI runtime is online and responsive."""
        pass

    @abstractmethod
    async def generate_grounded_answer(
        self,
        question: str,
        evidence_passages: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Synthesize answer strictly grounded in provided passages."""
        pass

    @abstractmethod
    async def synthesize_comparison(
        self,
        paper_a: Dict[str, Any],
        paper_b: Dict[str, Any],
        dimensions: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Generate high-level comparative synthesis."""
        pass
```

### Prompt Engineering Guardrails
- **Grounding Constraint:** Always instruct the model: *"You are an academic research assistant. Answer the user's question using ONLY the provided evidence passages. If the passages do not contain sufficient evidence to answer, state clearly that the evidence is insufficient. Do not speculate."*
- **Temperature:** Set temperature to `<= 0.2` for scientific tasks to minimize creative drift.

---

## 7. Required Evaluation & Regression Tests for the AI Phase

Before accepting any AI-powered PR or feature branch:

1. **Backend Regression Gate:**
   - All 222 non-AI pytest unit and integration tests must continue to pass (`./venv/bin/pytest tests/ -q`).
2. **Fallback Verification:**
   - Execute tests with the AI service disabled / mocked offline. All endpoints must return their standard deterministic response without crashing.
3. **Truthfulness & Hallucination Guard Test:**
   - Submit adversarial prompts (e.g. asking for claims not present in the paper). Assert that the system outputs an honest "insufficient evidence" disclaimer rather than a hallucinated assertion.
4. **Latency Budget:**
   - AI-enhanced endpoints must enforce an internal timeout (<= 15 seconds). If generation times out, return the deterministic synthesis immediately.

---

## 8. Summary & Certification

| Pillar | Status | Certification |
| :--- | :---: | :--- |
| **Non-AI Core Infrastructure** | Verified | Complete, stabilized, tested (222/222 Pytest, 63/63 Vitest). |
| **Vector Engine (SPECTER2/FAISS)** | Verified | Persistent, indexed, duplicate-preventing. |
| **Authentication & Ownership** | Verified | Secure JWT + bcrypt + per-user library isolation. |
| **Deterministic NLP Fallbacks** | Verified | Character-offset evidence extraction, 12-dim matrix, 6-class DRIUT. |
| **Hardware Fit** | Confirmed | RTX 3050 Ti (4GB VRAM) suitable for 1.5B–3.8B Q4 models; CPU/RAM suitable for 7B Q4. |
| **AI Integration Phase** | **READY TO PROCEED** | Clear boundaries defined; zero blockers. |
