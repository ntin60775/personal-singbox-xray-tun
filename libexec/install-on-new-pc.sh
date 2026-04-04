#!/usr/bin/env bash
set -euo pipefail

INTERNAL_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${INTERNAL_DIR}/../lib/subvost-common.sh"
subvost_load_project_layout_from_env

XRAY_INSTALL_REF="${XRAY_INSTALL_REF:-main}"
XRAY_INSTALL_URL="https://raw.githubusercontent.com/XTLS/Xray-install/${XRAY_INSTALL_REF}/install-release.sh"
REAL_USER="${SUDO_USER:-${USER:-$(id -un)}}"
REAL_HOME="$(
  getent passwd "$REAL_USER" | cut -d: -f6
)"

run_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

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
    run_root rm -f -- "$target_path"
  fi
}

remove_dir_if_empty() {
  local dir_path="$1"
  if [[ -d "$dir_path" ]] && ! find "$dir_path" -mindepth 1 -print -quit | grep -q .; then
    run_root rmdir --ignore-fail-on-non-empty -- "$dir_path" 2>/dev/null || true
  fi
}

cleanup_xray_install_artifacts() {
  echo "Приведение Xray-install к portable-режиму bundle"

  if command -v systemctl >/dev/null 2>&1; then
    run_root systemctl disable --now xray.service >/dev/null 2>&1 || true
  fi

  while IFS= read -r artifact_path; do
    [[ -n "$artifact_path" ]] || continue
    remove_path_if_present "$artifact_path"
  done < <(xray_install_artifact_paths)

  if command -v systemctl >/dev/null 2>&1; then
    run_root systemctl daemon-reload >/dev/null 2>&1 || true
    run_root systemctl reset-failed xray.service >/dev/null 2>&1 || true
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
  echo "Автоочистка остановлена: bundle не будет молча выбирать между разными версиями." >&2
  echo "Либо удалите/переименуйте лишний бинарник вручную, либо запустите installer с XRAY_BIN на нужный путь." >&2
  exit 1
}

ensure_real_home_detected
echo "[1/4] Проверка базовых системных утилит"
if command -v apt-get >/dev/null 2>&1; then
  run_root apt-get update
  run_root apt-get install -y ca-certificates curl iproute2 python3 sudo unzip
else
  echo "Скрипт установки пока поддерживает только Debian/Ubuntu с apt-get." >&2
  echo "Установи зависимости вручную: curl, unzip, iproute2, python3, sudo, xray." >&2
  exit 1
fi

require_cmd curl

echo "[2/5] Установка Xray"
curl -fsSL "$XRAY_INSTALL_URL" | run_root bash -s -- install

echo "[3/5] Очистка лишних артефактов Xray-install"
cleanup_xray_install_artifacts
dedupe_xray_binaries

echo "[4/4] Проверка установленных бинарников"
XRAY_BIN_INSTALLED="$(preferred_xray_bin)"
if [[ -n "$XRAY_BIN_INSTALLED" ]] && [[ -x "$XRAY_BIN_INSTALLED" ]]; then
  echo "Xray найден: ${XRAY_BIN_INSTALLED}"
else
  echo "Xray не найден в PATH после установки." >&2
  exit 1
fi

echo
echo "Зависимости установлены. Bundle не копировался."
echo "Запускай bundle из текущего каталога:"
echo "  ${SUBVOST_RUN_WRAPPER}"
