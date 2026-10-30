#!/usr/bin/env bash
# ==============================================================================
# stop-researchlens.sh — Stop ResearchLens Services
# ==============================================================================
# Cleanly terminates backend and frontend processes owned by ResearchLens:
#   - Stops systemd user units (researchlens-backend, researchlens-frontend)
#   - Gracefully stops PID-tracked processes with ownership verification
#   - NEVER kills processes based solely on port numbers
#   - Preserves containerized PostgreSQL container and all persistent data
# ==============================================================================
set -euo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)"
LOGS_DIR="${REPO_ROOT}/logs"
BACKEND_PID_FILE="${LOGS_DIR}/backend.pid"
FRONTEND_PID_FILE="${LOGS_DIR}/frontend.pid"

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    BOLD='\033[1m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    RED='\033[0;31m'
    RESET='\033[0m'
else
    BOLD=''
    GREEN=''
    YELLOW=''
    CYAN=''
    RED=''
    RESET=''
fi

for arg in "$@"; do
    case "${arg}" in
        --help|-h)
            cat << 'EOF'
Usage: ./stop-researchlens.sh [OPTIONS]

Stops all running ResearchLens backend and frontend processes cleanly,
using tracked PIDs and systemd user services. Preserves PostgreSQL container intact.

Options:
  --help, -h      Display this help message and exit.
EOF
            exit 0
            ;;
        *)
            echo -e "${YELLOW}Warning: Unknown argument '${arg}' ignored.${RESET}"
            ;;
    esac
done

echo "=================================================================="
echo -e " ${BOLD}Stopping ResearchLens Services${RESET}"
echo "=================================================================="

# ------------------------------------------------------------------------------
# 1. Stop systemd user units if active
# ------------------------------------------------------------------------------
if command -v systemctl >/dev/null 2>&1; then
    if systemctl --user is-active --quiet researchlens-backend 2>/dev/null; then
        echo -n "  - Stopping systemd unit 'researchlens-backend'... "
        systemctl --user stop researchlens-backend 2>/dev/null || true
        echo -e "${GREEN}stopped${RESET}"
    fi
    if systemctl --user is-active --quiet researchlens-frontend 2>/dev/null; then
        echo -n "  - Stopping systemd unit 'researchlens-frontend'... "
        systemctl --user stop researchlens-frontend 2>/dev/null || true
        echo -e "${GREEN}stopped${RESET}"
    fi
fi

# ------------------------------------------------------------------------------
# 2. Stop PID-tracked processes with strict ownership verification
# ------------------------------------------------------------------------------
stop_verified_pid() {
    local service_name="$1"
    local pid_file="$2"
    local expected_pattern="$3"

    if [ ! -f "${pid_file}" ]; then
        echo "  - ${service_name}: No active PID file found."
        return 0
    fi

    local pid
    pid="$(cat "${pid_file}" 2>/dev/null | tr -d '[:space:]')"

    if [ -z "${pid}" ]; then
        rm -f "${pid_file}"
        return 0
    fi

    if ! kill -0 "${pid}" 2>/dev/null; then
        echo "  - ${service_name} (PID ${pid}): Already stopped."
        rm -f "${pid_file}"
        return 0
    fi

    # Inspect process command line to ensure it is actually our service
    local cmdline=""
    if [ -f "/proc/${pid}/cmdline" ]; then
        cmdline="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
    else
        cmdline="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
    fi

    if ! echo "${cmdline}" | grep -qE "${expected_pattern}"; then
        echo -e "  - ${YELLOW}WARNING: PID ${pid} is running but does not match expected pattern '${expected_pattern}'!${RESET}"
        echo "    Process args: ${cmdline}"
        echo "    Skipping termination to protect unrelated system processes."
        rm -f "${pid_file}"
        return 1
    fi

    echo -n "  - Stopping ${service_name} (PID ${pid})... "
    kill -15 "${pid}" 2>/dev/null || true

    local waited=0
    while kill -0 "${pid}" 2>/dev/null && [ "${waited}" -lt 5 ]; do
        sleep 1
        waited=$((waited + 1))
    done

    if kill -0 "${pid}" 2>/dev/null; then
        echo -n "(forcing termination)... "
        kill -9 "${pid}" 2>/dev/null || true
    fi

    rm -f "${pid_file}"
    echo -e "${GREEN}stopped${RESET}"
}

stop_verified_pid "FastAPI Backend" "${BACKEND_PID_FILE}" "uvicorn|app\.main|backend/venv"
stop_verified_pid "React/Vite Frontend" "${FRONTEND_PID_FILE}" "vite|npm|node"

echo "------------------------------------------------------------------"
echo -e "${CYAN}Preserved:${RESET} PostgreSQL container ('research-paper-recommender-postgres-1')"
echo "remains running in Podman with all persistent data and FAISS indices untouched."
echo "=================================================================="
echo -e " ${GREEN}✔ All ResearchLens application processes stopped.${RESET}"
echo "=================================================================="
