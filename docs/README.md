# Documentation

Current Minecraft slice: [MC-B1-03 implementation](mc-b1-03-resources.md), [live evidence](mc-b1-03-evidence-20261027.md), and [exact MC-B1-04 handoff](mc-b1-04-handoff.md).


Earlier conversational foundation: [MC-B1-02](mc-b1-02-chat-play.md) · [dated evidence](mc-b1-02-evidence-20261027.md). Next: MC-B1-04.

Start with the [Minecraft Beta 1 plan](beta-1-plan.md) and
[next-session handoff](private-beta-pm-handoff.md). Minecraft is the sole active
beta: headless bot, its own character, Codex CLI and concurrent chat/play.
NES emulator companionship is goal 2; Stardew is out of active scope.
The [headless foundation](mc-b1-01-headless.md) has local bot qualification
[evidence](mc-b1-01-evidence-20261027.md); human joining is deferred. MC-B1-02/03
now have local qualification. The operational guides below describe existing legacy paths.


## Run and use

- [Repository quickstart](../README.md): requirements, source launch and tests.
- [Mario guide](mario-player-guide.md): setup, coaching, supported activities and limits.
- [Stardew guide](stardew-operator-guide.md): ordinary default-save copying/preparation, observation, review and recovery.
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

[Personal use](personal-use.md) defines the current working approach.
[Current engineering status](current-engineering-status.md) lists working paths,
exact source/app evidence and actual remaining problems. The
[October 25 audit](documentation-audit-20261025.md) records the latest reconciliation;
the [October 6 audit](documentation-audit-20261006.md) retains the earlier review.
The [app quick start](private-beta-quick-start.md) covers local app setup.

The named engineering, handoff, review and verification files retain development
plans and exact candidate evidence. They are records, not prerequisites for setup.
[Engineering plan](private-beta-engineering.md) and
[handoff](private-beta-pm-handoff.md) point to the current Beta 1 worklist.
[Review records](private-beta-review.md), [connected gameplay verification](gc-ai-loop-verification.md),
and [reconnaissance verification](gc-s-recon-verification.md) distinguish source,
simulation, native-game and package results. Historical package and campaign
records preserve their versioned meanings. Local evidence paths in those records
identify retained runs; they are not distributed runtime inputs.
