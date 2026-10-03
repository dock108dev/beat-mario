# Retained Game Companion review-package quick start

Updated October 3, 2026. This is the operating guide for retained local Apple Silicon engineering review packages. **No retained package demonstrates the corrected initial-beta Mario coaching and Stardew delegation experience.** Upcoming product work is in [product direction](product-direction.md), the [PM handoff](private-beta-pm-handoff.md) and the [engineering plan](private-beta-engineering.md).

For existing Mario and Stardew source-checkout workflows use the [Mario player guide](mario-player-guide.md), [Stardew guide](stardew-operator-guide.md) and [source launch instructions](../README.md#launch-and-first-use). They distinguish narrow current support from planned coaching/activities.

Private.2 exact app: `/Users/michaelfuscoletti/Desktop/beat-mario/dist/private-beta/0.2.0-private.2/Game Companion.app`; version `0.2.0-private.2`, bundle build `20002`, source SHA-256 `230c206e51a46014e457458a8e4c0036cbd501f9a3e228f04103f1d70473fa60`. Its adjacent manifest, Quick Start and Owner Review identify actual package abilities. It supports Minecraft calibration/small camera tasks; aim/move/place/wall Start remain unavailable. Its guide/checksums are preserved.

Current source adds Minecraft setup progress, protection persistence, direct-control/drafting fixes and stricter observation/deadline checks. The October 1 1,327-test gate verifies that source, not a new package. The operating steps below do not update a retained app or qualify current gameplay. See [review records](private-beta-review.md).

Minecraft connection/calibration is retained preparation for the later third-game beta stage. The wall/building sections describe unavailable future work. Initial-beta engineering now delivers Mario watched/coached learning, then Stardew approved activity delegation. Advanced-user no-code onboarding follows implementation of those experiences; no teaching demonstrations are requested now.

## Install and permissions

1. Copy the reviewed **Game Companion.app** to **Applications**, keeping the build manifest and guide. This local build is ad-hoc signed and not notarized. If macOS blocks it, verify the copy with the owner and use the normal **Privacy & Security → Open Anyway** flow for that reviewed copy. Do not disable platform protection.
2. Open the app. It opens **Setup & profiles** in your browser at `http://127.0.0.1:8765/setup`. Opening the app grants no gameplay authority. An incompatible existing app instance must be quit through its own **Quit Game Companion** button first.
3. Enable **Game Companion** in macOS **System Settings → Privacy & Security → Screen & System Audio Recording** and **Accessibility**, then quit/reopen. Missing permissions are reported; the app does not silently grant them. Fresh-machine installation and permission setup still need tester feedback.
4. Install the game separately. No game assets, worlds, account credentials or model weights are bundled. Minecraft's narrow typed requests do not require cloud inference. OpenTTD additionally requires local Ollama with **gemma3:4b**, installed through Ollama and running locally.
5. Choose a game, name your setup and **Save profile**. Open, rename/change notes, duplicate, export/inspect and import through the app. Profile edits cannot add an unsupported capability.

**Current review limit:** calibration and camera tasks are available. Aiming, nearby movement, additions and wall Start are unavailable in both retained private.2 and the current source. Treat the building preparation and requests below as engineering preparation for a future building-capable app. The first executable Minecraft practice in this review app is the small camera task.

## Minecraft: connect and practice

1. Use **Minecraft Java 26.3 vanilla** and a dedicated **Creative** disposable world with flat full-block ground. Personal worlds, multiplayer and Survival are outside this beta path. Keep the selected game unobscured, with the browser on another display or away from the game.
2. Quit Minecraft. In Setup choose **Apply supported Minecraft settings**. The app backs up your options/debug preferences before applying sensitivity **50%**, FOV **70**, inversion off, fullscreen off, GUI scale **Auto**, English/default font, advanced tooltips, an always-visible pose/target HUD, inventory **E**, and an unassigned smooth-camera key. Restart Minecraft. Preference backups are listed under the app's local settings-backups directory; applying setup never edits a world.
3. Open the disposable world. In its Creative inventory select **Building Blocks**, put **stone, bricks, oak planks or cobblestone** in the first hotbar slot, select that slot, then close inventory. The app inspects the actual Creative frame and selected-slot tooltip. A profile declaration or request is never material/mode evidence.
4. In the app open the Minecraft profile, **Refresh Minecraft windows**, choose the exact single-player window, choose a connected display, then **Move and size selected window**. The supported window is **854 × 508 points**, captured at native **854 × 508** on PHL or **1708 × 1016** on Retina. Changing display/size or restarting the game requires recalibration. Other layouts/fonts/scales are unsupported.
5. When the Mac is available for exclusive input, check **disposable Creative world / exclusive input**, choose **Calibrate camera**, keep the page open and do not touch mouse/keyboard. Calibration measures eight small signed responses, checks cancellation and settling, and preserves an inspectable attempt on failure. Connect the resulting current calibration. Old engineering receipts are unnecessary.
6. Begin with **Enter chat safely** → “Look right 2 degrees, then stop.” → read the actual angles and whole-task budget → **Review current scope** → **Start reviewed task**. Only families listed as available can Start. Questions never issue input. Stop and Take control remain directly available.

## Minecraft: retained future building preparation

This section preserves one future GC5 building case. It is not an enabled wall walkthrough for private.2 or the current initial-beta delivery requirement. In the corrected source, **Minecraft setup progress** shows what is completed, the next setup action and available tasks. The retained app predates that progress display.

For block work, select a supported full cube manually. Point near the center of a reachable ground-block top and choose **Check visible block and scope**. The selected ground block is the center beneath the doorway; direction **X** means east/west and **Z** north/south. Review the actual world coordinates, held material, protected cells and nearby stop point. **Save checked region** stores configuration only.

For the **7 wide × 3 high × 1 thick** wall, stand on a flat platform one block above its ground, opposite the center, with all seven columns within reach. Keep animals and other moving objects away; collisions can move you and stop a task. The placement implementation checks independently observed adjacent support faces, including side support for the doorway lintel. Only families marked Available in the app are executable. It cannot build the platform for you, jump or fly to a better position, break an obstruction, or choose/change your inventory. Mark each relevant exposed block of a structure with **Mark pointed block protected**. Advanced coordinate edits describe intent; Start still needs actual observations of those cells.

Examples, subject to the workspace's checked availability:

- “Tell me what you can do.” No input.
- “Look right 2 degrees, then stop.” Small camera correction, **0.3–15 degrees** on one axis.
- “Aim at the visible reachable full-block face.” Check visible scope first; the final face is independently observed.
- “Move forward 0.25 blocks.” **0.05–0.5 blocks** on inspected flat ground with body clearance; blocked/unknown paths stop.
- “Place one oak plank block.” Uses the reviewed work region and actual selected material; exactly one addition attempt before observation.
- “Finish a 7 by 3 wall with a centered 1 by 2 doorway; leave the marked structure alone.” Requires an actual checked region and marked protection when requested. There are **19 occupied target cells and two empty doorway cells**. Different dimensions require clarification.

Already correct blocks and newly placed blocks count separately. Empty doorway and protected surfaces are inspected separately. A posted event is not success. Unknown/occluded cells, uncertain material/pose, contradictory response, changed settings/window or exhausted total budget produce a **partial** result. A placement with an unknown effect is never retried blindly. Expensive planning stays outside the feedback loop.

Changes or corrections cancel the old review. Send a new request and review its future scope. Saving/reopening restores configuration, notes and history, never live authority, a current observation or an old reviewed plan. Reconnect and inspect the region again after reopening. Availability does not imply broader configurations or sustained reliability have been qualified.

## First OpenTTD task

1. Use **OpenTTD 15.3**, English, a disposable company/save, paused with cash and loan each **£100,000**. Open **Finances** and keep it unobscured. The supported game area is **1280 × 1024** (1280 × 1056 including the Mac title bar).
2. Open your OpenTTD profile and its workspace. Refresh/select the exact window, choose a display, **Set supported size on selected display**, confirm the disposable supported setup, and connect. The app independently checks the entry balances and repayment label.
3. **Enter chat safely** → “Repay exactly £10,000 once. Do not borrow money.” → **Review scope** → **Start reviewed work**, with exclusive Mac input.
4. Read the independently observed cash/loan changes and handback. A new repayment requires a fresh disposable entry state. The preserved private.1 package passed this path in 38.1 seconds on PHL; it was not repeated as part of Minecraft integration. Arbitrary balances, borrowing, building and general management remain unavailable.

## Stop, recovery and troubleshooting

**Stop / Take control** revoke authority before task locks and inference. Wait for confirmed release. To type, use **Enter chat safely** first. Closing/leaving the workspace or missing its heartbeat stops native work. **Quit Game Companion** performs verified cleanup. Unconfirmed release blocks new work until Take control establishes release; inspect diagnostics before continuing.

The corrected source locks the request field when native work starts and keeps pointed protection through a fresh scope check. It also lets immediate controls bypass malformed advanced coordinates. These fixes await a separately identified package; in retained private.2, keep advanced coordinate input valid and use Take control before returning to typing.

After a partial result: Take control → inspect the visible world yourself → restore the disposable world if effects are unknown → reconnect the exact window/calibration → inspect fresh scope → send and review a new request. Never assume that retrying an unknown addition is harmless.

- **No game window:** open the supported single-player world and refresh. The launcher and unrelated windows are not valid selections.
- **Window/focus/capture unavailable:** bring the exact game window into view, remove overlaps, restore the supported size/display and permissions. A changed process/window invalidates calibration.
- **Inventory transition unavailable:** restore Building Blocks, resume gameplay, then retry setup. The inspector waits for visible transitions without repeatedly toggling E.
- **Unknown HUD/face/material:** restore supported preferences and default font; select a supported full block; point at the middle of a nearby full-block top. Borders, partial blocks, tooltip occlusion and unsupported layouts can be refused.
- **Unexpected view/displacement:** Take control; reread the partial result and diagnostics; reconnect/recalibrate where requested. The app does not silently blame human input or reuse contradicted feedback.
- **Whole-task budget reached:** inspect actual progress and choose a smaller supported task or a better manual starting position. Camera, inspection, translation and placement all consume the reviewed total budget.
- **OpenTTD model unavailable:** start local Ollama and install gemma3:4b. This does not authorize cloud access.

Survival, breaking blocks, flying/jumping/navigation, automatic inventory changes, partial-block construction, unrestricted exploration, multiplayer, voice, Windows and universal game support remain unavailable. Existing Mario/Stardew paths retain their own setup/assets and evidence. Broader onboarding, gameplay variation, other displays/settings, additional games and sustained reliability are beta feedback work.

## Report feedback locally

In **Guide & feedback**, describe the build version, game/settings, request, expected/actual result, whether Stop worked and steps to repeat. Choose **Save local report & preview**, inspect the JSON, then manually share it through the owner's agreed channel. Reports include bounded selected configuration, recent sanitized outcomes and your text. Nothing is uploaded or sent automatically; screenshots, credentials and raw native evidence are not included automatically.

Profiles, history, reports, preference backups and native attempt diagnostics live outside the installation in **`~/Library/Application Support/Game Companion`**, shown in the app. Keep the build manifest with a report. Inspect any screenshot or log before sharing. Do not contact testers or distribute this review build until the owner authorizes it.
