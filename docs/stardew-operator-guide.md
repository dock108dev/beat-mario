# Stardew Companion Guide

## Setup and live-input prerequisites

The `/stardew` workspace provides disposable setup, conversation, reviewed scope, explicit Start, observation refresh and pause/reclaim controls. It uses Stardew-owned session/runtime authority. Unconfigured setup and unqualified perception keep live input disabled.

Use an explicitly selected disposable farm. The isolated-game launcher redirects configuration and data into a fresh namespace, preserves HOME, and applies OS restrictions against primary-save paths and network access. It accepts only inspected game and runtime hashes. Installation or copying alone does not verify that the game loads and persists within that namespace.

On Apple Silicon, an Intel game/runtime may require [Rosetta](https://support.apple.com/en-us/102527). Session verification still requires same-session process/window loading and persistence evidence; the UI cannot bypass it with a manual verified flag.

The ordinary workspace now offers **Check isolated farm session** and a selection
of server-registered screen profiles. Verification requires retained real loading
and persistence proof. Profile connection is limited to the current verified farm
and retained calibration evidence; missing evidence leaves the selection empty.
These actions never grant gameplay authority. Review and Start remain separate.

Automatic recognition is implemented as strict pixel matching for a bounded fixed
viewport. **No qualified real-game pixel profile ships with this candidate.** A
profile must identify every tile in the complete planted area, player and farmhouse
return tile, equipped can and exact resources, with retained calibration/coverage
evidence. Unknown pixels, scrolling, scale changes, occlusion or unobservable exact
resource counts stop recognition. Synthetic profiles and manual annotations remain
development evidence. Refilling is not live-qualified.

The unchanged watering contract is:

> Water every crop planted at the initial exact observation, then return to the
> visibly confirmed farmhouse entrance.

A visible subset cannot silently replace that complete set. Harvest, planting,
selected-debris clearing and combined routines remain unavailable for live execution
until implemented and verified. See [Stardew integration and extension contracts](b3-integration-contract.md).

The sections below describe controller contracts; they are not a claim that the
missing real-game calibration, isolation or live watering has passed.

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
The combined shell links this surface while preserving adapter-owned controls. Render checks cover desktop and 390-pixel widths.

The ordinary workspace provides setup, conversation and review actions. Start
remains disabled until verified loading/persistence, fresh automatic observation,
complete reviewed scope and ordinary input are available. Native input code uses
bounded process-targeted pulses with foreground checks; actual delivery and visible
effects remain unverified without the game. Chat focus stops gameplay authority.
Pause preserves the partial outcome; continuation requires fresh observation,
review and explicit Start. Saved information never restores permission.

Launch from the repository:

```bash
.venv/bin/python -m smb3_agent lab ui --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/stardew`. Use **Open isolated engineering game** to request
a fresh title-screen attempt. Existing-save copying is under **Advanced** and needs
an explicit source and copying authorization. Describe “water these crops” only after
the engineering farm, isolation and visible perception are qualified. Missing
prerequisites remain visible and Start stays disabled; a screenshot or copied folder
does not bypass them. Focus/observation and Start explicitly activate only the verified
engineering PID; polling and questions never steal focus.

The public CLI remains inspection-only. These commands do not select or copy a save,
detect or open a game, reset a session, or operate Stardew:

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

Live verification must use the exact tested source and assets with an isolated farm. Fixture, catalog and render checks do not establish real input delivery, visible watering or gameplay usefulness.
