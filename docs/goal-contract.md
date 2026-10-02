# Goal Contract

Mario route-goal reference. These versioned route contracts define their selected diagnostic or gameplay objective. The [private-beta engineering plan](private-beta-engineering.md) owns application release scope.

A goal contract is the machine-readable source of truth for a selected Mario route objective.
The default Route Lab contract remains
`data/goals/world_8_double_whistle.yaml`. Rank 28 adds the explicitly selected
`data/goals/world_8_big_tanks.yaml` contract without changing that default.
`data/goals/world_8_battleships.yaml` supplies a separately selected cumulative extension.

Goal contracts are also authoritative for supported product-goal ids, prefix
order, and Route Lab display metadata. Every contract declares `display.name`
and `display.subtitle`; Route Lab discovers product contracts instead of
maintaining its own registry. Fixed preset environment policy belongs only in
`src/smb3_agent/presets.py`; goal-local `runner.env` is unsupported.

## Route semantics

- `objective_milestone`: directly required by the owner goal.
- `game_prerequisite`: traversal required to reach a later owner milestone.
- `optional`: available but unnecessary for the selected goal.
- `recovery_only`: used only after a classified failure and never on the
  nominal route.
- `diagnostic_route`: a supported test path that is not the product goal.
- `bridge`: an explicit temporary transition aid. It is an execution mode, not
  evidence that the game requires a segment. Bridge use must be declared and
  cannot satisfy a goal that disallows it.

Route need and execution status are separate. All 15 default product steps and
the Big Tanks and Battleships extension steps are `normal_gameplay`; the legacy
diagnostic's bridges remain isolated and are not product proof.

## Default contract shape

```yaml
id: world_8_double_whistle
game: smb3
goal_type: product_goal
execution_status: executable
user_directive: >-
  Collect both World 1 Warp Whistles, safely reach World 2, use both
  whistles, and arrive on the World 8 map.
display:
  name: World 8 Arrival
  subtitle: World 2-first double-whistle route to World 8

objective:
  type: route_completion
  target: world_8_map_arrival

route:
  catalog: data/segments/world_8_double_whistle.yaml
  segments:
    - id: world_1_3_whistle
      classification: objective_milestone
      execution_mode: normal_gameplay
      evidence: [live_fceux_2026-08-09_first_whistle_inventory]
    - id: world_1_6_clear
      classification: game_prerequisite
      execution_mode: normal_gameplay
      evidence: [live_fceux_2026-08-09_1_6_fresh_playback]
    - id: world_1_airship_to_king
      classification: game_prerequisite
      execution_mode: normal_gameplay
      evidence: [live_fceux_2026-08-09_world_8_fresh_playback_x3]
    - id: world_2_map_arrival_with_two_whistles
      classification: objective_milestone
      execution_mode: normal_gameplay
      evidence: [live_fceux_2026-08-09_world_8_fresh_playback_x3]
    - id: world_2_first_whistle_use
      classification: objective_milestone
      execution_mode: normal_gameplay
      evidence: [live_fceux_2026-08-09_world_8_fresh_playback_x3]
    - id: world_8_map_arrival
      classification: objective_milestone
      execution_mode: normal_gameplay
      evidence: [live_fceux_2026-08-09_world_8_fresh_playback_x3]

runner:
  preset: fceux_world_8_double_whistle
  executable: true
```

The real contract contains every ordered step. Each step has non-empty evidence
and an explicit execution mode. Unknown classifications, modes, presets,
recovery actions, bridge declarations, duplicate segments, and missing catalog
segments fail validation.

## Default route invariants

- Both World 1 whistle acquisitions are owner milestones.
- World 1-4 is absent.
- World 1-5 and World 1-6 are game prerequisites after the owner corrected the
  route to require the final World 1 castle and World 2 arrival.
- Airship/King is an intermediate game prerequisite.
- World 2 map arrival with two whistles occurs before first-whistle use.
- First-whistle use and second-whistle use are distinct.
- The second whistle is used from the Warp Zone, before entering a numbered
  pipe.
- The 5/6/7 tier, World 8 tier, World 8 pipe, and World 8 map are distinct
  observable states.
- `post_probe_1_airship_success_king` cannot satisfy this contract.
- Only `post_probe_world_8_map_arrival` can be the final success event.
- Planned segments are never rendered or reported as solved.

## Rank 28 composed contract

The Big Tanks goal declares the accepted default goal as its prefix and owns
only the new segment:

```yaml
id: world_8_big_tanks
game: smb3
goal_type: product_goal
execution_status: executable

objective:
  type: route_completion
  target: world_8_big_tanks_post_clear

route:
  prefix_goal: world_8_double_whistle
  catalog: data/segments/world_8_double_whistle.yaml
  segments:
    - id: world_8_big_tanks_clear
      classification: objective_milestone
      execution_mode: normal_gameplay

runner:
  preset: fceux_world_8_big_tanks
  executable: true
```

Resolution produces the unchanged 15-segment prefix followed by exactly one
extension segment. Prefix cycles, cross-catalog composition, a missing prefix,
duplicate segments, or an unsupported preset fail validation.

The extension cannot pass on World 8 map arrival or stage entry. Its ordered
observer evidence requires Big Tanks entry, genuine scrolling gameplay, live
boss defeat with no life loss, chest collection and game return-map flag, then
a stable World 8 map observation at cursor `(64,112)`. The final success event
is `post_probe_world_8_big_tanks_post_clear`; no later World 8 stage may be
entered.

## World 8-Battleships composed contract

Battleships declares the accepted Big Tanks goal as its prefix and owns exactly
one segment:

```yaml
id: world_8_battleships
game: smb3
goal_type: product_goal
execution_status: executable

objective:
  type: route_completion
  target: world_8_battleships_post_clear

route:
  prefix_goal: world_8_big_tanks
  catalog: data/segments/world_8_double_whistle.yaml
  segments:
    - id: world_8_battleships_clear
      classification: objective_milestone
      execution_mode: normal_gameplay

runner:
  preset: fceux_world_8_battleships
  executable: true
```

Resolution produces exactly 17 ordered segments and zero bridges while leaving
the 15- and 16-segment goals unchanged. The observer requires the accepted Big
Tanks post-clear cursor `(64,112)`, normal automatic entry at map node
`(128,112)`, stage object set `10`, entry id `13`, and original entry state
`x=0`, `y=320`, `air=0`. A delayed screenshot does not rewrite that captured
entry identity.

Boss success is game-owned: live object id `75` must be replaced by the
defeated-transition object id `74` while Mario is alive, then return flag
`0x14=1` must occur. The final event is
`post_probe_world_8_battleships_post_clear` at cursor `(128,112)`, after a
180-frame stable map observation with `hand_trap_entered=0`.

## World 8 Hand Traps and Jet composed contract

`world_8_hand_traps_jet` declares `world_8_battleships` as its unchanged prefix
and adds exactly four ordered objective segments: right Hand Trap, center Hand
Trap, left Hand Trap, and World 8-Jet. Resolution is exactly 21 segments and
zero bridges; the 15-, 16-, and 17-segment goals remain unchanged.

Each trap owns a distinct entry, gameplay, reward, and stable-map contract.
All use object set `11`; right and left enter at `(24,320)`, while center enters
at `(24,368)`. Their map cursors are `(160,112)`, `(128,112)`, and `(96,112)`.
Every reward requires game object `82`, Super Leaf item id `3`, and an observed
`0 -> 1` inventory transition. One trap's events cannot advance another trap's
state machine.

Jet requires the preserved P-Wing, automatic map entry id `15`, object set `10`,
and entry `(0,320)`. Gameplay evidence identifies hazard-aware pause/advance
pacing rather than continuous forward input. Flying Boom Boom must transition
from active object `76` to defeated object `74` while Mario is alive, followed
by the game-owned return-map flag. The final contract traverses the normal dark
pipe tunnel and stops at World 8 map page 2 cursor `(64,112)`, with World 8-1
accessible and unentered.

## World 8-1 and World 8-2 composed contract

`world_8_8_2` declares `world_8_hand_traps_jet` as its unchanged prefix and
adds exactly two ordered objective segments: `world_8_1_clear` and
`world_8_2_clear`. Resolution is exactly 23 segments and zero bridges; the
15-, 16-, 17-, and 21-segment goals remain unchanged.

The typed goal-card observer catalog keeps a separate ordered state machine for
each stage. World 8-1 requires object set `1`, entry id `0`, entry `(0,384)`,
representative dark-level gameplay, object `65` state `4`, the card transition
`2,0,0 -> 2,3,0`, genuine map return, and 180 stable frames at `(64,112)`.
Only then may World 8-2 enter as object set `14`, entry id `0`, at `(0,112)`.
Its distinct object `65` state `4` advances `2,3,0 -> 2,3,1`; the game then
converts the completed three-card set to `0,0,0` during map return.

The final proof is normal Right input from the 8-2 return cursor `(32,144)` to
the Fortress node `(64,144)`, followed by 180 stable map frames with no A input
and no Fortress stage entry.

## Bowser's Castle and ending composed contract

`world_8_finish_game` declares the accepted 25-segment
`world_8_super_tanks` goal as its unchanged prefix and appends only
`world_8_bowser_castle_finish`. Resolution is exactly 26 ordered segments and
zero bridges; every earlier cumulative endpoint remains independently
selectable.

The final observer is ordered and fail-closed: exact Castle entry,
representative hazard and door traversal, boss-room entry, live Bowser, the
game's Bowser fight-state transition from active combat to falling through the
broken floor while Mario retains his life, Princess rescue, credits start, all
eight zero-based credits scenes 0 through 7 followed by the wrap to 0, and 300
consecutive frames at the game-owned final `THE END` state. Bowser
disappearance, coordinates, elapsed
time, or a Lua declaration cannot independently advance the contract.

Discovery may resume ignored local checkpoints but is review-only and cannot
satisfy this product goal. Product runs prohibit savestates, search, bridges,
RAM mutation, resumed execution, and throttled evidence.

```bash
.venv/bin/python -m smb3_agent goal validate \
  data/goals/world_8_finish_game.yaml
.venv/bin/python -m smb3_agent goal status world_8_finish_game
```

This contract is accepted. The fresh smoke passed 1/1, and the authoritative
`20260821T013757.568299Z_reliability` aggregate passed 3/3 independent fresh
runs with all 26 milestones, eight focused screenshots per run, and
byte-identical logs.

## Legacy diagnostic

`data/goals/world_1_king.yaml` is `goal_type: diagnostic_route`. It retains its
own honest validation and explicit bridges. It is executable only when
explicitly selected, and its king marker remains local to that diagnostic.

## Commands

```bash
.venv/bin/python -m smb3_agent goal validate \
  data/goals/world_8_double_whistle.yaml
.venv/bin/python -m smb3_agent segment validate \
  data/segments/world_8_double_whistle.yaml \
  --goal world_8_double_whistle
.venv/bin/python -m smb3_agent goal status world_8_double_whistle
.venv/bin/python -m smb3_agent goal validate \
  data/goals/world_8_big_tanks.yaml
.venv/bin/python -m smb3_agent goal status world_8_big_tanks
.venv/bin/python -m smb3_agent goal validate \
  data/goals/world_8_battleships.yaml
.venv/bin/python -m smb3_agent goal status world_8_battleships
.venv/bin/python -m smb3_agent goal validate \
  data/goals/world_8_hand_traps_jet.yaml
.venv/bin/python -m smb3_agent goal status world_8_hand_traps_jet
.venv/bin/python -m smb3_agent goal validate \
  data/goals/world_8_8_2.yaml
.venv/bin/python -m smb3_agent goal status world_8_8_2
```

`goal run world_8_double_whistle` executes the product preset directly and
never routes to `world_1_king`. The Big Tanks and Battleships presets are
selected only by their separate goals. The Hand-Traps-and-Jet preset follows
the same no-fallback rule, as does the dedicated `fceux_world_8_8_2` preset.
