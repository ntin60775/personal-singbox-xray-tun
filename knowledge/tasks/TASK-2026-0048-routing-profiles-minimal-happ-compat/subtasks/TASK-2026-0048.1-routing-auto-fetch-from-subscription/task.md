# Карточка задачи TASK-2026-0048.1

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0048.1` |
| Parent ID | `TASK-2026-0048` |
| Уровень вложенности | `1` |
| Ключ в путях | `TASK-2026-0048.1` |
| Технический ключ для новых именуемых сущностей | `routing-auto-fetch` |
| Краткое имя | `routing-auto-fetch-from-subscription` |
| Человекочитаемое описание | `Автоматически получать routing-профиль из подписки через `routing` metadata и `providerId`, связывать auto-managed профиль с подпиской и чистить stale state` |
| Статус | `на проверке` |
| Приоритет | `средний` |
| Ответственный | `Codex` |
| Ветка | `main` |
| Дата создания | `2026-04-08` |
| Дата обновления | `2026-04-28` |

## Цель

Подготовить следующий этап после import-first реализации: автоматически получать routing-профиль из подписки и связывать его с конкретным subscription/provider-контекстом без ручного copy-paste.

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

- поддержка `routing` header;
- поддержка mixed-body payload с `happ://routing/...`;
- связка routing-профиля с конкретной подпиской и `providerId`;
- обновление routing-профиля на `refresh` подписки.

### Не входит

- ручной импорт routing-профиля;
- базовая geodata и runtime-overlay, реализуемые в основной задаче `TASK-2026-0048`.

## Контекст

- источник постановки: явная декомпозиция после обсуждения import-first реализации
- связанная бизнес-область: подписки bundle и provider-specific Happ-совместимые расширения
- ограничения и зависимости: зависит от завершения `TASK-2026-0048`; требуется аккуратно не ломать общий импорт узлов для подписок без routing metadata
- основной контекст сессии: `следующий этап после основной задачи`

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | Refresh-процесс подписок извлекает `routing` metadata, `providerId` и синхронизирует auto-managed routing-профиль |
| Конфигурация / схема данных / именуемые сущности | Store получил поля `provider_id`, `provider_id_source`, `routing_profile_id`, `last_routing_status`, `last_routing_error` и атрибуты auto-managed routing-профиля |
| Интерфейсы / формы / страницы | Web UI и native shell показывают источник routing-профиля, связанную подписку, `providerId`, режим `add/onadd`, а также явно отделяют auto-import от ручного fallback и подготовки `GeoIP/GeoSite` |
| Интеграции / обмены | Подписка обрабатывает `routing` header, mixed-body `happ://routing/...`, URL/fragment `providerId` и cleanup при исчезновении metadata |
| Документация | План, карточка подзадачи и реестр синхронизируются с реализованным auto-fetch контуром |

## Связанные материалы

- основной каталог подзадачи: `knowledge/tasks/TASK-2026-0048-routing-profiles-minimal-happ-compat/subtasks/TASK-2026-0048.1-routing-auto-fetch-from-subscription/`
- файл плана: `plan.md`
- родительская задача: `knowledge/tasks/TASK-2026-0048-routing-profiles-minimal-happ-compat/`
- пользовательские материалы: обсуждение `providerId`, `routing` header и mixed-body Happ payload в текущей сессии
- связанные коммиты / PR / ветки: `—`
- связанные операции в `knowledge/operations/`, если есть: `—`

## Текущий этап

Кодовая реализация и review-fix цикл завершены локально: auto-fetch интегрирован в refresh подписок, добавлены регрессионные тесты на mixed-body metadata, `providerId`, cleanup stale auto-managed профиля и повторный refresh.

Осталась ручная provider-specific проверка с живой подпиской, чтобы подтвердить поведение в реальном окружении пользователя без synthetic fixtures.

## Стратегия проверки

### Покрывается кодом или тестами

- `tests.test_subvost_parser`, `tests.test_subvost_routing`, `tests.test_subvost_store`, `tests.test_subvost_app_service`;
- полный `python3 -S -m unittest discover -s tests -p 'test_*.py' -q`;
- статические проверки `python3 -S -m compileall -q gui tests`, `bash -n *.sh`, `bash -n libexec/*.sh`, `bash -n lib/*.sh`, `python3 -S -m json.tool xray-tun-subvost.json`.

### Остаётся на ручную проверку

- реальное обновление подписки провайдера с routing metadata;
- проверка поведения при смене `providerId` и несовместимом payload.

## Критерии готовности

- routing metadata автоматически извлекается из подписки;
- update не ломает обычные подписки без routing-профиля;
- связь routing-профиля с подпиской и provider-контекстом прозрачно видна в store/UI;
- повторный refresh не оставляет stale auto-managed профиль, если routing metadata исчезает.

## Итог

Реализован provider-aware auto-fetch routing-профиля из подписки: refresh теперь извлекает metadata из response header, mixed-body payload и URL/fragment, связывает auto-managed профиль с конкретной подпиской и показывает источник в web UI и native shell, при этом ручной ввод routing-профиля оставлен только как явный fallback.

В ходе review-fix цикла дополнительно закрыты две регрессии: mixed-body parsing перестал ломаться на дополнительных comment/meta строках, а исчезновение routing metadata больше не оставляет stale auto-managed профиль и старую привязку в store.

Локальный verify loop зелёный, но статус остаётся `на проверке`, потому что живой provider-specific refresh в пользовательском окружении пока не подтверждён.
