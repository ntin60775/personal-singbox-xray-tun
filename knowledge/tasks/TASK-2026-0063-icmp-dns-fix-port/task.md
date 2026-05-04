# TASK-2026-0063 — Перенос ICMP + DNS rotate + sudo config check из subvost-xray-tun

**ID задачи:** TASK-2026-0063
**Краткое имя:** icmp-dns-fix-port
**Человекочитаемое описание:** Портирование трёх исправлений из рабочего bundle `subvost-xray-tun` в основной репозиторий `personal-singbox-xray-tun`: разрешение ICMP echo-reply из VPN-excluded сетей, устранение нестабильности DNS-резолва из-за `rotate`, и запуск `xray -test` от root.

**Статус:** completed
**Ветка:** main
**Создана:** 2026-05-04

## Проблемы

### 1. ICMP ping падает через VPN
При активном xray TUN ICMP echo-request уходит через TUN-интерфейс, обрабатывается xray и отправляется напрямую через `eth0`. Echo-reply приходит на `eth0`, но UFW policy `DROP` отбрасывает его, потому что conntrack не связывает ответ с запросом (запрос ушёл через xray, а не напрямую).

### 2. DNS резолв коротких имён нестабилен
`options rotate` в runtime-`resolv.conf` заставляет glibc resolver случайно выбирать DNS-сервер. 50% запросов попадают на `8.8.8.8`/`1.1.1.1`, которые не знают локальный домен (`bg.ru`) → `NXDOMAIN`.

### 3. `xray run -test` падает без root
Версия xray 26.3.27 при `-test` пытается создать TUN-интерфейс, что требует root. Без sudo падает с `operation not permitted`.

## Причины

1. **ICMP:** UFW INPUT policy `DROP` + отсутствие conntrack state для ICMP через xray TUN.
2. **DNS:** glibc `rotate` равномерно распределяет запросы между всеми `nameserver` в `resolv.conf`, включая публичные DNS, не знающие локальные зоны.
3. **Config check:** `run-xray-tun-subvost.sh` запускал `xray run -test` от обычного пользователя.

## Исправления

### ICMP fix
```bash
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

cleanup_ufw_icmp_fix() {
  local route_value
  if ! command -v iptables >/dev/null 2>&1; then
    return 0
  fi
  for route_value in $VPN_EXCLUDED_IPV4_ROUTES; do
    sudo iptables -t filter -D INPUT -p icmp --icmp-type echo-reply -s "$route_value" -j ACCEPT >/dev/null 2>&1 || true
  done
}
```

### DNS rotate fix
```bash
# Было:
echo "options timeout:2 attempts:2 rotate"
# Стало:
echo "options timeout:2 attempts:2"
```

### Sudo config check fix
```bash
# Было:
if ! XRAY_LOCATION_ASSET="$XRAY_ASSET_DIR" "$XRAY_BIN" run -test -c "$XRAY_RUNTIME_CONFIG" ...
# Стало:
if ! sudo XRAY_LOCATION_ASSET="$XRAY_ASSET_DIR" "$XRAY_BIN" run -test -c "$XRAY_RUNTIME_CONFIG" ...
```

## Изменённые файлы

- `libexec/run-xray-tun-subvost.sh` — добавлен `apply_ufw_icmp_fix()`, `cleanup_ufw_icmp_fix()`, убран `rotate`, добавлен `sudo` для config check
- `libexec/stop-xray-tun-subvost.sh` — добавлен `cleanup_ufw_icmp_fix()`, чтение `VPN_EXCLUDED_IPV4_ROUTES` из state-файла

## Проверка

1. ICMP echo-reply из `10.0.0.0/14` проходит через UFW ✅
2. `ping v2` / `ping v38` / `ping V56` / `ping v69` стабильно работают ✅
3. `xray run -test` проходит без ошибок ✅

## Ручные проверки

- [x] Полный цикл stop → start через GUI
- [x] Ping LAN-хостов после старта VPN
- [x] Проверка `iptables -L INPUT | grep icmptype 0`

## Контур публикации

- **Host:** none
- **Тип публикации:** none
- **Статус:** local

---

## Ссылки

- `libexec/run-xray-tun-subvost.sh`
- `libexec/stop-xray-tun-subvost.sh`
