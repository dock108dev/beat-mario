# Live Mario observation

Valid completed observations also create an adapter-neutral V2.7 learning
attempt referencing the original run, input trace, and observation evidence.
This derived envelope never rewrites the raw session. Candidate derivation is
advisory and review-only; the takeover capability continues to enumerate only
accepted replay-safe executable solutions.

V2.4 uses one deliberately narrow connection mechanism. From the player page,
**Start visible live observation** launches a normal visible FCEUX process with
`scripts/fceux_live_observer.lua` loaded. FCEUX keeps its existing keyboard and
controller configuration, and the owner plays in that window. Game Companion
does not attach to an arbitrary already-running emulator and does not describe
a separate automated route process as the owner's session.

The Lua observer reads controller state with `joypad.get(1)` and reads bounded
Mario state with `memory.readbyte`. It contains no controller setter, memory
writer, reset, power-on, savestate, or state-load call. The Python live-session
manager only launches the observation-enabled window and reads its append-only
trace. It has no controller-output dependency or API. V2.4 therefore labels
direct emulator input as `player`, reserves `agent` as a separate future actor,
and fails closed if an agent, unknown, duplicated, unsupported, out-of-order,
or replacement-session record appears. The expected agent-input count is zero.

Each session has a generated session id, observer continuity token, FCEUX
process id, adapter/game id, and configured game-file SHA-256. Reconnection may
continue the same logical session only with the same process and token, a
strictly increasing sequence, and a non-decreasing emulator frame. Any identity
replacement closes the prior session. A two-second observation gap is stale;
an eight-second gap is disconnected. Stale, disconnected, unknown, and
unsupported state cannot feed live Tell.

The observer records frame-ordered facts and direct player input changes,
including source, UTC observation time, sequence, frame, confidence, and actor.
It derives bounded world/map/gameplay state, World 1-1 checkpoint support,
segment progress, deaths, recovery/re-entry, inventory resources, transitions,
and course-clear candidates. Sparse FCEUX screen samples provide independently
readable visual context. Other Mario checkpoints remain visible as unsupported
until they have an explicit adapter mapping; they are not guessed from movement.

**Stop observing** creates the detach request consumed by the Lua observer. The
observer closes its trace and returns, while FCEUX and the player's game remain
running. Game Companion does not send a neutral input, terminate the emulator,
reset, load state, modify inventory, reposition Mario, or advance the game as
part of stopping.

Every bounded local session directory under `artifacts/live-observation/`
contains:

- `session_manifest.json` and `connection.json`;
- `lifecycle.jsonl`;
- `observations.jsonl` with typed facts and provenance;
- `controller_inputs.jsonl` with `player` ownership;
- `events.jsonl` for progress, transition, death, recovery, resource, and clear
  observations;
- sparse original and converted screen samples plus a contact sheet when
  available;
- `reconciliation.json` with counts, final state, and the explicit agent-input
  count.

This evidence is owner-play observation evidence only. It is not route
reliability, Show evidence, agent-executed gameplay, takeover proof, or a player
completion claim. Show remains a separate fresh review process.

V2.6 preserves that exact observation-only launch and adds a separate opt-in
choice, **Allow takeover later**. The opt-in launch uses
`fceux_live_takeover.lua`; the passive script remains structurally incapable of
controller writes. Player ownership is still the default. A transfer requires
a fresh authorization bound to the session, emulator PID, game-file hash,
current-state fingerprint, objective/profile version, accepted executable
solution, scope, stop condition, timeout, protected resources and decisions,
nonce, and a new control epoch.

During authorized execution the same Lua process streams `agent`-labeled
controller samples into the observation trace. `Take Control Now` writes a
dedicated reclaim request that the accepted controller checks before every
emulated frame. It writes neutral input before the wrapper acknowledges
handback. The page then returns to player ownership and continues observing the
same FCEUX PID and state. Reclaim, timeout, cancellation, stale state, process
loss, solution failure, or ownership conflict all fail closed.

Every game-owned clear with stable adapter identity and complete timing is also
sent to the local append-only run library. Its captured trace is comparison
evidence and defaults to candidate/non-executable. The completion may establish
or improve a fastest *locally observed* baseline; it never implies a community,
global, or world record.

## B2 opt-in session plans

The separate B2 launch adds a fresh review hold, revision-bound primitive
mailboxes, acknowledged speed/pause and process-local input auditing. Only its
bounded plan path reads `fceux_b2_plan.lua`; passive observation remains unable
to emit controls. World 1-1 opening entry must have known level lineage, and the
full route requires exact fresh power-on. The controller consumes explicit
button states for all eight NES buttons so browser typing does not supply game
input. Unsupported fixed playback rates are rejected; normal and uncapped
faster intervals retain actual frames and wall time. See the [B2 guide](b2-conversation-guide.md)
and exact engineering evidence in the Desktop tracker. No owner acceptance is
inferred from these technical records.
