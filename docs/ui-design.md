# Game Companion UI design

## Active model-driven interaction

The UI target follows GC-A1–GC-U in the [engineering plan](private-beta-engineering.md): provider readiness/remedies, understood goal and clarification, readable approval, current action, observed progress, pending inference and meaningful replanning. Keep direct control available in every active/pending/error state and preserve drafts during asynchronous work.

Show whether an adjustment applies now or later and whether its effect is observed. Distinguish historical findings from current observations and usable goals from missing capabilities. Use the existing design system and simple product language. The working bounded flows below are current implementation; new Codex-driven behavior remains planned until verified.

Use the [design requirements](ui-design-requirements.md) and `src/smb3_agent/glass_ui.py` when changing the interface.
The [private-beta engineering plan](private-beta-engineering.md) owns the user workflow to deliver; the [PM handoff](private-beta-pm-handoff.md) records current build limitations and next work.

## Planned conversational gameplay interaction

The initial-beta interaction requires a current goal/attempt and conversation beside watched Mario play, readable current-versus-next-attempt coaching acknowledgment, inspectable route/life memory and persistent direct Stop/Take control. Stardew should present a short near-term activity plan, contextual approval, progress/check-ins and a safe pause/discuss/replan path. Make current abilities and setup remedies clear at the relevant action. Parts of these interactions exist in current bounded workflows; the model-driven integration is upcoming work; preserve the accepted visual system and change layout only where the new interaction needs it.

## Current layout and behavior

The catalog puts game selection before capability details. Mario places plan review beside conversation and keeps Stop/Take control visible above the workspace. Saved routes, earlier messages and advanced tools use named disclosures.

Keep setup blockers, pending changes, requested/applied speed and completion uncertainty visible. Legacy controls open when a live observation or Show session exists. Stardew keeps its current setup blocker and Refresh farm view above requests and review. Farm setup is a named disclosure (open initially without an observation); a direct link reaches it. Saved results are separate from the current result. Targets remain editable and full plan limits stay beside Start. Polling errors warn that the view may be outdated and clear only on successful recovery; action errors remain visible. Both ordinary workspaces use the shared glass styles in `glass_ui.py`.

CSS is embedded by the page renderers to preserve the content-security policy and package portability. Related renderers include `lab_ui.py`, `conversation_ui.py` and `stardew_adapter.py` in `src/smb3_agent/`. Stop/reclaim uses red emphasis. Styling must preserve execution authorization, game drivers and persistence.

`player_setup_ui.py` renders `/setup`, `/minecraft` and `/help` with its own embedded styles. Minecraft setup progress appears before the setup forms and comes from `player_onboarding.py`: save profile, connect/calibrate, check the building region, then review/run the available task. Available and unfinished task families are named separately, using current runtime flags. Direct Stop, Take control and Quit remain above the workflow. Setup and camera connection alone leave building marked unavailable while its feature flag is disabled.

## Visual checks

Check the affected screens at supported sizes, including keyboard focus, long content, disabled actions and error recovery. Existing review records are in [UI verification](ui-verification.md).
