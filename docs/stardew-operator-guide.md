# Stardew companion guide

Use [launch and first use](../README.md#launch-and-first-use), then choose Stardew Valley. Support is restricted to two locally prepared Standard Farm configurations. Live setup requires prepared seeds, profile registrations and their matching calibration files. These are ignored local assets and are not bundled by cloning the source or running the launcher. Without them, the CLI can inspect declared capabilities but the browser cannot start qualified farm work.

## Choose the matching farm and profile

| Configuration | Prepared source | Matching profile | Qualified work |
| --- | --- | --- | --- |
| Pilot / B3Test Farm · Day 2 | `pilot-day2`; 15 dry starter crops | `pilot-day2-75pct-v1` | Water all 15 initially planted crops, reconcile resources, return to farmhouse entrance |
| Pilot / B4Test Farm · Day 5 | `b4-day5-v1`; two mature parsnips and 13 owned seeds | `b4-day5-screen-v13` | Selected ordinary parsnip harvest, plant owned parsnip seed, water the new crop, clear the selected small stone, reviewed farmhouse return |

Day 2 seed hash: `1a71568b81ebb901c5fc289d4c2bfb0972db8c05325463a7487dad549eae3128`. Day 5 seed hash: `5bddd72e537c6888e3623c5cb66c819bf1add0b28bc75f179fb6b97f25e35eaa`. The local registry is `artifacts/stardew-prepared-farms.json`; profile pointers are `artifacts/stardew-qualified-profile.json` and `artifacts/stardew-qualified-farm-profiles.json`. They reference retained calibration, loading and persistence evidence. Missing or mismatched files block setup; selecting another profile is not a workaround.

Both require the qualified display: **Windowed Borderless, 3024×1964 display, 1512×949 capture at (0,33), 75% zoom, 100% UI, locked toolbar, tool-hit location marker, default WASD controls and daylight**. Other lighting, farms, layouts and display settings are unsupported. The local inspected Stardew executable/runtime (bundled .NET 6.0.32) must match the launch guard. On Apple Silicon its Intel runtime may need locally installed Rosetta. Screen capture and ordinary input require the relevant macOS permissions for the launching process.

## First use

1. Close the previous isolated Stardew game after stopping input. Choose the exact prepared farm, then **Open fresh copy of prepared farm**. The launcher creates a new isolated working copy; it preserves the frozen seed, uses a separate configuration/data namespace and denies primary-save access. Never point it at a personal save for this workflow.
2. In the game, choose **Load**, load the named farm, exit the farmhouse to the porch and select the watering can. Apply the required settings in this isolated session if necessary.
3. In Companion, choose **Check isolated farm session**, then the matching **Qualified profile for this session** and **Connect qualified screen profile**. These checks bind fresh process/window/copy identity and visible supported state; no permission to play is restored. If a check fails, use its stated reason instead of overriding it.
4. Observe the farm and type the request. For Day 2: “Water all initially planted crops.” Inspect all 15 targets, resources and farmhouse return. A visible subset is not a replacement for all 15.
5. For Day 5: “Harvest farm--1-3, then plant parsnip seeds on farm--1-3, then water them and clear farm-0-5 and return to the farmhouse entrance.” Inspect the selected left parsnip (`farm--1-3`), one owned seed, watering of the newly planted crop, selected small stone (`farm-0-5`), protected neighboring crops, zero purchases and return. A correction such as “Leave at least 20 energy” still requires checking the entire plan.
6. Choose **Review scope**, then **Start reviewed work**. Keep Stardew foreground and let the bounded routine run. The UI brings forward only the verified game process for Start/observation; polling does not steal focus. Chatting in another foreground window during execution stops farm authority, unlike Mario's scoped input path.

## Results, guarded stops and recovery

Progress counts only when fresh visible evidence confirms the action and its resources. Already wet crops or already satisfied steps in a new observation are a starting condition, not actions performed again. A sent click alone cannot prove a harvest, planting, watering or cleared stone.

**Pause**, **Stop** and **Take control** release companion input and revoke authority. Stardew has no automatic resume from refocusing: obtain a fresh complete supported view, Observe, request only remaining work, review and explicitly Start. Pause stops companion input, not the game clock; after handback use the game's Escape menu for a long break.

Occlusion, stale screenshots, unknown resources, unsupported positions or changed process/window identity can produce a guarded partial stop. For example, all requested farm actions may be confirmed while the farmhouse return remains unconfirmed. Inspect **Outcome** and **Saved results** separately for confirmed work, remaining work and uncertainty. If stopped between supported viewpoints, take player control to reach a clear supported position before observing/reviewing again, or close unsaved and open a fresh disposable copy. Do not blind-retry the whole routine in a changed farm. A new copy starts from the prepared seed, not from the unsaved stopped attempt.

Retained watering and combined-action successes apply to their exact source and configuration. A later successful final-return repair does not turn earlier stopped attempts into completed ones or qualify subsequent source changes. See the [delivery record](b8-personal-delivery.md) for the identified build and review limits.

The public CLI remains inspection-only. Inspection commands do not select or copy a save, open a game or send input:

```bash
.venv/bin/python -m smb3_agent stardew status
```

## Limits and evidence

Qualified Day 5 targets are the selected left ordinary parsnip and small stone only. Other plots/crops, regrowth, quality/bonus yields, other debris/tools, automatic refill, purchases, sales, gifts, discards, story choices and sleeping/saving are outside this live scope. Unknown resources stay unknown. Tell is input-free; Show is review-only; neither establishes completion or Do authority. Setup copying is not live game observation: current truth comes from supported visible screenshots, never save parsing or hidden game state.

[Shared history and shutdown](../README.md#history-recovery-and-safe-shutdown) explains switching and canceled reviews. The [Stardew integration contract](b3-integration-contract.md) describes engineering interfaces. Historical qualification and repair records are linked from the [delivery record](b8-personal-delivery.md).
