# UI verification

## Interaction checks

Check provider readiness, clarification, pending decisions, observed progress,
replanning, errors, immediate control, switching and historical reopening.
Inspect supported screen sizes, keyboard focus, draft preservation and long
conversation. Fixture/browser checks, native gameplay and packaged interaction
are separate evidence classes. The records below retain exact source identities.

## October 5 current-source presentation cleanup

Synthetic render/browser evidence is retained locally in `artifacts/ui-clarity-20261005/review.html`, with before/after source snapshots, identical fixtures, screenshots and measurements. These before images were captured at the start of this pass; older September images below remain historical. No owner data, game process, model call, installed build or frozen package was used.

Matched catalog, Mario empty/ready/pending, and Stardew empty/ready/stale-update/partial-result states were checked at 1440×900 and 390×844. The desktop Stardew Start action moved from y=1,148 to y=608; narrow Start moved from y=2,111 to y=1,343 and still requires scrolling. Catalog selection moved from y=1,013 to y=691 on narrow screens. Mario's narrow page height fell from 4,905 to 2,636px by disclosing optional tools. These are placements for these fixtures, not usability percentages.

Focused validation passed 76 existing tests (two HTTP tests excluded to avoid real provider/storage initialization), Ruff, Python/JavaScript syntax and whitespace checks. Browser checks covered no page overflow/exceptions, doubled text sizes, visible keyboard focus, disclosure interaction, preserved drafts, independently reachable Stop, stale-update feedback, relevant guidance/manual closure, retained earlier messages, current advice, confirmed-zero accounting and completed-versus-partial results. A first enlarged-text screenshot attempt failed because the preview harness scaled inherited font sizes repeatedly; the corrected harness captures computed sizes before scaling and passed. Screen-reader behavior, physical-browser coverage, native gameplay response, exact-app qualification and owner acceptance remain unverified.

Outside this presentation pass: the Day 5 request still needs opaque plot IDs; add verified user-facing target references without changing identity/approval rules. The tracked Stardew renderer/window mismatch also blocks native watering-can recognition; repair it on an isolated farm before the pending native acceptance.

## Historical September 26 ordinary-workspace cleanup

Source on local main as reviewed September 26; synthetic presentation evidence only. The retained B8/B9 candidate remains distinct from that modified checkout.

- Matched screenshots and measurements are retained locally at `artifacts/ui-clarity-20260926/review.html` (repository-relative path; ignored evidence, unavailable in a standalone checkout): Stardew’s ready-state request field moved from y=2,341 to y=538 at 390×844, and from y=1,917 to y=458 at 1440×900. Desktop Start moved from y=1,137 to y=629. Narrow Start remains below the first viewport at y=1,412; there is no claim that the whole workflow fits on one screen.
- Requests and plan review precede farm setup and history. The first-use setup disclosure starts open; its link, current blockers, fresh-view action, exact plan targets, resource/return limits and sticky Stop remain available. Mario retains its layout with shorter wording. Shared Starter 02 styling replaces the ordinary farm renderer’s leftover green styling.
- Matched empty/ready Stardew and Mario plan screens at both widths, plus doubled computed text sizes at 390px: no page-level horizontal overflow. Keyboard focus, history disclosure, draft preservation through polling, disabled empty-state actions and reachable Stop were checked. Failed-refresh feedback warns of stale display data and clears on recovery; action errors are preserved by a focused regression.
- 63 focused tests passed, along with Ruff, Python compilation, JavaScript syntax and whitespace checks. No production service/game, owner save, live gameplay, release or acceptance was exercised. Native behavior, screen readers and exhaustive contrast pairs remain unverified. Preview assets are local ignored evidence; the report remains readable without its temporary server.

Recorded follow-up: the Day 5 request example needed opaque plot IDs at this snapshot. Human-readable labels would require a verified target mapping while retaining stored IDs. The displayed labels must retain their stored target IDs.

## Historical September 23 cleanup

September 23, 2026 · Starter 02 presentation cleanup; synthetic engineering evidence only.

- At 390px, Select Mario moved from y=1,103 to y=363; both game-selection actions now fit in the first 844px. Mario's reviewed-plan Send moved from y=953 to y=660, and Start from y=1,692 to y=1,298. At 1440px, the same page's default height moved from 6,438 to 1,886px. No selection, request or execution-authorization steps were added; secondary setup/history details use disclosures. These are measured placements, not a usability or acceptance percentage.
- Matched catalog, selected game, Mario empty/reviewed/pending and Stardew unavailable states at 1440×900 and 390×844. Mario interaction checks also use 820×900. Shipped JavaScript runs against synthetic loopback responses, with no game driver or owner save.
- Checked keyboard focus/disclosures, editing through refresh, open/closed detail retention, long conversation history, failed updates and recovery, unknown versus zero, pending versus applied speed, and persistent Stop/Take control. Doubled text sizes and expanded secondary details have no measured page/control overflow. Primary controls remain at least 44px. No page exceptions occurred in passing browser checks.
- Canonical non-live validation: **842 passed**, plus syntax/lint, file guards, goal/segment/status contracts and player/Lab/Stardew rendering. **107 final focused tests passed**, covering the last presentation refinements and workspace polling. Earlier failed attempts are retained, including setup wording restored for the render contracts.
- No live games, owner save access, owner review, commit, push, publication, release or installed/frozen build replacement. Native input response, physical-device/browser coverage, screen-reader behavior and exhaustive contrast pairs are not established by these synthetic checks. The prior B2 evidence remains bound to its preserved source archive.

Historical suggestion, superseded by B3–B8: **Stardew live foundation (then confirmed)** — the public workspace cannot select a disposable save or connect observation/input, so a farm routine cannot start. This is B3 functionality, outside copy/layout work. Begin that tracked slice with disposable-copy setup and synthetic-save checks, then separately qualify live watering. No additional feature backlog was created.

## Historical Starter 01 adoption

September 21, 2026 · source implementation and engineering review only.

41 lab-UI tests and 44 Stardew-adapter/catalog tests passed. Rendered catalog, Mario, Stardew, lab, and onboarding pages were checked at 1440px and 390px. Screens are render-only previews; game observation, takeover, emulators, and save-copy operations were not started. The lab preview displays existing historical local metadata; it is not new runtime evidence.

## Retained review

The retained browser specimens use fixtures or isolated startup states.
Representative 1440px/390px layouts were checked for page exceptions and
horizontal overflow. Those checks do not establish every interaction, contrast
pair, screen reader, browser, installed build or physical phone. See
[UI design](ui-design.md) for current repository guidance.
