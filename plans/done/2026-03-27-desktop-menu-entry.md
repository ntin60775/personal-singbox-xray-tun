# Установка ярлыка bundle в меню приложений

- Дата: 2026-03-27
- Статус: done
- Источник: запрос пользователя на добавление `Subvost Xray TUN GUI` в меню приложений

## Цель

Сделать поддерживаемую установку ярлыка bundle в меню приложений Linux так, чтобы пункт меню запускал публичный `open-subvost-gui.sh` из текущего каталога bundle.

## Изменения

- Добавить отдельный public-скрипт для установки desktop-entry в `~/.local/share/applications`.
- Реализовать internal shell-логику генерации `.desktop` с абсолютными путями к launcher и иконке текущего bundle.
- Обновить README и описать разницу между portable desktop launcher внутри bundle и установленным пунктом меню.

## Проверки

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- Ручной smoke: выполнить installer ярлыка и убедиться, что файл появился в `~/.local/share/applications`.

## Допущения

- Bundle продолжает работать из текущего каталога и не копируется в системные директории.
- Если каталог bundle будет перемещён, ярлык в меню нужно переустановить, потому что он использует абсолютные пути к текущему расположению.

## Итог

- Добавлен public-скрипт `install-subvost-gui-menu-entry.sh` и internal-реализация `libexec/install-subvost-gui-menu-entry.sh`.
- Installer создаёт `~/.local/share/applications/subvost-xray-tun.desktop` с абсолютными путями к текущим `open-subvost-gui.sh` и `assets/subvost-xray-tun-icon.svg`.
- README обновлён: описан поддерживаемый сценарий установки ярлыка в меню приложений и ограничение при переносе bundle в другой каталог.
- Локальные проверки `bash -n *.sh`, `bash -n libexec/*.sh`, `bash -n lib/*.sh` и `python3 -m py_compile gui/gui_server.py` прошли успешно.
- Ручной smoke подтверждён: файл `/home/prog7/.local/share/applications/subvost-xray-tun.desktop` создан.
