# План TASK-2026-0044

## Кратко

Сузить стартовое embedded-окно и внутренний основной контейнер GUI, сохранив ожидаемую компоновку и зафиксировав новое поведение тестами.

## Изменения

- Встроенное окно:
  - уменьшить `DEFAULT_WIDTH` в `gui/embedded_webview.py` с `1440` до `1280`;
  - сохранить текущую логику ограничений по размеру монитора и минимальной ширине.

- Web-интерфейс:
  - уменьшить `max-width` основного контейнера `.app-shell` в `gui/main_gui.html` с `1360px` до `1200px`;
  - сохранить существующие внутренние и внешние отступы без изменения сетки.

- Тесты и документация:
  - обновить `tests/test_embedded_webview.py` под новую номинальную ширину окна по умолчанию;
  - добавить новый task-контур и строку в реестр задач.

## Проверки

- `python3 -m unittest tests.test_embedded_webview`
- `python3 -m py_compile gui/embedded_webview.py gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py`
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0044-main-window-width-reduction/task.md knowledge/tasks/TASK-2026-0044-main-window-width-reduction/plan.md`

## Остаточный риск

Автоматизированная сессия не подтверждает живую визуальную проверку на реальном сеансе рабочего стола; её нужно выполнить вручную после статических проверок.

## Шаги

- [x] Открыть task-контур и добавить запись в реестр.
- [x] Обновить ширину окна, ширину web-контейнера и релевантные тесты.
- [x] Прогнать проверки.
- [x] Синхронизировать итоговый статус и результат в task-артефактах.
