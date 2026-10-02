# Private-beta engineering plan

Updated October 1, 2026. **The private beta is the onboarding and real-use testing phase. Engineering now prioritizes an integrated app, clear setup/how-to guidance and a usable tester build.** The [Desktop tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md) owns remaining work. Historical PB1/PB2 results and camera attempts remain in their reports; this change does not qualify incomplete behavior.

## Product and launch scope

A technically comfortable nonprogrammer connects an eligible game, follows setup/practice, saves a profile and completes supported tasks mainly through typed conversation. Existing Mario/Stardew paths, profile-based reference-game work and Minecraft Java Creative tasks remain the direction. A playable profile parameterizes implemented skills; configuration cannot invent navigation or verification.

Before invitations, provide a coherent install/setup/play/Stop/reopen path, useful implemented tasks, understandable limitations and a feedback route. During private beta, testers do most onboarding usability evaluation, task variation, broader game configuration, sustained reliability and machine/environment testing. Unfamiliar-game evaluation, three-family reference-game coverage, the 30-minute setup target and exhaustive Minecraft matrices are beta exercises and improvement goals, not prerequisites for opening the cohort.

Do not require the former 48-core/30-fault camera matrix, three fresh-process repetitions or whole-matrix restarts to continue development. Preserve that material as optional diagnostic design. This policy change does not automatically remove runtime restrictions or enable camera input. Review and change those restrictions in implementation where appropriate, retaining conservative controls and truthful experimental labels.

Minecraft camera readiness, visible detection, native relative input and experimental controls are implemented; the first-callback suppression repair is documented. Camera's exhaustive qualification is incomplete. The report also retains unexplained movement outside owned emitter requests. Do not attribute it to human input without evidence or promote incomplete results. Continue independent integration while native testing is paused.

## Existing ownership and implementation seams

Reuse the current conversation, session, catalog, host, feedback and history owners. Avoid parallel product servers or a special controller that bypasses shared authority.

| Concern | Existing owner to reuse | Private-beta work |
| --- | --- | --- |
| Plans and revisions | [request_planning.py](../src/smb3_agent/request_planning.py), [conversation_service.py](../src/smb3_agent/conversation_service.py), [conversation_ui.py](../src/smb3_agent/conversation_ui.py) | Add model-backed proposals and profile skills while retaining typed plans, direct controls and revision binding |
| Ownership and continuity | [companion_session.py](../src/smb3_agent/companion_session.py), [takeover.py](../src/smb3_agent/takeover.py), adapter runtimes | Reuse player ownership, fresh authority, bounded execution, immediate reclaim and neutral handback |
| Catalog and switching | [companion_catalog.py](../src/smb3_agent/companion_catalog.py) | Profile-backed providers and task-specific proof labels; no shared-core game-ID branches |
| Screen/input foundation | [stardew_adapter.py](../src/smb3_agent/stardew_adapter.py), [stardew_input.py](../src/smb3_agent/stardew_input.py) | Extract reusable window/capture/control interfaces from game-specific calibration and action purposes |
| Current perception | [stardew_perception.py](../src/smb3_agent/stardew_perception.py), [stardew_farm_vision.py](../src/smb3_agent/stardew_farm_vision.py) | Add qualified reusable detectors/grounding; existing calibrated farm pixels do not generalize automatically |
| Outcomes and local evidence | [run_library.py](../src/smb3_agent/run_library.py), [learning.py](../src/smb3_agent/learning.py), [metrics.py](../src/smb3_agent/metrics.py) | Profile/skill/backend compatibility, observed task outcomes and configuration-test classifications |
| Contributor installation | [experimental_adapters.py](../src/smb3_agent/experimental_adapters.py), [onboarding guide](new-game-onboarding.md) | Separate playable-profile schema/provider from current fixture-only scaffolding; installation does not prove execution |
| Readiness and delivery | [beta_readiness.py](../src/smb3_agent/beta_readiness.py), [delivery.py](../src/smb3_agent/delivery.py), [launcher](../scripts/launch_companion.py) | Versioned tester build, focused launch checks and inspectable diagnostics |

Current source is authoritative for implementation status. Historical reports bind their exact candidates; they are not requirements to recreate every earlier run. The local model remains separate from immediate controls and fast motion feedback.

| Proposed owner | Responsibility |
| --- | --- |
| `model_gateway.py` | Backend/configuration identity, bounded multimodal input, structured results, cancellation, timeout, usage/spend, redaction and sanitized diagnostics |
| `screen_host.py` | Selected process/window/display identity, visible capture, scale transforms, capture timestamp and permission/occlusion status |
| `ordinary_input.py` | Mapped short actions, foreground/identity/freshness guards, pressed-input ledger, independent cancellation/watchdog and neutralization |
| `grounded_observation.py` | Frame-bound regions/labels/facts, source provenance, uncertainty, compatible detectors and target revalidation |
| `skill_contract.py`, `skill_runtime.py` | Finite typed primitives and predicates, parameters, eligibility, resource limits, outcomes, stop points and execution validation |
| `game_profiles.py` | Bounded versioned profile/skill inventory, compatibility, local manifests, import/export and integrity |
| `profile_onboarding.py` | Guided setup state, recording/annotation, candidate skill review, short practice and actionable setup failures |
| Private-beta readiness owner | Practical build/check/known-issue record and beta feedback; preserve personal-beta v3 behavior and evidence |

The model proposes typed plans; it cannot issue native input, execute arbitrary code, grant authority or declare verified success. Game-specific semantics belong to profile/providers. Profiles remain bounded declarative data.

## Current repository review and remaining integration

Reviewed October 1, 2026 against private.2 and its current source. This is a source/document review, not a new live run. The owner has made the Mac available for short native checks. The [private.2 owner review](/Users/michaelfuscoletti/Desktop/beat-mario/dist/private-beta/0.2.0-private.2/Owner%20Review.md) owns source identity, package limitations, 201 affected checks and native development observations.

| Implemented foundation | Remaining useful-path work |
| --- | --- |
| Player profile/setup/help/history/feedback and versioned packaging | Preserve it; finish and describe Minecraft tasks rather than recreating setup/storage |
| App calibration, bounded camera Review/Start and direct controls | Confirm the next package's useful gameplay path in a short integrated smoke; no camera matrix restart |
| `minecraft_scene.py`, inventory/hotbar/capture and native provider integration | Practical flat clear start, reliable fresh target/clearance inspection and efficient pose handling. Creative/material/one-addition development observations are retained, not package-wide claims |
| `minecraft_native.py` and `minecraft_camera_skill.py` | Finish nearby movement and aiming. Guard rejects unexpected translation/held input; key release alone cannot stop collision/game physics. Diagnose concrete failures without asserting an unproven cause |
| `minecraft_wall.py` coordinates inspections, approach, placement and final checks under a shared budget | Make the live wall path progress: avoid repeated scanning/aiming exhausting the task before movement; verify 19 solids, two doorway air cells, marked protected surfaces and return point |
| `minecraft_session.py` enables calibration/camera only | Enable aim/move/place/wall after focused practical checks for those paths, then rebuild accurate UI/manifest flags |

Remaining order: clear stable disposable start → efficient inspected move/aim/addition → useful wall completion and handback → enabled appropriate features and refreshed package → ordinary packaged wall smoke. The completed profile/setup/camera integration should not be reopened as missing scaffolding. Broad onboarding and reliability are beta work.

## Integration work — PB3 through PB7M

Stage IDs remain useful implementation references, not serial full-qualification gates. Work on skills, planning, setup, persistence, guidance and delivery together as their interfaces become usable.

### Shared observation and skill runtime

Reuse frame-bound observations and finite feedback/calibration contracts. Each observation binds actual capture time, pixels/window identity, settings and detector provenance. Each skill declares finite parameters, eligibility, feedback, budgets, correction boundaries and supported success/failure checks.

Use independent post-action observations. Event delivery and model confidence do not establish gameplay success. Unknown or contradictory observations stop the affected task and preserve partial work. Keep detector, policy, native execution and game semantics separate. Run focused checks for changed arithmetic, detector parsing, budgets, authority and cancellation.

### Camera and Minecraft movement

Integrate explicit readiness and calibration into ordinary setup/practice. Preserve finite preparation pulses, fresh visible response, settings compatibility and sampled settling checks. Remove player dependence on sealed engineering receipts or developer scripts through an explicit local profile/setup implementation; do not merely bypass validation.

Implement bounded forward/back/strafe and nearby approach/aiming on flat practice ground using the shared feedback loop. Re-observe between material actions, distinguish translation from rotation, and stop on uncertain pose, blocked paths or lost targets. Begin with conservative task/time/input limits. Expensive model inference chooses goals; local feedback owns motion and stopping.

A declared visible debug HUD may supply initial pose/orientation observations. Explain that requirement in setup. Do not claim HUD-disabled operation or hidden world knowledge. Settings changes require the appropriate recheck, without repeated full engineering campaigns.

### Minecraft interaction and useful task

Minecraft Java remains the required 3D product target, using a dedicated or verified copied Creative world. Profile/provider rules own block/material/hotbar semantics, reachable faces and occupancy. Shared motion and feedback remain game-neutral.

Implement aim at a fresh reachable face → confirm material/target → one placement → observe the result. Start with additions inside a reviewed work region; destructive actions require separately implemented and reviewed support. Preserve marked protected structures.

The first useful task is completing a 7-wide × 3-high × 1-thick wall with a centered 1-wide × 2-high opening. Its target contains 19 occupied cells and two empty doorway cells. Account for already-correct cells and observed new placements. Unknown/occluded cells remain unverified until inspected; do not invent completion from a wall-like screenshot.

Provide a short developer smoke for the integrated path when exclusive Mac input is available. Testers then exercise variations, corrections, different starts and usefulness during beta. General exploration, flying, parkour and survival remain later work.

### Conversation and task composition — PB4

Extend existing typed plans with profile/skill identities, current observations and bounded context. Support ordinary requests, questions, exclusions, clarification and changes to future work. Plans use only implemented skill signatures and retain one review/Start decision for their bounded scope.

Direct controls stay available independently of inference. Late or superseded replies cannot revive authority. Explain missing capabilities plainly. Do not expose internal schema, manifests or qualification vocabulary in the normal player flow.

### Guided setup and how-to — PB5

Build select game/window → permissions → prerequisites/settings → controls/calibration → disposable practice → supported task families → save profile. Prefer sensible defaults and supported templates. Explain failed setup with a concrete remedy. No YAML editing, terminal steps or developer-authored coordinates should be required for ordinary player configuration.

If teaching/demonstrations are offered, derive reviewable candidates from implemented primitives and outcome checks. A recorded macro alone is not a reusable skill. Missing capabilities must be explicit rather than yielding an apparently ready profile.

Include in-app guidance plus a concise first-use guide covering:

- App/game/model prerequisites and installation.
- Permissions, window selection and supported settings.
- Disposable worlds/saves and first practice.
- Camera capture and the need to avoid concurrent mouse/keyboard use while native automation runs.
- Tell/Show/Do behavior, example requests, review/Start, Stop and Take control.
- Saving/reopening, changed settings, recovery and known limitations.
- Inspectable issue/diagnostic export and how to give feedback.

Beta testers evaluate these instructions and setup usability. Record assistance and confusion so the flow improves; successful independent tester onboarding is not required before invitations.

### Profiles and normal product — PB6

Implement versioned save/reopen/edit/duplicate/import/export and history preservation. Bind profiles to supported game/settings/runtime/detector/skill versions. Reopening is useful but grants no fresh input authority. Switching, edits and removal neutralize current execution and preserve results.

Imports accept bounded declarative content only; reject code, unsafe paths and unknown executable capabilities. Default exports exclude credentials, personal saves and unrelated screenshots. Imported evidence does not establish local compatibility or execution authority.

## Focused checks and live-input scheduling

Before testers use a feature, confirm its basic integrated behavior and immediate control through focused regressions and a short practical smoke where native input is involved. Known wrong-window input, uncontrolled motion or broken Stop is a blocker for that feature; repair it or leave it disabled. This is not a demand for exhaustive gameplay testing.

Retain selected-window guards, finite input/time/model budgets, chat-before-focus neutralization, stale observation rejection, cancellation, direct Stop/Take control, shutdown and honest partial outcomes. Keep existing checks where relevant. Run the canonical gate once for an integrated handoff, repeating only after relevant changes or failures. Do not run full campaigns after every primitive or restart unrelated successful checks after a repair.

Native camera automation uses the owner's captured mouse/foreground. Do not start long campaigns or ask the owner to stop normal work indefinitely. Agree on a short input-exclusive smoke window when needed; otherwise continue code, UI, guides, profile and packaging work. If the owner needs the Mac, stop/release and preserve work. The owner has now made the Mac available for bounded native checks. Stop and release immediately if they reclaim it; availability does not justify the old full campaign.

Record practical build versions, affected checks and known issues. Historical evidence retains its classification; fixtures are not live proof. Do not create an expanded readiness-validator project solely to enforce removed matrices.

## Delivery integration — PB10

Prepare a versioned tester-usable Mac build alongside feature integration. Bundle the app-owned runtime/dependencies needed for the chosen distribution, detect separately installed game/model prerequisites, and keep profiles/history outside the installation. Avoid reliance on ignored developer files. Do not bundle proprietary game assets.

Check install/launch, permissions, one useful task, Stop/shutdown and reopening on the intended initial path. Explain actual tested machine/settings limits. Broader hardware, installation variations, sustained performance and update behavior are evaluated during beta; do not advertise untested compatibility.

Use the signing/distribution approach appropriate to the chosen channel, with normal platform protections and actual account access. Do not require every architecture, clean-machine matrix or universal portability claim before the initial cohort. Any prerequisite needed by the testers must be documented and workable.

Provide local bounded diagnostics, version/profile identifiers and an inspectable export. No automatic cloud telemetry or hosted service is needed. Protect credentials, unrelated screen content and personal saves.

## Private-beta launch and learning — PB7/PB8/PB9/PB11

Prepare the actual app/build, quick-start guide, feature/limitation list and issue-reporting path for owner review. Launch readiness means the integrated path is usable, focused control checks pass, known hazardous defects are fixed or disabled, and testers know the experimental scope. Owner approval and the authorized cohort/channel remain the final distribution decision. Do not require tester acceptance before inviting the testers who will supply that feedback.

During beta, gather onboarding friction, profile creation/reopening, Minecraft task results and variation, reference-game task expansion, additional eligible-game attempts, interruption/recovery, resource/performance issues and installation differences. Repair concrete defects and recheck affected behavior. Record failures and useful assistance without forcing blind-title freezes or total requalification after every beta fix.

The proposed 30-minute setup goal is a usability measurement. The third-game task breadth, unfamiliar-game transfer and broader reliability targets guide iteration. They do not claim universal support and are not private-beta admission gates. Public-beta readiness can be decided later from actual beta findings.

## Immediate engineering handoff

Continue private.2's implemented Minecraft scene/native/wall providers. Establish a clear flat stable disposable starting position, repair affected move/aim/addition behavior and inspection inefficiency, finish ordinary wall execution, enable checked families and rebuild into a separate version. The Mac is available for bounded native work now; stop/release if reclaimed. Run a short useful packaged wall/outcome/control/reopen smoke. Preserve prior artifacts and partial results; no full qualification campaign or unrelated restart is required.

Do not commit/push, contact testers, purchase access or distribute. Finish with the app, exact setup, actual useful task result, limitations and owner review.

## Integrated review build — October 1

A local versioned Mac review build and guide are now prepared; the [owner review](/Users/michaelfuscoletti/Desktop/beat-mario/docs/private-beta-review.md) binds the actual packaged candidate and checks. The PHL OpenTTD one-repayment smoke passed with independent outcomes, neutral handback and profile/history reopening. Packaging OCR/configuration/cursor defects were repaired and affected checks repeated. Minecraft native input remains disabled; visible material/ground/empty-cell integration and useful wall execution are unfinished. The canonical gate ran once; no exhaustive camera qualification or whole-matrix restart occurred. Native work ended with the app/game closed and the Mac released. Continue the remaining product implementation within this plan; this review build is not full private-beta launch acceptance.


## private.2 Minecraft integration in progress

The separate private.2 candidate preserves private.1 and its successful packaged OpenTTD smoke. PHL 346E2C is connected; native work uses only the visibly verified disposable Creative world. Current gameplay uses vanilla Minecraft Java 26.3, an 854 × 508 point selected window, native 1× PHL capture retained with exact 2× glyph decoding, and app-created directional calibration. Personal Survival worlds remain untouched.

Live calibration measured eight signed responses near 0.15 degrees per unit. A bounded camera task and centered reachable-face aiming completed with independently observed settling and native HID release. Creative inventory, selected Oak Planks and the resumed-world hotbar texture were independently read from pixels. One 60 ms addition produced an observed Oak Planks block at (5, −60, 10). A result serialization defect occurred after that addition; the before/after evidence and release receipt were preserved, the reporter repaired, and a subsequent check confirmed the existing block without another click. Air/ground intervals touching at their boundary now qualify clearance consistently.

Ordinary profile save/reopen/edit, calibration, window/display selection, world-bound region review, pointed-block protection, bounded requests, saved corrections, priority Stop/Take control, history and local feedback are integrated. Reopening restores configuration only. Movement and wall completion are still being checked; unverified families remain unavailable in the runtime and UI. A movement probe observed a position change during camera inspection and stopped before any movement command; its cause is not established. The guard now rejects translation during aiming and held physical keys/buttons before pulses. Historical r7 motion remains unattributed; the owner explicitly identified their interruption in a separate aim attempt.

The earlier checkpoint statement that PHL was absent and the game closed is historical, not current. No packaged Minecraft wall smoke or final wall success has been established yet. Continue focused repairs and short input-exclusive checks; preserve all partial results. No commit, push, distribution or tester contact occurred.

### Retained short checks after the clearance repair

The saved addition was re-inspected through the native port and reported completed/existing with no further placement. The repaired reporter serializes actual shared input commands before writing outcomes/history; write failures now preserve the observed gameplay result and release instead of suggesting a retry. The ordinary pointed-protection action is connected to setup and tested.

A nearby-movement inspection stopped on changed player position before any movement command. A tighter position guard now checks every aiming feedback frame and refuses held keys/buttons before camera pulses. Its next check retained a stable position but exhausted the 180-second total inspection budget before moving. Camera composition now uses one axis per child, at most 24 degrees, with individual pulses capped at 64 units, independent predicted-response checks, fresh captures and settling. No task budget or freshness guard was relaxed.

Key-up-only recovery did not establish stillness. A retained frame shows a large animal next to the player; collision is a plausible source of the current displacement, not proof of its cause or of the historical r7 motion. A later bounded disposable setup move ended one block lower than expected and preparation stopped. No jump or wall placement followed. The area needs a clear, flat starting position before further useful checks. Input was released after every attempt; no worker or held key/button remained.

Current native evidence is in `artifacts/private-beta/private2-checkpoint/brief-state4/`: `movement-confirmation`, `movement-stationary-guard-recheck`, `key-up-recovery`, and `platform-clear-space-preparation`. Camera/calibration are available; aiming, nearby movement, additions and wall Start remain unavailable pending their remaining affected checks and the packaged ordinary Minecraft smoke. This is unfinished integration, not launch acceptance. Native input is paused awaiting the next agreed brief window. The preserved private.1 packaged OpenTTD smoke is unchanged.
