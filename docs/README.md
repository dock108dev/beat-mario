# Documentation index

Updated October 4, 2026. Game Companion's personal Mac beta needs two connected
capabilities: contextual language understanding through Codex and an agent that
understands observations, chooses gameplay actions, verifies them and adapts.
Mario and Stardew are the initial games. Existing fixed routines and narrow
real-game results are useful foundations; they do not yet provide that complete
AI experience.

## Next engineering session

1. [Product direction](product-direction.md): current owner experience, two AI responsibilities, scope and delivery order.
2. [PM handoff](private-beta-pm-handoff.md): implementation starting point, useful foundations and next engineering action.
3. [Engineering plan](private-beta-engineering.md): complete technical roadmap from the current source through the actual personal beta, including provider integration, game understanding/decision loops, memory, control, setup and delivery.
4. [Desktop next steps](/Users/michaelfuscoletti/Desktop/mario_next_steps.md): source-of-truth status and the next concrete action.
5. [Architecture](agent-architecture.md), [Mario integration](b2-integration-contract.md), [Stardew integration](b3-integration-contract.md) and [learning](learning.md): shared and adapter-owned seams for implementation.

The next step is substantial AI engineering, followed by integrated game and
delivery validation. Repeatedly qualifying one more fixed path is not the active
roadmap. Preserve those paths as skills/baselines and use their evidence to inform
the agent. Recording is deferred to tentative beta v2; Minecraft expansion and
no-code onboarding are later work.

## Current player guides and retained packages

- [Mario player guide](mario-player-guide.md): current source coaching, remembered experimental route guidance and flight/reward support, with prerequisites and limits.
- [Stardew guide](stardew-operator-guide.md): current supported farm setup, watering, planting discussion and inspection; actual cave availability and limitations.
- [Retained package quick start](private-beta-quick-start.md): private.2 Minecraft calibration/camera and private.1 OpenTTD reference setup. No retained package demonstrates the corrected initial beta.
- [Review status](private-beta-review.md): historical owner review and exact package/source boundaries; current scope is in product direction and the engineering roadmap.
- [Personal-pilot delivery](b8-personal-delivery.md): historical in-place Mario/Stardew launcher and September 26 candidate identity, useful implementation context rather than the current readiness decision.
- [Known limitations](known-limitations.md): current capabilities, gaps and what local checks cannot prove.

Adjacent package manifests, supplied guides and Owner Review files remain authoritative for their exact apps. Editing repository docs does not upgrade a package. Owner product feedback and launch/distribution decisions remain separate.

## Understand and develop the system

- [Architecture](agent-architecture.md): reusable owners plus the planned conversation/decision/execution/attempt-memory integration.
- [Single sources of truth](ssot.md): authoritative runtime/contract modules and preserved compatibility boundaries.
- [Development](development.md): locked environment, public entry points, focused verification and distinct successor packaging.
- [Runtime and configuration](runtime-and-configuration.md): actual local settings, executables, artifact roots and operating boundaries.
- [Security](security.md) and [error handling](error-handling.md): authority, data preservation, failed workers, input release and fresh recovery.
- [UI design](ui-design.md), [UI requirements](ui-design-requirements.md) and [UI verification](ui-verification.md): current visual system, planned conversational interaction and candidate-specific checks.
- [Session automation and metrics](session-automation-metrics.md): existing evidence classes and planned coaching/activity events.

The canonical non-live check is `PYTHON=.venv/bin/python scripts/validate_phase0.sh`;
use affected checks after bounded changes and the full gate for integrated
handoff. Documentation-only changes need documentation/link/whitespace checks.
Gameplay evidence needs real sessions, and packaged claims need the built app.
The current engineering roadmap owns the release criteria; the legacy B2–B9
readiness contract and retained package gates require a successor before they
can report readiness for this beta. See [delivery work](development.md#personal-beta-delivery-work).

## Mario implementation and evidence

- [Conversation guide](b2-conversation-guide.md) and [integration contract](b2-integration-contract.md): existing interfaces and the contextual language/gameplay AI target.
- [Objective profiles](objective-profiles.md), [live observation](live-observation.md) and [learning](learning.md): goal/coin coverage, observation trust, attempt compatibility and coaching-memory separation.
- [Coaching verification](gc1-gc2-coaching-verification.md), [route verification](gc2-route-verification.md) and [flight verification](gc2-flight-verification.md): exact observed source capabilities; broader agent behavior remains to be built and validated.
- [Demonstration verification](gc2-demonstration-verification.md): implemented recording/application and its unverified live limits; follow-on beta v2 work.
- [Route Lab](mario-route-lab.md): engineering attempts, notes, issue ledgers and accepted-route patches.
- [Goal contracts](goal-contract.md), [FCEUX harness](fceux-harness.md), [reliability gates](reliability-gate.md), [route patch schema](route-patch-schema.md) and [route status](route-status.md): retained exact-route execution/evidence. They do not make every experimental coaching attempt an accepted route.

## Stardew and later expansion

- [Stardew integration](b3-integration-contract.md): reusable observed actions/ledgers, safe copy/input boundaries and the model-driven activity target.
- [Watering](gc3-watering-verification.md), [planting discussion](gc3-planting-verification.md) and [inspection verification](gc3-inspection-verification.md): narrow real-game source evidence and prerequisites.
- [Cave verification](gc3-cave-verification.md): earlier partial exterior survey plus newer manual round-trip evidence; ordinary companion cave delegation remains unverified. The current roadmap replaces the old cave-detour pickup as the next broad development direction.
- [New-game onboarding](new-game-onboarding.md): later guided no-code target and current fixture contributor infrastructure; work/discussion deferred until the first two experiences are implemented.
- [Minecraft source correction](minecraft-beta-course-correction-20261001.md), [camera report](pb3-minecraft-camera.md), [reference integration](pb2-integration.md) and [package review](private-beta-review.md): retained foundations for later-beta Minecraft gameplay; no full Minecraft wall claim.
- [Unattended regression](unattended-regression.md): opt-in engineering evidence; independent learning/practice remains future product work.

## Historical planning and assets

- [Personal-beta B-series packet](personal-beta-engineering.md), [B4 handoff](b4-engineering-handoff.md), [B5 handoff](b5-engineering-handoff.md), [B6 handoff](b6-engineering-handoff.md) and [B8 work order](b8-delivery-work-order.md): historical tasks and evidence. Continue work from the current engineering roadmap, not these old pickup instructions.
- [V2 roadmap](v2-roadmap.md) and [historical campaign guide](final-campaign-guide.md): retained phase/status/scenario meanings; superseded as the beta roadmap and readiness checklist.
- [Local assets](local-assets.md): ignored artwork and rights boundaries.

Implementation, local checks, retained gameplay, current packaged behavior, owner usefulness and launch acceptance are distinct claims throughout this documentation.
