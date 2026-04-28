# План задачи TASK-2026-0060

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0060` |
| Parent ID | `—` |
| Версия плана | `1` |
| Связь с SDD | `не требуется` |
| Дата обновления | `2026-04-28` |

## Цель

Исключить project-local `.agents/` из Git и подготовить консультационный дизайн-review gate через Kimi CLI для следующей UI-задачи.

## Границы

### Входит

- `.gitignore` правило для `.agents/`;
- проверка, что локальные skills больше не видны как untracked;
- проверка доступности `kimi`;
- фиксация Kimi CLI как внешнего дизайн-ревьюера для следующего макета.

### Не входит

- изменение интерфейса приложения;
- перенос локальных skills в Git;
- установка Kimi CLI или изменение его глобальной конфигурации.

## Планируемые изменения

### Код

- `нет`

### Конфигурация / схема данных / именуемые сущности

- добавить `/.agents/` в `.gitignore`.

### Документация

- добавить task-local `task.md` и `plan.md`;
- обновить `knowledge/tasks/registry.md`.

## Зависимости и границы

### Новые runtime/package зависимости

- `нет`

### Изменения import/module-связей и зависимостей между модулями

- `нет`

### Границы, которые должны остаться изолированными

- `.agents/` остаётся локальным рабочим контуром агента и не попадает в Git;
- Kimi CLI используется как консультационный инструмент, а не как источник автоматических изменений без проверки.

### Критический функционал

- Git больше не должен показывать `.agents/` как untracked;
- локальные skills остаются доступными на диске для текущего проекта.

### Основной сценарий

- установить project-local skills локально;
- добавить `.agents/` в `.gitignore`;
- использовать `kimi` CLI для дизайн-ревью макета перед UI-реализацией.

### Исходный наблюдаемый симптом

- `git status --short --branch` показывал `?? .agents/`.

## Риски и зависимости

- если в будущем появятся файлы `.agents/`, которые нужно версионировать, потребуется отдельное явное исключение из ignore-правила;
- консультация Kimi CLI зависит от локальной auth/config этого инструмента.

## Связь с SDD

- `не требуется`

## Проверки

### Что можно проверить кодом или тестами

- `git check-ignore -v .agents/skills/playwright-interactive/SKILL.md .agents/skills/ui-ux-pro-max/SKILL.md`;
- `git status --short --branch`;
- `command -v kimi`;
- `python3 /home/prog7/.agents/skills/owned-text-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/TASK-2026-0060-project-local-skills-ignore-and-kimi-review/task.md knowledge/tasks/TASK-2026-0060-project-local-skills-ignore-and-kimi-review/plan.md knowledge/tasks/TASK-2026-0060-project-local-skills-ignore-and-kimi-review/artifacts/kimi-design-review.md`;
- `git diff --check`.

### Что остаётся на ручную проверку

- живой browser smoke после реализации вкладки маршрутов.

## Шаги

- [x] Добавить `.agents/` в `.gitignore`
- [x] Зафиксировать task-local контур
- [x] Проверить ignore-правило, доступность Kimi CLI и локализацию task-документов
- [x] Получить консультационное дизайн-ревью через Kimi CLI

## Критерии завершения

- `.agents/` не попадает в `git status`;
- Kimi CLI доступен для консультаций;
- task-документы и diff проходят проверки.
