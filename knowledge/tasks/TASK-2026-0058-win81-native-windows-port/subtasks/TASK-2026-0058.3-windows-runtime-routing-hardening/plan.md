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

- [ ] Спроектировать route plan.
- [ ] Реализовать route add/delete с rollback.
- [ ] Добавить post-start checks.
- [ ] Перенести mutable paths.
- [ ] Добавить diagnostics/recovery.
- [ ] Пройти Windows smoke.
