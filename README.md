# Game Companion

Minecraft now supports bounded conversational log gathering, available tools, protected areas and saved-place return. [MC-B1-03 use and limits](docs/mc-b1-03-resources.md) · [live evidence](docs/mc-b1-03-evidence-20261027.md). Source qualification does not mean installed delivery; crafting/building is next.


Game Companion is becoming a chatbot that plays games: choose a game and open
its live view beside a persistent conversation.

**Active plan: [Minecraft Beta 1](docs/beta-1-plan.md).** A headless bot plays as
its own character while you chat or join the same world independently. Codex CLI
is the AI engine. Ordinary conversation must not require pausing gameplay or
controlling the user's screen. The next product goal is an NES emulator
companion; Stardew is out of active delivery.

**[MC-B1-03 passed local source and live qualification](docs/mc-b1-03-evidence-20261027.md).**
Choose Minecraft, gather logs with available tools, protect areas and return to saved
places. Ask questions during play, redirect work and Stop. Chat and places survive
reopening without resuming goals. The human walkthrough remains deferred; installed
delivery and full Beta 1 are incomplete. [Use and limitations](docs/mc-b1-03-resources.md).

Double-click **Open Game Companion.command** for this source version, then choose
Minecraft. The accepted retained practice world is reused. Java 21, Node 24.22.0,
pinned worker dependencies and signed-in Codex CLI are required. No Screen
Recording/Accessibility permission is used by the new Minecraft path. Stop Game
Companion.command closes its owned game processes and saves the world.

## Existing legacy capabilities

- **Mario:** bounded World 1-1 strategy, opening-jump coaching, remembered
  stairs/pipe guidance, experimental coin routes, and a supported sky 1UP activity.
  Arbitrary levels, tactics, and complete coin coverage are unsupported.
- **Stardew:** ordinary default-save isolated copying, observed preparation and narrow spring-patch watering; retained source planting-location discussion and supported
  inspection/return routines. Reconnaissance is implemented but native acceptance
  is pending. Arbitrary farms and delegated cave exploration are unverified.
  The public Stardew CLI remains inspection-only; it does not select or copy a
  save, open a game, or send input.
- **Minecraft:** setup, calibration, and small camera requests. Movement,
  placement, and wall execution remain disabled.
- **OpenTTD:** a narrow loan-repayment reference integration using local Ollama.
- **Experimental adapters:** data-only contributor fixtures; no native gameplay.

Use the installed local app or the source checkout. Current source changes do not
automatically update an installed app. Personal and small-group use follows
[the local working approach](docs/personal-use.md).
See [known limitations](docs/known-limitations.md) and the
[Mario](docs/mario-player-guide.md) and [Stardew](docs/stardew-operator-guide.md) guides.

## Legacy requirements

- Python 3.11 or newer and [`uv`](https://docs.astral.sh/uv/).
- macOS for native game observation and input; separately installed games.
- Discoverable, signed-in Codex CLI for ordinary Mario/Stardew conversation.
  Selected game images and context are sent for remote inference.
- FCEUX and a supported local game file for Mario. Set `SMB3_GAME_FILE` or select
  the file in setup. FCEUX discovery checks PATH and standard Homebrew locations.
- Screen recording and Accessibility permissions for supported native input.
- Stardew ordinary watering requires a supported game-created farm, approved
  isolated copying and current-pixel readiness. The established default farm is
  discovered by the app; manual profile calibration belongs to retained regression
  workflows. See [Stardew setup](docs/private-beta-quick-start.md#stardew-ordinary-farm).

Linux CI exercises offline contracts and tests, not native game behavior.
OpenTTD additionally requires local Ollama with `gemma3:4b`.

## Source launch

From the repository root:

```bash
uv sync --locked --all-extras
.venv/bin/python -m smb3_agent lab ui --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/` and choose Minecraft. `/minecraft` opens that same
headless workspace. Historical games remain under `/legacy-games`, with Mario at
`/mario` and Stardew at `/stardew`; `/setup`,
`/onboarding` and `/lab` are secondary engineering surfaces. Their older native
controls are not part of Minecraft Beta 1. See the [current launch guide](docs/mc-b1-02-chat-play.md).

The server accepts loopback hosts only. It has no remote-access authentication,
TLS, or multi-user support. Do not expose it through a proxy, tunnel, or LAN bind.
The app does not load `.env` files. `GAME_COMPANION_EXPERIMENTAL_ROOT` overrides
only the Experimental-adapter installation root. See
[runtime and configuration](docs/runtime-and-configuration.md) for settings and storage.

## Legacy history, recovery and safe shutdown

Review and Start authorize the displayed finite scope. Stop/Take control releases
input and cancels continuation. Wait for confirmed handback before switching or
closing a game. If release cannot be confirmed, stop the specifically identified
game process; do not terminate unrelated processes.

Saved results are descriptive. Reopening never restores a connection,
observation, reviewed plan, or input permission. New work requires fresh compatible
setup and review. Confirmed work, uncertain outcomes, and return-to-start are
reported separately. See [recovery](docs/error-handling.md).

After handback, stop the foreground server with Control-C. The source
`Open Game Companion.command` starts a background server; use
`Stop Game Companion.command` for that instance. Packaged apps have their own
Quit action. Closing a browser alone is not a verified server shutdown.

## Development and tests

```bash
.venv/bin/python -m smb3_agent --help
.venv/bin/python -m pytest -q tests/test_goals.py
```

Use focused tests for the changed behavior and a short ordinary-use check.
Broader existing checks and CI remain available for changes that justify them.
Node 24 (`.nvmrc`) enables JavaScript regressions; no npm installation is needed. Test metrics, GitHub summaries, and
retained report artifacts are described in [development](docs/development.md).

Source lives in `src/smb3_agent/`, authored contracts and fixtures in `data/`,
validation/build tools in `scripts/`, and tests in `tests/`. Local game state,
evidence, calibration registrations, and build output remain ignored.

Read [architecture](docs/agent-architecture.md),
[module ownership](docs/ssot.md), [security](docs/security.md), and the
[documentation index](docs/README.md) for implementation detail.
