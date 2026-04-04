#!/usr/bin/env bash
set -euo pipefail

INTERNAL_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${INTERNAL_DIR}/../lib/subvost-common.sh"
subvost_load_project_layout_from_env

HOST="${SUBVOST_GUI_HOST:-127.0.0.1}"
PORT="${SUBVOST_GUI_PORT:-8421}"
URL="http://${HOST}:${PORT}"
REAL_USER="${USER:-$(id -un)}"
REAL_HOME="${HOME:-$(getent passwd "$REAL_USER" | cut -d: -f6)}"
REAL_XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${REAL_HOME}/.config}"
REAL_UID="$(id -u "$REAL_USER" 2>/dev/null || id -u)"
LAUNCH_MODE="${SUBVOST_GUI_LAUNCH_MODE:-auto}"
WEBVIEW_LOG_FILE="/tmp/subvost-xray-tun-webview-${REAL_UID}.log"
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

Переменные окружения:
  SUBVOST_GUI_LAUNCH_MODE=auto|webview|browser
    auto    сначала встроенное GTK/WebKitGTK окно, затем fallback на браузер
    webview требовать встроенное окно и завершаться ошибкой без fallback
    browser всегда открывать системный браузер
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

load_current_gui_version() {
  python3 - "$SUBVOST_GUI_DIR" <<'PY'
import sys

sys.path.insert(0, sys.argv[1])
from gui_contract import GUI_VERSION

print(GUI_VERSION)
PY
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
  command -v xdg-open >/dev/null 2>&1 || {
    echo "Не найдена команда xdg-open для запуска системного браузера." >&2
    return 1
  }

  nohup xdg-open "${URL}" >/dev/null 2>&1 &
}

embedded_webview_available() {
  python3 "${SUBVOST_GUI_DIR}/embedded_webview.py" --check >/dev/null 2>&1
}

open_embedded_webview() {
  embedded_webview_available || return 1

  nohup python3 "${SUBVOST_GUI_DIR}/embedded_webview.py" \
    --url "${URL}" \
    --title "Subvost Xray TUN" \
    --icon-path "${SUBVOST_ASSETS_DIR}/subvost-xray-tun-icon.svg" \
    >"${WEBVIEW_LOG_FILE}" 2>&1 &

  local gui_pid="$!"
  sleep 0.4

  if kill -0 "${gui_pid}" 2>/dev/null; then
    return 0
  fi

  if wait "${gui_pid}"; then
    return 0
  fi

  tail -n 80 "${WEBVIEW_LOG_FILE}" >&2 2>/dev/null || true
  return 1
}

open_gui_frontend() {
  case "${LAUNCH_MODE}" in
    auto)
      open_embedded_webview || open_browser
      ;;
    webview)
      open_embedded_webview || {
        echo "Встроенный GTK/WebKitGTK launcher недоступен." >&2
        return 1
      }
      ;;
    browser)
      open_browser
      ;;
    *)
      echo "Неподдерживаемый SUBVOST_GUI_LAUNCH_MODE: ${LAUNCH_MODE}" >&2
      return 1
      ;;
  esac
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
CURRENT_GUI_VERSION="$(load_current_gui_version)"

if [[ -z "${CURRENT_GUI_VERSION}" ]]; then
  echo "Не удалось определить ожидаемую версию GUI-контракта." >&2
  exit 1
fi

if [[ "${FORCE_RESTART}" == "1" ]] || ! is_server_ready || ! server_contract_matches; then
  start_backend
fi

if ! wait_for_server; then
  echo "GUI backend не ответил на ${URL}" >&2
  exit 1
fi

open_gui_frontend
exit 0
