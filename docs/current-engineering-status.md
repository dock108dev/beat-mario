# Game Companion — dated implementation evidence

> October 27 product reset: [Beta 1](beta-1-plan.md) is Minecraft-only, using a
> headless bot with its own character and Codex CLI. Ordinary chat must not pause
> play. Next is MC-B1-03 in the [Desktop tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md).
> The evidence below remains dated; its old priorities do not dispatch work.
> NES emulator companionship is goal 2. Stardew is out of active scope.

## October 27 — MC-B1-02 conversational source session

**Passed local source qualification and real CLI/game demonstration.** Minecraft
selection, actual viewer, persistent chat, go-to/follow, concurrent state-aware
replies, redirection, direct Stop, pending-inference cancellation, reconnect and
safe reopening were exercised. 51 focused Python checks and six Node checks
passed. [Launch/implementation](mc-b1-02-chat-play.md) ·
[Measurements and retained evidence](mc-b1-02-evidence-20261027.md).

No installed update, hosted CI or owner acceptance is claimed. Human walkthrough
remains deferred. Next: MC-B1-03 navigation/resource/inventory/tools.

## October 27 — MC-B1-01 headless source foundation

Local bot qualification passed: separate vanilla Java 1.21.4 world, Mineflayer
4.39.0, pathfinder 2.4.5, patched Prismarine Viewer 1.33.0, Node 24.22.0. Real
movement/server block updates, active/queued Stop, stale/duplicate rejection,
viewer reconnect, TextEdit typing during play and owned cleanup are recorded.
The owner deferred the human-client walkthrough; installed 26.3 cannot join the
1.21.4 practice server. A second protocol identity coexisted successfully.

[Implementation, protocol and launch](mc-b1-01-headless.md) ·
[Exact live results and limitations](mc-b1-01-evidence-20261027.md).
Source changes are uncommitted; no new package, installation, release or hosted CI
run is claimed. Codex CLI integration belongs to MC-B1-02. Beta 1 is incomplete.

## Historical October 25 audit

Updated October 25, 2026 after a repository/documentation audit. Scope: personal
use and a handful of users under the [working approach](personal-use.md).

**Historical October 25 result:** Stardew demonstrated a narrow ordinary
workflow; the installed coached Mario segment was unfinished at that checkpoint. No new gameplay was run during this audit.

## Source, installed app and verification

| Layer | Verified status on October 25 |
| --- | --- |
| Repository | Audited `main` at `5f946ba65f1b505aa6d94cced80f5aafd89bdcec`; clean before this pass. This pass edits documentation and one launcher help message; gameplay behavior is unchanged. |
| Hosted CI | [Run 40216300354](https://github.com/dock108dev/beat-mario/actions/runs/40216300354) passed on that commit: 1,758 tests passed, 35 skipped, plus lint, security/file guards, goal/catalog checks and UI render contracts. Dependency review was skipped as expected on a push. This is Linux/offline evidence. |
| Installed app | `/Users/michaelfuscoletti/Applications/Game Companion.app`: bundle `local.gamecompanion.privatebeta`, version `0.3.0`, build `30035`, corresponding to candidate.35. |
| Package identity | [Build manifest](../dist/private-beta/0.3.0-candidate.35/build-manifest.json): source digest `dcb3dbe177a9409f733b7aad6c30e4a7d5ee861107a0904a1276b3df890f2f2b`. All 196 manifest-listed installed resources matched on October 25. This check does not establish current permission readiness or new gameplay. |
| Source versus app | Later source includes Stardew focus-cancellation checks, UI changes, packaging/resource maintenance and stricter FCEUX selection. The lockfile now specifies Pillow 13.0.0; candidate.35 records Pillow 12.3.0. Opening the installed app does not apply these changes. |

Build/source/package checks establish different facts. Historical native results
below belong to the October 6 candidate.35 sessions. The current checkout has
not received a new native walkthrough in this audit. Existing permission and
ordinary-save setup succeeded then; use the app's current readiness checks if
anything has changed instead of repeating the obsolete candidate.13 setup.

## Working paths and remaining gaps

| Area | Evidence-backed status | Remaining useful work |
| --- | --- | --- |
| Ordinary Stardew | Candidate.35 prepared an approved isolated ordinary save, accepted a correction to water only the middle crop, left both neighbors dry, used energy 270→268 and water 40→39, returned to the farmhouse and confirmed handback. | Owner feedback on this supported task; repair concrete failures. Arbitrary farms, mature crops, upgraded tools and refill remain unsupported. |
| Stardew control/recovery | Active watering-task Stop was exercised during navigation before watering; input became neutral and handback was confirmed. Stale Start refusal, fresh review, owned-provider failure/recovery and neutral game switching have separate records. | Broader focus/disconnect/exit cases remain unverified; check the affected case when a change or actual use requires it. |
| Ordinary Mario | The source has the bounded visual strategy and compatible saved coaching. Candidate.35 reached a reviewable coached proposal; retained helper assertions failed before Start. No completed coached native segment on this build is recorded. | Complete one supported World 1-1 early segment, verify neutral handback and exercise Stop/Take control on this path. Diagnose the first actual blocker; no current gameplay failure cause is established by the pre-Start assertions. |
| Shutdown and reopening | Candidate.35 has descriptive-history reopening evidence. Reopening must restore no live session, review or input authority. | Active keyboard/Dock quit and the broader interruption matrix are not qualified on this build. They are follow-up checks for affected use, not a prerequisite to feedback on working tasks. |
| Other games/activities | Minecraft source flags enable calibration/camera only; aim/move/place/wall are disabled. OpenTTD is a narrow repayment reference. Authored Mario routes, prepared Stardew routines and source flight/coaching trials have separate retained evidence. | Full-level adaptive Mario, generalized coaching improvement, native reconnaissance/cave delegation, recording and broader games remain later work. |
| Owner feedback | The retained qualification record still has `owner_accepted: false`. | Let the owner try useful supported flows now. A formal two-game release decision is not required for personal-use feedback. |

## Evidence to resume from

The [candidate.35 qualification record](../dist/private-beta/0.3.0-candidate.35/qualification.json)
indexes the historical checks and uncompleted qualification work. Its pending
list is not the current work order; the October 7 personal-use scope superseded
the earlier mandatory release campaign.

- [Ordinary preparation](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-ordinary-ready.json).
- [Corrected watering, resources, return and handback](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-ordinary-watering-native-acceptance.json).
- [Active task Stop](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-active-watering-stop.json) and [old-review Start refusal](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-stopped-review-start-refusal.json).
- [Owned-provider failure](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-owned-provider-failure.json), [fresh-question recovery](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-provider-fresh-question-recovery.json), and [neutral switch](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-neutral-switch-to-mario.json).
- [Mario coached proposal](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-mario-walking-coaching-reviewable.json), which has no completed outcome, and [Finder reopening](../artifacts/gc-delivery/ordinary-session/20261006-recovery/candidate35-finder-reopening.json).

These are retained local files, absent from a fresh clone. The declarative
[`local-candidate.yaml`](../data/companion/local-candidate.yaml) still marks full
packaged qualification pending; it is not a live per-session result ledger and
does not negate the narrower successful Stardew record.

## Historical next action — October 25

Use candidate.35 to try one finite, coached Mario early-segment request in a
fresh disposable session. Success means alive and grounded at x≥700, independent
neutral acknowledgment and a game-owned review pause. Check Stop/Take control
and no automatic resumption. Retain the result or exact blocker, make only a
needed repair, and check that changed path. Build a successor only if updated
source must run in the app; preserve stable identity, saves and history.

[Desktop priorities](/Users/michaelfuscoletti/Desktop/mario_next_steps.md) ·
[Next session](private-beta-pm-handoff.md) · [Engineering plan](private-beta-engineering.md) ·
[October 25 audit](documentation-audit-20261025.md).
