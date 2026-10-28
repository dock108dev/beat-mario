# MC-B1-03 — navigation and resource gathering

October 27, 2026. **Passed local source qualification and real Codex/Minecraft
app demonstrations.** This is not installed delivery, hosted CI, owner acceptance
or completion of Beta 1. [Evidence](mc-b1-03-evidence-20261027.md) ·
[Exact MC-B1-04 assignment](mc-b1-04-handoff.md).

## Ordinary use

Launch `Open Game Companion.command`. Select Creative practice or Survival practice
before selecting Minecraft. Both are retained, separate Java 1.21.4 worlds. Changing
worlds currently requires closing and reopening the source app. The accepted
Creative world remains flat/Creative. Survival is a separately identified natural
world in `artifacts/minecraft-b1-survival-1.21.4/`, using the existing owner EULA
acceptance and verified server binary. No owner save is imported or converted.

Requests supported through the existing chat include:

- “Remember this spot as home.” Move away, then “Return to home.”
- “Collect eight additional logs of any nearby wood, then return home.”
- “Remember this spot as camp. Protect everything within six blocks of home.
  Collect five additional oak logs outside that area and return to camp.”
- “Go to a nearby oak tree” without modifying it, or follow an observed player.
- Questions during gathering, a changed goal, and direct Stop during execution
  or pending Codex reasoning.

“Collect” defaults to additional collection. An explicit target total subtracts
existing matching inventory. The app states the starting inventory and additional
amount before work. Common Overworld log variants are supported; “any wood” can
select among them. Logs can be gathered by hand; available axes are compared by
harvest time. Crafting missing prerequisites and non-log mining remain unavailable.
Logs stay in the bot's inventory when it returns; chest deposit is not implemented.

Protection is an explicit radius around a saved place, applying to both navigation
and digging. Do not include a desired return point inside an excluded region.
Ambiguous “those trees” or “the house” asks for a named place and radius rather than
inventing boundaries. Protection and named places persist with world UUID,
dimension and game version. Reopening restores memory and conversation, never a
goal. Reuse checks identity, current terrain/hazards, route and arrival anew.

## Coordinator and worker contract

`minecraft_chat.py` retains Codex intent classification and a fresh proposal after
the cancellation/revision barrier. Codex is the sole AI engine; it interprets
resource variants, quantities, additional versus total, places, constraints and
changed requests. Context now includes bounded resource observations, actual goal
progress, saved places and recent outcomes, without recursively resending inference
records. No per-block model calls or phrase-to-script intent dispatch were added.

`minecraft_goals.py` composes inspect → approach → equip → dig → pickup → reconcile
→ continue/recover → return. It owns goal identity and captured session/revision,
not game inputs. The existing worker scheduler is still the only action owner.
Every child carries its goal ID, world identity and origin; uses the same captured
authority; and consumes the parent's remaining deadline/action budget.

Limits: 240 seconds from request processing (including reasoning), 80 child
skills, up to three failed target attempts, and a 32-block goal area. Child skills
have at most 15 seconds; approach considers at most three observed standing
positions. The resource block budget is the needed quantity plus two. Log requests
are limited to 1–32; that is not a guarantee every quantity fits the time budget.
Search examines at most 64 nearby log blocks, and harvesting stays within the
current low-trunk height band (feet through three blocks above). Inaccessible
upper trunks, distant resources, inventory limits and missing prerequisites produce
partial outcomes. No automatic climbing, tree cleanup or replanting is provided.

The worker validates reach, line of sight, current block identity, capacity,
protected targets and hazards. A running guard also halts on world changes,
32-block origin overflow or low health/food. Pathfinding cannot dig, scaffold,
tower or parkour. An obstruction may be routed around, but is never permission to
remove it. Recovery records rejected targets and route failures and does not retry
one failed target or repeatedly call Codex for an unsuccessful action.

Digging verifies authoritative single-block **or batched block-change packets**;
Mineflayer's predicted local removal is insufficient. Pickup re-resolves the
observed item entity after its initial fall. Inventory reconciliation records
positive changes, losses and net matching change separately from verified breaks
and distinct observed drop entities. It also records unrelated item changes.
Missing verification is not counted as a successful break, even if inventory later
changes. A partial report states the shortfall and whether return succeeded.

Questions do not replace the supervisor or worker revision. Replacement crosses
the same Stop barrier as the existing movement flow. Stop invalidates the parent,
pending reasoning and future children before waiting for observed cessation. Late
results may be logged but cannot resume a canceled goal. Memory writes also recheck
authority. One CLI request remains outstanding at a time; drafts survive busy
responses. Follow retains its existing 25-second/32-block limits.

## Checks and delivery boundaries

```sh
.venv/bin/pytest -q tests/test_minecraft_goals.py tests/test_minecraft_chat.py tests/test_minecraft_chat_ui.py tests/test_companion_ai.py tests/test_minecraft_bridge.py tests/test_minecraft_practice_modes.py tests/test_lab_ui.py::test_server_routes_player_shell_and_secondary_lab
npm test --prefix minecraft-worker
```

Final result: **68 Python checks and 12 Node checks passed**, plus scoped Ruff and
syntax/whitespace checks. Earlier failures and corrective trials are retained in
the evidence. The final source app was restarted and gathered one more birch log,
then returned to persisted camp with the final deadline and running guards active.

The tested source is now in shared-checkout commit `2f0a6a9`, which appeared
concurrently during this work; this session did not create or push it. Final
documentation updates remain uncommitted. No installed app was built or updated, no hosted CI
was run, and no human-client walkthrough was performed. The owner's deferral
remains in force. Remaining Beta 1: MC-B1-04 crafting/construction, MC-B1-05 sustained
sessions/recovery, and MC-B1-06 installed first-use/owner walkthrough.
