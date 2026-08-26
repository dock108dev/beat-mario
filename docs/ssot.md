# Single sources of truth

This repository keeps policy in the narrowest domain owner and routes CLI,
Route Lab, tests, and documentation through that owner.

## Goal identity, composition, and display

Domain: routing, product-goal configuration, and Route Lab goal metadata.

SSOT module/file: `data/goals/*.yaml`, loaded by `smb3_agent.goals`.

Why this is authoritative: contracts declare goal identity, prefix composition,
route steps, execution state, runner preset, success metrics, and display text.

Known callers: goal CLI, command runner, segment validation, reliability,
Route Lab, recovery, and attempt lab

`load_product_goal_contracts()` discovers executable product contracts and
orders them by resolved route length. Route Lab does not maintain a second goal
id, label, or subtitle registry. Adding a product goal without a matching
reliability acceptance profile fails the SSOT drift test.

## Preset execution policy

Domain: preset-to-environment execution policy.

SSOT module/file: `src/smb3_agent/presets.py`.

Why this is authoritative: `PRESET_ENV` is the only mapping from a contract's
preset name to fixed FCEUX environment settings.

Known callers: `run_goal_contract()` and tests that verify every contract
preset is represented exactly once

Goal validation derives its supported executable presets from this mapping.
Diagnostic bridge permission derives from `DIAGNOSTIC_PRESETS`; callers do not
repeat a preset switch. Goal-local `runner.env` is rejected so a contract cannot
silently shadow the preset policy.

## Product acceptance

Domain: fresh-run counts, boundaries, focused evidence, timeouts, and
byte-identity requirements.

SSOT module/file: `src/smb3_agent/reliability.py` (`RELIABILITY_PROFILES`).

Why this is authoritative: these are acceptance rules, distinct from the goal's
route definition and the Lua executor's behavior.

Known callers: `reliability run`, `reliability watch`, route-patch validation,
and reliability tests

The profile keys must equal the product-goal contract ids. This guard prevents
either catalog from silently gaining a product path the other does not know.

## Route changes and promotion

Domain: reviewed code changes, isolated validation, promotion, and rollback.

SSOT module/file: `src/smb3_agent/route_patch.py`.

Why this is authoritative: it enforces the normalized schema, provenance,
allowlists, hashes, detached worktree, validation profile, exact promotion, and
inverse rollback contract.

Known callers: `lab patch` CLI, Route Lab patch actions, and Codex task packets

`lab propose-variants latest` may create descriptive work proposals, but they
cannot execute, compare, or promote. The former metadata-only execution and
promotion commands were removed instead of retained as failing compatibility
paths.

## Rendering and local administration

Domain: Route Lab HTTP behavior and rendering.

SSOT module/file: `src/smb3_agent/lab_ui.py`.

Why this is authoritative: one handler owns supported GET/POST routes, browser
security policy, form validation, CSRF, artifact serving, and rendering.

Known callers: `lab ui`, `lab ui-render`, the canonical gate, and HTTP tests

The static HTML renderer intentionally has no live CSRF token and is not an
interactive server artifact. The hosted server injects one token into every
POST form.

## Catalog composition and switching

Domain: built-in/Experimental provider order, catalog validation, local
selection persistence, and safe switching.

SSOT module/file: `src/smb3_agent/companion_catalog.py`.

Why this is authoritative: `build_default_catalog_registry()` is the only
production assembly of Mario, Stardew, and discovered Experimental providers.
`CatalogRegistry` validates provider-owned truth, while `CatalogSession` owns
selection, retention, invalidation, and switch evidence.

Known callers: companion CLI status/render, Route Lab startup/refresh, and
catalog tests

Mario, Stardew, and Experimental modules own their individual declarations;
callers do not reconstruct the combined provider tuple.

## Mario observation, authority, and learning

Domain: live Mario state, takeover authority, local run history, and learned
candidate lifecycle.

SSOT module/file: `src/smb3_agent/live_observation.py`,
`src/smb3_agent/takeover.py`, `src/smb3_agent/run_library.py`, and
`src/smb3_agent/learning.py`, respectively.

Why this is authoritative: each module owns one non-overlapping state machine
or persistence contract. Route Lab renders their snapshots and invokes their
public operations; it does not infer ownership, fastest-run, or promotion
state.

Known callers: Mario product/session manager, Route Lab, learning CLI, metrics,
and focused tests

## Stardew copied-save operation

Domain: copied-save identity, visible observation, ordinary input, ownership,
reclaim, mode attempts, and reset.

SSOT module/file: `src/smb3_agent/stardew_adapter.py` for low-level safety and
`src/smb3_agent/stardew_companion.py` for Observe/Tell/Show/Do orchestration.

Why this is authoritative: the adapter contract owns exact process/window/save
validation and input safety; the companion controller owns mode lifecycle and
evidence. The CLI and Route Lab use the loader's default tracked contract path
instead of restating it.

Known callers: Stardew CLI render/status, combined catalog, Route Lab, and
Stardew tests

## Scenario and metric classification

Domain: scenario identity/lifecycle/evidence eligibility, V2.14 implementation
and campaign-entry readiness, candidate manifests, and classified local metrics.

SSOT module/file: `src/smb3_agent/scenarios.py` plus
`data/scenarios/catalog.yaml`; metric schemas and aggregation live in
`src/smb3_agent/metrics.py`.

Why this is authoritative: the scenario catalog defines what is implemented,
what is eligible for later validation, and what each result can prove; the
runner enforces transitions. Candidate manifests bind the exact clean Git
identity, authoritative contract hashes, deterministic gate records, and blank
owner fields. Readiness keeps entry separate from completion. Metrics accept
those classifications without inventing a blended success score. Generic
scenario `run`/`cancel` CLI entries were removed because no supported dispatcher
owned them.

Known callers: scenario CLI list/status/plan/candidate-manifest/readiness gate,
unattended eligibility, Route Lab, metrics CLI, and tests

## Unattended regression

Domain: unattended provider/display preflight, immutable manifests, isolated
execution, cancellation, cleanup, and repeatability evidence.

SSOT module/file: `src/smb3_agent/unattended.py`.

Why this is authoritative: one runner owns the regression-only proof limits,
process group, sanitized environment, paths, artifacts, and terminal records.

Known callers: unattended CLI, Route Lab planning/status, and unattended tests

## Experimental adapter lifecycle

Domain: scaffold schema, conformance, installation, discovery, integrity, and
removal.

SSOT module/file: `src/smb3_agent/experimental_adapters.py`.

Why this is authoritative: the versioned declarative contract and exact
manifest inventory are validated once, and catalog assembly consumes only
providers discovered through this module.

Known callers: adapter CLI, Route Lab onboarding, catalog factory, and tests

## Retained supported paths

- `goal run world_1_king` remains the explicit legacy diagnostic. Its duplicate
  `task fceux-world-1-king` wrapper was removed.
- `task fceux-1-1` remains a low-level harness diagnostic because it exposes
  direct runner controls not represented by a goal contract; it is not product
  acceptance.
- Mednafen remains a macOS-only diagnostic adapter. It is separate from the
  FCEUX product runner and fails explicitly on unsupported hosts.
- Supported user-command phrases remain input normalization; executable runs
  still resolve to a goal contract and `run_goal_contract()`, while the Show
  phrase routes through Attempt Lab's review-only path.

## Removed compatibility paths

- `lab propose-variant latest`; use `lab propose-variants latest`.
- `lab run-variant`, `lab compare-variant`, and `lab promote-variant`; use the
  `lab patch` lifecycle.
- `task fceux-world-1-king`; use `goal run world_1_king`.
- Parse-only `review the latest failed run` and `continue after losing a life
  if the route allows it`; use the supported `review log` and `recovery
  simulate` entry points.
- Generic scenario `run` and `cancel` parser entries. Use scenario
  list/status/plan/readiness for inspection; executable unattended regression
  has its own bounded runner, and owner campaign execution remains a separate
  acceptance workflow.
- Repeated Mario/Stardew/Experimental provider tuple construction in CLI and
  Route Lab; both now call `build_default_catalog_registry()`.

The canonical tests contain a static guard preventing these parser entries and
lab functions from returning.

## Enforcement

`tests/test_ci_contract.py` guards the removed compatibility symbols and the
single production catalog factory. Focused command, catalog, Experimental
adapter, and CLI tests cover the routed behavior. The complete canonical
Non-live gate passed on 2026-08-23 with the complete test suite plus the
active-goal, segment, deterministic-status, player, Route Lab, and Stardew
render contracts. Current gate output, rather than a copied test count, is the
authoritative validation record.
