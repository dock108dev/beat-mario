# Product clarity verification

## September 26 ordinary-workspace cleanup

Current source on local main; synthetic presentation evidence only. The retained B8/B9 candidate is unchanged as evidence and is not this modified checkout.

- Matched screenshots and measurements are retained locally at `artifacts/ui-clarity-20260926/review.html` (repository-relative path; ignored evidence, unavailable in a standalone checkout): Stardew’s ready-state request field moved from y=2,341 to y=538 at 390×844, and from y=1,917 to y=458 at 1440×900. Desktop Start moved from y=1,137 to y=629. Narrow Start remains below the first viewport at y=1,412; there is no claim that the whole workflow fits on one screen.
- Requests and plan review precede farm setup and history. The first-use setup disclosure starts open; its link, current blockers, fresh-view action, exact plan targets, resource/return limits and sticky Stop remain available. Mario retains its layout with shorter wording. Shared Starter 02 styling replaces the ordinary farm renderer’s leftover green styling.
- Matched empty/ready Stardew and Mario plan screens at both widths, plus doubled computed text sizes at 390px: no page-level horizontal overflow. Keyboard focus, history disclosure, draft preservation through polling, disabled empty-state actions and reachable Stop were checked. Failed-refresh feedback warns of stale display data and clears on recovery; action errors are preserved by a focused regression.
- 63 focused tests passed, along with Ruff, Python compilation, JavaScript syntax and whitespace checks. No production service/game, owner save, live gameplay, release or acceptance was exercised. Native behavior, screen readers and exhaustive contrast pairs remain unverified. Preview assets are local ignored evidence; the report remains readable without its temporary server.

Separate suggestion (confirmed): the Day 5 request example still needs opaque plot IDs. Adding human-readable labels requires a verified target mapping beyond presentation. Prototype labels only for the qualified Day 5 targets, retaining stored IDs.

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

Screenshots and browser check results are retained in `review.html` in the optional shared `UI Templates` folder described in [UI design](ui-design.md). That gallery is outside this repository and is not available in a standalone checkout. Browser specimens are local fixtures or isolated startup states. Web review checked representative 1440px/390px layouts, page exceptions, and page-level horizontal overflow; it is not an exhaustive audit of every state, contrast pair, screen reader, browser, installed build, or physical phone.

Template gallery search, form submit feedback, dialog opening, and Escape dismissal were exercised. Shared styles include keyboard focus, reduced-motion, and reduced-transparency handling. Native Godot is a basic translucent fallback, not a true blur material. Native games retain their desktop layout and illustrated artwork.

See [design and future template use](ui-design.md). No owner acceptance or release qualification is inferred. Rebuild/relaunch the appropriate source application to see the change; installed or frozen copies remain their original versions.
