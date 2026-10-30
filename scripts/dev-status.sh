#!/usr/bin/env bash
# ==============================================================================
# scripts/dev-status.sh — Report native development status
# ==============================================================================
# - Checks containerized PostgreSQL in Podman and port 5432 connectivity
# - Checks native FastAPI process, liveness, and database connection status
# - Checks native React/Vite process and web response
# - Never exposes credentials or secrets
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOGS_DIR="${REPO_ROOT}/logs"
BACKEND_PID_FILE="${LOGS_DIR}/backend.pid"
FRONTEND_PID_FILE="${LOGS_DIR}/frontend.pid"

OVERALL_STATUS=0

echo "=================================================================="
echo " ResearchLens Development Environment Status"
echo "=================================================================="

# ------------------------------------------------------------------------------
# 1. PostgreSQL Container (Podman)
# ------------------------------------------------------------------------------
PG_CONTAINER="research-paper-recommender-postgres-1"
echo "[1] Database (PostgreSQL - Podman Container)"
if command -v podman >/dev/null 2>&1; then
    CONTAINER_STATE="$(podman inspect "${PG_CONTAINER}" --format '{{.State.Status}} (health: {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}})' 2>/dev/null || echo 'NOT FOUND')"
    echo "    Container:      ${PG_CONTAINER}"
    echo "    State:          ${CONTAINER_STATE}"
fi

if (echo > /dev/tcp/127.0.0.1/5432) >/dev/null 2>&1; then
    echo "    Port 5432:      CONNECTED (127.0.0.1:5432 reachable)"
else
    echo "    Port 5432:      DOWN (not responding)"
    OVERALL_STATUS=1
fi

# ------------------------------------------------------------------------------
# 2. FastAPI Backend (Native Fedora)
# ------------------------------------------------------------------------------
echo ""
echo "[2] Backend (FastAPI - Native Fedora)"
BE_ACTIVE=false
if command -v systemctl >/dev/null 2>&1 && systemctl --user is-active --quiet researchlens-backend 2>/dev/null; then
    BE_PID="$(systemctl --user show --property MainPID --value researchlens-backend 2>/dev/null || echo '')"
    echo "    Process:        RUNNING (systemd unit: researchlens-backend, PID ${BE_PID:-unknown})"
    BE_ACTIVE=true
elif [ -f "${BACKEND_PID_FILE}" ]; then
    BE_PID="$(cat "${BACKEND_PID_FILE}")"
    if kill -0 "${BE_PID}" >/dev/null 2>&1; then
        echo "    Process:        RUNNING (PID ${BE_PID})"
        BE_ACTIVE=true
    else
        echo "    Process:        STOPPED (stale PID ${BE_PID})"
        OVERALL_STATUS=1
    fi
else
    echo "    Process:        NOT RUNNING"
    OVERALL_STATUS=1
fi

BE_HEALTH="$(curl -sf http://127.0.0.1:8000/api/v1/health 2>/dev/null || echo 'DOWN')"
if [ "${BE_HEALTH}" != "DOWN" ]; then
    DB_STATUS="$(echo "${BE_HEALTH}" | grep -o '"database":"[^"]*"' | cut -d':' -f2 | tr -d '"' || echo 'unknown')"
    echo "    API Health:     OK (http://localhost:8000/api/v1/health)"
    echo "    Database Link:  ${DB_STATUS}"
else
    echo "    API Health:     DOWN (http://localhost:8000 not responding)"
    OVERALL_STATUS=1
fi

# ------------------------------------------------------------------------------
# 3. React/Vite Frontend (Native Fedora)
# ------------------------------------------------------------------------------
echo ""
echo "[3] Frontend (React/Vite - Native Fedora)"
if command -v systemctl >/dev/null 2>&1 && systemctl --user is-active --quiet researchlens-frontend 2>/dev/null; then
    FE_PID="$(systemctl --user show --property MainPID --value researchlens-frontend 2>/dev/null || echo '')"
    echo "    Process:        RUNNING (systemd unit: researchlens-frontend, PID ${FE_PID:-unknown})"
elif [ -f "${FRONTEND_PID_FILE}" ]; then
    FE_PID="$(cat "${FRONTEND_PID_FILE}")"
    if kill -0 "${FE_PID}" >/dev/null 2>&1; then
        echo "    Process:        RUNNING (PID ${FE_PID})"
    else
        echo "    Process:        STOPPED (stale PID ${FE_PID})"
        OVERALL_STATUS=1
    fi
else
    echo "    Process:        NOT RUNNING"
    OVERALL_STATUS=1
fi

if curl -sf http://127.0.0.1:3000 >/dev/null 2>&1; then
    echo "    Dev Server:     OK (http://localhost:3000 reachable)"
else
    echo "    Dev Server:     DOWN (http://localhost:3000 not responding)"
    OVERALL_STATUS=1
fi

echo "=================================================================="
if [ ${OVERALL_STATUS} -eq 0 ]; then
    echo " Status: ALL SERVICES OPERATIONAL (Native Dev + Containerized DB)"
else
    echo " Status: ONE OR MORE SERVICES DEGRADED OR STOPPED"
fi
echo "=================================================================="

exit ${OVERALL_STATUS}
