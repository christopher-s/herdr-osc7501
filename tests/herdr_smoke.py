"""Real hc terminal smoke test, without a gateway/model call or user-tab changes.

Run using Hermes's Python: python tests/herdr_smoke.py
Only the uniquely named terminal this script creates is removed.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types
import uuid

ROOT = Path(__file__).resolve().parents[1]


class _Modal:
    def __init__(self, release=None):
        self._release = release
    def _approval_callback(self, command, description, **kwargs):
        if self._release is not None:
            self._release()
        return "once"
    def _clarify_callback(self, questions):
        return {"answers": {}, "outcome": "submitted"}
    def _sudo_password_callback(self):
        return ""


def hc(*args):
    result = subprocess.run(["hc", *args], capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def child():
    spec = importlib.util.spec_from_file_location("herdr_smoke_plugin", ROOT / "__init__.py")
    assert spec is not None and spec.loader is not None
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    # Install before importing the SDK, as in an actual CLI startup.
    plugin._install_cli_wrap()
    from hermes_cli.gateway_connection import SessionState
    from cli import HermesCLI
    from test_plugin import Connection
    connection = Connection(SessionState)
    # The real CLI class opens a session before lazily constructing its agent.
    # Bypass only its interactive constructor; exercise its wrapped assignments.
    from types import SimpleNamespace
    from typing import Any
    cli: Any = object.__new__(HermesCLI)
    cli.session_id = "smoke"
    cli._session_db = SimpleNamespace(connection=connection)
    connection.state("smoke").adopt_snapshot({"info": {"title": "Winston · 日本語 🐾"}})
    plugin._emit("idle")
    import threading
    release = threading.Event()
    print("READY", flush=True)

    class _HoldingModal(_Modal):
        def _approval_callback(self, command, description, **kwargs):
            release.wait(timeout=30)
            return "once"

    for command in sys.stdin:
        if command.strip() == "rename":
            connection.state(cli.session_id).apply_event("session.updated", {"title": "Renamed conversation"})
        elif command.strip() == "block":
            import types as _types
            plugin._wrap_modals(_types.SimpleNamespace(Modal=_HoldingModal))
            threading.Thread(target=_HoldingModal()._approval_callback,
                             args=("rm -rf /tmp/herdr-smoke", "Remove smoke scratch"), daemon=True).start()
        elif command.strip() == "release":
            release.set()
        elif command.strip() == "done":
            plugin._finish_from_result({"final_response": "Migration finished. Rows copied: 42\nMore detail."})
        elif command.strip() == "clear":
            plugin._force_clear()
        elif command.strip() == "exit":
            break


def main():
    name = "title-smoke-" + uuid.uuid4().hex[:8]
    address = None
    try:
        launched = hc("run", "--bg", "--no-notify", "--no-parent", "--name", name,
                      "--cwd", str(ROOT), sys.executable, str(Path(__file__).resolve()), "--child")
        address = launched["address"]
        hc("wait", address, "--output", "READY", "--timeout", "15")
        steps = [("Winston · 日本語 🐾", None, None),
                 ("Renamed conversation", "rename", None),
                 ("Renamed conversation", "block", "rm -rf /tmp/herdr-smoke"),
                 ("Renamed conversation", "release", None),
                 ("Renamed conversation", "done", None),
                 ("", "clear", None)]
        for expected, command, blocked_msg in steps:
            if command:
                # A blocked program still reads its own stdin through this harness.
                hc("send", *(["--force"] if command == "release" else []), address, command)
            actual = hc("get", address)
            assert actual["title"] == expected, actual
            status = actual["status"] or {}
            if blocked_msg:
                assert status.get("state") == "blocked", actual
                assert status.get("msg") == blocked_msg, actual
            if command == "release":
                for _ in range(40):
                    actual = hc("get", address)
                    status = actual["status"] or {}
                    if status.get("state") == "working":
                        break
                    time.sleep(0.25)
                assert status.get("state") == "working", actual
            if command == "done":
                assert status.get("state") == "done", actual
                assert status.get("msg") == "Migration finished. Rows copied: 42", actual
            if command == "clear":
                assert actual["status"] is None, actual
                assert actual["title"] == "", actual
            elif actual["status"] is not None:
                assert status.get("app") == "hermes", actual
            print(json.dumps({"terminal": address, "title": actual["title"],
                              "msg": status.get("msg"), "verified": True}, ensure_ascii=False))
    finally:
        if address:
            hc("kill", address)
            hc("rm", address)
            remaining = hc("ls")
            assert address not in {t["address"] for t in remaining["terminals"]}
            print("Smoke terminal removed.")


if __name__ == "__main__":
    child() if "--child" in sys.argv else main()
