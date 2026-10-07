# Mario planning and runtime interfaces

Ordinary Mario conversation uses `companion_ai.LanguageSession` through the
installed Codex CLI. `mario_strategy.MarioStrategyAgent` chooses finite maneuvers
from paused images and native progress for the World 1-1 early segment.
Deterministic typed planners and guarded controllers validate those choices;
they remain separate from model interpretation and do not grant their own authority.

## Implemented behavior and limits

Contextual requests, corrections and compatible coaching enter reviewed finite
plans. Adaptive play is limited to the early segment; full-level adaptive
completion and complete coin coverage are unverified. Authored route, opening
coaching, stairs/pipe and flight/reward controllers have their own entry contracts.
Recording/playback remains experimental and native demonstration application is
unverified. Exact source/build results belong to the
[qualification records](current-engineering-status.md), not this interface contract.

## Existing integration owners

- `request_planning.py` defines typed serializable goals, actions, references,
  resources, revisions, uncertainty, eligibility and scope. Current `Planner`
  and `mario_route_plan.py` are deterministic.
- `conversation_service.py` owns the ordinary conversation, reviewed plans,
  coaching, finite attempts and outcomes. `conversation_ui.py` presents the
  experience without granting authority through rendering or history.
- `mario_plan_runtime.py`, `live_observation.py`, `takeover.py` and the
  FCEUX Lua controllers independently validate actions and own actual execution.
- `mario_coaching.py`, `mario_coins.py`, `run_library.py`, `learning.py`
  and outcome history retain descriptive guidance and evidence. Experimental
  knowledge stays separate from the historical accepted-route registry.
- `codex_provider.py`, `companion_ai.py` and `mario_strategy.py` own ordinary
  language and strategy inference. `model_gateway.LocalOllamaGateway` serves
  the separate OpenTTD reference flow.

Keep typed plans and runtime validation as the integration boundary. A model
response cannot execute arbitrary code, mint a capability or provide its own
authorization.

## Role 1: conversational intention

Use the selected Codex provider to understand varied natural language, follow-up
references, goal changes and coaching in the current conversation. This role
produces a typed goal proposal containing:

- The player's intended outcome and any unresolved interpretation.
- Game/level and observed target or event references.
- Observable success criteria and declared coverage.
- Player preferences, protected choices, attempt/life/time limits and stop point.
- The change from the current goal or coaching, and its proposed applicability.
- Missing game information or missing capabilities that require clarification.

Preserve the original request. Keep examples as evaluation cases rather than a
literal vocabulary. Questions do not emit input. An unsupported full-completion
request must explain the available exploration scope; the unchanged base route
cannot be presented as fulfillment. Independent urgent controls bypass inference.

## Role 2: game understanding and action selection

The gameplay role receives the typed goal, fresh observations, relevant mechanics,
implemented skills and compatible attempt memory. It must choose and revise
actual play, not merely narrate an authored route.

Maintain a game-owned state representation sufficient for the declared scope:
Mario's position and motion, grounded/airborne state, form/abilities, level/camera,
visible geometry, reachable landing areas, enemies/hazards, interactable/reward
objects, lives/coins and observed event receipts. Game-owned emulator state can
supply supported facts; image observations supply additional scene context.
Declare source, observation time, confidence and any unknown fields.

Keep current state separate from historical discoveries. A prior coin yield does
not identify today's coin location; a retained route does not establish current
enemy timing. Update identities and relations across observations, and use
uncertainty to decide whether to inspect, choose a lower-risk supported action,
ask a question or stop.

At meaningful decision boundaries the gameplay role should:

1. Select a useful subgoal from current state and the approved objective.
2. Propose a skill/target/parameter combination and its expected effect.
3. Pass that proposal through the independent capability and authority validator.
4. Observe actual execution and compare its effect with the expected result.
5. Continue, revise, inspect further or report a blocker based on that comparison.

The same implemented skills must compose into more than one meaningful approach.
The engineer should not add a custom controller branch for each new wording,
landmark or failure merely to complete the AI acceptance check.

## Skills and the fast controller

Expose a machine-readable catalog generated from actual adapter capabilities.
Each skill declares parameters and bounds, observed preconditions, expected
effects, verification method, timing class, interruption behavior and limits.
Examples of useful skill families include movement, supported jumps/landings,
run-up, ability use, observation and interaction with an observed target.
Engineering chooses the concrete decomposition.

The deterministic controller remains responsible for frame timing, feedback,
collision/reachability checks, deadlines, game input and immediate handback.
A generic parameterized movement/jump skill is useful infrastructure; a
coordinate-specific stairs macro is a narrower fallback and must be labeled so.

Do not call a language model for every frame. Define the planning cadence,
observation-to-action latency limits and safe behavior while inference is pending.
The controller may finish the currently approved bounded skill or hold/release at
a supported decision boundary. A stale or late decision cannot target an event
that has already passed. Strategy changes may apply during a supported boundary
or on the next compatible attempt with clear acknowledgment.

If Mario requires a faster policy, search or local motion planner for general
action selection, implement the appropriate approach beneath the gameplay role.
An LLM alone is not assumed to supply reliable platformer timing. Acceptance is
chosen, observed behavior; no specific learning algorithm is mandated.

## Mechanics, outcomes and memory

Provide relevant mechanics knowledge through a bounded game-owned knowledge
source, separating stable rules, current observations, player reports and learned
hypotheses. Include movement/ability conditions and reward interpretation needed
for the declared tasks. Version that knowledge with the supported game identity.

Retain the goal, reasoning summary, selected skills, parameters, observed effects,
failures, coaching revisions and unresolved questions. Use compatible memory to
change future decisions. Keep learned advice inspectable and resettable without
erasing historical outcomes. Current player direction overrides old guidance.

For coin objectives, keep per-attempt collection separate from accumulated
discoveries, avoid double-counting and state the declared coin coverage.
For rewards, distinguish reaching, revealing and collecting; a life change alone
may be ambiguous. For coaching, distinguish proposed change, actual controller
application and observed improvement. A model explanation is not a success receipt.

Retries can share a reviewed finite scope when compatible. Death/reset requires
fresh state and budget checks; reclaim, expiry or scope expansion requires new
approval. Reopening restores descriptive knowledge, not live state or authority.

## Qualification boundaries

Fixtures verify logic and concurrency. Real disposable-game trials establish
perception, action application, adaptation and native handback only for the
identified build and tested scope. A fixed-route result or test count cannot
establish unrestricted gameplay. See [known limitations](known-limitations.md)
and the [engineering record](current-engineering-status.md).
