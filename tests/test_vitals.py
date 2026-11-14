"""Vitals sidecar contract: gated on HC_TERMINAL_ID, throttled, fail-open.

Run with Hermes's Python: python -m unittest discover -s tests -v.
"""
import json
import os
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from test_plugin import load_plugin


class FakeSnapshotCli:
    """Stand-in for the CLI object the vitals sampler reads."""

    def __init__(self, values):
        self._values = values
        self.calls = 0

    def _get_status_bar_snapshot(self):
        self.calls += 1
        return dict(self._values)


class Vitals(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ)
        self.env.start()
        os.environ.pop("HC_TERMINAL_ID", None)
        os.environ.pop("TMUX", None)
        self.addCleanup(self.env.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.plugin = load_plugin()
        self.plugin._vitals_reset_for_tests(dirpath=Path(self.tmp.name))

    def cli(self, **values):
        base = {
            "model_name": "zai/glm-5.3", "model_short": "glm-5.3",
            "context_percent": 23.0, "context_tokens": 184000,
            "context_length": 1000000, "avg_velocity": 54.2,
            "avg_latency": 412.0, "cache_hit_pct": 91.0,
            "session_total_tokens": 184000, "compressions": 1,
            "duration": "2m 13s",
        }
        base.update(values)
        return FakeSnapshotCli(base)

    def sample(self, cli):
        return self.plugin._vitals_sample(cli)

    def test_no_gate_no_file(self):
        path = self.plugin._vitals_write({"v": 1})
        self.assertIsNone(path)

    def test_gate_writes_contract_file(self):
        os.environ["HC_TERMINAL_ID"] = "t9"
        cli = self.cli()
        wrote = self.sample(cli)
        self.assertIsNotNone(wrote)
        data = json.loads(Path(wrote).read_text())
        self.assertEqual(data["v"], 1)
        self.assertEqual(data["term"], "t9")
        self.assertEqual(data["model_name"], "zai/glm-5.3")
        self.assertAlmostEqual(data["context_percent"], 23.0)
        self.assertNotIn("state", data)
        self.assertIn("ts", data)

    def test_machine_qualified_address_kept_verbatim(self):
        os.environ["HC_TERMINAL_ID"] = "devbox/t7"
        wrote = self.sample(self.cli())
        self.assertEqual(json.loads(Path(wrote).read_text())["term"], "devbox/t7")

    def test_throttle_many_events_one_write(self):
        os.environ["HC_TERMINAL_ID"] = "t3"
        cli = self.cli()
        first = self.sample(cli)
        for _ in range(5):
            self.assertIsNone(self.sample(cli))
        self.assertEqual(cli.calls, 6)

    def test_changed_value_within_window_is_deferred_not_dropped(self):
        os.environ["HC_TERMINAL_ID"] = "t3"
        cli = self.cli()
        self.sample(cli)
        cli._values["avg_velocity"] = 71.5
        # Inside the 500 ms window the write is rate-limited...
        self.assertIsNone(self.sample(cli))
        # ...and lands on the next eligible sample after the window.
        self.plugin._vitals_reset_for_tests(dirpath=Path(self.tmp.name))
        os.environ["HC_TERMINAL_ID"] = "t3"
        wrote = self.sample(cli)
        self.assertIsNotNone(wrote)
        self.assertAlmostEqual(json.loads(Path(wrote).read_text())["avg_velocity"], 71.5)

    def test_snapshot_failure_writes_nothing(self):
        os.environ["HC_TERMINAL_ID"] = "t4"

        class Boom:
            def _get_status_bar_snapshot(self):
                raise RuntimeError("no bar")

        self.assertIsNone(self.plugin._vitals_sample(Boom()))

    def test_partial_snapshot_maps_known_fields_only(self):
        os.environ["HC_TERMINAL_ID"] = "t5"
        cli = self.cli()
        del cli._values["avg_velocity"]
        del cli._values["cache_hit_pct"]
        wrote = self.sample(cli)
        data = json.loads(Path(wrote).read_text())
        self.assertNotIn("avg_velocity", data)
        self.assertAlmostEqual(data["context_pct"], 23.0)

    def test_exit_cleans_own_file(self):
        os.environ["HC_TERMINAL_ID"] = "t6"
        wrote = self.sample(self.cli())
        self.assertTrue(Path(wrote).exists())
        self.plugin._vitals_cleanup()
        self.assertFalse(Path(wrote).exists())

    def test_address_validation(self):
        for bad in ("", " ", "../evil", "t9;rm", "a/b/c"):
            os.environ["HC_TERMINAL_ID"] = bad
            self.assertFalse(self.plugin._vitals_enabled(),
                             f"{bad!r} should be rejected")
        for good in ("t3", "devbox/t7", "machine-2/t10"):
            os.environ["HC_TERMINAL_ID"] = good
            self.assertTrue(self.plugin._vitals_enabled(), f"{good!r} ok")

    def test_write_is_atomic_and_valid_json(self):
        os.environ["HC_TERMINAL_ID"] = "t7"
        wrote = self.sample(self.cli())
        d = Path(wrote).parent
        leftovers = [p for p in d.iterdir() if p.suffix == ".tmp"]
        self.assertEqual(leftovers, [])
        json.loads(Path(wrote).read_text())


if __name__ == "__main__":
    unittest.main()
