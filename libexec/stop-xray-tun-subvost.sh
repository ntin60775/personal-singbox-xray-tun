#!/usr/bin/env bash
set -euo pipefail

INTERNAL_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${INTERNAL_DIR}/../lib/subvost-common.sh"
subvost_load_project_layout_from_env

REAL_USER="${SUDO_USER:-${USER:-$(id -un)}}"
REAL_HOME="$(
  getent passwd "$REAL_USER" | cut -d: -f6
)"

if [[ -z "$REAL_HOME" ]]; then
  echo "Не удалось определить домашний каталог пользователя ${REAL_USER}" >&2
  exit 1
fi

XRAY_CONFIG="${XRAY_CONFIG:-${SUBVOST_XRAY_CONFIG_PATH}}"
SINGBOX_CONFIG="${SINGBOX_CONFIG:-${SUBVOST_SINGBOX_CONFIG_PATH}}"
STATE_FILE="${STATE_FILE:-${REAL_HOME}/.xray-tun-subvost.state}"
RESOLV_BACKUP="${RESOLV_BACKUP:-${REAL_HOME}/.xray-tun-subvost.resolv.conf.backup}"
ARG_XRAY_PID="${1:-}"
ARG_SINGBOX_PID="${2:-}"
XRAY_PID=""
SINGBOX_PID=""

ensure_absolute_path() {
  local path_value="$1"
  local label="$2"
  if [[ "$path_value" != /* ]]; then
    echo "${label} должен быть абсолютным путём: ${path_value}" >&2
    exit 1
  fi
}

ensure_absolute_path "$STATE_FILE" "STATE_FILE"
ensure_absolute_path "$RESOLV_BACKUP" "RESOLV_BACKUP"

if [[ -f "$STATE_FILE" ]]; then
  while IFS='=' read -r key value; do
    case "$key" in
      XRAY_PID)
        if [[ "$value" =~ ^[0-9]+$ ]]; then
          XRAY_PID="$value"
        fi
        ;;
      SINGBOX_PID)
        if [[ "$value" =~ ^[0-9]+$ ]]; then
          SINGBOX_PID="$value"
        fi
        ;;
      RESOLV_BACKUP)
        if [[ "$value" == /* ]]; then
          RESOLV_BACKUP="$value"
        fi
        ;;
    esac
  done <"$STATE_FILE"
fi

if [[ -n "$ARG_XRAY_PID" ]]; then
  XRAY_PID="$ARG_XRAY_PID"
fi

if [[ -n "$ARG_SINGBOX_PID" ]]; then
  SINGBOX_PID="$ARG_SINGBOX_PID"
fi

echo "[1/3] Остановка sing-box TUN"
if [[ -n "${SINGBOX_PID:-}" ]]; then
  sudo kill "$SINGBOX_PID" 2>/dev/null || true
else
  sudo pkill -f "sing-box run -c ${SINGBOX_CONFIG}" 2>/dev/null || true
fi

echo "[2/3] Остановка Xray core"
if [[ -n "${XRAY_PID:-}" ]]; then
  sudo kill "$XRAY_PID" 2>/dev/null || true
else
  sudo pkill -f "xray run -c ${XRAY_CONFIG}" 2>/dev/null || true
fi

echo "[3/3] Восстановление системного DNS"
if [[ -f "$RESOLV_BACKUP" ]]; then
  sudo cp -f "$RESOLV_BACKUP" /etc/resolv.conf
fi

rm -f "$STATE_FILE"
