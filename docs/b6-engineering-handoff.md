# B6 Mario qualification and repair handoff — September 26, 2026 UTC

The exact B6 verdict, source identity, attempt table, measured intervals, checks and limitations are retained in [the qualification report](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b6-engineering/20260926-mario/qualification-report.md) and [readiness record](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b6-engineering/20260926-mario/b6-readiness.json). B6 is technically complete within the supported boundaries below; these records retain its verification. Owner feedback and acceptance remain unrecorded; B8 delivery readiness and full-beta approval are separate.

## Candidate and preserved evidence

The initial full working tree, including uncommitted files, matched B5 SHA-256 `c10a8c6edf2738482b3e4b952395ff36aae18c0e2be714e9e3df36ed340259ba` exactly (217 files). B6 retains a new [source manifest](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b6-engineering/20260926-mario/candidate-source.json) and source archive, with the unchanged HEAD plus preserved uncommitted work. See the report for the identity of every live attempt and the runtime continuity comparison; earlier attempts are not relabeled as final-source proof.

B5's opening-hop/edit, input-audit and neutral-switch proof is reused for unchanged behavior. B3/B4/B5 candidates and failed/partial attempts remain historical records. B5 Stardew return attempts remain stopped, with return unconfirmed. B6 performs no Stardew gameplay or development. Both frozen seeds are hash-verified unchanged. No personal saves, existing configuration, commits or pushes are part of B6.

## Mario cases and repairs

| Case | Result and boundary |
| --- | --- |
| Playback speed | Normal → uncapped faster → normal has separate requests, native acknowledgments and frame/wall intervals. Uncapped is machine-dependent. The periodically sampled wall clock makes brief intervals approximate; pauses are included in wall time. Neither turbo nor choosing quickest optimizes a route. |
| Destination changes | In the same fresh compatible session, revision 1 authorizes the existing base and revision 2 changes the destination to World 1-1 exit. The exit acknowledgment identifies the executing revision; game frames show the cleared course on the world map, followed by neutral handback. |
| Saved variant | The World 1-1 exit variant preserves its primitive, base/version and stop, with an integrity hash and false stored authority. Reopening only proposes a plan. A fresh observation, compatible entry, review and explicit Start are required. Incompatible map and resumed level-exit requests are refused. |
| Player/agent transitions | Take control and paused reclaim receive native neutral acknowledgments. Reclaim revokes pending edits; Resume cannot restore authority. A fresh reviewed Start can return control to the agent at the supported opening, bounded to the opening stop. |
| Recovery | Stale displayed-plan identity and stale observations refuse edits. A late opening edit stops truthfully as boundary missed. Actual process loss clears pending work and authority, retains the incomplete attempt and requires a fresh session. No native handback receipt is invented for a dead process. |

Two concrete failures were repaired. First, a resumed opening-to-level-exit run died despite satisfying the former broad entry check. That attempt remains a death. The repaired entry contract permits only `world_1_1_opening_end` after player control at the verified opening; the level-exit and full-route objectives require fresh power-on. This is a qualification limit, not a route optimization. Fresh-session destination editing remains supported.

Second, an immediate edit after Start mistook uninitialized boot RAM for a missed opening. The runtime now recognizes only the already authenticated `fresh_power_on` checkpoint as an upcoming boundary. Other worlds, stale observations and passed boundaries retain their guards. No game state is rewritten and no accepted controller was changed.

The affected regression selection is the ordinary fresh World 1-1 destination/speed run, the resumed bounded opening, boot/late edit handling, paused reclaim, saved reopening and process loss. The accepted Lua route and its wrapper are unchanged. Broad historical World 8 campaigns would not qualify these changed entry/command contracts and are not rerun for documentation.

## Ordinary use and recovery

Open `Open Game Companion.command`, choose Mario, then **Open Mario for companion play**. Review an existing-base plan and Start. Quickest and 100% remain explicit base fallbacks; full-completion coverage remains unknown. Supported edits concern the upcoming World 1-1 opening path and stop point, bounded by the original authorization. Chat focus does not grant keyboard input to Mario.

For a saved route, expand **Save or reopen a route**, Reopen, inspect its contents and Start only from a fresh compatible observation. Reopening never restores permission. After Take control, an observed World 1-1 opening permits a newly reviewed opening-stop plan only. To reach the level exit or run the full base, close the old qualification game and open a fresh session, select/reopen and review the plan, then Start. Arbitrary manual states are unsupported. Stop and Take control remain immediately available.

After process loss, the old process cannot receive further input. Its missing native acknowledgment remains explicit. Open a fresh session; do not reuse old pending commands or Start identities. Qualification-process cleanup and independent OS input checks are retained separately from the game's outcome. Earlier attempts whose normal termination did not close FCEUX were explicitly terminated after verified handback; this is cleanup, not completion.

## Next unfinished stage

**B7 expansion guidance** is the next unfinished stage: concise supported-game/setup guidance and a practical future-adapter/testing plan. No third working game or third-game campaign is required. B8 identified delivery qualification and B9 neutral owner review remain separate and unfinished. Technical completion never fills owner acceptance.
