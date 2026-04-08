from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_DIRNAME = "subvost-xray-tun"
STORE_FILENAME = "store.json"
GENERATED_XRAY_CONFIG_FILENAME = "generated-xray-config.json"
ACTIVE_RUNTIME_XRAY_CONFIG_FILENAME = "active-runtime-xray-config.json"
GUI_SETTINGS_FILENAME = "gui-settings.json"
XRAY_ASSET_DIRNAME = "xray-assets"
GEOIP_ASSET_FILENAME = "geoip.dat"
GEOSITE_ASSET_FILENAME = "geosite.dat"


@dataclass(frozen=True)
class AppPaths:
    real_home: Path
    config_home: Path
    store_dir: Path
    store_file: Path
    generated_xray_config_file: Path
    active_runtime_xray_config_file: Path
    gui_settings_file: Path
    xray_asset_dir: Path
    geoip_asset_file: Path
    geosite_asset_file: Path


def resolve_config_home(real_home: Path, explicit_config_home: str | None = None) -> Path:
    candidate = explicit_config_home or os.environ.get("SUBVOST_REAL_XDG_CONFIG_HOME")
    if candidate:
        path = Path(candidate)
        if not path.is_absolute():
            raise ValueError(f"SUBVOST_REAL_XDG_CONFIG_HOME должен быть абсолютным путём: {candidate}")
        return path

    env_xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if env_xdg_config_home and os.geteuid() != 0:
        path = Path(env_xdg_config_home)
        if path.is_absolute():
            return path

    return real_home / ".config"


def build_app_paths(real_home: Path, explicit_config_home: str | None = None) -> AppPaths:
    config_home = resolve_config_home(real_home, explicit_config_home)
    store_dir = config_home / APP_DIRNAME
    xray_asset_dir = store_dir / XRAY_ASSET_DIRNAME
    return AppPaths(
        real_home=real_home,
        config_home=config_home,
        store_dir=store_dir,
        store_file=store_dir / STORE_FILENAME,
        generated_xray_config_file=store_dir / GENERATED_XRAY_CONFIG_FILENAME,
        active_runtime_xray_config_file=store_dir / ACTIVE_RUNTIME_XRAY_CONFIG_FILENAME,
        gui_settings_file=store_dir / GUI_SETTINGS_FILENAME,
        xray_asset_dir=xray_asset_dir,
        geoip_asset_file=xray_asset_dir / GEOIP_ASSET_FILENAME,
        geosite_asset_file=xray_asset_dir / GEOSITE_ASSET_FILENAME,
    )


def ensure_owned_dir(path: Path, uid: int | None = None, gid: int | None = None, mode: int = 0o700) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(mode)
    except OSError:
        pass
    if uid is not None and gid is not None and os.geteuid() == 0:
        try:
            os.chown(path, uid, gid)
        except OSError:
            pass


def ensure_store_dir(paths: AppPaths, uid: int | None = None, gid: int | None = None) -> None:
    ensure_owned_dir(paths.store_dir, uid=uid, gid=gid, mode=0o700)


def atomic_write_text(path: Path, text: str, mode: int = 0o600, uid: int | None = None, gid: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp_path = Path(handle.name)

    try:
        os.chmod(temp_path, mode)
    except OSError:
        pass

    if uid is not None and gid is not None and os.geteuid() == 0:
        try:
            os.chown(temp_path, uid, gid)
        except OSError:
            pass

    os.replace(temp_path, path)


def atomic_write_bytes(path: Path, data: bytes, mode: int = 0o600, uid: int | None = None, gid: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temp_path = Path(handle.name)

    try:
        os.chmod(temp_path, mode)
    except OSError:
        pass

    if uid is not None and gid is not None and os.geteuid() == 0:
        try:
            os.chown(temp_path, uid, gid)
        except OSError:
            pass

    os.replace(temp_path, path)


def atomic_write_json(path: Path, data: dict[str, Any], uid: int | None = None, gid: int | None = None) -> None:
    atomic_write_text(
        path,
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        mode=0o600,
        uid=uid,
        gid=gid,
    )


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def remove_file_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
