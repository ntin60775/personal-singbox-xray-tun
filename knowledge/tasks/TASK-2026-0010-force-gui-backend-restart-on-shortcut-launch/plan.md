# План задачи TASK-2026-0010

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0010` |
| Parent ID | `—` |
| Версия плана | `1` |
| Дата обновления | `2026-04-02` |

## Цель

Сделать поведение GUI launcher предсказуемым для desktop-сценариев: каждый запуск через ярлык должен не переиспользовать старый backend, а инициировать его принудительный restart и затем открывать веб-интерфейс уже на новом процессе.

Ожидаемый результат: и portable `subvost-xray-tun.desktop`, и ярлык, установленный через `install-subvost-gui-menu-entry.sh`, всегда запускают `open-subvost-gui.sh` в режиме forced restart backend; при этом ручной запуск `./open-subvost-gui.sh` без специальных аргументов сохраняет текущую модель поведения.

## Границы

### Входит

- исторический объём legacy-плана, сохранённого в `artifacts/legacy-plan.md`;
- сохранение исходного Markdown в `artifacts/legacy-plan.md`;
- приведение записи к task-centric структуре без потери контекста.

### Не входит

- новая реализация темы во время миграции;
- изменение исторического статуса legacy-задачи.

## Планируемые изменения

### Код

- содержание legacy-плана сохранено без переписывания; детали см. в историческом блоке ниже и в `artifacts/legacy-plan.md`.

### Конфигурация / схема данных / именуемые сущности

- при наличии изменений они описаны в историческом блоке ниже и в `artifacts/legacy-plan.md`.

### Документация

- task-centric карточка и план созданы в `knowledge/tasks/TASK-2026-0010-force-gui-backend-restart-on-shortcut-launch/`.

## Риски и зависимости

- legacy-план мог использовать ссылки удалённого legacy-контура; они сохраняются как исторический контекст внутри `artifacts/legacy-plan.md`.
- продолжение этой темы, если оно потребуется, должно идти уже из knowledge-системы, а не через восстановление отдельного legacy-контура.

## Проверки

### Что можно проверить кодом или тестами

- при наличии команд и автоматизируемых проверок см. исторический блок `Проверки` ниже.

### Что остаётся на ручную проверку

- сверить migrated-каталог с `artifacts/legacy-plan.md`.

## Шаги

- [x] Перенести исходный legacy-план в task-centric структуру
- [x] Сохранить исходный Markdown в `artifacts/legacy-plan.md`
- [x] Историческое состояние задачи зафиксировано и не требует дополнительной миграционной декомпозиции

## Критерии завершения

- Историческая задача уже завершена; текущий критерий миграции — сохранить контекст без потери деталей.

## Источник legacy-плана

- текущий артефакт: `artifacts/legacy-plan.md`
- карта миграции исходного пути: `knowledge/tasks/TASK-2026-0002-plans-to-knowledge-migration/artifacts/legacy/legacy-path-map.md`
- исходный статус: `done`
- исходный заголовок: `Принудительный restart GUI backend при запуске через ярлык`

## Исторический контекст

### Изменения

- Добавить в `open-subvost-gui.sh`-цепочку явный режим принудительного restart backend для desktop-launch сценариев.
- Обновить portable `subvost-xray-tun.desktop`, чтобы он передавал launcher'у этот режим явно.
- Обновить генерацию installed desktop entry в `install-subvost-gui-menu-entry.sh`, чтобы пункт меню приложений вёл себя так же, как portable ярлык.
- Кратко отразить новое поведение в README для раздела GUI.

## Исторические проверки

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m py_compile gui/gui_server.py`
- `desktop-file-validate subvost-xray-tun.desktop`
- Статическая проверка generated desktop entry template в installer-скрипте

## Исторические допущения

- Принудительный restart нужен именно для desktop-launch сценариев; ручной `./open-subvost-gui.sh` без аргументов не обязан всегда перезапускать backend.
- Для принудительного restart допустимо использовать уже существующий `pkexec -> start-gui-backend-root.sh` путь с `SUBVOST_GUI_RESTART=1`, без добавления отдельного HTTP API shutdown.

## Исторический итог

Добавлен явный флаг `--force-restart-backend` в `libexec/open-subvost-gui.sh`: при его наличии launcher всегда идёт в `pkexec`-цепочку и вызывает `start-gui-backend-root.sh` с `SUBVOST_GUI_RESTART=1`, не пытаясь переиспользовать уже поднятый backend. При обычном ручном запуске `./open-subvost-gui.sh` прежняя логика совместимого reuse сохранена.

Portable `subvost-xray-tun.desktop` и desktop entry, который генерирует `install-subvost-gui-menu-entry.sh`, теперь оба передают launcher'у `--force-restart-backend`. Это фиксирует требуемое поведение именно для ярлыков: каждый запуск через ярлык приводит к принудительному restart серверной части перед открытием браузера.

README обновлён под новое поведение GUI launcher. Статические проверки `bash -n *.sh`, `bash -n libexec/*.sh`, `bash -n lib/*.sh`, `python3 -m py_compile gui/gui_server.py` и `desktop-file-validate subvost-xray-tun.desktop` прошли без ошибок. Остаточный риск: в этой сессии не выполнялся ручной smoke реального desktop-launch с `pkexec`, поэтому фактический restart backend через системный ярлык нужно подтвердить отдельно на целевой машине.
