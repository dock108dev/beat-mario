# Unattended Regression Operator Guide

Game Companion V2.13 implements an optional local regression runner for an
adapter that explicitly declares unattended support. It is an engineering
surface, not a player play mode. Implementation is complete and final
validation is deferred; no unattended attempt was run while V2.13 was built.

## What its results mean

Every manifest permanently binds:

```text
classification=unattended_regression
evidence_classification=unattended_regression_result
execution_classification=unattended_regression
may_count_toward_reliability=false
may_count_toward_owner_acceptance=false
visible_live_proof=false
authoritative_game_outcome=false
network_access_allowed=false
```

An unattended result can describe bounded technical behavior and repeatability.
It cannot be visible player proof, Show evidence, route-reliability acceptance,
authoritative game completion, owner usefulness, owner acceptance, or a
replacement for the consolidated campaign. A visible-run reference is stored
only as correlation, never equivalence or causation.

## Architecture

`UnattendedRunner` is adapter-neutral. It owns eligibility, source and dirty
fingerprints, immutable manifests, safe paths, environment sanitization,
display continuity, isolated processes and run directories, run and aggregate
timeouts, sequential execution, exact-attempt cancellation, cleanup, failed
evidence retention, repeatability comparison, local reports, and proof limits.

Each `UnattendedProvider` owns support status, assets, executable and argument
vector, observation/input backends, fixture policy, protected data/actions,
milestones, success/failure predicates, cleanup, and adapter evidence. The
shared runner selects providers by registry identity and contains no Mario or
Stardew game-id branches.

A declared display provider represents a normal local desktop, a supported
local virtual display exposing rendered pixels to the adapter's ordinary
screen path, or no display. Identity and availability are frozen before launch
and checked throughout execution. Display loss stops the exact owned process,
retains the attempt, and fails closed. Virtual-display output is never visible
player proof. Remote displays, cloud runners, hidden APIs, and process-memory
observation are unsupported.

## Commands

Capability, plan, manifest, status, and comparison inspection do not launch a
game. Planning produces a manifest preview without creating an attempt.

```bash
.venv/bin/python -m smb3_agent unattended capabilities --adapter smb3
.venv/bin/python -m smb3_agent unattended plan \
  --adapter smb3 \
  --display-provider local-desktop \
  --display-backend normal_desktop \
  --display-identity WINDOW_SERVER_ID \
  --display-probe-executable /absolute/path/to/local-display-probe \
  --rom /absolute/owner/path/to/smb3.nes \
  --fceux /absolute/path/to/fceux \
  --goal-version GOAL_VERSION \
  --profile-version PROFILE_VERSION \
  --solution-version SOLUTION_VERSION
```

Stardew planning additionally requires a dedicated regression fixture, the
local executable, and every configured owner-save root. The fixture and fresh
copies must not equal, contain, or be contained by an owner-save location.

Execution requires an eligible scenario and the exact acknowledgement:

```bash
.venv/bin/python -m smb3_agent unattended run [the same plan options] \
  --runs 3 --per-run-timeout 300 --aggregate-timeout 1000 --concurrency 1 \
  --acknowledgement I_UNDERSTAND_UNATTENDED_REGRESSION_ONLY

.venv/bin/python -m smb3_agent unattended status ATTEMPT_ID
.venv/bin/python -m smb3_agent unattended cancel ATTEMPT_ID
.venv/bin/python -m smb3_agent unattended manifest ATTEMPT_ROOT/manifest.json
.venv/bin/python -m smb3_agent unattended compare ATTEMPT_ROOT_1 ATTEMPT_ROOT_2
```

Every run gets a fresh directory and process. Commands are argument arrays;
no shell is involved. Concurrency defaults to and is currently bounded to one.
A retry is a new attempt and cannot overwrite its predecessor. Cancellation
targets one attempt: the running owner stops input, terminates only its process
group, performs bounded provider cleanup, and retains all evidence. Process,
display, input, timeout, missing-evidence, or cleanup loss fails closed.

## Adapter boundaries

The Mario provider references an owner-configured ROM by local path, size, and
hash but never copies or exports ROM bytes. It launches fresh FCEUX processes
through the existing route/controller path, leaves gameplay observers and
contracts unchanged, and writes only below the unattended attempt. It cannot
mutate accepted evidence, reliability aggregates, routes, fastest-run indexes,
learning candidates, or owner history.

The Stardew provider accepts only a dedicated regression fixture and makes one
fresh disposable copy per run. It refuses owner-save overlap and symlinked
fixture content. It uses declared rendered pixels, ordinary input, and the
existing protected-action policy. Purchases, sales, discards, gifts,
consequential dialogue, story choices, sleep, and save operations remain
forbidden. Crop/resource/position facts must reconcile exactly. Every terminal
path requires neutral input, handback verification, primary-save exclusion,
and retained evidence. It cannot populate either owner-pilot manifest.

## Artifacts and repeatability

`data/scenarios/unattended-artifact-contract.yaml` requires the manifest,
invocation, environment, display diagnostics, per-run reports, classified
events, stdout/stderr, timing/exit status, last-good milestone, first missing
requirement, failure/cleanup records, aggregate report, integrity inventory,
and proof limits.

Comparisons require exact adapter/scenario/goal/profile/solution, source,
asset/fixture, display, environment, runner, and evidence-contract identity.
Reports keep requested/completed/passed/failed/cancelled/timed-out counts,
hashes, milestone/outcome agreement, resource/state deltas, failures,
artifact/cleanup completeness, and unknowns. There is no blended score.

Prepared tests and final-campaign hooks have not run. After V2.14 implementation,
freeze one cumulative release candidate and begin deterministic contract
validation before any live or owner proof.
