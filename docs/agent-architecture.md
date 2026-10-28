# Architecture

## Minecraft request flow

The loopback HTTP server in `lab_ui.py` serves the Minecraft document and script,
and dispatches chat commands to `MinecraftChat`. The coordinator owns session
identity, revisions, cancellation, inference and goal admission. Its lock and epoch
prevent late results from granting action authority after Stop or reconnect.

`minecraft_planning.py` owns model schemas and pure context/movement transformations.
It formats observations and world-scoped descriptive history for the configured local HTTP model without
performing I/O or authorizing actions. `minecraft_goals.py` and
`minecraft_construction.py` coordinate bounded work. `minecraft_bridge.py` transports
requests to the Node worker, whose scheduler is the sole owner of game actions.
Worker skills verify server effects and inventory changes rather than trusting a
model's claim that work completed.

## Persistence and lifecycle

`minecraft_delivery.py` owns data paths, supported server version and retained-world
eligibility. `minecraft_practice.py` owns the practice server lifecycle. The Java
server owns world files; `minecraft_memory.py` owns validated companion JSON,
atomic replacement and previous generations. The coordinator serializes writes.

Reopening restores conversation and descriptive facts, not a connection or permission
to resume. Observations, selected world/dimension, goal revision and current authority
must agree before action. Canceling a Python reply Future is not gameplay Stop.
Reconnect invalidates old work; Stop remains independent of model inference.

## Presentation and packaging

`minecraft_chat_ui.py` renders HTML and page styles; `minecraft_chat_script.py`
contains the separately served script. Both are importable Python assets, allowing
source and frozen applications to use the same resource path. Shared visual tokens
come from `glass_ui.py`. `app_runtime.py` owns the desktop entry point and helper
allowlist; the source launch/stop scripts manage their own local instance.

## Older integrations

Mario uses FCEUX, observed state and bounded controller plans. Stardew uses selected
save copies, calibrated observations, resource accounting and guarded native input.
Their conversation services retain separate authority. Profile-based references
use the shared companion core; Experimental adapters remain declarative fixtures.

Native workflows need explicit setup and fresh observations. Saved plans, readiness,
coaching and outcomes never restore input permission. Scenario and reliability tools
retain their own typed contracts rather than serving as general gameplay authority.

See [module ownership](ssot.md), [runtime configuration](runtime-and-configuration.md),
[security](security.md) and [development](development.md).
