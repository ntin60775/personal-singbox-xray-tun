#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable


SESSION_FILE_RE = re.compile(
    r"^rollout-(?P<date>\d{4}-\d{2}-\d{2})T\d{2}-\d{2}-\d{2}-(?P<id>.+)\.jsonl$"
)
OPENCODE_LOG_RE = re.compile(r"^(?P<stamp>\d{4}-\d{2}-\d{2}T\d{6})\.log$")


@dataclass(frozen=True)
class FsDelete:
    path: Path
    reason: str


@dataclass(frozen=True)
class RewriteFile:
    path: Path
    reason: str
    content: str


@dataclass(frozen=True)
class DbDelete:
    session_ids: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    cutoff_dt: datetime
    cutoff_ts: float
    cutoff_ms: int
    fs_deletes: tuple[FsDelete, ...]
    rewrites: tuple[RewriteFile, ...]
    db_delete: DbDelete


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Очистка старых сессий Codex/OpenCode с retention по календарным дням. "
            "По умолчанию сохраняются текущий день и два предыдущих."
        )
    )
    parser.add_argument(
        "--target",
        choices=("both", "codex", "opencode"),
        default="both",
        help="Что чистить: обе системы, только codex или только opencode.",
    )
    parser.add_argument(
        "--keep-days",
        type=int,
        default=2,
        help="Сохранять данные, начиная с начала текущего дня минус указанное число дней.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Применить изменения. По умолчанию выполняется только dry-run.",
    )
    parser.add_argument(
        "--allow-many",
        action="store_true",
        help="Разрешить массовое удаление, если объектов или session ID больше 7.",
    )
    return parser.parse_args()


def local_cutoff(keep_days: int) -> datetime:
    if keep_days < 0:
        raise ValueError("--keep-days не может быть отрицательным")
    now = datetime.now().astimezone()
    start_today = datetime.combine(now.date(), time.min, now.tzinfo)
    return start_today - timedelta(days=keep_days)


def unique_paths(items: Iterable[FsDelete]) -> tuple[FsDelete, ...]:
    seen: set[Path] = set()
    result: list[FsDelete] = []
    for item in sorted(items, key=lambda x: str(x.path)):
        if item.path in seen:
            continue
        seen.add(item.path)
        result.append(item)
    return tuple(result)


def parse_codex_filename(path: Path) -> tuple[date | None, str | None]:
    match = SESSION_FILE_RE.match(path.name)
    if not match:
        return None, None
    return date.fromisoformat(match.group("date")), match.group("id")


def is_older_than(path: Path, cutoff_ts: float) -> bool:
    try:
        return path.stat().st_mtime < cutoff_ts
    except FileNotFoundError:
        return False


def collect_codex(base: Path, cutoff_dt: datetime) -> tuple[tuple[FsDelete, ...], tuple[RewriteFile, ...]]:
    fs_deletes: list[FsDelete] = []
    rewrites: list[RewriteFile] = []
    cutoff_date = cutoff_dt.date()
    cutoff_ts = cutoff_dt.timestamp()
    kept_session_ids: set[str] = set()
    old_session_ids: set[str] = set()

    sessions_root = base / "sessions"
    if sessions_root.exists():
        for session_file in sorted(sessions_root.rglob("*.jsonl")):
            session_date, session_id = parse_codex_filename(session_file)
            if session_id is None:
                continue
            if session_date is not None and session_date >= cutoff_date:
                kept_session_ids.add(session_id)
            else:
                old_session_ids.add(session_id)
                fs_deletes.append(FsDelete(session_file, "codex session"))

    archived_root = base / "archived_sessions"
    if archived_root.exists():
        for archived_file in sorted(archived_root.glob("*.jsonl")):
            session_date, session_id = parse_codex_filename(archived_file)
            old_by_name = session_date is not None and session_date < cutoff_date
            old_by_mtime = is_older_than(archived_file, cutoff_ts)
            if old_by_name or old_by_mtime:
                if session_id:
                    old_session_ids.add(session_id)
                fs_deletes.append(FsDelete(archived_file, "codex archived session"))
            elif session_id:
                kept_session_ids.add(session_id)

    shell_snapshots = base / "shell_snapshots"
    if shell_snapshots.exists():
        for snapshot in sorted(shell_snapshots.glob("*.sh")):
            session_id = snapshot.stem
            if session_id in old_session_ids or (
                session_id not in kept_session_ids and is_older_than(snapshot, cutoff_ts)
            ):
                fs_deletes.append(FsDelete(snapshot, "codex shell snapshot"))

    tmp_root = base / "tmp"
    if tmp_root.exists():
        for subdir_name in ("arg0", "path"):
            subdir = tmp_root / subdir_name
            if not subdir.exists():
                continue
            for item in sorted(subdir.iterdir()):
                if is_older_than(item, cutoff_ts):
                    fs_deletes.append(FsDelete(item, "codex tmp"))

    session_index = base / "session_index.jsonl"
    if session_index.exists():
        kept_lines: list[str] = []
        changed = False
        for raw_line in session_index.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            data = json.loads(raw_line)
            updated_at = data.get("updated_at")
            if updated_at:
                updated_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00")).astimezone(cutoff_dt.tzinfo)
                if updated_dt >= cutoff_dt:
                    kept_lines.append(raw_line)
                else:
                    changed = True
            else:
                kept_lines.append(raw_line)
        if changed:
            content = "".join(f"{line}\n" for line in kept_lines)
            rewrites.append(RewriteFile(session_index, "codex session index prune", content))

    history_file = base / "history.jsonl"
    if history_file.exists():
        kept_lines = []
        changed = False
        for raw_line in history_file.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            data = json.loads(raw_line)
            ts = data.get("ts")
            if isinstance(ts, (int, float)) and ts >= cutoff_ts:
                kept_lines.append(raw_line)
            elif isinstance(ts, (int, float)):
                changed = True
            else:
                kept_lines.append(raw_line)
        if changed:
            content = "".join(f"{line}\n" for line in kept_lines)
            rewrites.append(RewriteFile(history_file, "codex history prune", content))

    return unique_paths(fs_deletes), tuple(sorted(rewrites, key=lambda x: str(x.path)))


def collect_opencode(share_root: Path, cutoff_dt: datetime) -> tuple[tuple[FsDelete, ...], DbDelete]:
    fs_deletes: list[FsDelete] = []
    cutoff_ms = int(cutoff_dt.timestamp() * 1000)
    cutoff_ts = cutoff_dt.timestamp()
    session_ids: list[str] = []

    db_path = share_root / "opencode.db"
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT id FROM session WHERE time_updated < ? ORDER BY time_updated ASC",
                (cutoff_ms,),
            ).fetchall()
            session_ids = [row[0] for row in rows]
        finally:
            conn.close()

    storage_roots = (
        share_root / "storage" / "session_diff",
        share_root / "storage" / "agent-usage-reminder",
        share_root / "storage" / "directory-readme",
    )
    for session_id in session_ids:
        for storage_root in storage_roots:
            candidate = storage_root / f"{session_id}.json"
            if candidate.exists():
                fs_deletes.append(FsDelete(candidate, "opencode session sidecar"))

    log_root = share_root / "log"
    if log_root.exists():
        for log_file in sorted(log_root.glob("*.log")):
            match = OPENCODE_LOG_RE.match(log_file.name)
            if match:
                stamp = datetime.strptime(match.group("stamp"), "%Y-%m-%dT%H%M%S").replace(tzinfo=cutoff_dt.tzinfo)
                old = stamp < cutoff_dt
            else:
                old = is_older_than(log_file, cutoff_ts)
            if old:
                fs_deletes.append(FsDelete(log_file, "opencode log"))

    for dir_name, reason in (("snapshot", "opencode snapshot"), ("tool-output", "opencode tool output")):
        root = share_root / dir_name
        if not root.exists():
            continue
        for item in sorted(root.iterdir()):
            if is_older_than(item, cutoff_ts):
                fs_deletes.append(FsDelete(item, reason))

    return unique_paths(fs_deletes), DbDelete(tuple(session_ids))


def build_plan(args: argparse.Namespace) -> Plan:
    cutoff_dt = local_cutoff(args.keep_days)
    fs_deletes: list[FsDelete] = []
    rewrites: list[RewriteFile] = []
    db_delete = DbDelete(tuple())

    home = Path.home()
    if args.target in ("both", "codex"):
        codex_fs, codex_rewrites = collect_codex(home / ".codex", cutoff_dt)
        fs_deletes.extend(codex_fs)
        rewrites.extend(codex_rewrites)

    if args.target in ("both", "opencode"):
        opencode_fs, opencode_db = collect_opencode(home / ".local" / "share" / "opencode", cutoff_dt)
        fs_deletes.extend(opencode_fs)
        db_delete = opencode_db

    return Plan(
        cutoff_dt=cutoff_dt,
        cutoff_ts=cutoff_dt.timestamp(),
        cutoff_ms=int(cutoff_dt.timestamp() * 1000),
        fs_deletes=unique_paths(fs_deletes),
        rewrites=tuple(sorted(rewrites, key=lambda x: str(x.path))),
        db_delete=db_delete,
    )


def print_plan(plan: Plan, mode: str) -> None:
    print(f"MODE = {mode}")
    print(
        "RETENTION = keep from local day start minus keep-days "
        f"=> cutoff {plan.cutoff_dt.isoformat()}"
    )
    print()
    print(f"DB_SESSION_DELETE_COUNT = {len(plan.db_delete.session_ids)}")
    for session_id in plan.db_delete.session_ids:
        print(session_id)
    print()
    print(f"REWRITE_COUNT = {len(plan.rewrites)}")
    for rewrite in plan.rewrites:
        print(rewrite.path)
    print()
    print(f"COUNT = {len(plan.fs_deletes)}")
    for item in plan.fs_deletes:
        print(item.path)


def confirm_apply(plan: Plan) -> bool:
    print()
    print("CONFIRMATION_REQUIRED = yes")
    print(
        "Для выполнения удаления введите YES "
        f"(session IDs: {len(plan.db_delete.session_ids)}, файлов/каталогов: {len(plan.fs_deletes)}, rewrites: {len(plan.rewrites)})"
    )
    try:
        answer = input("> ").strip()
    except EOFError:
        return False
    return answer == "YES"


def apply_db_delete(db_path: Path, db_delete: DbDelete) -> None:
    if not db_delete.session_ids:
        return
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        placeholders = ",".join("?" for _ in db_delete.session_ids)
        conn.execute("BEGIN")
        conn.execute(
            f"DELETE FROM session WHERE id IN ({placeholders})",
            db_delete.session_ids,
        )
        conn.commit()
        conn.execute("VACUUM")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def apply_rewrites(rewrites: Iterable[RewriteFile]) -> None:
    count = 0
    for rewrite in rewrites:
        rewrite.path.write_text(rewrite.content, encoding="utf-8")
        count += 1
    return count


def apply_fs_deletes(fs_deletes: Iterable[FsDelete]) -> None:
    count = 0
    for item in sorted(fs_deletes, key=lambda x: (x.path.is_file(), len(str(x.path))), reverse=True):
        path = item.path
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        count += 1
    return count


def main() -> int:
    args = parse_args()
    plan = build_plan(args)
    print_plan(plan, "apply" if args.apply else "dry-run")

    if not args.apply:
        return 0

    too_many = len(plan.fs_deletes) > 7 or len(plan.db_delete.session_ids) > 7
    if too_many and not args.allow_many:
        print()
        print("REFUSE_APPLY = too many objects/session IDs; rerun only after explicit confirmation with --allow-many")
        return 2

    if not confirm_apply(plan):
        print()
        print("APPLY_STATUS = cancelled")
        return 3

    rewritten_count = apply_rewrites(plan.rewrites)

    if args.target in ("both", "opencode"):
        apply_db_delete(Path.home() / ".local" / "share" / "opencode" / "opencode.db", plan.db_delete)

    deleted_fs_count = apply_fs_deletes(plan.fs_deletes)
    print()
    print("APPLY_STATUS = done")
    print("SUMMARY")
    print(f"cutoff = {plan.cutoff_dt.isoformat()}")
    print(f"deleted_opencode_sessions = {len(plan.db_delete.session_ids)}")
    print(f"rewritten_files = {rewritten_count}")
    print(f"deleted_fs_objects = {deleted_fs_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
