# Mario conversation and routes


Current source adds the complete experimental opening-jump practice/coaching loop. See the [Mario player guide](mario-player-guide.md#practice-and-coach-the-opening-jump) for review, finite retries, remembered guidance, reset and priority Stop, and [verification](gc1-gc2-coaching-verification.md) for source evidence. The retained B2 path/route contracts below keep their historical scope.

This guide links the current Mario conversation behavior and the corrected beta target. The [product direction](product-direction.md) makes conversational gameplay the initial beta: Mario plays while the user watches and coaches; Stardew handles delegated clicking/actions after a short plan and approval. Minecraft grows into the third playable option during beta and informs advanced no-code game onboarding. The [private-beta engineering plan](private-beta-engineering.md) owns delivery order and acceptance; connecting or calibrating Minecraft alone does not satisfy the initial beta.

The consolidated [Mario player guide](mario-player-guide.md) owns current conversation requests, path/destination edits, normal/uncapped speed, opening-only resumption, saved variants and recovery. [Launch and first use](../README.md#launch-and-first-use) owns shared setup and history. This avoids maintaining a second, conflicting player procedure.

For contributors, [Mario integration](b2-integration-contract.md) maps planning, service, UI and Mario runtime interfaces. [Stardew integration](b3-integration-contract.md) maps the farm runtime; [future adapter guidance](new-game-onboarding.md#adding-an-actual-game-adapter) explains extension boundaries. Current Day 2 and Day 5 support is in the [Stardew guide](stardew-operator-guide.md).

## Mario beta target and current gap

GC1/GC2 must deliver goal → reviewed play → watch/coaching → revised attempt → remembered result. The owner's examples are “lets find a 100% coin route to the end,” “youre jumping too early wait a few more frames,” “fly to get the hidden 1up,” and “STOP RIGHT NOW WAIT.” Route discoveries and timing corrections must survive attempts/lives and reopening. Selected real-time commands need an explicit supported application boundary; urgent stop must bypass planning and immediately release input.

Current source handles opening coaching, surface coin-route discovery and priority urgent Stop. Ask “find a coin route to the end” through `/mario`, approve the displayed finite scope, watch the changing route, inspect observed/unknown reporting and explicitly retry after handback. Generic quickest/100% selectors retain their historical fallback; the conversational coin goal now selects an experimental exploration plan. No complete coin set or 100% route is verified. See [Mario player guide](mario-player-guide.md) for accounting and retry semantics.

The ordinary player should not need the Lab, a source patch or a developer to try a reviewed experimental correction. [Learning](learning.md) separates that planned local experimentation from promotion into the historical accepted-solution registry. Independent self-training comes later, after watched/coached play is useful and verified.
