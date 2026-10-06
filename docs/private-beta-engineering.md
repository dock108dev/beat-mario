# Game Companion engineering plan to local private beta

Updated October 5, 2026 after the owner rejected repeated micro-adjustment milestones. The next deliverable is a usable local Mac app candidate. The [Desktop tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md) contains the active delivery checklist; [product scope](product-direction.md) and [architecture](agent-architecture.md) define behavior. Dated verification records retain their evidence scope.

## Release target and initial scope

Deliver one successor Game Companion.app that the owner can open from Finder, configure through ordinary controls, use for both supported games, interrupt and reopen. Contextual language and gameplay decisions use the existing Codex integration; local controllers retain timing, validation and release. Normal inference is remote, while game tools and histories are local.

The initial local beta uses the capabilities already demonstrated in source:

| Capability | Source evidence | Initial candidate treatment |
| --- | --- | --- |
| Mario | World 1-1 adaptive early segment, 3/3 final native arrivals alive/grounded; compatible coaching, Stop and reopening | Include bounded segment, finite attempts, coaching and history; qualify the packaged path |
| Stardew | Two prepared Day 2 model-directed watering variants with observed return/handback and pending-inference Stop | Include prepared-farm watering; repair current renderer/setup and qualify the packaged path |
| Reconnaissance | Source composition and two actual-model simulated completions; native activity has not begun | Experimental or unavailable by default until native acceptance; does not block candidate construction |
| Other retained activities | Independent source contracts for Mario routes/rewards, Stardew discussion/Day 5 and legacy games | Carry accurate status; enable only with declared prerequisites and applicable checks, or retain as secondary/experimental |
| Recording, broader levels/farms, cave interiors, training | Deferred or incomplete | Later beta work; recording tentatively beta v2 |

Both required games must work through the delivered app before the two-game beta is ready. Existing source evidence is a foundation; it does not qualify a new package or the current broken Stardew setup. Do not advertise unverified abilities to make the beta appear broader.

## Repository review — October 5

- Actual source now has both model roles, visual Mario skills, compatible memory, watering decisions and guarded cancellation. Do not repeat provider scaffolding or demand a new game objective before delivering them.
- GC-U added catalog model/permission status, direct Mario/Stardew setup and guarded process/window preparation. The latest retained setup reached the porch but clipped the toolbar/water bar; resource recognition refused. Reported bounds alone did not resolve it. This blocks current Stardew availability and needs a usable remedy.
- The generic `/setup` store/UI still owns only Minecraft/OpenTTD templates. `app_runtime.py` opens that historical surface. Integrate the existing catalog/game-owned setup into the app entry and persistence flow rather than creating a competing setup subsystem.
- `player_store.py` still declares private.2; the builder hardcodes bundle build 20002, copies the historical quick start, includes whole data/public trees and does not declare required FCEUX Lua resources. A successor identity, explicit resource set and current guide are needed.
- The initial GC-D inventory has 90 references, with eligibility, transitive images/calibration, absolute-path resolution and prepared-save import still pending. Inventory is not an implemented bundle.
- The frozen app changes working directory to Application Support. Required resources, profile registrations, scene assets and writable history must resolve correctly there. Games, owner game files and Codex authentication remain external.
- Readiness still targets historical B-series v3; the built-in smoke checks historical profile/HTTP behavior. A current capability matrix and packaged Mario/Stardew walkthrough must replace those as the new beta's acceptance path.
- Server-close cleanup exists, but discards its failure list; the app entry lacks the source signal handling. Exercise and repair owned provider/input/worker cleanup in the delivered app.

The retained GC-U canonical record is 1,659 tests. Later executable-discovery maintenance has focused checks, not new native/package qualification. This review is documentation/source inspection; no game, model or package was launched.

## Complete initial-beta delivery checklist

These are the remaining technical requirements through local release. Work proceeds as one delivery milestone with three exits, rather than another chain of isolated gameplay patches.

### Build the reviewable app candidate — GC-U / GC-D1

- [ ] Define a current versioned capability/readiness contract for the initial scope, keeping legacy B/PB records intact. Separate required beta capabilities from experimental/later work.
- [ ] Open the app on the actual Mario/Stardew/Codex catalog/readiness flow; integrate game-owned setup, selection and saved bindings without another authority owner.
- [ ] Preserve existing profiles, coaching and history through any schema/data migration; reopening restores no live permission.
- [ ] Make executable selection/discovery, CLI sign-in, macOS permission status and missing-prerequisite remedies usable from a Finder launch.
- [ ] Complete Mario disposable-session setup and Stardew owner-controlled prepared-copy/import/setup. Preserve primary/frozen saves and declare manual Load/porch/tool steps.
- [ ] Resolve Stardew rendered layout/resource visibility with a reproducible ordinary remedy; retain genuine geometry, resource, focus and freshness refusals.
- [ ] Complete the resource inventory for enabled capabilities, including transitive calibration/survey images, manifests, registries, FCEUX scripts, helpers and Python/runtime dependencies.
- [ ] Choose explicit bundled assets and owner-imported/external prerequisites. Avoid wholesale copying of ignored data, personal saves, receipts or credentials.
- [ ] Replace repository-relative/absolute developer paths with read-only app resources and writable Application Support registrations/history.
- [ ] Package required OCR/helper resources, or expose a verified external prerequisite where the initial scope actually needs it.
- [ ] Give the successor distinct version/build/output/manifest and preserve retained private.1/private.2 apps.
- [ ] Include a matching current quick start, scoped capability list, readable recovery steps and inspectable local diagnostics/feedback.
- [ ] Implement independent owned-process/input cleanup for Quit, provider cancellation, signal/termination and interrupted startup; surface cleanup failures.
- [ ] Build and locally sign a self-consistent Mac candidate. Candidate construction and asset/path fixes proceed while Stardew or experimental checks remain pending.

**Exit:** an actual app exists with its declared resources, setup and guide, plus an explicit list of remaining qualification blockers. A package may be reviewable before it is beta-ready.

### Qualify and repair the delivered experience — GC-Q / GC-D2

- [ ] Launch the candidate from Finder with isolated user data and no dependency on the developer shell or repository current directory.
- [ ] Check first-use readiness, current authentication, game/asset selection and actionable missing permission/dependency remedies.
- [ ] Run the ordinary Mario request/review/play/coach-or-compatible-retry/Stop loop with observed segment result and handback.
- [ ] Run the ordinary prepared Stardew request/correction/review/watering/return loop with fresh resource/crop observations and handback.
- [ ] Confirm game switching releases prior control, invalidates plans/targets and rejects old model replies.
- [ ] Check cancellation during pending inference and active execution on paths affected by packaging/setup changes; preserve finite authority and no continuation.
- [ ] Check provider unavailable/slow/invalid output, disconnect/focus/window change and fresh-review recovery without widening authorization.
- [ ] Verify persisted configuration, results and applicable guidance after restart/update, without restored session or control.
- [ ] Verify Quit and unexpected termination clean up owned inputs, provider children and workers; unrelated games/services remain untouched.
- [ ] Check readable small/supported-window layouts, keyboard/focus/drafts, loading/empty/error states and current-versus-historical results.
- [ ] Preview local feedback/diagnostics with build identity and relevant context, excluding credentials and unrelated captures.
- [ ] Repair blockers exposed by this integrated walkthrough and rerun affected checks; run meaningful affected tests and the canonical repository gate.
- [ ] Record exact app/resources/capabilities and evidence, preserving earlier failed outcomes. Test counts and source successes are not package proof.

**Exit:** both declared games work end to end through the delivered app, with controls, persistence and recovery verified. Reconnaissance can remain experimental without holding this exit.

### Prepare owner use and local release — GC-R

- [ ] Deliver the app, manifest, readable quick start, known limitations and concise walkthrough for the owner.
- [ ] Provide simple local report/triage and update/rollback steps that preserve user data and accepted evidence.
- [ ] List accepted limits and unresolved optional work separately from release-blocking setup/control/gameplay failures.
- [ ] Complete the owner's usefulness review of the actual candidate and obtain the local beta decision; do not manufacture acceptance from engineering trials.
- [ ] Record the released candidate and a finite post-beta backlog. No hosted service, external tester campaign or notarization requirement is implied for this personal Mac release.

**Exit:** the owner has a usable declared-scope beta and a recorded local release decision.

## Current engineering pickup

Implement and build the successor local app using the checklist above. Complete packaging, resource relocation, app entry and usable setup as a single concrete delivery task. Address the Stardew layout problem as part of that experience. If it remains blocked, finish independent candidate work and report the exact two-game qualification blocker rather than ending with only another setup repair.

Reconnaissance native qualification remains valid follow-on work; keep it visibly experimental until it passes. Broader hazards, complete levels/coins and arbitrary farm support develop after the initial scoped beta.

## Technical contracts and broader coverage backlog

The GC packages below retain shared technical contracts and the broader game roadmap. Their wider exits are not all prerequisites for the initial local candidate. Use the delivery checklist above for required initial-beta work; qualify only the declared enabled capabilities and keep incomplete features experimental or unavailable. Do not restart completed provider or gameplay work.

| Package | Deliverable | Dependencies | Current status |
| --- | --- | --- | --- |
| GC-A0 | Shared intent, game-state, decision and skill contracts | Current adapter/control owners | Partial: connected watering and visual Mario segment contracts implemented |
| GC-A1 | Codex provider and app lifecycle | GC-A0 | Source implemented; packaged discovery pending |
| GC-A2 | Contextual language role in ordinary interfaces | GC-A0/A1 | Connected; broader coaching/context evaluation pending |
| GC-A3 | Reusable observation and working game state | Existing observers; GC-A0 | Partial foundations |
| GC-A4 | Reusable executable skills and validated tool bridge | Existing controllers; GC-A0/A3 | Partial foundations |
| GC-A5 | Adaptive gameplay decision loop | GC-A1–A4 | Partial: native watering and visual Mario decisions consume fresh effects |
| GC-A6 | Supervision, coaching and applicable memory | GC-A2/A5; existing store/control | Partial: compatible coaching applied on a later native Mario attempt |
| GC-M | Model-driven Mario experience | GC-A2–A6 | Partial: supported segment completed 3/3 with completing variation/coaching; wider coverage open |
| GC-S | Model-driven Stardew activities | GC-A2–A6 | Watering source accepted; current setup recovery blocks availability; reconnaissance experimental |
| GC-U | Ordinary setup, conversation and shared usability | GC-A1; both adapters | Source readiness/entry/preparation implemented; integrated app walkthrough pending |
| GC-Q | Model, gameplay, control and regression evaluation | Enabled beta scope and D2 | Source evidence retained; exact-app checks pending; broader evaluation later |
| GC-D1 | Complete app resources, packaging and readiness contract | Declared beta scope; source foundations | Next: build candidate alongside setup recovery; inventory exists, builder incomplete |
| GC-D2 | Exact-package end-to-end qualification and repairs | D1; enabled beta capabilities | Open: integrated walkthrough and repairs |
| GC-R | Local private-beta release preparation and owner decision | D2 | Open |

### GC-A0 — contracts and responsibility boundaries

- Define contextual intent separately from executable plans: objective, resolved references, preferences/exclusions, time/resources, success conditions, coaching applicability and clarification needs.
- Define a game-state representation for observed entities, player state, terrain/relations, resources, current task progress, observation age/uncertainty and compatible memory.
- Define gameplay decisions: next subgoal/skill/target/parameters, concise reason, expected effect, needed observation and continuation/replan/stop condition.
- Own bounded session/context state, summaries and retrieval so long conversations preserve constraints, corrections, pending questions and evidence. Provider thread IDs never own gameplay authority.
- Define an adapter capability catalog generated from actual implemented skills: parameter bounds, preconditions, expected effects, completion/failure predicates and allowed contexts.
- Keep goal understanding independent of executable coverage. An unavailable action remains an accurately understood goal with a concrete missing capability.
- Bind proposals to the current goal, game/session, observation and plan version. Preserve authorization, cancellation and outcome owners rather than introducing a parallel input path.
- Establish module ownership and a small integration seam around current services, adapters and controllers. Runtime model decisions must not modify repository/controller code.

**Exit:** these contracts carry one real interpreted goal through a model-selected, validated adapter action. Schema work alone is preparation.

### GC-A1 — local Codex provider and lifecycle

- Choose a supported integration through non-interactive Codex or app-server. Reuse the owner's saved CLI sign-in; do not copy credentials into app profiles, reports or package assets. Use current official documentation and installed capabilities.
- Locate Codex from a packaged GUI environment as well as a terminal. Check availability/version/login/model modality and present simple install/sign-in/retry remedies.
- Support text plus relevant game images and structured outputs. Keep language and gameplay role contexts distinct even when sharing the model.
- Implement request/session ownership, streaming or asynchronous progress, deadlines, bounded retries, process cleanup and cancellation. Late or superseded output cannot create actions.
- Handle invalid/partial output, provider errors, rate limits, authentication loss and application restart. Keep uncertain work and explain the next remedy.
- Expose game tools only through the validated adapter bridge. Select an appropriate isolated runtime context and tool permissions so game execution uses implemented capabilities; the gameplay agent is not the engineering agent editing source.
- Measure latency, model calls and context size on real activity. Define useful caching/summaries without turning historical game state into current observations.
- Explain which selected-window images and context are sent for inference. Preserve the local report/privacy boundary; default Codex inference is not offline.

**Exit:** the ordinary app performs a real contextual model call, handles cancel/unavailable states, and consumes a validated structured result. CLI presence and mocked provider tests alone are insufficient.

### GC-A2 — contextual language-to-game LLM

- Replace normal activity interpretation by the model-backed role, while preserving deterministic priority control and validation.
- Supply original wording, relevant conversation, current goal/plan/progress, game state, capabilities/rules and applicable memory.
- Provide verified, versioned mechanics knowledge separately from model background knowledge, current observations and hypotheses. Retrieve relevant rules and expose uncertainty when rules/version/prerequisites are unknown.
- Resolve references, multi-turn edits, compound preferences, exclusions, questions, intent changes and temporal coaching scope.
- Clarify meaningful ambiguity; explain unsupported actions while retaining the desired objective. Avoid substituting a fixed route for a different requested goal.
- Turn intent into an understandable proposal and hand it to gameplay planning. Scope changes revise the goal/plan and approval as required.
- Connect the role to both Mario and Stardew ordinary interfaces, with actual provider status and a clear degraded state if inference is unavailable.

**Exit:** unseen phrasing and multi-turn references become correct grounded goals; a changed preference changes an executed choice. Record actual inference evidence. Adding phrase matches is not this exit.

### GC-A3 — observations, perception and working game state

- Build compact state/image snapshots with stable target identities, timestamps and provenance, including current versus historical/inferred/unknown information.
- Extend existing precise observers with the reusable semantic information the agent needs: objects, terrain, hazards, camera/player location, resources, tools/forms and reachable candidate targets.
- Use visual model understanding where useful; corroborate decision-critical facts and outcome claims through adapter checks. Model confidence is not an observed effect.
- Account for camera movement, occlusion, animation, changed scenes and uncertainty. Obtain another view or stop where localization is insufficient.
- Support target/state variation within declared coverage; avoid a new image template or full fixed route for every individual goal.
- Preserve protected-object/resource baseline and final accounting when the camera hides earlier regions. Hidden state remains historical until reacquired.
- Document initial game/settings/scene coverage and failure remedies. A game model can understand a goal outside the supported scene while execution remains unavailable.

**Exit:** the same observation/state path supports changed targets and conditions; the agent uses new observations to alter decisions and avoids unsafe assumptions when information is missing.

### GC-A4 — reusable skills and game-tool bridge

- Extract current successful behaviors into useful composable skills instead of exposing only full task scripts.
- Provide supported inspection, target movement, game interaction/tool use, Mario maneuvers and return/release capabilities as applicable to each adapter.
- Validate targets and parameters against fresh state, available capability, reviewed limits and protected actions. Reject invented tools and stale/unobserved actionable targets.
- Maintain fast local feedback, progress/stall checks, collision/reachability rules, deadlines and neutral release in the controller.
- Let ordinary navigation algorithms use current supported geometry; add reusable local reachability/obstacle observation where it prevents destination-specific scripting.
- Return structured action effects, progress, resource changes, uncertainty and failure reason to the agent. A sent input is not action success.
- Keep all input in existing guarded runtime owners. Stop/Take control and focus loss must remain independent of provider/process/tool locks.

**Exit:** a real agent composes skills into one activity, and a changed task variant runs without adding a new complete route script. Low-level deterministic skills are legitimate reusable foundations.

### GC-A5 — game understanding, decisions and replanning

- Maintain goal/subgoal progress and choose the next useful action from current state, game rules, capabilities and relevant memory.
- Predict a checkable effect, execute a finite skill, compare independent observations and update the working state before deciding again.
- Handle obstacles, failed actions, target changes, unexpected resources and lost visibility by inspecting, choosing a supported alternative, revising scope or explaining the missing capability.
- Bound repetitive attempts and recognize lack of progress. A new decision should cite new evidence or a materially different approach.
- Invoke the model at useful decision boundaries. Preserve fast controller timing between them; do not wait for inference on each Mario frame.
- Account for model delay and stale context. Pending inference must not allow an unbounded action to continue.
- Complete the first vertical slice on a slow Stardew activity with working skills; use watering/inspection foundations rather than requiring the unfinished cave route first.

**Exit:** real Codex selects executed actions, reacts to an observed change and completes useful work. The same implementation handles a second goal/state variant without code changes between trials. A model explanation attached to unchanged scripted execution is insufficient.

### GC-A6 — coaching, supervision and memory

- Carry player corrections into goal constraints and subsequent game decisions, acknowledging current/next-skill/next-attempt applicability.
- Persist intent, context, discoveries, action choices, observed effects, failed approaches and uncertainty through existing history owners.
- Retrieve compatible knowledge and resolve contradictions/obsolete guidance. Keep current observations authoritative over remembered state.
- Offer ordinary inspect, reset and undo of future guidance while preserving past outcomes and evidence.
- Preserve reviewed finite budgets across compatible retries; fresh authority is required after reclaim, cancellation or material scope change.
- Summarize progress and ask useful check-ins at decision boundaries. Reopening restores descriptive data only.

**Exit:** remembered guidance demonstrably changes an agent decision in a new compatible session; coaching changes actual behavior and interrupt/approval boundaries remain intact.

### GC-M — Mario integration and initial-beta coverage

- Connect contextual goals/coaching to the actual Mario strategy role, semantic observations and reusable fast controller skills.
- Deliver watched, goal-directed play with meaningful route choices and adaptation to supported different entries, hazards or preferences.
- Preserve and reuse working jumps, stairs/pipes, flight and reward verification while making their selection/composition state-driven.
- Support coin-route exploration with observed collected/missed/unknown accounting. Do not require a 100% achievement to claim the supported discovery experience; retain unknown full coverage.
- Support a flight/reward objective with observed prerequisites, actual execution and independent reward confirmation; make preparation remedies usable.
- Demonstrate real coaching application, compatible retry, changed tactic/goal composition and remembered guidance through ordinary conversation.
- State the initial supported level/segments and mechanics. Verify interruption during inference and execution, death/reset handling and resource/life accounting.

**Exit:** model interpretation and strategy decisions materially affect real Mario play in a second supported variation beyond the existing canned route. User-visible progress, outcomes and handback are verified.

### GC-S — Stardew integration and initial-beta coverage

- Connect language goals, working state and gameplay decisions to short approved activities, target selection and navigation.
- Deliver useful watering on observed targets with tool/water/energy checks, per-target effects, discussion/correction and revised continuation.
- Deliver planting-location discussion grounded in terrain, occupancy, access and crop/season rules; finding a spot grants no planting/purchase permission.
- Later coverage: qualify the implemented reconnaissance activity and its target/preference variation before enabling it as accepted gameplay. Initial beta can ship with reconnaissance experimental or unavailable; cave/interior coverage remains separately declared.
- Verify task/target/resource/preference variation without engineering coordinates and without a custom full script for each variation.
- Provide usable disposable/copy setup and backup/isolation checks, clear manual prerequisites, supported settings and tool/refill remedies.
- Preserve protected crops/resources and final return accounting; do not label unknown species or off-screen state as confirmed.

**Exit:** the agent chooses and revises real Stardew work across useful activity variations, including interruption and reopening. A prepared farm may define initial coverage, but the model must actually reason and adapt within it.

### GC-U — ordinary setup and coherent product UI

Source setup includes catalog Codex readiness, permission status, direct game setup and guarded preparation. Its recorded native trial reached the porch but could not recognize the selected can because the toolbar/resource bar was clipped. Resolve that as a Stardew usability blocker during candidate delivery. Source setup is partial; the app entry, persisted bindings and packaged walkthrough still need integration. Reconnaissance remains experimental until its separate native checks pass. Build/package work proceeds concurrently with renderer recovery.

- Integrate Mario, Stardew and Codex setup in the real app catalog/profile flow; current generic setup templates focus on Minecraft/OpenTTD.
- Detect or guide game/emulator paths, CLI availability/sign-in, macOS permissions, selected process/window/display and supported settings with readable remedies.
- Eliminate recurring app-name attachment failures using working process/window-bound preparation. Keep manual load/porch/tool steps explicit until automated and observed.
- Support a fresh disposable Mario session and user-selected Stardew disposable/copy workflow that protects primary/frozen saves.
- Provide one conversation/session experience with goal, approval, current action, observed progress, coaching and visible Stop/Take control.
- Preserve draft/focus and safe discussion during inference/start/execution races. Keep technical diagnostics out of the ordinary flow.
- Switch games only after confirmed release; discard old plans, targets and provider replies, while retaining appropriate history.
- Validate reconnect, first use, permission changes, unconfigured/error/empty/loading states and historical reopening. Check supported window sizes, keyboard accessibility and readable visual targets.

**Exit:** a normal owner can start and use both games and the model backend through the guide, with every manual preparation step declared and no hidden developer action.

### GC-Q — evidence and evaluation

- Build a versioned evaluation set for held-out wording, multi-turn references, unsupported goals, exclusions, coaching and contextual approvals.
- Evaluate actual model intent accuracy separately from gameplay decisions, controller effects and final outcomes. Use simulated tests for mechanics/races and real provider/game trials for their respective claims.
- Include changed target, starting state, obstacle/resource constraint and interrupted/failed-action cases. At least one variant is selected after implementation and handled without scenario-specific code edits.
- Retain concise decision records: request, intent, observation/rules/capabilities supplied, selected action, expected effect, actual effect, replan and release. Do not require private chain-of-thought logs.
- Check provider cancellation/failure, invalid output, stale replies, focus/window loss, authority changes, no-progress limits and shutdown races.
- Measure real latency, call/context volume, observable reliability and limits on the supported Mac; set practical activity budgets from measured behavior.
- Run affected regressions and the canonical repository gate after integrated changes. Recheck only relevant live/package behaviors after repairs, with final candidate records updated appropriately.

**Exit:** evidence establishes both AI contributions and controlled gameplay variation; test counts alone do not qualify the product.

### GC-D1 — assets, package and new readiness contract

- Define a new versioned private-beta readiness/scenario contract matching the AI Mario/Stardew experience. Legacy B/PB readiness results retain their original meanings.
- Make version, bundle build and output configurable; remove retained private.2 assumptions and preserve previous packages.
- Include actual runtime resources: Python dependencies, adapter data, FCEUX scripts/controllers, required observation/calibration assets and app UI. Test resource resolution from inside the app.
- Resolve ignored engineering asset dependencies: bundle eligible app-owned assets, or guide reproducible creation/import through setup. Inventory prepared-farm/profile registries, transitive manifests/sprite banks/calibration images and planting-survey data; absolute developer paths are not product availability. Personal games/saves and credentials remain separately owned.
- Use an explicit release resource inventory instead of copying all ignored files from data/public. Resolve read-only bundle data separately from writable variants/history and Application Support registrations.
- Replace machine-specific OCR/helper assumptions with packaged resources or clear prerequisites. Locate external game/emulator/Codex executables from a Finder-launched environment.
- Version/migrate profiles, coaching, discussion/history and any new agent store safely. Preserve user data and leave authority empty after restart/update.
- Exercise packaged Quit/signal/crash cleanup with provider children and active input; existing server-close cleanup must surface failures rather than discard them. Preserve owned-process targeting and never terminate unrelated game/server processes.
- Include truthful capability flags, provider/setup guidance, limitations, local feedback preview and complete shutdown/child-process cleanup.
- Build a distinct local Mac candidate with a manifest binding version/resources/capabilities and documented signing/channel. Local ad-hoc distribution is sufficient for the owner's Mac if it works; external tester distribution requirements are a separate explicit scope.

**Exit:** one installable self-consistent successor app can discover its prerequisites and resolve its own required resources without repository-relative surprises.

### GC-D2 — exact-package end-to-end qualification

- Verify the packaged app from Finder using isolated user data, without relying on the developer shell or undocumented repository assets.
- Check Codex discovery/sign-in/inference, first-use game setup and actionable missing-dependency/permission remedies.
- Run Mario goal/play/coach/retry/Stop, neutral game switch, Stardew request/plan/approve/activity/discuss/replan/Stop, historical reopening and feedback preview.
- Preserve truthful legacy Minecraft/OpenTTD entries if included; their new native campaigns do not block the two-game local beta. Full Minecraft gameplay remains later work.
- Verify provider unavailable/slow states, disconnect, window/focus changes, safe recovery, quit and restart. Confirm no leftover owned inputs/workers/games and no restored authority.
- Record engineering assistance and repair it or expose an acceptable manual step in the guide. Source-gameplay success does not replace package verification.

**Exit:** the delivered app completes the supported AI two-game loop, with matching manifest/guide/evidence and declared limitations.

### GC-R — local private-beta release

- Prepare the stable local candidate, readable quick start, supported capabilities/known limits and recovery instructions.
- Provide an inspectable local feedback/diagnostic report with request/decision/outcome and build identity, excluding credentials and unrelated images/files. Explain inference data separately from feedback sharing.
- Establish simple report/triage and update/rollback steps that preserve user data, evidence and editable work.
- Run an owner usefulness walkthrough of the exact app and record feedback separately from engineering verification.
- Resolve release-blocking usability/control/AI failures, record accepted limits and obtain the owner's explicit local beta decision.
- Keep release evidence and a finite post-release issue list. Invitations, uploads, external distribution, purchases and hosted services are not implied by documentation work.

**Exit:** the owner has a usable local private beta and a recorded release decision against the delivered candidate.

## Progress policy

Use the consolidated delivery exits above to decide what comes next. Independent packaging/setup work continues while an experimental gameplay check is pending. Routine Git/version identification is part of engineering, not a separate reconciliation project. Make reversible decisions autonomously. Preserve saves, credentials, accepted routes, evidence and incoming work.

A perception fix, new primitive or route repair is valuable when it unlocks the current AI milestone. Report the capability it enabled and demonstrate the connected behavior. Extend reusable capabilities that improve the connected model loops rather than adding isolated scripted scenarios.

If live access is unavailable, complete useful independent implementation and identify the exact pending check. Do not turn repeated missing input windows into additional synthetic qualification campaigns.

## Documentation ownership and completion

Maintain this repository-local plan and the Desktop tracker as the active worklists, product direction as the intended experience, architecture/runtime/security as contracts, player guides as implemented behavior, and dated verification records as evidence. The PM handoff contains only current pickup/status. Historical plans are references, not active next actions.

At every integrated closeout record actual model-driven behavior, automated checks, live/game/package evidence, remaining gaps and the next work package. Documentation updates do not themselves implement or qualify the new beta.

## Preserved evidence and later work

Use [opening/discovery verification](gc1-gc2-coaching-verification.md), [route verification](gc2-route-verification.md), [flight verification](gc2-flight-verification.md), [watering](gc3-watering-verification.md), [planting](gc3-planting-verification.md), [inspection](gc3-inspection-verification.md), [incomplete cave](gc3-cave-verification.md), [deferred demonstrations](gc2-demonstration-verification.md) and [retained package review](private-beta-review.md) for actual prior outcomes.

After initial local release: wider levels/farms/settings, completed Minecraft gameplay during beta, advanced guided no-code eligible-game onboarding, recording/demonstration qualification tentatively in beta v2, and eventual independent practice. These are not hidden initial-release gates.

## Historical documentation pass coverage

This pass reviewed the repository README and all top-level docs for scope/status consistency. Updated active product/architecture/engineering/PM/worklist, conversation/learning/limits, game interfaces/guides/onboarding, runtime/setup/ownership, observation/goals, security/recovery, UI/evaluation/metrics, assets/development/index and retained-package entry guidance. The plan contains the complete task sequence.

Historical B/V2/PB handoffs are explicitly labeled references. Dated verification records retain their results; the cave record has a status clarification for newer manual-route artifacts without converting them to ordinary activity success. Stable route schemas, FCEUX/reliability operator mechanics and accepted-route records remain implementation references. Retained app manifests/adjacent guides and gameplay artifacts were not changed.

This is a documentation update only: no Codex-backed runtime, new game skill, package, gameplay verification or release acceptance is established by it.

## Demonstrated bounded Mario milestone — October 5

- [x] Three final-source native arrivals at x=700, 700 and 713, alive and grounded, with independent neutral acknowledgment.
- [x] Compatible repeat and completing walking/raised-block preference variation on unchanged source.
- [x] Compatible guidance application, ordinary approved retry, pending-inference Stop, no continuation and descriptive reopening.
- [x] Final canonical gate: 1,634 tests and the repository checks.
- [ ] Broader hazards/starts/forms, full adaptive levels, complete coins and exact-package/owner qualification.

## October 5 source maintenance — SSOT enforcement

FCEUX setup, live observation, Show, engineering harness and default reliability preflight now share `executable_discovery.py`; missing discovery refuses launch without a bare-name fallback. README, runtime/configuration and the SSOT map describe the implemented Codex roles and retained diagnostic/controller boundaries. Focused validation passed 218 synthetic component tests (208 before this pass), Ruff and syntax/whitespace checks. This source maintenance changes the candidate; prior native/package evidence keeps its original identity. Current pickup is consolidated local app delivery; renderer recovery is a component of the supported Stardew walkthrough, and reconnaissance is experimental. See [SSOT decisions](ssot.md#october-5-ssot-enforcement-pass).
