# Repository and documentation audit — October 25, 2026

The personal-use priority is unchanged: complete one useful coached Mario early
segment in the existing app, verify handback/Stop, and repair the first actual
blocker. Candidate.35 has retained ordinary Stardew watering/return evidence.
This audit corrected the documentation; it did not complete new gameplay.

## Scope and sources

The repository was clean on `main` at
`5f946ba65f1b505aa6d94cced80f5aafd89bdcec` before these edits. The audit examined
current plans and guides, historical-record boundaries, local Markdown links,
source entry points and capability flags, source differences from candidate.35,
its manifest and qualification/session files, installed bundle metadata/resources,
and hosted CI for the audited commit. Behavior claims were checked against the
owning source modules and retained result files rather than inferred from test
counts or file modification times.

The active worklist is the [Desktop tracker](/Users/michaelfuscoletti/Desktop/mario_next_steps.md).
The repository's [current status](current-engineering-status.md) now provides
source/build identity, a capability/status table and direct evidence links.
[Personal use](personal-use.md) continues to control work scope. Dated trials
remain evidence of their original source, build and configuration.

## Discrepancies corrected

| Finding | Correction and source of truth |
| --- | --- |
| Desktop tracker dated October 7 had two missing supporting documents. | Replaced dead links with current repository status, handoff, scope and this audit; added the verified baseline and an ordered Mario-first worklist. |
| Current-status page was too abbreviated to support guides linking to “exact identity/evidence.” | Restored candidate.35 identity, exact source digest, installed-resource check, current CI and direct native evidence links. |
| Source changes and installed app were acknowledged only generically. | Compared the frozen source manifest/archive with the checkout. Named the later focus-cancellation checks, UI/package maintenance, FCEUX path validation and dependency differences; preserved build-specific claims. |
| README named a nonexistent `Launch Game Companion.command`; the actual launcher's missing-environment message named a removed README section. | Corrected the README to the tracked `Open Game Companion.command`, verified against `scripts/launch_companion.py`, and pointed the launcher help message to “Launch and first use.” Launch/Stop behavior is unchanged. |
| Development guide required a full canonical/package campaign for every runtime change, contradicting personal-use scope elsewhere in the same guide. | Aligned it with affected checks/native use, with broader checks for shared changes or demonstrated faults. CI still runs the full gate. |
| Optional build guidance omitted prerequisites and the retained default identity. | Documented PyInstaller, Tesseract data/license, ignored calibration inputs, successor version/build arguments and stable-identity installation rules from the builder/installer/resource owners. No build was made. |
| Conversation guide said exact packaged provider discovery remained pending and described the watering model only as prepared Day 2. | Candidate.35 ordinary Stardew used real model inference; documented both ordinary selected-save and prepared watering, while keeping Mario completion and wider quality evaluation open. |
| Architecture/runtime summaries obscured the ordinary Stardew package success. | Linked the exact evidence and separated it from source-native Mario, prepared farms and unqualified reconnaissance. |
| V2 roadmap introduction still dispatched a successor two-game release/third-game sequence despite its historical label. | Replaced the current-sounding dispatch with the active personal-use work order; preserved historical slice results. |
| October 6 audit and Stardew integration release criteria could reintroduce an obsolete mandatory campaign. | Added explicit historical/future-release scope, preserving the evidence and technical requirements. |
| Runtime guide linked to a shortened feedback page for package identities that it no longer contained. | Pointed to the current evidence index and named older package records. |
| Ordinary versus prepared farm instructions and source-native versus installed Mario claims could be read too broadly. | Scoped prepared-profile sections explicitly, dated the retained Mario stairs/pipe result and linked current remaining work. |
| “Permissions resolved” read as an unconditional current guarantee. | Preserved the recorded setup success, while distinguishing current readiness checks from this read-only audit. No old setup blocker was reinstated. |

## Confirmed status and limits

- Installed app metadata identifies `local.gamecompanion.privatebeta`, version
  `0.3.0`, build `30035`. All 196 manifest-listed installed resources match.
  The frozen candidate source digest is
  `dcb3dbe177a9409f733b7aad6c30e4a7d5ee861107a0904a1276b3df890f2f2b`.
- October 6 Stardew records show the middle crop watered, neighbors left dry,
  energy 270→268, water 40→39, completed return and confirmed handback. The Stop
  trial interrupted the active watering task during navigation before watering.
  It does not qualify every possible interruption point.
- Candidate.35 Mario has a reviewable coached proposal with no completed outcome.
  Retained helpers stopped on assertions before Start; a fresh ordinary trial
  must establish the actual remaining blocker, if any.
- Current source still disables Minecraft aim/movement/placement/wall via
  `CHECKED_FEATURES`. Full-level adaptive Mario, broader farms, native
  reconnaissance/cave delegation and ordinary recording remain outside verified
  personal-use coverage. Authored full-game route evidence is a separate product
  path and does not close the adaptive Mario task.
- The candidate qualification file and `data/companion/local-candidate.yaml`
  retain pending full qualification. These are not live per-task status ledgers;
  narrow Stardew success and incomplete two-game qualification can coexist.
- [Hosted CI](https://github.com/dock108dev/beat-mario/actions/runs/40216300354)
  passed on the audited commit: **1,758 passed, 35 skipped**, plus the canonical
  lint, security/file guards, goal/catalog validation and UI render checks.
  Dependency review was correctly skipped on the push run. This result predates
  the documentation edits and establishes no native game behavior.

## Validation and preservation

Validation passed: **421 local file/heading links across 64 Markdown documents**
(repository documents plus the Desktop tracker), **22 existing documentation/CI
contract tests**, and `git diff --check`. No broken local links or trailing
whitespace remained. The audit receipt is retained locally at
`artifacts/documentation-audit-20261025/receipt.json`; it records the exact counts,
source baseline and checks. The launcher help-text edit also passed `zsh -n`.
A full local gameplay/test campaign is not required for documentation and a
help-message correction.

No gameplay/application logic, test implementation, contract values, dependency lockfile,
installed bundle, retained qualification result or gameplay save was changed.
No game was launched, input posted, inference requested or permission altered.
The audit did not reverify original/frozen save integrity, current native
permissions, active keyboard/Dock exit or owner usefulness. Earlier preservation
receipts retain their original dates and are not fresh integrity claims.

The Desktop tracker is outside the repository and must be retained separately
from any future commit of the repository documentation. Embedded package docs
remain build-time text until a needed successor app is built.
