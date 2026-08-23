# Game Companion Lab — Mario

Game Companion Lab is the local evidence-first Mario route review surface. It
is the current engineering view beneath the planned player-facing companion
session. It answers:

- Where is Mario in the selected route?
- What is proved, bridged, planned, or failing?
- What should be observed or repaired next?

It is not a generic operations dashboard. The CLI, goal contract, catalog, and
artifact schemas remain the source of truth.

## Goal selection

The default selected goal is `world_8_double_whistle`. Route Lab loads its
declared segment catalog and renders exactly this contract order:

1. Fresh Start
2. 1-1
3. 1-2
4. 1-3 whistle
5. Fortress whistle
6. 1-5
7. 1-6
8. Airship / King
9. World 2 Map with both whistles
10. First Whistle (World 2)
11. Warp Zone 5 / 6 / 7
12. Second Whistle (Warp Zone)
13. Warp Zone World 8
14. World 8 Pipe
15. World 8 Map

World 1-4 is not rendered because it is not in the active contract. World 7 is
not a route destination; it appears only in the visible Warp Zone tier label.

The goal switcher exposes `world_8_big_tanks` as a distinct review surface.
That view renders the same 15-row prefix plus row 16, World 8 Big Tanks. It
does not change the default selection, modify the Rank 27 goal, or include a
later World 8 stage. A URL may select it directly with
`/?goal=world_8_big_tanks`.

The switcher also exposes `world_8_battleships`. That view composes the same
16-row Big Tanks route with row 17, World 8-Battleships, and can be selected
directly with `/?goal=world_8_battleships`. It contains no Hand Trap or later
World 8 row.

The `world_8_hand_traps_jet` view composes the unchanged 17-row Battleships
route with four rows in exact order: right Hand Trap, center Hand Trap, left
Hand Trap, and World 8-Jet. It renders exactly 21 locations and does not include
World 8-1 gameplay or any later level.

The `world_8_8_2` view preserves all 21 earlier rows and appends World 8-1 and
World 8-2. It renders exactly 23 locations and stops at Fortress access; the
Fortress is not a row because its gameplay is outside this goal.

The `world_8_super_tanks` view extends that route through Fortress and Super
Tanks to the accepted Bowser's Castle map boundary. The
`world_8_finish_game` view preserves all 25 rows and appends exactly one final
row, World 8-Bowser's Castle and Ending. Its URL selection is
`/?goal=world_8_finish_game`; selecting it changes only the review surface, not
the default goal or acceptance state.

Goal ids, ordering, labels, and subtitles come from the resolved product
contracts under `data/goals/`. Route Lab does not maintain an independent goal
registry. Product-contract and reliability-profile drift is rejected by the
ROM-free test suite. See [Single sources of truth](ssot.md).

Each route row uses player-facing language and displays its role:

- `goal milestone` for owner-required outcomes;
- `required path` for game traversal needed to reach the next milestone;
- truthful state such as Learned, Needs Validation, or Planned.

Planned steps never appear as learned or solved.

## Layout

The established layout remains:

- top run strip;
- Route index;
- Evidence viewer;
- Help & Learn panel;
- Latest Attempt, Active Problems, and Observation History.

The route correction changes content and source-of-truth plumbing, not the page
structure.

## Primary action

`Run World 8 Route` remains the only strong primary button and retains the
default Rank 27 behavior. The goal switcher is a route/evidence review control;
use the goal-specific CLI reliability command to execute Big Tanks,
Battleships, Hand Traps, or Jet. None of these surfaces runs the World 1 king
diagnostic.

Unit tests, phase gate, HTML render check, refresh, note, lifecycle, and Codex
task actions remain secondary or quiet controls.

For the selected actionable issue, the Fix Issue panel also shows its task
packet and normalized route patch: lifecycle state, changed files, base commit,
review record, exact unified diff, internally selected profile, validation
result, promotion blockers, and rollback availability. Import, review, preview,
prepare, validate, compare, promote, and rollback remain quiet controls.
Promote and rollback require typing the exact patch id. These forms call the
same functions and write the same artifacts as `lab patch` CLI commands.

## Evidence behavior

The selected route row drives the evidence and teaching panels. Evidence may
come from a screenshot, contact sheet, log, state trace, note, issue, or
proposal. Assisted evidence must remain labeled; a bridge screenshot cannot be
presented as normal gameplay proof.

The default live boundary remains the genuine World 8 map. In the Big Tanks
view, all 16 rows have normal-gameplay evidence; the extension has three fresh
byte-identical authoritative runs plus a separate five-frame review contact
sheet.

In the Battleships view, all 17 rows have normal-gameplay evidence. The final
row links to three fresh authoritative runs with five focused screenshots each
and the separate five-frame review contact sheet.

In the Hand-Traps-and-Jet view, all 21 rows have normal-gameplay evidence. The
four new rows link to a 3/3 authoritative aggregate with 17 focused images per
run and a separate 17-frame review contact sheet.

In the finish-game view, the final row requires eight focused evidence roles:
accepted Super Tanks boundary, Castle entry, representative Castle gameplay,
Bowser encounter, game-owned Bowser defeat, Princess rescue, credits, and the
stable final screen. Route Lab remains a review surface and does not itself
grant acceptance; Slice 5 is accepted by the passing authoritative 3/3 report
and its independently retained live evidence.

## Route roles and observations

Notes and issues continue to use human locations while retaining segment ids in
artifacts. New active mappings include:

- `world_2_map_arrival_with_two_whistles` -> World 2 Map
- `world_2_first_whistle_use` -> First Whistle (World 2)
- `warp_zone_5_6_7_tier` -> Warp Zone 5 / 6 / 7
- `warp_zone_second_whistle_use` -> Second Whistle (Warp Zone)
- `warp_zone_world_8_tier` -> Warp Zone World 8
- `world_8_pipe_entry` -> World 8 Pipe
- `world_8_map_arrival` -> World 8 Map
- `world_8_big_tanks_clear` -> World 8 Big Tanks
- `world_8_battleships_clear` -> World 8-Battleships
- `world_8_hand_trap_right_clear` -> World 8 Right Hand Trap
- `world_8_hand_trap_center_clear` -> World 8 Center Hand Trap
- `world_8_hand_trap_left_clear` -> World 8 Left Hand Trap
- `world_8_jet_clear` -> World 8-Jet
- `world_8_1_clear` -> World 8-1
- `world_8_2_clear` -> World 8-2
- `world_8_fortress_clear` -> World 8-Fortress
- `world_8_super_tanks_clear` -> World 8-Super Tanks
- `world_8_bowser_castle_finish` -> World 8-Bowser's Castle and Ending

## Commands

Render once:

```bash
python -m smb3_agent lab ui-render \
  --view lab \
  --output artifacts/ui/world_8_double_whistle.html
```

Serve locally:

```bash
python -m smb3_agent lab ui --host 127.0.0.1 --port 8765
```

The player-facing Game Companion session is at `/`; this engineering surface
is at `/lab`. The navigation links preserve that separation. Omitting `--view
lab` from `ui-render` renders the player session.

The server logs completed requests, expected request failures, subprocess
timeouts, and unexpected handler tracebacks. Browser responses distinguish
400 validation failures, 403 authorization failures, 404 missing records, 409
action conflicts, 413 oversized artifacts, 415 unsupported forms, 504 action
timeouts, and generic 500 server failures. Form bodies are bounded at 65,536
bytes and require the supported media type and valid UTF-8. Non-loopback bind
addresses and `Host` values are refused; POST forms require the server's CSRF
token. Operational details are in [Error handling and operations](error-handling.md),
and the complete trust model is in [Security model and hardening](security.md).

Inspect the contract independently:

```bash
python -m smb3_agent goal status world_8_double_whistle
python -m smb3_agent goal status world_8_big_tanks
python -m smb3_agent goal status world_8_battleships
python -m smb3_agent goal status world_8_hand_traps_jet
python -m smb3_agent goal status world_8_8_2
python -m smb3_agent goal status world_8_super_tanks
python -m smb3_agent goal status world_8_finish_game
```

## Visual contract

Keep the current warm off-white page, white panels, dark text, neutral borders,
blue selection, and restrained red/green/amber state treatments. Preserve the
semantic render hooks:

- `primary-button`
- `secondary-button`
- `segmented-control`
- `segment-active`
- `route-item-selected`
- `status-failed`
- `status-learned`
- `status-validation`

Tests assert these hooks and the exact contract-derived route, not color values.

## Diagnostic route

The bridge-assisted `world_1_king` route remains explicitly selectable from
the CLI under its diagnostic name. It is intentionally not the default Route
Lab route and its king marker is not a World 8 success state.
