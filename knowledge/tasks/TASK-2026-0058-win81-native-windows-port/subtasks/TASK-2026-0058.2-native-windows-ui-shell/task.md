# Карточка задачи TASK-2026-0058.2

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0058.2` |
| Parent ID | `TASK-2026-0058` |
| Уровень вложенности | `1` |
| Ключ в путях | `TASK-2026-0058.2` |
| Технический ключ для новых именуемых сущностей | `native-windows-ui-shell` |
| Краткое имя | `native-windows-ui-shell` |
| Статус | `завершена` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `task/task-2026-0058-win81-native-windows-port` |
| Дата создания | `2026-04-27` |
| Дата обновления | `2026-04-27` |

## Цель

Спроектировать и реализовать нативный Windows UI для Windows 8.1 без браузера и webview как основного интерфейса.

## Границы

### Входит

- выбор UI-стека после обсуждения;
- core/helper JSON contract для связи UI с Python-логикой;
- первый vertical slice:
  - статус подключения;
  - активный узел;
  - `Подключиться`;
  - `Отключиться`;
  - `Диагностика`;
  - базовый список подписок и узлов;
- обработка UAC ошибок и runtime ошибок;
- русские UI-строки.

### Не входит

- открытие локального `HTTP` GUI в браузере;
- webview wrapper вокруг существующего HTML;
- полный перенос всех Linux `GTK4` возможностей в первый Windows slice;
- поддержка Windows tray до отдельного решения, если выбранный стек усложняет это в первом slice.

## Решение

Выбран стек `.NET Framework 4.8 + Windows Forms` как нативный Windows shell, который вызывает Python core/helper через JSON-команды.

## Текущий этап

Реализована локально. Добавлен нативный WinForms shell на `.NET Framework 4.8`, отдельный JSON helper `subvost-core`, сборка UI/helper/runtime в `dist\SubvostXrayTun\` и тесты контракта.

Linux-среда не содержит `MSBuild`/`csc`, поэтому фактическая C# сборка и запуск окна остаются Windows-gate для `TASK-2026-0058.4`. Static gates подтверждают `.NET Framework 4.8`, `WinExe`, отсутствие browser/webview и отдельный helper layout.

## Критерии готовности

- UI запускается отдельным Windows-окном;
- UI не открывает браузер и не использует webview;
- базовые runtime-действия работают через core/helper;
- ошибки показываются пользователю по-русски;
- новые UI-строки проходят localization guard.

## Проверки

- `python3 -B -c "import ast,pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8'), filename=p) for p in ['gui/windows_core_cli.py','gui/subvost_paths.py']]; print('syntax ok')"`
- `env PYTHONPATH=gui python3 -B -m unittest tests.test_windows_core_helper_contract tests.test_windows_build_chain`
- `env PYTHONPATH=gui python3 -B -m unittest discover -s tests`
- `git diff --check`
- `python3 ~/.agents/skills/owned-text-localization-guard/scripts/markdown_localization_guard.py docs/windows/README-win81-build.md gui/windows_core_cli.py windows/SubvostXrayTun.WinForms/MainForm.cs windows/SubvostXrayTun.WinForms/CoreHelperClient.cs windows/SubvostXrayTun.WinForms/Properties/AssemblyInfo.cs build/windows/build-win81-release.ps1 build/windows/install-win81-build-deps.ps1`
