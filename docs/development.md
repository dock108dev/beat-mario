# Development and repository structure

## Local environment

Use Python 3.11 or newer and create the locked environment from the repository
root:

```bash
uv sync --locked --extra dev
```

The project CLI is available through the environment interpreter:

```bash
.venv/bin/python -m smb3_agent --help
```

`SMB3_GAME_FILE` is the only operator-facing runtime environment variable and
is an explicit override for live commands. The player Start button otherwise
uses `game-file.nes` or `roms/smb3.nes` when either local ignored file exists;
an explicit `--game-file` takes precedence. The validation script also accepts
`PYTHON` solely to select its
interpreter. Product preset variables are internal execution policy defined by
`src/smb3_agent/presets.py`; do not export route tuning variables for
authoritative runs. Game Companion Lab binds to loopback by default. See
[Runtime, configuration, and data](runtime-and-configuration.md)
for the complete boundary.

## Repository layout

```text
data/goals/             Goal contracts and composition
data/segments/          Route catalog and acceptance events
data/routes/scripts/    Structured route inputs
docs/                   Engineering and operating documentation
scripts/                Canonical gate and FCEUX Lua runner
src/smb3_agent/         Python package and CLI
tests/                  ROM-free unit and integration tests
artifacts/              Ignored local execution evidence
```

Generated sessions, screenshots, emulator output, ROMs, savestates, caches, and
local UI assets are ignored. Do not force-add them.

## Entry points

- `python -m smb3_agent goal ...`: validate, inspect, or run goal contracts.
- `python -m smb3_agent reliability ...`: authoritative fresh runs and
  review-only playback.
- `python -m smb3_agent lab ...`: attempt review, Game Companion Lab, and route patches.
- `python -m smb3_agent task ...`: bounded low-level diagnostics.
- `scripts/validate_phase0.sh`: canonical ROM-free repository gate.

Use `python -m smb3_agent COMMAND --help` for the current command surface. Do
not copy old command inventories into documentation.

## Validation workflow

Run a focused test while editing, then the full canonical gate:

```bash
.venv/bin/python -m pytest -q tests/test_goals.py
PYTHON=.venv/bin/python scripts/validate_phase0.sh
```

Ruff is the configured Python linter. The repository has no separate formatter
or static type-checker configuration. GitHub Actions runs the canonical gate on
Python 3.11 without a game file or emulator.

For live route changes, ROM-free validation is necessary but insufficient.
Follow the selected goal's profile in [reliability-gate.md](reliability-gate.md)
and keep watchable playback separate from authoritative evidence.

## Source files over roughly 500 lines

These files remain intentionally cohesive:

- `scripts/fceux_1_1_agent.lua`: one stateful FCEUX callback program. Its route
  phases share emulator memory, controller cleanup, and ordered event state;
  splitting it would require a loader/module system and live regression proof.
- `src/smb3_agent/fceux_harness.py`: parser state machine and runner share one
  log/event contract. A future split should follow a schema boundary, not line
  count alone.
- `src/smb3_agent/reliability.py`: profiles, inspection, and report generation
  form the authoritative acceptance policy and are heavily cross-validated.
- `src/smb3_agent/route_patch.py`: the transaction and its private integrity
  helpers form one security boundary; partial extraction would increase the
  mutation surface.
- `src/smb3_agent/lab.py`: attempt-session persistence, notes, issues, and
  proposal records share one on-disk schema.
- `src/smb3_agent/companion_session.py`: adapter-neutral player-session state,
  lifecycle, capabilities, safety boundary, outcome, and fail-closed handoff
  validation.
- `src/smb3_agent/lab_ui.py`: the dependency-free HTTP handler, HTML renderer,
  player and Lab routing, state actions, and embedded CSS form one local
  application. A template/static asset extraction should be a separately tested
  UI refactor.
- `src/smb3_agent/cli.py`: one parser and one dispatch entry point keep command
  registration adjacent to behavior. Its obsolete compatibility branches have
  been removed.

The first sensible future extractions are generated/static Game Companion Lab assets and
a typed route-patch record layer. Both deserve their own behavior-preserving
slice rather than mechanical file splitting.

## Change boundaries

- Update goal contracts before adding goal-specific UI or acceptance policy.
- Update preset policy only in `presets.py`.
- Use `route_patch.py` for accepted-tree mutation.
- Preserve live evidence; tests cannot promote gameplay acceptance.
- Update this document when entry points, required tools, or validation change.
