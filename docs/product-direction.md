# Game Companion product direction

## October 4 priority update — recording deferred

Player-controlled recording, demonstration playback and the attended stairs walkthrough are deferred to a later beta, tentatively beta v2. Preserve the implemented source and evidence; real demonstration gameplay remains unverified. Recording is optional future work and is not an initial-beta requirement or a gate for current development. No owner recording session is needed now.

**Next development:** improve World 1-1 route traversal through the stairs and toward the finish using the existing conversational coaching and discovery loop. Engineering chooses the approach without requiring a player demonstration. Continue observed coin accounting and remembered route adjustments, then the remaining Mario objectives and Stardew activities.

Updated October 3, 2026 from the owner's confirmed intent. The [engineering plan](private-beta-engineering.md) defines implementation and acceptance; the [PM handoff](private-beta-pm-handoff.md) and [Desktop tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md) identify the next sessions.

## The product

**Game Companion is a chatbot that interprets your intentions and plays for you.** You watch, discuss goals, coach its behavior and reclaim control whenever needed. It observes the current game, explains its understanding, acts within the agreed scope, reports what happened and carries useful guidance into future attempts.

The core loop is conversation → grounded plan → approval → real play → observation → coaching/correction → revised play → remembered result. Tell, Show and Do remain useful functions inside that experience; the primary product is a conversational player. Setup, profiles and evidence make that experience usable and understandable.

## Initial beta: Mario watched play and coaching

The user watches Mario play and coaches either the next attempt or selected behavior in the current attempt. Examples supplied by the owner:

- `lets find a 100% coin route to the end`
- `youre jumping too early wait a few more frames`
- `fly to get the hidden 1up`
- `STOP RIGHT NOW WAIT`

Mario should explore and train routes across attempts/lives, retain discoveries and user guidance, adjust supported behavior and make the effect visible. A timing correction is attached to the relevant event, with clear acknowledgment of whether it applies now or next time. An item objective requires the relevant game mechanic and current prerequisites. Immediate Stop releases control independently of planning.

The initial coverage may name supported levels/segments, but it must include meaningful route discovery, real coaching changes and supported game objectives. A route's coin coverage remains explicit: collected, missed and unknown. A 100% claim requires a complete observed coin universe and the reviewed finish. Independent practice to improve itself comes later; supervised route learning and durable coaching belong to the initial beta.

## Initial beta: Stardew activity delegation

Stardew generally replaces clicking actions through a slower, more immediate conversation. The owner asks for an activity, the app proposes what it will do over the next few minutes, and the owner approves. It then plays, reports progress, checks in and accepts changes.

Owner examples:

- `lets explore and find a good spot to plant corn`
- `time to water the tomatos`
- `lets go explore that cave`

The companion needs to identify relevant crops/tools/resources and reachable locations, make useful choices, explain its near-term plan and execute supported actions/navigation. Choosing a planting spot is distinct from approval to plant or purchase seeds. Exploration needs an understood destination, scope and check-in. Unknown state and shortages produce clear questions/remedies. Conversational changes pause/release input safely and renew the plan/approval as needed.

Prepared-farm watering/harvest/plant/clear routines are reusable foundations. The delivered experience must handle meaningful activities through observations and conversation rather than require engineering plot IDs and a fixed routine. Supported farm/area/settings coverage is stated honestly. Personal saves remain protected; ordinary review uses a user-selected disposable or verified copy workflow with backups.

## During beta: Minecraft and later game onboarding

After the first two gameplay experiences are implemented, the initial beta can connect Minecraft through the same product with its available abilities clearly labeled. Minecraft grows into a completed third playable option by beta end. It extends Stardew's activity planning into spatial play, including building, observation, protection, corrections and outcome reporting. The retained 7 × 3 × 1 wall/doorway is one useful building case.

Minecraft also guides the later advanced-user onboarding utility: add an eligible game through guided setup without writing code. That work and its teaching/demonstration discussion are deferred until Mario coaching and Stardew delegation are implemented. The onboarding result must be an actually usable game/task setup with clear supported abilities and practice results. A name, capability declaration or installed fixture scaffold is not sufficient.

## Current foundations and gaps

| Area | Current implementation | Required product development |
| --- | --- | --- |
| Mario | Accepted cumulative route, current observations, bounded takeover, opening path/stop/speed edits and variant/result history | Contextual goal interpretation, coin-route discovery, jump/flight coaching, cross-attempt learning and selected real-time actions |
| Learning | Local compatible attempts, patterns and engineering review/promotion candidates | Connect coach intent and applied changes to future experimental play, comparisons, user inspection/reset and durable route/life memory |
| Stardew | Two prepared farm/profile pairings with observed bounded watering and selected harvest/plant/water/stone work | Broader activity perception/navigation, useful choices, short approved plans and conversational check-ins |
| Conversation/control | Typed plans, explicit review/Start, direct Stop/Take control and local model gateway | Contextual conversational player and reliable urgent chat interruption; exact `STOP RIGHT NOW WAIT` is currently unrecognized by the chat parser |
| Minecraft | Setup/profile/history/feedback, current source progress/remedies, calibration and small camera requests | Later third-game integration; aim/move/place/wall remain disabled |
| Other-game setup | Profile/skill/provider foundations and data-only fixture contributor scaffold | Later guided playable no-code onboarding |

These are source/document inspection findings, not new live gameplay results. The [Mario guide](mario-player-guide.md), [Stardew guide](stardew-operator-guide.md) and [known limitations](known-limitations.md) own actual current use. The retained private.2 package supports Minecraft calibration/camera and predates newer setup/control source repairs. Package manifests and [review records](private-beta-review.md) bind capabilities to exact builds. No current package demonstrates the full corrected initial beta.

## Shared product requirements

- One understandable local game-selection and conversation experience; game mechanics remain adapter-owned.
- Questions produce no gameplay input. Approval covers a displayed current plan; superseded plans and late replies cannot revive authority.
- Immediate Stop/Take control and release confirmation remain available during play, inference, errors and pauses.
- The model interprets goals; fast controller feedback handles action timing and verifies effects. A persuasive response is not completion.
- Memory includes original coaching, interpretation, what actually changed, route/attempt outcomes and uncertainty. The user can inspect/reset future guidance.
- Completed, partial, failed and stopped outcomes reflect actual observed work and remaining work. Reopening history restores no live input authority.
- Personal saves/worlds, existing profiles, credentials, historical accepted routes, packages and evidence are preserved.
- Current implementation, local checks, real gameplay, packaged behavior, owner usefulness and launch/distribution decisions remain separate.

## Delivery order and acceptance

GC1 establishes conversation and priority control; GC2 delivers Mario coaching/route learning; GC3 delivers Stardew delegation; GC4 packages and reviews that initial two-game beta. GC5 develops Minecraft during beta. GC6 develops advanced-user no-code onboarding after the first two gameplay experiences. Independent self-training is later work.

Initial-beta acceptance is a user actually watching/coaching Mario and delegating useful Stardew activities through the delivered app, with interruption, remembered feedback, honest results and reopening. Use focused changed-behavior checks and short fresh gameplay evidence; evaluate broader variation/reliability during beta. Owner feedback is collected against the exact candidate, and launch/distribution needs its own explicit owner decision.

The historical V2/B/PB contracts retain their original evidence and meanings. They inform reuse; the October 3 requirements own new work. See the [engineering session plan](private-beta-engineering.md) for scope, code owners, acceptance examples, failure handling and checks.
