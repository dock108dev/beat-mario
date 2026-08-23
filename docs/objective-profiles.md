# Objective profiles and live coaching

Game Companion V2.5 treats each supported level as its own measurable objective space. A profile is adapter-neutral and versioned. It declares the game and level, classification, exact start and terminal conditions, timing boundary and units, finite required and optional events, allowed and prohibited techniques, resource rules, supported facts, recovery and miss semantics, evidence, outcomes, and capability flags.

Classifications are never promoted implicitly. Accepted agent best, accepted safe/reference run, player personal best, historical player run, review-only demonstration, and unreviewed candidate remain distinct. Review-only Show evidence cannot become an authoritative comparison reference.

## Initial Mario catalog

`smb3.world-1-1.fastest-accepted-clear@1` measures from the first supported World 1-1 gameplay frame through the game-owned course-clear map return. Its compatible accepted-agent reference is 2,060 emulator frames, with accepted route evidence from the byte-identical 3/3 `world_8_finish_game` reliability run. Comparison uses only the same profile version, level, timing boundary, units, and accepted provenance. It reports ahead, behind, tied, or not comparable at supported progress anchors.

`smb3.world-1-1.observable-progress-checklist@1` is a finite checklist: reach x=1000, reach x=2000, and clear the course; a no-death finish is optional. It is deliberately not a collectible, destruction, or full-completion profile. The accepted passive observer cannot enumerate every coin, enemy, power-up, breakable brick, or hidden block.

World 3-2 is unsupported because the passive observer does not yet expose a stable 3-2 identity and exact entry/clear boundary. World 4-1 full completion is unsupported because, in addition to level identity and boundaries, the observer cannot enumerate an exact object universe, distinguish object identities, or prove collection/destruction and scroll irreversibility. No new passive facts were added merely to imply support.

## Coaching and Tell

Quiet suppresses all unsolicited advice. On request emits advice only after the player asks. Proactive may emit one grounded, recoverable hint when a configured condition matches. Every hint carries its trigger, profile, provenance, recovery status, action, objective relevance, confidence, and stable deduplication key. Stale, unknown, unsupported, duplicated, obsolete, and unrelated hints are suppressed.

Objective-aware Tell answers comparison, remaining-requirement, miss, recovery, next-action, behind, and full-plan questions. Minimal, Guided, and Full spoiler levels control detail. Answers separately label current live facts, profile facts, reference facts, inferences, and unknowns.

V2.5 coaching itself never writes controller input. Show stays separate and
review-only.

## Dynamic V2.6 run and profile library

The local run library is open-ended and adapter-neutral. A measurable profile
is data with a version, boundaries, timing units, emulator assumptions, finite
required and optional events, required evidence, and provenance; profile names
or objective types are not enumerated in core code. A valid first normal clear
may create its profile automatically. More specific objectives remain
unavailable until their requirement universe is measurable.

Every retained run records actor and mixed-session classification, states,
frames, deaths/recoveries, resources, objective events, trace and observation
references, completion and compatibility decisions, solution classification,
and provenance. Compatible player, agent, mixed, and overall fastest records
are reconciled separately. Slower runs remain in history, faster compatible
runs replace only the relevant local index, duplicate evidence is idempotent,
and failed/incomplete/incompatible runs are retained without becoming a best.

An accepted replay-safe solution is separate from a fastest observed run and
from a captured candidate trace. V2.6 takeover can select only the former; trace
review and promotion remain V2.7 work.
