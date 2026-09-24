# Game Companion UI design

Use the [design requirements](ui-design-requirements.md) and `src/smb3_agent/glass_ui.py` when changing the interface.

## Layout and behavior

The catalog puts game selection before capability details. Mario places plan review beside conversation and keeps Stop/Take control visible above the workspace. Saved routes, earlier messages and advanced tools use named disclosures.

Keep setup blockers, pending changes, requested/applied speed and completion uncertainty visible. Legacy controls open when a live observation or Show session exists. Stardew must explain missing setup or perception requirements before unavailable actions.

CSS is embedded by the page renderers to preserve the content-security policy and package portability. Related renderers include `lab_ui.py`, `conversation_ui.py` and `stardew_adapter.py` in `src/smb3_agent/`. Stop/reclaim uses red emphasis. Styling must preserve execution authorization, game drivers and persistence.

## Visual checks

Check the affected screens at supported sizes, including keyboard focus, long content, disabled actions and error recovery. Existing review records are in [UI verification](ui-verification.md).
