# Добавление санитизированного xray-конфига в репозиторий

- Дата: 2026-03-29
- Статус: done
- Источник: запрос пользователя сделать `xray-tun-subvost.json` частью git-репозитория без публикации реальных `id`, `PublicKey` и `shortId`

## Цель

Убрать `xray-tun-subvost.json` из `.gitignore` и добавить в репозиторий sanitized-версию файла, чтобы структура проекта оставалась полной, но реальные `id`, `PublicKey` и `shortId` не хранились в git.

Ожидаемый результат: `xray-tun-subvost.json` появляется в репозитории как шаблон с актуальными несекретными параметрами узла и явными placeholders для `id`, `publicKey` и `shortId`, а `README.md` и `AGENTS.md` сразу подсказывают, какие поля оператор и ИИ должны дозаполнить локально.

## Изменения

- Удалить `/xray-tun-subvost.json` из `.gitignore`.
- Добавить в корень репозитория `xray-tun-subvost.json` с актуальным адресом, `serverName` и xhttp-параметрами, но с placeholders вместо реальных `id`, `publicKey` и `shortId`.
- Обновить `README.md` и `AGENTS.md`, чтобы пользователь и ИИ сразу видели список обязательных для локального дозаполнения полей.
- Зафиксировать это решение в плане репозитория.

## Проверки

- `python3 -m json.tool xray-tun-subvost.json`
- `rg -n 'REPLACE_WITH_REALITY_(UUID|PUBLIC_KEY|SHORT_ID)' xray-tun-subvost.json README.md AGENTS.md`
- `git check-ignore -v xray-tun-subvost.json`
- `git status --short`

## Допущения

- Реальные `id`, `PublicKey` и `shortId` остаются operator-managed и должны подставляться локально после клонирования или перед запуском bundle.
- Из-за намеренно санитизированных `id`, `PublicKey` и `shortId` полный runtime-smoke `xray run -test` для этого tracked-файла не является критерием успеха в этой задаче.

## Итог

`/xray-tun-subvost.json` удалён из `.gitignore`, поэтому файл теперь виден git и может жить в репозитории как часть структуры bundle.

В корень проекта добавлен `xray-tun-subvost.json` с актуальными несекретными параметрами рабочего узла: адресом `203.0.113.10`, `serverName` и xhttp-параметрами. Поля `id`, `publicKey` и `shortId` намеренно заменены на placeholders `REPLACE_WITH_REALITY_UUID`, `REPLACE_WITH_REALITY_PUBLIC_KEY` и `REPLACE_WITH_REALITY_SHORT_ID`, поэтому перед реальным запуском bundle оператор должен подставить локальные значения.

`README.md` и `AGENTS.md` дополнительно фиксируют точные JSON-пути и имена placeholders, чтобы и пользователь, и ИИ не путали tracked-шаблон с локальным runtime-конфигом.

Проверки завершены так: `python3 -m json.tool xray-tun-subvost.json` проходит, `git check-ignore -v xray-tun-subvost.json` возвращает `exit=1` и подтверждает, что файл больше не игнорируется, а `git status --short` показывает ожидаемые изменения `.gitignore`, нового `xray-tun-subvost.json`, документации и плана. Остаточный риск: tracked-файл без реальных `id`, `PublicKey` и `shortId` не является готовым runtime-конфигом и используется как санитизированный шаблон для репозитория.
