# Принудительный restart GUI backend при запуске через ярлык

- Дата: 2026-03-28
- Статус: done
- Источник: запрос пользователя сделать так, чтобы каждый запуск приложения через ярлык принудительно перезапускал серверную часть

## Цель

Сделать поведение GUI launcher предсказуемым для desktop-сценариев: каждый запуск через ярлык должен не переиспользовать старый backend, а инициировать его принудительный restart и затем открывать веб-интерфейс уже на новом процессе.

Ожидаемый результат: и portable `subvost-xray-tun.desktop`, и ярлык, установленный через `install-subvost-gui-menu-entry.sh`, всегда запускают `open-subvost-gui.sh` в режиме forced restart backend; при этом ручной запуск `./open-subvost-gui.sh` без специальных аргументов сохраняет текущую модель поведения.

## Изменения

- Добавить в `open-subvost-gui.sh`-цепочку явный режим принудительного restart backend для desktop-launch сценариев.
- Обновить portable `subvost-xray-tun.desktop`, чтобы он передавал launcher'у этот режим явно.
- Обновить генерацию installed desktop entry в `install-subvost-gui-menu-entry.sh`, чтобы пункт меню приложений вёл себя так же, как portable ярлык.
- Кратко отразить новое поведение в README для раздела GUI.

## Проверки

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m py_compile gui/gui_server.py`
- `desktop-file-validate subvost-xray-tun.desktop`
- Статическая проверка generated desktop entry template в installer-скрипте

## Допущения

- Принудительный restart нужен именно для desktop-launch сценариев; ручной `./open-subvost-gui.sh` без аргументов не обязан всегда перезапускать backend.
- Для принудительного restart допустимо использовать уже существующий `pkexec -> start-gui-backend-root.sh` путь с `SUBVOST_GUI_RESTART=1`, без добавления отдельного HTTP API shutdown.

## Итог

Добавлен явный флаг `--force-restart-backend` в `libexec/open-subvost-gui.sh`: при его наличии launcher всегда идёт в `pkexec`-цепочку и вызывает `start-gui-backend-root.sh` с `SUBVOST_GUI_RESTART=1`, не пытаясь переиспользовать уже поднятый backend. При обычном ручном запуске `./open-subvost-gui.sh` прежняя логика совместимого reuse сохранена.

Portable `subvost-xray-tun.desktop` и desktop entry, который генерирует `install-subvost-gui-menu-entry.sh`, теперь оба передают launcher'у `--force-restart-backend`. Это фиксирует требуемое поведение именно для ярлыков: каждый запуск через ярлык приводит к принудительному restart серверной части перед открытием браузера.

README обновлён под новое поведение GUI launcher. Статические проверки `bash -n *.sh`, `bash -n libexec/*.sh`, `bash -n lib/*.sh`, `python3 -m py_compile gui/gui_server.py` и `desktop-file-validate subvost-xray-tun.desktop` прошли без ошибок. Остаточный риск: в этой сессии не выполнялся ручной smoke реального desktop-launch с `pkexec`, поэтому фактический restart backend через системный ярлык нужно подтвердить отдельно на целевой машине.
