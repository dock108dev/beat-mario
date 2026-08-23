# Game Companion — Mario Adapter

Game Companion is a local, evidence-first game assistance workbench. It can
understand the current situation, then **Tell**, **Show**, or **Do** one bounded
objective before returning control with a truthful handoff.

This repository contains the live Mario adapter, the Stardew copied-save and
companion contracts, their combined local catalog, and engineering tools for
route evidence, reliability, and Experimental adapter onboarding. Mario's
accepted route reaches the stable ending from power-on. Stardew's public
surface is currently inspection-only and unconfigured. The consolidated owner
campaign has not run and no owner acceptance is claimed.

No game file or generated evidence is tracked. Local ROMs, saves, screenshots,
logs, and artifacts remain ignored.

## Requirements

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/) for the locked development environment
- FCEUX on `PATH` only for live gameplay or review runs
- macOS only for the optional legacy Mednafen diagnostics

## Setup

From the repository root:

```bash
uv sync --locked --extra dev
```

## Validate

Run the same ROM-free gate used by GitHub Actions:

```bash
PYTHON=.venv/bin/python scripts/validate_phase0.sh
```

The gate checks repository hygiene, shell syntax, Ruff, all ROM-free tests,
default goal and segment contracts, deterministic route status, and player/Lab
render contracts. It does not run an emulator or prove live gameplay.

Useful smoke commands:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m smb3_agent goal validate world_8_finish_game
.venv/bin/python -m smb3_agent goal status world_8_finish_game
.venv/bin/python -m smb3_agent lab ui-render --output /tmp/game-companion.html
.venv/bin/python -m smb3_agent stardew status
.venv/bin/python -m smb3_agent stardew operator-render --output /tmp/stardew-operator.html
.venv/bin/python -m smb3_agent companion catalog-status
.venv/bin/python -m smb3_agent companion render --output /tmp/combined-game-companion.html
```

## Run the local workbench

The loopback-only server opens the combined player catalog at `/`, the preserved
Mario workspace at `/mario`, the standalone Stardew workspace at `/stardew`,
and the engineering Game Companion Lab at `/lab`. Route evidence, notes,
issues, advanced route execution, and reviewed route patches remain in the Lab:

```bash
.venv/bin/python -m smb3_agent lab ui --host 127.0.0.1 --port 8765
```

The server is loopback-only and is not designed for network exposure. The root
shows the combined catalog; `/mario`, `/stardew`, `/lab`, and `/onboarding`
provide the adapter and engineering surfaces. See the [Mario player guide](docs/mario-player-guide.md),
[Game Companion Lab guide](docs/mario-route-lab.md), and [security model](docs/security.md).

Live Mario validation requires an operator-supplied game file and FCEUX. Follow
the [reliability guide](docs/reliability-gate.md); review playback never counts
as authoritative evidence.

## Documentation

Start with the [documentation index](docs/README.md). The primary engineering
references are:

- [Development and repository structure](docs/development.md)
- [Runtime, configuration, and data](docs/runtime-and-configuration.md)
- [Single sources of truth](docs/ssot.md)
- [Architecture and module responsibilities](docs/agent-architecture.md)
- [Operating and validation limitations](docs/known-limitations.md)
- [Consolidated final campaign](docs/final-campaign-guide.md)

## Working rules

- Goal contracts and accepted evidence define product truth.
- Green ROM-free tests are not live gameplay acceptance.
- Product runs start from power-on and prohibit bridges, savestates, search,
  blind mutation, and diagnostic fallback.
- Credentials and local game/evidence assets must never be committed.
