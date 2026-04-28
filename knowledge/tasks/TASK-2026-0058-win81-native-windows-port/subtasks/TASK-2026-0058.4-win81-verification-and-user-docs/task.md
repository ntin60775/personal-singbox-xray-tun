# Карточка задачи TASK-2026-0058.4

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0058.4` |
| Parent ID | `TASK-2026-0058` |
| Уровень вложенности | `1` |
| Ключ в путях | `TASK-2026-0058.4` |
| Технический ключ для новых именуемых сущностей | `win81-verification-user-docs` |
| Краткое имя | `win81-verification-and-user-docs` |
| Человекочитаемое описание | `Живой Windows 8.1 smoke, beginner README, troubleshooting и handoff-комплект` |
| Статус | `ждёт пользователя` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `main` |
| Дата создания | `2026-04-27` |
| Дата обновления | `2026-04-28` |

## Цель

Закрыть Windows 8.1 порт пользовательской документацией, воспроизводимым smoke-протоколом и понятным handoff-комплектом.

## Границы

### Входит

- пользовательский Windows README для новичка;
- troubleshooting и recovery;
- чек-лист ручной проверки;
- шаблон сырого validation log;
- проверка localization guard;
- итоговая синхронизация task registry.

### Не входит

- реализация UI и runtime-кода;
- публикация внешнего релиза без отдельного подтверждения.

## Текущий этап

Пользовательская документация, recovery-инструкция и smoke-протокол подготовлены. Build script копирует beginner README в `dist\SubvostXrayTun\README.md`.

Live smoke на реальной Windows 8.1 в текущей Linux-среде не выполнялся, поэтому подзадача ждёт проверки на Windows 8.1 по `docs/windows/win81-smoke-protocol.md`.

## Критерии готовности

- README объясняет путь от чистой машины до запуска приложения;
- recovery-раздел позволяет вернуть сеть вручную;
- smoke log содержит фактические версии и команды;
- документация не обещает непроверенные gates;
- localization guard проходит.

## Проверки

- `env PYTHONPATH=gui python3 -B -m unittest tests.test_windows_build_chain tests.test_windows_runtime_adapter tests.test_windows_core_helper_contract`
- `env PYTHONPATH=gui python3 -B -m unittest discover -s tests`
- `git diff --check`
- `python3 ~/.agents/skills/owned-text-localization-guard/scripts/markdown_localization_guard.py docs/windows/README-win81-build.md docs/windows/README-win81-runtime.md docs/windows/README-win81-user.md docs/windows/win81-smoke-protocol.md build/windows/build-win81-release.ps1 tests/test_windows_build_chain.py`

## Артефакты

- `docs/windows/README-win81-user.md`
- `docs/windows/README-win81-runtime.md`
- `docs/windows/win81-smoke-protocol.md`
- путь копии в пакете: `dist\SubvostXrayTun\README.md`
