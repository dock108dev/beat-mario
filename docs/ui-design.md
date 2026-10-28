# Interface design

Use the shared cool/light glass tokens in `src/smb3_agent/glass_ui.py` and the
[design requirements](ui-design-requirements.md). Keep product language concrete,
errors actionable and implementation diagnostics behind named disclosures.

## Minecraft workspace

World setup appears before an empty scene. Once connected, the live view and
conversation occupy the main columns. Progress and viewer controls stay nearby.
Closing the view hides its frame without stopping gameplay; explain that distinction.

Stop remains visible during inference and work. Send shows why it is unavailable.
Drafts survive rejected requests and asynchronous updates. Only describe ongoing
gameplay when a task is actually active. Keep local command errors and server errors
visible together. Recovery details open once when memory needs attention; polling
must not repeatedly reopen details the user closed.

`minecraft_chat_ui.py` owns markup and page styles. `minecraft_chat_script.py` owns
the independently served script. Credentials come from the escaped document dataset,
not interpolated script text. Incremental message updates preserve edits and scroll
position. Keep the practice-world limits accessible in a named disclosure.

## Older workspaces

Mario presents conversation and plan review with Stop/Take control always visible.
Requested versus applied speed and observed versus predicted outcomes are distinct.
Stardew presents its setup blocker, observation, targets, review/Start consequences
and resource/return accounting. Saved findings are separate from current results.
Unsupported actions must not appear ready merely because setup succeeded.

Check changed screens at desktop and narrow sizes with keyboard navigation, long
messages, loading, empty, disabled and error states. Styling changes must preserve
CSRF/CSP, action authority, data persistence and game-driver behavior.
