# TASK-2026-0067: Декомпозиция God Object — миграция SubvostAppService в Use Cases

| Поле | Значение |
|---|---|
| ID | `TASK-2026-0067` |
| Статус | `черновик` |
| Приоритет | `высокий` |
| Ветка | `main` |
| Каталог | `knowledge/tasks/TASK-2026-0067-decompose-god-object/` |

## Краткое описание

Перенести 42 метода `SubvostAppService` (1845 строк) в use cases, адаптеры и ViewModel, заменив прямые вызовы `self.service.*` в `tui_app.py` на инжектированные зависимости. Цель: God Object → thin orchestration layer (~400 строк), TUI зависит от use cases, а не от монолита.

## Исходное состояние

Фазы 1-7 DDD-рефакторинга (TASK-2026-0066) создали архитектурный скелет:

- ✅ `gui/domain/` — сущности, value objects, фабрики
- ✅ `gui/infrastructure/` — репозитории, UoW, адаптеры
- ✅ `gui/application/` — порты, use cases (оболочки без имплементации)
- ✅ `gui/presentation/` — ViewModel
- ❌ `SubvostAppService` — НЕ тронут, 1845 строк, 25+ прямых вызовов из tui_app.py

## План миграции

### Шаг 1: StatusViewModel — сразу в бой (низкий риск)

Заменить dict-доступ в `tui_app.py._update_dashboard()` на `StatusViewModel`:

```python
# Было:
status = self.service.collect_status()
label = status.get("summary", {}).get("label", "—")

# Стало:
status = self.service.collect_status()
vm = build_view_model(status)
label = vm.connection_label
```

**Файлы:** `tui_app.py` (методы `_update_dashboard`, `_update_nodes`, `_update_routing`, `_update_log`)

### Шаг 2: SystemNetworkAdapter — пинг и системные запросы

Выделить `ping_node_by_id()` из `SubvostAppService` в `SystemNetworkAdapter`. Заменить вызов в `tui_app.py._action_ping()`.

### Шаг 3: ShellRuntimeAdapter — start/stop/diagnostics

Выделить `start_runtime()`, `stop_runtime()`, `capture_diagnostics()` из `SubvostAppService` в `ShellRuntimeAdapter`. Заменить вызовы в `tui_app.py`.

### Шаг 4: Репозитории — Store CRUD

Заменить прямые вызовы `self.service.add_subscription()`, `self.service.delete_subscription()`, `self.service.activate_selection()` на репозитории через UoW.

### Шаг 5: Оставшиеся методы

`refresh_subscription()`, `refresh_all_subscriptions()`, `import_routing_profile()`, `load_settings()`, `save_settings()`, `cleanup_runtime_artifacts()`, `collect_log_payload()`, `prepare_routing_geodata()`, `set_routing_enabled()`.

### Шаг 6: Удаление мёртвого кода

После полной миграции `SubvostAppService` сокращается до ~400 строк (только `collect_status()`, `collect_store_snapshot()` и glue-код). `tui_app.py` инициализирует зависимости через DI-контейнер.

## Ожидаемый результат

- `SubvostAppService` ≤ 400 строк (было 1845)
- `tui_app.py` НЕ импортирует `SubvostAppService` напрямую
- Все 125+ тестов проходят
- TUI визуально не отличается

## Подзадачи

| ID | Описание |
|---|---|
| `TASK-2026-0067.1` | Шаг 1: StatusViewModel в tui_app.py |
| `TASK-2026-0067.2` | Шаг 2: SystemNetworkAdapter — ping |
| `TASK-2026-0067.3` | Шаг 3: ShellRuntimeAdapter — start/stop/diag |
| `TASK-2026-0067.4` | Шаг 4: Репозитории — Store CRUD |
| `TASK-2026-0067.5` | Шаг 5: Оставшиеся методы |
| `TASK-2026-0067.6` | Шаг 6: Чистка и финальный suite |

## Связанные задачи

- `TASK-2026-0066` — DDD-рефакторинг архитектуры (инфраструктура готова)
