# Game Companion Beta 1 — Minecraft chat and play

Updated October 27, 2026. Active product and delivery plan.

## Decisions and product promise

Choose Minecraft from the game dropdown. A live view and persistent chat open
together. Talk naturally to a companion that plays Minecraft as its own character.
Watch it work, ask questions while it continues, redirect it, and optionally join
the same world with your own character. Ordinary conversation never requires a
pause, window focus, screen capture, or control of the user's mouse and keyboard.
Codex CLI is the Beta 1 AI engine.

These are owner decisions, not alternatives still under evaluation:

- Beta 1 focuses solely on Minecraft.
- Gameplay control runs behind the scenes/headlessly through a game connection.
- The bot has its own character. The user can join independently.
- Codex CLI handles the AI conversation and gameplay reasoning.
- The second product goal is an NES emulator companion across supported games,
  not another Mario-only product. Stardew is out of the active roadmap.

This plan supersedes the narrow Mario/Stardew work order and the old Minecraft
camera/wall campaign. Preserve prior code, saves and evidence; none is a release
prerequisite. MC-B1-01/02 now have local source qualification; this does not establish an installed or complete Beta 1.

## What Beta 1 must feel like

1. Pick Minecraft. On first use, resolve the few real prerequisites in the app:
   Codex sign-in, a compatible Minecraft world/server, and connection identity.
2. Open a session with the bot's live view beside chat. State clearly which world
   and character are connected. A native Minecraft client is optional for watching.
3. Ask, for example, “Gather wood and build us a small shelter near here.” The
   companion describes its intent briefly and starts within the permitted scope.
4. Ask “Why did you pick that spot?” while it works. It answers using actual game
   state without stopping its current safe activity.
5. Say “Make it wider, and leave those trees alone.” It acknowledges the changed
   goal, cancels conflicting actions, and replans from the actual world state.
6. Join the world, move around, and ask it to follow or meet you. Your character
   and computer remain independent of the bot's control.
7. Stop the bot when desired. It cancels active and queued work promptly; stopping
   the bot does not pause the world. Resume only on a new explicit request.
8. Close and reopen. Chat, preferences, named places and outcomes remain. The bot
   reconnects, checks current state and asks before continuing unfinished work.

The screen should contain the game dropdown, world/session identity, a useful
live view, chat, a concise current activity and a persistent Stop button. Setup,
connection details and logs belong in secondary surfaces. Avoid recurring Review
and Start forms for every movement, block or subtask. A clear action request
within session permissions starts work; ambiguity or a new protected action may
need a short question.

## Beta 1 coverage

Recommended initial environment: local Minecraft Java Edition on macOS, one
explicitly tested game/server version, one bot, one active world, one owner.
Start with an app-managed local practice world/server and an embedded bot view;
add a guided connection to an owner-controlled compatible server. Existing-world
imports use a separate copy and an explicit choice. Never silently upgrade or
convert an original world. Exact versions and authentication topology are the
first implementation decision, not assumed compatible today.

Beta 1 includes a useful early-game range rather than a single scripted demo:

| Area | Required player-visible ability |
| --- | --- |
| Conversation | Answer state-aware questions, explain choices, remember constraints, interpret follow-up references and acknowledge uncertainty. |
| Travel | Walk to a named/observed location, follow the user's character, return to a saved home point and handle ordinary route obstacles. |
| Resources | Find nearby common resources, gather a requested quantity, select tools, track inventory and report shortfalls. |
| Crafting | Resolve prerequisites and craft basic materials/tools using actual inventory and available recipes/workstations. |
| Building | Build and revise simple structures with variable size/material/location, respecting protected areas and available resources. |
| Adaptation | Recover from a blocked route, missing material or changed target; ask when genuinely stuck rather than loop indefinitely. |
| Continuity | Sustain multi-step work while chatting, change goals mid-session and restore useful context after reconnecting. |

Creative mode is useful for early construction integration. It does not prove
resource gathering or crafting. Beta 1's full useful-session demonstration must
include early Survival resource/crafting work and parameterized building. This
is a planning target, not a claim that general Minecraft autonomy is solved.

Defer advanced combat, bosses, Nether/End progression, redstone, arbitrary mods,
Bedrock, public servers/Realms, multiple simultaneous bots, voice, cloud hosting,
and arbitrary unattended multi-hour play. Basic hazard detection, bounded
recovery and honest limitations are still required. The world continues while
thinking; running out of food, dying or disconnecting must have explicit handling.

## Technical approach

### Game connection and live view

MC-B1-01 implemented and locally qualified the Node worker using Mineflayer,
pathfinder and Prismarine Viewer. Exact pins and required rendering corrections
are in [the foundation contract](mc-b1-01-headless.md). MC-B1-02 connects it to
the ordinary source app and real Codex CLI; see [session evidence](mc-b1-02-evidence-20261027.md).

The bot receives server state and sends gameplay actions through its connection.
No OS keyboard/mouse events, foreground-window dependence, screenshot calibration
or mandatory Screen Recording/Accessibility permission belongs in this path.
The rendered view shows the bot's actual session. It is not its control channel.
A viewing failure can be repaired independently of the game connection, with
clear status and an explicit policy for continued background work.

An app-managed local server gives the headless bot a world even with no native
client open. A human may join that world with a separate character. Resolve
server distribution/EULA, version pinning, local-only networking, bot identity
and authentication during MC-B1-01. Do not assume one authenticated account can
be connected twice. Never weaken an existing server's authentication to make
the bot work. A local development connection is not proof of authenticated
owner-server support.

The old native Minecraft integration recorded version 26.3; the Mineflayer README
checked for this plan lists support through 26.1. Do not assume they interoperate.
Choose and verify a supported pairing in a new world; do not downgrade an owner
save. Verify viewer and pathfinder compatibility with that same pairing.

### Codex CLI and orchestration

Reuse the useful subprocess, sign-in, cancellation and response-validation work
in `codex_provider.py`, after checking installed CLI compatibility. Use Codex CLI
for both user-facing replies and higher-level game decisions. No Ollama fallback
or separate API-key engine is part of Beta 1.

Start with bounded `codex exec` requests and structured results. The application
owns the durable conversation and game context; ephemeral model calls do not
require ephemeral user conversations. Benchmark startup and reply latency early.
If process startup materially harms the experience, evaluate a persistent Codex
CLI integration, preserving the same provider interface and cancellation rules.
Do not spend the beta building a provider marketplace or choosing a different
engine to avoid integration work.

Keep three independently scheduled responsibilities:

1. Conversation: reads recent events and answers without canceling current play.
2. Goal supervisor: turns intent into a short plan, updates goals and requests
   bounded skills, then checks outcomes and replans when needed.
3. Fast game runtime: movement/path following, digging, placement, inventory
   operations, local hazard reactions and cancellation, without waiting for an
   LLM call on every tick or keystroke.

Only one action scheduler can command the bot. Chat and planning produce proposed
changes; they cannot race to move it. Ordinary questions leave the active goal
alone. A new goal advances its revision and invalidates conflicting queued work.
Stop uses a direct control path independent of model inference. Slow/late model
results cannot restart canceled work or apply to a different world/session.

Send Codex bounded structured facts: current goal, location, nearby relevant
blocks/entities, inventory, health, recent action results, user constraints and
useful memories. Don't resend the whole world or the whole transcript each tick.
World text and server messages are observations, not privileged instructions.
Codex returns validated actions through the adapter; it does not generate and
execute arbitrary code in the user's game or machine.

### Shared core and Minecraft adapter

Keep the existing Python app shell initially; connect a separate Node worker via
a versioned local message protocol. Prefer owned stdio IPC for control, with
request IDs, session IDs, goal revisions, timeouts and explicit event sequences.
The viewer needs its own loopback-bound serving path. Validate process lifecycle,
local endpoint access, reconnect semantics and duplicate-command handling.

Shared core owns chat/history, session lifecycle, goal revisions, action
scheduling, cancellation, settings, provider access and outcomes. Minecraft owns
world facts, recipes, pathfinding, concrete skills, danger rules and success
checks. Proposed adapter surface: connect, observe, capabilities, execute,
cancel, events, view and disconnect. Do not force old screen/window fields into
the new adapter contract or rewrite all legacy game adapters before shipping.

Skill results include observed changes, consumed resources, failure/partial
completion and continuation context. Completion comes from observed inventory,
position/block changes and server events rather than a fluent model reply.
Record named places, user preferences and successful approaches with world and
version identity; refresh them against the current world before acting.

## Existing work: reuse versus replace

Source inspected October 27 at `a50edad`; no gameplay or package requalification
was performed. The installed candidate.35 identity is the last documented
October 25 audit, not newly verified for this plan.

| Existing piece | Treatment |
| --- | --- |
| `codex_provider.py` | Reuse and adapt CLI discovery, sign-in, bounded requests, schema validation and cancellation. |
| `companion_ai.py` | Reuse selected context/validation ideas. Its current submission flow cancels gameplay; do not carry that behavior into ordinary questions. |
| Catalog, UI shell, local history/store, process lifecycle | Reuse selectively behind the new shared session model. Migrate data explicitly; retain old history. |
| Minecraft camera/native input/calibration | Historical implementation. Not the Beta 1 execution path and not a prerequisite to headless work. |
| Minecraft spatial/building code | Reuse useful geometry, budgets and verification concepts after adapting to server state. Do not transplant screenshot assumptions. |
| Current Minecraft feature flags | Describe the legacy path: calibration/camera enabled, aim/move/place/wall disabled. Do not flip them as a substitute for the new runtime. |
| Mario completion and emulator work | Retained proof and groundwork for the later NES companion. No Mario completion task blocks Minecraft. |
| Stardew | Removed from active product delivery. Preserve data/code/history; no new Stardew development or acceptance work. |

## Ordered delivery slices

MC-B1-01's headless source foundation passed local bot qualification October 27;
the owner deferred its human-client walkthrough. See the
[implementation/handoff](mc-b1-01-headless.md) and [evidence](mc-b1-01-evidence-20261027.md).
MC-B1-02 passed its local source and real chat/play demonstration on October 27.
[Launch, limitations and MC-B1-03 handoff](mc-b1-02-chat-play.md).
MC-B1-03 through MC-B1-06 remain not started. Each slice ends
with a usable demonstration, a focused check and an updated tracker. Early
owner feedback starts with the first connected slice; it does not wait for a
formal release campaign.

### MC-B1-01 — Prove the background game connection

Choose the exact server/bot/viewer versions and connection identity. Create a
separate test world. Connect the headless bot and show its actual live view.
Move, observe a block/inventory change and stop through a minimal local bridge.
Verify that typing in another application and changing focus have no effect on
bot control. Close/reconnect the viewer and terminate the worker cleanly.

Done: reproducible bot connection, visible world, real state/action round trip,
independent desktop use and stop; documented authentication/version choice and
server lifecycle. No Codex or polished UI required for this first proof. If this
stack fails, evaluate a game-native bridge; do not revert to screen control.

### MC-B1-02 — First real chat-and-play session

Connect the existing app to the new worker and Codex CLI. Dropdown → Minecraft →
world/view/chat must be one coherent route. Implement initial observation,
go-to/follow, current activity, streamed status, direct Stop and a clear error
state. Use a natural-language request to drive real movement, then answer a
question while the bot continues. Change its destination while moving.

Done: one complete visible session driven by real Codex CLI, with state-aware
conversation and concurrent play, no manual coordinate/configuration editing,
no window-focus dependency and no pause required to chat. This is the first
product milestone, not completion of Beta 1.

### MC-B1-03 — Reliable movement and resource work

Add navigation around ordinary obstacles, remembered destinations, digging,
pickup, inventory/tool selection and quantity tracking. Add hazard checks,
progress detection and bounded recovery. First stabilize Creative traversal,
then demonstrate resource collection in Survival from more than one start.

Done: “follow me,” “get some wood” and “return here” work with changed locations
and quantities, including an obstructed path and a missing resource. Failures
produce a useful question or truthful partial result, not endless retries.

### MC-B1-04 — Crafting and flexible construction

Add recipe prerequisites, workstations and simple structures. Let Codex choose
and revise a plan using validated skills. Start with small shelters/walls but
parameterize dimensions, materials, placement and openings. Reuse geometry only
where helpful. Add explicit permission for removal of existing structures and
preserve user-protected blocks/regions.

Done: gather → craft → build works as one requested goal. Repeat with different
materials/locations and a conversational revision during work. An exact 19-block
wall, predefined route or manually prepared inventory cannot alone pass this
slice. Observed world/inventory changes substantiate the result.

### MC-B1-05 — Sustained companionship and recovery

Complete durable chat, world-specific memory, goal summaries, background status,
reconnection and lifecycle handling. Exercise questions during play, changes of
mind, cancellation while inference is pending, death, insufficient resources,
server loss and Codex timeout/sign-in/usage errors. Keep a safe current skill
running while reasonable; when no valid continuation exists, stop the bot's work
and explain. Do not freeze the world or claim success.

Done: a 20–30 minute varied session survives ordinary conversation and redirection,
then reopens with useful context and fresh state. The user can independently join
and play. No stale action executes after Stop, world change or reconnect.

### MC-B1-06 — Deliver the usable local beta

Finish first-use setup, supported-version checks, server/world selection, viewer,
Codex status/remedies and local app packaging. Remove legacy calibration/permission
requirements from the new path. Preserve app identity and data on update. Keep
experimental and historical adapters out of the ordinary Beta 1 game choices.

Done: the owner starts the installed app without terminal work, opens Minecraft,
uses the full session, stops/closes/reopens and understands genuine limitations.
Run the complete user journey on the actual delivered build and capture owner
feedback. Broader distribution, notarization and cloud service work stay deferred.

## Acceptance and evidence

Beta 1 is complete only when all of these work together in the delivered app:

- Dropdown opens the actual Minecraft world view and persistent chat.
- Real Codex CLI decisions cause observed game changes through the headless bot.
- Chat remains usable while play continues; normal questions do not cancel play.
- Movement, resource collection, crafting and adaptable simple construction
  compose into a useful session across varied starts/goals.
- The user's separate character can join the same world without input conflict.
- Goal changes, Stop, slow inference, reconnect and app exit behave honestly.
- Session memory survives reopening without resurrecting canceled authority.
- The owner can use it without an engineer preparing coordinates or scripting
  each action, and says the full experience is useful.

For representative native sessions record time to first useful action, chat
response time, task completion/partial results, interventions, replans, Stop
latency and any engineering assistance. Initial targets: visible message receipt
within 1 second; local Stop acknowledgment/cancellation dispatch within 500 ms;
ordinary text answers usually within 10 seconds; a 20–30 minute session without
forced chat pauses. These are proposed targets to measure, not existing claims.
Server-confirmed cessation is separate from local dispatch. Set realistic
measured budgets after MC-B1-02; do not silently weaken the no-pause requirement.

Use focused tests for bridge contracts, scheduler races, validation, storage and
recovery. Synthetic tests do not establish live gameplay; live gameplay in a
source checkout does not establish the installed app. Avoid restarting an old
exhaustive camera campaign or counting tests as product completion.

## Risks and decisions to resolve early

| Risk | Resolution point |
| --- | --- |
| Current game version incompatible with bot/viewer | MC-B1-01 pins and verifies the entire stack in a separate world. |
| Bot account and user account cannot coexist | MC-B1-01 proves the chosen local or authenticated topology with distinct characters. |
| AI replies too slow or expensive | MC-B1-02 measures CLI latency/usage; use compact context and event-driven planning, with independent fast skills. |
| Pathfinding can unexpectedly dig/build | MC-B1-03 configures explicit movement permissions and protected areas before resource autonomy. |
| Minecraft changes while Codex thinks | Every action validates current state/revision; runtime handles immediate hazards and bounded recovery. |
| Generic chat hides fixed scripts | MC-B1-03/04 vary goals, starts, layouts and resources and retain actual model decisions/results. |
| Viewer renders poorly or lags | MC-B1-01 validates it early; a native client can provide a supplemental view, never OS input control. |
| Session feels like a setup console | MC-B1-02/06 test the ordinary owner path and remove coordinate/calibration chores. |

MC-B1-02 measured 3.560–6.192 second returned inference and 7.702–9.477 second
first action submission, with genuine concurrent replies. MC-B1-03 must establish
resource/recovery reliability before estimating the remaining Beta 1 delivery. A single native wall success must not be relabeled the full beta.

## Goal 2 — NES emulator companion

After the Minecraft beta is useful, add an NES emulator adapter to the same
session/chat/goal/memory/control contract. Select a local game, render emulator
frames, and control emulator input/frame stepping directly in the background.
Keep the desktop free. Support per-game knowledge and honest capability labels;
a generic emulator connection does not mean every NES game is solved.

Reuse existing emulator/Mario evidence and controllers where compatible. Prove
the new adapter with Mario and at least one materially different NES title
before claiming cross-game support. Preserve user-supplied game files and saves.
Do not build NES implementation or revive Stardew as Minecraft prerequisites.

## Sources and document ownership

This file owns product scope, target architecture, sequencing and completion.
The Desktop tracker owns the next action and slice status. Current engineering
status owns dated evidence; legacy guides describe legacy execution paths.

Primary sources checked October 27, 2026:

- [Mineflayer](https://github.com/PrismarineJS/mineflayer): protocol bot, game-state
  and action capabilities, version list and authentication examples.
- [Mineflayer pathfinder](https://github.com/PrismarineJS/mineflayer-pathfinder):
  navigation candidate; configuration and permissions need integration checks.
- [Prismarine viewer](https://github.com/PrismarineJS/prismarine-viewer): bot/world
  rendering with first/third-person options; version fit remains unverified.
- [Official Codex CLI documentation](https://learn.chatgpt.com/docs/developer-commands#codex-exec):
  noninteractive execution, JSON events and session continuation. Existing
  `codex_provider.py` provides the local starting implementation.
