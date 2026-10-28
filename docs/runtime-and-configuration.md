# Runtime and configuration

## Minecraft

The loopback application routes requests through `minecraft_chat.py`, bounded goal
coordinators and `minecraft_bridge.py` to one Node worker scheduler. Codex CLI
supplies structured decisions; its calls do not own game input. Server state and
worker events establish outcomes. Session/revision checks reject stale work.
Canceling a caller's Python Future only abandons its reply: it does not stop the
bot. Use bridge Stop for gameplay cancellation. Abandoned replies must not stop
the reader or prevent other pending requests from receiving failure/results.

Minecraft state uses JSON snapshots and JSONL event files, not SQL. `memory.json`
is authoritative for the structure library and current selection;
`construction.json` is its compatibility mirror. `places.json` stores scoped
places/protections; `conversation.json` stores bounded conversation and request
IDs. World identity and dimensions remain part of memory compatibility. Minecraft
world data is owned by the Java server, separately from companion snapshots.
`minecraft_delivery.py` selects source artifacts or the explicit/installed user
data root. Consult [usage and development](minecraft.md).

`DurableJSON` validates snapshots, syncs temporary files and archived prior
states, atomically replaces the primary and syncs its parent directory. Restore
preserves the displaced primary as incident evidence. The recovery warning clears
only after replacement and directory synchronization succeed. Failed restore
remains blocked and can be explicitly retried; it never grants gameplay authority.
Requests rejected for a memory problem do not consume their request ID or append
a user message. Direct Stop remains available.

The application coordinator serializes its writes; these files are not a
multi-process database. Do not run source and installed delivery against the same
writable state. Generations, incident copies and JSONL logs have no automatic pruning
policy. The source-to-install migration activates multiple directories separately;
an interruption can leave conflicting partial state. Preserve original data and
inspect a failed migration before retrying rather than merging or overwriting it.

## Other integrations

Mario uses FCEUX; Stardew uses calibrated native observations and guarded input.
Experimental adapters are declarative fixtures. Native Minecraft camera setup is
separate from the headless workspace. Source and desktop entry points open `/`;
older routes remain available under `/legacy-games`.

## Operator configuration

The application does not load `.env` files and does not need a sample env file.
Ordinary Mario/Stardew use CLI-managed Codex sign-in as described above. `codex_provider.discover_codex` checks PATH and bounded Node/Homebrew installation locations; no credential file is copied into app data. Setup can refresh readiness after sign-in. OpenTTD requires separately installed
local Ollama with `gemma3:4b` at its fixed loopback endpoint. Headless Minecraft uses Codex CLI; no local model download is required.

| Setting | Used by | Behavior |
| --- | --- | --- |
| `SMB3_GAME_FILE` | Live Mario goal, reliability, task, command, observation, and Route Lab actions | Absolute or repository-relative path to the operator's local game file. An explicit `--game-file` wins where the command exposes that option. |
| `GAME_COMPANION_EXPERIMENTAL_ROOT` | Experimental adapter installation, discovery, status, and removal | Optional local installation root. The default is `~/Library/Application Support/Game Companion/Experimental Adapters`. |
| `GAME_COMPANION_USER_DATA` | Player profiles, history, reports, settings backups and native sessions | Optional local data root, defaulting to `~/Library/Application Support/Game Companion`. Development checks should use disposable storage. Ordinary players use the in-app data location. |
| `PYTHON` | `scripts/validate_phase0.sh` | Interpreter used by the repository gate; defaults to `python`. This is a development-script setting, not application configuration. |

Authoritative reliability runs sanitize inherited variables whose names begin
with `SMB3_`, then apply the selected preset from
`src/smb3_agent/presets.py`. The many `SMB3_*` reads in the Lua runner are an
internal Python-to-FCEUX protocol and diagnostic tuning surface. They are not a
supported production configuration API. Low-level diagnostic commands may
accept explicit `--set-env NAME=VALUE` overrides; their output is not accepted
product reliability evidence.

`STARDEW_REGRESSION_SAVE` is also internal: the unattended Stardew provider
sets it to a fresh attempt-owned fixture copy. It is not an operator setting
and must never point to an owner save.

Other behavior is selected through CLI arguments and tracked configuration:

- goal composition and run policy: `data/goals/*.yaml`;
- segment acceptance events: `data/segments/*.yaml`;
- executable preset environment: `src/smb3_agent/presets.py`;
- structured diagnostic input: `data/routes/scripts/*.yaml`;
- Route Lab location labels: `data/worlds/world_1_locations.yaml`;
- Mario product, profile, Tell, and Show declarations: `data/mario/`,
  `data/profiles/`, `data/tell/`, and `data/show/`;
- Stardew safety/evidence declarations: `data/stardew/`;
- catalog, scenario, metric, campaign, and unattended contracts:
  `data/companion/` and `data/scenarios/`;
- finite private-beta OpenTTD profile and Minecraft settings/practice declarations:
  `data/private-beta/`, `minecraft_settings.py` and the app's supported templates;
- Experimental adapter schema, fixture, and artifact contract:
  `data/experimental-adapters/`.

Use `python -m smb3_agent COMMAND --help` and subcommand help for current CLI
arguments. Goal identifiers can be passed in place of paths to goal commands.

## Local executables and integrations

- `executable_discovery.py` owns FCEUX resolution for setup, live observation, Show, engineering runs and default reliability preflight: PATH first, then executable files in `/opt/homebrew/bin` and `/usr/local/bin`. Manual selection and saved selections must match FCEUX discovered on PATH or at those fixed locations; Homebrew symlinks and their resolved targets are supported. Other paths are refused before filesystem access to the supplied path. Custom installations must be on PATH when the app starts. Launches use the resolved path and explicitly refuse a missing executable. Python supplies the tracked Lua script and configured game-file path.
- Git must be available for source-state evidence and route-patch worktrees.
- Mednafen, AppleScript, Accessibility permission, screen-capture permission,
  and a visible desktop session are required only by the optional macOS
  diagnostic adapter.
- The macOS Stardew backend can inspect one visible foreground window and
  capture its pixels using Quartz and `mss`, and the browser setup connects the live controller and ordinary-input driver
  after checking isolation and profile compatibility. CLI commands remain inspection-only.
- Minecraft and OpenTTD native input require macOS Screen & System Audio Recording
  and Accessibility permissions, the exact selected supported game window and
  exclusive input while a reviewed task runs. The native path uses bounded
  input/guardian workers; changing window/settings requires fresh checks.
- OpenTTD additionally requires local Ollama/`gemma3:4b`; local model HTTP calls
  remain on loopback. Current Minecraft requests are parsed into finite skills.
- Packaged review builds include Python dependencies and OCR resources. Games,
  worlds, model weights and account credentials are separately owned prerequisites.
  The source Codex provider is implemented; retained review packages keep their original manifests and do not acquire source capabilities automatically.

Python dependencies and the supported Python version are declared in
`pyproject.toml`; the locked local resolution is in `uv.lock`. GitHub Actions
installs the exact locked development graph on Python 3.11 using a cache keyed
by `uv.lock` and runs the non-live gate. Pull requests additionally compare
dependency changes against GitHub's advisory data.

## Persistence and data ownership

Tracked YAML files under `data/goals/`, `data/segments/`, `data/routes/`, and
`data/worlds/` are repository inputs. Tests also use tracked PNG fixtures under
`data/fixtures/`. There is no relational or remote data store.

Generated state is filesystem-only and ignored by Git:

| Path | Contents |
| --- | --- |
| `artifacts/reliability/<goal>/` | Timestamped authoritative batch logs, execution metadata, and reports. |
| `artifacts/review/<goal>/` | Timestamped throttled watch playback and review images. |
| `artifacts/sessions/` | Attempt Lab sessions; `latest.txt` points to the latest local session. |
| `artifacts/route-patches/<patch-id>/` | Imported patch contract, state, diffs, validation output, comparison evidence, and audit records. |
| `artifacts/ui/last_command.yaml` | Most recent Route Lab command result for local display. |
| `artifacts/live-observation/` and `artifacts/show/` | Bounded Mario live-observation and review-only demonstration sessions. |
| `artifacts/run-library/` and `artifacts/learning/` | Local run/profile history and append-only learning/review records. |
| `artifacts/product-session/` | Mario first-use choices, appropriate preferences, and local product history. |
| `artifacts/companion/` | Bounded catalog selection/preferences and separately classified switch events. |
| `artifacts/stardew-operator/` | Stardew copied-save attempt evidence when a controller is explicitly constructed. |
| `artifacts/scenarios/` and `artifacts/session-metrics/` | Classified scenario attempts, events, indexes, summaries, and exports. |
| `artifacts/unattended-regression/` | Immutable regression-only manifests, run directories, reports, cleanup evidence, and comparisons. |
| `artifacts/campaigns/<exact-commit>/` | Ignored candidate-bound entry manifest with clean Git identity, contract hashes, deterministic totals, blank-owner guarantee, and proof limits. |
| `public/assets/local/` | Optional ignored local artwork used by Route Lab. |
| `~/Library/Application Support/Game Companion/profiles/`, `history/` and `reports/` | Player configurations, sanitized outcome history and inspectable feedback; `GAME_COMPANION_USER_DATA` can select another local root. |
| `~/Library/Application Support/Game Companion/sessions/` and `settings-backups/` | Calibration/native attempt diagnostics and backed-up Minecraft options/debug preferences; preserved outside installation. |
| `dist/private-beta/` | Ignored versioned review apps, manifests, supplied guides and retained package evidence. Existing identified packages must be preserved when preparing a successor. |

Experimental scaffolds default to repository-local `experimental-adapters/`.
Installed Experimental adapters live under the configured installation root,
outside `artifacts/`; each installation is bounded by its manifest and hashes.

Treat `artifacts/` as local evidence, not as a durable shared store. Back it up
separately if a run must be retained. Never commit game files, savestates,
screenshots, logs, generated evidence, or copyrighted local UI assets.

Saved player profiles restore configuration and notes only. They never restore a
live connection, current observation, calibration authority or reviewed plan.
Imports are bounded declarative data. Report previews exclude raw screenshots and
unrelated game data; native diagnostic folders may contain captures and require
inspection before sharing. Applying supported Minecraft settings backs up options
and debug preferences after checking that the game is closed; it does not edit worlds.

## Deployment and operations boundary

Current operation is a local installed app or source server with separate game/model prerequisites. Keep the loopback boundary and existing instance/process ownership. Unknown port owners are not stopped. Closing a browser is not server shutdown; use the app Quit or the matching source stop command.

Delivery identity/shutdown endpoints are local implementation tools. Preserve the installed signing identity and permissions when updating the app.

The app checks source identity before reusing an instance on port 8765. A different
app/build must be quit through its own verified shutdown path; an unknown port
owner is not stopped. Closing a native workspace revokes that page's task lease;
**Quit Game Companion** performs server/session cleanup. Use the [Minecraft recovery guide](minecraft.md)
for permissions, first practice, recovery and feedback.

For development checks, use the focused workflow in the
[development guide](development.md). For a
live route change, also run the selected goal's authoritative reliability
profile and a separate watch playback as described in
[World 8 reliability gates](reliability-gate.md). Preserve the resulting local
evidence directory and record its exact path when reporting acceptance.

The final campaign is not a deployed job or generic CLI runner:
`data/scenarios/final-campaign.yaml` has `execution_enabled: false`. It is a
manual evaluation contract described in [campaign contracts](final-campaign-guide.md).
The false setting prevents automatic execution. `scenario candidate-manifest` writes an ignored, exact clean
candidate-bound manifest under `artifacts/campaigns/`, and
`scenario final-campaign-readiness --candidate-manifest ... --gate` exits
nonzero unless implementation and campaign-entry prerequisites reconcile.
