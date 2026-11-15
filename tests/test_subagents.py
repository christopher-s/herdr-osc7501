"""Subagent roster sidecar: gated, throttled, active-only, fail-open.

Run with Hermes's Python: python -m unittest discover -s tests -v.
No gateway or model request is made; the registry source is injected.
"""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from test_plugin import load_plugin


class StubSource:
    """Stand-in for the registry backend; answers subagent_rows like the view."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def subagent_rows(self, *, busy):
        self.calls += 1
        return [dict(r) for r in self.rows]


def row(**over):
    base = {
        "subagent_id": "sa-3-9f2c", "goal": "Review for regressions",
        "status": "running", "last_tool": "web_search",
        "running_seconds": 12.0, "started_at": time.time() - 12.0,
    }
    base.update(over)
    return base


class Subagents(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ)
        self.env.start()
        os.environ.pop("HC_TERMINAL_ID", None)
        os.environ.pop("TMUX", None)
        self.addCleanup(self.env.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.plugin = load_plugin()
        self.plugin._subagents_reset_for_tests(dirpath=Path(self.tmp.name))
        self.addCleanup(lambda: self.plugin._subagents_reset_for_tests())

    def gate(self, term="t9"):
        os.environ["HC_TERMINAL_ID"] = term

    def source(self, rows):
        stub = StubSource(rows)
        self.plugin._subagents_source = lambda: stub
        return stub

    def files(self):
        return sorted(p.name for p in Path(self.tmp.name).iterdir()
                      if not p.name.startswith("."))

    def test_gate_off_writes_no_file(self):
        self.source([row()])
        self.assertIsNone(self.plugin._subagents_sample())
        self.assertEqual(self.files(), [])

    def test_roster_maps_contract_fields(self):
        self.gate()
        self.source([row()])
        wrote = self.plugin._subagents_sample()
        self.assertIsNotNone(wrote)
        data = json.loads(Path(wrote).read_text())
        self.assertEqual(data["v"], 1)
        self.assertEqual(data["term"], "t9")
        self.assertIn("ts", data)
        self.assertEqual(data["children"], [{
            "id": "sa-3-9f2c", "task": "Review for regressions",
            "state": "running", "activity": "web_search", "age_s": 12,
        }])

    def test_elapsed_from_started_at_when_no_running_seconds(self):
        self.gate()
        self.source([row(running_seconds=None, started_at=time.time() - 30.0)])
        wrote = self.plugin._subagents_sample()
        child = json.loads(Path(wrote).read_text())["children"][0]
        self.assertGreaterEqual(child["age_s"], 29)
        self.assertLessEqual(child["age_s"], 31)

    def test_task_sanitized_one_line_and_capped(self):
        self.gate()
        self.source([row(goal="  line\x02one\nline two  ")])
        child = json.loads(Path(self.plugin._subagents_sample()).read_text())["children"][0]
        self.assertEqual(child["task"], "lineone")  # first line only, control stripped
        self.source([row(goal="x" * 300)])
        self.plugin._subagents_reset_for_tests(dirpath=Path(self.tmp.name))
        self.gate()
        self.plugin._subagents_source = lambda: StubSource([row(goal="x" * 300)])
        child = json.loads(Path(self.plugin._subagents_sample()).read_text())["children"][0]
        self.assertEqual(child["task"], "x" * 120)

    def test_throttle_many_events_one_call_one_write(self):
        self.gate()
        stub = self.source([row()])
        self.assertIsNotNone(self.plugin._subagents_sample())
        for _ in range(5):
            self.assertIsNone(self.plugin._subagents_sample())
        # the throttle short-circuits before consulting the source
        self.assertEqual(stub.calls, 1)

    def test_changed_roster_deferred_not_dropped(self):
        self.gate()
        stub = self.source([row()])
        self.plugin._subagents_sample()
        stub.rows[0]["status"] = "queued"
        self.assertIsNone(self.plugin._subagents_sample())  # inside the window
        self.plugin._subagents_reset_for_tests(dirpath=Path(self.tmp.name))
        os.environ["HC_TERMINAL_ID"] = "t9"
        self.plugin._subagents_source = lambda: stub
        wrote = self.plugin._subagents_sample()
        self.assertIsNotNone(wrote)
        data = json.loads(Path(wrote).read_text())
        self.assertEqual(data["children"][0]["state"], "queued")

    def test_empty_roster_unlinks_own_file(self):
        self.gate()
        stub = self.source([row()])
        wrote = self.plugin._subagents_sample()
        self.assertTrue(Path(wrote).exists())
        stub.rows = []
        self.plugin._subagents_reset_for_tests(dirpath=Path(self.tmp.name))
        os.environ["HC_TERMINAL_ID"] = "t9"
        self.plugin._subagents_source = lambda: stub
        self.plugin._subagents_sample()
        self.assertFalse(Path(wrote).exists())

    def test_exit_cleanup_removes_own_file(self):
        self.gate()
        self.source([row()])
        wrote = self.plugin._subagents_sample()
        self.assertTrue(Path(wrote).exists())
        self.plugin._subagents_cleanup()
        self.assertFalse(Path(wrote).exists())

    def test_no_source_fails_open_silently(self):
        self.gate()
        self.plugin._subagents_source = lambda: None
        self.assertIsNone(self.plugin._subagents_sample())
        self.assertEqual(self.files(), [])
        diag = Path(self.tmp.name) / ".diag-t9.json"
        self.assertTrue(diag.exists())
        self.assertIn("no-source", json.loads(diag.read_text())["err"])

    def test_source_exception_fails_open_silently(self):
        self.gate()

        class Boom:
            def subagent_rows(self, *, busy):
                raise RuntimeError("gateway away")

        self.plugin._subagents_source = lambda: Boom()
        self.assertIsNone(self.plugin._subagents_sample())
        self.assertEqual(self.files(), [])
        diag = Path(self.tmp.name) / ".diag-t9.json"
        self.assertTrue(diag.exists())
        self.assertIn("gateway away", json.loads(diag.read_text())["err"])

    def test_write_failure_diagnoses_without_file(self):
        self.gate()
        self.source([row()])

        def boom(path, payload):
            raise RuntimeError("disk sulks")

        self.plugin._subagents_write = boom
        self.assertIsNone(self.plugin._subagents_sample())
        self.assertEqual(self.files(), [])
        diag = Path(self.tmp.name) / ".diag-t9.json"
        self.assertTrue(diag.exists())
        self.assertIn("disk sulks", json.loads(diag.read_text())["err"])

    def test_write_is_atomic_and_valid_json(self):
        self.gate()
        self.source([row()])
        wrote = self.plugin._subagents_sample()
        leftovers = [p for p in Path(self.tmp.name).iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])
        json.loads(Path(wrote).read_text())

    def click(self, child="sa-3-9f2c", ts=None):
        path = Path(self.tmp.name) / "t9.click.json"
        path.write_text(json.dumps({"v": 1, "child": child, "ts": ts or time.time()}))
        return path

    def tail_fixture(self, text="First line\nLatest activity"):
        self.gate()
        stub = self.source([row()])
        stub.tail_calls = []
        def tail(child, *, fetch=False):
            stub.tail_calls.append((child, fetch))
            if isinstance(text, Exception):
                raise text
            return text
        stub.subagent_tail = tail
        self.plugin._subagents_sample()
        return stub

    def test_click_fetches_own_live_child_once_and_writes_bounded_tail(self):
        stub = self.tail_fixture("\x1b[31mred\x1b[0m\n" + "\n".join("x" * 400 for _ in range(12)))
        click = self.click()
        request = json.loads(click.read_text())
        path = self.plugin._subagents_click_sample()
        data = json.loads(Path(path).read_text())
        self.assertEqual(data["term"], "t9")
        self.assertEqual(data["child"], "sa-3-9f2c")
        self.assertEqual(data["request_ts"], request["ts"])
        self.assertEqual(len(data["lines"]), 8)
        self.assertTrue(all(len(line) <= 240 for line in data["lines"]))
        self.assertNotIn("\x1b", json.dumps(data["lines"]))
        with patch.object(self.plugin.time, "monotonic", return_value=time.monotonic() + 2):
            self.assertIsNone(self.plugin._subagents_click_sample())
        self.assertEqual(stub.tail_calls, [("sa-3-9f2c", True)])

    def test_click_rate_limit_defers_new_request(self):
        stub = self.tail_fixture()
        self.click(ts=1000)
        with patch.object(self.plugin.time, "time", return_value=1000), patch.object(self.plugin.time, "monotonic", return_value=10):
            self.plugin._subagents_click_sample()
            self.click(ts=1000.1)
            self.assertIsNone(self.plugin._subagents_click_sample())
        with patch.object(self.plugin.time, "time", return_value=1001), patch.object(self.plugin.time, "monotonic", return_value=11):
            self.assertIsNotNone(self.plugin._subagents_click_sample())
        self.assertEqual(len(stub.tail_calls), 2)

    def test_click_invalid_foreign_stale_or_future_requests_do_not_fetch(self):
        stub = self.tail_fixture()
        for value in ["{bad", {"v": 2, "child": "sa-3-9f2c", "ts": time.time()},
                      {"v": 1, "child": "foreign", "ts": time.time()},
                      {"v": 1, "child": "sa-3-9f2c", "ts": time.time() - 30},
                      {"v": 1, "child": "sa-3-9f2c", "ts": time.time() + 30}]:
            (Path(self.tmp.name) / "t9.click.json").write_text(value if isinstance(value, str) else json.dumps(value))
            self.plugin._subagents_click_last_poll = 0
            self.assertIsNone(self.plugin._subagents_click_sample())
        self.assertEqual(stub.tail_calls, [])

    def test_click_no_roster_or_no_gate_performs_no_io(self):
        self.tail_fixture()
        self.click()
        (Path(self.tmp.name) / "t9.json").unlink()
        with patch("builtins.open", side_effect=AssertionError("must not read click")):
            self.assertIsNone(self.plugin._subagents_click_sample())
        os.environ.pop("HC_TERMINAL_ID")
        with patch("builtins.open", side_effect=AssertionError("gate must not read")):
            self.assertIsNone(self.plugin._subagents_click_sample())

    def test_empty_roster_clears_tail_and_click(self):
        stub = self.tail_fixture()
        click = self.click()
        tail = Path(self.plugin._subagents_click_sample())
        stub.rows = []
        with patch.object(self.plugin.time, "monotonic", return_value=time.monotonic() + 2):
            self.plugin._subagents_sample()
        self.assertFalse(tail.exists())
        self.assertFalse(click.exists())
        self.assertIsNone(self.plugin._subagents_click_sample())

    def test_tail_failure_is_fail_open_and_cleanup_only_own_files(self):
        stub = self.tail_fixture(RuntimeError("unavailable"))
        self.click()
        self.assertIsNone(self.plugin._subagents_click_sample())
        self.assertFalse((Path(self.tmp.name) / "t9.tail.json").exists())
        foreign = Path(self.tmp.name) / "t8.tail.json"
        foreign.write_text("{}")
        self.plugin._subagents_cleanup()
        self.assertFalse((Path(self.tmp.name) / "t9.click.json").exists())
        self.assertTrue(foreign.exists())
        self.assertEqual(len(stub.tail_calls), 1)


if __name__ == "__main__":
    unittest.main()
