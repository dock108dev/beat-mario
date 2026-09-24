# Runtime, configuration, and data

This repository is a local Python command-line application with a loopback-only
player and engineering UI. Mario uses FCEUX for supported live execution and
retains a separate Mednafen diagnostic path. Stardew currently provides a
copied-save/domain implementation and a safe unconfigured surface; its public
CLI and server do not launch or operate Stardew. Experimental adapters are
declarative, fixture-only catalog entries. There is no database, migration,
cloud API, or production deployment target.

## Runtime components

The `smb3_agent` CLI in `src/smb3_agent/cli.py` is the public entry point. Its
commands and the loopback UI route into these current subsystems:

1. Goal and segment loaders read tracked YAML contracts under `data/goals/`
   and `data/segments/`.
2. Reliability and goal runs launch a new FCEUX process with
   `scripts/fceux_1_1_agent.lua`, then parse its event log and write an
   inspection report.
3. Mario observation, Show, takeover, product-session, run-library, learning,
   and coaching modules keep their state and authority boundaries separate.
4. Stardew modules define disposable-copy safety, visible-window observation,
   exact task accounting, and Observe/Tell/Show/Do controllers. Only
   inspection and safe rendering are wired into the public entry points.
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

The legacy Mednafen adapter is a separate macOS diagnostic path. It starts the
local `mednafen` executable, uses AppleScript to focus it, Quartz to locate and
capture its window, and `pyautogui` for input. It is not used by the product
reliability gate.

There is no independent scheduler, queue, worker service, or daemon. An
operator starts each CLI, emulator, or Route Lab process directly. While Route
Lab is running, it owns bounded Show/live-observation threads and child
processes; server shutdown asks those managers to stop and closes the only
persistent server process.

## B2 conversation and plan runtime

The ordinary Mario workspace adds `conversation_service.py` between the typed
`request_planning.py` adapters and `mario_plan_runtime.py`. The renderer lives in
`conversation_ui.py`; HTTP transport remains in `lab_ui.py`. Plan revisions are
atomic data mailboxes, not Lua or shell supplied by text. The emulator consumes
epoch/session/revision-bound commands and acknowledges actual boundaries.
`fceux_b2_plan.lua` owns supported opening choices, speed/pause, reclaim and
neutral restoration; the accepted route script only exposes guarded callbacks.
The B2 explicit launch holds a fresh session for review and disables automatic
save/load for that isolated process. Legacy passive observation remains read-only.

Custom variants and outcome ledgers live under `artifacts/conversation/`; saved
revisions never restore runtime authority. The `game-companion-personal-beta/v2`
contract and `python -m smb3_agent.beta_readiness` inspect the new requirements
without altering historical campaign manifests. See the [B2 guide](b2-conversation-guide.md).

## Operator configuration

The application does not load `.env` files and does not need a sample env file.
There are no credentials or network service endpoints to configure.

| Setting | Used by | Behavior |
| --- | --- | --- |
| `SMB3_GAME_FILE` | Live Mario goal, reliability, task, command, observation, and Route Lab actions | Absolute or repository-relative path to the operator's local game file. An explicit `--game-file` wins where the command exposes that option. |
| `GAME_COMPANION_EXPERIMENTAL_ROOT` | Experimental adapter installation, discovery, status, and removal | Optional local installation root. The default is `~/Library/Application Support/Game Companion/Experimental Adapters`. |
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
  capture its pixels using Quartz and `mss`, but no public command currently
  constructs a live Stardew controller or ordinary-input driver.
- The standard-library web server and optional default-browser launch are the
  only Route Lab integrations. Route Lab makes no cloud or external HTTP calls.

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

Experimental scaffolds default to repository-local `experimental-adapters/`.
Installed Experimental adapters live under the configured installation root,
outside `artifacts/`; each installation is bounded by its manifest and hashes.

Treat `artifacts/` as local evidence, not as a durable shared store. Back it up
separately if a run must be retained. Never commit game files, savestates,
screenshots, logs, generated evidence, or copyrighted local UI assets.

## Deployment and operations boundary

There is no production service deployment, container image, package registry
release, database bootstrap, health endpoint, or service-manager definition.
The supported operating model is a repository checkout on an engineer's
machine. Route Lab is an operator convenience surface, not a deployable web
application: it has no TLS, user accounts, or remote-access authentication and
must remain on loopback.

For routine operation, run the canonical non-live gate before a change. For a
live route change, also run the selected goal's authoritative reliability
profile and a separate watch playback as described in
[World 8 reliability gates](reliability-gate.md). Preserve the resulting local
evidence directory and record its exact path when reporting acceptance.

The final campaign is not a deployed job or generic CLI runner:
`data/scenarios/final-campaign.yaml` has `execution_enabled: false`. It is a
manual, frozen-candidate workflow with explicit owner pauses described in the
[consolidated final campaign](final-campaign-guide.md). The false setting
prevents automatic campaign execution; it does not mean V2.14 implementation is
missing. `scenario candidate-manifest` writes an ignored, exact clean
candidate-bound manifest under `artifacts/campaigns/`, and
`scenario final-campaign-readiness --candidate-manifest ... --gate` exits
nonzero unless implementation and campaign-entry prerequisites reconcile.
