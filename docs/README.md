# Documentation index

The root [README](../README.md) identifies the current product path and source-checkout launch. The [private-beta quick start](private-beta-quick-start.md) owns player setup, supported Minecraft settings, controls and feedback for the review package. Use this index to find the next task-specific guide.

For project-manager review, start with the [private-beta handoff](private-beta-pm-handoff.md). It distinguishes current uncommitted source repairs, unchanged review packages, local checks and the remaining useful Minecraft task.

## Next engineering work

The [private-beta engineering plan](private-beta-engineering.md) and [Desktop next-steps tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md) own the user Minecraft onboarding and useful-task path. Setup/profile lifecycle, app calibration and bounded camera requests exist. Current source adds setup progress/remedies and affected control, protection, aiming and deadline repairs; those changes are not in retained private.2. Finish guided and visibly checked practice preparation, efficient inspection/aim/movement, additions and the useful wall task; rebuild with accurate availability and check setup → task → Stop/handback → profile/history reopening through the ordinary app. Existing B-series guides describe the narrower personal pilot.

## Player workflows

Use the [private-beta quick start](private-beta-quick-start.md) for Minecraft setup/calibration, typed task examples, controls, recovery and feedback. Aiming, nearby movement, additions and wall Start remain unavailable in private.2; the [review status](private-beta-review.md) distinguishes implemented components from completed packaged gameplay.

Use the [Mario player guide](mario-player-guide.md) for bounded planning, edits and fresh-session limits. The [Stardew guide](stardew-operator-guide.md) distinguishes Day 2 watering from Day 5 combined work, setup and guarded recovery. See [known limitations](known-limitations.md) for unfinished capabilities.

## Understand the system

- [Product direction](product-direction.md) defines Tell, Show, Do, player
  ownership, the adapter boundary, and the current Minecraft beta goal and existing game capabilities.
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

Private-beta packaging and launch checks are described in the [engineering plan](private-beta-engineering.md#delivery-integration--pb10) and [review status](private-beta-review.md). The canonical non-live check is `scripts/validate_phase0.sh`; CI runs it on the locked Python 3.11 environment. Install the development environment when missing; the engineering gate is not an every-launch requirement.

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

Use the [personal-pilot delivery guide](b8-personal-delivery.md) for retained Mario/Stardew in-place launch identity and review boundaries. The [private-beta review](private-beta-review.md) records the separate versioned packages and their actual checks. Minecraft's useful packaged task and owner launch acceptance remain pending.

## Release-candidate and historical planning material

- [Consolidated final campaign](final-campaign-guide.md) records the earlier V2/personal-pilot campaign. Current private-beta readiness follows the useful app workflow and focused launch checks in the active plan and tracker.
- [Game Companion V2 roadmap](v2-roadmap.md) records slice status through V2.14.
  It is a status/evidence document, not the setup guide.
- [Local UI assets](local-assets.md) explains optional ignored artwork.

Implementation, deterministic validation, historical live evidence, current
release-candidate proof, usefulness feedback, and owner acceptance are separate
claims throughout these documents.
