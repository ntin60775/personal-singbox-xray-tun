# План задачи TASK-2026-0048.1

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0048.1` |
| Parent ID | `TASK-2026-0048` |
| Версия плана | `2` |
| Дата обновления | `2026-04-23` |

## Цель

Добавить автоматическое извлечение и обновление routing-профиля из подписки после завершения import-first контура основной задачи.

## Границы

### Входит

- разбор `routing` header;
- разбор mixed subscription body с `happ://routing/...`;
- поддержка `providerId` и привязка routing-профиля к подписке;
- безопасное обновление routing-профиля при `refresh`.

### Не входит

- ручной импорт routing-профиля;
- базовая geodata и routing overlay;
- редактирование профилей вручную.

## Планируемые изменения

### Код

- расширить refresh подписок так, чтобы он извлекал routing metadata отдельно от списка узлов;
- добавить provider-aware хранение связи подписка ↔ routing-профиль;
- определить правила merge/replace при обновлении routing-профиля из того же provider/source;
- удалить stale auto-managed routing-профиль и связанный state, если metadata на следующем refresh исчезает.

### Конфигурация / схема данных / именуемые сущности

- добавить в store `provider_id`, `provider_id_source`, `routing_profile_id`, `last_routing_status`, `last_routing_error`, `source_subscription_id`, `auto_managed`, `source_kind`, `activation_mode`;
- зафиксировать явный статус auto-managed routing-профиля.

### Документация

- синхронизировать карточку, план и реестр после review-fix интеграции подзадачи, включая UI-контракт auto-import против ручного fallback.

## Риски и зависимости

- формат routing metadata может отличаться по провайдерам;
- нельзя ломать совместимость подписок, которые не отдают routing metadata вообще;
- обновление auto-managed routing-профиля не должно тихо затирать ручные профили пользователя.

## Проверки

### Что можно проверить кодом или тестами

- `python3 -S -m unittest tests.test_subvost_parser tests.test_subvost_routing tests.test_subvost_store tests.test_subvost_app_service -q`;
- `python3 -S -m unittest discover -s tests -p 'test_*.py' -q`;
- `python3 -S -m compileall -q gui tests`;
- `bash -n *.sh`, `bash -n libexec/*.sh`, `bash -n lib/*.sh`;
- `python3 -S -m json.tool xray-tun-subvost.json`.

### Что остаётся на ручную проверку

- живой provider-specific refresh в реальном окружении пользователя.

## Шаги

- [x] Зафиксировать scope подзадачи и вывести её из основной реализации
- [x] Добавить parsing routing metadata при refresh подписок
- [x] Связать routing-профиль с subscription/provider
- [x] Проверить поведение при повторном refresh и конфликтных данных
- [x] Закрыть review-fix регрессии по mixed-body comments и stale auto-managed routing state

## Критерии завершения

- auto-fetch работает только как отдельное расширение поверх основной import-first реализации;
- обычные подписки и ручной импорт не регрессируют;
- store и UI прозрачно отражают источник auto-managed routing-профиля.

## Итог

Подзадача реализована и отревьюена локально: refresh подписок извлекает `routing` metadata из header/body, поднимает `providerId`, создаёт или обновляет auto-managed routing-профиль, учитывает `add/onadd` и удаляет stale routing state, если metadata исчезает.

Автотесты и статические проверки пройдены, но финальный статус остаётся `на проверке`, потому что живой provider-specific refresh ещё не подтверждён в пользовательском окружении.
