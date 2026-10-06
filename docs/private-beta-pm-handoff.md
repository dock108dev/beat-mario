# Game Companion active engineering handoff

Updated October 5, 2026 after connected-loop implementation and bounded native trials. Read [product direction](product-direction.md), [architecture](agent-architecture.md), the complete [engineering plan](private-beta-engineering.md).

## Active objective

Build an actual conversational AI player for the owner's personal Mac. There are two responsibilities: contextual language-to-game interpretation and game understanding/action selection/replanning. Use the installed, signed-in Codex CLI first; one backend may serve both roles.

The ordinary source app now uses contextual Codex language inference for Mario and Stardew. Day 2 watering additionally uses a gameplay model to select approved targets, predicts effects, observes watering and resources, then chooses again. Mario additionally has a model-directed early segment that consumes current game images and native effects, composes maneuvers beyond the opening and retrieves compatible coaching. Existing controllers own timing, validation and input release. Reconnaissance now composes model-selected observations, viewpoint movement and return in source; its native acceptance is pending. Day 5 strategy retains its deterministic implementation. Read [the verification record](gc-ai-loop-verification.md) before treating any gate as complete.

## Next session

GC-S native acceptance remains pending. GC-U source setup adds catalog Codex readiness/refresh, macOS permission status, direct Mario/Stardew setup, explicit installation selection, Finder FCEUX discovery and corrected Mario setup returns. Preparation binds every step to its displayed process/window/bounds, moves the SDL pointer before clicking, and releases input after each step. A fresh isolated Day 2 copy reached the porch through the ordinary controls. Supported reported bounds were restored, but the rendered toolbar remains below retained calibration and its water bar is clipped; selected-can recognition refused. Guarded screen-rectangle capture did not resolve that rendering mismatch. Stop confirmed neutral input and player handback; the test game was closed without saving. No reconnaissance trial began. Canonical validation passed 1659 tests and all checks. Repair the disposable renderer/window layout without changing resource guards, then run the finite two-investigation/Stop/Take-control/reopening set and focused Mario/Stardew usability walkthrough. GC-S/GC-U source qualification remains pending. The initial GC-D inventory covers 90 referenced resources; packaging, exact-app GC-Q/GC-D qualification and recording remain separate, with recording deferred to tentative beta v2.

Mario’s supported World 1-1 x≥700 segment has 3/3 native completions on the final unchanged source, with independently observed alive/grounded arrival and neutral handback for each passing run. The set includes two compatible-coaching trials and a walking-on-flat/raised-block landing preference variation. Earlier failures remain failed under their own candidate identities. Running maneuvers, a feedback-bounded run-up, native object/projectile/motion facts, neutral waiting and after-frame arrival checks address the retained blockers. This small engineering set establishes observed scope, not broad reliability. Prepared Stardew watering acceptance is preserved. See [verification](gc-ai-loop-verification.md). Wider Mario coverage, exact-package qualification and owner release remain open.

GC-S final-source actual-model simulated set completed 2/2 with different observation/movement composition and fresh effects driving later decisions. Native setup stopped before gameplay; no native reconnaissance return, variation, interruption or reopening acceptance is inferred. See [GC-S verification](gc-s-recon-verification.md).

## Full sequence to release

1. GC-A0/A1: intent/state/decision/skill contracts and Codex provider lifecycle.
2. GC-A2–A5: contextual interpretation, semantic observation, composable skills and adaptive decisions; prove one connected Stardew activity early.
3. GC-A6: supervision, compatible coaching/memory and recovery.
4. GC-M/GC-S: actual model influence and supported variation in both game experiences.
5. GC-U/GC-Q: ordinary setup/UI, measured model/game/control evaluation and regressions.
6. GC-D1/D2: successor personal Mac app, required assets, new readiness contract and exact-package walkthrough.
7. GC-R: local quick start, feedback/update path, usefulness review and owner's private-beta decision.

The worklist enumerates the technical tasks and exits for every package. Packaging/launch scope is the owner's Mac first. No hosted application service, universal game support, custom model training or external distribution campaign is required.

## Existing behavior and limits

Mario has observed opening coaching, authored stairs/pipe guidance with two World 1-1 exits and two supported sky 1UP collections. Full coin coverage, arbitrary language-to-action execution and broader reliability are unknown.

Stardew has observed selected watering, live planting discussion and a supported eastern inspection round trip. The Farm Cave has newer manual route/handback evidence, but ordinary companion delegation remains unverified. Preserve the manual foundation and avoid presenting it as a completed conversational round trip.

Retained private.1/private.2 are historical review packages. No current package demonstrates the new Codex-driven two-game beta. Recording source work remains preserved and deferred to tentative beta v2. Minecraft connection/calibration has its own retained capability limits; full Minecraft gameplay and guided new-game onboarding follow later.

See the dated [Mario](gc2-route-verification.md), [flight](gc2-flight-verification.md), [watering](gc3-watering-verification.md), [inspection](gc3-inspection-verification.md), [cave](gc3-cave-verification.md) and [package](private-beta-review.md) records for actual evidence. Do not relabel those results as model-driven or package proof.

## Closeout standard

Report what model decisions affected real execution, what independent observations established, checks, user-facing limits and the next work package. Preserve cancellation, finite authority, current-vs-historical facts, saves, credentials, profiles and evidence. Game switches/reopening never transfer input authority.

Documentation reflects requirements and status; it does not qualify gameplay. Product usefulness feedback and the final local beta decision are separate from source/model/game/package checks. No outreach or external sharing is implied by this handoff.

October 5 connected closeout: both repaired Stardew watering variants return with neutral handback, and genuinely pending gameplay Stop produces no continuation. Mario visual model choices reach x=353 across raised terrain; the short-hop variation changes actual behavior, and after restart a later compatible attempt applies remembered 8-frame advice with matching native receipts. Both arrival at x=700 and improvement remain unconfirmed. Native pending Stop/reopening preserve control; canonical gate passes 1610 tests plus lint/scans/routes/renders. See the exact verification evidence; no package was qualified.

## October 5 source maintenance — SSOT enforcement

FCEUX setup, live observation, Show, engineering harness and default reliability preflight now share `executable_discovery.py`; missing discovery refuses launch without a bare-name fallback. README, runtime/configuration and the SSOT map describe the implemented Codex roles and retained diagnostic/controller boundaries. Focused validation passed 218 synthetic component tests (208 before this pass), Ruff and syntax/whitespace checks. This source maintenance changes the candidate; prior native/package evidence keeps its original identity. GC-S renderer repair and pending acceptance remain the next gameplay work. See [SSOT decisions](ssot.md#october-5-ssot-enforcement-pass).
