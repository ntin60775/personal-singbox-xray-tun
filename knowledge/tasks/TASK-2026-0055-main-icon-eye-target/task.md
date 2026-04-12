# Карточка задачи TASK-2026-0055

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0055` |
| Parent ID | `—` |
| Уровень вложенности | `0` |
| Ключ в путях | `TASK-2026-0055` |
| Технический ключ для новых именуемых сущностей | `main-icon-eye-target` |
| Краткое имя | `main-icon-eye-target` |
| Статус | `завершена` |
| Приоритет | `средний` |
| Ответственный | `Codex` |
| Ветка | `task/task-2026-0054-full-ui-redesign` |
| Дата создания | `2026-04-12` |
| Дата обновления | `2026-04-12` |

## Цель

Заменить основную `SVG`-иконку bundle на новый eye-target вариант, сохранив прежний asset-path `assets/subvost-xray-tun-icon.svg`, чтобы launcher, favicon и связанные точки использования автоматически подхватили новый образ.

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

- замена содержимого `assets/subvost-xray-tun-icon.svg` на новый eye-target `SVG`;
- перевод native shell и tray-helper на именованную app-иконку `subvost-xray-tun-icon` вместо stock `network-vpn`;
- форсированный refresh user-local `hicolor` icon cache после синхронизации ассета;
- мягкая invalidation launcher-preview через обновление timestamp `.desktop`-файла, если `Icon=` уже совпадает;
- расширение icon-sync на оба desktop launcher-а: `subvost-xray-tun.desktop` и `subvost-xray-tun-gtk-ui.desktop`;
- сохранение текущего пути ассета и совместимости со всеми существующими ссылками на него;
- синхронизация task-артефактов и реестра задач.

### Не входит

- смена имени asset-файла;
- redesign других иллюстраций и secondary-иконок интерфейса;
- ручная проверка отображения на всех темах, DPI и окружениях.

## Контекст

- пользователь прислал готовый `SVG`-концепт основной иконки: глаз, глобус-радужка, красный target и тёмный фон;
- в репозитории уже есть историческая задача `TASK-2026-0040` про прошлую замену иконки, но текущий запрос задаёт новый образ и требует отдельного контура;
- текущие точки использования иконки уже завязаны на `assets/subvost-xray-tun-icon.svg`, поэтому безопаснее заменить содержимое файла без смены пути.

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Именуемые asset-артефакты | Меняется содержимое `assets/subvost-xray-tun-icon.svg` |
| Интерфейсы / формы / страницы | Launcher, favicon и связанные UI-точки продолжают ссылаться на тот же asset-path, но получают новый визуальный образ |
| Shell / desktop lookup | Sync helper дополнительно обновляет icon cache и обе launcher-копии |
| Документация | Добавляется новый task-контур и обновляется `registry.md` |

## Связанные материалы

- основной каталог задачи: `knowledge/tasks/TASK-2026-0055-main-icon-eye-target/`
- файл плана: `plan.md`
- основной ассет: `assets/subvost-xray-tun-icon.svg`
- связанная предыдущая задача по иконке: `knowledge/tasks/TASK-2026-0040-anime-tech-icon/`
- связанная задача по desktop icon lookup: `knowledge/tasks/TASK-2026-0046-desktop-icon-local-assets/`

## Текущий этап

Задача завершена: eye-target `SVG` поставлен на путь `assets/subvost-xray-tun-icon.svg`, desktop icon lookup доработан до реального показа в `Thunar`, а пользователь подтвердил живое отображение иконки в текущем `XFCE/GTK`-окружении.

## Стратегия проверки

### Покрывается кодом или тестами

- `python3 -c "import xml.etree.ElementTree as ET; ET.parse('assets/subvost-xray-tun-icon.svg')"`
- `rg -n "subvost-xray-tun-icon.svg" -S`
- `python3 -m unittest tests.test_gui_server tests.test_native_shell_app`
- адресная проверка локализации Markdown через `markdown-localization-guard`
- `git diff --check`

### Остаётся на ручную проверку

- перенос bundle на другой ПК с тем же desktop-стеком для подтверждения, что первый штатный sync даёт тот же результат;
- субъективная оценка читаемости на малых размерах и высокой плотности пикселей на других темах.

## Критерии готовности

- `assets/subvost-xray-tun-icon.svg` заменён на eye-target вариант;
- ссылки на тот же asset-path в launcher и GUI остаются рабочими;
- sync helper обновляет user-local icon cache и не забывает про `GTK UI` launcher;
- `SVG` валиден как XML;
- task-контур и `registry.md` синхронизированы с фактической заменой.

## Итог

`assets/subvost-xray-tun-icon.svg` заменён на новый eye-target вариант из пользовательского `SVG`: тёмный квадрат со скруглением, красный target-контур, глаз, глобус-радужка и центральный shield-маркер. Путь ассета сохранён без изменений, поэтому launcher, favicon и существующие ссылки на `subvost-xray-tun-icon.svg` остаются совместимыми без дополнительных route-правок.

Дополнительно native shell и tray-helper переведены на именованную app-иконку `subvost-xray-tun-icon` вместо stock `network-vpn`, чтобы новый образ использовался не только launcher/favicion-контуром, но и самим приложением там, где работает user-local icon lookup.

После пользовательского замечания про отсутствие иконки в `Thunar` sync helper дополнительно форсирует `gtk-update-icon-cache` для user-local `hicolor`, обновляет обе desktop launcher-копии, включая `subvost-xray-tun-gtk-ui.desktop`, и мягко invalidates file-level preview cache через `touch` launcher-файла, если `Icon=` уже совпадает. Это убирает зависимость не только от stale icon cache, но и от ситуации, когда файловый менеджер держит старый generic preview для конкретного `.desktop`.

Пользователь подтвердил, что после этих правок иконка корректно отображается в реальном окне `Thunar`: сначала сработал `GTK UI` launcher, затем после invalidation-шага подтянулся и основной `subvost-xray-tun.desktop`.

Остаточный риск один: для нового ПК гарантируется корректный результат после первого штатного sync launcher-а или installer-а, но сценарий `git clone -> сразу открыть каталог без единого запуска` по-прежнему зависит от того, зарегистрирована ли именованная иконка в user-local XDG theme.
