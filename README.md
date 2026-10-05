# Game Companion

Game Companion is a conversational AI player for the owner's personal Mac: describe a goal in your own words, watch approved play, discuss or coach decisions, and take control whenever needed. The initial private beta must connect **a contextual language LLM and a game-understanding/play agent** for Mario and Stardew, using Codex CLI as the first backend.

Read [product direction](docs/product-direction.md), the complete [engineering plan](docs/private-beta-engineering.md), [architecture](docs/agent-architecture.md), [current handoff](docs/private-beta-pm-handoff.md) and [technical next steps](/Users/michaelfuscoletti/Desktop/mario_next_steps.md). Next work is the first real Codex-backed language-plus-play vertical slice on Stardew, followed by both-game integration and all setup/evaluation/package work through local release.

## Current workflows and product gaps

- **AI integration:** ordinary Mario/Stardew still use deterministic language and largely authored task/tactic choices. The separate reference-profile model gateway is not the required two-role gameplay agent. Contextual Codex interpretation and adaptive action selection remain implementation work.
- **Mario:** observed opening coaching, remembered stairs/pipe guidance, two World 1-1 finishes and two supported sky 1UP collections; immediate controls and persistent outcomes. Full coin coverage, arbitrary tactics and broader reliability remain unknown. See the factual [Mario guide](docs/mario-player-guide.md).
- **Stardew:** observed selected watering, planting-location discussion and eastern-margin inspection/return on supported prepared settings. Farm Cave activity has local lifecycle and newer manual route evidence; ordinary companion delegation remains unverified. Adaptive model decisions, reusable observation/skills and supported variation remain engineering work. See the [Stardew guide](docs/stardew-operator-guide.md).
- **Minecraft:** retained setup/calibration/camera capabilities. Aim/movement/placement/wall Start remain disabled. Connection carries forward with accurate limits; full third-game play follows during beta.
- **OpenTTD and Experimental adapters:** reference integration and contributor fixtures. They are not initial two-game AI beta acceptance.

Recording source work is preserved but deferred to tentative beta v2. Current source behavior, target requirements, real gameplay and packaged delivery are separate. Existing evidence is linked from the engineering plan; prior results are not relabeled as model-driven or package proof.

The release target is a successor personal Mac .app with integrated game/Codex setup and app-owned dependencies. Retained private.1/private.2 remain historical engineering review packages; their adjacent manifests/guides own those exact capabilities. See [retained review](docs/private-beta-review.md) and [quick start](docs/private-beta-quick-start.md).

Gameplay uses an approved finite scope. Direct Stop/Take control, safe conversation, fresh observations and neutral handback remain controller responsibilities even after model integration. Reopening history or switching games never restores input authority.

## Requirements

The retained private-beta review package bundles its app runtime. Games are installed separately; macOS permissions and supported game settings are explained in the [quick start](docs/private-beta-quick-start.md). Minecraft's current bounded requests require no model installation. OpenTTD uses separately installed local Ollama with gemma3:4b. The successor AI beta requires discoverable, signed-in Codex CLI; ordinary-app integration is still planned.

For source-checkout development and the existing local launchers:

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/) for the locked environment
- Git for source identity and reviewed route-patch worktrees
- FCEUX on `PATH` only for live Mario use
- For Stardew: the inspected local Mac game/runtime, macOS screen/input permissions, and the prepared seeds plus matching profile/evidence files described in the [Stardew guide](docs/stardew-operator-guide.md)
- Mednafen only for the optional legacy diagnostic path

Credentials and generated gameplay evidence are not tracked. The application
has no database, hosted app service, scheduler, or public deployment target.
The planned Codex-backed provider sends bounded game context/images for remote inference;
its setup, lifecycle and data disclosure remain release work.

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

## Launch and first use

For current Mario/Stardew use, follow their factual player guides and the source-checkout launcher below. For retained Minecraft camera/calibration review, use the [engineering-package quick start](docs/private-beta-quick-start.md) and exact adjacent manifest/guide. Saved configuration/history restores no connection or gameplay authority. The existing bounded workflows described in those guides are implemented; the new two-role AI integration remains upcoming work.

The following instructions describe the source-checkout launcher and existing Mario/Stardew first use.

The launcher uses the local `.venv` and game configuration; it does not install dependencies, games, prepared farms or calibration evidence. On another checkout, use the install instructions above. Delivery is in place, with prerequisites listed in the [delivery guide](docs/b8-personal-delivery.md). The full non-live gate is an engineering check, not an every-launch step.

1. Double-click **Open Game Companion.command**. It uses this checkout's `.venv`, opens the loopback page and starts a background server if needed. Logs are in `artifacts/local-companion.log`. A missing environment or another application on port 8765 is an error; inspect it before retrying. Reusing a running Companion server does not verify its source version; use the current launch target before reviewing new behavior.
2. Choose Mario or Stardew Valley. Use the [Mario guide](docs/mario-player-guide.md) to verify the local game file/emulator and open a fresh companion session, or the [Stardew guide](docs/stardew-operator-guide.md) to select the correct prepared farm, verify isolation and connect its matching screen profile.
3. Describe a bounded request; inspect the actual path/actions, targets, resources, destination and readiness reason. Correct ambiguities before reviewing. **Start reviewed plan** (Mario) or **Review scope → Start reviewed work** (Stardew) grants fresh permission. Opening the page or selecting a game does not.
4. Keep **Pause**, **Stop** and **Take control** available. Read the outcome and remaining work when execution ends. Use the recovery steps below before trying again.

For a foreground server whose shutdown you can directly control, run from this repository:


```bash
.venv/bin/python -m smb3_agent lab ui --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/` and choose an adapter. The server exposes:

- `/` — combined player catalog and selected workspace
- `/mario` — Mario player workspace and first-use setup
- `/stardew` — Stardew setup, conversation and guarded execution controls
- `/setup` — private-beta player profiles, permissions/settings and guidance
- `/minecraft` — Minecraft setup, calibration and available task workspace
- `/openttd` — OpenTTD profile requests, controls and history
- `/onboarding` — Experimental-adapter contributor flow
- `/lab` — engineering review, route, evidence, and patch tools

The server accepts loopback hosts only. It is a single-operator local tool, not
a web deployment; do not expose it through a LAN bind, proxy, tunnel, or public
port.

Mario first use uses the existing local configuration. The public
`GAME_COMPANION_EXPERIMENTAL_ROOT` setting changes the local Experimental-
adapter installation root. The current source does not load a `.env` file. The planned Codex-backed beta
uses the owner's CLI sign-in; current Mario/Stardew have no Codex provider yet. See
[runtime and configuration](docs/runtime-and-configuration.md) for internal
runner variables and local artifact paths.

## History, recovery and safe shutdown

**Saved results → Reopen result** is read-only. It shows the request, confirmed work, remaining/uncertain work and recovery advice; older records may lack the original request. Reopening never recreates observations, selected targets, reviewed scope or execution permission. A saved Mario *variant* proposes actions for a new review; a saved *result* records what happened.

Completed means the reviewed bounded work and required stop were observed. Stopped/partial means some work may be confirmed while the rest is unfinished or uncertain. For example, Mario's opening stop does not finish the base route; Stardew may finish its selected actions without confirming the return. A newly observed wet crop is a new starting condition, not retrospective success for an earlier uncertain click.

**Cancel review** removes Stardew's Start permission; Mario's **Cancel pending change** removes only unexecuted edits. Neither undoes game actions. After a farm stop, refresh a supported view, request remaining work, review and Start; after Mario reclaim, only the verified opening stop can be resumed with fresh review. Longer Mario traversal requires a fresh session.

Use **Choose a game** to switch. Switching stops input, waits for handback and retains the result before selecting the other adapter. If handback is unresolved, the switch is refused. Old observations, plans, targets and pending edits cannot transfer. Returning to a game requires fresh compatible setup/review; its history remains available.

Before closing, Stop or Take control and wait for input release/handback. Inspect the result, then close the game normally; close disposable Stardew copies without saving to preserve the seed. If handback cannot be confirmed, do not assume that switching or closing the browser stops input: end the specifically identified game process and retain the unresolved result. A dead process cannot provide a native receipt. For a foreground server, press Control-C in its terminal after handback. The source-checkout double-click launcher leaves a background server running when its terminal/browser closes. Double-click **Stop Game Companion.command** to request shutdown of this repository’s identified server and verify that it exits. The private-beta app has its own **Quit Game Companion** cleanup, and its native workspace heartbeat stops work when the workspace is left. Follow the guide for the launcher in use. A failed stop remains an error; inspect it before retrying. Do not terminate unrelated Python/game processes.

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
- [Source of truth](docs/ssot.md) — domain authorities and supported compatibility boundaries
- [Runtime and configuration](docs/runtime-and-configuration.md) — settings, integrations, persistence, and deployment boundary
- [Mario player guide](docs/mario-player-guide.md) — live first use and player controls
- [Stardew companion guide](docs/stardew-operator-guide.md) — setup, watering contract and live-input prerequisites
- [Testing and live reliability](docs/reliability-gate.md) — when non-live checks are insufficient
- [Error handling and operations](docs/error-handling.md) — failed workers, input release, incomplete evidence and recovery
- [Security model](docs/security.md) and [known limitations](docs/known-limitations.md)

## UI design

See [UI design](docs/ui-design.md) for layout, local styles and accessibility requirements.

Personal Mac source-checkout launch, source identity and verified shutdown: [Delivery instructions](docs/b8-personal-delivery.md). Closing that launcher's browser does not stop its server.
