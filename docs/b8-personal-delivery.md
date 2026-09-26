# Personal Mac delivery

This is an in-place delivery at `/Users/michaelfuscoletti/Desktop/beat-mario`. Keep this repository, its installed `.venv`, and the registered local engineering assets at their existing paths. It is not a portable package or an app bundle. No proprietary game files are bundled.

## Launch and stop

Double-click **Open Game Companion.command** in this folder. It verifies the running server's repository and source identity before reusing it. A stale source requires **Stop Game Companion.command**, then a fresh launch. An unidentified server on port 8765 is refused; inspect and close that application's server separately. The launcher does not kill unknown processes.

Double-click **Stop Game Companion.command** to revoke input, retain results, close this server's game processes and stop the identified service. It checks a fresh server-instance token and reports unconfirmed cleanup as a failure. It never searches for and terminates unrelated game processes. Closing the browser does not stop execution. Stop also closes unsaved disposable Stardew work; the frozen seeds and retained attempt history remain unchanged.

For a terminal:

```bash
cd /Users/michaelfuscoletti/Desktop/beat-mario
.venv/bin/python scripts/launch_companion.py --status
.venv/bin/python scripts/launch_companion.py --no-browser
.venv/bin/python scripts/launch_companion.py --stop
```

If the environment is missing, follow README's locked `uv` installation instructions in this folder. Do not move or assume portability of `.venv`. The localhost service uses port 8765. A new launch restores no gameplay authority: select the game, establish a fresh session, inspect a new plan and explicitly Start.

## Dependencies and evidence

The B8 dependency inventory resolves both frozen seeds, three registration files, both profiles and their transitive calibration/evidence references. These ignored engineering assets are **already installed locally**, not included by a source clone. The full source manifest includes application, scripts, data, tests and instructions. Python and packages are installed locally; `uv.lock` is included. FCEUX, the supported user-owned Mario file, Stardew and its accepted bundled runtime are external prerequisites. Optional local artwork uses CSS fallbacks when absent.

Stardew requires the exact Day 2/Day 5 profile pairing and display/settings in the [operator guide](stardew-operator-guide.md), plus macOS capture/input access and the installed Intel runtime support. Missing or changed registrations/calibration prevent setup; restore the exact recorded dependency, never switch profiles to bypass it. Personal saves are outside this delivery and must not be copied or migrated.

Mario results remain under `artifacts/conversation`, farm results under `artifacts/stardew-conversation`, native live evidence under its original attempt directories, and saved variants under `data/variants`. These local histories are preserved, not portable bundled content. Reopening history or a proposal is read-only and grants no authority.

The active mapping is `data/scenarios/personal-beta-v3.yaml`. The v2 contract and older manifests remain historical. B6 technical qualification, B7 guidance, B8 delivery and B9 owner usefulness/acceptance are separate. Execution remains disabled for unattended campaigns. The original failed delivery is retained at `artifacts/b8-delivery/20260926/closeout.md`. The subsequent successful final-return repair and delivery readiness are in `artifacts/b8-final-return-repair/20260926/closeout.md` and `b8-readiness.json` in that directory, bound to source `ed84e02a095d00df858cfd286fa458fb85267f983561b36483a5dfb712653b94`. B9 began against that source; later local failure-handling maintenance changes the checkout. Reconcile the running service/candidate identity before continuing review or relaunching; these instructions do not qualify the changed source. See the September 26 maintenance boundary in [error handling](error-handling.md#september-26-maintenance-boundary).

Carry forward normal/uncapped Mario speed only, quickest/100% base fallback, unknown full-completion coverage, opening-only resumed Mario play, bounded farm targets, foreground-only Stardew input, guarded partial stops, no automatic refill and local-only assets/service.
