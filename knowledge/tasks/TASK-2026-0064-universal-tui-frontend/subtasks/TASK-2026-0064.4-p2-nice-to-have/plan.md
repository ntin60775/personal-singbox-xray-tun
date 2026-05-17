# План подзадачи TASK-2026-0064.4

## Обзор

Реализация P2-функций TUI: полный паритет со старым UI.

## Фазы

### Фаза 1: Импорт routing-профиля
- [x] ImportRoutingProfileModal (TextArea для JSON)
- [x] Метод `_action_import_routing_profile`

### Фаза 2: Сброс активного routing-профиля
- [x] Кнопка "❌ Сбросить профиль" в RoutingTab
- [x] Метод `_action_clear_routing_profile` с ConfirmModal

### Фаза 3: Terminate с confirm
- [x] `action_quit` с проверкой активного VPN
- [x] ConfirmModal "Остановить и выйти?" если подключение активно

### Фаза 4: Проверка
- [x] Syntax check Python
- [ ] Ручной smoke: импорт профиля, сброс, выход с активным VPN
