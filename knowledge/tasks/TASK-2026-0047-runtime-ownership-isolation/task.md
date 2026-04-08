# Карточка задачи TASK-2026-0047

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0047` |
| Parent ID | `—` |
| Уровень вложенности | `0` |
| Ключ в путях | `TASK-2026-0047` |
| Технический ключ для новых именуемых сущностей | `runtime-ownership-isolation` |
| Краткое имя | `runtime-ownership-isolation` |
| Статус | `завершена` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `main` |
| Дата создания | `2026-04-08` |
| Дата обновления | `2026-04-08` |

## Цель

Сделать ownership VPN runtime привязанным к текущему bundle, чтобы GUI и shell-сценарии из одной копии проекта не могли остановить runtime, запущенный другой копией bundle под тем же пользователем.

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

- запись identity текущего bundle в runtime state;
- проверки ownership в GUI backend и `stop`/`run` shell-сценариях;
- защита сценариев `Стоп`, `закрытие окна` и `Старт` от влияния на foreign runtime;
- обновление тестов и task-документации под новый ownership-контракт.

### Не входит

- изменение production-копии bundle или запуск installer-ов вне репозитория;
- переработка сетевой модели runtime и route table;
- автоматическое удаление или переписывание foreign state-файлов.

## Контекст

- источник постановки: пользователь подтвердил необходимость жёсткой изоляции после выявления риска, что UI из repo может гасить уже работающий прод-runtime;
- связанная бизнес-область: lifecycle portable bundle и безопасность параллельных копий проекта;
- ограничения и зависимости: работаем только с tracked-файлами репозитория; безопасное поведение важнее обратной совместимости со старым state без identity;
- основной контекст сессии: `новая задача`

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | `gui/gui_server.py`, `gui/main_gui.html`, `libexec/run-xray-tun-subvost.sh`, `libexec/stop-xray-tun-subvost.sh` |
| Конфигурация / схема данных / именуемые сущности | Формат `STATE_FILE` дополняется bundle identity |
| Интерфейсы / формы / страницы | GUI должен различать свой runtime и foreign runtime, не предлагать опасные действия |
| Интеграции / обмены | Root-действия через `pkexec` и shell wrappers |
| Документация | Новый task-контур и запись в `knowledge/tasks/registry.md` |

## Связанные материалы

- основной каталог задачи: `knowledge/tasks/TASK-2026-0047-runtime-ownership-isolation/`
- файл плана: `plan.md`
- проблемные точки: `gui/gui_server.py`, `libexec/run-xray-tun-subvost.sh`, `libexec/stop-xray-tun-subvost.sh`
- связанные коммиты / PR / ветки: `—`
- связанные операции в `knowledge/operations/`, если есть: `—`

## Текущий этап

Реализация ownership-isolation завершена. Локальные проверки пройдены, а ручной desktop-smoke по сценарию foreign runtime подтверждён пользователем, поэтому задача переведена в `завершена`.

## Стратегия проверки

### Покрывается кодом или тестами

- unit-тесты GUI backend на ownership-классификацию и shutdown/stop/start guard;
- строковые проверки shell-контракта записи/чтения bundle identity;
- `bash -n`, `python3 -m py_compile` и `markdown-localization-guard`.

### Ручная проверка

- пользователь подтвердил desktop-smoke: при уже работающем foreign runtime repo-GUI корректно показывает ownership-guard и не требует опасного вмешательства в чужой runtime;
- пользователь подтвердил сценарий проверки в репозитории без вмешательства в production bundle.

## Критерии готовности

- runtime state фиксирует identity текущего bundle;
- GUI backend различает current и foreign runtime;
- `Старт`, `Стоп` и `закрытие окна` не останавливают foreign runtime;
- shell `stop` не трогает state и runtime другой копии bundle;
- тесты и task-контур синхронизированы.

## Итог

В `libexec/run-xray-tun-subvost.sh` runtime state теперь сохраняет `BUNDLE_PROJECT_ROOT`, а `libexec/stop-xray-tun-subvost.sh` и preflight `run`-сценария отказываются управлять state другой копии bundle или legacy-state без ownership-маркера. За счёт этого shell-контур больше не пытается остановить неподтверждённый или foreign runtime только потому, что найден общий `~/.xray-tun-subvost.state`.

В `gui/gui_server.py` добавлены helpers ownership-классификации runtime и safe-guards для `Старт`, `Стоп` и `закрытия окна`: current bundle управляет только своим runtime, foreign runtime не останавливается, а закрытие embedded-окна в таком случае завершает только UI/backend. В `gui/main_gui.html` кнопки `Старт` и `Стоп` теперь получают отдельные ownership-сигналы и не выглядят безопасно доступными при foreign/unknown runtime.

Локально подтверждены `bash -n *.sh`, `bash -n libexec/*.sh`, `bash -n lib/*.sh`, `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py`, `python3 -m unittest tests.test_gui_server` и `markdown-localization-guard` для task-контуров. Дополнительно пользователь подтвердил ручной desktop-smoke в репозитории. Остаточный риск обычный для desktop-среды: системно-зависимые различия `pkexec` и оконного менеджера вне проверенного сценария могут потребовать отдельного smoke на другой машине, но ownership-guards и unit-покрытие уже на месте.
