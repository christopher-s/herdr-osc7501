"""Exercise emitted terminal bytes and the installed Hermes SDK contracts.

Run with Hermes's Python: python -m unittest discover -s tests -v.
No gateway or model request is made.
"""
import importlib.util
import io
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from hermes_cli.gateway_connection import SessionState as NativeState
from hermes_cli.gateway_agent import GatewayAgent as NativeAgent

ROOT = Path(__file__).resolve().parents[1]


def load_plugin():
    spec = importlib.util.spec_from_file_location("herdr_plugin_test", ROOT / "__init__.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Connection:
    """In-memory transport: real SDK state/agent, no network or gateway writes."""
    def __init__(self, state_cls):
        self.states = {}
        self.epoch = 0
        self.state_cls = state_cls

    def state(self, session_id):
        if session_id not in self.states:
            self.states[session_id] = self.state_cls(session_id)
        return self.states[session_id]

    def call(self, method, **kwargs):
        return {}


class Titles(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ)
        self.env.start()
        os.environ.pop("TMUX", None)
        self.addCleanup(self.env.stop)
        self.plugin = load_plugin()
        self.output = []
        self.writer = patch.object(self.plugin, "_write", side_effect=self.capture)
        self.writer.start()
        self.addCleanup(self.writer.stop)
        # Subclass the real SDK so a test never changes the process-wide SDK.
        class State(NativeState):
            pass
        class Agent(NativeAgent):
            pass
        self.State, self.Agent = State, Agent
        getattr(self.plugin, "_wrap_connection", lambda mod: None)(types.SimpleNamespace(SessionState=State))
        self.plugin._wrap_gateway(types.SimpleNamespace(GatewayAgent=Agent))
        self.connection = Connection(State)

    def capture(self, data):
        self.output.append(data)
        return True

    def select(self, session="one", title="Herdr conversation titles"):
        state = self.connection.state(session)
        state.adopt_snapshot({"info": {"title": title}})
        return self.Agent(connection=self.connection, session_id=session)

    def titles(self):
        return [part for part in self.output if part.startswith(b"\x1b]2;")]

    def test_initial_native_conversation_title(self):
        self.select()
        self.assertEqual(self.titles(), [b"\x1b]2;Herdr conversation titles\x1b\\"])

    def test_unicode_title(self):
        self.select(title="Winston · 日本語 🐾")
        self.assertEqual(self.titles(), ["\x1b]2;Winston · 日本語 🐾\x1b\\".encode()])

    def test_renames_arrive_between_turns(self):
        agent = self.select()
        self.connection.state(agent.session_id).apply_event("session.updated", {"title": "Renamed conversation"})
        self.assertEqual(self.titles()[-1:], [b"\x1b]2;Renamed conversation\x1b\\"])

    def test_other_sessions_cannot_overwrite_selected_title(self):
        self.select()
        self.connection.state("other").adopt_snapshot({"info": {"title": "Wrong snapshot"}})
        self.connection.state("other").apply_event("session.info", {"title": "Wrong event"})
        self.assertEqual(self.titles(), [b"\x1b]2;Herdr conversation titles\x1b\\"])

    def test_new_and_resumed_sessions_replace_title(self):
        agent = self.select()
        agent.session_id = "new"
        self.connection.state("resumed").adopt_snapshot({"info": {"title": "Resumed conversation"}})
        agent.session_id = "resumed"
        self.connection.state("one").apply_event("session.updated", {"title": "Late stale event"})
        self.assertEqual(self.titles(), [b"\x1b]2;Herdr conversation titles\x1b\\",
                                        b"\x1b]2;Hermes\x1b\\", b"\x1b]2;Resumed conversation\x1b\\"])

    def test_null_and_empty_titles_clear_stale_sdk_title(self):
        agent = self.select()
        state = self.connection.state(agent.session_id)
        state.apply_event("session.updated", {"title": None})
        state.apply_event("session.updated", {"title": "Again"})
        state.adopt_snapshot({"info": {"title": ""}})
        self.assertEqual(self.titles()[-3:], [b"\x1b]2;Hermes\x1b\\", b"\x1b]2;Again\x1b\\", b"\x1b]2;Hermes\x1b\\"])

    def test_unrelated_events_and_duplicate_titles_do_not_write(self):
        self.select()
        state = self.connection.state("one")
        state.apply_event("session.updated", {"title": "Herdr conversation titles"})
        state.apply_event("session.info", {"model": "another-model"})
        state.apply_event("session.usage", {"api_calls": 1})
        self.assertEqual(len(self.titles()), 1)

    def test_controls_and_terminal_sequences_are_removed(self):
        self.select(title="  Read\x1b[31m red\x1b[0m\n\t title\x1b]52;c;c2VjcmV0\x07\x9b2J\u202e 🐾 ")
        self.assertEqual(self.titles(), ["\x1b]2;Read red title 🐾\x1b\\".encode()])

    def test_title_is_bounded(self):
        self.select(title="a" * 300)
        self.assertEqual(self.titles(), [b"\x1b]2;" + b"a" * 256 + b"\x1b\\"])

    def test_failed_write_is_retried_on_next_title_event(self):
        self.plugin._write.side_effect = lambda data: False
        self.select()
        self.plugin._write.side_effect = self.capture
        self.connection.state("one").apply_event("session.updated", {"title": "Herdr conversation titles"})
        self.assertEqual(self.titles(), [b"\x1b]2;Herdr conversation titles\x1b\\"])

    def test_title_failure_does_not_break_session_updates(self):
        self.plugin._write.side_effect = OSError("tty closed")
        self.select()
        self.connection.state("one").apply_event("session.updated", {"title": "Still usable"})
        self.assertEqual(self.connection.state("one").title, "Still usable")

    def test_tmux_passthrough(self):
        os.environ["TMUX"] = "test"
        self.select(title="Topic")
        self.assertIn(b"\x1bPtmux;\x1b\x1b]2;Topic\x1b\x1b\\\x1b\\", self.output)

    def test_quit_clears_title_and_ignores_late_events(self):
        self.select()
        self.plugin._force_clear()
        self.connection.state("one").apply_event("session.updated", {"title": "Late"})
        self.assertIn(b"\x1b]7501;state=clear:app=hermes\x1b\\", self.output)
        self.assertEqual(self.titles()[-1:], [b"\x1b]2;\x1b\\"])

    def test_missing_optional_sdk_seams_fail_open(self):
        getattr(self.plugin, "_wrap_connection", lambda m: None)(types.SimpleNamespace())
        self.plugin._wrap_gateway(types.SimpleNamespace())
        self.plugin._wrap_gateway(types.SimpleNamespace(GatewayAgent=type("Older", (), {})))

    def test_wrapping_twice_keeps_single_publication(self):
        self.plugin._wrap_gateway(types.SimpleNamespace(GatewayAgent=self.Agent))
        getattr(self.plugin, "_wrap_connection", lambda m: None)(types.SimpleNamespace(SessionState=self.State))
        self.select()
        self.assertEqual(len(self.titles()), 1)

    def test_resumed_title_before_first_agent_is_created(self):
        from hermes_cli.cli_init_mixin import CLIInitMixin
        from typing import Any
        class CLI(CLIInitMixin):
            pass
        self.plugin._wrap_cli_titles(types.SimpleNamespace(HermesCLI=CLI))
        cli: Any = object.__new__(CLI)
        cli.session_id = "resumed"
        cli.agent = None
        cli._session_db = types.SimpleNamespace(connection=self.connection)
        self.connection.state("resumed").adopt_snapshot({"info": {"title": "Idle resumed conversation"}})
        self.assertEqual(self.titles()[-1:], [b"\x1b]2;Idle resumed conversation\x1b\\"])
        self.connection.state("resumed").apply_event("session.updated", {"title": "Idle rename"})
        self.assertEqual(self.titles()[-1:], [b"\x1b]2;Idle rename\x1b\\"])

    def test_resume_before_first_chat_rebinds_cli_title(self):
        from typing import Any
        class CLI:
            pass
        self.plugin._wrap_cli_titles(types.SimpleNamespace(HermesCLI=CLI))
        cli: Any = CLI()
        cli._session_db = types.SimpleNamespace(connection=self.connection)
        self.connection.state("one").adopt_snapshot({"info": {"title": "First idle conversation"}})
        self.connection.state("two").adopt_snapshot({"info": {"title": "Second idle conversation"}})
        cli.session_id = "one"
        cli.agent = None
        cli.session_id = "two"
        self.connection.state("one").apply_event("session.updated", {"title": "Stale idle conversation"})
        self.assertEqual(self.titles()[-1:], [b"\x1b]2;Second idle conversation\x1b\\"])

    def test_import_hook_covers_startup_and_preloaded_modules(self):
        import subprocess
        for preload in (False, True):
            code = '''
import importlib.util, sys
spec = importlib.util.spec_from_file_location("plugin", sys.argv[1])
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
if sys.argv[2] == "True":
    import hermes_cli.gateway_agent
p._write = lambda data: True
p._install_cli_wrap()
import hermes_cli.gateway_agent
from hermes_cli.gateway_connection import SessionState
from hermes_cli.gateway_agent import GatewayAgent
assert getattr(SessionState.apply_event, p._WRAP, False)
assert getattr(SessionState.adopt_snapshot, p._WRAP, False)
assert getattr(GatewayAgent.session_id.fset, p._WRAP, False)
assert getattr(GatewayAgent.run_conversation, p._WRAP, False)
print("startup wrappers installed")
'''
            result = subprocess.run([sys.executable, "-c", code, str(ROOT / "__init__.py"), str(preload)],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("startup wrappers installed", result.stdout)

    def test_existing_status_protocol_and_deduplication(self):
        self.plugin._emit("working")
        self.plugin._emit("working")
        self.plugin._on_blocked(kind="clarify", platform="cli")
        self.plugin._finish_from_result({})
        self.assertEqual(self.output, [b"\x1b]7501;state=working:app=hermes\x1b\\",
            b"\x1b]7501;state=blocked:app=hermes:kind=question:msg=V2FpdGluZyBmb3IgYW4gYW5zd2Vy\x1b\\",
            b"\x1b]7501;state=done:app=hermes\x1b\\"])


    def test_short_terminal_writes_complete_the_payload(self):
        accepted = bytearray()
        def short_write(fd, data):
            accepted.extend(data[:2])
            return min(2, len(data))
        with patch.object(self.plugin.os, "open", return_value=99), patch.object(self.plugin.os, "close"), \
             patch.object(self.plugin.os, "write", side_effect=short_write):
            self.writer.stop()
            self.assertTrue(self.plugin._write(b"complete payload"))
        self.assertEqual(accepted, b"complete payload")

    def test_zero_progress_terminal_write_fails(self):
        with patch.object(self.plugin.os, "open", return_value=99), patch.object(self.plugin.os, "close"), \
             patch.object(self.plugin.os, "write", return_value=0):
            self.writer.stop()
            self.assertFalse(self.plugin._write(b"payload"))

    def test_utf8_stdout_fallback(self):
        class Output(io.StringIO):
            def isatty(self):
                return True
        out = Output()
        with patch.object(self.plugin.os, "open", side_effect=OSError), patch.object(sys, "__stdout__", out):
            self.writer.stop()
            self.assertTrue(self.plugin._write("\x1b]2;日本語\x1b\\".encode()))
        self.assertEqual(out.getvalue(), "\x1b]2;日本語\x1b\\")


class Messages(unittest.TestCase):
    def setUp(self):
        self.plugin = load_plugin()
        self.output = []
        self.writer = patch.object(self.plugin, "_write", side_effect=self.capture)
        self.writer.start()
        self.addCleanup(self.writer.stop)

    def capture(self, data):
        self.output.append(data)
        return True

    def reports(self):
        return [r for r in self.output if r.startswith(b"\x1b]7501;")]

    @staticmethod
    def msg_of(report):
        text = report.decode("ascii")
        for part in text.split(":"):
            if part.startswith("msg="):
                import base64
                return base64.b64decode(part[4:]).decode("utf-8")
        return None

    @staticmethod
    def modal():
        """A class carrying all three modal methods, as wrapper discovery requires."""
        class Modal:
            def _approval_callback(self, command, description, **kwargs):
                return "once"
            def _clarify_callback(self, questions):
                return {"answers": {}, "outcome": "submitted"}
            def _sudo_password_callback(self):
                return ""
        return Modal()

    def test_approval_block_carries_command(self):
        modal = self.modal()
        self.plugin._wrap_modals(types.SimpleNamespace(Modal=type(modal)))
        modal._approval_callback("rm -rf /tmp/x", "Remove scratch")
        blocked = [r for r in self.reports() if b"state=blocked" in r]
        self.assertEqual(len(blocked), 1)
        self.assertIn("kind=permission", blocked[0].decode())
        self.assertEqual(self.msg_of(blocked[0]), "rm -rf /tmp/x")

    def test_approval_block_prefers_short_description(self):
        modal = self.modal()
        self.plugin._wrap_modals(types.SimpleNamespace(Modal=type(modal)))
        modal._approval_callback("x" * 120, "Install dependencies")
        blocked = [r for r in self.reports() if b"state=blocked" in r]
        self.assertEqual(self.msg_of(blocked[0]), "Install dependencies")

    def test_clarify_block_carries_first_question(self):
        modal = self.modal()
        self.plugin._wrap_modals(types.SimpleNamespace(Modal=type(modal)))
        modal._clarify_callback([
            {"qid": "q0", "question": "Which database?", "choices": ["postgres", "sqlite"]},
            {"qid": "q1", "question": "And region?", "choices": None}])
        blocked = [r for r in self.reports() if b"state=blocked" in r]
        self.assertIn("kind=question", blocked[0].decode())
        self.assertEqual(self.msg_of(blocked[0]), "Which database?")

    def test_blocked_message_falls_back_when_payload_is_unusable(self):
        class Modal:
            def _approval_callback(self, command="", description="", **kwargs):
                return "once"
        self.plugin._wrap_modals(types.SimpleNamespace(Modal=Modal))
        Modal()._approval_callback("", "  ")
        blocked = [r for r in self.reports() if b"state=blocked" in r]
        self.assertEqual(self.msg_of(blocked[0]), "Waiting for approval")

    def test_block_clears_message_when_work_resumes(self):
        class Modal:
            def _approval_callback(self, command, description, **kwargs):
                return "once"
        self.plugin._wrap_modals(types.SimpleNamespace(Modal=Modal))
        Modal()._approval_callback("npm install", "Install")
        self.plugin._emit("working")
        working = [r for r in self.reports() if b"state=working" in r][-1]
        self.assertNotIn(b"msg=", working)

    def test_done_carries_reply_headline(self):
        self.plugin._finish_from_result({"final_response": "All 22 tests passed.\nDetails attached."})
        done = [r for r in self.reports() if b"state=done" in r]
        self.assertEqual(len(done), 1)
        self.assertEqual(self.msg_of(done[0]), "All 22 tests passed.")

    def test_done_headline_sanitized_and_bounded(self):
        self.plugin._finish_from_result({"final_response": "  \x1b[31mDeploy" + " ok" * 200 + "\x1b[0m\nline two"})
        done = [r for r in self.reports() if b"state=done" in r]
        self.assertEqual(self.msg_of(done[0]), ("Deploy" + " ok" * 200)[:120].strip())

    def test_done_without_usable_text_omits_msg(self):
        self.plugin._finish_from_result({"final_response": "   \n\t"})
        done = [r for r in self.reports() if b"state=done" in r]
        self.assertEqual(done, [b"\x1b]7501;state=done:app=hermes\x1b\\"])

    def test_error_carries_sanitized_error_text(self):
        self.plugin._finish_from_result({"failed": True, "error": "Gateway lost\nretry later"})
        error = [r for r in self.reports() if b"state=error" in r]
        self.assertEqual(self.msg_of(error[-1]), "Gateway lost")

    def test_failed_and_interrupted_omit_headline(self):
        self.plugin._finish_from_result({"failed": True, "final_response": "boom"})
        self.plugin._finish_from_result({"interrupted": True, "final_response": "halted"})
        self.assertEqual([r for r in self.reports() if b"state=done" in r], [])

    def test_hook_path_blocked_uses_real_payload_keys(self):
        # pre_approval_request actually carries command/description.
        self.plugin._on_blocked(kind="approval", platform="cli",
                                command="Rebuild the index?", description="Rebuild")
        blocked = [r for r in self.reports() if b"state=blocked" in r]
        self.assertEqual(self.msg_of(blocked[-1]), "Rebuild the index?")
        # on_human_input_request actually carries prompt.
        self.plugin._on_blocked(kind="clarify", platform="cli", prompt="Which region?")
        blocked = [r for r in self.reports() if b"state=blocked" in r]
        self.assertEqual(self.msg_of(blocked[-1]), "Which region?")
        # A long command falls back to its description.
        self.plugin._on_blocked(kind="approval", platform="cli",
                                command="x" * 120, description="Install dependencies")
        blocked = [r for r in self.reports() if b"state=blocked" in r]
        self.assertEqual(self.msg_of(blocked[-1]), "Install dependencies")
        # on_session_end carries no reply text: done stays without a headline.
        self.plugin._on_turn_end(platform="cli")
        done = [r for r in self.reports() if b"state=done" in r]
        self.assertEqual(done[-1], b"\x1b]7501;state=done:app=hermes\x1b\\")

if __name__ == "__main__":
    unittest.main()
