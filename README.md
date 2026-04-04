# Пакет Subvost Xray TUN

Этот репозиторий хранит переносимый bundle для запуска `xray-core` в `TUN`-режиме на Linux без второго runtime-контура и без внешнего proxy-движка поверх `xray`.

## Что лежит в корне

- `run-xray-tun-subvost.sh` — основной запуск `xray-core` в `TUN`-режиме
- `stop-xray-tun-subvost.sh` — корректная остановка runtime и восстановление DNS
- `capture-xray-tun-state.sh` — полный диагностический дамп в `logs/`
- `open-subvost-gui.sh` — запуск GUI launcher
- `install-on-new-pc.sh` — установка системных зависимостей для Debian/Ubuntu
- `install-subvost-gui-menu-entry.sh` — установка ярлыка GUI в меню приложений
- `subvost-xray-tun.desktop` — desktop entry для bundle
- `xray-tun-subvost.json` — основной tracked-шаблон `xray` runtime
- `assets/` — иконка и связанные статические ресурсы
- `gui/` — backend и web-интерфейс GUI
- `lib/`, `libexec/` — shell-реализация runtime, диагностики и installer-ов
- `knowledge/` — task-centric knowledge-система проекта

## Требования

Минимально нужны:

- `xray`
- `python3`
- `iproute2`
- `curl`
- `sudo`
- рабочий `/dev/net/tun`

Скрипты рассчитаны на Linux с обратимыми runtime-изменениями: временный `TUN`, policy-routing и временная подмена `/etc/resolv.conf`.

## Быстрый запуск

Перед первым `sudo ./run-xray-tun-subvost.sh` нужен активный узел в GUI: импортируй ссылку или подписку, затем явно выбери нужную ноду.

Старт:

```bash
sudo ./run-xray-tun-subvost.sh
```

Остановка:

```bash
./stop-xray-tun-subvost.sh
```

Диагностика:

```bash
sudo ./capture-xray-tun-state.sh
```

GUI:

```bash
./open-subvost-gui.sh
```

Web-GUI в bundle теперь одна: основной маршрут `/` и совместимые alias-маршруты отдают тот же рабочий экран с подписками, выбором узла, запуском `TUN` и диагностикой.

После успешного старта ожидаются:

- живой процесс `xray`
- поднятый `tun0`
- правило `ip rule` для таблицы runtime
- временно переписанный `/etc/resolv.conf`

## Подписки по URL

GUI поддерживает импорт и обновление подписок по URL.

Для запросов к subscription endpoint bundle теперь отправляет набор `Xray`-совместимых заголовков:

- `User-Agent: Xray-core`
- `X-HWID`
- `X-Device-OS`
- `X-Ver-OS`
- `X-Device-Model`

Это критично для провайдеров, которые отдают рабочий payload только `Xray`-клиентам. Для ссылки `https://example.com/subscription` такой режим подтвердился: вместо заглушки приходит base64-подписка с рабочими `VLESS`-нодами.

Если провайдер вместо рабочих нод возвращает stub-ссылку, GUI теперь показывает точную причину из ответа провайдера, например `Достигнут лимит устройств`, а не только общую фразу про несовместимый клиент. При запуске GUI через `pkexec` `HWID` для subscription-запросов теперь считается из real-user контекста, а не из домашнего каталога `root`.

Дополнительно parser теперь:

- отклоняет провайдерские заглушки вида `0.0.0.0:1` вместо тихого импорта мусорной ноды
- поддерживает `VLESS xhttp`-параметр `extra=...`

## Конфиг и placeholders

`xray-tun-subvost.json` хранится в Git только в санитизированном виде и используется как шаблон для генерации runtime-конфига выбранного узла. Live-значения не коммитятся:

- `REPLACE_WITH_REALITY_UUID`
- `REPLACE_WITH_REALITY_PUBLIC_KEY`
- `REPLACE_WITH_REALITY_SHORT_ID`

Прямой запуск из шаблона больше не поддерживается: bundle стартует только при наличии активного узла и сгенерированного `generated-xray-config.json`.

## Установка на новую машину

Для Debian/Ubuntu:

```bash
bash ./install-on-new-pc.sh
```

Installer:

- ставит базовые зависимости через `apt-get`
- ставит `xray` через официальный `Xray-install`
- удаляет лишние systemd-артефакты `Xray-install`, чтобы bundle оставался portable

## Ярлык GUI

Установка ярлыка в пользовательское меню:

```bash
bash ./install-subvost-gui-menu-entry.sh
```

Скрипт создаёт `~/.local/share/applications/subvost-xray-tun.desktop` с абсолютными путями к текущему bundle. Если каталог bundle перемещён, installer ярлыка нужно запустить повторно.

## Минимальные проверки

Перед фиксацией изменений:

```bash
bash -n *.sh
bash -n libexec/*.sh
bash -n lib/*.sh
python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py
python3 -m unittest tests.test_subvost_parser tests.test_subvost_store tests.test_subvost_runtime tests.test_gui_server
python3 -m json.tool xray-tun-subvost.json
```

## Ручной smoke

Автотесты не заменяют ручную сетевую проверку. После сетевых изменений отдельно проверь:

```bash
sudo ./run-xray-tun-subvost.sh
ip -brief link show tun0
ip rule show
./stop-xray-tun-subvost.sh
```

Если менялся GUI, дополнительно открой `http://127.0.0.1:8421` и прогони на единственном основном экране действия `Старт`, `Стоп`, `Снять диагностику`, а также импорт подписки по URL.
