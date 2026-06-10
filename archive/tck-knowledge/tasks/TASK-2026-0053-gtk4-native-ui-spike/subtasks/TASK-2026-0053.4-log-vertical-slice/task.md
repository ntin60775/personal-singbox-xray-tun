# Карточка задачи TASK-2026-0053.4

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0053.4` |
| Parent ID | `TASK-2026-0053` |
| Уровень вложенности | `1` |
| Ключ в путях | `TASK-2026-0053.4` |
| Технический ключ для новых именуемых сущностей | `gtk4-log-vertical-slice` |
| Краткое имя | `log-vertical-slice` |
| Статус | `завершена` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `topic/gtk4-native-ui-spike` |
| Дата создания | `2026-04-10` |
| Дата обновления | `2026-04-10` |

## Цель

Довести экран `Log` нативного `GTK4`-клиента до рабочего vertical slice: пользователь должен видеть ошибки и события из native shell, backend action-log и runtime tail, переключать фильтр по уровню и быстро копировать или экспортировать видимый журнал.

## Границы

### Входит

- helper-логика для view-model лога без зависимости от живого `GTK`;
- рабочий экран `Log` в `gui/native_shell_app.py`:
  - сводка по последней ошибке;
  - явное разделение `native shell` и `bundle/runtime` источников;
  - фильтр по уровню;
  - copy/export видимого содержимого;
- unit-покрытие helper-слоя и native-shell логики;
- синхронизация task-артефактов и реестра.

### Не входит

- финальный ручной smoke всей `TASK-2026-0053`;
- перевод launcher-а проекта на native GUI по умолчанию;
- изменение retention или формата runtime-файлового лога bundle за пределами текущего snapshot/tail-контракта.

## Контекст

- `TASK-2026-0053.3` уже перевела `Subscriptions` на общий `service-layer`;
- в native shell экран `Log` пока остаётся минимальным `TextView` c локальными строками shell и не закрывает план родительской задачи;
- родительский `plan.md` оставляет после `TASK-2026-0053.3` ровно один функциональный этап перед финальным manual smoke: полноценный `Log`.

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / native shell | `Log` перестал быть простым shell-буфером и стал рабочим экраном с фильтрацией, сводкой ошибок и copy/export |
| Helper-слой | `gui/native_shell_shared.py` получил headless helper-логику для логов, пригодную для unit-тестов |
| UX / operational flow | пользователь видит отдельно `native shell` и `bundle/runtime`, не теряя общий service-layer контракт |
| Документация | открыт и закрыт отдельный подконтур `TASK-2026-0053.4`, синхронизированы родительские артефакты и реестр |

## Связанные материалы

- основной каталог подзадачи: `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.4-log-vertical-slice/`
- файл плана: `plan.md`
- родительская задача: `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/`
- предыдущая реализованная подзадача: `../TASK-2026-0053.3-subscriptions-vertical-slice/`
- ключевые файлы реализации: `gui/native_shell_app.py`, `gui/native_shell_shared.py`
- ключевые тесты: `tests/test_native_shell_app.py`, `tests/test_native_shell_shared.py`

## Текущий этап

Подзадача завершена. Экран `Log` закрыт как рабочий vertical slice: native shell хранит структурированные shell-события, подтягивает backend/runtime entries из текущего snapshot, показывает последнюю ошибку, умеет фильтровать видимый журнал и экспортировать или копировать его без нового `HTTP`-контракта. У родительской `TASK-2026-0053` после этого функциональных этапов больше не осталось, только единый manual smoke и решение по launcher-роллауту.

## Стратегия проверки

### Покрывается кодом или тестами

- `python3 -m unittest tests.test_native_shell_shared tests.test_native_shell_app tests.test_subvost_app_service tests.test_gui_server`
- `python3 -m py_compile gui/native_shell_shared.py gui/native_shell_app.py gui/subvost_app_service.py gui/gui_server.py`

### Остаётся на ручную проверку

- живой clipboard-flow в реальной `GTK` сессии;
- общий финальный smoke родительской `TASK-2026-0053` с tray, launcher, `pkexec` и runtime.

## Критерии готовности

- native shell показывает два источника журнала: `native shell` и `bundle/runtime`;
- фильтр по уровню работает без живого `GTK` и покрыт unit-тестами;
- copy/export используют видимый фильтрованный контент и не требуют `pkexec`;
- task-артефакты и реестр синхронизированы;
- ручной интеграционный хвост остаётся только на родительской задаче.

## Итог

Закрыт четвёртый рабочий этап `TASK-2026-0053`:

- `gui/native_shell_shared.py` получил helper-слой для фильтра лога, выбора последней ошибки и сборки экспортного текста;
- `gui/native_shell_app.py` переведён на структурированные shell log entries и рабочий экран `Log` со сводкой ошибок, кнопками `Скопировать`/`Экспорт` и фильтром `Все / Ошибки / Предупреждения / Инфо`;
- unit-покрытие расширено в `tests/test_native_shell_shared.py` и `tests/test_native_shell_app.py`, а регрессионный набор `tests.test_subvost_app_service` и `tests.test_gui_server` подтверждён повторно.

Проверки, выполненные по факту:

- `python3 -m unittest tests.test_native_shell_shared tests.test_native_shell_app tests.test_subvost_app_service tests.test_gui_server`
- `python3 -m py_compile gui/native_shell_shared.py gui/native_shell_app.py gui/subvost_app_service.py gui/gui_server.py`

Остаточный риск один: нужен живой desktop-smoke для подтверждения clipboard/tray/launcher/runtime в реальной графической сессии, но этот риск уже целиком лежит в финальном manual smoke родительской `TASK-2026-0053`.
