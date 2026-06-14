#!/usr/bin/env bash
set -euo pipefail

INTERNAL_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${INTERNAL_DIR}/../lib/subvost-common.sh"
subvost_load_project_layout_from_env

LOG_DIR="${SUBVOST_LOG_DIR}"
REAL_USER="${SUDO_USER:-${USER:-$(id -un)}}"
REAL_HOME="$(
  getent passwd "$REAL_USER" | cut -d: -f6
)"
REAL_UID="$(id -u "$REAL_USER")"
REAL_GID="$(id -g "$REAL_USER")"

if [[ -z "$REAL_HOME" ]]; then
  echo "Не удалось определить домашний каталог пользователя ${REAL_USER}" >&2
  exit 1
fi

ACTIVE_XRAY_CONFIG_DEFAULT="$(subvost_resolve_active_xray_config_for_home "$REAL_HOME")"
ACTIVE_RUNTIME_XRAY_CONFIG_DEFAULT="$(subvost_resolve_active_runtime_xray_config_for_home "$REAL_HOME")"
XRAY_ASSET_DIR_DEFAULT="$(subvost_resolve_xray_asset_dir_for_home "$REAL_HOME")"
STORE_FILE_DEFAULT="$(subvost_resolve_store_file_for_home "$REAL_HOME")"

ensure_absolute_path() {
  local path_value="$1"
  local label="$2"
  if [[ "$path_value" != /* ]]; then
    echo "${label} должен быть абсолютным путём: ${path_value}" >&2
    exit 1
  fi
}

make_temp_log() {
  local prefix="$1"
  mktemp "${LOG_DIR}/${prefix}.XXXXXX.log"
}

capture_start_failure() {
  local output_path="$1"
  shift
  sudo timeout 5 "$@" >"$output_path" 2>&1 || true
}

service_is_active() {
  local unit_name="$1"
  command -v systemctl >/dev/null 2>&1 || return 1
  systemctl is-active --quiet "$unit_name" 2>/dev/null
}

ensure_no_conflicting_xray_service() {
  if service_is_active xray.service; then
    echo "Обнаружен активный системный xray.service." >&2
    echo "Для portable bundle он не нужен и может создавать дубли процесса Xray." >&2
    echo "Останови его перед запуском bundle: sudo systemctl disable --now xray.service" >&2
    exit 1
  fi

  if pgrep -xaf '/usr/local/bin/xray run -config /usr/local/etc/xray/config.json' >/dev/null 2>&1; then
    echo "Обнаружен запущенный системный Xray с конфигом /usr/local/etc/xray/config.json." >&2
    echo "Останови его перед запуском bundle, иначе диагностика и управление процессами будут неоднозначны." >&2
    exit 1
  fi
}

resolve_resolv_conf_target() {
  if readlink -f /etc/resolv.conf >/dev/null 2>&1; then
    readlink -f /etc/resolv.conf
  else
    printf '%s\n' "/etc/resolv.conf"
  fi
}

ensure_python3_available() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Не найдена обязательная зависимость python3." >&2
    echo "Установи python3 и повтори запуск bundle." >&2
    exit 1
  fi
}

sync_generated_runtime_snapshot_from_store() {
  HOME="$REAL_HOME" python3 "${SUBVOST_LIBEXEC_DIR}/_subvost_store_reader.py" \
    --uid "$REAL_UID" --gid "$REAL_GID" \
    sync-generated-runtime
}

ensure_tun_device_available() {
  if [[ ! -e /dev/net/tun ]]; then
    echo "Не найден /dev/net/tun. Без него xray-core не сможет поднять TUN-интерфейс." >&2
    echo "Проверь: ls -l /dev/net/tun ; lsmod | grep tun" >&2
    exit 1
  fi

  if [[ ! -c /dev/net/tun ]]; then
    echo "/dev/net/tun существует, но это не символьное устройство." >&2
    echo "Проверь: ls -l /dev/net/tun ; sudo ${SUBVOST_CAPTURE_WRAPPER}" >&2
    exit 1
  fi
}

ensure_dns_environment_is_supported() {
  local resolv_target
  local resolved_state="inactive"
  local network_manager_state="inactive"

  if [[ ! -e /etc/resolv.conf ]]; then
    echo "Не найден /etc/resolv.conf. Старт остановлен до изменения DNS." >&2
    echo "Сними диагностику: sudo ${SUBVOST_CAPTURE_WRAPPER}" >&2
    exit 1
  fi

  if [[ -L /etc/resolv.conf ]] && ! readlink -f /etc/resolv.conf >/dev/null 2>&1; then
    echo "/etc/resolv.conf является битой символьной ссылкой." >&2
    echo "Сними диагностику: sudo ${SUBVOST_CAPTURE_WRAPPER}" >&2
    exit 1
  fi

  if ! grep -Eq '^[[:space:]]*nameserver[[:space:]]+' /etc/resolv.conf; then
    echo "Предупреждение: в текущем /etc/resolv.conf нет явных строк nameserver." >&2
    echo "Bundle продолжит старт: файл всё равно будет сохранён в backup и временно переписан runtime-DNS." >&2
  fi

  resolv_target="$(resolve_resolv_conf_target)"

  if service_is_active systemd-resolved; then
    resolved_state="active"
  fi

  if service_is_active NetworkManager; then
    network_manager_state="active"
  fi

  if [[ "$resolved_state" == "active" ]] && [[ "$resolv_target" == "/run/systemd/resolve/stub-resolv.conf" ]]; then
    echo "Предупреждение: /etc/resolv.conf ведёт в ${resolv_target}, а systemd-resolved активен." >&2
    echo "Bundle продолжит старт и временно перепишет /etc/resolv.conf, но при проблемах с DNS сначала сними диагностику." >&2
    echo "Проверь: readlink -f /etc/resolv.conf ; systemctl status systemd-resolved" >&2
  fi

  if [[ "$network_manager_state" == "active" ]] && [[ "$resolv_target" == /run/NetworkManager/* ]]; then
    echo "Предупреждение: /etc/resolv.conf ведёт в ${resolv_target}, а NetworkManager активен." >&2
    echo "Bundle продолжит старт и временно перепишет /etc/resolv.conf, но при смене сети NetworkManager может перезаписать runtime-DNS." >&2
    echo "Проверь: readlink -f /etc/resolv.conf ; systemctl status NetworkManager" >&2
  fi
}

capture_runtime_diagnostic() {
  local diagnostic_path=""
  if [[ "$(id -u)" -eq 0 ]]; then
    diagnostic_path="$(timeout 90 "${SUBVOST_CAPTURE_WRAPPER}" 2>/dev/null || true)"
  else
    diagnostic_path="$(sudo timeout 90 "${SUBVOST_CAPTURE_WRAPPER}" 2>/dev/null || true)"
  fi
  printf '%s\n' "$diagnostic_path" | tail -n 1
}

load_active_selection_from_store() {
  local store_file="$1"

  if [[ ! -f "$store_file" ]]; then
    return 0
  fi

  ACTIVE_PROFILE_ID="$(HOME="$REAL_HOME" python3 "${SUBVOST_LIBEXEC_DIR}/_subvost_store_reader.py" --store-file "$store_file" active-profile-id)"
  ACTIVE_NODE_ID="$(HOME="$REAL_HOME" python3 "${SUBVOST_LIBEXEC_DIR}/_subvost_store_reader.py" --store-file "$store_file" active-node-id)"
}


legacy_state_runtime_is_live() {
  local state_file="$1"
  local state_pid=""
  local state_tun_interface=""

  state_pid="$(read_state_value "$state_file" "XRAY_PID")"
  state_tun_interface="$(read_state_value "$state_file" "TUN_INTERFACE")"

  if [[ ! "$state_pid" =~ ^[0-9]+$ ]]; then
    state_pid=""
  fi

  if [[ -z "$state_tun_interface" ]]; then
    state_tun_interface="$TUN_INTERFACE_NAME"
  fi

  if [[ -n "$state_pid" ]] && kill -0 "$state_pid" 2>/dev/null; then
    return 0
  fi

  if [[ -n "$state_tun_interface" ]] && ip link show "$state_tun_interface" >/dev/null 2>&1; then
    return 0
  fi

  return 1
}

backup_resolv_conf() {
  sudo cp -fL /etc/resolv.conf "$RESOLV_BACKUP"
}

write_runtime_resolv_conf() {
  {
    echo "# Managed by ${0##*/}"
    if [[ -n "$RUNTIME_DNS_SEARCH_DOMAINS" ]]; then
      echo "search ${RUNTIME_DNS_SEARCH_DOMAINS}"
    fi
    local nameserver
    for nameserver in $RUNTIME_DNS_SERVERS; do
      echo "nameserver ${nameserver}"
    done
    echo "options timeout:2 attempts:2"
  } | sudo tee /etc/resolv.conf >/dev/null
}

detect_default_ipv4_interface() {
  DEFAULT_IPV4_ROUTE_LINE="$(ip -4 route show default 2>/dev/null | head -n 1)"
  if [[ -z "$DEFAULT_IPV4_ROUTE_LINE" ]]; then
    echo "Не найден default IPv4 route. Без него runtime не сможет оставить исходящий трафик самого Xray во внешней сети." >&2
    exit 1
  fi

  DEFAULT_IPV4_INTERFACE="$(
    awk '{for (i = 1; i <= NF; i++) if ($i == "dev") { print $(i + 1); exit }}' <<<"$DEFAULT_IPV4_ROUTE_LINE"
  )"
  if [[ -z "$DEFAULT_IPV4_INTERFACE" ]]; then
    echo "Не удалось определить интерфейс из default IPv4 route: ${DEFAULT_IPV4_ROUTE_LINE}" >&2
    exit 1
  fi

  DEFAULT_IPV4_GATEWAY="$(
    awk '{for (i = 1; i <= NF; i++) if ($i == "via") { print $(i + 1); exit }}' <<<"$DEFAULT_IPV4_ROUTE_LINE"
  )"
  if [[ -z "$DEFAULT_IPV4_GATEWAY" ]]; then
    echo "Не удалось определить gateway из default IPv4 route: ${DEFAULT_IPV4_ROUTE_LINE}" >&2
    exit 1
  fi
}

load_runtime_routing_overrides() {
  local config_path="$1"
  [[ -f "$config_path" ]] || return 0

  python3 - "$config_path" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
except Exception:
    sys.exit(0)

for key in ("excluded_source_ipv4_ranges", "excluded_ipv4_routes", "excluded_hostnames"):
    value = data.get(key)
    if isinstance(value, list):
        print(f"{key}={' '.join(str(v) for v in value)}")
    elif isinstance(value, str):
        print(f"{key}={value}")
PY
}

detect_libvirt_source_networks() {
  local networks="" network_name cidr
  if ! command -v virsh >/dev/null 2>&1; then
    return 0
  fi
  networks="$(
    virsh -c qemu:///system net-list --all 2>/dev/null | awk 'NR>2 && $3=="yes" {print $1}'
  )"
  [[ -n "$networks" ]] || return 0
  for network_name in $networks; do
    cidr="$(
      virsh -c qemu:///system net-dumpxml "$network_name" 2>/dev/null \
      | python3 -c '
import sys, xml.etree.ElementTree as ET
try:
    root = ET.fromstring(sys.stdin.read())
    ip = root.find(".//ip")
    if ip is not None:
        addr = ip.get("address")
        netmask = ip.get("netmask", "255.255.255.0")
        import ipaddress
        network = ipaddress.IPv4Network((addr, netmask), strict=False)
        print(str(network))
except Exception:
    pass
    '
    )"
    if [[ -n "$cidr" ]]; then
      if [[ -n "${LIBVIRT_SOURCE_NETWORKS:-}" ]]; then
        if [[ " ${LIBVIRT_SOURCE_NETWORKS} " != *" ${cidr} "* ]]; then
          LIBVIRT_SOURCE_NETWORKS="${LIBVIRT_SOURCE_NETWORKS} ${cidr}"
        fi
      else
        LIBVIRT_SOURCE_NETWORKS="${cidr}"
      fi
    fi
  done
}

apply_vpn_excluded_source_rules() {
  local source_range
  [[ -n "$VPN_EXCLUDED_SOURCE_IPV4_RANGES" ]] || return 0
  for source_range in $VPN_EXCLUDED_SOURCE_IPV4_RANGES; do
    sudo ip rule add pref "$ROUTE_RULE_PREF_EXCLUDED_SOURCE" from "$source_range" lookup main >/dev/null 2>&1 || true
  done
}

cleanup_vpn_excluded_source_rules() {
  local source_range
  [[ -n "$VPN_EXCLUDED_SOURCE_IPV4_RANGES" ]] || return 0
  for source_range in $VPN_EXCLUDED_SOURCE_IPV4_RANGES; do
    sudo ip rule del pref "$ROUTE_RULE_PREF_EXCLUDED_SOURCE" from "$source_range" lookup main >/dev/null 2>&1 || true
  done
}

apply_vpn_excluded_destination_rules() {
  local source_range
  [[ -n "$VPN_EXCLUDED_SOURCE_IPV4_RANGES" ]] || return 0
  for source_range in $VPN_EXCLUDED_SOURCE_IPV4_RANGES; do
    sudo ip rule add pref "$ROUTE_RULE_PREF_EXCLUDED_DESTINATION" to "$source_range" lookup main >/dev/null 2>&1 || true
  done
}

cleanup_vpn_excluded_destination_rules() {
  local source_range
  [[ -n "$VPN_EXCLUDED_SOURCE_IPV4_RANGES" ]] || return 0
  for source_range in $VPN_EXCLUDED_SOURCE_IPV4_RANGES; do
    sudo ip rule del pref "$ROUTE_RULE_PREF_EXCLUDED_DESTINATION" to "$source_range" lookup main >/dev/null 2>&1 || true
  done
}

apply_vpn_excluded_source_marks() {
  local source_range
  [[ -n "$VPN_EXCLUDED_SOURCE_IPV4_RANGES" ]] || return 0
  if ! command -v iptables >/dev/null 2>&1; then
    return 0
  fi
  for source_range in $VPN_EXCLUDED_SOURCE_IPV4_RANGES; do
    iptables -t mangle -C POSTROUTING -s "$source_range" ! -d "$source_range" -j MARK --set-mark "$ROUTE_MARK" >/dev/null 2>&1 || \
      sudo iptables -t mangle -I POSTROUTING 1 -s "$source_range" ! -d "$source_range" -j MARK --set-mark "$ROUTE_MARK"
    iptables -t mangle -C PREROUTING -d "$source_range" -j MARK --set-mark "$ROUTE_MARK" >/dev/null 2>&1 || \
      sudo iptables -t mangle -I PREROUTING 1 -d "$source_range" -j MARK --set-mark "$ROUTE_MARK"
  done
}

cleanup_vpn_excluded_source_marks() {
  local source_range
  [[ -n "$VPN_EXCLUDED_SOURCE_IPV4_RANGES" ]] || return 0
  if ! command -v iptables >/dev/null 2>&1; then
    return 0
  fi
  for source_range in $VPN_EXCLUDED_SOURCE_IPV4_RANGES; do
    sudo iptables -t mangle -D POSTROUTING -s "$source_range" ! -d "$source_range" -j MARK --set-mark "$ROUTE_MARK" >/dev/null 2>&1 || true
    sudo iptables -t mangle -D PREROUTING -d "$source_range" -j MARK --set-mark "$ROUTE_MARK" >/dev/null 2>&1 || true
  done
}

apply_vpn_excluded_ipv4_routes() {
  local route_value host address resolved_any local_route local_dev

  [[ -n "$VPN_EXCLUDED_IPV4_ROUTES" ]] || return 0

  for route_value in $VPN_EXCLUDED_IPV4_ROUTES; do
    local_route="$(ip route show "$route_value" table main 2>/dev/null | head -n 1)"
    if [[ "$local_route" == *"proto kernel"* && "$local_route" == *"scope link"* ]]; then
      local_dev="$(awk '{for (i = 1; i <= NF; i++) if ($i == "dev") { print $(i + 1); exit }}' <<<"$local_route")"
      if [[ -n "$local_dev" ]]; then
        sudo ip route replace table "$ROUTE_TABLE" "$route_value" dev "$local_dev"
        continue
      fi
    fi
    sudo ip route replace table "$ROUTE_TABLE" "$route_value" via "$DEFAULT_IPV4_GATEWAY" dev "$DEFAULT_IPV4_INTERFACE"
  done

  [[ -n "$VPN_EXCLUDED_HOSTNAMES" ]] || return 0

  for host in $VPN_EXCLUDED_HOSTNAMES; do
    resolved_any=0
    while IFS= read -r address; do
      [[ -n "$address" ]] || continue
      resolved_any=1
      sudo ip route replace table "$ROUTE_TABLE" "${address}/32" via "$DEFAULT_IPV4_GATEWAY" dev "$DEFAULT_IPV4_INTERFACE"
    done < <(
      {
        getent ahostsv4 "$host" | awk '{print $1}' || true
        for search_domain in $RUNTIME_DNS_SEARCH_DOMAINS; do
          getent ahostsv4 "${host}.${search_domain}" | awk '{print $1}' || true
        done
      } | sort -u
    )

    if [[ "$resolved_any" == "0" ]]; then
      echo "Предупреждение: не удалось разрешить hostname для VPN-исключения: ${host}" >&2
    fi
  done
}

apply_ufw_icmp_fix() {
  local route_value
  if ! command -v iptables >/dev/null 2>&1; then
    return 0
  fi
  for route_value in $VPN_EXCLUDED_IPV4_ROUTES; do
    sudo iptables -t filter -C INPUT -p icmp --icmp-type echo-reply -s "$route_value" -j ACCEPT >/dev/null 2>&1 || \
      sudo iptables -t filter -I INPUT 1 -p icmp --icmp-type echo-reply -s "$route_value" -j ACCEPT
  done
}


materialize_runtime_config() {
  python3 - \
    "$XRAY_CONFIG" \
    "$XRAY_RUNTIME_CONFIG" \
    "$DEFAULT_IPV4_INTERFACE" \
    "$ROUTE_MARK" \
    "$REAL_UID" \
    "$REAL_GID" \
    "$SUBVOST_PROJECT_ROOT" <<'PY'
import json
import os
import sys
from pathlib import Path

base_config_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
default_interface = sys.argv[3]
outbound_mark = int(sys.argv[4])
uid = int(sys.argv[5])
gid = int(sys.argv[6])
project_root = Path(sys.argv[7])

sys.path.insert(0, str(project_root / "gui"))

from subvost_runtime import apply_transport_hints_to_runtime_config, read_json_config  # noqa: E402
from subvost_paths import atomic_write_json  # noqa: E402

base_config = read_json_config(base_config_path)

if not base_config:
    raise SystemExit(f"Не удалось прочитать активный Xray-конфиг: {base_config_path}")

runtime_config = apply_transport_hints_to_runtime_config(
    base_config,
    default_interface=default_interface,
    outbound_mark=outbound_mark,
)
atomic_write_json(output_path, runtime_config, uid=uid, gid=gid)
PY
}

policy_route_cleanup() {
  sudo ip rule del pref "$ROUTE_RULE_PREF" not fwmark "$ROUTE_MARK" table "$ROUTE_TABLE" >/dev/null 2>&1 || true
  sudo ip route flush table "$ROUTE_TABLE" >/dev/null 2>&1 || true
  sudo ip route flush cache >/dev/null 2>&1 || true
}

cleanup_partial_start() {
  cleanup_vpn_excluded_destination_rules
  cleanup_vpn_excluded_source_rules
  cleanup_vpn_excluded_source_marks

  policy_route_cleanup
  cleanup_ufw_icmp_fix

  if [[ -n "${XRAY_PID:-}" ]]; then
    sudo kill "$XRAY_PID" 2>/dev/null || true
  fi

  sleep 1

  if [[ -n "${TUN_INTERFACE_NAME:-}" ]]; then
    sudo ip link delete "$TUN_INTERFACE_NAME" >/dev/null 2>&1 || true
  fi

  if [[ -f "$STATE_FILE" ]]; then
    rm -f "$STATE_FILE"
  fi
}

fail_start_with_rollback() {
  local failure_message="$1"
  local diagnostic_path=""

  echo "$failure_message" >&2
  diagnostic_path="$(capture_runtime_diagnostic)"
  echo "Выполняется rollback частично поднятого состояния..." >&2
  cleanup_partial_start

  if [[ -f "$RESOLV_BACKUP" ]]; then
    sudo cp -f "$RESOLV_BACKUP" /etc/resolv.conf >/dev/null 2>&1 || true
  fi

  if [[ -n "$diagnostic_path" ]]; then
    echo "Диагностика сохранена в: $diagnostic_path" >&2
  else
    echo "Автоматически снять полный диагностический дамп не удалось. Запусти: sudo ${SUBVOST_CAPTURE_WRAPPER}" >&2
  fi

  exit 1
}

wait_for_tun_interface_ready() {
  local deadline=$((SECONDS + POST_START_SANITY_TIMEOUT_SECS))

  while (( SECONDS < deadline )); do
    if kill -0 "${XRAY_PID:-0}" 2>/dev/null \
      && ip link show "$TUN_INTERFACE_NAME" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  kill -0 "${XRAY_PID:-0}" 2>/dev/null && ip link show "$TUN_INTERFACE_NAME" >/dev/null 2>&1
}

XRAY_BIN_DEFAULT="$(
  subvost_find_executable \
    "/usr/local/bin/xray" \
    "/usr/bin/xray" \
    "${REAL_HOME}/.local/bin/xray" \
    "${HOME}/.local/bin/xray" \
    "$(command -v xray 2>/dev/null || true)" \
  || true
)"
XRAY_BIN="${XRAY_BIN:-${XRAY_BIN_DEFAULT:-${HOME}/.local/bin/xray}}"
XRAY_CONFIG="${ACTIVE_XRAY_CONFIG_DEFAULT}"
XRAY_RUNTIME_CONFIG="${XRAY_RUNTIME_CONFIG:-${ACTIVE_RUNTIME_XRAY_CONFIG_DEFAULT}}"
XRAY_ASSET_DIR="${XRAY_ASSET_DIR:-${XRAY_ASSET_DIR_DEFAULT}}"
STATE_FILE="${STATE_FILE:-${REAL_HOME}/.xray-tun-subvost.state}"
RESOLV_BACKUP="${RESOLV_BACKUP:-${REAL_HOME}/.xray-tun-subvost.resolv.conf.backup}"
RUNTIME_DNS_SERVERS="${RUNTIME_DNS_SERVERS:-10.2.12.20 10.2.12.33 8.8.8.8 1.1.1.1}"
RUNTIME_DNS_SEARCH_DOMAINS="${RUNTIME_DNS_SEARCH_DOMAINS:-bg.ru}"
XRAY_LOG="${XRAY_LOG:-${LOG_DIR}/xray-subvost.log}"
ENABLE_FILE_LOGS="${ENABLE_FILE_LOGS:-0}"
POST_START_SANITY_TIMEOUT_SECS="${POST_START_SANITY_TIMEOUT_SECS:-12}"
ROUTE_TABLE="${ROUTE_TABLE:-18421}"
ROUTE_MARK="${ROUTE_MARK:-8421}"
ROUTE_RULE_PREF="${ROUTE_RULE_PREF:-100}"
TUN_INTERFACE_NAME="${TUN_INTERFACE_NAME:-tun0}"
TUN_INTERFACE_ADDRESS="${TUN_INTERFACE_ADDRESS:-172.19.0.1/30}"
XRAY_PID=""
ACTIVE_PROFILE_ID=""
ACTIVE_NODE_ID=""
DEFAULT_IPV4_ROUTE_LINE=""
DEFAULT_IPV4_INTERFACE=""
DEFAULT_IPV4_GATEWAY=""
XRAY_CONFIG_SOURCE="store"
BUNDLE_INSTALL_ID="$(subvost_ensure_install_id)"
VPN_EXCLUDED_IPV4_ROUTES="${VPN_EXCLUDED_IPV4_ROUTES:-10.0.0.0/14 10.3.40.33/32 81.29.134.113/32 192.168.122.0/24}"

VPN_EXCLUDED_HOSTNAMES="${VPN_EXCLUDED_HOSTNAMES:-dcp33 dcp40 dcp41 kld33 mb011 mb012 mb013 mb017 sgp001 trm-stolovaya v11 v14 v2 v3 v38 v56 v69 vmscan inv0203 inv0125 mon002}"
VPN_EXCLUDED_SOURCE_IPV4_RANGES="${VPN_EXCLUDED_SOURCE_IPV4_RANGES:-}"
ROUTE_RULE_PREF_EXCLUDED_SOURCE="${ROUTE_RULE_PREF_EXCLUDED_SOURCE:-$((ROUTE_RULE_PREF - 1))}"
ROUTE_RULE_PREF_EXCLUDED_DESTINATION="${ROUTE_RULE_PREF_EXCLUDED_DESTINATION:-$((ROUTE_RULE_PREF - 2))}"

ensure_python3_available

if [[ -f "$STORE_FILE_DEFAULT" ]]; then
  sync_generated_runtime_snapshot_from_store
fi
STORE_DIR_DEFAULT="$(subvost_resolve_store_dir_for_home "$REAL_HOME")"
RUNTIME_ROUTING_CONFIG="${RUNTIME_ROUTING_CONFIG:-${STORE_DIR_DEFAULT}/runtime-routing.json}"

while IFS='=' read -r key value; do
  case "$key" in
    excluded_source_ipv4_ranges)
      [[ -n "${VPN_EXCLUDED_SOURCE_IPV4_RANGES:-}" ]] || VPN_EXCLUDED_SOURCE_IPV4_RANGES="$value"
      ;;
    excluded_ipv4_routes)
      [[ -n "${VPN_EXCLUDED_IPV4_ROUTES:-}" ]] || VPN_EXCLUDED_IPV4_ROUTES="$value"
      ;;
    excluded_hostnames)
      [[ -n "${VPN_EXCLUDED_HOSTNAMES:-}" ]] || VPN_EXCLUDED_HOSTNAMES="$value"
      ;;
  esac
done < <(load_runtime_routing_overrides "$RUNTIME_ROUTING_CONFIG")

detect_libvirt_source_networks
if [[ -n "${LIBVIRT_SOURCE_NETWORKS:-}" ]]; then
  for cidr in $LIBVIRT_SOURCE_NETWORKS; do
    if [[ " ${VPN_EXCLUDED_SOURCE_IPV4_RANGES} " != *" ${cidr} "* ]]; then
      VPN_EXCLUDED_SOURCE_IPV4_RANGES="${VPN_EXCLUDED_SOURCE_IPV4_RANGES} ${cidr}"
    fi
  done
fi

mkdir -p "$LOG_DIR"
ensure_absolute_path "$STATE_FILE" "STATE_FILE"
ensure_absolute_path "$RESOLV_BACKUP" "RESOLV_BACKUP"
ensure_absolute_path "$XRAY_LOG" "XRAY_LOG"
ensure_absolute_path "$XRAY_RUNTIME_CONFIG" "XRAY_RUNTIME_CONFIG"
ensure_absolute_path "$XRAY_CONFIG" "XRAY_CONFIG"
ensure_absolute_path "$XRAY_ASSET_DIR" "XRAY_ASSET_DIR"

echo "[0/8] Режим: Xray core TUN"
echo "Поднимается основной runtime проекта без дополнительных прокси-движков."
echo "Пользователь bundle: ${REAL_USER}"
if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
  echo "Файловое логирование: включено"
else
  echo "Файловое логирование: выключено (для включения: ENABLE_FILE_LOGS=1)"
fi
echo

if [[ ! -x "$XRAY_BIN" ]]; then
  echo "Не найден исполняемый файл Xray: $XRAY_BIN" >&2
  exit 1
fi

load_active_selection_from_store "$STORE_FILE_DEFAULT"
if [[ -z "$ACTIVE_PROFILE_ID" || -z "$ACTIVE_NODE_ID" ]]; then
  echo "Не найден активный узел в локальном store." >&2
  echo "Сначала открой GUI, импортируй подписку при необходимости и явно активируй нужную ноду." >&2
  exit 1
fi

if [[ ! -f "$XRAY_CONFIG" ]]; then
  echo "Не найден сгенерированный Xray-конфиг активного узла: $XRAY_CONFIG" >&2
  echo "Открой GUI и снова активируй узел, чтобы пересобрать runtime-конфиг." >&2
  exit 1
fi

ensure_no_conflicting_xray_service

echo "[1/8] Проверка TUN-окружения"
ensure_tun_device_available
ip -brief address | grep -E 'FlClashX|tun0|xray0' || true

if ip link show "$TUN_INTERFACE_NAME" >/dev/null 2>&1; then
  echo "Обнаружен уже существующий TUN-интерфейс ${TUN_INTERFACE_NAME}." >&2
  echo "Сначала выполни ${SUBVOST_STOP_WRAPPER} и убедись, что интерфейс исчез." >&2
  exit 1
fi

if pgrep -xaf 'FlClashX|FlClashCore' >/dev/null 2>&1; then
  echo "Обнаружен активный FlClash. Полностью останови FlClashX/FlClashCore и запусти скрипт снова." >&2
  exit 1
fi

if [[ -f "$STATE_FILE" ]]; then
  STATE_BUNDLE_INSTALL_ID="$(read_state_bundle_install_id "$STATE_FILE")"
  STATE_BUNDLE_PROJECT_ROOT="$(read_state_value "$STATE_FILE" "BUNDLE_PROJECT_ROOT_HINT")"
  if [[ -z "$STATE_BUNDLE_PROJECT_ROOT" ]]; then
    STATE_BUNDLE_PROJECT_ROOT="$(read_state_value "$STATE_FILE" "BUNDLE_PROJECT_ROOT")"
  fi

  if [[ -n "$STATE_BUNDLE_INSTALL_ID" ]]; then
    if [[ "$STATE_BUNDLE_INSTALL_ID" != "$BUNDLE_INSTALL_ID" ]]; then
      if legacy_state_runtime_is_live "$STATE_FILE"; then
        echo "Обнаружен файл состояния другой установки bundle: $STATE_FILE" >&2
        echo "Идентификатор установки владельца: ${STATE_BUNDLE_INSTALL_ID}" >&2
        echo "Идентификатор текущей установки: ${BUNDLE_INSTALL_ID}" >&2
        if [[ -n "$STATE_BUNDLE_PROJECT_ROOT" ]]; then
          echo "Последний известный путь владельца: ${STATE_BUNDLE_PROJECT_ROOT}" >&2
        fi
        echo "Сначала останови исходную установку или выполни ${SUBVOST_STOP_WRAPPER}, когда runtime уже не активен." >&2
        exit 1
      fi

      echo "Обнаружен устаревший файл состояния другой установки bundle: $STATE_FILE" >&2
      echo "Идентификатор установки владельца: ${STATE_BUNDLE_INSTALL_ID}" >&2
      echo "Идентификатор текущей установки: ${BUNDLE_INSTALL_ID}" >&2
      echo "Живой процесс по этому файлу состояния не найден, новый запуск перезапишет устаревшее состояние." >&2
    else
      if legacy_state_runtime_is_live "$STATE_FILE"; then
        echo "Обнаружен файл состояния прошлого запуска текущей установки bundle: $STATE_FILE" >&2
        echo "Сначала выполни ${SUBVOST_STOP_WRAPPER}" >&2
        exit 1
      fi

      echo "Обнаружен устаревший файл состояния прошлого запуска текущей установки bundle: $STATE_FILE" >&2
      echo "Живой процесс по этому файлу состояния не найден, новый запуск перезапишет устаревшее состояние." >&2
    fi
  elif [[ -n "$STATE_BUNDLE_PROJECT_ROOT" ]] && [[ "$STATE_BUNDLE_PROJECT_ROOT" != "$SUBVOST_PROJECT_ROOT" ]]; then
    if legacy_state_runtime_is_live "$STATE_FILE"; then
      echo "Обнаружен legacy state другого bundle: $STATE_FILE" >&2
      echo "Последний известный путь владельца runtime: ${STATE_BUNDLE_PROJECT_ROOT}" >&2
      echo "Текущий bundle: ${SUBVOST_PROJECT_ROOT}" >&2
      echo "Сначала останови исходный экземпляр или выполни ${SUBVOST_STOP_WRAPPER}, когда runtime уже не активен." >&2
      exit 1
    fi

    echo "Обнаружен stale legacy state другого bundle: $STATE_FILE" >&2
    echo "Последний известный путь владельца runtime: ${STATE_BUNDLE_PROJECT_ROOT}" >&2
    echo "Текущий bundle: ${SUBVOST_PROJECT_ROOT}" >&2
    echo "Живой процесс по этому файлу состояния не найден, новый запуск перезапишет устаревшее состояние." >&2
  elif [[ -z "$STATE_BUNDLE_PROJECT_ROOT" ]]; then
    if legacy_state_runtime_is_live "$STATE_FILE"; then
      echo "Обнаружен файл состояния без bundle identity: $STATE_FILE" >&2
      echo "Для безопасности текущий bundle не будет стартовать поверх неподтверждённого runtime." >&2
      echo "Сначала выполни ${SUBVOST_STOP_WRAPPER}" >&2
      exit 1
    fi

    echo "Обнаружен stale legacy state без bundle identity: $STATE_FILE" >&2
    echo "Процесс по этому файлу состояния уже не активен, файл будет перезаписан новым запуском." >&2
  else
    if legacy_state_runtime_is_live "$STATE_FILE"; then
      echo "Обнаружен файл состояния прошлого запуска текущего bundle: $STATE_FILE" >&2
      echo "Сначала выполни ${SUBVOST_STOP_WRAPPER}" >&2
      exit 1
    fi

    echo "Обнаружен устаревший файл состояния прошлого запуска текущего bundle: $STATE_FILE" >&2
    echo "Живой процесс по этому файлу состояния не найден, новый запуск перезапишет устаревшее состояние." >&2
  fi
fi

echo "[2/8] Preflight DNS и routing-окружения"
ensure_dns_environment_is_supported
detect_default_ipv4_interface
echo "Основной внешний интерфейс: ${DEFAULT_IPV4_INTERFACE}"
echo "Основной gateway: ${DEFAULT_IPV4_GATEWAY}"
echo "Default route: ${DEFAULT_IPV4_ROUTE_LINE}"

if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
  XRAY_CHECK_LOG="$XRAY_LOG"
  XRAY_RUN_TARGET="$XRAY_LOG"
else
  XRAY_CHECK_LOG="$(make_temp_log xray-check)"
  XRAY_RUN_TARGET="/dev/null"
fi

echo "[3/8] Materialize runtime-конфига"
materialize_runtime_config

if ! sudo XRAY_LOCATION_ASSET="$XRAY_ASSET_DIR" "$XRAY_BIN" run -test -c "$XRAY_RUNTIME_CONFIG" >>"$XRAY_CHECK_LOG" 2>&1; then
  echo "Xray config check завершился ошибкой. Смотри лог: $XRAY_CHECK_LOG" >&2
  exit 1
fi

echo "[4/8] Запуск Xray core"
sudo -v
sudo XRAY_LOCATION_ASSET="$XRAY_ASSET_DIR" "$XRAY_BIN" run -c "$XRAY_RUNTIME_CONFIG" >>"$XRAY_RUN_TARGET" 2>&1 &
XRAY_PID=$!
sleep 2

if ! kill -0 "$XRAY_PID" 2>/dev/null; then
  if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
    echo "Xray завершился сразу после старта. Смотри лог: $XRAY_LOG" >&2
  else
    XRAY_FAIL_LOG="$(make_temp_log xray-start-fail)"
    capture_start_failure "$XRAY_FAIL_LOG" env XRAY_LOCATION_ASSET="$XRAY_ASSET_DIR" "$XRAY_BIN" run -c "$XRAY_RUNTIME_CONFIG"
    fail_start_with_rollback "Xray завершился сразу после старта. Диагностика команды сохранена в: $XRAY_FAIL_LOG"
  fi
  fail_start_with_rollback "Xray завершился сразу после старта. Смотри лог: $XRAY_LOG"
fi

echo "[5/8] Ожидание tun-интерфейса и настройка policy-routing"
if ! wait_for_tun_interface_ready; then
  fail_start_with_rollback "Xray не создал интерфейс ${TUN_INTERFACE_NAME} за отведённое время."
fi

sudo ip link set dev "$TUN_INTERFACE_NAME" up >/dev/null 2>&1 || true
if [[ -n "$TUN_INTERFACE_ADDRESS" ]]; then
  sudo ip address add "$TUN_INTERFACE_ADDRESS" dev "$TUN_INTERFACE_NAME" >/dev/null 2>&1 || true
fi
sudo ip route replace table "$ROUTE_TABLE" default dev "$TUN_INTERFACE_NAME"
apply_vpn_excluded_ipv4_routes
apply_ufw_icmp_fix
apply_vpn_excluded_source_rules
apply_vpn_excluded_destination_rules
apply_vpn_excluded_source_marks

sudo ip rule add pref "$ROUTE_RULE_PREF" not fwmark "$ROUTE_MARK" table "$ROUTE_TABLE"
sudo ip route flush cache >/dev/null 2>&1 || true

if ! ip rule show | grep -F "lookup ${ROUTE_TABLE}" >/dev/null 2>&1; then
  fail_start_with_rollback "Policy-routing правило для таблицы ${ROUTE_TABLE} не появилось."
fi

if ! ip link show "$TUN_INTERFACE_NAME" | grep -q '<.*UP.*>'; then
  fail_start_with_rollback "TUN-интерфейс ${TUN_INTERFACE_NAME} создан, но не находится в состоянии UP."
fi

echo "[6/8] Настройка системного DNS"
backup_resolv_conf
write_runtime_resolv_conf

if [[ "$ENABLE_FILE_LOGS" != "1" ]]; then
  rm -f "$XRAY_CHECK_LOG"
fi

echo "[7/8] Сохранение состояния"
STARTED_AT="$(date -Iseconds)"
printf 'XRAY_PID=%s\nRESOLV_BACKUP=%s\nXRAY_CONFIG=%s\nACTIVE_PROFILE_ID=%s\nACTIVE_NODE_ID=%s\n' \
  "$XRAY_PID" \
  "$RESOLV_BACKUP" \
  "$XRAY_RUNTIME_CONFIG" \
  "$ACTIVE_PROFILE_ID" \
  "$ACTIVE_NODE_ID" \
  >"$STATE_FILE"
printf 'STARTED_AT=%s\n' "$STARTED_AT" >>"$STATE_FILE"
printf 'XRAY_CONFIG_SOURCE=%s\n' "$XRAY_CONFIG_SOURCE" >>"$STATE_FILE"
printf 'BUNDLE_INSTALL_ID=%s\n' "$BUNDLE_INSTALL_ID" >>"$STATE_FILE"
printf 'BUNDLE_PROJECT_ROOT_HINT=%s\n' "$SUBVOST_PROJECT_ROOT" >>"$STATE_FILE"
printf 'RUNTIME_IMPL=%s\n' "xray" >>"$STATE_FILE"
printf 'TUN_INTERFACE=%s\n' "$TUN_INTERFACE_NAME" >>"$STATE_FILE"
printf 'TUN_INTERFACE_ADDRESS=%s\n' "$TUN_INTERFACE_ADDRESS" >>"$STATE_FILE"
printf 'ROUTE_TABLE=%s\n' "$ROUTE_TABLE" >>"$STATE_FILE"
printf 'ROUTE_MARK=%s\n' "$ROUTE_MARK" >>"$STATE_FILE"
printf 'ROUTE_RULE_PREF=%s\n' "$ROUTE_RULE_PREF" >>"$STATE_FILE"
printf 'VPN_EXCLUDED_IPV4_ROUTES=%s\n' "$VPN_EXCLUDED_IPV4_ROUTES" >>"$STATE_FILE"
printf 'VPN_EXCLUDED_HOSTNAMES=%s\n' "$VPN_EXCLUDED_HOSTNAMES" >>"$STATE_FILE"
printf 'VPN_EXCLUDED_SOURCE_IPV4_RANGES=%s\n' "$VPN_EXCLUDED_SOURCE_IPV4_RANGES" >>"$STATE_FILE"
printf 'ROUTE_RULE_PREF_EXCLUDED_SOURCE=%s\n' "$ROUTE_RULE_PREF_EXCLUDED_SOURCE" >>"$STATE_FILE"
printf 'ROUTE_RULE_PREF_EXCLUDED_DESTINATION=%s\n' "$ROUTE_RULE_PREF_EXCLUDED_DESTINATION" >>"$STATE_FILE"

printf 'RUNTIME_DNS_SERVERS=%s\n' "$RUNTIME_DNS_SERVERS" >>"$STATE_FILE"
printf 'RUNTIME_DNS_SEARCH_DOMAINS=%s\n' "$RUNTIME_DNS_SEARCH_DOMAINS" >>"$STATE_FILE"

echo "[8/8] Готово"
echo "XRAY_PID=$XRAY_PID"
echo "RUNTIME_IMPL=xray"
echo "XRAY_CONFIG=$XRAY_RUNTIME_CONFIG"
echo "XRAY_CONFIG_SOURCE=$XRAY_CONFIG_SOURCE"
echo "STARTED_AT=$STARTED_AT"
echo "TUN_INTERFACE=$TUN_INTERFACE_NAME"
echo "TUN_INTERFACE_ADDRESS=$TUN_INTERFACE_ADDRESS"
echo "DEFAULT_IPV4_INTERFACE=$DEFAULT_IPV4_INTERFACE"
echo "DEFAULT_IPV4_GATEWAY=$DEFAULT_IPV4_GATEWAY"
echo "VPN_EXCLUDED_IPV4_ROUTES=$VPN_EXCLUDED_IPV4_ROUTES"
echo "VPN_EXCLUDED_HOSTNAMES=$VPN_EXCLUDED_HOSTNAMES"
echo "VPN_EXCLUDED_SOURCE_IPV4_RANGES=$VPN_EXCLUDED_SOURCE_IPV4_RANGES"
echo "RUNTIME_DNS_SERVERS=$RUNTIME_DNS_SERVERS"
echo "RUNTIME_DNS_SEARCH_DOMAINS=$RUNTIME_DNS_SEARCH_DOMAINS"
echo "ROUTE_TABLE=$ROUTE_TABLE"
echo "ROUTE_MARK=$ROUTE_MARK"
if [[ "$ENABLE_FILE_LOGS" == "1" ]]; then
  echo "Лог Xray: $XRAY_LOG"
else
  echo "Файловые логи отключены"
fi
echo "Для отката используй: ${SUBVOST_STOP_WRAPPER}"
