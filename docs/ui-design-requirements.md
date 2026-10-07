# Game Companion UI design requirements

## Model-driven interaction requirements

Integrate provider availability/sign-in remedies and both game setup paths without pushing diagnostics into ordinary conversation. Show the understood objective, scope, current activity and observed result. Pending inference, clarification, paused discussion, changed approval and provider/game errors need distinct readable states.

Keep Stop/Take control visible and responsive while the model is thinking. Preserve typed drafts and reject stale updates after switching or revising the goal. A model rationale cannot be displayed as completed gameplay. Historical images/results stay marked historical. Check real model/game and packaged interaction with the actual supported game and exact packaged artifact, alongside existing visual/accessibility checks.

The [product scope](product-direction.md) defines the user workflow. Apply these requirements to setup, conversation, task review, direct controls and reopening; record candidate-specific visual evidence in [UI verification](ui-verification.md).

## Task first

Put the useful result and next action before setup inventories or technical detail. Use ordinary sentences instead of internal codes and repeated badges. Group related facts; keep the current blocker, freshness, uncertainty and consequences next to the action. Move full history and advanced setup into named disclosures while leaving common controls directly available. Compare the same states and viewports, including keyboard use, increased text size and error recovery. Compact spacing must not come from smaller text or cramped controls.

For initial-beta Mario, make watched play, current goal/attempt, coach messages, applied/next-attempt changes and immediate control understandable. For Stardew, show the next-few-minutes plan, explicit approval, observed progress and conversation/check-in recovery. Reopening coaching/history restores no input authority. Bounded versions exist in source; the contextual AI experience and exact-app usability qualification remain unverified outside the bounded source cases.

For Minecraft first use, show the current setup step, its concrete next action and available tasks. Build readiness must follow the actual task-family flags and fresh session state. Place prerequisites and practice-area guidance beside the controls that need them, and preserve typed drafts and editable protection intent during routine refresh.

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

## Maintaining the interface

Keep design guidance consistent with the implementation. Check affected screens and interactions at supported sizes; record any remaining limitations. Preserve data contracts, calculations, permissions, persistence and game rules.
