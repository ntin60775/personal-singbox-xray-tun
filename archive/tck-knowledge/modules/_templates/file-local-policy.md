# Политика file-local contracts для `M-XXX`

Этот файл хранит только module-local contract для governed hot spots.
Он не заменяет `module.md`, не хранит task-truth и не подменяет `verification.md`.

Канонический путь:

`knowledge/modules/M-XXX-example/file-local-policy.md`

## Локальные hot spots

| Путь | Режим | Разрешённые markers | Обязательные blocks | Назначение |
|------|-------|---------------------|---------------------|------------|
| `scripts/example.py` | `required` | `MODULE_CONTRACT, MODULE_MAP` | `BLOCK_VALIDATE_INPUT, BLOCK_RENDER_OUTPUT` | Основной runtime hot spot с обязательной локальной навигацией. |
| `tests/test_example.py` | `advisory` | `CHANGE_SUMMARY` | `—` | Тестовый hot spot, где summary допустим, но не обязателен. |

## Синтаксис inline-маркеров

Используй только отдельные comment lines с одним из поддержанных prefix-наборов:

- `//`
- `#`
- `--`
- `;`
- `*`

Поддерживаемые парные markers:

- `MODULE_CONTRACT:BEGIN` / `MODULE_CONTRACT:END`
- `MODULE_MAP:BEGIN` / `MODULE_MAP:END`
- `CHANGE_SUMMARY:BEGIN` / `CHANGE_SUMMARY:END`
- `BLOCK_<NAME>:BEGIN` / `BLOCK_<NAME>:END`

Допустима и обратная форма `BEGIN MODULE_CONTRACT`.

`Режим = required` означает, что все markers из колонки `Разрешённые markers`
обязаны присутствовать полной парой.
`Режим = advisory` разрешает markers без hard-gate.
Колонка `Обязательные blocks` перечисляет именованные semantic blocks,
которые должны присутствовать полной парой для этого hot spot.
