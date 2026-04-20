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
  export SUBVOST_RUN_WRAPPER="${project_root}/run-xray-tun-subvost.sh"
  export SUBVOST_STOP_WRAPPER="${project_root}/stop-xray-tun-subvost.sh"
  export SUBVOST_CAPTURE_WRAPPER="${project_root}/capture-xray-tun-state.sh"
  export SUBVOST_UPDATE_XRAY_WRAPPER="${project_root}/update-xray-core-subvost.sh"
  export SUBVOST_OPEN_GUI_WRAPPER="${project_root}/open-subvost-gui.sh"
  export SUBVOST_OPEN_GTK_UI_WRAPPER="${project_root}/open-subvost-gtk-ui.sh"
  export SUBVOST_INSTALL_WRAPPER="${project_root}/install-on-new-pc.sh"
  export SUBVOST_DESKTOP_LAUNCHER="${project_root}/subvost-xray-tun.desktop"
  export SUBVOST_GTK_DESKTOP_LAUNCHER="${project_root}/subvost-xray-tun-gtk-ui.desktop"
  export SUBVOST_DESKTOP_ICON_NAME="subvost-xray-tun-icon"
  export SUBVOST_DESKTOP_ICON_PATH="${project_root}/assets/subvost-xray-tun-icon.svg"
  export SUBVOST_INSTALL_STATE_DIR="${project_root}/.subvost"
  export SUBVOST_INSTALL_ID_FILE="${project_root}/.subvost/install-id"
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

subvost_generate_install_id() {
  local generated=""

  if [[ -r /proc/sys/kernel/random/uuid ]]; then
    generated="$(tr '[:upper:]' '[:lower:]' </proc/sys/kernel/random/uuid)"
  elif command -v uuidgen >/dev/null 2>&1; then
    generated="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  elif command -v python3 >/dev/null 2>&1; then
    generated="$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)"
  else
    generated="subvost-$(date +%s)-$$"
  fi

  printf '%s\n' "$generated"
}

subvost_validate_install_id() {
  local install_id="$1"
  [[ "$install_id" =~ ^[a-z0-9][a-z0-9._:-]{7,127}$ ]]
}

subvost_read_install_id_file() {
  local install_id_file="$1"
  local install_id=""

  [[ -f "$install_id_file" ]] || return 1
  IFS= read -r install_id <"$install_id_file" || install_id=""
  subvost_validate_install_id "$install_id" || subvost_die "Некорректный install-id установки: ${install_id_file}"
  printf '%s\n' "$install_id"
}

subvost_ensure_install_id() {
  local install_id_file="${1:-${SUBVOST_INSTALL_ID_FILE:-}}"
  local install_id_dir
  local install_id
  local tmp_file

  [[ -n "$install_id_file" ]] || subvost_die "Не передан путь к install-id установки."
  subvost_ensure_absolute_path "$install_id_file" "SUBVOST_INSTALL_ID_FILE"

  if [[ -f "$install_id_file" ]]; then
    subvost_read_install_id_file "$install_id_file"
    return 0
  fi

  install_id_dir="$(dirname -- "$install_id_file")"
  mkdir -p "$install_id_dir" || subvost_die "Не удалось создать каталог install-id: ${install_id_dir}"

  install_id="$(subvost_generate_install_id)"
  subvost_validate_install_id "$install_id" || subvost_die "Не удалось сгенерировать корректный install-id."

  tmp_file="$(mktemp "${install_id_dir}/install-id.tmp.XXXXXX")"
  printf '%s\n' "$install_id" >"$tmp_file"
  chmod 0600 "$tmp_file" 2>/dev/null || true
  mv -- "$tmp_file" "$install_id_file"
  printf '%s\n' "$install_id"
}

subvost_resolve_real_user_name() {
  if [[ -n "${SUBVOST_REAL_USER:-}" ]]; then
    printf '%s\n' "${SUBVOST_REAL_USER}"
    return 0
  fi

  if [[ -n "${SUDO_USER:-}" ]]; then
    printf '%s\n' "${SUDO_USER}"
    return 0
  fi

  if [[ -n "${USER:-}" ]]; then
    printf '%s\n' "${USER}"
    return 0
  fi

  id -un
}

subvost_resolve_real_home() {
  local explicit_home="${SUBVOST_REAL_HOME:-}"
  local real_user
  local real_home

  if [[ -n "$explicit_home" ]]; then
    subvost_ensure_absolute_path "$explicit_home" "SUBVOST_REAL_HOME"
    printf '%s\n' "$explicit_home"
    return 0
  fi

  if [[ "${EUID:-$(id -u)}" -ne 0 ]] && [[ -n "${HOME:-}" ]] && [[ "${HOME}" == /* ]]; then
    printf '%s\n' "${HOME}"
    return 0
  fi

  real_user="$(subvost_resolve_real_user_name)"
  real_home="$(getent passwd "$real_user" | cut -d: -f6)"
  [[ -n "$real_home" ]] || return 1
  subvost_ensure_absolute_path "$real_home" "REAL_HOME"
  printf '%s\n' "$real_home"
}

subvost_resolve_real_data_home() {
  local real_home="$1"
  local explicit_data_home="${SUBVOST_REAL_XDG_DATA_HOME:-}"

  if [[ -n "$explicit_data_home" ]]; then
    subvost_ensure_absolute_path "$explicit_data_home" "SUBVOST_REAL_XDG_DATA_HOME"
    printf '%s\n' "$explicit_data_home"
    return 0
  fi

  if [[ "${EUID:-$(id -u)}" -ne 0 ]] && [[ -n "${XDG_DATA_HOME:-}" ]] && [[ "${XDG_DATA_HOME}" == /* ]]; then
    printf '%s\n' "${XDG_DATA_HOME}"
    return 0
  fi

  printf '%s\n' "${real_home}/.local/share"
}

subvost_sync_desktop_icon_value() {
  local desktop_file="$1"
  local icon_value="$2"
  local tmp_file

  [[ -n "$desktop_file" ]] || return 0
  [[ -n "$icon_value" ]] || return 0
  [[ -f "$desktop_file" ]] || return 0
  [[ -w "$desktop_file" ]] || return 0

  tmp_file="$(mktemp "${desktop_file}.tmp.XXXXXX")"
  SUBVOST_SYNC_ICON_VALUE="$icon_value" awk '
    BEGIN {
      replaced = 0
    }
    /^Icon=/ {
      print "Icon=" ENVIRON["SUBVOST_SYNC_ICON_VALUE"]
      replaced = 1
      next
    }
    {
      print
    }
    END {
      if (!replaced) {
        print "Icon=" ENVIRON["SUBVOST_SYNC_ICON_VALUE"]
      }
    }
  ' "$desktop_file" > "$tmp_file"

  if cmp -s -- "$desktop_file" "$tmp_file"; then
    rm -f -- "$tmp_file"
    touch -c -- "$desktop_file" 2>/dev/null || true
    return 0
  fi

  chmod --reference="$desktop_file" "$tmp_file"
  mv -- "$tmp_file" "$desktop_file"
}

subvost_refresh_icon_theme_cache() {
  local icon_theme_root="$1"

  [[ -n "$icon_theme_root" ]] || return 0
  [[ -d "$icon_theme_root" ]] || return 0
  command -v gtk-update-icon-cache >/dev/null 2>&1 || return 0

  gtk-update-icon-cache -f -t "$icon_theme_root" >/dev/null 2>&1 || true
}

subvost_sync_desktop_launcher_icon() {
  local desktop_file="${SUBVOST_DESKTOP_LAUNCHER:-}"
  local gtk_desktop_file="${SUBVOST_GTK_DESKTOP_LAUNCHER:-}"
  local icon_path="${SUBVOST_DESKTOP_ICON_PATH:-}"
  local icon_name="${SUBVOST_DESKTOP_ICON_NAME:-}"
  local real_home
  local data_home
  local icon_theme_root
  local icon_dir
  local icon_link_path
  local installed_desktop_file
  local installed_gtk_desktop_file

  [[ -n "$icon_name" ]] || return 0
  [[ -n "$icon_path" ]] || return 0
  [[ -f "$icon_path" ]] || return 0

  real_home="$(subvost_resolve_real_home)" || return 0
  data_home="$(subvost_resolve_real_data_home "$real_home")" || return 0
  icon_theme_root="${data_home}/icons/hicolor"
  icon_dir="${icon_theme_root}/scalable/apps"
  icon_link_path="${icon_dir}/${icon_name}.svg"
  installed_desktop_file="${data_home}/applications/subvost-xray-tun.desktop"
  installed_gtk_desktop_file="${data_home}/applications/subvost-xray-tun-gtk-ui.desktop"

  mkdir -p "$icon_dir" 2>/dev/null || return 0
  ln -sfn -- "$icon_path" "$icon_link_path" 2>/dev/null || return 0
  subvost_refresh_icon_theme_cache "$icon_theme_root"

  subvost_sync_desktop_icon_value "$desktop_file" "$icon_name"
  subvost_sync_desktop_icon_value "$gtk_desktop_file" "$icon_name"
  subvost_sync_desktop_icon_value "$installed_desktop_file" "$icon_name"
  subvost_sync_desktop_icon_value "$installed_gtk_desktop_file" "$icon_name"
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

subvost_resolve_xray_asset_dir_for_home() {
  local real_home="$1"
  local store_dir

  store_dir="$(subvost_resolve_store_dir_for_home "$real_home")"
  printf '%s\n' "${store_dir}/xray-assets"
}

subvost_resolve_geoip_asset_for_home() {
  local real_home="$1"
  local asset_dir

  asset_dir="$(subvost_resolve_xray_asset_dir_for_home "$real_home")"
  printf '%s\n' "${asset_dir}/geoip.dat"
}

subvost_resolve_geosite_asset_for_home() {
  local real_home="$1"
  local asset_dir

  asset_dir="$(subvost_resolve_xray_asset_dir_for_home "$real_home")"
  printf '%s\n' "${asset_dir}/geosite.dat"
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

subvost_resolve_active_xray_config_for_home() {
  local real_home="$1"
  local generated_xray_config

  generated_xray_config="$(subvost_resolve_generated_xray_config_for_home "$real_home")"
  printf '%s\n' "$generated_xray_config"
}
