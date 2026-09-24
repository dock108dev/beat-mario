# B3 Stardew integration and evidence contract

B3 owns disposable-session setup, visible perception, ordinary input and watering.
Its completion requires actual isolated-game evidence on the final source candidate.
A working browser, fixture, copied directory or parsed request cannot satisfy it.
Full beta readiness and owner acceptance are separate.

## Module ownership

- `stardew_setup.py` owns explicit source/destination selection, source classification,
  loading/persistence verification and fresh session attempts. The guarded fresh-game
  launcher pins inspected binaries, redirects XDG config/data, blocks primary paths
  and network access, and never grants input by launching. No automatic owner-save discovery.
- `stardew_input.py` owns bounded ordinary native input and neutralization, with
  foreground and process/window identity checked before input.
- `stardew_perception.py` owns supported viewport recognition. Automatic recognition
  requires a qualified pixel profile and complete coverage; unknown resources remain unknown.
- `stardew_runtime.py`, `stardew_adapter.py` and `stardew_companion.py` own volatile
  Stardew authority, observation validation, execution and watering reconciliation.
- `request_planning.py` and `stardew_planning.py` own proposals and corrections.
  A proposal is never permission to act.
- `conversation_service.py`, `conversation_ui.py` and `lab_ui.py` route the ordinary
  workspace into the Stardew runtime. Mario process/controller facts never satisfy it.
- `beta_readiness.py` and `personal-beta-v2.yaml` require classified, hashed evidence
  bound to HEAD and all active source files. `--gate-b3` cannot pass from unit evidence alone.

## Review and execution boundary

The unchanged watering contract means every initially planted crop, including
already-watered targets in the initial inventory, followed by return to the reviewed
farmhouse entrance. A visible subset is not silently treated as the whole farm.
Start binds the exact reviewed proposal, session, complete target set and observation
requirements. Any supported revision is reviewed and revalidated against remaining
work; it cannot erase completed actions or resume saved authority.

Foreground gameplay input must stop when chat receives focus. Reclaim, stale
observations, process/window changes, uncertain resources, incomplete coverage and
reset revoke execution. Neutral handback and partial outcomes are recorded even
when the task cannot complete. No promise of Mario-style play while typing applies.

## B3 evidence classes

| Requirement | Required evidence |
| --- | --- |
| Actual source/session selection and load/persistence isolation | Visible live; owner-copy preservation only for an explicitly authorized source |
| Complete initial planted set and resource recognition | Automatic visible live; calibrated fixture profiles remain development evidence |
| Actual water changes and return point | Before/after visible live observations with reconciled resources |
| Browser request/review/authorize/execute/outcome | Browser plus actual visible live execution |
| Reclaim, focus loss and neutral handback | Actual visible live, with unit concurrency coverage |
| Stale/reset/session mismatch, shortage, uncertainty | Focused unit/integration plus bounded live checks when feasible |
| Canonical gate | Unit/integration; never gameplay or owner acceptance |

## B4 interface handoff

B4 must extend `StardewPlanningAdapter.propose` with task-specific live eligibility
and supply runtime executors beside the watering executor. Harvest needs eligible
crop and inventory-delta observations; planting needs owned seed/plot/season
observations and newly planted target reconciliation; selected clearing needs
identified debris, correct tool, protected targets and acquired-item accounting.
Combined routines need ordered task dependencies and a ledger that includes newly
planted crops. Version any changed task semantics. Do not add these purposes to the
watering allowlist and call them supported. B4 live actions stay unavailable until
implemented and independently verified.
