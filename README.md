# Subvost Xray TUN Bundle

Этот каталог содержит переносимый bundle для запуска `Xray + sing-box` в `TUN`-режиме.

## Структура

Публичная поверхность bundle в корне:

- `run-xray-tun-subvost.sh` — запуск стека
- `stop-xray-tun-subvost.sh` — остановка стека
- `capture-xray-tun-state.sh` — единый диагностический скрипт
- `open-subvost-gui.sh` — пользовательский launcher GUI
- `install-on-new-pc.sh` — установка зависимостей на Debian/Ubuntu
- `subvost-xray-tun.desktop` — portable desktop launcher
- `xray-tun-subvost.json` и `singbox-tun-subvost.json` — operator-managed runtime-конфиги
- `logs/` — runtime-логи и диагностические дампы
- `plans/` — инженерные планы задач

Внутренние компоненты:

- `lib/` — общий shell-модуль с вычислением корня bundle и layout-путей
- `libexec/` — реальные shell-реализации, в которые `exec`-ятся корневые wrapper'ы
- `gui/` — Python backend локального GUI
- `docs/research/` — исследовательские и разовые аналитические документы
- `assets/` — repo-managed вспомогательные артефакты, включая SVG-иконку bundle

Корневые wrapper'ы всегда сами вычисляют корень проекта по своему физическому пути и переопределяют `SUBVOST_PROJECT_ROOT`. Ручная подстановка этой переменной пользователем не считается поддерживаемым интерфейсом.

## Зависимости

- `xray` должен быть доступен в одном из путей: `${HOME}/.local/bin/xray`, путь из `command -v xray`, `/usr/local/bin/xray`, `/usr/bin/xray`
- `sing-box` должен быть доступен в одном из путей: путь из `command -v sing-box`, `/usr/local/bin/sing-box`, `/usr/bin/sing-box`
- нужен `python3`: bundle использует его для GUI launcher/backend и для runtime-разбора `SINGBOX_CONFIG`
- нужен `sudo`
- файловые логи по умолчанию выключены; чтобы включить их, задай `ENABLE_FILE_LOGS=1`

Если на другом ПК бинарники лежат в другом месте, можно переопределить пути через переменные окружения:

```bash
export XRAY_BIN="/нужный/путь/xray"
export SINGBOX_BIN="/нужный/путь/sing-box"
export ENABLE_FILE_LOGS=1
```

## Запуск

```bash
sudo /путь/к/run-xray-tun-subvost.sh
```

Если нужны постоянные файловые логи:

```bash
ENABLE_FILE_LOGS=1 sudo /путь/к/run-xray-tun-subvost.sh
```

## GUI-пульт

Для повседневного использования добавлены:

- `open-subvost-gui.sh` — пользовательский launcher: при клике/запуске сам поднимает backend через `pkexec`, ждёт порт и автоматически открывает страницу в браузере
- `subvost-xray-tun.desktop` — portable desktop launcher
- `gui/gui_server.py` — internal backend и веб-интерфейс
- `libexec/start-gui-backend-root.sh` — internal root-bootstrap для `pkexec`

Обычный сценарий:

1. Нажать мышкой `subvost-xray-tun.desktop` или `open-subvost-gui.sh`.
2. Подтвердить пароль в системном окне `pkexec`.
3. Дождаться автоматического открытия страницы `http://127.0.0.1:8421`.

Что умеет GUI:

- `Старт` — запускает `run-xray-tun-subvost.sh`
- `Стоп` — запускает `stop-xray-tun-subvost.sh`
- `Снять диагностику` — запускает `capture-xray-tun-state.sh`
- показывает текущее состояние стека, PID'ы, `tun0`, DNS и базовую информацию о соединении
- даёт переключатель файлового логирования; настройка применяется при следующем запуске

`subvost-xray-tun.desktop` self-locating: `Exec` использует `%k`, вычисляет каталог bundle по пути к самому desktop-файлу и запускает только публичный `open-subvost-gui.sh`. Поддерживаемый сценарий переносимости: launcher хранится внутри самого bundle и запускается оттуда. Для `Icon` используется portable системный fallback, а repo-managed SVG лежит в `assets/`.

## Установка на другой ПК

Если каталог перенесён на другую машину, выполните:

```bash
bash /путь/к/install-on-new-pc.sh
```

Скрипт установки:

- не копирует bundle и не создаёт обёртки
- ставит системные зависимости
- ставит `python3` как обязательную runtime-зависимость bundle
- устанавливает `xray` и `sing-box`
- для `sing-box` подключает официальный APT-репозиторий SagerNet
- для `xray` использует официальный `XTLS/Xray-install`; при необходимости можно зафиксировать ref через `XRAY_INSTALL_REF`
- после установки `xray` переводит его в portable-режим bundle: отключает и удаляет ненужный `xray.service`, его drop-in'ы и системный `config.json`, которые upstream installer создаёт по умолчанию
- если одновременно найдены системный `xray` и `${HOME}/.local/bin/xray`, installer сравнивает их; идентичный пользовательский дубликат удаляется автоматически, а при разных бинарниках installer останавливается с явным сообщением
- проверяет доступность бинарников после установки

После этого bundle нужно запускать из того каталога, где он уже лежит:

```bash
sudo /путь/к/run-xray-tun-subvost.sh
```

## Остановка

```bash
/путь/к/stop-xray-tun-subvost.sh
```

## Диагностика

```bash
sudo /путь/к/capture-xray-tun-state.sh
```

Скрипт сам складывает полный дамп в `logs/xray-tun-state-YYYYMMDD-HHMMSS.log` и печатает путь к файлу.

Скрытый файл состояния хранится в `${HOME}/.xray-tun-subvost.state`.

## Troubleshooting

Если старт не дошёл до `Готово` или трафик не пошёл через туннель, проверяй систему в одном и том же порядке:

1. `TUN-устройство`

```bash
ls -l /dev/net/tun
lsmod | grep tun
```

Если `/dev/net/tun` отсутствует или модуль `tun` не загружен, `sing-box` не сможет создать TUN-интерфейс из текущего `SINGBOX_CONFIG`.

2. `Интерфейс`

```bash
ip -brief link show tun0
ip -brief address show tun0
```

После старта ожидается TUN-интерфейс из текущего `SINGBOX_CONFIG` в состоянии `UP` и с назначенным адресом.

3. `Маршруты и policy-routing`

```bash
ip rule show
ip route show table main
ip route show table all | grep -E 'tun|xray'
```

Минимальный инвариант для bundle: после старта должен появиться ожидаемый TUN-интерфейс из текущего `SINGBOX_CONFIG` и получить адрес, описанный в этом конфиге. Конкретные маршруты и split-tunnel-поведение остаются operator-managed, поэтому проверка не должна зависеть ни от одного фиксированного внешнего IP, ни от обязательного наличия IPv4-маршрута определённого вида.

4. `DNS`

```bash
ls -l /etc/resolv.conf
readlink -f /etc/resolv.conf
cat /etc/resolv.conf
systemctl is-active systemd-resolved
systemctl is-active NetworkManager
resolvectl status
```

Если `run-xray-tun-subvost.sh` предупреждает про `systemd-resolved` или `NetworkManager`, это не блокирует старт само по себе: bundle всё равно временно перепишет `/etc/resolv.conf` и затем восстановит его. Такие предупреждения означают только повышенный риск DNS-гонок при проблемах с сетью, поэтому в спорных случаях сразу снимай полный диагностический дамп. Постоянную перенастройку этих сервисов bundle автоматически не делает.

5. `Firewall`

```bash
nft list ruleset
iptables-save
ip6tables-save
```

Bundle не настраивает `iptables`/`nftables` автоматически. На обычном клиенте NAT и `ip_forward` не включаются; здесь нужно только убедиться, что локальный firewall не ломает трафик через ожидаемый TUN-интерфейс.

6. `MTU`

```bash
ip link show tun0
```

Если туннель поднялся, но часть сайтов зависает или соединения рвутся, проверь текущий `mtu` у ожидаемого TUN-интерфейса и отдельно протестируй ручное снижение MTU как диагностический fallback. Автоматически bundle MTU не меняет.

Для полного дампа состояния используй:

```bash
sudo /путь/к/capture-xray-tun-state.sh
```

## Исследовательские документы

Разовые исследования и аналитика лежат в `docs/research/`. Текущий отчёт для дальнейшего hardening: `docs/research/deep-research-report.md`.
