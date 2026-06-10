# Subvost Xray TUN — справка для агента

Этот файл описывает архитектуру, конвенции и процессы проекта **Subvost Xray TUN** — переносимого bundle для запуска `xray-core` в `TUN`-режиме на Linux.

---

## Обзор проекта

- **Основная платформа**: Linux desktop (Debian/Ubuntu-совместимые дистрибутивы).
- **Режим поставки**: переносимый bundle без отдельной сборки.
- **Язык проекта**: весь интерфейс, документация и комментарии в коде — на русском языке.
- **Лицензия**: MIT.

Bundle умеет:
- запускать `xray-core` в `TUN`-режиме без внешнего proxy-движка;
- импортировать подписки и отдельные ссылки (VLESS, VMess, Trojan, Shadowsocks);
- генерировать runtime-конфиг из выбранного узла;
- управлять маршрутизацией через routing-профили с geodata;
- предоставлять GUI для выбора узла, запуска, остановки и диагностики.

---

## Технологический стек

### Linux

- **Runtime**: Bash (`bash` + `set -euo pipefail`) + Python 3.
- **GUI (TUI)**: Универсальный текстовый интерфейс на `textual` (`gui/tui_app.py`) — работает в любом эмуляторе терминала под любым DE без зависимости от GTK/WebKitGTK. Импортирует `subvost_app_service.py` напрямую, не использует HTTP backend.
- **Сеть**: `iproute2`, `iptables` не требуется, policy-routing через `ip rule`/`ip route`.
- **Системные зависимости**: `xray`, `python3` (≥3.11), `textual` (≥8.2.6), `iproute2`, `curl`, `sudo`, `pkexec`, рабочий `/dev/net/tun`.

### Стек TUI (зафиксирован)

| Компонент | Версия | Примечание |
|-----------|--------|------------|
| Python | ≥3.11 | типизация, `pathlib`, `asyncio` |
| textual | ≥8.2.6 | TUI framework; `push_screen_wait` требует worker-контекст, используем `push_screen` + callback |
| rich | ≥15.0.0 | зависимость textual |
| pygments | ≥2.20.0 | подсветка синтаксиса в textual |

**Правило**: если apt предлагает textual <8.2.6, ставить через `pip install --upgrade textual --break-system-packages`.

**Bootstrap**: `gui/tui_bootstrap.py` проверяет версию textual и предлагает обновить через pip, если apt-версия устарела.


### Общие компоненты

- **Парсер ссылок**: `gui/subvost_parser.py` — VLESS, VMess, Trojan, Shadowsocks (SIP002).
- **Store**: `gui/subvost_store.py` — JSON-хранилище узлов, подписок, routing-профилей, настроек GUI.
- **Runtime-генератор**: `gui/subvost_runtime.py` — сборка готового Xray-конфига из шаблона и выбранного узла.
- **Routing**: `gui/subvost_routing.py` — импорт routing-профилей, скачивание `geoip.dat`/`geosite.dat`.
- **Пути**: `gui/subvost_paths.py` — XDG-совместимое разрешение путей к хранилищу.
- **App Service**: `gui/subvost_app_service.py` — общая бизнес-логика для Linux-backend.

---

## Структура каталогов

```text
├── lib/                    # Общая shell-библиотека (subvost-common.sh)
├── libexec/                # Реализация скриптов runtime, installer, launcher
├── gui/                    # Python TUI, бизнес-логика, tray + DDD-слои (domain, application, infrastructure, presentation)
├── tests/                  # Unit-тесты Python-части
├── assets/                 # Иконка и статические ресурсы
├── logs/                   # Runtime-логи (не коммитятся)
├── runtime/                # Runtime-артефакты
├── archive/                # Замороженные компоненты (Windows-порт, историческая TCK)
├── xray-tun-subvost.json   # Tracked-шаблон Xray-конфига (с placeholder-ами)
├── *.sh                    # Корневые wrapper-скрипты (делегируют в libexec/)
└── *.desktop               # Desktop entry для TUI
```

### Правило для shell-скриптов

Корневые `*.sh` — это **wrapper-ы**: они определяют `PROJECT_ROOT`, экспортируют layout через `lib/subvost-common.sh` и делегируют работу одноимённым скриптам в `libexec/`. Не дублируй логику в корневых скриптах.

---

## Ключевые конфигурационные файлы

- **`xray-tun-subvost.json`** — санитизированный шаблон Xray-конфига. Содержит placeholder-ы (`REPLACE_WITH_REALITY_UUID`, `REPLACE_WITH_REALITY_PUBLIC_KEY`, `REPLACE_WITH_REALITY_SHORT_ID`). Не запускается напрямую; bundle генерирует `generated-xray-config.json` при активации узла.
- **`.gitignore`** — исключает `logs/`, `__pycache__/`, `dist/`, runtime-артефакты.

---

## Сборка и запуск

### Linux

Сборка не требуется. Bundle работает как переносимый каталог.

```bash
# Первоначальная установка зависимостей
bash ./install-on-new-pc.sh

# Запуск TUI (универсальный, работает в любом DE)
./open-subvost-tui.sh

# Ручной старт runtime
sudo ./run-xray-tun-subvost.sh

# Остановка
./stop-xray-tun-subvost.sh

# Диагностика
sudo ./capture-xray-tun-state.sh
```


---

## Тестирование

### Автоматические тесты (Python)

```bash
python3 -m unittest tests.test_subvost_parser tests.test_subvost_store tests.test_subvost_runtime tests.test_subvost_app_service tests.test_subvost_routing
```

Также выполняются проверки синтаксиса:

```bash
bash -n *.sh
bash -n libexec/*.sh
bash -n lib/*.sh
python3 -m py_compile gui/tui_app.py gui/tui_bootstrap.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py gui/subvost_app_service.py gui/subvost_routing.py
python3 -m json.tool xray-tun-subvost.json
```

### Ручной smoke

Автотесты не заменяют сетевую проверку. После сетевых изменений обязателен ручной smoke:

```bash
sudo ./run-xray-tun-subvost.sh
ip -brief link show tun0
ip rule show
./stop-xray-tun-subvost.sh
```

Если менялся GUI — прогон через `./open-subvost-tui.sh`: `Старт`, `Стоп`, `Диагностика`, импорт подписки, выбор узла.

---

## Стиль кода и конвенции

### Bash
- `#!/usr/bin/env bash`
- `set -euo pipefail`
- Отступ: **2 пробела**
- Говорящие имена функций на русском или английском (в терминах проекта преобладает русский пользовательский текст, машинные литералы — английские).
- Все пути к bundle-ресурсам разрешаются через `lib/subvost-common.sh` и переменные окружения `SUBVOST_*`.

### Python
- PEP 8, отступ **4 пробела**, `snake_case`.
- `from __future__ import annotations` в начале каждого модуля.
- Типизация через `typing` (проект использует Python 3.11+).
- Все пути — `pathlib.Path`.
- JSON-файлы пишутся атомарно (`atomic_write_json`).


### Git и коммиты
- Короткие префиксы: `feat:`, `fix:`, `docs:`, `chore:`.
- Не коммить реальные subscription URL, UUID, publicKey, shortId, локальные IP, приватные дампы.
- В Git хранится только санитизированный шаблон конфига и обезличенная документация.

---

## Архитектура runtime (Linux)

1. Пользователь выбирает узел в TUI → `tui_app.py` сохраняет выбор в store через `subvost_app_service.py` и генерирует `generated-xray-config.json`.
2. Кнопка **Старт** → backend вызывает `run-xray-tun-subvost.sh` через `pkexec`.
3. Скрипт:
   - проверяет TUN-устройство, отсутствие конфликтующих сервисов;
   - материализует runtime-конфиг (применяет transport hints: `interface` + `mark`);
   - запускает `xray`;
   - поднимает `tun0`, настраивает policy-routing (`ip rule` + `ip route`);
   - временно переписывает `/etc/resolv.conf`;
   - сохраняет state-файл.
4. Кнопка **Стоп** → `stop-xray-tun-subvost.sh` откатывает изменения.

### Bundle identity и безопасность state

Каждая копия bundle получает `install-id` в `.subvost/install-id`. Скрипты `run`/`stop` проверяют, что state-файл принадлежит текущей установке, и отказываются управлять чужим runtime без явного `SUBVOST_FORCE_TAKEOVER=1`.

---

## Архитектура GUI

### TUI (единственный Linux-путь)

- `gui/tui_app.py` — приложение на `textual` с 5 вкладками: Dashboard, Узлы, Лог, Маршруты, Настройки.
- Запуск в любом эмуляторе терминала под любым DE (XFCE, KDE, GNOME, i3 и т.д.).
- Нет зависимости от GTK4/WebKitGTK/AppIndicator.
- Бизнес-логика импортируется напрямую из `subvost_app_service.py`, HTTP backend не используется.
- Bootstrap — `gui/tui_bootstrap.py` проверяет зависимости и предлагает установить через `pkexec`.


---

## Хранение данных

- **Linux store**: `~/.config/subvost-xray-tun/store.json` (XDG Base Directory).
- **Формат store**: версионированная структура (`version: 3`), содержит профили, узлы, подписки, active_selection, routing-профили, мета-данные.
- **Geodata**: `geoip.dat` и `geosite.dat` в каталоге `xray-assets` рядом со store.
- **Логи**: `logs/xray-subvost.log` (Linux).

---

## Подписки и HWID
Bundle отправляет Xray-совместимые заголовки при запросе подписок:
- `User-Agent: Xray-core`
- `X-HWID`, `X-Device-OS`, `X-Ver-OS`, `X-Device-Model`

HWID вычисляется детерминированно из хоста, домашнего каталога, системы и архитектуры через `uuid5`. При root-действиях через `pkexec` HWID берётся из контекста реального пользователя (`SUDO_USER` / `PKEXEC_UID`).

---

## Безопасность

- **Никаких секретов в Git**. Шаблон содержит только placeholder-ы.
- **Обратимые runtime-изменения**: временный TUN, policy-routing, backup `/etc/resolv.conf`.
- **Bundle identity** предотвращает случайное управление чужим runtime.
- **Парсер** отклоняет заглушки (`0.0.0.0:1`, `ZERO_UUID`) и placeholder-текст.
- Сообщения об уязвимостях — через приватный канал, не через публичный issue с exploit.

---

## Task-centric knowledge

Проект использует **worktrail v2** для учёта задач. Данные хранятся в git-notes `refs/notes/worktrail`.
Историческая TCK-система (`knowledge/tasks/`) перенесена в `archive/tck-knowledge/` для read-only контекста.

Новые задачи заводятся только через worktrail CLI: `worktrail contract init --task-id <id> --name "..."`.
---
## Полезные ссылки внутри репозитория

- `README.md` — быстрый старт, пользовательская документация.
- `DESIGN.md` — визуальный контракт GTK4 UI (палитра, типографика, запрещённые паттерны).
- `CONTRIBUTING.md` — правила вклада, стиль кода, preflight-проверки.
- `SECURITY.md` — политика безопасности и disclosure.
