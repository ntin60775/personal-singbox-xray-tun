# Карточка задачи TASK-2026-0064

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0064` |
| Parent ID | `—` |
| Уровень вложенности | `0` |
| Ключ в путях | `TASK-2026-0064` |
| Технический ключ для новых именуемых сущностей | `universal_tui` |
| Краткое имя | `universal-tui-frontend` |
| Человекочитаемое описание | Универсальный TUI-фронт для любого DE: XFCE, KDE, i3 и прочих Debian 12/13-based дистрибутивов |
| Статус | `в работе` |
| Приоритет | `высокий` |
| Ответственный | `не назначен` |
| Ветка | `task/task-2026-0064-universal-tui-frontend` |
| Требуется SDD | `да` |
| Статус SDD | `готов` |
| Ссылка на SDD | `sdd.md` |
| Дата создания | `2026-05-17` |
| Дата обновления | `2026-05-17` |

## Цель

Заменить существующие Linux-GUI (WebKitGTK + GTK4 Native Shell) одним универсальным TUI-фронтом на базе `textual`, который работает в любом эмуляторе терминала под любым DE без зависимости от GTK4/WebKitGTK/AppIndicator.

Результат для пользователя:
- Запуск через ярлык `.desktop` в любом DE
- Полная функциональность: Dashboard, Узлы/подписки, Лог, Routing, Настройки
- Tray-индикатор с быстрыми действиями
- Bootstrap из коробки: сам проверяет и предлагает установить зависимости

## Границы

### Входит

- Модуль `gui/tui_app.py` — основное TUI-приложение на `textual` с экранами Dashboard, Узлы, Лог, Routing, Настройки
- Модуль `gui/tui_bootstrap.py` — проверка зависимостей и предложение установки через `pkexec`
- Модуль `gui/tui_tray.py` — tray-индикатор (Ayatana/AppIndicator) с быстрыми действиями
- Wrapper-скрипт `open-subvost-tui.sh` для запуска
- `.desktop`-файл `open-subvost-tui.desktop` для запуска через меню приложений
- Удаление/deprecation старых GUI: `embedded_webview.py`, `native_shell_app.py`, `native_shell_tray_helper.py`, `open-subvost-gui.sh`, `open-subvost-gtk-ui.sh`, `open-subvost-gui.desktop`, `open-subvost-gtk-ui.desktop`
- Обновление `AGENTS.md` и `DESIGN.md`
- Обновление preflight-проверок (syntax check, .desktop validation)

### Не входит

- Изменение Windows-части (`windows/`, `gui/windows_core_cli.py`, `gui/windows_runtime_adapter.py`)
- Изменение `xray-tun-subvost.json` шаблона
- Изменение shell runtime (`run-xray-tun-subvost.sh`, `stop-xray-tun-subvost.sh`)
- Изменение `install-on-new-pc.sh`

## Контекст

- источник постановки: пользовательский запрос на универсальность GUI для KDE/XFCE
- связанная бизнес-область: Linux desktop frontend
- ограничения и зависимости: Debian 12/13, MX Linux 23.6/25, `python3-textual` из apt
- исходный наблюдаемый симптом / лог-маркер: GTK4 Native Shell выглядит чужеродно на KDE; WebKitGTK тяжёл в зависимостях; нет bootstrap для зависимостей
- основной контекст сессии: `текущая задача`

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | Новые `gui/tui_app.py`, `gui/tui_bootstrap.py`, `gui/tui_tray.py`; удаление `gui/embedded_webview.py`, `gui/native_shell_app.py`, `gui/native_shell_tray_helper.py` |
| Конфигурация / схема данных / именуемые сущности | Нет изменений в store-формате |
| Интерфейсы / формы / страницы | Полная замена Linux-GUI на TUI |
| Интеграции / обмены | Tray-индикатор через Ayatana/AppIndicator |
| Документация | Обновление `AGENTS.md`, `DESIGN.md`, `README.md` |

## Связанные материалы

- основной каталог задачи: `knowledge/tasks/TASK-2026-0064-universal-tui-frontend/`
- файл плана: `plan.md`
- файл контракта реализации: `sdd.md`
