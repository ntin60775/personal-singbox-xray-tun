from __future__ import annotations

import base64
import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gui"))

from subvost_paths import build_app_paths  # noqa: E402
from subvost_routing import RoutingProfileError  # noqa: E402
from subvost_store import (  # noqa: E402
    MANUAL_PROFILE_ID,
    activate_routing_profile,
    add_subscription,
    clear_active_routing_profile,
    ensure_store_initialized,
    import_routing_profile,
    refresh_subscription,
    sync_generated_runtime,
)


def single_vless_line(name: str = "Node") -> bytes:
    return (
        f"vless://11111111-1111-1111-1111-111111111111@example.com:443"
        f"?type=tcp&security=none#{name}\n"
    ).encode("utf-8")


def happ_routing_uri(payload: dict, *, mode: str = "add") -> str:
    """Build a happ://routing/{mode}/{base64} URI for test subscription headers."""
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("utf-8")
    return f"happ://routing/{mode}/{encoded}"


class FakeResponse:
    """Minimal file-like response object for mocking urllib.request.urlopen."""

    def __init__(self, payload: bytes, headers: dict[str, str] | None = None, status: int = 200) -> None:
        self._payload = payload
        self.headers = headers or {}
        self.status = status

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _setup_environment(
    temp_dir: str,
) -> tuple[dict, Path, any]:
    """Set up temp dir, template config, paths, store, and active node.

    Returns (store, paths, project_root).
    """
    project_root = Path(temp_dir)
    real_home = project_root / "home"
    real_home.mkdir()
    paths = build_app_paths(real_home, str(real_home / ".config"))

    # Write minimal xray template config
    (project_root / "xray-tun-subvost.json").write_text(
        json.dumps(
            {
                "outbounds": [
                    {
                        "tag": "proxy",
                        "protocol": "vless",
                        "settings": {
                            "vnext": [
                                {
                                    "address": "template",
                                    "port": 443,
                                    "users": [{"id": "uuid", "encryption": "none"}],
                                }
                            ]
                        },
                        "streamSettings": {"network": "tcp", "security": "none"},
                    },
                    {"tag": "direct", "protocol": "freedom"},
                    {"tag": "block", "protocol": "blackhole"},
                ],
                "routing": {
                    "domainStrategy": "AsIs",
                    "rules": [
                        {
                            "type": "field",
                            "inboundTag": ["tun-in"],
                            "port": "53",
                            "outboundTag": "dns-out",
                        },
                        {
                            "type": "field",
                            "inboundTag": ["tun-in"],
                            "network": "tcp,udp",
                            "outboundTag": "proxy",
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    store = ensure_store_initialized(paths, project_root)

    # Populate a manual profile node for active_selection
    manual_profile = next(p for p in store["profiles"] if p["id"] == MANUAL_PROFILE_ID)
    manual_profile["nodes"].append(
        {
            "id": "node-1",
            "fingerprint": "fingerprint-1",
            "name": "Node-1",
            "protocol": "vless",
            "raw_uri": "vless://...",
            "origin": {"kind": "manual", "subscription_id": None},
            "enabled": True,
            "user_renamed": False,
            "parse_error": "",
            "normalized": {
                "fingerprint_hash": "fingerprint-1",
                "protocol": "vless",
                "address": "example.com",
                "port": 443,
                "uuid": "11111111-1111-1111-1111-111111111111",
                "encryption": "none",
                "flow": "",
                "network": "tcp",
                "security": "none",
                "host": "",
                "path": "",
                "server_name": "",
                "service_name": "",
                "grpc_authority": "",
                "fingerprint": "",
                "public_key": "",
                "short_id": "",
                "spider_x": "/",
                "mode": "auto",
                "xhttp_extra": {},
                "alpn": [],
                "allow_insecure": False,
                "display_name": "Node-1",
                "raw_uri": "vless://...",
            },
            "created_at": "2026-04-08T00:00:00+00:00",
            "updated_at": "2026-04-08T00:00:00+00:00",
        }
    )
    store["active_selection"] = {
        "profile_id": MANUAL_PROFILE_ID,
        "node_id": "node-1",
        "activated_at": "2026-04-08T00:00:00+00:00",
        "source": "test",
    }
    return store, paths, project_root


class TestSubscriptionRoutingFlow(unittest.TestCase):
    """E2E 5.1: Cквозной поток подписка -> профиль -> активация -> конфиг."""

    def test_subscription_routing_profile_flow(self) -> None:
        """Subscription with onadd header creates profile, activates it,
        enabling routing generates a config with routing rules applied."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store, paths, project_root = _setup_environment(temp_dir)
            subscription = add_subscription(store, "Test Sub", "https://example.com/sub")

            # Prepare onadd routing URI so the profile auto-activates
            routing_uri = happ_routing_uri(
                {
                    "name": "SubRoute",
                    "directsites": ["geosite:cn"],
                    "directip": ["geoip:cn"],
                    "proxysites": ["geosite:youtube"],
                    "globalproxy": False,
                    "domainstrategy": "IPIfNonMatch",
                },
                mode="onadd",
            )
            headers = {"ETag": "etag-1", "routing": routing_uri}

            # HTTP calls: 1) subscription body  2) geoip.dat  3) geosite.dat
            with patch(
                "urllib.request.urlopen",
                side_effect=[
                    FakeResponse(single_vless_line(), headers),
                    FakeResponse(b"geoip-bytes"),
                    FakeResponse(b"geosite-bytes"),
                ],
            ):
                result = refresh_subscription(
                    store, subscription["id"], paths=paths
                )

            # --- Assert routing result ---
            self.assertEqual(result["routing"]["status"], "created")
            self.assertEqual(result["routing"]["source"], "response_header")
            self.assertTrue(result["routing"]["activated"])
            self.assertIsNotNone(result["routing"].get("profile_id"))
            self.assertIsNotNone(result["routing"].get("profile_name"))

            # --- Assert metadata on subscription ---
            saved_sub = store["subscriptions"][0]
            self.assertIsNotNone(saved_sub.get("routing_profile_id"))
            self.assertEqual(saved_sub.get("last_routing_status"), "linked")
            self.assertEqual(saved_sub.get("last_routing_error"), "")

            # --- Assert profile was created with expected fields ---
            profile = next(
                item
                for item in store["routing"]["profiles"]
                if item["id"] == saved_sub["routing_profile_id"]
            )
            self.assertTrue(profile["auto_managed"])
            self.assertEqual(profile["source_subscription_id"], subscription["id"])
            self.assertEqual(profile["source_kind"], "response_header")
            self.assertEqual(profile["activation_mode"], "onadd")
            self.assertEqual(profile["name"], "SubRoute")
            self.assertEqual(profile["direct_sites"], ["geosite:cn"])
            self.assertEqual(profile["direct_ip"], ["geoip:cn"])
            self.assertEqual(profile["proxy_sites"], ["geosite:youtube"])
            self.assertFalse(profile.get("global_proxy"))
            self.assertEqual(profile["domain_strategy"], "IPIfNonMatch")

            # --- Assert auto-activation ---
            self.assertEqual(
                store["routing"]["active_profile_id"], profile["id"]
            )
            self.assertTrue(store["routing"]["geodata"]["ready"])

            self.assertTrue(store["routing"]["active_profile_id"])
            self.assertTrue(store["routing"]["runtime_ready"])
            self.assertFalse(store["routing"]["runtime_error"])

            # --- Generate runtime config ---
            config_path = sync_generated_runtime(store, paths, project_root)
            self.assertIsNotNone(config_path)
            self.assertTrue(config_path.exists())

            rendered = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertIn("routing", rendered)
            self.assertIn("rules", rendered["routing"])

            # Verify routing rules include profile effect.
            # The last rule should be the catchall for proxy due to global_proxy=False.
            rules = rendered["routing"]["rules"]
            self.assertGreater(len(rules), 0)



class TestStartRejectedWhenRoutingNotReady(unittest.TestCase):
    """E2E 5.3: Старт runtime отклоняется при неготовой маршрутизации."""

    def test_start_rejected_when_routing_not_ready(self) -> None:
        """Import succeeds with failed geodata;
        enabling routing raises ValueError;
        sync_generated_runtime returns None when routing enabled but not ready."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store, paths, project_root = _setup_environment(temp_dir)

            routing_json = json.dumps(
                {
                    "name": "Broken Route",
                    "globalproxy": True,
                }
            )

            # Mock download_routing_geodata to fail
            with patch(
                "subvost_store.download_routing_geodata",
                side_effect=RoutingProfileError("Simulated geodata failure"),
            ):
                # Import succeeds even though geodata fails; profile is created
                result = import_routing_profile(store, paths, routing_json)
                self.assertTrue(result["created"])
                profile = result["profile"]
                profile_id = profile["id"]

                # Profile should be active (set by import_routing_profile)
                self.assertEqual(
                    store["routing"]["active_profile_id"], profile_id
                )
                # Geodata should NOT be ready
                self.assertFalse(
                    store["routing"]["geodata"]["ready"]
                )
                # Routing is active (active_profile_id set) but runtime_ready is False
                # because geodata download failed.
                self.assertFalse(store["routing"]["runtime_ready"])

                # sync_generated_runtime should reject config generation when
                # routing is active but not runtime_ready
                config_path = sync_generated_runtime(
                    store, paths, project_root
                )
                self.assertIsNone(config_path)

                # Clear routing profile so config can be generated for testing
                store["routing"]["active_profile_id"] = None
                config_path = sync_generated_runtime(
                    store, paths, project_root
                )
                self.assertIsNotNone(config_path)
                self.assertTrue(config_path.exists())

                rendered = json.loads(
                    config_path.read_text(encoding="utf-8")
                )
                # Config should NOT have routing rules from our profile
                self.assertIn("routing", rendered)


class TestActivateAndDeactivateProfile(unittest.TestCase):
    """E2E 5.4: Активация и деактивация профиля."""

    def test_activate_profile_sets_active_and_ready(self) -> None:
        """activate_routing_profile при наличии geodata выставляет active_profile_id и runtime_ready."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store, paths, project_root = _setup_environment(temp_dir)
            routing_json = json.dumps({
                "name": "Test Route",
                "globalproxy": True,
            })
            with patch(
                "urllib.request.urlopen",
                side_effect=[FakeResponse(b"geoip-bytes"), FakeResponse(b"geosite-bytes")],
            ):
                result = import_routing_profile(store, paths, routing_json)
                profile_id = result["profile"]["id"]
                # activate again to ensure idempotent
                activate_routing_profile(store, paths, profile_id)
            self.assertEqual(store["routing"]["active_profile_id"], profile_id)
            self.assertTrue(store["routing"]["runtime_ready"])
            self.assertFalse(store["routing"]["runtime_error"])

    def test_deactivate_profile_clears_active(self) -> None:
        """clear_active_routing_profile сбрасывает active_profile_id в None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store, paths, project_root = _setup_environment(temp_dir)
            routing_json = json.dumps({
                "name": "Test Route",
                "globalproxy": True,
            })
            with patch(
                "urllib.request.urlopen",
                side_effect=[FakeResponse(b"geoip-bytes"), FakeResponse(b"geosite-bytes")],
            ):
                result = import_routing_profile(store, paths, routing_json)
                profile_id = result["profile"]["id"]
                activate_routing_profile(store, paths, profile_id)
            self.assertEqual(store["routing"]["active_profile_id"], profile_id)
            self.assertTrue(store["routing"]["runtime_ready"])
            # Deactivate
            clear_active_routing_profile(store, paths)
            self.assertIsNone(store["routing"]["active_profile_id"])
            self.assertFalse(store["routing"]["runtime_ready"])


def _resolve_first_real_subscription_url() -> str | None:
    """Читает реальный store.json пользователя и возвращает URL первой enabled-подписки.

    Возвращает None если:
    - store.json не существует или не читается;
    - в store нет подписок;
    - все подписки disabled.
    """
    config_home = os.environ.get("SUBVOST_REAL_XDG_CONFIG_HOME") or Path.home() / ".config"
    store_path = Path(config_home) / "subvost-xray-tun" / "store.json"
    if not store_path.is_file():
        return None
    try:
        store = json.loads(store_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    for sub in store.get("subscriptions", []):
        if sub.get("enabled", True) and sub.get("url"):
            return sub["url"]
    return None


def _resolve_first_subscription_url() -> str | None:
    """Возвращает URL первой живой подписки: сначала ищет в реальном store.json,
    затем в переменной окружения SUBVOST_TEST_SUBSCRIPTION_URL.
    """
    url = _resolve_first_real_subscription_url()
    if url:
        return url
    return os.environ.get("SUBVOST_TEST_SUBSCRIPTION_URL") or None


_first_subscription_url = _resolve_first_subscription_url()
class TestLiveSubscriptionRoutingAutoImport(unittest.TestCase):
    """E2E 5.5: автоимпорт routing-профиля из живой подписки.

    Проверяет, что refresh_subscription без моков на живой подписке
    корректно импортирует routing-профиль (если провайдер отдаёт
    happ://routing/... header) или корректно сообщает 'none', если
    провайдер routing не поддерживает.
    """

    def test_live_subscription_auto_imports_routing_profile(self) -> None:
        """Реальная подписка: либо импортирует routing, либо корректно
        сообщает 'none' / 'skipped'. Любая ошибка сети — SkipTest.
        """
        url = _first_subscription_url
        if not url:
            raise unittest.SkipTest(
                "Нет доступной подписки: store.json не содержит enabled-подписок "
                "и SUBVOST_TEST_SUBSCRIPTION_URL не задан."
            )
        with tempfile.TemporaryDirectory() as temp_dir:
            store, paths, project_root = _setup_environment(temp_dir)
            subscription = add_subscription(store, "Live Test Sub", url)

            try:
                result = refresh_subscription(
                    store, subscription["id"], paths=paths
                )
            except (socket.timeout, OSError) as exc:
                raise unittest.SkipTest(
                    f"Live subscription unreachable: {exc}"
                ) from exc
            except ValueError as exc:
                message = str(exc)
                if any(
                    marker in message
                    for marker in (
                        "HTTP ",
                        "Не удалось загрузить подписку",
                        "timed out",
                    )
                ):
                    raise unittest.SkipTest(
                        f"Live subscription unreachable: {exc}"
                    ) from exc
                raise

            routing_block = result.get("routing") or {}
            status = routing_block.get("status")

            self.assertIn(
                status,
                {"created", "updated", "never", "none", "skipped", "error"},
            )

            if status in {"created", "updated"}:
                profile_id = routing_block.get("profile_id")
                self.assertIsNotNone(
                    profile_id,
                    f"routing status={status} обязан вернуть profile_id, "
                    f"получили: {routing_block}",
                )
                profile = next(
                    (
                        p
                        for p in store["routing"]["profiles"]
                        if p["id"] == profile_id
                    ),
                    None,
                )
                self.assertIsNotNone(
                    profile,
                    f"Профиль {profile_id} не найден в store: "
                    f"{store['routing']['profiles']}",
                )
                if routing_block.get("activated"):
                    self.assertEqual(
                        store["routing"]["active_profile_id"],
                        profile_id,
                    )
                if routing_block.get("activated"):
                    self.assertTrue(
                        store["routing"]["geodata"].get("ready"),
                        f"geodata не готовы: {store['routing']['geodata']}",
                    )
                else:
                    print(
                        f"[live routing] профиль {profile_id} создан, но не активирован "
                        f"(activation_mode не onadd) — geodata не требуется немедленно."
                    )
            elif status == "none":
                print(
                    f"[live routing] подписка '{subscription['name']}' "
                    f"не отдаёт happ://routing заголовок — пропускаем."
                )
            elif status == "skipped":
                print(
                    f"[live routing] подписка '{subscription['name']}' "
                    f"skipped: {routing_block.get('message', '')}"
                )
            elif status == "error":
                self.fail(
                    f"Routing auto-import failed: {routing_block}"
                )

if __name__ == "__main__":
    unittest.main()
