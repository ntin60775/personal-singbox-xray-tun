#!/usr/bin/env bash
set -euo pipefail

INTERNAL_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${INTERNAL_DIR}/../lib/subvost-common.sh"
subvost_load_project_layout_from_env

HOST="${SUBVOST_GUI_HOST:-127.0.0.1}"
PORT="${SUBVOST_GUI_PORT:-8421}"
REAL_USER="${SUBVOST_REAL_USER:-}"
REAL_HOME="${SUBVOST_REAL_HOME:-}"
REAL_UID="${PKEXEC_UID:-}"
FORCE_RESTART="${SUBVOST_GUI_RESTART:-0}"
PID_FILE="/tmp/subvost-xray-tun-gui-${REAL_UID:-root}.pid"
LOG_FILE="/tmp/subvost-xray-tun-gui-${REAL_UID:-root}.log"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Этот скрипт должен запускаться через pkexec/root." >&2
  exit 1
fi

if [[ -z "${REAL_USER}" || -z "${REAL_HOME}" ]]; then
  echo "Не переданы SUBVOST_REAL_USER/SUBVOST_REAL_HOME." >&2
  exit 1
fi

subvost_ensure_absolute_path "$REAL_HOME" "SUBVOST_REAL_HOME"

stop_existing_backend() {
  local old_pid=""

  if [[ -f "${PID_FILE}" ]]; then
    old_pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
    if [[ "${old_pid}" =~ ^[0-9]+$ ]] && kill -0 "${old_pid}" 2>/dev/null; then
      kill "${old_pid}" 2>/dev/null || true
      sleep 1
      kill -9 "${old_pid}" 2>/dev/null || true
    fi
    rm -f "${PID_FILE}"
  fi

  pkill -f "${SUBVOST_GUI_DIR}/gui_server.py --host ${HOST} --port ${PORT}" 2>/dev/null || true
}

if [[ "${FORCE_RESTART}" == "1" ]]; then
  stop_existing_backend
fi

if [[ -f "${PID_FILE}" ]]; then
  OLD_PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ "${OLD_PID}" =~ ^[0-9]+$ ]] && kill -0 "${OLD_PID}" 2>/dev/null; then
    exit 0
  fi
  rm -f "${PID_FILE}"
fi

cd "${SUBVOST_PROJECT_ROOT}"

nohup env \
  SUBVOST_PROJECT_ROOT="${SUBVOST_PROJECT_ROOT}" \
  SUBVOST_REAL_USER="${REAL_USER}" \
  SUBVOST_REAL_HOME="${REAL_HOME}" \
  PKEXEC_UID="${REAL_UID}" \
  PYTHONUNBUFFERED=1 \
  python3 "${SUBVOST_GUI_DIR}/gui_server.py" --host "${HOST}" --port "${PORT}" \
  >"${LOG_FILE}" 2>&1 &

GUI_PID=$!
echo "${GUI_PID}" >"${PID_FILE}"

sleep 1

if ! kill -0 "${GUI_PID}" 2>/dev/null; then
  echo "Не удалось запустить GUI backend." >&2
  tail -n 80 "${LOG_FILE}" 2>/dev/null || true
  exit 1
fi

exit 0
