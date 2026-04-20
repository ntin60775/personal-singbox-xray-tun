#!/usr/bin/env bash
set -euo pipefail

INTERNAL_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${INTERNAL_DIR}/../lib/subvost-common.sh"
subvost_load_project_layout_from_env

XRAY_INSTALL_REF="${XRAY_INSTALL_REF:-main}"
XRAY_INSTALL_URL="https://raw.githubusercontent.com/XTLS/Xray-install/${XRAY_INSTALL_REF}/install-release.sh"
REAL_USER="${SUDO_USER:-${SUBVOST_REAL_USER:-${USER:-$(id -un)}}}"
REAL_HOME="$(
  getent passwd "$REAL_USER" | cut -d: -f6
)"
TUN_INTERFACE_NAME="${TUN_INTERFACE_NAME:-tun0}"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Не найдена обязательная команда: $cmd" >&2
    exit 1
  fi
}

ensure_real_home_detected() {
  if [[ -z "$REAL_HOME" ]]; then
    echo "Не удалось определить домашний каталог пользователя ${REAL_USER}" >&2
    exit 1
  fi
}

reexec_with_pkexec_if_needed() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi

  require_cmd pkexec
  exec pkexec env \
    "SUDO_USER=${REAL_USER}" \
    "USER=${REAL_USER}" \
    "LOGNAME=${REAL_USER}" \
    "HOME=${REAL_HOME}" \
    "SUBVOST_PROJECT_ROOT=${SUBVOST_PROJECT_ROOT}" \
    "SUBVOST_REAL_USER=${REAL_USER}" \
    "SUBVOST_REAL_HOME=${REAL_HOME}" \
    "XRAY_INSTALL_REF=${XRAY_INSTALL_REF}" \
    "TUN_INTERFACE_NAME=${TUN_INTERFACE_NAME}" \
    /usr/bin/env bash "$0" "$@"
}

xray_install_artifact_paths() {
  cat <<'EOF'
/etc/systemd/system/xray.service
/etc/systemd/system/xray.service.d/10-donot_touch_single_conf.conf
/etc/systemd/system/xray@.service
/etc/systemd/system/xray@.service.d/10-donot_touch_single_conf.conf
/etc/systemd/system/multi-user.target.wants/xray.service
/usr/local/etc/xray/config.json
EOF
}

remove_path_if_present() {
  local target_path="$1"
  if [[ -e "$target_path" || -L "$target_path" ]]; then
    rm -f -- "$target_path"
  fi
}

remove_dir_if_empty() {
  local dir_path="$1"
  if [[ -d "$dir_path" ]] && ! find "$dir_path" -mindepth 1 -print -quit | grep -q .; then
    rmdir --ignore-fail-on-non-empty -- "$dir_path" 2>/dev/null || true
  fi
}

cleanup_xray_install_artifacts() {
  echo "Приведение Xray-install к переносимому режиму приложения"

  if command -v systemctl >/dev/null 2>&1; then
    systemctl disable --now xray.service >/dev/null 2>&1 || true
  fi

  while IFS= read -r artifact_path; do
    [[ -n "$artifact_path" ]] || continue
    remove_path_if_present "$artifact_path"
  done < <(xray_install_artifact_paths)

  if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload >/dev/null 2>&1 || true
    systemctl reset-failed xray.service >/dev/null 2>&1 || true
  fi

  remove_dir_if_empty "/etc/systemd/system/xray.service.d"
  remove_dir_if_empty "/etc/systemd/system/xray@.service.d"
  remove_dir_if_empty "/usr/local/etc/xray"
}

preferred_xray_bin() {
  subvost_find_executable \
    "/usr/local/bin/xray" \
    "/usr/bin/xray" \
    "${REAL_HOME}/.local/bin/xray" \
    "$(command -v xray 2>/dev/null || true)" \
  || true
}

print_xray_version() {
  local label="$1"
  local xray_bin
  xray_bin="$(preferred_xray_bin)"

  echo "${label}:"
  if [[ -n "$xray_bin" && -x "$xray_bin" ]]; then
    "$xray_bin" version | sed -n '1,2p'
  else
    echo "xray не найден"
  fi
}

dedupe_xray_binaries() {
  local user_xray="${REAL_HOME}/.local/bin/xray"
  local system_xray=""

  system_xray="$(
    subvost_find_executable \
      "/usr/local/bin/xray" \
      "/usr/bin/xray" \
    || true
  )"

  if [[ ! -x "$user_xray" ]] || [[ -z "$system_xray" ]]; then
    return 0
  fi

  if cmp -s -- "$user_xray" "$system_xray"; then
    rm -f -- "$user_xray"
    echo "Удалён дубликат Xray: ${user_xray}"
    return 0
  fi

  echo "Обнаружены два разных бинарника Xray: ${user_xray} и ${system_xray}" >&2
  echo "Автоочистка остановлена: приложение не будет молча выбирать между разными версиями." >&2
  exit 1
}

ensure_runtime_stopped_for_manual_run() {
  if pgrep -xaf 'xray .*run' >/dev/null 2>&1; then
    echo "Обнаружен запущенный процесс Xray. Отключи подключение перед обновлением ядра." >&2
    exit 1
  fi

  if ip link show "$TUN_INTERFACE_NAME" >/dev/null 2>&1; then
    echo "Обнаружен интерфейс ${TUN_INTERFACE_NAME}. Отключи подключение перед обновлением ядра." >&2
    exit 1
  fi
}

ensure_real_home_detected
reexec_with_pkexec_if_needed "$@"
require_cmd curl
require_cmd ip

echo "[1/4] Проверка, что подключение остановлено"
ensure_runtime_stopped_for_manual_run
print_xray_version "Версия Xray до обновления"

echo
echo "[2/4] Обновление Xray через официальный Xray-install"
curl -fsSL "$XRAY_INSTALL_URL" | bash -s -- install

echo
echo "[3/4] Очистка лишних артефактов Xray-install"
cleanup_xray_install_artifacts
dedupe_xray_binaries

echo
echo "[4/4] Проверка результата"
print_xray_version "Версия Xray после обновления"

echo
echo "Обновление ядра Xray завершено."
