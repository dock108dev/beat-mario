# Exact next assignment — MC-B1-04

You are the Gameplay AI / Minecraft Systems Engineering Lead for Game Companion.
Repository: `/Users/michaelfuscoletti/Desktop/beat-mario`.

Read applicable instructions, `/Users/michaelfuscoletti/Desktop/mario_next_steps.md`,
`docs/beta-1-plan.md`, `docs/mc-b1-03-resources.md`,
`docs/mc-b1-03-evidence-20261027.md`, and `docs/private-beta-pm-handoff.md`.
Inspect the actual code and uncommitted changes before choosing boundaries.

## Deliver crafting prerequisites and flexible construction

Extend the ordinary Minecraft conversation so a request such as “Gather what you
need and build a small oak shelter near camp, with a doorway facing me” can resolve
prerequisites, gather, craft and build. Let the owner change dimensions, materials,
openings or location during work and ask questions while safe skills continue.
Do not deliver a separate crafting demo, a phrase-driven fixed script or one exact
wall as the product.

Reuse `minecraft_chat.py`, `minecraft_goals.py`, `minecraft_bridge.py`,
`minecraft_practice.py`, `codex_provider.py`, and the existing worker scheduler and
resource skills. Codex CLI remains the sole AI engine. Preserve goal/session/world
identity, total deadlines, action/material budgets, inventory reconciliation,
protected regions, cancellation barriers and late-result rejection. Do not create
another input owner or globally enable pathfinding destruction or scaffolding.

1. Add typed, validated recipe inspection, crafting and workstation-use skills.
   Resolve actual ingredients, recipe variants, yields, inventory space and nearby
   workstations from server state. Plan dependencies for common planks, sticks,
   crafting tables and basic wooden/stone tools. Missing prerequisites must lead
   to bounded gathering/crafting, an explicit limitation, or a concise question.
   Never assume a crafted item exists without observed inventory changes.
2. Extend the resource registry/tool prerequisite checks as needed for those
   recipes. Do not equate valid hand collection of logs with valid hand mining of
   every material. Verify harvestability and actual drops, and retain accurate
   accounting of existing inventory, additional collection, consumption and loss.
3. Add flexible structures with parameters for footprint, height, material,
   orientation, doorway and openings. Ground the proposed site in observed terrain
   and named places. Codex chooses meaningful layout/material adaptations; fast
   deterministic skills validate and execute each bounded placement/removal.
4. Validate reach, support, collision, inventory and protected areas before every
   operation. Require explicit permission before removing an existing structure
   or modifying an obstruction. Changes to a planned structure must invalidate
   conflicting remaining work, account for placed/consumed blocks and replan from
   current state. Do not silently clear terrain to make a plan fit.
5. Verify placements/removals from authoritative server updates and material use
   from inventory. Report completed structure portions, shortfalls, assistance
   and unfinished work honestly. Bound recovery, no-progress and total work.
6. Keep progress visible through CLI waits. Use compact context and event-driven
   model choices, not a call per block. Measure calls, response/first-action/full
   goal latency and reported usage; canceled usage remains unknown if unreported.

## Live acceptance and preservation

Use the ordinary source app with real Codex CLI and headless Minecraft. Preserve
Java 1.21.4, dependency pins/viewer patches, accepted Creative topology, separately
identified Survival world, saved places, conversation and dated evidence. Do not
reset this uncommitted checkout or alter owner saves. Human testing remains
explicitly deferred and protocol characters do not count as human walkthroughs.

Demonstrate a natural Survival gather → craft → build request without prepared
materials or an engineer guiding each action. Repeat with different starts,
materials, dimensions and layout. Demonstrate a missing prerequisite, occupied or
unreachable site, protected area, inventory shortfall, a question during work,
mid-build revision and Stop during both skills and pending inference. Reopen
without resuming permission and revalidate saved sites before reuse. Document all
prepared inventory, operator commands and terrain assistance separately from the
unassisted runs. Retain unsuccessful trials.

Add focused tests for recipe dependency cycles/budgets, material variants/yields,
workstation reachability, inventory consumption, placement support and server
verification, protected/removal permissions, structure revisions, parent/child
cancellation and stale responses after reconnect/world changes. Run the existing
Minecraft chat/bridge/worker/UI/provider checks and verify changed paths live.

Update the Desktop tracker, evidence and engineering handoff. State source/local
checks, live gameplay, installed-app status, hosted CI, deferred human walkthrough
and remaining Beta 1 work separately. Finish with the exact MC-B1-05 handoff for
sustained companionship, memory and session/failure recovery. Minecraft remains
the sole active Beta 1 game; no Mario, Stardew, public-server or release campaign
belongs in this slice.
