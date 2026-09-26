# B8 delivery work order

**Historical work order prepared by B7; B8 has since completed on retained source `ed84e02a…`, and B9 has started with owner observations/acceptance pending.** See [current delivery guidance](b8-personal-delivery.md) and the [repair closeout](../artifacts/b8-final-return-repair/20260926/closeout.md). The requirements and pre-delivery gap descriptions below preserve the original work order, not new instructions to repeat completed work. Later maintenance does not inherit B8 qualification. B6 technical qualification and the [B7 closeout](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b7-guidance/20260926/closeout.md) remain separate evidence. This is one bounded engineering delivery stage, not a new game-development or broad gameplay campaign.

## Entry and exact identity

Start from this preserved working tree, not HEAD alone. HEAD is `c61de17668dce092b26990c18493c4bfb92eeb41`. B7 verified all 218 source files, including uncommitted work, against B6 SHA-256 `a82590feb3c490bb96a769753eeaaf361490049c3c5bc9c77091c4e317372226` with zero differences. B7 changes documentation only; its [final source manifest](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b7-guidance/20260926/candidate-source.json) and [continuity check](/Users/michaelfuscoletti/Desktop/beat-mario/artifacts/b7-guidance/20260926/continuity.json) identify the resulting tree. Do not label its full source hash as the B6 hash.

Before B8 work, verify that manifest against every nonignored tracked/untracked file and separately inspect the Desktop tracker. Preserve dirty work, seeds, exact source archives and every attempt. Freeze a new final source inventory plus launcher/package inventory and artifact hashes after any B8 changes. Bind checks to the actual delivered path/process and source; a pre-existing server on port 8765 is not proof it runs the delivery. Record any difference and select checks from its effect. No commit, push or owner acceptance is implied.

## Deliverable and prerequisites

Default to the existing repository-local **Open Game Companion.command** plus locked environment and instructions for this personal Mac. Do not introduce an app bundle merely for presentation. Confirm that choice works in the intended location; choose a package only if a concrete launch or relocation requirement warrants one, and retain the reason and exact inventory. Signing/notarization/public distribution are outside this work order.

| Inventory | Required B8 reconciliation |
| --- | --- |
| Launcher and application | Include command launcher, `scripts/launch_companion.py`, application/scripts/data and locked dependency instructions. Identify whether the environment is installed in place or recreated; do not assume a moved `.venv` is portable. |
| Local Mario prerequisites | Verify FCEUX resolution, supported user-provided game-file configuration and visible session launch. Proprietary game assets are external, not bundled. |
| Local Stardew prerequisites | Verify the installed executable/runtime hashes accepted by `stardew_setup.py`, macOS input/capture permissions, required display/settings and applicable Rosetta availability. No game installation or personal-save migration is implied. |
| Prepared seeds | Inventory `pilot-day2` and `b4-day5-v1`, both exact hashes in the [operator guide](stardew-operator-guide.md), and the registered absolute source paths. Preserve the frozen originals; use only fresh disposable copies for checks. |
| Profile and evidence dependencies | Inventory both local registration files and their referenced manifests, calibration images, loading/persistence proof and any transitively required evidence. Resolve every dependency and hash it. A launcher/source archive alone omits these ignored assets; missing dependencies must produce an actionable setup failure. |
| Optional UI artwork and history | Decide what artwork from [local assets](local-assets.md) is included versus optional. Identify retained history location and ensure reopening is read-only. Do not treat personal history or engineering artifacts as included by default. |

Write one delivery inventory that explicitly labels **included**, **already installed locally**, **external prerequisite**, and **missing/blocking**. If preserving the existing machine paths, say so: that is an in-place personal delivery, not a portable package. If copying allowed engineering assets, verify the dependency closure at the new paths without rewriting retained evidence or weakening trust checks.

## Scenario and readiness reconciliation

Inspect `data/scenarios/personal-beta-v2.yaml` and `src/smb3_agent/beta_readiness.py` before changing them. The existing contract has `execution_enabled: false`, B6 `mario_qualification_and_feedback` classified as `owner_usefulness_feedback`, and a single coarse B8 delivery case. These do not yet represent the completed technical B6 versus separate B9 owner review correctly.

Version the active beta mapping/validator as needed while preserving historical contracts/manifests. Map B6's actual technical cases (speed/destination, saved variants, opening-only return, stale/late edits, reclaim and process loss), B7 document review, and B8 launch/assets/isolation/cleanup evidence to the right classes. Keep owner usefulness/acceptance blank until B9. Do not enable an automatic campaign or require a third adapter. Retain B2–B6 evidence with its original source and continuity rationale; do not relabel older live evidence as a final-package rerun. A readiness report must explain missing cases rather than manufacturing a full-beta PASS.

## Necessary current-candidate checks

1. **Launch/relaunch and setup:** check the chosen delivery from its intended location; missing prerequisite/occupied-port behavior; known server identity; both game selectors; correct farm/profile pairing; fresh opening with no inherited authority. Check the ordinary review, canceled review, saved-result reopening and neutral switching surfaces on that candidate.
2. **Focused engineering checks:** run documentation/command/link checks and tests covering changed delivery/readiness contracts. Run the cumulative non-live gate once after B8 runtime/configuration/readiness changes. If only packaging paths change, demonstrate those paths; do not repeat B6's sixteen attempts or accepted World 8 campaigns. New failures justify only affected repair/checks.
3. **Mario delivery smoke:** use a fresh compatible session for a bounded reviewed opening-stop request, confirm result and neutral handback; reopen a saved proposal/history without permission. Reuse unchanged B6 speed/destination/guard qualification through explicit source continuity. Broaden only for a changed controller, entry or packaging behavior.
4. **Stardew delivery gap:** use a fresh Day 5 copy, exact profile/settings and ordinary combined request/review/Start to verify selected actions, resources, farmhouse return and neutral handback on the delivery candidate. Start with one uninterrupted attempt; preserve its source, screenshots, ledger and result. Day 2 needs fresh setup/profile compatibility verification; repeat its full watering path only if changed shared/farm contracts or a failed prerequisite affect its retained proof.
5. **Shutdown and reopening:** verify input release, game-process closure and no restored authority. The current command launcher leaves a background server alive and recognizes a server by header rather than source identity. Deliver a concrete way to identify/stop the correct server and game processes; verify clean relaunch, history retention and fresh review. Do not assume closing a browser/launcher terminal ends execution.

### Explicit Stardew gap decision

Guarded stops are supported safety behavior and do not invalidate B3/B4 development. However, **B5's combined attempt and fresh recovery both stopped with return unconfirmed**. Their neutral handback does not establish arrival at the reviewed farmhouse stop. Retained B3/B4 success is valid evidence for unchanged behavior, but cannot supply a current-source successful return. Because delivery promises a complete routine and reviewed return, this is a remaining delivery evidence/usability gap, not silently waived by B6 completion.

If the bounded B8 attempt confirms the complete flow, close this gap with exact current-candidate evidence. If it stops again, retain the partial result and first failed prerequisite, distinguish observation/environment failure from a concrete runtime defect, and keep delivery readiness blocked for the complete-return promise. Do not launch a repeat-until-pass campaign. Propose only the bounded prerequisite repair and affected repeat; any runtime development or changed product scope needs a separate explicit work decision. Reducing the delivery promise to partial work requires an explicit scope decision, not a documentation edit or assumed owner acceptance. B7 performs none of these gameplay checks.

## Exit and handoff to B9

Produce the identified launch/package, complete dependency inventory, versioned readiness reconciliation, check/evidence table with original versus new sources, known limitations and reproducible launch/cleanup instructions. State whether the Stardew gap closed; if not, name the blocker and next actor. B8 can be delivery-ready only after these engineering gates pass. Then provide one neutral B9 review of the exact delivery with owner fields still blank.

Carry forward: quickest/100% base fallback; unknown full-completion coverage; normal/uncapped speed only; opening-only resumed Mario play; bounded farm targets/settings and foreground-only input; possible guarded partial stops; no automatic refill; local-only service and assets. No new game features, third adapter, personal-save access, broad campaign, publication, commit or push belongs to this work order.
