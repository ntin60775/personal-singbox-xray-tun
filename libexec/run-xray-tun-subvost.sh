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

if [[ -z "$REAL_HOME" ]]; then
  echo "Не удалось определить домашний каталог пользователя ${REAL_USER}" >&2
  exit 1
fi

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

resolve_resolv_conf_target() {
  if readlink -f /etc/resolv.conf >/dev/null 2>&1; then
    readlink -f /etc/resolv.conf
  else
    printf '%s\n' "/etc/resolv.conf"
  fi
}

ensure_tun_device_available() {
  if [[ ! -e /dev/net/tun ]]; then
    echo "Не найден /dev/net/tun. Без него sing-box не сможет поднять TUN-интерфейс." >&2
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
    echo "В текущем /etc/resolv.conf нет ни одной строки nameserver." >&2
    echo "Старт остановлен до временной подмены DNS. Сними диагностику: sudo ${SUBVOST_CAPTURE_WRAPPER}" >&2
    exit 1
  fi

  resolv_target="$(resolve_resolv_conf_target)"

  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet systemd-resolved 2>/dev/null; then
    if [[ "$resolv_target" == "/run/systemd/resolve/stub-resolv.conf" ]]; then
      echo "Предупреждение: /etc/resolv.conf ведёт в ${resolv_target}, а systemd-resolved активен." >&2
      echo "Bundle продолжит старт и временно перепишет /etc/resolv.conf, но при проблемах с DNS сначала сними диагностику." >&2
      echo "Проверь: readlink -f /etc/resolv.conf ; systemctl status systemd-resolved" >&2
    fi
  fi

  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet NetworkManager 2>/dev/null; then
    if [[ "$resolv_target" == /run/NetworkManager/* ]]; then
      echo "Предупреждение: /etc/resolv.conf ведёт в ${resolv_target}, а NetworkManager активен." >&2
      echo "Bundle продолжит старт и временно перепишет /etc/resolv.conf, но при смене сети NetworkManager может перезаписать runtime-DNS." >&2
      echo "Проверь: readlink -f /etc/resolv.conf ; systemctl status NetworkManager" >&2
    fi
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

list_runtime_interfaces() {
  ip -o link show 2>/dev/null | awk -F': ' '{print $2}' | cut -d@ -f1 | grep -v '^lo$' || true
}

load_singbox_tun_expectations() {
  local parse_output
  local line
  local key
  local value

  EXPECTED_TUN_INTERFACE=""
  EXPECTED_TUN_ADDRESSES=""

  parse_output="$(
    python3 - "$SINGBOX_CONFIG" <<'PY'
import json
import sys

path = sys.argv[1]

try:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
except Exception:
    raise SystemExit(0)

for inbound in data.get("inbounds", []):
    if inbound.get("type") != "tun":
        continue

    interface_name = inbound.get("interface_name")
    if interface_name:
        print(f"interface_name={interface_name}")

    for address in inbound.get("address", []) or []:
        print(f"address={address}")
    break
PY
  )"

  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    case "$key" in
      interface_name)
        EXPECTED_TUN_INTERFACE="$value"
        ;;
      address)
        if [[ -n "$EXPECTED_TUN_ADDRESSES" ]]; then
          EXPECTED_TUN_ADDRESSES+=$'\n'
        fi
        EXPECTED_TUN_ADDRESSES+="$value"
        ;;
    esac
  done <<<"$parse_output"
}

capture_prestart_interfaces() {
  PRESTART_INTERFACES="$(list_runtime_interfaces)"
  PRESTART_INTERFACES_READY="1"
}

interface_was_present_before_start() {
  local interface_name="$1"
  [[ "${PRESTART_INTERFACES_READY:-0}" == "1" ]] || return 1
  printf '%s\n' "$PRESTART_INTERFACES" | grep -Fx -- "$interface_name" >/dev/null 2>&1
}

runtime_stack_is_alive() {
  kill -0 "${XRAY_PID:-0}" 2>/dev/null && kill -0 "${SINGBOX_PID:-0}" 2>/dev/null
}

interface_matches_singbox_config() {
  local interface_name="$1"
  local configured_address
  local interface_addresses=""
  local saw_configured_address="0"

  if [[ -n "$EXPECTED_TUN_INTERFACE" ]] && [[ "$interface_name" != "$EXPECTED_TUN_INTERFACE" ]]; then
    return 1
  fi

  if [[ -z "$EXPECTED_TUN_ADDRESSES" ]]; then
    [[ -n "$EXPECTED_TUN_INTERFACE" ]]
    return
  fi

  interface_addresses="$(ip -o addr show dev "$interface_name" 2>/dev/null | awk '{print $4}')"
  [[ -n "$interface_addresses" ]] || return 1

  while IFS= read -r configured_address; do
    [[ -n "$configured_address" ]] || continue
    saw_configured_address="1"
    if ! printf '%s\n' "$interface_addresses" | grep -Fx -- "$configured_address" >/dev/null 2>&1; then
      return 1
    fi
  done <<<"$EXPECTED_TUN_ADDRESSES"

  [[ "$saw_configured_address" == "1" ]]
}

detect_runtime_tun_interface() {
  local interface_name

  if [[ -n "$EXPECTED_TUN_INTERFACE" ]] && ip link show "$EXPECTED_TUN_INTERFACE" >/dev/null 2>&1; then
    printf '%s\n' "$EXPECTED_TUN_INTERFACE"
    return 0
  fi

  while IFS= read -r interface_name; do
    [[ -n "$interface_name" ]] || continue
    if interface_was_present_before_start "$interface_name"; then
      continue
    fi
    if interface_matches_singbox_config "$interface_name"; then
      printf '%s\n' "$interface_name"
      return 0
    fi
  done < <(list_runtime_interfaces)

  if [[ -n "${ACTIVE_TUN_INTERFACE:-}" ]] && ip link show "$ACTIVE_TUN_INTERFACE" >/dev/null 2>&1; then
    printf '%s\n' "$ACTIVE_TUN_INTERFACE"
    return 0
  fi

  return 1
}

cleanup_partial_start() {
  local interface_name="${ACTIVE_TUN_INTERFACE:-${EXPECTED_TUN_INTERFACE:-}}"

  if [[ -n "${SINGBOX_PID:-}" ]]; then
    sudo kill "$SINGBOX_PID" 2>/dev/null || true
  fi

  if [[ -n "${XRAY_PID:-}" ]]; then
    sudo kill "$XRAY_PID" 2>/dev/null || true
  fi

  sleep 1

  if [[ -n "$interface_name" ]] && [[ "${PRESTART_INTERFACES_READY:-0}" == "1" ]] && ! interface_was_present_before_start "$interface_name"; then
    sudo ip link delete "$interface_name" >/dev/null 2>&1 || true
  fi

  if [[ -f "$STATE_FILE" ]]; then
    rm -f "$STATE_FILE"
  fi
}

ensure_tun_runtime_is_ready() {
  if ! runtime_stack_is_alive; then
    return 1
  fi

  ACTIVE_TUN_INTERFACE="$(detect_runtime_tun_interface || true)"

  if [[ -z "$ACTIVE_TUN_INTERFACE" ]]; then
    return 1
  fi

  if ! ip link show "$ACTIVE_TUN_INTERFACE" >/dev/null 2>&1; then
    return 1
  fi

  if ! ip link show "$ACTIVE_TUN_INTERFACE" | grep -q '<.*UP.*>'; then
    return 1
  fi

  if ! ip -o addr show dev "$ACTIVE_TUN_INTERFACE" | grep -q .; then
    return 1
  fi

  if ! interface_matches_singbox_config "$ACTIVE_TUN_INTERFACE"; then
    return 1
  fi
}

wait_for_tun_runtime_ready() {
  local deadline=$((SECONDS + POST_START_SANITY_TIMEOUT_SECS))

  while (( SECONDS < deadline )); do
    if ensure_tun_runtime_is_ready; then
      return 0
    fi

    if ! runtime_stack_is_alive; then
      return 1
    fi

    sleep 1
  done

  ensure_tun_runtime_is_ready
}

dump_tun_routes_for_diagnostic() {
  local interface_name="${ACTIVE_TUN_INTERFACE:-${EXPECTED_TUN_INTERFACE:-}}"

  if [[ -n "$interface_name" ]]; then
    ip -4 route show table all 2>&1 | grep -F " dev ${interface_name}" || true
    return
  fi

  ip -4 route show table all 2>&1 | grep -E 'dev (tun|xray)[[:alnum:]_.-]+' || true
}

fail_start_with_rollback() {
  local failure_message="$1"
  local diagnostic_path=""

  echo "$failure_message" >&2
  diagnostic_path="$(capture_runtime_diagnostic)"
  echo "Выполняется rollback частично поднятого состояния..." >&2
  cleanup_partial_start

  if [[ -n "$diagnostic_path" ]]; then
    echo "Диагностика сохранена в: $diagnostic_path" >&2
  else
    echo "Автоматически снять полный диагностический дамп не удалось. Запусти: sudo ${SUBVOST_CAPTURE_WRAPPER}" >&2
  fi

  exit 1
}

XRAY_BIN_DEFAULT="$(
  subvost_find_executable \
    "${REAL_HOME}/.local/bin/xray" \
    "${HOME}/.local/bin/xray" \
    "$(command -v xray 2>/dev/null || true)" \
    "/usr/local/bin/xray" \
    "/usr/bin/xray" \
  || true
)"
XRAY_CONFIG="${XRAY_CONFIG:-${SCRIPT_DIR}/xray-tun-subvost.json}"
SINGBOX_BIN_DEFAULT="$(
  subvost_find_executable \
    "$(command -v sing-box 2>/dev/null || true)" \
    "/usr/local/bin/sing-box" \
    "/usr/bin/sing-box" \
  || true
)"
XRAY_BIN="${XRAY_BIN:-${XRAY_BIN_DEFAULT:-${HOME}/.local/bin/xray}}"
XRAY_CONFIG="${XRAY_CONFIG:-${SUBVOST_XRAY_CONFIG_PATH}}"
SINGBOX_CONFIG="${SINGBOX_CONFIG:-${SUBVOST_SINGBOX_CONFIG_PATH}}"
SINGBOX_BIN="${SINGBOX_BIN:-${SINGBOX_BIN_DEFAULT:-/usr/bin/sing-box}}"
STATE_FILE="${STATE_FILE:-${REAL_HOME}/.xray-tun-subvost.state}"
RESOLV_BACKUP="${RESOLV_BACKUP:-${REAL_HOME}/.xray-tun-subvost.resolv.conf.backup}"
RUNTIME_DNS_SERVERS="${RUNTIME_DNS_SERVERS:-8.8.8.8 1.1.1.1}"
XRAY_LOG="${XRAY_LOG:-${LOG_DIR}/xray-subvost.log}"
SINGBOX_LOG="${SINGBOX_LOG:-${LOG_DIR}/singbox-subvost.log}"
ENABLE_FILE_LOGS="${ENABLE_FILE_LOGS:-0}"
POST_START_SANITY_TIMEOUT_SECS="${POST_START_SANITY_TIMEOUT_SECS:-12}"
XRAY_PID=""
SINGBOX_PID=""
ACTIVE_TUN_INTERFACE=""
PRESTART_INTERFACES=""
PRESTART_INTERFACES_READY="0"
EXPECTED_TUN_INTERFACE=""
EXPECTED_TUN_ADDRESSES=""

load_singbox_tun_expectations

mkdir -p "$LOG_DIR"
ensure_absolute_path "$STATE_FILE" "STATE_FILE"
ensure_absolute_path "$RESOLV_BACKUP" "RESOLV_BACKUP"
ensure_absolute_path "$XRAY_LOG" "XRAY_LOG"
ensure_absolute_path "$SINGBOX_LOG" "SINGBOX_LOG"

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

echo "[0/8] Режим: Xray core + sing-box TUN, без одновременной работы FlClash"
echo "Схема повторяет рабочий подход Happ: Xray обслуживает SOCKS, sing-box поднимает TUN."
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

if [[ ! -x "$SINGBOX_BIN" ]]; then
  echo "Не найден исполняемый файл sing-box: $SINGBOX_BIN" >&2
  exit 1
fi

echo "[1/8] Проверка TUN-окружения"
ensure_tun_device_available
if [[ -n "$EXPECTED_TUN_INTERFACE" ]]; then
  ip -brief address show "$EXPECTED_TUN_INTERFACE" 2>/dev/null || true
else
  ip -brief address | grep -E 'FlClashX|tun0|xray0' || true
fi

if [[ -n "$EXPECTED_TUN_INTERFACE" ]] && ip link show "$EXPECTED_TUN_INTERFACE" >/dev/null 2>&1; then
  echo "Обнаружен уже существующий TUN-интерфейс ${EXPECTED_TUN_INTERFACE}." >&2
  echo "Сначала выполни ${SUBVOST_STOP_WRAPPER} и убедись, что интерфейс исчез." >&2
  exit 1
fi

if [[ -z "$EXPECTED_TUN_INTERFACE" ]] && { ip link show tun0 >/dev/null 2>&1 || ip link show xray0 >/dev/null 2>&1; }; then
  echo "Обнаружен уже существующий TUN-интерфейс tun0/xray0." >&2
  echo "Сначала выполни ${SUBVOST_STOP_WRAPPER} и убедись, что интерфейс исчез." >&2
  exit 1
fi

if pgrep -xaf 'FlClashX|FlClashCore' >/dev/null; then
  echo "Обнаружен активный FlClash. Полностью останови FlClashX/FlClashCore и запусти скрипт снова." >&2
  exit 1
fi

if pgrep -u "$REAL_USER" -xaf '.*(yandex_browser|chrome|chromium|firefox|brave|vivaldi).*' >/dev/null; then
  echo "Предупреждение: браузер уже запущен до старта туннеля."
  echo "Для чистой проверки лучше полностью закрыть браузер и открыть его после [8/8]."
fi

if [[ -f "$STATE_FILE" ]]; then
  echo "Обнаружен файл состояния прошлого запуска: $STATE_FILE" >&2
  echo "Сначала выполни ${SUBVOST_STOP_WRAPPER}" >&2
  exit 1
fi

capture_prestart_interfaces

echo "[2/8] Preflight-проверка конфигов и DNS-окружения"
ensure_dns_environment_is_supported
if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
  XRAY_CHECK_LOG="$XRAY_LOG"
  SINGBOX_CHECK_LOG="$SINGBOX_LOG"
  XRAY_RUN_TARGET="$XRAY_LOG"
  SINGBOX_RUN_TARGET="$SINGBOX_LOG"
else
  XRAY_CHECK_LOG="$(make_temp_log xray-check)"
  SINGBOX_CHECK_LOG="$(make_temp_log singbox-check)"
  XRAY_RUN_TARGET="/dev/null"
  SINGBOX_RUN_TARGET="/dev/null"
fi

if ! "$XRAY_BIN" run -test -c "$XRAY_CONFIG" >>"$XRAY_CHECK_LOG" 2>&1; then
  echo "Xray config check завершился ошибкой. Смотри лог: $XRAY_CHECK_LOG" >&2
  exit 1
fi

if ! "$SINGBOX_BIN" check -c "$SINGBOX_CONFIG" >>"$SINGBOX_CHECK_LOG" 2>&1; then
  echo "sing-box config check завершился ошибкой. Смотри лог: $SINGBOX_CHECK_LOG" >&2
  exit 1
fi

echo "[3/8] Запуск Xray core"
sudo -v
sudo "$XRAY_BIN" run -c "$XRAY_CONFIG" >>"$XRAY_RUN_TARGET" 2>&1 &
XRAY_PID=$!
sleep 2

if ! kill -0 "$XRAY_PID" 2>/dev/null; then
  if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
    echo "Xray завершился сразу после старта. Смотри лог: $XRAY_LOG" >&2
  else
    XRAY_FAIL_LOG="$(make_temp_log xray-start-fail)"
    capture_start_failure "$XRAY_FAIL_LOG" "$XRAY_BIN" run -c "$XRAY_CONFIG"
    fail_start_with_rollback "Xray завершился сразу после старта. Диагностика команды сохранена в: $XRAY_FAIL_LOG"
  fi
  fail_start_with_rollback "Xray завершился сразу после старта. Смотри лог: $XRAY_LOG"
fi

echo "[4/8] Запуск sing-box TUN"
sudo "$SINGBOX_BIN" run -c "$SINGBOX_CONFIG" >>"$SINGBOX_RUN_TARGET" 2>&1 &
SINGBOX_PID=$!
sleep 2

if ! kill -0 "$SINGBOX_PID" 2>/dev/null; then
  if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
    echo "sing-box завершился сразу после старта. Смотри лог: $SINGBOX_LOG" >&2
  else
    SINGBOX_FAIL_LOG="$(make_temp_log singbox-start-fail)"
    capture_start_failure "$SINGBOX_FAIL_LOG" "$SINGBOX_BIN" run -c "$SINGBOX_CONFIG"
    fail_start_with_rollback "sing-box завершился сразу после старта. Диагностика команды сохранена в: $SINGBOX_FAIL_LOG"
  fi
  fail_start_with_rollback "sing-box завершился сразу после старта. Смотри лог: $SINGBOX_LOG"
fi

echo "[5/8] Post-start sanity check"
if ! wait_for_tun_runtime_ready; then
  TUN_ROUTE_OUTPUT="$(dump_tun_routes_for_diagnostic)"
  fail_start_with_rollback "Post-start sanity check провален: ожидаемый TUN-интерфейс ${ACTIVE_TUN_INTERFACE:-${EXPECTED_TUN_INTERFACE:-не найден}} не появился в готовом состоянии, не получил все адреса из текущего SINGBOX_CONFIG или стек Xray/sing-box завершился во время ожидания.
Проверь вывод: ${TUN_ROUTE_OUTPUT}"
fi

if [[ "$ENABLE_FILE_LOGS" != "1" ]]; then
  rm -f "$XRAY_CHECK_LOG" "$SINGBOX_CHECK_LOG"
fi

echo "[6/8] Настройка системного DNS"
backup_resolv_conf
write_runtime_resolv_conf

echo "[7/8] Сохранение состояния"
printf 'XRAY_PID=%s\nSINGBOX_PID=%s\nRESOLV_BACKUP=%s\n' \
  "$XRAY_PID" \
  "$SINGBOX_PID" \
  "$RESOLV_BACKUP" \
  >"$STATE_FILE"

echo "[8/8] Готово"
echo "XRAY_PID=$XRAY_PID"
echo "SINGBOX_PID=$SINGBOX_PID"
echo "RESOLV_BACKUP=$RESOLV_BACKUP"
if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
  echo "Лог Xray: $XRAY_LOG"
  echo "Лог sing-box: $SINGBOX_LOG"
else
  echo "Файловые логи отключены"
fi
echo "Для отката используй: ${SUBVOST_STOP_WRAPPER}"
