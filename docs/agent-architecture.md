# Game Companion Architecture

## October 4 architecture correction — two model-driven responsibilities

This is the active product and implementation requirement. Game Companion must have both contextual language understanding and a game-playing decision loop. The first backend is the owner's installed, signed-in Codex CLI for this personal local application. The two roles may share one model/backend, but have separate inputs, outputs, session state and verification.

Current ordinary Mario and Stardew services construct the deterministic Planner and dispatch recognized request families. Their controllers have real observation feedback, interruption and outcome verification, but high-level choices are largely authored tactics, configured routes and calibrated scene rules. LocalOllamaGateway is currently connected to the separate profile/OpenTTD flow. Existing gameplay results establish those implementations, not general model-driven understanding or adaptive play. These foundations should become reusable capabilities beneath the decision loop.

### Responsibility 1 — contextual language-to-game LLM

The conversation layer understands what the player means across turns. It must handle original wording, incomplete descriptions, references to what is visible, priorities, exclusions, corrections, questions and coaching without requiring a prescribed vocabulary.

Input context includes the player's words, relevant conversation, selected game, current goal/plan/progress, fresh observed entities and images, available game capabilities, applicable mechanics and compatible remembered guidance. Keep it compact and task-relevant. Earlier observations must retain their age and uncertainty.

The output describes the requested objective, relevant targets/references, constraints, preferences, time/resource limits, proposed completion conditions and interaction type. It identifies clarification needs and capabilities the request would require. It also provides a concise player-facing interpretation. Engineering chooses the schema and provider abstraction.

Understanding a request is separate from having the ability to execute it. Preserve the intended objective even if a prerequisite or skill is missing. Explain the actual gap rather than substituting the nearest scripted task. Resolve a reference such as another patch or a previous jump using context; ask a question when the intended target remains materially ambiguous.

A correction updates the represented goal and constraints, then informs the gameplay agent. Coaching records the intended behavior change and applicable game event, rather than just storing a phrase or mapping it to a fixed preset. Questions request an answer or observation without gameplay authority.

The LLM may interpret an approval reference, but the app binds approval to the displayed current scope and session. Independent Stop/Take control remains immediately available. Neither role can restore canceled authority.

Acceptance includes wording withheld from implementation, multi-turn references, compound preferences, exclusions, changed priorities and accurately understood unsupported requests. Vary context as well as phrasing: identical words about different observed targets must resolve appropriately. Show actual model calls and resulting typed intent; simulated model replies and deterministic shortcuts do not establish model understanding. Provider failure must be visible, with input released rather than silent substitution by a narrower parser.

### Responsibility 2 — game understanding and adaptive play

The gameplay agent determines how to accomplish the understood objective from the current game. It uses mechanics, perception, spatial context, resources, available skills and observed consequences. This is an active decision layer during play, not just an initial plan explanation.

Its working state includes player location/motion/form, relevant objects and targets, terrain and possible routes, resources/time, completed work, hazards, observations with confidence/age, remembered outcomes and missing information. Separate observed facts, inferred possibilities, general game knowledge and historical evidence. A model's visual guess or knowledge of a typical map is not confirmation of the current scene.

Expose reusable adapter capabilities with preconditions, bounded parameters, expected effects, outcome checks and failure states. Capabilities may include inspecting an area, moving toward an observed target, acting on a selected target, executing a supported jump/flight maneuver or returning control. The model may compose implemented capabilities and ask for more observation; it may not invent executable skill IDs or expand input permission. Geometry, collision handling and fast movement can use ordinary algorithms.

The decision loop is:
goal + fresh state + rules + capabilities -> choose the next subgoal/action -> validate -> execute a bounded skill -> observe the result -> update state -> continue, replan, clarify or stop.

Each decision identifies the selected action/target, why it serves the goal, the expected observable effect and what would trigger a new decision. Keep explanations concise; no private chain-of-thought collection is required. The app validates the action against current conditions and approved constraints before dispatch.

After execution, independent observation determines the actual effect. Unexpected obstruction, resource loss, changed target, lost visibility or failed action must feed a revised decision. Distinguish a feasible alternative, a need to inspect, a missing implemented skill and a fundamentally blocked objective. Limit repetition and stop when it has no evidence-backed new approach; changing timing endlessly without learning is not adaptive play.

Perception must let the agent reason over supported variations in scenes and targets, not require engineers to install a new complete route for each request. Use current precise recognizers where reliable, and extend perception where its missing information blocks the decision. Visual model inference can propose object/location interpretations; critical movement and outcome checks still need sufficient independent grounding.

Memory retains coaching, discoveries, effective and failed actions, context and uncertainty. Retrieve applicable knowledge and show it affecting later decisions. A stored record or automatic selection from three fixed routes alone does not demonstrate learning. This does not require training a new neural network or an unattended practice service.

Acceptance includes a changed starting condition, target, constraint or obstacle selected after implementation, with the same agent choosing a different grounded action or revising a plan without a bespoke script edit. Demonstrate progress or completion from the approved goal, verified outcomes and usable handback. Test both interpretation and gameplay choice: novel wording alone proves only the first layer.

### Local Codex integration and execution boundary

Use Codex as an inference/agent backend during ordinary app use, not merely as the engineer writing the app. Engineering can start with non-interactive calls or choose the app-server integration if its persistent threads, tool interaction and cancellation are a better fit. Keep this personal integration small; no hosted product service or new training pipeline is required.

The installed CLI supports image inputs, JSON event output and schema-constrained final output. Its exec interface reuses saved CLI authentication. Official references: [non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) and [app-server](https://learn.chatgpt.com/docs/app-server). Installed CLI help and login status were inspected on October 4. No inference was performed and game-playing quality, latency and account limits were not measured by this documentation update. The normal OpenAI-backed CLI sends inference to a remote model even though the application and tools run locally.

Give the roles game-state/image access and a small explicit interface to validated adapter capabilities. Runtime gameplay does not edit repository code or patch controllers in response to each obstacle. Improvements to a reusable skill are engineering work; the agent's job is to compose supported skills using current state.

The existing fast controller continues to handle frame timing, movement feedback, input release and postconditions. Codex makes semantic/task decisions at useful boundaries, not each Mario frame. Stardew is the first complete adaptive-play integration because its slower activities fit these boundaries. Connect shared contextual intent to both game interfaces and then extend Mario strategy at suitable skill boundaries.

Measure actual inference latency and decisions per activity. Pause or maintain only the currently validated finite skill while a new decision is pending. Stale replies, invalid output, model unavailability and cancellation cannot initiate more input.

### Immediate milestone and evidence

Deliver one connected Stardew activity where real Codex interpretation creates the goal, a real Codex-backed gameplay agent selects/composes actions, existing controllers execute, and fresh results cause a later decision or replan. Use available watering/inspection skills so progress is not contingent on finishing a cave manifest first.

Include a changed preference and a supported changed scene/resource/target condition that require different decisions without code changes between trials. Extend a reusable observation or skill if necessary. Preserve operating controls and prior game evidence.

Record original language, resolved goal, evidence supplied, chosen skill/parameters, expected effect, actual effect, later decision, uncertainty and handback. Show which decisions actually came from the model. Keep real model, local simulation, live game and packaged evidence distinct.

AI capability is the next development gate. Pause the one-off cave detour qualification campaign as the lead task; retain its frames and current manual-route versus ordinary-activity evidence for future work. A foliage fix or route patch is appropriate when it unlocks this adaptive loop, but is not completion of the two AI responsibilities.

After the Stardew vertical slice works, extend model-driven task decisions into Mario and evaluate a second activity/state variation. Then continue product coverage and delivery. Recording stays deferred to tentative beta v2. Historical game successes remain valid under their original scope, without implying the new architecture is implemented.

Game Companion is a conversational player: it interprets the user's intent,
plays within an agreed scope, accepts coaching and reports observed results.
The active implementation begins with the shared Codex language and gameplay
roles on a useful Stardew activity, followed by Mario strategy integration. Minecraft connects during the initial beta and develops into the
third playable option by the end of beta. The [private-beta engineering
plan](private-beta-engineering.md) owns current scope and the [PM
handoff](private-beta-pm-handoff.md) owns remaining delivery work.

The repository already has typed plans, explicit player control, game-owned
observations, bounded runtimes and retained outcomes. FCEUX supplies the Mario
backend; Stardew, profile-based reference work and Minecraft have their own
runtime semantics. These are foundations for the required product integration;
their existence is not proof of the complete conversational gameplay loop.

## Required product integration

The shared product must connect conversation, game decisions, execution and
attempt memory. The intended loop is:

```text
user intent or coaching
-> fresh game context and compatible attempt memory
-> understandable proposed goal, constraints and stop point
-> player approval where required
-> game-owned decisions and bounded execution
-> fresh outcome checks and conversational updates
-> interrupt, revise or finish with confirmed input release
-> retained discoveries, corrections and outcome for the next attempt
```

Mario is watched play that the user can coach. A goal such as finding a 100%
coin route requires attempts across routes and lives, remembered discoveries
and corrections, and honest progress toward the goal. An instruction such as
"wait a few more frames" must bind to an identifiable timing decision and
produce an inspectable change in play. Selected supported commands can affect
the current attempt; other coaching is retained for the next one. Acknowledge
whether a correction was applied, awaits a safe execution boundary, is queued
for the next attempt or needs clarification. Later self-directed practice is
separate from this initial coached-play requirement.

Stardew uses short approved activities: understand "water the tomatoes" or an
exploration/planting goal, discuss choices when needed, state the intended work
for the next few minutes, receive approval, perform the clicking and movement,
then check in at an observed decision or task boundary. Goal reasoning,
navigation, resources and outcomes remain Stardew-owned. Conversational
check-ins must make changes and interruptions useful without requiring the
player to direct every click. These are required experiences, not claims that
the existing watering and farm-task implementations already cover them.

Higher-level intent interpretation and game decisions must use the model with typed
adapter planning and compatible knowledge. The fast game feedback loop must
continue through adapter-owned observations, finite primitives and checked
postconditions; it must not wait for a language model on each frame or input.
Direct Stop and Take control revoke authority and release input independently
of model availability, planning and task locks. "STOP RIGHT NOW WAIT" takes
priority over the goal and coaching queue. A requested scope change cannot
silently expand the player's approval, and saved learning never grants new
input authority.

Minecraft builds on the slower Stardew activity loop. Its present calibration
and camera path remains a component reference while Mario and Stardew lead
delivery. Later, Minecraft also informs guided advanced-user setup for another
eligible game without writing code. That no-code teaching/onboarding discussion
and implementation are deferred until the first two gameplay experiences are
implemented; they are not an initial beta gate. See [new-game
onboarding](new-game-onboarding.md) for the separate contributor scaffold and
its proof limits.

## Components

```text
Conversation and Player Session (Tell / Show / Do foundations)
  -> Authorization and Safety Contract
  -> Game Adapter Capabilities
  -> Goal Contract
  -> Intent and Game Decision Planning
  -> Adapter-Owned Execution and Fast Feedback
  -> Game Observer and Outcome Verification
  -> Recovery Manager
  -> Attempt Logger
  -> Note Collector
  -> Issue Ledger
  -> Reviewer
  -> Route Patch Manager
  -> Codex Task Builder
  -> Knowledge Store
  -> Local Learning and Candidate Review
  -> Handoff and Local Metrics
```

## Shared Companion Core

The cross-game core owns session lifecycle, authorization, mode selection,
protected decisions, cancellation/takeover, evidence references, handoff, and
local product metrics. It must not branch on a Mario or Stardew identifier.

A game adapter owns executable/window detection, observations and confidence,
supported inputs, game-specific goals and knowledge, protected actions,
recovery rules, success/failure predicates, and evidence capture. Capabilities
are declared and validated; unavailable capabilities are not inferred.

The shared lifecycle is:

```text
observe
-> offer supported help
-> authorize scope and stop point
-> tell, show, or do
-> verify game-owned outcome
-> stop input
-> hand back
```

The [live-observation contract](live-observation.md) documents the exact
visible FCEUX connection, direct player-input source, read-only boundary,
continuity rules, and retained local evidence.

## Ordinary player setup and Minecraft path

This section records current owners and feature limits. Completing a Minecraft
wall component does not establish the Mario/Stardew beta experiences above or
replace their delivery priority.

`lab_ui.py` serves `/setup`, `/minecraft` and `/help` through the existing local
server. `PlayerSetupService` in `player_setup.py` coordinates saved profiles,
questions/corrections, review and direct controls. `player_onboarding.py` derives
the visible setup step and available task list from the selected profile and
current Minecraft session. `player_store.py` retains bounded configuration,
outcomes and inspectable local reports outside the installed build; reopening
starts with fresh runtime authority.

`MinecraftPlayerSession` in `minecraft_session.py` owns the exact current
connection, review, page lease, cancellation epoch and active input owner.
`CHECKED_FEATURES` enables calibration and camera on the current candidate;
aiming, movement, additions and wall remain disabled pending their useful-path
checks. The source feature flags are the runtime eligibility authority.

`minecraft_native.py` composes selected-window capture, visible HUD pose/target
and inventory evidence, calibrated camera feedback and finite input owners.
`skill_runtime.py` checks fresh observations, child and parent deadlines,
independent post-input results and release. `minecraft_wall.py` accounts one
shared budget while coordinating work cells, doorway air, protected cells and
the observed stop point. These implemented ports supply the ongoing building
integration; their existence does not substitute for a successful packaged task.

`model_gateway.py` and profile conversation provide bounded local model
proposals for supported reference-game work. Immediate controls and Minecraft's
fast feedback loop remain independent of inference. Game/provider semantics
select supported skills and outcome predicates.

## Typed planning and bounded Mario execution

`request_planning.py` owns a registry of adapter planners and a serialized typed
plan contract. `mario_route_plan.py` and `stardew_planning.py` own actions,
capabilities, protected choices and target semantics. Advisory proposals cannot
grant permission. The Mario/Stardew local grammar supports bounded contextual requests and
keeps unsupported clauses explicit; these adapter planners need no model account.

This describes the existing deterministic implementation. The active two-role
requirement above connects Codex-backed intent and game decisions to these
validation/execution owners; the grammar is not the target AI architecture.

`conversation_service.py` coordinates the ordinary Mario UI, reviewed plans,
exact command acknowledgments, variant compatibility and append-only outcomes.
`mario_plan_runtime.py` independently validates primitives, process and state,
then delegates a fresh bounded authority to the existing takeover controller.
Conversation execution permission does not change accepted-solution or route records.
See [Planning interfaces and adapter extension points](b2-conversation-guide.md).
The product work must connect these owners to intent interpretation, route/life
practice and remembered coaching. The present bounded grammar and accepted
route execution are not evidence that arbitrary coin, flight or hidden-item
goals can already be played. Preserve typed validation while expanding only
the concrete supported behavior needed by the active engineering plan.

## Stardew companion adapter

`stardew_adapter.py` owns Stardew observations and input independently of Mario.
`stardew_companion.py` coordinates the operator. Its adapter-owned
pipeline is:

```text
explicit source or prepared-farm selection
-> verified attempt-owned disposable copy
-> visible process/window identity
-> complete screen-only farm sweep
-> exact crop/resource/position ledger
-> adapter-neutral observation envelope with opaque Stardew facts
-> grounded Tell or one fresh-copy review-only Show
-> player-owned boundary
-> explicit same-live-session Do authorization bound to task/copy/process/window/observation/expiry/driver
-> ordinary input plus fresh screen-confirmed postcondition
-> neutral stop and player handback
-> primary-save and artifact reconciliation
-> optional fresh-destination disposable reset that invalidates all old state
```

`DisposableSaveManager` refuses existing destinations, nesting, real-path
aliasing, symlinks, empty saves, copy mismatch, and source mutation during the
copy. `ScreenObservation` accepts only visible screen evidence bound to one
copied-save and process/window identity. It requires exact crops, energy,
watering-can state, tool uses, refills, and position. `WateringLedger` freezes
the initial planted set, keeps already-watered crops, and refuses additions,
removals, contradictions, or non-monotonic resource facts.

`CompanionObservationEnvelope` carries only shared identity, freshness,
confidence, evidence, ownership, and opaque adapter facts. The Stardew provider
alone interprets crops, resources, position, and watering safety, so Mario
records gain no Stardew fields and shared contracts require no game-id branch.

`StardewOperator` owns the bounded watering state machine and fresh ownership
epoch. `OrdinaryInputDriver` accepts explicitly configured OS-visible keyboard,
mouse, or controller emitters; it provides no hidden input path. Protected
action terms and task-purpose allowlists reject purchases, sales, discards,
gifts, consequential dialogue, story outcomes, sleep, and save operations.
Every failure neutralizes before retaining evidence and requires a fresh attempt
instead of restoring authority. `StardewCompanionController` separately owns
Tell's no-input contract, Show's review-only classification, Do's live
authorization and per-input revalidation, immediate reclaim, verified neutral
handback, completion evidence hashes, and reset invalidation.

The ordinary `/stardew` route uses `conversation_ui.py` and the shared catalog
shell. `stardew_runtime.py` connects copied-save setup, fresh observation, plan
review, bounded execution, and handback; `stardew_setup.py` owns prepared-save
isolation. The CLI also provides inspection. Low-level safety policy lives in
`data/stardew/operator.yaml`; `stardew_farm_tasks.py` owns selected farm-action
ledgers. Fixtures and qualification contracts remain separate under
`data/stardew/` and `data/scenarios/`. See the
[Stardew companion guide](stardew-operator-guide.md).

This retained pipeline supplies observation, protected input and watering/farm
task foundations. The active delegation work must integrate them with the
short approved activity conversation, navigation and decision/check-in behavior
described above. A fixture, isolated action or retained delivery attempt does
not prove the complete delegated activity.

The [authority map](ssot.md) identifies current domain owners and retained
compatibility boundaries. Mario planning and runtime validation share
`mario_route_contract.py` for traversal IDs, allowed stops, and playback speeds.
The runtime accepts the planner's `mario_traverse` action with its primitive in
`parameters.primitive_id`; historical flat/action-kind primitive aliases fail
validation. Accepted route evidence and live authorization remain separate.

## Combined catalog and switching

`companion_catalog.py` defines the adapter-neutral catalog registry, bounded
local preferences, runtime switch guard, and separately classified switch
event. `MarioCatalogProvider` and `StardewCatalogProvider` own their complete
entries and runtime hooks. Registry validation refuses duplicate identities,
missing declarations, unknown statuses, unsupported goal/profile/scope links,
version or provider disagreement, and missing safety/evidence policy.

The shared coordinator calls provider hooks rather than branching on game id.
It refuses switching during input, Show, Do authority, reclaim,
neutralization, ambiguous ownership, unconfirmed handback, incomplete failure
retention, unsafe save/reset transitions, or unknown continuity. A successful
switch retains the attempt, invalidates volatile state, records a
`catalog_switch` event, selects the target, and leaves active modes disabled
until a new target-owned observation exists.

Target identity and availability are validated before any current-adapter hook
runs. The Mario provider's invalidation hook clears the stopped live-observation
identity, terminal Show presentation, objective/coaching comparison, and Tell
state while leaving retained artifacts and adapter-owned history on disk. It
cannot report success while an observer thread, Show, authorization, agent
ownership, or unretained failure remains active.

## Unattended regression runner

`unattended.py` is the adapter-neutral engineering regression runner.
Its provider registry dispatches through explicit contracts instead of
shared-core game-id branches. The shared runner owns eligibility, immutable
manifests, source dirty-state identity, safe paths, sanitized environments,
display continuity, bounded sequential fresh processes, isolated workspaces,
cancellation, exact-process termination, cleanup, failed-attempt retention,
integrity, local metrics, and compatible repeatability reports.

Adapter providers own executable/argument vectors, assets and fixtures,
ordinary input and observation paths, protected data/actions, milestones,
success/failure predicates, cleanup, and evidence. Mario references but never
copies the configured local source, uses fresh FCEUX processes and the existing gameplay
path, and cannot mutate accepted evidence, reliability, routes, records, or
learning. Stardew accepts only a dedicated non-owner regression fixture,
creates a fresh disposable run copy, uses visible pixels and ordinary protected
input, preserves exact task reconciliation, and requires neutral handback
without opening a primary save.

Normal desktop, supported local virtual display, and unavailable-display
providers are explicit. Virtual pixels remain unattended evidence, never
visible player proof. Display/process/input loss, timeouts, missing evidence,
or incomplete cleanup fail closed and retain the attempt. Classifications and
proof denials are immutable after creation. See the
[operator guide](unattended-regression.md).

## Local learning and candidate review

These records are reusable attempt-memory foundations. The Mario product must
also retrieve compatible route/life discoveries and player corrections during
normal coaching, apply them through the checked execution path and explain
what changed. Stored notes or a candidate tactic alone do not establish that
feedback affected a later attempt. Preserve observed runs and distinguish
player coaching, proposed changes, tested changes and actual outcome evidence.

The run library is the immutable observed-run source. The learning layer wraps each
run in an adapter-neutral `AttemptContract` with the additional compatibility
and evidence-integrity fields needed for honest comparison. The learning core
owns compatible sets, comparisons, progress anchors, trouble patterns,
successful tactics, objective deltas, candidate tactics and solutions,
provenance, lifecycle decisions, preferences, manifests, and checksum-bound
local persistence. Adapters supply observations and policy; the shared core
does not branch on game identity.

Learning feeds evidence-classified statements into coaching and Tell. It cannot
send input. A candidate becomes reviewable without changing goal contracts,
accepted route order, reliability profiles, fastest-observed indexes, or
takeover capabilities. For historical accepted-route promotion, owner review permits later replay validation only. Ordinary reviewed coached experiments use versioned local parameters/actions and fresh runtime authority, separate from accepted-registry promotion. The
existing Route Lab patch manager remains the sole exact-diff application and
rollback mechanism, while the learning registry binds candidate hash, replay
evidence, affected reliability evidence, prior solution, promotion, and atomic
registry restoration. See [adaptive assistance and solution learning](learning.md).

## Grounded Tell

Tell is the advisory-only path through the shared companion core. A request
contains the game and goal identities, a stable segment checkpoint, explicit
observation source and freshness, bounded observed facts, spoiler preference,
and protected decisions. Adapter observations require current evidence;
player-reported observations remain labeled as such and can authorize only
Tell.

Mario player guidance lives in `data/tell/mario.yaml`, keyed by stable segment
IDs. The loader cross-validates it against supported product goal contracts and
the segment catalog: coverage must exactly match solved normal-gameplay scope,
with no missing, duplicate, orphaned, planned, bridged, or unsupported record.
Goal contracts continue to own route identity and order; segment contracts own
start, success, failure, and accepted evidence. The Tell catalog adds only
actions, cues, risks, recovery, protected-action declarations, spoiler-sized
detail, and source references.

Every factual card item carries typed provenance identifying the current
adapter observation or player report, goal contract, segment contract,
accepted knowledge record, and accepted evidence record. Missing or
contradictory checkpoint facts, stale state, game mismatch, incomplete
provenance, or protected-action conflict fails closed. A Tell card cannot
create a session outcome, send input, or construct a completion handoff.

## Review-only Show

Show uses an adapter-neutral request, capability, cue, lifecycle, session,
outcome, and artifact-reference contract. Mario supports exactly
`world_1_1_clear`. Its definition in `data/show/mario.yaml` is cross-validated
against the selected goal, solved normal-gameplay segment, Tell knowledge, and
exact observer events.

The local server owns at most one background Show controller. It launches one
fresh visible FCEUX process without savestates or retries, stops after 1-1,
streams cue activity from parsed events, and remains responsive to Stop
Demonstration and Take Control. Both controls stop only the exact owned process
and retain partial evidence. Successful reconciliation requires ordered cue
events, the game-owned course-clear event, stopped input, process
relinquishment, converted images, an ordered replay manifest, and a contact
sheet. Every outcome remains review-only, non-promotable, excluded from
reliability, and explicitly denies player completion and authoritative
acceptance.

## Goal Contract

The contract defines what the agent is trying to do and what tradeoffs are
allowed. It should be machine-readable and reviewable by a human.

Responsibilities:

- Store the user's directive.
- Define objective, constraints, and success metrics.
- Define allowed tactics, such as real gameplay only, assisted transition, or
  known-state bridge.
- Define recovery policy for life loss, wrong state, timeout, and unknown state.

## Route Planner

The planner maps a goal contract to route segments.

For SMB3, a route is a sequence such as:

```text
fresh_start
-> world_1_1
-> world_1_2
-> world_1_3_whistle
-> world_1_fortress_whistle
-> world_1_5
-> world_1_6
-> world_1_airship_and_king
-> world_2_map_with_two_whistles
-> first_whistle_from_world_2
-> warp_zone_5_6_7
-> second_whistle_from_warp_zone
-> warp_zone_world_8
-> world_8_pipe
-> world_8_map_arrival
```

The selected goal contract supplies this order. World 1-4 is not part of the
active route. The planner must not infer route need from a historical script or
bridge, and it must keep planned steps visibly planned.

## Segment Runner

The runner executes one segment at a time.

Each segment needs:

- Start condition.
- Success condition.
- Failure conditions.
- Input strategy.
- State observations.
- Retry/recovery policy.
- Evidence artifacts.

`segments.py` loads and validates explicit segment catalogs referenced by the
selected goal's `segments.catalog`. The goal supplies ordered route membership;
the catalog supplies each segment's conditions, strategy and evidence metadata.

## Emulator Adapter

The adapter hides emulator-specific details.

Current adapter:

- FCEUX Lua script for memory-aware state reads and controller writes.
- Python harness for launching, logging, parsing, and screenshot conversion.

Future adapters can target different emulators or games as long as they provide:

- `observe_state`
- `send_input`
- `save_checkpoint`
- `load_checkpoint`
- `reset`
- `capture_artifacts`

## State Observer

The observer turns raw emulator state into game facts.

Examples:

- Current mode: map, level, transition, death, inventory, special scene.
- Mario position, form, movement state, and lives.
- Map cursor position and world progress.
- Inventory state.
- Segment progress markers.

The observer must be able to detect "we died and returned to map" as different
from "we cleared the level and returned to map."

## Recovery Manager

Recovery is the difference between a scripted bot and a useful agent.

Initial recovery cases:

- Life lost inside a segment: log death, decide whether to continue from next
  life or reset the segment.
- Wrong map node: run map-position correction only if the route contract allows
  bridge steps.
- Timeout or stuck state: capture screenshots and stop the segment.
- Known transition bug: apply an explicit bridge and label the artifact as
  bridged.

The manager should never hide a bridge or recovery decision. It should log the
mode used.

## Reviewer

The reviewer explains failed attempts, groups notes into issues, and recommends
the next experiments.

Minimum output:

```text
segment: world_1_4
result: failed
classification: input_timing
evidence: last progress marker was x=639, then bad_state
likely cause: lost form or speed before the moving-platform gap
next experiment: reduce throttle/capture overhead or adjust the gap trigger
```

LLM review is useful here, but the facts must come from logs and artifacts.

## Note Collector

The note collector preserves user observations as artifacts attached to a
specific attempt session.

Examples:

- "1-1 around 320 timer: falls into the hole and usually gets lucky."
- "Castle flight starts too far right, then hits the ceiling blocks."
- "This run is watchable-speed only; do not promote from it."

Notes should preserve the raw user text and optional anchors such as segment,
attempt number, frame, event, screenshot, wall-clock time, or in-game timer.
Machine interpretation belongs in the review, not in the raw note.

## Issue Ledger

The issue ledger turns a batch of notes into durable route work. It prevents the
system from collapsing a whole run into one proposal just because one note came
first.

Responsibilities:

- Group notes by segment and problem type.
- Track positive evidence and expected behavior separately from actionable bugs.
- Assign priority.
- Preserve source note ids.
- Feed variant proposal generation and UI summaries.

## Route Patch Manager

The route-patch manager protects the known-working route while experiments
happen. `route_patch.py` is the only executable validation, promotion, and
rollback implementation; descriptive proposals do not mutate route code.

Responsibilities:

- Consume proposed variants and Codex task output from reviews.
- Record parent variant, source session, source notes, and intended changes.
- Normalize reviewed issues and Codex output into `beat-mario.route-patch/v1`.
- Enforce path, file-type, hash, allowlist, size, and provenance policy before
  any accepted-tree write.
- Apply exact postimages in detached Git worktrees and validate candidate code.
- Compare candidate artifacts with gates run against the parent commit.
- Atomically promote only the exact validated diff and write its inverse.
- Refuse rollback when later edits conflict with the promoted postimage.

## Codex Task Builder

The task builder packages a selected issue for Codex CLI or another patch agent.

It should include:

- session manifest
- notes and issue ledger
- selected issue
- nearby log excerpts
- segment catalog
- relevant route source files
- relevant-file allowlist
- concrete route-patch schema and source provenance

Codex returns content and hashes, not commands or decisions. The shared Route
Lab backend selects validation profiles, runs argv arrays without a shell,
compares, promotes, and rolls back through explicit lifecycle gates.

## Knowledge Store

Durable knowledge should be explicit, not buried in chat history.

Examples:

- "World 1-3 whistle requires the white-block crouch route."
- "The fortress whistle route requires flight; current implementation uses a
  bridge."
- "Visible demo throttle can change timing and should not be treated as a
  reliability gate."
- "World 1-4 is diagnostic history, not part of the active World 2-first
  double-whistle route."
- "The Airship/King transition is required before World 2 but cannot satisfy
  World 8 arrival."

This can start as YAML/Markdown and later move into structured storage.

## Dynamic Run Library and Takeover Controller

`run_library.py` owns append-safe local profile/run records and deterministic
fastest-observed indexes. Comparison compatibility includes game and level
identity, profile version, start/end boundaries, timing units, emulator
assumptions, and required evidence. Evidence keys make repeated processing
idempotent while preserving all distinct attempts.

`takeover.py` owns authorization, exclusive player/agent ownership, control
epochs, nonce replay protection, neutralization, terminal reasons, and
handback reconciliation. It does not invent game tactics. Adapter capability
data supplies replay-safe accepted solutions and scopes. The Mario live manager
binds this state machine to the opt-in Lua wrapper and the same FCEUX process;
the original passive observer remains a separate no-write path.

## Mario Product Session

`mario_product.py` is the adapter-owned presentation and product-session
boundary. It reads `data/mario/product.yaml` for supported identity and
capability contracts, detects the local game file and FCEUX, persists only safe
local player preferences/history, maps runtime observation and takeover state
to player lifecycle stages, and supplies plain-language unavailable and
recovery reasons.

The product manager never persists or restores authorization, control epochs,
process ownership, reclaim state, or write capability. `lab_ui.py` composes this
with the observation, objective, Show, takeover, run-library,
learning, scenario, and metrics views. The main page is player-first; `/lab`
exposes capability snapshots, first-use state, process/input ownership,
scenario readiness, missing final evidence, pilot manifest, and recovery state.

`data/scenarios/mario-owner-pilot.yaml` is the prepared, disabled owner-pilot
contract. It cannot populate feedback or acceptance and cannot upgrade
technical evidence.

`scenarios.py` also owns the retained V2 campaign readiness model and candidate-manifest
validation. Catalog status and implementation evidence determine implementation
readiness; exact clean Git identity, authoritative contract hashes,
deterministic gate records, fixtures/assets, safety requirements, and blank
owner fields determine campaign entry. Scheduled technical validation and
pending owner action are completion blockers for that versioned campaign. The
active private-beta delivery path follows the engineering plan linked above.

## Experimental adapter onboarding and discovery

This is the existing contributor infrastructure reference. The future guided
advanced-user add-game product is deferred until Mario coaching and Stardew
delegation are implemented; its discussion and implementation are not the next
engineering task or an initial beta launch gate. An installed scaffold does
not add playable no-code game support.

`experimental_adapters.py` owns the versioned adapter contract, deterministic
data-only scaffold, conformance report, source inventory, atomic manifest-owned
installation, integrity status, exact removal, and installed-provider discovery.
The shared registry receives discovered provider objects beside the explicit
Mario and Stardew built-ins; it contains no Experimental game-ID branches.

Generated scaffolds contain only known YAML, JSON, and README files. Detection
is names and visible-window text, observation is declared local read-only data,
and input is ordinary action tokens dispatched only by a separately implemented
host allowlist. No command, code, driver, module, URL, or dependency can be
generated. Provider capability truth remains declared or unsupported and the
catalog forces Experimental/live-unproven labeling.

Installation stages under the destination root, hashes the complete inventory,
writes a local ownership manifest, and atomically promotes only into an absent
adapter-ID directory. Removal rechecks every owned hash and refuses unknown,
modified, symlinked, ambiguous, or active state; it never reaches the external
evidence and history namespaces.
