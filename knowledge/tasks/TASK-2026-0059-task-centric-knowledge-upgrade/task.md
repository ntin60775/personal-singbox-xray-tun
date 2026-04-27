# Карточка задачи TASK-2026-0059

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0059` |
| Parent ID | `—` |
| Уровень вложенности | `0` |
| Ключ в путях | `TASK-2026-0059` |
| Технический ключ для новых именуемых сущностей | `task-centric-knowledge-upgrade` |
| Краткое имя | `task-centric-knowledge-upgrade` |
| Статус | `завершена` |
| Приоритет | `средний` |
| Ответственный | `Codex` |
| Ветка | `topic/task-centric-knowledge-upgrade` |
| Требуется SDD | `нет` |
| Статус SDD | `не требуется` |
| Ссылка на SDD | `—` |
| Дата создания | `2026-04-09` |
| Дата обновления | `2026-04-27` |

## Цель

Безопасно обновить развёрнутую в репозитории knowledge-систему до текущей версии skill-а `task-centric-knowledge`, не затронув project data и уже созданные task-каталоги.

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

## Git-подсказка

- Для верхнеуровневой задачи поле `Ветка` обычно имеет вид `task/<task-id-lower>-<slug>`, но в этом репозитории для upgrade-задачи зафиксирована совместимая ветка `topic/task-centric-knowledge-upgrade`.
- При каждом создании или переключении ветки нужно синхронизировать это поле и строку в `registry.md`.

## Границы

### Входит

- проверка совместимости текущей knowledge-системы штатным `check`;
- additive-upgrade managed-ресурсов через installer skill-а;
- сохранность `knowledge/tasks/registry.md`, существующих task-каталогов и managed-блока в `AGENTS.md`;
- фиксация upgrade-перехода в новом task-контуре.

### Не входит

- изменение содержимого существующих продуктовых задач;
- переработка пользовательских разделов `AGENTS.md` вне managed-блока;
- любые изменения runtime, GUI, сетевой логики или bundle-конфигов.

## Контекст

- источник постановки: пользователь активировал skill `task-centric-knowledge` в репозитории с уже развёрнутой knowledge-системой
- связанная бизнес-область: инженерный workflow, task-контур и сопровождение project memory
- ограничения и зависимости: upgrade должен быть идемпотентным, не должен дублировать managed-блоки и не должен переписывать `registry.md` как project data
- основной контекст сессии: `новая задача`

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | Без изменений в продуктовых модулях; используется внешний installer skill-а |
| Конфигурация / схема данных / именуемые сущности | Может быть докопирован отсутствующий managed-шаблон `knowledge/tasks/_templates/sdd.md` |
| Интерфейсы / формы / страницы | Без изменений |
| Интеграции / обмены | Без изменений |
| Документация | Task-контур upgrade, managed-шаблоны knowledge-системы и при необходимости managed-блок в `AGENTS.md` |

## Связанные материалы

- основной каталог задачи: `knowledge/tasks/TASK-2026-0059-task-centric-knowledge-upgrade/`
- файл плана: `plan.md`
- файл SDD: `не требуется для этой задачи`
- связанная предыдущая задача: `knowledge/tasks/TASK-2026-0001-task-centric-knowledge-rollout/`
- пользовательские материалы: активация skill `task-centric-knowledge` от `2026-04-09`
- связанные коммиты / PR / ветки: основная рабочая ветка задачи `topic/task-centric-knowledge-upgrade`
- связанные операции в `knowledge/operations/`, если есть: `—`

## Текущий этап

Upgrade завершён: managed-ресурсы обновлены, повторный запуск installer-а не создал дубликатов, task-контур синхронизирован.

## Стратегия проверки

### Покрывается кодом или тестами

- `python3 /home/prog7/.agents/skills/task-centric-knowledge/scripts/install_skill.py --project-root /home/prog7/РабочееПространство/projects/PetProjects/personal-singbox-xray-tun --mode check`
- `python3 /home/prog7/.agents/skills/task-centric-knowledge/scripts/install_skill.py --project-root /home/prog7/РабочееПространство/projects/PetProjects/personal-singbox-xray-tun --mode install --force`
- повторный `check` после установки
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py`

### Остаётся на ручную проверку

- визуально проверить, что `registry.md` сохранил project data, а managed-блок в `AGENTS.md` не продублировался;
- проверить diff, чтобы в scope попали только upgrade knowledge-системы и task-артефакты этой задачи.

## Критерии готовности

- knowledge-система остаётся в состоянии `compatible` после upgrade;
- в проекте присутствуют все актуальные additive managed-шаблоны skill-а;
- `knowledge/tasks/registry.md` и уже существующие task-каталоги не потеряли данные;
- managed-блок в `AGENTS.md` не продублирован;
- изменённые Markdown-файлы проходят локализационную проверку.

## Итог

В репозитории выполнен безопасный upgrade knowledge-системы до текущего дистрибутива skill-а `task-centric-knowledge`. Installer докопировал новый managed-шаблон `knowledge/tasks/_templates/sdd.md`, обновил `AGENTS.md`, `knowledge/README.md` и актуальные task-шаблоны так, чтобы в системе появились явные правила для `sdd.md`, маршрутизации между текущей задачей, подзадачей и новой задачей, а также git-синхронизации task-контекста.

`knowledge/tasks/registry.md` сохранил project data и был изменён только в части новой строки task-контура. При merge в `main` задача перенумерована из `TASK-2026-0054` в `TASK-2026-0059`, потому что номер `TASK-2026-0054` уже занят задачей `full-ui-redesign`. Повторный запуск `install --force` не создал дубликатов managed-блока и остался идемпотентным по состоянию структуры. Локально подтверждены `install_skill.py --mode check`, повторный `install --force`, `git diff --check` и `markdown-localization-guard`. Остаточный риск минимальный и сводится к тому, что в этом репозитории task-ветка зафиксирована под `topic/...`, а не под дефолтным `task/...`, потому что запись в `.git` потребовала sandbox-эскалации и была согласована через совместимый branch-name.
