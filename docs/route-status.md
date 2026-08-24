# Route Status

Last updated: 2026-08-11.

## Default goal

`world_8_double_whistle` is the product source of truth. It ends only on a
genuine World 8 map observation. The owner corrected the route boundary during
live investigation: Mario must clear the final World 1 castle/airship, arrive
safely in World 2 with both whistles, and use the first whistle from World 2.

The default goal is `executable`. Rank 27 launched five independent fresh FCEUX
processes; all five completed all 15 route steps, reported
`metrics_passed=true`, and ended at `post_probe_world_8_map_arrival`. Their
structured logs are byte-identical. A separate throttled playback also passed
and produced review images, ticks, and a contact sheet, but is explicitly
non-promotable. The legacy `world_1_king` gate remains a separate diagnostic.

## Rank 28 separate goal

`world_8_big_tanks` is an executable product goal separate from the default.
It declares `world_8_double_whistle` as its prefix, reuses all 15 accepted
arrival segments without copying them, and adds exactly one segment:
`world_8_big_tanks_clear`.

From the accepted World 8 map at cursor `(32,80)`, normal down/right/A input
reached Big Tanks. The promoted controller traverses the autoscrolling tanks,
enters the end pipe, defeats the Boomerang Brother, avoids the remaining
projectile, and collects the chest. Success requires the additional Super Star
inventory item and the game's return-to-map flag, followed by a stable World 8
map observation at cursor `(64,112)`. The goal stops there, before another
World 8 stage.

The authoritative command passed 3/3:

```bash
.venv/bin/python -m smb3_agent reliability run \
  --goal world_8_big_tanks \
  --game-file "$SMB3_GAME_FILE"
```

Accepted aggregate:

```text
artifacts/reliability/world_8_big_tanks/20260810T190157.201466Z_reliability/
```

All three fresh processes completed the 16 ordered events, reported
`metrics_passed=true`, retained all five focused screenshots, and produced the
same structured-log SHA-256:

```text
38ee2fb807d67fabfc4be08a2eef447d3631510ba2ab8e3386a32068a538ffa2
```

The separate review-only run passed with a `0.0001`-second throttle:

```text
artifacts/review/world_8_big_tanks/20260810T212112.984218Z_watchable/
```

Its five-frame contact sheet covers map arrival, stage entry, real tank
gameplay, chest/clear, and the post-clear map. Its 633-line state/tick trace and
contact sheet are non-promotable and do not count toward the 3/3 gate.

After Rank 28 changes, the unchanged default reliability profile passed 5/5
again at:

```text
artifacts/reliability/world_8_double_whistle/20260810T212451.471392Z_reliability/
```

## World 8-Battleships cumulative goal

`world_8_battleships` declares `world_8_big_tanks` as its prefix and adds only
`world_8_battleships_clear`. Resolution contains exactly 17 normal-gameplay
segments and zero bridges; the 15-segment default and 16-segment Big Tanks
contracts are unchanged.

From the accepted Big Tanks post-clear cursor `(64,112)`, the route normally
consumes the retained P-Wing, moves right twice, and accepts the game's
automatic entry at node `(128,112)`. The observed Battleships identity is
`world_number=7`, `object_set=10`, `map_enter_via_id=13`, with original entry
state `x=0`, `y=320`, `air=0`. The controller traverses the three-ship
autoscroller, enters the normal end pipe, and fights Boom Boom.

Boss proof does not rely on disappearance or a fixed hit count. Active object
id `75` is the live Boom Boom. The game-owned defeated transition removes id
`75` and activates id `74`; only then may return flag `0x14=1` prove the clear,
with Mario alive and lives unchanged. The returned map stabilizes for 180 frames
at cursor `(128,112)`, reports `hand_trap_region_accessible=1` and
`hand_trap_entered=0`, and stops before another stage.

The observer assignments used by this extension are documented in the runner:

- `0x727`: zero-based world number; `0x70A`: object set.
- `0x79`/`0x75`: map cursor coordinates; `0x1E`: map-entry object id.
- `0x90` + `0x75*256` and `0xA2` + `0x87*256`: Mario world coordinates;
  `0xD8`: Mario air state.
- `0x736`: lives; `0xF1`: player death state; `0x14`: return-to-map flag.
- `0x660+slot`: active object; `0x670+slot`: object id; `0xD8+slot`: object
  lifecycle state.

The authoritative command passed 3/3 with `success_rate=1.0`,
`overall_pass=true`, 17/17 ordered events, five focused screenshots per run,
and byte-identical structured logs:

```text
artifacts/reliability/world_8_battleships/20260810T225906.177318Z_reliability/
```

All three logs have SHA-256:

```text
9b278b158415144ceb188f13773ac457f6f4ada15493a0758e3ac21172b8ec2c
```

The separate review-only run passed at the independently validated
`0.0001`-second throttle and retained a five-frame contact sheet plus a 668-line
tick trace:

```text
artifacts/review/world_8_battleships/20260810T224805.096938Z_watchable/
```

After the shared runner, observer, catalog, and harness changes, the unchanged
Rank 27 route passed 5/5 at World 8 arrival and the unchanged Rank 28 route
passed 3/3 at the Big Tanks post-clear map:

```text
artifacts/reliability/world_8_double_whistle/20260810T230007.756761Z_reliability/
artifacts/reliability/world_8_big_tanks/20260810T230122.959142Z_reliability/
```

## World 8 Hand Traps and Jet cumulative goal

`world_8_hand_traps_jet` composes the unchanged 17-segment Battleships goal
with four ordered normal-gameplay segments: right Hand Trap, center Hand Trap,
left Hand Trap, and World 8-Jet. The result is exactly 21 segments and zero
bridges; all earlier goal endpoints remain separate.

The cumulative route preserves the P-Wing through Battleships, consumes a Star
from two to one, crosses the exposed first ship, enters the reddish water at
`x=900`, swims beneath the fleet, waits behind the final stern, and surfaces for
the normal pipe. The saved P-Wing is then consumed immediately before Jet.

The trap identities are distinct:

- Right: map `(160,112)`, object set `11`, entry `(24,320)`, Brother ids
  `-121,-127,-126,-122`; Sledge is defeated before Mario centers beneath the
  orange ceiling tube and jumps while holding Up.
- Center: map `(128,112)`, object set `11`, entry `(24,368)`, lava platforms
  and Podoboos; Mario centers under the tube before the Up exit.
- Left: map `(96,112)`, object set `11`, entry `(24,320)`, broken bridge and
  jumping Cheep-Cheeps; the controller pauses on observed footing for safe
  windows before centering under the exit tube.

Each trap observes reward object `82`, item id `3`, a Super Leaf inventory
transition from zero to one, a normal map return, 180 stable frames, unchanged
lives, and no premature next stage.

Jet enters automatically at node `(64,80)` with entry id `15`, object set `10`,
and original state `(0,320,air=0)`. Its controller holds position or neutral
input around Rocket Engine fire and newly exposed footing instead of moving
continually forward. The normal final pipe leads to flying Boom Boom; success
requires active object `76` to become defeated object `74` while Mario remains
alive, followed by the game-owned map transition.

The observed post-Jet path is left from `(64,80)` to the pipe at `(32,80)`, A
into the dark tunnel (`object_set=14`), right through the tunnel and Down from
the centered exit pipe, then right and down on map page 2. The accepted stop is
`world_number=7`, `object_set=0`, `map_page=2`, cursor `(64,112)`, with World
8-1 accessible and not entered.

The final authoritative aggregate passed 3/3, all 21 milestones, exactly 17
focused screenshots per run, `success_rate=1.0`, `overall_pass=true`, and
byte-identical log SHA-256
`6b6f66ca679ca63bba97a76e3da3326f5f643d881880b24203ccb97de67ca8fa`:

```text
artifacts/reliability/world_8_hand_traps_jet/20260811T062336.029178Z_reliability/
```

The separate `0.001`-second review passed with 17 focused frames, a 795-line
tick trace, and a contact sheet. It is review-only and non-promotable:

```text
artifacts/review/world_8_hand_traps_jet/20260811T060954.667404Z_watchable/
```

Final regressions passed at:

```text
artifacts/reliability/world_8_double_whistle/20260811T061710.427413Z_reliability/  # 5/5
artifacts/reliability/world_8_big_tanks/20260811T061936.683562Z_reliability/      # 3/3
artifacts/reliability/world_8_battleships/20260811T062230.086277Z_reliability/   # 3/3
```

## World 8-1 and World 8-2 cumulative goal

`world_8_8_2` preserves the accepted 21-segment Hand-Traps-and-Jet prefix and
adds two ordered normal-gameplay segments. It resolves to exactly 23 segments
and zero bridges; the 15-, 16-, 17-, and 21-segment endpoints remain separate.

World 8-1 enters normally at object set `1`, entry id `0`, `(0,384,air=0)`.
The route uses the normally awarded Super Leaf, traverses Bill Blasters,
Bullet Bills, plants, Koopas, pits, and the Boo, and proves goal object `65`
state `4` at `(2680,308)`. Its card inventory changes `2,0,0 -> 2,3,0`; the
game returns to map page 2 cursor `(64,112)` and remains stable for 180 frames
before 8-2 entry.

World 8-2 is distinct: object set `14`, entry id `0`, `(0,112,air=0)`. Mario
walks into the first sandfall, uses the chamber's right pipe and the normal
bonus-room exit, suppressing the Angry Sun without a map bypass. The route then
handles the remaining Venus Fire Traps and slopes, lands on the final chasm's
jump block at `(3035,368)`, and proves its own object `65` state `4` at
`(3709,329)`. The card set changes `2,3,0 -> 2,3,1`, then the game converts the
completed set to `0,0,0` on map return.

After 180 stable frames at the 8-2 return cursor `(32,144)`, normal Right input
reaches the Fortress node `(64,144)`. Another 180 stable frames prove access;
no A input occurs and the Fortress remains unentered.

The authoritative aggregate passed 3/3 with all 23 milestones, exactly nine
focused screenshots per run, `success_rate=1.0`, `overall_pass=true`, and
byte-identical log SHA-256
`f6d4ff8ba659b46496b9ed2e20413903073d6da9bab71ee2abf8388af91bafcb`:

```text
artifacts/reliability/world_8_8_2/20260811T221626.293001Z_reliability/
```

The independent `0.001`-second review passed with nine focused frames, an
823-line tick trace, and a contact sheet. It is review-only and non-promotable:

```text
artifacts/review/world_8_8_2/20260811T221806.076219Z_watchable/
```

Final regressions passed at:

```text
artifacts/reliability/world_8_double_whistle/20260811T222531.669742Z_reliability/  # 5/5
artifacts/reliability/world_8_big_tanks/20260811T222645.167671Z_reliability/      # 3/3
artifacts/reliability/world_8_battleships/20260811T222747.028266Z_reliability/   # 3/3
artifacts/reliability/world_8_hand_traps_jet/20260811T222848.457322Z_reliability/ # 3/3
```

## Rank 27 reliability evidence

The authoritative command passed 5/5:

```bash
.venv/bin/python -m smb3_agent reliability run --game-file "$SMB3_GAME_FILE"
```

Accepted aggregate:

```text
artifacts/reliability/world_8_double_whistle/20260810T160716.743170Z_reliability/
```

Every `run_01` through `run_05` record shows a new process, one attempt, fresh
game, clean product environment, zero throttle, all 15 ordered milestones,
`metrics_passed=true`, and final `world_number=7`, `object_set=0`. All FCEUX
processes exited zero. The five route-log SHA-256 values are identical:

```text
610c95128c06207d6a04bd7d41f4f1e2e4e59cd6b8d807570e4a85e4a0adb8df
```

The separate watchable command passed:

```bash
.venv/bin/python -m smb3_agent reliability watch --game-file "$SMB3_GAME_FILE"
```

Review-only artifacts:

```text
artifacts/review/world_8_double_whistle/20260810T160828.873705Z_watchable/
```

The report is labeled `review_only`, `promotable=false`, and
`counts_toward_reliability=false`. It retained 1,398 source/converted review
images, a 621-line state/tick trace, and `review/contact_sheet.png`.

Two fail-closed classifications were observed before final acceptance. A broken
local configuration was classified `preflight` with zero executions. The first
live batch recorded 4/5 because FCEUX 2.6.6 received SIGSEGV during raw
`os.exit()` Qt teardown after run 5 had already written a complete,
byte-identical passing route log. That process remained failed. The route script
was changed to FCEUX's supported `emu.exit()` API, covered by a non-live test,
and the complete five-run gate was rerun successfully. No gameplay,
observer/contract, prohibited-tactic, timeout, or artifact-integrity failure was
observed in the accepted batch.

## Ordered route

| Order | Route step | Role | Active execution | Current capability |
| ---: | --- | --- | --- | --- |
| 1 | Fresh start to 1-1 | game prerequisite | normal gameplay | solved |
| 2 | 1-1 | game prerequisite | normal gameplay | solved |
| 3 | 1-2 | game prerequisite | normal gameplay | solved |
| 4 | Collect 1-3 whistle | objective milestone | normal gameplay | solved in three fresh accepted replays |
| 5 | Collect Fortress whistle | objective milestone | normal gameplay | solved in three fresh accepted replays |
| 6 | 1-5 | game prerequisite | normal gameplay | solved in three fresh accepted replays |
| 7 | 1-6 | game prerequisite | normal gameplay | solved in three fresh accepted replays |
| 8 | Airship / King | game prerequisite | normal gameplay | solved in three fresh accepted replays |
| 9 | World 2 map with two whistles | objective milestone | normal gameplay | solved; both whistles and `item_2=9` observed |
| 10 | First whistle from World 2 | objective milestone | normal gameplay | solved after settled World 2 spawn |
| 11 | Warp Zone 5/6/7 tier | objective milestone | normal gameplay | solved and observed before second whistle |
| 12 | Second whistle from Warp Zone | objective milestone | normal gameplay | solved; whistle count fell to zero |
| 13 | Warp Zone World 8 tier | objective milestone | normal gameplay | solved and independently observed |
| 14 | World 8 pipe | objective milestone | normal gameplay | solved via right then A from the World 8 tier |
| 15 | World 8 map arrival | objective milestone | normal gameplay | solved; `world_number=7`, `object_set=0` |
| 16 | World 8 Big Tanks clear | objective milestone in separate goal | normal gameplay | solved 3/3; stable post-clear map return |
| 17 | World 8-Battleships clear | objective milestone in cumulative goal | normal gameplay | solved 3/3; stable map before Hand Trap |
| 18 | World 8 right Hand Trap clear | objective milestone in cumulative goal | normal gameplay | solved 3/3; Brothers defeated, Super Leaf awarded |
| 19 | World 8 center Hand Trap clear | objective milestone in cumulative goal | normal gameplay | solved 3/3; lava/Podoboo traversal, Super Leaf awarded |
| 20 | World 8 left Hand Trap clear | objective milestone in cumulative goal | normal gameplay | solved 3/3; paused broken-bridge traversal, Super Leaf awarded |
| 21 | World 8-Jet clear | objective milestone in cumulative goal | normal gameplay | solved 3/3; flying Boom Boom defeated, 8-1 accessible |
| 22 | World 8-1 clear | objective milestone in cumulative goal | normal gameplay | solved 3/3; distinct goal object 65 state 4, 8-2 accessible |
| 23 | World 8-2 clear | objective milestone in cumulative goal | normal gameplay | solved 3/3; distinct goal object 65 state 4, Fortress accessible and unentered |
| 24 | World 8-Fortress clear | objective milestone in cumulative goal | normal gameplay | accepted 3/3; switch, Boom Boom, and Magic Ball proved |
| 25 | World 8-Super Tanks clear | objective milestone in cumulative goal | normal gameplay | accepted 3/3; Bowser's Castle accessible and unentered |
| 26 | Bowser's Castle through stable ending | objective milestone in final cumulative goal | normal gameplay | accepted 3/3; Bowser defeated, Princess rescued, eight credits scenes completed, stable ending proved |

Rows 18-21 belong to `world_8_hand_traps_jet`; rows 22-23 are added only by
`world_8_8_2`. Rows 24-25 belong to the accepted `world_8_super_tanks`
continuation. Row 26 is added only by `world_8_finish_game`; its first 25 rows
are unchanged. The default contract still ends at row 15. World 1-4 is absent.
World 7 is not entered; it is only one of the labels on the expected first Warp
Zone tier.

## Fresh live investigation

The bounded FCEUX investigation wrote ignored artifacts under:

```text
artifacts/fceux/world_8_double_whistle_topology/
artifacts/fceux/world_8_double_whistle_rank10/
```

Observed facts:

- A fresh run collected the 1-3 whistle (`item_0=12`).
- The Fortress secret-room route collected the second whistle without the
  whistle-inventory bridge (`item_0=12`, `item_1=12`).
- The game returned to the World 1 map with both whistles visible in inventory.
- A fresh diagnostic continued through 1-5 with both whistles.
- A fresh power-on, single-attempt playback traversed 1-6 without discovery,
  savestate loads, position or inventory mutation, or bridge flags.
- The 1-6 end card changed its internal state from `0` to `4` while Mario was
  Raccoon (`form_before_clear=3`), followed by the normal course transition and
  an independently observed World 1 map return (`object_set=0`).
- Both whistles remained in inventory at the accepted 1-6 boundary
  (`item_0=12`, `item_1=12`).
- Normal `up,A` input from the post-1-6 node entered the roaming Hammer Bro
  battle with Raccoon form and both whistles. The observer now identifies that
  encounter instead of sending it to the castle controller.
- The accepted controller uses the overhead platform as a shield, brakes to
  `x=120`, and tail-attacks when the Bro jumps within 48 pixels. It requires 12
  consecutive absent-enemy frames while Mario is alive and still Raccoon
  before classifying the battle as won.
- Three independent fresh, no-savestate, no-search replays produced
  byte-identical logs and the same battle event frames: encounter `24469`, tail
  attack `24620`, enemy-removal proof `24803`, and normal map return `25196`.
- All three accepted replays retained `item_0=12` and `item_1=12`; collecting the
  Bro's chest added `item_2=9`. No savestate, position/inventory mutation, or
  bridge evidence was accepted.
- The promoted controller traversed the real Airship, entered its boss pipe
  with normal down input, defeated the Koopaling, and observed the normal King
  room transition without a bridge.
- World 2 was observed as `world_number=1`, `object_set=0` with both whistles
  (`item_0=12`, `item_1=12`) and the Hammer Bro reward (`item_2=9`).
- After Mario's World 2 spawn settled, B then A consumed the first whistle and
  produced the visible 5/6/7 tier at cursor `(64,112)`.
- The second whistle was used from that tier before any pipe entry, producing
  the World 8 tier at cursor `(128,144)`. Moving right to `(160,144)` and
  pressing A produced a genuine World 8 map at `world_number=7`.

Accepted Gate 1 evidence is under:

```text
artifacts/fceux/world_8_double_whistle_rank10/gate1_1_6_fresh_playback_v3/
```

Accepted roaming Hammer Bro evidence is under:

```text
artifacts/fceux/world_8_double_whistle_rank10/gate2_hammer_bro_fresh_playback_v1/
artifacts/fceux/world_8_double_whistle_rank10/gate2_hammer_bro_fresh_playback_v2/
artifacts/fceux/world_8_double_whistle_rank10/gate2_hammer_bro_fresh_playback_v3/
```

Accepted end-to-end product evidence is under:

```text
artifacts/fceux/world_8_double_whistle_rank10/gate4_world8_fresh_playback_v1/
artifacts/fceux/world_8_double_whistle_rank10/gate4_world8_fresh_playback_v2/
artifacts/fceux/world_8_double_whistle_rank10/gate4_world8_fresh_playback_v3/
artifacts/goals/world_8_double_whistle/final_validation/
```

Before the owner's correction, a probe tested whistle use from World 1. Those
artifacts are retained as rejected-hypothesis evidence only. They are not part
of the active route and cannot support active-goal success.

## Proof levels

- Contract/test proof: active goal, catalog, CLI status, review mapping, Route
  Lab order, and regression tests agree.
- Live game proof: every ordered state through genuine World 8 map arrival was
  observed in fresh, mutation-free, savestate-free playback. All three final
  logs are byte-identical.
- Assisted proof: the 1-3 return-to-map mode and later World 1 diagnostic
  bridges are explicit and cannot establish normal gameplay reliability.
- Executable route proof: available and independently passed through the
  promoted product goal runner.
- World 2-first Warp Zone and World 8 arrival proof: accepted.

## Diagnostic route

The explicit command remains:

```bash
.venv/bin/python -m smb3_agent goal status world_1_king
```

It may be used to repair World 1, but `post_probe_1_airship_success_king` is not
a World 8 success marker and is rejected by the active goal metrics.

## Current boundary

The accepted final cumulative boundary is the game-owned stable ending after
Bowser's live floor-break defeat, Princess rescue, eight ordered credits scenes
0 through 7, the credits wrap to 0, and `ending_state=1` for 300 frames. The
default Rank 27, Rank 28, Battleships, Hand-Traps-and-Jet, World-8-1/8-2, and
Super Tanks goals remain unchanged at their earlier boundaries. The
`world_8_finish_game` fresh smoke, authoritative 3/3, separate review-only
watch, canonical gate, and all cumulative regressions passed.

## Roaming placement note

The World 1 Hammer Bro's map movement is RNG-driven: the game reads a random
byte, masks it to one of four directions, and then validates that move. An
exact fresh, frame-identical emulator replay therefore repeats the same RNG
state and produced the same post-1-6 encounter in all three accepted runs.
Merely taking the same semantic map path by hand at different timing is not a
guarantee. The route remains observer-driven and only enters the battle
controller when the roaming encounter is actually present.
