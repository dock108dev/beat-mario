# Game Companion Architecture

The system is a local game companion, not a pile of one-off route scripts. The
FCEUX runner is the supported live Mario execution backend. The shared
player-session layer now also contains Stardew domain contracts, a combined
catalog, regression-only orchestration, and declarative Experimental adapters.

## Components

```text
Player Session (Tell / Show / Do)
  -> Authorization and Safety Contract
  -> Game Adapter Capabilities
  -> Goal Contract
  -> Route Planner
  -> Segment Runner
  -> Emulator Adapter
  -> State Observer
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

See the [V2 roadmap](v2-roadmap.md) for the slice order and acceptance gates.
The [live-observation contract](live-observation.md) documents V2.4's exact
visible FCEUX connection, direct player-input source, read-only boundary,
continuity rules, and retained local evidence.

## B2 typed planning and bounded Mario execution

`request_planning.py` owns a registry of adapter planners and a serialized typed
plan contract. `mario_route_plan.py` and `stardew_planning.py` own actions,
capabilities, protected choices and target semantics. Advisory proposals cannot
grant permission. The local grammar supports bounded contextual requests and
keeps unsupported clauses explicit; there is no external model dependency.

`conversation_service.py` coordinates the ordinary Mario UI, reviewed plans,
exact command acknowledgments, variant compatibility and append-only outcomes.
`mario_plan_runtime.py` independently validates primitives, process and state,
then delegates a fresh bounded authority to the existing takeover controller.
B2 execution permission does not change accepted-solution or route records.
See [B2 interfaces and B3 extension points](b2-conversation-guide.md).

## Stardew companion adapter

V2.10 adds `stardew_adapter.py` beside, not inside, the Mario implementation.
V2.11 adds `stardew_companion.py` above that operator. Its adapter-owned
pipeline is:

```text
owner primary-save selection
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

The responsive renderer is a standalone Stardew surface, not a shared game
catalog. Adapter capability truth lives in `data/stardew/operator.yaml`;
fixtures, evidence, and owner-pilot contracts remain separate under
`data/stardew/` and `data/scenarios/`. V2.12 adds cross-game selection without
changing Stardew's standalone contract. See the [Stardew companion guide](stardew-operator-guide.md).

The live Stardew domain objects are not yet wired to a public configuration or
start command. The CLI and `/stardew` route expose inspection and a safe
unconfigured render only; constructing a copied-save controller, live window
backend, and ordinary-input driver remains a separate integration slice.

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

V2.13 adds `unattended.py` as a separate adapter-neutral engineering runner.
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

The V2.6 run library remains the immutable observed-run source. V2.7 wraps each
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
takeover capabilities. Owner review permits later replay validation only. The
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
outcome, and artifact-reference contract. Mario V2.3 supports exactly
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

The current Lua route runner already has several implicit segments. The next
step is to promote those into an explicit segment catalog.

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

`mario_product.py` is the V2.9 adapter-owned presentation and product-session
boundary. It reads `data/mario/product.yaml` for supported identity and
capability contracts, detects the local game file and FCEUX, persists only safe
local player preferences/history, maps runtime observation and takeover state
to player lifecycle stages, and supplies plain-language unavailable and
recovery reasons.

The product manager never persists or restores authorization, control epochs,
process ownership, reclaim state, or write capability. `lab_ui.py` composes this
with the V2.4–V2.8 observation, objective, Show, takeover, run-library,
learning, scenario, and metrics views. The main page is player-first; `/lab`
exposes capability snapshots, first-use state, process/input ownership,
scenario readiness, missing final evidence, pilot manifest, and recovery state.

`data/scenarios/mario-owner-pilot.yaml` is the prepared, disabled owner-pilot
contract. It cannot populate feedback or acceptance and cannot upgrade
technical evidence.

`scenarios.py` also owns the V2.14 readiness model and candidate-manifest
validation. Catalog status and implementation evidence determine implementation
readiness; exact clean Git identity, authoritative contract hashes,
deterministic gate records, fixtures/assets, safety requirements, and blank
owner fields determine campaign entry. Scheduled technical validation and
pending owner action are completion blockers, not circular entry blockers.

## Experimental adapter onboarding and discovery

`experimental_adapters.py` owns the V2.14 versioned contract, deterministic
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
