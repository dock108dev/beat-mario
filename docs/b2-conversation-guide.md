# Mario conversation and routes

The Mario workspace supports conversation-based planning and bounded custom routes. Requests are reviewed against the current route, session and supported execution boundaries.

## Launch and controls

From the repository with the existing locked environment and configured local
game asset:

```bash
.venv/bin/python -m smb3_agent lab ui --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/mario`. Choose **Quickest**, **100% clear**, or the
existing base and **Review plan**. Every initial intent resolves through the
real `world_8_finish_game` registry. The requested objective and actual route
remain separate. There is no optimized or full-completion variant to load.
Selecting an intent does not start or reset Mario.

**Open Mario for companion play** explicitly opens a new visible FCEUX process
and holds it at the supported fresh boundary while the plan is reviewed.
**Start reviewed plan** grants fresh authority in that same process. Keep the
game window alongside the conversation. The older Observe, Tell, Show, Do,
History and Lab surfaces remain available below or through their existing links.

Examples of supported requests:

- “Take the opening hop, then stop after the opening section.”
- “Use the base path and stop at the end of World 1-1.”
- “Actually, use the default opening path.”
- “What if we take the opening hop?” — an advisory preview.
- “Cancel the pending change.”
- “Use normal speed” or “Use turbo speed.”

The opening branch can be queued before its World 1-1 entry. A late request
cannot be replayed at another point. Stop-point edits can apply at the declared
course boundary. Pending changes have revision and boundary acknowledgments.
An in-scope direct edit requests application; questions remain advisory and
material scope expansion requires **Apply change**. Completed gameplay cannot
be undone by canceling or reverting future plan steps.

**Pause**, **Resume**, **Stop**, and **Take control** stay available in the
conversation controls. Reclaim invalidates queued execution commands. Native
paused-emulator callbacks keep handback responsive. FCEUX receives scoped
controller values; chat keystrokes are never used as the control mechanism.

Playback offers **1× normal** and **Faster, uncapped**. The engine does not expose
a verified fixed 2×/4× setting through this interface. Unsupported numeric rates
are rejected. Requested and acknowledged speed, frame intervals, measured
wall-clock rate and normal-speed restoration remain recorded. Turbo speed is
machine dependent; it is not route optimization.

The local English planner supports bounded Mario and farm action families,
context, corrections, negation and selected targets. It is not general-purpose
chat or an arbitrary route generator. Unknown or materially ambiguous requests
ask for clarification. No model provider, credentials or network setup is needed.

## Routes, variants and outcomes

The implemented primitive choices are the default opening and an ordinary-input
opening hop. The explicit stop points are the opening end, World 1-1 course
clear, and the existing base route ending. The opening hop can execute only to
the opening-end stop (x >= 160); its later-level continuation is not validated.
The default path supports all three stops. The alternate does not become an
accepted full-game route. Full-route entry needs exact fresh
power-on. The retained route checks use exact fresh power-on and the resulting ordinary
World 1-1 entry. Arbitrary mid-run resumption, later-level custom paths, state loads,
teleportation and inventory mutation are unsupported.

Save a named variant to retain its stable identity, base, actual action data,
plan revision and append-only saved revisions. Reopen validates the current
adapter contract and requires fresh runtime authority. Invalid saved records
remain unavailable instead of restoring control. Saving does not promote a
candidate to accepted, fastest, or reliable status.

Attempt outcomes retain actual plans/revisions, requested objectives,
observations, game-frame timing, speed intervals, actor classification, handback
and runtime evidence references. Failed, canceled, reclaimed and partial runs
remain in history. The existing run library continues owning its compatible
level comparisons. Custom-session timing is not automatically comparable with
an accepted full route. Collectible/full-completion coverage remains unknown.

## Shared planning and adapter interfaces

| Owner | Interface and next extension |
| --- | --- |
| `request_planning.py` | `Planner.plan(text, PlanningContext)` returns a typed proposal/control/advisory/clarification. Context binds game, conversation, session, observation, selected targets and reviewed edit scope. No plan grants input authority. |
| `stardew_planning.py` | Adapter-owned targets/actions for water, harvest, plant and selected debris; unavailable-live/fixture status is explicit. Live target evidence requires qualified perception. |
| `conversation_service.py` | Connects Mario proposals, review, live revision acknowledgment, variants and outcomes. Its ordinary UI dispatch contract is documented in `b2-integration-contract.md`. Extend through a Stardew-owned runtime adapter; do not reuse Mario controller facts. |
| `stardew_adapter.py` | `DisposableSaveManager`, `ScreenObservation`, `OrdinaryInputDriver`, `WateringLedger`, `StardewOperator`: preserve existing save isolation and neutral handback. Configure real copied-save selection, screen perception and ordinary foreground input here. |
| `stardew_companion.py` | Same-current-session Observe/Tell/Show/Do authorization, target evidence and postconditions. Bind copy/process/window/observation identity; invalidate on reset/focus loss. |
| `companion_catalog.py` | Keep switching behind neutral input, retained history, confirmed handback and invalidated adapter state. |
| `custom_variants.py` | Authority-free saved plan revisions and separate immutable attempt outcomes. Runtime eligibility is recalculated on reopen. |
| `beta_readiness.py` and `personal-beta-v2.yaml` | New beta evidence mapping; historical V2 manifests remain unchanged. A passing Mario gate does not establish Stardew live readiness. |

Stardew live prerequisites: an explicitly selected engineering save or an owner-selected
source with copying authorization; verified isolated loading and persistence; visible supported game/window;
screen-only crop/plot/resource/position perception; configured ordinary input;
complete fresh observation and target identities; no primary-save overwrite.
The planner's fixture target objects cannot satisfy live perception. See the
[Stardew integration contract](b3-integration-contract.md) for current module ownership.

Stardew live checks: copied-save identity and primary preservation; visible
watering of the exact selected planted set and return point; before/after crop,
energy, can/refill and tool-use reconciliation; paused/neutral input on focus
loss; stale/reset/process/window mismatch refusal; immediate reclaim with
retained partial outcome; live evidence linked to the exact candidate. Harvest,
plant, selected clearing and combined routine remain planned extensions, outside the watering allowlist.

## Beta readiness

```bash
.venv/bin/python -m smb3_agent.beta_readiness
.venv/bin/python -m smb3_agent.beta_readiness --identity
```

The candidate-bound `game-companion-beta-evidence/v2` manifest hashes its
retained artifacts and requires the appropriate classifications. Add
`--manifest PATH --evidence-root DIRECTORY --gate-b2` for the B2 gate. Missing
visible proof cannot be supplied by fixture or browser-only records. Full Stardew live verification and expanded farming remain incomplete.
