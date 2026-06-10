# Заметка миграции task-centric-knowledge

## Паспорт

| Поле | Значение |
|------|----------|
| Эпоха до | `legacy-v1` |
| Эпоха после | `module-core-v1` |
| Класс legacy-задачи | `active` |
| Основание/задача | `TASK-2026-0044` |
| Дата обновления | `2026-04-28` |

## Что обновлено

- Создан task-local migration note.
- Repo upgrade-state синхронизирован с controlled backfill.
- Task sync обновил allowlisted summary/branch metadata для active-задачи.

## Что не трогалось

- Narrative-секции задачи не переписывались автоматически.
