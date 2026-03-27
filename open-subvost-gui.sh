#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HOST="${SUBVOST_GUI_HOST:-127.0.0.1}"
PORT="${SUBVOST_GUI_PORT:-8421}"
URL="http://${HOST}:${PORT}"
CURRENT_GUI_VERSION="2026-03-27-compact-v2"

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

server_version_matches() {
  python3 - "$URL" "$CURRENT_GUI_VERSION" <<'PY'
import json
import sys
import urllib.request

base_url = sys.argv[1]
expected = sys.argv[2]

try:
    with urllib.request.urlopen(f"{base_url}/api/status", timeout=0.8) as response:
        payload = json.load(response)
except Exception:
    sys.exit(1)

sys.exit(0 if payload.get("gui_version") == expected else 1)
PY
}

open_browser() {
  xdg-open "${URL}" >/dev/null 2>&1 &
}

if ! is_server_ready || ! server_version_matches; then
  pkexec env \
    SUBVOST_REAL_USER="${USER}" \
    SUBVOST_REAL_HOME="${HOME}" \
    SUBVOST_GUI_HOST="${HOST}" \
    SUBVOST_GUI_PORT="${PORT}" \
    SUBVOST_GUI_RESTART=1 \
    /usr/bin/env bash "${SCRIPT_DIR}/start-gui-backend-root.sh"
fi

if ! wait_for_server; then
  echo "GUI backend не ответил на ${URL}" >&2
  exit 1
fi

open_browser
exit 0
