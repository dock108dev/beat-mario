# Game Companion private-beta PM handoff

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

Updated October 3, 2026. **The initial beta is conversational Mario coaching and Stardew delegation.** The owner watches Mario play and coaches current/next attempts; Stardew handles useful activities after a short discussed plan and approval. The initial beta can connect Minecraft with current capabilities clearly labeled; it becomes the completed third playable option by beta end. Advanced-user guided no-code game onboarding follows implementation of the first two gameplay experiences.

Read [product direction](product-direction.md), [engineering plan](private-beta-engineering.md) and [Desktop next steps](/Users/michaelfuscoletti/Desktop/mario_next_steps.md). This is the active pickup for upcoming sessions.

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

Mario now has the integrated experimental opening-jump coaching loop described above, plus the retained controller/route and path/stop/speed foundations. Experimental surface coin-route discovery is implemented; full coin coverage and flight/reward actions remain unfinished.

Stardew has retained successful watering and selected farm actions, including the September 26 final-return repair. Its supported live work is two prepared farm/profile/display configurations. General crop/location/exploration behavior and short activity/check-in conversation remain engineering work. Typing in another foreground window currently stops Stardew input; the product needs a clear pause/discuss/replan/approve flow.

The exact urgent Stop phrase now takes the priority cancellation/release path in Mario. Its paused-play handback has source evidence; the retained package has not been rebuilt.

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
