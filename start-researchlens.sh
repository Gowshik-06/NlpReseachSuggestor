#!/usr/bin/env bash
# ==============================================================================
# start-researchlens.sh — One-Command ResearchLens Launcher
# ==============================================================================
# Starts all ResearchLens services with a single command:
#   1. Preflight checks (environment, configuration, ports, dependencies)
#   2. Starts containerized PostgreSQL in Podman if stopped (preserves all data)
#   3. Starts FastAPI backend on 127.0.0.1:8000 with health validation
#   4. Starts React/Vite frontend on 127.0.0.1:3000 with strictPort
#   5. Verifies end-to-end readiness and opens the app in your browser
# ==============================================================================
set -euo pipefail

# ------------------------------------------------------------------------------
# Script & Repository Resolution
# ------------------------------------------------------------------------------
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)"
LOGS_DIR="${REPO_ROOT}/logs"
BACKEND_PID_FILE="${LOGS_DIR}/backend.pid"
FRONTEND_PID_FILE="${LOGS_DIR}/frontend.pid"

mkdir -p "${LOGS_DIR}"

# ------------------------------------------------------------------------------
# Formatting & Colors
# ------------------------------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    BOLD='\033[1m'
    CYAN='\033[0;36m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BLUE='\033[0;34m'
    MAGENTA='\033[0;35m'
    RESET='\033[0m'
else
    BOLD=''
    CYAN=''
    GREEN=''
    YELLOW=''
    RED=''
    BLUE=''
    MAGENTA=''
    RESET=''
fi

# ------------------------------------------------------------------------------
# Flags & Arguments
# ------------------------------------------------------------------------------
AUTO_OPEN_BROWSER=true

for arg in "$@"; do
    case "${arg}" in
        --no-browser)
            AUTO_OPEN_BROWSER=false
            ;;
        --help|-h)
            cat << 'EOF'
Usage: ./start-researchlens.sh [OPTIONS]

Starts the entire ResearchLens system (PostgreSQL, FastAPI backend, Vite frontend)
verifies service health, and launches the application in your default browser.

Options:
  --no-browser    Skip opening the browser automatically after startup.
  --status        Display current status of ResearchLens services and exit.
  --help, -h      Display this help message and exit.
EOF
            exit 0
            ;;
        --status)
            if [ -x "${REPO_ROOT}/scripts/dev-status.sh" ]; then
                exec "${REPO_ROOT}/scripts/dev-status.sh"
            else
                echo "dev-status.sh not found."
                exit 1
            fi
            ;;
        *)
            echo -e "${YELLOW}Warning: Unknown argument '${arg}' ignored.${RESET}"
            ;;
    esac
done

# ------------------------------------------------------------------------------
# Cleanup Trap for Partial Startup
# ------------------------------------------------------------------------------
STARTED_BE_THIS_RUN=false
STARTED_FE_THIS_RUN=false

cleanup_on_interrupt() {
    echo ""
    echo -e "${YELLOW}Startup interrupted. Cleaning up services started in this session...${RESET}"
    if [ "${STARTED_FE_THIS_RUN}" = "true" ]; then
        if command -v systemctl >/dev/null 2>&1 && systemctl --user is-active --quiet researchlens-frontend 2>/dev/null; then
            systemctl --user stop researchlens-frontend >/dev/null 2>&1 || true
        fi
        if [ -f "${FRONTEND_PID_FILE}" ]; then
            kill "$(cat "${FRONTEND_PID_FILE}")" >/dev/null 2>&1 || true
            rm -f "${FRONTEND_PID_FILE}"
        fi
    fi
    if [ "${STARTED_BE_THIS_RUN}" = "true" ]; then
        if command -v systemctl >/dev/null 2>&1 && systemctl --user is-active --quiet researchlens-backend 2>/dev/null; then
            systemctl --user stop researchlens-backend >/dev/null 2>&1 || true
        fi
        if [ -f "${BACKEND_PID_FILE}" ]; then
            kill "$(cat "${BACKEND_PID_FILE}")" >/dev/null 2>&1 || true
            rm -f "${BACKEND_PID_FILE}"
        fi
    fi
    echo -e "${RED}Startup aborted.${RESET}"
    exit 130
}
trap cleanup_on_interrupt INT TERM

# ------------------------------------------------------------------------------
# Step A — Welcome Banner
# ------------------------------------------------------------------------------
echo -e "${CYAN}${BOLD}"
cat << 'EOF'
╔══════════════════════════════════════════════════╗
║                                                  ║
║          HIP HIP HURRAY! 🎉                      ║
║             RESEARCHLENS                         ║
║        Your Research Assistant is Waking Up      ║
║                                                  ║
╚══════════════════════════════════════════════════╝
EOF
echo -e "${RESET}"

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------
log_step() {
    local step="$1"
    local msg="$2"
    echo -e "${BOLD}${BLUE}[${step}]${RESET} ${msg}"
}

log_ok() {
    local msg="$1"
    echo -e "      ${GREEN}✔${RESET} ${msg}"
}

log_info() {
    local msg="$1"
    echo -e "      ${CYAN}ℹ${RESET} ${msg}"
}

log_warn() {
    local msg="$1"
    echo -e "      ${YELLOW}⚠${RESET} ${msg}"
}

log_fail() {
    local msg="$1"
    echo -e "      ${RED}✘${RESET} ${msg}"
}

get_process_on_port() {
    local port="$1"
    local proc=""
    if command -v ss >/dev/null 2>&1; then
        proc="$(ss -tulpn "sport = :${port}" 2>/dev/null | grep -E ":${port}\b" | head -n 1 || true)"
    fi
    if [ -z "${proc}" ] && command -v lsof >/dev/null 2>&1; then
        proc="$(lsof -iTCP:"${port}" -sTCP:LISTEN -n -P 2>/dev/null | tail -n +2 | head -n 1 || true)"
    fi
    echo "${proc}"
}

is_backend_researchlens() {
    local resp
    resp="$(curl -sf --max-time 3 http://127.0.0.1:8000/api/v1/health 2>/dev/null || true)"
    if echo "${resp}" | grep -q '"research-paper-recommender"'; then
        return 0
    elif echo "${resp}" | grep -q '"database":"connected"'; then
        return 0
    fi
    return 1
}

is_frontend_researchlens() {
    local resp
    resp="$(curl -sf --max-time 3 http://127.0.0.1:3000/ 2>/dev/null || true)"
    if echo "${resp}" | grep -qi 'ResearchLens'; then
        return 0
    elif echo "${resp}" | grep -q 'id="root"'; then
        return 0
    fi
    return 1
}

# ------------------------------------------------------------------------------
# Step B — Preflight Checks
# ------------------------------------------------------------------------------
log_step "1/5" "Performing preflight sanity checks..."

# 1. Config files
if [ ! -f "${REPO_ROOT}/backend/.env" ]; then
    log_fail "Missing backend configuration: ${REPO_ROOT}/backend/.env"
    exit 1
fi
if [ ! -f "${REPO_ROOT}/frontend/.env" ]; then
    log_fail "Missing frontend configuration: ${REPO_ROOT}/frontend/.env"
    exit 1
fi
if [ ! -f "${REPO_ROOT}/frontend/package.json" ]; then
    log_fail "Missing frontend package.json"
    exit 1
fi
log_ok "Configuration files verified."

# 2. Python environment
if [ -f "${REPO_ROOT}/backend/venv/Scripts/python.exe" ] && [ -f "${REPO_ROOT}/backend/venv/Scripts/uvicorn.exe" ]; then
    VENV_PYTHON="${REPO_ROOT}/backend/venv/Scripts/python.exe"
    VENV_UVICORN="${REPO_ROOT}/backend/venv/Scripts/uvicorn.exe"
elif [ -f "${REPO_ROOT}/backend/venv/bin/python" ] && [ -f "${REPO_ROOT}/backend/venv/bin/uvicorn" ]; then
    VENV_PYTHON="${REPO_ROOT}/backend/venv/bin/python"
    VENV_UVICORN="${REPO_ROOT}/backend/venv/bin/uvicorn"
else
    VENV_PYTHON="${REPO_ROOT}/backend/venv/bin/python"
    VENV_UVICORN="${REPO_ROOT}/backend/venv/bin/uvicorn"
fi
if [ ! -x "${VENV_PYTHON}" ] || [ ! -x "${VENV_UVICORN}" ]; then
    log_fail "Python virtual environment missing or invalid at backend/venv."
    log_info "Expected binaries: ${VENV_PYTHON} and ${VENV_UVICORN}"
    exit 1
fi
log_ok "Python virtual environment verified ($("${VENV_PYTHON}" --version))."

# 3. Frontend environment
# Ensure Node.js is in PATH for Windows (fnm path)
export PATH="${PATH}:/c/Users/GOWSHIK/AppData/Local/fnm_multishells/10428_1792688508648"
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    log_fail "Node.js and npm are required on the host system."
    exit 1
fi
if [ ! -d "${REPO_ROOT}/frontend/node_modules" ]; then
    log_fail "frontend/node_modules not found. Run 'npm install' inside frontend/."
    exit 1
fi
log_ok "Frontend runtime dependencies verified (Node $(node -v), npm $(npm -v))."

# 4. PostgreSQL service or container
PG_CONTAINER="research-paper-recommender-postgres-1"
if (echo > /dev/tcp/127.0.0.1/5432) >/dev/null 2>&1; then
    log_ok "PostgreSQL service is active and listening on 127.0.0.1:5432."
elif command -v podman >/dev/null 2>&1; then
    if podman inspect "${PG_CONTAINER}" >/dev/null 2>&1; then
        log_ok "Database container '${PG_CONTAINER}' confirmed (Podman)."
    else
        log_info "Database container '${PG_CONTAINER}' will be created during startup."
    fi
elif command -v docker >/dev/null 2>&1; then
    if docker inspect "${PG_CONTAINER}" >/dev/null 2>&1; then
        log_ok "Database container '${PG_CONTAINER}' confirmed (Docker)."
    else
        log_info "Database container '${PG_CONTAINER}' will be created during startup."
    fi
else
    log_fail "PostgreSQL is not listening on 127.0.0.1:5432 and neither Podman nor Docker is installed."
    log_info "Please install Podman or Docker, or start PostgreSQL on 127.0.0.1:5432."
    exit 1
fi

# 5. Ollama & Local AI
AI_ENABLED="$(grep -E '^RESEARCHLENS_AI_ENABLED=' "${REPO_ROOT}/backend/.env" | cut -d'=' -f2 | tr -d ' "' || echo 'false')"
OLLAMA_MODEL="$(grep -E '^RESEARCHLENS_OLLAMA_MODEL=' "${REPO_ROOT}/backend/.env" | cut -d'=' -f2 | tr -d ' "' || echo 'qwen2.5:3b')"

if [ "${AI_ENABLED}" = "true" ]; then
    if curl -sf --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        if curl -sf --max-time 2 http://127.0.0.1:11434/api/tags | grep -q "${OLLAMA_MODEL}"; then
            log_ok "Local AI active: Ollama reachable with model '${OLLAMA_MODEL}'."
        else
            log_warn "Ollama reachable, but model '${OLLAMA_MODEL}' not found. Cloud fallback will be used if configured."
        fi
    else
        log_warn "Ollama is not reachable on 127.0.0.1:11434. Cloud fallback (Groq) will handle AI queries if configured."
    fi
else
    log_info "Local AI features currently disabled via configuration."
fi

# 6. Check existing instances & port usage
BACKEND_REUSE=false
FRONTEND_REUSE=false

if (echo > /dev/tcp/127.0.0.1/8000) >/dev/null 2>&1; then
    if is_backend_researchlens; then
        BACKEND_REUSE=true
        log_info "Detected existing healthy ResearchLens backend on port 8000 (will reuse)."
    else
        PORT_PROC="$(get_process_on_port 8000)"
        log_fail "Port 8000 is occupied by an unrecognized process:"
        echo "      ${PORT_PROC:-unknown process}"
        log_info "ResearchLens will NOT terminate unknown processes. Please free port 8000 manually."
        exit 1
    fi
fi

if (echo > /dev/tcp/127.0.0.1/3000) >/dev/null 2>&1; then
    if is_frontend_researchlens; then
        FRONTEND_REUSE=true
        log_info "Detected existing healthy ResearchLens frontend on port 3000 (will reuse)."
    else
        PORT_PROC="$(get_process_on_port 3000)"
        log_fail "Port 3000 is occupied by an unrecognized process:"
        echo "      ${PORT_PROC:-unknown process}"
        log_info "ResearchLens will NOT terminate unknown processes. Please free port 3000 manually."
        exit 1
    fi
fi

# ------------------------------------------------------------------------------
# Step C — Start Dependencies (PostgreSQL)
# ------------------------------------------------------------------------------
log_step "2/5" "Verifying database service (PostgreSQL)..."

PG_READY=false
if (echo > /dev/tcp/127.0.0.1/5432) >/dev/null 2>&1; then
    PG_READY=true
    log_ok "PostgreSQL is already active and listening on 127.0.0.1:5432."
else
    # Determine container CLI (prefer podman, fallback to docker)
    CONTAINER_CMD="podman"
    if ! command -v podman >/dev/null 2>&1 && command -v docker >/dev/null 2>&1; then
        CONTAINER_CMD="docker"
    fi

    CONTAINER_EXISTS=false
    if "${CONTAINER_CMD}" inspect "${PG_CONTAINER}" >/dev/null 2>&1; then
        CONTAINER_EXISTS=true
    fi

    if [ "${CONTAINER_EXISTS}" = "true" ]; then
        CONTAINER_STATUS="$("${CONTAINER_CMD}" inspect "${PG_CONTAINER}" --format '{{.State.Status}}' 2>/dev/null || echo 'unknown')"
        if [ "${CONTAINER_STATUS}" != "running" ]; then
            log_info "Starting existing database container '${PG_CONTAINER}' (${CONTAINER_CMD})..."
            "${CONTAINER_CMD}" start "${PG_CONTAINER}" >/dev/null
        fi
    else
        log_info "Creating and starting PostgreSQL container '${PG_CONTAINER}' (${CONTAINER_CMD})..."
        if [ -f "${REPO_ROOT}/docker-compose.yml" ] && [ -f "${REPO_ROOT}/docker-compose.dev.yml" ]; then
            "${CONTAINER_CMD}" compose -f "${REPO_ROOT}/docker-compose.yml" -f "${REPO_ROOT}/docker-compose.dev.yml" up -d postgres >/dev/null 2>&1 || \
            "${CONTAINER_CMD}" run -d --name "${PG_CONTAINER}" -p 127.0.0.1:5432:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=research_papers postgres:16-alpine >/dev/null
        else
            "${CONTAINER_CMD}" run -d --name "${PG_CONTAINER}" -p 127.0.0.1:5432:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=research_papers postgres:16-alpine >/dev/null
        fi
    fi

    MAX_WAIT_PG=15
    for i in $(seq 1 "${MAX_WAIT_PG}"); do
        if (echo > /dev/tcp/127.0.0.1/5432) >/dev/null 2>&1; then
            PG_READY=true
            break
        fi
        sleep 1
    done

    if [ "${PG_READY}" = "true" ]; then
        log_ok "PostgreSQL is ready on 127.0.0.1:5432."
    else
        log_fail "PostgreSQL failed to respond on 127.0.0.1:5432 within ${MAX_WAIT_PG}s."
        log_info "Check container logs: ${CONTAINER_CMD} logs --tail 30 ${PG_CONTAINER}"
        exit 1
    fi
fi

# ------------------------------------------------------------------------------
# Step D — Start FastAPI Backend
# ------------------------------------------------------------------------------
log_step "3/5" "Checking backend service (FastAPI on 127.0.0.1:8000)..."

if [ "${BACKEND_REUSE}" = "true" ]; then
    BE_PID=""
    if [ -f "${BACKEND_PID_FILE}" ]; then
        BE_PID="$(cat "${BACKEND_PID_FILE}" 2>/dev/null || echo '')"
    fi
    log_ok "Reusing existing ResearchLens backend instance${BE_PID:+ (PID ${BE_PID})}."
else
    # Clean stale PID file if present
    if [ -f "${BACKEND_PID_FILE}" ]; then
        OLD_PID="$(cat "${BACKEND_PID_FILE}" 2>/dev/null || echo '')"
        if [ -n "${OLD_PID}" ] && ! kill -0 "${OLD_PID}" >/dev/null 2>&1; then
            rm -f "${BACKEND_PID_FILE}"
        fi
    fi

    log_info "Launching FastAPI backend..."
    STARTED_BE_THIS_RUN=true

    # Use systemd-run --user on Fedora if available, otherwise nohup fallback
    if command -v systemd-run >/dev/null 2>&1 && systemctl --user is-active --quiet default.target 2>/dev/null; then
        systemctl --user reset-failed researchlens-backend >/dev/null 2>&1 || true
        systemd-run --user --unit=researchlens-backend /bin/bash -c \
            "cd '${REPO_ROOT}/backend' && export PATH='${REPO_ROOT}/backend/venv/bin':\$PATH && exec '${VENV_UVICORN}' app.main:app --host 127.0.0.1 --port 8000 --reload > '${LOGS_DIR}/backend.log' 2>&1" >/dev/null 2>&1
        sleep 1
        BE_PID="$(systemctl --user show --property MainPID --value researchlens-backend 2>/dev/null || echo '')"
        [ -n "${BE_PID}" ] && echo "${BE_PID}" > "${BACKEND_PID_FILE}"
    else
        cd "${REPO_ROOT}/backend"
        nohup "${VENV_UVICORN}" app.main:app --host 127.0.0.1 --port 8000 --reload > "${LOGS_DIR}/backend.log" 2>&1 &
        BE_PID=$!
        echo "${BE_PID}" > "${BACKEND_PID_FILE}"
    fi

    # Bounded wait for backend health
    MAX_WAIT_BE=25
    BE_READY=false
    for i in $(seq 1 "${MAX_WAIT_BE}"); do
        HEALTH_RESP="$(curl -sf --max-time 2 http://127.0.0.1:8000/api/v1/health 2>/dev/null || echo '')"
        if echo "${HEALTH_RESP}" | grep -q '"status":"ok"'; then
            BE_READY=true
            break
        fi
        sleep 1
    done

    if [ "${BE_READY}" = "true" ]; then
        log_ok "Backend ready and healthy${BE_PID:+ (PID ${BE_PID})}."
    else
        log_fail "Backend failed to become healthy within ${MAX_WAIT_BE} seconds."
        echo ""
        echo "------ Last 20 lines of backend log (${LOGS_DIR}/backend.log) ------"
        tail -n 20 "${LOGS_DIR}/backend.log" 2>/dev/null || echo "(no log file found)"
        echo "------------------------------------------------------------------"
        cleanup_on_interrupt
        exit 1
    fi
fi

# ------------------------------------------------------------------------------
# Step E — Start React/Vite Frontend
# ------------------------------------------------------------------------------
log_step "4/5" "Checking frontend service (Vite on 127.0.0.1:3000)..."

# Verify API configuration
API_BASE="$(grep -E '^VITE_API_BASE_URL=' "${REPO_ROOT}/frontend/.env" | cut -d'=' -f2 | tr -d ' "' || echo '')"
if [ -n "${API_BASE}" ] && ! echo "${API_BASE}" | grep -qE 'localhost:8000|127\.0\.0\.1:8000'; then
    log_warn "frontend/.env VITE_API_BASE_URL is set to '${API_BASE}', expected localhost:8000."
fi

if [ "${FRONTEND_REUSE}" = "true" ]; then
    FE_PID=""
    if [ -f "${FRONTEND_PID_FILE}" ]; then
        FE_PID="$(cat "${FRONTEND_PID_FILE}" 2>/dev/null || echo '')"
    fi
    log_ok "Reusing existing ResearchLens frontend instance${FE_PID:+ (PID ${FE_PID})}."
else
    # Clean stale PID file if present
    if [ -f "${FRONTEND_PID_FILE}" ]; then
        OLD_PID="$(cat "${FRONTEND_PID_FILE}" 2>/dev/null || echo '')"
        if [ -n "${OLD_PID}" ] && ! kill -0 "${OLD_PID}" >/dev/null 2>&1; then
            rm -f "${FRONTEND_PID_FILE}"
        fi
    fi

    log_info "Launching React/Vite frontend..."
    STARTED_FE_THIS_RUN=true

    # Use systemd-run --user on Fedora if available, otherwise nohup fallback
    if command -v systemd-run >/dev/null 2>&1 && systemctl --user is-active --quiet default.target 2>/dev/null; then
        systemctl --user reset-failed researchlens-frontend >/dev/null 2>&1 || true
        systemd-run --user --unit=researchlens-frontend /bin/bash -c \
            "cd '${REPO_ROOT}/frontend' && exec npm run dev -- --host 127.0.0.1 --port 3000 --strictPort > '${LOGS_DIR}/frontend.log' 2>&1" >/dev/null 2>&1
        sleep 1
        FE_PID="$(systemctl --user show --property MainPID --value researchlens-frontend 2>/dev/null || echo '')"
        [ -n "${FE_PID}" ] && echo "${FE_PID}" > "${FRONTEND_PID_FILE}"
    else
        cd "${REPO_ROOT}/frontend"
        nohup npm run dev -- --host 127.0.0.1 --port 3000 --strictPort > "${LOGS_DIR}/frontend.log" 2>&1 &
        FE_PID=$!
        echo "${FE_PID}" > "${FRONTEND_PID_FILE}"
    fi

    # Bounded wait for frontend response
    MAX_WAIT_FE=20
    FE_READY=false
    for i in $(seq 1 "${MAX_WAIT_FE}"); do
        if is_frontend_researchlens; then
            FE_READY=true
            break
        fi
        sleep 1
    done

    if [ "${FE_READY}" = "true" ]; then
        log_ok "Frontend ready and serving application${FE_PID:+ (PID ${FE_PID})}."
    else
        log_fail "Frontend dev server failed to respond within ${MAX_WAIT_FE} seconds."
        echo ""
        echo "------ Last 20 lines of frontend log (${LOGS_DIR}/frontend.log) ------"
        tail -n 20 "${LOGS_DIR}/frontend.log" 2>/dev/null || echo "(no log file found)"
        echo "-------------------------------------------------------------------"
        cleanup_on_interrupt
        exit 1
    fi
fi

# ------------------------------------------------------------------------------
# Step F — Success & Open Application
# ------------------------------------------------------------------------------
log_step "5/5" "All services verified operational!"
echo ""

# Print required completion message
echo -e "${GREEN}${BOLD}"
cat << 'EOF'
🎉 HIP HIP HURRAY! RESEARCHLENS IS READY!

Frontend:    http://localhost:3000
Backend API: http://localhost:8000
API Docs:    http://localhost:8000/docs

Status:      READY
EOF
echo -e "${RESET}"

# Open browser if enabled and desktop environment is available
if [ "${AUTO_OPEN_BROWSER}" = "true" ]; then
    if command -v xdg-open >/dev/null 2>&1 && [ -n "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ]; then
        echo -e "🚀 Opening ${BOLD}http://localhost:3000${RESET} in your browser..."
        nohup xdg-open "http://localhost:3000" >/dev/null 2>&1 & disown || true
    else
        echo -e "🌐 Open ${BOLD}http://localhost:3000${RESET} in your browser to start researching!"
    fi
else
    echo -e "ℹ Browser auto-open skipped (--no-browser). Navigate to ${BOLD}http://localhost:3000${RESET}."
fi

exit 0
