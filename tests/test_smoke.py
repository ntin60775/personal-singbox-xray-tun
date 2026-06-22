"""Smoke-gate: базовый сценарий жизненного цикла без TUI.

Импорт подписки -> автоимпорт routing-профиля -> активация узла ->
генерация runtime-конфига -> деактивация routing-профиля.

Покрывает критический путь, чтобы регрессия в store/runtime/routing
сразу проваливала smoke-gate.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "e2e"))

from subvost_paths import build_app_paths  # noqa: E402
from subvost_store import (  # noqa: E402
    activate_selection,
    add_subscription,
    clear_active_routing_profile,
    ensure_store_initialized,
    refresh_subscription,
    sync_generated_runtime,
)

from test_routing_e2e import (  # noqa: E402,E501
    FakeResponse,
    happ_routing_uri,
    single_vless_line,
)


class TestSmokeGateway(unittest.TestCase):
    """Smoke-gate: полный жизненный цикл import -> select -> start -> stop."""

    def test_full_lifecycle_import_select_start_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            # --- Setup ---
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))

            # Минимальный шаблон Xray-конфига (3 outbound'а + базовый routing)
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
                                            "users": [
                                                {"id": "uuid", "encryption": "none"}
                                            ],
                                        }
                                    ]
                                },
                                "streamSettings": {
                                    "network": "tcp",
                                    "security": "none",
                                },
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

            # --- 1. Добавляем подписку ---
            sub = add_subscription(
                store, "Smoke Sub", "https://example.com/sub"
            )

            # --- 2. Мокаем HTTP: sub body + geoip + geosite ---
            routing_uri = happ_routing_uri(
                {
                    "name": "SmokeRoute",
                    "directsites": ["geosite:cn"],
                    "directip": ["geoip:cn"],
                    "proxysites": ["geosite:youtube"],
                    "globalproxy": False,
                    "domainstrategy": "IPIfNonMatch",
                },
                mode="onadd",
            )
            headers = {"ETag": "etag-smoke-1", "routing": routing_uri}
            with patch(
                "urllib.request.urlopen",
                side_effect=[
                    FakeResponse(single_vless_line(), headers),
                    FakeResponse(b"geoip-bytes"),
                    FakeResponse(b"geosite-bytes"),
                ],
            ):
                result = refresh_subscription(
                    store, sub["id"], paths=paths
                )

            # --- 3. Проверяем автоимпорт routing-профиля ---
            routing_block = result.get("routing") or {}
            self.assertIn(
                routing_block.get("status"),
                {"created", "updated"},
                f"routing status должен быть created/updated, "
                f"получили {routing_block}",
            )
            self.assertTrue(routing_block.get("activated"))
            self.assertIsNotNone(routing_block.get("profile_id"))

            # --- 4. Проверяем состояние store ---
            self.assertIsNotNone(store["routing"]["active_profile_id"])
            self.assertTrue(store["routing"]["runtime_ready"])
            self.assertTrue(store["routing"]["geodata"]["ready"])

            # --- 5. Активируем первый узел добавленной подписки ---
            # Подписка создала свой профиль — найдём его и первый узел в нём.
            saved_sub = store["subscriptions"][0]
            sub_profile_id = saved_sub["profile_id"]
            sub_profile = next(
                p for p in store["profiles"] if p["id"] == sub_profile_id
            )
            self.assertGreater(
                len(sub_profile["nodes"]),
                0,
                "smoke-gate: подписка должна вернуть хотя бы один узел",
            )
            first_node = sub_profile["nodes"][0]
            activate_selection(
                store, sub_profile_id, first_node["id"], source="test"
            )

            # --- 6. Генерируем runtime-конфиг ---
            config_path = sync_generated_runtime(
                store, paths, project_root
            )
            self.assertIsNotNone(
                config_path, "sync_generated_runtime не должен вернуть None"
            )
            self.assertTrue(
                config_path.exists(),
                f"runtime-конфиг не создан: {config_path}",
            )

            rendered = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertIn("routing", rendered)
            self.assertIn("rules", rendered["routing"])
            self.assertGreater(
                len(rendered["routing"]["rules"]),
                0,
                "routing.rules не должен быть пустым",
            )

            # --- 7. Эмулируем «стоп» — снимаем активный routing-профиль ---
            clear_active_routing_profile(store, paths)
            self.assertIsNone(store["routing"]["active_profile_id"])
            self.assertFalse(store["routing"]["runtime_ready"])


if __name__ == "__main__":
    unittest.main()
