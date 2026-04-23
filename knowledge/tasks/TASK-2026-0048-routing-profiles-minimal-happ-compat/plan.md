# План задачи TASK-2026-0048

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0048` |
| Parent ID | `—` |
| Версия плана | `2` |
| Дата обновления | `2026-04-23` |

## Цель

Реализовать минимально достаточный routing-контур по модели Happ: импорт профиля, один активный профиль, глобальный toggle маршрутизации, обязательная geodata и применение правил в `Xray`-runtime.

## Границы

### Входит

- import-first поддержка routing-профилей;
- geodata download/cache и интеграция с `Xray`;
- backend API и web UI для просмотра и переключения routing-профилей;
- tolerant parsing mixed subscription payload, если там есть `happ://routing/...`;
- оформление и реализация отдельной подзадачи на auto-fetch из subscription metadata.

### Не входит

- редактирование профилей вручную;
- удаление routing-профилей;
- применение DNS-части профиля в текущем runtime.

## Планируемые изменения

### Код

- добавить отдельный модуль routing-парсинга, normalizer, geodata manager и builder overlay для `Xray`;
- расширить `subvost_store` новой секцией `routing`, логикой импорта и переключения профилей;
- расширить `subvost_runtime`, `gui_server`, `main_gui.html` и shell runtime для geodata, routing status, явного manual fallback и отдельного действия подготовки `GeoIP/GeoSite`;
- сделать tolerant parsing mixed subscription payload и реализовать follow-up `TASK-2026-0048.1` для auto-fetch по `routing` metadata и `providerId`.

### Конфигурация / схема данных / именуемые сущности

- повысить версию store и добавить `routing.enabled`, `routing.active_profile_id`, `routing.profiles`, `routing.runtime_ready`, `routing.geodata`;
- добавить provider-aware поля связи подписка ↔ auto-managed routing-профиль;
- добавить пути к `geoip.dat` и `geosite.dat` в user config-home;
- подключить `XRAY_LOCATION_ASSET` к запуску и валидации `Xray`.

### Документация

- создать `task.md` и `plan.md` основной задачи;
- создать подзадачу `TASK-2026-0048.1` как следующий этап auto-fetch;
- обновить `knowledge/tasks/registry.md`.

## Риски и зависимости

- без geodata routing с `geosite:` и `geoip:` должен считаться неготовым и блокировать следующий старт;
- импорт routing-профиля должен быть совместим и с JSON, и с `happ://routing/...`, иначе пользовательский workflow будет лишне хрупким;
- маршрутный overlay нельзя строить поверх template правил так, чтобы сломать обязательные internal-исключения bundle;
- ручной smoke c `pkexec`, `tun0` и сетевым трафиком остаётся обязательным после кодовой реализации.

## Проверки

### Что можно проверить кодом или тестами

- `python3 -m unittest tests.test_subvost_parser tests.test_subvost_runtime tests.test_subvost_store tests.test_gui_server`
- `python3 -S -m unittest tests.test_subvost_parser tests.test_subvost_routing tests.test_subvost_store tests.test_subvost_app_service tests.test_gui_server -q`
- `python3 -S -m unittest discover -s tests -p 'test_*.py' -q`
- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -S -m compileall -q gui tests`
- `python3 -S -m json.tool xray-tun-subvost.json`

### Что остаётся на ручную проверку

- импорт routing-профиля через GUI;
- `Старт` / `Стоп` при включённой маршрутизации и готовой geodata;
- проверка фактической маршрутизации трафика в целевой Linux-среде.

## Шаги

- [x] Открыть task-контур и подзадачу auto-fetch
- [x] Добавить routing parser, normalizer и geodata manager
- [x] Расширить store/runtime и shell runtime
- [x] Добавить backend API и web UI
- [x] Обновить тесты и прогнать проверки
- [x] Реализовать и отревьюить `TASK-2026-0048.1` с auto-fetch и cleanup stale metadata state

## Критерии завершения

- основной import-first сценарий работает end-to-end;
- routing не ломает текущий выбор активного узла и старт bundle без него;
- auto-fetch реализован отдельной подзадачей `TASK-2026-0048.1` и не ломает import-first слой;
- все knowledge-артефакты и статические проверки синхронизированы.

## Итог

Umbrella-реализация завершена до статуса `на проверке`: import-first routing-контур дополнен реализованной подзадачей `TASK-2026-0048.1`, которая автоматически подтягивает routing metadata из подписки, связывает auto-managed профиль с `providerId`, очищает stale state при исчезновении metadata и отделяет auto-import UX от ручного fallback с явной подготовкой `GeoIP/GeoSite`.

Тестовый контур расширен unit/API-проверками parser/store/backend, дополнительными регрессиями на mixed-body comments и повторный refresh без metadata, а полный `unittest discover` прошёл без ошибок.

Отдельно остаётся ручная production-проверка с реальным `pkexec`, `tun0` и фактическим трафиком.
