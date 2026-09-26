# Adaptive Assistance and Reviewable Solution Learning

The learning layer turns the local run library into reviewable learning
evidence. It does not turn a captured controller trace into an accepted route.
All data stays local under `artifacts/learning`; no credentials,
cloud identifiers, telemetry, or unnecessary owner identity are stored.

## Evidence classes

Raw observed runs, fastest locally observed runs, player bests, agent bests,
mixed-actor completions, derived patterns, candidate tactics, candidate
solutions, preferences, validation-approved candidates, replay-verified
candidates, executable solutions, rejected candidates, and rolled-back
solutions are separate classifications. “Fastest observed” is a local timing
fact, not a strategy judgment. A successful input trace is a non-executable
candidate until compatible replay and promotion gates pass.

## Learning envelope and compatibility

`AttemptContract` references the immutable observed run and adds adapter version,
level and segment, objective ID/version, exact start and terminal boundaries,
timing units, complete-interval status, emulator assumptions, allowed
techniques, resource policy, required and observed facts, evidence integrity,
progress anchors, trace references, and actor ownership.

Two attempts are comparable only when all contract fields agree and both have
complete timing and intact required evidence. Incompatible attempts stay in
history but are excluded from timing claims, tactic ranking, personal records,
and candidate derivation.

## Derivation

The default repeated-trouble threshold is three compatible attempts. Patterns
retain every supporting run and counterexample. Successful tactics require a
completed supporting attempt plus a compatible comparison attempt. Silence and
ignored advice are never evidence of preference or success.

Automatic reprocessing is content-addressed and idempotent. It may create a
`review_required` candidate containing its objective boundary, preconditions,
proposed action, provenance, expected benefit, risks, protected resources and
decisions, recovery boundary, unsupported assumptions, validation requirements,
and stable hash. It does not edit goal contracts, route order, solution files,
reliability profiles, accepted evidence, run-library records, or preferences.

## Lifecycle and promotion

The fail-closed lifecycle is:

```text
observed -> candidate -> review_required
review_required -> rejected | approved_for_validation
approved_for_validation -> validation_failed | replay_verified
replay_verified -> promotion_ready
promotion_ready -> promoted
promoted -> rolled_back | superseded
```

Review approval means only “may enter later validation.” Compatible replay
evidence is required before replay verification. Promotion readiness also
requires a Route Lab route-patch ID, the exact diff, and affected reliability
evidence. Promotion is the only path that updates the atomic accepted-solution
registry. Rollback atomically restores the prior registry entry and retains the
candidate, decision, promotion, and rollback history. The existing route-patch
workflow remains responsible for applying and reversing the exact repository
diff.

## Local personalization

Preferences are explicitly owner-edited and scoped by game and objective:
Quiet/On-request/Proactive help, solution style, risk tolerance, protected
resources, spoiler level, confirmed helpful or dismissed suggestion types, and
comparison target. They are inspectable and resettable. They cannot override
protected resources, explicit current-session choices, safety policy, or a
takeover authorization.

## Persistence and recovery

The store appends checksum-bound `game-companion-learning/v1` events and
atomically rebuilds derived indexes. Stable IDs and candidate content hashes
make repeated processing idempotent. Unknown schema versions and checksum
mismatches fail explicitly. Rebuilding an index never rewrites raw run
evidence. Candidate review packets are hash-bound exports that declare the
existing `beat-mario.route-patch/v1` promotion mechanism and its missing gates.

Useful inspection commands are:

```text
python -m smb3_agent learning status
python -m smb3_agent learning recover-index
python -m smb3_agent learning backfill-run-library
python -m smb3_agent learning export CANDIDATE_ID
python -m smb3_agent learning review CANDIDATE_ID approve --reason "..."
```

These commands inspect, recover derived indexes, idempotently wrap historical
observed runs, export, or review. They do not
run replay validation, promote a route, or start the emulator.

## Deferred final campaign

`data/learning/campaign_cases.yaml` enumerates compatibility, thresholds,
counterexamples, candidate derivation, idempotency, invalid transitions,
review, rejection, validation failure, promotion readiness, exact-diff
promotion, rollback, supersession, corruption/recovery, preference reset,
advice provenance, UI classification, and takeover-isolation cases. None
of those cases is accepted until the consolidated V2 final-validation campaign
runs against the frozen cumulative release candidate.
