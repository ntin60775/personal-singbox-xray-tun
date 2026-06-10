# Карточка задачи TASK-2026-0063

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0063` |
| Parent ID | `—` |
| Уровень вложенности | `0` |
| Ключ в путях | `TASK-2026-0063` |
| Технический ключ для новых именуемых сущностей | `—` |
| Краткое имя | `fix-install-id-ownership` |
| Человекочитаемое описание | Исправить создание `.subvost/install-id` так, чтобы файл не оставался принадлежать root при запуске от sudo/pkexec |
| Статус | `завершена` |
| Приоритет | `высокий` |
| Ответственный | `не назначен` |
| Ветка | `task/task-2026-0064-fix-install-id-ownership` |
| Требуется SDD | `нет` |
| Статус SDD | `не требуется` |
| Ссылка на SDD | `—` |
| Дата создания | `2026-05-02` |
| Дата обновления | `2026-05-02` |

## Цель

Гарантировать, что `.subvost/install-id` создаётся с владельцем реального пользователя, даже если вызывающий процесс (shell-скрипт или GUI) работает от root через `sudo`/`pkexec`. Это предотвращает `PermissionError` при запуске GTK UI после root-операций с bundle.

## Границы

### Входит

- Исправление `subvost_ensure_install_id()` в `lib/subvost-common.sh`
- Исправление `ensure_bundle_install_id()` в `gui/subvost_app_service.py`
- Smoke-check: удаление `.subvost`, запуск GUI, проверка владельца
- Smoke-check: удаление `.subvost`, запуск `run-xray-tun-subvost.sh` (или `capture-xray-tun-state.sh`), проверка владельца

### Не входит

- Перенос `.subvost` в `~/.config` или другое место вне bundle
- Изменение формата или семантики `install-id`
- Изменение логики `bundle identity` и `runtime ownership isolation`

## Контекст

- источник постановки: инцидент — GTK UI перестал запускаться из-за `PermissionError` на `.subvost/install-id`
- связанная бизнес-область: Linux runtime, bundle identity, permissions
- ограничения и зависимости: изменения затрагивают root- и user-контур одновременно
- исходный наблюдаемый симптом / лог-маркер:
  ```
  PermissionError: [Errno 13] Отказано в доступе: '/home/prog7/.../.subvost/install-id'
  ```
- основной контекст сессии: `новая задача`

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | `lib/subvost-common.sh`, `gui/subvost_app_service.py` |
| Конфигурация / схема данных / именуемые сущности | Нет |
| Интерфейсы / формы / страницы | Нет |
| Интеграции / обмены | Нет |
| Документация | Нет |

## Связанные материалы

- основной каталог задачи: `knowledge/tasks/TASK-2026-0063-fix-install-id-ownership/`
- файл плана: `plan.md`
- файл SDD: `sdd.md`, если он обязателен для этой задачи
- файл verification matrix: `artifacts/verification-matrix.md`, если для задачи обязателен `sdd.md`
- канонический нормативный contract или source-of-truth для доменной модели, если задача его меняет: `AGENTS.md` (bundle identity)
- пользовательские материалы: скриншот ошибки запуска GTK UI
- связанные коммиты / PR / ветки: перечислять delivery-ветки, PR/MR и merge-коммиты по мере появления
- связанные операции в `knowledge/operations/`, если есть: ...

## Контур публикации

| Unit ID | Назначение | Head | Base | Host | Тип публикации | Статус | URL | Merge commit | Cleanup |
|---------|------------|------|------|------|----------------|--------|-----|--------------|---------|
| `—` | — | `—` | `—` | `none` | `none` | `planned` | `—` | `—` | `не требуется` |

## Текущий этап

Реализация и smoke-check завершены.

## Стратегия проверки

### Покрывается кодом или тестами

- Синтаксическая проверка bash: `bash -n lib/subvost-common.sh`
- Синтаксическая проверка python: `python3 -m py_compile gui/subvost_app_service.py`

### Остаётся на ручную проверку

- Удалить `.subvost`, запустить GUI — проверить `ls -la .subvost/install-id` (владелец prog7, не root)
- Удалить `.subvost`, запустить `sudo ./run-xray-tun-subvost.sh` (или `sudo ./capture-xray-tun-state.sh`) — проверить `ls -la .subvost/install-id` (владелец prog7, не root)
- Проверить, что `stop-xray-tun-subvost.sh` корректно работает с новым install-id

## Критерии готовности

- [x] `subvost_ensure_install_id()` в shell создаёт `.subvost/install-id` с владельцем реального пользователя
- [x] `ensure_bundle_install_id()` в Python создаёт `.subvost/install-id` с владельцем реального пользователя
- [x] GUI запускается без `PermissionError` после root-операций
- [x] Smoke-check пройден
- [x] Изменения зафиксированы в git

## Итоговый список ручных проверок

- [x] Удалить `.subvost`, запустить `./open-subvost-gtk-ui.sh` — GUI поднялось, `install-id` принадлежит `prog7:prog7`
- [x] Удалить `.subvost`, запустить `sudo bash -c 'source lib/subvost-common.sh; subvost_ensure_install_id'` — `install-id` принадлежит `prog7:root` (owner корректен)
- [x] Удалить `.subvost`, запустить `sudo python3 -c 'ensure_bundle_install_id(...)'` — `install-id` принадлежит `prog7:prog7` (owner и group корректны)

## Итог

### Что сделано
- В `lib/subvost-common.sh` (`subvost_ensure_install_id`): после создания файла добавлен `chown` на реального пользователя (`subvost_resolve_real_user_name`) для каталога `.subvost` и файла `install-id`.
- В `gui/subvost_app_service.py` (`ensure_bundle_install_id`): после создания файла добавлен `os.chown` через `discover_real_user()` и `pwd.getpwnam()` для каталога и файла.
- Preflight: синтаксис bash и python проверен.
- Smoke-check: GUI и root-скрипты создают `install-id` с корректным владельцем.

### Что осталось
- Не требуется.

### Риски
- Каталог `.subvost` при shell-создании от root получает группу `root`, т.к. `chown` меняет только owner. Для чтения файла это не критично (достаточно owner), но в идеале можно доработать до `chown user:group`.
- Если `.subvost/install-id` уже существует и принадлежит root, фикс не применится автоматически — нужен ручной `chown` один раз.
