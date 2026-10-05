# New-game onboarding and contributor reference

Updated October 4, 2026. The [private-beta engineering
plan](private-beta-engineering.md) owns active work: connect Codex-backed
conversational interpretation and a separate gameplay reasoning role to the
ordinary Mario/Stardew experience, prove meaningful action choice and replanning,
then complete the exact local private-beta artifact. One Codex provider may serve
both roles. Minecraft connection belongs in the initial beta with accurate
capability labels; full Minecraft gameplay is later work.

## Deferred advanced-user product

The intended later onboarding tool helps an advanced user add another eligible
game through guided setup without writing code. Minecraft development will
inform this tool, using the slower conversational activity loop developed for
Stardew. This is required future product work, not an implemented capability.

Discussion and implementation of no-code teaching/onboarding follow the working
AI Mario/Stardew experience and are not an initial-beta release gate. Recording
and player demonstrations remain deferred to tentative beta v2; no owner
demonstration is required for current work. Define later onboarding from actual
observation, knowledge, skill and decision contracts rather than treating a
declarative profile as a playable agent. Adding a game cannot imply unrestricted
gameplay or invent missing observation, action or outcome capabilities.

## Current setup and contributor capabilities

Ordinary player setup configures existing implemented templates. Its profile,
permissions/settings, selected-window connection, history and local-feedback
owners are reusable foundations. Minecraft has app-created calibration and
bounded camera requests. Current source shows setup progress, task availability
and remedies; these source repairs are not in retained private.2. Aiming,
nearby movement, additions and wall Start remain unavailable. The
[package-status quick start](private-beta-quick-start.md) records this narrower
path. Configuring an existing game is separate from adding a playable new one.

The contributor reference below documents the existing fixture scaffold. It
does not fulfill the deferred advanced-user product, establish playable
generic-game support or replace Mario/Stardew gameplay delivery.

Experimental adapters have a local, data-only contributor flow at `/onboarding` and under
the Lab. It creates declarative fixture-only adapters; it does not generate
Python, JavaScript, shell scripts, controller drivers, observation code, or
network dependencies, and it never launches or controls a game.

## Adding an actual game adapter

A live adapter is separate engineering work; the scaffold does not create its observation or controller implementation. Start with one useful, bounded task and an explicit unsupported list.

1. **Own the game facts and actions.** Implement detection, session/process/window continuity, fresh observations and ordinary input in adapter-owned modules. Use `CompanionObservationEnvelope` for shared identity, freshness, evidence and ownership; keep game-specific facts opaque to the shared shell. Do not teach the core to interpret farm tiles or Mario RAM for a third game.
2. **Integrate the shared lifecycle and AI roles.** Add a game provider to the catalog, typed goals/actions, the selected Codex conversational interpreter, game-state reasoning and adapter validation of proposals. The current `Planner.plan(text, PlanningContext)` is a reusable typed boundary with a deterministic implementation; connecting it alone does not supply AI. Reuse conversation, outcomes, read-only history and neutral switching. A parsed plan, installed provider or reopened result never grants input authority.
3. **Isolate sessions and evidence.** Use explicit disposable inputs and attempt-owned storage. Bind fresh authority to game, source/copy identity, process/window, observation, reviewed scope and expiry. Never discover or modify personal saves to prove isolation; persist history, not execution permission.
4. **Specify eligibility and postconditions per action.** Name observable targets, tools/resources, protected choices, timing and stop point before enabling Start. Confirm each effect from fresh game-owned evidence; input dispatch is not success. Preserve unknowns and distinguish already-satisfied work from newly executed work. Refuse unsupported actions rather than borrowing another adapter's controller.
5. **Stop before handback.** Pause/reclaim, focus or identity loss, stale evidence, missed boundaries and failure must release input, revoke authority and retain partial outcomes. Require confirmed handback for switching; record missing receipts honestly when the process is gone. Recovery requires fresh eligibility, review and Start.
6. **Test in layers and prove composition.** Use deterministic fixtures for typed goals, eligibility, postconditions, shortages, stale/replayed authority, cancellation, session isolation, switching and history. Evaluate held-out wording and changed supported scenes with real model decisions. Then verify actual isolated-game actions, effects, replanning, stop/return, handback and recovery through the ordinary interface. A second meaningful variation must work with the same skills rather than a new scene-specific script. Select affected shared/adapter regressions. Fixture conformance never becomes game success, owner feedback or release acceptance.

## Gameplay integration required before a new game is playable

The future onboarding tool must collect or establish these components, and show
which are implemented, declared, unverified or unavailable:

| Component | Required game-specific information |
| --- | --- |
| Observation/state | Supported settings and sources; scene/entity/player/camera state; resources; target identities; uncertainty, freshness and tracking across frames |
| Mechanics knowledge | Rules relevant to the declared tasks, provenance/version, protection and outcome interpretation; knowledge is separate from current observations |
| Skills | Actually implemented parameterized actions, preconditions, effects, input/timing bounds, verification and interruption |
| Gameplay decisions | Goal decomposition, action selection, expected/actual comparison, inspection, recovery and online replanning |
| Timing | Slower model decision cadence versus fast controller feedback; safe behavior during inference and rejection of late output |
| Learning/history | Compatible discoveries, failures, coaching and demonstrated future decision changes without restored authority |
| Setup | Local game/window selection, permissions, Codex readiness, usable supported entry and personal-data preservation |
| Acceptance | Real task and changed-condition behavior through the ordinary interface, then exact local artifact and owner usefulness checks |

A vision-language reply or recorded input sequence alone does not supply these
components. Reusable observed skills and a reasoner must influence actual play;
the deterministic controller remains responsible for reliable timing and Stop.
The shared framework can host them without knowing another game's mechanics.

For the initial private beta, finish these components for the declared Mario and
Stardew scope. Existing exact routes/calibrations remain useful baselines. They
must not make every new supported request require an engineer patch. Minecraft
connection can honestly show narrower available abilities; connection alone is
not full Minecraft gameplay.

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

Mario and Stardew are explicit built-ins with their own implementation and
evidence limits. Built-in status does not imply unrestricted or AI-qualified
gameplay. An Experimental provider may
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

This scaffold is optional contributor infrastructure. Installed adapters remain
Experimental until their live behavior is implemented and qualified. Keep its
contract and evidence truth while deferring the later player-facing no-code
onboarding work to the ordering above.
