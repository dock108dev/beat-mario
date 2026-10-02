# Minecraft private beta: user onboarding course correction

Reviewed October 1, 2026 against `fc019d50ff91abdee08d82514e885328fa5ca090` and its retained private.1/private.2 reports. This is a source, documentation and local regression review. Minecraft building remains unfinished.

For the current delivery status and October 2 pickup, start with the [PM handoff](private-beta-pm-handoff.md). This report retains the specific audit findings and repair evidence.

## The product we are delivering

A technically comfortable nonprogrammer opens the Mac app, creates a Minecraft profile, follows permission/settings guidance, selects the current game window, calibrates/connects, prepares and visibly checks a disposable Creative building region, asks for a useful task, reviews/starts it, receives an observed result and control, then reopens the saved profile/history.

The initial useful task is the 7-wide × 3-high × 1-thick wall with its centered 1 × 2 doorway: 19 occupied cells and two empty doorway cells. User setup supplies intent and configuration; fresh game observations supply material, pose, reach, clearance and results. Preparation can involve ordinary manual game actions, explained and checked through the app. Developer scripts or supplied world coordinates cannot stand in for that first-use flow.

This is the current [engineering contract](private-beta-engineering.md#guided-setup-and-how-to--pb5) and [tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md). Broader onboarding variation, setup-time measurement and sustained reliability continue during private beta.

## What the recent work delivered, and where it diverged

The audited release work is concentrated in `fc019d5`: 90 files, 13,991 inserted lines and 455 removed lines. That commit landed during this audit, at October 1, 11:11:32 p.m. Eastern. The preceding planning commit, `719009c`, is September 30 at 9:27 p.m. Eastern and falls outside the exact rolling 24-hour window. The actual work history comes from the retained reports as well as Git; there is no sequence of smaller commits attributing each native trial.

The reusable host, profile storage, calibration, conversation, Minecraft perception/skill providers, app packaging and feedback foundation are substantial implemented work. They should be reused.

The delivered private.2 app still enables only calibration and camera tasks. `MinecraftPlayerSession.CHECKED_FEATURES` disables aiming, movement, placement and wall execution. Its [owner review](private-beta-review.md) explicitly records no packaged wall success. Thus a saved Minecraft profile or successful camera check did not deliver the useful first building task.

Work also concentrated on camera trials and engineering-prepared probes. A retained 180-second movement inspection used 31 aim children, 93 camera pulses and 267 capture records before any movement. The current source already includes subsequent nearest-interior viewpoints and larger single-axis child goals; those changes have offline coverage but still need a short useful-path check. The correct next step is to measure and repair the ordinary setup/task bottleneck, using these existing improvements.

Several current entry documents still sent engineers back to PB1 feasibility and described player setup as planned, while the setup implementation already existed. That stale guidance competed with the tracker's current integration task. The corrected entry documents now identify the same user-facing next action.

## Corrections applied

- Current README, documentation index, product direction, onboarding guide, personal plan, engineering handoff and tracker point to user Minecraft onboarding → useful task → handback → reopening. The player setup link targets the current PB5 section.
- Setup now shows progress derived from actual profile/session state, available tasks and the next action. Saving or importing configuration cannot turn into a current connection or an executable building task. Disabled wall support is visible as a build limitation.
- Stop, Take control and safe chat dispatch independently of editable protected-cell/window fields. Malformed JSON in advanced setup cannot prevent direct controls.
- Pointed protection survives later scope checks. Explicit advanced edits survive polling and inspection; coordinate authoring is optional and collapsed.
- Start, calibration and native scope/protection checks immediately disable/blur drafting. A successful safe-chat response re-enables it; older responses cannot override newer controls.
- Outer aiming completion includes the observation's angle uncertainty, matching the skill provider's precision rule.
- Reusing a recent placement inspection requires a current compatible pose, window/settings identity and unchanged position. Changed or missing evidence triggers a fresh inspection before input.
- Child and parent task deadlines are checked again after observations, including the final wall position capture. A slow capture can no longer turn an expired task into a completed result; partial outcomes retain consumed work and confirmed input release.

Existing task feature flags and runtime limits remain truthful. Prior packages, game worlds and player profiles were not rewritten by these corrections. No native gameplay was performed during this audit.

## Verification and practical limits

**The canonical local gate passed: 1,327 tests**, Ruff, whitespace/syntax, tracked credential/game-asset checks, goal/segment contracts and Game Companion/Lab/Stardew renders. The retained log is `artifacts/private-beta/course-correction-20261001/canonical.log`.

An earlier affected run passed 218 tests, including shipped-JavaScript execution, fresh profile/configuration reopening, priority controls and late-response races, protection persistence, Minecraft composition, scene/camera contracts and documentation links. The final canonical run also includes the subsequent deadline regressions: expired captures, parent budgets, partial outcomes, consumed input, confirmed release and unchanged step accounting.

The corrected setup page was visually inspected in an isolated, synthetic, read-only browser preview at desktop size and 390 × 844. First-use guidance and direct controls are readable; narrow page width and scroll width were both 390 pixels. This does not establish game capture, calibration or live wall completion.

Final canonical check command:

```sh
PYTHON=.venv/bin/python scripts/validate_phase0.sh
```

## One concrete continuation

Complete the ordinary user Minecraft first-use path on a new local profile and user-selected disposable world. Explain and check the practice-area start through the app, repair actual inspection/aim/movement/addition bottlenecks, finish the wall path, and package a separately identified candidate with accurate feature availability. Then perform a brief packaged setup → calibration → work-region check → wall request/Review/Start → observed result/handback → Stop → profile/history reopening smoke, recording engineering assistance and any partial result.

The source corrections are ready for that integration work. A user completing a useful building task through the delivered app is the remaining release result.
