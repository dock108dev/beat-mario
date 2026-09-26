# Historical campaign procedure

This document retains the earlier versioned campaign workflow. It is an
engineering history record, not the current setup guide or current delivery
qualification. Use the [README](../README.md) to run the application and the
[delivery record](b8-personal-delivery.md) for identified build and review limits.
Historical schema names and phase identifiers below are retained for interpreting
existing contracts; they do not establish current-source readiness.

## Retained existing campaign procedure

The final campaign is prepared but has not run. V2.6 through V2.14 may be
implementation-ready and eligible to enter the campaign while every live,
reliability, usefulness, completion, and owner-acceptance result remains
pending. Campaign entry and campaign completion are deliberately separate.

The executable source of truth for this retained V2 procedure is `data/scenarios/final-campaign.yaml`; the
Mario owner workflow is frozen in `data/scenarios/mario-owner-pilot.yaml`; the
Stardew companion workflow is frozen in
`data/scenarios/stardew-owner-pilot.yaml`. Both contain release-candidate
identity placeholders, preconditions, owner
choices, expected product states, required evidence, failure retention, the
no-patching rule, first-unmet-requirement reporting, artifact reconciliation,
blank usefulness feedback, and a blank owner acceptance field.

## Readiness layers and candidate manifest

Implementation readiness means the required product surfaces, deterministic
fixtures, safety contracts, tests, and operator surfaces exist. Campaign-entry
readiness additionally requires one exact clean candidate, matching hashes for
the authoritative campaign contracts, passed deterministic gates, and verified
blank owner-response fields. The ignored manifest uses schema
`game-companion-campaign-entry-manifest/v1`, is defined by
`data/scenarios/campaign-entry-manifest-schema.json`, and lives below
`artifacts/campaigns/`; it binds the exact commit and Git tree without copying
or fabricating any owner response.

`scenario final-campaign-readiness` is an informational structured inspection.
Pass `--candidate-manifest` and `--gate` for a fail-closed entry gate. The output
keeps implementation blockers, candidate blockers, scheduled technical
validations, required owner actions, completion blockers, and proof limits
separate. Pending final owner acceptance never blocks entry, but it always
blocks campaign completion until the owner explicitly decides for that exact
candidate.

After the deterministic suites pass and the exact source commit is clean, bind
their real totals without filling owner fields:

```bash
.venv/bin/python -m smb3_agent scenario candidate-manifest \
  --output artifacts/campaigns/<exact-commit>/campaign-entry-manifest.json \
  --focused-readiness-total <total> \
  --focused-v2-total <total> \
  --canonical-total <total>
.venv/bin/python -m smb3_agent scenario final-campaign-readiness \
  --candidate-manifest artifacts/campaigns/<exact-commit>/campaign-entry-manifest.json \
  --gate
```

The first command refuses a dirty repository, a nonpositive total, or nonblank
owner fields. The gate verifies the manifest against current `HEAD`, the Git
tree, repository cleanliness, classification hash, and every authoritative
contract hash. Inspection without `--gate` retains exit zero for diagnostics;
gate mode exits nonzero when campaign entry is false.

## Attempt rules

Each attempt is immutable. The owner chooses every gameplay, support response,
authorization, reclaim, retry, usefulness response, and final decision. Do not
patch code, edit fixtures or manifests, rebuild evidence, promote or roll back a
candidate, or run historical backfill during an attempt. Failure retains the
complete attempt; retry creates a fresh attempt identity.

Completion claims require game-owned evidence and safe handback. Technical
success, route reliability, review-only Show, unattended output, owner
usefulness, owner acceptance, and authoritative game outcomes retain distinct
classifications. None can silently supply another.

## Mario owner workflow

The owner pilot covers first use, both observation launch choices, normal player
control, automatic profiles/runs, comparison and History, Tell, all coaching
policies, separate Show, current-session Do, goal-bounded control, immediate
reclaim, timeout/failure/cancellation/process-loss recovery, safe handback,
resumed observation, candidate review and learning clarity, full-game takeover,
usefulness/trust/control clarity, and the exact final owner decision.

The report must name the first unmet requirement. It may be empty only after
every required artifact, identity, transition, hash, classification, final
state, and owner field reconciles against the frozen release candidate.

## Stardew companion workflow

The owner selects the primary local save and authorizes creation of a verified
disposable copy. Only that copy may be opened. The campaign binds one visible
windowed process, one process-start identity, and one window identity, then
requires a complete screen-only farm sweep with exact planted/already-watered
crop ids, energy, watering-can state, tool uses, refills, and position.

The owner retains initial input ownership and explicitly authorizes only the
task to water the frozen initial crop set and return to the farmhouse entrance.
Every watering and refill must have before/after visible evidence. Completion
requires exact crop reconciliation, the visibly exact entrance position,
neutral input, player handback, unchanged primary save, and the complete
artifact contract.

The same campaign must retain separate failed attempts for unknown or occluded
crops, incomplete sweep, save mismatch, primary-save risk, ambiguous/expired
ownership, protected-action refusal, disconnection, process/window loss, and
missing evidence. It must inspect desktop and 390-pixel presentation and keep
input owner, unknowns, stop, and recovery visible.

The campaign must also prove the V2.11 mode boundaries from the frozen release
candidate. Observe must preserve copied-save/process/window identity, exact
confidence, crop/resource/position facts, and evidence while going stale on the
first continuity gap. Tell must remain input-free and provenance-complete. Show
must use a fresh disposable copy and remain review-only. Do must bind a fresh
owner authorization to the exact current live session and revalidate before
every input and after every expected postcondition. Reclaim is exercised during
every active phase; timeout, cancellation, ambiguity, protected action, and
process/window/input loss must all neutralize before handback. Reset must create
a fresh destination, preserve the previous attempt, reverify the primary, and
invalidate all prior observations, Tell cards, mode attempts, authority, and
resumability.

The owner chooses every authorization, reclaim, feedback response, and final
decision. The blank Stardew pilot fields cannot be populated by fixtures,
automated traversal, Mario evidence, or an implementation claim. No patching,
manifest editing, historical backfill, or retry-in-place is allowed during an
attempt.

## Preserved later campaign requirements

V2.12's implemented catalog must exercise capability-isolated Mario/Stardew
selection, every switching refusal, neutral handoff, volatile-state
invalidation, safe persistence recovery, root/standalone/Lab preservation, and
desktop/390-pixel presentation. Catalog-switch evidence must remain separate
from both games' evidence.
V2.13's implemented runner must prove repeatable isolated execution, immutable
regression-only classification, Mario/Stardew provider isolation, failure
retention, exact-process cancellation, cleanup, owner-data protection, and
correlation-only visible references. Its output cannot substitute for visible,
Show, reliability, authoritative, owner, or campaign proof.

V2.14's fixture-only scenario must validate the contract, compare deterministic
scaffolds, run every conformance check, prove path/symlink/command/code/network/
collision refusal, install and discover the sample as Experimental, demonstrate
rollback, refuse modified removal, then cleanly remove only exact manifest-owned
files with zero process, authority, input, and session state while preserving
evidence/history. Its proof-limit artifact must explicitly deny real-game
compatibility, live observation correctness, effective input, reliability,
authoritative completion, usefulness, owner acceptance, and Supported
eligibility. The final explicit owner decision remains required. Mario live,
takeover, reclaim, route, reliability, and owner requirements remain unchanged
and deferred.
