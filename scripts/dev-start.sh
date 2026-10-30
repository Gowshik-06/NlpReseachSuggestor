#!/usr/bin/env bash
# ==============================================================================
# scripts/dev-start.sh — Start native development environment
# ==============================================================================
# - Ensures Podman PostgreSQL container is running and healthy
# - Starts native FastAPI backend on Fedora host (port 8000) with hot reload
# - Starts native React/Vite frontend on Fedora host (port 3000) with hot reload
# - Uses systemd-run --user on Fedora (with nohup fallback) for clean process lifecycle
# - Logs are written to logs/backend.log and logs/frontend.log
# - Never exposes credentials or secrets
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOGS_DIR="${REPO_ROOT}/logs"
BACKEND_PID_FILE="${LOGS_DIR}/backend.pid"
FRONTEND_PID_FILE="${LOGS_DIR}/frontend.pid"

mkdir -p "${LOGS_DIR}"

echo "=================================================================="
echo " Starting ResearchLens Native Development Environment"
echo "=================================================================="

# ------------------------------------------------------------------------------
# 1. Verify / Start PostgreSQL container in Podman
# ------------------------------------------------------------------------------
echo -n "[1/3] Checking PostgreSQL container in Podman... "

PG_CONTAINER="research-paper-recommender-postgres-1"

if command -v podman >/dev/null 2>&1; then
    if podman ps --format '{{.Names}}' | grep -q "^${PG_CONTAINER}$"; then
        : # Already running
    elif podman ps -a --format '{{.Names}}' | grep -q "^${PG_CONTAINER}$"; then
        echo -n "starting stopped container ${PG_CONTAINER}... "
        podman start "${PG_CONTAINER}" >/dev/null
    fi
fi

# Wait for PostgreSQL port 5432 to respond
MAX_WAIT_PG=15
PG_READY=false
for i in $(seq 1 "${MAX_WAIT_PG}"); do
    if (echo > /dev/tcp/127.0.0.1/5432) >/dev/null 2>&1; then
        PG_READY=true
        break
    fi
    sleep 1
done

if [ "${PG_READY}" = "true" ]; then
    echo "OK (PostgreSQL listening on 127.0.0.1:5432)"
else
    echo "FAILED"
    echo "Error: PostgreSQL is not reachable on 127.0.0.1:5432."
    echo "Please verify container status: podman ps -a --filter name=${PG_CONTAINER}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 2. Start Native FastAPI Backend
# ------------------------------------------------------------------------------
echo -n "[2/3] Checking Native FastAPI Backend... "

VENV_PYTHON="${REPO_ROOT}/backend/venv/bin/python"
VENV_UVICORN="${REPO_ROOT}/backend/venv/bin/uvicorn"

if [ ! -x "${VENV_PYTHON}" ] || [ ! -x "${VENV_UVICORN}" ]; then
    echo "FAILED"
    echo "Error: Python virtual environment not found at backend/venv."
    echo "Please ensure backend/venv is configured."
    exit 1
fi

# Determine if backend is already running
BACKEND_RUNNING=false
if command -v systemctl >/dev/null 2>&1 && systemctl --user is-active --quiet researchlens-backend 2>/dev/null; then
    BACKEND_RUNNING=true
    BE_PID="$(systemctl --user show --property MainPID --value researchlens-backend 2>/dev/null || echo '')"
    echo "Already running (systemd unit researchlens-backend, PID ${BE_PID:-unknown})"
elif [ -f "${BACKEND_PID_FILE}" ]; then
    OLD_PID="$(cat "${BACKEND_PID_FILE}")"
    if kill -0 "${OLD_PID}" >/dev/null 2>&1; then
        BACKEND_RUNNING=true
        echo "Already running (PID ${OLD_PID})"
    else
        rm -f "${BACKEND_PID_FILE}"
    fi
fi

if [ "${BACKEND_RUNNING}" = "false" ]; then
    # Verify port 8000 is not already bound
    if (echo > /dev/tcp/127.0.0.1/8000) >/dev/null 2>&1; then
        echo "FAILED"
        echo "Error: Port 8000 is already in use by another process."
        echo "Inspect with: ss -tulpn | grep 8000"
        exit 1
    fi

    # Launch backend (prefer systemd-run --user on Fedora for robust lifecycle)
    if command -v systemd-run >/dev/null 2>&1 && systemctl --user is-active --quiet default.target 2>/dev/null; then
        systemd-run --user --unit=researchlens-backend /bin/bash -c \
            "cd '${REPO_ROOT}/backend' && exec '${VENV_UVICORN}' app.main:app --host 0.0.0.0 --port 8000 --reload > '${LOGS_DIR}/backend.log' 2>&1" >/dev/null 2>&1
        sleep 1
        BE_PID="$(systemctl --user show --property MainPID --value researchlens-backend 2>/dev/null || echo '')"
        [ -n "${BE_PID}" ] && echo "${BE_PID}" > "${BACKEND_PID_FILE}"
    else
        cd "${REPO_ROOT}/backend"
        nohup "${VENV_UVICORN}" app.main:app --host 0.0.0.0 --port 8000 --reload > "${LOGS_DIR}/backend.log" 2>&1 &
        BE_PID=$!
        echo "${BE_PID}" > "${BACKEND_PID_FILE}"
    fi

    # Wait up to 15s for backend health
    MAX_WAIT_BE=15
    BE_READY=false
    for i in $(seq 1 "${MAX_WAIT_BE}"); do
        if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
            BE_READY=true
            break
        fi
        sleep 1
    done

    if [ "${BE_READY}" = "true" ]; then
        echo "Started (PID ${BE_PID:-unknown}, http://localhost:8000)"
    else
        echo "WARNING: Backend process launched but health endpoint not yet responding."
        echo "Check logs: tail -n 20 ${LOGS_DIR}/backend.log"
    fi
fi

# ------------------------------------------------------------------------------
# 3. Start Native React/Vite Frontend
# ------------------------------------------------------------------------------
echo -n "[3/3] Checking Native React/Vite Frontend... "

if [ ! -d "${REPO_ROOT}/frontend/node_modules" ]; then
    echo "FAILED"
    echo "Error: frontend/node_modules not found. Run 'npm install' inside frontend/."
    exit 1
fi

FRONTEND_RUNNING=false
if command -v systemctl >/dev/null 2>&1 && systemctl --user is-active --quiet researchlens-frontend 2>/dev/null; then
    FRONTEND_RUNNING=true
    FE_PID="$(systemctl --user show --property MainPID --value researchlens-frontend 2>/dev/null || echo '')"
    echo "Already running (systemd unit researchlens-frontend, PID ${FE_PID:-unknown})"
elif [ -f "${FRONTEND_PID_FILE}" ]; then
    OLD_PID="$(cat "${FRONTEND_PID_FILE}")"
    if kill -0 "${OLD_PID}" >/dev/null 2>&1; then
        FRONTEND_RUNNING=true
        echo "Already running (PID ${OLD_PID})"
    else
        rm -f "${FRONTEND_PID_FILE}"
    fi
fi

if [ "${FRONTEND_RUNNING}" = "false" ]; then
    # Verify port 3000 is not already bound
    if (echo > /dev/tcp/127.0.0.1/3000) >/dev/null 2>&1; then
        echo "FAILED"
        echo "Error: Port 3000 is already in use by another process."
        echo "Inspect with: ss -tulpn | grep 3000"
        exit 1
    fi

    # Launch frontend (prefer systemd-run --user on Fedora)
    if command -v systemd-run >/dev/null 2>&1 && systemctl --user is-active --quiet default.target 2>/dev/null; then
        systemd-run --user --unit=researchlens-frontend /bin/bash -c \
            "cd '${REPO_ROOT}/frontend' && exec npm run dev -- --host 0.0.0.0 --port 3000 > '${LOGS_DIR}/frontend.log' 2>&1" >/dev/null 2>&1
        sleep 1
        FE_PID="$(systemctl --user show --property MainPID --value researchlens-frontend 2>/dev/null || echo '')"
        [ -n "${FE_PID}" ] && echo "${FE_PID}" > "${FRONTEND_PID_FILE}"
    else
        cd "${REPO_ROOT}/frontend"
        nohup npm run dev -- --host 0.0.0.0 --port 3000 > "${LOGS_DIR}/frontend.log" 2>&1 &
        FE_PID=$!
        echo "${FE_PID}" > "${FRONTEND_PID_FILE}"
    fi

    # Wait up to 10s for frontend response
    MAX_WAIT_FE=10
    FE_READY=false
    for i in $(seq 1 "${MAX_WAIT_FE}"); do
        if curl -sf http://127.0.0.1:3000 >/dev/null 2>&1; then
            FE_READY=true
            break
        fi
        sleep 1
    done

    if [ "${FE_READY}" = "true" ]; then
        echo "Started (PID ${FE_PID:-unknown}, http://localhost:3000)"
    else
        echo "WARNING: Frontend process launched but dev server not yet responding."
        echo "Check logs: tail -n 20 ${LOGS_DIR}/frontend.log"
    fi
fi

echo "=================================================================="
echo " Native Development Environment Ready!"
echo "   - PostgreSQL: Podman container '${PG_CONTAINER}' on port 5432"
echo "   - FastAPI:    http://localhost:8000 (Docs: http://localhost:8000/docs)"
echo "   - Frontend:   http://localhost:3000"
echo "   - Logs:       ${LOGS_DIR}/backend.log, ${LOGS_DIR}/frontend.log"
echo "   - Status:     ./scripts/dev-status.sh"
echo "   - Stop:       ./scripts/dev-stop.sh"
echo "=================================================================="
