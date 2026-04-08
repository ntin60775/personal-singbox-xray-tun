# План TASK-2026-0045

## Кратко

Сделать закрытие embedded GUI-окна единым сценарием полного завершения приложения: окно, GUI-backend и VPN runtime должны останавливаться согласованно.

## Изменения

- Backend:
  - добавить отдельный endpoint штатного завершения приложения;
  - при активном runtime останавливать VPN через существующий stop-контур;
  - при неактивном runtime завершать только GUI-backend без лишнего root-stop;
  - чистить PID-файл GUI-backend при штатном завершении процесса.

- Embedded окно:
  - перехватить close-событие и перед закрытием окна отправлять shutdown-запрос backend-у;
  - не закрывать окно молча, если полный shutdown не удался;
  - оставить текущее поведение простого `app.quit()` только как внутреннюю финальную стадию после успешного shutdown.

- Тесты и документация:
  - добавить unit-тесты на новый endpoint и cleanup PID-файла;
  - добавить unit-тесты на close handler embedded окна;
  - синхронизировать новую задачу в `knowledge/tasks/registry.md`.

## Проверки

- `python3 -m unittest tests.test_gui_server tests.test_embedded_webview`
- `python3 -m py_compile gui/gui_server.py gui/embedded_webview.py gui/gui_contract.py`
- `git diff --check`
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0045-ui-window-close-full-shutdown/task.md knowledge/tasks/TASK-2026-0045-ui-window-close-full-shutdown/plan.md`

## Остаточный риск

В автоматизированной сессии нельзя полноценно проиграть живой `pkexec`-диалог и реальный stop VPN runtime через закрытие окна, поэтому итоговый smoke всё равно остаётся на ручную desktop-проверку.

## Шаги

- [x] Открыть новый task-контур и добавить запись в реестр.
- [x] Реализовать полный shutdown окна, GUI-backend и VPN runtime.
- [x] Добавить и обновить unit-тесты.
- [x] Прогнать проверки и синхронизировать итог в task-артефактах.
