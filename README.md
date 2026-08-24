# Game Companion

Game Companion is a local, player-controlled assistant for single-player games.
It observes a supported game, offers grounded advice (**Tell**), can demonstrate
one bounded objective in a separate session (**Show**), and can take over only
after explicit same-session authorization (**Do**). Every execution path must
stop input and return control with a truthful handoff.

This repository is also the engineering workbench behind those experiences:
route contracts and reliability evidence for Mario, a copied-save safety model
for Stardew Valley, a combined adapter catalog, local scenario/metrics tooling,
unattended regression, and fixture-only Experimental-adapter onboarding.

## What works today

| Surface | Current repository behavior | Important boundary |
| --- | --- | --- |
| Mario | Public local UI, observation, Tell/coaching, separate Show, bounded same-process Do, route execution, review, and reliability tooling | Live use needs a configured local Mario environment and FCEUX. The current cumulative release candidate has not completed the final owner campaign. |
| Stardew Valley | Copied-save, screen-observation, Tell/Show/Do, reclaim, reset, and evidence contracts with deterministic coverage | The public CLI and UI are inspection-only: they do not select/copy a save, attach to Stardew, or construct a live input driver. |
| Combined catalog | Provider-owned Mario, Stardew, and installed Experimental entries at the local root UI | Switching is explicit and fails closed until the current adapter has stopped and returned player control. |
| Experimental adapters | Validate, scaffold, inspect, conform, install, discover, and safely remove data-only adapters | Conformance is fixture-only. Installation does not prove live compatibility or promote an adapter to Supported. |
| Scenarios, metrics, unattended regression | Local classified engineering contracts, reports, and bounded regression execution | These results cannot substitute for visible gameplay, authoritative completion, usefulness, or owner acceptance. |

The final campaign is deliberately disabled in
[`data/scenarios/final-campaign.yaml`](data/scenarios/final-campaign.yaml). Green
Non-live tests prove repository behavior, not live game operation or owner
acceptance.

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

For a quicker read-only check of the installed command surface:

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
- `/stardew` — safe, unconfigured Stardew inspection surface
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
- [Stardew companion guide](docs/stardew-operator-guide.md) — implemented contract and unwired-live boundary
- [Testing and live reliability](docs/reliability-gate.md) — when non-live checks are insufficient
- [Security model](docs/security.md) and [known limitations](docs/known-limitations.md)
- [Final campaign](docs/final-campaign-guide.md) — remaining release-candidate and owner proof

When modifying the project, keep adapter facts adapter-owned, require fresh
authorization for input, preserve actor-labeled evidence, fail closed on stale
or ambiguous state, and never treat deterministic or unattended results as
owner acceptance.
