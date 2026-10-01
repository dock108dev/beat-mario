# Private-beta engineering plan

Updated September 30, 2026. **Planning contract; PB1 implementation is next.** The [Desktop next-steps tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md) owns remaining work and stage status. This packet owns technical interfaces, dependencies, evaluation and delivery requirements through private release.

## Product and release scope

A technically comfortable nonprogrammer selects an eligible single-player game, configures it through guided setup, saves a reusable profile, and completes useful tasks primarily through typed natural language. The private release includes existing Mario/Stardew capabilities, a third reference game implemented through reusable profiles, and successful tester setup of an unfamiliar fourth game after the shared backend/wizard are frozen.

Support is stated per game, task family, settings and evidence. Tested integrations, player-created experimental profiles and imported community profiles have distinct capability labels. General configuration is a release requirement; universal competence across arbitrary games is not established by one transfer test. Begin with observable slower menu/turn-based interactions; expand real-time navigation only after a reusable controller and verifiers are proven.

macOS is first. PB1 chooses actual supported OS versions, chips, window modes, controls, language/UI settings and model backend from measurements. Every shipped architecture needs actual delivery qualification. Voice and additional platforms are later work. Locally exchanged profile bundles suffice; a hosted marketplace/accounts backend is not required for this cohort.

## Implementation entry and existing source owners

Read-only planning entry found a clean checkout at HEAD `02b25e808d1625c518738607f11df51105bc7eb9`, tree `dc152232f7a76c151da89ebff5fe14e8ce724c70`. These documentation edits occur after that entry. No new application test, current-source gameplay qualification, process-state audit or owner acceptance is implied. Existing engineering and delivery records remain in their repository guides/artifacts.

| Concern | Existing owner to reuse | Private-beta work |
| --- | --- | --- |
| Plans and revisions | [request_planning.py](../src/smb3_agent/request_planning.py), [conversation_service.py](../src/smb3_agent/conversation_service.py), [conversation_ui.py](../src/smb3_agent/conversation_ui.py) | Add model-backed proposals and profile skills while retaining typed plans, direct controls and revision binding |
| Ownership and continuity | [companion_session.py](../src/smb3_agent/companion_session.py), [takeover.py](../src/smb3_agent/takeover.py), adapter runtimes | Reuse player ownership, fresh authority, bounded execution, immediate reclaim and neutral handback |
| Catalog and switching | [companion_catalog.py](../src/smb3_agent/companion_catalog.py) | Profile-backed providers and task-specific proof labels; no shared-core game-ID branches |
| Screen/input foundation | [stardew_adapter.py](../src/smb3_agent/stardew_adapter.py), [stardew_input.py](../src/smb3_agent/stardew_input.py) | Extract reusable window/capture/control interfaces from game-specific calibration and action purposes |
| Current perception | [stardew_perception.py](../src/smb3_agent/stardew_perception.py), [stardew_farm_vision.py](../src/smb3_agent/stardew_farm_vision.py) | Add qualified reusable detectors/grounding; existing calibrated farm pixels do not generalize automatically |
| Outcomes and local evidence | [run_library.py](../src/smb3_agent/run_library.py), [learning.py](../src/smb3_agent/learning.py), [metrics.py](../src/smb3_agent/metrics.py) | Profile/skill/backend compatibility, observed task outcomes and configuration-test classifications |
| Contributor installation | [experimental_adapters.py](../src/smb3_agent/experimental_adapters.py), [onboarding guide](new-game-onboarding.md) | Separate playable-profile schema/provider from current fixture-only scaffolding; installation does not prove execution |
| Readiness and delivery | [beta_readiness.py](../src/smb3_agent/beta_readiness.py), [delivery.py](../src/smb3_agent/delivery.py), [launcher](../scripts/launch_companion.py) | New private-beta contract plus portable package and clean-machine qualification |

The current planner defaults to Mario/Stardew and uses bounded deterministic language. The repository has no qualified general multimodal gameplay backend. The current personal launcher depends on the checkout, local environment and locally retained game/calibration prerequisites. Both are concrete dependencies for this plan.

## Proposed modules and trust boundaries

Names below are proposed implementation owners, not claims that these files exist. Adjust module boundaries after the PB1 spike without moving domain facts into the shared shell or duplicating plan/session/history owners.

| Proposed owner | Responsibility |
| --- | --- |
| `model_gateway.py` | Backend/configuration identity, bounded multimodal input, structured results, cancellation, timeout, usage/spend, redaction and sanitized diagnostics |
| `screen_host.py` | Selected process/window/display identity, visible capture, scale transforms, capture timestamp and permission/occlusion status |
| `ordinary_input.py` | Mapped short actions, foreground/identity/freshness guards, pressed-input ledger, independent cancellation/watchdog and neutralization |
| `grounded_observation.py` | Frame-bound regions/labels/facts, source provenance, uncertainty, compatible detectors and target revalidation |
| `skill_contract.py`, `skill_runtime.py` | Finite typed primitives and predicates, parameters, eligibility, resource limits, outcomes, stop points and execution validation |
| `game_profiles.py` | Bounded versioned profile/skill inventory, compatibility, local manifests, import/export and integrity |
| `profile_onboarding.py` | Guided setup state, recording/annotation, candidate skill review, practice qualification and actionable setup failures |
| Private-beta readiness owner | Distinct versioned scenario/manifest/schema and validator; preserve personal-beta v3 behavior and evidence |

The model proposes observations and actions; it cannot issue host input, invoke shell/code, overwrite files/saves, grant authority or declare verified success. Screen text and profile descriptions are source material rather than instructions that can change runtime policy. The host alone owns window/capture/control identity; profile providers own game-specific semantics and protected actions.

## PB1 — Feasibility before full onboarding

Select a locally available third game with a bounded useful task, visible pre/postconditions and a disposable test session. Choose it to test an interaction family different from Mario route timing and prepared farm tiles. Record the game/build/settings and task before trials. Do not buy games or obtain assets as an implicit planning action.

Implement the smallest actual selected-window capture → grounded state/target → structured plan → validator → ordinary input → fresh outcome loop. A thin initial host/action implementation is acceptable; PB2 hardens and extracts it. Use the intended profile/skill seams so the spike cannot become a hidden bespoke controller.

Evaluate candidate multimodal backends with the same task/screens and supported hardware. The decision report must state:

- accessible backend/model/version, local versus provider execution and actual screen/context transport;
- hardware/OS requirements, installation/weights/dependency size and offline behavior;
- target/state recognition errors, ambiguous/occluded cases, false success, task completion and stop behavior;
- p50/p95 capture, grounding, planning and action latency; game responsiveness; peak CPU/memory;
- calls/tokens or equivalent compute, cost per attempted/completed task and proposed hard task/call/spend limits;
- which sensors/predicates/actions are reusable, which are configurable and which remain unimplemented;
- measured envelope, final backend choice and the concrete PB2/PB3 interfaces.

Local inference is viable only if it meets task and responsiveness needs on intended tester hardware. Provider inference requires appropriate credentials/access and explicit screen/context-transmission consent before actual calls; acquire neither during this documentation task. Missing provider access permits interface/offline work, but fixtures do not complete real backend feasibility. No backend is selected merely because it returns plausible chat.

**Exit:** real task execution with observed postconditions, fresh-session repetition, a correction, ambiguous-target refusal and independently verified reclaim. If visual grounding, action precision or success verification fails, retain the failure and repair that capability before building a playable-profile wizard around it.

## PB2 — Selected-window host and independent control

Implement capture/input interfaces with identity and coordinate transforms at their boundary. Version/display-bind normalized regions; reject process/window changes, resolution/UI/camera changes requiring recalibration, stale images, occlusion and denied permissions. Preserve existing Stardew pulse limits and foreground protections while extracting general controls; initially bound held-key actions to at most 250 ms before revalidation. Longer movement must use supported feedback-controlled skills rather than an unbounded key hold.

Separate expensive inference from capture/control/cancellation. Own a pressed-key/mouse ledger and independent neutralizer/watchdog. Check the current control epoch and session identity before dispatch; cancel stale queued actions. Never let a hung provider, model response, game crash or browser close leave input held. Stop/Take control remains a direct local path with observed release acknowledgment, and failure reports distinguish confirmed neutralization from an unavailable receipt.

Resolve foreground chat deliberately. For OS-visible input, focusing typed conversation pauses/neutralizes the game action path; fresh review/resume returns to the selected game. Keep Mario's proven process-specific chat behavior separate. Continuous typing while native game input runs is an additional capability requiring demonstrated input isolation.

**Exit:** permission denial, focus/window/process loss, stale capture, wrong coordinates, planner timeout, queue races and shutdown all exercise neutralization; affected existing input/session contracts regress without broadening qualified gameplay scope.

## PB3 — Observations, primitives and executable skills

Use finite schema-validated observations with frame IDs/timestamps, selected-window identity, regions, observed values, confidence/uncertainty and evidence references. Supported detectors might include OCR/HUD values, text/button presence, template/object grounding, region state changes and qualified landmark/location checks. Implement and qualify each detector before a profile can select it.

A skill carries version/hash, task family, parameters and target IDs, entry requirements, allowed primitive sequence, feedback/branch conditions, resource/protection limits, timeout, correction boundary, success/failure predicates and neutral stop. Initial primitives include mapped key pulses, clicks on fresh grounded targets, and bounded waits for observable state. Camera navigation or movement needs its own tested feedback skill; mapping WASD is not navigation competence.

Success requires supported verifiers over fresh post-action observations and resource/position reconciliation. Inference-supplied confidence or narrative is insufficient by itself. Re-observe after each material action; terminate/retain partial work on contradictory or unknown results. Model output cannot define arbitrary executable predicates or bypass hard limits. Establish per-task verifiers and examples of misleading apparent success before advertising those tasks.

**Exit:** changed screens, moving targets, failed input, exhausted resources and uncertain outcomes cannot execute against obsolete regions or become verified completions. Skills can be composed without adding game-specific branches to the core.

## PB4 — Natural-language plans and revisions

Extend existing typed plans with profile/skill/backend identities and bounded task context. A model uses the current verified observation and available skill signatures to propose a finite task; runtime eligibility and authority remain separate. Keep deterministic direct controls available when inference is down.

Cover ordinary paraphrases, multi-step dependencies, references, exclusions/negation, questions versus commands, uncertainty, unsupported requests and corrections. A proposal lists required targets, resources, checks and stop conditions. Corrections update only future work at a supported neutral boundary; duplicate/late responses cannot apply to another revision/session. Material expansion receives one review/apply decision, while ordinary authorized steps avoid repeated permission dialogs.

Bound retained conversation/state summaries by task and freshness. Save useful observations and reusable skills with provenance; do not send entire saves, unrelated windows, secret paths or unlimited gameplay history to a provider. Unsupported semantics receive a precise capability explanation rather than invented instructions.

**Exit:** free-text tasks compose implemented skills with grounded targets; corrections and protected exclusions take effect correctly; advisory questions produce no input; stale plans and model failures stop/clarify without corrupting history.

## PB5 — Player setup and demonstration teaching

The ordinary product flow is select window → compatibility/permissions → confirm controls/settings → mark relevant objects/HUD/return points → select supported task families → demonstrate missing steps → review candidate skill → practice in an isolated session → save profile. Prefer autofill/detection and existing profiles where supported; no terminal, YAML authoring or developer editing is required.

Record demonstrations only for the selected game, with input events, before/after screen evidence and user labels for objectives/protected actions. Convert them into parameterized candidate skills using implemented primitives/predicates. Never immediately promote a captured macro: fresh practice must verify entry conditions, outcome checks, interruption and changed target positions. Saved skills should handle useful task variations rather than replaying one coordinate trace.

Game/save isolation is provider-specific. Verify how each supported game actually loads a dedicated save/profile; do not assume arbitrary save paths or inspect personal saves to infer isolation. Offer reversible practice on dedicated engineering/tester-selected disposable sessions. Existing farm assets stay within their documented boundaries.

**Exit:** a nonprogrammer can build and test a useful candidate profile through the app; missing sensors/navigation/verifiers produce a concrete setup result rather than an apparently playable entry.

## PB6 — Profiles, reuse and ordinary product integration

Version each profile by game/build/settings, OS/runtime/backend compatibility, locale, capture scale/UI scale, controls, region/sensor definitions, skill hashes and capability evidence. Support inspect, edit, duplicate, save/reopen, export/import and removal with history preservation. Changes affecting semantics invalidate relevant qualification and pending authority.

Reuse catalog providers, conversation/review/Start, history and neutral switching. Installation and schema validation establish local data integrity; task labels distinguish declared, practice-verified and tested capabilities. Imported evidence does not confer local input authority or compatible qualification automatically.

Import only bounded allowlisted declarative data; reject executable code/commands, unexpected URLs, traversal/symlink escapes, collisions and unknown files. Do not export secrets, absolute private paths, personal saves, proprietary assets or raw screenshots by default. Optional evidence export is separately selected/reviewed. Profile updates never occur during active ownership and every reopened session starts player-owned.

**Exit:** the same profile supports later ordinary conversation and task variation; compatible reopening/import is useful, incompatible changes are detected, and switching/removal cannot leave active input or lose retained results.

## PB7/PB8 — Third-game and unfamiliar-game proof

PB7 delivers at least three useful third-game task families through the reusable engine. Include differing targets/start states, multi-step composition, a correction, exclusions/resources, an interruption, failed/partial work and reopening. Retain actual completed work and configuration/settings. Code written to expand a reusable family must be counted as engine work; an adapter-specific bypass cannot count as configurable support.

Before PB8, freeze backend/host/skills/wizard identity and the evaluation contract: eligible interaction families, task-selection rules, trial count, success criteria, allowed assistance and setup-time limit. Then a technically comfortable nonprogrammer selects an unfamiliar eligible fourth game with no prepared title-specific profile or fixture. Only generic templates and the tester's wizard-created labels/demonstrations may supply its setup; this tests project profile transfer, not whether the base model previously encountered the game. Permit documented setup guidance and profile annotation/demonstrations; record every intervention. Require several useful tasks, correction, immediate reclaim and profile reopening. Initial setup target is 30 minutes or less for game-profile setup once the app/game/prerequisites are installed. Measure installation separately.

No developer source changes are allowed during the unfamiliar-game evaluation. Record the task/start/end evidence and exact profile bytes. Repairs invalidate that blind result; re-freeze and select a new held-out game for renewed transfer evaluation before claiming generality. Do not replace a failed eligible title with a prepared success while omitting the failure. A successful test qualifies only the documented interaction/compatibility envelope.

## PB9 — Reliability, resources and readiness

Start scenarios and failure classification in PB1, then freeze the relevant task/environment matrix, required trial counts, success thresholds and performance/cost budgets before PB7/PB8 or other final trials. Do not set unfamiliar-game acceptance rules after observing its results. Include repetitions across fresh sessions and the setup/correction/reclaim/reopen cases, not merely screenshots or parser tests. Numerical limits must be justified by feasibility measurements and task timing. Any tested false completion, wrong-window/protected input or residual held input blocks release until repaired and rechecked.

Report attempted/completed/partial/failed counts with denominators; setup and intervention time; capture age; p50/p95 task/planning/control/stop latency; worst observed stop; sustained game responsiveness; CPU/memory; model calls/cost. Test overload, provider timeout/outage/rate limit, unavailable local model, budget exhaustion, permissions/focus loss, crash, pending edits and restart. Cancellation revokes authority even when a provider reply arrives later. Task/call/time/spend bounds are visible to the player and enforced locally.

Create a distinct private-beta scenario/manifest/schema/validator alongside the current personal-beta contracts. Bind source/build/artifact hashes, supported machines, model/configuration, profile/skill versions, evidence classification, task outcomes and actual tester/owner fields. Preserve personal-beta v3 semantics and manifests. PB9 closes runtime qualification and implements the validator, leaving package/distribution and owner fields pending. Complete release readiness is recomputed in PB11 after PB10 package evidence and the actual owner decision. It requires PB7/PB8 outcomes, operating limits and package evidence; the personal validator's optional third-game setting cannot qualify this release.

Use focused behavior checks and affected existing regressions, then the canonical non-live gate for shared runtime changes. Freeze/rebind candidate identity after repairs. Fixtures, screenshot mocks, review-only demonstrations, engineering gameplay, unfamiliar-game setup, clean-machine delivery and owner acceptance remain distinct evidence classes.

## PB10 — Portable Mac delivery and support

Spike packaging/permissions after PB2, then close delivery against the qualified runtime. Choose a self-contained Mac app/package around the shared local product, bundling the Python runtime, locked dependencies and app-owned assets. Detect separately installed games/emulators and supported prerequisites; do not bundle proprietary game content or require ignored developer calibration files. Place profiles/history/logs in versioned user app data rather than the installation/check-out.

Package Start/Stop and visible control ownership, explain screen/input permissions, validate prerequisite/backend availability and provide actionable first-use failures. Closing the UI must have documented, tested execution shutdown semantics. No active input authority survives relaunch/update. Updates occur while neutral, preserve user data and support returning to the prior compatible package; uninstall removes only app-owned installation/configuration chosen by the user and preserves game saves/evidence as documented.

For the chosen downloadable Mac distribution, obtain the required Developer ID signing access, inspect native/Python/helper dependencies and entitlements, enable the compatible hardened runtime, notarize/staple where required, and test the actual artifact under ordinary Gatekeeper on a separate clean machine. Apple's [Developer ID guidance](https://developer.apple.com/developer-id/) and [notarization workflow](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution) describe those platform requirements. Signing credentials/account actions remain a delivery dependency; do not request secrets in chat or bypass system protection to substitute for qualification.

Test every advertised architecture/OS on machines without the repository, developer environment or inherited profiles: install → permission/setup → actual gameplay → interruption → Stop → relaunch → profile reopening → data-preserving upgrade/rollback/remove. Include an intended tester machine/hardware class. Retain package hash, dependency/license inventory and exact permissions/runtime/backend matrix.

Diagnostics are local by default: bounded redacted logs, version/profile identity and selectable evidence, with an inspectable export. Credentials, personal save data and unrelated screen content are excluded. No cloud telemetry is necessary. Use a manual private download/issue path and explicit package versions for the first cohort; do not add a hosted service simply to distribute profiles or collect feedback.

## PB11 — Acceptance and private release

Prepare the qualified artifact, concise setup/play/Stop guide, supported-capability matrix, per-profile limitations, model/hardware/budget requirements, recovery/diagnostic instructions and small-cohort evaluation script. Tester tasks include useful first play, custom setup, conversational correction, interruption and reopening on the actual package. Record completion, setup assistance, usefulness and blockers without manufacturing acceptance.

Owner review selects **ACCEPT PRIVATE BETA / REVISE / STOP** against the exact package after required engineering and tester evidence. Resolve material defects with bounded repairs, reidentify the candidate and repeat affected qualification. Technical readiness permits review; it is not the owner's decision.

Only after that decision distribute the approved identified package through the chosen private channel to the authorized cohort, verify the first recipient can obtain/install it, and retain the release receipt/version/support owner. Invitations, provider/signing purchases/account actions and final distribution require the appropriate actual authorization; this documentation update performs none of them. Release can be paused or a broken version withdrawn with a clear data-preserving return path. Public beta is subsequent scope.

## Delivery dependencies and immediate handoff

| Needed item | Resolve by | Evidence/output |
| --- | --- | --- |
| Available third game and reversible test session | PB1 | Game/settings/task and isolation declaration; real screen/task result |
| Actual model/backend access and intended test hardware | PB1 | Measured backend comparison, installation/transport/credential requirements and selected envelope |
| Reusable sensors, skills and success verifiers | PB1–PB3 | Executable typed contracts and real outcome/negative-case evidence |
| No-code profile creator and compatible persistence | PB5/PB6 | Ordinary wizard, reviewed skill practice, reopen/import/change handling |
| Technically comfortable fourth-game tester | Before PB8 | Eligible game selected after freeze, setup time/intervention ledger and observed tasks |
| Signed portable distribution and clean tester machines | Spike after PB2; complete PB10 | Signing access, actual artifact and normal clean-machine launch/play receipts |
| Explicit operating thresholds and private-beta validator | PB1 initial measurements; freeze PB9 | Named limits, scenario/manifest/readiness schema and complete evidence matrix |
| Owner decision and authorized private cohort/channel | PB11 | Exact-package verdict, recipient install receipt and issue/recovery handoff |

**Immediate implementation handoff is PB1.** Implement the real model/vision/control spike and write its feasibility report before expanding the wizard. Existing personal-pilot review records remain in repository documentation and do not block independent private-beta engineering or imply acceptance of the new release.
