# Stardew Companion Guide

## Current beta work versus existing implementation

The September 23 [engineering packet](personal-beta-engineering.md) requires live setup/perception/input in B3, harvesting/planting/selected-debris clearing and a combined routine in B4, and shared conversational planning in B2/B5. Shared B2 planning now describes these actions with explicit fixture/unavailable-live eligibility; the live B3/B4 capabilities remain required implementation work. See the [B3 interface handoff](b2-conversation-guide.md#implementation-seams-for-b3). The guide below describes the existing watering-only contracts. Extend task-specific observations, resources, ledgers and postconditions while preserving primary-save protection; do not treat the old watering guard as approval for every farming action. No new owner scope decision is needed to begin the planned engineering.

V2.11 implements standalone Stardew companion modes above the V2.10 visible
operator for one bounded task:

> Water every crop planted at the initial exact observation, then return to the
> visibly confirmed farmhouse entrance.

The domain implementation and deterministic tests are complete; live product
integration and owner validation are deferred. The public `stardew` CLI and
`/stardew` server route are inspection-only: they report capability truth and
render a safe unconfigured surface. They do not select or copy a save, detect
or launch Stardew, construct an ordinary-input driver, or operate the game.
This guide describes the implemented controller contracts, not accepted live
behavior.

V2.12 exposes this unchanged standalone workspace at `/stardew` from the
combined catalog at `/`. Stardew supplies its own catalog truth. A switch is
refused during active Show/Do/input, reclaim, neutralization, ambiguous
ownership, unconfirmed handback, incomplete retention, unsafe reset, or unknown
window continuity. Mario state and evidence can never satisfy this adapter.

## Mode separation

Observe converts the adapter-owned `ScreenObservation` into the shared
`CompanionObservationEnvelope`. The shared envelope carries identity,
freshness, exact confidence, evidence, input owner, and opaque adapter facts;
Stardew alone interprets its copied-save identity, crop ledger, energy, can,
refills, and position. Mario records receive no Stardew fields.

Tell is advisory only. It selects the next confirmed unwatered crop, asks for
the watering can when needed, identifies a visibly safe refill, sends the
player back to the farmhouse entrance, or names the first reason to stop. Every
factual item cites retained screen evidence, the exact watering ledger, or the
Stardew safety policy. Tell never sends input, grants authority, fills unknowns,
recommends protected actions, or infers completion.

Show demonstrates only the bounded watering task on a fresh disposable copy.
It requires a fresh exact observation, uses only ordinary configured input, and
stops on completion, reclaim, timeout, failure, ambiguity, continuity loss,
save mismatch, or protected-action risk. Its retained attempt is always
`review_only`; player completion, authoritative evidence, owner acceptance,
reliability promotion, and transfer into Do are false.

Do starts only after the owner explicitly authorizes the exact task in the
currently observed live session. The volatile authorization binds the copied
save and nonce, process start, window, starting observation, expiry, supported
input driver, stop point, and stop conditions. It is never restored from disk.
Before every input, the controller rechecks authority, current observation,
save/process/window continuity, driver availability, and safety. Progress
advances only after a new exact screen observation proves the purpose-specific
postcondition.

## Freshness and screen-only truth

The usable state remains visible-screen-only. No process memory, hidden game
API, save parsing as live truth, invisible capture, or invisible automation is
accepted. The observation becomes stale immediately on copied-save mismatch,
process-start or window change, window trust loss, occlusion, incomplete crop
coverage, missing screenshot evidence, crop confidence below exact, or unknown
energy/can/position state. Stale or unknown state disables Tell, Show, and Do.

## Reclaim, handback, and failure

Immediate reclaim neutralizes the configured driver first, invalidates the
active epoch, restores player ownership, and preserves the partial Show or Do
attempt. The same ordering applies to completion, timeout, cancellation,
ambiguity, protected-action refusal, save mismatch, process/window loss,
ordinary-input loss, evidence loss, and unexpected failure.
If input dispatch and neutralization both fail, both causes remain in the
failure record, authority is cleared, and player handback remains unconfirmed.
Operational details are in [Error handling and operations](error-handling.md).

Every stopped attempt records its mode/classification, before and after screen
observations, actor-labeled inputs, crop/resource/position ledger, stop reason,
first unmet requirement, neutralization, handback, primary-save result, reset
status, and evidence hashes. A failure never resumes from persisted authority or
retries in place.

## Exact completion

Completion requires the initial crop set to remain exact, every initially
planted crop to be visibly reconciled as watered, monotonic tool/refill and
energy accounting, exact can state, the visibly confirmed farmhouse entrance,
neutral input, player ownership, an unchanged primary save, and every required
evidence file present and hashed. Implementation completion does not satisfy
these runtime facts.

## Disposable-copy reset

Reset operates only by creating a fresh attempt-owned destination from the
unchanged primary. The manager verifies the primary before and after, refuses
existing, symlinked, nested, aliased, mismatched, or reused destinations, and
never overwrites, modifies, renames, deletes, or launches the primary. The old
copy and attempt remain preserved.

A successful reset creates a fresh save identity and invalidates all prior
observations, Tell cards, Show sessions, Do attempts, authority epochs, and
resumability. An active reset first requires input neutralization and player
handback.

## Stardew safety policy

Only navigation, watering-can selection, crop watering, visibly safe refill,
return to the entrance, and neutralization are valid purposes. The adapter
continues refusing purchases, sales, discards/trash, gifts, consequential
dialogue or story choices, sleep/bed interaction, save/overwrite behavior,
unknown refill locations, and any input outside the watering contract. Any
uncertainty in state, resources, ownership, identity, continuity, or evidence
also stops input.

## Standalone operator surface

The separate Stardew surface shows current mode and availability reason,
observation freshness and evidence, contextual Tell, Show start/stop/status with
review-only labeling, Do scope and expiry, current input owner, immediate
reclaim, neutralization and handback, reset status, crop/energy/can/refill/
position reconciliation, protected-action refusal, and first failure with safe
recovery. Controls remain disabled when their exact preconditions are absent.
Desktop and 390-pixel standalone contracts are prepared. The V2.12 combined
shell links this surface without weakening its adapter-owned controls.

There is currently no public configuration/start action for these controls.
They remain disabled in the supported surface because no live save, window,
observation, or input driver is attached.

These inspection commands do not detect, open, copy, reset, or operate Stardew:

```bash
.venv/bin/python -m smb3_agent stardew status
.venv/bin/python -m smb3_agent stardew operator-render --output /tmp/stardew-operator.html
.venv/bin/python -m smb3_agent companion catalog-status
.venv/bin/python -m smb3_agent companion render --output /tmp/game-companion.html
```

## Deterministic coverage and deferred evidence

`data/stardew/fixtures.yaml`, `data/stardew/evidence-contract.yaml`, and the
Stardew test modules cover Observe conversion/freshness, adapter
isolation, Tell provenance/refusal, Show classification/lifecycle, Do binding
and per-input revalidation, reclaim across every phase, neutral handback,
timeout/cancellation/continuity/input loss, protected actions, reset and stale
authority, exact reconciliation, evidence hashes, first-unmet reporting,
desktop/narrow presentation, and Mario contract preservation. They were not
used with an owner save or live Stardew process. Catalog/switching and render
contracts are also exercised by the non-live suite.

The consolidated campaign must begin from a frozen cumulative release
candidate with deterministic contracts, then produce visible Stardew technical
proof and owner-pilot proof. The owner makes every authorization, reclaim,
feedback, usefulness, and acceptance decision. V2.12 is
implementation-complete with final validation deferred; V2.13 unattended
regression and V2.14 Experimental onboarding are also implemented and
Non-live-tested, but neither supplies Stardew live or owner proof.
