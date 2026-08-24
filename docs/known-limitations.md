# Known limitations

These boundaries are implemented or directly implied by the current runtime;
they are not unverified product promises.

## Live validation requires local assets

Non-live tests verify contracts, parsers, reports, security controls, and
deterministic rendering, but they cannot prove emulator startup, route timing,
gameplay success, or the game-owned ending. That proof requires the configured
local environment, FCEUX, and the goal-specific fresh-run gate.

Ignored gameplay artifacts are local-only. They are neither uploaded nor
replicated, so another checkout cannot reproduce an acceptance claim without
the recorded source revision, compatible local runtime, and a fresh run.

## Platform support

FCEUX is the supported live product adapter. The older Mednafen diagnostic
adapter is macOS-only and depends on a visible desktop plus Accessibility and
screen-capture permissions. Headless Mednafen operation and non-macOS Mednafen
control are unsupported.

The non-live CI job runs on Linux and intentionally does not install or start
either emulator.

## Stardew is not publicly wired for live operation

The Stardew copied-save, visible-window, observation, Tell/Show/Do, reclaim,
reset, and evidence contracts have deterministic coverage. The public CLI and
loopback server currently expose only capability inspection and a safe
unconfigured render. They do not create a save copy, launch or attach to
Stardew, configure ordinary input, or start a live controller. Live Stardew
operation and owner proof therefore require a separate integration decision
and the consolidated campaign; they cannot be inferred from the domain tests.

## Route Lab is local-only

Route Lab accepts only loopback bind hosts. It is not designed for LAN,
internet, multi-user, or unattended deployment. It has request-size limits,
CSRF protection, safe artifact serving, and serialized mutation actions, but
it does not provide TLS, accounts, durable sessions, backups, or an availability
guarantee. Local artifact files remain the source of its displayed state.

## No autonomous service operation

There is no scheduler, queue, worker, daemon, retry service, telemetry backend,
or alerting integration. CLI commands run under operator control. Route Lab may
own bounded Show/live-observation threads and emulator child processes while
the server is active; it is not an autonomous service. Failures are written
into local reports where the operation supports them, and an engineer must
inspect and respond to those reports.

A production web deployment, shared evidence store, or remote orchestration
model would require explicit product and security design. None should be
inferred from this local application. Repository-structure follow-ups and
retained large-file rationale live in the [development guide](development.md).
