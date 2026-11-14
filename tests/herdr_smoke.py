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
import uuid

ROOT = Path(__file__).resolve().parents[1]


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
    print("READY", flush=True)
    for command in sys.stdin:
        if command.strip() == "rename":
            connection.state(cli.session_id).apply_event("session.updated", {"title": "Renamed conversation"})
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
        for expected, command in [("Winston · 日本語 🐾", None),
                                  ("Renamed conversation", "rename"), ("", "clear")]:
            if command:
                hc("send", address, command)
            actual = hc("get", address)
            assert actual["title"] == expected, actual
            if command != "clear":
                assert actual["status"]["app"] == "hermes", actual
            print(json.dumps({"terminal": address, "title": actual["title"], "verified": True}, ensure_ascii=False))
    finally:
        if address:
            hc("kill", address)
            hc("rm", address)
            remaining = hc("ls")
            assert address not in {t["address"] for t in remaining["terminals"]}
            print("Smoke terminal removed.")


if __name__ == "__main__":
    child() if "--child" in sys.argv else main()
