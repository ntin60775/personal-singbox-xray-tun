# План TASK-2026-0001

## Цель

Исправить run-скрипт так, чтобы orphaned state-файлы текущей установки корректно обрабатывались — новый запуск продолжался, если runtime уже не активен.

## Этапы

### 1. Расследование (completed)
- Прочитать лог ошибки
- Проанализировать state-файл и его владельца
- Изучить run-скрипт и stop-скрипт
- Найти различие в логике проверки `legacy_state_runtime_is_live`

### 2. Исправление run-скрипта (completed)
- Добавить `legacy_state_runtime_is_live` в блок `BUNDLE_INSTALL_ID == current`
- Добавить `legacy_state_runtime_is_live` в блок `BUNDLE_PROJECT_ROOT == current`
- Убедиться, что сообщения о stale state консистентны с stop-скриптом

### 3. Проверка GUI (completed)
- Убедиться, что GUI корректно определяет `ownership` для текущей установки
- Убедиться, что `start_blocked` возвращает `False` для orphaned state текущей установки
- Подтвердить, что кнопка "Перехватить" не требуется для текущей установки (это не foreign runtime)

### 4. Документирование (in_progress)
- Создать `task.md`
- Создать `plan.md`
- Обновить `registry.md`

## Артефакты

- `libexec/run-xray-tun-subvost.sh` — изменён
- `knowledge/tasks/TASK-2026-0001-run-script-orphaned-state/task.md`
- `knowledge/tasks/TASK-2026-0001-run-script-orphaned-state/plan.md`
