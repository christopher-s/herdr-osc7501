# Conversation Titles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mirror the selected Hermes conversation title into Herdr's Agents sidebar.

**Architecture:** Extend the existing foreground CLI wrappers. Bind the current GatewayAgent's SessionState, observe gateway snapshots/events and publish sanitized OSC 2 titles without polling. Keep OSC 7501 behaviour intact.

**Tech Stack:** Python standard library, unittest, native Hermes plugin loader, Herdr hc.

**Spec:** docs/superpowers/specs/2026-11-14-conversation-titles-design.md

## Global Constraints

- Preserve plugin name herdr-osc7501 and existing status reports.
- Emit native titles only, no LLM calls, message reads, polling or core edits.
- Publish only the foreground CLI's selected session; normalize unsafe terminal text and support Unicode/tmux.
- Missing title resets to Hermes. Quit clears the title.
- Publish/install christopher-s/herdr-osc7501 without a commit pin; never restart Hermes.

## Review Focus

- Rapid session switching: late updates for an old session must not overwrite the active title.
- Snapshot clears: explicit null title must remove stale title despite upstream truthiness handling.
- Startup import forms: initial imports and already-loaded modules must both install wrappers.
- Terminal write failure: retry later and keep status/conversation operational.
- Native SDK changes: missing classes/methods must fail open.

### Task 1: Implement and prove conversation titles

**Files:** Modify `__init__.py`, `plugin.yaml`, `README.md`; create `tests/test_plugin.py` and `tests/herdr_smoke.py`.

**Interfaces:** Consumes GatewayAgent.session_id, GatewayAgent._state(), SessionState.adopt_snapshot(snapshot), SessionState.apply_event(kind,payload). Produces OSC 2 UTF-8 terminal title updates and unchanged OSC 7501 status reports. Tests import plugin via importlib without loading Hermes configuration.

- [ ] Write standard-library tests for title publishing through real selected SessionState objects: initial title, rename, unrelated update, resumed/new session, explicit empty title, Unicode, escape sanitization, deduplication, retry, tmux, exit and existing status.
- [ ] Run `python -m unittest discover -s tests -v` and observe missing title feature failures.
- [ ] Implement minimal guarded wrappers in the plugin; active-session binding and title publishing must serialize updates and deduplicate successful writes only. Normalize title controls, cap length at 256 characters, default to Hermes, clear to empty on quit. Support exact current SDK and missing optional seams.
- [ ] Run `python -m unittest discover -s tests -v`; expected zero failures. Run `hermes plugins doctor . --ci`; expected no errors.
- [ ] Exercise the real plugin under hc using tests/herdr_smoke.py in an isolated terminal; assert hc reports its Unicode native title, then a changed title, then a cleared title. Clean up only that test terminal.
- [ ] Update README with conversation-title semantics, manual Herdr naming precedence, fork installation and relaunch requirement. Bump plugin version to 1.1.0. Commit implementation and tests.

### Task 2: Review, publish and install the fork

**Files:** Same plugin files if review finds defects; installation in default Hermes profile only.

**Interfaces:** Consumes tested plugin from Task 1. Produces GitHub fork main revision and native installer provenance identifying christopher-s/herdr-osc7501.

- [ ] Dispatch fresh whole-branch code review of Task 1 against the spec. Reproduce and fix important findings with RED/GREEN tests and a green full suite.
- [ ] Run full tests and plugin doctor again; expected pass. Fast-forward main to reviewed implementation and push origin main. Read GitHub's exact main revision back.
- [ ] Back up existing installed plugin outside discovery paths. Run `hermes plugins install christopher-s/herdr-osc7501 --force --enable --yes-deps`.
- [ ] Read installed origin, revision, plugin manifest and install provenance. Run `hermes plugins doctor herdr-osc7501 --ci`; expected pass. Confirm no commit pin and no Hermes restart.
- [ ] Report verified repository, commit, tests, installed origin and activation requirement.
