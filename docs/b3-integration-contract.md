# Stardew integration and evidence contract

Adapter interface and evidence reference for the bounded Stardew path, updated October 3, 2026 for the corrected product direction. The [private-beta engineering plan](private-beta-engineering.md) owns current priorities and release scope; the B3 evidence classes below retain their original task and candidate boundaries.

Stardew is the second initial-beta gameplay priority, after Mario. The target is conversational delegation of clicking activities: understand the user's goal, discuss a short plan for the next few minutes, accept an explicit yes for that plan, observe and execute, report what happened, then discuss corrections or the next activity. The existing prepared farm routines are a foundation for that target. They do not qualify arbitrary-farm delegation, choosing a corn planting location, watering tomatoes or exploring a cave.

The current bounded Stardew integration owns disposable-session setup, visible perception, ordinary input and watering.
Qualification requires actual isolated-game evidence on the tested source candidate.
A working browser, fixture, copied directory or parsed request cannot satisfy it.
Full beta readiness and owner acceptance are separate.

## Current module ownership

- `stardew_setup.py` owns explicit source/destination selection, source classification,
  loading/persistence verification and fresh session attempts. The guarded fresh-game
  launcher pins inspected binaries, redirects XDG config/data, blocks primary paths
  and network access, and never grants input by launching. No automatic owner-save discovery.
- `stardew_input.py` owns bounded ordinary native input and neutralization, with
  foreground and process/window identity checked before input.
- `stardew_perception.py` owns supported viewport recognition. Automatic recognition
  requires a qualified pixel profile and complete coverage; unknown resources remain unknown.
- `stardew_runtime.py`, `stardew_adapter.py` and `stardew_companion.py` own volatile
  Stardew authority, observation validation, execution and watering reconciliation.
- `request_planning.py` and `stardew_planning.py` own proposals and corrections.
  A proposal is never permission to act.
- `conversation_service.py`, `conversation_ui.py` and `lab_ui.py` route the ordinary
  workspace into the Stardew runtime. Mario process/controller facts never satisfy it.
- `beta_readiness.py` and `personal-beta-v3.yaml` require classified, hashed evidence
  bound to HEAD and all active source files. `--gate-b3` cannot pass from unit evidence alone.

## Review and execution boundary

The unchanged watering contract means every initially planted crop, including
already-watered targets in the initial inventory, followed by return to the reviewed
farmhouse entrance. A visible subset is not silently treated as the whole farm.
Start binds the exact reviewed proposal, session, complete target set and observation
requirements. Any supported revision is reviewed and revalidated against remaining
work; it cannot erase completed actions or resume saved authority.

Foreground gameplay input must stop when chat receives focus. Reclaim, stale
observations, process/window changes, uncertain resources, incomplete coverage and
reset revoke execution. Neutral handback and partial outcomes are recorded even
when the task cannot complete. No promise of Mario-style play while typing applies.

## Evidence classes

| Requirement | Required evidence |
| --- | --- |
| Actual source/session selection and load/persistence isolation | Visible live; owner-copy preservation only for an explicitly authorized source |
| Complete initial planted set and resource recognition | Automatic visible live; calibrated fixture profiles remain development evidence |
| Actual water changes and return point | Before/after visible live observations with reconciled resources |
| Browser request/review/authorize/execute/outcome | Browser plus actual visible live execution |
| Reclaim, focus loss and neutral handback | Actual visible live, with unit concurrency coverage |
| Stale/reset/session mismatch, shortage, uncertainty | Focused unit/integration plus bounded live checks when feasible |
| Canonical gate | Unit/integration; never gameplay or owner acceptance |

## Selected farm-action extension

`stardew_farm_tasks.py` owns selected harvest, planting, watering and small-stone
clearing ledgers. Planning and runtime eligibility require supported targets,
owned tools/seeds, visible resources, inventory capacity and observable
postconditions. The browser routes reviewed proposals through the same session,
reclaim and handback boundaries. The original all-crop watering contract remains
separate from selected Day 5 work. See the [Stardew guide](stardew-operator-guide.md)
for the supported configurations and target limits.

The retained September 26 final-return repair completed the Day 5 combined routine,
resource reconciliation, return and independent released-input verification on
source `ed84e02a095d00df858cfd286fa458fb85267f983561b36483a5dfb712653b94`.
Its [closeout](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b8-final-return-repair/20260926/closeout.md) supersedes
the earlier in-place delivery readiness failure without rewriting that attempt.
Day 2 and Day 5 keep their original separate identities. This proof does not
qualify later source, a packaged beta, new crops, other farms or exploration.

## Next engineering work and initial-beta acceptance

Reuse the current request, runtime, input, history and setup owners. Expand their
actual supported gameplay rather than creating a second service or presenting
unimplemented activities as ready plans. A broad request can produce a discussion
or clarification before all of its actions are supported; it must not gain Start
eligibility until the applicable execution and outcome checks exist.

| Concern | Existing owners to extend | Required next behavior |
| --- | --- | --- |
| Intent, planning and dialogue | `request_planning.py`, `stardew_planning.py`, `conversation_service.py`, shared model gateway | Interpret activity goals and references, discuss choices, propose a short activity with limits, accept corrections and distinguish advice from executable work. Model proposals remain advisory until validated against current observed state and implemented actions. |
| Visible game state | `stardew_perception.py`, `stardew_farm_perception.py`, `stardew_farm_vision.py`, `stardew_adapter.py` | Broaden supported crop, plot, tool, inventory, resource and location recognition beyond the two prepared configurations; preserve uncertainty and identify missing observations. |
| Navigation and activities | `stardew_viewpoint_navigation.py`, `stardew_farm_navigation.py`, `stardew_farm_tasks.py`, `stardew_runtime.py` | Implement observable routes and activities for the chosen expansion, with recovery and postconditions. Choosing a planting location, tomato watering and cave exploration each require their own supported state/actions; configured farm corridors alone do not supply them. |
| Approval and conversation during play | `conversation_service.py`, `conversation_ui.py`, `stardew_runtime.py`, `stardew_input.py` | Bind explicit yes to the exact current short plan and session, safely release input for discussion, replan remaining work and request new approval when scope changes. Keep Stop/Take control independent of inference and reporting. |
| Save suitability and preservation | `stardew_setup.py`, existing session/loading verification | Engineer backups and copy isolation before offering an owner-selected save; verify that the copy loads and is suitable for the proposed work. Never assume the prepared-farm profile fits it or modify the original to make setup pass. |
| Progress, results and continuity | `stardew_farm_tasks.py`, `stardew_runtime.py`, `conversation_service.py`, shared outcome/history owners | Report confirmed actions, unfinished work, uncertainty and released control in plain language; preserve corrections and useful context without restoring input authority. |

The next implementation plan must identify which configuration and activities it
will support. The following owner requests are the initial-beta product targets;
partial engineering delivery must name which remain blocked:

1. **“lets explore and find a good spot to plant corn”.** Observe the supported
   location, relevant resources, season and owned materials; explain what makes a
   spot suitable and discuss a candidate before planting. Do not invent unseen
   terrain, available seeds or crop compatibility. Planting requires implemented
   preparation/planting actions and approval of that scope.
2. **“time to water the tomatos”.** Identify the intended observed crop group,
   clarify an ambiguous reference, propose the near-term watering activity and
   carry it out after approval. Confirm the actual changed crops and resources.
   Water availability, refill and return behavior must match implemented support;
   a clicked target alone does not prove watering.
3. **“lets go explore that cave”.** Resolve which cave and the supported approach,
   discuss the next few minutes and any relevant limits, then execute the approved
   supported exploration activity. Unknown routes or missing cave actions remain
   explicit blockers. A plan must not imply that fighting, mining or other cave
   actions are available merely because navigation is available.
4. **Conversation and correction.** A short proposal is understandable without
   crop IDs or engineering terms. Explicit yes starts only its current scope.
   The user can interrupt, ask what is happening or change the plan; native input
   is safely released for discussion, confirmed work remains recorded and revised
   remaining work gets the required new approval.
5. **Control and continuity.** Stop/Take control releases actual input promptly,
   including during observation, planning and outcome work. Unconfirmed release
   stops native qualification. Completed, partial and failed outcomes are
   understandable; reopening retains configuration/history and explains fresh
   session and approval requirements.
6. **Ordinary setup and personal-data preservation.** The supported configuration
   can be prepared through the documented app flow. Any future owner-save path
   proves backup/copy preservation, loads the correct isolated copy and states
   suitability limits. Setup effort and every engineer-assisted action are product
   findings, separate from gameplay completion.

### Verification boundaries for the expansion

- Focused unit/integration checks cover intent and clarification, proposal/yes
  binding, stale and changed plans, resource/target uncertainty, interruption races,
  partial accounting and save-preservation logic. Fixture tests do not establish
  crop recognition, exploration or native input release in the game.
- Actual disposable-game evidence must follow the ordinary conversational flow
  for each newly claimed activity/configuration, retain the exact candidate and
  before/after observations, and independently confirm outcome and input release.
  Existing Day 2/Day 5 proof may support unchanged behavior only with explicit
  source continuity; new support requires its own evidence.
- Engineering assistance, manually prepared starting states and failure recovery
  must be retained and labeled. They cannot be presented as ordinary user setup
  or silently erase a partial attempt.
- Package checks and owner usefulness review remain distinct from source-level
  gameplay proof. An exact package must include the app-owned dependencies and
  setup assets required for its claimed support; ignored local assets do not
  establish tester availability. Product acceptance and any launch/distribution
  decision are separate records.
