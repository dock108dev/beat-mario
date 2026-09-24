# Product clarity verification

September 23, 2026 · Starter 02 presentation cleanup; synthetic engineering evidence only.

[Matched before/after review](../artifacts/ui-clarity-20260924/review.html) · [check details](../artifacts/ui-clarity-20260924/report.html). These ignored local artifacts accompany this working tree; they are not a runtime dependency or portable release package.

- At 390px, Select Mario moved from y=1,103 to y=363; both game-selection actions now fit in the first 844px. Mario's reviewed-plan Send moved from y=953 to y=660, and Start from y=1,692 to y=1,298. At 1440px, the same page's default height moved from 6,438 to 1,886px. No selection, request or execution-authorization steps were added; secondary setup/history details use disclosures. These are measured placements, not a usability or acceptance percentage.
- Matched catalog, selected game, Mario empty/reviewed/pending and Stardew unavailable states at 1440×900 and 390×844. Mario interaction checks also use 820×900. Shipped JavaScript runs against synthetic loopback responses, with no game driver or owner save.
- Checked keyboard focus/disclosures, editing through refresh, open/closed detail retention, long conversation history, failed updates and recovery, unknown versus zero, pending versus applied speed, and persistent Stop/Take control. Doubled text sizes and expanded secondary details have no measured page/control overflow. Primary controls remain at least 44px. No page exceptions occurred in passing browser checks.
- Canonical non-live validation: **842 passed**, plus syntax/lint, file guards, goal/segment/status contracts and player/Lab/Stardew rendering. **107 final focused tests passed**, covering the last presentation refinements and workspace polling; logs are linked above. Earlier failed attempts are retained, including setup wording restored for the render contracts.
- No live games, owner save access, owner review, commit, push, publication, release or installed/frozen build replacement. Native input response, physical-device/browser coverage, screen-reader behavior and exhaustive contrast pairs are not established by these synthetic checks. The prior B2 evidence remains bound to its preserved source archive.

Separate suggestion: **Stardew live foundation (confirmed)** — the public workspace cannot select a disposable save or connect observation/input, so a farm routine cannot start. This is B3 functionality, outside copy/layout work. Begin that tracked slice with disposable-copy setup and synthetic-save checks, then separately qualify live watering. No additional feature backlog was created.

## Historical Starter 01 adoption

September 21, 2026 · source implementation and engineering review only.

41 lab-UI tests and 44 Stardew-adapter/catalog tests passed. Rendered catalog, Mario, Stardew, lab, and onboarding pages were checked at 1440px and 390px. Screens are render-only previews; game observation, takeover, emulators, and save-copy operations were not started. The lab preview displays existing historical local metadata; it is not new runtime evidence.

## Retained review

Screenshots and browser check results are retained in `review.html` in the optional shared `UI Templates` folder described in [UI design](ui-design.md). That gallery is outside this repository and is not available in a standalone checkout. Browser specimens are local fixtures or isolated startup states. Web review checked representative 1440px/390px layouts, page exceptions, and page-level horizontal overflow; it is not an exhaustive audit of every state, contrast pair, screen reader, browser, installed build, or physical phone.

Template gallery search, form submit feedback, dialog opening, and Escape dismissal were exercised. Shared styles include keyboard focus, reduced-motion, and reduced-transparency handling. Native Godot is a basic translucent fallback, not a true blur material. Native games retain their desktop layout and illustrated artwork.

See [design and future template use](ui-design.md). No owner acceptance or release qualification is inferred. Rebuild/relaunch the appropriate source application to see the change; installed or frozen copies remain their original versions.
