---
name: "playwright"
description: "Используй, когда нужно автоматизировать реальный браузер из терминала через `playwright-cli` или локальный wrapper, без перехода к test specs по умолчанию."
---

# Навык Playwright CLI

Навык для browser-level автоматизации через `playwright-cli`.
Основной способ запуска: wrapper `playwright_cli.sh`.
Он больше не должен зависать на сетевом `npx` bootstrap: сначала делает локальный preflight, затем ищет локально доступный runtime и только в самом конце пробует ограниченный по времени сетевой bootstrap.

По умолчанию не переходи к `@playwright/test`, если пользователь явно не просил именно тестовые файлы.

## Обязательный preflight

Перед первым реальным действием проверь среду:

```bash
command -v node >/dev/null 2>&1
command -v npm >/dev/null 2>&1
command -v npx >/dev/null 2>&1
```

Затем настрой путь к wrapper и сразу запусти диагностику:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PWCLI="$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh"
"$PWCLI" doctor
```

`doctor` проверяет:
- есть ли `playwright-cli` глобально;
- есть ли project-local бинарь `./node_modules/.bin/playwright-cli`;
- есть ли офлайн-кэш для `@playwright/cli`;
- не запущены ли вы внутри Codex sandbox, где browser launch обычно не работает;
- будет ли wrapper пытаться сетевой bootstrap или остановится сразу.

Если `npx` отсутствует, остановись и попроси пользователя установить Node.js/npm.

## Как wrapper выбирает runtime

Wrapper использует такой порядок:

1. Глобальный `playwright-cli` из `PATH`.
2. Локальный бинарь проекта `./node_modules/.bin/playwright-cli`.
3. Офлайн-кэш npm для `@playwright/cli`.
4. Ограниченный по времени сетевой bootstrap через `npx`.

Если запуск идёт из Codex sandbox, wrapper по умолчанию останавливается до старта browser-level команды и объясняет, что нужно сделать дальше.
Это лучше, чем бесконечно ждать `npx` или ловить падение Chromium уже после bootstrap.

## Ограничение Codex Sandbox

Для browser-level smoke и интерактивной автоматизации не запускай этот workflow из ограниченного Codex sandbox.
Практический режим для таких задач:

```bash
codex --sandbox danger-full-access
```

Если нужно сознательно попробовать запуск из sandbox несмотря на предупреждение, можно временно разрешить это так:

```bash
export PWCLI_ALLOW_CODEX_SANDBOX=1
```

Используй override только когда понимаешь риск: wrapper перестанет блокировать launch, но браузер всё равно может упасть на уровне sandbox.

## Быстрый старт

```bash
"$PWCLI" doctor
"$PWCLI" open https://playwright.dev --headed
"$PWCLI" snapshot
"$PWCLI" click e15
"$PWCLI" type "Playwright"
"$PWCLI" press Enter
"$PWCLI" screenshot
```

Если в проекте уже стандартизован глобальный install, это тоже допустимо:

```bash
npm install -g @playwright/cli@latest
playwright-cli --help
```

## Базовый цикл работы

1. Открыть страницу.
2. Сделать `snapshot`, чтобы получить стабильные ссылки на элементы.
3. Выполнить действие по свежим ref-id.
4. Повторно сделать `snapshot` после навигации или серьёзного изменения DOM.
5. Снять артефакты: `screenshot`, `pdf`, `tracing-stop` и т.д.

Минимальный цикл:

```bash
"$PWCLI" open https://example.com
"$PWCLI" snapshot
"$PWCLI" click e3
"$PWCLI" snapshot
```

## Когда делать snapshot заново

Повторный `snapshot` нужен после:

- навигации;
- кликов, которые меняют интерфейс;
- открытия или закрытия модалок и меню;
- переключения вкладок.

Если ref-id перестал работать, сначала обнови `snapshot`, а не пытайся обходить это `run-code`.

## Рекомендуемые сценарии

### Заполнение формы

```bash
"$PWCLI" open https://example.com/form
"$PWCLI" snapshot
"$PWCLI" fill e1 "user@example.com"
"$PWCLI" fill e2 "password123"
"$PWCLI" click e3
"$PWCLI" snapshot
```

### Диагностика проблемного UI flow

```bash
"$PWCLI" open https://example.com --headed
"$PWCLI" tracing-start
# ...действия...
"$PWCLI" tracing-stop
```

### Работа с несколькими вкладками

```bash
"$PWCLI" -s=demo tab-new https://example.com
"$PWCLI" -s=demo tab-list
"$PWCLI" -s=demo tab-select 0
"$PWCLI" -s=demo snapshot
```

## References

Открывай только то, что реально нужно:

- `references/cli.md` для справочника по командам;
- `references/workflows.md` для практических сценариев и troubleshooting.

## Guardrails

- Всегда делай `snapshot` перед использованием `e12`, `e24` и других ref-id.
- Повторяй `snapshot`, если refs устарели.
- Предпочитай явные команды вместо `eval` и `run-code`, пока это возможно.
- Если нет свежего `snapshot`, используй плейсхолдеры вроде `eX` и объясняй, почему точный ref пока неизвестен.
- Для визуальной проверки используй `--headed`.
- Артефакты в этом репозитории складывай в `output/playwright/`, не создавай новые верхнеуровневые папки.
- Для диагностики среды первым делом запускай `"$PWCLI" doctor`.
