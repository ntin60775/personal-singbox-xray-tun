#!/usr/bin/env python3
"""Install or refresh the task-centric knowledge system in a target project."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


SKILL_NAME = "task-centric-knowledge"
BEGIN_MARKER = "⟦⟦BEGIN_TASK_KNOWLEDGE_SYSTEM#KB01⟧⟧"
END_MARKER = "⟦⟦END_TASK_KNOWLEDGE_SYSTEM#KB01⟧⟧"
MIGRATION_NOTE_NAME = "MIGRATION-SUGGESTION.md"
PROFILE_TO_BLOCK = {
    "generic": "assets/agents-managed-block-generic.md",
    "1c": "assets/agents-managed-block-1c.md",
}
KNOWLEDGE_ASSET_FILES = (
    "assets/knowledge/README.md",
    "assets/knowledge/operations/README.md",
    "assets/knowledge/tasks/README.md",
    "assets/knowledge/tasks/registry.md",
    "assets/knowledge/tasks/_templates/task.md",
    "assets/knowledge/tasks/_templates/plan.md",
    "assets/knowledge/tasks/_templates/sdd.md",
    "assets/knowledge/tasks/_templates/artifacts/verification-matrix.md",
    "assets/knowledge/tasks/_templates/worklog.md",
    "assets/knowledge/tasks/_templates/decisions.md",
    "assets/knowledge/tasks/_templates/handoff.md",
)
REQUIRED_RELATIVE_PATHS = (
    "SKILL.md",
    "agents/openai.yaml",
    "references/deployment.md",
    "references/upgrade-transition.md",
    "references/task-routing.md",
    "references/task-workflow.md",
    "scripts/install_skill.py",
    "scripts/task_workflow.py",
    "assets/agents-managed-block-generic.md",
    "assets/agents-managed-block-1c.md",
    *KNOWLEDGE_ASSET_FILES,
)
FOREIGN_SYSTEM_INDICATORS = (
    ".sisyphus",
    "doc/tasks",
    "docs/tasks",
    "docs/roadmap",
    "docs/plans",
)
MANAGED_TARGET_FILES = tuple(
    str(Path(relative).relative_to("assets"))
    for relative in KNOWLEDGE_ASSET_FILES
)
PROJECT_DATA_TARGET_FILES = (
    "knowledge/tasks/registry.md",
)
FORCE_OVERWRITABLE_TARGET_FILES = tuple(
    relative
    for relative in MANAGED_TARGET_FILES
    if relative not in PROJECT_DATA_TARGET_FILES
)
ADDITIVE_MANAGED_TARGET_FILES = (
    "knowledge/tasks/_templates/sdd.md",
    "knowledge/tasks/_templates/artifacts/verification-matrix.md",
)
COMPATIBILITY_BASELINE_TARGET_FILES = tuple(
    relative
    for relative in MANAGED_TARGET_FILES
    if relative not in ADDITIVE_MANAGED_TARGET_FILES
)


@dataclass
class StepResult:
    key: str
    status: str
    detail: str
    path: str | None = None


@dataclass
class ExistingSystemReport:
    classification: str
    recommendation: str
    managed_present: list[str]
    foreign_present: list[str]
    agents_block_state: str


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_source(source_root: str | None) -> Path:
    return Path(source_root).resolve() if source_root else skill_root()


def asset_to_target_relative(asset_relative: str) -> str:
    return str(Path(asset_relative).relative_to("assets"))


def validate_source(source_root: Path) -> list[StepResult]:
    results: list[StepResult] = []
    for relative in REQUIRED_RELATIVE_PATHS:
        path = source_root / relative
        if path.exists():
            results.append(StepResult("source", "ok", "Исходный ресурс найден", str(path)))
        else:
            results.append(StepResult("source", "error", "Отсутствует исходный ресурс", str(path)))
    return results


def validate_target(project_root: Path) -> list[StepResult]:
    results: list[StepResult] = []
    if project_root.is_dir():
        results.append(StepResult("project_root", "ok", "Каталог проекта найден", str(project_root)))
    else:
        results.append(StepResult("project_root", "error", "Каталог проекта не найден", str(project_root)))
        return results

    agents_path = project_root / "AGENTS.md"
    if agents_path.exists():
        results.append(StepResult("agents", "ok", "Найден AGENTS.md", str(agents_path)))
    else:
        results.append(StepResult("agents", "warning", "AGENTS.md не найден; будет создан snippet для ручного включения", str(agents_path)))

    knowledge_path = project_root / "knowledge"
    if knowledge_path.exists():
        results.append(StepResult("knowledge", "warning", "Каталог knowledge уже существует", str(knowledge_path)))
    else:
        results.append(StepResult("knowledge", "ok", "Каталог knowledge будет создан", str(knowledge_path)))
    return results


def detect_managed_block_state(existing: str) -> str:
    begin_count = existing.count(BEGIN_MARKER)
    end_count = existing.count(END_MARKER)
    if begin_count == 0 and end_count == 0:
        return "absent"
    if begin_count == 1 and end_count == 1:
        return "managed" if existing.index(BEGIN_MARKER) < existing.index(END_MARKER) else "invalid"
    return "invalid"


def detect_existing_system(project_root: Path) -> ExistingSystemReport:
    managed_present = [relative for relative in MANAGED_TARGET_FILES if (project_root / relative).exists()]
    foreign_present = [relative for relative in FOREIGN_SYSTEM_INDICATORS if (project_root / relative).exists()]
    missing_managed = [relative for relative in MANAGED_TARGET_FILES if relative not in managed_present]
    agents_path = project_root / "AGENTS.md"
    agents_block_state = "absent"
    if agents_path.exists():
        agents_text = agents_path.read_text(encoding="utf-8")
        agents_block_state = detect_managed_block_state(agents_text)

    has_any_managed = bool(managed_present or agents_block_state != "absent")
    has_full_managed = len(managed_present) == len(MANAGED_TARGET_FILES)
    has_compatibility_baseline = all(
        (project_root / relative).exists()
        for relative in COMPATIBILITY_BASELINE_TARGET_FILES
    )
    missing_only_additive = all(
        relative in ADDITIVE_MANAGED_TARGET_FILES
        for relative in missing_managed
    )
    has_foreign = bool(foreign_present)

    if not has_any_managed and not has_foreign:
        return ExistingSystemReport(
            classification="clean",
            recommendation="Можно устанавливать knowledge-систему без миграции.",
            managed_present=managed_present,
            foreign_present=foreign_present,
            agents_block_state=agents_block_state,
        )
    if (has_full_managed or (has_compatibility_baseline and missing_only_additive)) and not has_foreign and agents_block_state != "invalid":
        recommendation = "Проект уже близок к целевой knowledge-модели; допустима обычная установка или обновление."
        if has_compatibility_baseline and not has_full_managed:
            recommendation = "Обнаружена совместимая предыдущая версия knowledge-системы без новых additive managed-файлов; обычная установка безопасно докопирует недостающие шаблоны."
        return ExistingSystemReport(
            classification="compatible",
            recommendation=recommendation,
            managed_present=managed_present,
            foreign_present=foreign_present,
            agents_block_state=agents_block_state,
        )
    if has_any_managed and not has_foreign:
        return ExistingSystemReport(
            classification="partial_knowledge",
            recommendation="Обнаружена частично совместимая knowledge-структура; сначала решить, принимать её как основу (`adopt`) или обновлять принудительно.",
            managed_present=managed_present,
            foreign_present=foreign_present,
            agents_block_state=agents_block_state,
        )
    if not has_any_managed and has_foreign:
        return ExistingSystemReport(
            classification="foreign_system",
            recommendation="Обнаружена другая система хранения; рекомендуется сначала миграция в knowledge-систему.",
            managed_present=managed_present,
            foreign_present=foreign_present,
            agents_block_state=agents_block_state,
        )
    return ExistingSystemReport(
        classification="mixed_system",
        recommendation="Обнаружена смешанная система хранения: частичная knowledge-модель и сторонние контуры. Рекомендуется явный миграционный сценарий.",
        managed_present=managed_present,
        foreign_present=foreign_present,
        agents_block_state=agents_block_state,
    )


def summarize_existing_system(report: ExistingSystemReport) -> list[StepResult]:
    results: list[StepResult] = []
    results.append(
        StepResult(
            "existing_system",
            "warning" if report.classification not in {"clean", "compatible"} else "ok",
            f"Классификация существующей системы хранения: {report.classification}. {report.recommendation}",
        )
    )
    for relative in report.managed_present:
        results.append(StepResult("existing_system_managed", "ok", "Найден совместимый managed-файл", relative))
    for relative in report.foreign_present:
        results.append(StepResult("existing_system_foreign", "warning", "Найден внешний контур хранения", relative))
    if report.agents_block_state == "managed":
        results.append(StepResult("existing_system_managed_block", "ok", "Найден managed-блок knowledge-системы в AGENTS.md"))
    if report.agents_block_state == "invalid":
        results.append(
            StepResult(
                "existing_system_managed_block",
                "error",
                "В AGENTS.md обнаружены неконсистентные managed-маркеры knowledge-системы; installer не будет дописывать новый блок поверх поврежденного состояния.",
                "AGENTS.md",
            )
        )
    return results


def has_errors(results: list[StepResult]) -> bool:
    return any(item.status == "error" for item in results)


def asset_to_target_path(project_root: Path, asset_relative: str) -> Path:
    return project_root / asset_to_target_relative(asset_relative)


def copy_knowledge_files(project_root: Path, source_root: Path, *, force: bool) -> list[StepResult]:
    results: list[StepResult] = []
    for relative in KNOWLEDGE_ASSET_FILES:
        source_path = source_root / relative
        target_relative = asset_to_target_relative(relative)
        target_path = asset_to_target_path(project_root, relative)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            if force and target_relative in FORCE_OVERWRITABLE_TARGET_FILES:
                target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
                results.append(StepResult("copy", "ok", "Файл обновлен из дистрибутива", str(target_path)))
                continue
            detail = "Файл уже существует; оставлен без изменений"
            if force and target_relative in PROJECT_DATA_TARGET_FILES:
                detail = "Файл содержит проектные данные; оставлен без изменений даже при --force"
            results.append(StepResult("copy", "warning", detail, str(target_path)))
            continue
        target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        results.append(StepResult("copy", "ok", "Файл развернут", str(target_path)))
    return results


def render_agents_block(source_root: Path, profile: str) -> str:
    block_path = source_root / PROFILE_TO_BLOCK[profile]
    return block_path.read_text(encoding="utf-8").strip() + "\n"


def upsert_block(existing: str, block: str) -> tuple[str, str]:
    managed_block_state = detect_managed_block_state(existing)
    if managed_block_state == "managed":
        start = existing.index(BEGIN_MARKER)
        end = existing.index(END_MARKER) + len(END_MARKER)
        updated = existing[:start].rstrip() + "\n\n" + block + "\n"
        tail = existing[end:].lstrip()
        if tail:
            updated += "\n" + tail
        return updated.rstrip() + "\n", "updated"
    if managed_block_state == "invalid":
        raise ValueError("В AGENTS.md обнаружены неконсистентные managed-маркеры knowledge-системы.")
    separator = "" if existing.endswith("\n") or not existing else "\n"
    updated = existing + separator
    if existing.strip():
        updated += "\n"
    updated += block
    return updated.rstrip() + "\n", "inserted"


def install_agents_block(project_root: Path, source_root: Path, profile: str) -> list[StepResult]:
    results: list[StepResult] = []
    block = render_agents_block(source_root, profile)
    agents_path = project_root / "AGENTS.md"
    if agents_path.exists():
        current = agents_path.read_text(encoding="utf-8")
        try:
            updated, mode = upsert_block(current, block)
        except ValueError as error:
            results.append(StepResult("agents", "error", str(error), str(agents_path)))
            return results
        agents_path.write_text(updated, encoding="utf-8")
        detail = "Managed-блок добавлен в AGENTS.md" if mode == "inserted" else "Managed-блок обновлен в AGENTS.md"
        results.append(StepResult("agents", "ok", detail, str(agents_path)))
        return results

    snippet_path = project_root / f"AGENTS.task-centric-knowledge.{profile}.md"
    snippet_path.write_text(block, encoding="utf-8")
    results.append(
        StepResult(
            "agents",
            "warning",
            "AGENTS.md не найден; создан snippet для ручного включения",
            str(snippet_path),
        )
    )
    return results


def validate_existing_system_policy(classification: str, mode: str) -> list[StepResult]:
    if classification in {"clean", "compatible"}:
        return []
    if classification == "partial_knowledge" and mode in {"adopt", "migrate"}:
        return [
            StepResult(
                "existing_system_policy",
                "warning",
                f"Частично совместимая knowledge-структура принята в режиме {mode}.",
            )
        ]
    if classification in {"foreign_system", "mixed_system"} and mode == "migrate":
        return [
            StepResult(
                "existing_system_policy",
                "warning",
                "Обнаружена другая система хранения; продолжаю только потому, что явно выбран режим migrate.",
            )
        ]
    return [
        StepResult(
            "existing_system_policy",
            "error",
            "Установка остановлена: обнаружена существующая система хранения. Сначала проверь классификацию и используй явный режим adopt или migrate.",
        )
    ]


def write_migration_suggestion(project_root: Path, report: ExistingSystemReport, profile: str) -> StepResult:
    migration_path = project_root / "knowledge" / MIGRATION_NOTE_NAME
    migration_path.parent.mkdir(parents=True, exist_ok=True)
    managed_lines = "\n".join(f"- `{item}`" for item in report.managed_present) or "- совместимые managed-файлы не обнаружены"
    foreign_lines = "\n".join(f"- `{item}`" for item in report.foreign_present) or "- внешние контуры не обнаружены"
    content = f"""# Предложение миграции в knowledge-систему

## Контекст

- профиль установки: `{profile}`
- классификация текущей системы: `{report.classification}`
- рекомендация installer: {report.recommendation}

## Что найдено

### Совместимые элементы knowledge-системы

{managed_lines}

### Сторонние контуры хранения

{foreign_lines}

## Рекомендуемый порядок миграции

1. Назначить `knowledge/` целевым источником истины по задачам.
2. Определить, какие старые контуры хранения нужно перестать использовать для новых задач.
3. Переносить в `knowledge/tasks/` только актуальные карточки задач, планы, решения и журналы, а не весь исторический шум.
4. Для каждой переносимой задачи завести `task.md`, `plan.md`, запись в `registry.md` и при необходимости подзадачи.
5. Для сложных задач дополнительно заводить `sdd.md` внутри каталога задачи и связывать его с `plan.md`.
6. После переноса закрепить в `AGENTS.md`, что новая работа ведётся только через `knowledge/`.

## Что installer не делает автоматически

- не переносит старые артефакты;
- не переименовывает исторические каталоги;
- не удаляет старую систему хранения;
- не принимает решение, что именно из старой системы нужно переносить.
"""
    migration_path.write_text(content, encoding="utf-8")
    return StepResult("migration", "warning", "Создано явное предложение миграции с другой системы хранения", str(migration_path))


def install(project_root: Path, source_root: Path, profile: str, *, force: bool, existing_system_mode: str) -> dict[str, object]:
    results: list[StepResult] = []
    results.extend(validate_source(source_root))
    results.extend(validate_target(project_root))
    existing_report = detect_existing_system(project_root)
    results.extend(summarize_existing_system(existing_report))
    results.extend(validate_existing_system_policy(existing_report.classification, existing_system_mode))
    if has_errors(results):
        return {
            "skill": SKILL_NAME,
            "project_root": str(project_root),
            "profile": profile,
            "existing_system_classification": existing_report.classification,
            "ok": False,
            "results": [asdict(item) for item in results],
        }

    results.extend(copy_knowledge_files(project_root, source_root, force=force))
    if existing_system_mode == "migrate" and existing_report.classification in {"foreign_system", "mixed_system", "partial_knowledge"}:
        results.append(write_migration_suggestion(project_root, existing_report, profile))
    results.extend(install_agents_block(project_root, source_root, profile))
    return {
        "skill": SKILL_NAME,
        "project_root": str(project_root),
        "profile": profile,
        "existing_system_classification": existing_report.classification,
        "ok": not has_errors(results),
        "results": [asdict(item) for item in results],
    }


def check(project_root: Path, source_root: Path, profile: str) -> dict[str, object]:
    results: list[StepResult] = []
    results.extend(validate_source(source_root))
    results.extend(validate_target(project_root))
    existing_report = detect_existing_system(project_root)
    results.extend(summarize_existing_system(existing_report))
    results.append(StepResult("profile", "ok", f"Выбран профиль {profile}", PROFILE_TO_BLOCK[profile]))
    return {
        "skill": SKILL_NAME,
        "project_root": str(project_root),
        "profile": profile,
        "existing_system_classification": existing_report.classification,
        "ok": not has_errors(results),
        "results": [asdict(item) for item in results],
    }


def print_text_report(payload: dict[str, object]) -> None:
    print(f"skill={payload['skill']}")
    print(f"project_root={payload['project_root']}")
    print(f"profile={payload['profile']}")
    print(f"existing_system_classification={payload['existing_system_classification']}")
    print(f"ok={payload['ok']}")
    for item in payload["results"]:
        suffix = f" path={item['path']}" if item.get("path") else ""
        print(f"- [{item['status']}] {item['key']}: {item['detail']}{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deploy or refresh the task-centric knowledge system in a target project.",
        allow_abbrev=False,
    )
    parser.add_argument("--project-root", required=True, help="Абсолютный путь к корню целевого проекта.")
    parser.add_argument("--source-root", help="Путь к исходному skill. По умолчанию — текущий каталог skill.")
    parser.add_argument("--mode", choices=("check", "install"), default="check", help="check только валидирует, install развертывает структуру.")
    parser.add_argument("--profile", choices=("generic", "1c"), default="generic", help="Профиль managed-блока для AGENTS.md.")
    parser.add_argument("--force", action="store_true", help="Перезаписать обновляемые managed-файлы knowledge/ шаблонами из дистрибутива, но не project data вроде registry.md.")
    parser.add_argument(
        "--existing-system-mode",
        choices=("abort", "adopt", "migrate"),
        default="abort",
        help="Как вести себя при обнаружении существующей системы хранения: abort, adopt или migrate.",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Формат вывода.")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    source_root = resolve_source(args.source_root)
    payload = (
        install(project_root, source_root, args.profile, force=args.force, existing_system_mode=args.existing_system_mode)
        if args.mode == "install"
        else check(project_root, source_root, args.profile)
    )
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_text_report(payload)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
