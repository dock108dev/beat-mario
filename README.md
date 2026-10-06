# Game Companion

Game Companion is a local macOS application for discussing a game goal, reviewing
bounded play, watching its results, and taking control. Mario and Stardew use
Codex CLI for contextual conversation and gameplay decisions; guarded controllers
validate actions and verify observed effects.

## Supported capabilities

- **Mario:** bounded World 1-1 strategy, opening-jump coaching, remembered
  stairs/pipe guidance, experimental coin routes, and a supported sky 1UP activity.
  Arbitrary levels, tactics, and complete coin coverage are unsupported.
- **Stardew:** prepared-farm watering, planting-location discussion, and supported
  inspection/return routines. Reconnaissance is implemented but native acceptance
  is pending. Arbitrary farms and delegated cave exploration are unverified.
- **Minecraft:** setup, calibration, and small camera requests. Movement,
  placement, and wall execution remain disabled.
- **OpenTTD:** a narrow loan-repayment reference integration using local Ollama.
- **Experimental adapters:** data-only contributor fixtures; no native gameplay.

The source checkout is the development workflow. Existing review apps have their
own versioned capabilities and manifests; current source changes do not update
those apps. A broadly qualified two-game distribution is not available.
See [known limitations](docs/known-limitations.md) and the
[Mario](docs/mario-player-guide.md) and [Stardew](docs/stardew-operator-guide.md) guides.

## Requirements

- Python 3.11 or newer and [`uv`](https://docs.astral.sh/uv/).
- macOS for native game observation and input; separately installed games.
- Discoverable, signed-in Codex CLI for ordinary Mario/Stardew conversation.
  Selected game images and context are sent for remote inference.
- FCEUX and a supported local game file for Mario. Set `SMB3_GAME_FILE` or select
  the file in setup. FCEUX discovery checks PATH and standard Homebrew locations.
- Screen recording and Accessibility permissions for supported native input.
- Stardew live activities additionally require a disposable prepared save and
  compatible pixel calibration. These local registrations are not included in a
  clone; see [Stardew setup](docs/stardew-operator-guide.md#choose-the-matching-farm-and-profile).

Linux CI exercises offline contracts and tests, not native game behavior.
OpenTTD additionally requires local Ollama with `gemma3:4b`.

## Launch and first use

From the repository root:

```bash
uv sync --locked --all-extras
.venv/bin/python -m smb3_agent lab ui --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/` and choose a game. Setup reports missing prerequisites
and provider readiness before play. `/mario` and `/stardew` are the ordinary
workspaces; `/setup`, `/minecraft`, and `/openttd` serve the other supported
profiles. `/onboarding` manages contributor fixtures; `/lab` exposes engineering
review tools. The Stardew CLI remains inspection-only.

The server accepts loopback hosts only. It has no remote-access authentication,
TLS, or multi-user support. Do not expose it through a proxy, tunnel, or LAN bind.
The app does not load `.env` files. `GAME_COMPANION_EXPERIMENTAL_ROOT` overrides
only the Experimental-adapter installation root. See
[runtime and configuration](docs/runtime-and-configuration.md) for settings and storage.

## History, recovery and safe shutdown

Review and Start authorize the displayed finite scope. Stop/Take control releases
input and cancels continuation. Wait for confirmed handback before switching or
closing a game. If release cannot be confirmed, stop the specifically identified
game process; do not terminate unrelated processes.

Saved results are descriptive. Reopening never restores a connection,
observation, reviewed plan, or input permission. New work requires fresh compatible
setup and review. Confirmed work, uncertain outcomes, and return-to-start are
reported separately. See [recovery](docs/error-handling.md).

After handback, stop the foreground server with Control-C. The source
`Launch Game Companion.command` starts a background server; use
`Stop Game Companion.command` for that instance. Packaged apps have their own
Quit action. Closing a browser alone is not a verified server shutdown.

## Development and tests

```bash
.venv/bin/python -m smb3_agent --help
.venv/bin/python -m pytest -q tests/test_goals.py
PYTHON=.venv/bin/python scripts/validate_phase0.sh
```

Use focused tests for a bounded change. The full gate runs lint, credential and
tracked-output checks, the offline test suite, contracts, and static UI renders.
CI also runs dependency review and managed CodeQL. Node 22 enables JavaScript
regressions; no npm installation is needed. Test metrics, GitHub summaries, and
retained report artifacts are described in [development](docs/development.md).

Source lives in `src/smb3_agent/`, authored contracts and fixtures in `data/`,
validation/build tools in `scripts/`, and tests in `tests/`. Local game state,
evidence, calibration registrations, and build output remain ignored.

Read [architecture](docs/agent-architecture.md),
[module ownership](docs/ssot.md), [security](docs/security.md), and the
[documentation index](docs/README.md) for implementation detail.
