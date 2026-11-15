# Hermes sub-agent sidebar rows in Herdr (live-only)

Date: 2026-11-15. Status: proposed — awaiting approval. Spans two repos:
this one (plugin = data producer) and `christopher-s/herdr-mods`
(agents-hermes clone = renderer). Written KISS-first.

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
  change, no new processes.
- **Alternative kept, paused: native hc-launch lane** (`hc run --bg` +
  templates, see the paused 2026-11-14 plan). Native nesting/peek/steer for
  zero code, but only children started through hc participate, and each child
  is a full process. Revisit if interactive steerable children matter.
- **Rejected for this lane: Hermes core change** to spawn delegate_task
  through hc. Docs confirm no plugin seam for spawn mechanism (delegation
  provider answers "which route" only; core keeps spawning). Parked.

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
  the registry (processes ~60 s after ending); the durable record is the
  completion message in the conversation.

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
        |  click (v1)
        v
small popup from roster fields (task, state,
  last activity, elapsed)
```

Sidecar file v1 (one per Hermes terminal; array of live children):

```json
{"v": 1, "term": "t1q", "ts": 0, "children": [
  {"id": "sa-3-9f2c", "task": "Review for regressions",
   "state": "running", "activity": "in web_search", "age_s": 12}
]}
```

- Empty roster → remove the file (rows disappear; the sidebar stays honest).
- Child rows render only under their parent Hermes row; they do not count
  against the 20-entry group limit.
- v1 status dot: state running/queued → working dot; that is all the roster
  honestly gives per child.
- **Phase 2 (listed, not v1):** click opens the live transcript tail via the
  same `subagent.tail` seam (CLI-side plugin proxy, on-demand ≤1 rps);
  Steer/Stop via the same `subagent_*` action seam. v1 click = popup from
  roster fields.

## Performance shape

- No new timers in the plugin: sampling piggybacks the existing status-event
  path + vitals heartbeat; the registry view's own ≤1 rps gate already holds
  the RPC; sidecar writes happen only when roster content changed (dedupe).
- Mod side stays event-driven: `watchFolder` on the new directory, repaint on
  change; no added polling.
- Bare-terminal and tmux Hermes: gated off entirely (no `$HC_TERMINAL_ID` →
  no file → no rows), same rule as vitals.
- Cold cost: one small JSON read per terminal on the first event; steady-state
  writes only when the roster actually changes.

## Tests & gates

- Plugin (run with Hermes's Python): unittest for gate-off (no env var),
  roster→file mapping, empty-roster file removal, throttle/dedupe, exit
  cleanup; existing suite + `hermes plugins doctor . --ci` green.
- Mod: `herdr-app check` passes; deployed via herdr-mods `scripts/deploy.sh`
  (agents-hermes source lives on the `feat/recent-hermes-sessions` branch —
  merge or branch from it deliberately).
- Live: one end-to-end run in scratch-owned tabs only — start Hermes in its
  own distinctly named hc terminal, delegate a trivial task, verify the row
  appears indented under the right parent while running and disappears at
  completion; click shows the popup. Act only on IDs captured from our own
  creation calls (two user tabs were once lost to focus-read assumptions).
- Publish: `hermes plugins install christopher-s/herdr-osc7501 --force
  --enable --yes-deps`; never restart Hermes; running CLIs keep their loaded
  plugin — new terminals only.

## Non-goals / open decision

- No Hermes core changes; no templates in this lane (that lane stays
  paused); no Steer/Stop or DB-transcript panels in v1; no changes to shipped
  mods (clones only); no polling loops.
- **Open decision:** is a v1 click-popup from roster fields acceptable
  (transcript tail + controls as phase 2), or does the click view gate the
  whole build?
