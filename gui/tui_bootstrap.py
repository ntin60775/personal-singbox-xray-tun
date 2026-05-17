#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REQUIRED_COMMANDS = (
    ("python3", "python3"),
    ("ip", "iproute2"),
    ("curl", "curl"),
)

REQUIRED_PACKAGES = (
    ("python3-textual", "python3-textual"),
)

REQUIRED_FILES = (
    ("/dev/net/tun", "TUN-устройство"),
)

PRIVILEGE_HELPERS = ("pkexec", "sudo")


def _has_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _has_apt_package(pkg: str) -> bool:
    try:
        subprocess.run(
            ["apt-cache", "show", pkg],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _can_install_packages() -> bool:
    if os.geteuid() == 0:
        return True
    for helper in PRIVILEGE_HELPERS:
        if _has_command(helper):
            return True
    return False


def _install_packages(packages: list[str]) -> bool:
    update_cmd: list[str] | None = None
    install_cmd: list[str]
    if os.geteuid() == 0:
        update_cmd = ["apt-get", "update"]
        install_cmd = ["apt-get", "install", "-y", *packages]
    elif _has_command("pkexec"):
        update_cmd = ["pkexec", "apt-get", "update"]
        install_cmd = ["pkexec", "apt-get", "install", "-y", *packages]
    elif _has_command("sudo"):
        update_cmd = ["sudo", "apt-get", "update"]
        install_cmd = ["sudo", "apt-get", "install", "-y", *packages]
    else:
        return False

    try:
        if update_cmd:
            subprocess.run(update_cmd, check=True, capture_output=True)
        subprocess.run(install_cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def check_textual() -> tuple[bool, str]:
    try:
        import textual  # noqa: F401
        return True, ""
    except ImportError:
        return False, "python3-textual не установлен"


def check_dependencies() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for cmd, description in REQUIRED_COMMANDS:
        ok = _has_command(cmd)
        results.append({
            "name": description,
            "kind": "command",
            "target": cmd,
            "ok": ok,
            "message": f"Команда `{cmd}` найдена" if ok else f"Не найдена команда `{cmd}`",
        })

    for path, description in REQUIRED_FILES:
        ok = Path(path).exists()
        results.append({
            "name": description,
            "kind": "file",
            "target": path,
            "ok": ok,
            "message": f"{description} доступно" if ok else f"{description} не найдено (`{path}`)",
        })

    ok, msg = check_textual()
    results.append({
        "name": "python3-textual",
        "kind": "python-package",
        "target": "textual",
        "ok": ok,
        "message": msg if msg else "python3-textual установлен",
    })

    # xray
    xray_ok = _has_command("xray")
    results.append({
        "name": "xray",
        "kind": "command",
        "target": "xray",
        "ok": xray_ok,
        "message": "xray найден в PATH" if xray_ok else "xray не найден в PATH",
    })

    # privilege helper
    priv_ok = any(_has_command(h) for h in PRIVILEGE_HELPERS)
    results.append({
        "name": "привилегированный helper",
        "kind": "command",
        "target": "pkexec/sudo",
        "ok": priv_ok,
        "message": "pkexec/sudo доступен" if priv_ok else "pkexec и sudo не найдены",
    })

    return results


def suggest_install(results: list[dict[str, Any]]) -> list[str]:
    missing_packages: list[str] = []
    for r in results:
        if r["ok"]:
            continue
        if r["kind"] == "python-package":
            missing_packages.append("python3-textual")
        elif r["name"] == "iproute2":
            missing_packages.append("iproute2")
        elif r["name"] == "curl":
            missing_packages.append("curl")
        elif r["name"] == "xray":
            # xray ставится отдельно, не через apt
            pass
        elif r["name"] == "привилегированный helper":
            missing_packages.append("policykit-1")
    return list(set(missing_packages))


def run_bootstrap(interactive: bool = True, check_only: bool = False) -> bool:
    results = check_dependencies()
    all_ok = all(r["ok"] for r in results)

    if check_only:
        if not all_ok:
            for r in results:
                if not r["ok"]:
                    print(f"[FAIL] {r['message']}", file=sys.stderr)
        return all_ok

    if all_ok:
        return True

    if not interactive:
        for r in results:
            if not r["ok"]:
                print(f"[FAIL] {r['message']}", file=sys.stderr)
        return False

    print("Subvost Xray TUN — проверка зависимостей\n", file=sys.stderr)
    for r in results:
        status = "OK" if r["ok"] else "FAIL"
        print(f"  [{status}] {r['message']}", file=sys.stderr)

    missing = suggest_install(results)
    if missing and _can_install_packages():
        print(f"\nПредлагается установить: {', '.join(missing)}", file=sys.stderr)
        answer = input("Установить через apt? [Д/н]: ").strip().lower()
        if answer in ("", "д", "да", "y", "yes"):
            if _install_packages(missing):
                print("Установка завершена. Перепроверка...", file=sys.stderr)
                return run_bootstrap(interactive=False)
            else:
                print("Ошибка установки пакетов.", file=sys.stderr)
                return False

    return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Subvost TUI bootstrap")
    parser.add_argument("--check-only", action="store_true", help="Только проверить зависимости, не устанавливать")
    args = parser.parse_args()

    ok = run_bootstrap(interactive=not args.check_only, check_only=args.check_only)
    sys.exit(0 if ok else 1)
