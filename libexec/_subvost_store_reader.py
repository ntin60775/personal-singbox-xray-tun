#!/usr/bin/env python3
"""CLI for shell scripts to read and sync the subvost store.json.

Usage:
  _subvost_store_reader.py [--uid N] [--gid N] <command>
  _subvost_store_reader.py [--store-file PATH] [--uid N] [--gid N] <command>

Commands:
  active-node-id          Print the active node ID.
  active-profile-id       Print the active profile ID.
  active-node-name        Print the active node's name.
  active-node-protocol    Print the active node's protocol.
  active-node-address     Print the active node's address.
  active-node-port        Print the active node's port.
  has-active-selection    Print "true" or "false".
  generated-config-path   Print the path to the generated xray config file.
  routing-active-profile-id  Print the routing active profile ID.
  routing-enabled         Print "true" or "false".
  sync-generated-runtime  Ensure store is initialized and sync generated runtime config.

Options:
  --store-file PATH  Use this store file instead of auto-resolving from HOME.
  --uid N            Use this uid for file ownership (default: SUDO_UID or current).
  --gid N            Use this gid for file ownership (default: SUDO_GID or current).

Exit 0 on success, exit 1 on any error (including missing store file).
Missing optional fields print empty string and exit 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent
_GUI_DIR = _PROJECT_ROOT / "gui"
if str(_GUI_DIR) not in sys.path:
    sys.path.insert(0, str(_GUI_DIR))

from subvost_paths import (  # noqa: E402
    APP_DIRNAME,
    GENERATED_XRAY_CONFIG_FILENAME,
    STORE_FILENAME,
    resolve_config_home,
)


def _load_store(store_file: Path) -> dict:
    """Read and parse store.json. Returns empty dict if file is missing."""
    if not store_file.is_file():
        return {}
    try:
        with store_file.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def _find_active_node(store: dict) -> dict | None:
    """Return the active node dict, or None if no valid active selection."""
    sel = store.get("active_selection")
    if not sel:
        return None
    profile_id = sel.get("profile_id")
    node_id = sel.get("node_id")
    if not profile_id or not node_id:
        return None
    for profile in store.get("profiles", []):
        if profile.get("id") == profile_id:
            for node in profile.get("nodes", []):
                if node.get("id") == node_id:
                    return node
    return None


def _parse_args(argv: list[str]) -> tuple[list[str], Path | None, int | None, int | None]:
    """Parse optional --store-file, --uid, --gid before the command.
    Returns (remaining_argv, store_file_override, uid, gid)."""
    store_file_override: Path | None = None
    uid: int | None = None
    gid: int | None = None
    remaining: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--store-file":
            i += 1
            if i >= len(argv):
                print("Missing value for --store-file", file=sys.stderr)
                sys.exit(1)
            store_file_override = Path(argv[i])
        elif arg == "--uid":
            i += 1
            if i >= len(argv):
                print("Missing value for --uid", file=sys.stderr)
                sys.exit(1)
            try:
                uid = int(argv[i])
            except ValueError:
                print(f"Invalid --uid value: {argv[i]}", file=sys.stderr)
                sys.exit(1)
        elif arg == "--gid":
            i += 1
            if i >= len(argv):
                print("Missing value for --gid", file=sys.stderr)
                sys.exit(1)
            try:
                gid = int(argv[i])
            except ValueError:
                print(f"Invalid --gid value: {argv[i]}", file=sys.stderr)
                sys.exit(1)
        else:
            remaining.append(arg)
        i += 1
    return remaining, store_file_override, uid, gid


def _resolve_uid_gid(uid: int | None, gid: int | None) -> tuple[int | None, int | None]:
    """Fill in uid/gid from SUDO_UID/SUDO_GID env vars if not explicitly provided."""
    import os
    if uid is None:
        sudo_uid = os.environ.get("SUDO_UID")
        if sudo_uid is not None:
            try:
                uid = int(sudo_uid)
            except ValueError:
                pass
    if gid is None:
        sudo_gid = os.environ.get("SUDO_GID")
        if sudo_gid is not None:
            try:
                gid = int(sudo_gid)
            except ValueError:
                pass
    return uid, gid


def _main() -> None:
    remaining, store_file_override, uid, gid = _parse_args(sys.argv[1:])

    if not remaining:
        print("Usage: _subvost_store_reader.py [--store-file PATH] [--uid N] [--gid N] <command>", file=sys.stderr)
        sys.exit(1)

    command = remaining[0]

    # Always resolve real_home / config_home for commands that need them.
    real_home = Path.home()
    config_home = resolve_config_home(real_home)

    if store_file_override is not None:
        store_file = store_file_override
        store_dir = store_file.parent
        generated_config_file = store_dir / GENERATED_XRAY_CONFIG_FILENAME
    else:
        store_dir = config_home / APP_DIRNAME
        store_file = store_dir / STORE_FILENAME
        generated_config_file = store_dir / GENERATED_XRAY_CONFIG_FILENAME

    # Commands that don't require the store to exist.
    if command == "generated-config-path":
        print(str(generated_config_file))
        return

    uid, gid = _resolve_uid_gid(uid, gid)

    if command == "sync-generated-runtime":
        from subvost_paths import build_app_paths  # noqa: E402
        from subvost_store import ensure_store_initialized  # noqa: E402
        paths = build_app_paths(real_home, str(config_home))
        ensure_store_initialized(paths, _PROJECT_ROOT, uid=uid, gid=gid)
        return

    store = _load_store(store_file)

    # All other commands require the store.
    if not store:
        sys.exit(1)

    if command == "active-node-id":
        print(store.get("active_selection", {}).get("node_id", ""))
    elif command == "active-profile-id":
        print(store.get("active_selection", {}).get("profile_id", ""))
    elif command == "active-node-name":
        node = _find_active_node(store)
        if node is None:
            print("")
        else:
            print(node.get("name", ""))
    elif command == "active-node-protocol":
        node = _find_active_node(store)
        if node is None:
            print("")
        else:
            normalized = node.get("normalized", {})
            print(normalized.get("protocol", node.get("protocol", "")))
    elif command == "active-node-address":
        node = _find_active_node(store)
        if node is None:
            print("")
        else:
            print(node.get("normalized", {}).get("address", ""))
    elif command == "active-node-port":
        node = _find_active_node(store)
        if node is None:
            print("")
        else:
            port = node.get("normalized", {}).get("port", "")
            print(str(port) if port != "" else "")
    elif command == "has-active-selection":
        print("true" if _find_active_node(store) is not None else "false")
    elif command == "routing-active-profile-id":
        print(store.get("routing", {}).get("active_profile_id", ""))
    elif command == "routing-enabled":
        active_id = store.get("routing", {}).get("active_profile_id")
        print("true" if active_id else "false")
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _main()
