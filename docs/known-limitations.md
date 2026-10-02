# Known limitations

These boundaries are implemented or directly implied by the current runtime;
they are not unverified product promises.

## Current private-beta delivery

Reviewed October 1, 2026. The intended user path is ordinary Minecraft setup → useful building task → observed result and control → saved profile/history reopening. The [PM handoff](private-beta-pm-handoff.md) records current work and the [quick start](private-beta-quick-start.md) describes the actual review app.

- Current source and retained private.2 enable Minecraft calibration and small camera requests. Aim, movement, placement and wall Start remain disabled; no packaged wall completion is established.
- The current source includes guided setup progress, protection persistence, direct-control/drafting fixes and stricter observation/deadline checks. Its 1,327 passing canonical local tests are source checks. Retained packages predate those corrections.
- Minecraft is limited to Java 26.3 vanilla Creative, English/default font, supported controls/HUD and an 854 × 508 point selected window at native 1× or 2× capture. The app requires a disposable world, a clear flat practice area, a manually selected supported full block and exclusive mouse/keyboard use during native work. Survival, multiplayer, breaking, jumping/flying, automatic inventory changes and unrestricted exploration are unavailable.
- The initial building task is a 7 × 3 × 1 wall with a centered 1 × 2 opening. Manual preparation is part of the intended guided setup; developer coordinates or scripts cannot substitute for the ordinary first-use path. Geometry, occupancy, material, reach, protection and the return point require visible checks. Unknown results remain partial.
- OpenTTD supports one £10,000 repayment from a paused disposable English 15.3 company with £100,000 cash and loan. The successful packaged result belongs to retained private.1. General management, borrowing, building and arbitrary starting balances are unavailable.
- Retained Mac packages are Apple Silicon, locally ad-hoc signed and not notarized. Fresh-machine onboarding, broader configurations and sustained reliability need beta feedback; owner release/distribution approval remains pending.

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

FCEUX is the supported live Mario adapter. Minecraft and OpenTTD use their separate ordinary-window/native-input paths described above. The older Mednafen diagnostic
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
CSRF protection, safe artifact serving, and serialized ordinary mutations with
priority direct-control paths, but
it does not provide TLS, accounts, durable sessions, backups, or an availability
guarantee. Local artifact files remain the source of its displayed state.

## No autonomous service operation

There is no independent scheduler, queue, daemon, retry service, telemetry backend,
or alerting integration. The local app and CLI run under user/operator control. The app owns bounded observation/task/watchdog threads and input/model helper or emulator child processes while
the server is active; it is not a hosted autonomous service. Failures are written
into local reports where the operation supports them. Users can inspect partial
results and follow the recovery guide; unresolved defects need engineering review.

A production web deployment, shared evidence store, or remote orchestration
model would require explicit product and security design. None should be
inferred from this local application. Repository-structure follow-ups and
retained large-file rationale live in the [development guide](development.md).
