# Карточка задачи TASK-2026-0053.2

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0053.2` |
| Parent ID | `TASK-2026-0053` |
| Уровень вложенности | `1` |
| Ключ в путях | `TASK-2026-0053.2` |
| Технический ключ для новых именуемых сущностей | `gtk4-dashboard-service-layer` |
| Краткое имя | `dashboard-and-shared-service-layer` |
| Статус | `завершена` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `topic/gtk4-native-ui-spike` |
| Дата создания | `2026-04-09` |
| Дата обновления | `2026-04-09` |

## Цель

Подключить `Dashboard` нативного `GTK4`-клиента к общему Python `application/service-layer`, чтобы runtime-статус, проверки ownership и действия `Старт / Стоп / Диагностика` работали без `HTTP`-зависимости внутри native shell и при этом не ломали текущий web GUI контракт.

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

- новый общий модуль `gui/subvost_app_service.py` для оркестрации runtime/status части;
- перенос в общий слой:
  - сборки `collect_status`;
  - action log;
  - traffic-метрик;
  - проверок ownership и блокирующих guard-условий;
  - `pkexec`-действий `Старт / Стоп / Диагностика`;
- thin-wrapper использование этого слоя из `gui/gui_server.py` без изменения `HTTP` shape payload;
- прямое подключение `gui/native_shell_app.py` к service-layer без внутренних `HTTP` вызовов;
- рабочий `Dashboard` с runtime-state, текущим узлом, transport/security, метриками, badge-ами и реальными runtime-действиями;
- сохранение текущей `pkexec`-границы: root только на runtime-операциях.

### Не входит

- рабочее наполнение `Subscriptions` и routing editor beyond placeholder;
- фильтрация, export и полноценная диагностическая плоскость `Log`;
- переключение проектного launcher-а на native GUI по умолчанию;
- финальный live-smoke с реальным `pkexec`, `tun0` и tray-сценариями во всей задаче `TASK-2026-0053`.

## Контекст

- источник постановки: декомпозиция родительской `TASK-2026-0053` после закрытия shell/tray-этапа `TASK-2026-0053.1`;
- текущий native shell уже умел поднимать окно, системный трей и минимальные настройки, но `Dashboard` и tray actions ещё были `stub`;
- web GUI уже содержал зрелую runtime/store/routing orchestration в `gui/gui_server.py`, но этот слой был жёстко сцеплен с `HTTP` backend-модулем;
- пользовательский и архитектурный риск: не допустить появления второго неофициального backend-контракта для native UI и не размазать `pkexec` по обычному открытию окна.

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | Появился общий `subvost_app_service.py` и прямое использование его из native shell |
| Архитектура | `gui_server.py` остаётся `HTTP`-обёрткой, а runtime/status orchestration больше не живёт только внутри web backend |
| Интерфейсы / формы / страницы | `Dashboard` стал рабочим экраном с реальными действиями и статусными данными |
| UX / runtime-flow | Tray и кнопки окна больше не ведут себя как `stub`, а запускают общий runtime-service |
| Документация | Открыт и закрыт отдельный подконтур `TASK-2026-0053.2`, синхронизированы родительские артефакты и реестр |

## Связанные материалы

- основной каталог подзадачи: `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.2-dashboard-and-shared-service-layer/`
- файл плана: `plan.md`
- родительская задача: `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/`
- предыдущая реализованная подзадача: `../TASK-2026-0053.1-gtk4-shell-tray-and-settings-shell/`
- дизайн-контракт: `../TASK-2026-0053.1-gtk4-shell-tray-and-settings-shell/subtasks/TASK-2026-0053.1.1-raycast-dark-ui-contract/sdd.md`
- ключевые файлы реализации: `gui/subvost_app_service.py`, `gui/gui_server.py`, `gui/native_shell_app.py`, `gui/native_shell_shared.py`
- новые тесты: `tests/test_subvost_app_service.py`

## Текущий этап

Подзадача завершена. Общий runtime/service-layer выделен в `gui/subvost_app_service.py`, web GUI сохранил совместимый `HTTP` контракт через thin-wrapper функции в `gui/gui_server.py`, а нативный `GTK4` shell перестал быть просто оболочкой: `Dashboard` теперь показывает реальный статус bundle, текущий узел, transport/security, признак ownership, `rx/tx`, `tun`, `DNS`, последнюю диагностику и запускает `Старт / Стоп / Диагностика` через тот же Python orchestration-layer.

## Стратегия проверки

### Покрывается кодом или тестами

- `python3 -m unittest tests.test_subvost_app_service tests.test_native_shell_app tests.test_gui_server tests.test_native_shell_shared`
- `python3 -m py_compile gui/subvost_app_service.py gui/gui_server.py gui/native_shell_app.py gui/native_shell_shared.py`
- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`

### Ручная проверка

Отдельного ручного хвоста у подзадачи нет. Все живые сценарии `pkexec`, `tun0`, tray и launcher сознательно перенесены в единый финальный manual smoke родительской `TASK-2026-0053`, поэтому закрытие `TASK-2026-0053.2` не оставляет собственного незавершённого списка ручных шагов.

## Критерии готовности

- нативный `GTK4` shell получает общий runtime/service-layer без внутренних `HTTP` вызовов;
- `Dashboard` перестаёт быть placeholder и показывает реальные runtime-данные проекта;
- web GUI не теряет текущий `HTTP` shape payload и не получает breaking changes;
- root-запрос остаётся только на действиях `Старт / Стоп / Диагностика`;
- task-артефакты и реестр задач синхронизированы.

## Итог

Реализован второй рабочий этап `TASK-2026-0053`:

- добавлен новый модуль `gui/subvost_app_service.py`, который собрал общий runtime/status orchestration, action log, traffic-метрики, проверки ownership и `pkexec`-действия;
- `gui/gui_server.py` переведён на thin-wrapper использование общего слоя для status/runtime helper-логики, но сохранил прежний тестируемый `HTTP`-контракт;
- `gui/native_shell_app.py` получил прямое подключение к общему service-layer, фоновые refresh/action worker-ы и рабочий `Dashboard` вместо shell-`stub`;
- `gui/native_shell_shared.py` обновлён так, чтобы страницы и tray-actions больше не объявляли runtime-операции как временные заглушки;
- добавлены unit-тесты `tests/test_subvost_app_service.py` и расширено покрытие `tests/test_native_shell_app.py`.

Проверки, выполненные по факту:

- `python3 -m unittest tests.test_subvost_app_service tests.test_native_shell_app tests.test_gui_server tests.test_native_shell_shared`
- `python3 -m py_compile gui/subvost_app_service.py gui/gui_server.py gui/native_shell_app.py gui/native_shell_shared.py`

Остаточный риск один: live runtime-smoke с реальным `pkexec`, `tun0`, tray и launcher ещё не завершён, но он полностью вынесен в единый финальный ручной список родительской `TASK-2026-0053`, а не остаётся отдельным хвостом этой подзадачи.
