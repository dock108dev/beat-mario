# World 8 Reliability Gates

Reliability is profile-driven by goal. The default Rank 27 profile proves
repeatable arrival at the accepted World 8 map boundary. The separate Rank 28
profile reuses that complete prefix, clears Big Tanks, and proves the normal
post-clear map return. The Battleships profile adds one cumulative segment and
stops before a Hand Trap. The Hand-Traps-and-Jet profile adds four ordered
segments and stops on accessible World 8-1 without entering it.

## Authoritative command

From the repository root:

```bash
export SMB3_GAME_FILE=/path/to/configured-mario-source
.venv/bin/python -m smb3_agent reliability run
```

Five runs are requested by default. Each run is structurally independent: the
orchestrator creates an isolated directory, records a single-attempt invocation,
and calls the existing `world_8_double_whistle` goal runner once. That call
launches a new FCEUX process from power-on. It cannot reuse an emulator process,
savestate, retry checkpoint, route bridge, mutation, discovery search, or the
legacy diagnostic route. Inherited `SMB3_*` route tuning is removed.

Passing requires all of the following:

- at least five runs were requested and every requested run completed;
- every run's structured log is present, valid, and parseable;
- the 15 `acceptance_event` values in the active segment catalog appear in the
  active contract's order;
- `metrics_passed=true` for every run;
- the final event is `post_probe_world_8_map_arrival` for every run;
- the accepted endpoint is observed as `world_number=7`, `object_set=0`;
- no prohibited event or local state artifact is detected;
- every FCEUX process exits successfully before its timeout.

Byte-identical SHA-256 log hashes are reported but are not required. Observable
contract success is authoritative.

The Rank 28 profile is selected explicitly:

```bash
.venv/bin/python -m smb3_agent reliability run \
  --goal world_8_big_tanks \
  --game-file "$SMB3_GAME_FILE"
```

It requests three runs by default. Each run must pass all 16 resolved events,
finish at `post_probe_world_8_big_tanks_post_clear`, and contain the five
focused authoritative screenshots: map, entry, gameplay, clear, and
post-clear. A map-only result, wrong stage, wrong entry state, death, gameplay
stall, timeout, enemy disappearance without a live boss defeat, missing chest
clear, missing stable post-clear state, or unexpected next-stage entry fails
closed with a bounded classification.

The Battleships profile is selected explicitly:

```bash
.venv/bin/python -m smb3_agent reliability run \
  --goal world_8_battleships \
  --game-file "$SMB3_GAME_FILE"
```

It requires at least three runs, all 17 ordered events, exactly five focused
screenshots per run, and byte-identical structured logs across the batch.
Wrong map, stage, entry state, death, false boss clear, missing or reordered
events, stall, timeout, unexpected next-stage entry, screenshot omission or
corruption, or fewer than three fresh successes fails the aggregate.

The 21-segment cumulative profile is selected explicitly:

```bash
.venv/bin/python -m smb3_agent reliability run \
  --goal world_8_hand_traps_jet \
  --game-file "$SMB3_GAME_FILE"
```

It requires at least three fresh one-attempt processes, all 21 ordered segment
events, byte-identical logs, and exactly 17 focused screenshots per run. The
accepted boundary is `world_number=7`, `object_set=0`, `map_page=2`, cursor
`(64,112)`. Missing, duplicate, or corrupt images; reordered or cross-satisfied
trap events; missing Leaf transitions; premature Jet; false boss defeat; death;
or World 8-1 entry fails closed.

## Watchable command

```bash
.venv/bin/python -m smb3_agent reliability watch
```

This command runs the same product goal once from a fresh game with the
documented 0.0035-second frame throttle. It captures review images and ticks,
extracts `state_tick_trace.log`, converts screenshots to PNG, and creates
`review/contact_sheet.png`. Its report always says:

```text
validation_policy=review_only
promotable=false
counts_toward_reliability=false
```

It writes beneath `artifacts/review/`, never under a reliability batch, and
cannot count toward the five authoritative runs. Capture and throttle overhead
may change route behavior.

Select the Big Tanks review profile with `--goal world_8_big_tanks`. The
accepted Rank 28 review used `--throttle-seconds 0.0001`; it retains exactly
the five focused contact-sheet frames plus a state/tick trace and remains
non-promotable.

Select `world_8_battleships` for the cumulative review. The accepted playback
used the independently validated `--throttle-seconds 0.0001`, retained exactly
five contact-sheet frames plus a 668-line tick trace, and remains `review_only`,
`promotable=false`, and excluded from authoritative reliability.

Select `world_8_hand_traps_jet` for the 21-segment review. The accepted playback
used `--throttle-seconds 0.001`, retained exactly 17 focused frames plus a
795-line tick trace and contact sheet, and is explicitly `review_only`,
`promotable=false`, and `counts_toward_reliability=false`.

## Artifact layout

An authoritative batch uses:

```text
artifacts/reliability/world_8_double_whistle/<timestamp>_reliability/
  reliability_report.json
  run_01/
    invocation.json
    fceux_execution.json
    fceux_1_1.log
    fceux_stdout.log
    fceux_stderr.log
    run_report.json
  run_02/ ... run_05/
```

A watchable review uses:

```text
artifacts/review/world_8_double_whistle/<timestamp>_watchable/
  invocation.json
  fceux_execution.json
  fceux_1_1.log
  fceux_stdout.log
  fceux_stderr.log
  state_tick_trace.log
  images/*.gd
  review/png/*.png
  review/contact_sheet.png
  run_report.json
  watchable_report.json
```

The equivalent Rank 28 roots are
`artifacts/reliability/world_8_big_tanks/` and
`artifacts/review/world_8_big_tanks/`. Authoritative Big Tanks run directories
also contain `evidence/png/01_...` through `05_...` for the required focused
screenshots.

The Battleships roots are
`artifacts/reliability/world_8_battleships/` and
`artifacts/review/world_8_battleships/`; its authoritative runs also contain
the five focused `evidence/png/` files.

The Hand-Traps-and-Jet roots are
`artifacts/reliability/world_8_hand_traps_jet/` and
`artifacts/review/world_8_hand_traps_jet/`; every authoritative run contains
exactly 17 ordered `evidence/png/` files.

The World-8-1-and-8-2 roots are
`artifacts/reliability/world_8_8_2/` and
`artifacts/review/world_8_8_2/`. Every authoritative run contains exactly nine
ordered `evidence/png/` files: Jet post-clear; 8-1 entry, gameplay, goal card,
and post-clear; then 8-2 entry, gameplay, goal card, and Fortress-access map.

Each aggregate records goal and route-catalog hashes, source commit and dirty
state, start/finish/elapsed time, run count, artifact paths, contract metrics,
final events, structured-log SHA-256 values, success rate, and overall result.

## Failure behavior

Runs fail closed and retain all artifacts created before the failure. Reports
distinguish:

- `preflight`: local prerequisite or product-contract invariant failed;
- `emulator-launch`: FCEUX could not launch or exited abnormally;
- `timeout`: the fresh process exceeded its bounded runtime;
- `artifact-integrity`: execution metadata or the route log is missing, corrupt,
  empty, or unparseable;
- `prohibited-tactic`: bridge, mutation, savestate/search, or prohibited local
  state evidence appeared;
- `observer/contract`: the ordered contract or observer metrics did not pass;
- `gameplay`: an explicit bad-state, missing-state, life-loss, or gameplay
  failure marker appeared.

Rank 28 refines gameplay failures into actionable wrong-map, wrong-stage,
wrong-entry-state, death, gameplay-stall, timeout, false-clear,
missing-post-clear, unexpected-next-stage, and ambiguous-state outcomes.
Battleships additionally rejects false boss clear, missing gameplay or clear,
event reordering, screenshot integrity failures, and a batch below its
three-fresh-success minimum.

Hand-Traps-and-Jet additionally reports and enforces the final accepted map
page/cursor boundary, rejects duplicate focused captures, and distinguishes the
last good segment from the first missing milestone.

World 8-1/8-2 additionally rejects visible-but-untouched goal objects, stale or
cross-satisfied goal-card events, goal touch without course clear, map return
without prior touch, death coincident with goal disappearance, unexplained card
transitions, premature 8-2 entry, an inaccessible or entered Fortress, and any
missing, duplicate, or corrupt member of the nine-image evidence set. Its
profile requires at least three fresh successes and byte-identical logs.

Every run report includes the last accepted product event and segment, the first
missing milestone, the first violated event when available, the final observable
map/mode/object set/inventory/lives/form, capture and throttle settings, and a
bounded recommended investigation. Unknown or ambiguous evidence is never a
pass. Preflight, runner, log-parser, focused-screenshot, and contact-sheet
exceptions retain their Python traceback in the owning report. See
[Error handling and operations](error-handling.md) for the operator triage order
and intentional resilience boundaries.

## Final finish-game profile

`world_8_finish_game` requires three successful runs, one attempt in each fresh
FCEUX process and isolated run directory. Each run must complete all 26 ordered
segments with zero bridges and retain exactly eight focused images: accepted
Super Tanks boundary, Castle entry, representative Castle gameplay, live
Bowser encounter, game-owned Bowser defeat, Princess rescue, credits, and the
stable final screen.

```bash
.venv/bin/python -m smb3_agent reliability run \
  --goal world_8_finish_game --game-file "$SMB3_GAME_FILE"
.venv/bin/python -m smb3_agent reliability watch \
  --goal world_8_finish_game --game-file "$SMB3_GAME_FILE"
```

The authoritative root is `artifacts/reliability/world_8_finish_game/`; the
separate review root is `artifacts/review/world_8_finish_game/`. A watch remains
`review_only=true`, `promotable=false`, and
`counts_toward_reliability=false`. Missing or reordered ending events, false
Bowser clear, life loss, incomplete credits, unstable ending, corrupt focused
evidence, and emulator or preflight failure all remain hard failures.

Accepted Slice 5 evidence is recorded under
`artifacts/reliability/world_8_finish_game/20260821T013757.568299Z_reliability`
and the separate review-only evidence under
`artifacts/review/world_8_finish_game/20260821T014037.846779Z_watchable`.
