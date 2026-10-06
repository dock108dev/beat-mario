# Game Companion UI design

## Active model-driven interaction

The model-backed workspace presents provider readiness/remedies, understood goal and clarification, readable approval, current action, observed progress, pending inference and meaningful replanning. Keep direct control available in every active/pending/error state and preserve drafts during asynchronous work.

Show whether an adjustment applies now or later and whether its effect is observed. Distinguish historical findings from current observations and usable goals from missing capabilities. Use the existing design system and simple product language. The bounded source flows include Codex-backed language and gameplay. Wider coverage and packaged usability still need their own verification.

Use the [design requirements](ui-design-requirements.md) and `src/smb3_agent/glass_ui.py` when changing the interface.
See [known limitations](known-limitations.md) for unsupported workflows.

## Conversational gameplay interaction

The initial-beta interaction requires a current goal/attempt and conversation beside watched Mario play, readable current-versus-next-attempt coaching acknowledgment, inspectable route/life memory and persistent direct Stop/Take control. Stardew should present a short near-term activity plan, contextual approval, progress/check-ins and a safe pause/discuss/replan path. Make current abilities and setup remedies clear at the relevant action. These interactions exist in bounded source workflows; wider model-driven coverage remains open; preserve the accepted visual system and change layout only where the new interaction needs it.

## Current layout and behavior

The catalog puts game selection before capability details. Mario places plan review beside conversation and keeps Stop/Take control visible above the workspace. Saved routes, earlier messages and advanced tools use named disclosures.

Keep setup blockers, pending changes, requested/applied speed and completion uncertainty visible. Legacy controls open when a live observation or Show session exists. Stardew keeps its current setup blocker and Refresh farm view above requests and review. Farm setup is a named disclosure (open initially without an observation); a direct link reaches it. Saved results are separate from the current result. Targets remain editable and full plan limits stay beside Start. Polling errors warn that the view may be outdated and clear only on successful recovery; action errors remain visible. Both ordinary workspaces use the shared glass styles in `glass_ui.py`.

CSS is embedded by the page renderers to preserve the content-security policy and package portability. Related renderers include `lab_ui.py`, `conversation_ui.py` and `stardew_adapter.py` in `src/smb3_agent/`. Stop/reclaim uses red emphasis. Styling must preserve execution authorization, game drivers and persistence.

`player_setup_ui.py` renders `/setup`, `/minecraft` and `/help` with its own embedded styles. Minecraft setup progress appears before the setup forms and comes from `player_onboarding.py`: save profile, connect/calibrate, check the building region, then review/run the available task. Available and unfinished task families are named separately, using current runtime flags. Direct Stop, Take control and Quit remain above the workflow. Setup and camera connection alone leave building marked unavailable while its feature flag is disabled.

## Visual checks

Check the affected screens at supported sizes, including keyboard focus, long content, disabled actions and error recovery. Existing review records are in [UI verification](ui-verification.md).

## Workspace layout

The catalog keeps sign-in and permission status, setup links and the inference transfer notice visible; full requirements/privacy use a named disclosure. Mario starts with conversation and plan review. Route shortcuts, recording, flight preparation, coin discoveries and guidance use named disclosures; newly relevant active guidance opens once and the player can close it without polling reopening it. Stop/Take control remain outside disclosures.

Stardew shows the current plan, observed resources and limits before optional activity teaching. Planting, inspection and cave findings appear when present, with historical/uncertain meanings retained. Advice without an executable plan is not preceded by empty review controls. The latest two messages stay visible and all earlier messages remain accessible. Current blockers, review/Start consequences, errors, partial results and resource/return accounting remain visible. Synthetic desktop/narrow comparison and accessibility checks are recorded in [UI verification](ui-verification.md); native gameplay and exact-package acceptance remain separate.
