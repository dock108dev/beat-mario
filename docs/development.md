# Development and repository structure

Use the source checkout for local development. The ordinary Mario and Stardew
interfaces connect contextual language and bounded gameplay roles through Codex;
controllers retain input authority and independent outcome verification. See
[architecture](agent-architecture.md) and [runtime configuration](runtime-and-configuration.md).
Native game behavior and packaged-app compatibility require separate validation
from the offline test suite.

## Local environment

Use Python 3.11 or newer and create the locked environment from the repository
root:

```bash
uv sync --locked --all-extras
```

The project CLI is available through the environment interpreter:

```bash
.venv/bin/python -m smb3_agent --help
```

This is the same locked dependency installation used by CI. The project does
not define a separate build step; installation creates the editable package and
the `smb3-agent` console command in `.venv/bin/`.

`SMB3_GAME_FILE` selects the configured local Mario source; an explicit
`--game-file` takes precedence where available. The validation script also accepts
`PYTHON` solely to select its interpreter. Experimental adapter commands also
accept `GAME_COMPANION_EXPERIMENTAL_ROOT` as the local installation root.
Product preset variables are internal execution policy defined by
`src/smb3_agent/presets.py`; do not export route tuning variables for
authoritative runs. Game Companion Lab binds to loopback by default. See
[Runtime, configuration, and data](runtime-and-configuration.md)
for the complete boundary.

## Repository layout

```text
data/goals/             Goal contracts and composition
data/segments/          Route catalog and acceptance events
data/routes/scripts/    Structured route inputs
data/companion/         Shared catalog contract
data/mario/             Mario product declaration
data/stardew/           Stardew safety and evidence contracts
data/scenarios/         Scenario, metrics, unattended, and campaign contracts
docs/                   Engineering and operating documentation
scripts/                Canonical gate and FCEUX Lua runner
src/smb3_agent/         Python package and CLI
tests/                  non-live unit and integration tests
artifacts/              Ignored local execution evidence
```

Generated sessions, screenshots, emulator output, runtime state, caches, and
local UI assets are ignored. Root `build/` and `dist/` are disposable packaging
output; authored tools remain in `scripts/`. NES/FDS game files and local saves
must stay ignored. Do not force-add generated output.

The tracked-file guard in `scripts/validate_phase0.sh` rejects local artifacts
and root packaging output even if force-added. Required replay images in
`data/fixtures/state/`, route inputs, contracts, and asset placeholders remain
tracked. Ignore changes do not untrack existing files: inspect callers before
any index removal and preserve local evidence. Historical artifact links refer
to retained local-only evidence, which a fresh clone does not include.

## Entry points

- `python -m smb3_agent goal ...`: validate, inspect, or run goal contracts.
- `python -m smb3_agent reliability ...`: authoritative fresh runs and
  review-only playback.
- `python -m smb3_agent lab ...`: attempt review, Game Companion Lab, and route patches.
- `python -m smb3_agent companion ...` and `stardew ...`: safe catalog and
  unconfigured Stardew inspection/rendering.
- `python -m smb3_agent learning ...`: inspect and maintain local learning
  records and review candidates.
- `python -m smb3_agent scenario ...` and `metrics ...`: inspect classified
  scenarios and local product metrics without launching a game.
- `python -m smb3_agent unattended ...`: explicitly acknowledged,
  regression-only planning, execution, lifecycle, and comparison.
- `python -m smb3_agent adapter ...`: validate, scaffold, install, inspect, and
  remove declarative Experimental adapters.
- `python -m smb3_agent task ...`: bounded low-level diagnostics.
- `scripts/validate_phase0.sh`: canonical non-live repository gate.
- `python -m smb3_agent.app_runtime`: source version of the ordinary setup app;
  opens `/setup` on the identified local instance.
- `scripts/build_private_beta.py`: local Mac review-package builder. The packaged
  executable enters `app_runtime.py` and provides an explicit `--smoke` HTTP/profile
  lifecycle check that does not capture or control a game.

Use `python -m smb3_agent COMMAND --help` for the current command surface. Do
not copy old command inventories into documentation.

## Validation workflow

For a bounded change, run affected tests, Ruff on changed Python files, and a
syntax check. For example:

```bash
.venv/bin/python -m pytest -q tests/test_goals.py
.venv/bin/python -m ruff check src/smb3_agent/goals.py
.venv/bin/python -m py_compile src/smb3_agent/goals.py
```

The full non-live gate is available for repository-wide validation and is run
by CI; it is not required after every documentation or localized cleanup edit:

```bash
PYTHON=.venv/bin/python scripts/validate_phase0.sh
```

Ruff is the configured Python linter. The repository has no separate formatter,
type-checker or standalone browser-test command. The local review-package builder
is separate from the canonical gate. GitHub Actions runs the
canonical gate on Python 3.11 without a game file or emulator. Pull requests also receive a
dependency-review check that rejects newly introduced dependencies with known
moderate-or-higher vulnerabilities. Dependabot checks the `uv` and GitHub
Actions dependency surfaces weekly.

JavaScript regressions run through pytest using Node.js. CI explicitly installs
Node 22 with an immutable `setup-node` action pin; it does not rely on the
runner image to provide Node. No npm packages or npm cache are required.
Locally, tests that need Node are explicitly skipped when it is unavailable. Pre-walkthrough qualification requires those cases to run,
plus actual browser keyboard/focus verification across background refreshes.

For Minecraft/player changes, affected checks include `test_player_setup_ui.py`,
`test_player_onboarding.py`, `test_player_beta.py`, `test_minecraft_integration.py`,
`test_minecraft_native_aim.py`, scene/camera/settings tests and the shared
feedback/skill runtime. Select the checks for the actual change. UI regressions
exercise priority controls, malformed drafts, protection persistence, input locks
and late responses. Use disposable user data; do not post native game input during
offline verification. A native behavior change additionally needs one short
integrated check of the affected useful path and handback.

The stable repository jobs are `verify` and `dependency-review`; the latter runs
only on pull requests and is intentionally skipped on pushes/manual runs.
GitHub also supplies managed CodeQL checks outside the workflow file:
`Analyze (actions)`, `Analyze (python)`, and `Analyze (javascript-typescript)`.
Hosted passes at a committed baseline do not qualify subsequent uncommitted edits.

CI publishes a GitHub job summary with the canonical gate outcome, test counts,
duration, skipped-test reasons, and the five slowest tests. It retains the temporary
JUnit XML, `metrics.json`, and `summary.md` as `ci-test-results` for seven days on
success or failure. Earlier failures explicitly report missing test results;
canceled runs do not upload. Reporting preserves the gate's failure status.
No workspace directories or local game evidence are included in that upload.
These metrics do not measure line/branch coverage or native Mac behavior.
Dependency review blocks newly introduced vulnerable dependencies; it is not a
full audit of existing dependencies. CodeQL and repository secret protections
provide separate security signals.

For live route changes, non-live validation is necessary but insufficient.
Follow the selected goal's profile in [reliability-gate.md](reliability-gate.md)
and keep watchable playback separate from authoritative evidence.

## Local review packaging

The source workflow above does not require signing or retained calibration evidence. Packaging and installation are separate, explicit commands. Inspect their options without building or updating an app:

```bash
.venv/bin/python scripts/build_private_beta.py --help
.venv/bin/python scripts/install_private_beta.py --help
```

The builder requires a new version/output directory, numeric build number, an existing stable signing identity, local PyInstaller/macOS dependencies and eligible OCR/calibration inputs. `release_resources.py` inventories authored contracts/controllers and verifies the retained Day 2 profile at `artifacts/b3-engineering/20260925-integrated/profile-qualified-v1.json`. Optional ordinary display features use `artifacts/gc-delivery/ordinary-session/20261006-recovery/view-feature-calibration/profile.json`. These are local builder prerequisites, excluded from a fresh source checkout; synthetic resource-staging tests need neither profile. Calibration eligibility rules remain separate; only recursive path relocation is shared.

The installer accepts a retained package directory, verifies the source and staged app, requires the installed app to be closed and preserves a previous installation in an archive. A staged identity mismatch refuses installation even under optimized Python. Failed final replacement restores the prior app and retains staging for inspection. The installation receipt does not establish macOS permission access. Both scripts are safe to import; execution occurs only through `main()` or the command-line entry point. Do not run build/install as ordinary source tests or to tidy a frozen candidate.

Root-level `app-lifecycle.json`, `cleanup-failures.json` and `runtime.log` are ignored diagnostic output. Authored data, replay images, resource tools and the favicon remain source inputs; ignored files are not removed from disk.

## Module boundaries

Keep stateful controllers and integrity transactions cohesive. These retained
boundaries explain why line count alone is not an extraction criterion:

- `scripts/fceux_1_1_agent.lua` is one stateful FCEUX
  callback program. Route phases share emulator memory, controller cleanup, and
  ordered events; splitting it requires a loader design and live regression.
- `src/smb3_agent/lab_ui.py` keeps the dependency-free HTTP
  handler, player/Lab rendering, actions, and embedded styles in one local-app
  boundary. Extracting presentation assets needs snapshot or browser-level coverage.
- `learning.py`, `live_observation.py`, `unattended.py`,
  `stardew_companion.py`, and `stardew_adapter.py`
  each implement a stateful lifecycle with its persistence or authority checks.
  Their internal operations are tightly coupled to their fail-closed state.
- `route_patch.py` is one reviewed mutation and integrity
  transaction. Partial extraction would widen a security-sensitive boundary.
- `fceux_harness.py` and `reliability.py` share, within
  each module, one log/event or acceptance-report contract. A future split
  should introduce a typed schema boundary first.
- `lab.py` owns one on-disk attempt, note, issue, review, and
  proposal schema.
- `cli.py` keeps parser registration and dispatch together.
  Separating command registration is reasonable only with a focused CLI API
  compatibility test across every command group.
- `experimental_adapters.py`, `mario_product.py`, `objective_profiles.py`,
  `show.py`, `scenarios.py`, and `companion_catalog.py` each remain a single bounded contract or lifecycle. Their size is
  moderate and extraction would currently add indirection without isolating a
  reusable subsystem.

Previously reviewed large test modules include:
`test_reliability.py`, `test_fceux_harness.py`, `test_lab_ui.py`,
`test_goals.py`, `test_live_observation.py`, and `test_route_patch.py`. They are
organized around their matching production contract and retain shared fixtures
and scenario matrices; splitting them would not improve test isolation.

The first sensible future extractions are the Game Companion Lab presentation
assets, a typed route-patch record layer, and CLI registration. Each needs its
own behavior-preserving change rather than a mechanical file split.

## Change boundaries

- Update goal contracts before adding goal-specific UI or acceptance policy.
- Update preset policy only in `presets.py`.
- Use `route_patch.py` for accepted-tree mutation.
- Preserve live evidence; tests cannot promote gameplay acceptance.
- Update this document when entry points, required tools, or validation change.

## Build qualification

A retained app's manifest/source archive establishes its identity. Later source
edits do not change that runtime. Runtime/resource changes need a newly frozen
build, affected tests, the canonical gate and affected native trials. Preserve
previous packages and immutable evidence. Documentation-only changes require
link, consistency and whitespace checks. Source tests and portable smoke do not
establish native behavior or owner acceptance. See
[known limitations](known-limitations.md#source-and-retained-builds).
