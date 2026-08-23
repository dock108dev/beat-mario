# Product Direction

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

The existing Mario adapter is the accepted execution and reliability proof,
not the final product identity. Its `world_8_finish_game` contract starts from
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

## Next proof: Stardew Valley

The first modern-game proof uses the visible, windowed game, ordinary player
input, and a disposable copy of an owner-provided local save. The first bounded
goal is:

> Water every currently planted crop, then return to the farmhouse entrance.

The proof reconciles crops observed with crops watered and reports time, energy,
tool use, refills, final position, and protected actions. It does not purchase,
sell, discard, gift, enter consequential dialogue, choose story outcomes,
sleep, overwrite the owner's primary save, read process memory, use a hidden
game API, or claim headless regression as player-facing proof.

V2.10 implements the operator foundation separately from Mario. The adapter owns
verified disposable-save creation, process/window continuity, screen-only crop
and resource observations, fresh player/agent ownership, ordinary input
filtering, exact watering reconciliation, neutral stop, primary-save
reverification, and append-only evidence. Unknown or occluded crops, missing
resources, save/process/window mismatch, ambiguous authority, protected-action
risk, or incomplete evidence stop the attempt. Final visible and owner proof is
deferred to the consolidated campaign; no Stardew execution or acceptance is
claimed.

V2.11 adds screen-only Observe conversion, provenance-grounded Tell, one-task
fresh-copy review-only Show, and same-current-session Do with exact volatile
authorization, per-input revalidation, immediate reclaim, neutral handback,
completion reconciliation, and safe disposable-copy reset. Stardew facts and
safety remain adapter-owned behind the shared envelope. V2.12 implements the
combined catalog with final validation deferred.

## Combined product

Mario and Stardew must use the same session contract:

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

The root product now shows both adapter-owned catalog entries without flattening
their capability truth. Explicit switching fails closed until input is neutral,
player handback is confirmed, the current attempt is retained, and continuity
is known. Catalog-switch evidence has its own classification; no observation,
authority, goal/profile state, save/process identity, route/crop state,
recovery, or game-evidence claim crosses adapters. Only schema-versioned,
bounded, namespaced presentation preferences persist locally.

## Catalog growth

V2 ends with a barebones New Game Onboarding flow for collaborators. It can
scaffold an experimental adapter, declare its capabilities and safety rules,
attach fixtures, run conformance checks, and install it locally. Experimental
adapters expose only proven capabilities and cannot enter the trusted supported
catalog without explicit review and game-specific live evidence.

The ordered implementation and acceptance gates are in the
[Game Companion V2 roadmap](v2-roadmap.md).

## Boundaries

- Local-only by default; no cloud telemetry.
- Offline, owner-controlled, single-player games only for V2.
- No multiplayer, competitive play, anti-cheat environments, purchases,
  economies, or unauthorized permanent decisions.
- Diagnostic, assisted, review-only, unattended, and owner-accepted evidence
  remain distinct.
- Reliability metrics cannot substitute for owner usefulness feedback.
- The user can cancel or take over; no input continues after handback.
- V2.6–V2.12 are implementation-complete only. The prepared owner pilots and
  consolidated validation campaign have not run and cannot be inferred from UI,
  deterministic, scenario-contract, or route evidence.
