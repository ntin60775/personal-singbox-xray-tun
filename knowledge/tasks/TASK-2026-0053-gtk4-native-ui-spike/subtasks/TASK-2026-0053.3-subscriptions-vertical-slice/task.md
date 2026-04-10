# Карточка задачи TASK-2026-0053.3

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0053.3` |
| Parent ID | `TASK-2026-0053` |
| Уровень вложенности | `1` |
| Ключ в путях | `TASK-2026-0053.3` |
| Технический ключ для новых именуемых сущностей | `gtk4-subscriptions-vertical-slice` |
| Краткое имя | `subscriptions-vertical-slice` |
| Статус | `завершена` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `topic/gtk4-native-ui-spike` |
| Дата создания | `2026-04-09` |
| Дата обновления | `2026-04-09` |

## Цель

Довести экран `Subscriptions` нативного `GTK4`-клиента до рабочего vertical slice без внутренних `HTTP` вызовов: URL-подписки, список узлов, отдельный `ping`, routing import и `GeoIP/Geosite` статус должны работать через общий Python `service-layer`, а web GUI обязан сохранить совместимый `HTTP` контракт.

## Подсказка по статусу

Использовать только одно из значений:

- `черновик`
- `готова к работе`
- `в работе`
- `на проверке`
- `ждёт пользователя`
- `заблокирована`
- `завершена`
- `отменена`

## Границы

### Входит

- расширение `gui/subvost_app_service.py` до общего store/routing orchestration-слоя:
  - snapshot `store + status`;
  - операции подписок;
  - активация узла;
  - `ping` узла;
  - import / activate / toggle / clear для routing-профилей;
- перевод `gui/gui_server.py` на thin-wrapper вызовы этого слоя без изменения shape текущих `/api/...` ответов;
- рабочий экран `Subscriptions` в `gui/native_shell_app.py`:
  - URL input и `Добавить`;
  - `Обновить все`;
  - список подписок с `refresh`, `enable/disable`, `delete`;
  - список узлов выбранной подписки с немедленной активацией по клику строки;
  - отдельный `Ping` без смены активного узла;
  - routing textarea, import, master toggle, clear active, список профилей и статус `GeoIP/Geosite`;
- чистые helper-правила выбора текущей подписки и чтения ping-cache в `gui/native_shell_shared.py`;
- unit-покрытие service-layer, native shell и shared helper-слоя под новый контракт.

### Не входит

- экран `Log` с фильтрами и export-операциями;
- переключение launcher-а проекта на native GUI по умолчанию;
- отдельный manual smoke всей `TASK-2026-0053` с реальным `pkexec`, `tun0`, tray и launcher-сценариями;
- расширение store-модели новыми сущностями сверх уже существующих подписок, узлов и routing-профилей;
- rename/edit/delete узлов как отдельная UX-плоскость.

## Контекст

- источник постановки: следующий рабочий этап родительской `TASK-2026-0053` после закрытия `TASK-2026-0053.2`;
- на входе `Dashboard` уже работал через общий `subvost_app_service.py`, но `Subscriptions` в native shell оставался placeholder-блоком;
- web GUI уже имел зрелые сценарии подписок, узлов, `ping` и routing, но они были размазаны по handler-логике `gui/gui_server.py`;
- пользовательское и архитектурное требование этапа: native shell не должен получить отдельный backend-контур, а web GUI не должен потерять тестируемый `HTTP` контракт.

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | `subvost_app_service.py` стал общим store/routing orchestration-слоем для native shell и web backend |
| Архитектура | `gui_server.py` переведён на thin-wrapper store/routing handlers поверх service-layer |
| Интерфейсы / формы / страницы | `Subscriptions` перестал быть placeholder и стал рабочим экраном с подписками, узлами и routing |
| UX / runtime-flow | native shell теперь показывает актуальный store snapshot, держит локальный выбор подписки и блокирует inline-actions во время фоновых операций |
| Документация | Открыт и закрыт отдельный подконтур `TASK-2026-0053.3`, синхронизированы родительские артефакты и реестр |

## Связанные материалы

- основной каталог подзадачи: `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.3-subscriptions-vertical-slice/`
- файл плана: `plan.md`
- родительская задача: `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/`
- предыдущая реализованная подзадача: `../TASK-2026-0053.2-dashboard-and-shared-service-layer/`
- дизайн-контракт: `../TASK-2026-0053.1-gtk4-shell-tray-and-settings-shell/subtasks/TASK-2026-0053.1.1-raycast-dark-ui-contract/sdd.md`
- ключевые файлы реализации: `gui/subvost_app_service.py`, `gui/gui_server.py`, `gui/native_shell_app.py`, `gui/native_shell_shared.py`
- ключевые тесты: `tests/test_subvost_app_service.py`, `tests/test_native_shell_app.py`, `tests/test_native_shell_shared.py`, `tests/test_gui_server.py`

## Текущий этап

Подзадача завершена. Store и routing операции подняты в общий `SubvostAppService`, web GUI сохранил совместимый `/api/store` и action-response shape через thin-wrapper handlers, а native `Subscriptions` теперь получает combined snapshot `store + status`, удерживает локально выбранную подписку, обновляет список узлов и routing-профили из того же источника истины и выполняет все действия без внутренних `HTTP` вызовов.

## Стратегия проверки

### Покрывается кодом или тестами

- `python3 -m unittest tests.test_subvost_app_service tests.test_native_shell_app tests.test_gui_server tests.test_native_shell_shared`
- `python3 -m py_compile gui/subvost_app_service.py gui/gui_server.py gui/native_shell_app.py gui/native_shell_shared.py`
- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`

### Остаётся на ручную проверку

- отдельного ручного хвоста у `TASK-2026-0053.3` не остаётся;
- живые сценарии `pkexec`, `tun0`, tray, launcher и end-to-end UI-smoke сознательно остаются в едином финальном manual smoke родительской `TASK-2026-0053`.

## Критерии готовности

- native shell получает рабочий экран `Subscriptions` без внутренних `HTTP` вызовов;
- web GUI сохраняет прежний shape `/api/store` и store/routing action-ответов;
- выбор подписки, активация узла, `ping` и routing-действия сходятся на одном service-layer;
- task-артефакты и реестр синхронизированы;
- ручной интеграционный хвост не дублируется внутри подзадачи, а остаётся только на уровне родителя.

## Итог

Закрыт третий рабочий этап `TASK-2026-0053`:

- `gui/subvost_app_service.py` расширен общим контрактом `collect_store_snapshot()` и store/routing mutation-методами для подписок, узлов и routing-профилей;
- `gui/gui_server.py` переведён на thin-wrapper вызовы service-layer для store/routing handlers и сохранил прежний `HTTP` payload shape;
- `gui/native_shell_app.py` получил реальный экран `Subscriptions` с URL-import, refresh, enable/disable, delete, активацией узла по клику строки, отдельным `Ping`, routing import и статусом `GeoIP/Geosite`;
- `gui/native_shell_shared.py` дополнен helper-слоем для выбора текущей подписки, чтения routing/store snapshot и человекочитаемых action labels;
- unit-покрытие расширено в `tests/test_subvost_app_service.py`, `tests/test_native_shell_app.py`, `tests/test_native_shell_shared.py`, а `tests/test_gui_server.py` синхронизирован с новым patch-point service-layer.

Проверки, выполненные по факту:

- `python3 -m unittest tests.test_subvost_app_service tests.test_native_shell_app tests.test_gui_server tests.test_native_shell_shared`
- `python3 -m py_compile gui/subvost_app_service.py gui/gui_server.py gui/native_shell_app.py gui/native_shell_shared.py`

Остаточный риск один: нужен общий живой smoke на машине пользователя для финального подтверждения native launcher, `pkexec`, tray и реального runtime `xray + tun0`, но этот риск уже целиком лежит в оставшемся manual smoke родительской `TASK-2026-0053`.
