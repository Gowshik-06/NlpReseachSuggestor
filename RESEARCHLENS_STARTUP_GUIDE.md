# ResearchLens — One-Command Startup Guide (“HIP HIP HURRAY!”)

Welcome to the **ResearchLens** launcher guide. This guide explains how to start, monitor, and stop the entire ResearchLens system on Fedora Linux with Hyprland using a single, reliable command.

---

## 1. Quickstart

To launch all services, run health verification, and open the application in your browser:

```bash
cd "/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender"
./start-researchlens.sh
```

When started, you will be greeted by the startup banner:

```text
╔══════════════════════════════════════════════════╗
║                                                  ║
║          HIP HIP HURRAY! 🎉                      ║
║             RESEARCHLENS                         ║
║        Your Research Assistant is Waking Up      ║
║                                                  ║
╚══════════════════════════════════════════════════╝
```

Once all services are verified healthy, the launcher prints:

```text
🎉 HIP HIP HURRAY! RESEARCHLENS IS READY!

Frontend:    http://localhost:3000
Backend API: http://localhost:8000
API Docs:    http://localhost:8000/docs

Status:      READY
```

and automatically opens `http://localhost:3000` in your default browser via `xdg-open`.

---

## 2. Stopping the Application

To cleanly stop the application services:

```bash
cd "/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender"
./stop-researchlens.sh
```

### Safety Guarantees:
- **Verified process termination:** `stop-researchlens.sh` verifies process ownership (inspecting `/proc/<pid>/cmdline`) and terminates only FastAPI backend and Vite frontend processes owned by ResearchLens. It **never** terminates processes based solely on a port number.
- **Data preservation:** The PostgreSQL container (`research-paper-recommender-postgres-1`) and its persistent database storage remain running and intact.
- **Index safety:** The FAISS vector index files (`research_index.faiss`, `papers_meta.json`) are preserved untouched.

---

## 3. Convenient Global Command (`researchlens`)

You can launch ResearchLens from any terminal by creating a symlink in your user's standard binary directory (`~/.local/bin/` is already in your Fedora `PATH`):

```bash
mkdir -p ~/.local/bin
ln -sf "/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/start-researchlens.sh" ~/.local/bin/researchlens
ln -sf "/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/stop-researchlens.sh" ~/.local/bin/stop-researchlens
```

Once linked, simply run:

```bash
researchlens
```

from any directory or terminal window!

---

## 4. Fedora + Hyprland Desktop Integration

If you use Hyprland as your window manager, you can bind a key combination (such as `Super + Shift + R`) to launch ResearchLens in a dedicated terminal window.

Add the following line to your `~/.config/hypr/hyprland.conf`:

```ini
# Launch ResearchLens in Kitty terminal
bind = $mainMod SHIFT, R, exec, kitty --hold -e /home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/start-researchlens.sh
```

*(If you use a different terminal emulator such as `foot` or `alacritty`, substitute `kitty` with your preferred terminal).*

---

## 5. Startup Sequence & Verification Flow

The launcher executes the following 5-phase startup sequence:

```
[1/5] Preflight Sanity Checks
      ├── Validates backend/.env and frontend/.env existence
      ├── Validates Python virtual environment (backend/venv) and uvicorn binary
      ├── Validates Node.js runtime and frontend/node_modules
      ├── Validates Podman and research-paper-recommender-postgres-1 container
      ├── Checks Ollama local AI availability and qwen2.5:3b model readiness
      └── Inspects ports 8000 & 3000 (identifies existing ResearchLens vs foreign processes)

[2/5] Database Verification
      ├── Checks PostgreSQL on 127.0.0.1:5432
      └── If stopped, starts existing container (NO migrations, seeds, or resets)

[3/5] Backend Startup (FastAPI)
      ├── Starts uvicorn on 127.0.0.1:8000 (or reuses healthy existing instance)
      ├── Tracks PID in logs/backend.pid and streams output to logs/backend.log
      └── Verifies /api/v1/health responds with {"status":"ok","database":"connected"}

[4/5] Frontend Startup (React/Vite)
      ├── Starts Vite on 127.0.0.1:3000 with --strictPort
      ├── Tracks PID in logs/frontend.pid and streams output to logs/frontend.log
      └── Verifies HTTP 200 and application HTML serving on http://127.0.0.1:3000

[5/5] Readiness & Browser Launch
      ├── Displays completion banner
      └── Invokes xdg-open http://localhost:3000
```

---

## 6. Service Architecture & Endpoints

| Component | Technology | Address / Port | Health Endpoint |
|---|---|---|---|
| **Frontend** | React 18, Vite, TypeScript | `http://localhost:3000` | `http://127.0.0.1:3000/` |
| **Backend API** | FastAPI, Python 3.14 | `http://localhost:8000` | `http://127.0.0.1:8000/api/v1/health` |
| **API Docs** | Swagger UI | `http://localhost:8000/docs` | `http://127.0.0.1:8000/docs` |
| **Database** | PostgreSQL 16 (Podman) | `127.0.0.1:5432` | TCP port probe |
| **Local AI** | Ollama (`qwen2.5:3b`) | `http://127.0.0.1:11434` | `http://127.0.0.1:11434/api/tags` |

### Log Files:
- Backend runtime log: `logs/backend.log`
- Frontend runtime log: `logs/frontend.log`
- Process IDs: `logs/backend.pid`, `logs/frontend.pid`

---

## 7. Command Options & Troubleshooting

### Available Options:

- `./start-researchlens.sh --no-browser` — Starts all services but skips automatic browser opening.
- `./start-researchlens.sh --status` — Displays current operational status of all services.
- `./start-researchlens.sh --help` — Displays usage instructions.

### Troubleshooting:

1. **Port 8000 or 3000 occupied by foreign process:**
   If another application uses port 8000 or 3000, ResearchLens reports the conflicting process and exits safely. Inspect the listening process using:
   ```bash
   ss -tulpn | grep -E ':(8000|3000)\b'
   ```
2. **Backend health timeout:**
   Inspect the tail of the backend log:
   ```bash
   tail -n 30 logs/backend.log
   ```
3. **Database connection failure:**
   Verify the Podman PostgreSQL container status:
   ```bash
   podman ps -a --filter name=research-paper-recommender-postgres-1
   podman logs --tail 20 research-paper-recommender-postgres-1
   ```
4. **Ollama local AI:**
   Verify that Ollama is running and has the model loaded:
   ```bash
   curl -s http://127.0.0.1:11434/api/tags
   ```

---

## 8. Data & Privacy Protections

- **Zero Reseeding / Overwrites:** The launcher never runs migrations, seed scripts, database truncation, re-indexing, or paper ingestion.
- **Privacy Gate:** The backend enforces `RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT=false`.
- **Secret Safety:** The launcher and logs never expose API keys, passwords, or JWT secrets.
