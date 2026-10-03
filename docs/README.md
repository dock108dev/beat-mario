# Documentation index

Updated October 3, 2026. Game Companion's initial beta delivers conversational Mario coaching and Stardew activity delegation. The initial beta can connect Minecraft, which develops into the third playable game during beta; advanced-user no-code game onboarding follows implementation of the first two experiences.

## Next engineering session

1. [Product direction](product-direction.md): confirmed owner experience, examples, scope and delivery order.
2. [PM handoff](private-beta-pm-handoff.md): current foundations/gaps, exact retained package and session pickup.
3. [Engineering plan](private-beta-engineering.md): GC1 priority conversation/control, GC2 Mario learning/coaching, GC3 Stardew delegation, GC4 delivery and deferred GC5/GC6 expansion; owners, acceptance, checks and failure handling.
4. [Desktop next steps](/Users/michaelfuscoletti/Desktop/mario_next_steps.md): source-of-truth status and the next concrete action.
5. [Mario integration](b2-integration-contract.md) and [learning](learning.md): immediate GC1/first-GC2 watched-play, timing-change and next-attempt-memory work.

Begin with urgent conversational Stop and one useful watched/coached Mario attempt. Finish Mario's initial experience, then Stardew's useful approved activities. Preserve existing game/control/history work and historical evidence.

## Current player guides and retained packages

- [Mario player guide](mario-player-guide.md): actual bounded paths/stops/speed and fresh-session/reclaim limits, separately from the planned coached-player experience.
- [Stardew guide](stardew-operator-guide.md): actual prepared Day 2/Day 5 routines and their local prerequisites, separately from planned crop/location/exploration delegation.
- [Retained package quick start](private-beta-quick-start.md): private.2 Minecraft calibration/camera and private.1 OpenTTD reference setup. No retained package demonstrates the corrected initial beta.
- [Review status](private-beta-review.md): October 3 owner words/engineering interpretation, unreviewed app use and exact historical package/source boundaries.
- [Personal-pilot delivery](b8-personal-delivery.md): retained in-place Mario/Stardew launcher and September 26 candidate identity.
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

The canonical non-live check is `PYTHON=.venv/bin/python scripts/validate_phase0.sh`; use affected checks after bounded changes and the full gate for integrated handoff. Documentation-only changes need documentation/link/whitespace checks. Gameplay evidence needs fresh real sessions, and packaged evidence needs the exact built app. [GC4 delivery/PB10](private-beta-engineering.md#delivery-integration--pb10) owns the next package and matching guide.

## Mario implementation and evidence

- [Conversation guide](b2-conversation-guide.md) and [integration contract](b2-integration-contract.md): existing interfaces and planned GC1/GC2 work.
- [Objective profiles](objective-profiles.md), [live observation](live-observation.md) and [learning](learning.md): goal/coin coverage, observation trust, attempt compatibility and coaching-memory separation.
- [Route Lab](mario-route-lab.md): engineering attempts, notes, issue ledgers and accepted-route patches.
- [Goal contracts](goal-contract.md), [FCEUX harness](fceux-harness.md), [reliability gates](reliability-gate.md), [route patch schema](route-patch-schema.md) and [route status](route-status.md): retained exact-route execution/evidence. They do not make every experimental coaching attempt an accepted route.

## Stardew and later expansion

- [Stardew integration](b3-integration-contract.md): reusable observed actions/ledgers, safe copy/input boundaries and GC3 activity acceptance.
- [New-game onboarding](new-game-onboarding.md): later guided no-code target and current fixture contributor infrastructure; work/discussion deferred until the first two experiences are implemented.
- [Minecraft source correction](minecraft-beta-course-correction-20261001.md), [camera report](pb3-minecraft-camera.md), [reference integration](pb2-integration.md) and [package review](private-beta-review.md): retained foundations for GC5; no full Minecraft wall claim.
- [Unattended regression](unattended-regression.md): opt-in engineering evidence; independent learning/practice remains future product work.

## Historical planning and assets

- [Personal-beta B-series packet](personal-beta-engineering.md): original two-game implementation/evidence requirements; new work uses the active GC plan.
- [V2 roadmap](v2-roadmap.md) and [historical campaign guide](final-campaign-guide.md): retained phase/status/scenario meanings, not the corrected readiness checklist.
- [Local assets](local-assets.md): ignored artwork and rights boundaries.

Implementation, local checks, retained gameplay, current packaged behavior, owner usefulness and launch acceptance are distinct claims throughout this documentation.
