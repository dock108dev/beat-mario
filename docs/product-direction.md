# Game Companion product direction

Updated October 4, 2026. This owns the intended product. The [architecture](agent-architecture.md) defines both AI responsibilities; the [engineering plan](private-beta-engineering.md) and [Desktop worklist](/Users/michaelfuscoletti/Desktop/mario_next_steps.md) enumerate all work through private-beta release. [PM handoff](private-beta-pm-handoff.md) is the current session pickup.

## The product

Game Companion is a conversational AI player for the owner's local Mac. Describe a goal in your own words, watch it understand the game and play, discuss decisions, coach behavior and reclaim control. It carries useful context into future attempts and reports what actually happened.

There are two required intelligent capabilities:

1. **Language understanding:** a real LLM interprets original language in conversational and game context. It understands goals, references, questions, preferences, exclusions, corrections and coaching, and clarifies material ambiguity.
2. **Game understanding and play:** an agent reasons from current observations, game mechanics, resources, possible actions and remembered outcomes. It chooses/composes actions, checks their consequences and adapts when the scene or goal changes.

Use Codex CLI as the first backend for this personal app. One model can serve both roles. The app supplies game context, images and validated tools, and existing controllers handle fast execution. Local application ownership does not make the default model inference offline.

The intended loop is conversation → understood objective → observed game state → grounded plan → approval → agent-selected action → observed effect → revised decision or coaching → actual outcome and handback → useful memory.

The same implementation must handle meaningful variation without engineering a new full script for every request. Reusable skills, ordinary algorithms and precise feedback controllers are part of the solution. Understanding and decision-making must affect execution, rather than only explain an authored route.

## Initial private beta

Deliver an installable personal Mac app with useful bounded Mario and Stardew coverage, integrated Codex/game setup, conversation, memory, interruption, readable limits and local feedback. The repo launcher is an engineering path; the successor .app is the release target. No hosted app service or external tester campaign is required for this local release.

### Mario: watched play and coaching

Understand route/coin, maneuver, reward and coaching intentions in context. Observe the supported scene and mechanics, choose useful actions and adapt a later decision or attempt using observations and feedback. Frame timing remains with the fast controller.

The player should be able to watch goal-directed play, change a preference, coach a relevant event, retry within a finite agreed scope and see remembered guidance affect decisions. Flight/reward objectives need observed prerequisites and confirmed collection. Coin discovery reports collected, known missed and uncertain coverage; full 100% is claimed only when actually established.

Initial supported levels/segments may be declared. A changed supported entry, target, hazard or preference should produce an appropriate different choice using the same implementation. Arbitrary games, perfect performance and universal English-to-button execution are not promised.

### Stardew: short delegated activities

Discuss useful work for the next few minutes, inspect the current farm, propose a plan, receive approval, choose actions and report progress. Handle revised preferences and unexpected conditions through further observation, replanning or a useful clarification/remedy.

Initial experiences are watering observed crops, finding/discussing a planting location and a meaningful exploration/reconnaissance activity. Tool/water/energy, season, occupancy, terrain and access must inform choices. Identifying a spot permits no planting or purchasing. Entrance reconnaissance and interior exploration are separate coverage.

Supported farms/settings can be bounded, but ordinary users should not provide engineering coordinates or an engineer-written route for each new goal. The agent must reason over supported variations. Primary saves stay protected through a usable disposable/copy workflow; explicit manual prerequisites are acceptable when the app explains them.

### Shared interaction

Show the understood goal, proposed scope, current action, observed progress and usable next step. Questions produce no input. Approval applies to the current plan; changes and interruption invalidate stale work. Model delay or failure cannot revive authority or conceal an unfinished result.

Stop/Take control remains immediate and independent of inference. Switching games waits for release. Reopening restores descriptive configuration/history/memory, never live control. Coaching can apply at a supported action boundary or later attempt; acknowledge when and what changed.

The owner can inspect/reset future guidance. Remember context and uncertainty, not just a canned instruction label. Preserve failed attempts as evidence without declaring every parameter change an improvement.

## Current source versus target

Current Mario/Stardew language is primarily deterministic, and high-level gameplay is primarily engineer-authored tactics/routes. Those ordinary paths do not yet contain the required connected LLM and adaptive play agent.

Existing source gameplay established Mario opening coaching, remembered stairs/pipe tactics, two World 1-1 finishes and two supported sky 1UP collections; Stardew selected watering, live planting discussion and an eastern inspection/return. These are useful capabilities and regression evidence, not proof of general AI gameplay understanding.

The Farm Cave has local activity/camera work and a newer manually verified tool-free route. Ordinary companion delegation remains unverified; a manual round trip is not the completed conversational activity. The separate Ollama/reference-profile model gateway does not establish model integration for Mario/Stardew. No successor package demonstrates the new AI beta yet.

See [current limits](known-limitations.md), factual [Mario](mario-player-guide.md) and [Stardew](stardew-operator-guide.md) guides, dated verification records and [retained package review](private-beta-review.md).

## Development and release sequence

First connect both AI roles to one useful Stardew activity using current observations/skills and real Codex calls. Include a changed goal or condition that causes another grounded decision. Then integrate Mario strategy and complete supported variation in both games, memory/supervision, ordinary setup and model/game evaluation.

Complete app-owned assets and a new readiness contract, build the successor app, verify the two-game experience on that app and gather the owner's usefulness feedback. Resolve blocking issues and record the local private-beta decision. The engineering plan lists every work package and acceptance gate through that endpoint.

Treat perception/controller repairs as reusable capability work serving these milestones. The next session is not another isolated cave-detour qualification loop. Prior achievements remain valid within their actual scopes.

## Later beta work

Minecraft connection/calibration enters the initial beta with truthful abilities; complete third-game play develops during beta. Advanced guided no-code eligible-game onboarding follows the first two AI experiences. Player recordings/demonstration learning remain preserved but deferred to tentative beta v2. Independent practice/model improvement is later work; pretrained model reasoning plus contextual memory can power the initial beta.

Full Mario coin coverage, larger farms, later levels, cave interiors, wider settings/hardware and broad reliability need later engineering/evidence unless an initial supported activity specifically depends on them. External distribution and signing/notarization beyond the owner's Mac require their own scope.
