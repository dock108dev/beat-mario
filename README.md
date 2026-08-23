# Game Companion — Mario Adapter

Game Companion is a local, evidence-first game assistance workbench. Its player
contract is to understand the current situation, then **Tell**, **Show**, or
**Do** one bounded objective before returning control with a truthful handoff.

This repository contains the first adapter and accepted reliability proof: a
Super Mario Bros. 3 route that starts from power-on, collects both World 1 Warp
Whistles, reaches World 2, uses both whistles, completes World 8, defeats
Bowser, observes the Princess rescue and credits, and stops at the stable final
screen.

The local root now presents the combined Mario and Stardew catalog, then opens
the selected adapter's existing player workspace. Each adapter owns its
capabilities, observation trust boundary, goals, profiles, takeover scopes,
safety, evidence, and recovery truth. Switching is explicit and fails closed
until active modes stop and neutral player handback is known. See the [Mario
Player Guide](docs/mario-player-guide.md) and [Game Companion V2 roadmap](docs/v2-roadmap.md).

V2.4 live observation launches one visible player-controlled FCEUX session with
a read-only observer, keeps Show separate, and leaves takeover unavailable. See
[Live Mario observation](docs/live-observation.md) for the exact connection and
evidence contract.

V2.7 adaptive assistance derives only from compatible local evidence, exposes
its provenance and classification, and requires owner review, later compatible
replay, the existing exact-diff route-patch workflow, and affected reliability
gates before promotion. See [Adaptive assistance and solution learning](docs/learning.md).

V2.6–V2.14 are implementation-complete with final validation deferred. The
prepared [consolidated final campaign](docs/final-campaign-guide.md) has not run
and no owner acceptance is claimed.

V2.11 now implements standalone Stardew Observe, contextual grounded Tell, one
fresh-copy review-only Show, and explicit same-live-session Do/Takeover above
the V2.10 visible operator. Immediate reclaim neutralizes ordinary input and
invalidates authority before player handback. Disposable reset creates a fresh
attempt-owned copy while preserving prior attempts and reverifying the primary
save. V2.12 adds the combined provider-owned catalog, safe switching, bounded
local presentation persistence, and evidence isolation. See the [Stardew
Companion Guide](docs/stardew-operator-guide.md). No validation or game activity
was run for V2.12 or V2.13. V2.13 adds an engineering-only, honestly labeled
unattended regression runner; its output cannot count as visible, Show,
reliability, authoritative, usefulness, acceptance, or campaign proof.

The repository contains no game file. ROMs, savestates, screenshots, logs, and
generated evidence remain ignored and local-only.

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

The equivalent existing-environment installation is:

```bash
.venv/bin/python -m pip install -e '.[dev]'
```

## Validate the repository

Run the same ROM-free gate used by GitHub Actions:

```bash
PYTHON=.venv/bin/python scripts/validate_phase0.sh
```

The gate checks tracked-file hygiene, shell syntax, Ruff, all ROM-free tests,
the default goal and segment contracts, deterministic route status, and a Route
Lab render smoke. It does not run an emulator or prove live gameplay.

Useful focused commands:

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

## Supported flows

The default product goal remains `world_8_double_whistle`. Later goal contracts
compose that accepted prefix without changing it:

| Goal | Accepted boundary | Authoritative runs |
| --- | --- | ---: |
| `world_8_double_whistle` | World 8 map arrival | 5 |
| `world_8_big_tanks` | Big Tanks post-clear map | 3 |
| `world_8_battleships` | Battleships post-clear map | 3 |
| `world_8_hand_traps_jet` | All Hand Traps and Jet post-clear map | 3 |
| `world_8_8_2` | World 8-2 clear and Fortress access | 3 |
| `world_8_super_tanks` | Super Tanks clear and Bowser's Castle access | 3 |
| `world_8_finish_game` | Stable game-owned ending | 3 |

Run an authoritative fresh-process gate with a local game file:

```bash
export SMB3_GAME_FILE=/absolute/path/to/local-game-file.nes
.venv/bin/python -m smb3_agent reliability run --goal world_8_finish_game
```

Run one throttled, review-only playback:

```bash
.venv/bin/python -m smb3_agent reliability watch --goal world_8_finish_game
```

Review playback never counts as authoritative reliability evidence. See
[World 8 reliability gates](docs/reliability-gate.md) for exact pass rules and
artifact layout.

## Game Companion and Lab

The loopback-only server opens the combined player catalog at `/`, the preserved
Mario workspace at `/mario`, the standalone Stardew workspace at `/stardew`,
and the engineering Game Companion Lab at `/lab`. Route evidence, notes,
issues, advanced route execution, and reviewed route patches remain in the Lab:

```bash
.venv/bin/python -m smb3_agent lab ui --host 127.0.0.1 --port 8765
```

It is not designed for network exposure. See [Game Companion Lab](docs/mario-route-lab.md),
[security](docs/security.md), and [error handling](docs/error-handling.md).

V2.14 also adds `/onboarding`: a desktop and narrow-screen contributor flow for
deterministic declarative Experimental-adapter scaffolds, fixture conformance,
atomic local installation, provider discovery, integrity inspection, and exact
fail-closed removal. It does not generate executable code or launch a game.
Installed adapters remain `Experimental · live-unproven` and cannot promote
themselves to Supported. See the [contributor guide](docs/new-game-onboarding.md).

Mario first use checks `SMB3_GAME_FILE`, a saved local selection,
`game-file.nes`, and `roms/smb3.nes`, then offers a native macOS picker and
manual local-path selection. It verifies the supported fingerprint without
copying ROM contents and detects FCEUX before starting either a structurally
read-only session or a takeover-capable session with zero agent input before
fresh explicit authorization. This also enables
the supported `world_1_1_clear` Show card. Show
opens a separate visible emulator process, runs one fresh attempt with a
positive playback delay, and retains local cue/replay evidence. **Stop
Demonstration** ends automation in that process and is distinct from live
**Take Control Now**; Show never advances the player's game or counts as
reliability evidence.

Executable route changes use only the normalized route-patch lifecycle:

```bash
.venv/bin/python -m smb3_agent lab patch import PATCH.yaml
.venv/bin/python -m smb3_agent lab patch review PATCH_ID
.venv/bin/python -m smb3_agent lab patch preview PATCH_ID
.venv/bin/python -m smb3_agent lab patch prepare PATCH_ID
.venv/bin/python -m smb3_agent lab patch validate PATCH_ID
.venv/bin/python -m smb3_agent lab patch compare PATCH_ID
.venv/bin/python -m smb3_agent lab patch promote PATCH_ID --confirm PATCH_ID
```

## Documentation

Start with [the documentation index](docs/README.md). Key references are:

- [Development and repository structure](docs/development.md)
- [Runtime, configuration, and data](docs/runtime-and-configuration.md)
- [Single sources of truth](docs/ssot.md)
- [Goal contracts](docs/goal-contract.md)
- [Route status and accepted evidence](docs/route-status.md)
- [Route patch schema](docs/route-patch-schema.md)
- [Agent architecture](docs/agent-architecture.md)
- [Known limitations](docs/known-limitations.md)
- [Session automation and local product metrics](docs/session-automation-metrics.md)
- [Mario player guide](docs/mario-player-guide.md)
- [Consolidated final campaign](docs/final-campaign-guide.md)
- [Stardew companion guide](docs/stardew-operator-guide.md)
- [Unattended regression operator guide](docs/unattended-regression.md)
- [New Game Onboarding and Experimental adapter contributor guide](docs/new-game-onboarding.md)

## Working rules

- Goal contracts and accepted evidence define product truth.
- Green ROM-free tests are not live gameplay acceptance.
- Product runs start from power-on and prohibit bridges, savestates, search,
  blind mutation, and diagnostic fallback.
- Credentials and local game/evidence assets must never be committed.
