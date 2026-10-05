# Player demonstration recording and application — source verification

## October 4 priority update — recording deferred

Player-controlled recording, demonstration playback and the attended stairs walkthrough are deferred to a later beta, tentatively beta v2. Preserve the implemented source and evidence; real demonstration gameplay remains unverified. Recording is optional future work and is not an initial-beta requirement or a gate for current development. No owner recording session is needed now.

**Current development:** follow the [two-role AI roadmap](private-beta-engineering.md), starting with Codex-backed interpretation and adaptive Stardew decisions, then Mario strategy integration and delivery. Supported stairs/pipe traversal and sky 1UP collection have later source-gameplay records. Recording and demonstration qualification remain deferred; no owner recording action is needed.

## October 4 stairs preparation — owner unavailable

The owner explicitly chose **Unavailable; prepare the workflow**. There is no saved demonstration in this checkout and no active task-owned Mario session. No new gameplay recording or application was performed. Entry reachability, recorded-input application in Mario, stairs traversal, improvement over the earlier x=1652 death, demonstration interruption and real-recording reopening remain live checks.

Preparation repaired observed interface friction: technical trim indexes were replaced by **Start here / End here** on sampled gameplay images and optional game-time seconds. The service converts times to exact frame boundaries, validates the selected sequence using existing compatibility/integrity rules, and retains the full draft after a refused save. Whole-recording saving and older callers remain compatible. Review actions show elapsed recording time. Application results now include stop reason and handback, and explain that a recorded endpoint receipt still needs traversal observation. Entry and drift tolerances were preserved because no real trace supports changing them.

**Recording walkthrough:** deferred to a later beta, tentatively beta v2. No owner recording action is needed now.

Local check evidence is retained under `artifacts/gc2-demonstrations/20261004-preparation/`; it establishes source preparation only. Owner experience and stairs success are unverified.

Local verification: **1,396 tests passed** in the canonical repository gate, including lint/security, generated-file guard, objective/segment contracts and UI renders; **45 focused tests passed**. The ordinary browser check confirmed editable time fields while idle, without launching Mario. UI evidence is `segment-selection.png` and `mario-workflow.png`. The temporary port-8776 server/tab were closed; an unrelated delivery on port 8765 was preserved. These checks do not verify real stairs application.

Implementation began October 3, 2026; final closeout October 4, 2026. The incoming uncommitted opening-coaching/coin-discovery implementation and evidence were preserved. HEAD is `5d4ed6280c65657c0c3184660ce514c9eef0a477`; HEAD alone does not identify this source. Runtime source hashes and local check outputs live in `artifacts/gc2-demonstrations/20261003/`.

## Implemented interaction

Ordinary `/mario` supports player play, passive frame-paired recording, explicit stop acknowledgment, sampled game-image/action review, optional segment trimming, saving a name/lesson, reviewing/editing/deleting, fresh disposable attempt preparation, explicit use proposal and reviewed Start. Saved examples replace actual Lua controller buttons at a compatible segment entry. Attempt history retains application receipts, frames followed, completion/partial results, observed coin context, terminal state and handback. Reopening restores data without a plan/recording/authority. Historical accepted routes are unchanged.

The strategy is bounded sequence following using an experimental balanced approach. It matches World 1-1/map identity, position, velocity, form and airborne state before playback; checks drift each frame; stops at segment end or mismatch/death/expiry/reclaim. Enemy timing is not synchronized. Ten-minute recording and three-minute application caps are separate. Unmatched starts fail safely. There is no generalized adaptation, automatic promotion or autonomous training.

## Local verification

Behavioral tests cover passive player ownership and frame pairing, exclusion of all companion authority while recording (including pending acknowledgment), closed-file stop, stop timeout, disconnected trace retention, frame continuity/tampering, trimming, cartridge compatibility, review/edit/delete and image retention, immutable reviewed choice, approved real controller wire parameters, fresh session preparation, recorded input override, mismatch/missed entry/death/reclaim, end state and neutral acknowledgment, disabled guidance, persisted applications and reopening without authority. Lua 5.1 tests execute the actual scripts using simulated RAM/input; they are mechanism evidence, not real Mario gameplay. The dev-only Lupa dependency and lock entry support these executable checks.

The ordinary browser check displayed the recording workflow and exposed a nested non-reentrant observation lock in the new recording-command path. The command now reads the already-locked accumulator directly; a real-manager regression fails on any locking-snapshot reentry. The earlier browser UUID capability observation did not establish the cause of the stuck request. Mario request IDs now avoid a browser UUID dependency, and JavaScript assets are served without caching. CSRF and reviewed authority remain separate from request deduplication. Existing coaching/coin/runtime/learning/history/control/UI regressions and the canonical gate qualify the current source. Exact final counts/results are recorded in the closeout below.

## Real-game and owner boundary

No current player/exclusive-input availability was supplied during this implementation. No new emulator gameplay was launched. There is no engineer-created real-game demonstration, no demonstrated stairs application and no observed improvement over the x=1652 death. The owner demonstration experience remains pending.

The precise remaining check is: record an alive stairs route segment as the player through `/mario`, stop/save/review it, open a fresh disposable compatible attempt, explicitly Use/Start it, observe controller application and whether Mario passes the stairs failure, exercise Stop/Take control with confirmed neutral handback, and reopen to confirm retained example/application with no resumed gameplay. Bind the source hashes, original lesson, trace, application receipts and independent observed outcome. Use the [ready walkthrough](mario-player-guide.md#let-me-show-you-record-a-route-or-segment). If entry fails, retain its refusal and make one bounded alignment repair; do not claim the lesson helped.

## Closeout

Final canonical gate passed **1,395 tests**, lint/security, generated-file checks, objective/segment contracts and Mario/Lab/Stardew renders (`final-complete-canonical-check.log`). Final focused recorder/UI/observation checks passed **73 tests** (`final-focused-check.log`); all three changed Lua modules compiled under Lua 5.1 (`lua-syntax-check.log`). Runtime source SHA-256 is `57a5c419a09161cad0a6f4601d330c8aa8f588e5916cfb5e12acd7f35b94a01e`; `final-source-identity.json` retains its per-file map. Earlier checks remain bound to their earlier changes; the final gate includes the lock repair and one-shot player-unpause regression.

The final in-app browser **Start recording** click returned a clear no-session refusal immediately, confirming the repaired ordinary API interaction. The temporary servers/tab were closed; no emulator or gameplay was launched. `ui-idle-state.json` retains no session, plan, recording or agent authority and the six prior coin attempts. `closeout.json` summarizes the distinct evidence classes. Source work only; real stairs application, improvement, owner experience, packaging and release remain pending.
