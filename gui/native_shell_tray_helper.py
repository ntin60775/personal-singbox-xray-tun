#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gtk3 tray helper for Subvost native shell.")
    parser.add_argument("--control-bus-name", required=True)
    parser.add_argument("--control-object-path", required=True)
    parser.add_argument("--indicator-namespace", required=True)
    parser.add_argument("--icon-name", default="network-vpn")
    return parser.parse_args(argv)


class NativeShellTrayHelper:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.loop = None
        self.gio_module = None
        self.glib_module = None

    def load_runtime(self):
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version(self.args.indicator_namespace, "0.1")
        from gi.repository import Gio, GLib, Gtk

        indicator_module = importlib.import_module(f"gi.repository.{self.args.indicator_namespace}")
        return Gtk, Gio, GLib, indicator_module

    def run(self) -> int:
        gtk_module, gio_module, glib_module, indicator_module = self.load_runtime()
        self.gio_module = gio_module
        self.glib_module = glib_module
        proxy = gio_module.DBusProxy.new_for_bus_sync(
            gio_module.BusType.SESSION,
            gio_module.DBusProxyFlags.NONE,
            None,
            self.args.control_bus_name,
            self.args.control_object_path,
            "io.subvost.XrayTunNativeShell.Control",
            None,
        )

        gtk_module.init_check()
        self.loop = glib_module.MainLoop()
        indicator = indicator_module.Indicator.new(
            "subvost-native-shell-tray",
            self.args.icon_name,
            indicator_module.IndicatorCategory.APPLICATION_STATUS,
        )
        indicator.set_status(indicator_module.IndicatorStatus.ACTIVE)
        indicator.set_title("Subvost Xray TUN")
        indicator.set_menu(self.build_menu(gtk_module, proxy, glib_module))
        glib_module.timeout_add_seconds(3, self.ensure_control_owner, proxy)
        self.loop.run()
        return 0

    def build_menu(self, gtk_module, proxy, glib_module):
        menu = gtk_module.Menu()
        items = (
            ("Показать окно", lambda *_args: self.call(proxy, "ShowWindow")),
            ("Скрыть окно", lambda *_args: self.call(proxy, "HideWindow")),
            ("Старт", lambda *_args: self.call(proxy, "TriggerAction", ("start-runtime",))),
            ("Стоп", lambda *_args: self.call(proxy, "TriggerAction", ("stop-runtime",))),
            ("Снять диагностику", lambda *_args: self.call(proxy, "TriggerAction", ("capture-diagnostics",))),
            ("Настройки", lambda *_args: self.call(proxy, "OpenSettings")),
            ("Выход", lambda *_args: self.call(proxy, "Quit")),
        )
        for label, callback in items:
            item = gtk_module.MenuItem(label=label)
            item.connect("activate", callback)
            item.show()
            menu.append(item)
        return menu

    def call(self, proxy, method_name: str, args: tuple[str, ...] | None = None) -> None:
        parameters = None
        if args is not None:
            parameters = self.glib_module.Variant("(s)", args)
        proxy.call_sync(method_name, parameters, self.gio_module.DBusCallFlags.NONE, -1, None)

    def ensure_control_owner(self, proxy) -> bool:
        owner = proxy.get_name_owner()
        if owner:
            return True
        if self.loop is not None:
            self.loop.quit()
        return False


def main(argv: list[str] | None = None) -> int:
    helper = NativeShellTrayHelper(parse_args(argv))
    return helper.run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
