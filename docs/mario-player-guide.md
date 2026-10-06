# Mario player guide

## Current abilities and the private-beta target

The ordinary source app uses Codex to understand your wording and a separate gameplay role to choose finite maneuvers. Ask to play the early World 1-1 segment, specify preferences and an attempt limit, choose **Apply change** to review, then **Start reviewed plan**. The experimental goal is x=700, alive and grounded. The model sees paused game images and native progress, predicts effects, then chooses again; the controller owns input timing. It may stop early on unsafe state, inference failure or exhausted limits. Arrival is reported only when independently observed.

For example, ask for short 8-frame hops on clear flat ground, longer running jumps for obstacles, or intermediate landings on visible raised blocks. A high-hop-on-flat trial failed near an enemy; that preference is not qualified as reliably completing. Ask to remember a correction for future compatible segments. **Remembered Mario guidance** shows active or superseded advice. A later compatible plan retrieves it; outcomes distinguish requested advice, matching native application receipts and unknown improvement. Current facts and fresh instructions take priority. **Reset future guidance** resets future advice while retaining historical attempts. Questions grant no input.

Each segment attempt permits at most 32 decisions, 1200 skill frames and 480 seconds; the reviewed finite attempt count and retry expiry still apply. **Stop** and **Take control** release input and cancel pending inference. After cancellation, open a fresh attempt and request/review a new goal. Saved history reopens without restoring a plan or control. Codex inference is remote; the app and game controls run locally. The final native engineering set completed 3/3 supported segments, including a raised-block preference trial. Full-level adaptive completion, complete coin coverage and broad reliability remain unverified. Existing coin routes and flight/reward controllers retain their separate scopes. See [verification](gc-ai-loop-verification.md). Recording remains deferred to tentative beta v2.

## Fly to the sky hidden 1UP

Ask **“Fly to the hidden 1UP.”** Companion names the hidden 1UP inside the sky brick in World 1-1 and checks your current form and entry. Other rewards or levels need clarification.

1. Choose **Open Mario for companion play**. Use **Preparation controls** for short ordinary presses that release every button and pause the game, or choose **Prepare flight form yourself** and use your normal emulator controls.
2. Get the Mushroom from the right upper question block before the first pipe. Keep Super Mario through the crossing. Stomp the red Koopa, carry its shell right and release it before the ground question block. Follow immediately to catch the Super Leaf. Return Raccoon or Tanooki Mario to the low green platform after the pipe. No recording is required.
3. Ask for flight again. Review the fresh observed requirements and finite plan, then choose **Start reviewed plan** or say **yes**. Companion stages onto the longer floor, clears the runway threat, builds full P-speed, flies to the sky brick, descends and jumps into it from below, then follows the mushroom. The attempt allows at most 15 seconds of gameplay and 30 seconds overall.
4. Watch the separate flight, area, revelation and collection results. Collection requires the target mushroom's game-owned hit receipt. Unknown observations stay unconfirmed; an extra life from 100 coins does not prove the hidden reward.
5. **Stop**, **Take control** or **STOP RIGHT NOW WAIT** interrupts play. Confirm handback before more input. The finished flight pauses with control returned. After release, **Open fresh attempt** opens a new disposable session; prepare again and review a fresh request before Start. Saved results can be reopened without playing.

This supported case collected the intended 1UP in real source gameplay, with lives 4→5 and native neutral handback. Wider flight goals, arbitrary starting positions and packaged delivery are unverified. See [flight verification](gc2-flight-verification.md). Full coin coverage remains unknown; recording is not a qualified ordinary workflow.

## Send instructions for the next attempt

Open Mario through the ordinary companion interface. Ask “Improve stairs traversal toward the finish for two attempts.” The proposal uses compatible failure memory and displays the next-attempt instructions. Review them, then choose **Start** or say **yes**. The app sends those instructions to the emulator; it reports whether the controller applied them and whether Mario actually landed beyond the stairs and reached the level exit.

You can teach the supported stair instruction directly: “At the stairs land on the left top before jumping across the gap.” Companion explains its interpretation, retains your words and uses the instruction in the next compatible attempt. If already playing, the correction applies next time. After confirmed handback choose **Try again with guidance** within the remaining approved budget. Each trial is capped at three minutes inside the ten-minute scope; one to five attempts can be reviewed. Reopening retains descriptive instructions/results and requires a fresh session and approval. Stop/Take control cancels future retry authority and requires confirmed input release before more play.

Current source observed the stairs and pipe continuation reaching the World 1-1 exit with **two coins**. Two consecutive reviewed attempts finished; collecting every coin is unverified. Urgent chat Stop during a paused pipe crossing also returned control with native confirmation. The supported next-attempt instructions are limited to this stair tactic, a failure-derived pipe continuation and the existing opening timing. The supported flight/reward case above is verified through real source gameplay; broader English tactics and wider learning remain development work. No recording or player demonstration is required. See [route verification](gc2-route-verification.md).

## Recording limitations

Player-controlled recording, demonstration playback and the attended stairs walkthrough are deferred to a later beta, tentatively beta v2. Preserve the implemented source and evidence; real demonstration gameplay remains unverified. Recording is optional future work and is not an initial-beta requirement or a gate for current development. No owner recording session is needed now.

This guide describes the source adapter. Current source documentation does not
establish a packaged app's abilities; use that app's versioned manifest for its
supported features. Full coin coverage, arbitrary strategies and generalized
learning remain unsupported.

Start with [launch and first use](../README.md#launch-and-first-use), then choose Mario. The ordinary conversation workspace is at `/mario`; the Lab is for engineering.

Before opening a session, the setup card must recognize a supported local game file and find FCEUX. If needed, select the local game-file path through first-use setup; the saved selection or `SMB3_GAME_FILE` supplies it on later launches. Confirm normal keyboard/controller mapping for player control. A missing file, unsupported identity or unavailable emulator must be resolved in setup; repeated launch does not bypass the check.

## Let me show you: record a route or segment

The following records the implemented source workflow for later beta work. It is
not required for the initial private beta, and no recording session is needed now.

The current source **Let me show you** card supports alive World 1-1 route segments. Your input controls Mario throughout recording. Check your usual FCEUX keyboard/controller mapping first.

1. Choose **Open Mario for companion play**, then **Play Mario yourself**. Focus FCEUX and enter World 1-1 normally. Position Mario where your example should begin. For the stairs case, begin just before the difficult stairs, ideally near the state the balanced companion route can reach.
2. In Companion, choose **Start recording** and check that the status says **recording**. Return to FCEUX and demonstrate the section. You can record a short useful move or a longer route, up to ten minutes.
3. Choose **Stop recording**. Expand **Review recorded actions and gameplay** to inspect sampled game images and action/context rows. Save the whole recording or choose **Start here** / **End here** on the sampled gameplay images. Optional start/end times use seconds of game time, measured from recording start; no frame indexes are needed. Images are sampled, so inspect the action review too. Choose an end before a death or transition if saving refuses the segment; the full draft is retained.
4. Give it a name, such as **Climb the stairs**, and describe the intended lesson, such as **Run and hold jump to land on the next stair before the enemy reaches me**. Choose **Save demonstration**.
5. Choose **Open fresh attempt**. This closes the released task-owned disposable game and opens a fresh paused session. Select your saved demonstration, choose **Review**, then **Use in next attempt**. Read the explanation and choose **Start reviewed plan** or say **yes**.
6. Watch the balanced approach and recorded sequence. The result reports whether demonstration input was applied, how many frames were followed, whether the segment end was observed, why it stopped and whether inputs were released. Observe whether Mario actually passes the earlier failure; sequence application alone does not establish improvement.
7. **Stop**, **Take control**, or **Stop using demonstration** interrupts playback. Rename/change its lesson with **Save name and lesson**, or **Delete demonstration** to remove future availability. Previous application outcomes and raw session evidence remain.

The companion follows recorded buttons frame by frame once position, motion, form, air and level/map state match. It stops at the segment end, on drift/death, or after the three-minute attempt limit. Different enemies and timing can prevent entry or success; it does not infer a general stair-climbing skill. Only World 1-1 is currently supported. Reopening restores saved demonstrations/results, never recording or permission to play. Real gameplay and the owner's demonstration experience for this source slice are still pending; these instructions require no engineer-created recording or file edits.

## Deferred demonstration verification

No stairs demonstration has been recorded or applied in the retained verification. When recording returns to scope in a later beta, the walkthrough is: open disposable Mario, release to player control, enter World 1-1, reach the approach to the stairs, record, demonstrate, stop, review and save **Climb the stairs**. Stop the recording while alive after the useful move. The start may need adjustment after comparing the actual companion approach; the player should not match hidden controller conditions. This is not the current engineering or owner action.

Next, open a fresh attempt, review/use the saved example and explicitly Start. Observe entry, actual recorded input, stairs traversal and whether it passes the earlier failure separately. Retain a refused or failed example; diagnose the trace and entry before changing alignment or drift guards. Interrupt a separate approved attempt with Take control and confirm handback. Reopen Companion and review the saved example/result with no resumed play. Enemy timing is not synchronized; a compatible entry does not guarantee the same outcome.

## Discover a World 1-1 coin route

Open Mario for companion play, then ask “Let's find a coin route to the end for three attempts” or “Collect all the coins and finish.” Review the experimental route and say **yes** or **Start**. The companion compares earlier/longer, later/shorter and balanced scheduled jumps across the surface level, preserving the existing hazard responses. After confirmed handback, **Try again** uses discoveries to select an untried alternative, the furthest observed partial route or the best observed finished yield. Each attempt is capped at three minutes within a ten-minute, one-to-five attempt approval. Stop cancels remaining retry permission.

The **Coin-route discoveries** card separates the last attempt's collected count from the best observed yields across attempts. Six landmark bands (opening, first pipes, middle gap, stairs, last pipes, goal) retain progress and opportunities. The missed number is a lower bound on previously observed segment-yield shortfalls in completed bands, not a count of individually identified coins. Unvisited bands and hidden, brick, airborne and bonus-room opportunities stay unknown. The level counter is read before every controlled frame; duplicate observations do not add coins, and resets, wraps or gaps make the total uncertain. The baseline counter is excluded. A finish requires the controller's level-exit observation; position alone is insufficient. No total coin universe has yet been verified, so a 100% claim is unavailable.

Results and failed routes survive reopening. Open the same recognized cartridge again to bind compatible discoveries before reviewing a new exploration plan. Reopening never restores approval or input ownership. Questions about coin discoveries are advisory. Accepted historical routes and experimental exploration results remain separate. The supported flight/reward case above has real source gameplay evidence. Broader learning and full coin coverage remain separate; recording is deferred to a later beta.

## Practice and coach the opening jump

1. Choose Mario from Games, then **Open Mario for companion play**. This opens a fresh disposable FCEUX cartridge session paused for review.
2. Ask “Could you help me practice the opening jump for three tries?” Inspect the proposed World 1-1 opening hop and stop at x ≥ 160; say **yes** or click **Start reviewed plan**. This authorizes up to three attempts in ten minutes (one to five can be requested).
3. Watch the separate game window. Ask questions without starting new gameplay. Coach it with “You're jumping too early, wait 3 more frames” or “Jump two frames earlier.” “A few” means three frames and the companion explains that interpretation. Supported delay is 0–12 frames before holding jump for 26 frames. Coaching applies to the next attempt; it does not alter a jump already underway.
4. After confirmed handback, choose **Try again with guidance** or say “try again.” Within the approved budget it closes its released disposable emulator and opens fresh paused power-on with the same cartridge, then starts a revalidated attempt. No manual reset or repeated Start is needed. It never retries by itself.
5. Inspect remembered guidance, actual controller timing receipts and saved outcomes. “Applied” means the controller reported starting that timing. It does not mean the attempt improved. Both attempts reaching the stop leaves improvement unknown; eligible prior death versus current stop completion is reported narrowly as observed completion improvement, with causation unknown.
6. Use **Reset future guidance** or “reset coaching” to clear future corrections while retaining outcomes. Reopening retains memory/history, but never restores a plan, live connection or approval.

**Stop** / **Take control**, or “STOP RIGHT NOW WAIT,” cancels pending work and retry permission immediately. Check the control owner and input-release result; an unconfirmed handback blocks further play. A new session, changed scope, exhausted budget or expired approval requires fresh review. Each attempt lasts at most three minutes, capped by the shared ten-minute deadline.

This experimental practice does not complete World 1-1, find all coins or learn flight. The local interpreter handles supported English goal/coaching/question/control variations; unsupported feedback is clarified. Historical accepted routes remain separate. See [verification](gc1-gc2-coaching-verification.md) for exact source evidence and retained-package limits.

## Review and Start

Choose the existing base, **Quickest**, or **100% clear**, or type a request. All initially load the same existing `world_8_finish_game` base. Quickest is an existing-base fallback, not an optimized route; full-completion coverage remains unknown. Review the actual path and stop, not just the requested objective.

This fallback is a current product gap. It does not satisfy a request to find or train a 100% coin route. The revised beta must explain unknown coverage and offer actual supported exploration or a clear blocked result, rather than treating an unchanged base route as fulfillment.

Choose **Open Mario for companion play** to open a visible FCEUX session held at the fresh boundary. **Review plan**, inspect the proposal, then **Start reviewed plan** grants permission in that session. Selecting a route, opening Mario, asking a question or reopening history never starts execution. The current deterministic English planner needs no model account or credentials. The planned AI experience will use the selected Codex CLI setup and show its availability in first-use setup; it is not active in this current path.

## Supported paths, destinations and changes

| Choice | Supported destination and entry |
| --- | --- |
| Default opening / base path | Opening end, World 1-1 exit, or existing base ending from fresh power-on |
| Opening hop | Opening end only; later traversal is not qualified |
| Return from player control at the verified World 1-1 opening | A fresh observation, review and Start may authorize only the opening stop (`world_1_1_opening_end`) |

**Longer traversal after taking control requires a fresh session.** The runtime refuses opening-to-level-exit resumption because that entry path is not supported. Close the old game after handback, open Mario afresh, select/reopen the desired plan, review and Start. Arbitrary map, later-level or manually positioned states cannot substitute for a compatible entry.

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

Current source recognizes “STOP RIGHT NOW WAIT” and urgency/punctuation variations through a priority release path. Dedicated **Stop** and **Take control** remain directly available. Source evidence does not update the retained private.2 package.

## Saved variants, results and recovery

Expand **Save or reopen a route** to save a named variant or Reopen it. A variant stores its base/version, actions and stop; it stores no gameplay permission. Reopen proposes a plan, then checks integrity, compatibility and fresh state. Review and explicitly Start. A saved variant is not automatically accepted, fastest or reliable.

A completed opening stop means that bounded stop completed; it does not mean the full base or a 100% objective completed. Death, lost process, reclaim and missed boundaries remain distinct partial/stopped results. After process loss, open a fresh session; old edits and Start identities cannot be reused, and no native handback receipt can be supplied by the dead process. See [shared history and recovery](../README.md#history-recovery-and-safe-shutdown).

The older Observe/Tell/Show/Do and History surfaces remain available. Observe only is read-only; Tell advises; Show is a separate review-only demonstration, never your completion. Their availability does not broaden conversation entry or destination limits.

## Broader coached-play requirements

The supported cases above remain current source behavior. The initial AI private
beta must add contextual interpretation and actual gameplay decisions within a
clearly described Mario scope:

| Player intention | Required AI experience |
| --- | --- |
| Explore a coin route or improve a section | Reason from the visible level, mechanics and remembered attempts; choose a useful approach, observe the result and revise it. Explain the declared collection scope and unknown coverage. A completed route does not establish every coin. |
| Coach a movement or timing decision | Resolve the relevant event from the conversation and current play, explain the adjustment and show when it actually reaches the controller. Compare observed results honestly. |
| Pursue a supported flight reward | Understand the destination, ability and current conditions, choose an executable approach and distinguish flight, reward revelation and collection. |
| Interrupt or change the goal | Release input promptly, preserve what happened, and discuss a revised plan. Old work must not restart after Stop. |

Examples in this guide illustrate intent; they are not a required vocabulary.
Private-beta acceptance requires varied wording and a meaningful changed gameplay
condition without a phrase-specific or route-specific patch. Mario's fast
controller must keep playing the current approved task safely while the slower
reasoner is working; a late decision cannot be applied to a missed event.

The companion must retain discoveries, coaching, decisions and outcomes so they
affect compatible future attempts. Reopening restores that history without
restoring gameplay permission. Ordinary experiments remain separate from
historical accepted routes. Full coin-universe coverage, broader game support,
independent training and recording remain separately labeled work. The
[integration contract](b2-integration-contract.md) defines the AI and gameplay
completion checks; source results alone do not establish a released package.

## Integrated source setup — October 5

Start at the game catalog to check Codex and macOS permissions, then open **Set up Mario and open a disposable session**. Select your supported local game file, confirm the FCEUX input mapping and open a fresh session through the existing first-use controls. Setup changes return to the Mario setup panel. FCEUX discovery checks the launch environment and the standard Homebrew/local executable locations so readiness and launch use the same installed program. No game file or emulator is bundled by these source changes.

**Refresh Codex readiness** checks existing sign-in after login or connectivity recovery. Credentials remain with Codex. Remote inference receives selected game context/images; controllers, approvals and input release remain local. Reopening or switching games restores no gameplay authority. Source and exact-package evidence remain separate.
