# 2026-03-27 Синхронизация иконки desktop launcher `desktop-icon-self-sync`

Статус: done

## Цель

Убрать жёстко зашитый absolute path к SVG-иконке из `subvost-xray-tun.desktop` в репозитории и заменить его на штатную схему, при которой bundle сам синхронизирует `Icon=` под свой текущий каталог после переноса.

## Ожидаемый результат

- Канонический `subvost-xray-tun.desktop` в репозитории остаётся переносимым и не ссылается на developer-specific absolute path.
- При запуске пользовательских entrypoint'ов bundle автоматически обновляет `Icon=` на absolute path к `assets/subvost-xray-tun-icon.svg` внутри текущего `SUBVOST_PROJECT_ROOT`, если launcher-файл доступен на запись.
- README описывает новый контракт и ограничения.

## Изменения по подсистемам

- `lib/`: добавить helper для синхронизации `Icon=` в `.desktop`.
- Корневые пользовательские wrapper'ы: вызывать sync-helper до перехода во внутреннюю реализацию.
- `subvost-xray-tun.desktop`: вернуть portable fallback вместо жёсткого absolute path.
- `README.md`: обновить описание поведения launcher'а и иконки.

## Проверки

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m py_compile gui/gui_server.py`
- `desktop-file-validate subvost-xray-tun.desktop`
- Ручная локальная проверка sync-helper на временной копии `.desktop`: до вызова fallback, после вызова absolute path к `assets/subvost-xray-tun-icon.svg`

## Допущения

- `Icon=` в `.desktop` не умеет вычисляться относительно `%k`, поэтому переносимость достигается только через runtime-синхронизацию файла launcher'а.
- Автоматическая синхронизация допустима только из пользовательских entrypoint'ов; root-only entrypoint'ы не должны переписывать `.desktop`, чтобы не менять владельца файла.

## Итог

Канонический `subvost-xray-tun.desktop` возвращён к portable fallback `Icon=network-vpn`, а в `lib/subvost-common.sh` добавлен helper `subvost_sync_desktop_launcher_icon`, который переписывает `Icon=` на absolute path к `assets/subvost-xray-tun-icon.svg` в текущем bundle. Helper подключён только в пользовательские wrapper'ы `open-subvost-gui.sh` и `install-on-new-pc.sh`, поэтому launcher самоисправляется после переноса без риска изменить владельца файла при `sudo`-сценариях. README обновлён под новый контракт. Остаточные риски: до первого подходящего пользовательского запуска `.desktop` может временно показывать fallback-иконку `network-vpn`; это ожидаемое поведение и исправляется автоматически после `open-subvost-gui.sh` или `install-on-new-pc.sh`.
