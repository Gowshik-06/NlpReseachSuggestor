#!/usr/bin/env bash
# ==============================================================================
# scripts/dev-stop.sh — Stop native development processes
# ==============================================================================
# - Stops native FastAPI backend and native Vite frontend
# - Handles systemd-run user units and PID-tracked processes
# - DOES NOT stop or touch containerized PostgreSQL
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOGS_DIR="${REPO_ROOT}/logs"
BACKEND_PID_FILE="${LOGS_DIR}/backend.pid"
FRONTEND_PID_FILE="${LOGS_DIR}/frontend.pid"

echo "=================================================================="
echo " Stopping ResearchLens Native Development Processes"
echo "=================================================================="

# Stop systemd units if active
if command -v systemctl >/dev/null 2>&1; then
    if systemctl --user is-active --quiet researchlens-backend 2>/dev/null; then
        echo -n "Stopping systemd unit researchlens-backend... "
        systemctl --user stop researchlens-backend 2>/dev/null || true
        echo "stopped"
    fi
    if systemctl --user is-active --quiet researchlens-frontend 2>/dev/null; then
        echo -n "Stopping systemd unit researchlens-frontend... "
        systemctl --user stop researchlens-frontend 2>/dev/null || true
        echo "stopped"
    fi
fi

# Function to safely terminate a tracked PID
stop_pid() {
    local name="$1"
    local pid_file="$2"

    if [ -f "${pid_file}" ]; then
        local pid
        pid="$(cat "${pid_file}")"
        if kill -0 "${pid}" >/dev/null 2>&1; then
            echo -n "Stopping ${name} (PID ${pid})... "
            kill -15 "${pid}" 2>/dev/null || true
            local waited=0
            while kill -0 "${pid}" >/dev/null 2>&1 && [ "${waited}" -lt 5 ]; do
                sleep 1
                waited=$((waited + 1))
            done
            if kill -0 "${pid}" >/dev/null 2>&1; then
                kill -9 "${pid}" 2>/dev/null || true
            fi
            echo "stopped"
        else
            echo "${name} (PID ${pid}) was already stopped"
        fi
        rm -f "${pid_file}"
    fi
}

stop_pid "Native FastAPI Backend" "${BACKEND_PID_FILE}"
stop_pid "Native React/Vite Frontend" "${FRONTEND_PID_FILE}"

echo "------------------------------------------------------------------"
echo "Preserved: PostgreSQL container ('research-paper-recommender-postgres-1')"
echo "remains running in Podman with its persistent data."
echo "=================================================================="
