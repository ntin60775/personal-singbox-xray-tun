# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


repo_root = Path(SPECPATH)
gui_dir = repo_root / "gui"


a = Analysis(
    [str(gui_dir / "windows_core_cli.py")],
    pathex=[str(gui_dir), str(repo_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "gui_contract",
        "subvost_paths",
        "subvost_store",
        "subvost_parser",
        "subvost_runtime",
        "subvost_routing",
        "windows_runtime_adapter",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "gui_server",
        "embedded_webview",
        "native_shell_app",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="subvost-core",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
)
