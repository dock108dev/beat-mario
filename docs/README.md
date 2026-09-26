# Documentation index

The root [README](../README.md) owns launch, first use, shared history and safe shutdown. Install the locked environment only when missing; the non-live gate is an engineering check, not an every-launch requirement. Use this index to find the next task-specific guide.

## Player workflows

Use the [Mario player guide](mario-player-guide.md) for bounded planning, edits and fresh-session limits. The [Stardew guide](stardew-operator-guide.md) distinguishes Day 2 watering from Day 5 combined work, setup and guarded recovery. See [known limitations](known-limitations.md) for unfinished capabilities.

## Understand the system

- [Product direction](product-direction.md) defines Tell, Show, Do, player
  ownership, the adapter boundary, and the current Mario/Stardew product scope.
- [Architecture](agent-architecture.md) maps the CLI, adapters, session model,
  local UI, evidence stores, catalog, and switching lifecycle.
- [Runtime, configuration, and data](runtime-and-configuration.md) lists the
  actual settings, local executables, artifact roots, and deployment boundary.
- [Single sources of truth](ssot.md) identifies the authoritative module or
  contract for each behavior and the compatibility surfaces intentionally kept.

## Set up, change, and test the repository

- [Development and repository structure](development.md) covers the locked
  environment, layout, public entry points, validation workflow, and change
  boundaries.
- [Security model](security.md) documents local trust boundaries, implemented
  controls, accepted local-only decisions, and security follow-ups.
- [Known limitations](known-limitations.md) states what the repository and
  non-live gate intentionally cannot prove or operate.
- [Error handling and operations](error-handling.md) explains retained failure
  evidence, process cleanup, recovery, and incident inspection.

There is no separate build, formatter, type-check, deployment, database,
migration, scheduler, or worker guide because the repository has none of those
surfaces. The canonical check is `scripts/validate_phase0.sh`; CI runs it on the
locked Python 3.11 environment.

## Use or modify the Mario adapter

- [Mario player guide](mario-player-guide.md): player first use, Observe, Tell,
  Show, Do, reclaim, History, and failure recovery.
- [Game Companion Lab](mario-route-lab.md): engineering UI, attempt sessions,
  notes, issue ledgers, and route work.
- [Goal contracts](goal-contract.md): route composition, runner policy, and
  success evidence.
- [World 8 reliability gates](reliability-gate.md): fresh authoritative runs,
  watchable review, and promotion boundaries.
- [FCEUX harness](fceux-harness.md): low-level process, log, image, and
  diagnostic behavior.
- [Live observation](live-observation.md), [objective profiles](objective-profiles.md),
  and [learning](learning.md): observation trust, coaching/comparison, and
  reviewable local learning.
- [Route patch schema](route-patch-schema.md): isolated review, validation,
  promotion, rollback, and rejection.
- [Route status](route-status.md): historical accepted Mario route evidence.

## Work with other adapters and shared product surfaces

- [Stardew companion guide](stardew-operator-guide.md) describes the implemented
  session isolation, guarded controller contract and live-input prerequisites.
- [Session automation and metrics](session-automation-metrics.md) documents
  scenario classification, local product metrics, and proof limits.
- [Unattended regression](unattended-regression.md) covers opt-in isolated
  engineering runs that can never become player or acceptance evidence.
- [New Game Onboarding](new-game-onboarding.md) covers data-only Experimental
  scaffolds, fixture conformance, installation, discovery, and safe removal.

Use the [delivery guide](b8-personal-delivery.md) for launch identity and review boundaries. A retained build has begun owner review; acceptance remains pending. Later source changes are not automatically qualified by that review.

## Release-candidate and historical planning material

- [Consolidated final campaign](final-campaign-guide.md) maps the revised beta
  requirements and preserves the still-unrun V2 workflow. Its existing executable
  contracts require versioned reconciliation before they can qualify this beta;
  automatic execution remains disabled.
- [Game Companion V2 roadmap](v2-roadmap.md) records slice status through V2.14.
  It is a status/evidence document, not the setup guide.
- [Local UI assets](local-assets.md) explains optional ignored artwork.

Implementation, deterministic validation, historical live evidence, current
release-candidate proof, usefulness feedback, and owner acceptance are separate
claims throughout these documents.
