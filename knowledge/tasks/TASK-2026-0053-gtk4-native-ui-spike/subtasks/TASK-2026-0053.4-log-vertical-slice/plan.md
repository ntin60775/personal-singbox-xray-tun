# План задачи TASK-2026-0053.4

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0053.4` |
| Parent ID | `TASK-2026-0053` |
| Версия плана | `1` |
| Дата обновления | `2026-04-10` |

## Цель

Закрыть `Log` как последний функциональный vertical slice внутри `TASK-2026-0053`, чтобы нативный `GTK4`-клиент показывал ошибки и журналы не хуже текущего web UI по базовому operational flow.

## Границы

### Входит

- helper-слой лога в `gui/native_shell_shared.py`;
- экран `Log` в `gui/native_shell_app.py`;
- copy/export видимого лога;
- unit-тесты и синхронизация документации.

### Не входит

- полный rollout и manual smoke `TASK-2026-0053`;
- переработка backend log-retention;
- новые API-роуты или отдельный log-backend для native shell.

## Планируемые изменения

### Код

- добавить headless helper-логику для фильтрации, подписей и экспортного текста лога;
- хранить локальный shell-log не только как строки, но и как структурированные записи;
- заменить текущий placeholder экрана `Log` на рабочий UI с:
  - фильтром `Все / Ошибки / Предупреждения / Инфо`;
  - сводкой по последней ошибке;
  - показом источников `native shell` и `bundle/runtime`;
  - кнопками `Скопировать` и `Экспорт`;
- обновлять экран лога при любом refresh snapshot и локальных shell-событиях.

### Документация

- довести `task.md` и `plan.md` этой подзадачи до завершённого состояния;
- синхронизировать родительские `task.md`, `plan.md` и `knowledge/tasks/registry.md`.

## Риски и зависимости

- нельзя потерять текущий shared `service-layer` контракт и уходить в новый `HTTP`-контур;
- нельзя сломать существующие unit-тесты `TASK-2026-0053.3`, так как worktree уже содержит незакоммиченный этап подписок;
- copy/export не должны требовать `pkexec` или менять системную конфигурацию;
- живой clipboard зависит от рабочего `GTK` display, поэтому нужен безопасный fallback-статус при недоступности буфера обмена.

## Проверки

### Что можно проверить кодом или тестами

- `python3 -m unittest tests.test_native_shell_shared tests.test_native_shell_app`
- `python3 -m py_compile gui/native_shell_shared.py gui/native_shell_app.py`
- локализационная проверка Markdown для новых и обновлённых task-артефактов.

### Что уже проверено

- `python3 -m unittest tests.test_native_shell_shared tests.test_native_shell_app tests.test_subvost_app_service tests.test_gui_server`
- `python3 -m py_compile gui/native_shell_shared.py gui/native_shell_app.py gui/subvost_app_service.py gui/gui_server.py`

### Что остаётся на ручную проверку

- реальный clipboard/export flow в живой `GTK` сессии;
- общий финальный smoke родительской `TASK-2026-0053` с tray, launcher, `pkexec` и runtime.

## Шаги

- [x] Открыть подзадачу и синхронизировать реестр
- [x] Вынести helper-логику Log view-model в headless-слой
- [x] Реализовать рабочий экран `Log` в native shell
- [x] Добавить unit-покрытие и прогнать проверки
- [x] Закрыть подзадачу и синхронизировать родительские артефакты

## Критерии завершения

- native shell получает рабочий `Log` vertical slice вместо минимального shell-буфера;
- фильтрованный лог можно скопировать или экспортировать без root-действий;
- источник истины по backend/runtime-логам остаётся тем же `service-layer` snapshot;
- task-артефакты и родительский knowledge-контур синхронизированы;
- ручной интеграционный хвост остаётся только у родительской задачи.

## Фактический результат

- `gui/native_shell_shared.py` получил helper-слой для фильтрации log entries, выбора последней ошибки и сборки фильтрованного экспортного текста;
- `gui/native_shell_app.py` хранит shell-журнал как структурированные записи и показывает экран `Log` с двумя источниками, фильтром по уровню и действиями `Скопировать`/`Экспорт`;
- тесты `tests/test_native_shell_shared.py` и `tests/test_native_shell_app.py` расширены под новый log-контур;
- регрессионно подтверждено, что `tests.test_subvost_app_service` и `tests.test_gui_server` не сломались после этапа `TASK-2026-0053.4`.
