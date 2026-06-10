# План задачи TASK-2026-0058.2

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0058.2` |
| Parent ID | `TASK-2026-0058` |
| Версия плана | `1` |
| Дата обновления | `2026-04-27` |

## Цель

Получить первый нативный Windows UI vertical slice без браузера.

## Планируемые изменения

### Код

- добавить core/helper JSON commands поверх существующего service-layer;
- добавить Windows shell-проект выбранного стека;
- подключить status/start/stop/diagnostics;
- добавить обработку ошибок и занятых действий;
- добавить smoke-friendly logging.

### UX

- главное окно:
  - статус подключения;
  - выбранный узел;
  - кнопки `Подключиться`, `Отключиться`, `Диагностика`;
  - блок последней ошибки;
  - список узлов текущей подписки;
- дополнительные окна или вкладки можно оставить минимальными до второго slice.

## Проверки

- unit-тесты helper JSON contract;
- build выбранного UI-проекта;
- ручной запуск на Windows 8.1;
- localization guard для UI strings.

## Шаги

- [x] Подтвердить UI-стек.
- [x] Зафиксировать helper JSON schema.
- [x] Собрать UI skeleton.
- [x] Подключить status.
- [x] Подключить start/stop/diagnostics.
- [x] Зафиксировать Windows smoke gate для `TASK-2026-0058.4`.

## Фактический результат

- добавлен `gui/windows_core_cli.py` с единым JSON envelope для `status`, runtime-actions, diagnostics, subscriptions и nodes;
- добавлен `windows/SubvostXrayTun.WinForms/` с нативным Windows Forms окном;
- добавлен `SubvostCore.win81.spec` для helper-only PyInstaller сборки;
- обновлены Windows build scripts: `tools\subvost-core.exe`, `SubvostXrayTun.exe`, `runtime\`, `xray-tun-subvost.json`;
- добавлены тесты helper contract и packaging gates.
