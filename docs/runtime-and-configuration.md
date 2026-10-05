# Runtime, configuration, and data

## Active AI beta runtime target

The current ordinary Mario/Stardew paths are deterministic; their Codex provider is not implemented. GC-A1 in the [engineering plan](private-beta-engineering.md) adds a supported app-owned Codex integration using saved CLI authentication, text/images, structured decisions and owned cancellation. The app must supply its own validated game tools; launching Codex does not automatically inherit this chat's computer-control tools.

The conversation and gameplay roles have separate bounded contexts. Scope/goal revision, observation/session identity and control generation bind replies; late output cannot execute. Provider sessions are descriptive, never gameplay permission. Runtime tools compose supported adapter skills instead of editing source.

Source launch currently runs from the checkout; the packaged app runs from Application Support. GC-D1 must separate read-only bundled resource paths from writable profiles, variants, histories and provider state. Relative planting-survey paths and ignored prepared-farm/profile/calibration registrations need explicit resource resolution/adoption, including their image dependencies. FCEUX scripts must be supplied and located as app resources. Finder launch cannot assume the developer shell's executable PATH.

Provider unavailability, login loss, rate limits, timeouts and invalid output produce visible remedies and safe release. GC-U/D2 integrate both-game setup, switch/reconnect, Quit, signals and restart; cleanup failures remain observable. Normal Codex inference sends selected game context/images to OpenAI, while reports remain local until explicitly shared.

Game Companion is a local Mac application with a loopback-only player UI, plus
Python engineering commands. The packaged app bundles its runtime; ordinary
player setup does not require terminal commands or YAML editing. Minecraft
Creative uses selected-window capture, app calibration and finite native skills.
OpenTTD uses visible observations, a local Ollama proposal and one reviewed
repayment. Mario uses FCEUX for supported live execution and
retains a separate Mednafen diagnostic path. Stardew provides isolated prepared-copy setup and guarded live browser controls for the locally qualified Day 2/Day 5 configurations; its public CLI remains inspection-only. Experimental adapters are
declarative, fixture-only catalog entries. There is no database, migration,
cloud API, or production deployment target.

The [PM handoff](private-beta-pm-handoff.md) records the active sequence: contextual Codex language and gameplay roles, reusable observations/skills, adaptive decisions and memory, both game experiences, ordinary setup, evaluation and a successor two-game Mac app. These AI and delivery requirements are not provided by the current deterministic parser or historical readiness flags. Minecraft/no-code expansion follows the first two gameplay experiences.
Current source and retained private.2 enable Minecraft calibration/camera only;
the building task is unfinished. Source corrections passed 1,327 canonical local
tests; Minecraft gameplay/package integration belongs to the later GC5 stage. The [review records](private-beta-review.md)
identify retained packages and their exact evidence.

## Runtime components

The packaged `Game Companion.app` enters through `app_runtime.py` and opens
`http://127.0.0.1:8765/setup`. For source development the same entry is
`python -m smb3_agent.app_runtime`; `smb3_agent/cli.py` owns engineering commands.
Both paths route into these current subsystems:

1. Goal and segment loaders read tracked YAML contracts under `data/goals/`
   and `data/segments/`.
2. Reliability and goal runs launch a new FCEUX process with
   `scripts/fceux_1_1_agent.lua`, then parse its event log and write an
   inspection report.
3. Mario observation, Show, takeover, product-session, run-library, learning,
   and coaching modules keep their state and authority boundaries separate.
4. Stardew modules define disposable-copy safety, visible-window observation,
   exact task accounting, and Observe/Tell/Show/Do controllers. The browser also owns prepared launch, profile connection, reviewed Start and input release; see the [Stardew guide](stardew-operator-guide.md).
5. Attempt Lab records runs, notes, reviews, issue ledgers, and task packets as
   local files. Route Lab serves those records and the player/catalog surfaces
   through Python's threaded HTTP server.
   The server binds only to `127.0.0.1`, `::1`, or `localhost` and runs until
   stopped.
6. Route-patch commands use Git and detached temporary worktrees to preview,
   validate, compare, promote, reject, or roll back an exact reviewed change.
7. Scenario, metric, and unattended modules keep deterministic, regression,
   reliability, visible, and owner evidence classifications distinct.
8. Experimental onboarding validates, scaffolds, installs, discovers, inspects,
   and removes bounded data-only adapters.
9. `player_setup.py`, `player_onboarding.py` and `player_setup_ui.py` own ordinary
   template/profile setup, read-only Minecraft progress, requests, local reports
   and safe-chat/direct controls. `player_store.py` persists bounded configuration
   and sanitized outcomes outside the app installation.
10. `minecraft_session.py` owns selected-window calibration connection, scope,
    review, task cancellation and page heartbeat. `minecraft_native.py` composes
    visible pose/material/cell observations, bounded camera/movement/addition
    providers and `minecraft_wall.py`. Availability comes from actual checked
    feature flags, independently of saved profiles.
11. `profile_conversation.py` and `profile_runtime.py` provide OpenTTD's narrow
    ordinary-app task; `model_gateway.py` sends a selected-window image and bounded
    task context to local Ollama at `127.0.0.1:11434`. The model proposes a finite
    plan and cannot post input or declare gameplay success.

The legacy Mednafen adapter is a separate macOS diagnostic path. It starts the
local `mednafen` executable, uses AppleScript to focus it, Quartz to locate and
capture its window, and `pyautogui` for input. It is not used by the product
reliability gate.

There is no independent scheduler, queue, worker service, or daemon. An
operator starts each CLI, emulator, or Route Lab process directly. While Route
Lab or the packaged player app is running, it owns bounded observation/task/watchdog
threads and helper/game child processes. The input guardian and camera emitter
are task-owned helpers. Server shutdown asks every session manager to stop;
unconfirmed cleanup is reported instead of permitting new authority.

## Conversation and plan runtime

The ordinary Mario workspace adds `conversation_service.py` between the typed
`request_planning.py` adapters and `mario_plan_runtime.py`. The renderer lives in
`conversation_ui.py`; HTTP transport remains in `lab_ui.py`. Plan revisions are
atomic data mailboxes, not Lua or shell supplied by text. The emulator consumes
epoch/session/revision-bound commands and acknowledges actual boundaries.
`fceux_b2_plan.lua` owns supported opening choices, speed/pause, reclaim and
neutral restoration; the accepted route script only exposes guarded callbacks.
The explicit conversation launch holds a fresh session for review and disables automatic
save/load for that isolated process. Legacy passive observation remains read-only.

Custom variants and outcome ledgers live under `artifacts/conversation/`; saved
revisions never restore runtime authority. The `game-companion-personal-beta/v3`
contract and `python -m smb3_agent.beta_readiness` inspect the retained B-series requirements. GC-D1 must version new readiness/scenario contracts for the corrected conversational beta; existing commands cannot certify it. Historical campaign manifests retain their meanings. See the [conversation guide](b2-conversation-guide.md).

## Operator configuration

The application does not load `.env` files and does not need a sample env file.
There is no ordinary-game Codex provider in current source yet. The successor beta uses CLI-managed sign-in as described above. OpenTTD requires separately installed
local Ollama with `gemma3:4b` at its fixed loopback endpoint. Minecraft's current
narrow typed requests do not require a model installation.

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

- FCEUX must be on `PATH` for live FCEUX runs. Python launches it as a local
  subprocess with the tracked Lua script and the operator's game-file path.
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
  No Codex/external inference provider is implemented in the current ordinary-game path; it is required successor-beta work.

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

There is no production service deployment, container image, package registry
release, database bootstrap, or service-manager definition. The local
`/api/delivery` endpoint reports server identity; `/api/delivery/shutdown`
requires the server token and matching instance identity.
The supported beta operating model is a local reviewed Mac app with ordinary
browser setup and separately installed game/model prerequisites. Engineers also
use the source checkout and CLI. Retained builds are locally ad-hoc signed, not
notarized; broader installation and machine compatibility remain untested.
The local UI has no TLS, user accounts, or remote-access authentication and
must remain on loopback.

The app checks source identity before reusing an instance on port 8765. A different
app/build must be quit through its own verified shutdown path; an unknown port
owner is not stopped. Closing a native workspace revokes that page's task lease;
**Quit Game Companion** performs server/session cleanup. Use the [quick start](private-beta-quick-start.md)
for permissions, first practice, recovery and feedback.

For development checks, use the focused workflow in the
[development guide](development.md). For a
live route change, also run the selected goal's authoritative reliability
profile and a separate watch playback as described in
[World 8 reliability gates](reliability-gate.md). Preserve the resulting local
evidence directory and record its exact path when reporting acceptance.

The final campaign is not a deployed job or generic CLI runner:
`data/scenarios/final-campaign.yaml` has `execution_enabled: false`. It is a
manual, frozen-candidate workflow with explicit owner pauses described in the
[consolidated final campaign](final-campaign-guide.md). The false setting
prevents automatic campaign execution. `scenario candidate-manifest` writes an ignored, exact clean
candidate-bound manifest under `artifacts/campaigns/`, and
`scenario final-campaign-readiness --candidate-manifest ... --gate` exits
nonzero unless implementation and campaign-entry prerequisites reconcile.
