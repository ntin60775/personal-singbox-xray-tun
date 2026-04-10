# План задачи TASK-2026-0053

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0053` |
| Parent ID | `—` |
| Версия плана | `8` |
| Дата обновления | `2026-04-10` |

## Цель

Зафиксировать рабочий `v1 scope` будущего нативного `GTK4`-клиента для bundle и определить объём реализации так, чтобы новый UI опирался на существующий `xray/TUN` backend-контур, а не дублировал или придумывал несоответствующие проекту возможности.

## Границы

### Входит

- переход от абстрактного концепта к конкретной постановке под текущий репозиторий;
- native `PyGObject + GTK4` UI поверх существующих Python-модулей store/runtime/routing/parser;
- три экрана:
  - `Dashboard`
  - `Subscriptions`
  - `Log`
- системный трей для Linux desktop-сценария bundle;
- обязательные operational-действия:
  - `Старт`
  - `Стоп`
  - `Снять диагностику`
  - выбор активного узла
  - импорт и обновление подписок
  - включение и выключение routing;
- правила UI для ошибок, блокировок и `pkexec`-переходов;
- синхронизация task-контура и записи в реестре задач.

### Не входит

- реализация `WireGuard`, `OpenVPN` или любых альтернативных VPN-backend-ов;
- прямой импорт `Clash/YAML`;
- обогащение узлов географическими метаданными как обязательная зависимость `v1`;
- крупный preferences-модуль с `GSettings`, системным автозапуском, сетевыми переключателями и уведомлениями;
- отказ от текущего web UI без отдельной задачи на миграцию launcher-а и rollout.

## Планируемые изменения

### Архитектура

- не строить нативный UI поверх `HTTP`-роутов текущего `gui_server.py` как над внутренним API;
- выделить общий application/service-слой над существующими Python-модулями, чтобы:
  - web GUI и будущий `GTK4` UI не дублировали бизнес-логику;
  - состояние store/runtime/routing собиралось из одного источника;
  - root-действия продолжали идти через существующие shell-скрипты и `pkexec`;
- сохранить launcher и `embedded_webview` как отдельный fallback-контур до стабилизации native UI.

### Визуальное направление

- базовый референс для dark theme: `Raycast DESIGN.md` с `getdesign.md`;
- использовать логику desktop productivity shell, а не web-dashboard:
  - тёмные плотные поверхности;
  - чёткая иерархия panel / sidebar / action-zone;
  - локальные яркие акценты только на selection, focus и critical runtime state;
  - компактное окно настроек без декоративного шума;
- не тащить в проект `Linear`-подобную фиолетовую SaaS-эстетику и не расползаться в терминальный ретро-стиль по умолчанию;
- `Dashboard`, `Subscriptions` и `Log` могут брать разную плотность контента, но должны оставаться внутри одного `Raycast`-совместимого visual system.

### Системный трей

- добавить Linux-специфичную интеграцию системного трея через совместимый status notifier слой;
- основное меню трея для `v1`:
  - показать окно;
  - `Старт`;
  - `Стоп`;
  - `Снять диагностику`;
  - `Выход`;
- не делать tray обязательной точкой входа: если окружение не даёт рабочий трей, приложение должно продолжать работать как обычное окно без падения;
- отдельно проверить сценарий, при котором закрытие окна убирает приложение в трей, а не завершает его полностью.

### Экран `Dashboard`

- показывать агрегированный статус подключения, а не selector несуществующих протоколов `WireGuard/OpenVPN`;
- отображать:
  - состояние runtime;
  - причину блокировки старта;
  - текущий активный узел;
  - transport/security выбранного узла;
  - ключевые метрики `rx/tx`, uptime, `tun`, DNS;
- дать быстрый доступ к выбору узла:
  - через `Popover` или отдельный selector;
  - без обязательной географии, с fallback на имя узла из подписки;
- разместить основные действия `Старт`, `Стоп`, `Снять диагностику` на первом экране.

### Экран `Subscriptions`

- поддержать:
  - добавление URL-подписки;
  - refresh одной подписки;
  - refresh всех подписок;
  - enable/disable подписки;
  - удаление подписки;
- отобразить связанный список узлов и дать отдельный `ping` без смены активного узла;
- уже в первом UI-каркасе показать routing-секцию как макет, даже если логика ещё не подключена:
  - многострочное поле для вставки `JSON` или `happ://routing/...`;
  - кнопка импорта;
  - список routing-профилей;
  - кнопка включения и выключения routing;
  - блок состояния `GeoIP/Geosite`;
  - кнопка обновления geodata;
- встроить routing-блок в рамках текущих возможностей проекта:
  - импорт `JSON` и `happ://routing/...`;
  - выбор одного активного routing-профиля;
  - включение и выключение routing;
  - явный статус готовности `geoip.dat` и `geosite.dat`;
- не обещать `Clash/YAML`, `GeoLite2` и другие форматы, которых в проекте сейчас нет.

### Фазирование routing UI

- фаза `UI-shell`:
  - routing import и `GeoIP/Geosite` присутствуют в layout уже в первом макете;
  - элементы могут работать через заглушки, disabled-state или demo-status без backend-связки;
  - цель фазы: зафиксировать компоновку и не откладывать routing-блок “на потом”;
- фаза `backend-wire`:
  - привязать импорт routing-профиля к существующим Python-модулям;
  - отобразить реальный статус `geoip.dat` и `geosite.dat`;
  - подключить активацию и обновление geodata к настоящим действиям.

### Экран `Log`

- разделить как минимум два визуальных источника:
  - action log GUI и shell-действий;
  - runtime-логи и файловые логи bundle;
- дать filter по уровню и быстрый способ скопировать или экспортировать содержимое;
- явно показывать последние ошибки backend-а, parser-а и runtime-действий.

### Настройки `v1`

- оставить минимальными и привязанными к тому, что уже есть в проекте;
- допускается только ограниченный набор, например:
  - переключатель файлового логирования;
  - закрытие окна в трей;
  - запуск свёрнутым в трей;
  - тема окна, если она не ломает системный `GTK` look;
- не добавлять в `v1` сетевые настройки, которые пока не имеют устойчивого backend-контракта:
  - `IPv6`;
  - системный или пользовательский `DNS`;
  - системный автозапуск;
- перенос настроек в `GSettings` считать отдельным этапом после рабочего `v1`.

### Документация

- обновить `task.md` под статус активной реализации;
- пересобрать `plan.md` из режима “сохраняем идею” в режим “можно брать в реализацию”;
- синхронизировать `knowledge/tasks/registry.md`.

## Риски и зависимости

- если `GTK4` UI начнёт общаться с runtime через внутренний `HTTP` backend вместо shared Python-слоя, проект получит лишнее дублирование и второй неофициальный контракт;
- root-действия нельзя размазывать по UI: `pkexec` должен остаться только на `Старт`, `Стоп` и `Диагностика`;
- tray на Linux зависит от реального наличия совместимого status notifier в окружении, поэтому нужен аккуратный fallback без деградации основного окна;
- узлы из подписок не всегда содержат страну, город и флаг, поэтому UI должен жить без этих данных;
- geodata может не быть готовой в момент включения routing, а значит UI обязан явно объяснять блокировку;
- если routing UI не заложить в первый каркас, экран `Subscriptions` почти наверняка придётся перекраивать после подключения geodata и routing-профилей;
- слишком раннее переключение launcher-а на native UI без fallback-а создаст регрессию для текущих пользователей bundle.

## Проверки

### Что можно проверить сейчас

- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/task.md knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/plan.md knowledge/tasks/registry.md`

### Что должно быть максимально автоматизировано

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m py_compile gui/subvost_app_service.py gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py gui/embedded_webview.py`
- `python3 -m py_compile gui/native_shell_shared.py gui/native_shell_app.py gui/native_shell_tray_helper.py`
- релевантные `python3 -m unittest` для parser/store/runtime/routing, `subvost_app_service` и новых native-модулей;
- D-Bus/X11 smoke для native shell в живой графической сессии, если сценарий воспроизводим без ручного визуального решения;
- любое новое backend/frontend поведение сначала пытаться закрепить автоматической проверкой, а в финальный ручной список оставлять только то, что реально зависит от целостной desktop/runtime-интеграции.

### Финальный ручной smoke вне рамок закрытия этой задачи

Изначально `TASK-2026-0053` закрывалась без обязательного rollout-smoke. Позднее, `2026-04-10`, архивный ручной GTK smoke всё же был проведён на живом display и зафиксировал UX-дефекты, которые теперь восстановлены как отдельная подзадача `TASK-2026-0053.6`.

Список ниже остаётся reference-контуром для отдельной задачи по rollout native UI; при этом конкретные замечания архивного smoke уже не висят без владельца и вынесены в `TASK-2026-0053.6`.

- запуск native GUI из проектного launcher-а без раннего `pkexec`;
- появление иконки и меню трея в поддерживаемом окружении;
- сценарии `show/hide`, `start minimized to tray` и `close-to-tray` через реальное tray-меню и пользовательский launcher;
- импорт URL-подписки, refresh одной и всех подписок, enable/disable и удаление;
- выбор активного узла и `ping` без смены активного узла;
- routing import и `GeoIP/Geosite` блоки видны уже в первом UI-макете и корректно работают после backend-подключения;
- `Старт` поднимает runtime, создаёт `tun0` и обновляет статус/метрики;
- `Снять диагностику` создаёт dump;
- `Стоп` останавливает runtime и восстанавливает DNS;
- негативные сценарии показывают понятные причины блокировки: нет активного узла, нет geodata, конфликт ownership с чужим runtime.

### Что уже подтверждено в рамках `TASK-2026-0053.1`

- `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py gui/native_shell_shared.py gui/native_shell_app.py gui/native_shell_tray_helper.py`
- `python3 -m unittest tests.test_native_shell_shared tests.test_native_shell_app tests.test_subvost_store`
- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- runtime-smoke `GTK4` shell без трея в реальной графической сессии: окно стартует видимым, `TrayAvailable=false`, ранний `pkexec` отсутствует, fallback для сохранённых tray-настроек корректен;
- runtime-smoke `GTK4` shell с tray-helper в реальной графической сессии: `TrayAvailable=true`, backend `Ayatana AppIndicator`, скрытый старт по `start_minimized_to_tray`, команды `ShowWindow` и `OpenSettings` через D-Bus control interface, `close-to-tray` через менеджер окон без завершения приложения;
- probe текущей Linux-сессии подтвердил `org.kde.StatusNotifierWatcher` и backend `Ayatana AppIndicator`.

### Что уже подтверждено в рамках `TASK-2026-0053.2`

- `python3 -m unittest tests.test_subvost_app_service tests.test_native_shell_app tests.test_gui_server tests.test_native_shell_shared`
- `python3 -m py_compile gui/subvost_app_service.py gui/gui_server.py gui/native_shell_app.py gui/native_shell_shared.py`
- общий `subvost_app_service.py` собирает status/runtime orchestration, ownership guard, action log, traffic и `pkexec`-операции без `HTTP`-зависимости native shell;
- `gui_server.py` продолжает отдавать совместимый `HTTP` payload и сохранил patchable handler-контракт для unit-тестов;
- `Dashboard` в native shell больше не работает как `stub`: кнопки окна и tray проходят через общий service-layer, а экран показывает runtime state, transport/security, ownership и метрики.

### Что уже подтверждено в рамках `TASK-2026-0053.3`

- `python3 -m unittest tests.test_subvost_app_service tests.test_native_shell_app tests.test_gui_server tests.test_native_shell_shared`
- `python3 -m py_compile gui/subvost_app_service.py gui/gui_server.py gui/native_shell_app.py gui/native_shell_shared.py`
- общий `subvost_app_service.py` теперь собирает не только runtime/status orchestration, но и store/routing snapshot и mutation-операции для подписок, узлов, `ping` и routing-профилей;
- `gui_server.py` переведён на thin-wrapper store/routing handlers поверх service-layer и сохранил совместимый `/api/store` и action-response shape;
- `Subscriptions` в native shell больше не является placeholder: экран работает с URL-подписками, выбором узла, отдельным `Ping`, routing import и статусом `GeoIP/Geosite` без внутренних `HTTP` вызовов.

### Что уже подтверждено в рамках `TASK-2026-0053.4`

- `python3 -m unittest tests.test_native_shell_shared tests.test_native_shell_app tests.test_subvost_app_service tests.test_gui_server`
- `python3 -m py_compile gui/native_shell_shared.py gui/native_shell_app.py gui/subvost_app_service.py gui/gui_server.py`
- `gui/native_shell_shared.py` теперь собирает headless helper-слой для фильтрации логов, выбора последней ошибки и экспортного текста;
- `gui/native_shell_app.py` хранит shell-журнал структурированно и показывает рабочий `Log` с источниками `native shell` и `bundle/runtime`, фильтром по уровню и действиями `Скопировать`/`Экспорт`;
- повторный прогон service-layer и web-backend тестов подтвердил, что этап `Log` не сломал контур `TASK-2026-0053.3`.

### Что уже подтверждено в рамках `TASK-2026-0053.5`

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `python3 -m py_compile gui/native_shell_app.py`
- появился отдельный launcher `open-subvost-gtk-ui.sh` и отдельный installer `install-subvost-gtk-ui-menu-entry.sh` для ручного запуска native shell;
- основной web launcher проекта не менялся и остаётся fallback/дефолтным пользовательским путём до отдельного rollout-решения.

### Что зафиксировано архивным ручным smoke от `2026-04-10`

- на экране `2560x1440` shell открылся с geometry `2892x1999+-12+-12`, а `WM_NORMAL_HINTS` тоже объявлял minimum size `2892x1999`;
- попытка уменьшить окно до `1400x980` не изменила geometry, поэтому `resize` был признан фактически неработающим;
- архивное review дополнительно подтвердило светлый `StackSidebar`, повторяющиеся `GtkBox ... natural size must be >= min size` и отдельное продолжение по visual/UX-правкам;
- восстановленный владелец этих замечаний: `TASK-2026-0053.6`.

## Шаги

- [x] Сверить пользовательский концепт с текущим `xray/TUN` bundle и фактическими backend-возможностями
- [x] Перевести `TASK-2026-0053` из абстрактного черновика в рабочую постановку
- [x] Синхронизировать реестр задач под новый статус и описание
- [x] Выделить общий application/service-слой для будущего native UI
- [x] Собрать каркас нативного окна `GTK4` с навигацией `Dashboard / Subscriptions / Log`
- [x] Реализовать системный трей и сценарии show-hide окна без раннего `pkexec`
- [x] Реализовать `Dashboard` с runtime-статусом, текущим узлом, метриками и действиями `Старт / Стоп / Диагностика`
- [x] Заложить в `Subscriptions` routing import и `GeoIP/Geosite` блоки уже на уровне UI-макета, даже если backend ещё не подключён
- [x] Реализовать `Subscriptions` с подписками, узлами, `ping` и routing-профилями
- [x] Реализовать `Log` с фильтрацией и экспортом
- [x] Реализовать минимальное окно настроек для `v1`
- [x] Зафиксировать закрытие задачи без финального manual smoke: этап признан пройденным, а решение о переключении launcher-а вынесено за рамки этой задачи по решению пользователя

## Критерии завершения

- task-контур больше не является “заготовкой на потом”, а задаёт конкретный `v1 scope` и ограничения для реализации;
- будущая реализация может стартовать без повторного пересогласования базовых сущностей UI;
- в постановке нет фиктивных функций, которых нет в текущем backend-контуре проекта;
- `Subscriptions` уже закрыт как рабочий vertical slice поверх общего service-layer, а не как отдельный mockup-контур;
- системный трей и минимальные настройки описаны как реальные части `v1`, а не как расплывчатые пожелания;
- локализационная проверка Markdown проходит успешно.
