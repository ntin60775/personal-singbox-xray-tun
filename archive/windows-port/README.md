# Архив: Windows 8.1 порт

Заморожено 2026-06-09. Причина: отсутствие живого smoke на реальной Windows 8.1, фокус проекта сместился на Linux TUI.

## Состав архива

| Компонент | Исходный путь | Описание |
|---|---|---|
| WinForms UI | `windows/SubvostXrayTun.WinForms/` | Нативное приложение на .NET Framework 4.8 + Windows Forms |
| Core CLI | `gui/windows_core_cli.py` | Python CLI helper, собирался через PyInstaller в `subvost-core.exe` |
| Runtime adapter | `gui/windows_runtime_adapter.py` | Управление xray.exe, wintun.dll, таблицей маршрутов Windows |
| Build scripts | `build/windows/` | PowerShell-скрипты установки зависимостей и сборки |
| PyInstaller spec | `SubvostCore.win81.spec` | Спецификация для сборки subvost-core.exe |
| Документация | `docs/windows/` | Пользовательские инструкции, build/run/smoke |
| Тесты | `tests/test_windows_*.py` | Unit-тесты Windows-цепи |

## Статус задачи

`TASK-2026-0058` — «заморожена». Три из четырёх подзадач завершены, четвёртая (живой smoke) не выполнена.

## Возврат в разработку

Для возврата Windows-порта в активную разработку:
1. Переместить файлы обратно из `archive/windows-port/` в соответствующие каталоги проекта.
2. Обновить статус `TASK-2026-0058` в `knowledge/tasks/registry.md`.
3. Актуализировать пути и зависимости (за время заморозки могли измениться).
