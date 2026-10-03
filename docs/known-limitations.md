# Known limitations

Updated October 3, 2026. These describe current runtime limits and inspected product gaps. [Product direction](product-direction.md) and the [engineering plan](private-beta-engineering.md) describe planned requirements separately.

## Initial-beta implementation gaps

The initial beta must deliver watched/coached Mario play and useful Stardew activity delegation. No retained package currently demonstrates that complete experience. Next work is GC1 priority conversation/control, GC2 Mario coaching/route learning, GC3 Stardew delegation and GC4 an identified two-game package. Minecraft is a later third-game beta stage; advanced-user no-code onboarding follows implementation of the first two experiences.

- Mario has a real cumulative route/controller and bounded path/stop/speed edits. Current Quickest/100% selections load the same existing base with unknown collectible coverage. Coin-route discovery, user jump-frame/flight objectives and an integrated cross-attempt/life coaching loop are not available through current conversation.
- Mario's local learning records derive patterns and review candidates. They do not currently apply conversational coaching to the next attempt. Engineering accepted-route promotion remains distinct from the planned local reviewed experiments.
- The Mario/Stardew intent interpreter is a bounded deterministic grammar. Exact `STOP RIGHT NOW WAIT` is not recognized by its full-match chat-control parser; dedicated Stop/Take control exist. Urgent conversational interruption is the first repair, with actual release verification required before claiming it works.
- Stardew supports only the two prepared farms and exact screen/profile/settings in the [operator guide](stardew-operator-guide.md). General tomato watering, corn-location choice and cave exploration are not provided by current action recognition/navigation. Parsing a crop name does not establish gameplay capability.
- Stardew chat focus stops ordinary native input and revokes authority. The planned immediate discussion/check-in experience needs a clear observe/replan/approve continuation flow; refocusing alone cannot resume input.
- Current other-game onboarding creates data-only fixture scaffolds. Live perception/controller integration still requires engineering. Guided playable no-code onboarding is deferred, not a current capability.

## Retained review-package scope

- Private.2 and current source enable Minecraft calibration/small camera requests; aim/move/place/wall Start remain disabled. No packaged Minecraft wall completion is established.
- October 1 source progress/protection/direct-control/drafting/observation/deadline fixes passed 1,327 canonical local tests on that source. They have not been rebuilt into private.2 and do not prove the corrected two-game beta.
- Minecraft's retained support is Java 26.3 vanilla Creative, English/default font, supported controls/HUD and an 854 × 508 point selected window at native 1× or 2× capture. It needs a disposable world and exclusive input during native work. Survival, multiplayer, breaking, flying/jumping, automatic inventory changes and unrestricted exploration are unavailable.
- The retained future building case is a 7 × 3 × 1 wall with a centered 1 × 2 doorway. Its geometry, occupancy, material, reach, protection and stop point need independent checks in later GC5 gameplay. Unknown results remain partial.
- OpenTTD supports one £10,000 repayment from a paused disposable English 15.3 company with £100,000 cash and loan. Its packaged success belongs to private.1; general management is unavailable.
- Retained Mac packages are Apple Silicon, locally ad-hoc signed and not notarized. Broader configurations and sustained reliability need actual beta feedback. Product review and launch/distribution approval remain separate.

## Current conversation and recovery limits

See the [Mario guide](mario-player-guide.md) for declared World 1-1 paths/stops, normal/uncapped speed and authority-free variants. Resumed play permits only the verified opening stop after fresh observation/review/Start; level-exit or full-base traversal requires fresh power-on. Arbitrary mid-run full-route resume, later custom routes and fixed 2×/4× playback are unsupported. New coached gameplay entries/actions need implemented runtime contracts and observed results.

Stardew guarded stops can leave the return unconfirmed even if selected actions finish. Neutral handback is distinct from reaching the farmhouse. The retained successful final-return repair does not reclassify earlier failures, qualify later source or establish owner acceptance. No current app/gameplay use was observed during the October 3 product-direction discussion. See [review records](private-beta-review.md).

## Live validation requires local assets

Non-live tests verify contracts, parsers, reports, security controls, and
deterministic rendering, but they cannot prove emulator startup, route timing,
gameplay success, or the game-owned ending. That proof requires the configured
local environment, FCEUX, and the goal-specific fresh-run gate.

Ignored gameplay artifacts are local-only. They are neither uploaded nor
replicated, so another checkout cannot reproduce an acceptance claim without
the recorded source revision, compatible local runtime, and a fresh run.

## Platform support

FCEUX is the supported live Mario adapter. Minecraft and OpenTTD use their separate ordinary-window/native-input paths described above. The older Mednafen diagnostic
adapter is macOS-only and depends on a visible desktop plus Accessibility and
screen-capture permissions. Headless Mednafen operation and non-macOS Mednafen
control are unsupported.

The non-live CI job runs on Linux and intentionally does not install or start
either emulator.

## Stardew live-input prerequisites

The browser workspace routes setup, planning and guarded controls into the Stardew runtime. The CLI remains inspection-only. Start requires verified session isolation, a qualified real-game pixel profile, complete fresh observations and reviewed scope. No qualified profile ships with this checkout. Day 5 supports only its selected ordinary parsnip, owned seed and small stone; arbitrary farming and automatic refill remain unsupported. See the [Stardew guide](stardew-operator-guide.md).

## Route Lab is local-only

Route Lab accepts only loopback bind hosts. It is not designed for LAN,
internet, multi-user, or unattended deployment. It has request-size limits,
CSRF protection, safe artifact serving, and serialized ordinary mutations with
priority direct-control paths, but
it does not provide TLS, accounts, durable sessions, backups, or an availability
guarantee. Local artifact files remain the source of its displayed state.

## No autonomous service operation

There is no independent scheduler, queue, daemon, retry service, telemetry backend,
or alerting integration. The local app and CLI run under user/operator control. The app owns bounded observation/task/watchdog threads and input/model helper or emulator child processes while
the server is active; it is not a hosted autonomous service. Failures are written
into local reports where the operation supports them. Users can inspect partial
results and follow the recovery guide; unresolved defects need engineering review.

A production web deployment, shared evidence store, or remote orchestration
model would require explicit product and security design. None should be
inferred from this local application. Repository-structure follow-ups and
retained large-file rationale live in the [development guide](development.md).
