# Hermes Vitals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Herdr live Hermes status-bar telemetry (model, context %, tok/s,
latency, cache hit, tokens, duration) to render in its own UI, while the
Hermes CLI under Herdr shows only the composer — its status bar suppressed.

**Architecture:** A sidecar JSON file per terminal is the contract. The
herdr-osc7501 fork (running inside the CLI) reads `HC_TERMINAL_ID`, samples
`cli._get_status_bar_snapshot()` on status events (throttled, deduped), and
writes `~/.config/herdr-app/data/hermes-vitals/<address>.json`. A new Herdr
mod ("vitals") reads that directory and renders the focused agent's numbers.
Suppression is fork-side and gated on `HC_TERMINAL_ID`: a forced
`display.status_bar.fields` of `[none]` blanks the left segments (config
mechanism, no patch), and a monkeypatch of `hint_pairs` in
`cli_modern_layout` blanks the right-half hints. Bare-terminal/tmux Hermes
is untouched (no env var, no suppression, no file).

**Tech Stack:** Python standard library, unittest, native Hermes plugin
loader; JavaScript (gpui-kit) for the Herdr mod; watchFolder for updates.

**Phases (each independently shippable and reversible):**

1. Emit only. Fork writes vitals files; Hermes UI unchanged. Verifiable by
   `cat` while you work.
2. Vitals mod in herdr-mods renders from the files; both UIs visible for
   side-by-side tuning.
3. Suppression on (fields `[none]` + hint_pairs patch), gated on
   HC_TERMINAL_ID.
4. Visual iteration; sidebar/pill reuse of the same files.

## Global Constraints

- Preserve plugin name herdr-osc7501, all OSC 7501/OSC 2 behaviour, and the
  status snapshot's truth: values come from the CLI's own
  `_get_status_bar_snapshot()`, never recomputed.
- Vitals writes must never block or break a turn: all I/O guarded, throttled
  to 500 ms, deduped by value; failures are silent.
- Suppression applies only when `HC_TERMINAL_ID` is set and matches
  `t<machine>/t<id>` or bare `t<id>` form; every gate fails open.
- The vitals file is a versioned contract: `{"v": 1, "term": ..., "ts": ...,
  "model": ..., "context_pct": ..., "tps": ..., "latency_ms": ...,
  "cache_hit": ..., "total_tokens": ..., "compressions": ...,
  "duration_s": ..., "state": ...}`. Non-Hermes agents simply have no file.
- Never restart Hermes; publish/install per herdr-desktop-operations
  (install with `--force --enable --yes-deps`, verify origin/revision and
  plugin doctor; existing CLI processes keep their loaded plugin until
  relaunch).

## Review Focus

- Snapshot availability: `_get_status_bar_snapshot` missing/partial must fail
  open (no file or partial file), never raise into the CLI.
- Throttle correctness: many events in one turn produce few writes; changed
  values bypass throttle.
- Suppression gating: bare terminal, tmux, and gateway/serve processes never
  suppress and never write vitals.
- hint_pairs patch: applied once, survives prompt_toolkit re-import, and is
  verified by the test suite against the installed Hermes source.
- Contract stability: the mod renders from v1 fields; unknown extra fields
  ignored.

### Task 1: Emit vitals from the fork (phase 1)

**Files:** Modify `~/Projects/herdr-osc7501/__init__.py`, `plugin.yaml`,
`README.md`; add `tests/test_vitals.py`.

**Interfaces:** Consumes `os.environ["HC_TERMINAL_ID"]`, the CLI's
`_get_status_bar_snapshot()` and `_get_status_bar_field_set` seams, and the
existing `_publish_state`/`_wrap_cli_titles` binding points. Produces
`~/.config/herdr-app/data/hermes-vitals/<address>.json` (v1 contract).

- [ ] Tests first: gate (no HC_TERMINAL_ID → no file), snapshot sampling and
  field mapping, throttle/dedupe, failure-open writes, address forms
  (`t3`, `devbox/t7`), cleanup on exit.
- [ ] Run `python -m unittest discover -s tests -v`; observe vitals failures.
- [ ] Implement: `_vitals_enabled()`, `_vitals_dir()`, `_vitals_write()`
  (atomic tmp+rename), sampling hook into `_publish_state`/turn events,
  throttle+dedupe, atexit cleanup of own file. All guarded.
- [ ] Green suite + `hermes plugins doctor . --ci`; commit on a branch.
- [ ] Live check: under hc, run a real turn, `cat` the vitals file for this
  terminal's address, verify fields track the on-screen bar (model,
  context_pct, tps).
- [ ] README section + version 1.3.0; push branch.

### Task 2: Vitals mod (phase 2)

**Files:** New `mods/vitals/` in `~/Projects/herdr-mods` (main.js, mod.json,
RECIPE.md); `layouts/hermes.json` adds a block; deploy via scripts/deploy.sh.

**Interfaces:** Consumes vitals JSON files by focused terminal address;
`readTextFile`, `watchFolder` on `~/.config/herdr-app/data/hermes-vitals/`,
`focused()`, `theme()`. Produces a compact telemetry strip in the layout.

- [ ] Mod renders model/context/tps/latency/cache/tokens/duration for the
  focused terminal; dim stale (>10 s); absent file renders nothing.
- dim >10s; absent file renders nothing.
- [ ] `herdr-app check` passes; deployed via deploy.sh; screenshot-verified
  with real values beside the still-visible Hermes bar.
- [ ] Commit and push herdr-mods.

### Task 3: Suppression (phase 3)

**Files:** Modify `~/Projects/herdr-osc7501/__init__.py`, tests.

**Interfaces:** Consumes `cli._get_status_bar_field_set()` seam and
`cli_modern_layout.hint_pairs`. Produces blank left segments and no right
hints, only under Herdr.

- [ ] Tests: gate on/off, `[none]` field-set forcing (blank left), hint_pairs
  patch returns [] and original restored on unload, fail-open everywhere.
- [ ] Implement gated suppression; green suite + doctor; commit.
- [ ] Live check: new hc terminal + hermes; observe composer-only footer;
  run tmux-based hermes and verify full bar still there.
- [ ] README + version bump; push; install per skill; verify installed
  revision.

### Task 4: Polish and integration notes

- [ ] Sidebar/pill reuse experiments (read-only, no fork changes).
- [ ] Update winston-skills herdr-desktop.md (vitals contract, suppression
  gate, mod entry) with ledger row; gates green; push.
- [ ] Watch upstream: herdr-core 7501 parser extension or herdr-app #228/#412
  could absorb parts; revisit then.
