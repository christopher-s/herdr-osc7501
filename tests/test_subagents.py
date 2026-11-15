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
        return sorted(p.name for p in Path(self.tmp.name).iterdir())

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

    def test_source_exception_fails_open_silently(self):
        self.gate()

        class Boom:
            def subagent_rows(self, *, busy):
                raise RuntimeError("gateway away")

        self.plugin._subagents_source = lambda: Boom()
        self.assertIsNone(self.plugin._subagents_sample())
        self.assertEqual(self.files(), [])

    def test_write_is_atomic_and_valid_json(self):
        self.gate()
        self.source([row()])
        wrote = self.plugin._subagents_sample()
        leftovers = [p for p in Path(self.tmp.name).iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])
        json.loads(Path(wrote).read_text())


if __name__ == "__main__":
    unittest.main()
