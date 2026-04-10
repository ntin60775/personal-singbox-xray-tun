# Карточка задачи TASK-2026-0053.5

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0053.5` |
| Parent ID | `TASK-2026-0053` |
| Уровень вложенности | `1` |
| Ключ в путях | `TASK-2026-0053.5` |
| Технический ключ для новых именуемых сущностей | `gtk-test-launcher` |
| Краткое имя | `gtk-test-launcher` |
| Статус | `завершена` |
| Приоритет | `средний` |
| Ответственный | `Codex` |
| Ветка | `topic/gtk4-native-ui-spike` |
| Дата создания | `2026-04-10` |
| Дата обновления | `2026-04-10` |

## Цель

Добавить отдельный launcher и отдельный desktop entry для запуска `GTK4` native UI, чтобы можно было вручную прогонять smoke-сценарии нативного клиента, не переключая основной GUI bundle по умолчанию.

## Границы

### Входит

- отдельный shell launcher для `GTK4` native UI;
- отдельный installer ярлыка в пользовательское меню приложений;
- repo-local `.desktop` файл для запуска native UI;
- синхронизация knowledge-артефактов и README.

### Не входит

- перевод основного launcher-а проекта на native UI;
- изменение текущего web launcher-а по умолчанию;
- финальный manual smoke родительской `TASK-2026-0053`.

## Контекст

- после закрытия `TASK-2026-0053.4` у родительской задачи остался только ручной smoke;
- для этого smoke нужен быстрый и явный способ открыть именно `GTK4` native shell, не подменяя основной GUI-маршрут bundle;
- пользователь явно запросил отдельный ярлык для тестирования native UI.

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Shell / launcher | Появился отдельный wrapper `open-subvost-gtk-ui.sh` для native shell |
| Desktop integration | Появились отдельные `.desktop` и installer-скрипты для `GTK UI` |
| Документация | README и knowledge-контур синхронизированы под тестовый native launcher |

## Связанные материалы

- основной каталог подзадачи: `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.5-gtk-test-launcher/`
- файл плана: `plan.md`
- родительская задача: `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/`
- ключевые файлы реализации: `open-subvost-gtk-ui.sh`, `libexec/open-subvost-gtk-ui.sh`, `install-subvost-gtk-ui-menu-entry.sh`, `libexec/install-subvost-gtk-ui-menu-entry.sh`, `subvost-xray-tun-gtk-ui.desktop`

## Текущий этап

Подзадача завершена. Для ручного тестирования native UI теперь есть отдельный launcher и отдельный menu-entry installer, а основной web launcher проекта не менялся.

## Стратегия проверки

### Покрывается кодом или тестами

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `python3 -m py_compile gui/native_shell_app.py`

### Остаётся на ручную проверку

- запуск `./open-subvost-gtk-ui.sh` в живой графической сессии;
- установка и открытие `subvost-xray-tun-gtk-ui.desktop` через `install-subvost-gtk-ui-menu-entry.sh`.

## Итог

Добавлен отдельный тестовый путь для `GTK4` native shell без изменения основного launcher-а проекта. Это позволяет прогонять оставшийся manual smoke родительской `TASK-2026-0053` напрямую через нативный клиент.
