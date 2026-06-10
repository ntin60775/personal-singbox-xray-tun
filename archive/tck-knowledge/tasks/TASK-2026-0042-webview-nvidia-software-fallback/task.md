# Карточка задачи TASK-2026-0042

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0042` |
| Parent ID | `—` |
| Уровень вложенности | `0` |
| Ключ в путях | `TASK-2026-0042` |
| Технический ключ для новых именуемых сущностей | `—` |
| Краткое имя | `webview-nvidia-software-fallback` |
| Человекочитаемое описание | `Аппаратно-независимый software-rendering fallback для embedded webview вместо хрупкого GPU/GBM-пути` |
| Статус | `на проверке` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `main` |
| Дата создания | `2026-04-06` |
| Дата обновления | `2026-04-28` |

## Цель

Убрать белый экран встроенного `GTK/WebKitGTK` окна и сделать запуск встроенного GUI аппаратно-независимым, сохранив текущий backend и браузерный fallback.

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

- диагностика белого экрана при запуске через `subvost-xray-tun.desktop`;
- аппаратно-независимый software-rendering fallback для `embedded_webview`;
- минимальные проверки launcher-а и Python-кода;
- синхронизация task-артефактов и реестра.

### Не входит

- переписывание web UI;
- замена `WebKitGTK` на другой desktop-стек;
- сетевые и runtime-правки `xray`.

## Контекст

- источник постановки: пользователь видит белый экран вместо приложения при запуске `subvost-xray-tun.desktop`;
- связанная бизнес-область: desktop launcher и встроенное окно GUI;
- ограничения и зависимости: на другом ПК с той же ОС и `Ryzen 5500U` проблема не воспроизводится; на текущей машине логи показывают `GeForce GT 730 [10de:1287]` и ошибки `DRM_IOCTL_MODE_CREATE_DUMB failed` / `Failed to create GBM buffer`, поэтому нужен не vendor-specific обход, а общий стабильный путь рендера;
- основной контекст сессии: `текущая задача`.

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | Меняются `gui/embedded_webview.py`, `libexec/open-subvost-gui.sh` и тесты launcher-а |
| Конфигурация / схема данных / именуемые сущности | Добавляется предсказуемый software-rendering режим для встроенного окна |
| Интерфейсы / формы / страницы | UI как пользовательский экран не меняется, меняется только способ его отрисовки |
| Интеграции / обмены | Сохраняется текущий локальный HTTP backend на `127.0.0.1:8421` |
| Документация | Добавляются task-артефакты и запись в `knowledge/tasks/registry.md` |

## Связанные материалы

- основной каталог задачи: `knowledge/tasks/TASK-2026-0042-webview-nvidia-software-fallback/`
- файл плана: `plan.md`
- пользовательские материалы: текущий запрос и дополнительная ремарка про другой ПК на `Ryzen 5500U`
- связанные коммиты / PR / ветки: `—`
- связанные операции в `knowledge/operations/`, если есть: `—`
- смежный контекст: `knowledge/tasks/TASK-2026-0038-embedded-webview-launcher/`

## Текущий этап

Кодовый фикс реализован и локально проверен; задача находится на ручной проверке запуска через `subvost-xray-tun.desktop` на проблемной машине.

## Стратегия проверки

### Покрывается кодом или тестами

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py gui/embedded_webview.py`
- `python3 -m unittest tests.test_gui_server tests.test_embedded_webview`

### Остаётся на ручную проверку

- живой запуск `subvost-xray-tun.desktop` на проблемной машине с проверкой, что вместо белого экрана открывается рабочее окно;
- при необходимости проверка browser fallback отдельно.

## Критерии готовности

- launcher по умолчанию использует аппаратно-независимый стабильный путь рендера вместо хрупкой привязки к конкретному GPU-стеку;
- встроенное окно остаётся работоспособным на машинах, где раньше всё уже работало;
- изменения подтверждены статическими проверками и релевантными unit-тестами;
- task-артефакты и реестр синхронизированы.

## Итог

Реализован двойной аппаратно-независимый fallback для встроенного окна. В `libexec/open-subvost-gui.sh` launcher теперь по умолчанию передаёт `WEBKIT_DISABLE_DMABUF_RENDERER=1`, `WEBKIT_DMABUF_RENDERER_FORCE_SHM=1`, `WEBKIT_WEBGL_DISABLE_GBM=1` и `WEBKIT_SKIA_ENABLE_CPU_RENDERING=1`, но не перетирает пользовательские override-значения. Это переводит `WebKitGTK` в более стабильный CPU/SHM-путь без жёсткой привязки к `NVIDIA`, `AMD` или `Intel`.

В `gui/embedded_webview.py` добавлен второй слой защиты: перед запуском применяется тот же набор software-rendering defaults, а для уже созданного `WebView` через `WebKit.Settings` отключаются `WebGL`, ускорение `2d canvas` и выставляется `hardware-acceleration-policy=NEVER`, если эта настройка поддерживается конкретным namespace. Такой путь одинаково применим к `Gtk4 + WebKitGTK 6.0` и `Gtk3 + WebKitGTK 4.1/4.0`, поэтому фикс ориентирован именно на аппаратную независимость.

Локально пройдены `bash -n *.sh`, `bash -n libexec/*.sh`, `bash -n lib/*.sh`, `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py gui/embedded_webview.py`, `python3 -m unittest tests.test_embedded_webview tests.test_gui_server` и `python3 gui/embedded_webview.py --check`. Остаточный риск один: нужен живой smoke через `subvost-xray-tun.desktop` на текущей машине, чтобы подтвердить, что белый экран ушёл именно в реальном desktop-сеансе.
