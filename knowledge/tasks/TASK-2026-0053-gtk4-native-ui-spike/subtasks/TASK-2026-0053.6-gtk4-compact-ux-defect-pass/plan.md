# План задачи TASK-2026-0053.6

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0053.6` |
| Parent ID | `TASK-2026-0053` |
| Версия плана | `2` |
| Дата обновления | `2026-04-11` |

## Цель

Свести архивные UX-дефекты `GTK4` shell к компактному и честному desktop-контракту: окно должно нормально работать на `Full HD`, не расползаться за пределы экрана, не скрывать действия и не обещать визуальные режимы, которых сейчас нет.

## Границы

### Входит

- исправление geometry, minimum size и visual-density;
- компактный `Dashboard` без giant banner и лишних поясняющих текстов;
- выравнивание тёмного визуального контракта для `Sidebar`, `Log` и `Settings`;
- честный `dark-only` settings contract;
- повторный ручной smoke и обновление smoke-артефактов.

### Не входит

- новый runtime/routing/tray функционал;
- миграция основного launcher-а проекта на native UI;
- полноценная поддержка `system/light/dark`;
- unrelated рефакторинг service-layer и backend-контракта.

## Планируемые изменения

### Knowledge и артефакты

- восстановить подзадачу `TASK-2026-0053.6` в `knowledge/tasks/`;
- сохранить архивные `PNG` в `artifacts/manual-smoke/raw/` без переименования;
- зафиксировать в `smoke-summary.md` фактическую геометрию, поведение `resize` и состав канонических артефактов;
- синхронизировать `knowledge/tasks/registry.md` и родительские `task.md` / `plan.md`.

### Публичный UI-contract

- базовое окно shell должно открываться не больше `1280x900`;
- minimum size окна не должен превышать `1280x900`;
- shell должен целиком помещаться на `1920x1080` без ручного ресайза;
- `resize` и `maximize` должны реально применяться window manager;
- launcher и D-Bus control interface не меняются.

### Компоновка и geometry

- пересобрать главный layout так, чтобы `Dashboard`, `Subscriptions` и `Log` не диктовали giant minimum size;
- убрать жёсткие композиции, которые заставляют `GTK` поднимать `min/natural height` выше экрана;
- верхнюю часть `Dashboard` без прокрутки ограничить статусом, базовыми действиями и кратким рабочим контекстом;
- вернуть доступность header-`CTA` без ухода элементов за экран.

### Copy и баннеры

- удалить верхний banner-блок про подключение `Dashboard` к service-layer;
- сократить page-description и технические пояснения до одной короткой рабочей строки на экран;
- убрать повторяющиеся объяснения про `pkexec`, backend-contract и service-layer из hero/action-секций;
- оставить только тексты, которые помогают принять решение пользователю в моменте.

### Visual и theme contract

- привести `StackSidebar` к той же dark system, что и остальные поверхности;
- устранить белую `Log` surface и сделать лог читаемым в тёмной теме;
- сохранить `Settings` компактным утилитарным окном без лишней поясняющей прозы;
- убрать ложный selector `system/light/dark` и зафиксировать shell как `dark-only`;
- не расширять persisted поле `theme` в этой подзадаче: старые значения должны безопасно приводиться к тёмному контракту.

## Риски и зависимости

- oversized minimum size может оказаться следствием нескольких вложенных `GtkBox` и `ScrolledWindow`, а не одной локальной константы;
- удаление поясняющих текстов не должно спрятать важные рабочие состояния и ошибки;
- `dark-only` контракт нужно оформить честно, чтобы не оставить полуработающий selector в `Settings`;
- итоговый smoke зависит от живой графической сессии и window manager поведения.

## Проверки

### Что можно проверить кодом или тестами

- `python3 -m unittest tests.test_native_shell_app tests.test_native_shell_shared tests.test_subvost_app_service tests.test_gui_server`;
- `python3 -m py_compile gui/native_shell_app.py gui/native_shell_shared.py gui/subvost_app_service.py gui/gui_server.py`;
- `bash -n *.sh`, `bash -n libexec/*.sh`, `bash -n lib/*.sh`, `git diff --check`;
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py` для новых и обновлённых Markdown-файлов подзадачи, родителя и `registry.md`.

### Что остаётся на ручную проверку

- запуск через `./open-subvost-gtk-ui.sh`;
- фиксация geometry через `xwininfo`, `wmctrl` и `xprop`;
- подтверждение, что окно целиком видно на `Full HD`;
- подтверждение, что `resize/maximize` меняют geometry;
- screenshot каждого экрана и `Settings` после правок;
- проверка, что header-`CTA` доступны без обходных D-Bus-команд;
- проверка, что `Log` больше не рендерится белым полотном;
- проверка, что idle-сценарий больше не воспроизводит repeated `GtkBox ... natural size must be >= min size`.

## Шаги

- [x] Восстановить подзадачу и перенести архивные smoke-артефакты в knowledge-контур
- [x] Синхронизировать `registry.md` и родительские `task.md` / `plan.md`
- [x] Исправить geometry и minimum size окна
- [x] Перепаковать `Dashboard` в компактную верхнюю часть без прокрутки
- [x] Убрать бесполезный banner и технические поясняющие тексты
- [x] Привести `Sidebar`, `Log` и `Settings` к одному тёмному визуальному контракту
- [x] Зафиксировать честный `dark-only` theme contract
- [x] Прогнать кодовые и статические проверки
- [ ] Прогнать повторный smoke на `Dashboard / Subscriptions / Log / Settings`
- [x] Синхронизировать итоговый статус и результат в knowledge

## Фактический результат реализации

- `gui/native_shell_app.py` переведён на более компактный shell-контракт: уменьшены nominal size и отступы, верхний статусный блок больше не играет роль giant banner, страницы получили `ScrolledWindow`, а `Dashboard` перестроен в вертикальный компактный flow.
- `Subscriptions` и `Log` ужаты по плотности, sidebar стал уже и получил явный тёмный CSS-контракт; для `Log` добавлен собственный dark `TextView`/scroller стиль.
- Окно `Settings` уменьшено и упрощено: selector темы удалён, вместо него показывается честный `dark-only` статус с пояснением про legacy-значения.
- `gui/native_shell_shared.py` теперь нормализует любые сохранённые значения `theme` к `dark`, не расширяя persisted-поле и не меняя launcher/D-Bus contract.
- Обновлены `tests/test_native_shell_app.py` и `tests/test_native_shell_shared.py`; полный прогон `tests.test_native_shell_app`, `tests.test_native_shell_shared`, `tests.test_subvost_app_service`, `tests.test_gui_server` прошёл успешно.

## Критерии завершения

- `GTK4` shell ощущается как компактная desktop utility, а не как oversized dashboard;
- geometry не выходит за рамки `Full HD`, а `resize/maximize` работают предсказуемо;
- `Dashboard` не тратит экран на лишнюю поясняющую прозу и giant banner;
- визуальный контракт тёмной темы консистентен на `Sidebar / Log / Settings`;
- новый ручной smoke приложен и подтверждает устранение исходных UX-дефектов.

## Остаточный риск

Автоматизированная сессия не подтвердила живой `GTK` smoke: попытка запуска `./open-subvost-gtk-ui.sh --disable-tray` завершилась ошибкой `Gtk не видит доступный display, хотя DISPLAY/WAYLAND объявлены`. Поэтому geometry, `resize/maximize` и отсутствие visual-регрессий ещё нужно подтвердить на реальном display с `xwininfo`, `wmctrl`, `xprop` и новыми screenshot-артефактами.
