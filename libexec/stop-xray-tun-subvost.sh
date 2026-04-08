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

ACTIVE_XRAY_CONFIG_DEFAULT="$(subvost_resolve_active_xray_config_for_home "$REAL_HOME")"
XRAY_CONFIG="${XRAY_CONFIG:-${ACTIVE_XRAY_CONFIG_DEFAULT}}"
STATE_FILE="${STATE_FILE:-${REAL_HOME}/.xray-tun-subvost.state}"
RESOLV_BACKUP="${RESOLV_BACKUP:-${REAL_HOME}/.xray-tun-subvost.resolv.conf.backup}"
ARG_XRAY_PID="${1:-}"
XRAY_PID=""
STATE_BUNDLE_PROJECT_ROOT=""
RUNTIME_IMPL="${RUNTIME_IMPL:-xray}"
TUN_INTERFACE="${TUN_INTERFACE:-tun0}"
ROUTE_TABLE="${ROUTE_TABLE:-18421}"
ROUTE_MARK="${ROUTE_MARK:-8421}"
ROUTE_RULE_PREF="${ROUTE_RULE_PREF:-100}"

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

read_state_bundle_project_root() {
  local state_file="$1"
  local key value

  [[ -f "$state_file" ]] || return 0

  while IFS='=' read -r key value; do
    case "$key" in
      BUNDLE_PROJECT_ROOT)
        if [[ "$value" == /* ]]; then
          printf '%s\n' "$value"
          return 0
        fi
        ;;
    esac
  done <"$state_file"
}

read_state_value() {
  local state_file="$1"
  local target_key="$2"
  local key value

  [[ -f "$state_file" ]] || return 0

  while IFS='=' read -r key value; do
    if [[ "$key" == "$target_key" ]]; then
      printf '%s\n' "$value"
      return 0
    fi
  done <"$state_file"
}

legacy_state_runtime_is_live() {
  local state_file="$1"
  local state_pid=""
  local state_tun_interface=""

  state_pid="$(read_state_value "$state_file" "XRAY_PID")"
  state_tun_interface="$(read_state_value "$state_file" "TUN_INTERFACE")"

  if [[ ! "$state_pid" =~ ^[0-9]+$ ]]; then
    state_pid=""
  fi

  if [[ -z "$state_tun_interface" ]]; then
    state_tun_interface="$TUN_INTERFACE"
  fi

  if [[ -n "$state_pid" ]] && kill -0 "$state_pid" 2>/dev/null; then
    return 0
  fi

  if [[ -n "$state_tun_interface" ]] && ip link show "$state_tun_interface" >/dev/null 2>&1; then
    return 0
  fi

  return 1
}

if [[ -f "$STATE_FILE" ]]; then
  STATE_BUNDLE_PROJECT_ROOT="$(read_state_bundle_project_root "$STATE_FILE")"
  while IFS='=' read -r key value; do
    case "$key" in
      XRAY_PID)
        if [[ "$value" =~ ^[0-9]+$ ]]; then
          XRAY_PID="$value"
        fi
        ;;
      RESOLV_BACKUP)
        if [[ "$value" == /* ]]; then
          RESOLV_BACKUP="$value"
        fi
        ;;
      XRAY_CONFIG)
        if [[ "$value" == /* ]]; then
          XRAY_CONFIG="$value"
        fi
        ;;
      BUNDLE_PROJECT_ROOT)
        if [[ "$value" == /* ]]; then
          STATE_BUNDLE_PROJECT_ROOT="$value"
        fi
        ;;
      RUNTIME_IMPL)
        if [[ -n "$value" ]]; then
          RUNTIME_IMPL="$value"
        fi
        ;;
      TUN_INTERFACE)
        if [[ -n "$value" ]]; then
          TUN_INTERFACE="$value"
        fi
        ;;
      ROUTE_TABLE)
        if [[ "$value" =~ ^[0-9]+$ ]]; then
          ROUTE_TABLE="$value"
        fi
        ;;
      ROUTE_MARK)
        if [[ "$value" =~ ^[0-9]+$ ]]; then
          ROUTE_MARK="$value"
        fi
        ;;
      ROUTE_RULE_PREF)
        if [[ "$value" =~ ^[0-9]+$ ]]; then
          ROUTE_RULE_PREF="$value"
        fi
        ;;
    esac
  done <"$STATE_FILE"
fi

if [[ -n "$ARG_XRAY_PID" ]]; then
  XRAY_PID="$ARG_XRAY_PID"
fi

if [[ ! -f "$STATE_FILE" ]]; then
  if [[ -z "$ARG_XRAY_PID" ]]; then
    echo "Файл состояния не найден: ${STATE_FILE}" >&2
    echo "Для безопасности без state-файла или явного PID текущий bundle не будет выполнять stop." >&2
    exit 1
  fi
elif [[ -z "$STATE_BUNDLE_PROJECT_ROOT" ]]; then
  if legacy_state_runtime_is_live "$STATE_FILE"; then
    echo "Файл состояния не содержит bundle identity: ${STATE_FILE}" >&2
    echo "Для безопасности текущий bundle не будет останавливать неподтверждённый runtime." >&2
    exit 1
  fi

  echo "Файл состояния не содержит bundle identity: ${STATE_FILE}" >&2
  echo "Runtime по этому state уже не активен. Удаляется только stale state-файл." >&2
  rm -f "$STATE_FILE"
  exit 0
elif [[ "$STATE_BUNDLE_PROJECT_ROOT" != "$SUBVOST_PROJECT_ROOT" ]]; then
  echo "Файл состояния принадлежит другому bundle: ${STATE_FILE}" >&2
  echo "Bundle-владелец runtime: ${STATE_BUNDLE_PROJECT_ROOT}" >&2
  echo "Текущий bundle: ${SUBVOST_PROJECT_ROOT}" >&2
  exit 1
fi

echo "[1/4] Остановка Xray core"
if [[ -n "${XRAY_PID:-}" ]]; then
  sudo kill "$XRAY_PID" 2>/dev/null || true
else
  sudo pkill -f "xray run -c ${XRAY_CONFIG}" 2>/dev/null || true
fi

echo "[2/4] Очистка policy-routing"
sudo ip rule del pref "$ROUTE_RULE_PREF" not fwmark "$ROUTE_MARK" table "$ROUTE_TABLE" >/dev/null 2>&1 || true
sudo ip route flush table "$ROUTE_TABLE" >/dev/null 2>&1 || true
sudo ip route flush cache >/dev/null 2>&1 || true

echo "[3/4] Очистка TUN-интерфейса"
if [[ -n "$TUN_INTERFACE" ]]; then
  sudo ip link delete "$TUN_INTERFACE" >/dev/null 2>&1 || true
fi

echo "[4/4] Восстановление системного DNS"
if [[ -f "$RESOLV_BACKUP" ]]; then
  sudo cp -f "$RESOLV_BACKUP" /etc/resolv.conf
fi

rm -f "$STATE_FILE"
