# План задачи TASK-2026-0050

## Правило

Для задачи существует только один файл плана: `plan.md`.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0050` |
| Parent ID | `—` |
| Версия плана | `1` |
| Дата обновления | `2026-04-08` |

## Цель

Стабилизировать текущий web/embedded GUI без перехода на native GTK4.

## Границы

### Входит

- Новый GUI-only shutdown endpoint.
- Переключение close-handler embedded webview на GUI-only shutdown.
- Переразмещение routing-панели в рабочую область вместо отдельной строки shell.
- Browser fallback для запуска из desktop launcher.
- Тесты и локальные проверки.

### Не входит

- Native GTK4 UI.
- Автоматическая смена runtime-портов.
- Store-изоляция dev/prod.

## Планируемые изменения

### Код

- Добавить `handle_gui_shutdown` в `gui_server.py`.
- Добавить route `/api/app/shutdown-gui` в `Handler.do_POST`.
- Оставить `/api/app/terminate` для полного сценария с остановкой runtime.
- Обновить `embedded_webview.py`, чтобы закрытие окна вызывало GUI-only endpoint.
- Упростить grid layout в `main_gui.html`: shell снова topbar, workspace, log; routing живёт в правой колонке workspace.
- Настроить desktop launcher и installer пользовательского ярлыка на `SUBVOST_GUI_LAUNCH_MODE=browser`, не меняя ручной запуск `open-subvost-gui.sh`.

### Конфигурация / схема данных / именуемые сущности

- Новый HTTP route `/api/app/shutdown-gui`.

### Документация

- Обновить task-контур и `knowledge/tasks/registry.md`.

## Риски и зависимости

- Если чёрный экран вызван низкоуровневым WebKit/GPU багом, layout и shutdown не устранят его полностью; fallback на browser останется рабочим обходом.
- Общий store/runtime между prod и repo остаётся отдельной проблемой.

## Проверки

### Что можно проверить кодом или тестами

- `python3 -m unittest tests.test_gui_server tests.test_embedded_webview`.
- `python3 -m py_compile gui/gui_server.py gui/embedded_webview.py gui/gui_contract.py`.
- `bash -n libexec/open-subvost-gui.sh`.
- `node --check` для встроенного JS, если скрипт будет извлечён.
- `markdown-localization-guard` для Markdown.

### Что остаётся на ручную проверку

- Повторный запуск ярлыка и визуальная проверка embedded WebKit.

## Шаги

- [x] Добавить GUI-only shutdown endpoint.
- [x] Переключить embedded webview на новый endpoint.
- [x] Исправить layout routing-блока.
- [x] Настроить browser fallback для desktop launcher.
- [x] Обновить тесты.
- [x] Прогнать проверки.

## Критерии завершения

- Window close не останавливает VPN runtime.
- Backend можно закрывать отдельно от runtime.
- Интерфейс не показывает чёрный экран из-за layout-регрессии.
- Проверки проходят.

## Итог

Добавлен GUI-only shutdown endpoint, обновлён embedded close-handler, routing-блок перенесён в трёхколоночный workspace, а запуск через desktop entry переведён на browser fallback. Старый полный endpoint закрытия приложения сохранён.
