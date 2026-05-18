#!/usr/bin/env bash
# Враппер для .desktop-ярлыка: переходит в каталог проекта и запускает TUI
set -euo pipefail
DESKTOP_FILE="$1"
cd "$(dirname "$DESKTOP_FILE")"
exec ./open-subvost-tui.sh
