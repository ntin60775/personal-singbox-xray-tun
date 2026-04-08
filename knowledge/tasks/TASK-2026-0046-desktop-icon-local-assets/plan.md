# План TASK-2026-0046

## Кратко

Убрать абсолютный путь из `Icon=` в desktop launcher, но сохранить фактическое использование локального `assets/subvost-xray-tun-icon.svg` текущего bundle через user-local icon theme lookup и синхронизацию shell helper-ом.

## Изменения

- Launcher и installer:
  - перевести `subvost-xray-tun.desktop` на `Icon=subvost-xray-tun-icon`;
  - изменить `libexec/install-subvost-gui-menu-entry.sh`, чтобы installer писал именованную иконку вместо absolute path;
  - после генерации ярлыка запускать синхронизацию user-local icon lookup.

- Shell helper:
  - расширить `lib/subvost-common.sh` функциями определения real user home и XDG data home;
  - обновить `subvost_sync_desktop_launcher_icon`, чтобы он создавал или обновлял user-local ссылку на текущий `assets/subvost-xray-tun-icon.svg`;
  - нормализовать `Icon=` в tracked launcher и в установленной пользовательской копии, если файл существует и доступен на запись.

- Тесты и документация:
  - обновить `tests/test_gui_server.py` под именованную иконку и новую shell-логику;
  - скорректировать README под контракт без absolute path в `Icon=`;
  - открыть task-контур и синхронизировать `knowledge/tasks/registry.md`.

## Проверки

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py`
- `python3 -m unittest tests.test_gui_server.GuiServerRuntimeSelectionTests.test_desktop_launcher_does_not_force_backend_restart`
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py README.md knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0046-desktop-icon-local-assets/task.md knowledge/tasks/TASK-2026-0046-desktop-icon-local-assets/plan.md`

## Остаточный риск

Статические и строковые проверки не гарантируют поведение конкретной desktop-среды по скорости подхвата обновлённой user-local иконки; после репозиторных правок нужна обычная ручная проверка launcher-иконки в реальном сеансе пользователя.

## Шаги

- [x] Открыть task-контур и добавить запись в реестр.
- [x] Перевести launcher и installer на именованную иконку без absolute path в `Icon=`.
- [x] Обновить shell helper для синхронизации user-local icon lookup на текущий bundle asset.
- [x] Синхронизировать тесты и README под новый контракт.
- [x] Прогнать проверки и зафиксировать итоговый статус.
