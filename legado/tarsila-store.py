#!/usr/bin/env python3
"""Tarsila Store — shell nativo GTK3 + WebKit2 (sem Chromium)."""
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GLib, Gtk, WebKit2  # noqa: E402

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

RAIZ = os.environ.get("TARSILA_DIR", "/opt/tarsila-store")
BACKEND = os.path.join(RAIZ, "bin", "tarsila-backend.py")
PORT = int(os.environ.get("TARSILA_PORTA", "8474"))
URL = f"http://127.0.0.1:{PORT}/"
LOG_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "tarsila-store")
LOG = os.path.join(LOG_DIR, "backend.log")

WIN_W, WIN_H = 760, 460

_backend_proc = None
_we_started_backend = False


def _api_ok():
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/api/instalados", timeout=1.5
        ) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _start_backend():
    global _backend_proc, _we_started_backend
    if _api_ok():
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    logf = open(LOG, "a", encoding="utf-8")  # noqa: SIM115
    _backend_proc = subprocess.Popen(
        [sys.executable, "-u", BACKEND],
        stdout=logf,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    _we_started_backend = True
    for _ in range(40):
        if _api_ok():
            return
        time.sleep(0.25)
    raise RuntimeError("Backend da Tarsila Store não respondeu na porta %d" % PORT)


def _stop_backend():
    global _backend_proc, _we_started_backend
    if not _we_started_backend or _backend_proc is None:
        return
    if _backend_proc.poll() is None:
        _backend_proc.terminate()
        try:
            _backend_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _backend_proc.kill()
    _backend_proc = None
    _we_started_backend = False


def _allow_uri(uri):
    if uri.startswith("about:"):
        return True
    return uri.startswith(f"http://127.0.0.1:{PORT}")


class StoreWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Tarsila Store", default_width=WIN_W, default_height=WIN_H)
        self.set_icon_name("tarsila-store")
        GLib.set_application_name("Tarsila Store")
        Gdk.set_program_class("tarsila-store")

        settings = WebKit2.Settings()
        settings.set_enable_javascript(True)
        settings.set_enable_html5_local_storage(True)
        settings.set_enable_developer_extras(False)
        self.webview = WebKit2.WebView.new_with_settings(settings)
        self.webview.connect("decide-policy", self._on_decide_policy)
        self.add(self.webview)
        self.connect("delete-event", self._on_delete)
        self.webview.load_uri(URL)

    def _on_decide_policy(self, _webview, decision, decision_type):
        if decision_type != WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            return
        action = decision.get_navigation_action()
        req = action.get_request()
        uri = req.get_uri() if req else ""
        if _allow_uri(uri):
            return
        decision.ignore()

    def _on_delete(self, *_args):
        _stop_backend()
        Gtk.main_quit()
        return False


def main():
    if not os.path.isfile(BACKEND):
        sys.stderr.write("Backend não encontrado: %s\n" % BACKEND)
        sys.exit(1)
    _start_backend()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    win = StoreWindow()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
