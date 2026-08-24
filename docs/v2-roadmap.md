# Game Companion V2 Roadmap

## Outcome

V2 turns the accepted Mario automation system into a player-facing companion,
proves the same contract in Stardew Valley, combines both games in one catalog,
and finishes with a contributor path for adding experimental games.

The delivery order is intentional:

```text
Mario companion interaction
-> grounded help and bounded control
-> automated scenarios and product metrics
-> owner acceptance
-> visible Stardew operator
-> Stardew companion
-> combined catalog
-> unattended regression
-> new-game onboarding
```

Do not build a polished multi-game shell before the Stardew operator can
complete one visible bounded task. Do not treat headless or automated traversal
as owner acceptance.

## Shared session contract

Every game adapter must support the same player-facing lifecycle even when its
capabilities differ:

1. Identify the game, save/session, and current observable state.
2. Offer only goals supported from that state.
3. Let the player select `Tell`, `Show`, or `Do` when that mode is supported.
4. Display scope, expected stop point, protected decisions, and recovery policy.
5. Keep current objective, confidence, attempts, and recent activity visible.
6. Allow cancellation or takeover during `Show` and `Do`.
7. Verify success from game-owned observations.
8. Stop all input before declaring handback.
9. Report what changed, what was consumed, what remains uncertain, and where
   control was returned.

The system must say that a capability is unavailable rather than offer a mode
the selected adapter cannot prove.

## Slice V2.0 — Rebrand and product contract

Status: **complete / non-live validated**.

Rename the user-facing product and workbench to Game Companion, document Mario
as the first adapter, preserve existing technical identifiers, and make this
roadmap authoritative.

Acceptance:

- root README, product direction, docs index, local lab, CLI help, render gate,
  and tests use the Game Companion name;
- existing `smb3_agent` imports, commands, goal ids, presets, and artifact paths
  remain compatible;
- no gameplay or accepted evidence changes;
- focused UI checks and the canonical non-live gate pass.

## Slice V2.1 — Mario companion shell

Status: **complete / non-live validated**.

Build the player session above the existing Mario contracts. The default view
contains game, observed state, selected objective, supported modes, declared
stop point, protected decisions, progress, `Take Control`, and handoff. Route
engineering, evidence review, issue handling, and patch controls remain in a
secondary Lab view.

Acceptance scenarios:

- known checkpoint with all three modes available;
- known checkpoint with one unavailable mode;
- unknown/stale state with execution disabled;
- active, failed, cancelled, taken-over, and completed sessions;
- no completion copy without a game-owned outcome;
- responsive rendered UI and deterministic semantic hooks.

## Slice V2.2 — Grounded Tell

Status: **complete / non-live validated**.

Generate a short state-specific instruction card using observed facts, the
selected goal, and accepted segment knowledge. Add spoiler preference and a
list of decisions the companion must not make.

The output schema includes observed starting facts and confidence, next actions
and expected visual cues, resource or risk warnings, recovery guidance,
provenance for factual claims, and explicit uncertainty and refresh requirement.

Acceptance rejects unsupported facts, stale observations, goal/state mismatch,
hidden completion claims, and instruction cards without provenance.

The Mario implementation accepts either an adapter-supplied fresh observation
with explicit evidence or a clearly labeled player-reported checkpoint and
bounded inventory facts. Its validated Tell catalog covers exactly the 26
solved normal-gameplay segments reachable through supported product goals.
Minimal, Guided, and Full remain bounded to the selected segment. Protected
resource conflicts fail closed, every factual card item carries typed record
provenance, and Tell remains structurally separate from execution outcomes.
Show and Do remain unavailable.

## Slice V2.3 — Show demonstration

Status: **complete / live review accepted**.

Demonstrate one selected Mario segment using watchable execution. Synchronize
the playback with a concise cue card and retain the replay and game-owned
outcome.

`Show` is review-only and non-promotable. It supports stop/takeover, never
changes the accepted reliability record, and explains the difference between
what was demonstrated and what the player has completed.

## Slice V2.4 — Live player observation and input tracking

Status: **complete / live owner-play accepted**.

Launch one normal visible player-controlled FCEUX session with a read-only
observer. Track direct emulator controller input with `player` ownership,
bounded game state, progress, deaths and recovery, inventory/resources,
transitions, freshness, confidence, and typed provenance. Feed fresh supported
state into Tell. Show remains a separate review process and takeover remains
unavailable.

Acceptance requires a bounded owner-played session whose input trace and
game-owned events reconcile, including honest stale/disconnect and clean-stop
behavior, while the agent-input count remains exactly zero. Fixtures, Show, and
automated agent gameplay cannot satisfy the live owner acceptance boundary. See
the [live-observation contract](live-observation.md) for the exact connection
mechanism and retained evidence.

## Slice V2.5 — Goal-aware live coaching and comparison

Status: **implementation complete / final validation deferred**.

Add versioned, adapter-neutral objective profiles and exact like-for-like
reference compatibility. The first honest pilot supports a fastest accepted
World 1-1 clear and a narrower observable-progress checklist. Quiet,
On-request, and Proactive coaching remain advisory and deduplicated. Objective
Tell preserves Minimal, Guided, and Full detail and separates live facts,
profile requirements, reference facts, inferences, and unknowns. See the
[objective-profile contract](objective-profiles.md).

The implementation is present, but V2.5 still requires a bounded owner-played
session in the consolidated campaign. Fixtures cannot prove coaching
timing, truthful stale/disconnect behavior, or player usefulness. Agent input
must remain exactly zero.

## Slice V2.6 — Dynamic run library and live takeover

Status: **implementation complete / final validation deferred**.

The local run library, explicit same-process takeover authorization, immediate
reclaim, neutral handback, and candidate-versus-executable boundaries are
implemented. Historical deterministic evidence is retained; the consolidated
campaign owns the remaining live proof.

## Slice V2.7 — Adaptive assistance and reviewable solution learning

Status: **implementation complete / final validation deferred**.

Completed runs now enter an adapter-neutral, checksum-bound learning envelope.
Compatible attempts can produce evidence-linked trouble patterns, successful
tactics, and hash-bound review candidates. Player, agent, mixed, and overall
local records remain separate. Owner-local help preferences are explicit,
editable, and resettable. Review can approve only for later validation; replay,
exact-diff route-patch, affected reliability, promotion, and rollback gates are
fail-closed. See [the learning contract](learning.md).

## Slice V2.8 — Session automation and local product metrics

Status: **implementation complete / final validation deferred**.

The implementation-only contract, classified evidence model, local storage,
UI/CLI surfaces, and deferred campaign hooks are documented in [Session
Automation and Local Product Metrics](session-automation-metrics.md).

## Slice V2.9 — Mario product completion and acceptance readiness

Status: **implementation complete / final validation deferred**.

The player product now covers first use, adapter-owned capability truth,
Observe, Tell, coaching, separate Show, same-session Do, persistent reclaim,
safe handback, History, learning clarity, failure/recovery, safe persistence,
and local evidence status. The disabled owner-pilot manifest and consolidated
campaign hooks are prepared. Non-live product, UI, regression, and scenario
contracts pass; live and owner validation remain deferred. See the [Mario Player Guide](mario-player-guide.md)
and [Consolidated Final Campaign](final-campaign-guide.md).

## Slice V2.10 — Visible Stardew operator and observation

Status: **implementation complete / final validation deferred**.

The separate Stardew adapter now owns verified disposable-save creation and
identity, primary-save isolation, visible process/window continuity,
screen-only crop/resource/position observations, ordinary keyboard/mouse/
controller input ports, fresh player/agent ownership, the bounded watering
ledger, protected-action refusal, failure recovery, append-only evidence, and a
standalone desktop/narrow operator surface. Fixture, scenario, artifact, and
blank owner-pilot hooks are covered by deterministic tests. See the
[Stardew Visible Operator Guide](stardew-operator-guide.md).

Acceptance remains in the consolidated campaign: a visible owner-provided
copied-save task, negative cases, exact evidence reconciliation, presentation,
owner usefulness, and explicit owner acceptance. No live execution is inferred
from implementation or deterministic fixtures.

## Slice V2.11 — Stardew companion modes

Status: **implementation complete / final validation deferred**.

The standalone Stardew adapter now exposes screen-only Observe through an
adapter-neutral envelope, contextual provenance-complete Tell, one fresh-copy
review-only watering Show, and explicit same-live-session Do. Do authorization
binds task, copied save, process start, window, observation, expiry, ordinary
input driver, and stop conditions; every input and postcondition is revalidated.
Immediate reclaim and all failures neutralize before player handback. Reset
preserves the old attempt, reverifies the primary, creates a fresh destination,
and invalidates all previous mode state and authority. See the [Stardew
Companion Guide](stardew-operator-guide.md).

Tests, fixtures, presentation contracts, and scenario hooks run in the non-live
suite. The public surface remains unconfigured and inspection-only; no live
Stardew process, owner save, input, or owner pilot has run. Acceptance remains
the frozen-release-candidate deterministic phase followed by visible Stardew
and owner-pilot proof in the consolidated campaign.

## V2.12 — implementation complete / final validation deferred

The local root now presents the ordered Mario and Stardew catalog through an
adapter-neutral registry. Each adapter explicitly provides its identity,
version, availability/setup state, observation trust boundary, Tell/Show/Do
truth, goals, profiles, takeover scopes and stop conditions, safety policy,
evidence namespace/classifications, standalone surface, and recovery guidance.
The shared catalog validates provider agreement and never branches on game id.

Selection and switching are player-owned. The switch coordinator refuses every
active, ambiguous, incompletely retained, unsafe-save, or continuity-unknown
state. A successful neutral handoff retains the current attempt, invalidates
volatile observation and authority, records separately classified catalog
switch evidence, persists only bounded namespaced presentation state, and
requires a fresh target-adapter observation. Corrupt or stale persistence
returns to the catalog with no selection and no authority.

The Mario workspace remains at `/mario`, the standalone Stardew workspace at
`/stardew`, and the engineering Lab at `/lab`; `/` is the combined player root.
Implementation-only catalog inspection/render commands, contracts, fixtures,
scenario hooks, artifact requirements, and desktop/390-pixel checks run in the
Non-live suite. No live game activity or owner validation ran.

## V2.13 — implementation complete / final validation deferred

The optional local unattended runner admits only explicitly classified
`unattended_regression` scenarios and explicit adapter providers. Immutable
manifests bind source/dirty identity, adapter/scenario/goal/profile/solution,
asset/fixture, display, invocation/environment, timeouts/concurrency, cleanup,
protected data/actions, artifacts, and exact proof limits. Fresh owned
processes and run roots, display continuity, cancellation, failed retention,
integrity, metrics isolation, and exact-compatible repeatability are shared;
Mario and Stardew retain their own assets, fixtures, safety, predicates,
cleanup, and evidence.

The CLI and Lab expose truthful capability, planning, manifest, lifecycle,
cancellation, cleanup, retained-artifact, failure, and comparison surfaces.
Prepared contracts, tests, and campaign hooks pass non-live validation. No live
unattended attempt has run for the current candidate, and no unattended output
can count as visible, Show, reliability, authoritative, usefulness, acceptance,
or campaign proof. See the
[operator guide](unattended-regression.md).

## V2.14 — implementation complete / final validation deferred

New Game Onboarding now has the versioned Experimental contract, deterministic
data-only scaffold, fixture sample, provider discovery without shared-core
game-ID branches, atomic manifest/hash installation and rollback, integrity
inspection, fail-closed exact removal, CLI/Lab/onboarding surfaces, desktop and
390-pixel presentation contract, comprehensive tests, evidence rules,
and deferred campaign hooks. Mario and Stardew remain explicit trusted
built-ins. Experimental entries remain live-unproven and cannot self-promote.

Non-live tests exercise rendering, conformance, deterministic scaffolding, and
temporary-root install/status/removal behavior. No persistent operator adapter
installation, live game activity, or owner acceptance has run. The next action
is to freeze the cumulative release candidate and rerun deterministic contract
validation against that exact identity.

## V2 completion

V2 is complete only when Mario has owner-accepted `Tell`, `Show`, and bounded
`Do`; Stardew has the accepted visible task through the same companion contract;
both games coexist safely in one catalog; local automation and metrics
distinguish reliability from usefulness; unattended regression is honestly
labeled; and a collaborator can onboard a sample game as Experimental through
the UI and conformance kit without modifying the core.
