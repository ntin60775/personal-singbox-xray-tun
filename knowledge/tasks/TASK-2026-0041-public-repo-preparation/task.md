# Карточка задачи TASK-2026-0041

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0041` |
| Parent ID | `—` |
| Уровень вложенности | `0` |
| Ключ в путях | `TASK-2026-0041` |
| Технический ключ для новых именуемых сущностей | `public-repo-preparation` |
| Краткое имя | `public-repo-preparation` |
| Статус | `ждёт пользователя` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `main` |
| Дата создания | `2026-04-05` |
| Дата обновления | `2026-04-05` |

## Цель

Подготовить репозиторий к публичной публикации как first-class public repo: убрать из текущего дерева и из истории Git приватные пути, персональные deployment-ссылки, operator-specific runtime-данные и добавить публичный repo-hygiene слой с лицензией, процессом вклада и базовыми community-policy файлами.

## Подсказка по статусу

Использовать только одно из значений:

- `черновик`
- `готова к работе`
- `в работе`
- `на проверке`
- `ждёт пользователя`
- `заблокирована`
- `завершена`
- `отменена`

## Границы

### Входит

- аудит текущего `HEAD` и всей истории Git на предмет приватных артефактов;
- санитизация публичной документации, шаблонов конфигурации и desktop-артефактов;
- переписывание истории Git для удаления уже закоммиченных приватных данных;
- добавление public-facing файлов репозитория: лицензия, правила вклада, security policy, issue/PR templates;
- фиксация остаточных рисков и проверки результата.

### Не входит

- публикация репозитория на конкретной Git-hosting площадке;
- ручной сетевой smoke реального VPN-подключения после обезличивания шаблонов.

## Контекст

- источник постановки: запрос пользователя подготовить репозиторий к переводу в публичный режим и проверить не только `HEAD`, но и всю историю Git;
- связанная бизнес-область: публикация персонального Linux bundle как безопасного public-repo;
- ограничения и зависимости: в worktree уже есть незакоммиченные изменения, поэтому историю нужно переписывать без потери текущего локального состояния;
- основной контекст сессии: `новая задача`

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | Могут обновиться shell-артефакты и desktop launcher для удаления жёстко зашитых локальных путей |
| Конфигурация / схема данных / именуемые сущности | Трacked-шаблон `xray` и публичные примеры станут provider-agnostic |
| Интерфейсы / формы / страницы | GUI не меняется функционально |
| Интеграции / обмены | Из документации и истории убираются личные subscription URL и operator-specific endpoints |
| Документация | README, public-facing process-файлы, knowledge-артефакты и реестр задач синхронизируются под публичную публикацию |

## Связанные материалы

- основной каталог задачи: `knowledge/tasks/TASK-2026-0041-public-repo-preparation/`
- файл плана: `plan.md`
- пользовательские материалы: запрос подготовить репозиторий к публичной публикации с очисткой истории Git
- связанные коммиты / PR / ветки: `—`
- связанные операции в `knowledge/operations/`, если есть: `—`

## Текущий этап

Локальная очистка и public-facing polish завершены: рабочее дерево санитизировано, локальные `refs/heads/*` уже были переписаны через `git-filter-repo`, а целевые private-маркеры больше не находятся ни в `HEAD`, ни в истории локальных веток. Поверх этого собран минимально полноценный публичный слой репозитория: `LICENSE` c лицензией `MIT`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, GitHub issue templates и PR template, а `README.md` переписан под внешний сценарий чтения.

Локальные изменения уже закоммичены и отправлены в `origin/main` commit-ом `66f83ce` (`docs: add public repo hygiene`). Задача остаётся в состоянии `ждёт пользователя`, потому что следующий шаг уже внешний: проверить финальное позиционирование на GitHub и перевести репозиторий в публичный режим на стороне hosting-площадки.

## Стратегия проверки

### Покрывается кодом или тестами

- `bash -n *.sh`
- `bash -n libexec/*.sh`
- `bash -n lib/*.sh`
- `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py gui/embedded_webview.py`
- `python3 -m unittest tests.test_subvost_parser tests.test_subvost_store tests.test_subvost_runtime tests.test_gui_server tests.test_embedded_webview`
- поисковые проверки по `git grep` и `rg` на приватные маркеры в `HEAD` и истории
- `python3 ~/.agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py README.md CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md .github/pull_request_template.md knowledge/tasks/TASK-2026-0041-public-repo-preparation/task.md knowledge/tasks/TASK-2026-0041-public-repo-preparation/plan.md knowledge/tasks/registry.md`

### Остаётся на ручную проверку

- финальный human-review README и public-facing файлов уже на конкретной площадке публикации;
- перевод репозитория в публичный режим на стороне GitHub.

## Критерии готовности

- в текущем `HEAD` нет приватных путей, личных subscription URL и operator-specific runtime-данных;
- история Git очищена от тех же маркеров;
- README и public-facing repo-файлы описывают generic/public workflow;
- task-артефакты отражают фактические изменения и остаточные риски.

## Итог

Локальный public-cleanup завершён в два этапа. Сначала текущее рабочее состояние было разнесено через `git-janitor` на две topic-ветки: одна для runtime/UI follow-up по `TASK-2026-0037.4`, вторая для public-packaging, новых task-records и task-контура подготовки к публикации. После атомарных коммитов обе ветки слиты обратно в `main`, а рабочее дерево приведено к чистому состоянию.

Затем локальные `refs/heads/*` были переписаны через `git-filter-repo` с backup-репозиторием в `/tmp/public-rewrite-backup-WoCoGg/repo.git`. В rewrite вошли path-rename для legacy task/plan-путей и text replacements для старых private-host/site-маркеров, абсолютных пользовательских путей и legacy desktop-label/filename. В результате локальная branch-history очищена от целевого audit-набора приватных маркеров этой задачи.

После этого репозиторий доведён до публичного public-facing состояния: по явному решению пользователя выбрана лицензия `MIT`, добавлены `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.github/ISSUE_TEMPLATE/*`, `.github/pull_request_template.md`, а `README.md` усилен под внешний читательский сценарий, публичные ожидания по вкладу и security-disclosure.

Локально пройдены: `git grep` по `$(git rev-list --branches)`, `rg` по рабочему дереву, `bash -n *.sh`, `bash -n libexec/*.sh`, `bash -n lib/*.sh`, `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py gui/embedded_webview.py`, `python3 -m unittest tests.test_subvost_parser tests.test_subvost_store tests.test_subvost_runtime tests.test_gui_server tests.test_embedded_webview`, `python3 -m json.tool xray-tun-subvost.json` и адресные прогоны `markdown-localization-guard`.

Остаточные действия и риски: локальный репозиторий и `origin/main` синхронизированы, public-facing polish уже отправлен в удалённый `main`. Пользователь должен вручную перевести репозиторий в публичный режим на стороне GitHub и проверить, как README, issue templates и policy-файлы выглядят уже на выбранной Git-hosting площадке.
