# План задачи TASK-2026-0055

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0055` |
| Parent ID | `—` |
| Версия плана | `1` |
| Дата обновления | `2026-04-12` |

## Цель

Поставить в проект новый eye-target `SVG` как основную иконку bundle, не меняя путь `assets/subvost-xray-tun-icon.svg`, и добить desktop icon lookup до реального показа иконки в файловом менеджере и launcher-окружении.

## Границы

### Входит

- замена содержимого `assets/subvost-xray-tun-icon.svg`;
- refresh user-local icon cache после обновления symlink на иконку;
- синхронизация icon lookup для обоих desktop launcher-ов (`GUI` и `GTK UI`);
- принудительное обновление timestamp launcher-файлов, чтобы файловый менеджер инвалидировал старый preview even when `Icon=` already matches;
- синхронизация `task.md`, `plan.md` и `knowledge/tasks/registry.md`;
- техническая проверка валидности нового `SVG`.

### Не входит

- массовая переработка других иконок и secondary-иллюстраций;
- отдельный multi-size экспорт в PNG;
- ручной screenshot-based аудит launcher на всех окружениях.

## Планируемые изменения

### Assets

- заменить текущий `SVG`-ассет eye-target вариантом из пользовательского запроса;
- сохранить текущий путь `assets/subvost-xray-tun-icon.svg`, чтобы launcher, favicon и icon-sync оставались совместимыми без дополнительных изменений.

### Код / shell-контракт

- перевести native shell и tray-helper на именованную иконку `subvost-xray-tun-icon`, чтобы они не продолжали просить stock `network-vpn`.
- после обновления user-local `hicolor` symlink принудительно обновлять icon cache, чтобы `Thunar` и launcher не оставались на generic gear из-за stale cache;
- расширить `subvost_sync_desktop_launcher_icon` на `subvost-xray-tun.desktop` и `subvost-xray-tun-gtk-ui.desktop`.

### Knowledge

- создать новый task-контур `TASK-2026-0055`;
- обновить `knowledge/tasks/registry.md` строкой новой задачи;
- после реализации синхронизировать фактический результат и проверки.

## Риски и зависимости

- новый образ может оказаться визуально слишком сложным на очень малых размерах;
- без ручного просмотра нельзя окончательно подтвердить, как eye-target и красный target читаются на конкретной desktop theme;
- иконка может не отображаться сразу, если desktop-среда держит stale icon cache;
- важно не менять путь asset-файла, иначе затронется больше интеграций, чем просит задача.

## Проверки

### Что можно проверить кодом или тестами

- `python3 -c "import xml.etree.ElementTree as ET; ET.parse('assets/subvost-xray-tun-icon.svg')"`
- `rg -n "subvost-xray-tun-icon.svg" -S`
- `python3 -m unittest tests.test_gui_server tests.test_native_shell_app`
- `git diff --check`
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/TASK-2026-0055-main-icon-eye-target/task.md knowledge/tasks/TASK-2026-0055-main-icon-eye-target/plan.md knowledge/tasks/registry.md`

### Что остаётся на ручную проверку

- перенос bundle на другой ПК с тем же desktop-стеком и подтверждение, что первый штатный sync даёт тот же результат;
- субъективная оценка читаемости на малых размерах на других темах и DPI.

## Шаги

- [x] Открыть отдельный task `TASK-2026-0055`
- [x] Заменить `assets/subvost-xray-tun-icon.svg` на новый eye-target `SVG`
- [x] Проверить валидность `SVG` и сохранить существующие ссылки на asset-path
- [x] Добавить refresh icon cache и синхронизацию обоих desktop launcher-ов
- [x] Синхронизировать итог и реестр задач

## Критерии завершения

- новый eye-target `SVG` лежит по пути `assets/subvost-xray-tun-icon.svg`;
- ссылки на ассет в launcher и GUI не требуют правок;
- sync helper обновляет user-local icon cache и оба desktop launcher-а;
- `SVG` валиден как XML;
- task-контур оформлен и синхронизирован.
