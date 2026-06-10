# Синхронизация версии GUI-контракта между backend и launcher

- Дата: 2026-04-02
- Статус: done
- Источник: review по исправлению root/review маршрутов, где уже запущенный backend мог пережить обновление bundle из-за неизменённой `gui_version`

## Цель

Сделать так, чтобы любое изменение HTTP-контракта GUI гарантированно приводило к корректному restart уже запущенного backend, а launcher и сервер не расходились по ожидаемой версии из-за дублирующихся литералов.

## Изменения

- Поднять `GUI_VERSION` после изменения root/review маршрутов.
- Убрать дублирование версии между `gui/gui_server.py` и `libexec/open-subvost-gui.sh`, оставив один источник истины.
- Обновить проверки launcher/backend-контракта так, чтобы следующая смена GUI-контракта не требовала ручной синхронизации в нескольких местах.
- Добавить тесты на единый источник версии и на использование этой версии launcher-ом.

## Проверки

- `python3 -m py_compile gui/gui_server.py gui/gui_contract.py`
- `python3 -m unittest tests.test_gui_server`
- Локальная проверка launcher-контракта:
  - убедиться, что launcher читает `GUI_VERSION` из общего python-модуля;
  - убедиться, что backend публикует ту же версию в `/api/status`.

## Допущения

- Наиболее надёжный способ убрать класс ошибки целиком — вынести версию GUI-контракта в общий python-модуль и читать её из launcher через короткий `python3` helper.
- Изменение root/review маршрутов является несовместимой сменой GUI-контракта и требует нового значения `GUI_VERSION`.

## Итог

- `GUI_VERSION` поднята до нового значения, соответствующего несовместимой смене root/review маршрутов.
- Версия GUI-контракта вынесена в общий модуль `gui/gui_contract.py`, который теперь используется и backend-ом, и launcher-ом.
- Из `libexec/open-subvost-gui.sh` убран hardcoded литерал версии: launcher читает ожидаемую версию из `gui_contract.py`, поэтому следующий bump делается в одном месте.
- Добавлены тесты на:
  - общий источник версии;
  - отсутствие дублирующего литерала в launcher;
  - согласованность маршрутов и GUI asset.
- Подтверждено:
  - `python3 -m py_compile gui/gui_server.py gui/gui_contract.py`;
  - `bash -n libexec/open-subvost-gui.sh`;
  - `python3 -m unittest tests.test_gui_server`;
  - runtime-проверка: `/api/status` публикует тот же `gui_version`, что и `gui_contract.py`.
