# Карточка задачи TASK-2026-0053

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0053` |
| Parent ID | `—` |
| Уровень вложенности | `0` |
| Ключ в путях | `TASK-2026-0053` |
| Технический ключ для новых именуемых сущностей | `gtk4-native-ui` |
| Краткое имя | `gtk4-native-ui-spike` |
| Статус | `завершена` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `topic/gtk4-native-ui-spike` |
| Дата создания | `2026-04-08` |
| Дата обновления | `2026-04-10` |

## Цель

Подготовить рабочую постановку для отдельного нативного `GTK4`-интерфейса bundle, который сможет заменить текущий web UI как основной desktop-слой без смены runtime-модели `xray-core + TUN`.

## Границы

### Входит

- нативный UI на `PyGObject + GTK4` без `HTML/WebKit` как основного presentation-слоя;
- три экрана `Dashboard / Subscriptions / Log` с явной навигацией внутри окна;
- системный трей с базовыми действиями:
  - показать и скрыть окно;
  - `Старт`;
  - `Стоп`;
  - `Снять диагностику`;
  - `Выход`;
- переиспользование существующих Python-модулей `subvost_store.py`, `subvost_runtime.py`, `subvost_routing.py`, `subvost_parser.py` и существующих shell entrypoint-ов bundle;
- запуск действий `Старт`, `Стоп` и `Снять диагностику` через те же shell-скрипты и `pkexec`, без раннего root-запроса при открытии окна;
- минимальное окно настроек с параметрами, которые действительно имеют смысл для `v1`:
  - файловое логирование;
  - поведение окна при закрытии в связке с треем;
  - запуск свёрнутым в трей;
  - тема окна, если она не ломает системный `GTK` look;
- UI-макет routing-части уже в первом native-прототипе:
  - поле импорта `JSON` и `happ://routing/...`;
  - список routing-профилей;
  - блок состояния `GeoIP/Geosite`;
  - кнопки импорта, активации и обновления geodata как элементы интерфейса, даже если в первой итерации они ещё не подключены к backend-логике;
- привязка UI к текущей модели данных проекта:
  - активная подписка и активный узел;
  - импорт URL-подписок;
  - routing-профили в формате `JSON` и `happ://routing/...`;
  - состояние `geoip.dat` и `geosite.dat`;
  - action log, runtime log, статус `tun0`, DNS и connection uptime;
- требования к типографике:
  - основной UI: `Inter` с системными `sans-serif` fallback;
  - лог: `MesloLGS NF`, `FiraCode` или системный `monospace`;
- явные UX-состояния для ошибок и блокировок старта:
  - нет активного узла;
  - routing включён, но runtime не готов;
  - нет geodata;
  - runtime уже поднят чужим bundle;
  - backend или shell-действие завершились ошибкой.

### Не входит

- поддержка `WireGuard`, `OpenVPN` или selector-а между несколькими VPN-движками;
- прямой импорт `Clash/YAML`, если не будет отдельной задачи на расширение parser-а;
- обязательное обогащение узлов метаданными страны, города и флага, если провайдер не даёт их в явном виде;
- `GSettings`, `gschema`, `GNotification`, hotkeys, автозапуск в систему, DNS/IPv6-переключатели и большой preferences-экран;
- удаление текущего web UI до тех пор, пока нативный клиент не пройдёт ручной smoke и не получит отдельное решение по миграции launcher-а.

## Контекст

- репозиторий уже работает как portable bundle для `xray-core` в `TUN`-режиме и не является `WireGuard/OpenVPN`-клиентом;
- текущий GUI живёт в `gui/main_gui.html` и `gui/gui_server.py`, но бизнес-логика уже вынесена в отдельные Python-модули, пригодные для повторного использования;
- старт bundle зависит от выбранного узла и сгенерированного runtime-конфига, а не от ручного редактирования tracked-шаблона;
- routing уже поддерживает импорт `JSON` и `happ://routing/...`, подготовку `geoip.dat` и `geosite.dat`, а также включение и выключение overlay-профиля;
- системный трей полезен для desktop-сценария bundle, но должен быть описан как Linux-специфичная интеграция с аккуратным fallback-поведением в средах без рабочего status notifier;
- пользовательский концепт переработан под реальные ограничения проекта, чтобы исключить фиктивные сущности и несуществующие backend-возможности.
- по дополнительному требованию пользователя routing import и geodata должны быть заложены в UI с самого начала хотя бы как макет, чтобы не пришлось перепроектировать экран после появления backend-связки.
- визуальный референс для текущего этапа выбран явно: `Raycast DESIGN.md` с `getdesign.md`, как источник dark desktop-shell направления для окна, поверхностей, акцентных состояний и минималистичных настроек.

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | Собраны общий runtime/service-layer и все три рабочих native-экрана: `Dashboard`, `Subscriptions`, `Log` |
| Документация | Базовая идея переведена в рабочую постановку с `v1 scope`, ограничениями и критериями приёмки |
| Архитектура будущей реализации | Зафиксирован native `GTK4` путь поверх существующего Python backend-контракта и уже закрыты shell/tray, service-layer, `Dashboard`, `Subscriptions` и `Log` этапы |
| UX-контракт | Уточнены реальные сущности UI: `xray/TUN`, подписки, узлы, routing, `pkexec`-действия, диагностика |
| Визуальный контракт | Базовый dark reference закреплён за `Raycast` с адаптацией под desktop utility, а не под web-dashboard |

## Связанные материалы

- основной каталог задачи: `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/`
- файл плана: `plan.md`
- связанная историческая задача: `knowledge/tasks/TASK-2026-0022-native-ui-gtk-direction/`
- первая реализованная подзадача: `subtasks/TASK-2026-0053.1-gtk4-shell-tray-and-settings-shell/`
- вторая реализованная подзадача: `subtasks/TASK-2026-0053.2-dashboard-and-shared-service-layer/`
- третья реализованная подзадача: `subtasks/TASK-2026-0053.3-subscriptions-vertical-slice/`
- четвёртая реализованная подзадача: `subtasks/TASK-2026-0053.4-log-vertical-slice/`
- пятая реализованная подзадача: `subtasks/TASK-2026-0053.5-gtk-test-launcher/`
- visual-contract подзадача: `subtasks/TASK-2026-0053.1-gtk4-shell-tray-and-settings-shell/subtasks/TASK-2026-0053.1.1-raycast-dark-ui-contract/`
- текущий runtime-контур: `README.md`
- текущий web GUI backend: `gui/gui_server.py`
- текущая логика store и routing: `gui/subvost_store.py`, `gui/subvost_routing.py`, `gui/subvost_runtime.py`, `gui/subvost_parser.py`
- общий runtime/service-layer: `gui/subvost_app_service.py`
- первый native-shell код: `gui/native_shell_app.py`, `gui/native_shell_shared.py`, `gui/native_shell_tray_helper.py`
- выбранный visual reference: `https://getdesign.md/raycast/design-md`

## Текущий этап

Задача закрыта как уже пройденный этап. Функциональная реализация `TASK-2026-0053` собрана: после `TASK-2026-0053.4` с готовым `Log` подзадача `TASK-2026-0053.5` добавила отдельный launcher для ручного тестирования `GTK4` native UI. Нативный клиент покрывает `Dashboard`, `Subscriptions` и `Log` без внутренних `HTTP` вызовов, но финальный manual smoke и решение о переводе launcher-а на native UI по умолчанию в рамках этой задачи не выполнялись и не фиксировались.

## Стратегия проверки

### Покрывается кодом или тестами

- для текущего обновления task-контура:
  - локализационная проверка Markdown через `markdown-localization-guard`;
- для будущей реализации:
  - `bash -n *.sh`
  - `bash -n libexec/*.sh`
  - `bash -n lib/*.sh`
  - `python3 -m py_compile gui/subvost_app_service.py`
  - `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_routing.py gui/subvost_parser.py`
  - `python3 -m py_compile gui/native_shell_shared.py gui/native_shell_app.py gui/native_shell_tray_helper.py`
  - актуальный набор `python3 -m unittest` по Python-логике store/runtime/parser/routing, service-layer и native-shell модулей;
  - все backend/frontend сценарии, которые воспроизводимы без визуального решения пользователя, сначала переводить в автоматические `unittest`, syntax-check, `py_compile` или D-Bus/X11 smoke, а не оставлять ручными по умолчанию.

### Остаётся на ручную проверку

Дополнительных обязательных ручных проверок по этой задаче не осталось: по решению пользователя `TASK-2026-0053` закрыта без финального manual smoke.

Если потребуется практический rollout native UI или решение о переводе launcher-а по умолчанию, это нужно открывать отдельной задачей и уже там проходить живой desktop/runtime smoke.

## Критерии готовности

- нативный `GTK4` клиент не вводит фиктивных сущностей вроде `WireGuard/OpenVPN`, а работает поверх текущей модели `xray-core + TUN`;
- `Dashboard`, `Subscriptions` и `Log` покрывают основной operational flow bundle без необходимости возвращаться в web UI для базовых действий;
- системный трей даёт быстрый доступ к окну и базовым runtime-действиям без раннего `pkexec`;
- старт, остановка и диагностика сохраняют текущую `pkexec`-границу: root-запрос только на runtime-действиях, а не при открытии окна;
- окно настроек в `v1` остаётся компактным и содержит только реально поддерживаемые параметры, без фиктивных сетевых переключателей;
- `Subscriptions` уже покрывает URL-подписки, выбор узла, отдельный `ping`, routing import и явный статус `GeoIP/Geosite`;
- routing в UI опирается на уже существующие `JSON` и `happ://routing/...` профили и явно показывает готовность `geoip.dat`/`geosite.dat` без второго backend-контракта;
- текущий web UI может оставаться fallback-слоем до отдельного решения по переключению основного GUI.

## Итог

`TASK-2026-0053` закрыта как завершённый и уже пройденный этап развития проекта. В её рамках зафиксированы рабочая постановка native `GTK4` направления, общий `service-layer`, отдельные экраны `Dashboard / Subscriptions / Log`, системный tray-контур, минимальные настройки `v1` и отдельный launcher для ручного тестирования native shell без смены основного GUI по умолчанию.

Финальный manual smoke и решение о переводе launcher-а на native UI по умолчанию в этой задаче не выполнялись: по решению пользователя knowledge-контур закрыт без них. Остаточный риск остаётся прежним: если понадобится реальный rollout native UI, потребуется отдельная задача с живой desktop/runtime-проверкой и отдельным решением по launcher migration.
