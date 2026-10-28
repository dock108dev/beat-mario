# Development

## Environment and commands

From the repository root, use Python 3.11+ and the Node version in
`minecraft-worker/.nvmrc`:

```bash
uv sync --locked --all-extras
npm ci --prefix minecraft-worker --ignore-scripts --no-audit --no-fund
.venv/bin/python -m smb3_agent --help
.venv/bin/python -m smb3_agent lab ui --host 127.0.0.1 --port 8765
```

The editable Python package supplies the `smb3-agent` command. Gameplay additionally
requires Java 21 and an explicitly [configured AI provider](ai-provider.md). Source launch opens the Minecraft workspace;
see [usage](minecraft.md). Configuration is explicit: the app does not load `.env`.

## Repository layout

| Directory | Responsibility |
|---|---|
| `src/smb3_agent/` | Application, HTTP/desktop entry points, adapters and CLI |
| `minecraft-worker/` | Headless bot, viewer, skills and Node tests |
| `tests/` | Python behavior, protocol, UI and configuration tests |
| `data/` | Authored contracts, schemas and required replay fixtures |
| `scripts/` | Launch, validation, packaging and emulator tools |
| `docs/` | Usage and contributor documentation |

Runtime state, game files, evidence, caches and root build output stay ignored.
Required fixtures in `data/fixtures/state/` and authored controller scripts remain
tracked. Do not force-add private game assets or local profiles. Internal working
notes are not prerequisites for running or contributing to the project.

## Testing

Use affected checks with disposable state:

```bash
GAME_COMPANION_USER_DATA="$(mktemp -d)" .venv/bin/python -m pytest -q tests/test_minecraft_chat.py tests/test_minecraft_memory.py
npm test --prefix minecraft-worker
.venv/bin/python -m ruff check src tests
```

Do not use owner data, paid inference or native input for offline tests. Existing
synthetic tests cover cancellation, revision checks, persistence, recovery and
HTTP boundaries. Native behavior needs a separate explicit live check when relevant.

The broader offline gate is:

```bash
PYTHON=.venv/bin/python scripts/validate_phase0.sh
```

It creates a fresh profile and checks lint, tracked-file hygiene, all Python tests,
CLI contracts and static renders. See [CI](CI.md) for worker tests, coverage,
workflow validation, clean-export builds and reports. Documentation-only edits need
link/reference and whitespace checks rather than a full application campaign.

## Local review packaging

Source development requires no signed app build. To distribute a local macOS app,
`scripts/build_private_beta.py` needs PyInstaller, Tesseract with English data and
license, the exact worker runtime/dependencies, compatible calibration resources
required by `release_resources.py`, and an existing stable signing identity.
Those local assets are not all supplied by the source checkout or `uv sync`.

Pass explicit new `--version`, `--build` and `--sign-identity` values; the builder
refuses to overwrite existing output. Its default identifiers are not a release
selection mechanism. The package includes `docs/minecraft.md` as its usage guide.
`scripts/install_private_beta.py` verifies signing identity, requires the old app
to be closed and retains the prior installation. Do not change installed data or
signing identity as part of ordinary source maintenance.

## Module boundaries

Keep stateful controllers and integrity transactions cohesive. The
[module map](ssot.md) identifies their owners. Pure Minecraft planning/context is
separate from session authority, execution and storage. The remaining coordinator's
connect/inference/Stop transitions share one lock, epoch and cancellation state;
extracting them needs an explicit shared authority interface.

The legacy HTTP module still mixes composition and rendering. Extract presentation
using explicit inputs before separating server ownership, preserving routes, CSP,
CSRF and response contracts. Mario/Stardew conversation separation likewise needs
a shared descriptive-history/refusal interface rather than circular imports.
CLI registration changes must preserve command groups and help/error behavior.

Route patching keeps its reviewed mutation and integrity checks together. Emulator
controllers retain their callback/event contracts. Large behavioral test modules
share simulator fixtures and scenario assertions; avoid cross-importing additional
mutable test state when splitting them.

Review authored Python above 500 lines and split or justify cohesion above 1,000;
JavaScript uses 300/600, UI templates 250/500, CSS 300/600 and shell 100/200.
Count physical lines, review embedded languages by role, and exclude generated
files/lockfiles from mechanical splitting. These are maintenance guidance, not a
reason to compress readable code or change existing lint policy.
