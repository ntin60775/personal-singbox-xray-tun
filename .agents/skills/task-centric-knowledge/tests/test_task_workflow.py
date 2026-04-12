from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_SCRIPT = ROOT / "scripts" / "task_workflow.py"
DEFAULT_HUMAN_DESCRIPTION = object()


def load_module(module_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


workflow_module = load_module("task_centric_knowledge_task_workflow", WORKFLOW_SCRIPT)


def git(project_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(project_root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


class TaskCentricKnowledgeWorkflowTests(unittest.TestCase):
    def _init_repo(self, root: Path) -> Path:
        project_root = root / "project"
        project_root.mkdir()
        git(project_root, "init")
        git(project_root, "config", "user.name", "Test User")
        git(project_root, "config", "user.email", "test@example.com")
        (project_root / "README.md").write_text("repo\n", encoding="utf-8")
        git(project_root, "add", "README.md")
        git(project_root, "commit", "-m", "init")
        return project_root

    def _write_registry(self, project_root: Path) -> None:
        registry_path = project_root / "knowledge/tasks/registry.md"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            textwrap.dedent(
                """\
                # Реестр задач

                | ID | Parent ID | Статус | Приоритет | Ветка | Каталог | Краткое описание |
                |----|-----------|--------|-----------|-------|---------|------------------|
                """
            ),
            encoding="utf-8",
        )

    def _write_task(
        self,
        task_dir: Path,
        *,
        task_id: str,
        parent_id: str = "—",
        slug: str,
        branch: str = "не создана",
        status: str = "в работе",
        priority: str = "средний",
        goal: str = "Краткое описание задачи.",
        human_description: str | None | object = DEFAULT_HUMAN_DESCRIPTION,
    ) -> None:
        task_dir.mkdir(parents=True, exist_ok=True)
        if human_description is DEFAULT_HUMAN_DESCRIPTION:
            human_description = goal
        human_description_line = ""
        if human_description is not None:
            human_description_line = f"| Человекочитаемое описание | {human_description} |\n"
        (task_dir / "task.md").write_text(
            textwrap.dedent(
                f"""\
                # Карточка задачи {task_id}

                ## Паспорт

                | Поле | Значение |
                |------|----------|
                | ID задачи | `{task_id}` |
                | Parent ID | `{parent_id}` |
                | Уровень вложенности | `0` |
                | Ключ в путях | `{task_id}` |
                | Технический ключ для новых именуемых сущностей | `—` |
                | Краткое имя | `{slug}` |
                {human_description_line.rstrip()}
                | Статус | `{status}` |
                | Приоритет | `{priority}` |
                | Ответственный | `Codex` |
                | Ветка | `{branch}` |
                | Требуется SDD | `нет` |
                | Статус SDD | `не требуется` |
                | Ссылка на SDD | `—` |
                | Дата создания | `2026-04-09` |
                | Дата обновления | `2026-04-09` |

                ## Цель

                {goal}
                """
            ),
            encoding="utf-8",
        )

    def _register_task(self, project_root: Path, task_dir: Path, summary: str) -> None:
        workflow_module.sync_task(
            project_root,
            task_dir,
            create_branch=False,
            register_if_missing=True,
            summary=summary,
            branch_name=None,
            inherit_branch_from_parent=False,
            today="2026-04-09",
        )

    def _commit_all(self, project_root: Path, message: str) -> None:
        git(project_root, "add", ".")
        git(project_root, "commit", "-m", message)

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(WORKFLOW_SCRIPT), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_sync_task_creates_branch_and_registry_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0004-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0004",
                slug="demo",
                goal="Демо-задача для проверки git-sync.",
            )

            payload = workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=True,
                register_if_missing=True,
                summary="Демо-задача для проверки git-sync.",
                branch_name=None,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["branch"], "task/task-2026-0004-demo")
            self.assertEqual(payload["branch_action"], "created")
            self.assertFalse(payload["remote_present"])
            self.assertEqual(git(project_root, "branch", "--show-current"), "task/task-2026-0004-demo")
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Ветка | `task/task-2026-0004-demo` |", task_text)
            registry_text = (project_root / "knowledge/tasks/registry.md").read_text(encoding="utf-8")
            self.assertIn("`TASK-2026-0004`", registry_text)
            self.assertIn("`task/task-2026-0004-demo`", registry_text)

    def test_sync_task_prefers_human_description_for_registry_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0020-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0020",
                slug="demo",
                goal="Подробная цель задачи для внутреннего описания.",
                human_description="Каноническая сводка задачи для registry.",
            )

            workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=True,
                register_if_missing=True,
                summary="Legacy summary не должен побеждать каноническое поле.",
                branch_name=None,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            registry_text = (project_root / "knowledge/tasks/registry.md").read_text(encoding="utf-8")
            self.assertIn("Каноническая сводка задачи для registry.", registry_text)
            self.assertNotIn("Legacy summary не должен побеждать каноническое поле.", registry_text)

    def test_sync_task_updates_existing_registry_summary_from_human_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0021-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0021",
                slug="demo",
                human_description="Актуальная каноническая сводка.",
            )
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text(
                registry_path.read_text(encoding="utf-8")
                + "| `TASK-2026-0021` | `—` | `в работе` | `средний` | `не создана` | `knowledge/tasks/TASK-2026-0021-demo/` | Устаревший кэш. |\n",
                encoding="utf-8",
            )

            workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=False,
                register_if_missing=False,
                summary=None,
                branch_name=None,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            registry_text = registry_path.read_text(encoding="utf-8")
            self.assertIn("Актуальная каноническая сводка.", registry_text)
            self.assertNotIn("Устаревший кэш.", registry_text)

    def test_sync_task_does_not_duplicate_existing_human_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0030-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0030",
                slug="demo",
                human_description="Каноническая summary.",
            )
            self._register_task(project_root, task_dir, "Каноническая summary.")

            workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=False,
                register_if_missing=False,
                summary="Каноническая summary.",
                branch_name=None,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertEqual(task_text.count("| Человекочитаемое описание |"), 1)
            self.assertIn("| Человекочитаемое описание | `Каноническая summary.` |", task_text)

    def test_sync_task_repairs_duplicate_human_description_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0037-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0037",
                slug="demo",
                goal="Старая цель.",
                human_description="Старое описание.",
            )
            task_path = task_dir / "task.md"
            task_text = task_path.read_text(encoding="utf-8")
            task_path.write_text(
                task_text.replace(
                    "| Человекочитаемое описание | Старое описание. |",
                    "| Человекочитаемое описание | Старое описание. |\n| Человекочитаемое описание | Дубликат, который нужно удалить. |",
                ),
                encoding="utf-8",
            )

            workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=False,
                register_if_missing=True,
                summary="Исправленная summary.",
                branch_name=None,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            updated_task_text = task_path.read_text(encoding="utf-8")
            self.assertEqual(updated_task_text.count("| Человекочитаемое описание |"), 1)
            self.assertIn("| Человекочитаемое описание | `Исправленная summary.` |", updated_task_text)
            registry_text = (project_root / "knowledge/tasks/registry.md").read_text(encoding="utf-8")
            self.assertIn("Исправленная summary.", registry_text)

    def test_sync_task_preserves_existing_human_description_when_repairing_duplicates_without_explicit_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0038-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0038",
                slug="demo",
                goal="Цель не должна заменить каноническое описание.",
                human_description="Каноническое описание задачи.",
            )
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text(
                registry_path.read_text(encoding="utf-8")
                + "| `TASK-2026-0038` | `—` | `в работе` | `средний` | `не создана` | `knowledge/tasks/TASK-2026-0038-demo/` | Кэшированное описание из registry. |\n",
                encoding="utf-8",
            )
            task_path = task_dir / "task.md"
            task_text = task_path.read_text(encoding="utf-8")
            task_path.write_text(
                task_text.replace(
                    "| Человекочитаемое описание | Каноническое описание задачи. |",
                    "| Человекочитаемое описание | Каноническое описание задачи. |\n| Человекочитаемое описание | Дубликат, который надо удалить без переписывания summary. |",
                ),
                encoding="utf-8",
            )

            workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=False,
                register_if_missing=False,
                summary=None,
                branch_name=None,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            updated_task_text = task_path.read_text(encoding="utf-8")
            self.assertEqual(updated_task_text.count("| Человекочитаемое описание |"), 1)
            self.assertIn("| Человекочитаемое описание | `Каноническое описание задачи.` |", updated_task_text)
            registry_text = registry_path.read_text(encoding="utf-8")
            self.assertIn("Каноническое описание задачи.", registry_text)
            self.assertNotIn("Кэшированное описание из registry.", registry_text)
            self.assertNotIn("Цель не должна заменить каноническое описание.", registry_text)

    def test_sync_task_falls_back_to_explicit_summary_for_legacy_task_without_human_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0022-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0022",
                slug="demo",
                goal="Goal fallback для legacy-задачи.",
                human_description=None,
            )

            workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=False,
                register_if_missing=True,
                summary="Legacy summary для строки registry.",
                branch_name=None,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            registry_text = (project_root / "knowledge/tasks/registry.md").read_text(encoding="utf-8")
            self.assertIn("Legacy summary для строки registry.", registry_text)
            self.assertNotIn("Goal fallback для legacy-задачи.", registry_text)

    def test_sync_task_ignores_placeholder_explicit_summary_for_legacy_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0041-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0041",
                slug="demo",
                goal="Goal fallback должен остаться канонической summary.",
                human_description=None,
            )

            workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=False,
                register_if_missing=True,
                summary="—",
                branch_name=None,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn(
                "| Человекочитаемое описание | `Goal fallback должен остаться канонической summary.` |",
                task_text,
            )
            self.assertNotIn("| Человекочитаемое описание | `—` |", task_text)
            registry_text = (project_root / "knowledge/tasks/registry.md").read_text(encoding="utf-8")
            self.assertIn("Goal fallback должен остаться канонической summary.", registry_text)
            self.assertNotIn("| `TASK-2026-0041` | `—` | `в работе` | `средний` | `main` | `knowledge/tasks/TASK-2026-0041-demo/` | — |", registry_text)

    def test_sync_task_backfills_existing_registry_summary_for_legacy_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0023-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0023",
                slug="demo",
                goal="Goal fallback не должен перезаписать curated summary из registry.",
                human_description=None,
            )
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text(
                registry_path.read_text(encoding="utf-8")
                + "| `TASK-2026-0023` | `—` | `в работе` | `средний` | `не создана` | `knowledge/tasks/TASK-2026-0023-demo/` | Curated legacy summary. |\n",
                encoding="utf-8",
            )

            workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=False,
                register_if_missing=False,
                summary=None,
                branch_name=None,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            registry_text = registry_path.read_text(encoding="utf-8")
            self.assertIn("Curated legacy summary.", registry_text)
            self.assertNotIn("Goal fallback не должен перезаписать curated summary из registry.", registry_text)
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Человекочитаемое описание | `Curated legacy summary.` |", task_text)

    def test_sync_task_backfills_explicit_summary_for_legacy_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0024-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0024",
                slug="demo",
                goal="Старая цель legacy-задачи.",
                human_description=None,
            )
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text(
                registry_path.read_text(encoding="utf-8")
                + "| `TASK-2026-0024` | `—` | `в работе` | `средний` | `не создана` | `knowledge/tasks/TASK-2026-0024-demo/` | Старая cached summary. |\n",
                encoding="utf-8",
            )

            workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=False,
                register_if_missing=False,
                summary="Явная summary для разрешения legacy-задачи.",
                branch_name=None,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            registry_text = registry_path.read_text(encoding="utf-8")
            self.assertIn("Явная summary для разрешения legacy-задачи.", registry_text)
            self.assertNotIn("Старая цель legacy-задачи.", registry_text)
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Человекочитаемое описание | `Явная summary для разрешения legacy-задачи.` |", task_text)

    def test_sync_task_uses_changed_goal_summary_for_legacy_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0031-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0031",
                slug="demo",
                goal="Старая цель legacy-задачи.",
                human_description=None,
            )
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text(
                registry_path.read_text(encoding="utf-8")
                + "| `TASK-2026-0031` | `—` | `в работе` | `средний` | `не создана` | `knowledge/tasks/TASK-2026-0031-demo/` | Curated legacy summary. |\n",
                encoding="utf-8",
            )
            self._commit_all(project_root, "prepare legacy task summary")

            self._write_task(
                task_dir,
                task_id="TASK-2026-0031",
                slug="demo",
                goal="Новая цель legacy-задачи.",
                human_description=None,
            )

            workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=False,
                register_if_missing=False,
                summary=None,
                branch_name=None,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            registry_text = registry_path.read_text(encoding="utf-8")
            self.assertIn("Новая цель legacy-задачи.", registry_text)
            self.assertNotIn("Curated legacy summary.", registry_text)
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Человекочитаемое описание | `Новая цель legacy-задачи.` |", task_text)
            self.assertEqual(task_text.count("| Человекочитаемое описание |"), 1)

    def test_sync_task_fails_before_task_update_when_registry_row_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0025-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0025",
                slug="demo",
                goal="Legacy-задача без строки в registry.",
                human_description=None,
            )
            task_path = task_dir / "task.md"
            task_before = task_path.read_text(encoding="utf-8")
            initial_branch = git(project_root, "branch", "--show-current")

            with self.assertRaisesRegex(ValueError, "В knowledge/tasks/registry.md не найдена строка"):
                workflow_module.sync_task(
                    project_root,
                    task_dir,
                    create_branch=True,
                    register_if_missing=False,
                    summary="Summary не должна успеть создать ветку.",
                    branch_name=None,
                    inherit_branch_from_parent=False,
                    today="2026-04-09",
                )

            self.assertEqual(git(project_root, "branch", "--show-current"), initial_branch)
            self.assertEqual(task_path.read_text(encoding="utf-8"), task_before)

    def test_sync_task_fails_before_branch_switch_when_target_branch_lacks_task_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            initial_commit = git(project_root, "rev-parse", "HEAD")
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0032-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0032",
                slug="demo",
                goal="Актуальная задача в основной ветке.",
                human_description="Актуальная summary.",
            )
            self._register_task(project_root, task_dir, "Актуальная summary.")
            self._commit_all(project_root, "prepare tracked task context")
            initial_branch = git(project_root, "branch", "--show-current")
            stale_branch = "task/task-2026-0032-stale"
            git(project_root, "branch", stale_branch, initial_commit)
            task_before = (task_dir / "task.md").read_text(encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Не найден knowledge/tasks/TASK-2026-0032-demo/task.md"):
                workflow_module.sync_task(
                    project_root,
                    task_dir,
                    create_branch=True,
                    register_if_missing=False,
                    summary=None,
                    branch_name=stale_branch,
                    inherit_branch_from_parent=False,
                    today="2026-04-09",
                )

            self.assertEqual(git(project_root, "branch", "--show-current"), initial_branch)
            self.assertEqual((task_dir / "task.md").read_text(encoding="utf-8"), task_before)

    def test_sync_task_reports_remote_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            git(project_root, "remote", "add", "origin", "https://example.com/repo.git")
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0007-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0007",
                slug="demo",
                goal="Задача с настроенным remote.",
            )

            payload = workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=True,
                register_if_missing=True,
                summary="Задача с настроенным remote.",
                branch_name=None,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["remote_present"])

    def test_sync_task_stops_on_dirty_worktree_before_branch_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0005-demo"
            self._write_task(task_dir, task_id="TASK-2026-0005", slug="demo")
            (project_root / "DIRTY.txt").write_text("dirty\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Рабочее дерево грязное"):
                workflow_module.sync_task(
                    project_root,
                    task_dir,
                    create_branch=True,
                    register_if_missing=True,
                    summary="Нельзя создавать ветку на грязном дереве.",
                    branch_name=None,
                    inherit_branch_from_parent=False,
                    today="2026-04-09",
                )

            self.assertNotEqual(git(project_root, "branch", "--show-current"), "task/task-2026-0005-demo")

    def test_subtask_can_inherit_parent_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            parent_dir = project_root / "knowledge/tasks/TASK-2026-0006-parent"
            self._write_task(
                parent_dir,
                task_id="TASK-2026-0006",
                slug="parent",
                branch="task/task-2026-0006-parent",
            )
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text(
                registry_path.read_text(encoding="utf-8")
                + "| `TASK-2026-0006` | `—` | `в работе` | `средний` | `task/task-2026-0006-parent` | `knowledge/tasks/TASK-2026-0006-parent/` | Родительская задача. |\n",
                encoding="utf-8",
            )
            git(project_root, "checkout", "-b", "task/task-2026-0006-parent")
            git(project_root, "checkout", git(project_root, "rev-parse", "--short", "HEAD"))

            child_dir = parent_dir / "subtasks" / "TASK-2026-0006.1-child"
            self._write_task(
                child_dir,
                task_id="TASK-2026-0006.1",
                parent_id="TASK-2026-0006",
                slug="child",
                branch="не создана",
                goal="Подзадача наследует ветку родителя.",
            )

            payload = workflow_module.sync_task(
                project_root,
                child_dir,
                create_branch=True,
                register_if_missing=True,
                summary="Подзадача наследует ветку родителя.",
                branch_name=None,
                inherit_branch_from_parent=True,
                today="2026-04-09",
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["branch"], "task/task-2026-0006-parent")
            self.assertFalse(payload["remote_present"])
            self.assertEqual(git(project_root, "branch", "--show-current"), "task/task-2026-0006-parent")
            child_text = (child_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Ветка | `task/task-2026-0006-parent` |", child_text)

    def test_subtask_inherits_parent_branch_from_parent_task_branch_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            initial_branch = git(project_root, "branch", "--show-current")
            self._write_registry(project_root)
            parent_dir = project_root / "knowledge/tasks/TASK-2026-0035-parent"
            self._write_task(
                parent_dir,
                task_id="TASK-2026-0035",
                slug="parent",
                branch=initial_branch,
                goal="Родительская задача в текущем checkout ещё привязана к основной ветке.",
                human_description="Родительская задача.",
            )
            self._register_task(project_root, parent_dir, "Родительская задача.")
            self._commit_all(project_root, "record parent task in main checkout")

            parent_branch = "task/task-2026-0035-parent"
            git(project_root, "checkout", "-b", parent_branch)
            workflow_module.sync_task(
                project_root,
                parent_dir,
                create_branch=False,
                register_if_missing=False,
                summary="Родительская задача.",
                branch_name=parent_branch,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )
            self._commit_all(project_root, "record parent task branch context")
            git(project_root, "checkout", initial_branch)

            child_dir = parent_dir / "subtasks" / "TASK-2026-0035.1-child"
            self._write_task(
                child_dir,
                task_id="TASK-2026-0035.1",
                parent_id="TASK-2026-0035",
                slug="child",
                branch="не создана",
                goal="Подзадача должна унаследовать parent task branch.",
            )

            payload = workflow_module.sync_task(
                project_root,
                child_dir,
                create_branch=True,
                register_if_missing=True,
                summary="Подзадача должна унаследовать parent task branch.",
                branch_name=None,
                inherit_branch_from_parent=True,
                today="2026-04-09",
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["branch"], parent_branch)
            self.assertEqual(git(project_root, "branch", "--show-current"), parent_branch)

    def test_subtask_prefers_recorded_custom_parent_branch_over_stale_default_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            parent_dir = project_root / "knowledge/tasks/TASK-2026-0039-parent"
            custom_parent_branch = "feature/task-2026-0039-parent-live"
            self._write_task(
                parent_dir,
                task_id="TASK-2026-0039",
                slug="parent",
                branch=custom_parent_branch,
                goal="Родительская задача уже переведена на кастомную ветку.",
                human_description="Родительская задача на кастомной ветке.",
            )
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text(
                registry_path.read_text(encoding="utf-8")
                + "| `TASK-2026-0039` | `—` | `в работе` | `средний` | `feature/task-2026-0039-parent-live` | `knowledge/tasks/TASK-2026-0039-parent/` | Родительская задача на кастомной ветке. |\n",
                encoding="utf-8",
            )
            self._commit_all(project_root, "record parent task with custom branch")
            git(project_root, "branch", "task/task-2026-0039-parent")
            git(project_root, "branch", custom_parent_branch)

            child_dir = parent_dir / "subtasks" / "TASK-2026-0039.1-child"
            self._write_task(
                child_dir,
                task_id="TASK-2026-0039.1",
                parent_id="TASK-2026-0039",
                slug="child",
                branch="не создана",
                goal="Подзадача не должна уходить в stale default branch.",
            )

            payload = workflow_module.sync_task(
                project_root,
                child_dir,
                create_branch=True,
                register_if_missing=True,
                summary="Подзадача не должна уходить в stale default branch.",
                branch_name=None,
                inherit_branch_from_parent=True,
                today="2026-04-09",
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["branch"], custom_parent_branch)
            self.assertEqual(git(project_root, "branch", "--show-current"), custom_parent_branch)

    def test_subtask_prefers_current_parent_branch_after_default_branch_was_merged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            initial_branch = git(project_root, "branch", "--show-current")
            self._write_registry(project_root)
            parent_dir = project_root / "knowledge/tasks/TASK-2026-0040-parent"
            default_parent_branch = "task/task-2026-0040-parent"
            self._write_task(
                parent_dir,
                task_id="TASK-2026-0040",
                slug="parent",
                branch=initial_branch,
                goal="Родительская задача уже вернулась на основную ветку.",
                human_description="Родительская задача после merge.",
            )
            self._register_task(project_root, parent_dir, "Родительская задача после merge.")
            self._commit_all(project_root, "record parent task on base branch")

            git(project_root, "checkout", "-b", default_parent_branch)
            workflow_module.sync_task(
                project_root,
                parent_dir,
                create_branch=False,
                register_if_missing=False,
                summary="Родительская задача после merge.",
                branch_name=default_parent_branch,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )
            self._commit_all(project_root, "record parent task branch context")

            git(project_root, "checkout", initial_branch)
            git(project_root, "merge", "--no-ff", default_parent_branch, "-m", "merge parent task branch")
            workflow_module.sync_task(
                project_root,
                parent_dir,
                create_branch=False,
                register_if_missing=False,
                summary="Родительская задача после merge.",
                branch_name=initial_branch,
                inherit_branch_from_parent=False,
                today="2026-04-10",
            )
            self._commit_all(project_root, "retarget parent task to base branch")

            child_dir = parent_dir / "subtasks" / "TASK-2026-0040.1-child"
            self._write_task(
                child_dir,
                task_id="TASK-2026-0040.1",
                parent_id="TASK-2026-0040",
                slug="child",
                branch="не создана",
                goal="Подзадача должна унаследовать актуальную ветку родителя.",
            )

            payload = workflow_module.sync_task(
                project_root,
                child_dir,
                create_branch=True,
                register_if_missing=True,
                summary="Подзадача должна унаследовать актуальную ветку родителя.",
                branch_name=None,
                inherit_branch_from_parent=True,
                today="2026-04-10",
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["branch"], initial_branch)
            self.assertEqual(git(project_root, "branch", "--show-current"), initial_branch)

    def test_sync_task_allows_staged_new_task_when_target_branch_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            self._commit_all(project_root, "record registry")
            initial_branch = git(project_root, "branch", "--show-current")
            target_branch = "task/task-2026-0036-demo"
            git(project_root, "branch", target_branch)

            task_dir = project_root / "knowledge/tasks/TASK-2026-0036-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0036",
                slug="demo",
                branch="не создана",
                goal="Новая staged-задача на существующую ветку.",
                human_description=None,
            )
            git(project_root, "add", str(task_dir / "task.md"))

            payload = workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=True,
                register_if_missing=True,
                summary="Новая staged-задача на существующую ветку.",
                branch_name=target_branch,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["branch"], target_branch)
            self.assertEqual(git(project_root, "branch", "--show-current"), target_branch)
            self.assertNotEqual(initial_branch, target_branch)

    def test_start_creates_delivery_unit_and_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0008-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0008",
                slug="demo",
                goal="Проверка старта delivery unit.",
            )
            self._register_task(project_root, task_dir, "Проверка старта delivery unit.")
            self._commit_all(project_root, "prepare task context")
            base_branch = git(project_root, "branch", "--show-current")

            payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id=None,
                purpose="Первая поставка",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["unit_id"], "DU-01")
            self.assertEqual(payload["branch"], "du/task-2026-0008-u01-demo")
            self.assertEqual(git(project_root, "branch", "--show-current"), "du/task-2026-0008-u01-demo")
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("## Контур публикации", task_text)
            self.assertIn("| `DU-01` | Первая поставка | `du/task-2026-0008-u01-demo` |", task_text)
            self.assertIn(f"| Ветка | `{payload['branch']}` |", task_text)

    def test_start_accepts_explicit_summary_for_legacy_task_without_human_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0010-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0010",
                slug="demo",
                goal="Goal fallback расходится с curated summary.",
                human_description=None,
            )
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text(
                registry_path.read_text(encoding="utf-8")
                + "| `TASK-2026-0010` | `—` | `в работе` | `средний` | `не создана` | `knowledge/tasks/TASK-2026-0010-demo/` | Старая cached summary. |\n",
                encoding="utf-8",
            )
            self._commit_all(project_root, "prepare legacy publish task")
            base_branch = git(project_root, "branch", "--show-current")

            payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id=None,
                purpose="Legacy publish",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                summary="Явная summary для publish helper.",
                today="2026-04-09",
            )

            self.assertTrue(payload["ok"])
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Человекочитаемое описание | `Явная summary для publish helper.` |", task_text)
            registry_text = registry_path.read_text(encoding="utf-8")
            self.assertIn("Явная summary для publish helper.", registry_text)
            self.assertNotIn("Старая cached summary.", registry_text)

    def test_start_ignores_placeholder_explicit_summary_for_legacy_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0042-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0042",
                slug="demo",
                goal="Goal fallback расходится с curated publish summary.",
                human_description=None,
            )
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text(
                registry_path.read_text(encoding="utf-8")
                + "| `TASK-2026-0042` | `—` | `в работе` | `средний` | `не создана` | `knowledge/tasks/TASK-2026-0042-demo/` | Curated publish summary. |\n",
                encoding="utf-8",
            )
            self._commit_all(project_root, "prepare placeholder publish summary")
            base_branch = git(project_root, "branch", "--show-current")

            payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id=None,
                purpose="Legacy publish with placeholder summary",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                summary="—",
                today="2026-04-09",
            )

            self.assertTrue(payload["ok"])
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Человекочитаемое описание | `Curated publish summary.` |", task_text)
            self.assertNotIn("| Человекочитаемое описание | `—` |", task_text)
            registry_text = registry_path.read_text(encoding="utf-8")
            self.assertIn("Curated publish summary.", registry_text)
            self.assertNotIn("| `TASK-2026-0042` | `—` | `в работе` | `средний` | `du/task-2026-0042-u01-demo` | `knowledge/tasks/TASK-2026-0042-demo/` | — |", registry_text)

    def test_start_backfills_existing_registry_summary_for_legacy_task_without_explicit_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0014-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0014",
                slug="demo",
                goal="Goal fallback расходится с curated summary.",
                human_description=None,
            )
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text(
                registry_path.read_text(encoding="utf-8")
                + "| `TASK-2026-0014` | `—` | `в работе` | `средний` | `не создана` | `knowledge/tasks/TASK-2026-0014-demo/` | Curated publish summary. |\n",
                encoding="utf-8",
            )
            self._commit_all(project_root, "prepare legacy publish task without explicit summary")
            base_branch = git(project_root, "branch", "--show-current")

            payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id=None,
                purpose="Legacy publish without explicit summary",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                summary=None,
                today="2026-04-09",
            )

            self.assertTrue(payload["ok"])
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Человекочитаемое описание | `Curated publish summary.` |", task_text)
            registry_text = registry_path.read_text(encoding="utf-8")
            self.assertIn("Curated publish summary.", registry_text)
            self.assertNotIn("Goal fallback расходится с curated summary.", registry_text)

    def test_start_fails_before_branch_creation_when_registry_row_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0013-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0013",
                slug="demo",
                goal="Publish helper без строки в registry.",
                human_description=None,
            )
            self._commit_all(project_root, "prepare unregistered publish task")
            task_path = task_dir / "task.md"
            task_before = task_path.read_text(encoding="utf-8")
            initial_branch = git(project_root, "branch", "--show-current")

            with self.assertRaisesRegex(ValueError, "В knowledge/tasks/registry.md не найдена строка"):
                workflow_module.run_publish_flow(
                    project_root,
                    task_dir,
                    action="start",
                    unit_id=None,
                    purpose="Missing registry row",
                    base_branch=initial_branch,
                    head_branch=None,
                    from_ref=None,
                    host=None,
                    publication_type=None,
                    url=None,
                    merge_commit=None,
                    cleanup=None,
                    remote_name="origin",
                    status=None,
                    create_publication=False,
                    sync_from_host=False,
                    title=None,
                    body=None,
                    summary="Summary не должна успеть создать delivery-ветку.",
                    today="2026-04-09",
                )

            self.assertEqual(git(project_root, "branch", "--show-current"), initial_branch)
            self.assertEqual(task_path.read_text(encoding="utf-8"), task_before)
            self.assertEqual(git(project_root, "branch", "--list", "du/task-2026-0013-u01-demo"), "")

    def test_sync_preflight_uses_target_branch_summary_when_switching_to_existing_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            initial_branch = git(project_root, "branch", "--show-current")
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0026-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0026",
                slug="demo",
                goal="Main branch goal summary.",
                human_description="Main branch summary.",
            )
            self._register_task(project_root, task_dir, "Main branch summary.")
            self._commit_all(project_root, "prepare main branch task context")

            target_branch = "task/task-2026-0026-demo"
            git(project_root, "checkout", "-b", target_branch)
            self._write_task(
                task_dir,
                task_id="TASK-2026-0026",
                slug="demo",
                branch=target_branch,
                goal="Target branch goal summary.",
                human_description="Target branch summary.",
            )
            self._register_task(project_root, task_dir, "Target branch summary.")
            self._commit_all(project_root, "prepare target branch task context")

            git(project_root, "checkout", initial_branch)
            workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=True,
                register_if_missing=False,
                summary=None,
                branch_name=target_branch,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            self.assertEqual(git(project_root, "branch", "--show-current"), target_branch)
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Человекочитаемое описание | `Target branch summary.` |", task_text)
            self.assertNotIn("Main branch summary.", task_text)

    def test_sync_preflight_uses_changed_legacy_goal_from_existing_target_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            initial_branch = git(project_root, "branch", "--show-current")
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0040-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0040",
                slug="demo",
                goal="Main branch goal summary.",
                human_description="Main branch summary.",
            )
            self._register_task(project_root, task_dir, "Main branch summary.")
            self._commit_all(project_root, "prepare main branch legacy target context")

            target_branch = "task/task-2026-0040-demo"
            git(project_root, "checkout", "-b", target_branch)
            self._write_task(
                task_dir,
                task_id="TASK-2026-0040",
                slug="demo",
                branch=target_branch,
                goal="Старая legacy-цель на target branch.",
                human_description=None,
            )
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text(
                registry_path.read_text(encoding="utf-8").replace(
                    "Main branch summary.",
                    "Старая cached summary target branch.",
                ),
                encoding="utf-8",
            )
            self._commit_all(project_root, "prepare stale legacy target summary")

            self._write_task(
                task_dir,
                task_id="TASK-2026-0040",
                slug="demo",
                branch=target_branch,
                goal="Новая legacy-цель на target branch.",
                human_description=None,
            )
            self._commit_all(project_root, "change legacy goal on target branch")

            git(project_root, "checkout", initial_branch)
            workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=True,
                register_if_missing=False,
                summary=None,
                branch_name=target_branch,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )

            self.assertEqual(git(project_root, "branch", "--show-current"), target_branch)
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Человекочитаемое описание | `Новая legacy-цель на target branch.` |", task_text)
            registry_text = registry_path.read_text(encoding="utf-8")
            self.assertIn("Новая legacy-цель на target branch.", registry_text)
            self.assertNotIn("Старая cached summary target branch.", registry_text)

    def test_publish_start_uses_target_delivery_branch_summary_when_reusing_existing_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0027-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0027",
                slug="demo",
                goal="Base branch goal summary.",
                human_description="Base branch summary.",
            )
            self._register_task(project_root, task_dir, "Base branch summary.")
            self._commit_all(project_root, "prepare publish base context")
            base_branch = git(project_root, "branch", "--show-current")

            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id="DU-01",
                purpose="Reusable delivery branch",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                summary=None,
                today="2026-04-09",
            )
            self._commit_all(project_root, "start reusable delivery branch")

            delivery_branch = "du/task-2026-0027-u01-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0027",
                slug="demo",
                branch=delivery_branch,
                goal="Delivery branch goal summary.",
                human_description="Delivery branch summary.",
            )
            self._register_task(project_root, task_dir, "Delivery branch summary.")
            self._commit_all(project_root, "record delivery branch summary")

            git(project_root, "checkout", base_branch)
            self._write_task(
                task_dir,
                task_id="TASK-2026-0027",
                slug="demo",
                branch=base_branch,
                goal="Base branch goal summary changed.",
                human_description="Base branch summary changed.",
            )
            self._register_task(project_root, task_dir, "Base branch summary changed.")
            self._commit_all(project_root, "change base branch summary")

            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id="DU-01",
                purpose="Reusable delivery branch",
                base_branch=base_branch,
                head_branch=delivery_branch,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                summary=None,
                today="2026-04-09",
            )

            self.assertEqual(git(project_root, "branch", "--show-current"), delivery_branch)
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Человекочитаемое описание | `Delivery branch summary.` |", task_text)
            self.assertNotIn("Base branch summary changed.", task_text)

    def test_publish_cli_passes_summary_to_publish_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0028-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0028",
                slug="demo",
                goal="Goal fallback расходится с curated summary.",
                human_description=None,
            )
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text(
                registry_path.read_text(encoding="utf-8")
                + "| `TASK-2026-0028` | `—` | `в работе` | `средний` | `не создана` | `knowledge/tasks/TASK-2026-0028-demo/` | Старая cached summary. |\n",
                encoding="utf-8",
            )
            self._commit_all(project_root, "prepare cli publish task")
            base_branch = git(project_root, "branch", "--show-current")

            completed = self._run_cli(
                "--project-root",
                str(project_root),
                "--task-dir",
                str(task_dir),
                "--publish-action",
                "start",
                "--purpose",
                "CLI legacy publish",
                "--base-branch",
                base_branch,
                "--summary",
                "CLI summary wiring.",
                "--format",
                "json",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Человекочитаемое описание | `CLI summary wiring.` |", task_text)

    def test_publish_create_publication_uses_resolved_summary_in_default_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0029-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0029",
                slug="demo",
                goal="Goal fallback расходится с curated summary.",
                human_description=None,
            )
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text(
                registry_path.read_text(encoding="utf-8")
                + "| `TASK-2026-0029` | `—` | `в работе` | `средний` | `не создана` | `knowledge/tasks/TASK-2026-0029-demo/` | Curated publication summary. |\n",
                encoding="utf-8",
            )
            self._commit_all(project_root, "prepare create publication task")
            base_branch = git(project_root, "branch", "--show-current")

            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id="DU-01",
                purpose="Create publication",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                summary=None,
                today="2026-04-09",
            )

            adapter = mock.Mock()
            adapter.create_publication.return_value = workflow_module.PublicationSnapshot(
                host="github",
                publication_type="pr",
                status="draft",
                url="https://github.com/example/project/pull/29",
                head="du/task-2026-0029-u01-demo",
                base=base_branch,
                merge_commit=workflow_module.DELIVERY_ROW_PLACEHOLDER,
            )

            with mock.patch.object(workflow_module, "resolve_forge_adapter", return_value=adapter):
                payload = workflow_module.run_publish_flow(
                    project_root,
                    task_dir,
                    action="publish",
                    unit_id="DU-01",
                    purpose=None,
                    base_branch=None,
                    head_branch=None,
                    from_ref=None,
                    host="github",
                    publication_type=None,
                    url=None,
                    merge_commit=None,
                    cleanup=None,
                    remote_name="origin",
                    status="draft",
                    create_publication=True,
                    sync_from_host=False,
                    title=None,
                    body=None,
                    summary=None,
                    today="2026-04-09",
                )

            self.assertEqual(payload["delivery_status"], "draft")
            adapter.create_publication.assert_called_once()
            self.assertIn("Summary: Curated publication summary.", adapter.create_publication.call_args.kwargs["body"])

    def test_publish_create_publication_uses_delivery_branch_summary_from_base_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0033-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0033",
                slug="demo",
                goal="Base branch goal summary.",
                human_description="Base branch summary.",
            )
            self._register_task(project_root, task_dir, "Base branch summary.")
            self._commit_all(project_root, "prepare base task context")
            base_branch = git(project_root, "branch", "--show-current")

            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id="DU-01",
                purpose="Create publication from base checkout",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                summary=None,
                today="2026-04-09",
            )
            self._commit_all(project_root, "start delivery branch for publication")

            delivery_branch = "du/task-2026-0033-u01-demo"
            task_path = task_dir / "task.md"
            task_text = task_path.read_text(encoding="utf-8")
            task_path.write_text(
                task_text
                .replace("Base branch goal summary.", "Delivery branch goal summary.")
                .replace("Base branch summary.", "Delivery branch summary."),
                encoding="utf-8",
            )
            self._register_task(project_root, task_dir, "Delivery branch summary.")
            self._commit_all(project_root, "record delivery branch summary")

            git(project_root, "checkout", base_branch)
            self._write_task(
                task_dir,
                task_id="TASK-2026-0033",
                slug="demo",
                branch=base_branch,
                goal="Base branch goal summary updated.",
                human_description="Base branch summary updated.",
            )
            self._register_task(project_root, task_dir, "Base branch summary updated.")
            self._commit_all(project_root, "update base branch summary")

            adapter = mock.Mock()
            adapter.create_publication.return_value = workflow_module.PublicationSnapshot(
                host="github",
                publication_type="pr",
                status="draft",
                url="https://github.com/example/project/pull/33",
                head=delivery_branch,
                base=base_branch,
                merge_commit=workflow_module.DELIVERY_ROW_PLACEHOLDER,
            )

            with mock.patch.object(workflow_module, "resolve_forge_adapter", return_value=adapter):
                workflow_module.run_publish_flow(
                    project_root,
                    task_dir,
                    action="publish",
                    unit_id="DU-01",
                    purpose=None,
                    base_branch=None,
                    head_branch=None,
                    from_ref=None,
                    host="github",
                    publication_type=None,
                    url=None,
                    merge_commit=None,
                    cleanup=None,
                    remote_name="origin",
                    status="draft",
                    create_publication=True,
                    sync_from_host=False,
                    title=None,
                    body=None,
                    summary=None,
                    today="2026-04-09",
                )

            adapter.create_publication.assert_called_once()
            self.assertIn("Summary: Delivery branch summary.", adapter.create_publication.call_args.kwargs["body"])
            self.assertNotIn("Summary: Base branch summary updated.", adapter.create_publication.call_args.kwargs["body"])
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Человекочитаемое описание | `Delivery branch summary.` |", task_text)
            registry_text = (project_root / "knowledge/tasks/registry.md").read_text(encoding="utf-8")
            self.assertIn("Delivery branch summary.", registry_text)
            self.assertNotIn("Base branch summary updated.", registry_text)

    def test_manual_publish_sync_uses_delivery_branch_summary_from_base_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0041-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0041",
                slug="demo",
                goal="Base branch goal summary.",
                human_description="Base branch summary.",
            )
            self._register_task(project_root, task_dir, "Base branch summary.")
            self._commit_all(project_root, "prepare manual publish base context")
            base_branch = git(project_root, "branch", "--show-current")

            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id="DU-01",
                purpose="Manual publish from base checkout",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                summary=None,
                today="2026-04-09",
            )
            self._commit_all(project_root, "start manual publish delivery branch")

            delivery_branch = "du/task-2026-0041-u01-demo"
            task_path = task_dir / "task.md"
            task_text = task_path.read_text(encoding="utf-8")
            task_path.write_text(
                task_text
                .replace("Base branch goal summary.", "Delivery branch goal summary.")
                .replace("Base branch summary.", "Delivery branch summary."),
                encoding="utf-8",
            )
            self._register_task(project_root, task_dir, "Delivery branch summary.")
            self._commit_all(project_root, "record delivery branch summary for manual sync")

            git(project_root, "checkout", base_branch)
            self._write_task(
                task_dir,
                task_id="TASK-2026-0041",
                slug="demo",
                branch=base_branch,
                goal="Base branch goal summary updated.",
                human_description="Base branch summary updated.",
            )
            self._register_task(project_root, task_dir, "Base branch summary updated.")
            self._commit_all(project_root, "update base summary before manual sync")

            payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="sync",
                unit_id="DU-01",
                purpose=None,
                base_branch=None,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                summary=None,
                today="2026-04-09",
            )

            self.assertEqual(payload["delivery_status"], "local")
            task_text = task_path.read_text(encoding="utf-8")
            self.assertIn("| Человекочитаемое описание | `Delivery branch summary.` |", task_text)
            self.assertNotIn("| Человекочитаемое описание | `Base branch summary updated.` |", task_text)
            registry_text = (project_root / "knowledge/tasks/registry.md").read_text(encoding="utf-8")
            self.assertIn("Delivery branch summary.", registry_text)
            self.assertNotIn("Base branch summary updated.", registry_text)

    def test_publish_create_publication_uses_current_worktree_summary_on_delivery_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0038-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0038",
                slug="demo",
                goal="Committed delivery summary.",
                human_description="Committed delivery summary.",
            )
            self._register_task(project_root, task_dir, "Committed delivery summary.")
            self._commit_all(project_root, "prepare publication worktree summary")
            base_branch = git(project_root, "branch", "--show-current")

            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id="DU-01",
                purpose="Create publication from current delivery worktree",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                summary=None,
                today="2026-04-09",
            )
            self._commit_all(project_root, "start delivery branch for current worktree summary")

            task_path = task_dir / "task.md"
            task_text = task_path.read_text(encoding="utf-8")
            task_path.write_text(
                task_text.replace("Committed delivery summary.", "Локальная summary из worktree."),
                encoding="utf-8",
            )

            adapter = mock.Mock()
            adapter.create_publication.return_value = workflow_module.PublicationSnapshot(
                host="github",
                publication_type="pr",
                status="draft",
                url="https://github.com/example/project/pull/38",
                head="du/task-2026-0038-u01-demo",
                base=base_branch,
                merge_commit=workflow_module.DELIVERY_ROW_PLACEHOLDER,
            )

            with mock.patch.object(workflow_module, "resolve_forge_adapter", return_value=adapter):
                workflow_module.run_publish_flow(
                    project_root,
                    task_dir,
                    action="publish",
                    unit_id="DU-01",
                    purpose=None,
                    base_branch=None,
                    head_branch=None,
                    from_ref=None,
                    host="github",
                    publication_type=None,
                    url=None,
                    merge_commit=None,
                    cleanup=None,
                    remote_name="origin",
                    status="draft",
                    create_publication=True,
                    sync_from_host=False,
                    title=None,
                    body=None,
                    summary=None,
                    today="2026-04-09",
                )

            adapter.create_publication.assert_called_once()
            self.assertIn("Summary: Локальная summary из worktree.", adapter.create_publication.call_args.kwargs["body"])
            self.assertNotIn("Summary: Committed delivery summary.", adapter.create_publication.call_args.kwargs["body"])

    def test_publish_sync_uses_delivery_branch_summary_from_detached_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0034-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0034",
                slug="demo",
                goal="Base branch goal summary.",
                human_description="Base branch summary.",
            )
            self._register_task(project_root, task_dir, "Base branch summary.")
            self._commit_all(project_root, "prepare detached publish base")
            base_branch = git(project_root, "branch", "--show-current")

            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id="DU-01",
                purpose="Detached publish sync",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                summary=None,
                today="2026-04-09",
            )
            self._commit_all(project_root, "start detached publish delivery")

            delivery_branch = "du/task-2026-0034-u01-demo"
            task_path = task_dir / "task.md"
            task_text = task_path.read_text(encoding="utf-8")
            task_path.write_text(
                task_text
                .replace("Base branch goal summary.", "Delivery summary v1.")
                .replace("Base branch summary.", "Delivery summary v1."),
                encoding="utf-8",
            )
            self._register_task(project_root, task_dir, "Delivery summary v1.")
            self._commit_all(project_root, "record delivery summary v1")
            old_commit = git(project_root, "rev-parse", "HEAD")

            task_text = task_path.read_text(encoding="utf-8")
            task_path.write_text(
                task_text.replace("Delivery summary v1.", "Delivery summary v2."),
                encoding="utf-8",
            )
            self._register_task(project_root, task_dir, "Delivery summary v2.")
            self._commit_all(project_root, "record delivery summary v2")

            git(project_root, "checkout", old_commit)
            payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="sync",
                unit_id="DU-01",
                purpose=None,
                base_branch=None,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                summary=None,
                today="2026-04-09",
            )

            self.assertEqual(payload["delivery_status"], "local")
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| Человекочитаемое описание | `Delivery summary v2.` |", task_text)
            self.assertNotIn("| Человекочитаемое описание | `Delivery summary v1.` |", task_text)

    def test_start_uses_next_delivery_unit_id_from_existing_delivery_branches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0011-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0011",
                slug="demo",
                goal="Проверка второго параллельного delivery unit.",
            )
            self._register_task(project_root, task_dir, "Проверка второго параллельного delivery unit.")
            self._commit_all(project_root, "prepare task context")
            base_branch = git(project_root, "branch", "--show-current")

            first_payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id=None,
                purpose="Первая поставка",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )
            self._commit_all(project_root, "start first delivery unit")
            git(project_root, "checkout", base_branch)

            second_payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id=None,
                purpose="Вторая поставка",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )

            self.assertEqual(first_payload["unit_id"], "DU-01")
            self.assertEqual(second_payload["unit_id"], "DU-02")
            self.assertEqual(second_payload["branch"], "du/task-2026-0011-u02-demo")
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| `DU-01` | Первая поставка | `du/task-2026-0011-u01-demo` |", task_text)
            self.assertIn("| `DU-02` | Вторая поставка | `du/task-2026-0011-u02-demo` |", task_text)
            self._commit_all(project_root, "start second delivery unit")
            git(project_root, "checkout", base_branch)

            publish_payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="publish",
                unit_id="DU-01",
                purpose=None,
                base_branch=None,
                head_branch=None,
                from_ref=None,
                host="github",
                publication_type=None,
                url="https://github.com/example/project/pull/11",
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status="draft",
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )

            self.assertEqual(publish_payload["delivery_status"], "draft")
            base_task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn(
                f"| `DU-01` | Первая поставка | `du/task-2026-0011-u01-demo` | `{base_branch}` | `github` | `pr` | `draft` |",
                base_task_text,
            )
            self.assertIn("| `DU-02` | Вторая поставка | `du/task-2026-0011-u02-demo` |", base_task_text)

    def test_publish_sync_and_merge_update_delivery_unit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0009-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0009",
                slug="demo",
                goal="Проверка publish lifecycle.",
            )
            self._register_task(project_root, task_dir, "Проверка publish lifecycle.")
            self._commit_all(project_root, "prepare task context")
            base_branch = git(project_root, "branch", "--show-current")
            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id="DU-01",
                purpose="Поставка через PR",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )

            publish_payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="publish",
                unit_id="DU-01",
                purpose=None,
                base_branch=None,
                head_branch=None,
                from_ref=None,
                host="github",
                publication_type=None,
                url="https://github.com/example/project/pull/1",
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status="draft",
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )
            self.assertEqual(publish_payload["delivery_status"], "draft")
            self.assertEqual(publish_payload["host"], "github")
            self.assertEqual(publish_payload["publication_type"], "pr")

            sync_payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="sync",
                unit_id="DU-01",
                purpose=None,
                base_branch=None,
                head_branch=None,
                from_ref=None,
                host="github",
                publication_type="pr",
                url="https://github.com/example/project/pull/1",
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status="review",
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )
            self.assertEqual(sync_payload["delivery_status"], "review")

            merge_payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="merge",
                unit_id="DU-01",
                purpose=None,
                base_branch=None,
                head_branch=None,
                from_ref=None,
                host="github",
                publication_type="pr",
                url="https://github.com/example/project/pull/1",
                merge_commit="abc1234",
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )
            self.assertEqual(merge_payload["delivery_status"], "merged")
            self.assertEqual(merge_payload["merge_commit"], "abc1234")
            self.assertEqual(merge_payload["cleanup"], "ожидается")
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn("| `github` | `pr` | `merged` | `https://github.com/example/project/pull/1` | `abc1234` | `ожидается` |", task_text)

    def test_merge_from_base_branch_keeps_checkout_branch_in_task_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0012-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0012",
                slug="demo",
                goal="Проверка синхронизации поля ветки после merge.",
            )
            self._register_task(project_root, task_dir, "Проверка синхронизации поля ветки после merge.")
            self._commit_all(project_root, "prepare task context")
            base_branch = git(project_root, "branch", "--show-current")

            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id="DU-01",
                purpose="Поставка через PR",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )
            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="publish",
                unit_id="DU-01",
                purpose=None,
                base_branch=None,
                head_branch=None,
                from_ref=None,
                host="github",
                publication_type=None,
                url="https://github.com/example/project/pull/12",
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status="draft",
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )
            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="sync",
                unit_id="DU-01",
                purpose=None,
                base_branch=None,
                head_branch=None,
                from_ref=None,
                host="github",
                publication_type="pr",
                url="https://github.com/example/project/pull/12",
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status="review",
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )
            self._commit_all(project_root, "prepare delivery branch for merge")
            git(project_root, "checkout", base_branch)
            git(project_root, "merge", "--no-ff", "-m", "merge delivery branch", "du/task-2026-0012-u01-demo")

            merge_payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="merge",
                unit_id="DU-01",
                purpose=None,
                base_branch=None,
                head_branch=None,
                from_ref=None,
                host="github",
                publication_type="pr",
                url="https://github.com/example/project/pull/12",
                merge_commit="merge123",
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )

            self.assertEqual(merge_payload["branch"], base_branch)
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn(f"| Ветка | `{base_branch}` |", task_text)
            registry_text = (project_root / "knowledge/tasks/registry.md").read_text(encoding="utf-8")
            self.assertIn(f"`{base_branch}`", registry_text)

    def test_publish_promotes_existing_draft_instead_of_creating_new_publication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0013-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0013",
                slug="demo",
                goal="Проверка draft -> review через update публикации.",
            )
            self._register_task(project_root, task_dir, "Проверка draft -> review через update публикации.")
            self._commit_all(project_root, "prepare task context")
            base_branch = git(project_root, "branch", "--show-current")

            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id="DU-01",
                purpose="Поставка через draft PR",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )
            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="publish",
                unit_id="DU-01",
                purpose=None,
                base_branch=None,
                head_branch=None,
                from_ref=None,
                host="github",
                publication_type=None,
                url="https://github.com/example/project/pull/13",
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status="draft",
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )

            adapter = mock.Mock()
            adapter.update_publication.return_value = workflow_module.PublicationSnapshot(
                host="github",
                publication_type="pr",
                status="review",
                url="https://github.com/example/project/pull/13",
                head="du/task-2026-0013-u01-demo",
                base=base_branch,
                merge_commit=workflow_module.DELIVERY_ROW_PLACEHOLDER,
            )
            adapter.create_publication.side_effect = AssertionError("create_publication не должен вызываться")

            with mock.patch.object(workflow_module, "resolve_forge_adapter", return_value=adapter):
                payload = workflow_module.run_publish_flow(
                    project_root,
                    task_dir,
                    action="publish",
                    unit_id="DU-01",
                    purpose=None,
                    base_branch=None,
                    head_branch=None,
                    from_ref=None,
                    host="github",
                    publication_type=None,
                    url=None,
                    merge_commit=None,
                    cleanup=None,
                    remote_name="origin",
                    status=None,
                    create_publication=True,
                    sync_from_host=False,
                    title=None,
                    body=None,
                    today="2026-04-09",
                )

            self.assertEqual(payload["delivery_status"], "review")
            adapter.update_publication.assert_called_once_with(
                project_root,
                reference="https://github.com/example/project/pull/13",
                head_branch="du/task-2026-0013-u01-demo",
                base_branch=base_branch,
            )
            adapter.create_publication.assert_not_called()

    def test_sync_allows_recorded_custom_task_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            initial_branch = git(project_root, "branch", "--show-current")
            custom_branch = "topic/task-2026-0015-custom"
            git(project_root, "checkout", "-b", custom_branch)
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0015-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0015",
                slug="demo",
                branch=custom_branch,
                goal="Проверка работы helper на кастомной task-ветке.",
            )
            self._register_task(project_root, task_dir, "Проверка работы helper на кастомной task-ветке.")
            workflow_module.update_task_file_with_delivery_units(
                task_dir / "task.md",
                custom_branch,
                [
                    workflow_module.DeliveryUnit(
                        unit_id="DU-01",
                        purpose="Поставка через PR",
                        head="du/task-2026-0015-u01-demo",
                        base=initial_branch,
                        host="none",
                        publication_type="none",
                        status="review",
                        url=workflow_module.DELIVERY_ROW_PLACEHOLDER,
                        merge_commit=workflow_module.DELIVERY_ROW_PLACEHOLDER,
                        cleanup="не требуется",
                    )
                ],
                today="2026-04-09",
            )
            self._commit_all(project_root, "prepare custom task branch context")

            payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="sync",
                unit_id="DU-01",
                purpose=None,
                base_branch=None,
                head_branch=None,
                from_ref=None,
                host="none",
                publication_type="none",
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status="review",
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )

            self.assertEqual(payload["branch"], custom_branch)
            task_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertIn(f"| Ветка | `{custom_branch}` |", task_text)

    def test_publish_stops_before_forge_adapter_on_foreign_checkout_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0016-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0016",
                slug="demo",
                goal="Проверка stop-гейта до forge-adapter.",
            )
            self._register_task(project_root, task_dir, "Проверка stop-гейта до forge-adapter.")
            self._commit_all(project_root, "prepare task context")
            base_branch = git(project_root, "branch", "--show-current")

            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id="DU-01",
                purpose="Поставка через draft PR",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )
            self._commit_all(project_root, "start delivery unit")
            git(project_root, "checkout", "-b", "task/task-2099-9998-foreign")
            adapter_resolver = mock.Mock()

            with mock.patch.object(workflow_module, "resolve_forge_adapter", adapter_resolver):
                with self.assertRaisesRegex(ValueError, "checkout-ветка не относится к контексту этой задачи"):
                    workflow_module.run_publish_flow(
                        project_root,
                        task_dir,
                        action="publish",
                        unit_id="DU-01",
                        purpose=None,
                        base_branch=None,
                        head_branch=None,
                        from_ref=None,
                        host="github",
                        publication_type=None,
                        url=None,
                        merge_commit=None,
                        cleanup=None,
                        remote_name="origin",
                        status=None,
                        create_publication=True,
                        sync_from_host=False,
                        title=None,
                        body=None,
                        today="2026-04-09",
                    )

            adapter_resolver.assert_not_called()

    def test_sync_prefers_fresher_delivery_metadata_with_same_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0017-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0017",
                slug="demo",
                goal="Проверка слияния одинакового status по свежести task.md.",
            )
            self._register_task(project_root, task_dir, "Проверка слияния одинакового status по свежести task.md.")
            base_branch = git(project_root, "branch", "--show-current")
            task_file = task_dir / "task.md"
            publication_url = "https://github.com/example/project/pull/17"

            workflow_module.update_task_file_with_delivery_units(
                task_file,
                base_branch,
                [
                    workflow_module.DeliveryUnit(
                        unit_id="DU-01",
                        purpose="Поставка через PR",
                        head="du/task-2026-0017-u01-demo",
                        base=base_branch,
                        host="github",
                        publication_type="pr",
                        status="merged",
                        url=publication_url,
                        merge_commit="merge017",
                        cleanup="ожидается",
                    )
                ],
                today="2026-04-09",
            )
            self._commit_all(project_root, "record merged delivery unit with pending cleanup")

            delivery_branch = "du/task-2026-0017-u01-demo"
            git(project_root, "checkout", "-b", delivery_branch)
            workflow_module.update_task_file_with_delivery_units(
                task_file,
                delivery_branch,
                [
                    workflow_module.DeliveryUnit(
                        unit_id="DU-01",
                        purpose="Поставка через PR",
                        head=delivery_branch,
                        base=base_branch,
                        host="github",
                        publication_type="pr",
                        status="merged",
                        url=publication_url,
                        merge_commit="merge017",
                        cleanup="выполнено",
                    )
                ],
                today="2026-04-10",
            )
            self._commit_all(project_root, "mark cleanup completed on delivery branch")
            git(project_root, "checkout", base_branch)

            payload = workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="sync",
                unit_id="DU-01",
                purpose=None,
                base_branch=None,
                head_branch=None,
                from_ref=None,
                host="github",
                publication_type="pr",
                url=publication_url,
                merge_commit="merge017",
                cleanup=None,
                remote_name="origin",
                status="merged",
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-10",
            )

            self.assertEqual(payload["delivery_status"], "merged")
            self.assertEqual(payload["cleanup"], "выполнено")
            task_text = task_file.read_text(encoding="utf-8")
            self.assertIn("| `github` | `pr` | `merged` | `https://github.com/example/project/pull/17` | `merge017` | `выполнено` |", task_text)

    def test_sync_from_host_allows_branch_context_from_host_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0018-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0018",
                slug="demo",
                goal="Проверка host-sync после retarget base-ветки.",
            )
            self._register_task(project_root, task_dir, "Проверка host-sync после retarget base-ветки.")
            base_branch = git(project_root, "branch", "--show-current")
            task_file = task_dir / "task.md"
            workflow_module.update_task_file_with_delivery_units(
                task_file,
                base_branch,
                [
                    workflow_module.DeliveryUnit(
                        unit_id="DU-01",
                        purpose="Поставка через PR",
                        head="du/task-2026-0018-u01-demo",
                        base=base_branch,
                        host="github",
                        publication_type="pr",
                        status="review",
                        url="https://github.com/example/project/pull/18",
                        merge_commit=workflow_module.DELIVERY_ROW_PLACEHOLDER,
                        cleanup="не требуется",
                    )
                ],
                today="2026-04-09",
            )
            self._commit_all(project_root, "record stale host metadata")

            new_base_branch = "release/2026"
            git(project_root, "checkout", "-b", new_base_branch)
            adapter = mock.Mock()
            adapter.read_publication.return_value = workflow_module.PublicationSnapshot(
                host="github",
                publication_type="pr",
                status="review",
                url="https://github.com/example/project/pull/18",
                head="du/task-2026-0018-u01-demo",
                base=new_base_branch,
                merge_commit=workflow_module.DELIVERY_ROW_PLACEHOLDER,
            )

            with mock.patch.object(workflow_module, "resolve_forge_adapter", return_value=adapter):
                payload = workflow_module.run_publish_flow(
                    project_root,
                    task_dir,
                    action="sync",
                    unit_id="DU-01",
                    purpose=None,
                    base_branch=None,
                    head_branch=None,
                    from_ref=None,
                    host="github",
                    publication_type="pr",
                    url=None,
                    merge_commit=None,
                    cleanup=None,
                    remote_name="origin",
                    status=None,
                    create_publication=False,
                    sync_from_host=True,
                    title=None,
                    body=None,
                    today="2026-04-10",
                )

            adapter.read_publication.assert_called_once_with(
                project_root,
                reference="https://github.com/example/project/pull/18",
                head_branch="du/task-2026-0018-u01-demo",
                base_branch=base_branch,
            )
            self.assertEqual(payload["branch"], new_base_branch)
            task_text = task_file.read_text(encoding="utf-8")
            self.assertIn(f"| Ветка | `{new_base_branch}` |", task_text)
            self.assertIn(f"| `DU-01` | Поставка через PR | `du/task-2026-0018-u01-demo` | `{new_base_branch}` |", task_text)

    def test_sync_stops_on_foreign_checkout_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0014-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0014",
                slug="demo",
                goal="Проверка stop-условия на чужой checkout-ветке.",
            )
            self._register_task(project_root, task_dir, "Проверка stop-условия на чужой checkout-ветке.")
            self._commit_all(project_root, "prepare task context")
            base_branch = git(project_root, "branch", "--show-current")

            workflow_module.run_publish_flow(
                project_root,
                task_dir,
                action="start",
                unit_id="DU-01",
                purpose="Поставка через PR",
                base_branch=base_branch,
                head_branch=None,
                from_ref=None,
                host=None,
                publication_type=None,
                url=None,
                merge_commit=None,
                cleanup=None,
                remote_name="origin",
                status=None,
                create_publication=False,
                sync_from_host=False,
                title=None,
                body=None,
                today="2026-04-09",
            )
            self._commit_all(project_root, "start delivery unit")
            git(project_root, "checkout", "-b", "task/task-2099-9999-foreign")
            before_text = (task_dir / "task.md").read_text(encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "checkout-ветка не относится к контексту этой задачи"):
                workflow_module.run_publish_flow(
                    project_root,
                    task_dir,
                    action="sync",
                    unit_id="DU-01",
                    purpose=None,
                    base_branch=None,
                    head_branch=None,
                    from_ref=None,
                    host="none",
                    publication_type="none",
                    url=None,
                    merge_commit=None,
                    cleanup=None,
                    remote_name="origin",
                    status="local",
                    create_publication=False,
                    sync_from_host=False,
                    title=None,
                    body=None,
                    today="2026-04-09",
                )

            after_text = (task_dir / "task.md").read_text(encoding="utf-8")
            self.assertEqual(after_text, before_text)

    def test_start_stops_when_from_ref_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._init_repo(Path(tmp_dir))
            base_branch = git(project_root, "branch", "--show-current")
            self._write_registry(project_root)
            task_dir = project_root / "knowledge/tasks/TASK-2026-0010-demo"
            self._write_task(
                task_dir,
                task_id="TASK-2026-0010",
                slug="demo",
                goal="Проверка stop-условия для start.",
            )
            workflow_module.sync_task(
                project_root,
                task_dir,
                create_branch=True,
                register_if_missing=True,
                summary="Проверка stop-условия для start.",
                branch_name=None,
                inherit_branch_from_parent=False,
                today="2026-04-09",
            )
            self._commit_all(project_root, "prepare task context")

            with self.assertRaisesRegex(ValueError, "Укажите `--from-ref`"):
                workflow_module.run_publish_flow(
                    project_root,
                    task_dir,
                    action="start",
                    unit_id="DU-01",
                    purpose="Новая поставка",
                    base_branch=base_branch,
                    head_branch=None,
                    from_ref=None,
                    host=None,
                    publication_type=None,
                    url=None,
                    merge_commit=None,
                    cleanup=None,
                    remote_name="origin",
                    status=None,
                    create_publication=False,
                    sync_from_host=False,
                    title=None,
                    body=None,
                    today="2026-04-09",
                )


if __name__ == "__main__":
    unittest.main()
