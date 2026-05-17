# План задачи TASK-2026-0064

## Обзор

Реализация универсального TUI-фронта на `textual` для замены WebKitGTK + GTK4 Native Shell.

## Фазы

### Фаза 1: Bootstrap и зависимости
- [x] `gui/tui_bootstrap.py` — проверка `python3-textual`, `xray`, `iproute2`, `curl`, `/dev/net/tun`
- [x] Предложение установки через `pkexec apt-get install`
- [x] Wrapper `open-subvost-tui.sh`
- [x] `.desktop` файл `open-subvost-tui.desktop`

### Фаза 2: Ядро TUI-приложения
- [x] `gui/tui_app.py` — базовое приложение `textual` с CSS
- [x] Экран Dashboard: статус, активный узел, Старт/Стоп/Диагностика
- [x] Экран Узлы/Подписки: таблица узлов, импорт, обновление, выбор
- [x] Экран Лог: просмотр с кнопкой Обновить
- [x] Экран Routing: профили, geodata, direct-отчёт
- [x] Экран Настройки: логирование, retention, тема

### Фаза 3: Tray-индикатор
- [x] `gui/tui_tray.py` — Ayatana/AppIndicator tray
- [x] Меню: Показать, Старт, Стоп, Диагностика, Выход
- [x] Запуск tray из TUI, graceful shutdown

### Фаза 4: Удаление legacy GUI
- [x] Удаление `gui/embedded_webview.py`
- [x] Удаление `gui/native_shell_app.py`
- [x] Удаление `gui/native_shell_tray_helper.py`
- [x] Удаление `open-subvost-gui.sh`
- [x] Удаление `open-subvost-gtk-ui.sh`
- [x] Удаление `install-subvost-gtk-ui-menu-entry.sh`
- [x] Обновление `AGENTS.md`, `DESIGN.md`, `README.md`

### Фаза 5: Проверка
- [x] Syntax check всех новых `.py`
- [x] Preflight check `.sh`
- [ ] Ручной smoke: запуск, Старт, Стоп, Диагностика, выбор узла
