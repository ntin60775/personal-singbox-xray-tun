#!/usr/bin/env bash
# Запускает TUI в kitty (если установлен) или в доступном системном терминале
set -euo pipefail

INTERNAL_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${INTERNAL_DIR}/../lib/subvost-common.sh"
subvost_load_project_layout_from_env

# Installer ставит xray в ~/.local/bin; убедимся, что она в PATH
export PATH="${HOME}/.local/bin:${PATH}"

HOLD_WRAPPER="${INTERNAL_DIR}/_tui-error-holder.sh"

# Приоритет: kitty
if command -v kitty >/dev/null 2>&1; then
  exec kitty --single-instance --directory="${SUBVOST_PROJECT_ROOT}" "$HOLD_WRAPPER" "${SUBVOST_OPEN_TUI_WRAPPER}"
fi

# Fallback: Debian-альтернатива (Cinnamon/Mint/Ubuntu)
if command -v x-terminal-emulator >/dev/null 2>&1; then
  exec x-terminal-emulator -e "$HOLD_WRAPPER '${SUBVOST_OPEN_TUI_WRAPPER}'"
fi

# Fallback: перебор известных терминалов
for term in gnome-terminal xfce4-terminal mate-terminal konsole lxterminal alacritty wezterm terminator terminology exo-open; do
  if command -v "$term" >/dev/null 2>&1; then
    case "$term" in
      gnome-terminal)
        exec gnome-terminal -- "$HOLD_WRAPPER" "${SUBVOST_OPEN_TUI_WRAPPER}"
        ;;
      exo-open)
        exec exo-open --launch TerminalEmulator -- "$HOLD_WRAPPER" "${SUBVOST_OPEN_TUI_WRAPPER}"
        ;;
      konsole)
        exec konsole -e "$HOLD_WRAPPER" "${SUBVOST_OPEN_TUI_WRAPPER}"
        ;;
      xfce4-terminal|mate-terminal|lxterminal|terminology|terminator|alacritty|wezterm)
        exec "$term" -e "$HOLD_WRAPPER '${SUBVOST_OPEN_TUI_WRAPPER}'"
        ;;
    esac
  fi
done

echo "Ошибка: не найден подходящий терминал для запуска TUI" >&2
exit 1
