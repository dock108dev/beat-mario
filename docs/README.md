# Documentation

## Run and use

- [Repository quickstart](../README.md): requirements, source launch and tests.
- [Mario guide](mario-player-guide.md): setup, coaching, supported activities and limits.
- [Stardew guide](stardew-operator-guide.md): prepared-copy requirements, observation, review and recovery.
- [Runtime and configuration](runtime-and-configuration.md): executables, settings, local storage and process ownership.
- [Known limitations](known-limitations.md): unavailable behavior and platform support.
- [Error handling](error-handling.md): failed workers, partial outcomes and safe recovery.

## Develop and operate

- [Development](development.md): locked environment, entry points, CI and module boundaries.
- [Architecture](agent-architecture.md): language, gameplay, observation, control and persistence.
- [Module ownership](ssot.md): canonical policies and compatibility boundaries.
- [Security](security.md): authority, local HTTP, model inference and data protection.
- [UI design](ui-design.md), [requirements](ui-design-requirements.md) and [verification](ui-verification.md): rendering conventions and interaction checks.
- [Mario integration](b2-integration-contract.md) and [Stardew integration](b3-integration-contract.md): adapter interfaces.
- [Learning](learning.md), [live observation](live-observation.md) and [objective profiles](objective-profiles.md): compatibility, observations and outcome accounting.
- [Route Lab](mario-route-lab.md), [goal contracts](goal-contract.md), [FCEUX harness](fceux-harness.md), [reliability](reliability-gate.md) and [route patches](route-patch-schema.md): engineering tools.
- [Experimental adapters](new-game-onboarding.md): contributor fixture infrastructure.

## Planning and evidence records

Current pickup: build a usable local Mac candidate with supported Mario and prepared Stardew watering, then qualify its ordinary setup/play/control/persistence loop. [Desktop next steps](/Users/michaelfuscoletti/Desktop/mario_next_steps.md) and the [delivery checklist](private-beta-engineering.md#complete-initial-beta-delivery-checklist) contain the remaining release tasks. Source reconnaissance stays experimental until native-qualified; it does not block independent packaging work.

The named engineering, handoff, review and verification files retain development
plans and exact candidate evidence. They are records, not prerequisites for setup.
[Engineering plan](private-beta-engineering.md) and
[handoff](private-beta-pm-handoff.md) contain editable worklists.
[Review records](private-beta-review.md), [connected gameplay verification](gc-ai-loop-verification.md),
and [reconnaissance verification](gc-s-recon-verification.md) distinguish source,
simulation, native-game and package results. Historical package and campaign
records preserve their versioned meanings. Local evidence paths in those records
identify retained runs; they are not distributed runtime inputs.
