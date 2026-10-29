# Documentation

## Use the application

- [Quickstart](../README.md): requirements, installation and source launch.
- [Minecraft](minecraft.md): chat, gathering, construction, Stop and recovery.
- [Known limitations](known-limitations.md): supported behavior and deployment limits.
- [Mario](mario-player-guide.md) and [Stardew](stardew-operator-guide.md): older integrations.
- [AI provider](ai-provider.md): local server configuration, capabilities and cancellation.
- [Runtime and configuration](runtime-and-configuration.md): settings and data locations.
- [Error handling](error-handling.md) and [security](security.md): recovery and trust boundaries.

## Product scope

The supported Minecraft foundation is bounded chat/play and wooden construction.
General novice-friendly world creation is the next product goal, not an existing
capability; see [scope and limitations](known-limitations.md#creative-building-target).
Local planning and dated evidence files are intentionally excluded from source
exports; they do not establish capabilities in a freshly installed build.

## Develop and maintain

- [Development](development.md): commands, repository layout and packaging requirements.
- [Architecture](agent-architecture.md) and [module ownership](ssot.md): responsibilities and invariants.
- [CI](CI.md): checks, triggers and reports.
- [UI design](ui-design.md) and [requirements](ui-design-requirements.md): interaction and styling.
- [Experimental adapters](new-game-onboarding.md): declarative integration format.

## Engineering tools

These tools operate on explicit inputs and do not imply broader gameplay support.

- [Goal contracts](goal-contract.md), [FCEUX harness](fceux-harness.md), [reliability](reliability-gate.md).
- [Route Lab](mario-route-lab.md), [route-patch schema](route-patch-schema.md).
- [Learning](learning.md), [live observation](live-observation.md), [objective profiles](objective-profiles.md).
- [Session metrics](session-automation-metrics.md), [unattended regression](unattended-regression.md), [campaign contracts](final-campaign-guide.md).
- [Local assets](local-assets.md): required inputs and excluded game assets.
