# План TASK-2026-0043

## Кратко

Перевести GUI на пользовательский backend и оставить root-доступ только на действиях `Старт`, `Стоп` и `Диагностика` через `pkexec`.

## Изменения

- Launcher:
  - запускать `gui/gui_server.py` из `libexec/open-subvost-gui.sh` как текущего пользователя;
  - хранить PID и лог пользовательского backend в `/tmp/subvost-xray-tun-gui-user-<uid>.*`;
  - при `--force-restart-backend` перезапускать только пользовательский backend, не запрашивая root;
  - если порт занят несовместимым backend, завершаться с понятной ошибкой вместо раннего `pkexec`.

- Ярлык desktop:
  - убрать `--force-restart-backend` из корневого `subvost-xray-tun.desktop`;
  - убрать этот флаг из шаблона `libexec/install-subvost-gui-menu-entry.sh`;
  - сохранить self-locating запуск корневого ярлыка через `%k`.

- GUI backend:
  - заменить fallback `sudo` на `pkexec env ... /usr/bin/env bash <script>` для root-действий из user-backend;
  - оставить прямой вызов скриптов только для root-backend;
  - передавать в privileged action пользовательский контекст и action-specific env;
  - обновить runtime label и флаги статуса под `pkexec`.

- Web UI:
  - сделать кнопку `Стоп` доступной при любом runtime-состоянии;
  - сохранять временную блокировку `Стоп` только на время другой выполняющейся операции.

- Документация и task-контур:
  - обновить README и AGENTS под новый privilege-flow;
  - добавить выбор доступного apt-пакета для команды `pkexec`: `pkexec` или `policykit-1`;
  - поднять `GUI_VERSION`;
  - добавить регрессионные тесты и синхронизировать реестр задач.

## Проверки

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py gui/embedded_webview.py`
- `python3 -m unittest tests.test_gui_server tests.test_embedded_webview`
- `desktop-file-validate subvost-xray-tun.desktop`, если команда доступна
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py README.md AGENTS.md knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0043-gui-user-backend-pkexec-actions/task.md knowledge/tasks/TASK-2026-0043-gui-user-backend-pkexec-actions/plan.md`

## Остаточный риск

Live-smoke с реальным `pkexec`, `xray`, `tun0`, DNS и desktop-сеансом нужно выполнить вручную на целевой машине после статических проверок.

## Итог выполнения

Статус задачи: `на проверке`.

Выполнено:

- GUI launcher переведён на пользовательский backend без раннего `pkexec`;
- root-действия GUI переведены на `pkexec`;
- кнопка `Стоп` больше не зависит от состояния runtime;
- desktop-entry и installer ярлыка обновлены;
- installer новой машины выбирает доступный apt-пакет для команды `pkexec`: `pkexec` или `policykit-1`;
- `GUI_VERSION`, README, AGENTS, тесты и реестр задач синхронизированы.

Проверки пройдены:

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py gui/embedded_webview.py`
- `python3 -m unittest tests.test_gui_server tests.test_embedded_webview`
- `python3 -m unittest tests.test_subvost_parser tests.test_subvost_store tests.test_subvost_runtime tests.test_gui_server tests.test_embedded_webview`
- `python3 -m json.tool xray-tun-subvost.json`
- `desktop-file-validate subvost-xray-tun.desktop`
- `git diff --check`
- адресный `markdown-localization-guard`
