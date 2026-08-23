# Stardew Companion Guide

V2.11 implements standalone Stardew companion modes above the V2.10 visible
operator for one bounded task:

> Water every crop planted at the initial exact observation, then return to the
> visibly confirmed farmhouse entrance.

Implementation is complete and final validation is deferred. No Stardew game,
save copy/reset, fixture, scenario, owner pilot, input, or presentation check
ran while building this slice. This guide describes contracts, not acceptance.

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

These inspection commands do not detect, open, copy, reset, or operate Stardew:

```bash
.venv/bin/python -m smb3_agent stardew status
.venv/bin/python -m smb3_agent stardew operator-render --output /tmp/stardew-operator.html
.venv/bin/python -m smb3_agent companion catalog-status
.venv/bin/python -m smb3_agent companion render --output /tmp/game-companion.html
```

## Deferred evidence

`data/stardew/fixtures.yaml`, `data/stardew/evidence-contract.yaml`, and
`tests/test_stardew_companion.py` prepare Observe conversion/freshness, adapter
isolation, Tell provenance/refusal, Show classification/lifecycle, Do binding
and per-input revalidation, reclaim across every phase, neutral handback,
timeout/cancellation/continuity/input loss, protected actions, reset and stale
authority, exact reconciliation, evidence hashes, first-unmet reporting,
desktop/narrow presentation, and Mario contract preservation. They were not
executed. V2.12 catalog/switching contracts and tests are likewise prepared and
unexecuted.

The consolidated campaign must begin from a frozen cumulative release
candidate with deterministic contracts, then produce visible Stardew technical
proof and owner-pilot proof. The owner makes every authorization, reclaim,
feedback, usefulness, and acceptance decision. V2.12 is
implementation-complete with final validation deferred; V2.13 and V2.14 remain
unstarted.
