# Game Companion

The private-beta goal is a Mac app that a user can open, connect to Minecraft Java, follow guided setup and practice, save a profile, complete a supported typed task, Stop or take control, and reopen their profile and result. The [private-beta technical plan](docs/private-beta-engineering.md) and [current tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md) own the remaining work.

Start project-manager review with the [private-beta handoff](docs/private-beta-pm-handoff.md), which identifies current source, retained packages, verification and the next delivery result.

**Current Minecraft status:** profile/setup/history/help/feedback, app-created calibration and bounded camera requests are implemented. Current source additionally has state-derived setup progress/remedies and focused control, protection, aiming and deadline repairs. These source changes have not been rebuilt into private.2. Aiming, nearby movement, additions and wall Start remain unavailable. Finish the guided first-task path and verify it in a separately identified packaged app. See the [quick start](docs/private-beta-quick-start.md) and [review status](docs/private-beta-review.md) for supported settings and evidence.

For the private-beta review package, open **Game Companion.app** and begin in **Setup & profiles**. The source-checkout launcher below remains available for local development and the existing Mario/Stardew paths.

Game Companion is a local, player-controlled assistant for single-player games.
It observes a supported game, offers grounded advice (**Tell**), can demonstrate
one bounded objective in a separate session (**Show**), and can take over only
after explicit same-session authorization (**Do**). Every execution path must
stop input and return control with a truthful handoff.

## Supported workflows

- **Minecraft Java Creative:** guided profile setup, supported settings, exact window selection, app calibration and bounded camera requests. The intended first useful task is a 7 × 3 × 1 wall with a centered 1 × 2 doorway; movement, aiming, additions and wall execution are still unavailable. Ordinary user preparation must explain and check the flat clear practice area, material, reachable work region and protected blocks, with a concrete remedy when something is missing. See the [private-beta guide](docs/private-beta-quick-start.md).
- **OpenTTD:** one reviewed £10,000 repayment from a disposable paused company with £100,000 cash and loan. Its retained packaged result applies to private.1 and its recorded environment; see the [review](docs/private-beta-review.md).
- **Mario:** observation, coaching, separate demonstrations, bounded execution, and conversation-based route edits. Quickest and 100% intents initially use the same base route; they do not imply an optimized or full-completion result. See the [conversation and route guide](docs/b2-conversation-guide.md).
- **Stardew Valley:** the locally prepared Pilot / B3Test farm supports reviewed automatic watering of all 15 crops, resource reconciliation, farmhouse return and neutral handback. Live input requires a newly verified isolated session and the retained local screen profile; the profile and proprietary game are not bundled with the checkout. A separate Pilot / B4Test Day 5 copy supports the qualified selected harvest → plant → water → small-stone clear routine. Other farms and targets are not qualified. See the [Stardew guide](docs/stardew-operator-guide.md).
- **Experimental adapters:** data-only adapter scaffolding, fixture conformance, installation and discovery. Passing conformance does not establish live game compatibility.

Game switching waits for the current adapter to stop and return control. Live execution requires explicit session authorization and a configured game environment. Automated tests cannot establish live gameplay reliability; see [known limitations](docs/known-limitations.md).

## Requirements

The private-beta package bundles the app runtime. Games are installed separately; macOS permissions and supported game settings are explained in the [quick start](docs/private-beta-quick-start.md). Minecraft's bounded requests require no model installation. OpenTTD uses separately installed local Ollama with gemma3:4b.

For source-checkout development and the existing local launchers:

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/) for the locked environment
- Git for source identity and reviewed route-patch worktrees
- FCEUX on `PATH` only for live Mario use
- For Stardew: the inspected local Mac game/runtime, macOS screen/input permissions, and the prepared seeds plus matching profile/evidence files described in the [Stardew guide](docs/stardew-operator-guide.md)
- Mednafen only for the optional legacy diagnostic path

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

## Launch and first use

For Minecraft profile setup and practice, follow the [private-beta quick start](docs/private-beta-quick-start.md) from the identified review app. Its adjacent guide and manifest describe that retained package; the PM handoff describes later source changes. A saved profile restores configuration and history only; reconnect the game and establish current readiness before a new Review/Start. Follow the app's actual capability labels: the useful wall task is still awaiting completion and a packaged workflow check.

The following instructions describe the source-checkout launcher and existing Mario/Stardew first use.

The launcher uses the local `.venv` and game configuration; it does not install dependencies, games, prepared farms or calibration evidence. On another checkout, use the install instructions above. Delivery is in place, with prerequisites listed in the [delivery guide](docs/b8-personal-delivery.md). The full non-live gate is an engineering check, not an every-launch step.

1. Double-click **Open Game Companion.command**. It uses this checkout's `.venv`, opens the loopback page and starts a background server if needed. Logs are in `artifacts/local-companion.log`. A missing environment or another application on port 8765 is an error; inspect it before retrying. Reusing a running Companion server does not verify its source version; reconcile its identity before owner review.
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
adapter installation root. The application does not load a `.env` file and
needs no credentials. See
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
