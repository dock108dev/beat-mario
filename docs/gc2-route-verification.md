# World 1-1 app-delivered route instructions — October 4, 2026

## Delivered behavior

The ordinary `/mario` app turns compatible observed failures into a supported next-attempt instruction, includes it in Review/Start and sends `stairs_tactic=land_then_cross_v1` and, after an observed post-stairs pipe death, `pipe_tactic=land_on_pipe_then_cross_v1` in the emulator's immutable `initial.request`. The existing `coin_balanced` approach remains the plan path. The controller changes execution because it receives these instruction fields. Accepted route registry/profile evidence is unchanged.

The supported player instruction “At the stairs land on the left top before jumping across the gap” is taught through app chat, retained with original wording and cartridge identity, and incorporated in the next approved attempt. Idle coaching revises the pending plan; active coaching changes future attempts only. Saved player wording and failure-derived pipe continuation merge without discarding the failure provenance. This is a finite tactic vocabulary and controller capability, not arbitrary English-to-game execution or independent training.

The stair controller stages a landing on the left top, counter-steers airborne momentum to zero, releases jump and launches across. The pipe controller stages on the first pipe, releases jump, takes a short run-up on its top and jumps over the next pipe. Each stage has a 240-frame stall bound, inside the existing per-attempt three-minute cap and ten-minute approval. Immediate reclaim, freshness, session identity, death and finite-budget owners are preserved. No save-state/game-memory writes, player demonstration or owner walkthrough were used.

## Real gameplay and retained failures

All gameplay was launched and reviewed through ordinary source `/mario` on task-owned loopback port 8875 and the recognized local cartridge. Normal 1× gameplay used ordinary emulator joypad input. Earlier recordings, outcomes, packages and game files were preserved.

| Session | Applied change and observed result | Finish / handback |
| --- | --- | --- |
| `20261004T043612807136Z` | Preliminary separate running-jump candidate; 2 coins, death at x=1652 | No finish; native neutral acknowledgment |
| `20261004T044455957841Z` | App-delivered landing instruction; neutral direction retained air momentum; 2 coins, x=1643, stairs stall | No finish; native neutral acknowledgment |
| `20261004T044709671254Z` | Counter-steering landed beyond stairs; 2 coins, death at x=1855 near next pipe | No finish; native neutral acknowledgment |
| `20261004T045057021354Z` | App-delivered first-pipe staging; jump still collided with next plant; 2 coins, x=1862, pipe stall | No finish; native neutral acknowledgment |
| `20261004T045351399757Z` | App-delivered stairs instruction plus failure-derived pipe run-up; 2 coins, x=2848, game-owned COURSE CLEAR/card and World 1-1 exit | Completed stop frame 2991; neutral acknowledgment frame 2992 |
| `20261004T045537490216Z` | Explicit Try again reused remembered instructions within the same two-attempt approval; same 2 coins, x=2848 and exit | Completed stop frame 2991; neutral acknowledgment frame 2992 |
| `20261004T045751030401Z` | Separate reviewed single attempt; paused frame 2031 at x=1852 during pipe crossing; exact `STOP RIGHT NOW WAIT` | Reclaimed frame 2032; native neutral acknowledgment frame 2033; retry scope cleared |

The preliminary candidate was superseded by instructions carried through the app. Its failure stays archived under its original `coin_stairs` path; current review cannot select that path. The first preliminary candidate was not source-sealed and is failure evidence only. Staging, counter-steering, pipe and final candidates have separate retained source maps and source snapshots; no earlier result is relabeled as final-source proof.

Both final-source finishes followed real controller application and the game-owned exit receipt; a visual game image says COURSE CLEAR and shows the received card. A completed instruction or distance alone does not establish a finish. A rejected third retry after the two-attempt scope started no additional emulator input. Reopening source servers restored original instruction wording and compatible discoveries, while plans/retry authority were empty. Final shutdown/reopening inspection is retained in the closeout evidence: no plan or retry scope, idle runtime, stored instruction file preserved, task-owned servers/browser closed and zero remaining FCEUX processes.

## Exact candidate and checks

Repository HEAD: `5d4ed6280c65657c0c3184660ce514c9eef0a477`; the incoming working tree already contained coaching, coin and deferred demonstration work and remains uncommitted. Final source-map SHA-256: `ef9f30dd88746ab9265a8e290213d42551686a4346c5296bd376eb1d2622262b`. The source map covers Python adapter/runtime source and Lua scripts; documentation/tests have their own final check record. No commit, push, package or release was performed.

Evidence root: `artifacts/gc2-route/20261004/`. `final-source-identity.json` and `final-source/` bind the successful controller/app candidate; `observed-finish.json`, `repeat-finish-and-budget-refusal.json`, `urgent-stop.json` retain full app outcomes. The native sessions above retain actual initial instructions, per-frame observations, effective-input audits, progress/exit receipts, screenshots and neutral acknowledgments. `observed-finish-app.png`, `urgent-handback-app.png` and the final finish game's `state-samples-png/002785_agent_tick.png` retain visible evidence.

Final canonical gate: **1,401 tests passed**, plus lint, whitespace, security/game-asset scan, generated-file guard, objective/segment contracts and UI renders (`closeout-canonical.log`). **123 focused tests passed** for coin accounting, guidance-to-wire/next attempt/reopening, simulated actual Lua stair/pipe staging, stalls, opening coaching, demonstration preservation and existing bounded Mario runtime (`runup-focused.log`). The canonical gate was rerun after the final source changes. Fixture/Lua-host tests establish behavior under simulated state; live sessions separately establish the observed gameplay.

## Limits and next handoff

Two consecutive final-source finishes qualify this World 1-1 disposable-session loop only. They do not establish broad reliability, arbitrary player states, later-level learning, fastest play, owner acceptance or a current packaged app. Collected coins remain **2 per finished attempt**, never 4 across attempts. Hidden/brick, airborne, bonus-room and the complete individual coin universe remain unknown. The missed opportunity lower bound was zero for these measured surface bands; it does not establish zero missed coins.

The current instruction vocabulary is limited to this stairs tactic, the observed-failure pipe continuation and opening jump timing. A remaining wording limitation is that the exhausted retry error still refers to an opening-practice plan; a fresh reviewed route plan also renews the scope. Recording/demonstration gameplay qualification remains deferred to a later beta, tentatively beta v2, and is not a gate here.

Route traversal pickup and the subsequent [real sky hidden 1UP flight/reward qualification](gc2-flight-verification.md) are complete for their supported source cases. GC3 Stardew watering is the current next development action. Full coin coverage and broader Mario tactics remain explicit limits; no owner recording is required.
