# Game Companion

Choose Minecraft and chat beside its live view with a bot that plays as its own
character. It can gather resources, craft supplies, build bounded wooden shelters,
answer questions during play, and Stop. Codex CLI supplies the AI; gameplay runs
headlessly without taking over the desktop.

Minecraft is the main supported experience. Older integrations remain available
with narrower capabilities. See [Minecraft usage and recovery](docs/minecraft.md)
and [known limitations](docs/known-limitations.md).

## Source launch

Use Python 3.11+, uv, the exact Node version in `minecraft-worker/.nvmrc`, Java 21,
and a signed-in Codex CLI. From the repository root:

```bash
uv sync --locked --all-extras
npm ci --prefix minecraft-worker --ignore-scripts --no-audit --no-fund
.venv/bin/python -m smb3_agent lab ui --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`; `/minecraft` opens the same workspace. Follow the
in-app setup checks to open a retained world or explicitly create a practice world.
[usage and development](docs/minecraft.md) explains the required runtimes and limits.
No Screen Recording or Accessibility permission is needed for headless Minecraft.

Alternatively, use **Open Game Companion.command** after installing dependencies.
Use **Stop Game Companion.command** to close that background source instance and
save its world. For a foreground server, use Control-C after Stop; packaged apps
have their own Quit action. Closing a browser alone does not shut down the server.
Reopening restores conversation and memory, never gameplay authority.

The server accepts loopback hosts only. It has no remote-access authentication,
TLS or multi-user support; do not expose it through a proxy, tunnel or LAN bind.
It does not load `.env` files. `GAME_COMPANION_EXPERIMENTAL_ROOT` only overrides
Experimental-adapter storage. See [runtime and configuration](docs/runtime-and-configuration.md)
for data paths, settings and process ownership.

## Retained integrations

Historical games remain under `/legacy-games`, with Mario at `/mario` and Stardew
at `/stardew`. `/setup`, `/onboarding` and `/lab` are engineering surfaces.

- [Mario](docs/mario-player-guide.md): bounded strategy, coaching, coin routes and
  demonstration work; requires FCEUX, a supported local game file and native permissions.
- [Stardew](docs/stardew-operator-guide.md): retained preparation and bounded watering;
  its public CLI is inspection-only. Broader activity remains unverified.
- Legacy native Minecraft setup/calibration is separate from the headless product;
  movement, placement and wall execution remain disabled.
- OpenTTD retains a narrow loan-repayment reference using Ollama and `gemma3:4b`.
  Experimental adapters are data-only contributor fixtures.

See [known limitations](docs/known-limitations.md) for supported boundaries.
Linux CI checks offline behavior, not native game operation.

## Development and tests

```bash
.venv/bin/python -m smb3_agent --help
.venv/bin/python -m pytest -q tests/test_minecraft_chat.py tests/test_minecraft_memory.py
npm test --prefix minecraft-worker
```

Use focused checks for the changed behavior. See [development](docs/development.md)
for structure and commands, and the [CI contract](docs/CI.md) for broader gates.
Source lives in `src/smb3_agent/` and `minecraft-worker/`; authored contracts and
fixtures in `data/`; tools in `scripts/`; tests in `tests/` and `minecraft-worker/test/`.
Local game state, evidence, calibration registrations and build output stay ignored.

[Architecture](docs/agent-architecture.md) · [module ownership](docs/ssot.md) ·
[security](docs/security.md) · [documentation index](docs/README.md).
