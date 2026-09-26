# Mario player guide

Start with [launch and first use](../README.md#launch-and-first-use), then choose Mario. The ordinary conversation workspace is at `/mario`; the Lab is for engineering.

Before opening a session, the setup card must recognize a supported local game file and find FCEUX. If needed, select the local game-file path through first-use setup; the saved selection or `SMB3_GAME_FILE` supplies it on later launches. Confirm normal keyboard/controller mapping for player control. A missing file, unsupported identity or unavailable emulator must be resolved in setup; repeated launch does not bypass the check.

## Review and Start

Choose the existing base, **Quickest**, or **100% clear**, or type a request. All initially load the same existing `world_8_finish_game` base. Quickest is an existing-base fallback, not an optimized route; full-completion coverage remains unknown. Review the actual path and stop, not just the requested objective.

Choose **Open Mario for companion play** to open a visible FCEUX session held at the fresh boundary. **Review plan**, inspect the proposal, then **Start reviewed plan** grants permission in that session. Selecting a route, opening Mario, asking a question or reopening history never starts execution. The local bounded English planner needs no model account or credentials.

## Supported paths, destinations and changes

| Choice | Supported destination and entry |
| --- | --- |
| Default opening / base path | Opening end, World 1-1 exit, or existing base ending from fresh power-on |
| Opening hop | Opening end only; later traversal is not qualified |
| Return from player control at the verified World 1-1 opening | A fresh observation, review and Start may authorize only the opening stop (`world_1_1_opening_end`) |

**Longer traversal after taking control requires a fresh session.** A resumed opening-to-level-exit attempt died in B6 and remains a failed attempt. The current guard refuses that request. Close the old game after handback, open Mario afresh, select/reopen the desired plan, review and Start. Arbitrary map, later-level or manually positioned states cannot substitute for a compatible entry.

Useful requests include:

- “Take the opening hop, then stop after the opening section.”
- “Use the base path and stop at the end of World 1-1.”
- “Actually, use the default opening path.”
- “What if we take the opening hop?” (advice only).
- “Cancel the pending change.”

Opening edits must arrive before their supported boundary; destination changes remain inside the original authorized scope. Inspect pending/applied revision acknowledgments. A late or stale edit is refused or stops at a missed boundary; it never rewinds the game. Canceling a pending change affects only unexecuted work. A material scope change requires the displayed Apply decision.

## Speed and player control

Playback offers **1× normal** and **Faster, uncapped**. “Use normal speed” and “Use turbo speed” are supported; fixed 2×/4× rates are not. Inspect requested versus acknowledged speed. Measured frame/wall intervals are approximate, include pauses, and depend on the machine; uncapped speed is not route optimization.

Mario can keep playing its approved plan while you type in Companion: chat keystrokes are isolated from game input. **Pause** holds the current session; **Resume** is usable only while that paused authority remains valid. **Stop** or **Take control** releases input and revokes pending commands. Reclaim while paused also invalidates Resume. Starting again requires fresh compatible observation and review, with the opening-only resumption limit above.

## Saved variants, results and recovery

Expand **Save or reopen a route** to save a named variant or Reopen it. A variant stores its base/version, actions and stop; it stores no gameplay permission. Reopen proposes a plan, then checks integrity, compatibility and fresh state. Review and explicitly Start. A saved variant is not automatically accepted, fastest or reliable.

A completed opening stop means that bounded stop completed; it does not mean the full base or a 100% objective completed. Death, lost process, reclaim and missed boundaries remain distinct partial/stopped results. After process loss, open a fresh session; old edits and Start identities cannot be reused, and no native handback receipt can be supplied by the dead process. See [shared history and recovery](../README.md#history-recovery-and-safe-shutdown).

The older Observe/Tell/Show/Do and History surfaces remain available. Observe only is read-only; Tell advises; Show is a separate review-only demonstration, never your completion. Their availability does not broaden conversation entry or destination limits. Technical evidence: [B6 handoff](/Users/michaelfuscoletti/Desktop/beat-mario/docs/b6-engineering-handoff.md). B6 is complete; owner acceptance and delivery remain separate.
