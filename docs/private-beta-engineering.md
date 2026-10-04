# Game Companion private-beta engineering plan

## October 4 route progress — instructions delivered through the app

Current source now carries remembered **next-attempt instructions from `/mario` into the emulator**, rather than relying on a newly selected route alone. A compatible stairs failure proposes landing on the left stair top, releasing jump and running across the gap. A later observed pipe failure adds landing and a short run-up on the first pipe before crossing the next pipe. Review/Start binds these supported instructions to a fresh finite attempt; explicit Try again applies them to a fresh disposable session. Player wording, failure attempt IDs, the reviewed instructions, wire fields, controller application and actual outcomes are retained separately.

**Observed result:** the final source and its explicit memory-guided retry both traversed the stairs and later pipes, reached maximum x=2848 and observed the World 1-1 exit with **2 collected coins each**. Native neutral acknowledgment confirmed player handback. These are two consecutive source gameplay finishes, not broad reliability, packaged delivery or full coin coverage. A separately reviewed one-attempt check paused during the pipe crossing, accepted urgent chat Stop, confirmed native neutral handback and cleared retry authority. Hidden/brick, airborne and bonus-room opportunities and the full coin universe remain unknown. Recording/demonstration learning stays deferred to a later beta, tentatively beta v2.

The ordinary chat also accepts “At the stairs land on the left top before jumping across the gap,” stores the original words and includes that instruction in the next reviewed attempt. The supported instruction vocabulary is currently narrow: stair staging/crossing, the failure-derived pipe continuation, and existing opening timing. It does not compile arbitrary gameplay advice. No owner recording, walkthrough or engineering configuration is needed for this supported loop.

See [route verification](gc2-route-verification.md) for exact candidates, failed trials, real gameplay, checks and interruption evidence. Existing accepted routes, editable demonstration work and retained private.2 are preserved.

**One concrete next development step:** implement the app’s bounded flight/reward request, starting with “fly to get the hidden 1up”: observe and explain form/flight prerequisites, review the supported action and report the actual reward separately from reaching its area. Complete remaining Mario learning before Stardew activity delegation.

## October 4 priority update — recording deferred

Player-controlled recording, demonstration playback and the attended stairs walkthrough are deferred to a later beta, tentatively beta v2. Preserve the implemented source and evidence; real demonstration gameplay remains unverified. Recording is optional future work and is not an initial-beta requirement or a gate for current development. No owner recording session is needed now.

**Current continuation:** the app-delivered route-instruction closeout above now owns route progress. Flight/reward objectives and remaining Mario learning follow, then Stardew activity delegation. Recording remains deferred.

## October 4 stairs preparation — owner unavailable

The owner explicitly chose **Unavailable; prepare the workflow**. There is no saved demonstration in this checkout and no active task-owned Mario session. No new gameplay recording or application was performed. Entry reachability, recorded-input application in Mario, stairs traversal, improvement over the earlier x=1652 death, demonstration interruption and real-recording reopening remain live checks.

Preparation repaired observed interface friction: technical trim indexes were replaced by **Start here / End here** on sampled gameplay images and optional game-time seconds. The service converts times to exact frame boundaries, validates the selected sequence using existing compatibility/integrity rules, and retains the full draft after a refused save. Whole-recording saving and older callers remain compatible. Review actions show elapsed recording time. Application results now include stop reason and handback, and explain that a recorded endpoint receipt still needs traversal observation. Entry and drift tolerances were preserved because no real trace supports changing them.

**Recording walkthrough:** deferred to a later beta, tentatively beta v2. No owner recording action is needed now.

Local check evidence is retained under `artifacts/gc2-demonstrations/20261004-preparation/`; it establishes source preparation only. Owner experience and stairs success are unverified.

Local verification: **1,396 tests passed** in the canonical repository gate, including lint/security, generated-file guard, objective/segment contracts and UI renders; **45 focused tests passed**. The ordinary browser check confirmed editable time fields while idle, without launching Mario. UI evidence is `segment-selection.png` and `mario-workflow.png`. The temporary port-8776 server/tab were closed; an unrelated delivery on port 8765 was preserved. These checks do not verify real stairs application.

Updated October 3, 2026 from the owner's product correction. **Deliver conversational Mario coaching and Stardew activity delegation first.** Minecraft becomes the third playable option during beta. Guided advanced-user onboarding of other games follows implementation of the first two gameplay experiences. The [product direction](product-direction.md) owns the intended experience, the [PM handoff](private-beta-pm-handoff.md) owns session pickup, and the [Desktop tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md) owns ordered status and the next action.

## Player demonstrations — October 4 source closeout

The ordinary `/mario` **Let me show you** card now owns player-controlled recording, stop, visual/action review, optional frame-range trimming, named saving, lesson editing, deletion and explicit use. **Play Mario yourself** releases the initial review pause without companion authority. Recording is passive; all gameplay inputs remain the player's. Alive World 1-1 routes or segments are supported, bounded to ten minutes/36,000 frames. Frame pairing retains actual effective buttons, pre/post position, motion, form, air state, level/map identity, lives and coin counter, plus sampled images. Closed-file acknowledgment is required before saving. A replaced/disconnected recording remains raw evidence and cannot be silently saved as complete.

**Open fresh attempt** closes only the released task-owned disposable emulator and opens a fresh paused session. Choose **Use in next attempt**, review its proposal, then **Start** or **yes** approves one attempt of at most three minutes. The experimental balanced approach reaches the segment's entry; matching position (8 pixels), velocity (4 units), form, air and World 1-1/map identity triggers frame-by-frame recorded-button playback. Per-frame state mismatch (24-pixel position tolerance, same motion/form/air/level checks), a missed entry, death, expiry or Stop ends playback with the existing neutral acknowledgment. Segment completion stops immediately; it does not resume the accepted base route or declare a level clear. Enemies are not synchronized: different enemy timing may cause death or drift even when entry matches. This is recorded sequence following, not generalized adaptation or independent training.

Demonstrations live separately in `artifacts/conversation/demonstrations/`; each approved attempt copies the immutable trace hash, name and intended lesson into existing outcome history. Requested use, actual controller application, frames followed, sequence completion, terminal observations and handback remain distinct. Improvement stays unknown unless real gameplay independently establishes it. Demonstration-altered yields do not rank ordinary coin candidates. Reopening restores saved demonstrations and application outcomes, with no recording, selected guidance, plan or input authority. **Stop using demonstration** revokes the attempt and clears future use; deleting a saved demonstration preserves prior attempt/session evidence. Historical accepted routes, profiles, saves and retained packages are unchanged.

The final local gate passed **1,395 tests** plus lint/security/contracts/UI rendering; 73 focused recorder/UI/observation checks and Lua 5.1 compilation passed. Behavioral checks execute the actual recorder/controller with a simulated host. Ordinary browser recording refusal responded immediately after the manager-lock repair. This source slice has no new real gameplay or owner demonstration evidence. The stairs application near x=1652 and whether it helps remain pending separately. See [verification](gc2-demonstration-verification.md) and the [ready recording walkthrough](mario-player-guide.md#let-me-show-you-record-a-route-or-segment).

**Route continuation completed:** the October 4 app-delivered instruction closeout above now owns current status and next development. Demonstration qualification remains deferred to a later beta.

## Delivered source slice — October 3, 2026

GC1 plus the first GC2 conversational Mario coaching loop is implemented through `/mario`. Ask to practice the World 1-1 opening jump, review its proposed stop at x ≥ 160, approve with **yes** or **Start**, coach an earlier/later jump, and request **Try again**. Default scope is three attempts in ten minutes; explicit budgets support one to five attempts. Each trial is at most three minutes and cannot extend the overall deadline. Corrections tune a 0–12 frame delay before the existing 26-frame opening hop and apply on the next compatible attempt. No accepted route is edited.

Guidance and original words persist locally; the interface shows the current delay, retry budget, actual controller application, stop completion and uncertainty. **Reset future guidance** preserves old outcomes. Questions remain input-free. Reopening restores descriptive guidance/history only. Retry explicitly closes the released task-owned disposable emulator, checks the same cartridge, opens fresh paused power-on and revalidates before input. Stop/Take control, process/session replacement, changed scope, expiry and unconfirmed release invalidate retry permission. Urgent chat Stop bypasses the conversation/action locks and cancels pending planning/retry preparation.

The source walkthrough verified zero-frame and three-frame opening attempts, a changed retry without renewed approval, persistent guidance after server reopening, reset with retained history, and `STOP RIGHT NOW WAIT` after a controller pause with neutral acknowledgment and a retained partial result. Both timing variants reached the opening stop; improvement remains unestablished. The first retry failed safely when FCEUX ignored graceful closure; retained failure evidence led to bounded cleanup of the already-neutral task-owned child. The final UI/count repairs and exact source verification are recorded in [coaching verification](gc1-gc2-coaching-verification.md). This is source evidence; private.2 is unchanged and packaging/owner acceptance remain separate.

Remaining scope is explicit: the local contextual English interpreter handles the declared goal/coaching/control families, not general free-form gameplay intelligence. Timing changes are next-attempt only. Full coin coverage, flight/reward objectives, jump-height coaching, later levels and Stardew expansion remain future work. Player demonstration source workflow is delivered above; gameplay qualification is pending.

**Current GC2 slice:** World 1-1 surface coin-route exploration now interprets conversational coin goals, changes scheduled jumps across the level, remembers compatible attempts and reports collected, missed-opportunity lower bounds and unknown coverage. Earlier/longer, later/shorter and balanced candidates are experimental; the balanced candidate preserves the opening through x=700 before later exploration. Counter observations and independent level-exit receipts govern results. No full coin set or 100% completion is established. Preserve finite approval, explicit retries, priority Stop and the delivered opening coaching. **Subsequent demonstration implementation:** delivered above; attended stairs qualification is deferred to a later beta. Flight/reward and wider learning remain GC2; Stardew follows.


## Coin-discovery observed boundary — October 3

Ordinary-interface gameplay observed two failed alternatives (0 coins near x=351/x=582), then a balanced route with 2 coins and maximum x=1652 before death. Memory selected that furthest candidate on an explicit retry; a final attempt collected 2 before urgent Stop near x=1572 and confirmed native handback. Reopening retains discoveries and no authority. Surface coverage through the middle gap is partial; stairs, later pipes, finish and the full coin universe remain unverified. The usable exploration loop is delivered, with honest partial route progress. Tests and exact source/evidence details are in [coaching and discovery verification](gc1-gc2-coaching-verification.md).

## Product contract and sequence

Game Companion is a chatbot that interprets the player's intentions, observes the game, plays within an agreed scope, accepts coaching and returns control. The owner should be able to watch real gameplay and direct it through conversation. Setup, profiles, demonstrations and reports support that loop.

1. **Initial beta, Mario:** watched play, route discovery across attempts/lives, durable coaching, selected real-time changes, immediate interruption and inspectable results.
2. **Initial beta, Stardew:** delegate clicking and navigation activities, discuss a short plan for the next few minutes, approve it, watch execution and correct or interrupt it.
3. **Minecraft connection in the initial beta, gameplay development during beta:** carry forward usable connection/setup with accurate available abilities, extend the Stardew-style conversation/action loop into spatial play, and deliver a completed third playable option by beta end. The retained wall is one useful integration case.
4. **After the first two gameplay experiences are implemented:** develop guided advanced-user setup that can add an eligible game without writing code. Minecraft helps establish reusable observation/control/teaching needs. Teaching demonstrations and the onboarding interaction will be discussed at that stage.
5. **Later:** independent Mario practice/self-improvement. Learning from supervised attempts and owner coaching belongs in the initial Mario experience; an autonomous training service does not.

Typed conversation is the initial input. Game coverage can begin with explicitly supported levels/areas, but the initial experiences must include meaningful goal-directed play and adjustments. The acceptance examples below cannot be replaced by selecting an unchanged base route or completing only a settings wizard. Requests that need an unavailable ability must explain the prerequisite and offer an actionable next step.

## Current implementation and exact evidence

The documentation-overhaul starting checkout was clean at `482374ff83b202c6ac3c2ceae6ae1711dfe11c68`. This identifies the source inspected for the gap inventory; subsequent documentation and implementation change its source identity. Reconcile HEAD, working tree and build/source manifest at each session.

| Area | Reusable foundation | Product gap |
| --- | --- | --- |
| Mario play | FCEUX, accepted cumulative route, observation/takeover, watchable play, pause/reclaim, revision acknowledgments, saved variants/results | Current grammar edits only declared opening paths, stop points and playback speed. Experimental opening jump timing and cross-attempt guidance are integrated; full coin coverage and hidden-item objectives remain |
| Mario learning | Compatible run library, repeated-trouble patterns, candidate review and engineering promotion | Opening coaching now changes the next controller attempt and retains comparable stop outcomes; broader route learning remains |
| Conversation | Typed plans, context/identity, review/Start, corrections and local model gateway | Mario/Stardew intent handling is a narrow deterministic grammar. Add contextual interpretation and task orchestration, keeping executable validation separate |
| Immediate controls | Dedicated Stop/Take control and bounded native/emulator release | Mario urgent chat Stop now has a priority path, cancellation generation and confirmed paused-play release evidence |
| Stardew play | Screen observations, isolated copies, tool/resource accounting, farm navigation, reviewed actions/outcomes | Two prepared farm/profile/display pairings only; general crop tasks, planting-location judgment and cave/exploration activities are absent |
| Setup and history | Existing game selection, profile lifecycle, settings/permissions guidance, saved outcomes and feedback | New gameplay, coaching memory and reconnection need one understandable conversation-led product flow |
| Minecraft | Calibration/camera, scene/native/wall components, settings/window/setup owners | Current source and retained private.2 enable calibration/camera only. Aim/move/place/wall remain disabled |
| Other-game onboarding | Declarative profiles, finite skills, catalog/provider seams and fixture contributor scaffolding | Contributor installation creates no live game perception/control. Playable guided no-code onboarding remains future work |

Preserve retained packages and evidence. Private.2 is `/Users/michaelfuscoletti/Desktop/beat-mario/dist/private-beta/0.2.0-private.2/Game Companion.app`, version `0.2.0-private.2`, bundle build `20002`, source SHA-256 `230c206e51a46014e457458a8e4c0036cbd501f9a3e228f04103f1d70473fa60`. Its manifest enables Minecraft calibration/camera and disables aim/move/place/wall. It predates the October 1 source repairs. Its packaged native Minecraft smoke is unfinished. The retained private.1 OpenTTD result and September 26 Stardew final-return repair qualify their own candidates/configurations. The October 1 1,327-test local gate verifies that source; it does not prove the corrected product or a new package. See [review records](private-beta-review.md).

## Existing owners to reuse

| Concern | Owners | Required integration |
| --- | --- | --- |
| Conversation and plans | `request_planning.py`, `conversation_service.py`, `profile_conversation.py`, `model_gateway.py` | Contextual intent, questions, clarification, coaching and activity planning; bounded structured proposals |
| Mario actions/control | `mario_route_plan.py`, `mario_route_contract.py`, `mario_plan_runtime.py`, `live_observation.py`, `takeover.py`, FCEUX Lua controllers | State-dependent supported actions, selected live edits, next-attempt tuning and independent priority reclaim |
| Attempt/learning memory | `run_library.py`, `learning.py`, `learning_promotion.py`, `custom_variants.py`, `objective_profiles.py` | Durable route/life discoveries, coach intent, applied parameters, outcome comparison and resettable experimental profiles |
| Stardew observation/actions | `stardew_planning.py`, `stardew_runtime.py`, `stardew_companion.py`, `stardew_perception.py`, farm perception/navigation/tasks modules | Broader observed targets, activity navigation, resource-aware plans and observable task results |
| Stardew isolation/input | `stardew_setup.py`, `stardew_input.py` | Verified disposable/copy workflow, primary-save preservation, foreground-safe input and release |
| Shared sessions and catalog | `companion_session.py`, `companion_catalog.py`, `lab_ui.py`, `conversation_ui.py` | One local product/session ownership model, truthful game abilities, safe switching and responsive conversation |
| Setup, profiles, reports | `player_setup.py`, `player_onboarding.py`, `player_setup_ui.py`, `player_store.py` | Guide actual supported setup and persist inspectable configuration/history without live authority |
| Native observation/control | `screen_host.py`, `native_host.py`, `ordinary_input.py`, `input_guardian.py`, `feedback_contracts.py`, `skill_runtime.py` | Exact selected window, fresh feedback, bounded actions and independent release |
| Delivery and readiness | `beta_readiness.py`, `delivery.py`, `app_runtime.py`, `scripts/build_private_beta.py` | New versioned contracts/package/guide for the corrected two-game experience |

Game-specific mechanics, observations and action rules stay adapter-owned. The model interprets goals and proposes plans; the fast game controller owns frame/action timing and verified effects. The model cannot issue arbitrary code/input or declare success. Immediate controls must not wait for model inference, conversation locks or advanced setup parsing. Preserve the accepted route registry and existing safety boundaries while developing separate experimental gameplay profiles.

## Engineering sessions and acceptance

### GC1 — Shared conversation and immediate control

**Delivered first slice:** the integrated opening-jump loop above. Extend contextual coverage only alongside new executable adapter capabilities; broader conversation and GC3 remain pending.

- Interpret the owner's original words in current game/attempt/goal context. Separate questions, goal requests, current-attempt commands, next-attempt coaching and emergencies. Select and document a usable backend through the existing gateway; deterministic control handling remains independent. Do not present phrase matching as general intention understanding.
- Acknowledge the understood goal and any ambiguity. Preserve original wording alongside interpreted intent, the executable proposal, reviewed scope and later applied result.
- Route urgent Stop/Take control directly to cancellation/release, including `STOP RIGHT NOW WAIT`, casing, urgency and punctuation variations. Cover idle, pending inference/review, active and paused execution. Never grant new authority after a late reply.
- Show what applies now versus next attempt, pending/applied/refused status and why. A selected real-time edit applies only at its supported action boundary; timing corrections that arrive too late are saved for the next eligible attempt.
- Preserve typed draft/focus, visible direct controls and inspectable outcomes. In Stardew, chat focus must safely pause/release native input before discussion; continuation needs fresh eligibility and approval.

**Exit:** ordinary question/goal/correction conversations and urgent interruption run through the shared product interface, with meaningful affected parsing/orchestration/control-race tests. A short freshly authorized Mario check confirms actual release and an acknowledged applied change; unit-only work stays labeled as such.

### GC2 — Mario watched play, coaching and route learning

Deliver the owner's examples as goal-directed gameplay on clearly identified initial levels/segments:

| Owner request | Required behavior and evidence |
| --- | --- |
| `lets find a 100% coin route to the end` | Establish the level/route scope and coin-accounting basis, retaining unknown coverage during discovery; explore/retry under a reviewed attempt/life budget; retain discoveries and compare routes. Show collected, missed and uncertain coins. A 100% claim requires a complete observed checklist and reaching the reviewed end |
| `youre jumping too early wait a few more frames` | Bind feedback to the relevant jump/hazard and attempt; infer or clarify the timing adjustment; show changed parameters, apply at an eligible live boundary or next attempt, and compare the actual outcome |
| `fly to get the hidden 1up` | Resolve the objective against current game state and the implemented flight mechanic; check or obtain the required ability within reviewed scope; execute the supported approach and verify the reward. If a prerequisite is missing, explain it without silently running the base route |
| `STOP RIGHT NOW WAIT` | Stop/release immediately through GC1, revoke pending edits and authority, retain progress and show confirmed handback |

Implementation should proceed as useful slices: one state-aware playable segment with real timing coaching → durable next-attempt application and route/life memory → coin-route exploration and supported flight/reward objectives. Expand supported actions/entries enough to make these conversations useful. An added preset or playback-speed change alone is not completion.

A reviewed finite attempt/life budget may cover multiple compatible retries. Re-observe eligibility after each life/reset; do not require another Start for every retry while the same scope and authority remain valid. New approval is required after reclaim, invalidated authority or a material scope change. Supported coaching inside the reviewed adjustment range can apply with acknowledgment; changes beyond it require review.

Persist level/game/backend compatibility, route discoveries, relevant state/landmarks, attempts/lives used, user feedback in their words, interpretation, proposed/applied parameter changes, outcomes and uncertainty. Failed attempts and deaths are learning evidence; they do not erase successful discoveries or imply improvement. Store this with existing run/history owners; give the user inspect/reset/undo for future coaching.

Ordinary coached attempts may use versioned, bounded experimental controller parameters/actions after fresh review and runtime checks. They must not require the user to edit repository files or use Route Lab. Historical accepted-route promotion retains its separate reliability/replay/exact-diff process; experimental learning cannot overwrite that registry or inherit its reliability label.

**Exit:** watch real play, issue a supported live command, stop, coach a failed/early jump, run another approved attempt and visibly see the changed behavior. Coin-route and flight cases have actual observed progress/reward results in their supported scope. Reopen coaching/history, start a fresh compatible session and apply remembered guidance. Report limits honestly; a full-completion preset fallback cannot satisfy route discovery. Owner usefulness is evaluated separately from technical implementation.

### GC3 — Stardew conversational activity delegation

Use a short loop: request → current observations → understandable plan for the next few minutes → explicit approval → play and report → discuss/correct/approve continuation. A contextual `yes` authorizes only the current displayed plan, session, targets, protection and limits. A changed plan invalidates that approval.

Deliver activity slices against a documented playable farm/area, extending beyond the two engineering fixtures:

- `time to water the tomatos`: find the relevant observed crops, distinguish dry/already-watered/unknown, confirm the watering tool and water/energy, navigate, water and report what remains. Implement needed tool selection/refill if advertised; shortages give a useful remedy.
- `lets explore and find a good spot to plant corn`: inspect reachable terrain, season/resources and location constraints; propose and explain a suitable spot. Finding a spot does not imply purchasing seeds or planting before approval. If planting is approved and supported, verify soil/seed/crop effects.
- `lets go explore that cave`: identify or clarify the destination, agree the near-term navigation/exploration boundary and resource/risk limits, travel using supported observed navigation, then check in. State the extent of cave gameplay actually implemented; reaching an entrance and exploring inside are distinct outcomes.
- Accept changes such as another destination, a different crop or conserving energy; safely pause/release for conversation, observe remaining work and obtain fresh approval. Stop/Take control bypass planning.

Extend perception and navigation from fixed plot IDs/corridors to observed supported targets and activities. Reuse existing ledgers, clearance, resource and per-action result checks. Do not infer valid corn/tomato gameplay from seed-name parsing or existing parsnip evidence. Starting coverage/settings must be explicit and usable without engineer-authored target coordinates.

Keep primary saves untouched. Build the user-selected disposable or verified copy workflow and backups before ordinary farm use; existing prepared copies remain regression assets. No purchases, sales, gifts, story choices, overwrites or other consequential actions are inferred from a general activity request. Implement and review additional actions when the activity actually requires them.

**Exit:** the ordinary UI proposes and receives approval for useful multi-action activities, executes supported watering/location/exploration work with observed outcomes, accepts a correction/check-in, stops with actual release, and reopens understandable history. Fresh evidence identifies farm/settings/source and assistance. Engineering preparation alone is not the delivered experience.

### GC4 — Initial two-game beta delivery and owner review

Package the implemented GC1–GC3 experience with accurate capabilities, prerequisites and guide. Use one coherent game-selection/conversation surface and actionable setup. Verify the initial beta on the exact package: open → select Mario → goal/play/coach/retry/Stop → neutral switch → Stardew request/plan/yes/activity/correction/Stop → save/reopen → feedback preview → verified shutdown.

Update versioned readiness/scenario contracts to the corrected requirements. Current `personal-beta-v3` and PB records retain their original meaning; create a new version rather than repurposing historical pass results. No existing readiness command currently proves GC1–GC4.

Build a distinctly identified successor. Before running the existing builder, fix its version/output and hardcoded bundle-build assumptions so it cannot replace private.1/private.2. Include all runtime/adapter/controller resources and a workable game/calibration setup; ignored developer-only assets cannot be the ordinary product's hidden prerequisite. Keep game files, personal saves and credentials outside the package.

**Exit:** actual two-game gameplay, conversation, coaching persistence, input release, history and local reporting work through the packaged ordinary UI with retained evidence. Carry forward and check the initial Minecraft connection/setup with its actual capability labels; unfinished full Minecraft play stays in GC5. Record engineer assistance as product issues. Owner product feedback and a later launch/distribution decision remain separate; do not fill an acceptance verdict from tests.

### GC5 — Minecraft third playable option during beta

After the initial two-game experience is implemented, resume Minecraft connection and useful gameplay through the same conversational activity flow. Connect/setup capability belongs in the initial beta; full Minecraft play develops during beta and is the beta-end third-game outcome. Keep any initial camera/calibration-only limitation visible.

Reuse current scene/native/session/wall work. Finish efficient observed aim/movement/addition, preparation guidance, protection, task composition and truthful handback; enable each family only after affected practical checks. The existing 7 × 3 × 1 wall with a centered 1 × 2 doorway has 19 occupied cells and two empty cells and preserves marked blocks. It is one acceptance case, with observed material/cells/doorway/protection/stop point. Later Minecraft goals should express useful player intent through discussion and revised plans.

**Exit by beta end:** Minecraft is a usable third game through ordinary connect → request → approve → play → correct/Stop → outcome/history, with supported coverage stated and actual gameplay evidence.

### GC6 — Advanced-user no-code onboarding, deferred

Start this work only after Mario coaching and Stardew delegation are implemented. Keep the confirmed requirement: an advanced user adds an eligible game through guided setup without writing code. At that stage, discuss the appropriate controls, observations, demonstrations and practice with the owner; no demonstration request or onboarding implementation is required for the current pickup.

Use Minecraft to identify what can be shared. Existing fixture scaffolds/configuration are reusable data foundations, not a playable onboarding result. The future flow must end in an actually usable, inspectable game/task setup, with explicit unavailable abilities and observed practice outcomes. Preserve finite runtime authority and adapter-owned semantics. Feasibility and eligible game coverage need their own bounded implementation/evidence.

## Guided setup and how-to — PB5

For GC1–GC4, guide the user to actual Mario/Stardew play, explain prerequisites/remedies at the relevant step, and make controls and current capabilities readable. Reopening restores configuration and learning/history only; game connection, observation, approval and input authority are fresh. Keep questions input-free and ordinary users out of schemas, repository patches and terminal-based task configuration. The player guides describe current behavior separately from these targets.

Carry forward Minecraft window connection/calibration and truthful capability labels into GC4 initial-beta setup; check that entry on the exact successor package. Useful third-game activities/building preparation and completed Minecraft gameplay remain GC5. Advanced-user other-game onboarding is GC6. Profile naming/importing and fixture conformance do not teach an unimplemented game action.

## Focused checks, failure handling and evidence

Run tests appropriate to changed parsing, contextual interpretation, action eligibility, coaching application, persistence, superseded approvals, command races, perception, navigation and outcome accounting. Begin with affected tests listed in the adapter contracts and [development guide](development.md). Use `.venv/bin/python -m pytest -q <affected tests>` and `git diff --check`; run `PYTHON=.venv/bin/python scripts/validate_phase0.sh` once for an integrated source handoff, repeating after relevant changes/failures. Documentation-only updates need documentation/link checks, not a gameplay campaign.

Use short fresh real-game checks for each enabled behavior. Preserve historical successes/failures and avoid repeating unrelated accepted campaigns. New controllers/shared boundaries get their affected route/control regressions. Model evaluation should test contextual/paraphrased goals and coaching beyond the exact examples, while uncertain actions remain reviewable/refused.

Before native work, establish current process/window/display/settings, disposable world/farm/session and a current exclusive-input window with the owner. Historical permissions/availability are not present authorization. Stop/release when the owner reclaims the Mac. Future gameplay still needs explicit Start/approval for its reviewed scope.

At the first unmet safety or outcome requirement, stop and release, save the partial result and sanitized failure evidence, make the bounded repair, then start from a fresh compatible boundary. Unconfirmed release blocks further native work. A sent command, model explanation, candidate record or test count is not gameplay success. An unknown action effect is not blindly retried.

Record exact source/build/profile/backend/settings, request/approval, observations, attempted/applied actions, resources/lives, confirmed outcomes, uncertainty, release and help supplied. Keep local/fixture checks, real gameplay, packaged workflow, owner feedback and launch decision distinct. Never manufacture 100% coverage or current-state eligibility from historical evidence.

## Delivery integration — PB10

GC4 owns the next initial-beta package; GC5/GC6 add later versions. Preserve the retained apps, manifests, supplied guides and evidence. New packages need distinct version/source/build identity and matching guide, accurate runtime flags, local report preview and verified shutdown. Broader hardware/settings/reliability are beta learning, with actual supported prerequisites documented.

Do not commit/push, distribute, invite/contact testers or purchase access without a direct applicable user instruction. Preserve uncommitted work, credentials, worlds/saves, profiles, reports and evidence. The October 3 update is a product/documentation reset; it makes no gameplay, package, owner acceptance or distribution claim.

## Immediate engineering pickup

Continue GC2 by improving World 1-1 traversal through the stairs and toward the finish using the existing conversational coaching/discovery loop. Make routine engineering choices autonomously. Recording and demonstration qualification are deferred to a later beta, tentatively beta v2, and do not block Mario, Stardew or initial-beta delivery. Then continue remaining Mario objectives and GC3 Stardew activities.

## Retained private.1 review record — October 1

A local versioned Mac review build and guide were prepared; the [owner review](private-beta-review.md) binds the actual packaged candidate and checks. The PHL OpenTTD one-repayment smoke passed with independent outcomes, neutral handback and profile/history reopening. Packaging OCR/configuration/cursor defects were repaired and affected checks repeated. In private.1, Minecraft native input was disabled and visible material/ground/empty-cell integration and useful wall execution were unfinished. The canonical gate ran once. Native work ended with the app/game closed and the Mac released. This record applies to private.1 and is not current Minecraft availability or full private-beta launch acceptance.


## Retained private.2 Minecraft integration record — October 1

The separate private.2 candidate preserves private.1 and its successful packaged OpenTTD smoke. At this checkpoint PHL 346E2C was connected and native work used only the visibly verified disposable Creative world. Gameplay used vanilla Minecraft Java 26.3, an 854 × 508 point selected window, native 1× PHL capture retained with exact 2× glyph decoding, and app-created directional calibration. Personal Survival worlds remained untouched. These environment and process observations describe the checkpoint; current availability must be established for the next native check.

Live calibration measured eight signed responses near 0.15 degrees per unit. A bounded camera task and centered reachable-face aiming completed with independently observed settling and native HID release. Creative inventory, selected Oak Planks and the resumed-world hotbar texture were independently read from pixels. One 60 ms addition produced an observed Oak Planks block at (5, −60, 10). A result serialization defect occurred after that addition; the before/after evidence and release receipt were preserved, the reporter repaired, and a subsequent check confirmed the existing block without another click. Air/ground intervals touching at their boundary now qualify clearance consistently.

Ordinary profile save/reopen/edit, calibration, window/display selection, world-bound region review, pointed-block protection, bounded requests, saved corrections, priority Stop/Take control, history and local feedback are integrated. Reopening restores configuration only. Movement and wall completion are still being checked; unverified families remain unavailable in the runtime and UI. A movement probe observed a position change during camera inspection and stopped before any movement command; its cause is not established. The guard now rejects translation during aiming and held physical keys/buttons before pulses. Historical r7 motion remains unattributed; the owner explicitly identified their interruption in a separate aim attempt.

This checkpoint superseded an earlier PHL-absent/game-closed observation. No packaged Minecraft wall smoke or final wall success was established, and at that checkpoint no commit, push, distribution or tester contact had occurred. The later `fc019d5` commit records the implementation; it does not change the retained package or establish wall completion. Resume from the current handoff above.

### Retained short checks after the clearance repair

The saved addition was re-inspected through the native port and reported completed/existing with no further placement. The repaired reporter serializes actual shared input commands before writing outcomes/history; write failures now preserve the observed gameplay result and release instead of suggesting a retry. The ordinary pointed-protection action is connected to setup and tested.

A nearby-movement inspection stopped on changed player position before any movement command. A tighter position guard now checks every aiming feedback frame and refuses held keys/buttons before camera pulses. Its next check retained a stable position but exhausted the 180-second total inspection budget before moving. Camera composition now uses one axis per child, at most 24 degrees, with individual pulses capped at 64 units, independent predicted-response checks, fresh captures and settling. No task budget or freshness guard was relaxed.

Key-up-only recovery did not establish stillness. A retained frame shows a large animal next to the player; collision is a plausible source of the current displacement, not proof of its cause or of the historical r7 motion. A later bounded disposable setup move ended one block lower than expected and preparation stopped. No jump or wall placement followed. The area needs a clear, flat starting position before further useful checks. Input was released after every attempt; no worker or held key/button remained.

Retained native evidence is in `artifacts/private-beta/private2-checkpoint/brief-state4/`: `movement-confirmation`, `movement-stationary-guard-recheck`, `key-up-recovery`, and `platform-clear-space-preparation`. Private.2 enabled camera/calibration and left aiming, nearby movement, additions and wall Start unavailable. Native work paused at that checkpoint. The preserved private.1 packaged OpenTTD smoke is unchanged. At that checkpoint the feature flags left building unavailable and packaged wall completion was the next proposed result. New sessions follow the October 3 GC1–GC4 sequence above.
