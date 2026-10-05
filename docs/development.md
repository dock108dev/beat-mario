# Development and repository structure

Updated October 4, 2026. Start with the [current engineering roadmap](private-beta-engineering.md)
and [PM handoff](private-beta-pm-handoff.md). The personal Mac beta needs both a
Codex-backed contextual language layer and an observation-driven gameplay agent.
Existing Mario and Stardew routes, action controllers, perception, interruption
and histories are foundations for that work. Adding another fixed phrase or
one-off route does not complete either AI capability.

The current source has useful, narrow real-game results for Mario coaching,
route traversal and a flight reward, plus Stardew watering, planting discussion
and inspection. Farm Cave travel is still unavailable. These results qualify the
documented source sessions; they do not establish general gameplay or a current
packaged beta. Retained private.1/private.2 packages have their own older
capabilities; see [review status](private-beta-review.md).

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

For live route changes, non-live validation is necessary but insufficient.
Follow the selected goal's profile in [reliability-gate.md](reliability-gate.md)
and keep watchable playback separate from authoritative evidence.

## Personal-beta delivery work

The first release is a successor **Game Companion.app** for the owner's existing
Mac. The repository-local launcher remains the engineering path. This delivery
does not require a hosted service, accounts for testers, multi-machine
portability or public notarized distribution. Verify the actual app and its
first-use path; a working source launch alone does not complete the beta.

These are engineering tasks in the [master roadmap](private-beta-engineering.md),
not extra setup procedures for the owner:

| Surface | Current implementation and required work |
| --- | --- |
| Codex dependency and session | The existing `model_gateway.py` implements loopback Ollama; there is no app-owned Codex gateway. Add discovery/selection of the installed CLI, sign-in/readiness guidance, a supported invocation protocol, bounded image/context transfer, structured response validation, cancellation, error/limit handling and worker cleanup. Qualify the chosen CLI integration with the app; having Codex installed alone does not connect it to gameplay. |
| Provider and control ownership | Give the model a bounded task context and selected observations. Run it without direct native-input or arbitrary filesystem/shell authority in the gameplay process. Bind replies to the current session/plan/control generation, discard late work, and keep deterministic Stop/Take control independent of inference. Record provider/version/model identity and actual call status; leave unknown usage unknown. |
| Mario/Stardew setup | `/setup` and `PlayerStore` still offer Minecraft/OpenTTD templates. Integrate the actual Mario and Stardew connections, prerequisites, saved preferences, model readiness and recovery into a coherent two-game first-use flow. Reuse current setup controls rather than creating another hidden engineer launcher. |
| Calibration and data | Stardew reads ignored `artifacts/stardew-prepared-farms.json`, `stardew-qualified-profile.json`, `stardew-qualified-farm-profiles.json`, their transitive calibration files and the installed manual cave-route manifest where selected. Prepared farms reference local paths; the planting observer also reads a current-directory-relative survey manifest and referenced images. Inventory these dependencies, distinguish reusable calibration from historical evidence, and provide app-owned adoption/calibration/setup. Retain primary saves and frozen seeds. A clone without ignored files is not this installed working environment. |
| Writable locations | The source launcher runs from the repository; `app_runtime` changes to Application Support. Relative `artifacts/*` registrations and `data/variants` therefore have different meanings. Resolve durable profiles, learning, variants, calibration, histories and reports through one explicit writable root; keep bundled/source resources read-only. Preserve/migrate existing local data deliberately. |
| Save preparation | Convert the qualified isolated Stardew launch/load/preparation into a dependable product path. Explain remaining manual Load/tool/refill prerequisites. An authorized copied save is not evidence that the game loaded that copy; retain actual isolation/load checks without asking the owner to supply engineering receipts. |
| Switching and lifecycle | Exercise game switching with pending inference, active input and partial outcomes. Confirm neutralization before activating another game, preserve histories, invalidate prior plans and reconnect with fresh observations. Cover Quit, launcher Stop, browser departure, signal/worker failure, stale or incompatible servers and reopening. Owned-process cleanup must not terminate personal game processes. |
| Readiness contract | `beta_readiness.py` reads the historical `personal-beta-v3.yaml` B2–B9 checklist. It still describes old routes/farm routines and contains no Codex or adaptive decision-loop requirements. Add a successor contract/report matching the current roadmap and chosen delivery target; preserve old reports and evidence. Tests must not manufacture the owner's usefulness feedback. |
| Feedback/privacy | Extend local report preview beyond legacy Minecraft/OpenTTD profiles to include the actual selected Mario/Stardew session, build, provider and sanitized decision/outcome diagnostics. Explain selected-window transmission to the Codex service and retention separately from local storage. Let the owner inspect/remove local histories and explicitly choose exported images/logs. Nothing is sent as feedback automatically. |

## Preparing a successor Mac app

`scripts/build_private_beta.py` is currently the retained-review builder, not a
completed two-game/Codex delivery pipeline. Its output/version is still
`player_store.VERSION` (`0.2.0-private.2`), its bundle build is hardcoded to
`20002`, and it consumes the historical [quick start](private-beta-quick-start.md).
It bundles `data` and `public` but omits the `scripts/fceux_*` Lua files used by
Mario. It assumes fixed Homebrew OCR/tessdata/license locations. PyInstaller is
an additional build dependency outside the declared project graph.

Before a successor build, give it a distinct version/output and bundle build,
declare build inputs, include the actual required controller/resources, resolve
external executable discovery from Finder as well as the shell, and match its
guide to the selected backend and supported games. The manifest must identify
app resources, external prerequisites, calibration compatibility, backend
requirements and the exact candidate. Use an explicit resource inventory rather
than copying every current file in `data`/`public`; ignored player variants,
personal images and runtime state belong to local data, not app resources.
Preserve the retained apps and their
adjacent manifests/guides.

Use isolated player data to verify first launch, permission failures, useful
Mario and Stardew requests, Stop/Take control, game switching, Quit, worker/game
cleanup and reopening. Move/copy the app to its intended local location and
verify it there so a working repository path or shell `PATH` cannot conceal a
missing dependency. The app must load historical data without restoring input
authority.

The existing packaged `--smoke` exercises Minecraft profile/HTTP/report behavior
only. Expand smoke coverage to the chosen two-game setup/provider/persistence
flow, keeping it input-free. A successful smoke and non-live gate do not replace
native checks of the exact built app. Local ad-hoc signing can remain sufficient
for this owner's Mac; broader distribution is later work.

## Conversation and route verification

Focused conversation checks live in `test_request_planning.py`, `test_stardew_planning.py`,
`test_conversation_service.py`, `test_conversation_ui.py`, `test_custom_variants.py`,
`test_beta_readiness.py` and the runtime tests. The canonical gate includes them.
Live proof additionally needs fresh isolated Mario attempts, actual alternate
traversal, dynamic speed, typing with no effective-input mismatch, revision
acknowledgment, paused reclaim, neutral handback and affected route regression.
Source snapshots include uncommitted files. Keep every failed attempt and use a
new directory after repair. The [conversation guide](b2-conversation-guide.md) describes the
ordinary launch path and shared adapter interfaces.

## Historical large-file review

The approximate counts below come from an earlier review, not the current
candidate. Line count alone is not an extraction boundary. Revisit ownership
when building the shared AI loop; split where it makes planning, observation,
execution or persistence independently understandable and testable. Avoid a
mechanical file-splitting prerequisite. These earlier files were reviewed and
retained:

- `scripts/fceux_1_1_agent.lua` (about 25,900 lines) is one stateful FCEUX
  callback program. Route phases share emulator memory, controller cleanup, and
  ordered events; splitting it requires a loader design and live regression.
- `src/smb3_agent/lab_ui.py` (about 5,300 lines) keeps the dependency-free HTTP
  handler, player/Lab rendering, actions, and embedded styles in one local-app
  boundary. The duplicate shadowed status style was removed; extracting assets
  still needs snapshot or browser-level coverage.
- `learning.py`, `live_observation.py`, `unattended.py`,
  `stardew_companion.py`, and `stardew_adapter.py` (about 960–1,770 lines each)
  each implement a stateful lifecycle with its persistence or authority checks.
  Their internal operations are tightly coupled to their fail-closed state.
- `route_patch.py` (about 1,670 lines) is one reviewed mutation and integrity
  transaction. Partial extraction would widen a security-sensitive boundary.
- `fceux_harness.py` and `reliability.py` (about 1,250–1,440 lines) share, within
  each module, one log/event or acceptance-report contract. A future split
  should introduce a typed schema boundary first.
- `lab.py` (about 1,220 lines) owns one on-disk attempt, note, issue, review, and
  proposal schema.
- `cli.py` (about 1,480 lines) keeps parser registration and dispatch together.
  Separating command registration is reasonable only with a focused CLI API
  compatibility test across every command group.
- `experimental_adapters.py`, `mario_product.py`, `objective_profiles.py`,
  `show.py`, `scenarios.py`, and `companion_catalog.py` (about 560–800 lines
  each) each remain a single bounded contract or lifecycle. Their size is
  moderate and extraction would currently add indirection without isolating a
  reusable subsystem.

Previously reviewed large test modules include:
`test_reliability.py`, `test_fceux_harness.py`, `test_lab_ui.py`,
`test_goals.py`, `test_live_observation.py`, and `test_route_patch.py`. They are
organized around their matching production contract and retain shared fixtures
and scenario matrices; splitting them would not improve test isolation.

The first sensible future extractions are the Game Companion Lab presentation
assets, a typed route-patch record layer, and CLI registration. Each needs its
own behavior-preserving slice rather than a mechanical file split.

## Change boundaries

- Update goal contracts before adding goal-specific UI or acceptance policy.
- Update preset policy only in `presets.py`.
- Use `route_patch.py` for accepted-tree mutation.
- Preserve live evidence; tests cannot promote gameplay acceptance.
- Update this document when entry points, required tools, or validation change.
