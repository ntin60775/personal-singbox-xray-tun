# Модульный паспорт `M-XXX`

## Паспорт

| Поле | Значение |
|------|----------|
| Модуль | `M-XXX` |
| Слаг | `example` |
| Название | `Example Module` |
| Краткое назначение | `Краткая сводка shared/public truth governed module.` |
| Ссылка верификации | `knowledge/modules/M-XXX-example/verification.md` |
| Ссылка file-local policy | `knowledge/modules/M-XXX-example/file-local-policy.md` |
| Статус готовности исполнения | `partial` |
| Краткая сводка готовности | `Writer-level readiness определяется через verification.md; file-local policy уточняет только governed hot spots.` |
| Задача происхождения | `TASK-2026-XXXX` |
| Последняя задача обновления | `TASK-2026-XXXX` |
| Дата обновления | `YYYY-MM-DD` |

## Назначение и границы

Кратко опиши:

- зачем существует governed module;
- какая управляемая поверхность считается его ответственностью;
- что сознательно не входит в scope shared/public truth.

## Управляемая поверхность

| Тип | Путь | Роль | Причина владения |
|-----|------|------|------------------|
| `runtime` | `scripts/example.py` | `primary-entry` | Основной runtime surface governed module. |
| `test` | `tests/test_example.py` | `verification` | Канонический smoke/test surface для readiness и handoff. |

`Ссылка file-local policy` всегда хранит project-relative ссылку
на канонический путь `knowledge/modules/<MODULE-ID>-<slug>/file-local-policy.md`.
Сам policy-файл управляет только governed hot spots и локальными anchors,
а не статусом задачи и не readiness truth.

## Публичные контракты

| Контракт | Форма | Ссылка/маркер | Для кого |
|----------|-------|---------------|----------|
| `CLI example` | `command-surface` | `task-knowledge example run` | `operator` |
| `Failure marker` | `log-marker` | `[ExampleDomain][FAIL]` | `controller/verifier` |

## Связи

| Тип связи | Цель | Статус | Заметка |
|-----------|------|--------|---------|

`depends_on` в v1 указывает только на exact `MODULE-ID` другого governed module.
Обратные связи `used_by` вычисляются read-model автоматически и руками в паспорт не записываются.
Допустимые значения `Статус`: `required`, `informational`, `planned`.
