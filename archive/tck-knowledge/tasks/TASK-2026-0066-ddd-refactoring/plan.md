# План: DDD-рефакторинг Subvost Xray TUN

## Цель

Перевести архитектуру проекта с Transaction Script + God Object на Domain-Driven Design с явными границами слоёв и зонами ответственности.

## Исходное состояние (что рефакторим)

| Модуль | Строк | Проблема |
|---|---|---|
| `subvost_app_service.py` | 1846 | God Object: 5 зон ответственности в 42 методах |
| `subvost_store.py` | 1480 | Процедурный CRUD на сырых dict без инвариантов |
| `subvost_routing.py` | 664 | 4 разнородных концерна в одном файле |
| `subvost_parser.py` | 678 | **Эталонный модуль** — не трогаем |
| `subvost_runtime.py` | 245 | Чистая генерация конфига — почти ок |
| Shell-скрипты | ~1500 | Дублирование логики, inline Python, 3 разных способа чтения store |
| `tui_app.py` | 1229 | UI без ViewModel, прямые вызовы God Object |

## Принципы рефакторинга

1. **Не ломать работающее.** Каждая фаза сохраняет прохождение всех 73 тестов.
2. **Вытягивать, а не переписывать.** Выделяем доменные типы из dict, а не пишем с нуля.
3. **Incremental.** Никаких «остановим разработку на месяц». Одна фаза = одна неделя.
4. **Тесты — граница безопасности.** Перед каждой фазой добавляем характеризационные тесты на поведение, которое будем менять.
5. **Python 3.11+ датаклассы** — не тянем тяжёлые ORM/фреймворки.

---

## Фаза 1: Доменные сущности и value objects

**Срок:** ~1 неделя. **Риск:** низкий (только добавляем типы, не меняем поведение).

### 1.1 Value Objects

Создать `gui/domain/value_objects.py`:

```python
@dataclass(frozen=True)
class NodeAddress:
    host: str
    port: int
    transport: str  # "tcp", "ws", "grpc", "quic"

@dataclass(frozen=True)
class ProtocolConfig:
    protocol: str  # "vless", "vmess", "trojan", "shadowsocks"
    uuid: str
    encryption: str
    # ... поля из node dict

@dataclass(frozen=True)
class TransportHint:
    """interface + mark для TUN-маршрутизации."""
    interface: str | None
    mark: int | None
```

### 1.2 Entities

Создать `gui/domain/entities.py`:

```python
@dataclass
class Node:
    id: str
    profile_id: str
    name: str
    address: NodeAddress
    protocol_config: ProtocolConfig
    transport_hint: TransportHint | None
    # доменные методы
    def is_valid(self) -> bool: ...
    def matches_fingerprint(self, fp: str) -> bool: ...
    def render_outbound(self) -> dict: ...  # то, что сейчас в subvost_runtime

@dataclass
class Subscription:
    id: str
    url: str
    name: str
    nodes: list[Node]
    # инварианты
    def has_nodes(self) -> bool: ...
    def active_node_count(self) -> int: ...

@dataclass
class Profile:
    id: str
    name: str
    nodes: list[Node]
    # агрегат: Profile — корень, Node — дочерняя сущность
    def activate_node(self, node_id: str) -> None: ...
    def add_node(self, node: Node) -> None: ...
    def remove_node(self, node_id: str) -> None: ...

@dataclass
class RoutingProfile:
    id: str
    name: str
    source_url: str | None
    geodata_ready: bool
    rules: list[RoutingRule]
```

### 1.3 Фабрики из dict

Создать `gui/domain/factories.py`:

```python
def node_from_dict(d: dict) -> Node: ...
def subscription_from_dict(d: dict) -> Subscription: ...
def profile_from_dict(d: dict) -> Profile: ...
def routing_profile_from_dict(d: dict) -> RoutingProfile: ...

def node_to_dict(n: Node) -> dict: ...  # обратно для store
# ...
```

### 1.4 Доменные события

Создать `gui/domain/events.py`:

```python
@dataclass(frozen=True)
class RuntimeStarted: ...

@dataclass(frozen=True)
class RuntimeStopped: ...

@dataclass(frozen=True)
class NodeActivated:
    node_id: str
    profile_id: str

@dataclass(frozen=True)
class SubscriptionImported:
    subscription_id: str
    node_count: int
```

### 1.5 Проверка

- 73 существующих теста продолжают проходить
- Добавить unit-тесты на `node_from_dict()` / `node_to_dict()` — roundtrip
- Добавить тест на `Profile.activate_node()` — проверка инварианта «узел принадлежит профилю»

---

## Фаза 2: Репозитории

**Срок:** ~1 неделя. **Риск:** средний (меняем слой персистенции).

### 2.1 Порт репозитория

Создать `gui/application/ports.py`:

```python
class NodeRepository(Protocol):
    def get_active(self) -> Node | None: ...
    def get_by_id(self, profile_id: str, node_id: str) -> Node | None: ...
    def save(self, profile_id: str, node: Node) -> None: ...
    def delete(self, profile_id: str, node_id: str) -> None: ...

class SubscriptionRepository(Protocol): ...
class ProfileRepository(Protocol): ...
class RoutingRepository(Protocol): ...
```

### 2.2 JSON-адаптер

Создать `gui/infrastructure/json_repositories.py`:

```python
class JsonNodeRepository:
    """Реализация NodeRepository поверх существующего store.json."""
    def __init__(self, store_path: Path): ...
    # внутри использует существующие функции subvost_store
    # но возвращает domain.Node, а не dict
```

### 2.3 Unit of Work

Создать `gui/infrastructure/unit_of_work.py`:

```python
@dataclass
class StoreUnitOfWork:
    """Координирует запись: загрузить store, изменить, атомарно сохранить."""
    store_path: Path
    _store: dict | None = None
    
    def __enter__(self) -> StoreUnitOfWork: ...
    def __exit__(self, ...): ...  # atomic_write_json
    def rollback(self): ...
```

### 2.4 Миграция вызовов в SubvostAppService

Заменить прямые вызовы `subvost_store.save_profile(store, profile_dict)` на `profile_repo.save(domain.Profile(...))` — **по одному методу за раз**, с тестами после каждого.

### 2.5 Проверка

- Существующие тесты проходят (временные адаптеры dict↔domain на границах)
- Новые тесты: `JsonNodeRepository` read/write/delete roundtrip
- Новые тесты: `StoreUnitOfWork` commit/rollback

---

## Фаза 3: Разделение God Object на Use Cases

**Срок:** ~2 недели. **Риск:** высокий (ядро системы).

### 3.1 Инвентаризация методов SubvostAppService

Разбить 42 метода на категории (результат уже есть из архитектурного аудита):

| Категория | Количество методов | Куда |
|---|---|---|
| Store CRUD | 17 | Repository (Фаза 2) |
| Shell orchestration | 6 | Infrastructure Adapters |
| System queries | 8 | Infrastructure Adapters |
| UI strings | 11 | Presentation ViewModel |
| Network probing | 1 | Domain Service → Infrastructure |

### 3.2 Use Cases (Application Layer)

Создать `gui/application/use_cases.py`:

```python
@dataclass
class StartRuntimeUseCase:
    runtime_adapter: RuntimePort
    node_repo: NodeRepository
    
    def execute(self) -> RuntimeResult: ...

@dataclass
class StopRuntimeUseCase:
    runtime_adapter: RuntimePort
    
    def execute(self) -> None: ...

@dataclass
class ImportSubscriptionUseCase:
    subscription_repo: SubscriptionRepository
    parser: SubscriptionParser  # subvost_parser
    
    def execute(self, url: str) -> ImportResult: ...

@dataclass
class CollectStatusUseCase:
    """Сборка read-model для UI."""
    runtime_adapter: RuntimePort
    node_repo: NodeRepository
    subscription_repo: SubscriptionRepository
    # ...
    
    def execute(self) -> StatusDTO: ...

@dataclass
class ActivateNodeUseCase: ...
@dataclass
class RefreshSubscriptionUseCase: ...
@dataclass
class PingNodeUseCase: ...
```

### 3.3 Порт RuntimePort

Создать `gui/application/ports.py`:

```python
class RuntimePort(Protocol):
    def start(self, config_path: Path, asset_dir: Path) -> RuntimeResult: ...
    def stop(self) -> None: ...
    def status(self) -> RuntimeStatus: ...
```

### 3.4 Порт NetworkPort

```python
class NetworkPort(Protocol):
    def ping(self, host: str, port: int, timeout: float = 2.0) -> PingResult: ...
    def read_resolv_conf_nameservers(self) -> list[str]: ...
    def read_interface_addresses(self) -> list[InterfaceAddress]: ...
    def collect_traffic_metrics(self, interface: str) -> TrafficMetrics: ...
```

### 3.5 Адаптеры (Infrastructure)

Создать `gui/infrastructure/adapters.py`:

```python
class ShellRuntimeAdapter:
    """RuntimePort через pkexec + shell-скрипты."""
    # переносит run_shell_action(), build_shell_action_command() из SubvostAppService

class SystemNetworkAdapter:
    """NetworkPort через /proc, /sys, socket."""
    # переносит inspect_runtime_state(), ping_node_by_id() и т.д.
```

### 3.6 Подключение в tui_app.py

```python
# Было:
service = build_default_service(gui_dir)
status = service.collect_status()

# Стало:
uow = StoreUnitOfWork(store_path)
repos = JsonRepositories(uow)
runtime = ShellRuntimeAdapter(project_root)
network = SystemNetworkAdapter()

status = CollectStatusUseCase(
    runtime_adapter=runtime,
    network_adapter=network,
    node_repo=repos.nodes,
    # ...
).execute()
```

### 3.7 Проверка

- Все 73 теста проходят
- Новые тесты: `StartRuntimeUseCase` с mock-адаптером
- Новые тесты: `CollectStatusUseCase` — структура StatusDTO без реальной сети

---

## Фаза 4: ViewModel — отделение presentation от application

**Срок:** ~3 дня. **Риск:** низкий.

### 4.1 Статус-лейблы и бейджи

Создать `gui/presentation/view_models.py`:

```python
@dataclass
class StatusViewModel:
    """Все русские строки для UI."""
    connection_status: str
    traffic_summary: str
    node_badge: str
    # ...
    
    @classmethod
    def from_status_dto(cls, dto: StatusDTO) -> StatusViewModel:
        """Фабрика: domain DTO → UI-строки."""
        ...
```

### 4.2 Перенос строк из SubvostAppService

Все методы `_humanize_*`, `_resolve_status_*`, `_build_summary_*` переносятся в `StatusViewModel` или хелперы. `SubvostAppService` перестаёт генерировать UI-строки — отдаёт только DTO.

### 4.3 Проверка

- TUI визуально не отличается от текущего
- Строковые константы больше не лежат в `subvost_app_service.py`

---

## Фаза 5: Чистка shell-слоя

**Срок:** ~3 дня. **Риск:** средний (shell сложно тестировать).

### 5.1 Единый Python CLI для чтения store

Создать `libexec/_subvost_store_reader.py`:

```python
"""CLI для shell-скриптов: читает store JSON и возвращает нужные поля."""
# Замена трём разным inline-Python реализациям в shell-скриптах
```

Использование в shell:
```bash
ACTIVE_NODE_ID=$(python3 "${SUBVOST_LIBEXEC_DIR}/_subvost_store_reader.py" active-node-id)
ACTIVE_PROFILE_ID=$(python3 "${SUBVOST_LIBEXEC_DIR}/_subvost_store_reader.py" active-profile-id)
```

### 5.2 Вынос install-id логики в общую функцию

В `lib/subvost-common.sh` уже есть `subvost_ensure_install_id()`. Убрать дубликаты проверок в `run` и `stop` — вызывать общую функцию.

### 5.3 Вынос ICMP cleanup в общую функцию

`cleanup_ufw_icmp_fix()` дублирована в run и stop. Вынести в `lib/subvost-common.sh` или отдельный `libexec/_ufw_helpers.sh`.

### 5.4 Проверка

- `bash -n` на всех скриптах
- Ручной smoke: run → stop → нет мусора

---

## Фаза 6: Разделение subvost_routing.py

**Срок:** ~2 дня. **Риск:** низкий.

### 6.1 Разделить на два модуля

```
gui/routing/
├── __init__.py          # реэкспорт
├── profile_manager.py   # парсинг hap:// URI, управление профилями, geodata download
└── config_rewriter.py   # apply_routing_profile_to_config()
```

Существующий `subvost_routing.py` → `routing/profile_manager.py` + `routing/config_rewriter.py`.

### 6.2 Проверка

- Все импорты `from subvost_routing import ...` продолжают работать через `__init__.py`
- Тесты проходят

---

## Фаза 7: Характеризационные и интеграционные тесты

**Срок:** ~1 неделя. **Риск:** низкий (только добавляем).

### 7.1 Доменные тесты

- `Node.from_dict()` / `Node.to_dict()` roundtrip для каждого протокола
- `Profile.activate_node()` — нормальный путь + ошибка «узел не из этого профиля»
- `Subscription.has_nodes()` — пустая подписка, нормальная, after refresh

### 7.2 Use Case тесты с mock-адаптерами

- `StartRuntimeUseCase` — успех / отказ / уже запущен
- `ImportSubscriptionUseCase` — успех / невалидный URL / пустой ответ
- `CollectStatusUseCase` — все секции StatusDTO без реальной сети

### 7.3 Проверка

```bash
python3 -m pytest tests/domain/ tests/application/ tests/infrastructure/
```

---

## Сводка по файлам (новые и изменяемые)

| Файл | Статус |
|---|---|
| `gui/domain/__init__.py` | Новый |
| `gui/domain/value_objects.py` | Новый |
| `gui/domain/entities.py` | Новый |
| `gui/domain/factories.py` | Новый |
| `gui/domain/events.py` | Новый |
| `gui/application/__init__.py` | Новый |
| `gui/application/ports.py` | Новый |
| `gui/application/use_cases.py` | Новый |
| `gui/application/dto.py` | Новый |
| `gui/infrastructure/__init__.py` | Новый |
| `gui/infrastructure/json_repositories.py` | Новый |
| `gui/infrastructure/unit_of_work.py` | Новый |
| `gui/infrastructure/adapters.py` | Новый |
| `gui/presentation/__init__.py` | Новый |
| `gui/presentation/view_models.py` | Новый |
| `gui/routing/__init__.py` | Новый |
| `gui/routing/profile_manager.py` | Новый (из `subvost_routing.py`) |
| `gui/routing/config_rewriter.py` | Новый (из `subvost_routing.py`) |
| `libexec/_subvost_store_reader.py` | Новый |
| `gui/subvost_app_service.py` | **Сильно изменён** (уменьшен до ~400 строк) |
| `gui/subvost_store.py` | **Изменён** (репозитории — обёртка, старые функции не удаляем) |
| `gui/subvost_routing.py` | **Удалён** (разделён) |
| `gui/tui_app.py` | **Слегка изменён** (инжектирование зависимостей) |
| `lib/subvost-common.sh` | **Слегка изменён** (дедупликация) |
| `libexec/run-xray-tun-subvost.sh` | **Слегка изменён** (единый store reader) |
| `libexec/stop-xray-tun-subvost.sh` | **Слегка изменён** (единый store reader) |

## Ожидаемый результат

После всех фаз:

- Домен выражен в типах — `Node`, `Subscription`, `Profile`, `RoutingProfile`
- Инварианты enforced на уровне агрегатов, а не размазаны по 1480 строкам store
- `SubvostAppService` сокращён с 1846 до ~400 строк оркестрации
- Use Cases тестируемы изолированно (с mock-адаптерами)
- UI строки отделены от бизнес-логики
- Shell-скрипты не дублируют логику
- 73 существующих теста проходят на каждом шаге
