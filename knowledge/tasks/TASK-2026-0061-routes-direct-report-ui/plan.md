# План задачи TASK-2026-0061

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0061` |
| Parent ID | `—` |
| Версия плана | `1` |
| Связь с SDD | `sdd.md` |
| Дата обновления | `2026-04-28` |

## Цель

Реализовать отдельную вкладку `Маршруты` с read-only отчётом `Прямые маршруты`, который показывает источники direct-правил, фактический runtime и конфликты приоритетов.

## Границы

### Входит

- backend extractor/report для template, active profile и runtime;
- API/status payload для UI;
- web UI с верхними вкладками;
- GTK UI с вкладкой `Маршруты` и `Настройки`;
- тесты, консультационное ревью Kimi CLI и живой smoke через Playwright.

### Не входит

- управление direct-правилами;
- новый формат routing-профилей;
- изменение текущего порядка применения runtime rules.

## Планируемые изменения

### Код

- добавить функции извлечения direct-правил из Xray config;
- добавить функцию построения сводного direct-report;
- добавить конфликтный анализ по `template > профиль > catch-all`;
- расширить service/status payload;
- обновить web UI и GTK UI.

### Конфигурация / схема данных / именуемые сущности

- добавить read-only report shape в runtime/status payload;
- не менять persisted store schema без отдельной необходимости;
- не менять `xray-tun-subvost.json` semantics.

### Документация

- обновить task-local evidence после Kimi-review и Playwright smoke.

## Зависимости и границы

### Новые runtime/package зависимости

- `нет`

### Изменения import/module-связей и зависимостей между модулями

- ожидаемо: `subvost_routing` или отдельный helper становится источником direct-report builder;
- `subvost_app_service` / `gui_server` отдают готовый report, чтобы UI не парсил Xray JSON самостоятельно;
- UI-слои только отображают report.

### Границы, которые должны остаться изолированными

- routing behavior и порядок Xray rules не меняются;
- report не должен быть источником runtime-конфига;
- `Подписки` остаются экраном управления подписками, а не диагностическим отчётом по маршрутам.

### Критический функционал

- пользователь видит все прямые маршруты без чтения JSON;
- пользователь понимает источник правила и итоговый победивший runtime;
- настройки доступны как верхняя вкладка.

### Основной сценарий

- пользователь открывает `Маршруты`;
- видит сводку и блок `Прямые маршруты`;
- раскрывает источники `template`, `профиль`, `runtime`;
- при конфликте видит inline-пояснение, какое правило победило.

### Исходный наблюдаемый симптом

- прямые маршруты сейчас рассыпаны между template, store и runtime JSON; в интерфейсе нет единого отчёта.

## Риски и зависимости

- конфликтный анализ может быть неточным, если пытаться доказать все возможные пересечения CIDR/geosite/domain без ограничений;
- для первого релиза допустим conservative conflict detector: точные совпадения и очевидные CIDR/private coverage, остальное показывать как потенциальное перекрытие;
- web UI и GTK UI сейчас не полностью совпадают по навигации, поэтому task должна привести обе поверхности к верхним вкладкам.

## Связь с SDD

- см. `sdd.md`;
- матрица покрытия: `artifacts/verification-matrix.md`.

## Проверки

### Что можно проверить кодом или тестами

- `python3 -S -m unittest tests.test_subvost_routing tests.test_subvost_runtime tests.test_subvost_store tests.test_subvost_app_service tests.test_gui_server tests.test_native_shell_app -q`
- `python3 -S -m json.tool xray-tun-subvost.json`
- `python3 /home/prog7/.agents/skills/owned-text-localization-guard/scripts/markdown_localization_guard.py <изменённые task-docs и UI-файлы>`
- `git diff --check`
- Kimi CLI review command с финальным макетом;
- Playwright/browser smoke с screenshots/artifacts.

### Что остаётся на ручную проверку

- визуальная читаемость длинных списков direct-групп;
- пользовательская понятность conflict/priority explanation.

## Шаги

- [x] Спроектировать report shape и invariants
- [x] Реализовать extractor/report/conflict analyzer
- [x] Расширить service/status payload
- [x] Перевести web UI на верхние вкладки и добавить `Маршруты`
- [x] Перенести `Настройки` в верхнюю вкладку GTK UI и добавить `Маршруты`
- [x] Прогнать Kimi CLI review финального макета
- [x] Прогнать unit-тесты, localization guard и diff check
- [x] Прогнать Playwright/browser smoke и приложить evidence

## Критерии завершения

- task invariants из `artifacts/verification-matrix.md` покрыты проверками;
- `Маршруты` работает как отдельная верхняя вкладка;
- `Прямые маршруты` показывает source и outcome без изменения runtime behavior;
- финальные evidence приложены в `artifacts/`.
