from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = ROOT / "scripts" / "install_skill.py"


def load_module(module_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


install_module = load_module("task_centric_knowledge_install_skill", INSTALL_SCRIPT)


class TaskCentricKnowledgeInstallerTests(unittest.TestCase):
    def _create_legacy_compatible_project(self, root: Path) -> Path:
        project_root = root / "project"
        project_root.mkdir()
        (project_root / "AGENTS.md").write_text(
            (
                "# AGENTS\n\n"
                f"{install_module.BEGIN_MARKER}\n"
                "managed block\n"
                f"{install_module.END_MARKER}\n"
            ),
            encoding="utf-8",
        )
        for relative in install_module.COMPATIBILITY_BASELINE_TARGET_FILES:
            path = project_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(relative, encoding="utf-8")
        return project_root

    def _create_project_with_custom_agents_block(self, root: Path) -> Path:
        project_root = root / "project"
        project_root.mkdir()
        (project_root / "AGENTS.md").write_text(
            "# Пользовательский пролог\n\n"
            "## Custom\n"
            "before managed block\n",
            encoding="utf-8",
        )
        return project_root

    def test_detect_existing_system_treats_missing_only_additive_files_as_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._create_legacy_compatible_project(Path(tmp_dir))

            report = install_module.detect_existing_system(project_root)

            self.assertEqual(report.classification, "compatible")
            self.assertNotIn("knowledge/tasks/_templates/sdd.md", report.managed_present)

    def test_install_allows_abort_mode_for_legacy_compatible_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._create_legacy_compatible_project(Path(tmp_dir))

            payload = install_module.install(
                project_root,
                ROOT,
                "generic",
                force=False,
                existing_system_mode="abort",
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["existing_system_classification"], "compatible")
            self.assertTrue((project_root / "knowledge/tasks/_templates/sdd.md").exists())

    def test_detect_existing_system_counts_all_deployed_templates_as_managed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "project"
            project_root.mkdir()
            template_path = project_root / "knowledge/tasks/_templates/worklog.md"
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text("custom worklog\n", encoding="utf-8")

            report = install_module.detect_existing_system(project_root)

            self.assertEqual(report.classification, "partial_knowledge")
            self.assertIn("knowledge/tasks/_templates/worklog.md", report.managed_present)

    def test_install_force_preserves_registry_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._create_legacy_compatible_project(Path(tmp_dir))
            registry_path = project_root / "knowledge/tasks/registry.md"
            registry_path.write_text("CUSTOM-REGISTRY\n", encoding="utf-8")

            payload = install_module.install(
                project_root,
                ROOT,
                "generic",
                force=True,
                existing_system_mode="abort",
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["existing_system_classification"], "compatible")
            self.assertEqual(registry_path.read_text(encoding="utf-8"), "CUSTOM-REGISTRY\n")
            self.assertTrue((project_root / "knowledge/tasks/_templates/sdd.md").exists())

    def test_install_reports_invalid_managed_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "project"
            project_root.mkdir()
            agents_path = project_root / "AGENTS.md"
            original_content = f"# AGENTS\n\n{install_module.BEGIN_MARKER}\nmanaged block without end\n"
            agents_path.write_text(original_content, encoding="utf-8")

            payload = install_module.install(
                project_root,
                ROOT,
                "generic",
                force=False,
                existing_system_mode="adopt",
            )

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["existing_system_classification"], "partial_knowledge")
            invalid_results = [
                item
                for item in payload["results"]
                if item["key"] == "existing_system_managed_block"
            ]
            self.assertEqual(len(invalid_results), 1)
            self.assertEqual(invalid_results[0]["status"], "error")
            self.assertEqual(agents_path.read_text(encoding="utf-8"), original_content)

    def test_repeated_install_keeps_single_managed_block_and_custom_agents_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._create_project_with_custom_agents_block(Path(tmp_dir))

            first_payload = install_module.install(
                project_root,
                ROOT,
                "generic",
                force=False,
                existing_system_mode="abort",
            )
            second_payload = install_module.install(
                project_root,
                ROOT,
                "generic",
                force=True,
                existing_system_mode="abort",
            )

            self.assertTrue(first_payload["ok"])
            self.assertTrue(second_payload["ok"])
            agents_text = (project_root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertEqual(agents_text.count(install_module.BEGIN_MARKER), 1)
            self.assertEqual(agents_text.count(install_module.END_MARKER), 1)
            self.assertIn("# Пользовательский пролог", agents_text)
            self.assertIn("before managed block", agents_text)

    def test_install_force_preserves_existing_task_directory_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._create_legacy_compatible_project(Path(tmp_dir))
            task_dir = project_root / "knowledge/tasks/TASK-2026-0001-existing-task"
            task_dir.mkdir(parents=True, exist_ok=True)
            task_file = task_dir / "task.md"
            task_file.write_text("CUSTOM-TASK-DATA\n", encoding="utf-8")

            payload = install_module.install(
                project_root,
                ROOT,
                "generic",
                force=True,
                existing_system_mode="abort",
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(task_file.read_text(encoding="utf-8"), "CUSTOM-TASK-DATA\n")

    def test_install_deploys_testing_contract_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._create_project_with_custom_agents_block(Path(tmp_dir))

            payload = install_module.install(
                project_root,
                ROOT,
                "generic",
                force=False,
                existing_system_mode="abort",
            )

            self.assertTrue(payload["ok"])
            task_template = (project_root / "knowledge/tasks/_templates/task.md").read_text(encoding="utf-8")
            plan_template = (project_root / "knowledge/tasks/_templates/plan.md").read_text(encoding="utf-8")
            sdd_template = (project_root / "knowledge/tasks/_templates/sdd.md").read_text(encoding="utf-8")
            verification_template = (
                project_root / "knowledge/tasks/_templates/artifacts/verification-matrix.md"
            ).read_text(encoding="utf-8")
            handoff_template = (project_root / "knowledge/tasks/_templates/handoff.md").read_text(encoding="utf-8")
            readme_text = (project_root / "knowledge/tasks/README.md").read_text(encoding="utf-8")

            self.assertIn("## Итоговый список ручных проверок", task_template)
            self.assertIn("не дублировать общий итоговый checklist", task_template)
            self.assertIn("## Контур публикации", task_template)
            self.assertIn("| Unit ID | Назначение | Head | Base | Host | Тип публикации | Статус | URL | Merge commit | Cleanup |", task_template)
            self.assertIn("`planned` — контур поставки ещё не стартовал.", task_template)
            self.assertIn("реально исполним в проекте и допустим его правилами", plan_template)
            self.assertIn("artifacts/verification-matrix.md", plan_template)
            self.assertIn("## Зависимости и границы", plan_template)
            self.assertIn("### Критический функционал", plan_template)
            self.assertIn("### Основной сценарий", plan_template)
            self.assertIn("Полный invariant set", sdd_template)
            self.assertIn("artifacts/verification-matrix.md", sdd_template)
            self.assertIn("### Допустимые и недопустимые связи", sdd_template)
            self.assertIn("### Новые зависимости и их обоснование", sdd_template)
            self.assertIn("Матрица проверки по задаче", verification_template)
            self.assertIn("Статус покрытия", verification_template)
            self.assertIn("допустимые и недопустимые связи", verification_template)
            self.assertIn("основной источник истины", handoff_template)
            self.assertIn("не считается обязательной автопроверкой задачи", readme_text)
            self.assertIn("delivery unit живёт внутри `task.md`", readme_text)
            self.assertIn("artifacts/verification-matrix.md", readme_text)
            self.assertIn("## Контроль code-related задач", readme_text)
            self.assertIn("Отдельной команды `finalize-task` нет", readme_text)

    def test_install_deploys_updated_agents_testing_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._create_project_with_custom_agents_block(Path(tmp_dir))

            payload = install_module.install(
                project_root,
                ROOT,
                "generic",
                force=False,
                existing_system_mode="abort",
            )

            self.assertTrue(payload["ok"])
            agents_text = (project_root / "AGENTS.md").read_text(encoding="utf-8")

            self.assertIn("`1` — продолжить текущую задачу", agents_text)
            self.assertIn("Латиница вроде `A/B/C` запрещена.", agents_text)
            self.assertIn("реально исполним в текущем проекте и допустим его правилами", agents_text)
            self.assertIn("не должна попадать в обязательные автопроверки задачи", agents_text)
            self.assertIn("Доказательный verify-контур", agents_text)
            self.assertIn("artifacts/verification-matrix.md", agents_text)
            self.assertIn("### Контроль code-related задач", agents_text)
            self.assertIn("### Контроль code-related задач", agents_text)
            self.assertIn("критический функционал", agents_text)
            self.assertIn("### Контур публикации", agents_text)
            self.assertIn("delivery units не переведены в `merged` или `closed`", agents_text)
            self.assertIn("python3 scripts/task_workflow.py --publish-action start|publish|sync|merge|close", agents_text)

    def test_install_deploys_publish_rules_for_1c_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = self._create_project_with_custom_agents_block(Path(tmp_dir))

            payload = install_module.install(
                project_root,
                ROOT,
                "1c",
                force=False,
                existing_system_mode="abort",
            )

            self.assertTrue(payload["ok"])
            agents_text = (project_root / "AGENTS.md").read_text(encoding="utf-8")
            readme_text = (project_root / "knowledge/tasks/README.md").read_text(encoding="utf-8")
            task_template = (project_root / "knowledge/tasks/_templates/task.md").read_text(encoding="utf-8")

            self.assertIn("### Контур публикации", agents_text)
            self.assertIn("Доказательный verify-контур", agents_text)
            self.assertIn("### Контроль code-related задач", agents_text)
            self.assertIn("валидного remote, поддерживаемого host adapter", agents_text)
            self.assertIn("delivery unit живёт внутри `task.md`", readme_text)
            self.assertIn("artifacts/verification-matrix.md", readme_text)
            self.assertIn("## Контур публикации", task_template)


if __name__ == "__main__":
    unittest.main()
