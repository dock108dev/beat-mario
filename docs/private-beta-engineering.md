# Game Companion engineering plan to private beta

Updated October 5, 2026. This is the complete active technical roadmap for the owner's personal Mac private beta. [product direction](product-direction.md) owns the experience; [architecture](agent-architecture.md) defines the two AI responsibilities. Historical B/V2/PB plans and verification records describe their own implementations, not the new beta's completion.

## Source AI milestone — October 5 connected acceptance

Mario’s supported World 1-1 x≥700 segment has 3/3 native completions on the final unchanged source, with independently observed alive/grounded arrival and neutral handback for each passing run. The set includes two compatible-coaching trials and a walking-on-flat/raised-block landing preference variation. Earlier failures remain failed under their own candidate identities. Running maneuvers, a feedback-bounded run-up, native object/projectile/motion facts, neutral waiting and after-frame arrival checks address the retained blockers. This small engineering set establishes observed scope, not broad reliability. Prepared Stardew watering acceptance is preserved. See [verification](gc-ai-loop-verification.md). Wider Mario coverage, exact-package qualification and owner release remain open.

## Release target

The player can talk naturally about a goal, have the companion understand the game and choose how to pursue it, watch approved play, correct its decisions, interrupt immediately and reopen useful remembered results. Deliver this for bounded but useful Mario and Stardew coverage through a Mac app. Minecraft connection/calibration carries forward with accurate capabilities; complete Minecraft play develops later during beta.

This is a single-owner local application. Use the already installed, ChatGPT-authenticated Codex CLI as the first model backend. The app and game tools run locally; ordinary OpenAI-backed inference is remote. No hosted application service, public accounts, fleet infrastructure or custom model-training program is required. Validate the actual provider's latency and availability during implementation; installation/login alone establishes neither gameplay quality nor unlimited usage.

Private-beta readiness requires two connected AI responsibilities:

1. **Contextual language LLM:** original words and conversation/game context become an understood objective, targets, preferences, constraints, clarification and coaching.
2. **Game-understanding/play agent:** current observations, mechanics, available capabilities and memory become action choices, verified effects and revised decisions during play.

One model/provider may serve both. Existing deterministic controllers execute fast finite skills and remain responsible for timing and release. Engineering chooses modules, schemas, prompts and algorithms. The requirements below define behavior and interfaces, not prescribed phrases or a controller implementation.

## Current foundation and honest status

| Area | Available foundation | Remaining release work |
| --- | --- | --- |
| Conversation | Ordinary game workspaces, typed plans, review/approval, priority interruption and history | Broader contextual/coaching evaluation and reusable strategy coverage |
| Model integration | Separate local Ollama/reference-profile gateway; installed and signed-in Codex CLI inspected | Source Codex lifecycle implemented; packaged discovery and wider provider-limit evaluation pending |
| Mario | Observed coached opening, remembered authored stairs/pipe tactics, two World 1-1 exits, two supported sky 1UP collections, outcome receipts | Wider hazards, other forms/starts and useful unseen combinations |
| Stardew | Observed selected watering, planting discussion and eastern inspection on supported prepared settings | Prepared watering model decisions implemented; broader perception, skills and changed-condition coverage pending |
| Cave | Local activity lifecycle, camera work and a newer manually verified tool-free route | Ordinary companion round trip remains unverified; manual route records do not establish delegated activity or AI play |
| Learning | Persistent coaching, discoveries, outcomes and experimental instructions | Contextual retrieval/updates that demonstrably alter agent decisions, inspect/reset, contradiction handling |
| Setup/delivery | Launchers, process/window isolation, prepared farms, player store and retained private.2 package | Integrated Mario/Stardew/Codex setup, app-owned assets, successor package and ordinary package verification |
| Verification | Local gates plus bounded source-gameplay records | Real-model evaluations, adaptive play variation, new readiness contract and exact packaged two-game walkthrough |

Recording source work is preserved but deferred to tentative beta v2. Full Mario coin coverage, arbitrary English action execution, later levels, arbitrary farms and broad reliability remain unknown. Prior successes provide regression assets and reusable skills; they do not complete the two AI layers.

## Ordered work packages

Status is **Foundation**, **Partial** or **Open**; mark a package complete only when its exit is evidenced. Tasks may progress together where dependencies permit. Complete one model-driven vertical slice early, then extend it; avoid building all infrastructure before it affects ordinary gameplay.

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
| GC-S | Model-driven Stardew activities | GC-A2–A6 | Partial: watering accepted; reconnaissance source implemented, native setup/acceptance pending |
| GC-U | Ordinary setup, conversation and shared usability | GC-A1; both adapters | Partial |
| GC-Q | Model, gameplay, control and regression evaluation | Starts with A1; exit after M/S/U | Actual-model and source live trials; wider evaluation pending |
| GC-D1 | Complete app resources, packaging and readiness contract | GC-U; release capability set | Partial retained delivery |
| GC-D2 | Exact-package end-to-end qualification and repairs | M/S/Q/D1 | Open |
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
- Deliver one meaningful exploration/reconnaissance activity. Clarify the destination and actual entrance/interior coverage. Complete any required supported route work within reusable perception/navigation improvements.
- Verify task/target/resource/preference variation without engineering coordinates and without a custom full script for each variation.
- Provide usable disposable/copy setup and backup/isolation checks, clear manual prerequisites, supported settings and tool/refill remedies.
- Preserve protected crops/resources and final return accounting; do not label unknown species or off-screen state as confirmed.

**Exit:** the agent chooses and revises real Stardew work across useful activity variations, including interruption and reopening. A prepared farm may define initial coverage, but the model must actually reason and adapt within it.

### GC-U — ordinary setup and coherent product UI


GC-S native acceptance remains pending. GC-U source setup adds catalog Codex readiness/refresh, macOS permission status, direct Mario/Stardew setup, explicit installation selection, Finder FCEUX discovery and corrected Mario setup returns. Preparation binds every step to its displayed process/window/bounds, moves the SDL pointer before clicking, and releases input after each step. A fresh isolated Day 2 copy reached the porch through the ordinary controls. Supported reported bounds were restored, but the rendered toolbar remains below retained calibration and its water bar is clipped; selected-can recognition refused. Guarded screen-rectangle capture did not resolve that rendering mismatch. Stop confirmed neutral input and player handback; the test game was closed without saving. No reconnaissance trial began. Canonical validation passed 1659 tests and all checks. Repair the disposable renderer/window layout without changing resource guards, then run the finite two-investigation/Stop/Take-control/reopening set and focused Mario/Stardew usability walkthrough. GC-S/GC-U source qualification remains pending. The initial GC-D inventory covers 90 referenced resources; packaging, exact-app GC-Q/GC-D qualification and recording remain separate, with recording deferred to tentative beta v2.

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
- Check initial Minecraft connection/calibration entry with truthful available capabilities. Full Minecraft gameplay remains a later-beta deliverable.
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

Use the task exits to decide what comes next. Routine Git/version identification is part of engineering, not a separate reconciliation project. Make reversible decisions autonomously. Preserve saves, credentials, accepted routes, evidence and incoming work.

A perception fix, new primitive or route repair is valuable when it unlocks the current AI milestone. Report the capability it enabled and demonstrate the connected behavior. Extend reusable capabilities that improve the connected model loops rather than adding isolated scripted scenarios.

If live access is unavailable, complete useful independent implementation and identify the exact pending check. Do not turn repeated missing input windows into additional synthetic qualification campaigns.

## Documentation ownership and completion

Maintain this repository-local plan as the active worklist, product direction as the intended experience, architecture/runtime/security as contracts, player guides as implemented behavior, and dated verification records as evidence. The PM handoff contains only current pickup/status. Historical plans are references, not active next actions.

At every integrated closeout record actual model-driven behavior, automated checks, live/game/package evidence, remaining gaps and the next work package. Documentation updates do not themselves implement or qualify the new beta.

## Preserved evidence and later work

Use [opening/discovery verification](gc1-gc2-coaching-verification.md), [route verification](gc2-route-verification.md), [flight verification](gc2-flight-verification.md), [watering](gc3-watering-verification.md), [planting](gc3-planting-verification.md), [inspection](gc3-inspection-verification.md), [incomplete cave](gc3-cave-verification.md), [deferred demonstrations](gc2-demonstration-verification.md) and [retained package review](private-beta-review.md) for actual prior outcomes.

After initial local release: wider levels/farms/settings, completed Minecraft gameplay during beta, advanced guided no-code eligible-game onboarding, recording/demonstration qualification tentatively in beta v2, and eventual independent practice. These are not hidden initial-release gates.

## Documentation pass coverage

This pass reviewed the repository README and all top-level docs for scope/status consistency. Updated active product/architecture/engineering/PM/worklist, conversation/learning/limits, game interfaces/guides/onboarding, runtime/setup/ownership, observation/goals, security/recovery, UI/evaluation/metrics, assets/development/index and retained-package entry guidance. The plan contains the complete task sequence.

Historical B/V2/PB handoffs are explicitly labeled references. Dated verification records retain their results; the cave record has a status clarification for newer manual-route artifacts without converting them to ordinary activity success. Stable route schemas, FCEUX/reliability operator mechanics and accepted-route records remain implementation references. Retained app manifests/adjacent guides and gameplay artifacts were not changed.

This is a documentation update only: no Codex-backed runtime, new game skill, package, gameplay verification or release acceptance is established by it.

## Next source activity

GC-S native acceptance remains pending. GC-U source setup adds catalog Codex readiness/refresh, macOS permission status, direct Mario/Stardew setup, explicit installation selection, Finder FCEUX discovery and corrected Mario setup returns. Preparation binds every step to its displayed process/window/bounds, moves the SDL pointer before clicking, and releases input after each step. A fresh isolated Day 2 copy reached the porch through the ordinary controls. Supported reported bounds were restored, but the rendered toolbar remains below retained calibration and its water bar is clipped; selected-can recognition refused. Guarded screen-rectangle capture did not resolve that rendering mismatch. Stop confirmed neutral input and player handback; the test game was closed without saving. No reconnaissance trial began. Canonical validation passed 1659 tests and all checks. Repair the disposable renderer/window layout without changing resource guards, then run the finite two-investigation/Stop/Take-control/reopening set and focused Mario/Stardew usability walkthrough. GC-S/GC-U source qualification remains pending. The initial GC-D inventory covers 90 referenced resources; packaging, exact-app GC-Q/GC-D qualification and recording remain separate, with recording deferred to tentative beta v2.


## Demonstrated bounded Mario milestone — October 5

- [x] Three final-source native arrivals at x=700, 700 and 713, alive and grounded, with independent neutral acknowledgment.
- [x] Compatible repeat and completing walking/raised-block preference variation on unchanged source.
- [x] Compatible guidance application, ordinary approved retry, pending-inference Stop, no continuation and descriptive reopening.
- [x] Final canonical gate: 1,634 tests and the repository checks.
- [ ] Broader hazards/starts/forms, full adaptive levels, complete coins and exact-package/owner qualification.

## October 5 source maintenance — SSOT enforcement

FCEUX setup, live observation, Show, engineering harness and default reliability preflight now share `executable_discovery.py`; missing discovery refuses launch without a bare-name fallback. README, runtime/configuration and the SSOT map describe the implemented Codex roles and retained diagnostic/controller boundaries. Focused validation passed 218 synthetic component tests (208 before this pass), Ruff and syntax/whitespace checks. This source maintenance changes the candidate; prior native/package evidence keeps its original identity. GC-S renderer repair and pending acceptance remain the next gameplay work. See [SSOT decisions](ssot.md#october-5-ssot-enforcement-pass).
