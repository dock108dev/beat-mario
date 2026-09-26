# Current source-of-truth map

This map describes code ownership and supported interfaces. Source identity and
qualification evidence are separate: changing an implementation does not qualify
a new delivery. See the [delivery record](b8-personal-delivery.md) for retained
build identity and review limits.

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
