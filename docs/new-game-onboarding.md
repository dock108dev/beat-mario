# New Game Onboarding and Experimental Adapter Contributor Guide

V2.14 provides a local, barebones contributor flow at `/onboarding` and under
the Lab. It creates declarative fixture-only adapters; it does not generate
Python, JavaScript, shell scripts, controller drivers, observation code, or
network dependencies, and it never launches or controls a game.

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

Final acceptance remains deferred. The first next action is to freeze the
cumulative release candidate and begin deterministic contract validation.
