#!/usr/bin/env bash
set -euo pipefail

INTERNAL_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${INTERNAL_DIR}/../lib/subvost-common.sh"
subvost_load_project_layout_from_env

REAL_USER="${SUDO_USER:-${USER:-$(id -un)}}"
REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
APPLICATIONS_DIR="${REAL_HOME}/.local/share/applications"
DESKTOP_ENTRY_PATH="${APPLICATIONS_DIR}/subvost-xray-tun.desktop"
ICON_PATH="${SUBVOST_ASSETS_DIR}/subvost-xray-tun-icon.svg"
LAUNCHER_PATH="${SUBVOST_OPEN_GUI_WRAPPER}"

ensure_real_home_detected() {
  if [[ -z "$REAL_HOME" ]]; then
    echo "Не удалось определить домашний каталог пользователя ${REAL_USER}" >&2
    exit 1
  fi
}

ensure_runtime_paths() {
  subvost_ensure_absolute_path "$APPLICATIONS_DIR" "APPLICATIONS_DIR"
  subvost_ensure_absolute_path "$DESKTOP_ENTRY_PATH" "DESKTOP_ENTRY_PATH"
  subvost_ensure_absolute_path "$ICON_PATH" "ICON_PATH"
  subvost_ensure_absolute_path "$LAUNCHER_PATH" "LAUNCHER_PATH"

  [[ -x "$LAUNCHER_PATH" ]] || subvost_die "Не найден launcher GUI: ${LAUNCHER_PATH}"
  [[ -f "$ICON_PATH" ]] || subvost_die "Не найдена иконка bundle: ${ICON_PATH}"
}

write_desktop_entry() {
  mkdir -p "$APPLICATIONS_DIR"
  cat >"$DESKTOP_ENTRY_PATH" <<EOF_DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=Subvost Xray TUN GUI
Comment=Запуск локального GUI для управления туннелем
Exec=/usr/bin/env python3 -c "import os, sys; os.execv(sys.argv[1], [sys.argv[1]])" "${LAUNCHER_PATH}"
TryExec=${LAUNCHER_PATH}
Icon=${ICON_PATH}
Terminal=false
Categories=Network;
StartupNotify=true
EOF_DESKTOP
  chmod 0644 "$DESKTOP_ENTRY_PATH"
}

refresh_desktop_database() {
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
  fi
}

ensure_real_home_detected
ensure_runtime_paths
write_desktop_entry
refresh_desktop_database

echo "Ярлык установлен в меню приложений:"
echo "  ${DESKTOP_ENTRY_PATH}"
echo "Если каталог bundle будет перемещён, переустанови ярлык этой же командой."
