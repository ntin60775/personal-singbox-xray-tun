# План задачи TASK-2026-0058.3

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0058.3` |
| Parent ID | `TASK-2026-0058` |
| Версия плана | `1` |
| Дата обновления | `2026-04-27` |

## Цель

Стабилизировать Windows runtime перед тем, как считать порт пригодным для пользователя.

## Планируемые изменения

### Код

- расширить Windows controller:
  - определить исходный default gateway;
  - добавить host route для proxy endpoint;
  - добавить route rollback;
  - добавить post-start health check;
  - читать command output с безопасной кодировочной стратегией;
- перенести mutable data в user-local paths;
- добавить tests с mock-командами.

### Документация

- описать, какие сетевые изменения выполняются;
- добавить recovery-команды;
- добавить формат диагностического отчёта.

## Проверки

- unit-тесты command runner и route planning;
- `xray.exe run -test` на Windows;
- ручной `route print` до старта, после старта и после остановки;
- ручная проверка аварийного восстановления.

## Шаги

- [x] Спроектировать route plan.
- [x] Реализовать route add/delete с rollback.
- [x] Добавить post-start checks.
- [x] Перенести mutable paths.
- [x] Добавить diagnostics/recovery.
- [x] Зафиксировать Windows smoke gate для `TASK-2026-0058.4`.

## Фактический результат

- добавлен `gui/windows_runtime_adapter.py`;
- `gui/windows_core_cli.py` теперь вызывает runtime controller для start/stop/diagnostics;
- Windows Xray config получает adapter name `SubvostTun` и очищается от Linux-only `sockopt.mark`/`sockopt.interface`;
- host route к proxy endpoint добавляется через исходный default gateway;
- при ошибке старта выполняется rollback добавленных route;
- diagnostics содержит `route print`, `netsh`, `ipconfig`, `tasklist` и recovery-команды;
- добавлен `docs/windows/README-win81-runtime.md`.
