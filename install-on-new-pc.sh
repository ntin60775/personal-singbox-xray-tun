#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
XRAY_INSTALL_REF="${XRAY_INSTALL_REF:-main}"
XRAY_INSTALL_URL="https://raw.githubusercontent.com/XTLS/Xray-install/${XRAY_INSTALL_REF}/install-release.sh"

run_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Не найдена обязательная команда: $cmd" >&2
    exit 1
  fi
}

echo "[1/4] Проверка базовых системных утилит"
if command -v apt-get >/dev/null 2>&1; then
  run_root apt-get update
  run_root apt-get install -y ca-certificates curl iproute2 sudo unzip
else
  echo "Скрипт установки пока поддерживает только Debian/Ubuntu с apt-get." >&2
  echo "Установи зависимости вручную: curl, unzip, iproute2, sudo, xray, sing-box." >&2
  exit 1
fi

require_cmd curl

echo "[2/4] Установка Xray"
curl -fsSL "$XRAY_INSTALL_URL" | run_root bash -s -- install

echo "[3/4] Установка sing-box"
run_root mkdir -p /etc/apt/keyrings
run_root curl -fsSL https://sing-box.app/gpg.key -o /etc/apt/keyrings/sagernet.asc
run_root chmod a+r /etc/apt/keyrings/sagernet.asc
printf 'Types: deb\nURIs: https://deb.sagernet.org/\nSuites: *\nComponents: *\nEnabled: yes\nSigned-By: /etc/apt/keyrings/sagernet.asc\n' \
  | run_root tee /etc/apt/sources.list.d/sagernet.sources >/dev/null
run_root apt-get update
run_root apt-get install -y sing-box

echo "[4/4] Проверка установленных бинарников"
if command -v xray >/dev/null 2>&1; then
  echo "Xray найден: $(command -v xray)"
else
  echo "Xray не найден в PATH после установки." >&2
  exit 1
fi

if command -v sing-box >/dev/null 2>&1; then
  echo "sing-box найден: $(command -v sing-box)"
else
  echo "sing-box не найден в PATH после установки." >&2
  exit 1
fi

echo
echo "Зависимости установлены. Bundle не копировался."
echo "Запускай bundle из текущего каталога:"
echo "  ${SCRIPT_DIR}/run-xray-tun-subvost.sh"
