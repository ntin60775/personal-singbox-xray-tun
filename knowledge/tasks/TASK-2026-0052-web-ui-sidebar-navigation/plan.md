# План задачи TASK-2026-0052

## Правило

Для задачи существует только один файл плана: `plan.md`.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0052` |
| Parent ID | `—` |
| Версия плана | `1` |
| Дата обновления | `2026-04-08` |

## Цель

Собрать более управляемый и удобный operational UI: главное окно для подключения и узлов, служебные панели в отдельных view через sidebar.

## Границы

### Входит

- sidebar-navigation и новые view внутри `main_gui.html`;
- переработка header/action hierarchy;
- вынос routing и log в служебные разделы;
- обновление JS-логики переключения и тестов.

### Не входит

- native GTK4 UI;
- смена REST endpoints;
- переработка runtime или подписок на уровне backend.

## Планируемые изменения

### Код

- перестроить shell `main_gui.html` на схему `sidebar + content`;
- добавить переключение служебных view в client-side JS;
- сфокусировать главный view на статусе подключения, подписках и узлах;
- вынести routing и log в отдельные панели, открываемые через sidebar;
- обновить `gui/gui_contract.py` и string-based тесты.

### Конфигурация / схема данных / именуемые сущности

- обновить `GUI_VERSION`, чтобы launcher не держал старый HTML-shell.

### Документация

- оформить task-контур и запись в реестре;
- после проверок зафиксировать итог и user-facing эффект.

## Риски и зависимости

- string-based тесты плотно завязаны на HTML и потребуют синхронного обновления;
- при слишком агрессивной переделке можно ухудшить responsive-поведение, поэтому layout нужно держать спокойным и операционным, без декоративного шума.

## Проверки

### Что можно проверить кодом или тестами

- `python3 -m unittest tests.test_gui_server`
- `python3 -m py_compile gui/gui_server.py gui/gui_contract.py`
- при необходимости headless sanity-check рендера страницы
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0052-web-ui-sidebar-navigation/task.md knowledge/tasks/TASK-2026-0052-web-ui-sidebar-navigation/plan.md`

### Что остаётся на ручную проверку

- пользовательская проверка нового shell в browser mode.

## Шаги

- [x] Открыть task-контур и добавить запись в реестр.
- [x] Перепроектировать shell `main_gui.html`.
- [x] Обновить JS и тесты под sidebar-navigation.
- [x] Прогнать проверки и зафиксировать итог.

## Критерии завершения

- sidebar и отдельные service-view работают;
- routing и log убраны из главного экрана;
- основной экран визуально чище и удобнее;
- проверки проходят.
