# Карточка задачи TASK-2026-0048

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0048` |
| Parent ID | `—` |
| Уровень вложенности | `0` |
| Ключ в путях | `TASK-2026-0048` |
| Технический ключ для новых именуемых сущностей | `routing-profiles` |
| Краткое имя | `routing-profiles-minimal-happ-compat` |
| Статус | `на проверке` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `main` |
| Дата создания | `2026-04-08` |
| Дата обновления | `2026-04-23` |

## Цель

Добавить в bundle упрощённый, но рабочий контур routing-профилей по модели Happ: пользователь должен видеть импортированные профили, включать или отключать конкретный профиль, отдельно включать или выключать маршрутизацию в целом и запускать runtime с применением одного активного routing-профиля.

Ожидаемый результат: bundle умеет импортировать routing-профиль из JSON или `happ://routing/...`, хранить несколько профилей, поддерживать обязательные `geosite.dat` и `geoip.dat`, строить `Xray`-routing overlay для активного узла и показывать состояние маршрутизации в GUI без ручного редактирования правил.

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

- импорт routing-профиля из экспортированного Happ-совместимого JSON или `happ://routing/...`;
- хранение нескольких routing-профилей, одного активного профиля и отдельного master toggle маршрутизации;
- загрузка и кеширование `geoip.dat` и `geosite.dat` для активного профиля;
- генерация `routing`-overlay поверх `xray-tun-subvost.json`;
- backend API и web UI для просмотра, импорта и переключения routing-профилей;
- tolerant parsing подписок, если в payload встречается строка `happ://routing/...`;
- отдельная подзадача `TASK-2026-0048.1` с auto-fetch routing-профиля из subscription metadata, `providerId` и refresh-синхронизацией.

### Не входит

- редактирование routing-правил вручную в GUI;
- удаление routing-профилей, объединение нескольких профилей или их merge;
- применение DNS-части routing-профиля в runtime этой задачи.

## Контекст

- источник постановки: запрос пользователя добавить функционал маршрутизации как в Happ, но упрощённо
- связанная бизнес-область: portable `Xray TUN` bundle с подписками, активным узлом и локальным GUI
- ограничения и зависимости: в `Xray`-runtime должен применяться только один routing-профиль; geodata обязательна; DNS-поля профиля пока только сохраняются и отображаются
- основной контекст сессии: `текущая задача`

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | Реализованы parser/store/runtime/GUI-сценарии для import-first routing и provider-aware auto-fetch из подписок |
| Конфигурация / схема данных / именуемые сущности | Store получил секцию `routing`, geodata-state и поля auto-managed subscription↔routing связи |
| Интерфейсы / формы / страницы | Web UI и native shell показывают состояние профиля, источник, связанную подписку, `providerId` и режим `add/onadd` |
| Интеграции / обмены | Runtime использует `geosite` и `geoip` через `XRAY_LOCATION_ASSET`, а refresh подписок читает `routing` metadata и cleanup stale state |
| Документация | Knowledge-контур задачи и подзадачи синхронизирован с реализованным umbrella-результатом |

## Связанные материалы

- основной каталог задачи: `knowledge/tasks/TASK-2026-0048-routing-profiles-minimal-happ-compat/`
- файл плана: `plan.md`
- подзадача следующего этапа: `subtasks/TASK-2026-0048.1-routing-auto-fetch-from-subscription/`
- пользовательские материалы: пример `happ://routing/add/...` из текущей подписки в этой сессии
- связанные коммиты / PR / ветки: `—`
- связанные операции в `knowledge/operations/`, если есть: `—`

## Текущий этап

Import-first контур и отдельная подзадача auto-fetch реализованы, review-fix цикл завершён, локальные автопроверки зелёные. Остался ручной smoke production/runtime-сценария с реальным `pkexec`, `tun0`, фактической маршрутизацией трафика и живой provider-specific подпиской.

## Стратегия проверки

### Покрывается кодом или тестами

- unit-проверки импорта routing-профилей, `happ://routing/...` и tolerant parsing подписок;
- unit-проверки генерации `Xray`-routing overlay и geodata readiness;
- unit/API-проверки store и GUI backend для import/activate/toggle и auto-fetch сценариев;
- полный `python3 -S -m unittest discover -s tests -p 'test_*.py' -q`;
- статические проверки shell и Python.

### Остаётся на ручную проверку

- импорт routing-профиля через GUI;
- включение и выключение маршрутизации на реальном bundle;
- запуск `Старт` / `Стоп` с geodata в целевой Linux-среде и фактический `tun0` smoke.

## Критерии готовности

- routing-профиль можно импортировать без auto-fetch подписки;
- в store поддерживаются несколько routing-профилей, один активный профиль и отдельный master toggle;
- generated `Xray` config умеет применять routing overlay с `geosite` и `geoip`;
- GUI показывает состояние routing-профилей, geodata и позволяет переключать профиль и master toggle;
- auto-fetch из подписки реализован отдельной подзадачей `TASK-2026-0048.1` и не регрессирует import-first контур;
- все изменённые Markdown-файлы проходят localization guard.

## Итог

Реализован umbrella-контур Happ-совместимой маршрутизации: bundle принимает routing-профиль как JSON или `happ://routing/...`, хранит несколько профилей в store, поддерживает один активный профиль и отдельный master toggle маршрутизации, а также автоматически подтягивает routing metadata из подписки через подзадачу `TASK-2026-0048.1`.

Добавлены обязательные `geoip.dat` и `geosite.dat` в user config-home, их atomic download/cache, прокидывание `XRAY_LOCATION_ASSET` в `run-xray-tun-subvost.sh` и генерация `Xray` routing overlay поверх базового шаблона с сохранением внутренних правил bundle.

Backend, web UI и native shell расширены блоком маршрутизации и индикацией источника auto-managed профиля: import профиля, просмотр списка профилей, выбор активного профиля, master toggle, `providerId`, связанная подписка, режим `add/onadd`, tolerant parsing mixed payload и cleanup stale routing state при исчезновении metadata.

Пройдены проверки: `bash -n *.sh`, `bash -n libexec/*.sh`, `bash -n lib/*.sh`, `python3 -S -m compileall -q gui tests`, `python3 -S -m json.tool xray-tun-subvost.json`, `python3 -S -m unittest tests.test_subvost_parser tests.test_subvost_routing tests.test_subvost_store tests.test_subvost_app_service tests.test_gui_server -q`, `python3 -S -m unittest discover -s tests -p 'test_*.py' -q`.

Остаточный риск: manual smoke с реальным стартом, `pkexec`, `tun0`, `Xray`-runtime и фактической маршрутизацией трафика в этой сессии не выполнялся.
