# Interface design

Use the shared cool/light glass tokens in `src/smb3_agent/glass_ui.py`. Keep product language concrete,
errors actionable and implementation diagnostics behind named disclosures.

## Minecraft workspace

The play screen is a viewport-filling world with a compact, opaque conversation
column. The composer stays visible while conversation scrolls independently. At
narrow widths the world and conversation stack within the viewport. Hide chat and
Full screen are reversible viewing controls; neither changes execution authority.

Only connection, active work, errors, Stop and camera controls appear around play.
Idle project bookkeeping, model metadata and privacy explanations do not occupy
chat space. Settings owns AI connection information, world selection, reconnect,
save/quit, recovery and engineering disclosures. Project opens a modal review with
landscape/building actions; no review or start happens merely by opening it.

Stop remains visible in both the main view and project review. Modal failures are
shown inside the open panel as well as in chat. Escape/Done returns to play, with
native dialog focus handling. Memory recovery opens Settings once when needed.

Chat renders paragraphs, bold spans and bullet lists using text nodes only, never
untrusted HTML. Enter sends and Shift+Enter adds a line; IME composition does not
send. Drafts survive rejection. The initial view scrolls to the latest message;
subsequent polling preserves a reader's position. Planning mode remains an explicit
checkbox because the current backend distinguishes discussion from design changes.

`minecraft_chat_ui.py` owns markup and page styles; `minecraft_chat_script.py` owns
behavior. CSRF/CSP, captured review identities, explicit Start, retained state and
world execution remain unchanged by presentation controls.

## Desktop launch

The browser is the play window. The native process keeps its Dock/menu Quit and
reopen actions, but creates no status/launcher window. Browser Save and quit uses
the same cleanup path. Closing a browser tab alone does not quit the world.

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

Project review is separate from the play surface. Geometry, requirements, material
selection and editing stay available there. Technical inventories and measurements
use closed disclosures. The main chat shows a short notice when planning needs
attention. Planning syntax appears only when Plan a build is selected.

Polling preserves open building details and unsaved place edits. Command names,
review identity checks, world creation consent and backend approval rules remain.

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
