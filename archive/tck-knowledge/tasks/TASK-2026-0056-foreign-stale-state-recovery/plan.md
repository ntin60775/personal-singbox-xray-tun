# План задачи TASK-2026-0056

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0056` |
| Parent ID | `—` |
| Версия плана | `2` |
| Дата обновления | `2026-04-19` |

## Цель

Сделать принадлежность подключения переносимой: идентификатор установки должен храниться как стабильный `install-id`, а абсолютный путь каталога не должен быть постоянным ключом владельца.

## Границы

### Входит

- локальный для установки `.subvost/install-id`;
- `BUNDLE_INSTALL_ID` в файле состояния;
- `BUNDLE_PROJECT_ROOT_HINT` только как диагностика и резервная логика для старого формата;
- сравнение GUI-службы по `install_id`;
- явный перехват живого чужого подключения через кнопку `Перехватить`;
- сохранение целевого `install-id` при синхронизации каталога;
- regression-тесты и task-документация.

### Не входит

- удаление абсолютных путей из рабочих указателей подключения;
- переработка installed menu-entry `Exec` / `TryExec`;
- единое подключение для всех копий установки;
- принудительная остановка живого подключения другой установки.

## Планируемые изменения

### Код

- добавить shell-helper-ы `subvost_ensure_install_id`, `subvost_validate_install_id`, `subvost_read_install_id_file`;
- экспортировать `SUBVOST_INSTALL_ID_FILE` в layout;
- в `run` писать `BUNDLE_INSTALL_ID` и `BUNDLE_PROJECT_ROOT_HINT`, но не `BUNDLE_PROJECT_ROOT`;
- в `stop` сначала сравнивать `BUNDLE_INSTALL_ID`, а legacy path использовать только при отсутствии install-id;
- в Python-службу добавить `install_id` в `ServiceContext`, статус и `bundle_identity`;
- в запускателе заменить проверку GUI-службы с `project_root` на `install_id`, сохранив перезапуск при смене root той же установки;
- в синхронизации каталога исключить `.subvost` из копирования источника и обеспечить целевой `install-id`;
- добавить `takeover_runtime` в service-layer и связать кнопку `Перехватить` с этим действием;
- в `stop` разрешить остановку живого чужого подключения только при `SUBVOST_FORCE_TAKEOVER=1`.

### Конфигурация / схема данных / именуемые сущности

- новых runtime/package зависимостей нет;
- новых import-направлений между UI и shell нет;
- новый постоянный файл: `.subvost/install-id`, ignored в Git;
- новый state key: `BUNDLE_INSTALL_ID`;
- ключ пути в новом файле состояния: `BUNDLE_PROJECT_ROOT_HINT`, не идентификатор владельца.

### Документация

- обновить task-контур с версии `recovery-fix` на `install-id portability-fix`;
- обновить verification matrix под install-id инварианты;
- проверить локализацию task-документов.

## Риски и зависимости

- если `install-id` скопировать из repo в production, dev и prod начнут считаться одной установкой;
- если `install-id` потерять при переносе каталога, новая копия станет другой установкой;
- если запускатель сравнивать только по `install-id` и не учитывать root, можно переиспользовать GUI-службу из старого каталога после переноса;
- `Exec` / `TryExec` в menu-entry всё ещё абсолютные и требуют отдельной задачи для запускателя без зависимости от пути.

## Проверки

### Что можно проверить кодом или тестами

- `bash -n *.sh lib/*.sh libexec/*.sh`;
- `env PYTHONPYCACHEPREFIX=/tmp/subvost-pycache python3 -m py_compile gui/subvost_app_service.py gui/gui_server.py gui/native_shell_app.py`;
- `python3 -m unittest discover tests`;
- `git diff --check`;
- `python3 .agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/task.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/plan.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/sdd.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/artifacts/verification-matrix.md`;
- `python3 ~/.agents/skills/owned-text-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/task.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/plan.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/sdd.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/artifacts/verification-matrix.md`.

### Что остаётся на ручную проверку

- production sync после rework;
- ручная проверка запуска и остановки из production-каталога;
- перенос production-каталога с сохранением `.subvost/install-id`;
- проверка dev/repo GUI рядом с живым production-подключением.
- ручной перехват живого production-подключения из другого экземпляра через кнопку `Перехватить`.

## Шаги

- [x] Проверить текущую модель принадлежности по пути.
- [x] Добавить локальные helper-ы `install-id` установки.
- [x] Перевести shell state и guards на `BUNDLE_INSTALL_ID`.
- [x] Обновить GUI-службу и контракт запускателя.
- [x] Защитить синхронизацию production-каталога от копирования `install-id` источника.
- [x] Реализовать явный ручной перехват чужого подключения через кнопку `Перехватить`.
- [x] Обновить regression-тесты.
- [x] Обновить task-документацию.
- [x] Повторить guard-проверки документации.
- [x] Синхронизировать production-каталог.
- [x] Переоформить локальный commit через `amend`.

## Критерии завершения

- абсолютный путь не используется как идентификатор владельца;
- разные установки отличаются по install-id;
- обычные сценарии не останавливают чужое подключение, а кнопка `Перехватить` выполняет явный force-stop;
- перенос каталога той же установки не меняет install-id;
- синхронизация production-каталога сохраняет целевую идентичность установки;
- все проверки и task-контур синхронизированы.
