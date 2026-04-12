#!/usr/bin/env python3
"""Sync task-centric knowledge metadata with the current Git task workflow."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


PLACEHOLDER_BRANCH_VALUES = {"", "—", "не создана"}
TASK_SUMMARY_FIELD = "Человекочитаемое описание"
TABLE_ROW_RE = re.compile(r"^\|\s*(?P<field>[^|]+?)\s*\|\s*(?P<value>.*?)\s*\|$")
DELIVERY_SECTION_TITLE = "## Контур публикации"
DELIVERY_TABLE_HEADER = (
    "| Unit ID | Назначение | Head | Base | Host | Тип публикации | "
    "Статус | URL | Merge commit | Cleanup |"
)
DELIVERY_TABLE_SEPARATOR = "|---------|------------|------|------|------|----------------|--------|-----|--------------|---------|"
DELIVERY_INTRO_LINES = (
    "Delivery unit описывает конкретную поставку через ветку и публикацию.",
    "В одном `task.md` допускается `0..N` delivery units.",
)
DELIVERY_ROW_PLACEHOLDER = "—"
VALID_HOSTS = {"none", "github", "gitlab", "generic"}
VALID_PUBLICATION_TYPES = {"none", "pr", "mr"}
VALID_DELIVERY_STATUSES = {"planned", "local", "draft", "review", "merged", "closed"}
VALID_CLEANUP_VALUES = {"не требуется", "ожидается", "выполнено"}
DELIVERY_STATUS_PRIORITY = {
    "planned": 0,
    "local": 1,
    "draft": 2,
    "review": 3,
    "closed": 4,
    "merged": 5,
}
PUBLISH_FLOW_TRANSITIONS = {
    "start": {
        "planned": {"local"},
        "local": {"local"},
    },
    "publish": {
        "local": {"draft"},
        "draft": {"review"},
    },
    "sync": {
        "planned": {"planned", "local"},
        "local": {"local", "draft", "closed"},
        "draft": {"draft", "review", "closed"},
        "review": {"review", "merged", "closed"},
        "merged": {"merged"},
        "closed": {"closed"},
    },
    "merge": {
        "review": {"merged"},
    },
    "close": {
        "local": {"closed"},
        "draft": {"closed"},
        "review": {"closed"},
    },
}
UNIT_ID_RE = re.compile(r"^(?:DU-)?0*(?P<number>\d+)$", re.IGNORECASE)
MERGE_REQUEST_URL_RE = re.compile(r"/(?:-?/)?merge_requests/(?P<number>\d+)(?:/|$)")


@dataclass
class StepResult:
    key: str
    status: str
    detail: str
    path: str | None = None


@dataclass
class DeliveryUnit:
    unit_id: str
    purpose: str
    head: str
    base: str
    host: str
    publication_type: str
    status: str
    url: str
    merge_commit: str
    cleanup: str

    @classmethod
    def from_cells(cls, cells: list[str]) -> "DeliveryUnit":
        if len(cells) != 10:
            raise ValueError(f"Ожидалось 10 колонок delivery unit, получено {len(cells)}.")
        normalized_cells = [normalize_table_value(cell) for cell in cells]
        return cls(
            unit_id=normalize_unit_id(normalized_cells[0]),
            purpose=normalize_delivery_text(normalized_cells[1]),
            head=normalize_delivery_text(normalized_cells[2]),
            base=normalize_delivery_text(normalized_cells[3]),
            host=normalize_delivery_text(normalized_cells[4]),
            publication_type=normalize_delivery_text(normalized_cells[5]),
            status=normalize_delivery_text(normalized_cells[6]),
            url=normalize_delivery_text(normalized_cells[7]),
            merge_commit=normalize_delivery_text(normalized_cells[8]),
            cleanup=normalize_delivery_text(normalized_cells[9]),
        )

    def to_cells(self) -> list[str]:
        return [
            format_table_value(self.unit_id),
            sanitize_delivery_text(self.purpose, allow_placeholder=False),
            format_table_value(self.head),
            format_table_value(self.base),
            format_table_value(self.host),
            format_table_value(self.publication_type),
            format_table_value(self.status),
            format_table_value(self.url),
            format_table_value(self.merge_commit),
            format_table_value(self.cleanup),
        ]


@dataclass
class DeliveryUnitVersion:
    unit: DeliveryUnit
    freshness_rank: tuple[int, int, int, str]


@dataclass
class PublicationSnapshot:
    host: str
    publication_type: str
    status: str
    url: str
    head: str
    base: str
    merge_commit: str


def normalize_table_value(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`") and len(value) >= 2:
        return value[1:-1]
    return value


def format_table_value(value: str) -> str:
    return f"`{value}`"


def normalize_delivery_text(value: str) -> str:
    normalized = normalize_table_value(value)
    return normalized or DELIVERY_ROW_PLACEHOLDER


def sanitize_delivery_text(value: str, *, allow_placeholder: bool = True) -> str:
    sanitized = value.replace("\n", " ").replace("|", "/").strip()
    if not sanitized and allow_placeholder:
        return DELIVERY_ROW_PLACEHOLDER
    return sanitized


def sanitize_registry_summary(value: str) -> str:
    return value.replace("\n", " ").replace("|", "/").strip()


def normalize_unit_id(unit_id: str) -> str:
    match = UNIT_ID_RE.fullmatch(unit_id.strip())
    if not match:
        raise ValueError(f"Некорректный Unit ID: {unit_id!r}. Ожидался формат `DU-01`.")
    return f"DU-{int(match.group('number')):02d}"


def delivery_unit_index(unit_id: str) -> int:
    return int(normalize_unit_id(unit_id).split("-", 1)[1])


def normalize_branch_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", value.lower())
    token = re.sub(r"-{2,}", "-", token).strip("-")
    return token


def default_branch_name(task_id: str, short_name: str) -> str:
    return f"task/{normalize_branch_token(task_id)}-{normalize_branch_token(short_name)}"


def default_delivery_branch_name(task_id: str, unit_id: str, short_name: str) -> str:
    return (
        f"du/{normalize_branch_token(task_id)}-u{delivery_unit_index(unit_id):02d}-"
        f"{normalize_branch_token(short_name)}"
    )


def extract_delivery_branch_index(task_id: str, branch_name: str) -> int | None:
    pattern = re.compile(rf"^du/{re.escape(normalize_branch_token(task_id))}-u(?P<number>\d+)(?:-|$)")
    match = pattern.match(branch_name.strip())
    if not match:
        return None
    return int(match.group("number"))


def run_git(project_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", "-C", str(project_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        message = stderr or stdout or "git command failed"
        raise RuntimeError(message)
    return completed


def current_git_branch(project_root: Path) -> str:
    return run_git(project_root, "branch", "--show-current").stdout.strip()


def worktree_is_clean(project_root: Path) -> bool:
    return run_git(project_root, "status", "--porcelain").stdout.strip() == ""


def dirty_paths(project_root: Path) -> list[str]:
    output = run_git(project_root, "status", "--porcelain").stdout.splitlines()
    paths: list[str] = []
    for line in output:
        if len(line) < 4:
            continue
        candidate = line[3:]
        if " -> " in candidate:
            candidate = candidate.split(" -> ", 1)[1]
        paths.append(candidate.strip())
    return paths


def branch_exists(project_root: Path, branch_name: str) -> bool:
    completed = run_git(project_root, "rev-parse", "--verify", f"refs/heads/{branch_name}", check=False)
    return completed.returncode == 0


def has_remote(project_root: Path) -> bool:
    return bool(run_git(project_root, "remote").stdout.split())


def remote_url(project_root: Path, remote_name: str = "origin") -> str | None:
    completed = run_git(project_root, "remote", "get-url", remote_name, check=False)
    if completed.returncode != 0:
        return None
    url = completed.stdout.strip()
    return url or None


def remote_hostname(url: str | None) -> str | None:
    if not url:
        return None
    if "://" in url:
        parsed = urlparse(url)
        return parsed.hostname.lower() if parsed.hostname else None
    if url.startswith("git@") and ":" in url:
        host_part = url.split("@", 1)[1].split(":", 1)[0].strip()
        return host_part.lower() if host_part else None
    return None


def detect_host_kind(host_value: str | None) -> str:
    if not host_value or host_value == DELIVERY_ROW_PLACEHOLDER:
        return "none"
    lowered = host_value.lower()
    if lowered in VALID_HOSTS:
        return lowered
    if "github" in lowered:
        return "github"
    if "gitlab" in lowered:
        return "gitlab"
    return "generic"


def default_publication_type_for_host(host_kind: str) -> str | None:
    if host_kind == "none":
        return "none"
    if host_kind == "github":
        return "pr"
    if host_kind == "gitlab":
        return "mr"
    return None


def normalize_publication_type(publication_type: str | None, host_kind: str) -> str:
    if publication_type:
        normalized = publication_type.strip().lower()
        if normalized not in VALID_PUBLICATION_TYPES:
            raise ValueError(
                f"Некорректный тип публикации: {publication_type!r}. "
                "Допустимы `none`, `pr`, `mr`."
            )
        return normalized
    default_type = default_publication_type_for_host(host_kind)
    if default_type is None:
        raise ValueError("Для host=`generic` нужно явно указать `--publication-type`.")
    return default_type


def normalize_cleanup_value(cleanup: str | None, *, default: str) -> str:
    value = (cleanup or default).strip()
    if value not in VALID_CLEANUP_VALUES:
        raise ValueError(
            f"Некорректное значение Cleanup: {value!r}. "
            "Допустимы `не требуется`, `ожидается`, `выполнено`."
        )
    return value


def normalize_delivery_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized not in VALID_DELIVERY_STATUSES:
        raise ValueError(
            f"Некорректный статус delivery unit: {status!r}. "
            "Допустимы `planned`, `local`, `draft`, `review`, `merged`, `closed`."
        )
    return normalized


def split_markdown_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [part.strip() for part in stripped.strip("|").split("|")]


def find_section_bounds(lines: list[str], title: str) -> tuple[int, int] | None:
    for start_index, line in enumerate(lines):
        if line.strip() != title:
            continue
        end_index = len(lines)
        for candidate in range(start_index + 1, len(lines)):
            if lines[candidate].startswith("## "):
                end_index = candidate
                break
        return start_index, end_index
    return None


def parse_delivery_units(lines: list[str]) -> list[DeliveryUnit]:
    bounds = find_section_bounds(lines, DELIVERY_SECTION_TITLE)
    if bounds is None:
        return []
    start_index, end_index = bounds
    units: list[DeliveryUnit] = []
    for line in lines[start_index:end_index]:
        cells = split_markdown_row(line)
        if not cells or len(cells) != 10:
            continue
        if cells[0] == "Unit ID" or cells[0].startswith("---------"):
            continue
        if normalize_table_value(cells[0]) == DELIVERY_ROW_PLACEHOLDER:
            continue
        units.append(DeliveryUnit.from_cells(cells))
    return units


def render_delivery_units_section(units: list[DeliveryUnit]) -> list[str]:
    rendered = [
        DELIVERY_SECTION_TITLE,
        "",
        *DELIVERY_INTRO_LINES,
        "",
        DELIVERY_TABLE_HEADER,
        DELIVERY_TABLE_SEPARATOR,
    ]
    if not units:
        rendered.append(
            "| `—` | — | `—` | `—` | `none` | `none` | `planned` | `—` | `—` | `не требуется` |"
        )
        return rendered
    for unit in sorted(units, key=lambda item: delivery_unit_index(item.unit_id)):
        rendered.append("| " + " | ".join(unit.to_cells()) + " |")
    return rendered


def upsert_delivery_units_section(lines: list[str], units: list[DeliveryUnit]) -> list[str]:
    rendered = render_delivery_units_section(units)
    bounds = find_section_bounds(lines, DELIVERY_SECTION_TITLE)
    if bounds is None:
        insert_at = next(
            (index for index, line in enumerate(lines) if line.strip() == "## Текущий этап"),
            len(lines),
        )
        prefix = lines[:insert_at]
        suffix = lines[insert_at:]
        if prefix and prefix[-1] != "":
            prefix = prefix + [""]
        updated = prefix + rendered
        if suffix and updated[-1] != "":
            updated.append("")
        return updated + suffix
    start_index, end_index = bounds
    updated = lines[:start_index] + rendered
    if end_index < len(lines) and updated and updated[-1] != "" and lines[end_index] != "":
        updated.append("")
    updated.extend(lines[end_index:])
    return updated


def next_delivery_unit_id(project_root: Path, task_id: str, units: list[DeliveryUnit]) -> str:
    known_indexes = {delivery_unit_index(unit.unit_id) for unit in units}
    branches = run_git(project_root, "for-each-ref", "--format=%(refname:short)", "refs/heads").stdout.splitlines()
    for branch_name in branches:
        branch_index = extract_delivery_branch_index(task_id, branch_name)
        if branch_index is not None:
            known_indexes.add(branch_index)
    next_index = max(known_indexes, default=0) + 1
    return f"DU-{next_index:02d}"


def task_file_is_dirty(project_root: Path, task_file_relative: str) -> bool:
    normalized_target = task_file_relative.replace("\\", "/").rstrip("/")
    return any(path.replace("\\", "/").rstrip("/") == normalized_target for path in dirty_paths(project_root))


def task_file_history_depth(project_root: Path, ref_name: str, task_file_relative: str) -> int:
    completed = run_git(project_root, "rev-list", "--count", ref_name, "--", task_file_relative, check=False)
    if completed.returncode != 0:
        return 0
    return int((completed.stdout or "0").strip() or "0")


def parse_task_file_freshness(output: str, fallback_ref: str, history_depth: int) -> tuple[int, int, int, str]:
    payload = output.strip()
    if not payload:
        return (0, 0, history_depth, fallback_ref)
    timestamp_text, _, commit_id = payload.partition("\x00")
    timestamp = int(timestamp_text or "0")
    return (1, timestamp, history_depth, commit_id or fallback_ref)


def current_task_file_freshness(
    project_root: Path,
    task_file: Path,
    task_file_relative: str,
) -> tuple[int, int, int, str]:
    active_branch = current_git_branch(project_root) or "HEAD"
    history_depth = task_file_history_depth(project_root, active_branch, task_file_relative)
    if task_file_is_dirty(project_root, task_file_relative):
        return (2, task_file.stat().st_mtime_ns, history_depth, f"WORKTREE:{active_branch}")
    completed = run_git(
        project_root,
        "log",
        "-1",
        "--format=%ct%x00%H",
        active_branch,
        "--",
        task_file_relative,
        check=False,
    )
    if completed.returncode == 0:
        parsed = parse_task_file_freshness(completed.stdout, active_branch, history_depth)
        if parsed[0] != 0:
            return parsed
    completed = run_git(project_root, "log", "-1", "--format=%ct%x00%H", active_branch, check=False)
    return parse_task_file_freshness(completed.stdout, active_branch, history_depth)


def ref_task_file_freshness(project_root: Path, ref_name: str, task_file_relative: str) -> tuple[int, int, int, str]:
    history_depth = task_file_history_depth(project_root, ref_name, task_file_relative)
    completed = run_git(
        project_root,
        "log",
        "-1",
        "--format=%ct%x00%H",
        ref_name,
        "--",
        task_file_relative,
        check=False,
    )
    if completed.returncode == 0:
        parsed = parse_task_file_freshness(completed.stdout, ref_name, history_depth)
        if parsed[0] != 0:
            return parsed
    completed = run_git(project_root, "log", "-1", "--format=%ct%x00%H", ref_name, check=False)
    return parse_task_file_freshness(completed.stdout, ref_name, history_depth)


def delivery_unit_merge_key(version: DeliveryUnitVersion) -> tuple[int, tuple[int, int, int, str], int, int, int, int]:
    unit = version.unit
    return (
        DELIVERY_STATUS_PRIORITY.get(normalize_delivery_status(unit.status), -1),
        version.freshness_rank,
        int(unit.merge_commit != DELIVERY_ROW_PLACEHOLDER),
        int(unit.url != DELIVERY_ROW_PLACEHOLDER),
        int(unit.cleanup not in {"не требуется", DELIVERY_ROW_PLACEHOLDER}),
        sum(
            int(value not in {DELIVERY_ROW_PLACEHOLDER, "none", "не требуется"})
            for value in (
                unit.purpose,
                unit.head,
                unit.base,
                unit.host,
                unit.publication_type,
                unit.url,
                unit.merge_commit,
                unit.cleanup,
            )
        ),
    )


def preferred_delivery_value(
    versions: list[DeliveryUnitVersion],
    field_name: str,
    *,
    placeholders: set[str],
) -> str:
    for version in versions:
        unit = version.unit
        value = getattr(unit, field_name)
        if value not in placeholders:
            return value
    return getattr(versions[0].unit, field_name)


def merge_delivery_unit_versions(versions: list[DeliveryUnitVersion]) -> DeliveryUnit:
    if not versions:
        raise ValueError("Нельзя объединить пустой список delivery units.")
    ordered_versions = sorted(versions, key=delivery_unit_merge_key, reverse=True)
    best = ordered_versions[0].unit
    return DeliveryUnit(
        unit_id=best.unit_id,
        purpose=preferred_delivery_value(ordered_versions, "purpose", placeholders={DELIVERY_ROW_PLACEHOLDER}),
        head=preferred_delivery_value(ordered_versions, "head", placeholders={DELIVERY_ROW_PLACEHOLDER}),
        base=preferred_delivery_value(ordered_versions, "base", placeholders={DELIVERY_ROW_PLACEHOLDER}),
        host=preferred_delivery_value(ordered_versions, "host", placeholders={DELIVERY_ROW_PLACEHOLDER, "none"}),
        publication_type=preferred_delivery_value(
            ordered_versions,
            "publication_type",
            placeholders={DELIVERY_ROW_PLACEHOLDER, "none"},
        ),
        status=best.status,
        url=preferred_delivery_value(ordered_versions, "url", placeholders={DELIVERY_ROW_PLACEHOLDER}),
        merge_commit=preferred_delivery_value(
            ordered_versions,
            "merge_commit",
            placeholders={DELIVERY_ROW_PLACEHOLDER},
        ),
        cleanup=preferred_delivery_value(
            ordered_versions,
            "cleanup",
            placeholders={DELIVERY_ROW_PLACEHOLDER, "не требуется"},
        ),
    )


def related_publish_refs(project_root: Path, task_dir: Path, fields: dict[str, str]) -> list[str]:
    task_id = fields.get("ID задачи", "").strip()
    short_name = fields.get("Краткое имя", "").strip()
    refs: set[str] = set()
    all_branches = run_git(project_root, "for-each-ref", "--format=%(refname:short)", "refs/heads").stdout.splitlines()
    for branch_name in all_branches:
        if extract_delivery_branch_index(task_id, branch_name) is not None:
            refs.add(branch_name)
    recorded_branch = fields.get("Ветка", "").strip()
    if recorded_branch and recorded_branch not in PLACEHOLDER_BRANCH_VALUES and branch_exists(project_root, recorded_branch):
        refs.add(recorded_branch)
    if task_id and short_name:
        default_task_branch = default_branch_name(task_id, short_name)
        if branch_exists(project_root, default_task_branch):
            refs.add(default_task_branch)
    try:
        parent_branch = find_parent_branch(task_dir)
    except ValueError:
        parent_branch = None
    if parent_branch and branch_exists(project_root, parent_branch):
        refs.add(parent_branch)
    active_branch = current_git_branch(project_root)
    refs.discard(active_branch)
    return sorted(refs)


def read_task_lines_from_ref(project_root: Path, ref_name: str, task_file_relative: str) -> list[str] | None:
    completed = run_git(project_root, "show", f"{ref_name}:{task_file_relative}", check=False)
    if completed.returncode != 0:
        return None
    return completed.stdout.splitlines()


def path_exists_in_head(project_root: Path, relative_path: str) -> bool:
    return read_task_lines_from_ref(project_root, "HEAD", relative_path) is not None


def collect_delivery_units(
    project_root: Path,
    task_dir: Path,
    fields: dict[str, str],
    current_lines: list[str],
) -> list[DeliveryUnit]:
    task_file_relative = (task_dir / "task.md").relative_to(project_root).as_posix()
    units_by_id: dict[str, list[DeliveryUnitVersion]] = {}
    current_freshness = current_task_file_freshness(project_root, task_dir / "task.md", task_file_relative)
    for unit in parse_delivery_units(current_lines):
        units_by_id.setdefault(unit.unit_id, []).append(
            DeliveryUnitVersion(unit=unit, freshness_rank=current_freshness)
        )
    for ref_name in related_publish_refs(project_root, task_dir, fields):
        ref_lines = read_task_lines_from_ref(project_root, ref_name, task_file_relative)
        if ref_lines is None:
            continue
        ref_freshness = ref_task_file_freshness(project_root, ref_name, task_file_relative)
        for unit in parse_delivery_units(ref_lines):
            units_by_id.setdefault(unit.unit_id, []).append(
                DeliveryUnitVersion(unit=unit, freshness_rank=ref_freshness)
            )
    return sorted(
        (merge_delivery_unit_versions(unit_versions) for unit_versions in units_by_id.values()),
        key=lambda item: delivery_unit_index(item.unit_id),
    )


def find_delivery_unit(units: list[DeliveryUnit], unit_id: str | None) -> DeliveryUnit:
    if unit_id:
        normalized_id = normalize_unit_id(unit_id)
        for unit in units:
            if unit.unit_id == normalized_id:
                return unit
        raise ValueError(f"В publish-блоке не найден delivery unit {normalized_id}.")
    if len(units) == 1:
        return units[0]
    raise ValueError("Нужно явно указать `--unit-id`, потому что delivery unit неоднозначен.")


def replace_delivery_unit(units: list[DeliveryUnit], updated_unit: DeliveryUnit) -> list[DeliveryUnit]:
    replaced = False
    result: list[DeliveryUnit] = []
    for unit in units:
        if unit.unit_id == updated_unit.unit_id:
            result.append(updated_unit)
            replaced = True
            continue
        result.append(unit)
    if not replaced:
        result.append(updated_unit)
    return sorted(result, key=lambda item: delivery_unit_index(item.unit_id))


def validate_transition(action: str, current_status: str, target_status: str) -> None:
    current = normalize_delivery_status(current_status)
    target = normalize_delivery_status(target_status)
    allowed_targets = PUBLISH_FLOW_TRANSITIONS[action].get(current, set())
    if target not in allowed_targets:
        raise ValueError(
            f"Недопустимый переход для `{action}`: {current} -> {target}. "
            f"Разрешены: {', '.join(sorted(allowed_targets)) or 'нет'}."
        )


def infer_base_branch(project_root: Path) -> str:
    completed = run_git(project_root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False)
    if completed.returncode == 0:
        ref = completed.stdout.strip()
        if ref:
            return ref.rsplit("/", 1)[-1]
    candidates = [branch for branch in ("main", "master") if branch_exists(project_root, branch)]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise ValueError("Невозможно автоматически определить base-ветку: найдены и `main`, и `master`.")
    active_branch = current_git_branch(project_root)
    if active_branch and not active_branch.startswith("du/"):
        return active_branch
    raise ValueError("Не удалось определить base-ветку. Укажите `--base-branch`.")


def ref_exists(project_root: Path, ref_name: str) -> bool:
    completed = run_git(project_root, "rev-parse", "--verify", ref_name, check=False)
    return completed.returncode == 0


def resolve_delivery_start_ref(
    project_root: Path,
    *,
    base_branch: str,
    from_ref: str | None,
) -> str:
    if from_ref:
        if not ref_exists(project_root, from_ref):
            raise ValueError(f"Не найден `--from-ref`: {from_ref}.")
        return from_ref
    active_branch = current_git_branch(project_root)
    if active_branch == base_branch or not active_branch:
        return base_branch
    raise ValueError(
        "Нельзя безопасно выбрать стартовую точку delivery-ветки автоматически: "
        f"активная ветка `{active_branch}` не совпадает с base `{base_branch}`. "
        "Укажите `--from-ref`."
    )


def ensure_delivery_branch(
    project_root: Path,
    *,
    target_branch: str,
    base_branch: str,
    from_ref: str | None,
) -> str:
    active_branch = current_git_branch(project_root)
    if active_branch == target_branch:
        return "reused"
    if not worktree_is_clean(project_root):
        raise ValueError("Для `start` нужен чистый worktree перед переключением delivery-ветки.")
    if branch_exists(project_root, target_branch):
        run_git(project_root, "checkout", target_branch)
        return "switched"
    start_ref = resolve_delivery_start_ref(project_root, base_branch=base_branch, from_ref=from_ref)
    run_git(project_root, "checkout", "-b", target_branch, start_ref)
    return "created"


def command_exists(command_name: str) -> bool:
    return shutil.which(command_name) is not None


def run_command(
    project_root: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        cwd=project_root,
        check=False,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        message = stderr or stdout or "command failed"
        raise RuntimeError(message)
    return completed


def extract_publication_url(output_text: str) -> str | None:
    for line in reversed(output_text.splitlines()):
        candidate = line.strip()
        if candidate.startswith("http://") or candidate.startswith("https://"):
            return candidate
    return None


def parse_merge_request_reference(reference: str, head_branch: str) -> str:
    match = MERGE_REQUEST_URL_RE.search(reference)
    if match:
        return match.group("number")
    return head_branch


class ForgeAdapter:
    host_kind = "generic"
    cli_name = ""

    def __init__(self, hostname: str) -> None:
        self.hostname = hostname

    def ensure_cli(self) -> None:
        if not command_exists(self.cli_name):
            raise ValueError(f"Для host `{self.host_kind}` не найден CLI `{self.cli_name}`.")

    def ensure_auth(self, project_root: Path) -> None:
        raise NotImplementedError

    def create_publication(
        self,
        project_root: Path,
        *,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
        draft: bool,
    ) -> PublicationSnapshot:
        raise NotImplementedError

    def update_publication(
        self,
        project_root: Path,
        *,
        reference: str,
        head_branch: str,
        base_branch: str,
    ) -> PublicationSnapshot:
        raise NotImplementedError

    def read_publication(
        self,
        project_root: Path,
        *,
        reference: str,
        head_branch: str,
        base_branch: str,
    ) -> PublicationSnapshot:
        raise NotImplementedError


class GitHubAdapter(ForgeAdapter):
    host_kind = "github"
    cli_name = "gh"

    def ensure_auth(self, project_root: Path) -> None:
        completed = run_command(
            project_root,
            "gh",
            "auth",
            "status",
            "--hostname",
            self.hostname,
            check=False,
        )
        if completed.returncode != 0:
            raise ValueError(
                f"`gh auth status --hostname {self.hostname}` завершился ошибкой. "
                "Publish-flow не должен обещать сетевые действия без валидной auth."
            )

    def create_publication(
        self,
        project_root: Path,
        *,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
        draft: bool,
    ) -> PublicationSnapshot:
        self.ensure_cli()
        self.ensure_auth(project_root)
        command = [
            "gh",
            "pr",
            "create",
            "--base",
            base_branch,
            "--head",
            head_branch,
            "--title",
            title,
            "--body",
            body,
        ]
        if draft:
            command.append("--draft")
        completed = run_command(project_root, *command)
        publication_url = extract_publication_url(completed.stdout)
        if not publication_url:
            raise ValueError("`gh pr create` не вернул URL публикации.")
        return self.read_publication(
            project_root,
            reference=publication_url,
            head_branch=head_branch,
            base_branch=base_branch,
        )

    def update_publication(
        self,
        project_root: Path,
        *,
        reference: str,
        head_branch: str,
        base_branch: str,
    ) -> PublicationSnapshot:
        self.ensure_cli()
        self.ensure_auth(project_root)
        run_command(project_root, "gh", "pr", "ready", reference)
        return self.read_publication(
            project_root,
            reference=reference,
            head_branch=head_branch,
            base_branch=base_branch,
        )

    def read_publication(
        self,
        project_root: Path,
        *,
        reference: str,
        head_branch: str,
        base_branch: str,
    ) -> PublicationSnapshot:
        self.ensure_cli()
        self.ensure_auth(project_root)
        completed = run_command(
            project_root,
            "gh",
            "pr",
            "view",
            reference,
            "--json",
            "url,isDraft,state,headRefName,baseRefName,mergeCommit",
        )
        payload = json.loads(completed.stdout)
        merge_commit = payload.get("mergeCommit")
        merge_commit_value = DELIVERY_ROW_PLACEHOLDER
        if isinstance(merge_commit, dict):
            merge_commit_value = merge_commit.get("oid") or DELIVERY_ROW_PLACEHOLDER
        elif isinstance(merge_commit, str) and merge_commit.strip():
            merge_commit_value = merge_commit.strip()
        state = str(payload.get("state") or "").upper()
        if state == "MERGED" or merge_commit_value != DELIVERY_ROW_PLACEHOLDER:
            status = "merged"
        elif state == "CLOSED":
            status = "closed"
        elif payload.get("isDraft"):
            status = "draft"
        else:
            status = "review"
        return PublicationSnapshot(
            host="github",
            publication_type="pr",
            status=status,
            url=str(payload.get("url") or DELIVERY_ROW_PLACEHOLDER),
            head=str(payload.get("headRefName") or head_branch),
            base=str(payload.get("baseRefName") or base_branch),
            merge_commit=merge_commit_value,
        )


class GitLabAdapter(ForgeAdapter):
    host_kind = "gitlab"
    cli_name = "glab"

    def ensure_auth(self, project_root: Path) -> None:
        completed = run_command(
            project_root,
            "glab",
            "auth",
            "status",
            "--hostname",
            self.hostname,
            check=False,
        )
        if completed.returncode != 0:
            raise ValueError(
                f"`glab auth status --hostname {self.hostname}` завершился ошибкой. "
                "Publish-flow не должен обещать сетевые действия без валидной auth."
            )

    def create_publication(
        self,
        project_root: Path,
        *,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
        draft: bool,
    ) -> PublicationSnapshot:
        self.ensure_cli()
        self.ensure_auth(project_root)
        command = [
            "glab",
            "mr",
            "create",
            "--source-branch",
            head_branch,
            "--target-branch",
            base_branch,
            "--title",
            title,
            "--description",
            body,
            "--yes",
        ]
        if draft:
            command.append("--draft")
        run_command(project_root, *command)
        return self.read_publication(
            project_root,
            reference=head_branch,
            head_branch=head_branch,
            base_branch=base_branch,
        )

    def update_publication(
        self,
        project_root: Path,
        *,
        reference: str,
        head_branch: str,
        base_branch: str,
    ) -> PublicationSnapshot:
        self.ensure_cli()
        self.ensure_auth(project_root)
        run_command(
            project_root,
            "glab",
            "mr",
            "update",
            parse_merge_request_reference(reference, head_branch),
            "--ready",
            "--yes",
        )
        return self.read_publication(
            project_root,
            reference=reference,
            head_branch=head_branch,
            base_branch=base_branch,
        )

    def read_publication(
        self,
        project_root: Path,
        *,
        reference: str,
        head_branch: str,
        base_branch: str,
    ) -> PublicationSnapshot:
        self.ensure_cli()
        self.ensure_auth(project_root)
        completed = run_command(
            project_root,
            "glab",
            "mr",
            "view",
            parse_merge_request_reference(reference, head_branch),
            "--output",
            "json",
        )
        payload = json.loads(completed.stdout)
        merge_commit_value = (
            payload.get("merge_commit_sha")
            or payload.get("mergeCommitSha")
            or DELIVERY_ROW_PLACEHOLDER
        )
        state = str(payload.get("state") or "").lower()
        is_draft = bool(payload.get("draft") or payload.get("work_in_progress"))
        if state == "merged" or merge_commit_value != DELIVERY_ROW_PLACEHOLDER:
            status = "merged"
        elif state == "closed":
            status = "closed"
        elif is_draft:
            status = "draft"
        else:
            status = "review"
        return PublicationSnapshot(
            host="gitlab",
            publication_type="mr",
            status=status,
            url=str(payload.get("web_url") or payload.get("webUrl") or DELIVERY_ROW_PLACEHOLDER),
            head=str(payload.get("source_branch") or payload.get("sourceBranch") or head_branch),
            base=str(payload.get("target_branch") or payload.get("targetBranch") or base_branch),
            merge_commit=str(merge_commit_value),
        )


def resolve_forge_adapter(project_root: Path, host_kind: str, remote_name: str, url: str | None) -> ForgeAdapter:
    hostname = remote_hostname(url) or remote_hostname(remote_url(project_root, remote_name))
    if not hostname:
        raise ValueError("Не удалось определить hostname forge-хостинга по remote или URL.")
    if host_kind == "github":
        return GitHubAdapter(hostname)
    if host_kind == "gitlab":
        return GitLabAdapter(hostname)
    raise ValueError(f"Для host `{host_kind}` нет сетевого adapter-а.")

def replace_task_field(lines: list[str], field: str, value: str) -> None:
    replacement = f"| {field} | {format_table_value(value)} |"
    for index, line in enumerate(lines):
        match = TABLE_ROW_RE.match(line)
        if match and match.group("field").strip() == field:
            lines[index] = replacement
            return
    raise ValueError(f"В task.md не найдено поле {field!r}.")


def upsert_task_field(lines: list[str], field: str, value: str, *, after_field: str) -> None:
    replacement = f"| {field} | {format_table_value(value)} |"
    insert_index: int | None = None
    existing_indexes: list[int] = []
    for index, line in enumerate(lines):
        match = TABLE_ROW_RE.match(line)
        if not match:
            continue
        current_field = match.group("field").strip()
        if current_field == field:
            existing_indexes.append(index)
            continue
        if current_field == after_field:
            insert_index = index + 1
    if existing_indexes:
        first_index = existing_indexes[0]
        lines[first_index] = replacement
        for duplicate_index in reversed(existing_indexes[1:]):
            del lines[duplicate_index]
        return
    if insert_index is not None:
        lines.insert(insert_index, replacement)
        return
    raise ValueError(f"В task.md не найдено поле {after_field!r} для вставки {field!r}.")


def read_task_fields(task_file: Path) -> tuple[list[str], dict[str, str]]:
    lines = task_file.read_text(encoding="utf-8").splitlines()
    return lines, parse_task_fields(lines)


def parse_task_fields(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines:
        match = TABLE_ROW_RE.match(line)
        if not match:
            continue
        field_name = match.group("field").strip()
        if field_name in fields:
            continue
        fields[field_name] = normalize_table_value(match.group("value"))
    return fields


def find_parent_branch(task_dir: Path, *, project_root: Path | None = None) -> str:
    if task_dir.parent.name != "subtasks":
        raise ValueError("Нельзя наследовать ветку: задача не находится внутри каталога subtasks/.")
    parent_task_file = task_dir.parent.parent / "task.md"
    if not parent_task_file.exists():
        raise ValueError("Нельзя наследовать ветку: у родительской задачи отсутствует task.md.")
    _, parent_fields = read_task_fields(parent_task_file)
    parent_branch = parent_fields.get("Ветка", "").strip()
    if project_root is not None:
        parent_task_id = parent_fields.get("ID задачи", "").strip()
        parent_short_name = parent_fields.get("Краткое имя", "").strip()
        if parent_task_id and parent_short_name:
            default_parent_branch = default_branch_name(parent_task_id, parent_short_name)
            if branch_exists(project_root, default_parent_branch):
                parent_task_relative = parent_task_file.relative_to(project_root).as_posix()
                ref_lines = read_task_lines_from_ref(project_root, default_parent_branch, parent_task_relative)
                ref_branch = ""
                if ref_lines is not None:
                    ref_fields = parse_task_fields(ref_lines)
                    ref_branch = ref_fields.get("Ветка", "").strip()
                if parent_branch not in PLACEHOLDER_BRANCH_VALUES:
                    inferred_base_branch = infer_base_branch(project_root)
                    if (
                        ref_branch not in PLACEHOLDER_BRANCH_VALUES
                        and parent_branch == inferred_base_branch
                        and ref_branch != parent_branch
                        and not commit_is_ancestor(project_root, default_parent_branch, "HEAD")
                    ):
                        return ref_branch
                    return parent_branch
                if ref_branch not in PLACEHOLDER_BRANCH_VALUES:
                    return ref_branch
                return default_parent_branch
    if parent_branch in PLACEHOLDER_BRANCH_VALUES:
        raise ValueError("Нельзя наследовать ветку: у родительской задачи ветка ещё не зафиксирована.")
    return parent_branch


def resolve_target_branch(
    project_root: Path,
    task_dir: Path,
    fields: dict[str, str],
    *,
    branch_name: str | None,
    inherit_branch_from_parent: bool,
) -> str:
    if branch_name:
        return branch_name
    if inherit_branch_from_parent:
        return find_parent_branch(task_dir, project_root=project_root)
    recorded_branch = fields.get("Ветка", "").strip()
    if recorded_branch not in PLACEHOLDER_BRANCH_VALUES:
        return recorded_branch
    task_id = fields.get("ID задачи", "").strip()
    short_name = fields.get("Краткое имя", "").strip()
    if not task_id or not short_name:
        raise ValueError("В task.md должны быть заполнены поля `ID задачи` и `Краткое имя`.")
    return default_branch_name(task_id, short_name)


def update_task_file(task_file: Path, branch_name: str, *, today: str, summary: str | None = None) -> dict[str, str]:
    lines, fields = read_task_fields(task_file)
    if summary:
        upsert_task_field(lines, TASK_SUMMARY_FIELD, summary, after_field="Краткое имя")
    replace_task_field(lines, "Ветка", branch_name)
    replace_task_field(lines, "Дата обновления", today)
    task_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if summary:
        fields[TASK_SUMMARY_FIELD] = summary
    fields["Ветка"] = branch_name
    fields["Дата обновления"] = today
    return fields


def update_task_file_with_delivery_units(
    task_file: Path,
    branch_name: str,
    delivery_units: list[DeliveryUnit],
    *,
    today: str,
    summary: str | None = None,
) -> dict[str, str]:
    lines, fields = read_task_fields(task_file)
    if summary:
        upsert_task_field(lines, TASK_SUMMARY_FIELD, summary, after_field="Краткое имя")
    replace_task_field(lines, "Ветка", branch_name)
    replace_task_field(lines, "Дата обновления", today)
    updated_lines = upsert_delivery_units_section(lines, delivery_units)
    task_file.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    if summary:
        fields[TASK_SUMMARY_FIELD] = summary
    fields["Ветка"] = branch_name
    fields["Дата обновления"] = today
    return fields


def task_summary_from_fields(fields: dict[str, str]) -> str | None:
    summary = sanitize_registry_summary(fields.get(TASK_SUMMARY_FIELD, ""))
    if not summary or summary == DELIVERY_ROW_PLACEHOLDER:
        return None
    return summary


def derive_goal_summary_from_task(task_file: Path) -> str | None:
    lines = task_file.read_text(encoding="utf-8").splitlines()
    return derive_goal_summary_from_lines(lines)


def derive_goal_summary_from_lines(lines: list[str]) -> str | None:
    in_goal = False
    for line in lines:
        if line.startswith("## ") and line != "## Цель":
            if in_goal:
                break
        if line == "## Цель":
            in_goal = True
            continue
        if not in_goal:
            continue
        stripped = line.strip()
        if stripped:
            return sanitize_registry_summary(stripped)
    return None


def tracked_goal_summary(project_root: Path, task_dir: Path) -> str | None:
    task_file_relative = (task_dir / "task.md").relative_to(project_root).as_posix()
    tracked_lines = read_task_lines_from_ref(project_root, "HEAD", task_file_relative)
    if tracked_lines is None:
        return None
    return derive_goal_summary_from_lines(tracked_lines)


def commit_history_for_path(project_root: Path, relative_path: str, *, ref_name: str = "HEAD") -> list[str]:
    return run_git(project_root, "log", ref_name, "--format=%H", "--", relative_path).stdout.splitlines()


def commit_introducing_goal_summary(
    project_root: Path,
    task_dir: Path,
    goal_summary: str,
    *,
    ref_name: str = "HEAD",
) -> str | None:
    task_file_relative = (task_dir / "task.md").relative_to(project_root).as_posix()
    matching_commit: str | None = None
    for commit_id in commit_history_for_path(project_root, task_file_relative, ref_name=ref_name):
        lines = read_task_lines_from_ref(project_root, commit_id, task_file_relative)
        if lines is None:
            continue
        if derive_goal_summary_from_lines(lines) == goal_summary:
            matching_commit = commit_id
            continue
        if matching_commit is not None:
            return matching_commit
    return matching_commit


def registry_summary_from_lines(lines: list[str], task_id: str) -> tuple[str | None, bool]:
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("| `"):
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if len(parts) != 7:
            continue
        row_task_id = normalize_table_value(parts[0])
        if row_task_id != task_id:
            continue
        return parts[6].strip(), True
    return None, False


def commit_introducing_registry_summary(
    project_root: Path,
    task_id: str,
    summary: str,
    *,
    ref_name: str = "HEAD",
) -> str | None:
    registry_relative = "knowledge/tasks/registry.md"
    matching_commit: str | None = None
    for commit_id in commit_history_for_path(project_root, registry_relative, ref_name=ref_name):
        lines = read_task_lines_from_ref(project_root, commit_id, registry_relative)
        if lines is None:
            continue
        registry_summary, row_exists = registry_summary_from_lines(lines, task_id)
        if row_exists and registry_summary == summary:
            matching_commit = commit_id
            continue
        if matching_commit is not None:
            return matching_commit
    return matching_commit


def commit_is_ancestor(project_root: Path, ancestor: str, descendant: str) -> bool:
    completed = run_git(project_root, "merge-base", "--is-ancestor", ancestor, descendant, check=False)
    return completed.returncode == 0


def legacy_goal_summary_overrides_registry(
    project_root: Path,
    task_dir: Path,
    *,
    task_id: str,
    goal_summary: str | None,
    existing_summary: str | None,
    ref_name: str | None = None,
) -> bool:
    sanitized_existing = legacy_registry_summary_candidate(existing_summary)
    if not goal_summary or not sanitized_existing or goal_summary == sanitized_existing:
        return False
    history_ref_name = ref_name or "HEAD"
    if ref_name is None:
        current_head_goal_summary = tracked_goal_summary(project_root, task_dir)
        if current_head_goal_summary not in (None, goal_summary):
            return True
    goal_commit = commit_introducing_goal_summary(
        project_root,
        task_dir,
        goal_summary,
        ref_name=history_ref_name,
    )
    if goal_commit is None:
        return False
    registry_commit = commit_introducing_registry_summary(
        project_root,
        task_id,
        sanitized_existing,
        ref_name=history_ref_name,
    )
    if registry_commit is None:
        return True
    if goal_commit == registry_commit:
        return False
    return commit_is_ancestor(project_root, registry_commit, goal_commit)


def count_task_field_occurrences(lines: list[str], field: str) -> int:
    count = 0
    for line in lines:
        match = TABLE_ROW_RE.match(line)
        if match and match.group("field").strip() == field:
            count += 1
    return count


def derive_summary_from_task(task_file: Path) -> str | None:
    _, fields = read_task_fields(task_file)
    return task_summary_from_fields(fields) or derive_goal_summary_from_task(task_file)


def legacy_registry_summary_candidate(value: str | None) -> str | None:
    sanitized = sanitize_registry_summary(value or "")
    if not sanitized or sanitized == DELIVERY_ROW_PLACEHOLDER:
        return None
    return sanitized


def preferred_registry_summary(
    fields: dict[str, str],
    *,
    goal_summary: str | None,
    summary: str | None,
    existing_summary: str | None = None,
    prefer_goal_over_existing: bool = False,
    ignore_task_summary: bool = False,
) -> str | None:
    explicit_task_summary = task_summary_from_fields(fields)
    if explicit_task_summary and not ignore_task_summary:
        return explicit_task_summary

    explicit_summary = legacy_registry_summary_candidate(summary)
    if explicit_summary:
        return explicit_summary

    existing_registry_summary = legacy_registry_summary_candidate(existing_summary)
    if prefer_goal_over_existing and goal_summary:
        return goal_summary
    if existing_registry_summary:
        return existing_registry_summary

    return goal_summary


def read_registry_lines(
    project_root: Path,
    *,
    ref_name: str | None = None,
    allow_untracked_fallback: bool = False,
) -> list[str]:
    registry_relative = "knowledge/tasks/registry.md"
    registry_path = project_root / registry_relative
    if ref_name is None:
        if not registry_path.exists():
            raise ValueError("Не найден knowledge/tasks/registry.md.")
        return registry_path.read_text(encoding="utf-8").splitlines()
    completed = run_git(project_root, "show", f"{ref_name}:{registry_relative}", check=False)
    if completed.returncode != 0:
        if (
            allow_untracked_fallback
            and registry_path.exists()
            and not path_exists_in_head(project_root, registry_relative)
        ):
            return registry_path.read_text(encoding="utf-8").splitlines()
        raise ValueError(f"Не найден knowledge/tasks/registry.md в `{ref_name}`.")
    return completed.stdout.splitlines()


def read_existing_registry_summary(
    project_root: Path,
    task_id: str,
    *,
    ref_name: str | None = None,
    allow_untracked_fallback: bool = False,
) -> tuple[str | None, bool]:
    lines = read_registry_lines(
        project_root,
        ref_name=ref_name,
        allow_untracked_fallback=allow_untracked_fallback,
    )
    return registry_summary_from_lines(lines, task_id)


def read_task_context(
    project_root: Path,
    task_dir: Path,
    *,
    ref_name: str | None = None,
    allow_untracked_fallback: bool = False,
) -> tuple[list[str], dict[str, str], str | None]:
    task_file = task_dir / "task.md"
    if ref_name is None:
        lines, fields = read_task_fields(task_file)
    else:
        task_file_relative = task_file.relative_to(project_root).as_posix()
        lines = read_task_lines_from_ref(project_root, ref_name, task_file_relative)
        if lines is None:
            if (
                allow_untracked_fallback
                and task_file.exists()
                and not path_exists_in_head(project_root, task_file_relative)
            ):
                lines, fields = read_task_fields(task_file)
                return lines, fields, derive_goal_summary_from_lines(lines)
            raise ValueError(f"Не найден {task_file_relative} в `{ref_name}`.")
        fields = parse_task_fields(lines)
    return lines, fields, derive_goal_summary_from_lines(lines)


def preflight_registry_summary(
    project_root: Path,
    task_dir: Path,
    *,
    register_if_missing: bool,
    summary: str | None,
    ref_name: str | None = None,
    allow_untracked_fallback: bool = False,
) -> str:
    lines, fields, goal_summary = read_task_context(
        project_root,
        task_dir,
        ref_name=ref_name,
        allow_untracked_fallback=allow_untracked_fallback,
    )
    task_id = fields.get("ID задачи", "").strip()
    existing_summary, row_exists = read_existing_registry_summary(
        project_root,
        task_id,
        ref_name=ref_name,
        allow_untracked_fallback=allow_untracked_fallback,
    )
    if not row_exists and not register_if_missing:
        raise ValueError(f"В knowledge/tasks/registry.md не найдена строка для {task_id}.")
    prefer_goal_over_existing = legacy_goal_summary_overrides_registry(
        project_root,
        task_dir,
        task_id=task_id,
        goal_summary=goal_summary,
        existing_summary=existing_summary,
        ref_name=ref_name,
    )
    explicit_summary = legacy_registry_summary_candidate(summary)
    ignore_task_summary = count_task_field_occurrences(lines, TASK_SUMMARY_FIELD) > 1 and bool(explicit_summary)
    resolved_summary = preferred_registry_summary(
        fields,
        goal_summary=goal_summary,
        summary=summary,
        existing_summary=existing_summary,
        prefer_goal_over_existing=prefer_goal_over_existing,
        ignore_task_summary=ignore_task_summary,
    )
    if not resolved_summary:
        raise ValueError(
            "Для строки registry.md нужно заполнить `Человекочитаемое описание` в task.md, "
            "передать `--summary` или заполнить секцию `Цель`."
        )
    return resolved_summary


def sync_preflight_ref_name(
    project_root: Path,
    *,
    create_branch: bool,
    target_branch: str,
) -> str | None:
    active_branch = current_git_branch(project_root)
    if create_branch and active_branch != target_branch and branch_exists(project_root, target_branch):
        return target_branch
    return None


def publish_preflight_ref_name(
    project_root: Path,
    *,
    action: str,
    target_branch: str | None,
    start_ref: str | None,
    current_unit: DeliveryUnit | None = None,
) -> str | None:
    if action == "start":
        if target_branch and branch_exists(project_root, target_branch):
            return target_branch
        return start_ref
    if current_unit and current_unit.head != DELIVERY_ROW_PLACEHOLDER and branch_exists(project_root, current_unit.head):
        active_branch = current_git_branch(project_root)
        if not active_branch or active_branch != current_unit.head:
            return current_unit.head
    return None


def publication_body_ref_name(project_root: Path, current_unit: DeliveryUnit) -> str | None:
    if current_git_branch(project_root) == current_unit.head:
        return None
    if current_unit.head != DELIVERY_ROW_PLACEHOLDER and branch_exists(project_root, current_unit.head):
        return current_unit.head
    return None


def default_publication_title(fields: dict[str, str], purpose: str) -> str:
    task_id = fields.get("ID задачи", "").strip()
    return f"{task_id}: {purpose}"


def default_publication_body(
    fields: dict[str, str],
    purpose: str,
    task_dir: Path,
    *,
    summary: str | None = None,
) -> str:
    task_id = fields.get("ID задачи", "").strip()
    summary_value = summary or derive_summary_from_task(task_dir / "task.md") or "Публикация delivery unit."
    return (
        f"Task: {task_id}\n"
        f"Purpose: {purpose}\n"
        f"Summary: {summary_value}\n"
    )


def create_delivery_unit(
    *,
    unit_id: str,
    purpose: str,
    head_branch: str,
    base_branch: str,
) -> DeliveryUnit:
    return DeliveryUnit(
        unit_id=normalize_unit_id(unit_id),
        purpose=sanitize_delivery_text(purpose, allow_placeholder=False),
        head=head_branch,
        base=base_branch,
        host="none",
        publication_type="none",
        status="planned",
        url=DELIVERY_ROW_PLACEHOLDER,
        merge_commit=DELIVERY_ROW_PLACEHOLDER,
        cleanup="не требуется",
    )


def resolve_requested_host(
    project_root: Path,
    *,
    requested_host: str | None,
    url: str | None,
    remote_name: str,
) -> str:
    if requested_host and requested_host != "auto":
        normalized = detect_host_kind(requested_host)
        if normalized not in VALID_HOSTS:
            raise ValueError(f"Некорректный host: {requested_host!r}.")
        return normalized
    url_host = detect_host_kind(url)
    if url_host != "none":
        return url_host
    remote_host = detect_host_kind(remote_hostname(remote_url(project_root, remote_name)))
    return remote_host


def resolve_explicit_snapshot(
    current_unit: DeliveryUnit,
    *,
    host_kind: str,
    publication_type: str,
    target_status: str,
    url: str | None,
    merge_commit: str | None,
) -> PublicationSnapshot:
    resolved_url = normalize_delivery_text(url or current_unit.url)
    resolved_merge_commit = normalize_delivery_text(merge_commit or current_unit.merge_commit)
    return PublicationSnapshot(
        host=host_kind,
        publication_type=publication_type,
        status=target_status,
        url=resolved_url,
        head=current_unit.head,
        base=current_unit.base,
        merge_commit=resolved_merge_commit,
    )


def existing_publication_reference(current_unit: DeliveryUnit, url: str | None) -> str:
    for candidate in (url, current_unit.url, current_unit.head):
        resolved = normalize_delivery_text(candidate or "")
        if resolved != DELIVERY_ROW_PLACEHOLDER:
            return resolved
    raise ValueError("Для перехода существующей draft-публикации в review нужен URL или head-ветка.")


def resolve_publish_snapshot(
    project_root: Path,
    task_dir: Path,
    fields: dict[str, str],
    current_unit: DeliveryUnit,
    *,
    action: str,
    requested_host: str | None,
    requested_publication_type: str | None,
    requested_status: str | None,
    url: str | None,
    merge_commit: str | None,
    remote_name: str,
    create_publication: bool,
    sync_from_host: bool,
    title: str | None,
    body: str | None,
    summary: str | None,
) -> PublicationSnapshot:
    if create_publication and sync_from_host:
        raise ValueError("Нельзя одновременно использовать `--create-publication` и `--sync-from-host`.")

    host_kind = resolve_requested_host(
        project_root,
        requested_host=requested_host,
        url=url or current_unit.url,
        remote_name=remote_name,
    )
    publication_type = normalize_publication_type(requested_publication_type, host_kind)

    if action == "publish":
        if requested_status:
            target_status = normalize_delivery_status(requested_status)
        elif current_unit.status == "local":
            target_status = "draft"
        elif current_unit.status == "draft":
            target_status = "review"
        else:
            raise ValueError(
                "Для `publish` helper может только открыть draft-публикацию или перевести draft в review."
            )
    elif action == "merge":
        target_status = "merged"
    elif action == "close":
        target_status = "closed"
    else:
        target_status = normalize_delivery_status(requested_status or current_unit.status)

    if create_publication:
        if action != "publish":
            raise ValueError("`--create-publication` допустим только вместе с действием `publish`.")
        adapter = resolve_forge_adapter(project_root, host_kind, remote_name, url or current_unit.url)
        if current_unit.status == "draft" and target_status == "review":
            return adapter.update_publication(
                project_root,
                reference=existing_publication_reference(current_unit, url),
                head_branch=current_unit.head,
                base_branch=current_unit.base,
            )
        return adapter.create_publication(
            project_root,
            head_branch=current_unit.head,
            base_branch=current_unit.base,
            title=title or default_publication_title(fields, current_unit.purpose),
            body=body or default_publication_body(fields, current_unit.purpose, task_dir, summary=summary),
            draft=target_status == "draft",
        )

    if sync_from_host:
        adapter = resolve_forge_adapter(project_root, host_kind, remote_name, url or current_unit.url)
        return adapter.read_publication(
            project_root,
            reference=url or current_unit.url,
            head_branch=current_unit.head,
            base_branch=current_unit.base,
        )

    return resolve_explicit_snapshot(
        current_unit,
        host_kind=host_kind,
        publication_type=publication_type,
        target_status=target_status,
        url=url,
        merge_commit=merge_commit,
    )


def start_preflight_branch_context(
    project_root: Path,
    *,
    target_branch: str,
    base_branch: str,
    from_ref: str | None,
) -> str | None:
    if branch_exists(project_root, target_branch):
        return target_branch
    return resolve_delivery_start_ref(project_root, base_branch=base_branch, from_ref=from_ref)


def related_task_context_branches(task_dir: Path, fields: dict[str, str], delivery_unit: DeliveryUnit) -> set[str]:
    branches = {
        delivery_unit.head,
        delivery_unit.base,
    }
    recorded_branch = fields.get("Ветка", "").strip()
    if recorded_branch:
        branches.add(recorded_branch)
    task_id = fields.get("ID задачи", "").strip()
    short_name = fields.get("Краткое имя", "").strip()
    if task_id and short_name:
        branches.add(default_branch_name(task_id, short_name))
    try:
        branches.add(find_parent_branch(task_dir))
    except ValueError:
        pass
    return {
        branch_name
        for branch_name in branches
        if branch_name and branch_name not in PLACEHOLDER_BRANCH_VALUES and branch_name != DELIVERY_ROW_PLACEHOLDER
    }


def branch_for_task_context(
    project_root: Path,
    task_dir: Path,
    fields: dict[str, str],
    delivery_unit: DeliveryUnit,
) -> str:
    active_branch = current_git_branch(project_root)
    allowed_branches = related_task_context_branches(task_dir, fields, delivery_unit)
    if active_branch:
        if active_branch in allowed_branches:
            return active_branch
        allowed_text = ", ".join(sorted(allowed_branches)) or "нет"
        raise ValueError(
            "Текущая checkout-ветка не относится к контексту этой задачи; helper остановлен. "
            f"Текущая ветка: `{active_branch}`. Ожидалось одно из: {allowed_text}."
        )
    if delivery_unit.head != DELIVERY_ROW_PLACEHOLDER:
        return delivery_unit.head
    recorded_branch = fields.get("Ветка", "").strip()
    if recorded_branch and recorded_branch not in PLACEHOLDER_BRANCH_VALUES:
        return recorded_branch
    return DELIVERY_ROW_PLACEHOLDER


def format_registry_row(
    task_id: str,
    parent_id: str,
    status: str,
    priority: str,
    branch_name: str,
    task_dir_relative: str,
    summary: str,
) -> str:
    safe_summary = sanitize_registry_summary(summary) or DELIVERY_ROW_PLACEHOLDER
    return (
        f"| `{task_id}` | `{parent_id}` | `{status}` | `{priority}` | "
        f"`{branch_name}` | `{task_dir_relative}` | {safe_summary} |"
    )


def update_registry(
    project_root: Path,
    task_dir: Path,
    fields: dict[str, str],
    *,
    branch_name: str,
    register_if_missing: bool,
    summary: str | None,
) -> tuple[bool, str]:
    registry_path = project_root / "knowledge" / "tasks" / "registry.md"
    if not registry_path.exists():
        raise ValueError("Не найден knowledge/tasks/registry.md.")

    lines = registry_path.read_text(encoding="utf-8").splitlines()
    task_id = fields.get("ID задачи", "").strip()
    parent_id = fields.get("Parent ID", "—").strip() or "—"
    status = fields.get("Статус", "").strip()
    priority = fields.get("Приоритет", "").strip()
    task_dir_relative = task_dir.relative_to(project_root).as_posix().rstrip("/") + "/"
    task_file = task_dir / "task.md"

    existing_summary: str | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("| `"):
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if len(parts) != 7:
            continue
        row_task_id = normalize_table_value(parts[0])
        if row_task_id != task_id:
            continue
        existing_summary = parts[6].strip()
        new_summary = preferred_registry_summary(
            fields,
            goal_summary=derive_goal_summary_from_task(task_file),
            summary=summary,
            existing_summary=existing_summary,
        )
        if not new_summary:
            raise ValueError(
                "Для строки registry.md нужно заполнить `Человекочитаемое описание` в task.md, "
                "передать `--summary` или заполнить секцию `Цель`."
            )
        lines[index] = format_registry_row(
            task_id,
            parent_id,
            status,
            priority,
            branch_name,
            task_dir_relative,
            new_summary,
        )
        registry_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return False, str(registry_path)

    if not register_if_missing:
        raise ValueError(f"В knowledge/tasks/registry.md не найдена строка для {task_id}.")

    new_summary = preferred_registry_summary(
        fields,
        goal_summary=derive_goal_summary_from_task(task_file),
        summary=summary,
    )
    if not new_summary:
        raise ValueError(
            "Для новой строки registry.md нужно заполнить `Человекочитаемое описание` в task.md, "
            "передать `--summary` или заполнить секцию `Цель`."
        )

    lines.append(
        format_registry_row(
            task_id,
            parent_id,
            status,
            priority,
            branch_name,
            task_dir_relative,
            new_summary,
        )
    )
    registry_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True, str(registry_path)


def dirty_paths_are_task_scoped(project_root: Path, task_dir: Path) -> bool:
    task_dir_relative = task_dir.relative_to(project_root).as_posix().rstrip("/") + "/"
    registry_relative = "knowledge/tasks/registry.md"
    for path in dirty_paths(project_root):
        normalized = path.replace("\\", "/").rstrip("/")
        if normalized == registry_relative:
            continue
        if normalized and task_dir_relative.startswith(normalized + "/"):
            continue
        if normalized and registry_relative.startswith(normalized + "/"):
            continue
        if normalized.startswith(task_dir_relative.rstrip("/")):
            continue
        return False
    return True


def sync_task(
    project_root: Path,
    task_dir: Path,
    *,
    create_branch: bool,
    register_if_missing: bool,
    summary: str | None,
    branch_name: str | None,
    inherit_branch_from_parent: bool,
    today: str | None = None,
) -> dict[str, object]:
    project_root = project_root.resolve()
    task_dir = (project_root / task_dir).resolve() if not task_dir.is_absolute() else task_dir.resolve()
    task_file = task_dir / "task.md"
    if not task_file.exists():
        raise ValueError(f"Не найден task.md по пути {task_file}.")

    results: list[StepResult] = []
    lines, fields = read_task_fields(task_file)
    del lines
    target_branch = resolve_target_branch(
        project_root,
        task_dir,
        fields,
        branch_name=branch_name,
        inherit_branch_from_parent=inherit_branch_from_parent,
    )
    resolved_summary = preflight_registry_summary(
        project_root,
        task_dir,
        register_if_missing=register_if_missing,
        summary=summary,
        ref_name=sync_preflight_ref_name(
            project_root,
            create_branch=create_branch,
            target_branch=target_branch,
        ),
        allow_untracked_fallback=True,
    )
    active_branch = current_git_branch(project_root)
    branch_action = "recorded"

    if create_branch:
        if active_branch != target_branch:
            if not worktree_is_clean(project_root) and not dirty_paths_are_task_scoped(project_root, task_dir):
                raise ValueError("Рабочее дерево грязное; автоматическое переключение task-ветки остановлено.")
            if branch_exists(project_root, target_branch):
                run_git(project_root, "checkout", target_branch)
                branch_action = "switched"
            else:
                run_git(project_root, "checkout", "-b", target_branch)
                branch_action = "created"
        else:
            branch_action = "reused"
    elif active_branch:
        target_branch = active_branch

    today_value = today or date.today().isoformat()
    updated_fields = update_task_file(task_file, target_branch, today=today_value, summary=resolved_summary)
    registry_inserted, registry_path = update_registry(
        project_root,
        task_dir,
        updated_fields,
        branch_name=target_branch,
        register_if_missing=register_if_missing,
        summary=resolved_summary,
    )

    results.append(StepResult("task", "ok", "Карточка задачи синхронизирована с git-контекстом", str(task_file)))
    results.append(
        StepResult(
            "git_branch",
            "ok",
            f"Ветка задачи синхронизирована: action={branch_action}, branch={target_branch}",
        )
    )
    remote_present = has_remote(project_root)
    remote_detail = "Связанный удалённый репозиторий обнаружен; push можно предлагать только после локальной фиксации изменений."
    if not remote_present:
        remote_detail = "Связанный удалённый репозиторий не обнаружен; workflow остаётся только локальным."
    results.append(StepResult("git_remote", "ok", remote_detail))
    registry_detail = "Строка в registry.md обновлена"
    if registry_inserted:
        registry_detail = "Строка в registry.md создана"
    results.append(StepResult("registry", "ok", registry_detail, registry_path))

    return {
        "ok": True,
        "task_id": updated_fields.get("ID задачи"),
        "task_dir": str(task_dir),
        "branch": target_branch,
        "branch_action": branch_action,
        "remote_present": remote_present,
        "results": [asdict(item) for item in results],
    }


def run_publish_flow(
    project_root: Path,
    task_dir: Path,
    *,
    action: str,
    unit_id: str | None,
    purpose: str | None,
    base_branch: str | None,
    head_branch: str | None,
    from_ref: str | None,
    host: str | None,
    publication_type: str | None,
    url: str | None,
    merge_commit: str | None,
    cleanup: str | None,
    remote_name: str,
    status: str | None,
    create_publication: bool,
    sync_from_host: bool,
    title: str | None,
    body: str | None,
    summary: str | None = None,
    today: str | None = None,
) -> dict[str, object]:
    project_root = project_root.resolve()
    task_dir = (project_root / task_dir).resolve() if not task_dir.is_absolute() else task_dir.resolve()
    task_file = task_dir / "task.md"
    if not task_file.exists():
        raise ValueError(f"Не найден task.md по пути {task_file}.")

    lines, fields = read_task_fields(task_file)
    delivery_units = collect_delivery_units(project_root, task_dir, fields, lines)
    task_id = fields.get("ID задачи", "").strip()
    short_name = fields.get("Краткое имя", "").strip()
    if not task_id or not short_name:
        raise ValueError("В task.md должны быть заполнены поля `ID задачи` и `Краткое имя`.")

    selected_base_branch: str | None = None
    selected_head_branch_for_preflight: str | None = None
    start_ref_for_preflight: str | None = None
    current_unit_for_preflight: DeliveryUnit | None = None
    if action == "start":
        selected_base_branch = base_branch or infer_base_branch(project_root)
        normalized_unit_id = normalize_unit_id(unit_id) if unit_id else next_delivery_unit_id(project_root, task_id, delivery_units)
        selected_head_branch_for_preflight = head_branch or default_delivery_branch_name(
            task_id,
            normalized_unit_id,
            short_name,
        )
        start_ref_for_preflight = start_preflight_branch_context(
            project_root,
            target_branch=selected_head_branch_for_preflight,
            base_branch=selected_base_branch,
            from_ref=from_ref,
        )
    else:
        current_unit_for_preflight = find_delivery_unit(delivery_units, unit_id)

    resolved_summary = preflight_registry_summary(
        project_root,
        task_dir,
        register_if_missing=False,
        summary=summary,
        ref_name=publish_preflight_ref_name(
            project_root,
            action=action,
            target_branch=selected_head_branch_for_preflight,
            start_ref=start_ref_for_preflight,
            current_unit=current_unit_for_preflight,
        ),
        allow_untracked_fallback=True,
    )
    publication_summary = resolved_summary
    if create_publication and body is None and current_unit_for_preflight is not None:
        publication_ref_name = publication_body_ref_name(project_root, current_unit_for_preflight)
        if publication_ref_name is not None:
            publication_summary = preflight_registry_summary(
                project_root,
                task_dir,
                register_if_missing=False,
                summary=summary,
                ref_name=publication_ref_name,
            )
    effective_summary = publication_summary if create_publication else resolved_summary

    results: list[StepResult] = []
    today_value = today or date.today().isoformat()
    branch_action = "recorded"

    if action == "start":
        if unit_id:
            normalized_unit_id = normalize_unit_id(unit_id)
            existing_unit = next((item for item in delivery_units if item.unit_id == normalized_unit_id), None)
        else:
            normalized_unit_id = next_delivery_unit_id(project_root, task_id, delivery_units)
            existing_unit = None
        if existing_unit is None and not purpose:
            raise ValueError("Для нового delivery unit нужно указать `--purpose`.")
        assert selected_base_branch is not None
        selected_head_branch = selected_head_branch_for_preflight or head_branch or default_delivery_branch_name(
            task_id,
            normalized_unit_id,
            short_name,
        )
        branch_action = ensure_delivery_branch(
            project_root,
            target_branch=selected_head_branch,
            base_branch=selected_base_branch,
            from_ref=from_ref,
        )
        current_unit = existing_unit or create_delivery_unit(
            unit_id=normalized_unit_id,
            purpose=purpose or "",
            head_branch=selected_head_branch,
            base_branch=selected_base_branch,
        )
        validate_transition(action, current_unit.status, "local")
        updated_unit = DeliveryUnit(
            unit_id=current_unit.unit_id,
            purpose=sanitize_delivery_text(purpose or current_unit.purpose, allow_placeholder=False),
            head=selected_head_branch,
            base=selected_base_branch,
            host="none",
            publication_type="none",
            status="local",
            url=DELIVERY_ROW_PLACEHOLDER,
            merge_commit=DELIVERY_ROW_PLACEHOLDER,
            cleanup="не требуется",
        )
        delivery_units = replace_delivery_unit(delivery_units, updated_unit)
        branch_name = selected_head_branch
    else:
        current_unit = current_unit_for_preflight
        assert current_unit is not None
        if create_publication:
            branch_name = branch_for_task_context(project_root, task_dir, fields, current_unit)
        snapshot = resolve_publish_snapshot(
            project_root,
            task_dir,
            fields,
            current_unit,
            action=action,
            requested_host=host,
            requested_publication_type=publication_type,
            requested_status=status,
            url=url,
            merge_commit=merge_commit,
            remote_name=remote_name,
            create_publication=create_publication,
            sync_from_host=sync_from_host,
            title=title,
            body=body,
            summary=effective_summary,
        )
        if not create_publication:
            branch_context_unit = DeliveryUnit(
                unit_id=current_unit.unit_id,
                purpose=current_unit.purpose,
                head=snapshot.head or current_unit.head,
                base=snapshot.base or current_unit.base,
                host=snapshot.host,
                publication_type=snapshot.publication_type,
                status=snapshot.status,
                url=snapshot.url,
                merge_commit=snapshot.merge_commit,
                cleanup=current_unit.cleanup,
            )
            branch_name = branch_for_task_context(project_root, task_dir, fields, branch_context_unit)
        validate_transition(action, current_unit.status, snapshot.status)
        if action == "publish" and snapshot.url == DELIVERY_ROW_PLACEHOLDER:
            raise ValueError(
                "Для `publish` нужен URL публикации или сетевой adapter через `--create-publication`."
            )
        if action == "merge" and snapshot.merge_commit == DELIVERY_ROW_PLACEHOLDER:
            raise ValueError("Для `merge` нужен `--merge-commit` или успешный `--sync-from-host`.")
        if action == "close" and merge_commit:
            raise ValueError("Для `close` нельзя передавать `--merge-commit`.")
        default_cleanup = current_unit.cleanup
        if snapshot.status in {"merged", "closed"} and default_cleanup == "не требуется":
            default_cleanup = "ожидается"
        updated_unit = DeliveryUnit(
            unit_id=current_unit.unit_id,
            purpose=current_unit.purpose,
            head=snapshot.head or current_unit.head,
            base=snapshot.base or current_unit.base,
            host=snapshot.host,
            publication_type=snapshot.publication_type,
            status=snapshot.status,
            url=snapshot.url,
            merge_commit=DELIVERY_ROW_PLACEHOLDER if action == "close" else snapshot.merge_commit,
            cleanup=normalize_cleanup_value(cleanup, default=default_cleanup),
        )
        delivery_units = replace_delivery_unit(delivery_units, updated_unit)

    updated_fields = update_task_file_with_delivery_units(
        task_file,
        branch_name,
        delivery_units,
        today=today_value,
        summary=effective_summary,
    )
    registry_inserted, registry_path = update_registry(
        project_root,
        task_dir,
        updated_fields,
        branch_name=branch_name,
        register_if_missing=False,
        summary=effective_summary,
    )

    results.append(
        StepResult(
            "publish_block",
            "ok",
            f"Контур публикации синхронизирован: action={action}, unit={updated_unit.unit_id}, status={updated_unit.status}",
            str(task_file),
        )
    )
    if action == "start":
        results.append(
            StepResult(
                "git_branch",
                "ok",
                f"Delivery-ветка синхронизирована: action={branch_action}, branch={branch_name}",
            )
        )
    if create_publication or sync_from_host:
        results.append(
            StepResult(
                "host_adapter",
                "ok",
                f"Host adapter использован: host={updated_unit.host}, type={updated_unit.publication_type}",
            )
        )
    registry_detail = "Строка в registry.md обновлена"
    if registry_inserted:
        registry_detail = "Строка в registry.md создана"
    results.append(StepResult("registry", "ok", registry_detail, registry_path))

    return {
        "ok": True,
        "task_id": updated_fields.get("ID задачи"),
        "task_dir": str(task_dir),
        "action": action,
        "branch": branch_name,
        "branch_action": branch_action,
        "unit_id": updated_unit.unit_id,
        "delivery_status": updated_unit.status,
        "host": updated_unit.host,
        "publication_type": updated_unit.publication_type,
        "url": updated_unit.url,
        "merge_commit": updated_unit.merge_commit,
        "cleanup": updated_unit.cleanup,
        "results": [asdict(item) for item in results],
    }


def print_text_report(payload: dict[str, object]) -> None:
    print(f"ok={payload['ok']}")
    print(f"task_id={payload['task_id']}")
    print(f"task_dir={payload['task_dir']}")
    if "action" in payload:
        print(f"action={payload['action']}")
    print(f"branch={payload['branch']}")
    print(f"branch_action={payload['branch_action']}")
    if "remote_present" in payload:
        print(f"remote_present={payload['remote_present']}")
    if "unit_id" in payload:
        print(f"unit_id={payload['unit_id']}")
    if "delivery_status" in payload:
        print(f"delivery_status={payload['delivery_status']}")
    if "host" in payload:
        print(f"host={payload['host']}")
    if "publication_type" in payload:
        print(f"publication_type={payload['publication_type']}")
    if "url" in payload:
        print(f"url={payload['url']}")
    if "merge_commit" in payload:
        print(f"merge_commit={payload['merge_commit']}")
    if "cleanup" in payload:
        print(f"cleanup={payload['cleanup']}")
    for item in payload["results"]:
        suffix = f" path={item['path']}" if item.get("path") else ""
        print(f"- [{item['status']}] {item['key']}: {item['detail']}{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync task-centric knowledge files with the current Git task workflow.",
        allow_abbrev=False,
    )
    parser.add_argument("--project-root", required=True, help="Абсолютный путь к корню проекта.")
    parser.add_argument("--task-dir", required=True, help="Путь к каталогу задачи относительно project-root или абсолютный путь.")
    parser.add_argument("--create-branch", action="store_true", help="Создать или переключить task-ветку по правилам knowledge-системы.")
    parser.add_argument("--register-if-missing", action="store_true", help="Создать строку в registry.md, если она отсутствует.")
    parser.add_argument(
        "--summary",
        help="Legacy-fallback описание для registry.md, если в task.md ещё нет поля `Человекочитаемое описание`.",
    )
    parser.add_argument("--branch-name", help="Явно задать имя ветки вместо branch-паттерна по умолчанию.")
    parser.add_argument(
        "--inherit-branch-from-parent",
        action="store_true",
        help="Для подзадачи взять ветку родительской задачи вместо создания отдельной ветки.",
    )
    parser.add_argument(
        "--publish-action",
        choices=("start", "publish", "sync", "merge", "close"),
        help="Выполнить publish-helper действие вместо обычной sync-задачи.",
    )
    parser.add_argument("--unit-id", help="Delivery unit в формате `DU-01`.")
    parser.add_argument("--purpose", help="Назначение delivery unit для `start` или нового unit.")
    parser.add_argument("--base-branch", help="Целевая base-ветка для публикации и merge.")
    parser.add_argument("--head-branch", help="Явно задать head-ветку delivery unit.")
    parser.add_argument("--from-ref", help="Ref, от которого создавать новую delivery-ветку.")
    parser.add_argument("--host", help="Host публикации: `github`, `gitlab`, `generic`, `none` или `auto`.")
    parser.add_argument("--publication-type", help="Тип публикации: `pr`, `mr`, `none`.")
    parser.add_argument("--url", help="URL опубликованного PR/MR.")
    parser.add_argument("--merge-commit", help="Merge commit SHA или ID.")
    parser.add_argument("--cleanup", help="Состояние cleanup: `не требуется`, `ожидается`, `выполнено`.")
    parser.add_argument("--remote-name", default="origin", help="Имя git remote для auto-detect хостинга.")
    parser.add_argument("--status", help="Явно задать publish-статус delivery unit.")
    parser.add_argument(
        "--create-publication",
        action="store_true",
        help="Попробовать создать PR/MR через поддерживаемый host adapter.",
    )
    parser.add_argument(
        "--sync-from-host",
        action="store_true",
        help="Прочитать состояние существующего PR/MR через host adapter.",
    )
    parser.add_argument("--title", help="Заголовок публикации для `--create-publication`.")
    parser.add_argument("--body", help="Тело публикации для `--create-publication`.")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Формат вывода.")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    task_dir = Path(args.task_dir)
    try:
        if args.publish_action:
            payload = run_publish_flow(
                project_root,
                task_dir,
                action=args.publish_action,
                unit_id=args.unit_id,
                purpose=args.purpose,
                base_branch=args.base_branch,
                head_branch=args.head_branch,
                from_ref=args.from_ref,
                host=args.host,
                publication_type=args.publication_type,
                url=args.url,
                merge_commit=args.merge_commit,
                cleanup=args.cleanup,
                remote_name=args.remote_name,
                status=args.status,
                create_publication=args.create_publication,
                sync_from_host=args.sync_from_host,
                title=args.title,
                body=args.body,
                summary=args.summary,
            )
        else:
            payload = sync_task(
                project_root,
                task_dir,
                create_branch=args.create_branch,
                register_if_missing=args.register_if_missing,
                summary=args.summary,
                branch_name=args.branch_name,
                inherit_branch_from_parent=args.inherit_branch_from_parent,
            )
    except Exception as error:  # noqa: BLE001
        payload = {
            "ok": False,
            "task_id": None,
            "task_dir": str(task_dir),
            "branch": None,
            "branch_action": "failed",
            "results": [asdict(StepResult("workflow", "error", str(error)))],
        }

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_text_report(payload)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
