#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
REAL_USER="${SUDO_USER:-${USER:-$(id -un)}}"
REAL_HOME="$(
  getent passwd "$REAL_USER" | cut -d: -f6
)"

if [[ -z "$REAL_HOME" ]]; then
  echo "Не удалось определить домашний каталог пользователя ${REAL_USER}" >&2
  exit 1
fi

find_executable() {
  local candidate
  for candidate in "$@"; do
    [[ -n "$candidate" ]] || continue
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

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

XRAY_BIN_DEFAULT="$(
  find_executable \
    "${REAL_HOME}/.local/bin/xray" \
    "${HOME}/.local/bin/xray" \
    "$(command -v xray 2>/dev/null || true)" \
    "/usr/local/bin/xray" \
    "/usr/bin/xray" \
  || true
)"
XRAY_CONFIG="${XRAY_CONFIG:-${SCRIPT_DIR}/xray-tun-subvost.json}"
SINGBOX_BIN_DEFAULT="$(
  find_executable \
    "$(command -v sing-box 2>/dev/null || true)" \
    "/usr/local/bin/sing-box" \
    "/usr/bin/sing-box" \
  || true
)"
XRAY_BIN="${XRAY_BIN:-${XRAY_BIN_DEFAULT:-${HOME}/.local/bin/xray}}"
SINGBOX_CONFIG="${SINGBOX_CONFIG:-${SCRIPT_DIR}/singbox-tun-subvost.json}"
SINGBOX_BIN="${SINGBOX_BIN:-${SINGBOX_BIN_DEFAULT:-/usr/bin/sing-box}}"
STATE_FILE="${STATE_FILE:-${REAL_HOME}/.xray-tun-subvost.state}"
RESOLV_BACKUP="${RESOLV_BACKUP:-${REAL_HOME}/.xray-tun-subvost.resolv.conf.backup}"
RUNTIME_DNS_SERVERS="${RUNTIME_DNS_SERVERS:-8.8.8.8 1.1.1.1}"
XRAY_LOG="${XRAY_LOG:-${LOG_DIR}/xray-subvost.log}"
SINGBOX_LOG="${SINGBOX_LOG:-${LOG_DIR}/singbox-subvost.log}"
ENABLE_FILE_LOGS="${ENABLE_FILE_LOGS:-0}"

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

echo "[0/7] Режим: Xray core + sing-box TUN, без одновременной работы FlClash"
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

echo "[1/7] Проверка существующих TUN-интерфейсов"
ip -brief address | grep -E 'FlClashX|tun0|xray0' || true

if ip link show tun0 >/dev/null 2>&1 || ip link show xray0 >/dev/null 2>&1; then
  echo "Обнаружен уже существующий TUN-интерфейс tun0/xray0." >&2
  echo "Сначала выполни ${SCRIPT_DIR}/stop-xray-tun-subvost.sh и убедись, что интерфейс исчез." >&2
  exit 1
fi

if pgrep -xaf 'FlClashX|FlClashCore' >/dev/null; then
  echo "Обнаружен активный FlClash. Полностью останови FlClashX/FlClashCore и запусти скрипт снова." >&2
  exit 1
fi

if pgrep -u "$REAL_USER" -xaf '.*(yandex_browser|chrome|chromium|firefox|brave|vivaldi).*' >/dev/null; then
  echo "Предупреждение: браузер уже запущен до старта туннеля."
  echo "Для чистой проверки лучше полностью закрыть браузер и открыть его после [7/7]."
fi

if [[ -f "$STATE_FILE" ]]; then
  echo "Обнаружен файл состояния прошлого запуска: $STATE_FILE" >&2
  echo "Сначала выполни ${SCRIPT_DIR}/stop-xray-tun-subvost.sh" >&2
  exit 1
fi

echo "[2/7] Preflight-проверка конфигов"
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

echo "[3/7] Запуск Xray core"
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
    echo "Xray завершился сразу после старта. Диагностика сохранена в: $XRAY_FAIL_LOG" >&2
  fi
  exit 1
fi

echo "[4/7] Запуск sing-box TUN"
sudo "$SINGBOX_BIN" run -c "$SINGBOX_CONFIG" >>"$SINGBOX_RUN_TARGET" 2>&1 &
SINGBOX_PID=$!
sleep 2

if ! kill -0 "$SINGBOX_PID" 2>/dev/null; then
  if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
    echo "sing-box завершился сразу после старта. Смотри лог: $SINGBOX_LOG" >&2
  else
    SINGBOX_FAIL_LOG="$(make_temp_log singbox-start-fail)"
    capture_start_failure "$SINGBOX_FAIL_LOG" "$SINGBOX_BIN" run -c "$SINGBOX_CONFIG"
    echo "sing-box завершился сразу после старта. Диагностика сохранена в: $SINGBOX_FAIL_LOG" >&2
  fi
  sudo kill "$XRAY_PID" 2>/dev/null || true
  exit 1
fi

ip link show tun0 >/dev/null

if [[ "$ENABLE_FILE_LOGS" != "1" ]]; then
  rm -f "$XRAY_CHECK_LOG" "$SINGBOX_CHECK_LOG"
fi

echo "[5/7] Настройка системного DNS"
backup_resolv_conf
write_runtime_resolv_conf

echo "[6/7] Сохранение состояния"
printf 'XRAY_PID=%s\nSINGBOX_PID=%s\nRESOLV_BACKUP=%s\n' \
  "$XRAY_PID" \
  "$SINGBOX_PID" \
  "$RESOLV_BACKUP" \
  >"$STATE_FILE"

echo "[7/7] Готово"
echo "XRAY_PID=$XRAY_PID"
echo "SINGBOX_PID=$SINGBOX_PID"
echo "RESOLV_BACKUP=$RESOLV_BACKUP"
if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
  echo "Лог Xray: $XRAY_LOG"
  echo "Лог sing-box: $SINGBOX_LOG"
else
  echo "Файловые логи отключены"
fi
echo "Для отката используй: ${SCRIPT_DIR}/stop-xray-tun-subvost.sh"
