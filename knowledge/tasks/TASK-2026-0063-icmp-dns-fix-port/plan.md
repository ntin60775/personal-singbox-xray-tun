# План TASK-2026-0063

## Цель

Портировать три исправления из рабочего bundle `subvost-xray-tun` в основной репозиторий `personal-singbox-xray-tun`.

## Этапы

### 1. Расследование (completed)
- Пользователь сообщил, что часть LAN-хостов не пингуется через VPN
- Выявлено: ICMP echo-reply блокируется UFW, т.к. conntrack не видит связь запроса (через xray TUN) и ответа (на eth0)
- Выявлено: DNS резолв коротких имён нестабилен из-за `options rotate` в resolv.conf
- Выявлено: `xray run -test` в версии 26.3.27 требует root для создания TUN

### 2. Исправление в subvost-xray-tun (completed)
- Добавлен `apply_ufw_icmp_fix()` / `cleanup_ufw_icmp_fix()` в `run`/`stop`
- Убран `rotate` из `write_runtime_resolv_conf()`
- Добавлен `sudo` для `xray run -test`

### 3. Портирование в personal-singbox-xray-tun (completed)
- Аналогичные изменения применены к `libexec/run-xray-tun-subvost.sh`
- Аналогичные изменения применены к `libexec/stop-xray-tun-subvost.sh`

### 4. Документирование (completed)
- Создан `task.md`
- Создан `plan.md`
- Обновлён `registry.md`

## Артефакты

- `libexec/run-xray-tun-subvost.sh` — изменён
- `libexec/stop-xray-tun-subvost.sh` — изменён
- `knowledge/tasks/TASK-2026-0063-icmp-dns-fix-port/task.md`
- `knowledge/tasks/TASK-2026-0063-icmp-dns-fix-port/plan.md`
