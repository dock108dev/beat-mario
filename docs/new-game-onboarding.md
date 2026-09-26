# New Game Onboarding and Experimental Adapter Contributor Guide

Experimental adapters have a local, data-only contributor flow at `/onboarding` and under
the Lab. It creates declarative fixture-only adapters; it does not generate
Python, JavaScript, shell scripts, controller drivers, observation code, or
network dependencies, and it never launches or controls a game.

## Adding an actual game adapter

A live adapter is separate engineering work; the scaffold does not create its observation or controller implementation. Start with one useful, bounded task and an explicit unsupported list.

1. **Own the game facts and actions.** Implement detection, session/process/window continuity, fresh observations and ordinary input in adapter-owned modules. Use `CompanionObservationEnvelope` for shared identity, freshness, evidence and ownership; keep game-specific facts opaque to the shared shell. Do not teach the core to interpret farm tiles or Mario RAM for a third game.
2. **Integrate the shared lifecycle.** Add a provider to the catalog, typed actions and clarification through `Planner.plan(text, PlanningContext)`, and adapter validation of reviewed proposals. Reuse conversation, outcomes, read-only history and neutral switching. A parsed plan, installed provider or reopened result never grants input authority.
3. **Isolate sessions and evidence.** Use explicit disposable inputs and attempt-owned storage. Bind fresh authority to game, source/copy identity, process/window, observation, reviewed scope and expiry. Never discover or modify personal saves to prove isolation; persist history, not execution permission.
4. **Specify eligibility and postconditions per action.** Name observable targets, tools/resources, protected choices, timing and stop point before enabling Start. Confirm each effect from fresh game-owned evidence; input dispatch is not success. Preserve unknowns and distinguish already-satisfied work from newly executed work. Refuse unsupported actions rather than borrowing another adapter's controller.
5. **Stop before handback.** Pause/reclaim, focus or identity loss, stale evidence, missed boundaries and failure must release input, revoke authority and retain partial outcomes. Require confirmed handback for switching; record missing receipts honestly when the process is gone. Recovery requires fresh eligibility, review and Start.
6. **Test in layers.** Use deterministic fixtures for parsing/corrections, eligibility, postconditions, shortages, stale/replayed authority, cancellation, session isolation, switching and history. Test rendered controls separately. Then qualify the actual game on the exact source with fresh isolated sessions: ordinary request/review/Start, observed work and resources, reviewed stop/return, neutral handback, interruption and recovery. Select regressions for changed shared contracts and existing adapters. Fixture conformance never becomes actual-game success, owner feedback or release acceptance.

Use [architecture](agent-architecture.md), [Mario integration](b2-integration-contract.md) and [Stardew integration](b3-integration-contract.md) to locate owners. Retain exact failed/partial attempts alongside successes; freeze source and artifact identities before making delivery claims. Owner usefulness and acceptance are a later, explicit review.

## State vocabulary

- **Declared:** the versioned contract is structurally valid.
- **Conformant:** deterministic fixture checks agree with the declaration.
- **Live-unproven:** no real-game observation, input, reliability, or outcome
  proof exists. This remains true after conformance and installation.
- **Unsupported:** the adapter explicitly has no implementation for a
  capability or scope.
- **Scaffolded:** the deterministic bounded YAML/JSON/README inventory exists
  below `experimental-adapters/<adapter-id>`.
- **Installed:** an exact hashed inventory is locally manifest-owned and
  provider-discoverable. Installed never means Supported.

Mario and Stardew are explicit trusted built-ins. An Experimental provider may
not use their IDs, collide with their game identities, claim Supported status,
or promote its capability declarations.

## Contract

`game-companion-experimental-adapter/v1` owns identity and version, executable
name and visible-window detection, continuity fields, local read-only
observation envelopes, ordinary host-allowlisted input actions, player-default
ownership, fresh same-process authorization, immediate reclaim, neutral
handback, capabilities, measurable goals, fixture-only solution profiles,
protected actions, takeover scopes and stop conditions, bounded fixtures,
isolated evidence, proof limits, installation ownership, and exact removal.

The contract rejects reserved IDs, Mario/Stardew collisions, absolute paths,
traversal, symlink escapes, unknown fields and files, overwrite attempts,
arbitrary commands, generated executable code, and network dependencies.
Contract and installation-manifest reads are limited to 256 KiB per file, and
fixture JSON reads are limited to 1 MiB per file before parsing.

## Contributor flow

The loopback UI presents metadata, detection, observation, input, safety,
goals, capabilities, fixtures, scaffold review, conformance, installation, and
removal on desktop and approximately 390-pixel screens. Equivalent safe CLI
surfaces are:

```bash
.venv/bin/python -m smb3_agent adapter validate PATH/adapter.yaml
.venv/bin/python -m smb3_agent adapter scaffold my-game --display-name "My Game"
.venv/bin/python -m smb3_agent adapter inspect PATH/adapter.yaml
.venv/bin/python -m smb3_agent adapter conformance experimental-adapters/my-game
.venv/bin/python -m smb3_agent adapter install experimental-adapters/my-game
.venv/bin/python -m smb3_agent adapter status
.venv/bin/python -m smb3_agent adapter installed
.venv/bin/python -m smb3_agent adapter remove my-game
```

Scaffolding refuses an existing destination. Installation validates the
contract and complete known-file inventory, runs conformance, copies into a
temporary sibling, writes the manifest with every SHA-256 hash, and atomically
promotes the directory. Existing targets refuse collision. Failure removes the
temporary tree and leaves no partial target.

The combined catalog discovers clean local manifests in stable adapter-ID
order. Discovery constructs providers from the versioned data contract; it
does not add a shared-core branch for any Experimental game ID. The catalog
always labels these providers `Experimental · installed · live-unproven` and
shows declared capabilities as validation-deferred or unavailable.

## Conformance and proof limits

The deterministic kit covers schema, provider truth, observation envelopes,
capability agreement, ownership/reclaim, protected-action refusal, measurable
goals, evidence isolation, persistence isolation, installation integrity,
removal, catalog labeling, and proof that no shared-core edit is required.

Conformance cannot prove real-game compatibility, live observation correctness,
effective input, reliability, authoritative completion, usefulness, owner
acceptance, or Supported-catalog eligibility. The fixture-only `Fixture Quest`
sample under `data/experimental-adapters/` makes no live claim.

## Removal

Removal loads the exact local installation manifest and refuses a symlinked,
missing, modified, unknown, or ambiguous file. It also refuses while any exact
adapter state marker indicates an active process, authority, input, or session.
Only after all hashes and zero-residual conditions agree does it unlink the
manifest-owned files, manifest, empty fixture directories, and adapter
directory. Evidence and history live outside the install tree and are
preserved.

Failed scaffold or installation staging is removed before the original error is
returned. If that bounded cleanup also fails, the operation fails explicitly
and reports the retained staging path; it never silently claims rollback. See
[Error handling and operations](error-handling.md).

This scaffold is optional expansion infrastructure. Installed adapters remain Experimental until their live behavior is implemented and qualified.
