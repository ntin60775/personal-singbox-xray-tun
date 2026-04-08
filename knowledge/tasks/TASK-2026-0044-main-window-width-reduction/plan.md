# План TASK-2026-0044

## Кратко

Сузить стартовое embedded-окно и внутренний основной контейнер GUI, затем снять регрессии верхней панели под новое окно `1280` px и зафиксировать новое поведение тестами.

## Изменения

- Встроенное окно:
  - уменьшить `DEFAULT_WIDTH` в `gui/embedded_webview.py` с `1440` до `1280`;
  - сохранить текущую логику ограничений по размеру монитора и минимальной ширине.

- Web-интерфейс:
  - убрать жёсткий лимит `1200px` у `.app-shell` и вернуть заполнение доступной ширины desktop-окна без лишних боковых полей;
  - сохранить существующие внутренние отступы и сетку панелей без возврата к старому oversized-окну;
  - ослабить жёсткие минимальные ширины метрик и action-row, сохранить двухколоночный баннер на окне `1280` px и собирать narrow-layout в три строки только ниже, без пустой зоны внутри баннера;
  - оставить кнопку `Старт` доступной в stopped-состоянии GUI и показывать причину неподготовленного старта через tooltip, а не через hard-disable на клиенте.

- Backend и launcher:
  - перестать держать `main_gui.html` в module-level snapshot внутри `gui/gui_server.py`;
  - обслуживать root GUI через живое чтение asset-файла на каждый GET;
  - обновить `gui/gui_contract.py`, чтобы launcher считал старый user-backend устаревшим и перезапускал его после обновления bundle.

- Embedded webview и polling:
  - выставить тёмный background на уровне `WebKit.WebView`, GTK-окна и корневого контейнера, чтобы repaint не вспыхивал белым фоном между обновлениями;
  - включить `WEBKIT_DISABLE_COMPOSITING_MODE=1` в launcher и runtime-defaults для более предсказуемого software-rendering пути;
  - убрать холостые `renderAll()` в `main_gui.html`, когда `/api/store` принёс payload без видимых изменений кроме служебного timestamp;
  - сохранить polling, но уменьшить его визуальную цену в stopped-сценарии.

- Тесты и документация:
  - обновить `tests/test_embedded_webview.py` под новую номинальную ширину окна по умолчанию;
  - добавить строковые GUI-регрессии в `tests/test_gui_server.py`, проверку live-load для root-route и guard против возврата лишних боковых полей/пустых rerender;
  - синхронизировать task-контур и строку в реестре задач.

## Проверки

- `python3 -m unittest tests.test_gui_server tests.test_embedded_webview`
- `python3 -m py_compile gui/embedded_webview.py gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py`
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0044-main-window-width-reduction/task.md knowledge/tasks/TASK-2026-0044-main-window-width-reduction/plan.md`

## Остаточный риск

Автоматизированная сессия не подтверждает живую визуальную проверку на реальном сеансе рабочего стола; после статических проверок нужно вручную проверить новую компоновку верхней панели, исчезновение боковых полей, сохранение двухколоночного режима на `1280` px, отсутствие пустой зоны внутри баннера, поведение кнопки `Старт`, факт, что launcher действительно поднял уже новый backend, и снижение white-flicker в embedded runtime.

## Шаги

- [x] Открыть task-контур и добавить запись в реестр.
- [x] Обновить ширину окна, ширину web-контейнера и релевантные тесты.
- [x] Снять follow-up регрессии верхней панели после сужения окна.
- [x] Устранить stale user-backend, который держал старый HTML и скрывал эффект UI-правок.
- [x] Прогнать проверки.
- [x] Синхронизировать итоговый статус и результат в task-артефактах.
