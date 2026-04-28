# Карточка задачи TASK-2026-0061

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0061` |
| Parent ID | `—` |
| Уровень вложенности | `0` |
| Ключ в путях | `TASK-2026-0061` |
| Технический ключ для новых именуемых сущностей | `routes-direct-report-ui` |
| Краткое имя | `routes-direct-report-ui` |
| Человекочитаемое описание | `Добавить вкладку Маршруты с read-only отчётом Прямые маршруты по template, routing-профилю, runtime и конфликтам` |
| Статус | `реализация` |
| Приоритет | `высокий` |
| Ответственный | `не назначен` |
| Ветка | `task/task-2026-0061-routes-direct-report-ui` |
| Требуется SDD | `да` |
| Статус SDD | `создан` |
| Ссылка на SDD | `sdd.md` |
| Дата создания | `2026-04-28` |
| Дата обновления | `2026-04-28` |

## Цель

Добавить отдельную верхнюю вкладку `Маршруты`, где пользователь явно видит, какие адреса, домены и группы идут напрямую, минуя VPN, из какого источника пришло каждое правило и какое правило фактически победило в runtime.

## Границы

### Входит

- read-only report builder для правил прямого маршрута из template `xray-tun-subvost.json`;
- read-only report builder для direct-части активного routing-профиля;
- read-only report builder для фактически сгенерированного runtime-конфига;
- анализ конфликтов с учётом порядка `template > профиль > catch-all`;
- web UI с верхними вкладками вместо sidebar;
- native GTK UI: отдельная вкладка `Маршруты`;
- перенос `Настройки` из отдельной кнопки в верхнюю вкладку;
- русские пользовательские тексты: основной блок `Прямые маршруты`, подзаголовок `Адреса и группы, которые идут напрямую, минуя VPN`;
- консультационный дизайн-review через Kimi CLI перед финальным UI;
- browser/live smoke через локальный project-skill `playwright-interactive` после реализации.

### Не входит

- редактирование правил прямого маршрута;
- сохранение пользовательских исключений;
- изменение semantics маршрутизации;
- изменение формата импортируемых Happ/routing-профилей;
- изменение источника `GeoIP/GeoSite`.

## Контекст

- источник постановки: пользователь хочет явно видеть все direct-исключения в интерфейсе приложения;
- связанная бизнес-область: VPN/TUN routing visibility, diagnostic UX, split-routing observability;
- ограничения и зависимости: первый релиз только read-only; редактирование правил является отдельной задачей;
- исходный наблюдаемый симптом / лог-маркер: прямые маршруты сейчас видны только через `xray-tun-subvost.json`, `store.json`, `generated-xray-config.json` и `active-runtime-xray-config.json`;
- основной контекст сессии: `TASK-2026-0060` зафиксировал локальные project-skills и Kimi CLI review gate.

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | builder/extractor direct-report, status/store payload, runtime report surface |
| Конфигурация / схема данных / именуемые сущности | новая read-only report shape в API payload; runtime config semantics не меняется |
| Интерфейсы / формы / страницы | web и GTK: верхние вкладки, новая вкладка `Маршруты`, `Настройки` как вкладка |
| Интеграции / обмены | консультационный `kimi` CLI и live browser check через локальный project-skill `playwright-interactive` |
| Документация | SDD, verification matrix и task-local evidence |

## Связанные материалы

- основной каталог задачи: `knowledge/tasks/TASK-2026-0061-routes-direct-report-ui/`
- файл плана: `plan.md`
- файл SDD: `sdd.md`
- файл verification matrix: `artifacts/verification-matrix.md`
- вход дизайн-ревью: `knowledge/tasks/TASK-2026-0060-project-local-skills-ignore-and-kimi-review/artifacts/kimi-design-review.md`
- локальные project-skills: `.agents/skills/ui-ux-pro-max`, `.agents/skills/playwright-interactive`

## Контур публикации

| Unit ID | Назначение | Head | Base | Host | Тип публикации | Статус | URL | Merge commit | Cleanup |
|---------|------------|------|------|------|----------------|--------|-----|--------------|---------|
| `—` | — | `—` | `—` | `none` | `none` | `planned` | `—` | `—` | `не требуется` |

## Текущий этап

Реализация выполнена: backend report, web/GTK UI, Kimi review и browser smoke готовы; остаются финальные проверки и commit.

## Стратегия проверки

### Покрывается кодом или тестами

- `python3 -S -m unittest tests.test_subvost_routing tests.test_subvost_runtime tests.test_subvost_store tests.test_subvost_app_service tests.test_gui_server tests.test_native_shell_app -q`
- `python3 -S -m unittest tests.test_subvost_routing tests.test_subvost_runtime -q`
- `python3 -S -m json.tool xray-tun-subvost.json`
- `python3 /home/prog7/.agents/skills/owned-text-localization-guard/scripts/markdown_localization_guard.py <изменённые task-docs и UI-файлы>`
- `git diff --check`
- Kimi CLI consultation gate для финального макета
- Playwright/browser smoke для вкладки `Маршруты`

### Остаётся на ручную проверку

- финальная визуальная оценка вкладки `Маршруты` в desktop viewport;
- проверка, что пользователь без чтения JSON понимает: что идёт напрямую, почему и какой источник победил.

## Критерии готовности

- верхняя навигация содержит `Подключение`, `Подписки`, `Маршруты`, `Диагностика`, `Настройки`;
- `Подписки` больше не содержит основной routing-report;
- вкладка `Маршруты` показывает `Прямые маршруты` и подзаголовок про обход VPN;
- report различает `template`, активный профиль и итоговый runtime;
- report показывает inline-конфликты и итоговое победившее правило;
- runtime routing behavior не меняется;
- новые пользовательские строки проходят локализационный guard;
- Kimi CLI и Playwright/live smoke зафиксированы в artifacts.

## Итоговый список ручных проверок

- открыть вкладку `Маршруты` и проверить, что блок `Прямые маршруты` не смешан с `Подписками`;
- проверить состояние с активным профилем `SubVostVPN`;
- проверить состояние без активного routing-профиля;
- проверить длинный список `geosite:*` / `geoip:*` на читаемость и отсутствие переполнения;
- проверить inline-конфликт, если тестовый fixture создаёт перекрытие template/profile.

## Итог

Реализация добавила read-only `direct_report` в status payload, верхнюю вкладку `Маршруты` в Web/GTK, вкладку `Настройки`, inline-конфликты и evidence-артефакты Kimi/Playwright.
