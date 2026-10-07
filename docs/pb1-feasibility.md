# PB1 — Reusable gameplay feasibility

> Historical evidence or work order. Results and contracts retain their named scope. Any “current,” “next” or prerequisite instructions below belong to that checkpoint. For candidate.35 and resumption use [current engineering status](current-engineering-status.md) and the [Desktop tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md).

> Historical implementation/evidence reference. Its recorded contracts and results retain their original meaning. Active next work and complete local private-beta requirements are in the [engineering plan](private-beta-engineering.md) and [Desktop worklist](/Users/michaelfuscoletti/Desktop/mario_next_steps.md), including contextual Codex interpretation and adaptive gameplay decisions. Do not use a continuation below as the current pickup.

Historical PB1 feasibility report. All candidate identities, counts, limits and handoffs below describe that recorded experiment. Current integration and delivery work follows the [private-beta engineering plan](private-beta-engineering.md).

September 30, 2026. **PB1 engineering feasibility is complete for the bounded menu interaction described here.** The final eight declared real-game cases passed on one engineering Mac. Three fresh processes repaid exactly £10,000 and independently verified both balances. Correction, ambiguity refusal, Stop, Take control and cancellation during a dispatched inference request passed. This establishes one reusable task family; PB2–PB11, including Minecraft PB7M, remain open.

## Candidate and evidence

The PB1 checkout entered and was retained at HEAD `719009c4fa2f17c6d28790d0676c50ffb23bfe2c`, with uncommitted implementation. Exact executable source maps, profile/configuration/checkpoint identities and backend identity live in `artifacts/private-beta/pb1/candidate.json`. All final trial manifests match the historical PB1 runtime source map SHA-256 `256cb244e1ae45dbc693df106650f86c8fdac07fe9fa185b6256cb0a9238dd3a`. Documentation edits do not change that executable identity. PB2 recorded a separate candidate in `docs/pb2-integration.md`; original PB1 source bytes are preserved under `artifacts/private-beta/pb2/baseline/`.

Evidence is retained locally under `artifacts/private-beta/pb1/`: experiment declarations, `trial-01` through `trial-34`, `summary.json`, `candidate.json` and `preflight/`. Each trial owns frame pixels and hashes, selected PID/start/window, timestamped observations, structured proposal/review, input acknowledgments where available, outcomes/history, native release receipts, model usage and resource samples. Setup and retained-image probes have separate evidence classes and do not qualify gameplay. These artifacts are ignored local evidence, not a distributed package.

## Declared experiment and isolation

| Item | Frozen condition |
| --- | --- |
| Game | Installed OpenTTD 15.3; free OpenGFX 8.0 |
| Machine | M3 Pro, 11 CPU / 14 GPU cores, 18 GB unified memory; macOS 27.0, build 26A428 |
| Display | External 3440×1440 above built-in 3024×1964; selected window only, including negative desktop Y coordinates |
| UI | Cocoa client 1280×1024; captured window 1280×1056 including title bar; Arial 12, English, GBP |
| World | Disposable company paused January 1, 1950; `command_pause_level=2` permits money management while paused |
| Entry | Finance panel visible; independently read loan £100,000 and bank balance £100,000; unique Repay £10,000 label |
| Task | Repay £10,000 once; verify loan **and** bank balance become £90,000; neutral handback |
| Protected during execution | Borrow, build, sell, demolish, unpause, save and network |
| Correction boundary | Before the one action: changing the request cancels the prior review; no already-applied effect is undone |
| Limits | Three calls/task, 60 seconds/call, 180 seconds/task, 4096 context tokens, 256 output tokens, image 4 MB, context JSON 16,000 characters; local provider fee budget $0 |
| Input | Reviewed, freshly grounded mouse target; requested 80 ms pulse, hard primitive ceiling 250 ms; frame age ≤2 seconds |
| Qualification | Three fresh-process task repetitions plus correction, ambiguity, Stop, Take control and pending-inference cancellation; first failed boundary stops that group |
| Proposed performance bounds | Sampled aggregate process RSS ≤8 GiB; direct control handler ≤250 ms; these are feasibility limits, not release thresholds |

The launch uses an isolated config and `-X -x`, excluding global/personal directories. Ordinary Save UI created the checkpoint in the owned test directory; fresh ordinary loads reproduced both entry balances before every trial. The final checkpoint SHA-256 is `16ad1f1a62996974082e3fb9b0e395d549e9b07ae6da3c75953fa977c3798d56`. Save bytes were hashed for identity, never interpreted as gameplay state. No personal saves were inspected or changed.

The isolated application initially lacked language, graphics and sound base files. Bundled language, fonts, `NoSound`, `NoMusic`, OpenTTD graphics/title resources and free OpenGFX resolved launch. Audio output is null for this test session. No paid assets or system/daemon upgrades were acquired. OpenGFX came from the [official downloads](https://www.openttd.org/downloads/opengfx-releases/latest); its archive hash is retained. Isolation/setup scripts open the finance panel with manually reviewed ordinary input; that preparation establishes neither useful gameplay nor nonprogrammer onboarding.

Declarations `experiment.json` and `experiment-v2.json` through `experiment-v7.json` precede their respective groups. Each repair begins a fresh process/checkpoint; failed earlier candidates remain visible. The final group is trials 27–34, declared by `experiment-v7.json`.

## Implemented execution and shared owners

| Source | Responsibility |
| --- | --- |
| `src/smb3_agent/screen_host.py` | Explicit selected PID/start/window, foreground/occlusion/geometry checks, existing native window capture, immutable frame reference/hash and bounded local OCR |
| `src/smb3_agent/model_gateway.py` | Local multimodal transport, pinned model identity, finite structured response schema, call/time/image/context budgets, cancellable subprocess and dispatched-request acknowledgment |
| `src/smb3_agent/game_profiles.py` | Finite declarative sensors, skill signatures, entry conditions, exact integer deltas, target regions, explicit action vocabulary and compatibility identity |
| `src/smb3_agent/profile_runtime.py` | Existing typed planner/session/observation/history contracts; independent target/state validation, review/Start, control epochs, bounded input and observed outcome |
| `src/smb3_agent/ordinary_input.py` | Existing bounded native input driver with independently read HID key/button state plus pressed ledger; at most 50 ms to observe a queued release acknowledgment |
| `src/smb3_agent/profile_catalog.py` | Existing catalog provider/registry seam, experimental setup-required capabilities and volatile-authority invalidation on switch |
| `data/private-beta/openttd-pb1.json` | OpenTTD meanings and settings; profile hash `4f9525be70a69aad1e6dfe899b3ebbdcea6a5cb3c6d5bb3ba4e1507d6b2f2443` |
| `scripts/pb1_feasibility.py` | Explicit isolated engineering entry, real-game cases, candidate manifests, input observation and owned-process resource sampling |

The path is selected-window pixels → frame-bound OCR target/integers plus multimodal proposal → existing `ConversationPlan` → independent runtime checks → ordinary bounded input → fresh exact deltas → `SessionOutcome` and `PlanAttemptHistory`. It uses `Planner`, `AdapterProposal`, `PlannedAction`, `CompanionObservationEnvelope`, `CompanionSession`, `CatalogRegistry` and the existing native capture/input owners. It does not introduce a parallel application or game-state store. Existing Mario/Stardew implementation files were unchanged.

The model receives the selected window and bounded request/skill/current-observation context over loopback. Its normalized target box must agree with an independent unique text label. Fresh captures after inference, before action, after pointer movement and after input reconcile state and target identity. Model confidence never establishes success. Unknown, ambiguous, moved, stale, incompatible, altered or unfocused observations refuse execution. A reviewed left-of-label anchor remains inside the declared button region and keeps the cursor from covering the currency text.

Authority is absent until the exact current finite plan is reviewed and explicitly started. Stop/Take control first revoke authority, change the epoch, cancel pending work and neutralize independently of planner/persistence locks. The gateway kills/reaps its request worker; late results cannot restore authority. Disconnect does not prove cancellation of Ollama's underlying GPU computation or reveal canceled-call tokens. The direct path records unavailable release truthfully and blocks fresh authority until neutral state is confirmed.

`begin_chat()` is the host/UI seam to call **before** typed chat takes foreground focus. The prototype invoked it before proposals. Its closeout handed that transition, visible Review/Start, lifecycle controls and catalog discovery to PB2/PB4/PB6 integration. This runner was the engineering surface for that experiment.

## Actual results and every gameplay attempt

| Trials | Cases and result |
| --- | --- |
| 01 | Task failed: low model confidence, no input; refusal retained |
| 02 | Task failed: cursor obscured target after pointer movement; no click; movement was input |
| 03 | Task partial: click delivered, game refused repayment while paused at its default pause level; both balances unchanged, neutral receipt confirmed |
| 04–06 | Three fresh-session tasks completed after isolated pause-level repair |
| 07–08 | Correction passed; ambiguity failed because proposal chose repayment for an unnamed loan-button request; no click |
| 09–11 | Three fresh-session tasks completed after independent action/negation guard repair |
| 12–15 | Correction and ambiguity passed; Stop and Take control passed, interrupted tasks remained partial |
| 16 | Cancellation passed at gateway preparation; actual HTTP dispatch was not yet evidenced, so this alone did not close pending-backend cancellation |
| 17–18 | Task failed when foreground focus changed during inference; no input and confirmed handback |
| 19–24 | Actual dispatched-request cancellation, three fresh completions, correction and ambiguity passed |
| 25–26 | Stop passed; Take control task stayed partial because the immediate native state read still showed left mouse held despite an empty ledger. Final exit later confirmed release. This failed the group |
| 27 | Take control during press passed after bounded native acknowledgment repair; task partial, both observed balances £90,000 |
| 28–30 | **Three fresh-process useful tasks completed**: loan and cash £100,000 → £90,000; confirmed neutral handback |
| 31 | “Actually, do not repay anything. Leave both balances unchanged.” invalidated the prior review and produced clarification; no input |
| 32 | “Use the loan button.” produced clarification through the independent ambiguity guard; no input |
| 33 | Stop during press passed; task partial, both observed balances £90,000; confirmed release |
| 34 | Take control during an acknowledged dispatched inference request passed; worker ended, late reply discarded, no input, confirmed release |

Across **34 declared gameplay/control attempts**: 12 completed, 7 partial, 5 failed and 10 passed advisory/cancellation cases. Ordinary task attempts: **12 completed / 17 attempted**, one partial and four failed. Six active-press interruption cases: five passed and one failed release verification; all six task outcomes stayed partial. The final candidate passed **8/8 required cases**, including **3/3 ordinary tasks**. Earlier completions do not qualify later source revisions. Zero false verified completions were observed among 12 completion records; this small matrix does not estimate a general failure rate.

Stop does not roll back an already delivered click. The final interrupted cases independently observed its financial effect and still reported partial because completion was interrupted. Ambiguity handling is partly deterministic: the model previously guessed the only declared skill. An explicit, non-negated configured action vocabulary now independently blocks that guess. General request interpretation and multi-step correction are unqualified.

All 34 attempt records remain. There were also **four retained-image warmup calls without input authority**. Three individual records remain; one preliminary warmup metadata file was overwritten during preparation. Its latency/token metrics are unavailable and excluded from measured totals. This is an accounting limitation of setup evidence, not a missing gameplay trial; no warmup is counted as task success.

## Backend decision and measured envelope

Use **local Gemma 3 4B provisionally for this slow, readable menu family on the tested Mac**. Installed Ollama version is 0.12.3. Model `gemma3:4b` is 4.3B, GGUF Q4_K_M, 3,338,801,804 bytes, with completion/vision capabilities. Exact digest: `a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a`. Requests use temperature 0, seed 1, context 4096, output ceiling 256 and two-minute keep-alive. Identity is checked before and after returned calls; cloud tags and non-loopback transport are rejected.

The previously installed `llama3.2:latest` is text-only. [Gemma 3 4B](https://ollama.com/library/gemma3:4b) is compatible with the installed daemon. [Qwen3-VL 4B](https://ollama.com/library/qwen3-vl:4b) requires a newer daemon and was not evaluated; this task did not upgrade it. Provider option: **zero calls**, because actual screen/context transmission was not explicitly authorized. No provider latency, cost or model-quality comparison is claimed. Credentials were not inspected, acquired or retained.

Prerequisites are the installed game/free graphics, local Ollama and downloaded weights, existing Tesseract 5.5.1, Python dependencies, and macOS capture/input permissions. Apple Vision OCR was not selected after a native error and poor bounded results; two local Tesseract passes over the selected window provide the independent sensors. Inference requires no external service after installation, but clean-machine/offline delivery is unqualified. macOS/chip support is **only the tested configuration above**; no other OS version, architecture, smaller-memory machine, UI language or game family inherits evidence.

Percentiles below use median and nearest-rank p95; with small samples p95 is the maximum. Cancellation samples are excluded from returned-model latency.

| Measured quantity | Samples | p50 | p95 / peak |
| --- | ---: | ---: | ---: |
| Returned local model calls, all gameplay revisions | 35 | 4.324 s | p95 28.354 s; max 42.501 s |
| Returned model calls, final candidate warmed | 8 | 4.356 s | 4.862 s |
| Live capture plus OCR grounding, final candidate | 32 | 1.343 s | 1.538 s; max 1.547 s |
| Separate idle capture probe, technical only | 5 | 0.161 s | 0.697 s |
| Separate idle OCR grounding probe, technical only | 5 | 1.113 s | 1.157 s |
| Uninterrupted native pulse, final tasks | 3 | 80.718 ms | 81.842 ms |
| Input acknowledgment → fresh verified observation | 3 | 1.491 s | 1.556 s |
| Request/chat-neutralization → completed outcome | 3 | 11.419 s | 12.386 s |
| Direct Stop/reclaim handler during press/inference | 3 | 0.097 ms | 0.119 ms |
| All final control/neutralization handlers | 26 | 0.041 ms | p95 15.811 ms; max 17.219 ms |
| Sampled owned-process CPU sum | 282 | 39.05% | peak 102.0% |
| Sampled owned-process RSS sum | 282 | 0.683 GiB | peak 3.715 GiB |
| Ollama reported model GPU allocation | 282 | 4.846 GiB | peak 4.846 GiB |

Resource sampling covers controller, selected game, Ollama service and descendants including OCR/request workers, at approximately 250 ms intervals. `ps` CPU counters use 100% per core and are sampled counters, not an instantaneous or sustained-load benchmark. Ollama allocation is reported separately; unified-memory GPU allocation and process RSS must not be added as independent physical RAM totals. GPU utilization, total-machine working set, power and sustained gameplay FPS were not measured. Earlier partial resource scopes are retained but do not define this final envelope.

Control durations measure the direct handler, excluding human UI interaction and thread scheduling. The final pending-request call ended after 0.142 seconds from gateway request preparation; this includes worker cancellation and does not measure server-side compute cessation. Ordinary product controls and their end-to-end UI latency remain later qualification.

The paused game's financial effect was visible at the first valid post-action observation in all final tasks. Responsiveness numbers include local sensing and are adequate for this slow task; they do not establish reaction-speed play, unpaused simulation, camera navigation or long-session reliability. Cold-load planning was materially slower. Foreground focus must stay with the selected game while this prototype observes; two actual focus-loss failures demonstrate refusal rather than background-input isolation.

Gameplay used **38 model calls**: 35 returned with known usage, three canceled with unavailable token usage. Known totals are **25,097 prompt tokens + 3,540 output tokens** across all gameplay revisions. The three retained warmup records add 2,163 prompt + 321 output tokens; one additional warmup's usage is unknown. Local provider fee is $0 per attempt and $0 per completed task, including warmups. Electricity, hardware cost and canceled compute are unknown; $0 is not a total operating-cost estimate.

The measured settings and conservative runtime budgets were retained for subsequent engineering. The proposed 8 GiB sampled-RSS and 250 ms control bounds passed this final matrix. The original follow-on design proposed PB9 tester-machine, sustained-session and resource acceptance rules; these samples describe only this experiment. Current beta measurements and release scope follow the private-beta engineering plan.

## Executable-profile schema and configuration boundary

`game-companion-executable-profile/v1` is implemented by frozen typed data and a strict JSON loader. Top level: `version`, `profile_id`, `game_id`, `game_build`, `settings_id`, `backend_id`, `viewport`, `frame_max_age`, `sensors`, `skills`, `protected_actions`.

Each number sensor contains an ID, normalized region and a literal text pattern with the single implemented integer capture `([0-9,]+)`. It needs exactly one ≥0.9-confidence match. Each click skill contains `skill_id`, `target_id`, `target_text`, `target_region`, `required_before`, `deltas`, `description`, `pulse_ms`, `click_anchor` and finite `request_verbs`. Entry values and expected deltas must cover every sensor, use exact integers, and describe a nonzero effect. The only anchors are label center and reviewed left gutter. Unknown fields, executable content, unbounded regex, invalid/nonfinite coordinates, protected skills, excessive inventories and incompatible versions are rejected.

Configuration supplies identifiers, language/UI regions, labels, finite action phrases, entry/resource values, bounded pulse length and exact arithmetic outcomes. The reusable implementation supplies capture identity, local OCR, unique matching, target/frame validation, typed proposal validation, negation/explicit-action guarding, native pulses and arithmetic reconciliation. There are no OpenTTD-specific branches in the runtime. Setup's fixed menu points are outside the qualified execution path; the task click is grounded again from current pixels.

The `game_build`/`settings_id` are declared engineering compatibility identities, with separately retained game/config/checkpoint hashes; arbitrary game-settings recognition and imported-profile trust are not implemented. Configuration cannot create navigation, camera aiming, spatial/3D perception, inventory semantics, generic predicates, feedback movement or arbitrary task composition. A key map or description cannot supply those missing capabilities. Profile validation/import hardening and player-facing calibration remain later stages.

## Validation and concrete handoff

Focused checks: **33 passed** in `tests/test_profile_runtime.py`. They exercise malformed structured results and invented success, protected/unknown targets, nonfinite/bool boxes, ambiguous OCR, stale/mutated captures, wrong geometry/focus, incompatible data, outcome mismatch, correction supersession, budgets/timeouts and worker termination, late-result cancellation, interrupted partial work, catalog switching, required isolation, independent native release acknowledgment and unconfirmed-release authority blocking.

The final executable candidate passed `PYTHON=.venv/bin/python scripts/validate_phase0.sh`: **1087 passed**, lint, credential/game-asset scan, goal/segment validation and player/Lab/Stardew render contracts. Log: `artifacts/private-beta/pb1/preflight/non-live-gate-v7.log`. An initial gate found existing Markdown links to ignored personal-beta evidence; the documentation now describes those as retained local paths without changing existing qualification facts. That repair is distinct from gameplay. Shared Mario/Stardew behavior was not modified, so unrelated accepted real campaigns were not repeated.

**Historical PB1 handoff to PB2:** integrate exact window selection, chat-before-focus neutralization, fresh review/Start and direct Stop/Take control into the ordinary shell; extract host capture/coordinate/input contracts while preserving existing adapters; add independent watchdog/shutdown and permission/process-loss qualification. Separate capture/OCR/planning/action telemetry and native acknowledgment evidence remain part of the recorded design. The subsequent PB2 report records that integration.

PB3 then versions detector/skill registries and independent verifiers around the implemented text/integer/click family, adds required feedback primitives and observable failure examples, and rejects unsupported profile capabilities. Relative camera capture, navigation and block-placement verification require new reusable engineering before Minecraft PB7M. The onboarding wizard must select qualified capabilities rather than generate executable semantics. Three-task reference-game qualification, unfamiliar-game configuration, portable package, tester usefulness and owner/release verdicts remain separate later gates. Nothing was committed, pushed, sent to testers or distributed.
