#!/usr/bin/env bash

subvost_die() {
  echo "$*" >&2
  exit 1
}

subvost_ensure_absolute_path() {
  local path_value="$1"
  local label="$2"
  if [[ "$path_value" != /* ]]; then
    subvost_die "${label} должен быть абсолютным путём: ${path_value}"
  fi
}

subvost_require_existing_dir() {
  local dir_path="$1"
  [[ -d "$dir_path" ]] || subvost_die "Каталог не найден: ${dir_path}"
}

subvost_resolve_project_root_from_entrypoint() {
  local script_path="$1"
  local script_dir
  script_dir="$(cd -P -- "$(dirname -- "$script_path")" && pwd)"
  printf '%s\n' "$script_dir"
}

subvost_load_project_layout_from_env() {
  local project_root="${SUBVOST_PROJECT_ROOT:-}"

  [[ -n "$project_root" ]] || subvost_die "Не передан SUBVOST_PROJECT_ROOT."
  subvost_ensure_absolute_path "$project_root" "SUBVOST_PROJECT_ROOT"
  subvost_require_existing_dir "$project_root"

  export SUBVOST_PROJECT_ROOT="$project_root"
  export SUBVOST_LIB_DIR="${project_root}/lib"
  export SUBVOST_LIBEXEC_DIR="${project_root}/libexec"
  export SUBVOST_GUI_DIR="${project_root}/gui"
  export SUBVOST_DOCS_DIR="${project_root}/docs"
  export SUBVOST_ASSETS_DIR="${project_root}/assets"
  export SUBVOST_LOG_DIR="${project_root}/logs"
  export SUBVOST_XRAY_CONFIG_PATH="${project_root}/xray-tun-subvost.json"
  export SUBVOST_SINGBOX_CONFIG_PATH="${project_root}/singbox-tun-subvost.json"
  export SUBVOST_RUN_WRAPPER="${project_root}/run-xray-tun-subvost.sh"
  export SUBVOST_STOP_WRAPPER="${project_root}/stop-xray-tun-subvost.sh"
  export SUBVOST_CAPTURE_WRAPPER="${project_root}/capture-xray-tun-state.sh"
  export SUBVOST_OPEN_GUI_WRAPPER="${project_root}/open-subvost-gui.sh"
  export SUBVOST_INSTALL_WRAPPER="${project_root}/install-on-new-pc.sh"
  export SUBVOST_DESKTOP_LAUNCHER="${project_root}/subvost-xray-tun.desktop"
  export SUBVOST_DESKTOP_ICON_PATH="${project_root}/assets/subvost-xray-tun-icon.svg"
}

subvost_export_project_layout() {
  local project_root="$1"
  export SUBVOST_PROJECT_ROOT="$project_root"
  subvost_load_project_layout_from_env
}

subvost_find_executable() {
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

subvost_sync_desktop_launcher_icon() {
  local desktop_file="${SUBVOST_DESKTOP_LAUNCHER:-}"
  local icon_path="${SUBVOST_DESKTOP_ICON_PATH:-}"
  local tmp_file

  [[ -n "$desktop_file" ]] || return 0
  [[ -n "$icon_path" ]] || return 0
  [[ -f "$desktop_file" ]] || return 0
  [[ -f "$icon_path" ]] || return 0
  [[ -w "$desktop_file" ]] || return 0

  tmp_file="$(mktemp "${desktop_file}.tmp.XXXXXX")"
  SUBVOST_SYNC_ICON_PATH="$icon_path" awk '
    BEGIN {
      replaced = 0
    }
    /^Icon=/ {
      print "Icon=" ENVIRON["SUBVOST_SYNC_ICON_PATH"]
      replaced = 1
      next
    }
    {
      print
    }
    END {
      if (!replaced) {
        print "Icon=" ENVIRON["SUBVOST_SYNC_ICON_PATH"]
      }
    }
  ' "$desktop_file" > "$tmp_file"

  if cmp -s -- "$desktop_file" "$tmp_file"; then
    rm -f -- "$tmp_file"
    return 0
  fi

  chmod --reference="$desktop_file" "$tmp_file"
  mv -- "$tmp_file" "$desktop_file"
}
