#!/usr/bin/env bash
set -euo pipefail

INTERNAL_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${INTERNAL_DIR}/../lib/subvost-common.sh"
subvost_load_project_layout_from_env

LOG_DIR="${SUBVOST_LOG_DIR}"
REAL_USER="${SUDO_USER:-${USER:-$(id -un)}}"
REAL_HOME="$(
  getent passwd "$REAL_USER" | cut -d: -f6
)"
REAL_UID="$(id -u "$REAL_USER")"
REAL_GID="$(id -g "$REAL_USER")"

if [[ -z "$REAL_HOME" ]]; then
  echo "Не удалось определить домашний каталог пользователя ${REAL_USER}" >&2
  exit 1
fi

ACTIVE_XRAY_CONFIG_DEFAULT="$(subvost_resolve_active_xray_config_for_home "$REAL_HOME")"
ACTIVE_RUNTIME_XRAY_CONFIG_DEFAULT="$(subvost_resolve_active_runtime_xray_config_for_home "$REAL_HOME")"
XRAY_ASSET_DIR_DEFAULT="$(subvost_resolve_xray_asset_dir_for_home "$REAL_HOME")"
STORE_FILE_DEFAULT="$(subvost_resolve_store_file_for_home "$REAL_HOME")"

ensure_absolute_path() {
  local path_value="$1"
  local label="$2"
  if [[ "$path_value" != /* ]]; then
    echo "${label} должен быть абсолютным путём: ${path_value}" >&2
    exit 1
  fi
}

make_temp_log() {
  local prefix="$1"
  mktemp "${LOG_DIR}/${prefix}.XXXXXX.log"
}

capture_start_failure() {
  local output_path="$1"
  shift
  sudo timeout 5 "$@" >"$output_path" 2>&1 || true
}

service_is_active() {
  local unit_name="$1"
  command -v systemctl >/dev/null 2>&1 || return 1
  systemctl is-active --quiet "$unit_name" 2>/dev/null
}

ensure_no_conflicting_xray_service() {
  if service_is_active xray.service; then
    echo "Обнаружен активный системный xray.service." >&2
    echo "Для portable bundle он не нужен и может создавать дубли процесса Xray." >&2
    echo "Останови его перед запуском bundle: sudo systemctl disable --now xray.service" >&2
    exit 1
  fi

  if pgrep -xaf '/usr/local/bin/xray run -config /usr/local/etc/xray/config.json' >/dev/null 2>&1; then
    echo "Обнаружен запущенный системный Xray с конфигом /usr/local/etc/xray/config.json." >&2
    echo "Останови его перед запуском bundle, иначе диагностика и управление процессами будут неоднозначны." >&2
    exit 1
  fi
}

resolve_resolv_conf_target() {
  if readlink -f /etc/resolv.conf >/dev/null 2>&1; then
    readlink -f /etc/resolv.conf
  else
    printf '%s\n' "/etc/resolv.conf"
  fi
}

ensure_python3_available() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Не найдена обязательная зависимость python3." >&2
    echo "Установи python3 и повтори запуск bundle." >&2
    exit 1
  fi
}

sync_generated_runtime_snapshot_from_store() {
  local config_home

  config_home="$(subvost_resolve_real_config_home "$REAL_HOME")"
  python3 - \
    "$REAL_HOME" \
    "$config_home" \
    "$SUBVOST_PROJECT_ROOT" \
    "$REAL_UID" \
    "$REAL_GID" <<'PY'
import sys
from pathlib import Path

real_home = Path(sys.argv[1])
config_home = sys.argv[2]
project_root = Path(sys.argv[3])
uid = int(sys.argv[4])
gid = int(sys.argv[5])

sys.path.insert(0, str(project_root / "gui"))

from subvost_paths import build_app_paths  # noqa: E402
from subvost_store import ensure_store_initialized  # noqa: E402

paths = build_app_paths(real_home, config_home)
ensure_store_initialized(paths, project_root, uid=uid, gid=gid)
PY
}

ensure_tun_device_available() {
  if [[ ! -e /dev/net/tun ]]; then
    echo "Не найден /dev/net/tun. Без него xray-core не сможет поднять TUN-интерфейс." >&2
    echo "Проверь: ls -l /dev/net/tun ; lsmod | grep tun" >&2
    exit 1
  fi

  if [[ ! -c /dev/net/tun ]]; then
    echo "/dev/net/tun существует, но это не символьное устройство." >&2
    echo "Проверь: ls -l /dev/net/tun ; sudo ${SUBVOST_CAPTURE_WRAPPER}" >&2
    exit 1
  fi
}

ensure_dns_environment_is_supported() {
  local resolv_target
  local resolved_state="inactive"
  local network_manager_state="inactive"

  if [[ ! -e /etc/resolv.conf ]]; then
    echo "Не найден /etc/resolv.conf. Старт остановлен до изменения DNS." >&2
    echo "Сними диагностику: sudo ${SUBVOST_CAPTURE_WRAPPER}" >&2
    exit 1
  fi

  if [[ -L /etc/resolv.conf ]] && ! readlink -f /etc/resolv.conf >/dev/null 2>&1; then
    echo "/etc/resolv.conf является битой символьной ссылкой." >&2
    echo "Сними диагностику: sudo ${SUBVOST_CAPTURE_WRAPPER}" >&2
    exit 1
  fi

  if ! grep -Eq '^[[:space:]]*nameserver[[:space:]]+' /etc/resolv.conf; then
    echo "Предупреждение: в текущем /etc/resolv.conf нет явных строк nameserver." >&2
    echo "Bundle продолжит старт: файл всё равно будет сохранён в backup и временно переписан runtime-DNS." >&2
  fi

  resolv_target="$(resolve_resolv_conf_target)"

  if service_is_active systemd-resolved; then
    resolved_state="active"
  fi

  if service_is_active NetworkManager; then
    network_manager_state="active"
  fi

  if [[ "$resolved_state" == "active" ]] && [[ "$resolv_target" == "/run/systemd/resolve/stub-resolv.conf" ]]; then
    echo "Предупреждение: /etc/resolv.conf ведёт в ${resolv_target}, а systemd-resolved активен." >&2
    echo "Bundle продолжит старт и временно перепишет /etc/resolv.conf, но при проблемах с DNS сначала сними диагностику." >&2
    echo "Проверь: readlink -f /etc/resolv.conf ; systemctl status systemd-resolved" >&2
  fi

  if [[ "$network_manager_state" == "active" ]] && [[ "$resolv_target" == /run/NetworkManager/* ]]; then
    echo "Предупреждение: /etc/resolv.conf ведёт в ${resolv_target}, а NetworkManager активен." >&2
    echo "Bundle продолжит старт и временно перепишет /etc/resolv.conf, но при смене сети NetworkManager может перезаписать runtime-DNS." >&2
    echo "Проверь: readlink -f /etc/resolv.conf ; systemctl status NetworkManager" >&2
  fi
}

capture_runtime_diagnostic() {
  local diagnostic_path=""
  if [[ "$(id -u)" -eq 0 ]]; then
    diagnostic_path="$(timeout 90 "${SUBVOST_CAPTURE_WRAPPER}" 2>/dev/null || true)"
  else
    diagnostic_path="$(sudo timeout 90 "${SUBVOST_CAPTURE_WRAPPER}" 2>/dev/null || true)"
  fi
  printf '%s\n' "$diagnostic_path" | tail -n 1
}

load_active_selection_from_store() {
  local store_file="$1"
  local selection_data=""

  if [[ ! -f "$store_file" ]]; then
    return 0
  fi

  selection_data="$(
    python3 - "$store_file" <<'PY'
import json
import sys

path = sys.argv[1]
profile_id = ""
node_id = ""
try:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    selection = payload.get("active_selection", {})
    profile_id = selection.get("profile_id") or ""
    node_id = selection.get("node_id") or ""
except Exception:
    pass
print(profile_id)
print(node_id)
PY
  )"

  ACTIVE_PROFILE_ID="$(printf '%s\n' "$selection_data" | sed -n '1p')"
  ACTIVE_NODE_ID="$(printf '%s\n' "$selection_data" | sed -n '2p')"
}

read_state_bundle_install_id() {
  local state_file="$1"
  local key value

  [[ -f "$state_file" ]] || return 0

  while IFS='=' read -r key value; do
    case "$key" in
      BUNDLE_INSTALL_ID)
        if subvost_validate_install_id "$value"; then
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
    state_tun_interface="$TUN_INTERFACE_NAME"
  fi

  if [[ -n "$state_pid" ]] && kill -0 "$state_pid" 2>/dev/null; then
    return 0
  fi

  if [[ -n "$state_tun_interface" ]] && ip link show "$state_tun_interface" >/dev/null 2>&1; then
    return 0
  fi

  return 1
}

backup_resolv_conf() {
  sudo cp -fL /etc/resolv.conf "$RESOLV_BACKUP"
}

write_runtime_resolv_conf() {
  {
    echo "# Managed by ${0##*/}"
    local nameserver
    for nameserver in $RUNTIME_DNS_SERVERS; do
      echo "nameserver ${nameserver}"
    done
    echo "options timeout:2 attempts:2 rotate"
  } | sudo tee /etc/resolv.conf >/dev/null
}

detect_default_ipv4_interface() {
  DEFAULT_IPV4_ROUTE_LINE="$(ip -4 route show default 2>/dev/null | head -n 1)"
  if [[ -z "$DEFAULT_IPV4_ROUTE_LINE" ]]; then
    echo "Не найден default IPv4 route. Без него runtime не сможет оставить исходящий трафик самого Xray во внешней сети." >&2
    exit 1
  fi

  DEFAULT_IPV4_INTERFACE="$(
    awk '{for (i = 1; i <= NF; i++) if ($i == "dev") { print $(i + 1); exit }}' <<<"$DEFAULT_IPV4_ROUTE_LINE"
  )"
  if [[ -z "$DEFAULT_IPV4_INTERFACE" ]]; then
    echo "Не удалось определить интерфейс из default IPv4 route: ${DEFAULT_IPV4_ROUTE_LINE}" >&2
    exit 1
  fi
}

materialize_runtime_config() {
  python3 - \
    "$XRAY_CONFIG" \
    "$XRAY_RUNTIME_CONFIG" \
    "$DEFAULT_IPV4_INTERFACE" \
    "$ROUTE_MARK" \
    "$REAL_UID" \
    "$REAL_GID" \
    "$SUBVOST_PROJECT_ROOT" <<'PY'
import json
import os
import sys
from pathlib import Path

base_config_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
default_interface = sys.argv[3]
outbound_mark = int(sys.argv[4])
uid = int(sys.argv[5])
gid = int(sys.argv[6])
project_root = Path(sys.argv[7])

sys.path.insert(0, str(project_root / "gui"))

from subvost_runtime import apply_transport_hints_to_runtime_config, read_json_config  # noqa: E402
from subvost_paths import atomic_write_json  # noqa: E402

base_config = read_json_config(base_config_path)

if not base_config:
    raise SystemExit(f"Не удалось прочитать активный Xray-конфиг: {base_config_path}")

runtime_config = apply_transport_hints_to_runtime_config(
    base_config,
    default_interface=default_interface,
    outbound_mark=outbound_mark,
)
atomic_write_json(output_path, runtime_config, uid=uid, gid=gid)
PY
}

policy_route_cleanup() {
  sudo ip rule del pref "$ROUTE_RULE_PREF" not fwmark "$ROUTE_MARK" table "$ROUTE_TABLE" >/dev/null 2>&1 || true
  sudo ip route flush table "$ROUTE_TABLE" >/dev/null 2>&1 || true
  sudo ip route flush cache >/dev/null 2>&1 || true
}

cleanup_partial_start() {
  policy_route_cleanup

  if [[ -n "${XRAY_PID:-}" ]]; then
    sudo kill "$XRAY_PID" 2>/dev/null || true
  fi

  sleep 1

  if [[ -n "${TUN_INTERFACE_NAME:-}" ]]; then
    sudo ip link delete "$TUN_INTERFACE_NAME" >/dev/null 2>&1 || true
  fi

  if [[ -f "$STATE_FILE" ]]; then
    rm -f "$STATE_FILE"
  fi
}

fail_start_with_rollback() {
  local failure_message="$1"
  local diagnostic_path=""

  echo "$failure_message" >&2
  diagnostic_path="$(capture_runtime_diagnostic)"
  echo "Выполняется rollback частично поднятого состояния..." >&2
  cleanup_partial_start

  if [[ -f "$RESOLV_BACKUP" ]]; then
    sudo cp -f "$RESOLV_BACKUP" /etc/resolv.conf >/dev/null 2>&1 || true
  fi

  if [[ -n "$diagnostic_path" ]]; then
    echo "Диагностика сохранена в: $diagnostic_path" >&2
  else
    echo "Автоматически снять полный диагностический дамп не удалось. Запусти: sudo ${SUBVOST_CAPTURE_WRAPPER}" >&2
  fi

  exit 1
}

wait_for_tun_interface_ready() {
  local deadline=$((SECONDS + POST_START_SANITY_TIMEOUT_SECS))

  while (( SECONDS < deadline )); do
    if kill -0 "${XRAY_PID:-0}" 2>/dev/null \
      && ip link show "$TUN_INTERFACE_NAME" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  kill -0 "${XRAY_PID:-0}" 2>/dev/null && ip link show "$TUN_INTERFACE_NAME" >/dev/null 2>&1
}

XRAY_BIN_DEFAULT="$(
  subvost_find_executable \
    "/usr/local/bin/xray" \
    "/usr/bin/xray" \
    "${REAL_HOME}/.local/bin/xray" \
    "${HOME}/.local/bin/xray" \
    "$(command -v xray 2>/dev/null || true)" \
  || true
)"
XRAY_BIN="${XRAY_BIN:-${XRAY_BIN_DEFAULT:-${HOME}/.local/bin/xray}}"
XRAY_CONFIG="${ACTIVE_XRAY_CONFIG_DEFAULT}"
XRAY_RUNTIME_CONFIG="${XRAY_RUNTIME_CONFIG:-${ACTIVE_RUNTIME_XRAY_CONFIG_DEFAULT}}"
XRAY_ASSET_DIR="${XRAY_ASSET_DIR:-${XRAY_ASSET_DIR_DEFAULT}}"
STATE_FILE="${STATE_FILE:-${REAL_HOME}/.xray-tun-subvost.state}"
RESOLV_BACKUP="${RESOLV_BACKUP:-${REAL_HOME}/.xray-tun-subvost.resolv.conf.backup}"
RUNTIME_DNS_SERVERS="${RUNTIME_DNS_SERVERS:-8.8.8.8 1.1.1.1}"
XRAY_LOG="${XRAY_LOG:-${LOG_DIR}/xray-subvost.log}"
ENABLE_FILE_LOGS="${ENABLE_FILE_LOGS:-0}"
POST_START_SANITY_TIMEOUT_SECS="${POST_START_SANITY_TIMEOUT_SECS:-12}"
ROUTE_TABLE="${ROUTE_TABLE:-18421}"
ROUTE_MARK="${ROUTE_MARK:-8421}"
ROUTE_RULE_PREF="${ROUTE_RULE_PREF:-100}"
TUN_INTERFACE_NAME="${TUN_INTERFACE_NAME:-tun0}"
TUN_INTERFACE_ADDRESS="${TUN_INTERFACE_ADDRESS:-172.19.0.1/30}"
XRAY_PID=""
ACTIVE_PROFILE_ID=""
ACTIVE_NODE_ID=""
DEFAULT_IPV4_ROUTE_LINE=""
DEFAULT_IPV4_INTERFACE=""
XRAY_CONFIG_SOURCE="store"
BUNDLE_INSTALL_ID="$(subvost_ensure_install_id)"

ensure_python3_available

if [[ -f "$STORE_FILE_DEFAULT" ]]; then
  sync_generated_runtime_snapshot_from_store
fi

mkdir -p "$LOG_DIR"
ensure_absolute_path "$STATE_FILE" "STATE_FILE"
ensure_absolute_path "$RESOLV_BACKUP" "RESOLV_BACKUP"
ensure_absolute_path "$XRAY_LOG" "XRAY_LOG"
ensure_absolute_path "$XRAY_RUNTIME_CONFIG" "XRAY_RUNTIME_CONFIG"
ensure_absolute_path "$XRAY_CONFIG" "XRAY_CONFIG"
ensure_absolute_path "$XRAY_ASSET_DIR" "XRAY_ASSET_DIR"

echo "[0/8] Режим: Xray core TUN"
echo "Поднимается основной runtime проекта без дополнительных прокси-движков."
echo "Пользователь bundle: ${REAL_USER}"
if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
  echo "Файловое логирование: включено"
else
  echo "Файловое логирование: выключено (для включения: ENABLE_FILE_LOGS=1)"
fi
echo

if [[ ! -x "$XRAY_BIN" ]]; then
  echo "Не найден исполняемый файл Xray: $XRAY_BIN" >&2
  exit 1
fi

load_active_selection_from_store "$STORE_FILE_DEFAULT"
if [[ -z "$ACTIVE_PROFILE_ID" || -z "$ACTIVE_NODE_ID" ]]; then
  echo "Не найден активный узел в локальном store." >&2
  echo "Сначала открой GUI, импортируй подписку при необходимости и явно активируй нужную ноду." >&2
  exit 1
fi

if [[ ! -f "$XRAY_CONFIG" ]]; then
  echo "Не найден сгенерированный Xray-конфиг активного узла: $XRAY_CONFIG" >&2
  echo "Открой GUI и снова активируй узел, чтобы пересобрать runtime-конфиг." >&2
  exit 1
fi

ensure_no_conflicting_xray_service

echo "[1/8] Проверка TUN-окружения"
ensure_tun_device_available
ip -brief address | grep -E 'FlClashX|tun0|xray0' || true

if ip link show "$TUN_INTERFACE_NAME" >/dev/null 2>&1; then
  echo "Обнаружен уже существующий TUN-интерфейс ${TUN_INTERFACE_NAME}." >&2
  echo "Сначала выполни ${SUBVOST_STOP_WRAPPER} и убедись, что интерфейс исчез." >&2
  exit 1
fi

if pgrep -xaf 'FlClashX|FlClashCore' >/dev/null 2>&1; then
  echo "Обнаружен активный FlClash. Полностью останови FlClashX/FlClashCore и запусти скрипт снова." >&2
  exit 1
fi

if [[ -f "$STATE_FILE" ]]; then
  STATE_BUNDLE_INSTALL_ID="$(read_state_bundle_install_id "$STATE_FILE")"
  STATE_BUNDLE_PROJECT_ROOT="$(read_state_value "$STATE_FILE" "BUNDLE_PROJECT_ROOT_HINT")"
  if [[ -z "$STATE_BUNDLE_PROJECT_ROOT" ]]; then
    STATE_BUNDLE_PROJECT_ROOT="$(read_state_value "$STATE_FILE" "BUNDLE_PROJECT_ROOT")"
  fi

  if [[ -n "$STATE_BUNDLE_INSTALL_ID" ]]; then
    if [[ "$STATE_BUNDLE_INSTALL_ID" != "$BUNDLE_INSTALL_ID" ]]; then
      if legacy_state_runtime_is_live "$STATE_FILE"; then
        echo "Обнаружен файл состояния другой установки bundle: $STATE_FILE" >&2
        echo "Идентификатор установки владельца: ${STATE_BUNDLE_INSTALL_ID}" >&2
        echo "Идентификатор текущей установки: ${BUNDLE_INSTALL_ID}" >&2
        if [[ -n "$STATE_BUNDLE_PROJECT_ROOT" ]]; then
          echo "Последний известный путь владельца: ${STATE_BUNDLE_PROJECT_ROOT}" >&2
        fi
        echo "Сначала останови исходную установку или выполни ${SUBVOST_STOP_WRAPPER}, когда runtime уже не активен." >&2
        exit 1
      fi

      echo "Обнаружен устаревший файл состояния другой установки bundle: $STATE_FILE" >&2
      echo "Идентификатор установки владельца: ${STATE_BUNDLE_INSTALL_ID}" >&2
      echo "Идентификатор текущей установки: ${BUNDLE_INSTALL_ID}" >&2
      echo "Живой процесс по этому файлу состояния не найден, новый запуск перезапишет устаревшее состояние." >&2
    else
      echo "Обнаружен файл состояния прошлого запуска текущей установки bundle: $STATE_FILE" >&2
      echo "Сначала выполни ${SUBVOST_STOP_WRAPPER}" >&2
      exit 1
    fi
  elif [[ -n "$STATE_BUNDLE_PROJECT_ROOT" ]] && [[ "$STATE_BUNDLE_PROJECT_ROOT" != "$SUBVOST_PROJECT_ROOT" ]]; then
    if legacy_state_runtime_is_live "$STATE_FILE"; then
      echo "Обнаружен legacy state другого bundle: $STATE_FILE" >&2
      echo "Последний известный путь владельца runtime: ${STATE_BUNDLE_PROJECT_ROOT}" >&2
      echo "Текущий bundle: ${SUBVOST_PROJECT_ROOT}" >&2
      echo "Сначала останови исходный экземпляр или выполни ${SUBVOST_STOP_WRAPPER}, когда runtime уже не активен." >&2
      exit 1
    fi

    echo "Обнаружен stale legacy state другого bundle: $STATE_FILE" >&2
    echo "Последний известный путь владельца runtime: ${STATE_BUNDLE_PROJECT_ROOT}" >&2
    echo "Текущий bundle: ${SUBVOST_PROJECT_ROOT}" >&2
    echo "Живой процесс по этому файлу состояния не найден, новый запуск перезапишет устаревшее состояние." >&2
  elif [[ -z "$STATE_BUNDLE_PROJECT_ROOT" ]]; then
    if legacy_state_runtime_is_live "$STATE_FILE"; then
      echo "Обнаружен файл состояния без bundle identity: $STATE_FILE" >&2
      echo "Для безопасности текущий bundle не будет стартовать поверх неподтверждённого runtime." >&2
      echo "Сначала выполни ${SUBVOST_STOP_WRAPPER}" >&2
      exit 1
    fi

    echo "Обнаружен stale legacy state без bundle identity: $STATE_FILE" >&2
    echo "Процесс по этому файлу состояния уже не активен, файл будет перезаписан новым запуском." >&2
  else
    echo "Обнаружен файл состояния прошлого запуска текущего bundle: $STATE_FILE" >&2
    echo "Сначала выполни ${SUBVOST_STOP_WRAPPER}" >&2
    exit 1
  fi
fi

echo "[2/8] Preflight DNS и routing-окружения"
ensure_dns_environment_is_supported
detect_default_ipv4_interface
echo "Основной внешний интерфейс: ${DEFAULT_IPV4_INTERFACE}"
echo "Default route: ${DEFAULT_IPV4_ROUTE_LINE}"

if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
  XRAY_CHECK_LOG="$XRAY_LOG"
  XRAY_RUN_TARGET="$XRAY_LOG"
else
  XRAY_CHECK_LOG="$(make_temp_log xray-check)"
  XRAY_RUN_TARGET="/dev/null"
fi

echo "[3/8] Materialize runtime-конфига"
materialize_runtime_config

if ! XRAY_LOCATION_ASSET="$XRAY_ASSET_DIR" "$XRAY_BIN" run -test -c "$XRAY_RUNTIME_CONFIG" >>"$XRAY_CHECK_LOG" 2>&1; then
  echo "Xray config check завершился ошибкой. Смотри лог: $XRAY_CHECK_LOG" >&2
  exit 1
fi

echo "[4/8] Запуск Xray core"
sudo -v
sudo XRAY_LOCATION_ASSET="$XRAY_ASSET_DIR" "$XRAY_BIN" run -c "$XRAY_RUNTIME_CONFIG" >>"$XRAY_RUN_TARGET" 2>&1 &
XRAY_PID=$!
sleep 2

if ! kill -0 "$XRAY_PID" 2>/dev/null; then
  if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
    echo "Xray завершился сразу после старта. Смотри лог: $XRAY_LOG" >&2
  else
    XRAY_FAIL_LOG="$(make_temp_log xray-start-fail)"
    capture_start_failure "$XRAY_FAIL_LOG" env XRAY_LOCATION_ASSET="$XRAY_ASSET_DIR" "$XRAY_BIN" run -c "$XRAY_RUNTIME_CONFIG"
    fail_start_with_rollback "Xray завершился сразу после старта. Диагностика команды сохранена в: $XRAY_FAIL_LOG"
  fi
  fail_start_with_rollback "Xray завершился сразу после старта. Смотри лог: $XRAY_LOG"
fi

echo "[5/8] Ожидание tun-интерфейса и настройка policy-routing"
if ! wait_for_tun_interface_ready; then
  fail_start_with_rollback "Xray не создал интерфейс ${TUN_INTERFACE_NAME} за отведённое время."
fi

sudo ip link set dev "$TUN_INTERFACE_NAME" up >/dev/null 2>&1 || true
if [[ -n "$TUN_INTERFACE_ADDRESS" ]]; then
  sudo ip address add "$TUN_INTERFACE_ADDRESS" dev "$TUN_INTERFACE_NAME" >/dev/null 2>&1 || true
fi
sudo ip route replace table "$ROUTE_TABLE" default dev "$TUN_INTERFACE_NAME"
sudo ip rule add pref "$ROUTE_RULE_PREF" not fwmark "$ROUTE_MARK" table "$ROUTE_TABLE"
sudo ip route flush cache >/dev/null 2>&1 || true

if ! ip rule show | grep -F "lookup ${ROUTE_TABLE}" >/dev/null 2>&1; then
  fail_start_with_rollback "Policy-routing правило для таблицы ${ROUTE_TABLE} не появилось."
fi

if ! ip link show "$TUN_INTERFACE_NAME" | grep -q '<.*UP.*>'; then
  fail_start_with_rollback "TUN-интерфейс ${TUN_INTERFACE_NAME} создан, но не находится в состоянии UP."
fi

echo "[6/8] Настройка системного DNS"
backup_resolv_conf
write_runtime_resolv_conf

if [[ "$ENABLE_FILE_LOGS" != "1" ]]; then
  rm -f "$XRAY_CHECK_LOG"
fi

echo "[7/8] Сохранение состояния"
STARTED_AT="$(date -Iseconds)"
printf 'XRAY_PID=%s\nRESOLV_BACKUP=%s\nXRAY_CONFIG=%s\nACTIVE_PROFILE_ID=%s\nACTIVE_NODE_ID=%s\n' \
  "$XRAY_PID" \
  "$RESOLV_BACKUP" \
  "$XRAY_RUNTIME_CONFIG" \
  "$ACTIVE_PROFILE_ID" \
  "$ACTIVE_NODE_ID" \
  >"$STATE_FILE"
printf 'STARTED_AT=%s\n' "$STARTED_AT" >>"$STATE_FILE"
printf 'XRAY_CONFIG_SOURCE=%s\n' "$XRAY_CONFIG_SOURCE" >>"$STATE_FILE"
printf 'BUNDLE_INSTALL_ID=%s\n' "$BUNDLE_INSTALL_ID" >>"$STATE_FILE"
printf 'BUNDLE_PROJECT_ROOT_HINT=%s\n' "$SUBVOST_PROJECT_ROOT" >>"$STATE_FILE"
printf 'RUNTIME_IMPL=%s\n' "xray" >>"$STATE_FILE"
printf 'TUN_INTERFACE=%s\n' "$TUN_INTERFACE_NAME" >>"$STATE_FILE"
printf 'TUN_INTERFACE_ADDRESS=%s\n' "$TUN_INTERFACE_ADDRESS" >>"$STATE_FILE"
printf 'ROUTE_TABLE=%s\n' "$ROUTE_TABLE" >>"$STATE_FILE"
printf 'ROUTE_MARK=%s\n' "$ROUTE_MARK" >>"$STATE_FILE"
printf 'ROUTE_RULE_PREF=%s\n' "$ROUTE_RULE_PREF" >>"$STATE_FILE"

echo "[8/8] Готово"
echo "XRAY_PID=$XRAY_PID"
echo "RUNTIME_IMPL=xray"
echo "XRAY_CONFIG=$XRAY_RUNTIME_CONFIG"
echo "XRAY_CONFIG_SOURCE=$XRAY_CONFIG_SOURCE"
echo "STARTED_AT=$STARTED_AT"
echo "TUN_INTERFACE=$TUN_INTERFACE_NAME"
echo "TUN_INTERFACE_ADDRESS=$TUN_INTERFACE_ADDRESS"
echo "DEFAULT_IPV4_INTERFACE=$DEFAULT_IPV4_INTERFACE"
echo "ROUTE_TABLE=$ROUTE_TABLE"
echo "ROUTE_MARK=$ROUTE_MARK"
if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
  echo "Лог Xray: $XRAY_LOG"
else
  echo "Файловые логи отключены"
fi
echo "Для отката используй: ${SUBVOST_STOP_WRAPPER}"
