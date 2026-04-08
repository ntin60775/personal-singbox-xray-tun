# План TASK-2026-0047

## Кратко

Привязать VPN runtime к identity текущего bundle и сделать явные ownership-guards в GUI и shell-сценариях, чтобы одна копия bundle не останавливала runtime другой копии под тем же пользователем.

## Изменения

- GUI backend:
  - добавить helpers для классификации ownership runtime по state-файлу;
  - не считать foreign runtime управляемым текущим bundle;
  - заблокировать `Старт` и `Стоп` API-сценарии для foreign/unknown runtime с понятной диагностикой;
  - при закрытии embedded-окна закрывать только UI/backend, если активен foreign runtime, без попытки его остановить.

- Shell:
  - в `libexec/run-xray-tun-subvost.sh` записывать identity текущего bundle в `STATE_FILE`;
  - в `libexec/run-xray-tun-subvost.sh` и `libexec/stop-xray-tun-subvost.sh` различать current / foreign / unknown state и печатать безопасные сообщения;
  - не использовать небезопасный stop-path для foreign или legacy state без ownership-маркера.

- UI и тесты:
  - обновить `gui/main_gui.html`, чтобы dangerous-кнопки не выглядели доступными при foreign runtime;
  - обновить `tests/test_gui_server.py` строковыми и behavioral-проверками нового ownership-контракта;
  - при необходимости добавить строковые shell-проверки на `BUNDLE_PROJECT_ROOT`.

## Проверки

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py`
- `python3 -m unittest tests.test_gui_server`
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0047-runtime-ownership-isolation/task.md knowledge/tasks/TASK-2026-0047-runtime-ownership-isolation/plan.md`
- ручной desktop-smoke в репозитории подтверждён пользователем

## Риски и зависимости

- Старые state-файлы без ownership-маркера будут трактоваться консервативно, чтобы не гасить runtime неизвестного происхождения.
- Для других desktop-сред и вариантов `pkexec` может понадобиться отдельный smoke, но подтверждённый сценарий в репозитории закрывает целевой риск foreign runtime.

## Шаги

- [x] Открыть task-контур и добавить запись в реестр.
- [x] Реализовать ownership identity в runtime state и shell-guards.
- [x] Добавить ownership-классификацию и safe-guards в GUI backend.
- [x] Обновить UI-кнопки и тесты под новый контракт.
- [x] Прогнать проверки, получить подтверждение ручного smoke и зафиксировать итоговый статус.

## Критерии завершения

- current bundle не останавливает foreign runtime;
- GUI явно различает свой и чужой runtime;
- проверки проходят;
- task-контур переведён в `завершена` после подтверждённого smoke.
