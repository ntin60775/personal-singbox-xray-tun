# Карточка задачи TASK-2026-0051

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0051` |
| Parent ID | `—` |
| Уровень вложенности | `0` |
| Ключ в путях | `TASK-2026-0051` |
| Технический ключ для новых именуемых сущностей | `legacy-state-recovery` |
| Краткое имя | `legacy-state-recovery` |
| Статус | `завершена` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `main` |
| Дата создания | `2026-04-08` |
| Дата обновления | `2026-04-08` |

## Цель

Убрать тупиковый сценарий после ownership-isolation, когда legacy `~/.xray-tun-subvost.state` без `BUNDLE_PROJECT_ROOT` блокирует и `run`, и `stop`, даже если runtime уже не жив.

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

- диагностика и исправление сценария stale legacy state без bundle identity;
- безопасный recovery-path в shell-сценариях `run` и `stop`;
- синхронизация GUI-guard, чтобы web UI не блокировал старт из-за мёртвого legacy state;
- тесты на stale unknown state без ослабления foreign-runtime guard.

### Не входит

- ослабление защиты от active foreign runtime;
- миграция старых state-файлов в фоне или массовая очистка домашнего каталога;
- изменение GUI-поведения вне отражения shell-контракта.

## Контекст

- источник постановки: пользователь сообщил, что после последней задачи `run` и `stop` зациклились на legacy state без identity;
- связанная бизнес-область: lifecycle portable bundle и безопасное восстановление после обновления shell-контракта;
- ограничения и зависимости: нельзя снова разрешить управление чужим runtime; допускается recovery только для явно stale state;
- основной контекст сессии: `новая задача`

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | `libexec/run-xray-tun-subvost.sh`, `libexec/stop-xray-tun-subvost.sh`, `gui/gui_server.py`, `tests/test_gui_server.py` |
| Конфигурация / схема данных / именуемые сущности | Уточняется контракт обработки legacy `STATE_FILE` без `BUNDLE_PROJECT_ROOT` |
| Интерфейсы / формы / страницы | Косвенно меняется поведение shell-команд `run` и `stop` |
| Интеграции / обмены | Runtime state в домашнем каталоге пользователя |
| Документация | Новый task-контур и запись в `knowledge/tasks/registry.md` |

## Связанные материалы

- основной каталог задачи: `knowledge/tasks/TASK-2026-0051-legacy-state-recovery/`
- файл плана: `plan.md`
- связанная предыдущая задача: `knowledge/tasks/TASK-2026-0047-runtime-ownership-isolation/`
- связанные коммиты / PR / ветки: `—`
- связанные операции в `knowledge/operations/`, если есть: `—`

## Текущий этап

Реализация и ручной smoke завершены. Пользователь подтвердил, что GUI в браузере запускается, VPN работает и консольный запуск снова рабочий.

## Стратегия проверки

### Покрывается кодом или тестами

- unit-проверки `tests/test_gui_server.py` на stale unknown state и shell-контракт recovery-path;
- `bash -n *.sh`;
- `bash -n libexec/*.sh`;
- `bash -n lib/*.sh`;
- `python3 -m unittest tests.test_gui_server`;
- dry-run `./stop-xray-tun-subvost.sh` на временном legacy state без `BUNDLE_PROJECT_ROOT`;
- `markdown-localization-guard` для изменённых Markdown-файлов задачи.

### Остаётся на ручную проверку

- дополнительных обязательных ручных проверок по этой задаче не осталось; при необходимости отдельно можно проверить embedded webview-launcher.

## Критерии готовности

- stale legacy state без живого runtime больше не блокирует запуск;
- `stop` умеет безопасно зачистить stale legacy state, но не трогает live unknown runtime;
- foreign-runtime guard остаётся жёстким;
- task-контур и проверки синхронизированы с реализацией.

## Итог

В `libexec/run-xray-tun-subvost.sh` добавлен recovery-path для legacy state без `BUNDLE_PROJECT_ROOT`: если по state не обнаруживаются живой `XRAY_PID` и TUN-интерфейс, запуск больше не зацикливается на требовании `stop`, а перезаписывает stale state новым запуском. Если unknown runtime действительно жив, жёсткий guard остаётся прежним.

В `libexec/stop-xray-tun-subvost.sh` stale legacy state теперь можно безопасно зачистить без попытки управлять неподтверждённым runtime: скрипт удаляет только stale state-файл и завершает recovery-path успешно. В `gui/gui_server.py` web UI синхронизирован с этим контрактом и больше не блокирует `Старт` только из-за мёртвого unknown state без живого runtime. В `tests/test_gui_server.py` добавлены регрессионные проверки на этот сценарий, локально подтверждены `bash -n`, `python3 -m unittest tests.test_gui_server` и dry-run cleanup временного legacy state, а пользователь отдельно подтвердил, что GUI в браузере запускается, VPN работает и консольный запуск снова рабочий.
