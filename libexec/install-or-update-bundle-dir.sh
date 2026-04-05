#!/usr/bin/env bash
set -euo pipefail

INTERNAL_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${INTERNAL_DIR}/../lib/subvost-common.sh"
subvost_load_project_layout_from_env

usage() {
  cat <<'EOF'
Использование:
  bash ./install-or-update-bundle-dir.sh /абсолютный/путь/к/каталогу

Или:
  SUBVOST_BUNDLE_TARGET_DIR=/абсолютный/путь bash ./install-or-update-bundle-dir.sh

Сценарий копирует bundle в целевой каталог без жёстко зашитых путей.
Локальные repo-артефакты (`.git`, `.codex`, `.playwright-cli`, `.gitignore`) и содержимое `logs/` не переносятся.
Существующий каталог `logs/` в целевом bundle сохраняется.
EOF
}

require_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || subvost_die "Не найдена обязательная команда: ${cmd}"
}

resolve_target_dir() {
  local cli_target="${1:-}"
  local env_target="${SUBVOST_BUNDLE_TARGET_DIR:-}"

  if [[ -n "$cli_target" ]] && [[ -n "$env_target" ]]; then
    subvost_die "Укажи target path либо аргументом, либо через SUBVOST_BUNDLE_TARGET_DIR."
  fi

  if [[ -n "$cli_target" ]]; then
    printf '%s\n' "$cli_target"
    return 0
  fi

  if [[ -n "$env_target" ]]; then
    printf '%s\n' "$env_target"
    return 0
  fi

  return 1
}

assert_safe_target() {
  local source_root="$1"
  local target_dir="$2"
  local source_real
  local target_real_parent

  source_real="$(readlink -f -- "$source_root")"
  [[ -d "$(dirname -- "$target_dir")" ]] || subvost_die "Родительский каталог target path не найден: $(dirname -- "$target_dir")"
  target_real_parent="$(readlink -f -- "$(dirname -- "$target_dir")")"
  target_dir="${target_real_parent}/$(basename -- "$target_dir")"

  if [[ "$target_dir" == "$source_real" ]]; then
    subvost_die "Целевой каталог совпадает с текущим bundle: ${target_dir}"
  fi

  if [[ "$target_dir" == "${source_real}/"* ]]; then
    subvost_die "Целевой каталог не должен находиться внутри исходного bundle: ${target_dir}"
  fi
}

copy_bundle_tree() {
  local source_root="$1"
  local target_dir="$2"

  (
    cd "$source_root"
    tar \
      --exclude='./.git' \
      --exclude='./.codex' \
      --exclude='./.playwright-cli' \
      --exclude='./.gitignore' \
      --exclude='./AGENTS.md' \
      --exclude='./logs' \
      --exclude='*/__pycache__' \
      --exclude='*/.pytest_cache' \
      --exclude='*/.mypy_cache' \
      --exclude='*.pyc' \
      -cf - .
  ) | (
    cd "$target_dir"
    tar -xf -
  )
}

TARGET_DIR=""
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "$#" -gt 1 ]]; then
  usage >&2
  subvost_die "Ожидался один target path."
fi

TARGET_DIR="$(resolve_target_dir "${1:-}")" || {
  usage >&2
  exit 1
}

subvost_ensure_absolute_path "$TARGET_DIR" "TARGET_DIR"
require_cmd tar
require_cmd readlink

assert_safe_target "$SUBVOST_PROJECT_ROOT" "$TARGET_DIR"
mkdir -p "$TARGET_DIR"

echo "Синхронизация bundle в целевой каталог"
echo "Источник: ${SUBVOST_PROJECT_ROOT}"
echo "Цель: ${TARGET_DIR}"

mkdir -p "${TARGET_DIR}/logs"
copy_bundle_tree "$SUBVOST_PROJECT_ROOT" "$TARGET_DIR"

subvost_export_project_layout "$TARGET_DIR"
subvost_sync_desktop_launcher_icon

echo
echo "Bundle синхронизирован."
echo "Содержимое logs/ в целевом каталоге сохранено."
echo "При первом развёртывании на новой машине при необходимости выполни:"
echo "  bash \"${TARGET_DIR}/install-on-new-pc.sh\""
echo "  bash \"${TARGET_DIR}/install-subvost-gui-menu-entry.sh\""
