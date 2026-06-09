# TASK-2026-0066: DDD-рефакторинг архитектуры проекта

| Поле | Значение |
|---|---|
| ID | `TASK-2026-0066` |
| Статус | `черновик` |
| Приоритет | `средний` |
| Ветка | `main` |
| Каталог | `knowledge/tasks/TASK-2026-0066-ddd-refactoring/` |

## Краткое описание

Перевести архитектуру проекта с Transaction Script + God Object (`SubvostAppService`, 1846 строк, 42 метода) на Domain-Driven Design с явными границами слоёв: Domain (сущности, value objects, агрегаты), Application (use cases, ports), Infrastructure (адаптеры, репозитории), Presentation (ViewModel).

## Мотивация

Архитектурный аудит (2026-06-09) выявил:

- **Нет доменной модели.** Все данные — сырые `dict[str, Any]`, нет ни одной сущности, ни одного инварианта.
- **God Object.** `SubvostAppService` смешивает 5 зон ответственности: persistence CRUD, shell orchestration, system queries, UI strings, network probing.
- **Store — 1480 строк процедурных мутаций.** Нет Repository, нет Unit of Work.
- **Shell-слой дублирует логику.** 3 разных способа чтения store JSON, дублирование install-id и ICMP cleanup.
- **UI-строки в сервисном слое.** Все русские лейблы жёстко закодированы в `SubvostAppService`.

Единственный DDD-совместимый модуль — `subvost_parser.py` (чистая функция, один доменный тип, ноль внутрипроектных зависимостей).

## Ожидаемый результат

- Домен выражен в типах: `Node`, `Subscription`, `Profile`, `RoutingProfile`, `NodeAddress`, `ProtocolConfig`
- `SubvostAppService` сокращён до ~400 строк оркестрации
- Use Cases (`StartRuntimeUseCase`, `ImportSubscriptionUseCase`, `CollectStatusUseCase`) тестируемы изолированно
- UI-строки в `StatusViewModel`, отделены от бизнес-логики
- Shell-скрипты не дублируют логику
- Все 73 существующих теста проходят на каждом шаге

## План

См. [`plan.md`](./plan.md) — 7 фаз, ~5 недель:

1. Доменные сущности и value objects
2. Репозитории и Unit of Work
3. Разделение God Object на Use Cases
4. ViewModel — отделение presentation от application
5. Чистка shell-слоя
6. Разделение `subvost_routing.py`
7. Характеризационные и интеграционные тесты

## Подзадачи

| ID | Статус | Описание |
|---|---|---|
| `TASK-2026-0066.1` | `черновик` | Фаза 1: Доменные сущности, value objects, фабрики, события |
| `TASK-2026-0066.2` | `черновик` | Фаза 2: Репозитории, Unit of Work, миграция вызовов |
| `TASK-2026-0066.3` | `черновик` | Фаза 3: Use Cases, Ports, Adapters |
| `TASK-2026-0066.4` | `черновик` | Фаза 4: ViewModel, отделение presentation |
| `TASK-2026-0066.5` | `черновик` | Фаза 5: Дедупликация shell-слоя |
| `TASK-2026-0066.6` | `черновик` | Фаза 6: Разделение `subvost_routing.py` |
| `TASK-2026-0066.7` | `черновик` | Фаза 7: Тесты (характеризационные + интеграционные) |

## Решения

Решения фиксируются в [`decisions.md`](./decisions.md).

## Связанные задачи

- `TASK-2026-0064` — Универсальный TUI-фронт (текущий UI, который рефакторим)
- `TASK-2026-0048` — Routing-профили (один из рефакторимых модулей)
