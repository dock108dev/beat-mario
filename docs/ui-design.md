# Interface design

Use the shared cool/light glass tokens in `src/smb3_agent/glass_ui.py`. Keep product language concrete,
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

## Project controls

The Minecraft workspace keeps camera/reconnect controls directly below the scene.
Conversation precedes project review in the document order and narrow layout;
landscape and building controls form two numbered stages with aligned field labels.
New-world settings open on first use, while checking setup remains secondary.
Planning syntax appears beside the composer only in Plan mode. Empty terrain maps
are hidden; optional geometry, measurements and building inventories remain available
in named disclosures. Blockers and recovery messages stay visible.

Polling preserves open building details and unsaved place edits when unrelated
reference/version metadata changes. Command names, captured review identities,
world creation consent, Stop, and backend approval rules are unchanged.

## Direction

Use a light iOS Liquid Glass-inspired appearance: cool white surfaces, restrained translucency, subtle blue/lavender ambient background, soft depth, rounded controls, and native system typography. Do not recreate the former beige, forest-green, yellow-tinted dashboard theme.

## Foundations

- Use `src/smb3_agent/glass_ui.py` for tokens and components. Default action accent is blue (#0969df); primary text is deep slate (#182338), secondary text #54647b.
- Use the platform system font stack. Favor natural sentence case; reserve small uppercase labels for occasional context. Avoid oversized headings and widely spaced labels throughout the interface.
- Use an 8-ish pixel spacing rhythm (8, 12, 16, 20, 24, 32). Keep related controls close and groups visibly distinct.
- Panels generally use 22–26px radii; controls 12–14px; status pills fully rounded. Avoid applying pills to every piece of information.
- Glass is a surface treatment, not decoration to stack endlessly. Use subtle borders, a white top highlight, restrained shadows, and approximately 24px backdrop blur. Keep text and dense data on sufficiently opaque surfaces.
- Blue communicates action/selection. Green is reserved for meaningful success/positive values; amber for caution; red for error/destructive states. Pair color with text or icons. Preserve negative, zero, unknown, stale, and unavailable states accurately.

## Layout and common patterns

Use dashboard summaries for overview, list/table layouts for comparison, grouped forms for editing, sidebar settings for preferences, and detail views for records. Put secondary diagnostics in disclosures; retain necessary provenance and limits. Give each view a clear title and primary next action. Import/setup/debug controls should not displace the main product heading.

Use compact tables on desktop, deliberate horizontal scrolling or readable record cards on phones. Long names, timestamps, and values must wrap or remain accessible. Avoid clipped selects, overlapping controls, and page-level horizontal scrolling. Keep useful data near the first viewport; do not sacrifice usability for giant empty hero sections.

## Interaction and accessibility

- Use native buttons, links, labels, inputs, and dialog semantics. Provide visible keyboard focus and accessible names. Aim for at least 44px primary touch targets.
- Body text should meet 4.5:1 contrast; large text and meaningful component boundaries should meet applicable 3:1 contrast requirements. Check actual composited colors because transparency changes contrast.
- Honor reduced motion and reduced transparency; provide opaque fallback surfaces when blur is unsupported. Do not animate large backgrounds or use glass effects that impair reading.
- Distinguish loading, empty, error, disabled, selected, and successful states in words. Do not make a control look active when unavailable.
- A light theme is included. Do not claim dark-mode support without implementing and checking it.
- Demo interactions are local-only. Real apps must retain their existing behavior, confirmation rules, persistence, math, data boundaries, and source labels.
