"""Report Hermes status with OSC 7501 so Herdr lists it as an agent.

Herdr's agents list only includes a terminal whose program speaks OSC 7501.
Claude Code does. Hermes did not, so a session in a Herdr pane stayed a shell.

Interactive Hermes runs the turn in the gateway, which has no terminal. Hooks
there cannot reach the pane. The CLI process owns the tty, so this plugin
emits from the CLI's turn and approval calls, and still uses lifecycle hooks
for in-process runs (one-shot, no gateway).
"""

from __future__ import annotations

import base64
import os
import re
import sys
import threading
import unicodedata

_APP = "hermes"
_INTERACTIVE = {"cli", "tui", "desktop"}
_SKIP_ARGV = {"gateway", "serve", "dashboard", "proxy", "cron", "server"}
_KIND = {
    "approval": "permission",
    "sudo": "auth",
    "clarify": "question",
    "permission": "permission",
    "question": "question",
    "auth": "auth",
}
_MSG = {
    "permission": "Waiting for approval",
    "question": "Waiting for an answer",
    "auth": "Waiting to sign in",
}
_WRAP = "_herdr_osc7501"
_last: tuple[str, str] | None = None
_title_lock = threading.RLock()
_active_state = None
_last_title: str | None = None
# Remove complete CSI and OSC/DCS strings before stripping individual controls.
_TERMINAL_ESCAPE = re.compile(
    r"(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]"
    r"|(?:\x1b\]|\x9d|\x1b[P^_]|[\x90\x98\x9e\x9f])[^\x07\x1b\x9c]*(?:\x07|\x1b\\|\x9c|$)"
    r"|\x1b[ -/]*[@-Z\\-_]"
)


def _title_text(title) -> str:
    if not isinstance(title, str):
        return "Hermes"
    text = _TERMINAL_ESCAPE.sub("", title)
    text = "".join(" " if c.isspace() else c for c in text
                   if c.isspace() or unicodedata.category(c) not in {"Cc", "Cf", "Cs"})
    return " ".join(text.split())[:256] or "Hermes"


def _emit_title(title: str) -> None:
    """Caller holds _title_lock; remember only writes the terminal accepted."""
    global _last_title
    if title == _last_title:
        return
    seq = "\x1b]2;" + title + "\x1b\\"
    if os.environ.get("TMUX"):
        seq = "\x1bPtmux;" + seq.replace("\x1b", "\x1b\x1b") + "\x1b\\"
    if _write(seq.encode("utf-8")):
        _last_title = title


def _publish_state(state) -> None:
    """Never query another session or read messages; state is the CLI's exact snapshot."""
    try:
        with _title_lock:
            if state is not _active_state:
                return
            info = getattr(state, "info", {})
            title = info["title"] if isinstance(info, dict) and "title" in info else getattr(state, "title", None)
            _emit_title(_title_text(title))
    except Exception:
        pass  # Display integration must not break a gateway event.


def _bind_title(agent) -> None:
    global _active_state
    try:
        with _title_lock:
            _active_state = agent._state()
            _publish_state(_active_state)
    except Exception:
        pass


def _wrap_connection(mod) -> None:
    cls = getattr(mod, "SessionState", None)
    if cls is None:
        return

    def observe(orig):
        def changed(self, *args, **kwargs):
            result = orig(self, *args, **kwargs)
            _publish_state(self)
            return result
        return changed

    _wrap(cls, "adopt_snapshot", observe)
    _wrap(cls, "apply_event", observe)


def _platform(kwargs: dict) -> str:
    plat = kwargs.get("platform")
    if isinstance(plat, str) and plat.strip():
        return plat.strip().lower()
    env = os.environ.get("HERMES_PLATFORM") or os.environ.get("HERMES_SESSION_PLATFORM") or ""
    return env.strip().lower()


def _interactive(kwargs: dict) -> bool:
    plat = _platform(kwargs)
    return plat in _INTERACTIVE if plat else True


def _foreground_cli() -> bool:
    argv = [os.path.basename(a).lower() for a in sys.argv[1:]]
    if any(a in _SKIP_ARGV for a in argv):
        return False
    try:
        return os.isatty(0) or os.isatty(1)
    except Exception:
        return False


def sequence(state: str, *, kind: str | None = None, msg: str | None = None) -> str:
    """One OSC 7501 report. Values stay inside the spec's unescaped alphabet."""
    parts = [f"state={state}", f"app={_APP}"]
    if state == "blocked" and kind in ("permission", "question", "auth"):
        parts.append(f"kind={kind}")
    if msg:
        encoded = base64.b64encode(msg.encode("utf-8")).decode("ascii")
        if encoded and len(encoded) <= 2732:
            parts.append(f"msg={encoded}")
    seq = "\x1b]7501;" + ":".join(parts) + "\x1b\\"
    if os.environ.get("TMUX"):
        # tmux swallows unknown OSC unless the sequence is passthrough-wrapped.
        seq = "\x1bPtmux;" + seq.replace("\x1b", "\x1b\x1b") + "\x1b\\"
    return seq


def _write(payload: bytes) -> bool:
    try:
        fd = os.open("/dev/tty", os.O_WRONLY | os.O_NOCTTY)
    except OSError:
        fd = -1
    if fd >= 0:
        try:
            os.write(fd, payload)
            return True
        except Exception:
            return False
        finally:
            os.close(fd)
    try:
        out = sys.__stdout__
        if out is not None and out.isatty():
            out.write(payload.decode("utf-8"))
            out.flush()
            return True
    except Exception:
        return False
    return False


def _emit(state: str, *, kind: str | None = None, msg: str | None = None) -> None:
    global _last
    key = (state, kind or "")
    if key == _last:
        return
    if _write(sequence(state, kind=kind, msg=msg).encode("ascii")):
        _last = key


def _force_clear() -> None:
    """Always drop the record. Quit uses os._exit, so this must run on that path."""
    global _last, _active_state
    with _title_lock:
        _active_state = None
        _last = None
        try:
            _emit_title("")
        except Exception:
            pass
        _write(sequence("clear").encode("ascii"))


def _clear() -> None:
    """Drop the status record. idle and done survive process exit unless cleared."""
    if _last is None:
        return
    _force_clear()


def _on_exit() -> None:
    try:
        _clear()
    except Exception:
        return


def _install_exit_clear() -> None:
    import atexit
    import signal

    if getattr(_install_exit_clear, "_done", False):
        return
    atexit.register(_on_exit)

    def _on_hup(signum, _frame):
        _on_exit()
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    try:
        signal.signal(signal.SIGHUP, _on_hup)
    except Exception:
        pass
    _install_exit_clear._done = True


def _report(state: str, kwargs: dict, *, kind: str | None = None, msg: str | None = None) -> None:
    try:
        if _interactive(kwargs):
            _emit(state, kind=kind, msg=msg)
    except Exception:
        return


def _on_idle(**kwargs) -> None:
    _report("idle", kwargs)


def _on_working(**kwargs) -> None:
    _report("working", kwargs)


def _on_turn_end(**kwargs) -> None:
    if kwargs.get("interrupted"):
        _report("idle", kwargs)
    elif kwargs.get("failed"):
        _report("error", kwargs)
    else:
        _report("done", kwargs)


def _on_blocked(**kwargs) -> None:
    kind = _KIND.get(str(kwargs.get("kind") or "permission"), "permission")
    _report("blocked", kwargs, kind=kind, msg=_MSG.get(kind))


def _finish_from_result(result) -> None:
    if not isinstance(result, dict):
        _emit("done")
        return
    if result.get("interrupted"):
        _emit("idle")
    elif result.get("failed"):
        _emit("error")
    elif result.get("admitted") is False:
        _emit("idle")
    else:
        _emit("done")


def _wrap(obj, name: str, factory) -> None:
    current = getattr(obj, name, None)
    if current is None or getattr(current, _WRAP, False):
        return
    wrapped = factory(current)
    setattr(wrapped, _WRAP, True)
    setattr(obj, name, wrapped)


def _wrap_gateway(mod) -> None:
    cls = getattr(mod, "GatewayAgent", None)
    if cls is None:
        return

    # Hermes repoints this property on new/resume/branch, including at construction.
    prop = getattr(cls, "session_id", None)
    if isinstance(prop, property) and prop.fset and not getattr(prop.fset, _WRAP, False):
        setter = prop.fset

        def select(self, value):
            global _active_state
            # Do not hold the lock across the setter: it can wait for a gateway
            # snapshot delivered by another thread running our state observer.
            with _title_lock:
                _active_state = None
            result = setter(self, value)
            _bind_title(self)
            return result

        setattr(select, _WRAP, True)
        setattr(cls, "session_id", property(prop.fget, select, prop.fdel, prop.__doc__))

    def factory(orig):
        def run_conversation(self, *args, **kwargs):
            _bind_title(self)
            _emit("working")
            try:
                result = orig(self, *args, **kwargs)
            except Exception:
                _emit("error")
                raise
            _finish_from_result(result)
            return result
        return run_conversation

    _wrap(cls, "run_conversation", factory)


def _wrap_modals(mod) -> None:
    cls = None
    for value in vars(mod).values():
        if isinstance(value, type) and hasattr(value, "_approval_callback"):
            cls = value
            break
    if cls is None:
        return

    def blocking(kind):
        def factory(orig):
            def method(self, *args, **kwargs):
                _emit("blocked", kind=kind, msg=_MSG.get(kind))
                try:
                    return orig(self, *args, **kwargs)
                finally:
                    _emit("working")
            return method
        return factory

    _wrap(cls, "_approval_callback", blocking("permission"))
    _wrap(cls, "_clarify_callback", blocking("question"))
    _wrap(cls, "_sudo_password_callback", blocking("auth"))


def _install_cli_wrap() -> None:
    """Patch the CLI classes once they import. Hooks never see a gateway turn."""
    import builtins

    if getattr(builtins, "_herdr_osc7501_hook", False):
        _patch_loaded()
        return
    orig = builtins.__import__

    def hooked(name, globals=None, locals=None, fromlist=(), level=0):
        mod = orig(name, globals, locals, fromlist, level)
        # __import__('hermes_cli.gateway_agent') may return the package. Look
        # up completed modules by their actual names for every import form.
        _patch_loaded()
        return mod

    builtins.__import__ = hooked
    builtins._herdr_osc7501_hook = True
    _patch_loaded()


def _wrap_cli_exit(mod) -> None:
    """Quit calls these, then os._exit, which skips atexit."""
    if hasattr(mod, "_run_cleanup"):
        def cleanup_factory(orig):
            def _run_cleanup(*args, **kwargs):
                _force_clear()
                return orig(*args, **kwargs)
            return _run_cleanup
        _wrap(mod, "_run_cleanup", cleanup_factory)
    cls = getattr(mod, "HermesCLI", None)
    if cls is None:
        for value in vars(mod).values():
            if isinstance(value, type) and hasattr(value, "_print_exit_summary"):
                cls = value
                break
    if cls is None:
        return

    def summary_factory(orig):
        def _print_exit_summary(self, *args, **kwargs):
            try:
                return orig(self, *args, **kwargs)
            finally:
                _force_clear()
        return _print_exit_summary
    _wrap(cls, "_print_exit_summary", summary_factory)


def _patch_loaded() -> None:
    conn = sys.modules.get("hermes_cli.gateway_connection")
    if conn is not None:
        _wrap_connection(conn)
    gw = sys.modules.get("hermes_cli.gateway_agent")
    if gw is not None:
        _wrap_gateway(gw)
    modal = sys.modules.get("hermes_cli.cli_modal_mixin")
    if modal is not None:
        _wrap_modals(modal)
    for key in ("cli", "hermes_cli.cli_session_mixin"):
        mod = sys.modules.get(key)
        if mod is not None:
            _wrap_cli_exit(mod)


def register(ctx) -> None:
    ctx.register_hook("on_session_start", _on_idle)
    ctx.register_hook("on_session_reset", _on_idle)
    ctx.register_hook("pre_llm_call", _on_working)
    ctx.register_hook("pre_approval_request", _on_blocked)
    ctx.register_hook("on_human_input_request", _on_blocked)
    ctx.register_hook("post_approval_response", _on_working)
    ctx.register_hook("on_human_input_resolved", _on_working)
    ctx.register_hook("on_session_end", _on_turn_end)
    ctx.register_hook("agent_loop_stopped", _on_idle)
    if _interactive({}) and _foreground_cli():
        _install_exit_clear()
        _install_cli_wrap()
        _emit("idle")
