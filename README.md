# Game Companion

Game Companion is a local, player-controlled assistant for single-player games.
It observes a supported game, offers grounded advice (**Tell**), can demonstrate
one bounded objective in a separate session (**Show**), and can take over only
after explicit same-session authorization (**Do**). Every execution path must
stop input and return control with a truthful handoff.

## Supported workflows

- **Mario:** observation, coaching, separate demonstrations, bounded execution, and conversation-based route edits. Quickest and 100% intents initially use the same base route; they do not imply an optimized or full-completion result. See the [conversation and route guide](docs/b2-conversation-guide.md).
- **Stardew Valley:** disposable-session setup, conversation, reviewed watering plans and pause/reclaim controls are under development. Live input requires verified isolation and qualified perception; no qualified real-game pixel profile ships with this checkout. Harvesting, planting and debris clearing are not live-supported. See the [Stardew guide](docs/stardew-operator-guide.md).
- **Experimental adapters:** data-only adapter scaffolding, fixture conformance, installation and discovery. Passing conformance does not establish live game compatibility.

Game switching waits for the current adapter to stop and return control. Live execution requires explicit session authorization and a configured game environment. Automated tests cannot establish live gameplay reliability; see [known limitations](docs/known-limitations.md).

## Requirements

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/) for the locked environment
- Git for source identity and reviewed route-patch worktrees
- FCEUX on `PATH` only for live Mario use
- macOS permissions and Mednafen only for the optional legacy diagnostic path

Credentials and generated gameplay evidence are not tracked. The application
has no database, cloud service, scheduler, or production deployment target.

## Install and validate

From the repository root:

```bash
uv sync --locked --all-extras
PYTHON=.venv/bin/python scripts/validate_phase0.sh
```

The canonical gate checks whitespace, shell syntax, Ruff, tracked-file guards,
the complete non-live test suite, goal/segment contracts, deterministic route
status, and the player, Lab, and Stardew HTML render contracts. It never starts
an emulator or reads an owner save.

The Stardew CLI is inspection-only; live setup and guarded controls are in the
browser workspace. For a quicker read-only check of the installed command surface:

```bash
.venv/bin/python -m smb3_agent --help
.venv/bin/python -m smb3_agent companion catalog-status
.venv/bin/python -m smb3_agent stardew status
```

## Start the local UI

```bash
.venv/bin/python -m smb3_agent lab ui --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/` and choose an adapter. The server exposes:

- `/` — combined player catalog and selected workspace
- `/mario` — Mario player workspace and first-use setup
- `/stardew` — Stardew setup, conversation and guarded execution controls
- `/onboarding` — Experimental-adapter contributor flow
- `/lab` — engineering review, route, evidence, and patch tools

The server accepts loopback hosts only. It is a single-operator local tool, not
a web deployment; do not expose it through a LAN bind, proxy, tunnel, or public
port.

Mario first use uses the existing local configuration. The public
`GAME_COMPANION_EXPERIMENTAL_ROOT` setting changes the local Experimental-
adapter installation root. The application does not load a `.env` file and
needs no credentials. See
[runtime and configuration](docs/runtime-and-configuration.md) for internal
runner variables and local artifact paths.

## Repository map

```text
src/smb3_agent/       Python package, CLI, adapters, lifecycle, and local UI
data/                 Versioned goals, catalogs, profiles, scenarios, and schemas
scripts/              Canonical gate and FCEUX Lua runners
tests/                non-live unit, contract, integration, and render tests
docs/                 Engineering, operating, safety, and evidence guides
artifacts/            Ignored local runtime evidence (created as needed)
```

The installed console command is `smb3-agent`; `python -m smb3_agent` is used in
the docs so commands always run through the selected environment. The package
name and `smb3_agent` namespace are retained compatibility names even though the
user-facing product is Game Companion.

## Where to go next

- [Documentation index](docs/README.md) — task-oriented map of the canonical docs
- [Local development](docs/development.md) — setup, layout, entry points, and change boundaries
- [Architecture](docs/agent-architecture.md) — components, ownership, and data flow
- [Runtime and configuration](docs/runtime-and-configuration.md) — settings, integrations, persistence, and deployment boundary
- [Mario player guide](docs/mario-player-guide.md) — live first use and player controls
- [Stardew companion guide](docs/stardew-operator-guide.md) — setup, watering contract and live-input prerequisites
- [Testing and live reliability](docs/reliability-gate.md) — when non-live checks are insufficient
- [Security model](docs/security.md) and [known limitations](docs/known-limitations.md)

## UI design

See [UI design](docs/ui-design.md) for layout, local styles and accessibility requirements.
