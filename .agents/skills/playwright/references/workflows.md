# Практические workflow для Playwright CLI

Используй wrapper и делай `snapshot` часто.
Предполагается, что `PWCLI` уже задан, а `pwcli` это alias для `"$PWCLI"`.

Перед первым browser-level сценарием в новой среде:

```bash
pwcli doctor
```

Если `doctor` показывает Codex sandbox, не трать время на browser smoke в этой сессии.
Перезапусти Codex с `--sandbox danger-full-access`.

В этом репозитории складывай артефакты в `output/playwright/<label>/`.

## Стандартный цикл

```bash
pwcli open https://example.com
pwcli snapshot
pwcli click e3
pwcli snapshot
```

## Отправка формы

```bash
pwcli open https://example.com/form --headed
pwcli snapshot
pwcli fill e1 "user@example.com"
pwcli fill e2 "password123"
pwcli click e3
pwcli snapshot
pwcli screenshot
```

## Извлечение данных

```bash
pwcli open https://example.com
pwcli snapshot
pwcli eval "document.title"
pwcli eval "el => el.textContent" e12
```

## Диагностика UI-проблем

После воспроизведения ошибки собери консоль и сеть:

```bash
pwcli console warning
pwcli network
```

Если нужен подробный след выполнения:

```bash
pwcli tracing-start
# воспроизвести проблему
pwcli tracing-stop
pwcli screenshot
```

## Изоляция по сессиям

```bash
pwcli -s=marketing open https://example.com
pwcli -s=marketing snapshot
pwcli -s=checkout open https://example.com/checkout
```

Или так:

```bash
export PLAYWRIGHT_CLI_SESSION=checkout
pwcli open https://example.com/checkout
```

## Конфиг-файл

По умолчанию CLI читает `playwright-cli.json` из текущего каталога.
Если нужен другой файл, используй `--config`.

Минимальный пример:

```json
{
  "browser": {
    "launchOptions": {
      "headless": false
    },
    "contextOptions": {
      "viewport": { "width": 1280, "height": 720 }
    }
  }
}
```

## Разбор проблем

- Если ref-id не сработал, сначала повтори `pwcli snapshot`.
- Если страница выглядит неправильно, открой заново с `--headed` и при необходимости измени размер окна.
- Если сценарий зависит от прошлого состояния, зафиксируй отдельную `-s=<имя>`.
- Если wrapper пишет, что локальный runtime отсутствует, установи `@playwright/cli` один раз вне sandbox или добавь project-local dependency.
- Если wrapper пишет, что текущий Codex sandbox блокирует browser-level команды, не обходи это вслепую: либо перезапусти Codex без sandbox, либо ставь `PWCLI_ALLOW_CODEX_SANDBOX=1` только для осознанной диагностики.
