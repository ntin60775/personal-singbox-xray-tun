# Карточка задачи TASK-2026-0058.1

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0058.1` |
| Parent ID | `TASK-2026-0058` |
| Уровень вложенности | `1` |
| Ключ в путях | `TASK-2026-0058.1` |
| Технический ключ для новых именуемых сущностей | `win81-release-package-build-chain` |
| Краткое имя | `win81-release-package-and-build-chain` |
| Статус | `завершена` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `task/task-2026-0058-win81-native-windows-port` |
| Дата создания | `2026-04-27` |
| Дата обновления | `2026-04-27` |

## Цель

Сделать Windows build/release chain воспроизводимой и понятной: зависимости, runtime assets, pin/checksum, build manifest и ожидаемый layout должны быть очевидны до запуска сборки.

## Границы

### Входит

- preflight для Windows 8.1 x64 build host;
- отдельный скрипт установки или проверки build-зависимостей;
- pin версии Xray/Wintun и SHA256;
- offline режим с локальными архивами;
- fail-fast вместо silent fallback на неподтверждённый asset;
- package manifest с версиями и источниками;
- обновление `.gitignore` для build-output без скрытия важных source-файлов.

### Не входит

- реализация нативного UI;
- укрепление Windows runtime и маршрутизации;
- публикация внешнего release artifact.

## Текущий этап

Реализована локально. Добавлены Windows build/preflight scripts, manifest runtime-ресурсов с pin/checksum, режим без сети, staging runtime-файлов и build README.

Пройден review/fix-loop без открытых замечаний по срезу `TASK-2026-0058.1`.

## Критерии готовности

- пользователь может запустить preflight и понять, каких зависимостей не хватает;
- build не скачивает неподтверждённый `latest` без проверки;
- checksum mismatch останавливает сборку;
- результат сборки имеет manifest;
- README для build-команд обновлён и проходит localization guard.

## Проверки

- `python3 -m json.tool build/windows/runtime-assets.win81.json`
- `python3 -m unittest tests.test_windows_build_chain`
- `env PYTHONPATH=gui python3 -B -m unittest discover -s tests`
- `git diff --check`
- `python3 ~/.agents/skills/owned-text-localization-guard/scripts/markdown_localization_guard.py docs/windows/README-win81-build.md knowledge/tasks/TASK-2026-0058-win81-native-windows-port/task.md knowledge/tasks/TASK-2026-0058-win81-native-windows-port/plan.md knowledge/tasks/TASK-2026-0058-win81-native-windows-port/sdd.md knowledge/tasks/TASK-2026-0058-win81-native-windows-port/subtasks/TASK-2026-0058.1-win81-release-package-and-build-chain/task.md knowledge/tasks/TASK-2026-0058-win81-native-windows-port/subtasks/TASK-2026-0058.1-win81-release-package-and-build-chain/plan.md knowledge/tasks/registry.md`
