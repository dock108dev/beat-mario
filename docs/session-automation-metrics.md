# Session Automation and Local Product Metrics

V2.8 defines repeatable, adapter-neutral session scenarios and a local event and
metrics pipeline. This implementation is not a validation result. A scenario is
not made true by being defined, planned, or technically completed.

## V2.9 Mario product events

The Mario product prepares first-use, game-file detection/selection, identity
verification, emulator detection, input-readiness confirmation, session choice,
configuration failure, first-use completion, product-session start, History
update, and owner-feedback-prompt event types. The V2.9 scenario hooks bind
these to the existing observation, Tell, advice, Show, takeover, ownership,
reclaim, handback, learning, recovery, and reconciliation events.

These contracts are exercised by ROM-free tests. They do not populate owner
usefulness or owner acceptance, and they cannot upgrade technical or
review-only evidence.

## Scenario and evidence classifications

Every immutable scenario ID/version has a deterministic-only, visible
technical, owner-required, reliability, review-only, unattended-regression, or
final-campaign-orchestration classification. Evidence remains one of:

- deterministic fixture result;
- unit/integration result;
- technical session result;
- visible live result;
- route-reliability result;
- review-only Show result;
- unattended regression result;
- owner usefulness feedback;
- owner product acceptance; or
- authoritative game-owned outcome.

A technical pass cannot become route reliability, owner usefulness, owner
acceptance, visible live proof, or authoritative game completion. Unattended
execution is regression-only. Evidence classification is bound when the attempt
is created and cannot be upgraded after execution.

The catalog at `data/scenarios/catalog.yaml` covers observation, first baseline,
comparison, coaching, Show, learning review, takeover/reclaim, terminal
failures, Mario full-game control, planned Stardew scenarios, adapter switching,
unattended regression, experimental onboarding/removal, and final owner
acceptance. Later-slice definitions expose their capability blockers.

## Lifecycle and dry plans

Lifecycle states are `defined`, `preflight_pending`, `ready`, `blocked`,
`running`, `owner_action_required`, `cleanup_pending`, `completed`, `failed`,
`timed_out`, `cancelled`, `process_lost`, and `retained_for_review`.

Preflight fails closed for missing capabilities, fixtures, assets, or adapters.
Owner-required work cannot run unattended. Owner steps are never automated: a
final-campaign runner must pause and request the owner. A failed step blocks a
completion claim. Safe cleanup applies on terminal paths; failed artifacts are
retained; retries create new attempts; duplicate processing is idempotent.

Dry plans state what happens, which steps are automated, owner pauses, affected
process/save, allowed input, protected decisions, reclaim behavior, duration,
cleanup, retained evidence, and exact proof limits. V2.8 does not activate plan
execution.

## Versioned local events

`game-companion-event/v1` contains event, session, scenario/attempt,
correlation/causation, game/adapter, objective/profile/solution, actor,
input-owner, control-epoch, lifecycle, source/provenance/evidence, monotonic
sequence, emulator-frame, wall-clock, confidence, payload, artifact, and
integrity fields. Its schema is `data/scenarios/event-schema.json`.

Events cover observation/facts, inputs/ownership, Tell/coaching/suggestions,
comparison, profiles/runs, learning/candidates, Show, takeover/reclaim/handback,
outcomes/failures/recovery/process loss/cleanup, adapter switching, and evidence
reconciliation. Unknown, malformed, out-of-order, unsupported, contradictory,
corrupt, duplicated-content, or classification-changing events do not enter
derived metrics. Exact duplicate events are idempotent; conflicting duplicates
are quarantined.

## Exact metric contracts

Each metric names its numerator, denominator, unit, filters, unknown policy, and
one label: technical operation, route reliability, product behavior, owner
usefulness, owner acceptance, visible live evidence, unattended regression, or
authoritative game outcome.

The registry covers observation freshness/support/reconciliation; player and
agent ownership, authorization boundaries, conflicts and latency; Tell,
coaching, responses and comparison; takeover preflight, transfer, outcome,
continuity and handback; run actors, fastest compatible replacements, learning
and candidate lifecycle; and artifact completeness, integrity, classification,
duplicates and reconciliation. The required boundary-violation value is zero.

Unknown and failed evidence is never dropped to improve a percentage. Owner
usefulness comes only from explicit owner feedback during the final campaign.
Inputs, completion, ignored advice, elapsed time, technical success, and
unattended execution cannot supply it.

There is no combined success score because it would erase the distinction
between operation, gameplay proof, usefulness, and owner acceptance.

V2.13 stores unattended events in a dedicated `unattended_regression_result`
series. Ingestion requires the immutable regression-only fields and rejects
owner-feedback, owner-acceptance, fastest-run, candidate-review, or learning-
promotion mutations. Summaries report unattended event/attempt counts
separately and list route reliability, visible live counts, authoritative
outcomes, player completion, usefulness, acceptance, fastest-run indexes, and
learning promotion as excluded consumers. No blended score exists.

## Local storage, retention, recovery, and privacy

Raw events are append-only JSONL with integrity hashes. Derived indexes are
atomic and rebuildable from raw evidence. Unsupported versions fail explicitly;
corrupt raw evidence stops recovery at the exact line instead of being skipped.
Attempt binding preserves source, adapter, profile, solution, scenario, and
evidence versions.

Retention bounds never silently delete. Deletion/reset planning requires a
later explicit confirmation and protects accepted route evidence, reliability
artifacts, and owner acceptance. Exports retain provenance, classification,
raw events, metric definitions, failures, and unknowns.

The pipeline is local-only. It has no network telemetry, dashboard, pixel,
background upload, credentials, ROM content, unnecessary personal data, or
cloud identifiers.

## Command and UI surfaces

The CLI exposes scenario `list`, `status`, `plan`, and
`final-campaign-readiness`, plus metrics `summarize`, `export`, `rebuild`,
`schema`, and `status`. Generic scenario run/cancel entries are not supported;
unattended regression uses its dedicated bounded runner, and the consolidated
owner campaign must follow its explicit guide rather than a placeholder CLI.

The player view shows recent classified local activity, ownership, freshness,
suggestions, takeover/handback, run-library/learning changes, missing evidence,
and proof boundaries with technical detail collapsed. The Lab shows scenario
plans/blockers, schemas, counts, definitions/filters, artifact reconciliation,
failure retention, corruption/recovery, and campaign readiness.

## Final-campaign hooks and limitations

`data/scenarios/fixtures.yaml` lists deterministic and negative cases.
`data/scenarios/artifact-contract.yaml` defines required artifacts and retention.
Hooks cover malformed, duplicate, out-of-order, corrupt, unsupported, upgraded,
missing, mismatched, ambiguous, post-handback, unattended-owner, cleanup,
adapter-leakage, and incomplete-rebuild cases.

The deterministic and negative hooks are exercised by the ROM-free suite.
V2.13 implements unattended emulator execution, but no live unattended attempt
has run for the current candidate. Owner-pilot fields remain blank and the
disabled final campaign has not run. Historical backfill and candidate
promotion/rollback remain separate explicit operator actions rather than
automatic scenario behavior.
