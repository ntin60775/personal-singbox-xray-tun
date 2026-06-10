# План задачи TASK-2026-0053.3

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0053.3` |
| Parent ID | `TASK-2026-0053` |
| Версия плана | `1` |
| Дата обновления | `2026-04-09` |

## Цель

Собрать полноценный vertical slice `Subscriptions` для native shell так, чтобы store/routing сценарии стали общими для web GUI и `GTK4` клиента, а экран подписок дал реальную пользовательскую ценность до начала работ над `Log`.

## Границы

### Входит

- общий store/routing snapshot и mutation-методы в `subvost_app_service.py`;
- thin-wrapper store/routing handlers в `gui_server.py`;
- рабочий native экран `Subscriptions`;
- helper-слой выбора подписки и ping-cache в `native_shell_shared.py`;
- unit-тесты и синхронизация task-артефактов.

### Не входит

- экран `Log`;
- rollout launcher-а на native GUI по умолчанию;
- общий финальный manual smoke `TASK-2026-0053`.

## Планируемые изменения

### Код

- добавить в `gui/subvost_app_service.py`:
  - `collect_store_snapshot()`;
  - общий builder store-response envelope;
  - store/routing action-методы для подписок, узлов, `ping` и routing;
- перевести `gui/gui_server.py` на thin-wrapper вызовы service-layer для store/routing handlers;
- заменить placeholder `Subscriptions` в `gui/native_shell_app.py` на рабочий layout:
  - верхнюю строку импорта URL-подписки;
  - список подписок;
  - список узлов;
  - routing textarea, статус и список профилей;
- перевести polling native shell с `status-only` на combined snapshot `store + status`;
- добавить в `gui/native_shell_shared.py` helper-логику выбора текущей подписки и чтения ping-cache.

### Документация

- открыть и сразу закрыть подзадачу `TASK-2026-0053.3`;
- обновить родительские `task.md` и `plan.md` под новый фактический этап;
- синхронизировать `knowledge/tasks/registry.md`.

## Риски и зависимости

- нельзя менять shape текущих `/api/store` и store/routing action-ответов web GUI;
- нельзя допустить второй backend-контур для native shell поверх собственного `HTTP`;
- inline-actions native shell должны уважать общий busy-lock, иначе появятся гонки refresh/activate/delete;
- ручной smoke нельзя “растворить” внутри подзадачи: он остаётся только на родительском уровне.

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

Отдельных ручных проверок внутри `TASK-2026-0053.3` не остаётся. Реальные сценарии `pkexec`, launcher, tray и `tun0` остаются в едином финальном smoke-листе родительской `TASK-2026-0053`.

## Шаги

- [x] Открыть подзадачу и синхронизировать реестр
- [x] Поднять store/routing snapshot и mutation-операции в `subvost_app_service.py`
- [x] Перевести web backend на thin-wrapper store/routing handlers поверх service-layer
- [x] Реализовать рабочий экран `Subscriptions` в native shell
- [x] Добавить helper-логику выбора текущей подписки и ping-cache для headless-тестов
- [x] Прогнать unit/syntax проверки и зафиксировать результат

## Критерии завершения

- native shell получает рабочий `Subscriptions` vertical slice;
- web GUI остаётся совместимым по существующему store/routing `HTTP` контракту;
- store/routing действия не дублируются между native shell и `gui_server.py`;
- task-артефакты и реестр синхронизированы;
- ручной интеграционный хвост остаётся только на родительской задаче.

## Фактический результат

- `gui/subvost_app_service.py` стал единым store/routing orchestration-слоем для native shell и web backend;
- `gui/gui_server.py` переведён на thin-wrapper вызовы service-layer для `store`, подписок, узлов и routing;
- `gui/native_shell_app.py` получил рабочий экран `Subscriptions` с combined snapshot, локальным выбором подписки и async store/routing actions;
- `gui/native_shell_shared.py` дополнен helper-функциями для выбора текущей подписки, чтения routing/store snapshot и action labels;
- тесты `tests/test_subvost_app_service.py`, `tests/test_native_shell_app.py`, `tests/test_native_shell_shared.py` и `tests/test_gui_server.py` синхронизированы с новым контрактом.
