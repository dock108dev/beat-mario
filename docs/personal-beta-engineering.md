# Personal beta engineering packet

Updated September 23, 2026. **B2 implementation and evidence are tracked against this contract. B1 remains complete; owner acceptance and B3/B4 live Stardew work remain pending.** The [Desktop tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md) owns current slice status; this packet owns implementation contracts and checks. The V2 roadmap records the existing foundation and its historical proof.

The implemented module/API mapping, launch flow and B3 prerequisites are in the [B2 conversation guide](b2-conversation-guide.md). Exact integrated results and retained evidence are recorded in the Desktop tracker; code presence does not establish B2 PASS.

## Product loop and scope

Choose Mario or Stardew, describe a task in ordinary typed language, inspect the proposed actions, start supported play, adjust the task through conversation, and receive an honest result. Mario must support visible play while typing, selectable playback speed, and useful custom path changes derived from the single existing route. Stardew must support watering, harvesting, planting and selected-debris clearing in one useful routine on a disposable copy.

“Faster,” “quickest,” and “100% clear” are requested objectives, not separate routes already in storage. Initially every such selection resolves to the existing `world_8_finish_game` base route, with an explicit fallback explanation. Keep the requested objective separate from the plan that can actually execute. The game need not already have an optimal or full-completion solution for the selector to work. A player can load the base, discuss changes and build a saved variant during supported play. Do not reject the entire session just because the requested ideal route is unavailable.

Typed conversation is the required beta input. Microphone/voice transcription is not required by “talk and adjust.” Playback multiplier controls simulation presentation rate; optimizing a route concerns game-frame duration, decisions and measured outcomes. Increasing the multiplier does not produce a better route record. No arbitrary-state universal Mario solver or prebuilt optimal/100% route collection is promised.

## Inspected foundation and original gaps

Source baseline: clean `main` at `022bfd618e5c78754364e6c548a9a62555fed8e0`, matching remote main at this packet's start. This packet and related documentation then change the working tree. Existing hosted results apply to the baseline; they do not qualify new beta behavior.

| Concern | Existing owner / evidence | Required change |
| --- | --- | --- |
| Text commands | [`commands.py`](../src/smb3_agent/commands.py) recognizes narrow run/show phrases and optional speed | Shared conversational intent, corrections, references, clarification and reviewable plans; retain legacy CLI behavior |
| One Mario base route | [`world_8_finish_game.yaml`](../data/goals/world_8_finish_game.yaml) and [route status](route-status.md) describe the cumulative 26-segment route | Preset-to-base resolution and saved variants; earlier prefix goals are coverage boundaries, not independent optimized routes |
| Objective truth | [`objective_profiles.py`](../src/smb3_agent/objective_profiles.py), [`mario.yaml`](../data/profiles/mario.yaml) and [profile guide](objective-profiles.md) | Requested intent versus measured objective; exact completion universe before any 100% claim. Existing observable-progress checklist is not collectible completion |
| Live Mario | [`live_observation.py`](../src/smb3_agent/live_observation.py), [`takeover.py`](../src/smb3_agent/takeover.py), [`fceux_live_takeover.lua`](../scripts/fceux_live_takeover.lua) | Revision-bound commands, resumable supported boundaries, acknowledged speed/pause, same-process edited execution |
| Current executable policies | `supported_solutions()` allows World 1-1 remainder and exact-fresh-start full route | Current full route cannot simply be restarted at an arbitrary mid-run state; implement explicit supported segment entry/resume contracts |
| Speed controls | Lab has run/watch speed choices; legacy text commands carry speed | Existing launch-time/watch controls do not establish dynamic speed changes in a live companion session. Prove actual engine control and input isolation early |
| Route engineering | [`route_patch.py`](../src/smb3_agent/route_patch.py), [patch schema](route-patch-schema.md), learning/promotion | Existing source-patch review/worktree lifecycle is not live path editing. Use versioned data plans for player edits; preserve source patches for engineering changes |
| History | [`run_library.py`](../src/smb3_agent/run_library.py), [`learning.py`](../src/smb3_agent/learning.py), [`learning_promotion.py`](../src/smb3_agent/learning_promotion.py) | Persist base/variant/revision, requested objective, speed intervals and actual outcomes; retain candidate/executable and player/agent/mixed distinctions |
| Stardew live foundation | [`stardew_adapter.py`](../src/smb3_agent/stardew_adapter.py), [`stardew_companion.py`](../src/smb3_agent/stardew_companion.py), [guide](stardew-operator-guide.md) | Public UI/CLI are inspection-only; `OrdinaryInputDriver` has injectable emitters, not a configured live driver or perception system |
| Farm actions | [`operator.yaml`](../data/stardew/operator.yaml), [`evidence-contract.yaml`](../data/stardew/evidence-contract.yaml), fixtures | Watering-only ledgers and guards must evolve into explicit harvest/plant/clear contracts, not blanket permission to use tools |
| Shared product | [`companion_session.py`](../src/smb3_agent/companion_session.py), [`companion_catalog.py`](../src/smb3_agent/companion_catalog.py), [`lab_ui.py`](../src/smb3_agent/lab_ui.py) | One conversation/plan flow with adapter-owned capabilities; responsive status, controls, revision history and safe switching |
| Qualification | [`scenarios.py`](../src/smb3_agent/scenarios.py), [existing campaign](../data/scenarios/final-campaign.yaml), both owner pilots | Existing executable campaign requires older watering/onboarding obligations and omits new route/NLP/farm cases. Version the active beta contracts; preserve historical manifests |

## Shared request and plan contract — B2.1

Add cohesive modules for conversation/plan ownership instead of growing `lab_ui.py` into a parser, planner and executor. B2 now implements `request_planning.py`, `mario_route_plan.py`, `stardew_planning.py` and the runtime/service modules mapped in the B2 guide. The following requirements remain the implementation contract; the original gap inventory above describes the prepared baseline. Reuse existing session, capability, history and observation owners; no parallel game-state database.

The plan must bind:

- request ID, original text, conversation/game/session identity and observation reference;
- requested objective and normalized intent, material ambiguities and unsupported portions;
- base route/task identity and version, variant ID, revision and parent revision;
- adapter-validated actions/targets, preconditions, expected observed outcomes and resource/protection rules;
- effective boundary, stop point, requested and acknowledged speed when supported;
- plain-language changes, execution eligibility, evidence classification and authorization scope.

Plans carry typed actions from the adapter's declared capabilities. Text/model output cannot directly issue controller input, execute shell/code, edit repository files, change saves, declare success or promote itself. Advisory chat has no controller effects. Record requests and results without exposing local secret paths or copying whole saves into prompts.

Start with a local bounded intent/planning layer: support useful paraphrases, ordered multi-action requests, negation (“leave those crops”), corrections (“the other patch”), references to the selected visible target, and follow-ups within the current game. Reuse deterministic parsing for direct controls. The engineer selects an implementation backend based on these cases; a handful of exact phrase aliases does not complete NLP. If a semantic model is needed, keep it behind this contract and record its requirements. No paid/cloud service, credential access or external save/screen transmission is assumed. Missing backend access must not block deterministic plan/control/adapter work.

Plain controls such as Stop, Pause, Resume, Take control and a supported speed request should not trigger a repeated permission interview. Starting agent play authorizes a bounded plan. An unambiguous edit inside a reviewed session's allowed edit scope may itself request application; show the exact change and acknowledge when it takes effect. A suggestion, question or ambiguous request stays a preview. Materially expanded targets/resources or scope need one clear Apply decision. Every applied revision still receives fresh internal authority bound to current state; routine steps do not repeatedly ask the owner.

## Mario live route contract — B2.2 through B2.4

### Presets and honest route identity

Display **Requested: quickest · Loaded: existing base route · Optimized variant: not available** or equivalent concise copy. “Faster/fastest/quickest” may normalize to the same optimization intent while preserving the original wording. “100% clear” must display that the existing route does not establish full completion. If the user asks to measure full completion, clarify the relevant level/route and finite objectives; unspecified or unobservable requirements remain unknown. Finishing the base never silently marks the requested 100% objective complete.

The fallback must resolve through the real goal/solution registry; do not clone accepted metadata into invented accepted variants. Preserve all existing goal IDs and accepted prefixes. Loading a route means selecting/preparing its plan. Starting a new game or resetting current progress is a separate explicit action; do not implicitly reload fresh power-on because a mid-run start is unsupported.

Extend execution eligibility deliberately: a session plan composed of implemented, validated action primitives and compatible entry/exit contracts can be authorized for its bounded live task without being promoted as an accepted fastest route. Preserve the old accepted-solution gate for its existing policies. An unvalidated primitive or arbitrary captured trace remains non-executable; the planner cannot assert its own safety or reliability. This distinction permits useful live customization without fabricating historical route qualification.

### Continued play and conversational edits

1. Display the game and the conversation/plan together, with current controller owner and persistent Pause/Take control. In authorized agent mode the current plan can continue while the player types or asks a question. Typed characters must never become Mario input.
2. Parse an edit against the selected base/variant and current observation. Show a short changed-actions summary, affected route boundary and any unsupported portion. A full-screen engineering diff is not the product interaction.
3. Queue one identified pending revision, with explicit replacement/cancel semantics. Apply at a supported safe boundary using compare-and-swap against the current revision and fresh state; completed path history stays immutable. A late, duplicate or stale command must never execute against a different point in the game.
4. Neutralize and acknowledge the boundary before changing the executable plan. Resume in the same process from a supported entry contract. If an edit cannot safely take effect yet, show its boundary; if the boundary is missed, execution fails or the bounded wait expires, stop and offer supported recovery. Do not inject savestates, teleport or silently replay the fresh-start script.
5. The player can cancel a pending edit or revert future steps to an earlier compatible plan. Reverting a plan cannot undo actions already performed in the game. Reclaim always wins over pending edit, Resume or speed commands.
6. Save the custom variant with its parent, actual edited steps and evidence status. Reloading it later requires compatible state and fresh authorization. A saved name or successful parse is not executable or reliability promotion.

**Minimum custom-path delivery:** support at least one real alternative traversal within a bounded, observable segment, in addition to changing a supported destination/stop point. A concrete first target is a named path choice within World 1-1 using the existing observable progress anchors, with newly implemented entry/exit conditions and ordinary-input execution. Exact waypoints/controller parameters are engineering choices verified in B2.2. Text annotations, speed changes and stop-point changes alone do not satisfy custom paths. If the first chosen alternative cannot be implemented safely, finish another explicit playable alternative; do not relabel the feature complete.

Arbitrary new levels, unobserved objects and routes requiring an unimplemented controller can be retained as non-executable ideas with a clear explanation. The beta must still deliver the supported path-edit loop above; unsupported-case handling is not a substitute for it. Additional objectives/routes can grow from valid retained runs and later reviewed variants without altering historical route evidence.

### Speed, focus and timing

Engineering defaults: start at 1×; target a useful selectable set such as 1×/2×/4×, then advertise only rates actually supported and checked. Exact rates are implementation choices, not claimed current capability. At least normal speed and one faster rate, including a change during play, must work for the requested beta loop. Existing Lab values up to 100× are not evidence that the new loop can safely offer them. Reject unsupported rates visibly; no silent substitution.

Record requested multiplier, applied acknowledgment, frame intervals and measured wall-clock rate; show when machine load prevents achieving the target. Keep game-frame route timing separate from wall-clock playback time. Freshness, timeout, edit deadlines and reclaim responsiveness use appropriate wall-clock bounds even when simulation speed changes. A paused emulator still needs responsive stop/detach controls; a paused frame loop must not deadlock command processing. Restore the documented normal/player setting on handback or disclose a failed restore.

Prove Mario's process-specific emulator input while the text field has keyboard focus. Do not solve chat focus by injecting global keystrokes. Window/process loss, game occlusion that invalidates required observations and unrelated application input remain distinct from intentional chat focus. Stardew's foreground-only ordinary-input safety is not automatically relaxed: pause/neutralize that adapter before chat focus would send inputs elsewhere.

## Stardew live and farm contract — B3 and B4

B3 must deliver actual setup: owner-selected save source, separately identified disposable copy, clear launch/selection instructions, visible supported game/window, screen observations and configured ordinary-input driver. Reuse copy verification and hashes. Never inspect/migrate a primary save merely to manufacture proof of isolation. Do not assume the game can directly load an arbitrary copy path: verify the actual supported save-selection workflow and persistence location before enabling input. No copying, game launch or owner-data inspection occurs in this planning task.

Screen-only perception is a real implementation dependency. Fixtures and manual annotations may support development but cannot be represented as automatic live observation. Bound the supported farm/viewport state, identify crops/plots/debris, tools/seeds/inventory and relevant resources from actual visible evidence, handle scrolling/occlusion, and stop on insufficient confidence. If reliable coverage is not yet possible, retain partial engineering and the exact missing perception capability rather than marking the adapter usable.

| Task | Scope and observed completion |
| --- | --- |
| Water | Preserve the exact initial planted set, water state, energy/can/refill accounting and selected return point. Existing watering proof does not cover other tasks |
| Harvest | Select visibly eligible ready crops; collect through ordinary input; reconcile inventory and crop post-state, including crops that remain after harvest. Full inventory and uncertain crop identity stop or produce an honest partial result |
| Plant | Select owned seed type/count and explicit valid plots; check season/plot constraints when observable; reconcile seeds consumed and newly planted tiles. No seed purchase or broad terrain conversion implied |
| Clear | Select debris IDs/area and suitable tools; protect crops, buildings and unselected objects; reconcile removal, energy and acquired items. Ambiguous targets cannot authorize blind swinging |
| Routine | Resolve dependencies such as harvest/clear before planting and water after planting; recompute the watering set for newly planted crops. Handle tool/seed shortages, full inventory, time/energy limits, cancellation and the reviewed stop point |

Use task-specific preconditions, ledgers and postconditions under the existing Stardew ownership/evidence boundary. Version the watering-only rules where generalization changes meaning; preserve old fixtures as historical watering cases. Do not append harvest/clear purposes to the watering allowlist without implementing their observations and accounting. Task ordering comes from selected scope and dependencies, not one fixed universal farm script.

Natural-language farm corrections use the same request/revision semantics, but targets and safety are Stardew-owned. After a reset or copy change, all observations, plans that depend on old state and volatile authorization become stale. No purchases, sales, gifts, story decisions, sleeping or primary-save overwrite are inferred from a farming request. Unknown outcomes remain unknown; partial work remains visible.

## Engineering slices and dependencies

Keep the existing B-stage IDs. B2 now includes the required Mario custom-route experience; B3/B4 retain Stardew ownership; B6 verifies the new Mario behavior rather than repeating the old prepared walkthrough as if it covered it.

| Slice | Implementable deliverable | Completion check |
| --- | --- | --- |
| B1 | This source inventory, contracts, dependencies and revised qualification mapping | Documentation reviewed; no implementation claimed |
| B2.1 | Shared intent/plan schema, bounded conversation, correction/clarification, preset fallback and adapter validation | Paraphrases, context, negation, ambiguity, stale plans, wrong-game references and no-input previews; original text retained |
| B2.2 | Mario execution seam: revision protocol, segment resume boundaries, process-scoped input, pause/reclaim and dynamic speed; implement first alternate path primitive | Same-process 1×/faster transition and chat focus; acknowledged boundary application; true alternate traversal; missed boundary/timeout/reclaim tests |
| B2.3 | Ordinary Mario conversation and plan UI on the shared product surface | Select any requested preset → visible base fallback → start → type while play continues → edit/acknowledgment → handback; no Lab patch workflow needed |
| B2.4 | Saved custom variants, parent/revision history, undo of pending/future changes and outcome/comparison integration | Save/reopen compatible variant; original remains intact; execution eligibility and mixed/completion labels honest; fresh authority on reload |
| B3 | Live Stardew setup, perception, ordinary input and watering | Actual copied-save watering through ordinary UI with resource reconciliation, primary preservation and immediate reclaim |
| B4.1–B4.3 | Harvest, plant and selected-debris clear, one completed task contract at a time | Each performs visible work and covers its relevant inventory/resource/uncertainty failures |
| B4.4 | Combined farm routine and conversational adjustment | Useful ordered routine, including newly planted crop watering, partial results, stop/return and safe handback |
| B5 | Shared game switching, conversation/plan/history integration and recovery | Mario edit session → neutral switch → Stardew routine → saved histories, with no game-state/authority leakage |
| B6 | Mario live proof and focused repairs | Base fallback, actual path edits, speed changes, manual/agent transitions, recoverable errors and unchanged accepted-route regressions where affected |
| B7 | Expansion/setup guidance | Explain supported games and future adapter work; no third working game gate |
| B8 | Versioned beta scenarios/readiness, exact candidate and usable personal Mac delivery | Required engineering/visible evidence, launch/relaunch, prerequisites, cleanup and known limits bound to the delivered source/artifact |
| B9 | Complete owner review, repairs and personal-beta handoff | Owner judges Mario conversation/editing and Stardew usefulness on identified candidate; explicit ACCEPT PERSONAL BETA / REVISE / STOP |

Execute B2.1 → B2.2 → B2.3 → B2.4 → B3 → B4 → B5, with focused checks and slice status updated as each becomes useful. Begin scenario contract reconciliation in B2.1 and extend it with each delivered feature; B8 closes the cumulative qualification rather than discovering missing cases. Carry B6's Mario proof checklist while implementing B2. B7 is a small guide, not a detour into adapter infrastructure. Finish B6–B9 once the product paths exist. Tonight is the intended work session, not a promised release deadline.

## Qualification reconciliation and focused checks

The current executable `final-campaign.yaml`, owner pilots and `scenarios.py` describe the prior V2 contract. Do not run their existing readiness PASS and call this beta complete. Implement a versioned current-beta scenario contract/manifest and matching validator together, preserving legacy schemas and manifests for historical replay/inspection. Keep existing safety/regression checks; make third-game onboarding completion optional for this beta. No requirement is satisfied by deleting a failing case or filling owner fields.

| Beta case | Required evidence |
| --- | --- |
| NLP and plan truth | Supported paraphrases, corrections, multi-step tasks, negation, questions versus commands, wrong/stale references and unsupported requests; adapter rejection has no input side effect |
| Preset fallback | All named intents resolve to the same real base initially; clear fallback; no invented optimum or 100% result |
| Real live edit | At least one actual alternate traversal plus changed supported destination/stop; same-process state continuity, event order and game-observed result |
| Speed and typing | Normal/faster execution, mid-play speed change, requested/applied/measured distinction, text-focus isolation, wall-clock timeouts and responsive reclaim including paused state |
| Revision and recovery | Duplicate/out-of-order/stale edits, supersession, cancel, boundary miss, restart, lost process, parser failure and reclaim race preserve original route/history and stop correctly |
| Stardew breadth | Real copied-save watering/harvest/plant/clear and combined ordering, resource changes, negative paths, primary preservation and honest partial completion |
| Shared product | Stable typing/focus/draft during polling, visible current/pending plans, safe switching, save/reopen histories, accessible control labels and usable layout |
| Exact delivery and owner | Reproducible local launch or a justified personal package, declared game/engine prerequisites, no restored control authority; neutral actual-use review and explicit verdict |

Start from relevant existing tests: `test_takeover.py`, `test_run_library.py`, `test_objective_profiles.py`, `test_learning.py`, `test_route_patch.py`, `test_stardew_adapter.py`, `test_stardew_companion.py`, `test_companion_catalog.py`, `test_scenarios.py` and `test_lab_ui.py`. Add behavior-focused tests for new contracts; do not merely snapshot implementation text. Use the repository's locked `.venv` and the canonical `PYTHON=.venv/bin/python scripts/validate_phase0.sh` when cumulative changes require its non-live gate. Its artifact/render outputs are engineering evidence, not gameplay or owner acceptance.

Keep live engineering attempts, review-only demonstrations, historical authoritative reliability, player/agent/mixed results and owner feedback separate. Custom edited or speed-adjusted play cannot inherit the accepted base route's reliability status. Select affected historical route regressions from actual changed controllers/contracts; do not repeat every accepted campaign for documentation or isolated presentation edits. No always-on agent or automatic unattended campaign is required.

The current app is a local loopback Python/UI product with external game prerequisites, not an already packaged standalone Mac app. B8 should deliver the simplest usable, identified local launcher/package and instructions for this personal beta; signing/notarization or public distribution is a separate scope. No bundled proprietary game assets. Distinguish engineering delivery readiness from the owner's final beta decision.

## First engineering handoff

Start **B2.1**, then **B2.2**, in the current repository. Re-read the tracker, current Git state and this packet; preserve these documentation edits and all existing route/evidence/game inputs. Implement the smallest shared request/plan contract that supports both games, with honest Mario preset fallback and real conversation correction. Establish the Mario runtime seam and alternate traversal before calling the UI complete. Continue through the stated dependent slices under the engineering task's authorization, report concrete blockers while doing independent work, and do not reopen settled product-scope questions.

This preparation task changes documentation only. It does not launch games, inspect or copy owner saves, change executable scenarios, install a model/provider, run gameplay, commit, push or publish. Later technical results and owner verdicts must be recorded when they actually occur.
