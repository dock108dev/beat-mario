# Game Companion private-beta PM handoff

Updated October 3, 2026. **The initial beta is conversational Mario coaching and Stardew delegation.** The owner watches Mario play and coaches current/next attempts; Stardew handles useful activities after a short discussed plan and approval. The initial beta can connect Minecraft with current capabilities clearly labeled; it becomes the completed third playable option by beta end. Advanced-user guided no-code game onboarding follows implementation of the first two gameplay experiences.

Read [product direction](product-direction.md), [engineering plan](private-beta-engineering.md) and [Desktop next steps](/Users/michaelfuscoletti/Desktop/mario_next_steps.md). This is the active pickup for upcoming sessions.

## Owner requirements

| Game/area | Intended experience |
| --- | --- |
| Mario | `lets find a 100% coin route to the end`; explore and remember routes across attempts/lives |
| Mario coaching | `youre jumping too early wait a few more frames`; actual supported behavior changes now or next attempt with clear acknowledgment |
| Mario objective | `fly to get the hidden 1up`; interpret the goal, check the ability and execute/verify supported gameplay |
| Control | `STOP RIGHT NOW WAIT`; immediate release, cancellation and preserved outcome |
| Stardew | `lets explore and find a good spot to plant corn`, `time to water the tomatos`, `lets go explore that cave`; propose the next few minutes, receive approval, play and discuss changes |
| Minecraft | Connect in the initial beta with accurate available abilities; extend the slower activity loop into spatial play and finish a third game by beta end |
| Later onboarding | An advanced user adds an eligible game without writing code; defer implementation and teaching discussion until the first two experiences work |

Supervised Mario learning and remembered coaching are initial-beta features. Independent practice/self-improvement comes later. A limited initial level/farm/area scope is acceptable when explicit and useful; substituting an unchanged route or engineering fixture for the requested experience is not completion.

## Current status and reusable work

Mario has actual controller/route foundations, current observations, watchable play, bounded path/stop/speed changes and history. It lacks integrated coin-route discovery, conversational jump/flight adjustments and durable coaching application. Learning records exist separately from ordinary conversational execution.

Stardew has retained successful watering and selected farm actions, including the September 26 final-return repair. Its supported live work is two prepared farm/profile/display configurations. General crop/location/exploration behavior and short activity/check-in conversation remain engineering work. Typing in another foreground window currently stops Stardew input; the product needs a clear pause/discuss/replan/approve flow.

The exact urgent Stop phrase above does not match the current chat parser. Direct Stop/Take control foundations exist; priority natural-language interruption is the first concrete repair.

Minecraft's setup, calibration/camera and current-source progress/control repairs are useful retained work. Aim/move/place/wall remain disabled. Existing contributor onboarding produces fixture scaffolding, not a new playable game. Preserve these foundations for their later stages.

## Exact package and evidence boundaries

- Retained app: `/Users/michaelfuscoletti/Desktop/beat-mario/dist/private-beta/0.2.0-private.2/Game Companion.app`.
- Version/build: `0.2.0-private.2` / bundle `20002`; Apple Silicon, local ad-hoc signature, not notarized.
- Source SHA-256: `230c206e51a46014e457458a8e4c0036cbd501f9a3e228f04103f1d70473fa60`. Adjacent manifest, Quick Start and Owner Review are authoritative for that package.
- Minecraft calibration/camera available; aim/move/place/wall unavailable. It predates October 1 source repairs and has no packaged native Minecraft wall success.
- Retained private.1 OpenTTD smoke and B-series Mario/Stardew results apply to their own identities/settings. They do not qualify the corrected conversational product or a successor package.
- The October 1 canonical local gate's 1,327 tests are source verification. No new gameplay, package or owner acceptance was established by this October 3 documentation update.

The documentation work began on clean HEAD `482374ff83b202c6ac3c2ceae6ae1711dfe11c68`; future sessions must reconcile the working tree/source identity and exact running build. See [review status](private-beta-review.md).

## Ordered engineering pickup

1. **GC1 + first GC2 slice:** urgent chat Stop, contextual intent/coaching, one watched supported Mario attempt with an actual jump-timing change and next-attempt memory. Use existing service/runtime/controller seams. Retain what was requested, applied and observed.
2. **Finish GC2:** useful coin-route exploration across lives/attempts, supported flight/reward objectives, selected real-time commands and inspectable persisted coaching/history.
3. **GC3:** Stardew observed crop/tool/resource targets, activity navigation and useful watering/location/exploration plans; explicit approval, safe conversation, correction and outcomes.
4. **GC4:** distinct two-game package/guide/readiness contract; ordinary Mario coaching → neutral switch → Stardew activity → controls → reopening/report/shutdown walkthrough. Record every engineer intervention.
5. **GC5/GC6 during later beta work:** Minecraft playable integration and advanced-user onboarding, after the first two experiences are implemented. Do not begin no-code demonstration requests in the current sessions.

The [engineering plan](private-beta-engineering.md) gives code owners, task acceptance, affected checks and failure handling. Update the tracker at each session with the exact candidate, actual behavior, unresolved gap and next action.

## Review and release

The October 3 discussion is confirmed product direction and proposed-work authorization, not a gameplay review or launch acceptance. The opening walkthrough paused before the owner reported using an app screen. Do not manufacture observed UX/gameplay feedback or a tester decision from it. [Review notes](private-beta-review.md) preserve the owner's words separately from engineering interpretation.

For the next actual app review, guide one action at a time, allow the app's guidance first, ask one short feedback question and wait. Record the user's words, screen, expected/actual behavior and help supplied. Let the owner correct the closing summary before recording it. Product feedback remains separate from a launch/distribution verdict.

Preserve player data, profiles, packages, credentials, accepted routes, uncommitted work and all evidence. Native work needs fresh session/window/settings and current exclusive-input availability; release immediately when the owner reclaims the Mac. No commit/push, distribution, invitations or tester contact is authorized by this handoff.
