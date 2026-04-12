---
name: codex-opencode-session-cleaner
description: "Навык очистки старых сессий и вспомогательных сессионных данных Codex и OpenCode с retention по календарным дням. По умолчанию сохраняет данные от начала текущего дня минус два дня, сначала делает dry-run, выводит точный список абсолютных путей и требует отдельного подтверждения для массового удаления."
---

# Очистка сессий Codex / OpenCode

## Цель

Безопасно очистить старые сессии и связанные с ними вспомогательные данные:
- `Codex`: `sessions/`, `archived_sessions/`, `shell_snapshots/`, старые временные хвосты, а также подрезать `session_index.jsonl` и `history.jsonl`
- `OpenCode`: старые `session`-записи из `opencode.db`, связанные файловые артефакты в `storage/`, старые `log/`, `snapshot/`, `tool-output/`

По умолчанию хранить данные начиная с начала дня `today - 2 days` по локальному времени машины.

Пример:
- если сегодня `2026-03-17`, сохраняются данные с `2026-03-15 00:00:00` и новее
- под очистку попадает всё, что старше этого cutoff

## Когда использовать

Используй навык, когда пользователь просит:
- очистить старые сессии `codex`
- очистить старые сессии `opencode`
- освободить место за счёт истории/логов/временных session-артефактов
- сохранить только последние N календарных дней сессий, где по умолчанию нужен режим `today - 2 days`

## Режим работы

Скрипт навыка:
- по умолчанию делает только dry-run
- показывает cutoff, список session ID из `OpenCode`, список абсолютных путей к удалению и `COUNT = N`
- отдельно показывает файлы, которые будут не удаляться, а переписываться (`history.jsonl`, `session_index.jsonl`)
- перед `--apply` требует явного подтверждения: нужно ввести `YES`
- отказывается выполнять `--apply`, если удалений слишком много, пока явно не передан флаг массового подтверждения

## Запуск

Dry-run по обеим системам:

```bash
python3 /home/prog7/MyWorkspace/30-Knowledge/AI/ai-agents-rules-main/skills-global/codex-opencode-session-cleaner/scripts/prune_sessions.py
```

Только `codex`:

```bash
python3 /home/prog7/MyWorkspace/30-Knowledge/AI/ai-agents-rules-main/skills-global/codex-opencode-session-cleaner/scripts/prune_sessions.py --target codex
```

Только `opencode`:

```bash
python3 /home/prog7/MyWorkspace/30-Knowledge/AI/ai-agents-rules-main/skills-global/codex-opencode-session-cleaner/scripts/prune_sessions.py --target opencode
```

Применение после dry-run:

```bash
python3 /home/prog7/MyWorkspace/30-Knowledge/AI/ai-agents-rules-main/skills-global/codex-opencode-session-cleaner/scripts/prune_sessions.py --apply
```

Массовое применение после явного подтверждения пользователя:

```bash
python3 /home/prog7/MyWorkspace/30-Knowledge/AI/ai-agents-rules-main/skills-global/codex-opencode-session-cleaner/scripts/prune_sessions.py --apply --allow-many
```

## Обязательный сценарий

1. Всегда запускать dry-run первым.
2. Всегда показывать пользователю:
   - cutoff-дату и точное правило retention
   - список session ID `OpenCode` к удалению
   - точный список абсолютных путей к удалению
   - `COUNT = N`
3. Если объектов больше 7:
   - не запускать применение без явного подтверждения пользователя
   - только после подтверждения использовать `--apply --allow-many`
4. Если scope неочевиден:
   - сузить через `--target codex` или `--target opencode`
5. После `--apply` показывать итоговую сводку:
   - какой cutoff был применён
   - сколько session ID удалено из `OpenCode`
   - сколько файлов было переписано
   - сколько объектов ФС удалено
6. Не трогать:
   - `auth.json`
   - конфиги (`config.toml`, `opencode.json`, `oh-my-opencode.json`)
   - runtime-зависимости (`node_modules`, `bin/`, `models.json`, package metadata)

## Что делает скрипт

### Codex

- удаляет старые session-файлы в `~/.codex/sessions/YYYY/MM/DD/`
- удаляет старые файлы из `~/.codex/archived_sessions/`
- удаляет старые `shell_snapshots`, привязанные к старым session ID, и старые временные хвосты из `~/.codex/tmp/`
- подрезает `~/.codex/session_index.jsonl` по `updated_at`
- подрезает `~/.codex/history.jsonl` по `ts`

### OpenCode

- выбирает старые session ID из `~/.local/share/opencode/opencode.db` по `time_updated`
- удаляет эти сессии из SQLite с каскадом на связанные таблицы
- удаляет связанные файлы из:
  - `~/.local/share/opencode/storage/session_diff/`
  - `~/.local/share/opencode/storage/agent-usage-reminder/`
  - `~/.local/share/opencode/storage/directory-readme/`
- удаляет старые файлы/каталоги из:
  - `~/.local/share/opencode/log/`
  - `~/.local/share/opencode/snapshot/`
  - `~/.local/share/opencode/tool-output/`
- после удаления делает `VACUUM` и `wal_checkpoint(TRUNCATE)` для базы

## Запрещено

- Не выполнять `--apply` без dry-run в том же контексте задачи
- Не удалять относительными путями
- Не подменять retention без явного запроса пользователя
- Не чистить системные или установочные каталоги `OpenCode`
- Не редактировать произвольные файлы вне перечисленного scope

## Итог

Краткий отчет должен содержать:
- какой cutoff использован
- сколько `OpenCode` session ID под удаление
- сколько файлов будет переписано
- сколько объектов ФС будет удалено
- какие именно пути затронуты
- применялся dry-run или реальное удаление
