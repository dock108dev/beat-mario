# B4 engineering handoff — September 25, 2026

B4.1–B4.4 are technically complete for the bounded Day5 configuration below. Ordinary real work, combined return/handback, live safeguards, cumulative checks and affected regressions are complete. Owner acceptance and full-beta readiness remain open.

The combined typed request, exact review and Start completed in attempt `stardew-do-b8178678367d3c50` on source `eddec8828933c64c77dbc336924ce336b5182b1651ec47f1bb2885bea127c972` (HEAD `c61de17668dce092b26990c18493c4bfb92eeb41`, 214-file uncommitted tree). See [combined proof](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b4-engineering/20260925-live/combined-substage-proof.json) and [fresh handback verification](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b4-engineering/20260925-live/attempt18-handback.json). Cumulative971 tests, lint, security, goal/segment and shared renders passed on that source. No commits or pushes.

| Substage | Ordinary observed result |
| --- | --- |
| B4.1 Harvest | Selected mature `farm--1-3` became empty; +1 ordinary parsnip; energy/water unchanged |
| B4.2 Plant | One owned parsnip seed used on that selected empty plot; seeds13→12; new immature crop observed and added to watering dependency |
| B4.3 Clear | Selected small stone `farm-0-5` removed with owned pickaxe; +1 stone; energy268→266; surrounding protected targets unchanged |
| B4.4 Combined | Harvest → plant → water new crop → clear → farmhouse return; all four steps confirmed; energy270→266, water32→31; fresh final screen, stationary player and released keys/buttons verified |

The shared planner, review, Start, task ledger, history, cancellation and handback paths perform these actions. Live facts come from actual screenshots, including current full toolbar, menu capacity/calendar, target area, player, resources and aim. The B3 watering allowlist is unchanged. Harvest, planting and clearing have separate eligibility and postcondition contracts. Partial or unknown outcomes never become full completion.

## Launch and supported setup

Double-click `Open Game Companion.command`, choose Stardew and open a fresh copy of `b4-day5-v1` (Pilot / B4Test, Day5). Close the prior isolated game first. In the game, Load the prepared farm, exit the farmhouse, select the watering can and remain at the porch. Use **Check isolated farm session**, then connect `b4-day5-screen-v13`. Type:

> Harvest farm--1-3, then plant parsnip seeds on farm--1-3, then water them and clear farm-0-5 and return to the farmhouse entrance.

Review the four selected actions, one owned seed, new-crop watering dependency, protected neighbors, zero purchases and farmhouse return; choose Apply then Start. Keep the game foreground and avoid manual input. Pause/Take control revoke authority; observe and review remaining work before another Start. A single-action conversational correction edits that action family in an existing plan; review the entire resulting plan, or explicitly remove unwanted steps.

Supported configuration: exact retained Day5 Standard Farm,1512×949 capture at OS(0,33),3024×1964 display,zoom75%,UI100%,locked toolbar,hit-location marker,default WASD,daylight. Only the selected left parsnip and small stone have qualified action approaches. Right parsnip and configured nearby weeds/rocks/grass are observed and protected. Inventory capacity12,seeds13/12,one ordinary parsnip and one stone gain are calibrated. Broader crops,quality/bonus yields,regrowing crops,other plots,twig/weed clearing,multi-hit objects,refilling,night or other settings are not live-qualified. Unsupported/uncertain views stop.

## Preservation and retained failures

B3 remains COMPLETE on its original candidate: attempt27 watered all15,energy270→240,water40→25,returned to the farmhouse and released control. Preserve its [qualification report](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b3-engineering/20260925-integrated/qualification-report.md) and original dry Day2 seed SHA `1a71568b81ebb901c5fc289d4c2bfb0972db8c05325463a7487dad549eae3128`. The separate frozen B4 Day5 seed SHA is `5bddd72e537c6888e3623c5cb66c819bf1add0b28bc75f179fb6b97f25e35eaa`. Working copies have separate identified namespaces. No save parsing, personal-save access or purchases were used.

The owner-touched attempt is `interrupted_by_owner_input`, not a confirmed control defect; controls were released and that copy closed unsaved. Later apparent movement was investigated from retained frames: a butterfly covered the boots; the player matched the same position before and after without gameplay input. Other failures retain their exact partial ledger and neutral handback: raster/hover/marker variants, temporary obstruction and freshness expiry. Repairs use retained screen evidence, bounded no-input retries and one complete pre-click reacquisition. Resource freshness remains2seconds,aim3seconds,actual menu capacity/calendar5seconds; no timestamps are rewritten. Manual fixture preparation/calibration is not ordinary action evidence.

Live Pause after harvesting, fresh reviewed planting/watering/clearing, Reclaim after planting, actual application focus loss and no automatic resume after focus restoration passed. Immature harvest Start and protected-debris requests were refused. Shared Mario/Stardew catalog switching and ordinary conversation/render checks passed; no unrelated historical Mario campaign was rerun. The B3 repeat watered all15, reconciled270→240/40→25, returned to the farmhouse and passed independent stationary/OS-neutral handback verification. Its first regression attempt watered all15 but stopped on the unchanged30-second occlusion-history guard during return; that failure remains retained. Slow or occluded runs can still stop truthfully and require fresh review or a fresh copy. Full inventory, shortages, unsupported seasons/tools and unobservable postconditions have focused contract tests; no real full-inventory fixture is claimed.

Final source identity, evidence hashes, exact attempt records and validation boundaries: [qualification report](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b4-engineering/20260925-live/qualification-report.md) and [candidate manifest](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b4-engineering/20260925-live/candidate-source.json). Only documentation changed after the successful combined source; runtime continuity is verified.
