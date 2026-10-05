# Mario planning and runtime interfaces

Updated October 4, 2026. This contract distinguishes the implemented bounded
Mario controller from the **Codex-backed conversational interpretation and
gameplay reasoning required for the initial private beta**. The
[engineering plan](private-beta-engineering.md) owns the complete delivery order;
the [product direction](product-direction.md) owns the intended experience.

## Current implementation and evidence

| Area | Implemented behavior | Remaining limit |
| --- | --- | --- |
| Conversation | Deterministic `Planner`, adapter request matching and supported coaching helpers | No Codex-backed interpretation or gameplay reasoner on the ordinary Mario decision path |
| Opening coaching | Persisted delay adjustments, finite explicit retries, actual Lua application and urgent interruption | One authored opening event and bounded timing parameter |
| Surface-route learning | Selection among authored high/low/balanced jump schedules, failure-derived supported stairs/pipe tactics, per-attempt coin accounting | No general route discovery; individual and full coin-universe coverage unknown |
| Traversal | Two observed World 1-1 finishes with two coins each, plus preserved historical accepted routes | Those results do not establish novel-state play or broader reliability |
| Flight/reward | Observed prepared Raccoon/Tanooki World 1-1 sky-1UP case, separate revelation/collection and handback | Prepared entry and one authored objective; broader flight reasoning unavailable |
| Demonstrations | Source recording, review, storage and bounded numeric playback | Real demonstration application remains unverified; deferred to tentative beta v2 |
| Control/history | Independent Stop/Take control, session-bound plans, outcomes and reopening without restored authority | Must remain effective while new model work is pending |

See [coaching](gc1-gc2-coaching-verification.md),
[route](gc2-route-verification.md),
[flight](gc2-flight-verification.md) and
[demonstration](gc2-demonstration-verification.md) records for their exact evidence.
Historical B2 parser limitations and later repairs describe their own candidates;
the urgent interruption gap is repaired in current source.

These are real gameplay foundations. They do not complete the AI-player product.
Adding another fixed route or another request pattern alone is not the next
milestone.

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
- The existing model gateway demonstrates bounded inference in the separate
  profile path. Its presence does not establish model use in Mario. Connect the
  selected Codex CLI backend to the actual ordinary decision path.

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

## Initial AI gameplay acceptance

After the shared slow decision loop is proved in Stardew, complete Mario's faster
version through the ordinary interface. Declare the supported level, entry
conditions, mechanics and tasks rather than claiming unrestricted gameplay.

Required evidence:

- Varied held-out goals and corrections are interpreted without phrase-specific
  patches, including contextual references and meaningful ambiguity.
- A real Codex request and reply lead to a validated runtime action selection;
  logs distinguish model decisions, authored fallback skills and algorithms.
- A changed supported condition or failed approach leads to a materially changed
  decision based on fresh observations, without a bespoke route patch.
- A compatible later attempt uses retained evidence or coaching to change play.
- At least one supported traversal/exploration task and one ability/reward task
  have observed effects and honest outcomes under the declared scope.
- Stop during inference and active play releases input, and stale replies cannot
  revive authority. Reopening retains results without playing.
- The same implementation handles a second meaningful supported variation,
  demonstrating composition rather than replay of one accepted trace.

Use fixtures for logic and concurrency, and real disposable-game evidence for
perception, action application, adaptation and handback. Measure task results,
interventions, refusals, failures and decision latency for the exact candidate.
A large test count or a single fixed-route success cannot substitute for this.

## Local private-beta delivery

The release candidate must include the app-owned runtime/controller assets,
readable setup, Codex CLI availability/authentication guidance, local game-file
selection, capability labels and actionable connection errors. Do not bundle game
files or credentials. The app is private and local; Codex-backed inference uses
the selected provider and should be described accurately without implying
on-device inference.

Verify the exact local artifact from first launch through connection, goal,
approval, model decision, play, coaching/replan, Stop and saved reopening.
Preserve Mario/Stardew shared regressions and verify the chosen configuration
matrix. Retained private.2/source evidence does not establish a later artifact.
Owner usefulness review and the local beta release decision follow that actual
artifact check. Recording, arbitrary game support, independent training and
no-code addition of games remain later work.
