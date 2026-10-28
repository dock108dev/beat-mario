# Campaign contracts

Campaign files under `data/scenarios/` describe bounded evaluation inputs and
expected outcomes. They are engineering contracts, not a background service or
an authorization to run games. The final-campaign contract has execution disabled.

Use the CLI's `scenario --help`, `metrics --help` and `unattended --help` commands
to inspect the available validation/reporting operations. Follow
[unattended regression](unattended-regression.md) for explicit execution constraints
and [session metrics](session-automation-metrics.md) for result classifications.

Keep synthetic, regression and live observations distinct in reports. A stored
successful result does not grant future input permission or prove a different
runtime or game state. World/save identity, startup assumptions, cleanup and
supported outcomes must be explicit before native execution.
