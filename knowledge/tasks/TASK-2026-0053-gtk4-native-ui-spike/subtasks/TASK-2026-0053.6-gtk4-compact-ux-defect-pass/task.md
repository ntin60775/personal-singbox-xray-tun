# Карточка задачи TASK-2026-0053.6

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0053.6` |
| Parent ID | `TASK-2026-0053` |
| Уровень вложенности | `1` |
| Ключ в путях | `TASK-2026-0053.6` |
| Технический ключ для новых именуемых сущностей | `gtk4-compact-ux-defect-pass` |
| Краткое имя | `gtk4-compact-ux-defect-pass` |
| Статус | `готова к работе` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `topic/gtk4-native-ui-spike` |
| Дата создания | `2026-04-10` |
| Дата обновления | `2026-04-10` |

## Цель

Превратить текущий `GTK4` shell в компактный desktop-интерфейс, который целиком помещается на `Full HD` без ручного ресайза, не прячет `CTA` за пределами экрана, не содержит лишних поясняющих текстов и не ломает тёмный визуальный контракт на `Sidebar / Log / Settings`.

## Подсказка по статусу

Использовать только одно из значений:

- `черновик`
- `готова к работе`
- `в работе`
- `на проверке`
- `ждёт пользователя`
- `заблокирована`
- `завершена`
- `отменена`

## Границы

### Входит

- исправление oversized geometry, default size и minimum size окна;
- восстановление рабочего `resize/maximize` поведения;
- перепаковка `Dashboard` в компактную верхнюю часть экрана без прокрутки;
- удаление бесполезного верхнего баннера и избыточных поясняющих текстов;
- выравнивание тёмного визуального контракта для `StackSidebar`, `Log` и `Settings`;
- честный `dark-only` контракт в настройках;
- повторный ручной smoke и перенос smoke-артефактов в knowledge-контур.

### Не входит

- новый функционал runtime, routing или tray;
- перевод native UI в основной launcher проекта;
- полноценный multi-theme pass;
- переписывание service-layer, parser/store/runtime контрактов без прямой связи с UX-дефектами.

## Контекст

- источник постановки: архивный ручной GTK smoke от `2026-04-10`, выполненный через `./open-subvost-gtk-ui.sh`;
- в архиве зафиксированы экран `2560x1440`, окно `2892x1999` и `WM_NORMAL_HINTS` minimum size `2892x1999`, то есть shell сам требовал геометрию больше экрана;
- попытка уменьшить окно до `1400x980` не изменила geometry, поэтому `resize` был признан фактически неработающим;
- архивный план отдельно фиксировал UX-дефекты: oversized geometry, неработающий `resize/maximize`, бесполезный верхний banner, светлый `StackSidebar`, белую `Log` surface, misleading theme selector и недоступность части header-`CTA`;
- исходный план существовал только в архивах Codex-сессий и не был перенесён в репозиторий; текущая сессия восстанавливает его как полноценную подзадачу с raw-артефактами.

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| `GTK4` geometry / layout | Нужно уменьшить default/minimum size и убрать давление oversized-layout на окно |
| Визуальный контракт | `Sidebar`, `Log` и `Settings` должны вернуться к консистентному тёмному виду |
| Тексты и плотность | `Dashboard` должен остаться рабочим экраном, а не полотном пояснений |
| Knowledge / ручной smoke | Восстановлены task-контур и артефакты ручного smoke |

## Связанные материалы

- основной каталог подзадачи: `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.6-gtk4-compact-ux-defect-pass/`
- файл плана: `plan.md`
- сводка архивного smoke: `artifacts/manual-smoke/smoke-summary.md`
- raw screenshot-артефакты: `artifacts/manual-smoke/raw/`
- родительская задача: `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/`
- тестовый launcher из предыдущей подзадачи: `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.5-gtk-test-launcher/`

## Текущий этап

Подзадача восстановлена из архивного плана и готова к реализации. В текущей сессии перенесены knowledge-артефакты и raw `PNG`; кодовые правки `GTK4` UI ещё не начинались.

## Стратегия проверки

### Покрывается кодом или тестами

- `python3 -m unittest tests.test_native_shell_app tests.test_native_shell_shared tests.test_subvost_app_service tests.test_gui_server`;
- `python3 -m py_compile gui/native_shell_app.py gui/native_shell_shared.py gui/subvost_app_service.py gui/gui_server.py`;
- локализационная проверка новых и обновлённых Markdown-файлов через `markdown-localization-guard`.

### Остаётся на ручную проверку

- повторный запуск `./open-subvost-gtk-ui.sh` на живом display;
- фиксация geometry через `xwininfo`, `wmctrl` и `xprop`;
- smoke экранов `Dashboard / Subscriptions / Log / Settings`;
- проверка доступности header-`CTA`, реального `resize/maximize` и отсутствия giant banner;
- проверка, что `Log` не рендерится белым полотном, а idle-сценарий больше не воспроизводит repeated `GtkBox ... natural size must be >= min size`.

## Критерии готовности

- окно по умолчанию и minimum size не превышают `1280x900`;
- shell целиком виден на `1920x1080` без обязательного ручного ресайза;
- `resize` и `maximize` реально меняют geometry через window manager;
- `Dashboard` содержит только краткий рабочий контекст и базовые действия;
- `StackSidebar`, `Log` и `Settings` работают в одном тёмном визуальном контракте;
- настройка темы больше не обещает режимы, которых shell фактически не поддерживает;
- повторный smoke приложен в knowledge вместе с новыми screenshot-артефактами.

## Итог

Подзадача восстановлена как потерянное продолжение после архивного ручного smoke от `2026-04-10`. В рамках текущей сессии оформлены `task.md`, `plan.md`, `smoke-summary.md`, перенесены raw screenshot-артефакты и синхронизирован knowledge-контур; реализация UX-исправлений остаётся следующим этапом.
