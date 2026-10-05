# Known limitations

Updated October 4, 2026. These describe inspected source capabilities and remaining product gaps. [Product direction](product-direction.md), the [two-role architecture](agent-architecture.md#october-4-architecture-correction--two-model-driven-responsibilities) and the [engineering plan](private-beta-engineering.md) describe the required private beta separately. Retained source/game results and packages keep their original evidence scope.

## Initial-beta implementation gaps

The initial private beta requires both a contextual language LLM and a gameplay agent that observes, chooses/composes supported actions, verifies effects and revises decisions. The owner's installed, signed-in Codex CLI is the first intended backend. Its presence is confirmed; integration into ordinary gameplay, contextual quality, decision quality, latency and usage-limit handling are not implemented or verified by that check. No retained package demonstrates the required two-role Mario/Stardew experience.

| Area | Current source and evidence | Remaining limitation |
| --- | --- | --- |
| Language | Mario/Stardew use a deterministic grammar and task-specific conversation branches. A separate OpenTTD profile uses local Ollama. | Ordinary contextual LLM interpretation, rich multi-turn references and model-backed task decisions are absent. |
| Mario | Opening timing coaching, experimental scheduled coin routes, remembered stairs/pipe instructions, two World 1-1 finishes and two supported sky 1UP collections have live source evidence. | High-level choices are mainly authored tactics/routes. Arbitrary instructions, general flight, complete coin coverage and broader reliability remain unverified. |
| Stardew | Supported Day 2 selected watering, live planting-location discussion, eastern-margin inspection/return, corrections, Stop and saved results have live source evidence. | Two prepared farms and qualified display/viewpoints only. General crop identity, arbitrary farms, automatic tool selection/refill and adaptive task composition remain absent. |
| Cave | Partial western survey saw the Farm Cave exterior; camera anchors and navigation-only state accounting are implemented. | Travel remains disabled. Foliage/player recognition, debris clearance and a complete tool-free approach/return are unqualified. Interior exploration is unavailable. |
| Learning | Local opening guidance, authored-route outcome selection, history and engineering promotion are implemented. | General contextual retrieval and outcome-driven model decisions remain required; stored notes and fixed route selection do not establish them. |
| Recording | Recording/review/application source and executable local checks are preserved. | Real demonstration application remains unverified and deferred to a later beta, tentatively beta v2. |
| Delivery | Retained review packages and source launchers exist. | New AI contracts, backend/setup experience, two-game packaged walkthrough and owner usefulness remain unqualified. |

The immediate development task is the Codex-backed two-role loop using current watering/inspection skills, followed by Mario decision integration and required product coverage. A bespoke cave manifest is no longer the lead work item. Preserve its partial evidence for later reusable perception/navigation work.

Questions and passive planting discussion permit no farm action. Native Stardew discussion releases input; a revised continuation requires a current reviewed plan. Choosing a planting location grants no planting, clearing or purchase authority. Reopening any result grants no live connection or gameplay authority.

Minecraft is later beta expansion; advanced-user no-code onboarding and independent training remain deferred. Current contributor onboarding creates data-only fixture scaffolds and does not generate live perception or gameplay control.

## Required Codex integration remains unimplemented

The current `model_gateway.py` supports only the loopback Ollama screen/skill proposal contract. It has no ordinary Codex provider, contextual intent schema or adaptive gameplay decision schema. Current Mario/Stardew services do not invoke it. Engineering must connect the installed CLI or app-server through bounded structured contracts, app-owned context/session state and validated controller dispatch.

Ordinary OpenAI-backed Codex inference sends selected game context/images to a remote model. A local app and locally stored histories do not imply local inference. The target setup must describe this and reuse existing authentication without storing credentials in profiles, evidence or packages. Neither a specific subscription allowance nor service availability is established by CLI discovery.

The required runtime must handle slow inference, invalid/incomplete outputs, signed-out/unavailable service, limits, cancellation and stale replies. Native release is independent of provider cancellation; late output cannot reauthorize or queue input. Backend failure must be visible rather than silently replaced by narrower phrase matching. Actual-model evaluation and live adaptive gameplay remain separate from simulated provider tests.

## Retained review-package scope

- Private.2 and current source enable Minecraft calibration/small camera requests; aim/move/place/wall Start remain disabled. No packaged Minecraft wall completion is established.
- October 1 source progress/protection/direct-control/drafting/observation/deadline fixes passed 1,327 canonical local tests on that source. They have not been rebuilt into private.2 and do not prove the corrected two-game beta.
- Minecraft's retained support is Java 26.3 vanilla Creative, English/default font, supported controls/HUD and an 854 × 508 point selected window at native 1× or 2× capture. It needs a disposable world and exclusive input during native work. Survival, multiplayer, breaking, flying/jumping, automatic inventory changes and unrestricted exploration are unavailable.
- The retained future building case is a 7 × 3 × 1 wall with a centered 1 × 2 doorway. Its geometry, occupancy, material, reach, protection and stop point need independent checks during later-beta Minecraft gameplay. Unknown results remain partial.
- OpenTTD supports one £10,000 repayment from a paused disposable English 15.3 company with £100,000 cash and loan. Its packaged success belongs to private.1; general management is unavailable.
- Retained Mac packages are Apple Silicon, locally ad-hoc signed and not notarized. Broader configurations and sustained reliability need actual beta feedback. Product review and launch/distribution approval remain separate.

## Current conversation and recovery limits

See the [Mario guide](mario-player-guide.md) for declared World 1-1 paths/stops, normal/uncapped speed and authority-free variants. Resumed play permits only the verified opening stop after fresh observation/review/Start; level-exit or full-base traversal requires fresh power-on. Arbitrary mid-run full-route resume, later custom routes and fixed 2×/4× playback are unsupported. New coached gameplay entries/actions need implemented runtime contracts and observed results.

Stardew guarded stops can leave the return unconfirmed even if selected actions finish. Neutral handback is distinct from reaching the farmhouse. The October 4 watering and eastern inspection records separately establish their named source activities, including return and saved reopening. They do not reclassify earlier failures, establish owner acceptance or qualify arbitrary farms. See [watering verification](gc3-watering-verification.md), [inspection verification](gc3-inspection-verification.md) and [review records](private-beta-review.md).

## Live validation requires local assets

Non-live tests verify contracts, parsers, reports, security controls, and
deterministic rendering, but they cannot prove emulator startup, route timing,
gameplay success, or the game-owned ending. That proof requires the configured
local environment, FCEUX, and the goal-specific fresh-run gate.

Ignored gameplay archives are local records and are not automatically uploaded
or replicated. Selected images/context supplied to the planned Codex provider
are a separate inference transfer. Another checkout cannot reproduce an acceptance
claim without compatible local assets/runtime and a fresh run.

## Platform support

FCEUX is the supported live Mario adapter. Minecraft and OpenTTD use their separate ordinary-window/native-input paths described above. The older Mednafen diagnostic
adapter is macOS-only and depends on a visible desktop plus Accessibility and
screen-capture permissions. Headless Mednafen operation and non-macOS Mednafen
control are unsupported.

The non-live CI job runs on Linux and intentionally does not install or start
either emulator.

## Stardew live-input prerequisites

The browser workspace routes setup, planning and guarded controls into the Stardew runtime. The public Stardew CLI remains inspection-only. Start requires verified session isolation, a qualified real-game pixel profile, sufficient fresh observations for the specific activity and reviewed scope. Local prepared saves, profile registrations and calibration assets are ignored; cloning or launching alone does not install them. The current preparation workflow supports PID-bound image-reviewed Load/porch/tool steps, but requires the player or engineer to inspect and direct them. Day 5 supports only its selected ordinary parsnip, owned seed and small stone; arbitrary farming and automatic refill remain unsupported. See the [Stardew guide](stardew-operator-guide.md).

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

## World 1-1 surface coin discovery — October 3

The ordinary conversation loop explores three bounded scheduled-jump patterns and applies compatible outcome memory to future gameplay. It reports level-counter increases, landmark yields, prior-yield shortfalls and unknown bands; counter gaps/resets/wraps prevent a trusted total. Individual coin identities and the full universe (including hidden/brick, airborne and bonus rooms) remain unverified, so no 100% claim is possible. Experimental failures and source walkthrough progress are retained in [coaching and discovery verification](gc1-gc2-coaching-verification.md). Player demonstration source is deferred; sequence following requires matching entry/motion/form and stops on drift, with unsynchronized enemy timing. The later supported sky 1UP collection has its own [flight verification](gc2-flight-verification.md). Wider strategy/learning remains required under the new AI architecture.

## October 4 app-delivered route instructions

Current source observed two consecutive World 1-1 finishes with two coins each after app-delivered remembered stairs/pipe instructions. This supersedes the experimental route's earlier stairs failure boundary, not the separate demonstration qualification. Instruction application, stairs landing, level exit and neutral handback have separate receipts. The vocabulary is a finite supported tactic contract; arbitrary gameplay instructions and generalized autonomous learning are unavailable. Historical route evidence and private.2 retain their original meaning. Two attempts are limited repeat evidence, not broad reliability or full coin coverage. See [route verification](gc2-route-verification.md).

The supported World 1-1 sky-brick 1UP was subsequently collected twice with independent target, collection, life-credit and handback receipts. This requires prepared Raccoon/Tanooki Mario at the declared early-runway entry; acquiring those prerequisites remains player-controlled. It does not qualify arbitrary rewards, flight areas or broader strategy. See [flight verification](gc2-flight-verification.md).
