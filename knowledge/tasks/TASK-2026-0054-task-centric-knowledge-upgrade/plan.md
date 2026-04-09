# План задачи TASK-2026-0054

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0054` |
| Parent ID | `—` |
| Версия плана | `1` |
| Связь с SDD | `не требуется` |
| Дата обновления | `2026-04-09` |

## Цель

Обновить managed-часть knowledge-системы до текущего дистрибутива skill-а `task-centric-knowledge` без потери project data и без побочных изменений продуктового репозитория.

## Границы

### Входит

- открыть новый task-контур под upgrade-переход;
- синхронизировать git-контекст задачи и запись в `registry.md`;
- выполнить штатный installer skill-а в режиме upgrade;
- проверить повторным `check`, что система осталась совместимой и без дубликатов.

### Не входит

- миграция или редактирование уже завершённых задач;
- изменения продуктового кода и пользовательских фич;
- публикация изменений в remote.

## Планируемые изменения

### Код

- продуктовый код не меняется;
- допускается только использование служебных скриптов skill-а для обновления knowledge-системы.

### Конфигурация / схема данных / именуемые сущности

- докопировать отсутствующие managed-ресурсы knowledge-системы, если installer их обнаружит;
- не менять `registry.md` вне служебной синхронизации новой задачи.

### Документация

- создать `task.md` и `plan.md` для `TASK-2026-0054`;
- при необходимости обновить managed-шаблоны `knowledge/tasks/_templates/`;
- зафиксировать итог, проверки и остаточные риски.

## Связь с SDD

- отдельный `sdd.md` для этой задачи не требуется, потому что upgrade ограничен managed-ресурсами knowledge-системы и не меняет продуктовые контракты;
- задача всё равно должна проверить, что после upgrade в репозитории появился актуальный шаблон `knowledge/tasks/_templates/sdd.md`.

## Риски и зависимости

- случайная перезапись project data при неверном режиме installer-а;
- дублирование managed-блока в `AGENTS.md` или повторное создание уже существующих артефактов;
- скрытые изменения вне upgrade-scope, если не проверить итоговый diff.

## Проверки

### Что можно проверить кодом или тестами

- `python3 /home/prog7/.agents/skills/task-centric-knowledge/scripts/install_skill.py --project-root /home/prog7/РабочееПространство/projects/PetProjects/personal-singbox-xray-tun --mode check`
- `python3 /home/prog7/.agents/skills/task-centric-knowledge/scripts/install_skill.py --project-root /home/prog7/РабочееПространство/projects/PetProjects/personal-singbox-xray-tun --mode install --force`
- повторный `python3 /home/prog7/.agents/skills/task-centric-knowledge/scripts/install_skill.py --project-root /home/prog7/РабочееПространство/projects/PetProjects/personal-singbox-xray-tun --mode check`
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0054-task-centric-knowledge-upgrade/task.md knowledge/tasks/TASK-2026-0054-task-centric-knowledge-upgrade/plan.md AGENTS.md knowledge/tasks/_templates/sdd.md`

### Что остаётся на ручную проверку

- убедиться по `git diff`, что upgrade затронул только managed-ресурсы и task-артефакты этой задачи;
- визуально подтвердить отсутствие дублирования managed-блока в `AGENTS.md`.

## Шаги

- [x] Собрать локальный контекст и проверить классификацию существующей knowledge-системы.
- [x] Открыть новый task-контур `TASK-2026-0054` и синхронизировать ветку задачи.
- [x] Выполнить upgrade managed-ресурсов installer-ом.
- [x] Проверить итоговый diff, локализацию Markdown и повторный `check`.
- [x] Зафиксировать результат в task-артефактах и реестре.

## Критерии завершения

- additive-upgrade выполнен без потери project data;
- новый managed-шаблон `sdd.md` и другие актуальные ресурсы присутствуют в проекте;
- `registry.md` и `AGENTS.md` остались консистентными;
- task-артефакты синхронизированы с фактическим результатом.
