# План задачи TASK-2026-0036

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0036` |
| Parent ID | `—` |
| Версия плана | `1` |
| Дата обновления | `2026-04-04` |

## Цель

Добавить в проект альтернативный `xray-core only` runtime для TUN-режима, не ломая текущий стек `Xray + sing-box`.

## Границы

### Входит

- новый tracked runtime-шаблон для `xray-only` режима;
- новые root/internal wrapper'ы запуска и остановки;
- materialize runtime-конфига на базе активного `Xray`-конфига;
- адаптация диагностики и GUI status;
- обновление README и knowledge-артефактов.

### Не входит

- удаление `sing-box` из основного сценария проекта;
- перевод GUI-кнопки `Старт` на `xray-only` по умолчанию;
- ручной end-to-end smoke с реальным поднятием туннеля в этой сессии.

## Планируемые изменения

### Код

- добавить функцию сборки `xray-only` runtime-конфига из активного `Xray`-конфига и TUN/DNS-шаблона;
- добавить `run-xray-only-tun-subvost.sh` и обновить stop-логику так, чтобы она корректно снимала `xray-only` policy-routing и DNS;
- научить диагностику и GUI отличать `runtime_impl=xray-only` от `runtime_impl=stack`.

### Конфигурация / схема данных / именуемые сущности

- добавить `xray-only-tun-subvost.json`;
- расширить state-файл новыми полями runtime-режима, интерфейса и routing-параметров.

### Документация

- описать, зачем в текущем проекте используется `sing-box`;
- описать новый `xray-only` режим, его сценарий запуска и ограничения;
- синхронизировать статус задачи и запись в `knowledge/tasks/registry.md`.

## Риски и зависимости

- `xray-core` TUN в проекте требует ручной policy-routing, поэтому поведение будет менее автоматическим, чем у `sing-box`;
- без ручного smoke в целевом Linux-окружении нельзя гарантировать полный runtime-parity;
- tracked-конфиги содержат placeholders и валидируются только структурно, без живого подключения к реальному узлу.

## Проверки

### Что можно проверить кодом или тестами

- `python3 -m unittest tests.test_subvost_runtime tests.test_gui_server`
- `python3 -m json.tool xray-only-tun-subvost.json`
- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m py_compile gui/gui_server.py`

### Что остаётся на ручную проверку

- `sudo ./run-xray-only-tun-subvost.sh`
- `ip -brief link show tun0`
- `ip rule show`
- `./stop-xray-tun-subvost.sh` или `./stop-xray-only-tun-subvost.sh`
- GUI/status после запуска альтернативного режима

## Шаги

- [x] Открыть task-контур и зафиксировать scope
- [x] Добавить `xray-only` runtime-конфиг и materialize-логику
- [x] Добавить wrapper'ы запуска/остановки и policy-routing cleanup
- [x] Обновить диагностику и GUI-status
- [x] Обновить README, registry и прогнать проверки

## Критерии завершения

- `xray-only` runtime добавлен как альтернативный сценарий без поломки текущего bundle;
- статус/диагностика понимают активный runtime-режим;
- документация и knowledge-система отражают новую возможность и её ограничения;
- выполнены все доступные статические проверки, а ручной smoke явно отмечен как отдельный шаг.

## Итог

Альтернативный `xray-core only` runtime реализован как отдельный сценарий, не ломающий основной режим `Xray + sing-box`. В проект добавлены новый tracked-шаблон `xray-only-tun-subvost.json`, materialize-логика в `gui/subvost_runtime.py`, отдельный `run-xray-only-tun-subvost.sh`, а общий stop-скрипт теперь умеет корректно снимать и `xray-only` policy-routing по state-файлу.

GUI и диагностика синхронизированы с новым `runtime_impl`: статус умеет различать `Xray + sing-box` и `Xray only`, а диагностический дамп показывает динамическую routing-таблицу и не требует активного `sing-box`, если текущий runtime его не использует.

Статические проверки и unit-тесты пройдены. Ручной smoke с реальным `sudo`, `tun0`, `ip rule`, DNS и сетевым трафиком остаётся отдельной обязательной проверкой на целевой Linux-машине.
