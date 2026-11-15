# Withdrawn Herdr Hermes subagent integration

Status: withdrawn at Chris's request. The implementation was rejected after live testing. Do not redeploy this architecture without a new design approval.

## Scope and retained functionality

The experiment projected Hermes in-process subagents into the Herdr Agents sidebar. The rollback removes only the subagent roster, indented virtual rows and click-tail additions. Existing OSC 7501 status, OSC 2 titles, vitals, footer suppression, recent sessions, pane headers, pinning and the personal Hermes layout are retained.

Repositories:
- Producer: /home/chris/Projects/herdr-osc7501, branch vitals-sidecar.
- Consumer: /home/chris/Projects/herdr-mods/.worktrees/recent-hermes-sessions, branch feat/recent-hermes-sessions.
- Plan retained for history: docs/superpowers/plans/2026-11-15-herdr-subagent-rows.md in the producer repository.

Restore targets: producer runtime files from 49ef62e (plugin 1.3.0); consumer runtime files from c97b849 (existing pane-header feature included). No Hermes core changes were made.

## User requirements explored

Live Hermes children launched via delegate_task or the public lifecycle API were to appear indented under their parent session in Active/Idle groups. Clicking a child would inspect its current activity. Completed children were to disappear immediately. Native hc terminal trees, grouping, folding and pin ordering were to remain intact.

## Alternatives considered

1. Filesystem sidecar projection with virtual sidebar rows. Chosen for the experiment because native Hermes children execute without their own PTY.
2. Full Hermes child processes under hc run --bg, using named templates and native Herdr parent/child terminals. This is a separate workflow and was not implemented here.
3. Parent-row summary text only. Considered, not implemented.
4. Replacing Hermes's internal child spawner through a delegation-provider plugin. Documentation restricts these plugins to route/model configuration; this was rejected as an unsupported extension point.

The repositories remained separate because the Hermes plugin requires a root plugin.yaml whereas Herdr mods use per-mod folders and scripts/deploy.sh.

## Implemented producer

The plugin sampled the CLI's existing GatewaySessionView or LocalSubagents adapter through the already-loaded hermes_cli.gateway_tools module. Looking up sys.modules avoided recursive import-hook activation encountered during a live check.

Sampling piggybacked the vitals heartbeat, gated by HC_TERMINAL_ID. It wrote atomic JSON files under ~/.config/herdr-app/data/hermes-subagents/. Diagnostic files recorded source/write failures. Empty rosters and exit cleanup removed the owned roster.

Roster v1:

    {"v":1,"term":"t7","ts":0,"children":[{"id":"sa-...","task":"goal first line","state":"running","activity":"terminal","age_s":12}]}

Task text was sanitized and capped at 120 characters. State, activity and elapsed values came from the existing registry adapter. The implementation attempted throttled and deduplicated writes; review found timestamp inclusion defeated semantic deduplication.

Click request:

    {"v":1,"child":"sa-...","ts":0}

The final producer addition read its own .click.json at most once per second while a roster existed, validated ownership against that roster, deduplicated child/timestamp pairs and called subagent_tail(child, fetch=True). Replies were atomic .tail.json records with v, term, child, ts, request_ts and lines. Output was limited to the last eight sanitized lines, each capped at 240 characters, with a bounded input slice. request_ts correlated the reply with the popup request. Failures left the ordinary metadata popup usable.

## Implemented consumer

mods/agents-hermes/main.js merged virtual rows into the existing native tree. Rows used connectors and status indicators and followed their parent in grouping/folding, without entering terminal pin ordering. A virtual row opened an agents-hermes popup instead of focusing a nonexistent terminal.

Subsequent uncommitted fixes added the missing popup render branch, compare-and-swap replacement of click requests, unique click timestamps, exact request/terminal correlation, asynchronous tail loading, initial roster restoration and root-watch batch rescanning. Those uncommitted changes are preserved in the rollback patch archive. Watcher recovery, deeper virtual parentage and expiry still needed work.

## Commit inventory

Producer:
- fc976a9: initial design plan.
- 76ce375: expanded implementation plan.
- 696820f: roster sidecar and tests.
- 1b040e2: README contract/version prose.
- 5bed988: manifest version 1.4.0.
- c8d83d4: sys.modules adapter lookup and diagnostics.
- b678473: write-path diagnostics.
- 0bee4bd: bounded on-demand transcript tails.

Consumer:
- 1133e18: virtual subagent rows and initial popup.
- Additional click and watcher fixes remained uncommitted at withdrawal.

The producer additions had been pushed to origin/vitals-sidecar and installed. The consumer push failed for lack of an upstream; the named feature branch was absent from origin when rollback began. No history rewriting is required.

## Verification actually performed

- Initial producer roster suite and Plugin Doctor passed.
- Live hc scratch sessions produced real roster files during delegate execution and removed them after completion.
- Screenshots sidebar-keep-live.png and sidebar-keep-after.png showed the indented child and its later removal, respectively.
- Scratch terminals without a Herdr pane did not appear as top-level agents. terminal.keep made the parent visible, after which the child row appeared.
- Producer suite after click-tail work: 65 tests passed; Plugin Doctor passed.
- Consumer suite including initial restoration/root batch test: 70 tests passed in the review run. Herdr check passed with a display-authorization warning; app status reported no errors.
- Actual desktop click on the child of sa-tail-check (t3x) opened an agents-hermes overlay. Reading the exact t3x click and tail files verified matching child sa-0-147102da and request_ts 1794783716.185, with eight transcript lines. The app reported errors: [].
- Repeated-click semantics were unit tested. No second successful real desktop click was recorded before withdrawal.
- A real public-lifecycle idle-parent end-to-end test was not performed.

Evidence images remain under /home/chris/.hermes/cache/scratch/, including tail-popup-live.png and sidebar-keep-live.png. Scratch files are temporary and may be pruned. They are not committed to the public repositories.

## Independent review findings at withdrawal

These findings were returned by the reviewer. They were not all independently reproduced by the parent before Chris cancelled the implementation:

1. LocalSubagents can include waiting_to_resume entries, so blindly projecting every adapter row violates live-only requirements.
2. Idle public-lifecycle children need a discovery trigger; the gateway view's busy/watch/delegation gate can otherwise suppress polling.
3. A watchFolder rejection exits the entire watch loop permanently; directory creation and retry recovery require coverage. Initial scan/watch handoff can also miss an event.
4. parent_id is discarded, flattening virtual descendants into terminal-level leaves.
5. Five-second tail freshness is checked only during file loads; displayed text can remain beyond the expiry without a further event.
6. Roster comparisons include a fresh ts, preventing intended deduplication.
7. Explicit CLI cleanup clears OSC state but sidecar cleanup occurs on atexit; hard-exit paths and in-flight publication need protection.
8. TMUX plus HC_TERMINAL_ID still passes the gate, conflicting with the plan's broad tmux exclusion wording.

These gaps are recorded for any future redesign. No further feature work was authorized after withdrawal.

## Rollback approach

Preserve this record, the original plan and full source diffs first. Restore producer __init__.py, README.md and plugin.yaml from 49ef62e; remove the added test_subagents.py. Restore consumer main.js and README.md from c97b849 and remove test_agents_roster.mjs. Preserve existing unrelated changes and commit forward rollback changes rather than reset history. Reinstall the exact prior plugin revision and deploy the prior mod through scripts/deploy.sh. Clean only experiment-owned scratch terminals and sidecar files. Run both remaining suites and Plugin Doctor, read back installed source and deployed state, and record results below.

Pre-rollback full patches (private local archive):
- /home/chris/.hermes/cache/scratch/herdr-subagent-rollback/producer.patch
- /home/chris/.hermes/cache/scratch/herdr-subagent-rollback/consumer.patch

## Running-session limitation

Existing Hermes processes retain the Python plugin code loaded at launch. Reinstalling the prior plugin restores new-session behavior. Reverting the sidebar removes the visible experimental interface immediately. Existing user Hermes sessions will not be restarted by Winston. Any already-loaded writer can continue producing unused sidecars until Chris closes/relaunches that session. The rollback must report this limitation explicitly.

## Rollback results

- Restored producer runtime files byte-for-byte from 49ef62e5df392ad4388c85be270c40bf109f0b1d, including plugin version 1.3.0.
- Restored consumer runtime files byte-for-byte from c97b849; preserved the pane header, recent sessions and vitals work.
- Removed the experiment-specific producer and consumer test files.
- Installed immutable prior plugin revision 49ef62e5df392ad4388c85be270c40bf109f0b1d through the Hermes plugin installer. The installer reloaded gateway hooks. No Hermes process was restarted.
- Compared installed plugin source and deployed sidebar source directly against Git's prior revision bytes: exact matches.
- Producer: 47 tests passed, Plugin Doctor passed with version 1.3.0.
- Consumer: 60 tests passed, all deployed mod checks passed; app status errors: [].
- Ended and removed only scratch terminals t3w (sa-live-rows) and t3x (sa-tail-check), then verified both absent from hc's full terminal list.
- Removed leftover experiment diagnostics/sidecars, including .diag-t3v.json, .diag-t3w.json and .diag-t3x.json. Existing user sessions were left running.
- Original implementation plan remains as historical documentation, marked withdrawn. Source patches are embedded below so the implementation survives scratch-cache pruning.
- The producer branch is updated by a forward rollback commit. The consumer rollback is committed locally; its feature branch has no upstream and was never published, so no new remote branch is created.

## Preserved producer implementation diff

<details>
<summary>Full withdrawn source changes, including uncommitted work</summary>

```diff
diff --git a/README.md b/README.md
index fa575be..920acc5 100644
--- a/README.md
+++ b/README.md
@@ -109,3 +109,19 @@ When Hermes runs inside an hc terminal (`$HC_TERMINAL_ID` set, address like
 `prompt_elapsed`, `state`. Writes are atomic, throttled to 500 ms, deduped,
 and fail-open; the file is removed on exit. Bare-terminal and tmux Hermes
 never write vitals. Herdr mods read the directory; the file is the contract.
+
+## Subagent roster sidecar (1.4.0)
+
+One JSON file per Herdr terminal under `~/.config/herdr-app/data/hermes-subagents/`, named by
+`$HC_TERMINAL_ID` — the same gate as vitals (bare-terminal and tmux Hermes write nothing). It lists only
+the session's **live** children (delegate_task batch, `/review`, the public lifecycle API — all one live
+registry); an empty roster **removes** the file, so Herdr mods show sub rows only while children are
+alive. Source: the same registry backend the CLI monitor and dock consult (the gateway session's view
+when its children run there, else this process's own registry). Sampling runs on the vitals heartbeat;
+the registry source's own ≤1 rps poll governs RPCs, and writes happen only when the roster changed.
+
+`{"v": 1, "term": "t1q", "ts": 0, "children": [{"id": "sa-3-9f2c", "task": "Review for regressions",
+"state": "running", "activity": "web_search", "age_s": 12}]}` — `task` is the goal's sanitized first
+line (120-char cap); `state`, `activity` and `age_s` carry exactly what the registry knows per child,
+no invented granularity. Atomic, deduped, fail-open, removed on exit; the plugin's only reader is the
+Herdr agents mod.
diff --git a/__init__.py b/__init__.py
index cf7d4d4..a16d494 100644
--- a/__init__.py
+++ b/__init__.py
@@ -389,6 +389,11 @@ def _vitals_heartbeat() -> None:
                      if k in _vitals_orig_snapshot), None)
                 if build is not None:
                     _vitals_sample(cli, snapshot=build(cli))
+                try:
+                    _subagents_sample()
+                    _subagents_click_sample()
+                except Exception:
+                    pass
             except Exception:
                 pass

@@ -397,6 +402,220 @@ def _vitals_heartbeat() -> None:
     _vitals_thread = t


+# --- Subagent roster sidecar (contract v1) ----------------------------------
+# One JSON file per hc terminal under ~/.config/herdr-app/data/hermes-subagents/,
+# named by $HC_TERMINAL_ID, holding only the LIVE children (active-only rule:
+# an empty roster removes the file). Source: the same registry backend the CLI
+# monitor and dock consult — the gateway session view when its children run
+# there, else this process's own registry. Gated (same rule as vitals),
+# throttled, fail-open: nothing here may ever break a turn.
+_SUBAGENTS_MIN_INTERVAL = 0.5
+_subagents_dir_override: str | None = None
+_subagents_last_write = 0.0
+_subagents_last_payload: dict | None = None
+_subagents_own_path: str | None = None
+_subagents_diag_written: str | None = None
+_subagents_live_source = None
+_subagents_click_last_poll = 0.0
+_subagents_click_seen = None
+_subagents_click_lock = threading.Lock()
+
+
+def _subagents_dir() -> str:
+    if _subagents_dir_override is not None:
+        return _subagents_dir_override
+    base = os.environ.get("HERDR_APP_HOME") or os.path.expanduser("~/.config/herdr-app")
+    return os.path.join(base, "data", "hermes-subagents")
+
+
+def _subagents_source():
+    """The registry backend (view or in-process); None when unresolvable. Test seam.
+    Architecture rule: the plugin never imports hermes_cli modules at call time
+    (a function-local import from inside the plugin fires the plugin's own
+    import hook) — resolve from sys.modules the way the import hook does."""
+    gt = sys.modules.get("hermes_cli.gateway_tools")
+    if gt is None:
+        return None
+    view = gt.process_view()
+    if view is not None:
+        return view
+    if _active_cli is not None:
+        return gt.LocalSubagents(_active_cli)
+    return None
+
+
+def _subagents_diag(reason: str) -> None:
+    """One line of truth per failure reason, written once; never raises."""
+    global _subagents_diag_written
+    if _subagents_diag_written == reason:
+        return
+    _subagents_diag_written = reason
+    try:
+        path = os.path.join(_subagents_dir(), f".diag-{os.environ['HC_TERMINAL_ID']}.json")
+        with open(path, "w", encoding="utf-8") as fh:
+            json.dump({"err": reason, "ts": time.time()}, fh)
+    except Exception:
+        pass
+
+
+def _roster_child(row: dict) -> dict:
+    age = row.get("running_seconds")
+    if not isinstance(age, (int, float)):
+        started = row.get("started_at")
+        age = (time.time() - started) if isinstance(started, (int, float)) else None
+    return {
+        "id": row.get("subagent_id"),
+        "task": _message_text(row.get("goal")),
+        "state": row.get("status"),
+        "activity": row.get("last_tool") or None,
+        "age_s": int(age) if isinstance(age, (int, float)) else None,
+    }
+
+
+def _subagents_write(path: str, payload: dict) -> None:
+    directory = os.path.dirname(path)
+    os.makedirs(directory, exist_ok=True)
+    tmp = f"{path}.{os.getpid()}.tmp"
+    with open(tmp, "w", encoding="utf-8") as fh:
+        json.dump(payload, fh)
+    os.replace(tmp, path)
+
+
+def _subagents_sample() -> str | None:
+    global _subagents_last_write, _subagents_last_payload, _subagents_own_path
+    global _subagents_live_source
+    if not _vitals_enabled():
+        return None
+    now = time.monotonic()
+    if _subagents_last_payload is not None and now - _subagents_last_write < _SUBAGENTS_MIN_INTERVAL:
+        return None
+    source = _subagents_source()
+    if source is None:
+        _subagents_diag("no-source")
+        return None
+    try:
+        rows = source.subagent_rows(busy=bool(getattr(_active_cli, "_agent_running", False)))
+    except Exception as exc:
+        _subagents_diag(repr(exc))
+        return None
+    children = [_roster_child(r) for r in (rows or []) if isinstance(r, dict)]
+    _subagents_live_source = source  # LocalSubagents keeps transcript paths from this read.
+    path = os.path.join(_subagents_dir(), f"{os.environ['HC_TERMINAL_ID']}.json")
+    payload = {"v": 1, "term": os.environ["HC_TERMINAL_ID"], "ts": time.time(),
+               "children": children}
+    if not children:
+        _subagents_cleanup()
+        # active-only rule: an empty roster removes the file; never write an empty one
+        if _subagents_last_payload is not None and _subagents_last_payload.get("children"):
+            try:
+                os.unlink(path)
+            except OSError:
+                pass
+        elif _subagents_last_payload is None and os.path.exists(path):
+            os.unlink(path)  # ours: the gate means one process per terminal address
+        _subagents_last_write = now
+        _subagents_last_payload = payload
+        _subagents_own_path = None
+        return None
+    if _subagents_last_payload is not None and payload == _subagents_last_payload:
+        return None
+    try:
+        _subagents_write(path, payload)
+    except Exception as exc:
+        _subagents_diag(repr(exc))
+        return None
+    _subagents_last_write = now
+    _subagents_last_payload = payload
+    _subagents_own_path = path
+    return path
+
+
+def _subagents_click_sample() -> str | None:
+    """One bounded tail per new click, at most once a second while live.
+
+    Runs on the existing heartbeat. request_ts correlates the asynchronous
+    reply so a popup cannot consume an earlier click's transcript.
+    """
+    global _subagents_click_last_poll, _subagents_click_seen
+    if not _vitals_enabled() or not _subagents_own_path:
+        return None
+    if not _subagents_click_lock.acquire(blocking=False):
+        return None
+    try:
+        now = time.monotonic()
+        if now - _subagents_click_last_poll < 1:
+            return None
+        if not os.path.isfile(_subagents_own_path):
+            return None
+        _subagents_click_last_poll = now
+        term = os.environ["HC_TERMINAL_ID"]
+        base = os.path.join(_subagents_dir(), term)
+        with open(base + ".click.json", encoding="utf-8") as fh:
+            click = json.loads(fh.read(4096))
+        if not isinstance(click, dict) or click.get("v") != 1:
+            return None
+        child, ts = click.get("child"), click.get("ts")
+        if (not isinstance(child, str) or not isinstance(ts, (int, float))
+                or isinstance(ts, bool) or not 0 <= time.time() - ts <= 10):
+            return None
+        key = (child, ts)
+        if key == _subagents_click_seen:
+            return None
+        if child not in {c["id"] for c in (_subagents_last_payload or {}).get("children", [])}:
+            return None
+        _subagents_click_seen = key  # failures are deduped and rate-limited too
+        source = _subagents_live_source
+        if source is None:
+            return None
+        text = source.subagent_tail(child, fetch=True)
+        if not isinstance(text, str):
+            return None
+        lines = [_message_text(line, limit=240) for line in text[-16384:].splitlines()]
+        lines = [line for line in lines if line][-8:]
+        # A concurrent empty-roster update must never resurrect a tail.
+        if not _subagents_own_path or not os.path.isfile(_subagents_own_path):
+            return None
+        path = base + ".tail.json"
+        _subagents_write(path, {"v": 1, "term": term, "child": child,
+                                "ts": time.time(), "request_ts": ts, "lines": lines})
+        return path
+    except Exception:
+        return None
+    finally:
+        _subagents_click_lock.release()
+
+
+def _subagents_cleanup() -> None:
+    """Remove only this terminal's roster and click/tail files; never raises."""
+    global _subagents_own_path, _subagents_click_seen
+    path, _subagents_own_path = _subagents_own_path, None
+    _subagents_click_seen = None
+    paths = [path] if path else []
+    if _vitals_enabled():
+        base = os.path.join(_subagents_dir(), os.environ["HC_TERMINAL_ID"])
+        paths.extend([base + ".click.json", base + ".tail.json"])
+    for path in paths:
+        try:
+            os.unlink(path)
+        except Exception:
+            pass
+
+
+def _subagents_reset_for_tests(dirpath=None) -> None:
+    """Fresh module state, optional directory override; tests only."""
+    global _subagents_dir_override, _subagents_last_write, _subagents_last_payload
+    global _subagents_own_path, _subagents_diag_written
+    global _subagents_live_source, _subagents_click_last_poll, _subagents_click_seen
+    _subagents_dir_override = str(dirpath) if dirpath is not None else None
+    _subagents_last_write = 0.0
+    _subagents_last_payload = None
+    _subagents_own_path = None
+    _subagents_diag_written = None
+    _subagents_live_source = None
+    _subagents_click_last_poll = 0.0
+    _subagents_click_seen = None
+
+
 def _suppress_status_bar_window(cli_mod) -> None:
     """Phase 3b: collapse the footer WINDOW under Herdr. Empty fragments
     still occupy a row; ``_status_bar_visible = False`` removes the
@@ -551,6 +770,7 @@ def _on_exit() -> None:
         return
     finally:
         _vitals_cleanup()
+        _subagents_cleanup()


 def _install_exit_clear() -> None:
diff --git a/docs/superpowers/plans/2026-11-15-herdr-subagent-rows.md b/docs/superpowers/plans/2026-11-15-herdr-subagent-rows.md
new file mode 100644
index 0000000..ec40a64
--- /dev/null
+++ b/docs/superpowers/plans/2026-11-15-herdr-subagent-rows.md
@@ -0,0 +1,256 @@
+# Hermes sub-agent sidebar rows in Herdr (live-only)
+
+Date: 2026-11-15. Status: approved 2026-11-15 — building. Spans two repos:
+this one (plugin = data producer) and `christopher-s/herdr-mods`
+(agents-hermes clone = renderer). Supersedes the 2026-11-14 decision that
+kept in-process delegate children off the sidebar (the active-only rule is
+what keeps it un-cluttered). Written KISS-first.
+
+## Goal
+
+When a Hermes session running inside Herdr starts delegated agents
+(`delegate_task`, batch, `/review`, and the public lifecycle API — all feed
+one live registry), show each **live** child as an indented row under its
+parent session row in the agents sidebar (Active/Idle groups), named after
+the child's task, clickable to see what it is doing. When a child finishes,
+its row disappears: rows exist only while the child is in the live registry.
+
+## Why this shape (and not the others)
+
+- **Chosen: projection lane.** Keep Hermes launches as they are. The plugin
+  projects the live registry to Herdr over the established sidecar-file
+  channel; the personal agents-hermes clone merges the rows. No Hermes core
+  change, no new processes, no templates needed (that lane stays paused).
+- **Alternative kept, paused: native hc-launch lane** (`hc run --bg` +
+  templates, see the paused 2026-11-14 plan). Native nesting/peek/steer for
+  zero code, but only children started through hc participate, and each child
+  is a full process. Revisit if interactive steerable children matter.
+- **Rejected for this lane: Hermes core change** to spawn delegate_task
+  through hc. Docs confirm no plugin seam for the spawn mechanism (delegation
+  providers answer "which route" only; core keeps spawning). Parked.
+
+## Verified building blocks (2026-11-15)
+
+- Live registry feed: `hermes_cli/gateway_tools.py` — the CLI monitor's view;
+  `subagent_rows()` asks the gateway `subagent.list` **at most once a
+  second**, only while busy / children listed last time / watch window open /
+  active delegations; rows expire after ~1 minute without an answer
+  (`_RETAIN_SECONDS`). `LocalSubagents` answers the same `subagent_*` calls
+  when the CLI runs its agent in-process. Roster rows carry id, state,
+  current activity, elapsed (what the CLI dock and Desktop frame render).
+- Sidecar channel: `~/.config/herdr-app/data/<name>/<HC_TERMINAL_ID>.json` —
+  the vitals contract pattern: gated on `$HC_TERMINAL_ID`, atomic tmp+rename,
+  ≤500 ms throttle, deduped by value, fail-open, removed on exit.
+- Renderer: agents-hermes (herdr-mods, `feat/recent-hermes-sessions` branch)
+  — fixed Sessions/Active/Idle grouping + tree rendering exist; `watchFolder`
+  drives all data reads (vitals-mod pattern, no polling timers).
+- Hermes's own monitors define the model and retention we mirror: rows live
+  while the live registry holds them; the dock drops children when they leave
+  the registry; the durable record is the completion message in the
+  conversation. `subagent.tail` is the documented live-tail seam (bounded
+  recent excerpt), and the same `subagent_*` seam already answers per-child
+  actions — those become the future Steer/Stop path.
+
+## Architecture (contract v1)
+
+```
+delegate registry (gateway or in-process LocalSubagents)
+        |  subagent.list  (≤1 rps, gated by existing view)
+        v
+CLI process (has $HC_TERMINAL_ID)
+  herdr-osc7501 plugin: on change, write
+  data/hermes-subagents/<address>.json
+  (atomic, ≤500 ms throttle, deduped, fail-open,
+   removed when roster empty or on exit)
+        |  watchFolder event
+        v
+agents-hermes: merge indented rows under the parent
+  row matching <address>; file present = show;
+  entry gone = row gone (ACTIVE-ONLY RULE)
+        |  click -> <address>.click.json
+        v
+plugin polls its own dir ≤1 s while the roster
+file exists; one fetch per new click entry via
+subagent.tail (≤1 rps); writes <address>.tail.json
+```
+
+Sidecar file v1 (one per Hermes terminal; array of live children):
+
+```json
+{"v": 1, "term": "t1q", "ts": 0, "children": [
+  {"id": "sa-3-9f2c", "task": "Review for regressions",
+   "state": "running", "activity": "in web_search", "age_s": 12}
+]}
+```
+
+Click file (written by the mod, read by the plugin; one entry at a time):
+
+```json
+{"v": 1, "child": "sa-3-9f2c", "ts": 0}
+```
+
+Tail file v1 (written by the plugin, read by the mod popup):
+
+```json
+{"v": 1, "term": "t1q", "child": "sa-3-9f2c", "ts": 0,
+ "lines": ["…bounded recent excerpt, per Hermes tail semantics…"]}
+```
+
+- Empty roster → remove the file (rows disappear; the sidebar stays honest).
+- Child rows render only under their parent Hermes row; they do not count
+  against the 20-entry group limit and do not enter pinned agent ordering
+  (they ride their parent).
+- Row status dot: any live child = working dot; that is all the roster
+  honestly gives per child (state/activity/age strings are shown, not
+  invented).
+- Row staleness dim: file older than ~60 s (matches registry retention), not
+  content timestamp — writes are change-driven, so a quiet-but-live child's
+  row legitimately holds.
+- Click popup: roster fields at a glance; expands with the tail file's lines
+  when fresh (≤5 s).
+
+## Performance shape
+
+- No new timers in the plugin for the roster: sampling piggybacks the
+  existing status-event path + vitals heartbeat; the registry view's own
+  ≤1 rps gate already holds the RPC; sidecar writes happen only when roster
+  content changed (dedupe).
+- The plugin's only new poll (click-file, Task 3) runs ≤1 s **only while the
+  roster file exists** — zero steady-state cost for idle sessions.
+- Mod side stays event-driven: `watchFolder` on the directory, repaint on
+  change; no added polling.
+- Bare-terminal and tmux Hermes: gated off entirely (no `$HC_TERMINAL_ID` →
+  no file → no rows), same rule as vitals.
+- Cold cost: one small JSON read per terminal on the first event; steady
+  state only when rosters actually change.
+
+## Global constraints
+
+- Preserve all existing OSC 7501/OSC 2/vitals behaviour untouched; new
+  surfaces are additive.
+- Plugin import of `hermes_cli.gateway_tools` is a guarded private CLI seam
+  (same rule as the existing hooks): guard every access, fail open, rerun
+  the tests after Hermes upgrades.
+- All new plugin I/O guarded, throttled, deduped, fail-open: nothing here
+  may ever break a turn. Sanitize task names through the existing one-line
+  sanitizer with caps; no secrets in contract files.
+- Gate-off paths must write nothing: no env var, bare terminal, tmux, or the
+  gateway/serve entrypoints the plugin already skips.
+- agents-hermes is edited in the herdr-mods repo on the
+  `feat/recent-hermes-sessions` branch (its source of truth) and deployed
+  via `scripts/deploy.sh` + `herdr-app check`; never edit deployed copies in
+  place; never touch shipped mods.
+- Publish per herdr-desktop-operations: `hermes plugins install
+  christopher-s/herdr-osc7501 --force --enable --yes-deps`, verify
+  origin/revision, `hermes plugins doctor . --ci`. Never restart Hermes
+  (Chris does); running CLIs keep their loaded plugin — new terminals pick
+  up new code.
+- Live checks act only on scratch-owned, distinctly named terminals created
+  by our own launch calls (two user tabs were once lost to focus-read
+  assumptions).
+
+## Phases (each independently shippable and reversible)
+
+1. **Emit only.** Plugin writes the roster sidecar; Hermes UI unchanged.
+   Verifiable by `cat` while you work.
+2. **Render.** agents-hermes merges indented active-only rows + click popup
+   from roster fields.
+3. **Tail on click.** Click-file round-trip → `subagent.tail` fetch →
+   popup shows the bounded live tail. (Steer/Stop via the same seam stays a
+   listed follow-on, unbuilt.)
+4. **Polish.** READMEs, winston-skills reference + ledger row, final gates.
+
+## Task 1: Emit the roster sidecar (phase 1 — this repo)
+
+**Files:** Modify `__init__.py`, `plugin.yaml` (version 1.4.0, description),
+`README.md` (contract section); add `tests/test_subagents.py`.
+
+**Interfaces:** Consumes `os.environ["HC_TERMINAL_ID"]`, the running CLI's
+gateway_tools view (`subagent_rows()`; `LocalSubagents` when in-process), and
+the existing vitals machinery (atomic write, throttle, dedupe, cleanup,
+sanitizers). Produces `~/.config/herdr-app/data/hermes-subagents/<address>.json`
+(v1 contract above).
+
+- [ ] Tests first: no-env-var → no file; roster→file field mapping verbatim
+      (id/task/state/activity/age); sanitized one-line task capped like msg;
+      changed roster bypasses throttle; unchanged → no write; empty roster →
+      unlink own file; exit removes own file; unresolvable view → fail open
+      silently.
+- [ ] Implement roster sampling on the existing status-event path +
+      heartbeat; single-file-per-terminal contract; reuse vitals dir rules.
+- [ ] Green suite (`python -m unittest discover -s tests -v`) +
+      `hermes plugins doctor . --ci`; commit on branch.
+- [ ] Live check under hc: run a real delegate in a scratch-owned named
+      terminal, `cat` the file, verify fields track the CLI's own dock rows.
+- [ ] README section + version bump; push.
+
+## Task 2: Render merged rows (phase 2 — herdr-mods repo)
+
+**Files:** `mods/agents-hermes/` on `feat/recent-hermes-sessions` (main.js +
+tests per repo convention); `README.md` contents line.
+
+**Interfaces:** Consumes the roster/click/tail JSON files by parent terminal
+address via `watchFolder`; existing tree rendering, grouping, theme, popup
+mechanisms. Produces indented active-only child rows + click popup.
+
+- [ ] Node tests for a pure state module first: watch-dir map; merge keyed
+      by parent address; entry gone → row gone; empty/absent file → no rows;
+      children never count against the 20-cap and never enter pinned order;
+      dim only past ~60 s file age.
+- [ ] Implement rendering: reuse the existing tree row shape (connector
+      rails, indent), working dot, task name, click handler writing the
+      click file; popup shows roster fields, tail lines when the tail file
+      is fresh.
+- [ ] `herdr-app check` green; deploy via `scripts/deploy.sh`;
+      `herdr-app status` shows `errors: []`; `herdr-app shot` verified with
+      a real running delegate.
+- [ ] Commit on `feat/recent-hermes-sessions`; push.
+
+## Task 3: Tail on click (phase 3 — this repo + mod)
+
+**Files:** `__init__.py` (click-file poll + tail fetch + tail writer),
+`tests/test_subagents.py` additions; mod popup tail section + Node tests.
+
+**Interfaces:** Consumes the click file (mod-written), the existing
+`subagent.tail` seam via the same guarded CLI view (≤1 rps), and Hermes's
+bounded-tail semantics. Produces `<address>.tail.json` (v1 above).
+
+- [ ] Plugin tests first: parse own click file; one fetch per new (child,
+      ts) entry; ≤1 rps; roster-empty → no poll, no tail file; unlink own
+      tail file with cleanup; tail fetch failure → popup still shows roster
+      fields (fail open).
+- [ ] Mod tests: fresh tail file (≤5 s) renders lines; stale/absent shows
+      roster fields only.
+- [ ] Implement the ≤1 s dir poll gated on roster-file existence; reuse the
+      atomic writer.
+- [ ] Both suites green + doctor; deploy; live verify click→tail on the same
+      scratch terminal; commit + push both repos.
+
+## Task 4: Polish and integration (phase 4)
+
+- [ ] READMEs: osc7501 gets the subagents contract section (roster/click/
+      tail files, gates, caps); herdr-mods README gains the agents-hermes
+      contents line with this feature.
+- [ ] winston-skills `herdr-desktop.md`: contract lines + ledger row once
+      live-verified; mark the 2026-11-14 paused plan's relation (sidebar
+      decision superseded; templates lane still paused).
+- [ ] Full gates on both repos green; publish install per skill; verify
+      revision; live proof on a scratch-owned terminal; then Chris decides
+      when real terminals pick it up (new terminals only; no restarts by me).
+- [ ] Watch upstream: an OSC 7501 parser extension in herdr-core could
+      collapse the roster file into the native channel later; the contract
+      does not block on it.
+
+## Follow-ons (documented, deliberately unbuilt)
+
+- Steer/Stop on virtual rows via the same `subagent_*` action seam (the TUI
+  already uses it: queued steering at checkpoints, per-child stop without
+  touching siblings).
+- Background-process rows (`terminal(background=true)`) sharing the lane —
+  the same registry feed carries them; needs its own contract decision.
+
+## Non-goals
+
+No Hermes core changes; no templates in this lane; no shipped-mod edits; no
+polling loops (plugin's single dir poll is gated and idle-free); no database
+reads; no Steer/Stop in the build.
diff --git a/plugin.yaml b/plugin.yaml
index 57d2ebc..cf2632d 100644
--- a/plugin.yaml
+++ b/plugin.yaml
@@ -1,5 +1,5 @@
 name: herdr-osc7501
-version: "1.3.0"
+version: "1.4.0"
 description: Report Hermes status, messages and conversation titles to Herdr
 provides_hooks:
   - on_session_start
diff --git a/tests/test_subagents.py b/tests/test_subagents.py
new file mode 100644
index 0000000..db363e9
--- /dev/null
+++ b/tests/test_subagents.py
@@ -0,0 +1,282 @@
+"""Subagent roster sidecar: gated, throttled, active-only, fail-open.
+
+Run with Hermes's Python: python -m unittest discover -s tests -v.
+No gateway or model request is made; the registry source is injected.
+"""
+import json
+import os
+import tempfile
+import time
+import unittest
+from pathlib import Path
+from unittest.mock import patch
+
+from test_plugin import load_plugin
+
+
+class StubSource:
+    """Stand-in for the registry backend; answers subagent_rows like the view."""
+
+    def __init__(self, rows):
+        self.rows = rows
+        self.calls = 0
+
+    def subagent_rows(self, *, busy):
+        self.calls += 1
+        return [dict(r) for r in self.rows]
+
+
+def row(**over):
+    base = {
+        "subagent_id": "sa-3-9f2c", "goal": "Review for regressions",
+        "status": "running", "last_tool": "web_search",
+        "running_seconds": 12.0, "started_at": time.time() - 12.0,
+    }
+    base.update(over)
+    return base
+
+
+class Subagents(unittest.TestCase):
+    def setUp(self):
+        self.env = patch.dict(os.environ)
+        self.env.start()
+        os.environ.pop("HC_TERMINAL_ID", None)
+        os.environ.pop("TMUX", None)
+        self.addCleanup(self.env.stop)
+        self.tmp = tempfile.TemporaryDirectory()
+        self.addCleanup(self.tmp.cleanup)
+        self.plugin = load_plugin()
+        self.plugin._subagents_reset_for_tests(dirpath=Path(self.tmp.name))
+        self.addCleanup(lambda: self.plugin._subagents_reset_for_tests())
+
+    def gate(self, term="t9"):
+        os.environ["HC_TERMINAL_ID"] = term
+
+    def source(self, rows):
+        stub = StubSource(rows)
+        self.plugin._subagents_source = lambda: stub
+        return stub
+
+    def files(self):
+        return sorted(p.name for p in Path(self.tmp.name).iterdir()
+                      if not p.name.startswith("."))
+
+    def test_gate_off_writes_no_file(self):
+        self.source([row()])
+        self.assertIsNone(self.plugin._subagents_sample())
+        self.assertEqual(self.files(), [])
+
+    def test_roster_maps_contract_fields(self):
+        self.gate()
+        self.source([row()])
+        wrote = self.plugin._subagents_sample()
+        self.assertIsNotNone(wrote)
+        data = json.loads(Path(wrote).read_text())
+        self.assertEqual(data["v"], 1)
+        self.assertEqual(data["term"], "t9")
+        self.assertIn("ts", data)
+        self.assertEqual(data["children"], [{
+            "id": "sa-3-9f2c", "task": "Review for regressions",
+            "state": "running", "activity": "web_search", "age_s": 12,
+        }])
+
+    def test_elapsed_from_started_at_when_no_running_seconds(self):
+        self.gate()
+        self.source([row(running_seconds=None, started_at=time.time() - 30.0)])
+        wrote = self.plugin._subagents_sample()
+        child = json.loads(Path(wrote).read_text())["children"][0]
+        self.assertGreaterEqual(child["age_s"], 29)
+        self.assertLessEqual(child["age_s"], 31)
+
+    def test_task_sanitized_one_line_and_capped(self):
+        self.gate()
+        self.source([row(goal="  line\x02one\nline two  ")])
+        child = json.loads(Path(self.plugin._subagents_sample()).read_text())["children"][0]
+        self.assertEqual(child["task"], "lineone")  # first line only, control stripped
+        self.source([row(goal="x" * 300)])
+        self.plugin._subagents_reset_for_tests(dirpath=Path(self.tmp.name))
+        self.gate()
+        self.plugin._subagents_source = lambda: StubSource([row(goal="x" * 300)])
+        child = json.loads(Path(self.plugin._subagents_sample()).read_text())["children"][0]
+        self.assertEqual(child["task"], "x" * 120)
+
+    def test_throttle_many_events_one_call_one_write(self):
+        self.gate()
+        stub = self.source([row()])
+        self.assertIsNotNone(self.plugin._subagents_sample())
+        for _ in range(5):
+            self.assertIsNone(self.plugin._subagents_sample())
+        # the throttle short-circuits before consulting the source
+        self.assertEqual(stub.calls, 1)
+
+    def test_changed_roster_deferred_not_dropped(self):
+        self.gate()
+        stub = self.source([row()])
+        self.plugin._subagents_sample()
+        stub.rows[0]["status"] = "queued"
+        self.assertIsNone(self.plugin._subagents_sample())  # inside the window
+        self.plugin._subagents_reset_for_tests(dirpath=Path(self.tmp.name))
+        os.environ["HC_TERMINAL_ID"] = "t9"
+        self.plugin._subagents_source = lambda: stub
+        wrote = self.plugin._subagents_sample()
+        self.assertIsNotNone(wrote)
+        data = json.loads(Path(wrote).read_text())
+        self.assertEqual(data["children"][0]["state"], "queued")
+
+    def test_empty_roster_unlinks_own_file(self):
+        self.gate()
+        stub = self.source([row()])
+        wrote = self.plugin._subagents_sample()
+        self.assertTrue(Path(wrote).exists())
+        stub.rows = []
+        self.plugin._subagents_reset_for_tests(dirpath=Path(self.tmp.name))
+        os.environ["HC_TERMINAL_ID"] = "t9"
+        self.plugin._subagents_source = lambda: stub
+        self.plugin._subagents_sample()
+        self.assertFalse(Path(wrote).exists())
+
+    def test_exit_cleanup_removes_own_file(self):
+        self.gate()
+        self.source([row()])
+        wrote = self.plugin._subagents_sample()
+        self.assertTrue(Path(wrote).exists())
+        self.plugin._subagents_cleanup()
+        self.assertFalse(Path(wrote).exists())
+
+    def test_no_source_fails_open_silently(self):
+        self.gate()
+        self.plugin._subagents_source = lambda: None
+        self.assertIsNone(self.plugin._subagents_sample())
+        self.assertEqual(self.files(), [])
+        diag = Path(self.tmp.name) / ".diag-t9.json"
+        self.assertTrue(diag.exists())
+        self.assertIn("no-source", json.loads(diag.read_text())["err"])
+
+    def test_source_exception_fails_open_silently(self):
+        self.gate()
+
+        class Boom:
+            def subagent_rows(self, *, busy):
+                raise RuntimeError("gateway away")
+
+        self.plugin._subagents_source = lambda: Boom()
+        self.assertIsNone(self.plugin._subagents_sample())
+        self.assertEqual(self.files(), [])
+        diag = Path(self.tmp.name) / ".diag-t9.json"
+        self.assertTrue(diag.exists())
+        self.assertIn("gateway away", json.loads(diag.read_text())["err"])
+
+    def test_write_failure_diagnoses_without_file(self):
+        self.gate()
+        self.source([row()])
+
+        def boom(path, payload):
+            raise RuntimeError("disk sulks")
+
+        self.plugin._subagents_write = boom
+        self.assertIsNone(self.plugin._subagents_sample())
+        self.assertEqual(self.files(), [])
+        diag = Path(self.tmp.name) / ".diag-t9.json"
+        self.assertTrue(diag.exists())
+        self.assertIn("disk sulks", json.loads(diag.read_text())["err"])
+
+    def test_write_is_atomic_and_valid_json(self):
+        self.gate()
+        self.source([row()])
+        wrote = self.plugin._subagents_sample()
+        leftovers = [p for p in Path(self.tmp.name).iterdir() if p.name.endswith(".tmp")]
+        self.assertEqual(leftovers, [])
+        json.loads(Path(wrote).read_text())
+
+    def click(self, child="sa-3-9f2c", ts=None):
+        path = Path(self.tmp.name) / "t9.click.json"
+        path.write_text(json.dumps({"v": 1, "child": child, "ts": ts or time.time()}))
+        return path
+
+    def tail_fixture(self, text="First line\nLatest activity"):
+        self.gate()
+        stub = self.source([row()])
+        stub.tail_calls = []
+        def tail(child, *, fetch=False):
+            stub.tail_calls.append((child, fetch))
+            if isinstance(text, Exception):
+                raise text
+            return text
+        stub.subagent_tail = tail
+        self.plugin._subagents_sample()
+        return stub
+
+    def test_click_fetches_own_live_child_once_and_writes_bounded_tail(self):
+        stub = self.tail_fixture("\x1b[31mred\x1b[0m\n" + "\n".join("x" * 400 for _ in range(12)))
+        click = self.click()
+        request = json.loads(click.read_text())
+        path = self.plugin._subagents_click_sample()
+        data = json.loads(Path(path).read_text())
+        self.assertEqual(data["term"], "t9")
+        self.assertEqual(data["child"], "sa-3-9f2c")
+        self.assertEqual(data["request_ts"], request["ts"])
+        self.assertEqual(len(data["lines"]), 8)
+        self.assertTrue(all(len(line) <= 240 for line in data["lines"]))
+        self.assertNotIn("\x1b", json.dumps(data["lines"]))
+        with patch.object(self.plugin.time, "monotonic", return_value=time.monotonic() + 2):
+            self.assertIsNone(self.plugin._subagents_click_sample())
+        self.assertEqual(stub.tail_calls, [("sa-3-9f2c", True)])
+
+    def test_click_rate_limit_defers_new_request(self):
+        stub = self.tail_fixture()
+        self.click(ts=1000)
+        with patch.object(self.plugin.time, "time", return_value=1000), patch.object(self.plugin.time, "monotonic", return_value=10):
+            self.plugin._subagents_click_sample()
+            self.click(ts=1000.1)
+            self.assertIsNone(self.plugin._subagents_click_sample())
+        with patch.object(self.plugin.time, "time", return_value=1001), patch.object(self.plugin.time, "monotonic", return_value=11):
+            self.assertIsNotNone(self.plugin._subagents_click_sample())
+        self.assertEqual(len(stub.tail_calls), 2)
+
+    def test_click_invalid_foreign_stale_or_future_requests_do_not_fetch(self):
+        stub = self.tail_fixture()
+        for value in ["{bad", {"v": 2, "child": "sa-3-9f2c", "ts": time.time()},
+                      {"v": 1, "child": "foreign", "ts": time.time()},
+                      {"v": 1, "child": "sa-3-9f2c", "ts": time.time() - 30},
+                      {"v": 1, "child": "sa-3-9f2c", "ts": time.time() + 30}]:
+            (Path(self.tmp.name) / "t9.click.json").write_text(value if isinstance(value, str) else json.dumps(value))
+            self.plugin._subagents_click_last_poll = 0
+            self.assertIsNone(self.plugin._subagents_click_sample())
+        self.assertEqual(stub.tail_calls, [])
+
+    def test_click_no_roster_or_no_gate_performs_no_io(self):
+        self.tail_fixture()
+        self.click()
+        (Path(self.tmp.name) / "t9.json").unlink()
+        with patch("builtins.open", side_effect=AssertionError("must not read click")):
+            self.assertIsNone(self.plugin._subagents_click_sample())
+        os.environ.pop("HC_TERMINAL_ID")
+        with patch("builtins.open", side_effect=AssertionError("gate must not read")):
+            self.assertIsNone(self.plugin._subagents_click_sample())
+
+    def test_empty_roster_clears_tail_and_click(self):
+        stub = self.tail_fixture()
+        click = self.click()
+        tail = Path(self.plugin._subagents_click_sample())
+        stub.rows = []
+        with patch.object(self.plugin.time, "monotonic", return_value=time.monotonic() + 2):
+            self.plugin._subagents_sample()
+        self.assertFalse(tail.exists())
+        self.assertFalse(click.exists())
+        self.assertIsNone(self.plugin._subagents_click_sample())
+
+    def test_tail_failure_is_fail_open_and_cleanup_only_own_files(self):
+        stub = self.tail_fixture(RuntimeError("unavailable"))
+        self.click()
+        self.assertIsNone(self.plugin._subagents_click_sample())
+        self.assertFalse((Path(self.tmp.name) / "t9.tail.json").exists())
+        foreign = Path(self.tmp.name) / "t8.tail.json"
+        foreign.write_text("{}")
+        self.plugin._subagents_cleanup()
+        self.assertFalse((Path(self.tmp.name) / "t9.click.json").exists())
+        self.assertTrue(foreign.exists())
+        self.assertEqual(len(stub.tail_calls), 1)
+
+
+if __name__ == "__main__":
+    unittest.main()
```

</details>

## Preserved consumer implementation diff

<details>
<summary>Full withdrawn source changes, including uncommitted work</summary>

```diff
diff --git a/README.md b/README.md
index e45077f..5fc3541 100644
--- a/README.md
+++ b/README.md
@@ -14,6 +14,7 @@ mod at `mods/<name>/`, each with a `RECIPE.md`, liftable out for publishing.
 - `mods/tabs-live` — tab pills that show the live conversation title for tabs
   the + menu named after their program (works with the herdr-osc7501 fork).
 - `mods/recent` — **Recent** sidebar: 20 recent Hermes conversations, 30-second refresh, title/message search and guarded resume into a new tab. Open Herdr conversations are hidden; externally open ones are locked.
+- `mods/agents-hermes` — our clone of the shipped Agents sidebar: live Hermes sub-agents from the herdr-osc7501 roster sidecar show as indented active-only rows under their parent terminal, click for a status popup; native sub-agent trees, pinning, folding and grouping are unchanged.
 - `layouts/hermes.json` — our clone of the shipped `main` layout: `tabs-live`
   tab bar + the Links panel in the right stack.

diff --git a/mods/agents-hermes/main.js b/mods/agents-hermes/main.js
index 997d69a..2e138fd 100644
--- a/mods/agents-hermes/main.js
+++ b/mods/agents-hermes/main.js
@@ -2,9 +2,18 @@

 import { View, div, image, svg } from "gpui-kit";
 import { v_flex, h_flex } from "gpui-base";
-import { agents, terminals, panes, focused, spaces, run, theme, shared, setShared, setAgentOrder, openOverlay, closeOverlay, props, window, layout } from "herdr";
+import { agents, terminals, panes, focused, spaces, run, theme, shared, setShared, setAgentOrder, openOverlay, closeOverlay, props, window, layout, watchFolder, readTextFile, writeTextFile, appHome } from "herdr";
 import { request } from "./recent-client.js";

+// Live Hermes sub-agents (roster sidecar, herdr-osc7501 contract v1): one file
+// per Hermes terminal under data/hermes-subagents/, named by terminal address.
+// Files exist only while children are live — the active-only rule lives in the
+// plugin (empty roster removes the file); the mod just shows what the files say.
+const ROSTER_DIR = () => appHome() + "/data/hermes-subagents";
+const ROSTER_ID = /^[A-Za-z0-9._-]{1,64}$/;
+const VIRT_STATUS = (s) => (["running", "queued", "starting", "pending"].includes(s) ? "working" : s);
+const onepart = (s, max) => (typeof s === "string" ? s.replace(/[\u0000-\u001f\u007f]/g, " ").split(/\s+/).join(" ").slice(0, max) : null);
+
 const pinPrefetchPending=new Set();
 function prefetchChatPin(terminal,cx) {
   const cached=shared('recent.pin.'+terminal);
@@ -99,8 +108,32 @@ function icon(p, size, color) {

 export default class Agents extends View {
   init(_props, cx) {
+    if (props()?.rosterPopup) {
+      this.rosterTail = null;
+      this.loadRosterTail(cx);
+      cx.spawn(async (acx) => {
+        try { for (;;) { await watchFolder(ROSTER_DIR()); await this.loadRosterTail(acx); } } catch {}
+      });
+      return;
+    }
     if (props()?.sortMenu) return;
     this.folded = new Set();
+    this.rosters = new Map();
+    this.rosterReads = new Map();
+    const dir = ROSTER_DIR();
+    cx.spawn(async (acx) => {
+      await this.refreshRosters(acx);
+      try {
+        for (;;) {
+          const batch = await watchFolder(dir);
+          const terms = batch.includes(dir) ? null : batch.map((pth) => {
+            const relative = pth.startsWith(dir + '/') ? pth.slice(dir.length + 1) : pth;
+            return /^[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)?\.json$/.test(relative) ? relative.slice(0,-5) : null;
+          }).filter(Boolean);
+          await this.refreshRosters(acx, terms);
+        }
+      } catch {}
+    });
     // Each agent's last state and when it changed (ms), kept across restarts.
     this.changed = JSON.parse(localStorage.getItem("changed") ?? "{}");
     this.pendingPins = JSON.parse(localStorage.getItem("pins") ?? "[]");
@@ -184,15 +217,96 @@ export default class Agents extends View {
     run("terminal.peek", { terminal: addr });
   }

+  async refreshRosters(cx, terms = null) {
+    const known = new Set([...agents(), ...terminals()].map((a) => a.address));
+    const targets = terms ?? [...new Set([...known, ...this.rosters.keys()])];
+    for (const term of targets) {
+      if (!/^[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)?$/.test(term)) continue;
+      const seq = (this.rosterReads.get(term) ?? 0) + 1;
+      this.rosterReads.set(term, seq);
+      try {
+        const parsed = this.parseRoster(await readTextFile(`${ROSTER_DIR()}/${term}.json`), term);
+        if (this.rosterReads.get(term) !== seq) continue;
+        if (parsed?.children.length) this.rosters.set(term, parsed);
+        else this.rosters.delete(term);
+      } catch { this.rosters.delete(term); }
+    }
+    if (targets.length) cx.notify();
+  }
+
+  parseRoster(text, term) {
+    if (typeof text !== "string" || !text) return null;
+    let value = null;
+    try { value = JSON.parse(text); } catch { return null; }
+    if (!value || value.v !== 1 || value.term !== term || !Number.isFinite(value.ts) || !Array.isArray(value.children)) return null;
+    const children = [];
+    for (const c of value.children) {
+      if (!c || typeof c.id !== "string" || !ROSTER_ID.test(c.id)) continue;
+      children.push({ id: c.id, task: onepart(c.task, 120), state: onepart(c.state, 24), activity: onepart(c.activity, 40), age_s: Number.isFinite(c.age_s) ? c.age_s : null });
+    }
+    return { v: 1, term, ts: value.ts, children };
+  }
+
+  parseTail(text, p) {
+    if (typeof text !== "string" || !text) return null;
+    let value = null;
+    try { value = JSON.parse(text); } catch { return null; }
+    if (!value || value.v !== 1 || value.child !== p.id || value.term !== p.term || value.request_ts !== p.request_ts || !Number.isFinite(value.ts)) return null;
+    const age = Date.now() / 1000 - value.ts;
+    if (age < 0 || age > 5) return null;
+    return { lines: Array.isArray(value.lines) ? value.lines.filter((l) => typeof l === "string").slice(0, 8) : [] };
+  }
+
+  dimRoster(ts) { return Date.now() / 1000 - ts > 60; }
+
+  async rosterClick(k, e) {
+    const vr = k.vr;
+    this.clickTs = Math.max(Date.now() / 1000, (this.clickTs ?? 0) + 0.001);
+    const request_ts = this.clickTs;
+    openOverlay({ mod: "agents-hermes", props: { rosterPopup: { ...vr, request_ts } }, kind: "popup", width: 420, height: 320, at: e?.position });
+    const path = `${ROSTER_DIR()}/${vr.term}.click.json`;
+    try {
+      const previous = await readTextFile(path);
+      await writeTextFile(path, JSON.stringify({ v: 1, child: vr.id, ts: request_ts }), previous);
+    } catch {} // roster details remain usable when filesystem access fails
+  }
+
+  async loadRosterTail(cx) {
+    const p = props().rosterPopup;
+    try { this.rosterTail = this.parseTail(await readTextFile(`${ROSTER_DIR()}/${p.term}.tail.json`), p); }
+    catch { this.rosterTail = null; }
+    cx.notify();
+  }
+
+  popupRoster(cx) {
+    const t = theme();
+    const p = props().rosterPopup ?? {};
+    const tail = this.rosterTail;
+    return v_flex().w_full().min_h(0).p(10).gap(4).bg(t.popover).text_size(12)
+      .child(div().font_medium().truncate().child(p.task || p.id || "Sub-agent"))
+      .child(h_flex().gap(6).child(div().text_color(t.dim).child("state")).child(div().flex_1().truncate().child(p.state || "—")))
+      .child(h_flex().gap(6).child(div().text_color(t.dim).child("activity")).child(div().flex_1().truncate().child(p.activity || "—")))
+      .child(h_flex().gap(6).child(div().text_color(t.dim).child("elapsed")).child(div().flex_1().child(p.age_s != null ? `${p.age_s}s` : "—")))
+      .when(tail?.lines?.length, (el) => el.child(v_flex().mt(4).pt(6).border_t(1).border_color(t.border).gap(2)
+        .children(tail.lines.map((l) => div().text_size(11).text_color(t.muted).truncate().child(l)))));
+  }
+
   // Live sub-agents of `addr`, depth first, each with the tree lines in front of it.
+  // Virtual rows (roster sidecar) join at every level, so nested agents parent
+  // their own children too. Virtual nodes have no core terminal: they leaf.
   tree(all, addr, lead = []) {
     const kids = all.filter((k) => k.parent === addr && k.state === "live");
-    return kids.flatMap((k, i) => {
-      const last = i === kids.length - 1;
-      return [
-        { t: k, lines: [...lead, last ? "└" : "├"] },
-        ...this.tree(all, k.address, [...lead, last ? "" : "│"]),
-      ];
+    const virts = (this.rosters?.get(addr)?.children ?? []).map((c) => ({
+      t: { address: `vr-${addr}-${c.id}`, vr: { ...c, term: addr, dim: this.dimRoster(this.rosters.get(addr).ts) }, name: c.task, status: VIRT_STATUS(c.state), program: null },
+      virt: true,
+    }));
+    const ordered = [...kids, ...virts];
+    return ordered.flatMap((k, i) => {
+      const last = i === ordered.length - 1;
+      const lines = [...lead, last ? "\u2514" : "\u251c"];
+      const node = k.virt ? { t: k.t, lines } : { t: k, lines };
+      const sub = k.virt ? [] : this.tree(all, k.address, [...lead, last ? "" : "\u2502"]);
+      return [node, ...sub];
     });
   }

@@ -213,14 +327,15 @@ export default class Agents extends View {
       .text_size(12.5)
       .when(on, (el) => el.bg(t.raised))
       .hover((s) => s.bg(t.hover))
-      .on_hover((on,cx)=>{if(on)prefetchChatPin(k.address,cx);})
-      .on_mouse_down('right',(e,cx)=>chatMenu(k.address,e,cx))
-      .on_click(() => (this.listed.has(k.address) ? run("pane.focus", { terminal: k.address }) : this.peek(k.address)))
+      .when(!k.vr, (el) => el.on_hover((on,cx)=>{if(on)prefetchChatPin(k.address,cx);}))
+      .when(!k.vr, (el) => el.on_mouse_down('right',(e,cx)=>chatMenu(k.address,e,cx)))
+      .when(k.vr, (el) => el.on_mouse_down('left',(e)=>this.rosterClick(k,e)).cursor_pointer())
+      .when(!k.vr, (el) => el.on_click(() => (this.listed.has(k.address) ? run("pane.focus", { terminal: k.address }) : this.peek(k.address))))
       .children(s.lines.map(l => div().self_start().mt(-4).w(9).h(17).mr(4).flex_none()
         .when(Boolean(l), el => el.border_l(1.5).border_color(t.input))
         .when(l === "└" || l === "├", el => el.border_b(1.5).rounded_bl(6))))
       .when(Boolean(pic), el => el.child(div().mr(8).child(pic)))
-      .child(div().flex_1().truncate().text_color(on ? t.foreground : t.muted).child(k.name || k.template || k.program?.name || k.address))
+      .child(div().flex_1().truncate().text_color(k.vr?.dim ? t.dim : (on ? t.foreground : t.muted)).child(k.name || k.template || k.program?.name || k.address))
       .child(this.status(t, { status: st }, compact));
   }

@@ -237,6 +352,7 @@ export default class Agents extends View {

   render(cx) {
     const t = theme();
+    if (props()?.rosterPopup) return this.popupRoster(cx);
     if (props()?.sortMenu) return this.sortMenu(t);
     const collapsed = narrow();
     const sort = SORTS[0];
diff --git a/tests/test_agents_roster.mjs b/tests/test_agents_roster.mjs
new file mode 100644
index 0000000..c696ca7
--- /dev/null
+++ b/tests/test_agents_roster.mjs
@@ -0,0 +1,170 @@
+import test from 'node:test';
+import assert from 'node:assert/strict';
+import {readFileSync} from 'node:fs';
+import vm from 'node:vm';
+
+// vm sandbox over agents-hermes/main.js (imports stripped) with the roster
+// contract wired through stubs.
+function native(kind) {
+  const node={kind,_children:[],styles:{}};
+  const proxy=new Proxy(node,{get(target,key){
+    if(key==='children')return children=>{target._children.push(...children);return proxy;};
+    if(key in target)return target[key];
+    if(key==='child')return child=>{target._children.push(child);return proxy;};
+    if(key==='when')return (condition,callback)=>{if(condition)callback(proxy);return proxy;};
+    return (...args)=>{target.styles[key]=args;return proxy;};
+  }});
+  return proxy;
+}
+const source=readFileSync(new URL('../mods/agents-hermes/main.js',import.meta.url),'utf8')
+  .replace(/^import .*;\n/gm,'').replace('export default class Agents','class Agents');
+
+const themeColors={chrome:'#111',border:'#222',dim:'#444',muted:'#999',raised:'#333',foreground:'#eee',
+  hover:'#333',selected:'#2a2a2a',input:'#555',working:'#0af',blocked:'#f55',idle:'#888',done:'#0a0'};
+
+function sandbox(agents, terminals, opts={}){
+  const ordered=[];
+  const sb={
+    View:class{}, div:()=>native('div'), h_flex:()=>native('h_flex'), v_flex:()=>native('v_flex'),
+    image:()=>native('image'), svg:(p)=>{const n=native('svg');n.styles.path=[p];return n;},
+    agents:()=>agents, terminals:()=>terminals, panes:()=>[], focused:()=>({agent:opts.shown??null}),
+    spaces:()=>[{tabs:[{id:'tab1',name:'tab1',named:false}]}], run:()=>null,
+    theme:()=>themeColors, shared:()=>undefined, setShared:()=>null, setAgentOrder:(l)=>ordered.push(l),
+    openOverlay:()=>null, closeOverlay:()=>null, props:()=>undefined, window:()=>({platform:'linux'}),
+    layout:()=>({}), localStorage:{getItem:()=>null,setItem:()=>null,removeItem:()=>null},
+    watchFolder:()=>new Promise(()=>{}), readTextFile:async()=>null, writeTextFile:async()=>null,
+    appHome:()=>'/fixture',
+  };
+  vm.createContext(sb);
+  const Agents=vm.runInContext(source+'\nAgents;',sb);
+  return {sb,Agents,ordered};
+}
+
+function cxStub(){return {notify(){},timer:{every(){}},spawn(){},stop_propagation(){}};}
+
+function flatten(node){return typeof node==='string'?[node]:[node,...(node?._children??[]).flatMap(flatten)];}
+
+const AGENT={address:'t7',status:'idle',pinned:false,program:{name:'hermes',key:'hermes'},title:'',
+  tab:'tab1',space:'s1',space_name:'space',seq:1,pane:'p1',focused:false};
+
+const ROSTER={v:1,term:'t7',ts:Date.now()/1000,children:[
+  {id:'sa-3-9f2c',task:'Review for regressions',state:'running',activity:'in web_search',age_s:12}]};
+
+test('parseRoster accepts the v1 contract and rejects everything else',()=>{
+  const {sb,Agents}=sandbox([],[]);
+  const v=new Agents();
+  assert.equal(v.parseRoster(JSON.stringify(ROSTER),'t7').children[0].id,'sa-3-9f2c');
+  assert.equal(v.parseRoster(JSON.stringify(ROSTER),'other'),null);
+  assert.equal(v.parseRoster('', 't7'),null);
+  assert.equal(v.parseRoster('{bad','t7'),null);
+  assert.equal(v.parseRoster(null,'t7'),null);
+  assert.equal(v.parseRoster(JSON.stringify({...ROSTER,v:2}),'t7'),null);
+  assert.equal(v.parseRoster(JSON.stringify({...ROSTER,children:[]}),'t7').children.length,0);
+});
+
+test('roster children render indented under their parent with a working status',()=>{
+  const {sb,Agents}=sandbox([AGENT],[]);
+  const v=new Agents();v.init({},cxStub());
+  v.rosters=new Map([['t7',JSON.parse(JSON.stringify(ROSTER))]]);
+  const nodes=flatten(v.render({notify(){}}));
+  const texts=nodes.filter(n=>typeof n==='string');
+  assert.ok(texts.includes('Review for regressions'));
+  const vr=nodes.find(n=>n?.styles?.id?.[0]?.startsWith?.('sub-vr-'));
+  assert.ok(vr,'virtual row node exists');
+  // working status renders the spinner svg
+  assert.ok(flatten(vr).some(n=>n?.kind==='svg'&&String(n.styles?.path).includes('spinner')));
+});
+
+test('no roster entry or an empty roster means no rows',()=>{
+  const {Agents}=sandbox([AGENT],[]);
+  const a=new Agents();a.init({},cxStub());a.rosters=new Map();
+  assert.equal(flatten(a.render({notify(){}})).some(n=>String(n?.styles?.id?.[0]??'').startsWith('sub-vr-')),false);
+  const b=new Agents();b.init({},cxStub());
+  b.rosters=new Map([['t7',{...ROSTER,children:[]}]]);
+  assert.equal(flatten(b.render({notify(){}})).some(n=>String(n?.styles?.id?.[0]??'').startsWith('sub-vr-')),false);
+});
+
+test('virtual rows never enter the pinned order',()=>{
+  const {sb,Agents,ordered}=sandbox([AGENT],[]);
+  const v=new Agents();v.init({},cxStub());
+  v.rosters=new Map([['t7',JSON.parse(JSON.stringify(ROSTER))]]);
+  v.render({notify(){}});
+  assert.equal(JSON.stringify(ordered.at(-1)),'["t7"]');
+});
+
+test('dim only past sixty seconds of file age',()=>{
+  const {Agents}=sandbox([],[]);
+  const v=new Agents();
+  const now=Date.now()/1000;
+  assert.equal(v.dimRoster(now-59),false);
+  assert.equal(v.dimRoster(now-61),true);
+});
+
+test('popup render routes to roster fields and accepts only this request fresh tail',async()=>{
+  const {sb,Agents}=sandbox([],[]);
+  const p={...ROSTER.children[0],term:'t7',request_ts:123};
+  sb.props=()=>({rosterPopup:p});
+  const v=new Agents();v.init({},cxStub());
+  assert.ok(flatten(v.render(cxStub())).includes('Review for regressions'));
+  const tail={v:1,term:'t7',child:p.id,request_ts:123,ts:Date.now()/1000,lines:['Visible live output']};
+  sb.readTextFile=async()=>JSON.stringify(tail);
+  await v.loadRosterTail(cxStub());
+  assert.ok(flatten(v.render(cxStub())).includes('Visible live output'));
+  for(const changed of [{ts:Date.now()/1000-6},{term:'t8'},{request_ts:122},{ts:Date.now()/1000+30}]){
+    sb.readTextFile=async()=>JSON.stringify({...tail,...changed});
+    await v.loadRosterTail(cxStub());
+    const texts=flatten(v.render(cxStub()));
+    assert.ok(texts.includes('Review for regressions'));
+    assert.equal(texts.includes('Visible live output'),false);
+  }
+});
+
+test('second click replaces existing request atomically and opens popup immediately',async()=>{
+  const {sb,Agents}=sandbox([],[]);const files=new Map();const overlays=[];
+  sb.readTextFile=async path=>files.get(path)??null;
+  sb.writeTextFile=async(path,text,expected)=>{
+    assert.equal(files.get(path)??null,expected,'compare-and-swap expected text');files.set(path,text);
+  };
+  sb.openOverlay=value=>overlays.push(value);
+  const v=new Agents();const k={vr:{...ROSTER.children[0],term:'t7'}};
+  await v.rosterClick(k,{position:{x:10,y:20}});
+  const first=files.get('/fixture/data/hermes-subagents/t7.click.json');
+  assert.equal(overlays.length,1);
+  await v.rosterClick(k,{position:{x:10,y:20}});
+  const second=files.get('/fixture/data/hermes-subagents/t7.click.json');
+  assert.notEqual(first,second);
+  assert.equal(overlays.length,2);
+  assert.equal(JSON.parse(second).ts,overlays[1].props.rosterPopup.request_ts);
+});
+
+test('virtual hover avoids terminal pin lookup',()=>{
+  const {sb,Agents}=sandbox([AGENT],[]);let calls=0;
+  sb.exec=async()=>{calls++;return {stdout:'{}',code:0};};
+  const v=new Agents();v.init({},cxStub());v.rosters=new Map([['t7',ROSTER]]);
+  const row=flatten(v.render(cxStub())).find(n=>n?.styles?.id?.[0]?.startsWith?.('sub-vr-'));
+  row.styles.on_hover?.[0](true,{...cxStub(),spawn(fn){fn(cxStub());}});
+  assert.equal(calls,0);
+});
+
+test('rosters restore on init and root watch batches rescan known terminals',async()=>{
+  const {sb,Agents}=sandbox([AGENT],[]);let watcher;
+  sb.readTextFile=async path=>path==='/fixture/data/hermes-subagents/t7.json'?JSON.stringify(ROSTER):null;
+  sb.watchFolder=async()=>new Promise(resolve=>{watcher=resolve;});
+  const cx={...cxStub(),spawn(fn){fn(cx);}};
+  const v=new Agents();v.init({},cx);
+  await new Promise(resolve=>setImmediate(resolve));
+  assert.equal(v.rosters.get('t7')?.children[0].id,ROSTER.children[0].id);
+  sb.readTextFile=async()=>null;
+  watcher(['/fixture/data/hermes-subagents']);
+  await new Promise(resolve=>setImmediate(resolve));
+  assert.equal(v.rosters.has('t7'),false);
+});
+
+test('folded parents fold their virtual children into the count',()=>{
+  const {Agents}=sandbox([AGENT],[]);
+  const v=new Agents();v.init({},cxStub());
+  v.rosters=new Map([['t7',JSON.parse(JSON.stringify(ROSTER))]]);
+  v.folded=new Set(['t7']);
+  const texts=flatten(v.render({notify(){}})).filter(n=>typeof n==='string');
+  assert.ok(texts.includes('1'),'fold shows the count while closed');
+});
```

</details>
