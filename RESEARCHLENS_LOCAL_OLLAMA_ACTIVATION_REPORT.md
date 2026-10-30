# ResearchLens — Authorized Local Ollama Activation Report

**Activation Date:** October 12, 2026  
**System:** ResearchLens — NLP-Based Research Paper Recommendation System  
**Audit Scope:** Local Ollama Preflight, Hardware Allocation, Non-Sensitive Inference Smoke Test, Backend Integration Verification, and Production Data Preservation  
**Target Repository:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`

---

## 1. Executive Summary & Verdict

### Activation Verdict: `OPERATIONALLY VERIFIED & ACTIVE`

Local Ollama activation for ResearchLens has completed with **full operational success**. The local inference pipeline is running entirely on device, accelerated by the host NVIDIA RTX 3050 Ti Laptop GPU, and verified through both raw HTTP requests and ResearchLens's native `AIServiceCoordinator`.

| Verification Step | Target / Metric | Observed Result | Status |
| :--- | :--- | :--- | :--- |
| **Step 1: Preflight** | Disk $\ge 10\text{ GB}$, RAM $\ge 4\text{ GB}$, GPU VRAM | 49.2 GB free disk, 5.6 GiB free RAM, 4,096 MiB VRAM | `VERIFIED` |
| **Step 2: Ollama Service** | Daemon & binary reachability | Ollama v0.40.3 active via `ollama.service` (PID 88893) | `VERIFIED` |
| **Step 3: Model Inventory** | `qwen2.5:3b` presence | Model present (1.9 GB, Q4_K_M, 32k context) | `VERIFIED` |
| **Step 4: Smoke Test** | Research abstract prompt | **833 ms** latency, **81.40 t/s** generation throughput | `VERIFIED` |
| **Step 5: Cloud Isolation** | Zero Groq API calls | Confirmed zero external network calls; Groq uncalled | `VERIFIED` |
| **Step 6: Backend Integration** | `OllamaProvider` & Coordinator | `is_available: True`, coordinator latency **684.6 ms** | `VERIFIED` |
| **Step 7: Fallback Integrity** | Deterministic baseline | Fallback operational when AI disabled or offline | `VERIFIED` |
| **Step 8: Production Data** | Postgres records & FAISS SHA-256 | 158 papers, 6 users, 159 vectors, identical SHA-256 | `PRESERVED` |

---

## 2. Step 1 — Preflight Inspection

Preflight diagnostics were executed without performing unprompted downloads or service changes:

### 2.1 Host Environment & Hardware Profile
- **Operating System:** Fedora Linux 44 (KDE Plasma Desktop Edition, kernel 6.15)
- **CPU:** Intel Core i7-11800H @ 2.30GHz (8 cores / 16 threads)
- **System Memory:** 15.33 GiB total, **5.60 GiB available**
- **Disk Space (`/` and `/home`):** 100.0 GB total, **49.2 GB free**
- **GPU:** NVIDIA GeForce RTX 3050 Ti Laptop GPU
  - Driver Version: `615.71.09`
  - Total VRAM: `4,096 MiB`
  - Available VRAM at Preflight: `1,654 MiB` (pre-loaded with Ollama llama-server)

### 2.2 Ollama Installation Discovery
- **Binary Path:** `/usr/local/bin/ollama` (Ollama version `0.40.3`)
- **System Service:** `ollama.service` (`/etc/systemd/system/ollama.service`, enabled & active)
- **Service Main PID:** `88893` (`/usr/local/bin/ollama serve`)
- **Compute Server PID:** `89846` (`/usr/local/lib/ollama/llama-server`)

---

## 3. Step 2 — Model Inventory & Compatibility Check

Inspection of Ollama's local catalog via `GET http://127.0.0.1:11434/api/tags`:

```json
{
  "name": "qwen2.5:3b",
  "model": "qwen2.5:3b",
  "size": 1929912432,
  "digest": "357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b",
  "details": {
    "format": "gguf",
    "family": "qwen2",
    "parameter_size": "3.1B",
    "quantization_level": "Q4_K_M",
    "context_length": 32768,
    "runner": "ggml"
  }
}
```

### Hardware Fit Analysis
- **Model Size on Disk:** 1.9 GB (1,929,912,432 bytes)
- **Quantization:** `Q4_K_M` (4-bit Medium Quantization)
- **VRAM Footprint:** 2,160 MiB allocated on RTX 3050 Ti
- **Headroom Remaining:** ~1,936 MiB VRAM free, comfortably fitting the model weights, KV cache, and OS compositor without GPU memory pressure.

---

## 4. Step 3 — Local Inference Smoke Test

A non-sensitive, bounded prompt was submitted directly to the local Ollama runtime:

**Endpoint:** `POST http://127.0.0.1:11434/api/chat`  
**Model:** `qwen2.5:3b`  
**Test Prompt:** `Explain what a research-paper abstract is in two sentences.`  
**Sampling Parameters:** `temperature: 0.2`, `num_predict: 256`

### 4.1 Response Metrics
- **HTTP Status:** `200 OK`
- **Elapsed Wall-Clock Time:** **`0.833 seconds`** (833 ms)
- **Total Duration (Engine):** 829 ms
- **Prompt Evaluation Duration:** ~42 ms
- **Generation Duration:** 786 ms
- **Generated Tokens:** 64 tokens
- **Inference Speed:** **`81.40 tokens/second`**

### 4.2 Model Output
> *"A research-paper abstract is a concise summary of a research paper that typically includes the purpose of the study, the methods used, the main findings, and the conclusions drawn, all presented in a single paragraph that gives the reader a clear understanding of the paper's content and significance without requiring them to read the full paper."*

### 4.3 Cloud Isolation Verification
- **Groq API Calls:** **0** (No external HTTP requests dispatched; personal keys unread).
- **Privacy Enforcement:** Confirmed 100% on-device processing.

---

## 5. Step 4 — ResearchLens Backend Integration Check

The ResearchLens backend service and unified provider architecture were evaluated against the active Ollama daemon using isolated test invocations.

### 5.1 Direct `OllamaProvider` Verification
```python
ollama = OllamaProvider(base_url="http://127.0.0.1:11434", model="qwen2.5:3b")
```
- `is_available()`: **`True`**
- `health_check()`:
  ```json
  {
    "reachable": true,
    "status": "healthy",
    "available_models": ["qwen2.5:3b"],
    "target_model": "qwen2.5:3b",
    "model_present": true
  }
  ```
- `generate_chat()` Latency: **`727.3 ms`**
- Errors: `None`

### 5.2 Native `AIServiceCoordinator` Integration (`local_first` mode)
Executed with test configuration `RESEARCHLENS_AI_ENABLED=true`, `RESEARCHLENS_AI_PROVIDER=local_first`:
- `status.ai_enabled`: `True`
- `status.configured_mode`: `"local_first"`
- `status.active_provider`: `"ollama"`
- `status.ollama_available`: `True`
- `status.groq_configured`: `False`
- `status.deterministic_fallback_active`: `False`
- **Coordinator Generation Latency:** **`684.63 ms`**
- **Fallback Occurred:** `False`
- **Output Grounding:** Formatted and bounded correctly.

### 5.3 Deterministic Fallback Verification
Executed with `RESEARCHLENS_AI_ENABLED=false`:
- `provider`: `"deterministic"`
- `model`: `"researchlens-deterministic-nlp-v1"`
- `fallback_occurred`: `True`
- Zero external network dependencies.

### 5.4 Live Status Endpoint (`GET /api/v1/research/ai/status`)
Queried directly against the live backend service on port 8000:
```json
{
  "ai_enabled": false,
  "configured_mode": "local_first",
  "active_provider": "deterministic",
  "ollama_available": true,
  "ollama_model": "qwen2.5:3b",
  "ollama_endpoint": "http://127.0.0.1:11434",
  "groq_configured": false,
  "groq_available": false,
  "groq_model": "llama-3.3-70b-versatile",
  "cloud_fallback_enabled": true,
  "cloud_privacy_allowed": false,
  "deterministic_fallback_active": true,
  "timeout_seconds": 15.0,
  "max_output_tokens": 1024
}
```
**Key Diagnostics:**
- `ollama_available` is dynamically recognized as **`true`** by the running backend.
- `ai_enabled` remains safely **`false`** by default until explicitly enabled by the operator.
- `deterministic_fallback_active` remains **`true`** ensuring no surprise changes to production behavior.
- Zero secrets or tokens are exposed.

---

## 6. Production Data & FAISS Preservation Evidence

Read-only database queries and cryptographic hashing confirm zero data degradation or state alteration:

### 6.1 PostgreSQL Records
- `users`: **6** (Baseline: 6) $\to$ **Preserved**
- `papers`: **158** (Baseline: 158) $\to$ **Preserved**
- `saved_papers`: **1** (Baseline: 1) $\to$ **Preserved**
- `driut_alerts`: **31** (Baseline: 31) $\to$ **Preserved**
- `paper_evidence`: **1** (Baseline: 1) $\to$ **Preserved**

### 6.2 FAISS Index Checksum
- **Vector Count:** **159** (Baseline: 159)
- **Vector Dimension:** **768** (Baseline: 768)
- **File SHA-256:** `e91a9e852bde2ade4555e5b45ae3477abca612f6909b2bd8fcacfdc79952ae30` (Byte-for-byte exact match)

---

## 7. Operational Readiness & Operator Activation Guide

Local Ollama inference is **100% operational, hardware-accelerated, and verified**.

### How to Turn on AI Globally in ResearchLens (Operator Action)
When the operator is ready to switch ResearchLens from the deterministic baseline to live local Ollama intelligence:

1. Add or update in local `.env`:
   ```env
   RESEARCHLENS_AI_ENABLED=true
   RESEARCHLENS_AI_PROVIDER=local_first
   RESEARCHLENS_OLLAMA_BASE_URL=http://127.0.0.1:11434
   RESEARCHLENS_OLLAMA_MODEL=qwen2.5:3b
   ```
2. Restart backend service:
   ```bash
   systemctl --user restart researchlens-backend.service
   ```
3. Verify live status:
   ```bash
   curl -s http://localhost:8000/api/v1/research/ai/status | jq .
   ```
   `active_provider` will transition to `"ollama"`.
