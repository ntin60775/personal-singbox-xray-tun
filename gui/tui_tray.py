#!/usr/bin/env python3
"""Tray-индикатор для TUI-фронта через Ayatana/AppIndicator."""
from __future__ import annotations

import argparse
import importlib
import os
import sys
import threading
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from subvost_app_service import SubvostAppService, build_default_service


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TUI tray helper for Subvost Xray TUN.")
    parser.add_argument("--indicator-namespace", default="AyatanaAppIndicator3")
    parser.add_argument("--icon-name", default="subvost-xray-tun-icon")
    return parser.parse_args(argv)


class TUITrayHelper:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.service: SubvostAppService | None = None
        self.loop = None
        self.indicator = None
        self.indicator_module = None

    def load_runtime(self):
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version(self.args.indicator_namespace, "0.1")
        from gi.repository import Gio, GLib, Gtk

        indicator_module = importlib.import_module(f"gi.repository.{self.args.indicator_namespace}")
        return Gtk, Gio, GLib, indicator_module

    def init_service(self) -> None:
        try:
            self.service = build_default_service(SCRIPT_DIR)
        except Exception as exc:
            print(f"Tray: ошибка инициализации сервиса: {exc}", file=sys.stderr)

    def run(self) -> int:
        try:
            gtk_module, gio_module, glib_module, indicator_module = self.load_runtime()
        except Exception as exc:
            print(f"Tray недоступен: {exc}", file=sys.stderr)
            return 1
        self.indicator_module = indicator_module
        self.init_service()

        gtk_module.init_check()
        self.loop = glib_module.MainLoop()
        try:
            indicator = indicator_module.Indicator.new(
                "subvost-tui-tray",
                self.args.icon_name,
                indicator_module.IndicatorCategory.APPLICATION_STATUS,
            )
        except Exception as exc:
            print(f"Tray: не удалось создать индикатор: {exc}", file=sys.stderr)
            return 1
        indicator.set_status(indicator_module.IndicatorStatus.ACTIVE)
        indicator.set_title("Subvost Xray TUN")
        indicator.set_menu(self.build_menu(gtk_module, glib_module))
        self.indicator = indicator

        glib_module.timeout_add_seconds(3, self.update_status)
        self.loop.run()
        return 0

    def build_menu(self, gtk_module, glib_module):
        menu = gtk_module.Menu()
        items = (
            ("Подключить", lambda *_args: self.safe_call("start")),
            ("Отключить", lambda *_args: self.safe_call("stop")),
            ("Снять диагностику", lambda *_args: self.safe_call("diag")),
            ("Выход", lambda *_args: self.quit()),
        )
        for label, callback in items:
            item = gtk_module.MenuItem(label=label)
            item.connect("activate", callback)
            item.show()
            menu.append(item)
        return menu

    def safe_call(self, action: str) -> None:
        def _run():
            if self.service is None:
                return
            try:
                if action == "start":
                    self.service.start_runtime()
                elif action == "stop":
                    self.service.stop_runtime()
                elif action == "diag":
                    self.service.capture_diagnostics()
            except Exception as exc:
                print(f"Tray action {action} failed: {exc}", file=sys.stderr)
        threading.Thread(target=_run, daemon=True).start()

    def update_status(self) -> bool:
        if self.service is None or self.indicator is None:
            return True
        try:
            status = self.service.collect_status()
            summary = status.get("summary", {})
            state = summary.get("state", "unknown")
            if state == "connected":
                self.indicator.set_icon_full("network-vpn", "Подключено")
            elif state == "running":
                self.indicator.set_icon_full("network-vpn-acquiring", "Запуск...")
            else:
                self.indicator.set_icon_full("network-vpn-disconnected", "Отключено")
        except Exception:
            pass
        return True

    def quit(self) -> None:
        if self.loop is not None:
            self.loop.quit()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    helper = TUITrayHelper(args)
    return helper.run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
