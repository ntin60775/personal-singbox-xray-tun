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

if [[ -z "$REAL_HOME" ]]; then
  echo "Не удалось определить домашний каталог пользователя ${REAL_USER}" >&2
  exit 1
fi

STATE_FILE="${STATE_FILE:-${REAL_HOME}/.xray-tun-subvost.state}"
RESOLV_BACKUP="${RESOLV_BACKUP:-${REAL_HOME}/.xray-tun-subvost.resolv.conf.backup}"

TS="$(date +%Y%m%d-%H%M%S)"
OUT="${LOG_DIR}/xray-tun-state-${TS}.log"

mkdir -p "$LOG_DIR"

print_section() {
  local title="$1"
  shift
  echo "== ${title} =="
  "$@" 2>&1 || true
  echo
}

print_shell_block() {
  local title="$1"
  shift
  echo "== ${title} =="
  bash -lc "$*" 2>&1 || true
  echo
}

print_shell_block_as_real_user() {
  local title="$1"
  shift
  echo "== ${title} =="
  if [[ "$(id -u)" -eq 0 && "$REAL_USER" != "root" ]]; then
    sudo -u "$REAL_USER" env \
      HOME="$REAL_HOME" \
      USER="$REAL_USER" \
      LOGNAME="$REAL_USER" \
      bash -lc "$*" 2>&1 || true
  else
    bash -lc "$*" 2>&1 || true
  fi
  echo
}

{
  echo "timestamp=$(date --iso-8601=seconds)"
  echo "hostname=$(hostname)"
  echo "cwd=$(pwd)"
  echo "real_user=${REAL_USER}"
  echo "real_home=${REAL_HOME}"
  echo "user=$(id -un)"
  echo "uid=$(id -u)"
  echo "euid=${EUID}"
  echo "project_root=${SUBVOST_PROJECT_ROOT}"
  echo "internal_script=${INTERNAL_DIR}/capture-xray-tun-state.sh"
  echo "public_wrapper=${SUBVOST_CAPTURE_WRAPPER}"
  echo "state_file=${STATE_FILE}"
  echo "resolv_backup=${RESOLV_BACKUP}"
  echo

  print_section "versions" bash -lc '
    XRAY_CANDIDATES=(
      /usr/local/bin/xray
      /usr/bin/xray
      "'"${REAL_HOME}"'/.local/bin/xray"
      "'"${HOME}"'/.local/bin/xray"
    )
    XRAY_BIN=""
    for candidate in "${XRAY_CANDIDATES[@]}"; do
      if [[ -x "$candidate" ]]; then
        XRAY_BIN="$candidate"
        break
      fi
    done
    if [[ -n "$XRAY_BIN" ]]; then
      "$XRAY_BIN" version
    else
      echo "xray: not found"
    fi
    echo
    command -v sing-box >/dev/null 2>&1 && sing-box version || echo "sing-box: not found"
    echo
    command -v curl >/dev/null 2>&1 && curl --version | sed -n "1,2p" || echo "curl: not found"
    echo
    uname -a
  '

  print_shell_block "systemctl status xray.service" '
    if command -v systemctl >/dev/null 2>&1; then
      systemctl status xray.service --no-pager -l || true
    else
      echo "systemctl: not found"
    fi
  '

  print_section "state file" bash -lc '
    if [[ -f "'"${STATE_FILE}"'" ]]; then
      cat "'"${STATE_FILE}"'"
    else
      echo "missing"
    fi
  '

  print_section "resolv backup" bash -lc '
    if [[ -f "'"${RESOLV_BACKUP}"'" ]]; then
      cat "'"${RESOLV_BACKUP}"'"
    else
      echo "missing"
    fi
  '

  print_section "proxy env" bash -lc '
    env | sort | grep -iE "(^|_)(http|https|all|no)_proxy=" || true
  '

  print_section "ls -l /dev/net/tun" ls -l /dev/net/tun
  print_shell_block "lsmod | grep tun" '
    if command -v lsmod >/dev/null 2>&1; then
      lsmod | grep -iE "^tun\\b| tun\\b" || echo "tun module not listed"
    else
      echo "lsmod: not found"
    fi
  '

  print_section "processes" bash -lc '
    ps aux | grep -E "FlClashCore|FlClash|sing-box|xray|yandex_browser|chrome|chromium|firefox|curl" | grep -v grep || true
  '

  print_section "ip -brief address" ip -brief address
  print_section "ip -brief link" ip -brief link
  print_section "ip rule show" ip rule show
  print_section "ip -6 rule show" ip -6 rule show
  print_section "ip route show table main" ip route show table main
  print_section "ip route show table 2022" ip route show table 2022
  print_shell_block "ip route show table all | grep tun/xray" 'ip route show table all | grep -E "\\b(tun|xray)[[:alnum:]_.-]*\\b" || true'
  print_section "ip -6 route show" ip -6 route show
  print_section "ip route get 152.53.39.18" ip route get 152.53.39.18
  print_section "ip route get 8.6.112.6" ip route get 8.6.112.6
  print_section "ip route get 34.160.111.145" ip route get 34.160.111.145

  print_section "ss -tnap" ss -tnap
  print_section "ss -unap" ss -unap

  print_section "ls -l /etc/resolv.conf" ls -l /etc/resolv.conf
  print_section "readlink -f /etc/resolv.conf" readlink -f /etc/resolv.conf
  print_section "resolv.conf" cat /etc/resolv.conf
  print_section "systemctl is-active systemd-resolved" systemctl is-active systemd-resolved
  print_section "systemctl is-enabled systemd-resolved" systemctl is-enabled systemd-resolved
  print_section "resolvectl status" resolvectl status
  print_section "resolvectl query chatgpt.com" resolvectl query chatgpt.com
  print_section "resolvectl query ifconfig.me" resolvectl query ifconfig.me
  print_section "getent ahostsv4 chatgpt.com" getent ahostsv4 chatgpt.com
  print_section "getent ahostsv4 ifconfig.me" getent ahostsv4 ifconfig.me

  print_section "systemctl is-active NetworkManager" systemctl is-active NetworkManager
  print_section "systemctl is-enabled NetworkManager" systemctl is-enabled NetworkManager
  print_section "NetworkManager DNS" bash -lc '
    if command -v nmcli >/dev/null 2>&1; then
      nmcli dev show | grep -E "GENERAL.DEVICE|IP4.DNS|IP6.DNS" || true
    else
      echo "nmcli: not found"
    fi
  '

  print_section "gsettings proxy mode" gsettings get org.gnome.system.proxy mode

  print_section "nft list ruleset" nft list ruleset
  print_section "iptables-save" iptables-save
  print_section "ip6tables-save" ip6tables-save

  print_shell_block_as_real_user "curl https://chatgpt.com" '
    if command -v curl >/dev/null 2>&1; then
      curl -4 -v --max-time 15 https://chatgpt.com -o /dev/null
    else
      echo "curl: not found"
    fi
  '

  print_shell_block_as_real_user "curl --socks5-hostname 127.0.0.1:10808 https://chatgpt.com" '
    if command -v curl >/dev/null 2>&1; then
      curl -4 -v --max-time 15 --socks5-hostname 127.0.0.1:10808 https://chatgpt.com -o /dev/null
    else
      echo "curl: not found"
    fi
  '

  print_shell_block_as_real_user "curl https://ifconfig.me" '
    if command -v curl >/dev/null 2>&1; then
      curl -4 -v --max-time 15 https://ifconfig.me
    else
      echo "curl: not found"
    fi
  '

  print_shell_block_as_real_user "curl --socks5-hostname 127.0.0.1:10808 https://ifconfig.me" '
    if command -v curl >/dev/null 2>&1; then
      curl -4 -v --max-time 15 --socks5-hostname 127.0.0.1:10808 https://ifconfig.me
    else
      echo "curl: not found"
    fi
  '

  print_section "xray config snippet" sed -n '1,220p' "${SUBVOST_XRAY_CONFIG_PATH}"
  print_section "sing-box config snippet" sed -n '1,220p' "${SUBVOST_SINGBOX_CONFIG_PATH}"

  print_section "xray log tail" tail -n 200 "${LOG_DIR}/xray-subvost.log"
  print_section "sing-box log tail" tail -n 260 "${LOG_DIR}/singbox-subvost.log"
  print_section "journalctl -k -b -n 200" journalctl -k -b --no-pager -n 200
  print_shell_block "journalctl -k -b | grep -i tun" 'journalctl -k -b --no-pager | grep -i tun || true'
  print_section "journalctl -b -u systemd-resolved -n 120" journalctl -b -u systemd-resolved --no-pager -n 120
  print_section "journalctl -b -u NetworkManager -n 120" journalctl -b -u NetworkManager --no-pager -n 120
} >"$OUT"

echo "$OUT"
