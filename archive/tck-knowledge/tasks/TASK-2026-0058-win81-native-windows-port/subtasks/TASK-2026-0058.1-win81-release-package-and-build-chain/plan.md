# План задачи TASK-2026-0058.1

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0058.1` |
| Parent ID | `TASK-2026-0058` |
| Версия плана | `1` |
| Дата обновления | `2026-04-27` |

## Цель

Подготовить build chain, которому можно доверять перед интеграцией UI и runtime-кода.

## Планируемые изменения

### Код

- добавить `build/windows/install-win81-build-deps.ps1` или эквивалентный preflight;
- переработать `build/windows/build-win81-x64.ps1` в сторону pin/checksum и понятных ошибок;
- добавить manifest generation для release package;
- добавить tests/static checks для запрета silent fallback.

### Документация

- описать build prerequisites простым языком;
- разделить source build и готовую portable-поставку;
- указать offline-сценарий с локальными архивами.

## Проверки

- PowerShell syntax на Windows;
- проверка контрольных сумм;
- сборка без доступа к сети;
- `python3 -m unittest` для manifest/checksum helpers, если они будут на Python;
- localization guard по новым docs.

## Шаги

- [x] Зафиксировать runtime asset policy.
- [x] Добавить preflight/install deps script.
- [x] Добавить pin/checksum в build script.
- [x] Добавить release manifest.
- [x] Обновить README build-раздел.
- [x] Пройти проверки.

## Фактический результат

- добавлен `build/windows/runtime-assets.win81.json` с pin-ами `Xray-win7-64.zip` и `wintun-0.14.1.zip`;
- добавлен `build/windows/install-win81-build-deps.ps1` для проверки `Python 3.11 x64`, `.NET Framework 4.8` и build-зависимостей;
- добавлен `build/windows/build-win81-release.ps1` с проверкой `SHA256`, режимом без сети и staging runtime-ресурсов;
- добавлен `docs/windows/README-win81-build.md` с простым сценарием preflight/runtime-staging;
- добавлены unit-тесты build-chain policy.
