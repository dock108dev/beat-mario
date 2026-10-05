# GC3 conversational watering — October 4, 2026

## Delivered source scope

Ordinary `/stardew`: watering request → fresh qualified Day 2 farm observation → connected dry patch or target clarification → displayed resource/route/120-second plan → contextual yes bound to displayed version or Review/Start → existing observed navigation and watering outcomes → discussion/Stop with native authority revoked → fresh remaining-work proposal/approval → retained plan and actual/uncertain outcome without reopened control.

The complete planted set stays the accounting/protection boundary. A reviewed subset controls task completion and navigation; unselected dry crops remain dry and are not reported completed. Wet baseline tiles are skipped. Unknown water/species, tool/water/energy shortages and unreachable routes explain remedies before approval. Tool selection/refill are manual prerequisites. The time limit includes return; expiration can leave work or return incomplete. B4 combined routines and Mario remain separate.

No new observation profile, crop species, farm, lighting or arbitrary terrain support is claimed. This activity uses existing qualified Day 2 screen recognition/viewpoints and selected-can prerequisites. Corn/tomato identification, planting-location discussion, cave exploration and automatic refill remain unsupported. Mario's real route/flight evidence and full-coin/broader-reliability limits remain intact; recording remains deferred to later beta, tentatively v2.

## Local verification

Evidence directory: `artifacts/gc3-watering/20261004/`.

- Initial canonical gate: 1,453 tests passed plus lint, tracked credential/game-asset scan, generated-file guard, objective/segment contracts and Mario/Lab/Stardew renders.
- Focused final watering/planning/runtime/conversation checks: 82 passed. These cover dry/wet/unknown/ambiguous targets, species uncertainty, resource remedies, changed-plan/stale yes rejection, discussion release, subset completion without watering neighbors, observed resource effects, expiration/handback and saved plan/outcome with no reopened authority. Existing checks cover native-input cancellation, focus/process loss and postcondition failures.
- Final canonical gate: **1,454 tests passed**, plus lint/security/generated-file/contracts/renders. A final browser-input guard change also releases input when typing races a pending Start/yes response; the affected GC3/Stardew/Mario UI checks then passed **52 tests** (`ui-focused.log`). `git diff --check` and lint passed. Source hashes are retained in `source-sha256.json`.
- Frozen Day 2 and Day 5 source hashes were independently recomputed and match the prepared registry (`prepared-source-preservation.json`).
- The first final-gate attempt passed 1,453 tests but failed its tracked-document-link guard on this new verification file. Intent-to-add registration repaired the link check; no commit or push was made. The failed log remains retained.

Synthetic tests establish behavior contracts, not real watering.

## Actual gameplay closeout — current source

The launch/window blocker is resolved using the existing process-bound native backend and bounded ordinary input. Added **Show game window** (activation only) and explicit **Reconnect open disposable game** (exact retained PID/start/isolation identity, exactly one copy; no authority restored). The ordinary interface describes Load → Pilot/B3Test, left from bed to door, down to porch, slot-3 watering can, Check isolated farm session, Connect profile. Manual selection/refill stay prerequisites.

Final live copy: `artifacts/stardew-engineering/eb85ce6da0fd4f1a95ffe118ca0566ef/`, launch `7bbc01ca8d7ed777c995c4947ebafdba`, verified save session `75bff774eb149a45f469755c2da40d9b`, `pilot-day2-75pct-v1`. Current source server on port 8777, qualified 1512×949 window at (0,33), zoom 75%, UI 100%, daylight, locked toolbar/default WASD/hit marker. Frozen source hash `1a71568b81ebb901c5fc289d4c2bfb0972db8c05325463a7487dad549eae3128`.

Through ordinary UI:

1. “Please water the crops” observed 15 dry crops, energy 270 and water 40; several patches correctly required clarification. “Water the left patch” selected six observed dry tiles. Review/Start approved the displayed 120-second plan and farmhouse return.
2. `stardew-do-386fc2f89d12b3d5`: navigation and **two confirmed dry→watered** changes. Typing “How much is left?” released input and confirmed player handback. Reply reported two watered/four remaining, energy 266, water 38.
3. “Water the remaining dry crops in the left patch” freshly proposed four tiles, excluding wet tiles. Review/Start authorized revised continuation without manual repositioning. `stardew-do-7387ea93724baa2d`: one additional tile confirmed; urgent Stop retained three remaining and confirmed neutral input/player handback, energy 264, water 37.
4. Fresh remaining-work request, review and contextual **yes** authorized `stardew-do-bdc8bc2559997c75`: three more tiles watered, **zero remaining within this continuation**, return independently confirmed, completed and neutral handback. Final actual scene: **six selected wet tiles, nine unselected dry tiles**, energy **258**, water **34**, six tool uses, zero refills. Newly performed work remains per-attempt; wet baselines are not credited again.
5. Page reload and Saved results reopened the actual plan/outcome. Restarting Companion and reopening Saved results retained all three attempts, completion, resource ledger and reviewed plan. New runtime is **unconfigured/player-owned**, plan null, reviewed false, Start disabled: no control resumes. Before restart the disposable game was placed in its manual menu with the clock paused. It exited during the server restart; the unchanged disposable Day 2 save and retained watering evidence were preserved (`disposable-save-preservation.json`). Companion history is saved; no in-game overnight save was performed or promised.

Evidence: `artifacts/gc3-watering/20261004-gameplay/verification-summary.json`, `live-progress.json`, `continuation-approved.json`, `urgent-stop.json`, `completed.json`, `reopened.json`, `current-source-sha256.json`, `prepared-source-preservation.json`; per-command before/after pixels, native timing, resource/target postconditions and terminal outcomes under the final copy's `watering-attempts/`. Final released farm screenshot `191312265683-before.png` shows the wet selected patch and farmhouse return. The ordinary UI shows six wet and nine dry targets after completion. Saved history retains stopped attempts separately.

## Repairs, checks and assistance

Practical repairs: readable stable connected-patch labels survive stale observations; wet neighbors do not split the named patch; explicit reconnect/show controls and actionable setup; natural progress question; typing releases native input; focusing a control button no longer sends an unrelated chat pause; fresh review can recover an interrupted position only inside an already-qualified cardinal corridor, first reaching its endpoint before taking another path. Off-corridor/uncertain positions still refuse. Unsupported night recognition gives daylight/menu/reload advice rather than weakening recognition.

Final canonical gate: **1,459 passed**, lint, tracked credential/game-asset scan, generated-file guard, objective/segment contracts and Mario/Lab/Stardew renders (`canonical.log`). Repair subset: **51 passed** for GC3/viewpoint/setup checks. Earlier expanded repair pass: 131 passed before the last two reconnect tests. Synthetic checks cover retained PID reuse/multiple-copy refusal, stale patch labels without eligibility, natural check-in without replanning, corridor-only recovery, resource/target/approval/outcome/persistence contracts. After closeout edits, CI/documentation and route-patch checks passed **49 tests** (`documentation.log`); final lint and `git diff --check` passed. Frozen Day 2 and Day 5 hashes match; personal saves were never selected and remain sandbox-denied. Existing Mario changes/evidence were preserved.

Engineering assistance was limited to visible manual preparation with the existing isolated-process guard, bounded key/click pulses and neutralization: Load, walking bed→door→porch and selecting the can. These steps are explained in the player interface. No save XML/game memory edits or gameplay bypasses. The earlier copy (`dbc1c28...`) was recognized, watered three tiles and used to expose the interruption gap; it exited before this continuation. Its partial evidence remains. A long setup reached night; the same unsaved Day 2 was reloaded through the game's normal title menu. The first launch checkpoint (`ab667fab...`) failed computer-control attachment and never established authority; that is historical, not the current blocker.

Limitations: this is current-source qualification for the supported prepared Day 2 farm, not arbitrary-farm/species/package/release qualification. Manual tool selection/refill and menu clock pause remain explicit prerequisites. The exact farm/day/view/settings remain required. Unknown crops, off-route positions and shortages refuse with remedies. Tomato/corn, planting-location discussion and cave exploration follow later. Mario full coin coverage and broader reliability remain unknown; recording remains deferred to tentative beta v2.

Next development step: build observed planting-location discussion on the supported farm, preserving selected-target protection and reviewed approval, before cave exploration.
