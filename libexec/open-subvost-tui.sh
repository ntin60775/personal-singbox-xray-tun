#!/usr/bin/env bash
set -euo pipefail

INTERNAL_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${INTERNAL_DIR}/../lib/subvost-common.sh"
subvost_load_project_layout_from_env

REAL_USER="${USER:-$(id -un)}"
REAL_HOME="${HOME:-$(getent passwd "$REAL_USER" | cut -d: -f6)}"

export SUBVOST_PROJECT_ROOT="${SUBVOST_PROJECT_ROOT}"
export SUBVOST_REAL_USER="${REAL_USER}"
export SUBVOST_REAL_HOME="${REAL_HOME}"
export SUBVOST_REAL_XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${REAL_HOME}/.config}"

# Bootstrap: проверить зависимости
if ! python3 "${SUBVOST_GUI_DIR}/tui_bootstrap.py" --check-only 2>/dev/null; then
  echo "Зависимости не удовлетворены. Запускаю bootstrap..."
  python3 "${SUBVOST_GUI_DIR}/tui_bootstrap.py" || {
    echo "Bootstrap завершился ошибкой. Завершение." >&2
    exit 1
  }
fi

# Запуск TUI
exec python3 "${SUBVOST_GUI_DIR}/tui_app.py" "$@"
