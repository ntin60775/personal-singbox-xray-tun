# Браузерный smoke через Playwright TASK-2026-0061

## Среда

- backend-адрес: `http://127.0.0.1:18421`
- браузер: Google Chrome через Playwright `1.59.1`
- Playwright установлен во временный каталог `/tmp/subvost-playwright-NNwo4s`, без изменения project dependencies.

## Desktop-окно

- размер viewport: `1366x900`
- открыта вкладка `Маршруты`;
- видимый pane: `view-routes`;
- заголовок экрана: `Маршруты`;
- заголовок отчёта: `Прямые маршруты`;
- badge отчёта: `Без конфликтов`;
- строк direct-report: `62`;
- заголовок правой панели: `Профиль маршрутизации`;
- `#view-connection #panel-routing`: `false`.

Скриншот:

```text
knowledge/tasks/TASK-2026-0061-routes-direct-report-ui/artifacts/playwright-routes-tab.png
```

## Узкий viewport

- размер viewport: `820x900`
- открыта вкладка `Маршруты`;
- видимый pane: `view-routes`;
- горизонтальное переполнение документа: `false`.

Скриншот:

```text
knowledge/tasks/TASK-2026-0061-routes-direct-report-ui/artifacts/playwright-routes-tab-820.png
```

## Вкладка настроек

- открыта вкладка `Настройки`;
- видимый pane: `view-settings`;
- кнопка файлового логирования: `Включить`.
