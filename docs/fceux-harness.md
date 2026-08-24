# FCEUX Harness

FCEUX is the current reliable backend for SMB3 route work. It gives the project
direct controller input, stable state reads, route logs, and optional screenshot
captures.

Use this document for backend mechanics. Use
[World 8 reliability gates](reliability-gate.md) for product pass/fail rules and
[development](development.md) for the repository validation workflow.

## Core Runner

Command:

```bash
python -m smb3_agent task fceux-1-1 \
  --game-file "$SMB3_GAME_FILE" \
  --attempts 10 \
  --artifacts-dir artifacts/fceux/cli_gate_1_1 \
  --require-perfect
```

The Python harness launches FCEUX with `scripts/fceux_1_1_agent.lua`, captures
stdout/stderr, writes `fceux_1_1.log`, and parses route markers.

## Route Markers

The Lua script writes markers that the Python harness parses:

```text
attempt_N_reached_end_x
attempt_N_goal_area
attempt_N_success_course_clear
attempt_N_bad_state
post_probe_*
```

`success_course_clear` only counts if the route first reached the expected goal
area. This avoids mistaking a death or invalid transition for a completed level.

## Legacy diagnostic preset: World 1 King Transition

Command:

```bash
python -m smb3_agent goal run world_1_king \
  --game-file "$SMB3_GAME_FILE" \
  --attempts 10 \
  --artifacts-dir artifacts/goals/world_1_king
```

Expected summary:

```text
successes=10/10
bad_states=0/10
post_probe_last_event=post_probe_1_airship_success_king
post_probe_clear=true
```

This preset is a diagnostic route, not the product goal and not a claim that
every World 1 segment is solved by regular gameplay. It cannot prove safe World
2 arrival or World 8. See [Route status](route-status.md).

## Visual Review

For screenshot-backed review:

```bash
python -m smb3_agent goal run world_1_king \
  --game-file "$SMB3_GAME_FILE" \
  --attempts 1 \
  --artifacts-dir artifacts/goals/inspect_world_1_king \
  --capture-images \
  --capture-ticks

python -m smb3_agent task fceux-contact-sheet \
  --input-dir artifacts/goals/inspect_world_1_king/images
```

The contact sheet is a review aid only. Structured log markers are the source of
truth for this diagnostic's pass/fail; the selected goal contract determines
whether those markers mean product success.

## Product reliability mode

Use the operator-facing product gate instead of a multi-attempt low-level
invocation:

```bash
export SMB3_GAME_FILE=/path/to/configured-mario-source
.venv/bin/python -m smb3_agent reliability run
```

The outer orchestrator invokes the existing product goal five times with
`attempts=1`. Each invocation starts a new FCEUX process and gets isolated
stdout, stderr, route log, execution metadata, invocation metadata, and result
report. Reliability mode removes inherited `SMB3_*` tuning variables before
setting its required product environment and leaves frame sleep at zero.

## Watchable product review

Use the separate review command:

```bash
.venv/bin/python -m smb3_agent reliability watch
```

This fresh product-route run uses a 0.0035-second per-frame sleep, captures
images and ticks, converts review PNGs, and writes a contact sheet. Its report
is permanently `review_only` and excluded from reliability evidence. Watchable
timing and capture overhead can alter gameplay; leave them out of reliability
mode.

## Environment Overrides

The low-level `fceux-1-1` command supports route experiments through
`--set-env KEY=VALUE`.

Example:

```bash
python -m smb3_agent task fceux-1-1 \
  --attempts 1 \
  --artifacts-dir artifacts/fceux/probe_1_2_timing \
  --post-1-1-probe run_1_2_naive \
  --set-env SMB3_1_2_HILL_ENEMY_JUMP_FRAMES=32 \
  --require-perfect
```

Use explicit artifact directories for experiments. Do not overwrite gate
artifacts when sweeping timings.

## Failure Review

Review an existing log:

```bash
python -m smb3_agent task review-fceux-log \
  --log artifacts/fceux/world_1_king/fceux_1_1.log \
  --attempts 10
```

Minimum useful failure evidence:

- Last `post_probe_*` event.
- Max x reached in the active segment.
- Final mode/object set.
- Lives/form state if available.
- Whether the run used watchable throttle or reliability mode.
