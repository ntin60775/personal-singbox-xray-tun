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

subvost_resolve_real_config_home() {
  local real_home="$1"
  local explicit_config_home="${SUBVOST_REAL_XDG_CONFIG_HOME:-}"

  if [[ -n "$explicit_config_home" ]]; then
    subvost_ensure_absolute_path "$explicit_config_home" "SUBVOST_REAL_XDG_CONFIG_HOME"
    printf '%s\n' "$explicit_config_home"
    return 0
  fi

  if [[ "${EUID:-$(id -u)}" -ne 0 ]] && [[ -n "${XDG_CONFIG_HOME:-}" ]] && [[ "${XDG_CONFIG_HOME}" == /* ]]; then
    printf '%s\n' "${XDG_CONFIG_HOME}"
    return 0
  fi

  printf '%s\n' "${real_home}/.config"
}

subvost_resolve_store_dir_for_home() {
  local real_home="$1"
  local config_home

  config_home="$(subvost_resolve_real_config_home "$real_home")"
  printf '%s\n' "${config_home}/subvost-xray-tun"
}

subvost_resolve_store_file_for_home() {
  local real_home="$1"
  local store_dir

  store_dir="$(subvost_resolve_store_dir_for_home "$real_home")"
  printf '%s\n' "${store_dir}/store.json"
}

subvost_resolve_generated_xray_config_for_home() {
  local real_home="$1"
  local store_dir

  store_dir="$(subvost_resolve_store_dir_for_home "$real_home")"
  printf '%s\n' "${store_dir}/generated-xray-config.json"
}

subvost_resolve_active_runtime_xray_config_for_home() {
  local real_home="$1"
  local store_dir

  store_dir="$(subvost_resolve_store_dir_for_home "$real_home")"
  printf '%s\n' "${store_dir}/active-runtime-xray-config.json"
}

subvost_store_has_active_selection() {
  local store_file="$1"

  if [[ ! -f "$store_file" ]]; then
    return 1
  fi

  python3 - "$store_file" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
except Exception:
    raise SystemExit(1)

selection = payload.get("active_selection", {})
profile_id = selection.get("profile_id")
node_id = selection.get("node_id")
raise SystemExit(0 if profile_id and node_id else 1)
PY
}

subvost_store_prefers_generated_xray_config() {
  local store_file="$1"

  if [[ ! -f "$store_file" ]]; then
    return 1
  fi

  python3 - "$store_file" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
except Exception:
    raise SystemExit(1)

selection = payload.get("active_selection", {}) or {}
has_selection = bool(selection.get("profile_id") and selection.get("node_id"))
runtime_preference = str(payload.get("runtime_preference") or "").strip().lower()

if runtime_preference == "builtin":
    raise SystemExit(1)
if runtime_preference == "store":
    raise SystemExit(0 if has_selection else 1)

raise SystemExit(0 if has_selection else 1)
PY
}

subvost_resolve_active_xray_config_for_home() {
  local real_home="$1"
  local fallback_xray_config="$2"
  local store_file
  local generated_xray_config

  store_file="$(subvost_resolve_store_file_for_home "$real_home")"
  generated_xray_config="$(subvost_resolve_generated_xray_config_for_home "$real_home")"

  if [[ -f "$generated_xray_config" ]] && subvost_store_prefers_generated_xray_config "$store_file"; then
    printf '%s\n' "$generated_xray_config"
    return 0
  fi

  printf '%s\n' "$fallback_xray_config"
}

subvost_resolve_active_xray_source_for_home() {
  local real_home="$1"
  local fallback_xray_config="$2"
  local resolved_config

  resolved_config="$(subvost_resolve_active_xray_config_for_home "$real_home" "$fallback_xray_config")"
  if [[ "$resolved_config" == "$fallback_xray_config" ]]; then
    printf '%s\n' "builtin"
    return 0
  fi

  printf '%s\n' "store"
}
