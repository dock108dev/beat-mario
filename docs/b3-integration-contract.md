# Stardew integration and evidence contract

Updated October 4, 2026. The initial private beta requires both **Codex-backed
conversational intention** and **gameplay understanding, action selection and
replanning**. One provider may serve the two roles. This document defines the
Stardew adapter work beneath the shared [architecture](agent-architecture.md) and
[engineering plan](private-beta-engineering.md).

## Current behavior and its limits

| Area | Existing implementation/evidence | What remains missing |
| --- | --- | --- |
| Prepared-farm setup | Separate Day 2/Day 5 disposable copies, matching calibration, PID-bound image-reviewed preparation | Ordinary release setup must include its required local assets and explain compatibility without engineer file edits |
| Watering | Real selected-patch watering, discussion, revised approval, resource reconciliation, return and Stop | General observed task choice; broader crop identification; tool/refill support where claimed |
| Planting discussion | Live season/crop-rule discussion and calibrated location recommendations | Gameplay reasoning about unfamiliar supported observations; actual planting is a separate action capability |
| Eastern inspection | Live fresh findings, reviewed continuation, farmhouse return and saved reopening | General observation-driven inspection and navigation beyond authored viewpoints |
| Farm Cave | Conversation/control/persistence code, western survey, newer installed manual tool-free route and baseline/final reconciliation | Manual route record explicitly marks ordinary activity unverified; no complete companion delegation claim |
| Language | Deterministic request matching and explicit follow-up handling | No Codex-backed conversational interpretation on this path |
| Game decisions | Configured graph search, calibrated perception, closed-loop native pulses and authored activity lifecycle | No integrated AI state reasoning, reusable skill composition and online replanning |
| Persistence/control | Saved results without restored authority and independent handback | Extend to pending inference, evolving state and model-selected activity |

Read [watering](gc3-watering-verification.md),
[planting](gc3-planting-verification.md),
[inspection](gc3-inspection-verification.md) and
[cave](gc3-cave-verification.md) records for exact scope and source identity.
Those real foundations do not establish the AI-player product or a released
artifact. Another fixed corridor alone does not satisfy the next milestone.

The cave verification document retains an earlier incomplete survey checkpoint.
Newer [manual route qualification](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/gc3-cave/20261004-completion/manual-route-qualification.json)
records approach/return, unchanged 15 dry crops, energy 270 and water 40, and
confirmed manual handback. It explicitly sets ordinary activity verification to
false. Preserve both evidence classes; installing a route does not establish the
ordinary request/approval/findings/return loop.

## Existing ownership to reuse

- `stardew_setup.py`: source/copy identity, isolated loading, persistence and
  the current image-reviewed preparation path.
- `stardew_input.py`: native pulse bounds, foreground/process/window checks
  and release.
- `stardew_perception.py`, `stardew_farm_perception.py`,
  `stardew_farm_vision.py`, `stardew_planting.py`: current visible-state
  recognition and calibrated game observations.
- `stardew_viewpoint_navigation.py`, `stardew_farm_navigation.py`:
  configured route search and observed movement.
- `stardew_runtime.py`, `stardew_adapter.py`,
  `stardew_companion.py`, `stardew_farm_tasks.py`: action authority,
  resources, protection, reconciliation and outcomes.
- `request_planning.py`, `stardew_planning.py`,
  `conversation_service.py`, `conversation_ui.py`: current typed plans,
  ordinary discussion and proposal/review/start flow.
- Shared Codex integration, knowledge, skill catalog and memory: extend these
  boundaries rather than creating another independent input path.

The initial all-crop B3 watering contract remains historical: every initially
planted crop, including already-watered inventory entries, followed by return.
Current selected activities preserve the complete observed initial protection
boundary while executing only the approved selected work. Neither contract can
silently turn an observed subset into a claim about the whole farm.

The historical Day 5 combined routine completed on source
`ed84e02a095d00df858cfd286fa458fb85267f983561b36483a5dfb712653b94`;
its [closeout](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b8-final-return-repair/20260926/closeout.md) retains
the separate seed/profile and evidence boundaries. It does not qualify later
AI behavior or a package.

## Next engineering work and initial-beta acceptance

Start with an actual **decision-and-replanning loop** in Stardew's slower
activities. The conversational role interprets player intent; the gameplay role
uses fresh scenes, mechanics, implemented skills and history to select useful
work. The app validates and executes that work. Do not treat conversational
paraphrasing as a substitute for gameplay reasoning.

### Conversational intention contract

Interpret held-out natural language, references, corrections and preferences.
Produce a typed proposal containing goal, observed targets, requested outcome,
time/resource limits, protection, return/stop expectations, ambiguities and
observable success criteria. Preserve the original words and contextual
references. Clarify uncertainty when it affects the intended work.

Discussion can compare alternatives, explain mechanics or request a better view.
A model reply does not authorize movement or farm work. Contextual approval binds
the displayed current scope; an old yes or delayed model reply cannot revive an
outdated plan. Examples such as watering a crop group, finding a suitable
planting area and visiting a cave illustrate intentions, not a finite vocabulary.

### Grounded game state and perception

Build a current game-owned state representation suitable for the declared farm
coverage:

- Player position, facing/movement and camera transform, with uncertainty.
- Terrain, observed obstacles, traversable space, meaningful landmarks,
  interaction reach and protected areas.
- Crop/plot identity and state where actually identifiable; unknown species or
  watering state stays unknown.
- Selected and owned tools, inventory/resources, water/energy, season/day/time
  and relevant menus.
- Current targets and outcomes, past observations and regions not yet inspected.

Combine suitable visible perception methods with image-based model understanding
where useful. Calibrated pixels can remain strong checks for known values, but a
new scene should not always demand a new exact raster template. Evaluate robust
player/entity recognition, tracking, camera movement and changed-object
detection within the chosen supported settings.

Carry evidence source, timestamp, confidence and identity with observations.
Historical/off-screen state is not fresh truth. Use temporal consistency and
independent checks for consequential actions; disagreement triggers reacquisition,
a supported inspection, a question or a stop. Stardew current truth remains
visible-game observation, not hidden save parsing used to bypass perception.

Separate state estimation from interpretation of mechanics and from action
authorization. A VLM's plausible object label or asserted confidence alone does
not establish tool ownership, exact resource count or a verified effect.

### Mechanics and knowledge

Provide a game-owned knowledge source for supported activities: crop/season and
growth rules, terrain/occupancy, tools and interaction range, water/energy use,
navigation and chosen cave limits. Identify the relevant game/version and
provenance. Stable mechanics, current observations, player reports and learned
hypotheses remain distinct.

Use that knowledge to make decisions. For example, a changed crop preference
affects the suitability discussion; a shortage changes the task or proposes a
supported remedy. A recognized crop name does not identify the observed crop,
and a guide entry does not prove a currently owned tool or seed.

### Reusable skills and online navigation

Expose capabilities from the real implementation as a machine-readable catalog.
Every skill supplies its allowed parameters, observed preconditions, expected
effects, verification, resource/time limits and interruption behavior.

Useful families include observe/inspect, move toward an observed target, face or
aim, supported tool/interaction, and return/release. Engineering determines the
decomposition. Tool selection/refill belongs in the catalog only when actually
implemented and qualified. Existing Day 5 macros may remain narrowly labeled
fallbacks, not evidence of general task composition.

Move from a configured-corridor-only planner toward a map or spatial
representation built and updated from observations within the declared region.
Combine suitable path search/local motion planning with gameplay reasoning.
Maintain observed obstacles, unknown areas and valid return options. The model
selects subgoals and inspection/recovery choices; deterministic movement keeps
pulses bounded and uses fresh position feedback.

Support a meaningful detour or different target without adding an engineer-authored
edge for that exact variation. Stop/reacquire when localization is unreliable.
Inspect unknown space before committing movement where needed, and refuse
unsupported or protected terrain. Clearing an obstacle is a separate tool action
and authority scope; a blocked walk does not grant clearing permission.

Independent validation rejects invented capability IDs, unobserved target
references, invalid parameters, incompatible sessions and expanded authority.
The AI may compose implemented skills, never manufacture new native commands.

### Verify, replan and remember

At each meaningful skill boundary:

1. Compare the expected result with fresh observed position, target state and
   resources.
2. Credit only confirmed work; retain partial or ambiguous effects.
3. Update state and the remaining goal.
4. Choose the next skill, inspect further, try a supported alternative, discuss
   a changed plan or stop.
5. Preserve the decision and outcome so compatible later choices can use it.

Stalls, obstacles, hidden targets, shortages and changed preferences must produce
actual decisions. Repeating a failed pulse or changing only the status message is
not replanning. Unknown effects are not blindly repeated.

Persist goal context, observed facts, chosen actions, expected/actual effects,
failures, useful discoveries and user corrections. Show why compatible memory
changes a subsequent choice, and support inspection/reset of future guidance
while retaining outcomes. Do not turn replay history into current game truth.

### Timing, authority and discussion

Stardew's slow loop can use Codex at activity/subgoal boundaries. Define request
limits, cancellation, responsiveness and the safe state while inference is
pending. Native input is released before conversation or slow planning.

Approval may cover a bounded collection of supported skills and alternatives.
Within-scope replanning does not need a new approval for every pulse. Material
scope expansion, revised protected choices, expired/revoked authority or a new
session requires a fresh displayed proposal. Discussion preserves completed work;
returning focus does not silently resume.

Stop and Take control revoke authority and release input independently of model
availability, capture, persistence and service locks. Late replies cannot apply to
a new control epoch. Reopening retains knowledge/results only.

### Setup and useful coverage

Initial private-beta scope can be bounded to explicitly supported farms, display
settings and activity families. It must still handle meaningful variation within
that scope, rather than requiring a new scripted route for every request.

Finish the ordinary setup path: game/window detection, supported settings,
permissions, Codex availability/authentication, selected disposable source,
isolated loading and current observation. State manual prerequisites accurately
and remove engineer-only asset registration from the advertised release path.

Required prepared assets must be available to the local released app through an
explicit setup/bundle path; ignored files on the engineering checkout do not
satisfy that. Do not bundle game files, credentials or personal saves.

An owner-selected save path requires backup/copy isolation and a suitability
assessment before use. It can remain outside the initial supported matrix if
clearly labeled. The player's original save is never modified to make
qualification pass.

## Required gameplay proof

Choose a useful supported activity and complete it through ordinary conversation
with a changed goal or gameplay condition. Demonstrate:

- A real Codex interpretation and game-state decision reaches actual execution.
- Fresh observations ground the chosen targets and skills.
- A meaningful changed condition causes a revised action/approach without a new
  phrase matcher, pixel template or route script for that individual check.
- Expected effects are compared with actual work, resources and return/handback.
- A second supported variation uses the same reusable skills.
- Compatible memory changes a later decision.
- Questions remain input-free; discussion, interruption, inference failure and
  reopening preserve correct ownership and outcomes.

Watering and planting-location discussion remain useful acceptance families.
Cave reconnaissance may provide a spatial case when its approach is actually
supported; a disabled cave plan or completed fixed route alone does not finish
the AI milestone. Interior exploration, combat/mining and arbitrary farms remain
separate capability decisions.

## Evidence and local private-beta release

| Evidence | What it establishes |
| --- | --- |
| Focused logic/fixtures | Goal contracts, proposals, validation, memory, concurrency and synthetic perception |
| Held-out language/state evaluation | Interpretation and decision behavior beyond authored examples |
| Retained-frame replay | Recognition/decision behavior on those frames, without native action or current freshness |
| Real disposable gameplay | Actual perception, selected actions, changed effects, replanning and native handback for the tested scope |
| Exact local artifact walkthrough | First use, Codex setup, assets, connection, AI activity, Stop and saved reopening in the released build |
| Owner usefulness review | Whether that artifact delivers understandable, useful delegation |
| Release record | Exact local beta identity, support matrix, known limits and rollback/recovery |

Run the relevant shared and adapter checks, then evaluate real task success,
interventions, refusal quality, repeated failures and decision latency over the
declared configuration matrix. Keep setup assistance visible. A large repository
test count does not establish game understanding or beta acceptance.

The app is private and local. The selected Codex CLI still uses its configured
model provider; local app data and provider-submitted images/context must be
described accurately. Complete backend failures, cancellation, shutdown, history
and save-preservation behavior before releasing the exact local candidate.
No public SaaS deployment is required.

Preserve working Mario evidence and shared control boundaries. Recording remains
deferred to tentative beta v2. Minecraft connection with accurate capability
labels belongs in the initial beta; full Minecraft gameplay and advanced no-code
addition of other games remain later work.
