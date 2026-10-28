# Minecraft companion

The companion runs a headless bot with its own character in a local Java practice
world. A live view and persistent chat share the workspace. It uses the configured AI provider to
interpret requests and bounded worker skills to execute them; it does not control
your desktop keyboard or mouse.

## Start and connect

Install the source dependencies in the [quickstart](../README.md#source-launch).
Gameplay requires Java 21, the Node version in `minecraft-worker/.nvmrc`, the locked
worker dependencies and an explicitly [configured AI provider](ai-provider.md). Open the app or local source server,
choose Minecraft and a practice mode, then **Open retained world**. Wait for
Connected and the live view. Use **Check setup again** after fixing prerequisites.

On an empty profile, expand **Create a new practice world**, read the Minecraft
EULA, accept it if you agree, and explicitly create the world. Creation does not
replace retained or damaged worlds. No Screen
Recording or Accessibility permission is required for this headless path.

## Requests and limits

Try “Remember this place as camp”, “Gather four oak logs and return to camp”,
“Craft a total of 32 birch planks”, or “Build a small wooden shelter near here”.
Ask questions while it works. Clarify ambiguous places, material changes and
removal permissions before construction; a remembered structure is historical
information until inspected again.

Movement is bounded to 30 blocks per request. Following uses an observed player,
lasts at most 25 seconds and stays within 32 blocks. Resource trips and construction
have action, time and failure limits; partial results are normal when terrain,
resources or travel are infeasible. Shelters support bounded dimensions, wood
variants, doors/windows and revisions. Work consumes inventory and verifies effects
against server observations. Protection areas constrain changes to named locations.

The current experience targets local practice worlds. General combat/progression,
Bedrock, arbitrary servers and unrestricted autonomy are unsupported. Stone-tool
chains and hostile survival are not established as reliable ordinary workflows.
The bot owns its character; the companion does not attach to your player's controls.

## Stop, reconnect and recover

**Stop** cancels work and inference. Requests sent while Stop settles retain their
draft; wait for confirmation and send again. Closing the view leaves the bot
connected. **Reconnect** cancels work and establishes a fresh connection. Reopening
restores conversation and descriptive memory, never permission to resume a goal.

Use the app's Quit action to save and close its owned server. For the background
source launcher use `Stop Game Companion.command`. Closing a browser alone does
not stop the server. Do not terminate unrelated processes to clear a port conflict.

If the viewer fails, use Stop and then Reconnect. Damaged companion memory blocks
new work and offers saved generations under Session details. Stop and wait for
inference to settle before explicitly restoring one. Missing world files require
restoring a matching backup, not creating over the damaged directory. Keep the
world and its identity together; do not merge histories from different worlds.

## Storage and support

Installed macOS data lives under `~/Library/Application Support/Game Companion/`.
Source defaults and `GAME_COMPANION_USER_DATA` are described in
[runtime configuration](runtime-and-configuration.md). Companion data is JSON/JSONL;
the Java server owns world files. Copy stopped, consistent app data before manual
recovery. A source change does not update an installed application automatically.

The local feedback form exports reports locally; it does not send them to a service.
Review logs before sharing them because they may include conversation and world
context. See [security](security.md) and [recovery](error-handling.md).
