# Справочник Playwright CLI

Предпочитай wrapper, если `playwright-cli` не установлен глобально:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PWCLI="$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh"
"$PWCLI" doctor
```

Допустимый короткий alias:

```bash
alias pwcli="$PWCLI"
```

`pwcli doctor` должен быть первым шагом в новой среде или после смены sandbox-режима.

## Базовые команды

```bash
pwcli open https://example.com
pwcli close
pwcli snapshot
pwcli click e3
pwcli dblclick e7
pwcli type "search terms"
pwcli press Enter
pwcli fill e5 "user@example.com"
pwcli drag e2 e8
pwcli hover e4
pwcli select e9 "option-value"
pwcli upload ./document.pdf
pwcli check e12
pwcli uncheck e12
pwcli eval "document.title"
pwcli eval "el => el.textContent" e5
pwcli dialog-accept
pwcli dialog-accept "confirmation text"
pwcli dialog-dismiss
pwcli resize 1920 1080
```

## Навигация

```bash
pwcli go-back
pwcli go-forward
pwcli reload
```

## Клавиатура

```bash
pwcli press Enter
pwcli press ArrowDown
pwcli keydown Shift
pwcli keyup Shift
```

## Мышь

```bash
pwcli mousemove 150 300
pwcli mousedown
pwcli mousedown right
pwcli mouseup
pwcli mouseup right
pwcli mousewheel 0 100
```

## Сохранение артефактов

```bash
pwcli screenshot
pwcli screenshot e5
pwcli pdf
```

## Вкладки

```bash
pwcli tab-list
pwcli tab-new
pwcli tab-new https://example.com/page
pwcli tab-close
pwcli tab-close 2
pwcli tab-select 0
```

## DevTools и диагностика

```bash
pwcli console
pwcli console warning
pwcli network
pwcli run-code "await page.waitForTimeout(1000)"
pwcli tracing-start
pwcli tracing-stop
```

## Сессии

Изолируй работу именованной сессией:

```bash
pwcli -s=todo open https://demo.playwright.dev/todomvc
pwcli -s=todo snapshot
```

Либо задай окружение один раз:

```bash
export PLAYWRIGHT_CLI_SESSION=todo
pwcli open https://demo.playwright.dev/todomvc
```

## Поведение wrapper

- Если `playwright-cli` уже есть в `PATH`, wrapper использует его напрямую.
- Если в проекте есть `./node_modules/.bin/playwright-cli`, wrapper предпочитает этот бинарь.
- Если пакет есть только в офлайн-кэше npm, wrapper использует `npx --offline`.
- Если локального runtime нет, wrapper либо делает ограниченный по времени bootstrap, либо останавливается с понятной ошибкой.
- В Codex sandbox browser-level команды по умолчанию блокируются до запуска браузера. Для осознанного обхода нужен `PWCLI_ALLOW_CODEX_SANDBOX=1`, но это не гарантирует успешный launch.
