# Herdr conversation titles

## Intent

Show the current Hermes conversation title in Herdr's existing Agents sidebar, preserving OSC 7501 status reporting. Chris selected conversation titles over live activity labels.

## Approach

Extend the fork's CLI-side integration to publish a sanitized terminal title using OSC 2. The existing Herdr Agents mod already reads terminal titles, and gives a meaningful live title precedence when the tab is unnamed or named after its program.

The alternative is the gallery's Auto Title service, which reads Hermes titles from SQLite and renames desktop tabs. It adds a separate service and requires a session identity bridge. We selected extending the existing integration in the conversation; no Herdr layout or mod changes are required.

## Design

The installed Hermes CLI receives exact-session snapshots and title updates from its gateway. `hermes_cli.gateway_connection.SessionState` holds the session ID, title and info, updating via `adopt_snapshot` and `apply_event`. `GatewayAgent` identifies which session this CLI currently displays.

Extend the plugin's existing guarded CLI wrappers to bind title publishing to the active session and observe its snapshot/title updates. Follow session changes through new, resume and branch. Ignore updates for other sessions held by the same connection. Emit the existing native conversation title without generating titles, reading chat messages or making additional LLM calls. Default to `Hermes` when the selected session has no title, clearing any previous conversation title. Suppress duplicate terminal writes.

Strip terminal escape/control sequences and unsafe formatting controls; normalize whitespace and bound the emitted title. Write UTF-8 through the foreground CLI's terminal writer. Preserve tmux passthrough when applicable. Clear the title on the existing quit cleanup path. Title handling failures must leave the conversation and status reporting operational.

No periodic database polling or background service is needed. Changes stay inside the plugin; Hermes core and shipped Herdr files remain untouched.

## Distribution

Work in `/home/chris/Projects/herdr-osc7501`, with origin `christopher-s/herdr-osc7501` and upstream `edgarsgogolevs/herdr-osc7501`. Commit and push the tested implementation to the fork's default branch. Reinstall using `hermes plugins install christopher-s/herdr-osc7501 --force --enable`, without a commit pin, preserving the plugin name. Verify the installed origin, revision and provenance.

Do not restart Hermes. Existing CLI processes retain their loaded plugin; Chris must relaunch those processes to activate the installed version.

## Verification

Write failing tests before implementation. Cover native title emission, Unicode, title changes during and between turns, unrelated-session isolation, new/resume selection, duplicate suppression, empty-title reset, escape injection, failed writes, tmux wrapping and existing status/quit behaviour. Run the complete plugin suite and Hermes plugin doctor. Exercise real title output through an isolated Herdr terminal and read back its title with hc. Verify the fork commit and installed plugin state.

## Limits

Herdr preserves explicitly customized tab labels; its sidebar may prioritize those labels. This feature does not override manual Herdr names. Hermes title-generation behaviour remains unchanged. End-to-end adoption in Chris's existing CLI requires Chris to relaunch it after installation.
