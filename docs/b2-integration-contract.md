# Mario planning and runtime interfaces

Adapter interface reference and planned GC1/GC2 work. The [product direction](product-direction.md) defines watched/coached Mario play across attempts and lives as an initial-beta requirement. The [private-beta engineering plan](private-beta-engineering.md) owns implementation order and exact-candidate acceptance. Existing contracts below are reusable foundations; they do not yet implement that product loop.

The ordinary conversation flow separates proposals, execution and presentation.
See the [Stardew integration contract](b3-integration-contract.md) for farm interfaces.

- Planning uses `request_planning.py`, `mario_route_plan.py`, `stardew_planning.py` and matching new tests. Typed JSON-serializable plans expose request/conversation/game/session/observation identity; original objective, normalized intent, real base route, revision/parent; typed actions and preconditions/outcomes; protection/resources/stop/effective boundary; speed; eligibility/evidence/authority. Pure planning never emits input.
- Runtime validation uses `mario_plan_runtime.py`, the Python/Lua control seams in `live_observation.py`, `takeover.py`, `fceux_live_takeover.lua`, `fceux_1_1_agent.lua`, any new Lua controller file and matching runtime tests. It validates adapter-owned primitives, process/session/state, revisions and commands independently of planner claims.
- Presentation uses `conversation_ui.py`, integration edits in `lab_ui.py` and matching browser/render tests. Keep planner/execution logic in their modules and expose ordinary `/mario` conversation with stable draft/focus, persistent control and visible revision/speed/outcome.
- `conversation_service.py` coordinates runtime and planning; `custom_variants.py` stores descriptive plans and outcomes without restoring authority.

Integration surface: UI calls `ConversationService(live_manager, artifacts_root=...)`; `snapshot()` yields JSON-safe state; `dispatch(action, payload)` yields JSON-safe state or raises ValueError. Actions: select_intent, message, start, apply, cancel_pending, revert, speed, pause, resume, stop, reclaim, save_variant, load_variant. No endpoint starts or resets an emulator implicitly; existing explicit launch remains. Service shares the server live manager.

The runtime offers snapshot/start/edit/cancel/control operations and never relies on stored or planner-supplied execution authority. UI treats returned plan/runtime dictionaries as presentation data, text only. CSRF and loopback protections remain mandatory.

## Implemented opening coaching slice

Current source now provides the ordinary experimental opening practice described in the [Mario guide](mario-player-guide.md#practice-and-coach-the-opening-jump) and [verification record](gc1-gc2-coaching-verification.md): next-attempt delay coaching, bounded explicit retries, persisted compatible guidance, reset, outcomes and priority urgent Stop. Accepted-route evidence below retains its historical scope. Broader coin/flight/life-learning requirements remain pending.

## Current implementation boundary

`Planner` is a deterministic phrase matcher. `MarioPlanningAdapter` resolves the existing `world_8_finish_game` base, the default/opening-hop paths, declared stops and normal/turbo speed. `MarioPlanRuntime` accepts one supported traversal primitive and applies revisions only at declared boundaries. Quickest/100% requests fall back to the same base. General coin-route discovery, conversational jump-frame revisions, an arbitrary hidden-1-up flight goal and multi-life training are not implemented through these interfaces. Conversation history/custom variants and `learning.py` are retained foundations, but there is no integrated coaching-to-next-attempt application loop.

`request_planning._control_request` uses full-string matching for narrow phrases such as “stop” and “stop now.” The exact owner command “STOP RIGHT NOW WAIT” does not match; it returns Mario help/clarification instead. Dedicated stop/reclaim operations reach runtime control. GC1 must repair the conversational interruption gap and separately verify actual input release; inspection of the parser is not a native receipt.

## Planned GC1: priority interruption

Detect an explicit urgent stop before model work, ordinary request planning, clarification or revision application. The detector must recognize the owner's exact command and checked urgent variants without interpreting negated or hypothetical stop discussion as authorization. Dispatch through the direct runtime reclaim path, invalidate pending commands first, and expose observed release state. A slow/unavailable model, busy planner, paused task or pending revision cannot delay interruption. Retain unconfirmed release as an issue and refuse further native work until control is known.

Acceptance requires the exact command while a supported task is active, while paused and with a pending edit; retained evidence must show the interruption and neutral input/returned control, with no later queued input. Direct visible Stop/Take control stay available independently of conversation. Bounds and timing receipts must identify the exact runtime/package under review.

## Planned GC2: coachable Mario attempts

Extend the current typed proposal/runtime boundary rather than allowing planner text to issue raw input. Define these contracts before adding gameplay breadth:

| Contract | Required behavior |
| --- | --- |
| Play objective | Bind a level/route, observable goal, current entry, protected resources and reviewed limits on attempts/lives. “100% coin route” needs observed coin accounting and explicit unknown coverage; the unchanged base route cannot be presented as satisfying it. |
| Experimental route and attempt | Create a local versioned route experiment with an attempt/life identity, entry and stop, discoveries, controller actions, outcome and release receipt. Retain death and partial progress; never overwrite historical accepted evidence. |
| Coaching revision | Keep the owner's exact words, targeted jump/action, prior/new timing or tactic, applicability and requested effective boundary. Clarify ambiguous targets/“a few” frames, then acknowledge applied, next-attempt, refused or missed-boundary state. |
| Selected real-time command | Validate adapter-owned capability, current observation, remaining authority and a safe application boundary. A late command is reported as late, never silently marked applied or deferred. Urgent Stop has its separate priority path. |
| Retry and memory | Load compatible route discoveries and approved coaching for the next authorized attempt/life; explain what changed and why. Reopening restores descriptive memory, not input authority or assumed current game state. |
| Flight/objective action | Reuse existing flight mechanics only through a supported action contract with observed current ability/target and measured outcome. A fixed fortress flight controller does not prove general “fly to get the hidden 1up” support. |
| Outcome | Show goal progress, missed/unknown coins or target, lives/resources used, applied coaching, discoveries, comparison and control release. A controller completing its segment is separate from the requested goal being satisfied. |

The player-facing workspace must make a useful supported play request, reviewing it, watching Mario and coaching the next attempt possible without developer edits. Keep a compact current goal/attempt, visible Stop/Take control, chat isolation, applied-versus-pending coaching and readable results. The Lab remains engineering infrastructure.

Acceptance is a visible Mario run followed by the owner's timing correction, a compatible retry within a reviewed finite attempt/life budget, and evidence that the new timing actually reached the controller; reopening must retain the correction and experiment. Add a bounded coin-exploration case across attempts/lives that remembers discoveries, reconciles collected/known/missed coins and leaves unknown coverage explicit. GC2 also needs an actual supported flight-to-reward attempt with observed ability/target, controller execution and reward outcome; a prerequisite explanation alone cannot complete that implemented task case. Declare flight and each live command Available only after their exact task has implementation and evidence; show clear limitations for the rest. Meaningful checks cover ignored/late corrections, death, reclaim, process loss, incompatible memory, reopening and queued-input cancellation, followed by exact-package owner review. Local contract checks alone do not establish useful gameplay.

One reviewed finite attempt/life budget may cover compatible retries without a new Start for every life. Recheck current eligibility and remaining limits each time; reclaim, invalidated authority or expanded scope needs fresh approval. A selected timing/tactic change inside the reviewed adjustment range may apply with acknowledgment; a material scope change needs review.

Ordinary experimental coaching uses local versioned records and reviewed runtime validation; it does not require a repository route patch or accepted-registry promotion for each trial. [Learning](learning.md) owns this separation. Promotion into the historical accepted registry retains its existing gates. Independent practice/self-improvement remains later work.

## Experimental surface coin exploration

The adapter accepts `coin_high` and `coin_low` only with the versioned coin-discovery plan and unexpired finite approval, stopping at the World 1-1 exit. These are scheduled-jump alternatives across the level, retaining hazard precedence. Fresh power-on is required for level-exit traversal. Per-frame native `coin_observation` events read game-owned `$7967`; `coin_route_applied` confirms selection and `coin_level_finish_observed` confirms the independent exit boundary. Plans and results never modify accepted-route registry entries.

## Player demonstration sequence extension — October 3

The ordinary conversation API adds `player_play`, `record_start`, `record_stop`, `record_save` (name, lesson, optional first/last indexes), `demo_review`, `demo_edit`, `demo_delete`, `demo_fresh`, `demo_use`, and priority `demo_disable`. Demonstration review/edit/use/delete select `demonstration_id`; use only creates a proposal. Start retains existing plan/revision binding. `recording.request`/`recording.ack` are passive process/session-bound mailboxes; all native takeover entry points reject recording/pending start. The actual FCEUX Lua recorder pairs pre-frame state with effective post-frame buttons and position, retaining raw traces and visual frames. Stop acknowledges file closure before save. The controller receives only validated numeric replay rows, copies the recorded buttons to the actual eight-button override and emits application/frame/completion receipts. Priority reclaim, expiry, death and drift dominate replay. Sequence completion stops locally and does not emit a level-exit receipt. Reopening retains data only. See [verification](gc2-demonstration-verification.md) for limits and pending real-game evidence.
