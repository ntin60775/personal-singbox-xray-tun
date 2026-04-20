# Subvost Xray TUN для Linux

Открытый репозиторий переносимого Linux bundle для запуска `xray-core` в `TUN`-режиме без второго прокси-runtime поверх `xray`. Проект ориентирован на локальный desktop-сценарий: импортировать подписку или ссылку, выбрать активный узел, поднять `TUN`, при необходимости снять диагностику и затем корректно остановить runtime.

## Статус проекта

- основная целевая платформа: Linux;
- текущий режим поставки: переносимый bundle без отдельной сборки;
- в Git хранится только санитизированный шаблон runtime-конфига и обезличенная документация;
- автоматические тесты есть только для части Python-логики, сетевой smoke остаётся обязательным вручную.

## Что умеет bundle

- запускать `xray-core` в `TUN`-режиме без внешнего proxy-движка;
- держать один рабочий GUI для импорта подписок, выбора узла, запуска, остановки и диагностики;
- импортировать URL подписки провайдера с `Xray`-совместимыми заголовками;
- генерировать runtime-конфиг из выбранного узла, не коммитя live-секреты;
- переноситься в другой каталог или на другую машину без привязки к локальному checkout.

## Что лежит в репозитории

- `run-xray-tun-subvost.sh` — основной запуск `xray-core` в `TUN`-режиме
- `stop-xray-tun-subvost.sh` — корректная остановка runtime и восстановление DNS
- `capture-xray-tun-state.sh` — полный диагностический дамп в `logs/`
- `open-subvost-gui.sh` — запуск GUI launcher
- `open-subvost-gtk-ui.sh` — запуск отдельного `GTK4` native UI для тестирования
- `install-on-new-pc.sh` — установка системных зависимостей для Debian/Ubuntu
- `update-xray-core-subvost.sh` — ручное обновление системного бинарника `xray-core`
- `install-subvost-gui-menu-entry.sh` — установка ярлыка GUI в меню приложений
- `install-subvost-gtk-ui-menu-entry.sh` — установка отдельного ярлыка `GTK4` native UI
- `install-or-update-bundle-dir.sh` — установка или обновление bundle в отдельный каталог
- `subvost-xray-tun.desktop` — desktop entry для bundle
- `subvost-xray-tun-gtk-ui.desktop` — отдельный desktop entry для тестового `GTK4` native UI
- `xray-tun-subvost.json` — tracked-шаблон `xray` runtime
- `assets/` — иконка и связанные статические ресурсы
- `gui/` — backend и web-интерфейс GUI
- `lib/`, `libexec/` — shell-реализация runtime, диагностики и installer-ов
- `tests/` — unit-тесты для Python-части
- `knowledge/` — внутренняя task-centric knowledge-система проекта

## Требования

Минимально нужны:

- `xray`
- `python3`
- `iproute2`
- `curl`
- `sudo`
- `pkexec`
- рабочий `/dev/net/tun`

Скрипты рассчитаны на обратимые runtime-изменения: временный `TUN`, policy-routing и временную подмену `/etc/resolv.conf`. Репозиторий не должен использоваться как место хранения реальных подписок, секретов и операторских дампов.

## Быстрый старт

Перед первым стартом runtime нужен активный узел в GUI: импортируй ссылку или подписку, затем явно выбери нужную ноду.

Запуск GUI без root-запроса:

```bash
./open-subvost-gui.sh
```

Отдельный запуск `GTK4` native UI для ручного smoke:

```bash
./open-subvost-gtk-ui.sh
```

Старт runtime из GUI выполняет кнопка `Старт`. В этот момент появится системный запрос `pkexec` на root-доступ для обратимых runtime-изменений.

Ручной старт runtime из терминала остаётся доступен:

```bash
sudo ./run-xray-tun-subvost.sh
```

Кнопки `Стоп` и `Диагностика` в GUI тоже используют `pkexec`. Ручная остановка из терминала:

```bash
./stop-xray-tun-subvost.sh
```

Диагностика:

```bash
sudo ./capture-xray-tun-state.sh
```

После успешного старта ожидаются:

- живой процесс `xray`;
- поднятый `tun0`;
- правило `ip rule` для таблицы runtime;
- временно переписанный `/etc/resolv.conf`.

## Подписки по URL

GUI поддерживает импорт и обновление подписок по URL.

Для запросов к subscription endpoint bundle отправляет набор `Xray`-совместимых заголовков:

- `User-Agent: Xray-core`
- `X-HWID`
- `X-Device-OS`
- `X-Ver-OS`
- `X-Device-Model`

Это важно для провайдеров, которые отдают рабочий payload только `Xray`-совместимым клиентам. В публичной версии репозитория используются только обезличенные примеры. Реальные endpoint-ы провайдера, рабочие токены и живые runtime-данные не должны попадать ни в Git, ни в issue, ни в PR.

Если провайдер вместо рабочих нод возвращает заглушку, GUI показывает точную причину из ответа провайдера. При root-действиях через `pkexec` `HWID` для subscription-запросов считается из контекста реального пользователя, а не из домашнего каталога `root`.

Parser дополнительно:

- отклоняет заглушки вида `0.0.0.0:1` вместо тихого импорта мусорной ноды;
- поддерживает `VLESS xhttp`-параметр `extra=...`.

## Конфиг и placeholders

`xray-tun-subvost.json` хранится в Git только в санитизированном виде и используется как шаблон для генерации runtime-конфига выбранного узла. Live-значения не коммитятся:

- `REPLACE_WITH_REALITY_UUID`
- `REPLACE_WITH_REALITY_PUBLIC_KEY`
- `REPLACE_WITH_REALITY_SHORT_ID`

Прямой запуск из шаблона не поддерживается: bundle стартует только при наличии активного узла и сгенерированного `generated-xray-config.json`.

## Установка на новую машину

Для Debian/Ubuntu:

```bash
bash ./install-on-new-pc.sh
```

Установщик:

- ставит базовые зависимости через `apt-get`;
- ставит `xray` через официальный `Xray-install`;
- удаляет лишние systemd-артефакты `Xray-install`, чтобы bundle оставался portable.

## Обновление ядра Xray

Код приложения и системный бинарник `xray-core` обновляются отдельно. Если нужно обновить только ядро, сначала отключи активное подключение, затем используй кнопку `Обновить ядро Xray` в окне `Настройки интерфейса` `GTK4` UI или запусти:

```bash
bash ./update-xray-core-subvost.sh
```

Сценарий использует официальный `Xray-install`, после обновления снова убирает лишние `systemd`-артефакты и оставляет проект в переносимом режиме. Если `xray` или `tun0` уже активны, обновление блокируется до ручной остановки подключения.

## Установка или обновление bundle в отдельный каталог

Если bundle нужно развернуть или обновить вне текущего git-репозитория, используй:

```bash
bash ./install-or-update-bundle-dir.sh /абсолютный/путь/к/каталогу
```

Сценарий:

- синхронизирует bundle в указанный абсолютный каталог;
- не копирует repo-local артефакты вроде `.git`, `.codex`, `.playwright-cli`, `.gitignore`;
- не затирает содержимое `logs/` в целевом каталоге;
- нормализует `Icon=subvost-xray-tun-icon` в desktop launcher и обновляет user-local theme-ссылку на `assets/subvost-xray-tun-icon.svg` из целевого bundle.

Если каталог развёрнут на новой машине впервые, после копирования при необходимости отдельно запусти:

```bash
bash /путь/к/каталогу/install-on-new-pc.sh
bash /путь/к/каталогу/install-subvost-gui-menu-entry.sh
bash /путь/к/каталогу/install-subvost-gtk-ui-menu-entry.sh
```

## Ярлык GUI

Установка ярлыка в пользовательское меню:

```bash
bash ./install-subvost-gui-menu-entry.sh
```

Скрипт создаёт `~/.local/share/applications/subvost-xray-tun.desktop` с абсолютными `Exec`/`TryExec` к текущему bundle, но без абсолютного пути в `Icon=`: launcher использует theme-имя `subvost-xray-tun-icon`, а installer обновляет user-local ссылку на `assets/subvost-xray-tun-icon.svg` из текущего bundle. Ярлык открывает GUI без раннего root-запроса; `pkexec` появляется только при действиях `Старт`, `Стоп` и `Диагностика`. Если каталог bundle перемещён, installer ярлыка нужно запустить повторно, чтобы обновить `Exec` и локальную theme-ссылку на иконку.

Отдельный ярлык для `GTK4` native UI:

```bash
bash ./install-subvost-gtk-ui-menu-entry.sh
```

Этот installer создаёт `~/.local/share/applications/subvost-xray-tun-gtk-ui.desktop` и запускает именно `open-subvost-gtk-ui.sh`. Он нужен для ручного тестирования native shell и не меняет основной GUI-путь bundle по умолчанию.

## Проверки для разработчика

Перед фиксацией изменений:

```bash
bash -n *.sh
bash -n libexec/*.sh
bash -n lib/*.sh
python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py gui/embedded_webview.py
python3 -m unittest tests.test_subvost_parser tests.test_subvost_store tests.test_subvost_runtime tests.test_gui_server tests.test_embedded_webview
python3 -m json.tool xray-tun-subvost.json
```

Автотесты не заменяют ручную сетевую проверку. После сетевых изменений отдельно проверь:

```bash
sudo ./run-xray-tun-subvost.sh
ip -brief link show tun0
ip rule show
./stop-xray-tun-subvost.sh
```

Если менялся GUI, дополнительно открой `http://127.0.0.1:8421` или `subvost-xray-tun.desktop` и прогони действия `Старт`, `Стоп`, `Снять диагностику`, импорт подписки по URL и выбор активного узла. Отдельно проверь, что открытие GUI не вызывает `pkexec`, а root-запрос появляется только на действиях runtime.

## Публичный процесс репозитория

- правила вклада: см. `CONTRIBUTING.md`;
- безопасность и disclosure-процесс: см. `SECURITY.md`;
- правила взаимодействия: см. `CODE_OF_CONDUCT.md`.

Если хочешь принести крупную идею, сначала открой issue с контекстом и ограничениями, а уже потом переходи к PR.

## Лицензия

Проект распространяется по лицензии `MIT`. Полный текст лежит в `LICENSE`.
