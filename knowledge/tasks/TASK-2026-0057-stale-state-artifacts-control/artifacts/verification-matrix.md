# Матрица проверки TASK-2026-0057

## Инварианты и проверки

| Инвариант | Сценарий нарушения | Проверка | Статус |
|-----------|--------------------|----------|--------|
| `INV-1` пассивная диагностика не удаляет файлы | `collect_status` удаляет expired dumps при простом открытии диагностики | Unit-тест `test_collect_status_reports_expired_artifacts_without_deleting_them` | `покрыто` |
| `INV-2` stale state считается stale artifact | State без живого PID/TUN помечается как активный чужой runtime | Unit-тест `test_runtime_artifacts_audit_marks_stale_state_cleanup_available` | `покрыто` |
| `INV-3` live runtime не очищается автоматически | Cleanup удаляет state живого подключения | Service-layer guard в `cleanup_runtime_artifacts`; ручной production smoke | `покрыто` |
| `INV-4` orphan DNS backup очищается только без state/runtime | Backup удаляется при наличии state или живого runtime | Unit-тест `test_cleanup_runtime_artifacts_cleans_stale_state_backup_and_expired_dumps` | `покрыто` |
| `INV-5` retention удаляет только managed ordinary files | Удаляется произвольный `logs/notes.log`, symlink или каталог | Unit-тест `test_retention_cleanup_removes_only_expired_managed_artifacts`; diff review glob-шаблонов | `покрыто` |
| `INV-6` retention default равен `7` и нормализуется | Повреждённая настройка ломает аудит или приводит к нулевому retention | Unit-тесты `test_subvost_store`, `test_native_shell_shared`; diff review clamp `1..365` | `покрыто` |
| `INV-7` диагностика показывает состояние артефактов | Пользователь не видит state/DNS/dumps/cleanup status | Unit-тесты native shell labels; ручной production smoke | `покрыто` |
| `INV-8` диагностика содержит явное cleanup-действие | Кнопка отсутствует в блоке `Файлы и дампы` или не запускает service action | Unit-тест `test_cleanup_artifacts_button_starts_diagnostics_cleanup_action`; worker dispatch action | `покрыто` |
| `INV-9` кнопки и cleanup имеют видимый feedback | Hover/active не отличаются от обычного состояния или после cleanup нет локального статуса | CSS diff review; unit-тест `test_diagnostics_action_feedback_tracks_cleanup_lifecycle`; ручной production smoke | `покрыто` |
| `INV-10` текущий живой state получает no-op сообщение | Cleanup показывает `выполнена частично`, хотя state принадлежит текущему активному подключению | Unit-тест `test_cleanup_runtime_artifacts_reports_noop_for_current_live_state`; ручной UI smoke | `покрыто` |
| `INV-11` нет новых зависимостей и import-направлений | Для cleanup добавлен новый пакет или UI удаляет файлы напрямую | Diff review; `py_compile`; отсутствие изменений package-файлов | `покрыто` |

## Выполненные команды

```bash
env PYTHONPYCACHEPREFIX=/tmp/subvost-pycache python3 -m py_compile gui/subvost_app_service.py gui/gui_server.py gui/native_shell_app.py gui/native_shell_shared.py gui/subvost_store.py
env PYTHONPYCACHEPREFIX=/tmp/subvost-pycache python3 -m unittest tests.test_subvost_app_service tests.test_native_shell_app tests.test_native_shell_shared tests.test_subvost_store
env PYTHONPYCACHEPREFIX=/tmp/subvost-pycache python3 -m unittest tests.test_native_shell_app
env PYTHONPYCACHEPREFIX=/tmp/subvost-pycache python3 -m unittest tests.test_subvost_app_service tests.test_native_shell_app
env PYTHONPYCACHEPREFIX=/tmp/subvost-pycache python3 -m unittest discover tests
git diff --check
python3 .agents/skills/markdown-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/task.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/plan.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/sdd.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/artifacts/verification-matrix.md
python3 ~/.agents/skills/owned-text-localization-guard/scripts/markdown_localization_guard.py knowledge/tasks/registry.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/task.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/plan.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/sdd.md knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/artifacts/verification-matrix.md gui/native_shell_app.py gui/native_shell_shared.py gui/subvost_app_service.py gui/gui_server.py gui/subvost_store.py
bash install-or-update-bundle-dir.sh /home/prog7/MyWorkspace/40-Tools-and-Apps/Apps/subvost-xray-tun
rg -n "cleanup_runtime_artifacts|artifact_retention_days|runtime_state_status|cleanup-artifacts|Очистить служебные файлы|/api/artifacts/cleanup" /home/prog7/MyWorkspace/40-Tools-and-Apps/Apps/subvost-xray-tun/gui /home/prog7/MyWorkspace/40-Tools-and-Apps/Apps/subvost-xray-tun/knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control -S
```

## Результаты

- `py_compile`: `OK`;
- точечные unit-тесты затронутых модулей: `82 tests`, `OK`;
- native GUI unit-тесты после UX-feedback правки: `40 tests`, `OK`;
- service/UI unit-тесты после уточнения no-op сообщения: `61 tests`, `OK`;
- `python3 -m unittest discover tests`: `175 tests`, `OK`;
- `git diff --check`: `OK`;
- guard Markdown-локализации: `OK`;
- guard пользовательских текстов: `OK`;
- repo-specific wrapper `scripts/check-docs-localization.sh`: отсутствует, использован прямой fallback guard-а;
- синхронизация production-каталога: `OK`;
- поиск маркеров в production-каталоге: маркеры cleanup и retention найдены.

## Ручной остаток

- ручной production smoke подтверждён пользователем 2026-04-20: кнопки в `Диагностика → Файлы и дампы` есть, работают, визуальный feedback и no-op сообщение понятны.
