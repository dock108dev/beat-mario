# MC-B1-01 — Headless Minecraft foundation

October 27, 2026. Source implementation and local live qualification; **not an
installed-app delivery or completion of Beta 1**. Human-client walkthrough is
pending at the owner's explicit request. No Codex inference was used in this slice.

Current successor: [MC-B1-02 conversational session](mc-b1-02-chat-play.md) passed local qualification; its handoff now targets MC-B1-03. The protocol and original dated handoff below are retained.

## Integration decisions

| Component | Exact qualified version |
| --- | --- |
| Minecraft Java vanilla server | 1.21.4, official Mojang download |
| Server SHA-1 | `4707d00eb834b446575d89a61a11b5d548d8c001` |
| Java used | Oracle Java 21.0.4+8-LTS-274 |
| Node / npm used | 24.22.0 / 11.19.1 |
| Mineflayer | 4.39.0 |
| mineflayer-pathfinder | 2.4.5 |
| prismarine-viewer | 1.33.0, with the bounded serving corrections below |
| Express / Socket.IO / vec3 | 4.21.2 / 4.8.1 / 0.1.10 |

`minecraft-worker/package-lock.json` pins the complete transitive dependency
resolution; use `npm ci`. Worker `.nvmrc` pins Node independently of the historical
root Node major. Java 21 is required for this server; no Java installation changed.

The installed game versions were 26.3 and 26.4-snapshot-2. Mineflayer's current
README lists through 26.1, while the published viewer's version table explicitly
includes 1.21.4. We selected that common version and demonstrated it against the
actual server. No existing game installation or world was downgraded.

A new marked directory owns the server and world:
`artifacts/minecraft-b1-practice-1.21.4/`. It contains the official server download,
its verified digest, EULA record, properties, logs and retained `practice-world/`.
The owner explicitly accepted the Minecraft EULA in this chat. Fresh directories
require an explicit `--accept-eula`; an existing accepted directory needs no flag.
The launcher refuses an unmarked nonempty directory or mismatched version marker.
No legacy save, application data, authentication cache or launcher profile is read
or rewritten. Server binaries and world assets remain local and untracked.

The server binds **127.0.0.1:25575**, with RCON/query disabled. It is a Creative,
peaceful flat practice world with independent local offline identities. The bot is
`CompanionBot`; no password or Microsoft token is required or stored. Offline mode
applies only to this new loopback server and is not suitable for external hosting.
No existing server authentication setting was changed. This is not evidence of
Microsoft-authenticated external-server support.

A human with a licensed **Java 1.21.4** client can use Multiplayer → Direct
Connection → `127.0.0.1:25575`, under their own username, different from
`CompanionBot`. Use a separate launcher installation/game directory for that
version and do not open any newer-version single-player saves with it. The
installed 26.3 client is incompatible. Two distinct protocol players were verified;
that test is explicitly not relabeled a human-client walkthrough.

## Run, view, stop, reconnect

From the repository root:

```sh
npm ci --prefix minecraft-worker
PYTHONPATH=src .venv/bin/python -m smb3_agent.minecraft_demo
```

For an entirely new practice directory, add `--accept-eula` only after the owner
has accepted [Minecraft's EULA](https://www.minecraft.net/en-us/eula).
First preparation downloads the server from Mojang's version manifest and checks
its SHA-1 before launch. The existing Java executable on PATH starts the server.
Do not run two harnesses or the live-verification script at the same time.

Wait for the printed ready URL, then open **http://127.0.0.1:8768**. The minimal
harness displays world/session/character, the live third-person view, current
position and action state. Walk requests a destination five blocks away (arrival
tolerance is one block); remove-ground requests one adjacent reachable block.
This is an engineering harness, not the product dropdown/chat UI.

- **Stop** sends cancellation directly to the worker. It clears active and queued
  work and invalidates the old revision. Local dispatch is displayed separately
  from observed stationary confirmation. Momentum can take several ticks to settle.
- **Close view / Reopen view** detaches only the renderer. Actions continue, state
  remains visible and Stop remains available. Reopening adds no action authority.
- **Reconnect bot** closes the old connection/viewer, creates a fresh session and
  opens a new viewer URL, without restoring a goal or action queue.
- **Ctrl-C** in the launch terminal shuts down the worker and viewer, then sends
  the owned Java server `stop`, allowing up to 30 seconds to save the world before
  bounded process cleanup. A later launch retains that world.
- The minimal view follows the bot; orbit adjustments are preserved as it moves.
  Rendering is read-only. Viewer failure does not authorize or cancel gameplay.
  If the connection/status becomes unavailable, the harness warns that cessation
  must not be assumed. Reconnect repairs the viewer as well as the connection.

Process handles, process groups and parent-death watchdogs reuse the repository's
`OwnedGameProcesses` / `ChildWatchdog` foundation. Normal shutdown saves the world.
An abrupt parent death kills owned children to prevent orphan control; as with a
crash, that fallback cannot promise the latest unsaved world changes were flushed.
No process-name scanning or termination of unrelated Minecraft/Java apps is used.

## Python integration and ownership

`src/smb3_agent/minecraft_bridge.py` owns worker stdio, request futures, session
identity and a bounded event buffer. It does not import native input/capture code.
`minecraft_practice.py` owns only the isolated Java child and retained practice
configuration. `minecraft_demo.py` supplies a temporary loopback browser harness.
The worker is plain Node CommonJS JavaScript, avoiding a build/TypeScript runtime
prerequisite. It owns the only action scheduler and Mineflayer connection.

```python
from smb3_agent.minecraft_bridge import MinecraftBridge

with MinecraftBridge() as game:  # practice server must already be running
    state = game.connect(port=25575)
    authority = {"session_id": game.session_id, "revision": state["revision"]}
    # Capture this authority BEFORE requesting a plan from Codex.
    target = {**state["position"], "x": state["position"]["x"] + 5}
    request_id, completion = game.submit(
        "execute", {"action": "move", "target": target},
        timeout_ms=10000, **authority,
    )
    # Concurrent chat reads state/events; it does not cancel this future.
    facts = game.observe()
    events = game.events_after(0)
    result = completion.result(timeout=14)
    stopped = game.stop()  # independent of model inference
    game.disconnect()
```

Actions must explicitly supply the captured session and revision. Never replace
an old model result's authority with current values. Never treat cancellation of
a Python Future as gameplay Stop; use `stop()`. A goal replacement calls Stop,
waits for its outcome, then deliberately captures fresh authority. Ordinary
questions only observe. The worker serializes actions, not conversation.

## Protocol v1

Owned UTF-8 JSONL stdio is the control channel. No shell snippets, server-console
commands, credentials, chat-text execution or HTTP game-control endpoint exists
in the worker. The harness's separate HTTP wrapper binds only loopback; writes
require a per-process token plus matching Host/Origin. The token is never logged.
The viewer validates Host/Origin and has no control authority.

Every request includes `v:1`, unique string `request_id`, string `session_id`,
`op`, integer `timeout_ms` (100–30000), `args`, and `revision` for actions. IDs use
1–80 letters/digits/underscores/hyphens. Maximum input frame budget is 64 KiB.

| Operation | Result / semantics |
| --- | --- |
| `connect` | Args `port`, optional `viewer_port` (0 selects a free port). Fixed loopback, bot identity, offline auth and 1.21.4. Ready after spawn and nearby chunks. Returns state and viewer URL, or explicit viewer failure with bot still ready. |
| `observe` | Position, health/food, dimension, nearby blocks, inventory, player names, readiness, revision, active/queued IDs and viewer URL. |
| `capabilities` | Supported actions, version and bounds. |
| `execute` | `move` with finite target x/y/z within 32 blocks, or `dig` within 4.5 blocks. One active action, up to 16 queued. Pathfinding cannot dig, scaffold or tower automatically. |
| `cancel` | Bypasses action queue; increments revision before awaiting; clears queue, halts pathfinder/control states/digging, awaits active settlement, then samples stationarity. |
| `disconnect` | Cancels, closes viewer sockets/listener, quits bot, invalidates session. Does not stop an independently owned server. |

Events include `v`, monotonically increasing worker `seq`, `at_ms`, `session_id`,
`request_id` (null for unsolicited events), `type`, and bounded result/error data.
Types include worker readiness, state, accepted, progress, completed, failed,
cancel-dispatched, viewer connection/failure and game disconnection. The Python
bridge resolves responses only for the matching request **and** session.
State events stream every 500 ms. Buffer retention is 2,000 events; a consumer
must persist needed history and detect sequence gaps. No durable chat is added.

Request IDs are never replayed: duplicates fail, including after reconnect.
Session IDs cannot be reused within a worker lifetime. At 10,000 requests, restart
the worker deliberately rather than evict duplicate history. Queue time consumes
the action timeout. Cancel/timeout aborts clear bot controls; an action that fails
to settle within 1.5 seconds closes its game connection and quarantines its
scheduler. Missing bridge replies close the worker and report cessation as
unconfirmed. No automatic reconnect/resume occurs.

Movement completion verifies the resulting connection position and arrival
radius. Digging additionally waits for an actual server `block_change` packet;
Mineflayer's speculative local block removal alone does not count. Stop's
`stopped_observed` means controls cleared, action settled and successive position
samples stationary. Minecraft has no dedicated server Stop acknowledgment;
this field must not be displayed as such. Gravity/external forces may still move
a neutral bot. Failure to observe stationarity is explicitly `unconfirmed`.

## Viewer compatibility corrections

Published Prismarine Viewer 1.33.0 advertises 1.21.4 but its browser bundles retain
pre-1.18 height assumptions. The first actual run showed a sky-only view despite
valid game state. `minecraft-worker/viewer.cjs` serves checked, narrowly modified
bundles without changing `node_modules` or committing generated/vendor assets:

1. Initialize camera at negative Y and follow the same bot's position.
2. Mesh/unload sections over -64 through 319, the qualified Overworld range.
3. Index chunk sections relative to `minY` in both terrain-worker paths.
4. Stop rejecting visible neighboring faces simply because Y is negative.

Each replacement verifies its exact expected occurrence count and fails closed
on dependency drift. This is a **1.21.4 Overworld** integration, not a general
renderer-version/dimension compatibility claim. Upstream helpers bind wildcard
addresses, so this integration uses `WorldView` with an explicit 127.0.0.1 server.
Mouse-click events have no game action handler. Viewer tab loss removes its own
listeners/timer, leaving the bot connection and scheduler independent.

## Verification and handoff

Run focused offline checks:

```sh
npm test --prefix minecraft-worker
.venv/bin/pytest -q tests/test_minecraft_bridge.py
.venv/bin/ruff check src/smb3_agent/minecraft_bridge.py src/smb3_agent/minecraft_practice.py src/smb3_agent/minecraft_demo.py scripts/verify_minecraft_headless.py tests/test_minecraft_bridge.py
```

Run real server qualification, with the harness stopped:

```sh
PYTHONPATH=src .venv/bin/python scripts/verify_minecraft_headless.py
```

The script moves and removes one adjacent block in the retained practice world.
It records connection/viewer identity, state changes, duplicate/stale rejection,
active/queued Stop, reconnect, second protocol player, world retention and owned
cleanup. See [dated results](mc-b1-01-evidence-20261027.md) and local
`artifacts/mc-b1-01-live/`. Synthetic checks are not substituted for these results.

**Next: MC-B1-02.** Wire the Minecraft dropdown to this lifecycle and viewer plus
persistent chat. Adapt existing `CodexProvider` to bounded observation/plan
schemas. Keep conversation calls independent of `submit()` and the runtime;
capture session/revision before inference and discard late conflicting plans.
Add go-to/follow as validated skills, streamed activity, direct Stop, goal
replacement and explicit connection failures. Demonstrate one real Codex-driven
movement, a question while moving, and a changed destination. Measure CLI startup,
reply latency and Stop dispatch separately from observed cessation. Keep the
human-client walkthrough visible as pending and handle its 1.21.4 prerequisite.
Do not flip legacy camera flags or port screen-capture/focus prerequisites.

Primary compatibility sources: [Mineflayer](https://github.com/PrismarineJS/mineflayer),
[pathfinder](https://github.com/PrismarineJS/mineflayer-pathfinder),
[Prismarine Viewer](https://github.com/PrismarineJS/prismarine-viewer), and
[Mojang version manifest](https://piston-meta.mojang.com/mc/game/version_manifest_v2.json).
Package source and actual local game evidence determine the exact qualified pairing.
