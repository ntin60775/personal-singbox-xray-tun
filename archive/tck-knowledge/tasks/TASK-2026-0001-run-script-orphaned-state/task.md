# TASK-2026-0001 — Исправление обработки orphaned state в run-скрипте

**ID задачи:** TASK-2026-0001
**Краткое имя:** orphaned-state-run-script-fix
**Человекочитаемое описание:** Исправлена ошибка, при которой run-скрипт (`libexec/run-xray-tun-subvost.sh`) не проверял, жив ли runtime, при наличии state-файла текущей установки bundle. Теперь orphaned state (мёртвый PID, отсутствующий TUN-интерфейс) корректно игнорируется, и запуск продолжается.

**Статус:** completed
**Ветка:** main
**Создана:** 2026-04-30

## Проблема

При наличии orphaned state-файла текущей установки (например, после некорректного завершения работы через `pkexec`/`sudo`) run-скрипт выходил с ошибкой:

```
Обнаружен файл состояния прошлого запуска текущей установки bundle: /home/prog7/.xray-tun-subvost.state
Сначала выполни /home/prog7/.../stop-xray-tun-subvost.sh
```

При этом:
- Процесс Xray (PID из state-файла) уже не существовал
- TUN-интерфейс `tun0` уже не существовал
- Файл состояния принадлежал `root:root` (предыдущий запуск был с повышенными привилегиями)

## Причина

В `libexec/run-xray-tun-subvost.sh` в блоках, где `BUNDLE_INSTALL_ID` совпадал с текущей установкой, **отсутствовала** проверка `legacy_state_runtime_is_live`. Скрипт безусловно выходил с `exit 1`, не проверяя, жив ли runtime.

Сравнение со `stop-xray-tun-subvost.sh`:
- В stop-скрипте проверка `legacy_state_runtime_is_live` была реализована корректно
- В run-скрипте она отсутствовала для двух блоков:
  1. `BUNDLE_INSTALL_ID` совпадает (строки 568–572 оригинала)
  2. `BUNDLE_PROJECT_ROOT` совпадает, `BUNDLE_INSTALL_ID` пуст (строки 596–600 оригинала)

## Исправление

Добавлена проверка `legacy_state_runtime_is_live` в оба блока run-скрипта:

```bash
# Блок 1: BUNDLE_INSTALL_ID совпадает
else
  if legacy_state_runtime_is_live "$STATE_FILE"; then
    echo "Обнаружен файл состояния прошлого запуска текущей установки bundle: $STATE_FILE" >&2
    echo "Сначала выполни ${SUBVOST_STOP_WRAPPER}" >&2
    exit 1
  fi

  echo "Обнаружен устаревший файл состояния прошлого запуска текущей установки bundle: $STATE_FILE" >&2
  echo "Живой процесс по этому файлу состояния не найден, новый запуск перезапишет устаревшее состояние." >&2
fi

# Блок 2: BUNDLE_PROJECT_ROOT совпадает
else
  if legacy_state_runtime_is_live "$STATE_FILE"; then
    echo "Обнаружен файл состояния прошлого запуска текущего bundle: $STATE_FILE" >&2
    echo "Сначала выполни ${SUBVOST_STOP_WRAPPER}" >&2
    exit 1
  fi

  echo "Обнаружен устаревший файл состояния прошлого запуска текущего bundle: $STATE_FILE" >&2
  echo "Живой процесс по этому файлу состояния не найден, новый запуск перезапишет устаревшее состояние." >&2
fi
```

## Изменённые файлы

- `libexec/run-xray-tun-subvost.sh` — добавлена проверка `legacy_state_runtime_is_live` для orphaned state текущей установки

## Проверка

1. Orphaned state текущей установки (мёртвый PID, нет TUN):
   - Run-скрипт продолжает запуск ✅
2. Живой state текущей установки:
   - Run-скрипт требует stop ✅
3. Orphaned state чужой установки:
   - Уже работало корректно ✅
4. Живой state чужой установки:
   - Уже работало корректно ✅

## Ручные проверки

- [x] Запуск GUI с orphaned state-файлом (после исправления run-скрипта)
- [ ] Полный интеграционный тест через GUI (start → stop → start)

## Контур публикации

- **Host:** none
- **Тип публикации:** none
- **Статус:** local

---

## Ссылки

- `libexec/run-xray-tun-subvost.sh`
- `libexec/stop-xray-tun-subvost.sh`
- `gui/subvost_app_service.py`
- `gui/native_shell_app.py`
