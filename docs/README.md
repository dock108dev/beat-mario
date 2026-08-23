# Documentation index

Use the root [README](../README.md) to install, validate, and start the supported
flows. The documents below provide implementation and operating detail.

## Develop and modify

- [Development and repository structure](development.md): layout, entry points,
  environment, validation, and intentionally large files.
- [Runtime, configuration, and data](runtime-and-configuration.md): process
  model, settings, integrations, persistence, and deployment boundary.
- [Single sources of truth](ssot.md): authoritative modules and retained paths.
- [Agent architecture](agent-architecture.md): component responsibilities.
- [Goal contracts](goal-contract.md): route composition and execution contract.
- [Route patch schema](route-patch-schema.md): reviewed change lifecycle.

## Run and operate

- [World 8 reliability gates](reliability-gate.md): authoritative and watchable
  runs, evidence, and failure behavior.
- [Game Companion Lab](mario-route-lab.md): player-session routing plus the
  local Mario review and attempt workflow.
- [FCEUX harness](fceux-harness.md): low-level emulator runner and diagnostics.
- [Error handling and operations](error-handling.md): failure artifacts,
  response behavior, and incident checks.

## Product and evidence

- [Product direction](product-direction.md): current product boundary.
- [Game Companion V2 roadmap](v2-roadmap.md): ordered Mario companion,
  metrics, Stardew, combined-catalog, and contributor-onboarding slices.
- [Live Mario observation](live-observation.md): V2.4 player-session connection,
  read-only input/state evidence, freshness, and stop behavior.
- [Objective profiles and live coaching](objective-profiles.md): V2.5 measurable
  profiles, compatible references, comparison, coaching, and Tell behavior.
- [Adaptive assistance and solution learning](learning.md): V2.7 compatible
  evidence, review candidates, local preferences, promotion, and rollback.
- [Session automation and local product metrics](session-automation-metrics.md):
  V2.8 scenarios, classified events and metrics, retention, and campaign hooks.
- [Mario player guide](mario-player-guide.md): V2.9 first use, compact player
  workspace, Observe/Tell/Show/Do, reclaim, History, and recovery.
- [Stardew companion guide](stardew-operator-guide.md): V2.10 copied-save and
  visible operator foundations plus V2.11 Observe, grounded Tell, one-task
  review-only Show, same-session Do, reclaim/handback, reset, safety, and
  deferred evidence.
- [Agent architecture](agent-architecture.md#combined-catalog-and-switching):
  V2.12 provider-owned catalog, explicit safe switching, bounded persistence,
  and adapter/evidence isolation.
- [Unattended regression operator guide](unattended-regression.md): V2.13
  provider, display, isolation, cancellation, artifact, repeatability,
  proof-limit, and owner-data boundaries.
- [New Game Onboarding and Experimental adapter contributor guide](new-game-onboarding.md):
  V2.14 contract, state labels, deterministic scaffold, conformance, provider
  discovery, atomic installation, fail-closed removal, and proof limits.
- [Consolidated final campaign](final-campaign-guide.md): frozen owner-pilot
  manifest, evidence rules, failure retention, and explicit acceptance boundary.
- [Route status](route-status.md): accepted route and evidence history.

## Security and local data

- [Security model](security.md): trust boundaries, implemented controls, and
  deferred security work.
- [Local Game Companion Lab assets](local-assets.md): optional ignored UI images.
- [Known limitations](known-limitations.md): intentionally unsupported flows
  and validation boundaries.

Historical build plans and duplicated validation checklists are intentionally
not retained. Current contracts, tests, source modules, and the canonical gate
describe how the repository works today.
