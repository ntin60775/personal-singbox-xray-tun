# Карточка задачи TASK-2026-0043

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0043` |
| Parent ID | `—` |
| Уровень вложенности | `0` |
| Ключ в путях | `TASK-2026-0043` |
| Технический ключ для новых именуемых сущностей | `—` |
| Краткое имя | `gui-user-backend-pkexec-actions` |
| Статус | `на проверке` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `main` |
| Дата создания | `2026-04-07` |
| Дата обновления | `2026-04-07` |

## Цель

Сделать запуск `subvost-xray-tun.desktop` пользовательским действием без раннего запроса root-доступа, а root-подтверждение через `pkexec` показывать только при действиях `Старт`, `Стоп` и `Диагностика` в GUI.

## Границы

### Входит

- запуск GUI backend от текущего пользователя;
- перенос privilege prompt с открытия GUI на root-действия GUI;
- сохранение self-locating desktop launcher;
- постоянная доступность кнопки `Стоп`, кроме момента выполнения другой операции;
- регрессионные проверки shell, Python, GUI-контракта и Markdown-локализации.

### Не входит

- переписывание runtime-скриптов `xray`;
- замена `pkexec` на `sudo`;
- удаление старого внутреннего helper-а `libexec/start-gui-backend-root.sh`;
- ручной live-smoke с реальным вводом пароля в `pkexec` внутри этой автоматизированной сессии.

## Контекст

Пользователь ожидает, что запуск `subvost-xray-tun.desktop` просто откроет UI, а не стартует runtime и не требует root-доступ сразу. `run-xray-tun-subvost.sh` должен запускаться кнопкой `Старт` в UI, после чего появляется проверка и запрос root через `pkexec`. Кнопка `Стоп` не должна блокироваться состоянием кнопки `Старт`.

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Launcher | `open-subvost-gui.sh` запускает пользовательский backend и не вызывает `pkexec` при открытии UI |
| Desktop entry | ярлык открывает GUI без `--force-restart-backend` |
| GUI backend | root-действия выполняются через `pkexec env ... /usr/bin/env bash <script>` |
| Web UI | `Стоп` доступен независимо от состояния runtime |
| Installer | `install-on-new-pc.sh` выбирает доступный пакет для `pkexec`: `pkexec` или `policykit-1` |
| Документация | обновляются README, AGENTS, task-артефакты и реестр |

## Стратегия проверки

### Покрывается кодом или тестами

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py gui/embedded_webview.py`
- `python3 -m unittest tests.test_gui_server tests.test_embedded_webview`
- `desktop-file-validate subvost-xray-tun.desktop`, если команда доступна
- адресный запуск `markdown-localization-guard` для изменённых Markdown-файлов

### Остаётся на ручную проверку

- запуск `subvost-xray-tun.desktop` в desktop-сеансе без раннего `pkexec`;
- нажатие `Старт` с реальным `pkexec` и проверкой `xray`/`tun0`;
- нажатие `Стоп` при остановленном и запущенном runtime;
- запуск `Диагностика` из GUI с реальным `pkexec`.

## Критерии готовности

- запуск GUI не требует root-доступа;
- `Старт`, `Стоп` и `Диагностика` из пользовательского backend запрашивают root-доступ через `pkexec`;
- `Стоп` не блокируется состоянием runtime;
- статические проверки и релевантные unit-тесты проходят;
- task-артефакты и реестр синхронизированы.

## Итог

Реализован новый privilege-flow для GUI. `open-subvost-gui.sh` теперь запускает `gui/gui_server.py` как пользовательский backend и не вызывает `pkexec` при открытии UI. Корневой `subvost-xray-tun.desktop` и installer пользовательского ярлыка больше не передают `--force-restart-backend` по умолчанию, поэтому запуск ярлыка не должен показывать root-запрос. Installer новой машины дополнительно выбирает доступный apt-пакет для команды `pkexec`: `pkexec` или `policykit-1`.

Backend-действия `Старт`, `Стоп` и `Диагностика` из пользовательского режима переведены с терминального `sudo` на явную команду `pkexec env ... /usr/bin/env bash <script>` с передачей пользовательского контекста. Для root-backend оставлен прямой вызов скриптов. В web UI кнопка `Стоп` больше не блокируется состоянием stopped/runtime и отключается только на время выполняющейся операции.

Локально пройдены `bash -n *.sh`, `bash -n libexec/*.sh`, `bash -n lib/*.sh`, `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py gui/embedded_webview.py`, `python3 -m unittest tests.test_gui_server tests.test_embedded_webview`, полный набор `python3 -m unittest tests.test_subvost_parser tests.test_subvost_store tests.test_subvost_runtime tests.test_gui_server tests.test_embedded_webview`, `python3 -m json.tool xray-tun-subvost.json`, `desktop-file-validate subvost-xray-tun.desktop`, `git diff --check` и адресный `markdown-localization-guard`.

Остаточный риск: в этой сессии не выполнялся живой desktop-smoke с реальным системным `pkexec`, стартом `xray`, появлением `tun0`, проверкой DNS и последующей остановкой. Это нужно подтвердить на целевой машине вручную.
