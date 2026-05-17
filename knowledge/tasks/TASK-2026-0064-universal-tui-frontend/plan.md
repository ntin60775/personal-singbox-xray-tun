# План задачи TASK-2026-0064

## Обзор

Реализация универсального TUI-фронта на `textual` для замены WebKitGTK + GTK4 Native Shell.

## Фазы

### Фаза 1: Bootstrap и зависимости
- [ ] `gui/tui_bootstrap.py` — проверка `python3-textual`, `xray`, `iproute2`, `curl`, `/dev/net/tun`
- [ ] Предложение установки через `pkexec apt-get install`
- [ ] Wrapper `open-subvost-tui.sh`
- [ ] `.desktop` файл `open-subvost-tui.desktop`

### Фаза 2: Ядро TUI-приложения
- [ ] `gui/tui_app.py` — базовое приложение `textual` с CSS
- [ ] Экран Dashboard: статус, активный узел, Старт/Стоп/Диагностика
- [ ] Экран Узлы/Подписки: таблица узлов, импорт, обновление, выбор
- [ ] Экран Лог: просмотр с кнопкой Обновить
- [ ] Экран Routing: профили, geodata, direct-отчёт
- [ ] Экран Настройки: логирование, retention, тема

### Фаза 3: Tray-индикатор
- [ ] `gui/tui_tray.py` — Ayatana/AppIndicator tray
- [ ] Меню: Показать, Старт, Стоп, Диагностика, Выход
- [ ] Синхронизация статуса с TUI

### Фаза 4: Удаление legacy GUI
- [ ] Удаление `gui/embedded_webview.py`
- [ ] Удаление `gui/native_shell_app.py`
- [ ] Удаление `gui/native_shell_tray_helper.py`
- [ ] Удаление `open-subvost-gui.sh`
- [ ] Удаление `open-subvost-gtk-ui.sh`
- [ ] Удаление `open-subvost-gui.desktop`
- [ ] Удаление `open-subvost-gtk-ui.desktop`
- [ ] Обновление `AGENTS.md`, `DESIGN.md`, `README.md`

### Фаза 5: Проверка
- [ ] Syntax check всех новых `.py`
- [ ] Preflight check
- [ ] Ручной smoke: запуск, Старт, Стоп, Диагностика, выбор узла
