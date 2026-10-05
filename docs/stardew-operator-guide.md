# Stardew companion guide

## Current abilities and the private-beta target

Watering, passive planting discussion and the eastern-margin inspection have real
source-gameplay evidence on the supported prepared farms. They use deterministic
language handling, calibrated perception and authored routes. They do not yet
establish the intended AI companion. Cave conversation and a registered
manual-route foundation are implemented; the complete ordinary cave activity
remains unverified.

The next priority is a Codex-backed conversational interpreter and a separate
gameplay reasoning role. One understands the player's own wording and goals; the
other interprets current observations, chooses supported actions, checks results
and changes its plan when conditions differ. Both may use the same Codex provider.
The app owns controls, protection and immediate Stop.

These roles must affect real play before the initial private beta is complete.
The first proof is a useful Stardew activity with a changed preference or gameplay
condition handled by observation and replanning, without a new script for that
individual case. This is planned work. See the [integration
contract](b3-integration-contract.md) and [engineering plan](private-beta-engineering.md).

## Farm Cave status: ordinary activity unverified

You can discuss a cave destination and receive clarification and setup guidance.
The earlier survey reached the western farm and showed the exterior but did not
complete a round trip. Newer local route evidence records a manual tool-free
approach and return with 15 dry crops, energy 270 and water 40 unchanged. Its
[qualification record](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/gc3-cave/20261004-completion/manual-route-qualification.json)
explicitly marks the ordinary activity unverified. That manual walk is not proof
of companion delegation through request, approval, findings and return.

The current implementation separates arrival, fresh findings, return and handback
and treats off-screen crops as historical. It requires its installed route and
current observation guards before offering travel. The route remains an
experimental source capability; no completed ordinary-interface acceptance is
claimed here. Those controls remain useful foundations, but the active next work
is the shared AI decision-and-replanning loop rather than another fixed cave route
as the beta completion criterion. The [cave verification
record](gc3-cave-verification.md) retains the earlier partial-survey checkpoint;
the linked newer qualification records only its manual route scope.
Interior exploration remains later. Recording stays deferred to tentative beta v2.

## GC3: discuss where to plant

Prepare and connect the matching disposable **Pilot/B3Test Day 2** or **Pilot/B4Test Day 5** farm as described below, with daylight, 75% zoom and 100% UI. Stand at the supported porch viewpoint and ask **“Where should we plant corn?”** The companion focuses and captures the farm without game keys, clicks, inventory access or character movement. It shows numbered candidate tiles beside the starter crops/below the mailbox, outlines the recommendation and explains terrain, access and season suitability. Corn cannot grow on the observed spring farm: discuss a summer plan or ask **“Actually, parsnips instead”**. Try **“Why?”**, **“What about another spot?”**, **“Closer to the crops”** or **“Below the mailbox”**. Only corn, tomato, parsnip and green bean rules are currently supported; that does not identify existing crops as those species.

Suitability is for a single location and future preparation: observed bare dirt still needs tilling in a later activity. Existing crops and vegetation remain protected; porch access stays clear, especially for a blocking bean trellis. Changed or hidden pixels, missing access and unreadable season/day are explicitly uncertain. Candidate positions are calibration search locations; current images must match before any recommendation. On Day 2 you can request **“Inspect the eastern crop margin”** for a separate reviewed walk. Unqualified areas remain unknown. Seeds, tools, water and energy are not inspected by this passive survey.

Location discussion cancels an earlier work review. **Yes** chooses no farm action, and Review/Start stay disabled for the recommendation. Saved location discussion reopens the explanation, image and conversation as historical information without authority; ask again for a current survey. New farm/profile setup makes prior recommendations historical. Stop/Take control retain their existing priority.

See [planting verification](gc3-planting-verification.md) and [inspection verification](gc3-inspection-verification.md) for current-source live evidence and separate retained-frame checks. Arbitrary farms, larger plots, planting, terrain clearing, purchases and caves remain outside this activity; recording stays deferred to tentative beta v2.


## GC3: inspect a second planting area

From the connected Day 2 porch, ask **“Inspect the eastern crop margin”**. The displayed proposal describes the path past the mailbox toward the eastern crop patch, the two margin tiles to inspect and a **120-second limit including return to the farmhouse**. Review scope, then Start, or approve the displayed version with **“yes”**. Approval permits this navigation and observation only. Unsupported destinations refuse; a changed request cancels the old proposal.

Companion walks the qualified cardinal corridors, takes a fresh image at the eastern viewpoint and reports bare ground, protected vegetation or unknown terrain. These two tiles add coverage beyond the porch recommendation survey. Their planting access remains unknown; inspection does not certify a larger plot. It returns along the qualified route. Typing a discussion or Stop releases input and gives handback status; an interrupted return remains incomplete. Request a new inspection and approve again before continuing. Saved findings/image reopen as historical, with no plan or control authority.

### Preparation without native app attachment

Under Farm setup, expand **Prepare through Companion when native attachment is unavailable**. Open a fresh copy, then **View preparation screen**. Wait for the title menu; choose Load. Refresh after the loading animation and choose the displayed Pilot farm. Check the bedroom image, walk left for 0.8 seconds, and use a 0.1-second nudge to align with the door. Walk down for 0.8 seconds, then inspect the porch image. If slightly below the entrance, use the 0.05-second upward nudge; the 0.015-second up/down adjustment provides finer alignment. Select the watering can to move the game pointer away from the house recognition anchor, Check isolated farm session, then connect the offered profile. The checker requires the actual qualified entrance and full resources; it refuses a misplaced player.

Every preparation button approves only its named step on the displayed isolated game. Check each returned image before another step; movement releases after its short pulse budget. **Pause clock between survey steps** captures an unobstructed image and pauses the game while you review it. End that preparation pause with **Toggle game menu** before Check isolated farm session. Stop interrupts remaining pulses. These controls do not use native app-name attachment. After connection, View and Toggle game menu remain available to pause the clock during long breaks; movement preparation is disabled. Closing the game menu is required before a farm observation.

## GC3: ask to water the dry patch

On the qualified **Pilot/B3Test Day 2 disposable farm**, follow the fresh-copy, Load, porch, selected watering-can and screen-connection setup below. Ask **“Please water the crops”**. Companion observes the current dry patch and describes its targets using visible relative locations. No plot IDs or coordinates are needed. Several separate patches require a selection/location clarification. Already watered crops are skipped; uncertain identity is described as observed crops rather than guessed tomatoes or corn.

Read the target list, water/energy, reserve, route and **two-minute** limit. Choose **Review scope → Start reviewed work**, or send **“yes”** to approve the displayed current plan. Start rechecks the game; changed conditions require a new proposal. Watering and return share the two minutes, so a time limit can leave work or return unfinished. Tool selection and refill are manual prerequisites: follow the remedy, observe and review again.

Typing, asking **“what is left?”** or **“How much is left?”**, correcting the plan, Pause, Stop or Take control releases native input. Read confirmed progress and handback. Returning to the game does not resume work. Ask **“Water the remaining crops”** from a qualified clear viewpoint or an already-qualified cardinal corridor, inspect the revised dry targets and approve again. Saved results retain the plan, observed work, remaining/uncertain work and handback after reopening; reopening grants no gameplay authority. Already wet baseline crops are not credited as newly performed work.

This source activity still uses the prepared farm's qualified viewpoints/settings. Its completed current-source watering/discussion/Stop/reopened-result check is in [GC3 watering verification](gc3-watering-verification.md); earlier Day 2/B4 successes do not qualify this new conversation. Day 5 combined routines below remain separate. Arbitrary farms, automatic refill, tomato/corn identification and cave exploration are unsupported. The planting discussion and eastern inspection above have separate Day 2 live evidence.


Guide for the implemented, locally prepared Stardew adapter configurations, with the corrected product target agreed October 3, 2026. The [private-beta quick start](private-beta-quick-start.md) describes retained engineering review packages; the [private-beta engineering plan](private-beta-engineering.md) owns next-session priorities and release scope.

## Product target for the initial beta

Stardew is the second initial-beta gameplay priority, after Mario. Its purpose is to let the user delegate activities through conversation and have Companion handle the clicking. The intended experience is: describe a goal → discuss a short plan for the next few minutes → explicitly say yes → watch it act → read what happened → discuss or correct the next activity.

Owner examples are “lets explore and find a good spot to plant corn”, “time to water the tomatos” and “lets go explore that cave”. These are product acceptance targets, not a list of currently supported requests. Companion must interpret the goal, observe the relevant game situation, propose useful actions and ask for a choice when needed. Finding a planting spot includes discussing its suitability; cave exploration needs its own implemented navigation and activity support. A recognized phrase or seed name does not establish an ability to perform the task.

The next engineering sessions must connect actual model interpretation and
gameplay reasoning to observed state and reusable actions. Broader calibration or
one more authored route alone does not complete the product. The companion should
choose useful subgoals, inspect what is uncertain, verify progress and replan
within its approved scope. An explicit yes authorizes the displayed current scope;
material expansion or revoked authority needs a new decision. Stop and Take
control remain immediately available, including while the model is working.
Talking during native-input play releases input safely and preserves confirmed
work for a revised continuation.

The prepared routines below are real gameplay foundations. Watering, planting
discussion and eastern inspection retain their separate supported coverage.
Arbitrary farms, tomato identification/watering and actual corn planting remain
unsupported; ordinary cave delegation remains unverified. The [Stardew integration
contract](b3-integration-contract.md#next-engineering-work-and-initial-beta-acceptance)
defines the AI state, skills, replanning and release requirements. Future
owner-save support requires backup/copy isolation and a suitability check; this
guide currently uses prepared disposable farms only.

## Currently implemented prepared-farm path

Use [launch and first use](../README.md#launch-and-first-use), then choose Stardew Valley. Support is restricted to two locally prepared Standard Farm configurations. Live setup requires prepared seeds, profile registrations and their matching calibration files. These are ignored local assets and are not bundled by cloning the source or running the launcher. Without them, the CLI can inspect declared capabilities but the browser cannot start qualified farm work.

## Choose the matching farm and profile

| Configuration | Prepared source | Matching profile | Qualified work |
| --- | --- | --- | --- |
| Pilot / B3Test Farm · Day 2 | `pilot-day2`; 15 dry starter crops | `pilot-day2-75pct-v1` | Water all 15 initially planted crops, reconcile resources, return to farmhouse entrance |
| Pilot / B4Test Farm · Day 5 | `b4-day5-v1`; two mature parsnips and 13 owned seeds | `b4-day5-screen-v13` | Selected ordinary parsnip harvest, plant owned parsnip seed, water the new crop, clear the selected small stone, reviewed farmhouse return |

Day 2 seed hash: `1a71568b81ebb901c5fc289d4c2bfb0972db8c05325463a7487dad549eae3128`. Day 5 seed hash: `5bddd72e537c6888e3623c5cb66c819bf1add0b28bc75f179fb6b97f25e35eaa`. The local registry is `artifacts/stardew-prepared-farms.json`; profile pointers are `artifacts/stardew-qualified-profile.json` and `artifacts/stardew-qualified-farm-profiles.json`. They reference retained calibration, loading and persistence evidence. Missing or mismatched files block setup; selecting another profile is not a workaround.

Both require the qualified display: **Windowed Borderless, 3024×1964 display, 1512×949 capture at (0,33), 75% zoom, 100% UI, locked toolbar, tool-hit location marker, default WASD controls and daylight**. Other lighting, farms, layouts and display settings are unsupported. The local inspected Stardew executable/runtime (bundled .NET 6.0.32) must match the launch guard. On Apple Silicon its Intel runtime may need locally installed Rosetta. Screen capture and ordinary input require the relevant macOS permissions for the launching process.

## First use

1. Close the previous isolated Stardew game after stopping input. Choose the exact prepared farm, then **Open fresh copy of prepared farm**. The launcher creates a new isolated working copy; it preserves the frozen seed, uses a separate configuration/data namespace and denies primary-save access. Never point it at a personal save for this workflow.
2. Choose **Show game window** if the isolated game is behind another window. In the game, choose **Load → Pilot/B3Test**, walk left from the bed to the door, then down onto the porch. Click the watering can in toolbar slot 3. These are manual preparation steps. Use daylight, zoom 75%, UI 100%, locked toolbar, hit marker and default WASD. For long breaks, open the game menu to pause its clock. Companion release alone does not stop time. If night makes the supported view unrecognizable, exit to title without sleeping/saving and reload this disposable Day 2 copy.

   **Reconnect open disposable game** explicitly attaches the one still-running isolated game after a source restart. It never restores a plan or gameplay permission. After reconnect, show the game and complete verification/connection. An already altered farm cannot pass the fresh-copy setup check: preserve its evidence, then reload the unchanged disposable Day 2 save or open a fresh copy.
3. In Companion, choose **Check isolated farm session**, then the matching **Qualified profile for this session** and **Connect qualified screen profile**. These checks bind fresh process/window/copy identity and visible supported state; no permission to play is restored. If a check fails, use its stated reason instead of overriding it.
4. Observe the farm and ask “Please water the crops.” Inspect the proposed dry patch, resources, return and two-minute bound. The full observed planted set remains the protection/accounting boundary, even when you choose fewer dry targets.
5. For Day 5: “Harvest farm--1-3, then plant parsnip seeds on farm--1-3, then water them and clear farm-0-5 and return to the farmhouse entrance.” Inspect the selected left parsnip (`farm--1-3`), one owned seed, watering of the newly planted crop, selected small stone (`farm-0-5`), protected neighboring crops, zero purchases and return. A correction such as “Leave at least 20 energy” still requires checking the entire plan.
6. Choose **Review scope**, then **Start reviewed work**. Keep Stardew foreground and let the bounded routine run. The UI brings forward only the verified game process for Start/observation; polling does not steal focus. Chatting in another foreground window during execution stops farm authority, unlike Mario's scoped input path.

## Results, guarded stops and recovery

Progress counts only when fresh visible evidence confirms the action and its resources. Already wet crops or already satisfied steps in a new observation are a starting condition, not actions performed again. A sent click alone cannot prove a harvest, planting, watering or cleared stone.

**Pause**, **Stop** and **Take control** release companion input and revoke authority. Stardew has no automatic resume from refocusing: obtain a fresh complete supported view, Observe, request only remaining work, review and explicitly Start. Pause stops companion input, not the game clock; after handback use the game's Escape menu for a long break.

Occlusion, stale screenshots, unknown resources, unsupported positions or changed process/window identity can produce a guarded partial stop. For example, all requested farm actions may be confirmed while the farmhouse return remains unconfirmed. Inspect **Outcome** and **Saved results** separately for confirmed work, remaining work and uncertainty. If stopped between supported viewpoints, take player control to reach a clear supported position before observing/reviewing again, or close unsaved and open a fresh disposable copy. Do not blind-retry the whole routine in a changed farm. A new copy starts from the prepared seed, not from the unsaved stopped attempt.

Retained watering and combined-action successes apply to their exact source and configuration. The September 26 final-return repair completed one fresh Day 5 four-action routine, return and independent input-release check on source `ed84e02a095d00df858cfd286fa458fb85267f983561b36483a5dfb712653b94`. It did not turn earlier stopped attempts into completed ones or qualify later source changes, an arbitrary farm or a packaged beta. Day 2 and Day 5 retain separate seed/profile/evidence identities. See the [delivery record](b8-personal-delivery.md) and [repair closeout](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b8-final-return-repair/20260926/closeout.md) for the identified source and review limits. Check an exact package's manifest and owner review before describing its Stardew availability.

The public CLI remains inspection-only. Inspection commands do not select or copy a save, open a game or send input:

```bash
.venv/bin/python -m smb3_agent stardew status
```

## Limits and evidence

Qualified Day 5 targets are the selected left ordinary parsnip and small stone only. Other plots/crops, regrowth, quality/bonus yields, other debris/tools, automatic refill, purchases, sales, gifts, discards, story choices and sleeping/saving are outside this live scope. Unknown resources stay unknown. Tell is input-free; Show is review-only; neither establishes completion or Do authority. Setup copying is not live game observation: current truth comes from supported visible screenshots, never save parsing or hidden game state.

## What the AI private beta must add

Within its declared supported farms and activities, the companion must understand
new wording, interpret fresh scenes, choose reusable actions and change its
approach after an observed problem. It must explain the intended work and limits,
show confirmed progress and remember useful results for another compatible
activity. A changed crop request must use season and terrain knowledge; a changed
target or blocked approach must affect the actual selected actions.

Prepared farms can bound initial coverage, but each task variant must not require
new coordinates, templates or a route script from the player or an engineer.
Some conditions will still be unsupported. The app should explain the limit or
ask for a useful observation, rather than suggesting it completed unavailable
work. Examples in this guide are suggestions, not the only recognized language.

The release walkthrough must use the exact local app artifact, including its
Codex setup, game connection, observations, model decisions, native actions,
interruption and saved reopening. Existing source-gameplay records do not prove
that artifact. Personal saves remain protected, and reopening never restores
control. Recording and no-code addition of new games remain later work.

[Shared history and shutdown](../README.md#history-recovery-and-safe-shutdown) explains switching and canceled reviews. The [Stardew integration contract](b3-integration-contract.md) describes engineering interfaces. Historical qualification and repair records are linked from the [delivery record](b8-personal-delivery.md).
