# Приведение структуры bundle к управляемому layout

- Дата: 2026-03-27
- Статус: done
- Источник: `AGENTS.md`, `README.md` и `plans/drafts/2026-03-27-tun-hardening-from-report.md` как контекст текущего layout и инженерного workflow

## Цель

Отделить пользовательские точки входа, внутреннюю реализацию и инженерную документацию так, чтобы bundle оставался переносимым и не ломал текущий сценарий запуска через CLI и GUI.

Ожидаемый результат: корень репозитория содержит только публичные entrypoint-скрипты, operator-managed конфиги, `logs/`, `plans/` и верхнеуровневую документацию, а внутренняя реализация и вспомогательные артефакты разнесены по специализированным каталогам без изменения пользовательского контракта.

## Изменения

### Целевая структура

Зафиксировать и реализовать следующий layout:

```text
/
  README.md
  AGENTS.md
  run-xray-tun-subvost.sh
  stop-xray-tun-subvost.sh
  capture-xray-tun-state.sh
  open-subvost-gui.sh
  install-on-new-pc.sh
  subvost-xray-tun.desktop
  xray-tun-subvost.json
  singbox-tun-subvost.json
  logs/
  plans/
  lib/
  libexec/
  gui/
  docs/research/
  assets/
```

- Корень оставить только для user-facing entrypoint'ов, operator-managed JSON, `logs/`, `plans/`, `README.md` и `AGENTS.md`.
- В `lib/` вынести общий shell-модуль с единым разрешением путей относительно корня проекта.
- В `libexec/` перенести внутренние shell-реализации; корневые `.sh` оставить thin wrapper'ами.
- В `gui/` перенести Python backend GUI.
- В `docs/research/` перенести исследовательские и разовые аналитические документы.
- `subvost-xray-tun.desktop` оставить в корне как публичный launcher bundle.
- В `assets/` держать repo-managed иконки, шаблоны launcher'ов и прочие вспомогательные артефакты, которые не должны быть прямой пользовательской точкой входа.

### Совместимость и контракты

- Сохранить текущие публичные имена команд в корне: `run-xray-tun-subvost.sh`, `stop-xray-tun-subvost.sh`, `capture-xray-tun-state.sh`, `open-subvost-gui.sh`, `install-on-new-pc.sh`.
- Сохранить `subvost-xray-tun.desktop` в корне как канонический portable launcher для bundle.
- Ввести единый внутренний env-контракт `SUBVOST_PROJECT_ROOT` только как transport-параметр внутри одной process-chain; пользовательская установка этой переменной не считается поддерживаемым интерфейсом.
- Корневые wrapper'ы всегда самостоятельно вычисляют корень проекта по собственному физическому пути и переопределяют `SUBVOST_PROJECT_ROOT`, не доверяя значению из внешнего окружения.
- Зафиксировать единый authority для root resolution:
  - корневые wrapper'ы и `open-subvost-gui.sh` определяют корень только по своему пути;
  - `open-subvost-gui.sh` передаёт вычисленный `SUBVOST_PROJECT_ROOT` в `pkexec`-цепочку;
  - `start-gui-backend-root.sh` принимает только абсолютный `SUBVOST_PROJECT_ROOT`, валидирует его и не пытается вычислять альтернативный корень;
  - `gui_server.py` использует `SUBVOST_PROJECT_ROOT` как основной источник только в launcher/bootstrap-сценарии, а fallback на parent-каталог допустим только для прямого локального запуска backend вне GUI-цепочки.
- Добавить bundle identity contract для GUI-цепочки: backend публикует в `/api/status` стабильный идентификатор текущего bundle как минимум по `project_root`, а `open-subvost-gui.sh` переиспользует уже поднятый backend только если совпадают и `gui_version`, и bundle identity; при несовпадении любого из них backend перезапускается.
- Перевести shell- и Python-компоненты на root-based path resolution вместо зависимости от расположения runtime-файлов рядом с вызываемым скриптом.
- Оставить `xray-tun-subvost.json`, `singbox-tun-subvost.json` и `logs/` в корне как operator-managed runtime-артефакты.
- Не менять URL GUI, расположение state-файлов в `${HOME}` и текущий runtime-контракт запуска.

### Миграция shell- и GUI-слоя

- Добавить общий модуль в `lib/` с вычислением `PROJECT_ROOT`, путей до конфигов, логов и внутренних скриптов.
- Перенести реальные реализации `run`, `stop`, `capture`, `open`, `install` и root-bootstrap GUI в `libexec/`.
- Оставить в корне только thin wrapper'ы, которые вычисляют корень, экспортируют `SUBVOST_PROJECT_ROOT` и делают `exec` во внутреннюю реализацию.
- Явно зафиксировать судьбу `start-gui-backend-root.sh`: после реорганизации это внутренний bootstrap в `libexec/`, а не публичная пользовательская команда; `README.md` и `AGENTS.md` должны отражать его как internal-компонент GUI-цепочки.
- Перенести `gui_server.py` в `gui/` и привязать его к вычисленному корню проекта по описанному выше authority ruleset.
- Зафиксировать единый operational path: GUI вызывает только публичные корневые wrapper-скрипты `run/stop/capture`, прямые вызовы `libexec` из backend запрещены.
- Добавить в план статическую проверку этого контракта: action-path'ы внутри `gui_server.py` должны резолвиться к корневым wrapper'ам, а не к `libexec/`.

### Launcher и документация

- Убрать из `.desktop` зашитые absolute path к старому расположению bundle.
- Сделать `.desktop` self-locating через `Exec` с field code `%k`: launcher должен получать путь к самому desktop-файлу, вычислять каталог bundle из `dirname(%k)` и запускать только публичный `open-subvost-gui.sh` из этого каталога.
- Явно запретить для `.desktop` прямой запуск internal-скриптов из `libexec/`; desktop launcher обязан вести в публичный `open-subvost-gui.sh`.
- Не использовать `Path` как обязательное условие работы launcher'а; корректность запуска должна обеспечиваться самим `Exec`.
- Явно зафиксировать scope переносимости launcher'а: поддерживается запуск `subvost-xray-tun.desktop`, который лежит внутри самого bundle; отдельная установка launcher'а в системное меню вне bundle в эту задачу не входит.
- Для `Icon` использовать portable вариант: системную иконку по умолчанию или layout, не требующий старого абсолютного пути; не завязывать launcher на старый путь к SVG.
- Перенести `deep-research-report.md` в `docs/research/` и обновить ссылки на него в проектной документации и планах.
- Обновить `README.md`: краткая карта структуры проекта, разделение public/internal частей, правила по runtime-артефактам и переносимости launcher'а.
- Обновить `AGENTS.md` под новый layout и сохранить в нём актуальный контракт по точкам входа, `plans/` и operator-managed артефактам.
- Явно убрать `start-gui-backend-root.sh` из списка пользовательских точек входа в документации и оставить его только как внутренний компонент GUI bootstrap chain.

### Cleanup остаточных привязок

- Удалить из кода и документации ссылки на старый пользовательский путь `MyWorkspace/.../subvost-xray-tun`.
- Проверить, что внутренние компоненты больше не полагаются на старый flat-layout для поиска реализаций, GUI backend и launcher-артефактов.
- Не включать в эту задачу изменения сетевой логики, TUN/DNS hardening, PID/state-механики и формата operator-managed JSON, кроме адаптации путей и структуры.

## Проверки

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m py_compile gui/gui_server.py`
- `desktop-file-validate subvost-xray-tun.desktop`
- Поиск по репозиторию на жёстко зашитые старые absolute path и на прямые зависимости от устаревшего flat-layout
- Статическая проверка GUI-контракта: `gui_server.py` резолвит action-path'ы только к корневым wrapper'ам `run/stop/capture`, а не к `libexec/`
- Статическая проверка desktop-контракта: `Exec` в `subvost-xray-tun.desktop` использует `%k`, вычисляет каталог bundle и ведёт в публичный `open-subvost-gui.sh`
- Статическая проверка GUI identity-контракта: `/api/status` возвращает `project_root` или эквивалентный bundle identity, а launcher сравнивает его вместе с `gui_version`
- Ручной happy-path: `sudo ./run-xray-tun-subvost.sh`, подтверждение наличия `tun0`, затем `./stop-xray-tun-subvost.sh`
- Ручной запуск диагностики: `sudo ./capture-xray-tun-state.sh`
- Ручной GUI-smoke: `./open-subvost-gui.sh`, затем команды `Старт`, `Стоп`, `Снять диагностику`
- Ручной GUI-smoke через launcher: запуск `subvost-xray-tun.desktop` двойным кликом или эквивалентным desktop-сценарием из нового расположения bundle, без зависимости от terminal `cwd`, подтверждение `pkexec`, открытие `http://127.0.0.1:8421`
- Проверка рестарта GUI backend: launcher корректно переиспользует уже поднятый backend и корректно перезапускает его при несовпадении версии
- Проверка cwd-agnostic поведения: вызов корневых wrapper'ов по абсолютному пути из произвольного чужого `cwd`
- Проверка переносимости: копирование bundle в другой absolute path и запуск корневых wrapper'ов, `open-subvost-gui.sh` и `subvost-xray-tun.desktop` из нового места
- Отдельная проверка relocation в путь с пробелами: копирование bundle в каталог с пробелами в имени и повторный запуск `open-subvost-gui.sh` и `subvost-xray-tun.desktop`
- Отдельная проверка relocation при уже запущенном старом backend: после копирования bundle и старта launcher из нового пути должен быть обнаружен mismatch по bundle identity, выполнен restart backend и открыт GUI именно нового bundle
- Негативные сценарии: отсутствие одного из JSON-конфигов, отсутствие `logs/`, запуск `.desktop` из bundle вне старого пути, корректное определение корня проекта у backend и wrapper'ов, попытка подменить `SUBVOST_PROJECT_ROOT` внешним окружением, ошибка в `pkexec`-запуске backend без потери диагностируемости

## Допущения

- Это консервативный structural refactor без изменения пользовательских команд и штатного runtime-поведения TUN/DNS.
- Operator-managed JSON-конфиги и каталог `logs/` остаются в корне, чтобы не требовать ручной миграции данных и привычных сценариев эксплуатации.
- Переносимость launcher'а важнее сохранения кастомного absolute path до SVG-иконки; допустим portable fallback на системную иконку.
- Переносимость `.desktop` в этой задаче ограничена сценарием, где сам launcher хранится внутри каталога bundle и запускается оттуда.
- `SUBVOST_PROJECT_ROOT` не является внешним пользовательским API и не должен менять поведение корневых wrapper'ов при его ручной подстановке извне.
- Текущий draft-план по hardening bundle остаётся отдельной задачей и не смешивается с уборкой структуры.
- Если после этой задачи потребуется более глубокая переработка runtime-layout для конфигов, state или var-данных, это оформляется отдельным планом после стабилизации новой public/internal границы.

## Итог

Реализован новый layout bundle: shell-общие path-хелперы вынесены в `lib/subvost-common.sh`, реальные реализации перенесены в `libexec/`, Python backend — в `gui/gui_server.py`, исследовательский отчёт — в `docs/research/deep-research-report.md`, SVG-иконка — в `assets/`. Корневые `run/stop/capture/open/install` теперь работают как thin wrapper'ы, которые вычисляют корень bundle по собственному пути, переопределяют `SUBVOST_PROJECT_ROOT` и `exec`-ят internal-реализацию.

GUI-контракт обновлён: `gui/gui_server.py` теперь резолвит action-path'ы только к публичным wrapper'ам в корне, публикует `project_root` и `bundle_identity` в `/api/status`, а `libexec/open-subvost-gui.sh` переиспользует backend только при совпадении `gui_version` и `project_root`, иначе инициирует restart через `pkexec` и `libexec/start-gui-backend-root.sh`. `subvost-xray-tun.desktop` переведён на self-locating `Exec` с `%k`, без старых absolute path.

Статические проверки выполнены: `bash -n *.sh`, `bash -n libexec/*.sh`, `bash -n lib/*.sh`, `python3 -m py_compile gui/gui_server.py`, `desktop-file-validate subvost-xray-tun.desktop`, а также поиск по репозиторию на старые absolute path и прямые зависимости от устаревшего flat-layout. Остаточные риски: в текущем окружении не выполнены ручные smoke-проверки с `sudo`, `pkexec`, переносом bundle в другой путь и запуском `.desktop` из реального desktop-session; их нужно провести отдельно на целевой машине.
