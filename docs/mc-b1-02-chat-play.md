# MC-B1-02 — conversational Minecraft session

October 27, 2026. **Passed local source qualification and real Codex/Minecraft
session demonstration.** Installed delivery, hosted CI, owner acceptance and the
full Beta 1 remain separate and incomplete. [Evidence](mc-b1-02-evidence-20261027.md).

## Launch and ordinary use

Double-click **Open Game Companion.command** in the repository. It opens the
source app at `http://127.0.0.1:8765`. Choose **Minecraft**. The app starts the
accepted retained practice world and CompanionBot, then embeds its actual view
beside chat (stacked on narrow windows). No native game client, coordinates,
calibration, keyboard capture or focus permission is needed for this route.

The qualified local prerequisites remain Java 21, Node 24.22.0, the pinned
`minecraft-worker` dependencies and signed-in Codex CLI (tested 0.144.6). Existing
EULA acceptance is reused. Missing prerequisites/sign-in/connection failures are
reported; installation/setup polishing belongs to MC-B1-06.

Try “Walk 10 blocks north,” “Go back home,” or “Follow Alex” when Alex's character
is observed nearby. Ask “Who are you following?” during follow, or change the
request with “Walk east instead.” Unknown places or unavailable gathering/building
requests receive clarification or an explanation. Home means this connection's
starting location, not a durable named-place memory.

**Stop** is always available and bypasses inference. Exact chat “Stop”/“Stop now”
also bypasses inference; other conversation uses Codex. A question does not stop
or restart movement. Only one inference request is outstanding in this session;
you may keep editing a draft while it runs. Requests rejected while busy retain
the draft. New goals currently need two bounded CLI calls: intent classification,
then a fresh action proposal after previous motion has stopped.

Close view/Reopen view changes only the renderer. Bot work can continue with the
view closed. Reconnect replaces the game session and cancels pending reasoning;
it never resumes a goal. A browser refresh retains the current running session;
a full app restart restores conversation only. Double-click **Stop Game
Companion.command** to close this source delivery and save its owned world.
Closing a browser tab alone does not shut down the app or server.

## Implementation and authority

- `src/smb3_agent/lab_ui.py`: existing app lifecycle, protected same-origin routes,
  Minecraft as the ordinary home/dropdown path; legacy catalog at `/legacy-games`.
- `minecraft_chat.py`: durable app conversation, bounded context, one outstanding
  inference, typed intent/plan proposals, session/revision/epoch checks, progress,
  transitions and actual bridge cancellation. No model-generated code executes.
- `minecraft_chat_ui.py`: incremental message insertion; asynchronous updates do
  not replace the composer or transcript. Drafts use tab session storage. Existing
  scroll position is preserved unless the reader is already at the bottom.
- `codex_provider.py`: reused discovery, sign-in, isolated ephemeral read-only CLI,
  schema validation, subprocess cancellation and usage; adds spawn and first CLI
  JSON-event timing. Shell tools remain disabled. No API or Ollama substitution.
- `minecraft-worker/worker.cjs`: the existing sole action scheduler now accepts
  `follow` as well as its foundation move/dig. Product proposals expose only move
  and follow. Viewer compatibility patches and endpoint protections are retained.

Questions capture authority before inference and leave the worker revision/action
future alone. A replacement's first response establishes intent only. The app
calls bridge Stop, waits for controls cleared and observed stationarity, then
captures new authority **before a second inference**. It never relabels an old
proposal. A changed position prompts one fresh observation/replan; further drift
asks the user to retry. Stop and reconnect invalidate pending responses immediately.
Local epoch checks also cover the interval before a Stop response updates the
bridge revision. The worker still validates session, revision, bounds and duplicate
request IDs. There is no independently executing chat/planner movement queue.

State context includes observed position/yaw, health, food, inventory, nearby
blocks, observed player entities, current goal, recent messages and bounded results.
Directions resolve from those observations, not user-authored coordinates. Player
names alone in the roster are insufficient: the entity must be observed. Appended
status clarifies when an action ended while a question was being answered.

Follow protocol v1 extension: `{action: "follow", player, entity_id, duration_ms}`.
Duration is 1–25 seconds (product default 25); wrapper action deadline remains
29 seconds, below the original 30-second maximum. Target identity must match.
The target and bot must remain within 32 blocks of the follow start, and within
32 blocks of each other. Disappearance, identity change, distance overflow and
five seconds without progress away from the target end the action honestly.
Pathfinding still cannot dig, scaffold, tower or parkour. Follow is bounded, not
indefinite; another explicit request starts another interval. Inventory, tools,
resource work, durable landmarks and richer navigation belong to MC-B1-03.

Conversation is retained in `artifacts/minecraft-chat/conversation.json` (latest
500 messages, up to 10,000 accepted IDs). No goal, session or execution authority
is restored from it. Local diagnostics are in `events.jsonl` and
`worker-events.jsonl`. Do not confuse these evolving runtime logs with the retained
dated evidence directory. Context and usage are remote Codex inference; world
execution and retained conversation files are local.

## Verification

```sh
.venv/bin/pytest -q tests/test_minecraft_chat.py tests/test_minecraft_chat_ui.py tests/test_companion_ai.py tests/test_minecraft_bridge.py tests/test_lab_ui.py::test_server_routes_player_shell_and_secondary_lab
npm test --prefix minecraft-worker
```

The source launcher was exercised, not just the engineering movement harness.
[Recorded live session and measurements](mc-b1-02-evidence-20261027.md) distinguish
actual model use, observed movement, follow-probe assistance and deferred work.

Official CLI reference checked before integration:
[Codex exec](https://learn.chatgpt.com/docs/developer-commands#codex-exec).
Installed `codex exec --help` verified `--ephemeral`, `--ignore-user-config`,
`--ignore-rules`, `--output-schema`, `--output-last-message` and `--json` support.

## Exact next task: MC-B1-03

Extend this same coordinator/worker boundary for reliable navigation, resource
collection and inventory/tools. First add observed landmark candidates, explicit
protected regions, hazard checks and bounded route recovery; preserve cancellation
and the non-pausing question path. Add typed gather/pickup/equip proposals with
quantity budgets and server-observed inventory/block outcomes. Reuse the foundation
dig evidence carefully; do not enable automatic navigation digging globally.

Demonstrate “get some wood” with varied start locations/quantities, an obstructed
route, a missing resource, tool selection, pickup and return to a remembered place.
Establish Creative navigation first, then a separately scoped Survival resource
run. Retain the accepted practice world and current evidence. Do not implement the
whole crafting/building slice, resurrect Mario/Stardew work, or make the deferred
human walkthrough a prerequisite. Expand follow's bounded usability only with
explicit progress/recovery budgets. Improve CLI latency without weakening authority
capture or introducing a separate inference engine.
