# Карточка задачи TASK-2026-0058.3

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0058.3` |
| Parent ID | `TASK-2026-0058` |
| Уровень вложенности | `1` |
| Ключ в путях | `TASK-2026-0058.3` |
| Технический ключ для новых именуемых сущностей | `windows-runtime-routing-hardening` |
| Краткое имя | `windows-runtime-routing-hardening` |
| Статус | `завершена` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `task/task-2026-0058-win81-native-windows-port` |
| Дата создания | `2026-04-27` |
| Дата обновления | `2026-04-27` |

## Цель

Убрать блокирующие runtime-риски Windows 8.1: routing loop, запись рядом с `.exe`, хрупкие кодировки команд, stale adapter и недостаточный rollback при ошибке старта.

## Границы

### Входит

- host routes к proxy endpoint через исходный gateway;
- post-start проверки Xray process, `SubvostTun`, route table;
- rollback route/process при ошибке;
- перенос state/logs в `%LOCALAPPDATA%`;
- устойчивый command runner с `errors=replace`;
- диагностика для recovery;
- тесты вокруг Windows controller.

### Не входит

- оконная оболочка интерфейса;
- установщик зависимостей сборки;
- поддержка IPv6 как полноценного отдельного режима.

## Текущий этап

Реализована локально. Добавлен Windows runtime controller с host-route к proxy endpoint, rollback маршрутов, подготовкой Windows Xray-конфига, state/log paths в `%LOCALAPPDATA%`, diagnostics JSON и тестами.

Реальный запуск `xray.exe`, проверка `SubvostTun`, `route print` и аварийное восстановление остаются live-gate в `TASK-2026-0058.4`.

## Критерии готовности

- Windows runtime не полагается только на `sockopt.interface`;
- ошибка старта не оставляет default route в сломанном состоянии;
- diagnostics содержит данные для ручного восстановления сети;
- state/logs не требуют записи в каталог установки;
- ключевые ветки покрыты unit-тестами или ручным smoke.

## Проверки

- `python3 -B -c "import ast,pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8'), filename=p) for p in ['gui/windows_core_cli.py','gui/windows_runtime_adapter.py','gui/subvost_paths.py']]; print('syntax ok')"`
- `env PYTHONPATH=gui python3 -B -m unittest tests.test_windows_runtime_adapter tests.test_windows_core_helper_contract tests.test_windows_build_chain`
- `env PYTHONPATH=gui python3 -B -m unittest discover -s tests`
- `git diff --check`
- `python3 ~/.agents/skills/owned-text-localization-guard/scripts/markdown_localization_guard.py docs/windows/README-win81-build.md docs/windows/README-win81-runtime.md gui/windows_core_cli.py gui/windows_runtime_adapter.py tests/test_windows_runtime_adapter.py`
