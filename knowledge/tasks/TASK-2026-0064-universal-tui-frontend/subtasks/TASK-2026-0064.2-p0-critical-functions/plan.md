# План подзадачи TASK-2026-0064.2

## Обзор

Реализация P0-критичных функций TUI: активация узла, импорт подписки, импорт ссылок.

## Фазы

### Фаза 1: Активация узла
- [x] Добавить кнопку "Активировать" в NodesTab
- [x] Обработчик `on_data_table_row_selected` для выбора строки
- [x] Метод `_action_activate_node` с вызовом `service.activate_selection`

### Фаза 2: Импорт подписки
- [x] Создать `ImportSubscriptionModal` (Input name + Input URL)
- [x] Заменить заглушку `_action_import_subscription`
- [x] Вызов `service.add_subscription(name, url)`

### Фаза 3: Импорт ссылок
- [x] Создать `ImportLinkModal` (TextArea для ссылок)
- [x] Заменить заглушку `_action_add_manual`
- [x] Вызов `preview_links` + `save_manual_import_results`

### Фаза 4: Проверка
- [x] Syntax check Python
- [ ] Ручной smoke: импорт подписки, выбор узла, активация, старт
