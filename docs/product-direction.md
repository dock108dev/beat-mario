# Product Direction

## Private-beta direction

The private beta should let a technically comfortable nonprogrammer open the Mac app, connect Minecraft Java, follow understandable settings/calibration and practice, save a profile, ask for a supported task through typed conversation, Review/Start, Stop or take control, and reopen the profile and result. The [private-beta engineering plan](private-beta-engineering.md) and [Desktop tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md) own implementation and launch checks. Game Companion remains the working name.

The first useful Minecraft task is a 7-wide × 3-high × 1-thick Creative wall with a centered 1-wide × 2-high doorway, preserving marked protected blocks. The user follows guided preparation of a disposable, flat clear practice area and reachable work region. The app must explain and visibly check the required start, material and clearance, and give a concrete remedy when they are missing. Setup uses ordinary app controls rather than developer scripts or authored coordinates.

## Current capabilities and planned work

Minecraft profile/setup/help/history/local-feedback and app-created calibration/bounded camera requests are implemented. Current source adds state-derived setup progress/remedies and affected control, protection, aiming and deadline repairs. These changes have local checks and have not been rebuilt into private.2. Aiming, nearby movement, additions and wall Start remain unavailable in both the current source feature flags and that retained package. Finish the useful path, enable checked task families, and verify the packaged setup → task → outcome/handback → Stop → reopening workflow. The [quick start](private-beta-quick-start.md) and [review](private-beta-review.md) distinguish current settings and retained package evidence. Broader onboarding usability, task variation and sustained reliability are private-beta evaluation.

Mario supports shared typed planning, a conversation surface, revision-bound controller changes and custom variant history. Faster, quickest and 100% intents initially load the same base route; speed does not imply route optimization or full completion. See the [conversation guide](b2-conversation-guide.md).

Stardew has retained technical qualification for Day 2 watering and the selected Day 5 harvest/plant/water/small-stone routine, including the B8 final-return repair. Those results apply to their exact prepared farms, settings and candidates; owner usefulness/acceptance remains pending and later source changes need affected qualification. See the [Stardew guide](stardew-operator-guide.md) and [personal-pilot delivery](b8-personal-delivery.md).

## Product

**Game Companion** is a local, user-steered game assistant. It observes the
player's current situation and offers three bounded kinds of help:

- **Tell:** explain the next useful actions from observed state and accepted
  game knowledge;
- **Show:** demonstrate an approved section with visible cues and a replay;
- **Do:** complete one explicitly bounded objective, then stop input and return
  control in a known state.

The product result is not "the agent emitted inputs" or "the agent says it
won." A completed session includes the observed starting state, authorization
and protected decisions, attempts, game-owned outcome, state changes and
resources consumed, unresolved uncertainty, evidence, and safe handback.

Generic walkthrough generation is outside the differentiating promise. Help
must be specific to the player's observed state. Unsupported, stale, or
ambiguous state fails closed.

## Current proof: Mario

The existing Mario adapter retains historical accepted execution and reliability
proof for its original route; that proof does not qualify new conversational
variants or the current cumulative beta. Its `world_8_finish_game` contract starts from
fresh power-on, executes the accepted route with normal gameplay, defeats
Bowser, observes the Princess rescue and credits, and stops at the stable
game-owned ending.

The player-facing Game Companion at `/` provides Mario first use, adapter-owned
capability truth, a compact live workspace, and grounded Tell/coaching from a
current adapter observation or clearly labeled player report. Show remains a
separate, fresh, visible, review-only process with synchronized cues and
retained evidence. It never advances the player's game, counts toward
reliability, or claims player completion. The engineering Game Companion Lab
remains at `/lab`.

Observe-only sessions are structurally read-only. Takeover-capable sessions
still require a fresh, same-process, goal-bounded authorization; **Take Control
Now** remains visible during agent control and neutral handback precedes
returned ownership. Unknown, stale, mismatched, or conflicting state fails
closed.

Mario History combines sessions, level runs, compatible player/agent/mixed
records, comparison targets, recovery, learning patterns, candidate review, and
evidence classifications. Local fastest is never presented as a world record,
and candidate approval never implies executable promotion.

Existing compatibility remains deliberate:

- `smb3_agent` stays the internal Python package and CLI namespace;
- existing goal ids, presets, artifact paths, and accepted evidence remain
  stable;
- Game Companion is the user-facing product and shared cross-game contract;
- Mario becomes one adapter behind that contract.

## Bounded second-adapter proof: Stardew Valley

The retained modern-game proof uses the visible windowed game, ordinary player input and dedicated disposable engineering farms. Qualified bounded tasks cover watering all 15 crops in the prepared Day 2 farm and the selected harvest → plant → water → small-stone-clear routine in the prepared Day 5 farm, each with resource accounting and farmhouse return/neutral handback on its identified candidate. This does not establish arbitrary-farm support or owner-save-copy validation.

The proof reconciles crops observed with crops watered and reports time, energy,
tool use, refills, final position, and protected actions. It does not purchase,
sell, discard, gift, enter consequential dialogue, choose story outcomes,
sleep, overwrite the owner's primary save, read process memory, use a hidden
game API, or claim headless regression as player-facing proof.

The Stardew operator foundation is independent of Mario. The adapter owns
verified disposable-save creation, process/window continuity, screen-only crop
and resource observations, fresh player/agent ownership, ordinary input
filtering, exact watering reconciliation, neutral stop, primary-save
reverification, and append-only evidence. Unknown or occluded crops, missing
resources, save/process/window mismatch, ambiguous authority, protected-action
risk, or incomplete evidence stop the attempt. Live support is restricted to the prepared farms and pixel profiles described
in the [Stardew guide](stardew-operator-guide.md). Owner acceptance remains
separate from technical qualification.

The companion supports screen-only Observe conversion, provenance-grounded Tell, one-task
fresh-copy review-only Show, and same-current-session Do with exact volatile
authorization, per-input revalidation, immediate reclaim, neutral handback,
completion reconciliation, and safe disposable-copy reset. Stardew facts and
safety remain adapter-owned behind the shared envelope. The combined catalog coordinates switching and neutral handback.

An optional engineering-only unattended regression surface supports eligible
adapters. It is not a player-facing mode. Only explicitly eligible
scenarios and adapter providers may use it, every attempt is isolated and
bounded, and its evidence is permanently `unattended_regression_result`.
Neither normal nor virtual-display output can supply visible player proof,
Show, route reliability, authoritative completion, usefulness, acceptance, or
the consolidated campaign. Mario protected assets/evidence and Stardew primary
saves remain outside its artifact and mutation boundaries.

Experimental adapter onboarding provides a data-only contributor path. A contributor can
declare metadata, detection, read-only observation, ordinary allowlisted input,
ownership, reclaim/handback, capabilities, measurable goals, fixture-only
profiles, safety, scopes, fixtures, evidence, and removal; review a deterministic
non-executable scaffold; run fixture conformance; and atomically install or
safely remove it. Discovery is provider-based and adds no shared-core game-ID
branch. Every such entry remains Experimental, installed, and live-unproven.

## Combined product

Existing adapters and profile-backed games use the same session contract, with their own supported task and mode labels:

```text
Select game and goal
-> observe current state
-> choose Tell / Show / Do
-> review scope, stop point, and protected decisions
-> instruct or execute
-> verify the game-owned outcome
-> stop input
-> return control with a truthful handoff
```

Game-specific adapters own observation, actions, capabilities, goals, safety
rules, and success predicates. The companion core owns session state,
authorization, mode behavior, handoff, evidence references, and local metrics.

The root product shows adapter/profile-owned catalog entries without flattening
their capability truth. Explicit switching fails closed until input is neutral,
player handback is confirmed, the current attempt is retained, and continuity
is known. Catalog-switch evidence has its own classification; no observation,
authority, goal/profile state, save/process identity, route/crop state,
recovery, or game-evidence claim crosses adapters. Only schema-versioned,
bounded, namespaced presentation preferences persist locally.

## Catalog growth

The New Game Onboarding flow is contributor infrastructure; its fixture conformance does not create live gameplay. Player setup/profile creation is a separate implemented app surface, with available Minecraft calibration/camera tasks and the useful wall path still unfinished. Additional eligible-game configuration and task breadth are beta evaluation and future integration work. The contributor flow can
scaffold an experimental adapter, declare its capabilities and safety rules,
attach fixtures, run conformance checks, and install it locally. Experimental
adapters expose only proven capabilities and cannot enter the trusted supported
catalog without explicit review and game-specific live evidence.

The current engineering order and acceptance cases are in the [private-beta engineering plan](private-beta-engineering.md). The [personal-pilot packet](personal-beta-engineering.md) and [Game Companion V2 roadmap](v2-roadmap.md) contain the existing integration contracts and earlier evidence boundaries.

## Boundaries

- Local application and local diagnostics by default; no cloud telemetry. The private-beta backend decision may permit explicitly consented model screen/context transport with bounded usage and secure local credentials.
- Offline, owner-controlled, single-player games only.
- No multiplayer, competitive play, anti-cheat environments or unauthorized
  permanent decisions. The beta farm routine uses owned tools/seeds and excludes
  implied purchases, sales, gifts and story choices.
- Diagnostic, assisted, review-only, unattended, and owner-accepted evidence
  remain distinct.
- Reliability metrics cannot substitute for owner usefulness feedback.
- The user can cancel or take over; no input continues after handback.
- Automated checks and retained technical runs do not establish owner acceptance.
  Historical campaign contracts remain separate from current source qualification.
