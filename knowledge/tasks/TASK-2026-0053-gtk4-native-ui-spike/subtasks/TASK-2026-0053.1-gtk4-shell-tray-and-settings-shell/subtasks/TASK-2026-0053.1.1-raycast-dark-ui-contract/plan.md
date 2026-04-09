# План задачи TASK-2026-0053.1.1

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0053.1.1` |
| Parent ID | `TASK-2026-0053.1` |
| Версия плана | `1` |
| Дата обновления | `2026-04-09` |

## Цель

Оформить `Raycast`-ориентированный dark design-contract как отдельную подзадачу и сделать его пригодным для последующих реализационных этапов `TASK-2026-0053`.

## Границы

### Входит

- открыть подзадачу третьего уровня внутри `TASK-2026-0053.1`;
- описать visual system в отдельном `sdd.md`;
- синхронизировать `task.md`, `plan.md`, `registry.md` и родительские артефакты.

### Не входит

- рефакторинг `GTK4` интерфейса;
- новый код визуальных компонентов;
- интеграционный runtime-smoke.

## Планируемые изменения

### Код

- без изменений продуктового кода.

### Конфигурация / схема данных / именуемые сущности

- без изменений.

### Документация

- создать `task.md`, `plan.md`, `sdd.md` и корневой `DESIGN.md`;
- описать тёмную палитру, typography contract, surface hierarchy и screen-specific guidance;
- обновить ссылки в родительских task-артефактах и строку в `registry.md`.

## Риски и зависимости

- без отдельного `sdd.md` визуальное направление снова размоется между `Dashboard`, `Subscriptions` и `Log`;
- если reference будет слишком буквально копировать web-продукт, нативный `GTK4` shell потеряет desktop-характер;
- если ручные smoke-проверки не останутся единым списком в общей задаче, knowledge-контур снова начнёт дублировать требования.

## Проверки

### Что можно проверить кодом или тестами

- `git diff --check`
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py DESIGN.md knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/task.md knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/plan.md knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.1-gtk4-shell-tray-and-settings-shell/task.md knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.1-gtk4-shell-tray-and-settings-shell/plan.md knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.1-gtk4-shell-tray-and-settings-shell/subtasks/TASK-2026-0053.1.1-raycast-dark-ui-contract/task.md knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.1-gtk4-shell-tray-and-settings-shell/subtasks/TASK-2026-0053.1.1-raycast-dark-ui-contract/plan.md knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.1-gtk4-shell-tray-and-settings-shell/subtasks/TASK-2026-0053.1.1-raycast-dark-ui-contract/sdd.md knowledge/tasks/registry.md`

### Что остаётся на ручную проверку

- визуально убедиться, что формулировки в `sdd.md` действительно описывают desktop-shell, а не generic SaaS UI;
- убедиться, что единый финальный manual smoke остался только на уровне `TASK-2026-0053`.

## Шаги

- [x] Открыть подзадачу и синхронизировать реестр.
- [x] Зафиксировать `Raycast` как основной dark reference.
- [x] Описать visual contract в `sdd.md`.
- [x] Вынести корневую входную точку в `DESIGN.md`.
- [x] Синхронизировать родительские task-артефакты.
- [x] Прогнать проверки и зафиксировать результат.

## Критерии завершения

- подзадача создана и зарегистрирована;
- `sdd.md` содержит достаточно конкретный visual contract для следующих UI-этапов;
- в корне проекта рядом с `AGENTS.md` существует актуальный `DESIGN.md`;
- родительские задачи знают о новом подконтуре;
- Markdown проходит локализационную проверку.
