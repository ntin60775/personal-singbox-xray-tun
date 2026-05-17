# SDD: Универсальный TUI-фронт TASK-2026-0064

## Архитектура

### Компоненты

```
┌─────────────────────────────────────┐
│         open-subvost-tui.sh         │
│   (wrapper: bootstrap → launch)     │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         gui/tui_bootstrap.py        │
│   (проверка зависимостей, apt)      │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│           gui/tui_app.py            │
│  (textual App: Dashboard/Nodes/     │
│   Log/Routing/Settings)             │
│  ↓ импортирует напрямую             │
│   subvost_app_service.py            │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│          gui/tui_tray.py            │
│   (фоновый tray-процесс)            │
└─────────────────────────────────────┘
```

### Правила

1. **Backend**: TUI импортирует `SubvostAppService` напрямую, не использует `gui_server.py`.
2. **Модальность**: при `pkexec`-действиях (Старт/Стоп) TUI показывает модальный диалог с прогрессом.
3. **Автообновление статуса**: таймер `set_interval(2.0)` на Dashboard, обновляет `inspect_runtime_state()`.
4. **Tray**: отдельный процесс `gui/tui_tray.py`, запускается при старте TUI, общается через state-файл или D-Bus (опционально).
5. **Bootstrap**: если `python3-textual` не найден — предлагает установить через `pkexec apt-get install -y python3-textual`.

## Экраны

### Dashboard
- Статус: connected / disconnected / error (цветной бейдж)
- Активный узел: имя, протокол, сервер
- Быстрые действия: `Старт` / `Стоп` / `Диагностика`
- Трафик: RX/TX за сессию
- Routing-бейдж: активный профиль

### Узлы и подписки
- DataTable: колонки `Имя | Протокол | Сервер | Пинг | Действия`
- Кнопки: `Импорт подписки` / `Обновить все` / `Добавить вручную`
- Контекстное меню на строке: `Активировать` / `Проверить` / `Удалить`

### Лог
- TextArea (read-only) с логом `logs/xray-subvost.log`
- Кнопка `Обновить` — перечитывает файл
- Фильтр: Все / Ошибки / Предупреждения

### Routing
- Список routing-профилей
- Статус geodata (GeoIP/GeoSite)
- Кнопка `Обновить geodata`
- Direct-отчёт (таблица)

### Настройки
- Переключатель `Файловые логи`
- `Retention days` (Input)
- Кнопка `Очистить артефакты`

## Зависимости

### Runtime
- `python3 >= 3.11`
- `python3-textual >= 2.0`
- `xray` (в PATH или `./xray`)
- `iproute2` (`ip`)
- `curl`
- `sudo` / `pkexec`
- `/dev/net/tun`

### Python imports
- `textual.app`, `textual.containers`, `textual.widgets`, `textual.screen`, `textual.reactive`
- `subvost_app_service` (build_default_service, SubvostAppService)
- `subvost_store` (store_payload)
- `subvost_paths` (build_app_paths)

## Invariant set

| # | Инвариант | Проверка |
|---|-----------|----------|
| 1 | TUI запускается без GUI backend | Ручной: `./open-subvost-tui.sh`, verify no `gui_server.py` in `ps` |
| 2 | Старт/Стоп работают через pkexec | Ручной: нажать Старт, проверить `ip rule show` |
| 3 | Tray запускается и реагирует на клик | Ручной: клик по tray-иконке |
| 4 | Выбор узла обновляет generated config | Ручной: активировать узел, проверить `generated-xray-config.json` |
| 5 | Bootstrap предлагает установить textual | Ручной: удалить `python3-textual`, запустить bootstrap |
| 6 | `.desktop` запускает TUI в терминале | Ручной: клик по ярлыку |
| 7 | Старые GUI удалены из репозитория | Авто: `test -f gui/embedded_webview.py` → fail |
| 8 | Лог-экран читает `logs/xray-subvost.log` | Авто: `python3 -m py_compile gui/tui_app.py` |
