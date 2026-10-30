# Bounded Creative construction

This source-only engineering preview evaluates scalable construction in a newly
created, explicitly enabled Creative practice world. The [world design preview](minecraft-designs.md) accepts named text requirements and
reference captions with a provenance-backed checklist. Image analysis is unavailable; terrain and architecture use separate reviews
and bounded compilers described below. Existing Survival construction
keeps its own limits and resource accounting. No installed build is updated by
source changes.

In **Create a new practice world**, select Creative and explicitly enable bounded
construction. The additional engineering panel can prepare the representative
terrain/building fixture, start/continue it, or request undo. Stop remains the
ordinary persistent Stop control. An existing unmarked world cannot be enabled
through this interface. Do not manually add permission markers to retained worlds.
Enabled preview worlds use a fixed empty Creative generation seed with generated
structures disabled. Other practice worlds keep their existing generation policy.

## Ownership and execution

- `minecraft_build.py` owns world/region identity, immutable approved cell baselines,
  design revisions, SQLite write-ahead intents and verified receipts. Reopening is
  idle. A continuation is an explicit new command with captured session/revision.
- `minecraft-worker/build-service.cjs` validates the installed game registry's
  complete block states, bounded palette, region, protection and observed preconditions.
  All writes and physical placement batches enter the existing worker scheduler.
- `BuildConsole` is a private callback for an enabled app-owned Creative server.
  It emits only generated conditional setblock/fill operations plus a receipt barrier.
  No raw command string, operator permission, public port or model-generated code
  is exposed through the application API.
- A unit has at most 64 cells. Homogeneous contiguous rows can use conditional fill;
  other units use per-cell conditional writes. A unit can partially succeed. Intents
  remain durable until fresh observations establish results; partial work is not
  reported as completion. Final verification checks the entire saved design.

The barrier confirms command processing; block packets can arrive later, so both
barrier and observed target states are required. Stop admits no further units and
waits for the in-flight barrier/verification. Unknown cessation closes the worker;
reconnect does not restore permission to continue. Client cancellation does not
prove that remote model computation stopped.

## Recovery and limitations

Reconciliation distinguishes exact before/after states from conflicts. Changed
player blocks are never silently replayed or undone. Undo targets the latest design
and is repeatable; it refuses interactive-block removal because a block-state-only
journal cannot safely restore a player's chest contents. This is a real limitation,
not a claim of general world rollback. Replacing a design is not authority to erase
an unresolved conflict.

**Undo unchanged cells only** explicitly skips conflicting and interactive cells
and reports a partial undo with their positions. Ordinary undo refuses the entire
operation on conflict. Neither operation supports undoing fluid designs: removing
their containing walls safely needs a dedicated operation. First-time designs refuse
unrecorded occupied cells; this empty-world preview does not assume existing work is
expendable. State checks cannot distinguish another person replacing a block with
the exact same state.

Random vegetation ticks are disabled in explicitly enabled Creative engineering
worlds so reviewed terrain states remain reproducible. Fluid simulation still runs;
water requires a projected closed basin, with containment built before fluid cells.
The approved fluid volume is staged as journaled glass before replacing it with
source water in bounded batches. This prevents water spreading into unbuilt air
after Stop. An interrupted staged cell is recognized only through its saved intent.
This setting does not change Survival or unmarked worlds.

The small engineering preview region is 64 × 64 with an excluded 8 × 8 protected column.
Block observations require loaded chunks; unavailable chunks cause refusal. The
fixture is a test input, not a general map generator or proof of whole-project
quality. Expanded terrain uses the separately reviewed manifest described below.
Reference captions inform designs; image analysis and arbitrary functional block
entities remain unsupported. Source changes do not update installed apps.

`scripts/qualify_minecraft_build.py` is an explicit live harness. It requires a new
output directory and runtime-only server assets plus an existing owner-accepted
EULA receipt. It copies no world/save data. It runs the source HTTP application,
retains trial outcomes, saves the disposable world and shuts down owned processes.
Run it only when live qualification is authorized. Ordinary and batched placement
benchmarks include equivalent cells, with setup positioning/materials disclosed;
those timings are not full landscape throughput.
Each strategy's first trial starts with a fresh server process; two trials use that
warm process. This does not flush operating-system disk caches. The viewer reports
round-trip samples after all pending meshes finish and two browser frames run;
these measure rendering backlog, not pixel-level verification of every block.

`scripts/qualify_minecraft_build_recovery.py` separately exercises fluid Stop,
actual owned-server loss, explicit continuation, unknown-player-edit refusal and
interruption during the final verification read. Both harnesses require the same
explicit live-test authority and fresh output directory. They do not install or
operate on retained owner worlds.

`directory_migration.py` provides restartable directory activation for the delivery
migration script. It verifies copies, persists a journal, syncs activation boundaries
and leaves source data intact. An already activated destination that changed after
interruption is refused, never overwritten. A completed receipt never replays the
migration onto a subsequently used destination.

## Focused offline checks

```bash
.venv/bin/python -m pytest -q tests/test_minecraft_build.py tests/test_minecraft_chat.py tests/test_minecraft_chat_ui.py tests/test_minecraft_bridge.py tests/test_minecraft_delivery.py
node --test minecraft-worker/test/*.test.cjs
```

Synthetic fault tests exercise transaction and recovery behavior; they do not
establish live-game fidelity or performance.

## Reviewed terrain regions

Landscape construction uses the same project database, worker scheduler and
64-cell conditional write units. **Review terrain** stores a versioned manifest;
**Start / continue terrain** explicitly activates its region. Reviewing alone
never expands write authority. Reopening stays idle, and re-reviewing the same
revision cannot reinterpret or replace its manifest.

The compiler supports 192×192 and 256×256 landscapes in 64-block tiles. It reserves
future architecture, grades paths, carves bounded caves, and stages earth and glass
containment before native foliage and water. The review map shows actual reserved
sites; a raised site or crest can be repositioned to preserve its elevation and
clear entrances. Buildings and interiors use a separate architecture review and explicit Start.

A one-block perimeter rim contains water inside the reviewed extent; channels end
at that rim. A fixed 32-block outer buffer is observable but never writable. Each stage has a
100,000-cell limit; a terrain operation has a two-million-cell and two-hour limit.
The existing 2 GiB storage budget and 1 GiB free-space reserve remain in force.
The worker admits at most 100,000 request envelopes before requiring a restart;
this does not widen any action, region or per-write limit. Chunk readiness is
checked before working on each tile. A reviewed manifest describes planned work;
only fresh world observations establish completion.

Native leaf distance changes when supporting logs and neighbouring leaves change.
Trunks therefore precede persistent leaves, which are placed in increasing native
distance order. A revision removes affected connected canopies outside-in before
changing trunks. Exact-state conflicts still stop construction; physics updates
are not a general excuse to adopt unexpected states.

Surface routing follows cave carving and uses the actual crest and entrance
positions. Cave mouths allow an uphill exit while the passage retains its required
clearance. Crossing decks preserve the full reviewed width. Completed terrain is
checked again after revisions; saved manifest changes are refused before region
admission. A failed final storage check leaves the project needing review.

## Architecture ownership

`minecraft_architecture.py` compiles reviewed terrain-bound components into bounded
cells and explicit room/object metadata. `BuildProject` stores architecture reviews
and binding indexes in the same SQLite database as terrain; all mutations still
use the existing intent/receipt journal and sole worker scheduler. Native multipart
states are registry-validated. Removing interactive blocks remains refused when
contents-aware restoration is unavailable. Repeated geometry revisions use the
first captured baseline for each removed coordinate.

Terrain revisions filter architecture-owned positions, including interior air,
from writes. Height or water changes beneath that ownership require an explicit
dependency resolution. Path changes can be reviewed around other buildings without
rebuilding their foundations. Player-edited blocks remain conflicts; stored
architecture is not permission to overwrite them.

## Continued sessions and diagnostics

Closing saves the retained world and leaves companion work idle. Reopening loads
saved stage counts and receipts; choose Continue explicitly to inspect and finish
remaining work. A saved completion count is historical until its cells are freshly
surveyed. A hard server crash can roll the world behind the receipt journal; an
unexpected state is refused, not overwritten. Preserve the failed profile/world
and restore a matching closed backup into a fresh location before continuing.
Never mix a journal from one checkpoint with world files from another.

Status polling uses the latest display summaries; execution still reads and
validates the original manifests. All model replies during active reviewed project work, and informational
questions in idle projects, use a read-only result contract. A mistaken command
classification cannot cancel or redirect reviewed work. Direct Stop remains
independent. Control/status answers receive relevant application facts and current project
state separately from the latest question. Known control contradictions are
withheld, but that narrow guard cannot certify arbitrary prose. Model-generated
answers can still be inaccurate; verify important claims against visible state.

The experimental question path first asks the model to choose up to two split
points from generic punctuation/conjunction boundaries in the user's exact text.
The application constructs one to three complete source spans, preserving every
character, including negation. Each span receives a separate selection of typed
claims from the same captured evidence. Logs retain source offsets, claim references
and an evidence snapshot digest. The last two prior user messages may resolve
follow-ups; previous assistant prose is not treated as factual evidence.

The application composes complete claim text, preserving procedures, conditional
prerequisites and unknowns. Unsupported spans are identified without dropping
supported spans. This is model interpretation plus deterministic fact composition,
not proof of unconstrained prose quality. A source span with a selected fact is
structurally covered, but the chosen fact can still be irrelevant: current testing
mapped a reopening-preservation question to historical-record facts. This remains
a failed conversational answer even though every source character was retained.

Each question has one shared 240-second deadline, at most four model calls, and
at most 512 generated tokens per call (2,048 aggregate generated tokens). The
existing 32,000-character per-request context bound also applies. Cancellation or
changed authority prevents publication. Direct Stop is independent. No fallback
model or automatically retried interpretation is used. Current/historical state,
unknown test outcomes and retained world authority remain distinct.

The sustained qualification harness records every question stage and reserves
four calls before admission against an 80-call limit across process sessions.
Its default is seven questions per session, allowing at least 20 replies across
three sessions if actual usage stays within the cap. These infrastructure limits
do not establish actual-model completeness or sustained acceptance; both remain open.

For source measurement, the viewer accepts an optional `?measure=x,y,z` query.
It samples real framebuffer colors at a ray-verified world face for controlled
dirt/white-wool transitions. Measurements include browser-clock uncertainty and
the bot-observation-to-frame-acknowledgement interval; they cannot locate the
server's exact commit tick. The delivery script separately requires screenshot
pixel confirmation. Its synthetic messages test display delivery, not inference
accuracy. Ordinary viewing does not enable framebuffer sampling.

Diagnostic event logs rotate at 64 MiB, retaining the current file and one previous
file (`.1`). Older diagnostic output is replaced automatically. Duplicate block-survey
payloads are represented by count and digest; actual observations and receipt
validation remain exact. Rotation does not touch worlds, project journals, settings
or conversation history. An unwritable log or oversized single batch still stops
work and refuses new requests; Stop remains available. Check storage and folder
permissions before reopening and explicitly issuing new work.

`scripts/qualify_minecraft_sustained.py` runs authorized engineering trials only
in copied, closed disposable worlds. Each invocation is one process session. Its
prior diagnostics remain at their original source rather than being copied into
each disposable run. On macOS it uses independent copy-on-write files and keeps
the existing reserve for later growth; source state is never edited. Session reports distinguish admitted requests, actual model replies,
verified construction, Stop, idle reopening and explicit continuation. They do
not establish owner acceptance or installed behavior.
