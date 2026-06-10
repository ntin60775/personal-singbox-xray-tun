# План задачи TASK-2026-0057

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0057` |
| Parent ID | `—` |
| Версия плана | `1` |
| Дата обновления | `2026-04-20` |

## Цель

Сделать stale-state и связанные служебные файлы управляемыми: без скрытого накопления, без опасной автоостановки живого runtime и с понятным выводом прямо в диагностическом блоке `Файлы и дампы`.

## Границы

### Входит

- аудит состояния runtime artifacts в `collect_status`;
- отдельное действие cleanup для state, DNS backup и managed diagnostic dumps;
- retention `7` дней для управляемых диагностических файлов;
- пользовательский UI-контроль в `Диагностика → Файлы и дампы`;
- regression-тесты и task-документация.

### Не входит

- принудительная очистка живого чужого runtime;
- удаление нераспознанных файлов;
- изменение правил ownership из `TASK-2026-0056`;
- новое фоновое daemon-задание.

## Планируемые изменения

### Код

- добавить настройку `artifact_retention_days` в хранилище GUI и shared settings;
- добавить аудит `runtime_state_status`, `resolv_backup_status`, `diagnostic_dumps`, `cleanup_available` и `manual_attention_required`;
- добавить метод `cleanup_runtime_artifacts`;
- добавить retention cleanup только для `xray-tun-state-*.log` и `native-shell-log-export-*.log`;
- оставить `collect_status` не-мутирующим: он считает и показывает, но не удаляет;
- запускать retention cleanup в контролируемых runtime-действиях и явной cleanup-команде;
- добавить `/api/artifacts/cleanup`;
- добавить action `cleanup-artifacts` в native shell;
- вывести состояние артефактов и кнопку cleanup в `Диагностика → Файлы и дампы`.
- добавить hover, active, focus и disabled-состояния кнопок;
- добавить локальный feedback выполнения диагностических действий рядом с кнопками.

### Конфигурация / схема данных / именуемые сущности

- новых runtime/package зависимостей нет;
- новых import-направлений между UI и shell нет;
- новое поле настроек: `artifact_retention_days`;
- новый action id: `cleanup-artifacts`;
- новый endpoint: `/api/artifacts/cleanup`.

### Документация

- завести `TASK-2026-0057`;
- описать stale-state как stale artifact, а не активный чужой runtime;
- описать границы auto/manual cleanup;
- проверить локализацию task-документов.

## Риски и зависимости

- если cleanup будет вызываться из пассивной диагностики, пользователь получит скрытое удаление файлов при открытии экрана;
- если cleanup удалит state живого runtime, приложение может потерять контроль над подключением;
- если glob будет слишком широким, можно удалить пользовательские файлы из `logs/`;
- если UI покажет только кнопку без статуса, проблема снова станет непрозрачной.
- если кнопки не показывают hover/active и итог действия, пользователь не понимает, сработало ли нажатие.

## Проверки

### Что можно проверить кодом или тестами

- `env PYTHONPYCACHEPREFIX=/tmp/subvost-pycache python3 -m py_compile gui/subvost_app_service.py gui/gui_server.py gui/native_shell_app.py gui/native_shell_shared.py gui/subvost_store.py`;
- `python3 -m unittest discover tests`;
- `git diff --check`;
- `python3 .agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/task.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/plan.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/sdd.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/artifacts/verification-matrix.md`;
- `python3 ~/.agents/skills/owned-text-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/task.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/plan.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/sdd.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/artifacts/verification-matrix.md gui/native_shell_app.py gui/native_shell_shared.py gui/subvost_app_service.py gui/gui_server.py gui/subvost_store.py`.

### Что остаётся на ручную проверку

- ручной production smoke подтверждён пользователем: кнопки cleanup в диагностике работают, визуальный feedback и no-op сообщение понятны.

## Шаги

- [x] Уточнить честную модель stale-state и управляемых артефактов.
- [x] Добавить настройки retention.
- [x] Добавить аудит runtime artifacts в service-layer.
- [x] Добавить controlled cleanup action.
- [x] Вывести статус и кнопку cleanup в `Диагностика → Файлы и дампы`.
- [x] Добавить интерактивные состояния кнопок.
- [x] Добавить локальный feedback выполнения диагностических действий.
- [x] Добавить backend endpoint cleanup.
- [x] Добавить regression-тесты.
- [x] Оформить task-документацию.
- [x] Прогнать автоматические проверки.
- [x] Прогнать локализационные guard-ы.
- [x] Синхронизировать production-каталог.
- [x] Получить подтверждение ручного production smoke от пользователя.

## Критерии завершения

- пассивная диагностика не удаляет файлы;
- cleanup не трогает живой runtime;
- stale state и orphan DNS backup очищаются только при доказанно неактивном runtime;
- retention удаляет только управляемые диагностические файлы старше заданного срока;
- экран диагностики показывает состояние и причину ручного контроля;
- диагностика даёт явное cleanup-действие рядом со статусом служебных файлов;
- диагностические кнопки визуально реагируют на наведение, фокус, нажатие и disabled-состояние;
- после cleanup пользователь видит локальное подтверждение результата рядом с кнопками;
- текущий живой state не считается ошибкой cleanup и объясняется no-op сообщением;
- проверки и документация синхронизированы.
