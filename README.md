# herdr-osc7501

Hermes plugin that reports status to [Herdr](https://herdr.dev) with
[OSC 7501](https://mitchellh.com/writing/program-status-osc7501), so a Hermes
session shows up in the agents list the way Claude Code does.

Herdr only lists a terminal whose program speaks that protocol. Hermes did
not. This plugin emits `idle`, `working`, `blocked`, and `done` from the
process that owns the terminal. Quitting clears the record. Hermes exits with
`os._exit`, which skips a normal exit handler, so the clear runs on the
shutdown path Hermes actually calls.

A remote agent is a Hermes process on that machine. Install the plugin there,
not only on the computer running the Herdr window.

## Install

On this computer:

```sh
hermes plugins install christopher-s/herdr-osc7501 --force --enable --yes-deps
```

On a machine from `hc machine ls`:

```sh
./install.sh arch
./install.sh --all
```

`install.sh` copies this folder to that machine's `~/.hermes/plugins` and
enables it. Restart Hermes after installing. A session that is already open
keeps the copy it started with.

## What it reports

| When | Status |
|---|---|
| Hermes is waiting at the prompt | idle |
| A turn is running | working |
| Approval, a question, or a sign-in | blocked |
| The turn finishes | done |
| Hermes quits, or the pane is closed | clear |

`done` stays until you look at the pane. Herdr turns it into idle.

## Conversation titles

This fork adds the selected Hermes conversation's native title to the terminal
using OSC 2. Herdr's existing Agents sidebar reads it automatically when the tab
is unnamed or named `Hermes`. A manually customized Herdr tab name takes
precedence. No layout changes or separate service are needed.

The foreground classic CLI observes the gateway's exact-session snapshots and
`session.info` / `session.updated` events. Titles follow generation, manual
renames, `/new`, `/resume` and `/branch`, including updates between turns. A
session without a title shows `Hermes`; quitting clears it. Unicode is supported,
terminal control sequences are removed, and titles are capped at 256 characters.
There are no additional model calls, transcript reads or database polling.

Status reporting remains OSC 7501. Title support targets the gateway-backed
classic CLI's `GatewayAgent` and `SessionState` contracts; other Hermes surfaces
retain their existing status reporting. Missing optional SDK methods are skipped.
The integration uses guarded private CLI seams, so rerun the tests after Hermes
upgrades. Fully close and relaunch existing Hermes CLI processes after installing;
an already running process retains the plugin it loaded.

This repository is a fork of
[edgarsgogolevs/herdr-osc7501](https://github.com/edgarsgogolevs/herdr-osc7501).
The native install command above tracks this fork without a commit pin. Use
`hermes plugins update herdr-osc7501` to fetch later changes. The legacy
`install.sh` copies files directly and does not register Git provenance.

## Verification

Use Python from the Hermes runtime so its SDK is importable:

```sh
python -m unittest discover -s tests -v
hermes plugins doctor . --ci
python tests/herdr_smoke.py
```

The unit suite uses real SDK state and agent objects with an in-memory transport;
no gateway or model request is made. The smoke test creates its own hc terminal,
checks Unicode, rename and clear titles through `hc get`, then removes that
terminal. It leaves user tabs and processes untouched.

## License

MIT
