# Hermes sub-agent sidebar rows in Herdr (live-only)

Date: 2026-11-15. Status: approved 2026-11-15 — building. Spans two repos:
this one (plugin = data producer) and `christopher-s/herdr-mods`
(agents-hermes clone = renderer). Supersedes the 2026-11-14 decision that
kept in-process delegate children off the sidebar (the active-only rule is
what keeps it un-cluttered). Written KISS-first.

## Goal

When a Hermes session running inside Herdr starts delegated agents
(`delegate_task`, batch, `/review`, and the public lifecycle API — all feed
one live registry), show each **live** child as an indented row under its
parent session row in the agents sidebar (Active/Idle groups), named after
the child's task, clickable to see what it is doing. When a child finishes,
its row disappears: rows exist only while the child is in the live registry.

## Why this shape (and not the others)

- **Chosen: projection lane.** Keep Hermes launches as they are. The plugin
  projects the live registry to Herdr over the established sidecar-file
  channel; the personal agents-hermes clone merges the rows. No Hermes core
  change, no new processes, no templates needed (that lane stays paused).
- **Alternative kept, paused: native hc-launch lane** (`hc run --bg` +
  templates, see the paused 2026-11-14 plan). Native nesting/peek/steer for
  zero code, but only children started through hc participate, and each child
  is a full process. Revisit if interactive steerable children matter.
- **Rejected for this lane: Hermes core change** to spawn delegate_task
  through hc. Docs confirm no plugin seam for the spawn mechanism (delegation
  providers answer "which route" only; core keeps spawning). Parked.

## Verified building blocks (2026-11-15)

- Live registry feed: `hermes_cli/gateway_tools.py` — the CLI monitor's view;
  `subagent_rows()` asks the gateway `subagent.list` **at most once a
  second**, only while busy / children listed last time / watch window open /
  active delegations; rows expire after ~1 minute without an answer
  (`_RETAIN_SECONDS`). `LocalSubagents` answers the same `subagent_*` calls
  when the CLI runs its agent in-process. Roster rows carry id, state,
  current activity, elapsed (what the CLI dock and Desktop frame render).
- Sidecar channel: `~/.config/herdr-app/data/<name>/<HC_TERMINAL_ID>.json` —
  the vitals contract pattern: gated on `$HC_TERMINAL_ID`, atomic tmp+rename,
  ≤500 ms throttle, deduped by value, fail-open, removed on exit.
- Renderer: agents-hermes (herdr-mods, `feat/recent-hermes-sessions` branch)
  — fixed Sessions/Active/Idle grouping + tree rendering exist; `watchFolder`
  drives all data reads (vitals-mod pattern, no polling timers).
- Hermes's own monitors define the model and retention we mirror: rows live
  while the live registry holds them; the dock drops children when they leave
  the registry; the durable record is the completion message in the
  conversation. `subagent.tail` is the documented live-tail seam (bounded
  recent excerpt), and the same `subagent_*` seam already answers per-child
  actions — those become the future Steer/Stop path.

## Architecture (contract v1)

```
delegate registry (gateway or in-process LocalSubagents)
        |  subagent.list  (≤1 rps, gated by existing view)
        v
CLI process (has $HC_TERMINAL_ID)
  herdr-osc7501 plugin: on change, write
  data/hermes-subagents/<address>.json
  (atomic, ≤500 ms throttle, deduped, fail-open,
   removed when roster empty or on exit)
        |  watchFolder event
        v
agents-hermes: merge indented rows under the parent
  row matching <address>; file present = show;
  entry gone = row gone (ACTIVE-ONLY RULE)
        |  click -> <address>.click.json
        v
plugin polls its own dir ≤1 s while the roster
file exists; one fetch per new click entry via
subagent.tail (≤1 rps); writes <address>.tail.json
```

Sidecar file v1 (one per Hermes terminal; array of live children):

```json
{"v": 1, "term": "t1q", "ts": 0, "children": [
  {"id": "sa-3-9f2c", "task": "Review for regressions",
   "state": "running", "activity": "in web_search", "age_s": 12}
]}
```

Click file (written by the mod, read by the plugin; one entry at a time):

```json
{"v": 1, "child": "sa-3-9f2c", "ts": 0}
```

Tail file v1 (written by the plugin, read by the mod popup):

```json
{"v": 1, "term": "t1q", "child": "sa-3-9f2c", "ts": 0,
 "lines": ["…bounded recent excerpt, per Hermes tail semantics…"]}
```

- Empty roster → remove the file (rows disappear; the sidebar stays honest).
- Child rows render only under their parent Hermes row; they do not count
  against the 20-entry group limit and do not enter pinned agent ordering
  (they ride their parent).
- Row status dot: any live child = working dot; that is all the roster
  honestly gives per child (state/activity/age strings are shown, not
  invented).
- Row staleness dim: file older than ~60 s (matches registry retention), not
  content timestamp — writes are change-driven, so a quiet-but-live child's
  row legitimately holds.
- Click popup: roster fields at a glance; expands with the tail file's lines
  when fresh (≤5 s).

## Performance shape

- No new timers in the plugin for the roster: sampling piggybacks the
  existing status-event path + vitals heartbeat; the registry view's own
  ≤1 rps gate already holds the RPC; sidecar writes happen only when roster
  content changed (dedupe).
- The plugin's only new poll (click-file, Task 3) runs ≤1 s **only while the
  roster file exists** — zero steady-state cost for idle sessions.
- Mod side stays event-driven: `watchFolder` on the directory, repaint on
  change; no added polling.
- Bare-terminal and tmux Hermes: gated off entirely (no `$HC_TERMINAL_ID` →
  no file → no rows), same rule as vitals.
- Cold cost: one small JSON read per terminal on the first event; steady
  state only when rosters actually change.

## Global constraints

- Preserve all existing OSC 7501/OSC 2/vitals behaviour untouched; new
  surfaces are additive.
- Plugin import of `hermes_cli.gateway_tools` is a guarded private CLI seam
  (same rule as the existing hooks): guard every access, fail open, rerun
  the tests after Hermes upgrades.
- All new plugin I/O guarded, throttled, deduped, fail-open: nothing here
  may ever break a turn. Sanitize task names through the existing one-line
  sanitizer with caps; no secrets in contract files.
- Gate-off paths must write nothing: no env var, bare terminal, tmux, or the
  gateway/serve entrypoints the plugin already skips.
- agents-hermes is edited in the herdr-mods repo on the
  `feat/recent-hermes-sessions` branch (its source of truth) and deployed
  via `scripts/deploy.sh` + `herdr-app check`; never edit deployed copies in
  place; never touch shipped mods.
- Publish per herdr-desktop-operations: `hermes plugins install
  christopher-s/herdr-osc7501 --force --enable --yes-deps`, verify
  origin/revision, `hermes plugins doctor . --ci`. Never restart Hermes
  (Chris does); running CLIs keep their loaded plugin — new terminals pick
  up new code.
- Live checks act only on scratch-owned, distinctly named terminals created
  by our own launch calls (two user tabs were once lost to focus-read
  assumptions).

## Phases (each independently shippable and reversible)

1. **Emit only.** Plugin writes the roster sidecar; Hermes UI unchanged.
   Verifiable by `cat` while you work.
2. **Render.** agents-hermes merges indented active-only rows + click popup
   from roster fields.
3. **Tail on click.** Click-file round-trip → `subagent.tail` fetch →
   popup shows the bounded live tail. (Steer/Stop via the same seam stays a
   listed follow-on, unbuilt.)
4. **Polish.** READMEs, winston-skills reference + ledger row, final gates.

## Task 1: Emit the roster sidecar (phase 1 — this repo)

**Files:** Modify `__init__.py`, `plugin.yaml` (version 1.4.0, description),
`README.md` (contract section); add `tests/test_subagents.py`.

**Interfaces:** Consumes `os.environ["HC_TERMINAL_ID"]`, the running CLI's
gateway_tools view (`subagent_rows()`; `LocalSubagents` when in-process), and
the existing vitals machinery (atomic write, throttle, dedupe, cleanup,
sanitizers). Produces `~/.config/herdr-app/data/hermes-subagents/<address>.json`
(v1 contract above).

- [ ] Tests first: no-env-var → no file; roster→file field mapping verbatim
      (id/task/state/activity/age); sanitized one-line task capped like msg;
      changed roster bypasses throttle; unchanged → no write; empty roster →
      unlink own file; exit removes own file; unresolvable view → fail open
      silently.
- [ ] Implement roster sampling on the existing status-event path +
      heartbeat; single-file-per-terminal contract; reuse vitals dir rules.
- [ ] Green suite (`python -m unittest discover -s tests -v`) +
      `hermes plugins doctor . --ci`; commit on branch.
- [ ] Live check under hc: run a real delegate in a scratch-owned named
      terminal, `cat` the file, verify fields track the CLI's own dock rows.
- [ ] README section + version bump; push.

## Task 2: Render merged rows (phase 2 — herdr-mods repo)

**Files:** `mods/agents-hermes/` on `feat/recent-hermes-sessions` (main.js +
tests per repo convention); `README.md` contents line.

**Interfaces:** Consumes the roster/click/tail JSON files by parent terminal
address via `watchFolder`; existing tree rendering, grouping, theme, popup
mechanisms. Produces indented active-only child rows + click popup.

- [ ] Node tests for a pure state module first: watch-dir map; merge keyed
      by parent address; entry gone → row gone; empty/absent file → no rows;
      children never count against the 20-cap and never enter pinned order;
      dim only past ~60 s file age.
- [ ] Implement rendering: reuse the existing tree row shape (connector
      rails, indent), working dot, task name, click handler writing the
      click file; popup shows roster fields, tail lines when the tail file
      is fresh.
- [ ] `herdr-app check` green; deploy via `scripts/deploy.sh`;
      `herdr-app status` shows `errors: []`; `herdr-app shot` verified with
      a real running delegate.
- [ ] Commit on `feat/recent-hermes-sessions`; push.

## Task 3: Tail on click (phase 3 — this repo + mod)

**Files:** `__init__.py` (click-file poll + tail fetch + tail writer),
`tests/test_subagents.py` additions; mod popup tail section + Node tests.

**Interfaces:** Consumes the click file (mod-written), the existing
`subagent.tail` seam via the same guarded CLI view (≤1 rps), and Hermes's
bounded-tail semantics. Produces `<address>.tail.json` (v1 above).

- [ ] Plugin tests first: parse own click file; one fetch per new (child,
      ts) entry; ≤1 rps; roster-empty → no poll, no tail file; unlink own
      tail file with cleanup; tail fetch failure → popup still shows roster
      fields (fail open).
- [ ] Mod tests: fresh tail file (≤5 s) renders lines; stale/absent shows
      roster fields only.
- [ ] Implement the ≤1 s dir poll gated on roster-file existence; reuse the
      atomic writer.
- [ ] Both suites green + doctor; deploy; live verify click→tail on the same
      scratch terminal; commit + push both repos.

## Task 4: Polish and integration (phase 4)

- [ ] READMEs: osc7501 gets the subagents contract section (roster/click/
      tail files, gates, caps); herdr-mods README gains the agents-hermes
      contents line with this feature.
- [ ] winston-skills `herdr-desktop.md`: contract lines + ledger row once
      live-verified; mark the 2026-11-14 paused plan's relation (sidebar
      decision superseded; templates lane still paused).
- [ ] Full gates on both repos green; publish install per skill; verify
      revision; live proof on a scratch-owned terminal; then Chris decides
      when real terminals pick it up (new terminals only; no restarts by me).
- [ ] Watch upstream: an OSC 7501 parser extension in herdr-core could
      collapse the roster file into the native channel later; the contract
      does not block on it.

## Follow-ons (documented, deliberately unbuilt)

- Steer/Stop on virtual rows via the same `subagent_*` action seam (the TUI
  already uses it: queued steering at checkpoints, per-child stop without
  touching siblings).
- Background-process rows (`terminal(background=true)`) sharing the lane —
  the same registry feed carries them; needs its own contract decision.

## Non-goals

No Hermes core changes; no templates in this lane; no shipped-mod edits; no
polling loops (plugin's single dir poll is gated and idle-free); no database
reads; no Steer/Stop in the build.
