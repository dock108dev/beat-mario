# Known limitations

These boundaries are implemented or directly implied by the current runtime;
they are not unverified product promises.

## Bounded planning and unfinished capabilities

The [conversation guide](b2-conversation-guide.md) describes local contextual planning, declared World 1-1 path/stop edits, normal/uncapped playback and authority-free saved variants. Only one cumulative Mario base exists. Quickest and 100% selections do not invent optimized routes or completion coverage. Resumed play permits only the verified opening stop after fresh observation/review/Start; level-exit or full-base traversal requires fresh power-on. Arbitrary mid-run full-route resume, custom later levels and fixed 2×/4× playback are unsupported. The deterministic language backend recognizes bounded action families and contextual corrections; unknown wording asks for clarification rather than using an external model.

Stardew watering and combined-action support is restricted to the prepared configurations in the [Stardew guide](stardew-operator-guide.md). Guarded stops may leave the return unconfirmed even when selected actions finish. Neutral handback is distinct from reaching the farmhouse. Retained successful runs establish behavior only for their identified source and configuration; they do not qualify later source changes or establish owner acceptance.

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

## Stardew live-input prerequisites

The browser workspace routes setup, planning and guarded controls into the Stardew runtime. The CLI remains inspection-only. Start requires verified session isolation, a qualified real-game pixel profile, complete fresh observations and reviewed scope. No qualified profile ships with this checkout. Day 5 supports only its selected ordinary parsnip, owned seed and small stone; arbitrary farming and automatic refill remain unsupported. See the [Stardew guide](stardew-operator-guide.md).

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
