#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_IGNORED_TREE_PARTS = (
    ".git",
    ".venv",
    "dist",
    "node_modules",
)

DEFAULT_ALLOWED_PHRASES = (
    "README.md",
    "AGENTS.md",
    "SQLite",
    "Markdown",
    "JSON",
    "YAML",
    "XML",
    "MCP",
    "MVP",
    "GitHub",
    "OpenAI",
    "Anthropic",
    "Gemini",
    "OpenRouter",
    "CLI",
    "API",
    "HTTP",
    "SDK",
    "UI",
    "UX",
)


@dataclass(frozen=True)
class GuardConfig:
    root: Path
    ignored_tree_parts: tuple[str, ...] = DEFAULT_IGNORED_TREE_PARTS
    ignore_rel_globs: tuple[str, ...] = ()
    allowed_phrases: tuple[str, ...] = DEFAULT_ALLOWED_PHRASES
    max_issues_per_file: int = 10
    resolve_relative_to_root: bool = False


def build_config(
    *,
    root: Path,
    ignored_tree_parts: Iterable[str] = DEFAULT_IGNORED_TREE_PARTS,
    ignore_rel_globs: Iterable[str] = (),
    allowed_phrases: Iterable[str] = DEFAULT_ALLOWED_PHRASES,
    max_issues_per_file: int = 10,
    resolve_relative_to_root: bool = False,
) -> GuardConfig:
    return GuardConfig(
        root=root.resolve(),
        ignored_tree_parts=tuple(ignored_tree_parts),
        ignore_rel_globs=tuple(ignore_rel_globs),
        allowed_phrases=tuple(allowed_phrases),
        max_issues_per_file=max_issues_per_file,
        resolve_relative_to_root=resolve_relative_to_root,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check-docs-localization",
        description="Проверяет, что Markdown-документы содержат русскоязычную прозу.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Файлы или каталоги для проверки. Если не указаны, проверяется весь --root.",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Корневой каталог проверки. По умолчанию используется текущий каталог.",
    )
    parser.add_argument(
        "--allow-phrase",
        action="append",
        default=[],
        help="Дополнительная фраза, которую можно игнорировать как машинно-значимую.",
    )
    parser.add_argument(
        "--ignore-rel-glob",
        action="append",
        default=[],
        help="Дополнительный glob по пути относительно --root для игнорирования Markdown.",
    )
    parser.add_argument(
        "--max-issues-per-file",
        type=int,
        default=10,
        help="Максимальное число проблемных строк, выводимых на один файл.",
    )
    parser.add_argument(
        "--resolve-relative-to-root",
        action="store_true",
        help="Разрешать относительные аргументы paths относительно --root, а не cwd.",
    )
    return parser.parse_args(argv)


def path_from_arg(raw: str, config: GuardConfig) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path.resolve()
    base = config.root if config.resolve_relative_to_root else Path.cwd()
    return (base / path).resolve()


def relative_to_root(path: Path, root: Path) -> Path | None:
    try:
        return path.relative_to(root)
    except ValueError:
        return None


def matches_ignore_glob(path: Path, config: GuardConfig) -> bool:
    rel = relative_to_root(path, config.root)
    if rel is None:
        return False
    rel_text = rel.as_posix()
    return any(fnmatch.fnmatch(rel_text, pattern) for pattern in config.ignore_rel_globs)


def is_ignored_markdown(path: Path, config: GuardConfig) -> bool:
    rel = relative_to_root(path, config.root)
    if rel is not None and any(part in config.ignored_tree_parts for part in rel.parts):
        return True
    return matches_ignore_glob(path, config)


def iter_markdown_in_dir(directory: Path, config: GuardConfig) -> list[Path]:
    return sorted(
        path
        for path in directory.rglob("*.md")
        if path.is_file() and not is_ignored_markdown(path, config)
    )


def iter_target_files(raw_paths: Iterable[str], config: GuardConfig) -> list[Path]:
    args = list(raw_paths)
    if args:
        result: list[Path] = []
        for raw in args:
            path = path_from_arg(raw, config)
            if path.is_dir():
                result.extend(iter_markdown_in_dir(path, config))
                continue
            if path.is_file() and path.suffix.lower() == ".md" and not is_ignored_markdown(path, config):
                result.append(path)
        return sorted(set(result))

    return iter_markdown_in_dir(config.root, config)


def strip_code_blocks(text: str) -> str:
    text = re.sub(r"\A---\s*\n[\s\S]*?\n---\s*(?:\n|$)", "", text, count=1)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`\n]+`", "", text)
    text = re.sub(r"https?://\S+", "", text)
    return text


def normalize_line(line: str, allowed_phrases: Iterable[str]) -> str:
    clean = line
    for phrase in allowed_phrases:
        clean = re.sub(re.escape(phrase), "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\[[^\]]*\]\([^)]+\)", "", clean)
    clean = re.sub(r"[#>*_\-\[\](){}:;,.!?/\\|\"'=+]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text))


def is_machine_directive_line(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9_ ⟦⟧]+", text))


def suspicious_lines(text: str, allowed_phrases: Iterable[str]) -> list[str]:
    issues: list[str] = []
    for raw_line in strip_code_blocks(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        clean = normalize_line(line, allowed_phrases)
        if not clean:
            continue
        latin_words = re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{2,}\b", clean)
        if not latin_words:
            continue
        if has_cyrillic(clean):
            continue
        if is_machine_directive_line(clean):
            continue
        if len("".join(latin_words)) < 12:
            continue
        issues.append(raw_line.strip())
    return issues


def display_path(path: Path, root: Path) -> str:
    rel = relative_to_root(path, root)
    return rel.as_posix() if rel is not None else str(path)


def run_with_config(raw_paths: Iterable[str], config: GuardConfig) -> tuple[int, str]:
    files = iter_target_files(raw_paths, config)
    if not files:
        return 1, "Не найдено Markdown-файлов для проверки."

    failures: list[tuple[Path, list[str]]] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not has_cyrillic(strip_code_blocks(text)):
            failures.append((path, ["В документе не найдено русскоязычной прозы."]))
            continue
        issues = suspicious_lines(text, config.allowed_phrases)
        if issues:
            failures.append((path, issues[: config.max_issues_per_file]))

    if failures:
        lines = ["Проверка локализации не пройдена:", ""]
        for path, issues in failures:
            lines.append(f"- {display_path(path, config.root)}")
            for issue in issues:
                lines.append(f"  * {issue}")
        return 2, "\n".join(lines)

    return 0, "Проверка локализации пройдена."


def main(
    argv: list[str] | None = None,
    *,
    default_root: Path | None = None,
    default_allowed_phrases: Iterable[str] = DEFAULT_ALLOWED_PHRASES,
    default_ignore_rel_globs: Iterable[str] = (),
    resolve_relative_to_root: bool = False,
) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve() if args.root else (default_root or Path.cwd()).resolve()
    config = build_config(
        root=root,
        ignore_rel_globs=tuple(default_ignore_rel_globs) + tuple(args.ignore_rel_glob),
        allowed_phrases=tuple(default_allowed_phrases) + tuple(args.allow_phrase),
        max_issues_per_file=args.max_issues_per_file,
        resolve_relative_to_root=resolve_relative_to_root or args.resolve_relative_to_root,
    )
    code, output = run_with_config(args.paths, config)
    print(output)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
