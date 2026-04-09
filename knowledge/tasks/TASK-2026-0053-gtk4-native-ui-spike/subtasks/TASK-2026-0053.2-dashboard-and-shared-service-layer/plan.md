# План задачи TASK-2026-0053.2

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0053.2` |
| Parent ID | `TASK-2026-0053` |
| Версия плана | `2` |
| Дата обновления | `2026-04-09` |

## Цель

Выделить общий `application/service-layer` для runtime/status части и сразу довести `Dashboard` до рабочего вертикального среза, чтобы подзадача дала и архитектурный результат, и видимую пользовательскую ценность.

## Границы

### Входит

- новый `gui/subvost_app_service.py`;
- вынос общего runtime/status orchestration из web backend-а;
- сохранение совместимого `HTTP` payload для web GUI;
- прямое использование service-layer из native shell;
- рабочий `Dashboard` с real status, метриками и runtime-действиями.

### Не входит

- `Subscriptions` backend-wire и routing editor;
- фильтрация и export-операции на экране `Log`;
- rollout launcher-а на native GUI по умолчанию;
- единый финальный live manual smoke всей `TASK-2026-0053`.

## Планируемые изменения

### Код

- собрать в `gui/subvost_app_service.py`:
  - context/state для runtime-service;
  - `collect_status`;
  - action log и traffic-метрики;
  - проверки ownership и блокирующие условия запуска/остановки;
  - `start_runtime`, `stop_runtime`, `capture_diagnostics`, `shutdown_gui`;
- перевести `gui/gui_server.py` на thin-wrapper использование service-layer, но оставить существующие patch-point-ы unit-тестов;
- подключить `gui/native_shell_app.py` к service-layer напрямую, без внутренних `HTTP` вызовов;
- заменить `Dashboard` placeholder на рабочий экран со status-strip, action-cluster, metrics cluster и runtime context panels;
- перевести tray/button actions с `stub` на реальный вызов service-layer в фоновых worker-thread-ах.

### Документация

- открыть подзадачу `TASK-2026-0053.2`;
- обновить родительские `task.md` и `plan.md`;
- синхронизировать `knowledge/tasks/registry.md`.

## Риски и зависимости

- нельзя сломать текущий `HTTP` shape payload web GUI;
- нельзя сдвинуть `pkexec` границу с runtime-действий на обычное открытие native shell;
- нельзя смешать в одном этапе `Dashboard`, `Subscriptions` и `Log`, иначе подзадача потеряет вертикальный фокус;
- без live-smoke пока нельзя считать проверенной реальную `pkexec + tun0` интеграцию, даже если unit-слой зелёный.

## Проверки

### Что можно проверить кодом или тестами

- `python3 -m unittest tests.test_subvost_app_service tests.test_native_shell_app tests.test_gui_server tests.test_native_shell_shared`
- `python3 -m py_compile gui/subvost_app_service.py gui/gui_server.py gui/native_shell_app.py gui/native_shell_shared.py`
- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- локализационная проверка Markdown для новых и обновлённых task-артефактов.

### Что уже проверено

- `python3 -m unittest tests.test_subvost_app_service tests.test_native_shell_app tests.test_gui_server tests.test_native_shell_shared`
- `python3 -m py_compile gui/subvost_app_service.py gui/gui_server.py gui/native_shell_app.py gui/native_shell_shared.py`
- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`

### Что остаётся на ручную проверку

Отдельных ручных проверок внутри `TASK-2026-0053.2` не остаётся. Сценарии реального `pkexec`, появления `tun0`, tray и launcher целиком перенесены в единый финальный smoke-лист родительской `TASK-2026-0053`.

## Шаги

- [x] Открыть подзадачу и синхронизировать реестр
- [x] Добавить общий `subvost_app_service.py`
- [x] Перевести web backend на thin-wrapper использование service-layer
- [x] Подключить `Dashboard` native shell к общему runtime-service
- [x] Заменить runtime `stub`-действия окна и tray на реальные операции
- [x] Прогнать unit/syntax проверки и зафиксировать результат

## Критерии завершения

- общий runtime/status orchestration существует вне `gui_server.py`;
- native shell получает real `Dashboard` без внутренних `HTTP` вызовов;
- web GUI остаётся совместимым по `HTTP` контракту;
- документация и реестр синхронизированы;
- live runtime-smoke целиком вынесен в единый финальный список родительской задачи, а не оставлен хвостом подзадачи.

## Фактический результат

- реализован `gui/subvost_app_service.py` с общим контекстом, логикой runtime-блокировок, status payload и `pkexec`-операциями;
- `gui/gui_server.py` использует общий слой для runtime/status helper-части и сохраняет прежний patchable handler-контракт;
- `gui/native_shell_app.py` получил worker-based refresh/action flow и рабочий `Dashboard` вместо placeholder;
- `gui/native_shell_shared.py` синхронизирован с новым состоянием runtime-действий;
- добавлены `tests/test_subvost_app_service.py` и дополнительный сценарий в `tests/test_native_shell_app.py`.
