# Mario conversation and routes

This guide links the current Mario conversation behavior and the corrected beta target. The [product direction](product-direction.md) makes conversational gameplay the initial beta: Mario plays while the user watches and coaches; Stardew handles delegated clicking/actions after a short plan and approval. Minecraft grows into the third playable option during beta and informs advanced no-code game onboarding. The [private-beta engineering plan](private-beta-engineering.md) owns delivery order and acceptance; connecting or calibrating Minecraft alone does not satisfy the initial beta.

The consolidated [Mario player guide](mario-player-guide.md) owns current conversation requests, path/destination edits, normal/uncapped speed, opening-only resumption, saved variants and recovery. [Launch and first use](../README.md#launch-and-first-use) owns shared setup and history. This avoids maintaining a second, conflicting player procedure.

For contributors, [Mario integration](b2-integration-contract.md) maps planning, service, UI and Mario runtime interfaces. [Stardew integration](b3-integration-contract.md) maps the farm runtime; [future adapter guidance](new-game-onboarding.md#adding-an-actual-game-adapter) explains extension boundaries. Current Day 2 and Day 5 support is in the [Stardew guide](stardew-operator-guide.md).

## Mario beta target and current gap

GC1/GC2 must deliver goal → reviewed play → watch/coaching → revised attempt → remembered result. The owner's examples are “lets find a 100% coin route to the end,” “youre jumping too early wait a few more frames,” “fly to get the hidden 1up,” and “STOP RIGHT NOW WAIT.” Route discoveries and timing corrections must survive attempts/lives and reopening. Selected real-time commands need an explicit supported application boundary; urgent stop must bypass planning and immediately release input.

Today the deterministic planner operates the existing route with bounded opening-path, stop-point and playback-speed changes. Quickest/100% requests load that same route; this does not provide route discovery or coin training. Saved variants and separate learning evidence are foundations, not an integrated coached player. The exact urgent stop example also misses the current narrow chat control matcher; visible Stop/Take control remain the current remedy. These gaps are planned engineering work, not beta acceptance or abilities of a newer package.

The ordinary player should not need the Lab, a source patch or a developer to try a reviewed experimental correction. [Learning](learning.md) separates that planned local experimentation from promotion into the historical accepted-solution registry. Independent self-training comes later, after watched/coached play is useful and verified.
