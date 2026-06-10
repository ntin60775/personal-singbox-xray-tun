# План задачи TASK-2026-0051

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0051` |
| Parent ID | `—` |
| Версия плана | `1` |
| Дата обновления | `2026-04-08` |

## Цель

Вернуть рабочий recovery-path для устаревшего state-файла без bundle identity, не ломая защиту от чужого или неподтверждённого живого runtime.

## Границы

### Входит

- классификация stale legacy state в `run` и `stop`;
- точечные shell-правки без смены основного ownership-контракта;
- регрессионные тесты и task-документация.

### Не входит

- принудительное управление active unknown runtime;
- новые CLI-флаги force-stop;
- изменение GUI API.

## Планируемые изменения

### Код

- добавить в shell-сценарии helper-логику для определения, жив ли legacy runtime по PID и TUN;
- в `run` пропускать stale legacy state с явным сообщением и перезаписью state на новом старте;
- в `stop` разрешать cleanup stale legacy state и отказывать только для live unknown runtime;
- в `gui/gui_server.py` не блокировать старт и stop-only recovery для stale unknown state без живого runtime.

### Конфигурация / схема данных / именуемые сущности

- без новых форматов; уточняется semantics legacy state без `BUNDLE_PROJECT_ROOT`.

### Документация

- оформить task-контур и запись в реестре;
- после проверок зафиксировать итог, локальные проверки и остаточные риски.

## Риски и зависимости

- слишком мягкая эвристика stale/live может снова открыть путь к управлению чужим runtime;
- сценарий нужно держать консервативным: recovery только если PID не жив и TUN отсутствует.

## Проверки

### Что можно проверить кодом или тестами

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m unittest tests.test_gui_server`
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0051-legacy-state-recovery/task.md knowledge/tasks/TASK-2026-0051-legacy-state-recovery/plan.md`

### Что остаётся на ручную проверку

- ручной smoke подтверждён пользователем: GUI в браузере запускается, VPN работает, консольный запуск снова рабочий.

## Шаги

- [x] Открыть task-контур и добавить запись в реестр.
- [x] Исправить shell-обработку stale legacy state.
- [x] Обновить тесты под recovery-path.
- [x] Прогнать проверки и зафиксировать итог.
- [x] Получить подтверждение ручного smoke от пользователя.

## Критерии завершения

- `run` не зацикливается на stale legacy state;
- `stop` может очистить stale legacy state;
- live unknown runtime по-прежнему не управляется автоматически;
- task-артефакты синхронизированы.
