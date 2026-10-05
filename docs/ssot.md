# Current source-of-truth map

## Active AI beta ownership

GC-A0–GC-R in the [engineering plan](private-beta-engineering.md) replace the old slice-by-slice continuation. Current module owners below remain implementation foundations. The contextual LLM and gameplay decision interfaces are required additions; their exact module layout is an engineering choice.

| Responsibility | Current owners to reuse | Required seam |
| --- | --- | --- |
| Contextual language | conversation_service, request_planning, model_gateway | Codex provider plus typed original intent, context and clarification |
| Working game state | live_observation, Stardew observers, feedback_contracts | Fresh semantic entities/images, uncertainty, history and scene continuity |
| Gameplay decisions | adapter planning/runtime, skill_runtime | Goal/subgoal/action selection, expected effect and observed replanning |
| Skill validation/control | takeover, Mario Lua, stardew_companion/input/runtime | Composable finite skills under existing independent authority/release |
| Memory | learning, run_library, custom_variants and discussion stores | Contextual retrieval and evidence that guidance changes a later decision |
| Product/delivery | catalog, player_setup/store, app_runtime, delivery/readiness | Both-game/provider setup, app-owned assets and new beta criteria |

A real model decision must reach the controller and receive an independently observed effect. Do not duplicate native input owners or label an existing deterministic planner as the new AI layer.

This map describes code ownership and supported interfaces. Source identity and
qualification evidence are separate: changing an implementation does not qualify
a new delivery. The [private-beta engineering plan](private-beta-engineering.md)
owns release scope; the [PM handoff](private-beta-pm-handoff.md) records the current
delivery candidate, limitations and next work. The [B8 delivery record](b8-personal-delivery.md)
retains its September 26 build identity.

The [product direction](product-direction.md) now requires initial-beta Mario coaching and Stardew activity delegation. GC-A0–GC-R in the active plan own upcoming AI integration and release work; no existing readiness flag or historical evidence qualifies that full experience. Minecraft and advanced-user no-code onboarding follow implementation of the first two gameplay experiences. The domain map below describes existing owners to reuse, not completed new features.

Domain: Ordinary player setup and Minecraft onboarding progress
SSOT module/file: `src/smb3_agent/player_setup.py`, with read-only progress in `player_onboarding.py`
Why this is authoritative: Coordinates profile operations, conversation, current
Minecraft state and prioritized direct controls. Setup progress derives from the
selected profile and actual session/feature state.
Known callers: `lab_ui.py` at `/setup`, `/minecraft` and `/help`; `player_setup_ui.py`.

Domain: Minecraft feature eligibility and live lifecycle
SSOT module/file: `src/smb3_agent/minecraft_session.py` (`CHECKED_FEATURES`, `MinecraftPlayerSession`)
Why this is authoritative: Owns available task families, volatile connection,
review, cancellation epoch and active input owner. The current flags enable
calibration/camera; aim/move/place/wall await practical integration checks.
Known callers: Player setup service, Minecraft planner, native runtime.

Domain: Finite Minecraft execution and observed outcomes
SSOT module/file: `src/smb3_agent/minecraft_native.py`, `skill_runtime.py`, `minecraft_wall.py`
Why this is authoritative: Selected-window observations and independently checked
outcomes drive finite execution. Child and composite deadlines, position/settings
guards and neutralization constrain work; model output and saved configuration
cannot establish a gameplay fact.
Known callers: `MinecraftPlayerSession`, calibrated camera provider, spatial skill provider.

Domain: Player profiles, local outcomes and issue reports
SSOT module/file: `src/smb3_agent/player_store.py`
Why this is authoritative: Validates bounded configuration, saves profiles and
sanitized history/reports outside the application installation, and restores no
live window, reviewed plan or input authority.
Known callers: Player setup service, Minecraft session and packaged launch.

Domain: Mario traversal feature policy
SSOT module/file: `src/smb3_agent/mario_route_contract.py`
Why this is authoritative: Defines implemented primitive IDs, ordered stops,
allowed path/stop combinations, and supported playback speeds once. It does not
accept routes or grant live control.
Known callers: `mario_route_plan.py` (including selected-target resolution),
`mario_plan_runtime.py`; `live_observation.py` uses runtime field validation.

Domain: Accepted Mario route identity
SSOT module/file: `src/smb3_agent/takeover.py` (`supported_solutions`) and goal contracts through `goals.py`
Why this is authoritative: The accepted solution registry supplies executable
route identity; a conversational plan cannot invent an accepted variant.
Known callers: `mario_route_plan.resolve_base_route`, takeover execution,
`conversation_service.py` compatibility checks.

Domain: Catalog and game switching
SSOT module/file: `src/smb3_agent/companion_catalog.py`
Why this is authoritative: Validates provider identities/capabilities and
coordinates switching through each provider's runtime hooks.
Known callers: `lab_ui.py`, catalog providers, CLI inspection.

Domain: Stardew execution authorization
SSOT module/file: `src/smb3_agent/stardew_companion.py`
Why this is authoritative: Owns Tell/Show/Do control rules, per-input validation,
reclaim, and handback. `stardew_runtime.py` orchestrates this controller rather
than deriving input authority from saved history. `stardew_setup.py` owns copy
isolation; `stardew_farm_tasks.py` owns action ledgers.
Known callers: Stardew runtime, adapter/input boundary, ordinary conversation flow.

Domain: Saved conversation outcomes
SSOT module/file: `src/smb3_agent/custom_variants.py`
Why this is authoritative: Persists descriptive plans and append-only outcomes;
reopening requires a fresh observation/review and explicit Start.
Known callers: `conversation_service.py`, ordinary UI history.

Domain: Source identity
SSOT module/file: `src/smb3_agent/beta_readiness.py` (`source_identity`)
Why this is authoritative: Hashes the active nonignored source including
uncommitted files; HEAD alone is insufficient.
Known callers: `delivery.py`, beta-readiness inspection.

## Enforcement and removal decisions

- Planner and runtime now consume the same traversal table. Removed separate
  primitive/path/stop definitions, duplicate hop-limit validation, and the
  runtime's duplicate advertised speed list.
- Deleted runtime `BOUNDARIES`: no caller in source, tests, scripts, or config.
- Removed flat `action.primitive_id` and primitive-as-action-kind compatibility.
  Current planner and runtime fixtures produce `kind: mario_traverse` with
  `parameters.primitive_id`; no supported producer of the aliases was found.
  Noncanonical actions now fail runtime validation. Historical artifacts were
  excluded from deletion and remain readable as evidence, not executable plans.
- Kept typed-plan/dictionary conversion and Mario game-name aliases: current
  planner, catalog, runtime tests, and saved-plan inspection use these boundaries.
- Kept CLI Mednafen diagnostics and experimental adapter conformance scaffolding:
  README and CLI expose these as supported diagnostic/inspection workflows;
  they do not establish live adapter qualification.
- Kept historical scenario contracts and disabled execution declarations:
  beta inspection and retained evidence rely on versioned contracts. A false
  execution declaration describes capability; it is not proof of unreachable code.
- Kept separate launch ownership for Mario and Stardew. They retain different
  owned child handles and input cleanup obligations; unifying them requires a
  separate lifecycle review and focused failure coverage.
- Kept environment/file preference resolution at current entry points. Before
  removing alternate configuration paths, compare explicit CLI argument,
  environment, and saved-preference precedence for each supported launcher.
- The FCEUX Lua controller still enforces its native input boundary independently.
  Python policy consolidation does not replace that check. Changing the wire
  vocabulary requires a separate Python/Lua protocol compatibility pass.

## Focused regression coverage

`tests/test_b2_mario_runtime.py` covers all six path/stop combinations and rejects
three removed action spellings. `tests/test_request_planning.py` exercises real
planner outputs through runtime validation for all four supported combinations.
`tests/test_conversation_service.py` protects ordinary plan/revision callers.
No live game, owner save, package, or release qualification is part of this pass.

## Experimental Mario coin accounting and selection

SSOT module/file: `src/smb3_agent/mario_coins.py`

Owns per-attempt counter reconciliation, compatible landmark-yield knowledge, experimental route selection and failure-derived next-attempt stairs/pipe instructions. `route-guidance.json` retains explicit cartridge-bound player instruction wording; plans carry the versioned instruction contract and exact supported tactic fields through runtime validation to the emulator. Conversation outcome history owns persistence; `conversation_service.py` owns review/retry/control orchestration; the Mario runtime and Lua controller own execution/observations. Accepted-route registry authority is unchanged. `tests/test_mario_coins.py` protects accounting and future-route application.

Domain: Player-controlled Mario demonstrations
SSOT module/file: `src/smb3_agent/mario_demonstrations.py`, `scripts/fceux_demonstration.lua`
Why this is authoritative: Versioned cartridge-bound player action/state traces, atomic named demonstration records, trim/integrity checks, passive frame synchronization and review images. `live_observation.py` binds recorder ownership; `mario_plan_runtime.py` and `fceux_b2_plan.lua` own approved real input application; `conversation_service.py` retains application outcomes and volatile selection/approval. Saved demonstrations do not modify accepted routes.
Known callers: Ordinary `/mario` conversation API/UI and retained outcome history.
