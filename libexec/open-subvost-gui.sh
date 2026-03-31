#!/usr/bin/env bash
set -euo pipefail

INTERNAL_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${INTERNAL_DIR}/../lib/subvost-common.sh"
subvost_load_project_layout_from_env

HOST="${SUBVOST_GUI_HOST:-127.0.0.1}"
PORT="${SUBVOST_GUI_PORT:-8421}"
URL="http://${HOST}:${PORT}"
CURRENT_GUI_VERSION="2026-03-31-wave1-v1"
REAL_USER="${USER:-$(id -un)}"
REAL_HOME="${HOME:-$(getent passwd "$REAL_USER" | cut -d: -f6)}"
REAL_XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${REAL_HOME}/.config}"
FORCE_RESTART=0

if [[ -z "$REAL_HOME" ]]; then
  echo "Не удалось определить домашний каталог пользователя ${REAL_USER}" >&2
  exit 1
fi

if [[ "$REAL_XDG_CONFIG_HOME" != /* ]]; then
  echo "XDG_CONFIG_HOME должен быть абсолютным путём: ${REAL_XDG_CONFIG_HOME}" >&2
  exit 1
fi

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --force-restart-backend)
        FORCE_RESTART=1
        ;;
      --help)
        cat <<'EOF'
Использование: open-subvost-gui.sh [--force-restart-backend]

  --force-restart-backend  принудительно перезапустить GUI backend перед открытием браузера
EOF
        exit 0
        ;;
      *)
        echo "Неизвестный аргумент: $1" >&2
        exit 1
        ;;
    esac
    shift
  done
}

is_server_ready() {
  python3 - "$HOST" "$PORT" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

try:
    with socket.create_connection((host, port), timeout=0.6):
        sys.exit(0)
except OSError:
    sys.exit(1)
PY
}

wait_for_server() {
  local attempt
  for attempt in {1..40}; do
    if is_server_ready; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

server_contract_matches() {
  python3 - "$URL" "$CURRENT_GUI_VERSION" "$SUBVOST_PROJECT_ROOT" <<'PY'
import json
import sys
import urllib.request

base_url = sys.argv[1]
expected_version = sys.argv[2]
expected_root = sys.argv[3]

try:
    with urllib.request.urlopen(f"{base_url}/api/status", timeout=0.8) as response:
        payload = json.load(response)
except Exception:
    sys.exit(1)

same_version = payload.get("gui_version") == expected_version
same_root = payload.get("project_root") == expected_root

if not same_root and isinstance(payload.get("bundle_identity"), dict):
    same_root = payload["bundle_identity"].get("project_root") == expected_root

sys.exit(0 if same_version and same_root else 1)
PY
}

open_browser() {
  xdg-open "${URL}" >/dev/null 2>&1 &
}

start_backend() {
  pkexec env \
    SUBVOST_PROJECT_ROOT="${SUBVOST_PROJECT_ROOT}" \
    SUBVOST_REAL_USER="${REAL_USER}" \
    SUBVOST_REAL_HOME="${REAL_HOME}" \
    SUBVOST_REAL_XDG_CONFIG_HOME="${REAL_XDG_CONFIG_HOME}" \
    SUBVOST_GUI_HOST="${HOST}" \
    SUBVOST_GUI_PORT="${PORT}" \
    SUBVOST_GUI_RESTART=1 \
    /usr/bin/env bash "${SUBVOST_LIBEXEC_DIR}/start-gui-backend-root.sh"
}

parse_args "$@"

if [[ "${FORCE_RESTART}" == "1" ]] || ! is_server_ready || ! server_contract_matches; then
  start_backend
fi

if ! wait_for_server; then
  echo "GUI backend не ответил на ${URL}" >&2
  exit 1
fi

open_browser
exit 0
