# Current engineering status — October 6, 2026

This repository record binds qualification evidence to the retained candidate and lists remaining engineering checks. **Engineering acceptance is open; owner usefulness review and the local beta decision have not begun.** This documentation audit adds no gameplay acceptance.

## Exact candidate and stopped state

Installed app: `/Users/michaelfuscoletti/Applications/Game Companion.app`. Retained package: `dist/private-beta/0.3.0-candidate.35/`, version **0.3.0-candidate.35**, build **30035**. Runtime source SHA-256: `dcb3dbe177a9409f733b7aad6c30e4a7d5ee861107a0904a1276b3df890f2f2b`; **367 source files, 196 packaged resources**. The [build manifest](../dist/private-beta/0.3.0-candidate.35/build-manifest.json), matching source archive and installation receipt identify delivered code. The [qualification record](../dist/private-beta/0.3.0-candidate.35/qualification.json) remains in progress.

The app and owned Stardew/FCEUX games are currently closed. Local `app-lifecycle.json` records `state=closed`, PID 9589, no restored authority and no cleanup failures. The last Mario helper received connection refused before submitting its request; this establishes neither a gameplay failure nor an app crash. Reopen and verify fresh state when engineering resumes. All Finder windows were closed at the owner's request; reuse one window and close it after launching.

The owner completed the specific authentication required by supported permission recovery. Stable certificate identity restored actual installed-app capture and guarded input. Certificate fingerprint: `39CBC0B0231D6A0DC5EDE4F15CC2CC2C4884BB91`; bundle identifier `local.gamecompanion.privatebeta`. Routine successors preserve that identity. Save selection and generic permission enabling are not pending owner work.

## Verified evidence

All paths in this table are retained under `artifacts/gc-delivery/ordinary-session/20261006-recovery/` unless stated otherwise. Source tests, replay, packaged smoke, actual-model native trials and owner acceptance keep separate meanings.

| Check | Result and scope | Evidence |
| --- | --- | --- |
| Canonical gate | 1,761 tests plus required lint, security, contracts and renders passed on frozen source35 | [Gate log](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-canonical-gate.log) |
| Portable package | Smoke passed from `/tmp`; this exercises no native input | [Smoke](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-isolated-smoke/packaged-smoke.json) |
| Finder reopening | Exact delivered app; saved descriptions retained without plan, review or authority | [Reopening](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-finder-reopening.json) |
| Normal default save | Companion/Alex Standard farm created through the game, planted, slept/saved to Day 2 and visibly reloaded; distinct from frozen regression farm | Original `~/.config/StardewValley/Saves/Companion_450980429`; [Preservation receipt](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate34-exact-identity-original-preservation.json) |
| Ordinary preparation | Actual model prepared the isolated default-save copy from observed title/load/bedroom to readiness; 270 energy, 40 water, three dry crops | [Ready](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-ordinary-ready.json) |
| Contextual watering | All-three request corrected to middle only; fresh reviewed attempt completed in 126.657 seconds within 180 seconds. Middle wet, both outer crops dry; energy 270→268, water 40→39; farmhouse entrance observed; neutral player handback | [Native acceptance](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-ordinary-watering-native-acceptance.json) |
| Active Stardew Stop | Independent Stop during native movement before watering; 0.305 seconds response and neutral handback | [Stop](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-active-watering-stop.json) |
| Fresh review | Stopped plan Start refused; explicitly requested fresh finite activity subsequently succeeded; consumed stopped attempt preserved | [Old Start refusal](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-stopped-review-start-refusal.json) |
| Owned provider failure | Injected exit of verified app-owned provider process during a question; no plan/input authority; fresh actual-model question recovered. This is not a remote-service outage test | [Failure](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-owned-provider-failure.json), [Recovery](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-provider-fresh-question-recovery.json) |
| Neutral game switch | Stardew→Mario after handback; old cross-game watering Start refused | [Switch](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-neutral-switch-to-mario.json), [Refusal](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-switched-old-water-plan-refusal.json) |

Original save tree SHA-256 at retained preservation check: `87c47fad414d054e10fb943aee02e326da2d1a44475647b1239427880853ad51` (four files, 6,199,054 bytes). Final closeout must repeat original and frozen-fixture preservation checks on the delivered candidate.

## Repairs and failed trials retained

Permission recovery corrected stale code requirements through supported macOS mechanisms; no direct TCC edits or weakened guards. Preparation uses current screen/menu/player observations and default-save discovery with isolated copying. Target marker settings are visibly verified around watering and kept off during navigation. Avatar occlusion uses the same bounded footprint for cells and edges; unknown terrain still refuses. Requested watering durations are honored through 180 seconds; invalid bounds refuse before input. Original/frozen saves and existing app data remain preserved.

Candidate.33 stopped before watering on marker-obscured ground. Candidate.34 stopped on inconsistent cell/edge avatar footprints. Candidate.35's original native-frame replay and outside-footprint test qualified the reusable repair, then the fresh native watering trial above passed. Those older failures remain evidence, not successes. Candidate.35 initially rejected an out-of-bounds model Load click without input; a fresh observed preparation succeeded.

Candidate.30 completed a native Mario early segment with grounded alive endpoint and stable paused handback. Candidate.32's outcome repair replayed that trace. Neither establishes candidate.35 native Mario completion. On candidate.35 a normal disposable session reached World 1-1 entry; actual-model walking guidance was saved as `7a71d4e85ce844d98d5a9c7ac1d6899c`, for the exact cartridge and early-segment contract. Qualification helpers incorrectly expected new guidance on the already-built plan or at Review. They failed before Start and are helper errors. Start validates compatible current guidance; a fresh request should display the saved guidance before review. No candidate.35 coached gameplay completion or improvement is claimed.

## Remaining acceptance and resumption

1. Reopen the exact app from Finder using one window; verify build/source identity, current capture/input, closed prior lifecycle and fresh authority-free state. Preserve history and existing guidance. Open a fresh disposable Mario session and enter World 1-1 through normal menus.
2. Request one 480-second supported early-segment attempt using the saved preference: walk on clear ground, inspect after landings, build running speed for tall obstacles. Review compatible scope, Start, and verify alive grounded x≥700, independent neutral acknowledgment and game-owned review pause. Link matching native skill receipts to the saved guidance; demonstrate a meaningful walking variation against retained baseline. Improvement remains unknown unless independently demonstrated.
3. Complete affected final-candidate preparation, pending-inference and active Mario Stop/Take control checks; no late reply, input or background completion. The final active Stardew Stop already passed. Verify affected focus/window-change and disconnect recovery with fresh observation/review. Preserve consumed attempts; no implicit reset.
4. Qualify actual keyboard Quit and actual Dock Quit during active or pending gameplay, owned process/input cleanup, and historical reopening without restored authority. Candidate.30 keyboard Quit after completed gameplay does not prove active exit or Dock Quit. The current closed lifecycle does not identify the quit gesture.
5. Recheck final manifest/resources, original save and frozen-fixture integrity; complete evidence summary, qualification and owner walkthrough. If runtime/resources change, freeze/build a successor and rerun affected native checks plus canonical gate. Documentation-only updates do not change candidate.35's code identity or grant acceptance.

Stop at the first unmet gate, retain sanitized evidence, repair the reusable cause, and restart from a fresh authorized boundary. Never terminate unrelated processes or overwrite prior packages, saves, history or credentials. Engineering setup remains engineer-owned. Wider farms, full-level Mario, cave exploration, recording and unrestricted play are outside this milestone; recording remains tentative beta v2.

## Working checkout and retained build

The working checkout contains subsequent presentation, packaging-tool and
source/documentation maintenance changes. Public guides describe portable source
setup and current implemented contracts; named engineering/review/verification
records retain their exact historical scope. Player-facing planning labels were
replaced with feature constraints. These source edits do not update candidate.35
or inherit its native qualification. Runtime/resource changes require a new
frozen build and affected qualification before acceptance.

## Documentation and acceptance boundaries

This audit postdates the immutable runtime snapshot. Corrected repository guides and adjacent `Quick Start.md` are current; documentation embedded inside the retained app still reflects its build-time snapshot. Preserve its resource hashes and include corrected embedded documentation in the next runtime build. Earlier candidate headings/checklists in retained records are historical, even when their original wording says “current” or “next.” Follow this record for resumption.

Owner usefulness review and the local beta/release decision follow engineering acceptance. No synthetic test count, helper assertion, model explanation, stored advice or earlier-candidate success substitutes for final native evidence.
