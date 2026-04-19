# Матрица проверки TASK-2026-0056

## Инварианты и проверки

| Инвариант | Сценарий нарушения | Проверка | Статус |
|-----------|--------------------|----------|--------|
| `INV-1` идентификатор владельца не зависит от абсолютного пути | Новый файл состояния продолжает писать `BUNDLE_PROJECT_ROOT` как ключ владельца | Unit-тест `test_runtime_scripts_persist_and_guard_bundle_install_id`; ревью diff блока записи состояния | `покрыто` |
| `INV-2` перенос той же установки не делает подключение чужим | Файл состояния содержит тот же `BUNDLE_INSTALL_ID`, но другую подсказку пути, и классифицируется как чужой | Unit-тест `test_classify_runtime_ownership_prefers_install_id_over_path`; тест запускателя для `restart` при том же `install-id` | `покрыто` |
| `INV-3` разные установки не управляют живым подключением друг друга | `stop` или GUI управляет живым состоянием с чужим `BUNDLE_INSTALL_ID` | Unit-тесты `tests.test_gui_server`, `tests.test_subvost_app_service`; shell-маркеры отказа по `install-id` | `покрыто` |
| `INV-4` новый файл состояния пишет `install-id` и путь только как подсказку | `run` не пишет `BUNDLE_INSTALL_ID` или снова пишет `BUNDLE_PROJECT_ROOT` | Строковые проверки shell-скриптов в `tests.test_gui_server` | `покрыто` |
| `INV-5` устаревший файл состояния без `install-id` поддержан | Старый файл состояния с `BUNDLE_PROJECT_ROOT` больше не классифицируется корректно | Unit-тест резервной проверки пути; сохранён парсинг `BUNDLE_PROJECT_ROOT` | `покрыто` |
| `INV-6` синхронизация production-каталога сохраняет целевую идентичность | Синхронизация копирует `.subvost/install-id` из checkout-а в production | Unit-тест `test_bundle_sync_preserves_target_install_id`; проверка tar exclude; синхронизация production-каталога | `покрыто` |
| `INV-7` контракт GUI-службы использует `install-id` и root | Запускатель переиспользует GUI-службу из старого root или принимает GUI-службу другой установки | Unit-тест запускателя на `install_id`, `match`, `restart`, `mismatch`; status payload содержит `bundle_identity.install_id` | `покрыто` |
| `INV-8` `Перехватить` является явным override, а обычные сценарии защищены | Кнопка остаётся заглушкой или обычный `stop` начинает останавливать живое чужое подключение | Unit-тесты `takeover_runtime`, `on_takeover_requested`, worker-dispatch; shell-маркеры `SUBVOST_FORCE_TAKEOVER` | `покрыто` |
| `INV-9` нет новых зависимостей и import-направлений | Для install-id или перехвата добавлен новый пакет или UI обходит service-layer | Diff review; `py_compile`; отсутствие изменений package-файлов | `покрыто` |

## Выполненные команды

```bash
bash -n lib/subvost-common.sh libexec/run-xray-tun-subvost.sh libexec/stop-xray-tun-subvost.sh libexec/open-subvost-gui.sh libexec/install-or-update-bundle-dir.sh
env PYTHONPYCACHEPREFIX=/tmp/subvost-pycache python3 -m py_compile gui/subvost_app_service.py gui/gui_server.py gui/native_shell_app.py
python3 -m unittest discover tests
git diff --check
python3 .agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/task.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/plan.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/sdd.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/artifacts/verification-matrix.md
python3 ~/.agents/skills/owned-text-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/task.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/plan.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/sdd.md knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/artifacts/verification-matrix.md
bash install-or-update-bundle-dir.sh /home/prog7/MyWorkspace/40-Tools-and-Apps/Apps/subvost-xray-tun
rg -n "BUNDLE_INSTALL_ID|BUNDLE_PROJECT_ROOT_HINT|install-id|server_contract_status|SUBVOST_FORCE_TAKEOVER|takeover_runtime|Перехватить" /home/prog7/MyWorkspace/40-Tools-and-Apps/Apps/subvost-xray-tun/lib /home/prog7/MyWorkspace/40-Tools-and-Apps/Apps/subvost-xray-tun/libexec /home/prog7/MyWorkspace/40-Tools-and-Apps/Apps/subvost-xray-tun/gui -S
```

## Результаты

- `bash -n`: `OK`;
- `py_compile`: `OK`;
- `python3 -m unittest discover tests`: `167 tests`, `OK`;
- `git diff --check`: `OK`;
- локализационные guard-ы: `OK`;
- синхронизация production-каталога: `OK`;
- поиск маркеров в production-каталоге: маркеры `install-id` и перехвата найдены.

## Ручной остаток

- открыть production GUI и проверить обычный start/stop;
- проверить кнопку `Перехватить` в production GUI на живом подключении другой установки;
- перенести production-каталог в другой путь с сохранением `.subvost/install-id` и проверить, что подключение остаётся текущим;
- проверить dev/repo GUI рядом с живым production-подключением: он должен видеть живое чужое подключение и не останавливать его;
- повторить reboot-сценарий на реальной desktop-сессии.
