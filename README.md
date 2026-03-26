# Subvost Xray TUN Bundle

Этот каталог содержит переносимый комплект для запуска `Xray + sing-box` в `TUN`-режиме.

## Что внутри

- `run-xray-tun-subvost.sh` — запуск стека
- `stop-xray-tun-subvost.sh` — остановка стека
- `capture-xray-tun-state.sh` — единый диагностический скрипт: собирает сетевое состояние, DNS, `curl`-проверки, правила маршрутизации/фаервола и хвосты логов в один файл
- `xray-tun-subvost.json` — конфиг `Xray`
- `singbox-tun-subvost.json` — конфиг `sing-box`
- `logs/` — снимки состояния и диагностические логи при включенном логировании или сбоях

## Зависимости

- `xray` должен быть доступен в одном из путей: `${HOME}/.local/bin/xray`, путь из `command -v xray`, `/usr/local/bin/xray`, `/usr/bin/xray`
- `sing-box` должен быть доступен в одном из путей: путь из `command -v sing-box`, `/usr/local/bin/sing-box`, `/usr/bin/sing-box`
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

## Установка на другой ПК

Если каталог перенесен на другую машину, выполните:

```bash
bash /путь/к/install-on-new-pc.sh
```

Скрипт установки:

- не копирует bundle и не создает обёртки,
- ставит системные зависимости,
- устанавливает `xray` и `sing-box`,
- для `sing-box` подключает официальный APT-репозиторий SagerNet,
- для `xray` использует официальный `XTLS/Xray-install`; при необходимости можно зафиксировать ref через `XRAY_INSTALL_REF`,
- проверяет доступность бинарников после установки.

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
