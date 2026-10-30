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
Install the known compatible build tool into the project environment with
`uv pip install --python .venv/bin/python 'PyInstaller==6.22.3'`.
If original local calibration files are unavailable, pass `--calibration-app`
with an existing signed Game Companion app. Its signature and retained calibration
hashes are verified before reuse; this does not establish new gameplay results.

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

The shared legacy document shell and CSRF form injection live in `lab_page.py`;
`lab_page_styles.py` owns its stylesheet and `player_workspace_script.py` owns
browser refresh behavior. `lab_ui.py` keeps existing import names for callers.
These modules have no server or session dependencies. The stylesheet remains one
roughly 610-line cascade: companion and Route Lab share primitives and responsive
overrides, and separating selectors without a design boundary risks changing their
precedence. It is reviewed as CSS, not exempted by its Python container.

The remaining legacy HTTP module still mixes route dispatch, service composition
and feature panels. Next extract pure panel renderers with explicit inputs; then
introduce a service container before separating dispatch. Preserve routes, CSP,
CSRF, patchable service hooks and response contracts. Mario/Stardew conversation separation likewise needs
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


### Remaining structural work

`MinecraftChat`, `BuildProject`, `LiveObservationManager` and `StardewRuntime`
remain cohesive authority/transaction owners: their callbacks share locks, epochs,
connection ownership or database transactions. Extracting methods into independent
stateful services now would create competing owners. Before splitting them, define
an explicit owner-supplied transaction/session interface and move pure projections
first. Keep BuildProject storage and receipt validation in the same transaction.

Other bounded follow-ups are CLI command-group registration/dispatch; independent
report generation in `lab.py`, `learning.py`, `reliability.py` and `unattended.py`;
and presentation versus input/accounting in the Stardew companion/adapter. These
remain unresolved separations, not declarations that their current sizes are ideal.
The FCEUX log parser is a single ordered protocol reducer: keep its event state and
sequence validation together until typed event records can replace shared local
state. Route-patch validation/promotion must retain its hash checks and atomic
mutation boundary. Existing simulator-heavy test modules should be separated by
protocol, HTTP/rendering and reliability scenarios after shared fixtures move into
fixture modules; never import mutable setup from another test module.

### Source hygiene

Keep required replay fixtures in `data/fixtures/state/` and authored contracts in
`data/`. Generated reports, caches, local notes, game assets and app builds stay
ignored. Do not add credentials or owner profiles to source control. Documentation
and tests must not require private trackers or previously generated local reports.
