# План задачи TASK-2026-0053.5

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0053.5` |
| Parent ID | `TASK-2026-0053` |
| Версия плана | `1` |
| Дата обновления | `2026-04-10` |

## Цель

Дать пользователю быстрый отдельный вход в `GTK4` native shell для ручного smoke-тестирования, не ломая основной GUI launcher и не меняя rollout-политику проекта.

## Границы

### Входит

- wrapper для запуска native shell;
- отдельный installer menu-entry;
- repo-local `.desktop` для native UI;
- документация и реестр задач.

### Не входит

- смена default GUI launcher-а;
- автоматическое открытие native UI вместо текущего GUI;
- полный manual smoke родительской задачи.

## Планируемые изменения

### Код и shell

- добавить `open-subvost-gtk-ui.sh` и `libexec/open-subvost-gtk-ui.sh`;
- добавить `install-subvost-gtk-ui-menu-entry.sh` и `libexec/install-subvost-gtk-ui-menu-entry.sh`;
- добавить `subvost-xray-tun-gtk-ui.desktop`;
- при необходимости расширить общие env-path переменные в `lib/subvost-common.sh`.

### Документация

- зафиксировать подзадачу `TASK-2026-0053.5`;
- обновить `README.md` и `knowledge/tasks/registry.md`.

## Риски и зависимости

- нельзя менять основной launcher по умолчанию, иначе это уже будет rollout-решение, а не test-only контур;
- новый ярлык должен использовать те же bundle-иконки и тот же portable layout;
- root-запрос по-прежнему должен появляться только на runtime-действиях внутри native shell, а не на старте launcher-а.

## Проверки

### Что можно проверить кодом или тестами

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `python3 -m py_compile gui/native_shell_app.py`
- локализационная проверка Markdown для новых и обновлённых task-артефактов.

### Что уже проверено

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `python3 -m py_compile gui/native_shell_app.py`

### Что остаётся на ручную проверку

- запуск `./open-subvost-gtk-ui.sh`;
- установка и открытие ярлыка через `bash ./install-subvost-gtk-ui-menu-entry.sh`.

## Шаги

- [x] Открыть подзадачу и синхронизировать реестр
- [x] Добавить отдельный launcher native shell
- [x] Добавить отдельный desktop installer для GTK UI
- [x] Обновить README и task-артефакты
- [x] Прогнать shell/syntax проверки
