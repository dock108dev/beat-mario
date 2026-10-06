# Adaptive Assistance and Reviewable Solution Learning

Local learning records store compatible coaching and observed outcomes for later
attempts. Model-directed Mario play retrieves descriptive context; deterministic
coin routes also use retained outcomes. Generalized improvement, model training
and player demonstration qualification are unsupported. See
[architecture](agent-architecture.md#conversation-gameplay-and-control).

The learning layer turns the local run library into reviewable learning
evidence. It does not turn a captured controller trace into an accepted route.
Learning and gameplay evidence are retained locally under their existing learning,
conversation and player-history owners. The current Ollama reference path uses local
inference. The required Codex-backed app will send selected contextual material to
the remote model during inference; local storage does not mean inference stays on
the Mac. Credentials and unrelated owner data must not be copied into learning
records or provider context.

## Required memory for the two AI roles

The language role retrieves relevant preferences, prior instructions, current
conversation context and unresolved questions. The gameplay role retrieves
applicable mechanics, discovered landmarks, failed/effective actions, coaching
and outcomes. The two roles can share one store and backend, but each must receive
the relevant evidence rather than an unbounded transcript or the entire archive.

Keep these records distinct:

| Record | Meaning and use |
| --- | --- |
| Current observed state | Facts grounded in a current game observation, with evidence and uncertainty. Freshness is rechecked before action. |
| Mechanics and reference knowledge | Adapter-owned rules or sourced game knowledge, versioned independently of the current scene. A rule does not prove the required object/resource is present. |
| Player preferences and coaching | Original words, resolved meaning, effective scope, supersession and compatibility. Current choices override older preferences. |
| Episode or attempt | Goal, proposed/selected actions, actually applied parameters, observed effects, discoveries, failures, resources and release. Partial or failed outcomes remain useful evidence. |
| Derived guidance | A hypothesis or useful lesson linked to supporting episodes and counterexamples. It remains uncertain where evidence is weak. |
| Conversation summary | Bounded continuity for references, constraints and unresolved questions. A summary cannot upgrade a hypothesis to fact or restore approval. |

Retrieve by game/level or activity, state and capability compatibility, relevant
objective and the decision being made. Include applicable failures and
counterexamples, not only successful results. Historical/off-screen observations
must retain their age and provenance; they cannot silently become current world
state. Incompatible knowledge may inform discussion but cannot directly create an
executable action.

Persist the understood goal and the model's selected action, supporting evidence,
expected effect, actual effect, updated knowledge and subsequent decision. Record
which decisions were model-generated versus deterministic runtime/controller work.
Keep concise decision explanations; private chain-of-thought collection is
unnecessary.

The initial beta requires memory to influence actual later decisions. Show a
coaching instruction or discovery changing the selected action/target/parameters
in a compatible later attempt, and show a changed condition causing a different
decision with the same code. Storing a note, replaying one trace or selecting among
three fixed routes is an implemented foundation, not sufficient proof of the
required learning behavior. No new neural-network training or unattended practice
service is needed for this milestone.

Inspection/reset must show the guidance in use, its basis and scope. Reset or
supersession affects future retrieval while preserving historical episodes.
Conversation compaction and index rebuilding must preserve exclusions, remaining
work, uncertainty and the original evidence references. Reopening requires fresh
game context and approval; neither memory nor a resumed Codex thread grants input
authority.

Verification combines deterministic retrieval/compatibility/reset checks,
real-model contextual decisions and live application/outcome checks. Test
contradictory feedback, changed objectives, stale/off-screen facts, incomplete
results, incompatible entries, summary loss, duplicates, interruption and reopening.
Report whether guidance was retrieved, applied and helpful as separate results.

## Ordinary experimental coaching

`mario_coaching.py` owns a versioned local profile at `artifacts/conversation/coaching.json`, compatible only with `smb3/world-1-1/opening-hop/v1`. It stores original coaching words and prior/new delay frames. Conversation plans copy the guidance into each attempt; the Mario runtime validates its range and opening-only scope and passes timing to the Lua controller. Controller events distinguish requested guidance from observed application. Outcomes retain failures, partial stops, input release and compatible comparisons; application alone never establishes improvement.

The finite attempt budget is volatile. Reopening restores descriptive guidance/outcomes, never authority. Reset changes future guidance only and preserves history. Explicit Retry checks the approved session, deadline, neutral handback and exact cartridge before fresh disposable startup. Engineering promotion, accepted routes and reliability evidence are unchanged.

## Experimental coin-route memory

`mario_coins.py` derives compatible route knowledge from append-only conversation outcomes, separately from the accepted registry. Cartridge fingerprint plus the World 1-1 coin-discovery version binds observations. Finite approvals remain volatile. Each attempt carries original words, selected route, controller application, per-frame level-counter observations, landmark yields, failure/finish and neutral handback. Deduplication is by frame within an attempt; retries have independent baselines. Accumulated knowledge retains per-landmark maxima; the known coin opportunity lower bound is the best single-attempt count, never a sum of collections from different attempts. Missed opportunity uses the maximum historical yield in the completed bands from one prior attempt, preventing cross-attempt boundary shifts from inflating a total. Shortfalls against prior verified segment yields are opportunity lower bounds; individual coin identity remains unknown. Untried alternatives change scheduled jump windows and durations in the actual Lua traversal; measured finished-route yields can influence subsequent selection. Counter discontinuity prevents a trusted total and no record asserts full coin coverage.

## Player-recorded experimental sequences

Recording, demonstration application and the attended stairs walkthrough remain
deferred to a later beta, tentatively beta v2. The source and evidence below are
preserved; real demonstration application is unverified and does not block the
initial model-driven beta.

`mario_demonstrations.py` owns saved traces, range validation, cartridge/version compatibility, trace hashes, names/lessons and visual/action review. `fceux_demonstration.lua` reads effective player inputs after each frame paired with its pre-frame state; it writes no game input or RAM. `live_observation.py` owns process-bound recorder requests and excludes native companion authority while recording. `conversation_service.py` owns explicit use/review/approval and durable application outcomes; `mario_plan_runtime.py` binds validated numeric traces to the exact cartridge/session; `fceux_b2_plan.lua` matches entry, overrides real inputs, audits them and stops on divergence or segment completion. No trace becomes historical accepted-route authority.

Saved demonstrations under `artifacts/conversation/demonstrations/` are distinct from ordinary coin-route candidates and engineering promotion. Application records retain immutable content/lesson hashes and observed controller receipts. Completion of a recorded sequence does not establish improvement or level completion. Reopening restores descriptive examples/outcomes only. See [verification](gc2-demonstration-verification.md).

## Implemented evidence classes

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

## Implemented accepted-registry lifecycle and promotion

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
diff. This is the historical accepted-solution promotion contract. It must not
become a requirement for each ordinary player-coached experimental trial.

## Ordinary experimental memory and required extension

The initial beta must let a user watch Mario, coach a relevant action and see compatible later play reflect that guidance. The narrow opening-timing loop and authored coin-route memory are implemented; contextual model interpretation and adaptive strategy remain required. Preserve original coaching and resolve its target, amount and applicability before claiming a change. Retain discoveries, branches tried, missed opportunities and coverage uncertainty across attempts/lives. Saying that a correction was saved is distinct from confirming it reached the controller or improved the outcome.

Add local, inspectable and resettable records for the experiment objective/route version; attempt/life and observation boundary; discovered route/coin facts with provenance; the original coaching text; resolved target, parameter/tactic revision and scope; application eligibility/effective boundary; controller acknowledgment; result and confirmed release. Preserve superseded revisions and negative results. Current user choices override older coaching, and incompatible game/route/entry/ability records may inform a discussion but cannot silently become an executable action.

Use two distinct paths:

| Path | Purpose and acceptance |
| --- | --- |
| Local opening coached experiment — implemented | An explicit reviewed trial may execute an implemented bounded action using a versioned local experiment and fresh runtime authority. The player can change timing/tactics, retry within reviewed limits and retain each result without authoring a repository patch. Label it Experimental and report its observed success/failure and remaining uncertainty; one successful trial does not turn it into the historical accepted route. |
| Historical accepted solution — implemented | Keep the existing compatibility, replay, exact-diff reliability, promotion and rollback gates before altering the accepted-solution registry. Historical route contracts and accepted evidence remain immutable; experimental successes are not relabeled as prior accepted evidence. |

An experiment still needs a supported controller/action, current compatible observation, clear limits and confirmed release. Conversational coaching cannot authorize arbitrary code, raw native input, process-memory mutation or a missing capability. Implement and record the supported retry/reset entry method; experimental attempts do not change the entry/evidence rules of historical accepted routes. The ordinary opening experiment is implemented by `mario_coaching.py`, conversation orchestration and the validated Mario runtime/Lua controller; `custom_variants.py` and historical derivation/promotion remain separate owners.

A reviewed finite attempt/life budget can cover multiple compatible retries; the user need not approve every life while the same scope and authority remain valid. Recheck eligibility/limits after each retry. Reclaim, invalidated authority and material scope expansion require new approval. Coaching within the reviewed adjustment range may be acknowledged/applied; other changes need review.

The model-driven extension must connect the entire loop: retain an attempt → understand contextual coaching → bind the revised goal and finite attempt/life budget → choose an applicable supported action → execute and independently observe its effect → retain and explain the result → use that result in another decision. Reopening retains the owner's words, discoveries, prior/new parameters and application status, without authority. Verify late corrections, death/partial attempts, changed entry/ability, queued work during reclaim, supersession and reset. For coin exploration, distinguish known collectibles from unknown coverage and avoid double-counting discoveries from previous lives. Independent practice is deferred; it is not a prerequisite for useful reasoning with episodic memory.

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

## Historical deferred final campaign

`data/learning/campaign_cases.yaml` enumerates compatibility, thresholds,
counterexamples, candidate derivation, idempotency, invalid transitions,
review, rejection, validation failure, promotion readiness, exact-diff
promotion, rollback, supersession, corruption/recovery, preference reset,
advice provenance, UI classification, and takeover-isolation cases. None
of those historical cases is accepted until the retained campaign is actually
run against its declared candidate. These contracts do not cover Codex-backed
contextual intent or adaptive gameplay. Initial private-beta acceptance needs
focused evidence for the new two-role architecture and the delivered app, as
defined in the active engineering plan.
