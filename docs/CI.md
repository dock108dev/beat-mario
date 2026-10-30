# Continuous integration

## Checks and events

The `CI` workflow runs on pull requests, pushes to `main`, manual dispatch and
Monday at 08:23 UTC. Scheduled runs use the default branch and may be delayed.
They do not establish results for a newer pull request. PR runs cancel superseded
work on the same ref. Other events are not cancelled. No path filters strand checks.

Repository branch-protection settings are separate from workflow configuration.
There is no publishing, signing or deployment job. Native gameplay, full browser
accessibility and signed application installation are not covered by these jobs.
Existing Python dependencies are audited on weekly/manual runs, per platform. Dependency review is not an
existing-inventory audit. Whole-product coverage is not claimed by the focused suite.

## Reproducibility and security

Python uses `uv.lock`; the worker uses `package-lock.json` and its exact Node version.
Worker installation disables lifecycle scripts. Build tools and external Actions
are pinned; actionlint's downloaded binary is checksum verified. Caches are optional
for correctness. Dependabot checks Python, npm and Actions weekly.

Jobs use read-only repository permissions, ephemeral hosted runners and bounded
timeouts. Checkout credentials do not persist. No privileged PR trigger, self-hosted
runner, artifact execution or broad inherited secrets are used. Offline tests create
disposable profiles and must not launch games or call paid model providers.

## Reports

Native job summaries include outcomes, test counts, skips, slow tests, runtime,
ref, tested SHA and run/attempt links. PR head and tested merge commit are distinct.
JUnit, metrics, coverage XML/JSON, build sizes and applicable audit results are
retained as run/attempt-specific artifacts for seven days. No owner data, world
files or source archive is uploaded by the reporting steps.

Missing, malformed, empty or inconsistent required reports fail visibly. Reporting
does not turn an earlier failed gate green. Cancelled runs skip uploads and retain
their native cancellation status. Missing audit data is unavailable, not zero findings.
Counts, coverage and package sizes have no implicit baseline; compare only matching
suite scope, inputs, tools and environments. Coverage runs separately from the full
suite so instrumentation does not alter its responsiveness deadlines.

Native GitHub reporting is used without a third-party dashboard. npm audit sends
dependency inventory to the configured registry advisory endpoint; its results
reflect advisories at request time. Account quotas and storage allowances are
account-specific, not a guarantee made by this repository.

## Local equivalents

Install the locked development and worker dependencies, then run:

```bash
python3 scripts/check_actions.py
PYTHON=.venv/bin/python scripts/validate_phase0.sh
npm test --prefix minecraft-worker
.venv/bin/python scripts/ci_build.py
```

The build check exports versionable source into a temporary directory, installs
locked runtime dependencies and checks imports. It is not the signed desktop app.
The workflow defines the exact coverage and report commands. Focused local checks
are sufficient for ordinary small changes; see [development](development.md).

## Platforms and check coverage

The `verify` check keeps its name and Linux/Python 3.11 PR/main responsibilities.
Weekly/manual runs additionally execute `compatibility-macos` on `macos-14` arm64
with Python 3.14, using the same steps and exact Node pin. The matrix does not fail
fast: each environment retains its own evidence. Installation selects the matrix
Python explicitly; fresh wheel checks use that same interpreter. A cold export
includes versionable untracked files locally, so an uncommitted local pass is not
proof those files exist in GitHub. Commit scope must include required new files.

| Area / product risk | Exact workflow / job / command | Event / platform | Policy | Reason / evidence |
|---|---|---|---|---|
| Source and shell quality | CI / verify / `scripts/validate_phase0.sh` | PR, main, weekly/manual; Linux 3.11 | Blocking | Ruff lint, Bash syntax, hygiene; Ruff format check for CI tools/tests |
| Workflow correctness | CI / verify / `scripts/check_actions.py` | Same; plus scheduled Mac | Blocking | Checksum-pinned actionlint 1.7.12; no implicit host ShellCheck dependency |
| APIs, authorization, SQLite/JSON recovery | CI / verify / full `pytest -q` | Same | Blocking | Disposable profiles; no collection exclusions or test retries |
| Main interface contracts | CI / verify / `tests/test_minecraft_chat_ui.py` and full suite | Same | Blocking | HTTP/CSP/CSRF, document/script and deterministic DOM checks; legacy static renders retained |
| Worker scheduling and effects | CI / minecraft-worker / Node JUnit tests | All workflow events, Linux/exact Node | Blocking | Locked install without lifecycle scripts; routing, fake game actions and cancellation |
| Focused coverage | CI / verify / `coverage run --branch` | Same plus scheduled Mac | Required evidence, percentage advisory | Memory, bridge, delivery, SQLite build and design modules; separate run avoids instrumenting timing tests |
| Distribution/imports | CI / verify / `scripts/ci_build.py` | Same plus scheduled Mac | Blocking | Clean versionable export, wheel/sdist, hashed runtime install, fresh core/design/HTTP imports |
| Newly vulnerable dependencies | CI / dependency-review | PR only/Linux | Blocking at moderate | Intentional N/A on push/schedule; repository is public and eligible |
| Existing Python inventory | CI / verify and compatibility-macos / `scripts/ci_python_audit.py` | Weekly/manual | Blocking audit job outcome | pip-audit 2.9.0, all locked extras, current platform markers; all known findings fail, severity unavailable |
| Existing npm inventory | CI / minecraft-worker / `scripts/ci_npm_audit.py` | Weekly/manual | Blocking at high/critical | Registry advisory inventory; timeout/error yields unavailable report and failure |
| Credential/asset hygiene | CI / verify / `scripts/security_check.py` | All events | Blocking | High-confidence patterns and forbidden assets; not comprehensive secret detection or a SAST certification |
| Compatibility | CI / compatibility-macos | Weekly/manual, macOS 14 arm64/Python 3.14 | Scheduled assurance | Mac dependencies and newer Python; Linux stays the fast PR platform. Native permissions/gameplay remain untested |
| Size/performance | CI / verify / build sizes, JUnit durations | All events | Advisory | Bytes and seconds retained, no matched baseline/budget; live-game performance needs separately authorized game trials |
| Type checking/full-tree formatting | N/A | — | Deferred | No existing typed or formatter-clean baseline; avoid broad application rewrites. CI-tool formatting is enforced now |
| Browser accessibility/native installation | N/A as hosted gate | — | Unverified | Manual visual review is separate; no browser fixture runner is yet a maintained CI dependency, no signed build authority |
| Containers/IaC/production services | N/A | — | N/A | No supported deployment service or container/IaC inputs; SQLite tests use temporary files |
| Release/license approval | N/A | — | Separate scope | No release job or license allowlist policy; lockfiles inventory dependencies but do not constitute legal approval |

Recommended branch-protection checks are `verify`, `minecraft-worker` and
`dependency-review`; configure repository settings separately after checking the
workflow on the intended branch. If a merge queue is enabled, add `merge_group`
to the required jobs before enabling it.
No reusable workflow/composite is needed: the native matrix reuses one job body.

### Evidence and failure semantics

`ci_report.py` receives explicit required step outcomes and validates required
build JSON and coverage XML/JSON even when JUnit passes. Failure, unexpected skip,
cancellation or missing evidence cannot satisfy those checks. Reports still render
on failure; the native job remains failed. Worker summaries identify worker scope
instead of claiming Python gates. Versioned metrics include timestamps, Python,
Node, uv, platform, tested SHA/ref and required-check outcomes. Artifact names include
the matrix check, run and attempt; retention stays seven days. Audit tools write
unavailable evidence on timeout instead of silently implying zero findings.

No changed-code coverage delta or historical performance trend is claimed without
matching scope and inputs. A changed coverage scope requires a new comparable
baseline. Size is advisory; repeated builds on
different Python/platform inputs are not comparable benchmarks.

### Reporting tools

Only existing GitHub reporting and in-runner open-source tools are used. No new
SaaS account, secret, code upload, PR comments, or external dashboard is configured.

- [GitHub summaries](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary)
  retain per-job Markdown and downloadable artifacts. This repository is public;
  [standard hosted runners are free for public repositories](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
  Storage/budget usage is account-specific and was not queried. Artifacts expire
  after seven days; exhausted storage or unavailable upload remains a visible job
  failure. Private-repository allowances must be rechecked if visibility changes.
- [Dependency review](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review)
  is available for public repositories; private eligibility requires the documented
  paid/security arrangement. The current read-only action needs no new account.
- [pip-audit](https://github.com/pypa/pip-audit) runs locally/inside CI, needs no token
  or user/LOC/upload subscription, and sends dependency names/versions to PyPI's
  advisory service. It does not upload project source. The pinned CLI runs with
  hashes and dependency resolution disabled against `uv export`; both OS scans
  are needed because environment markers select different dependencies. Advisory
  outages fail visibly; no API availability guarantee or severity data is invented.
- [actionlint](https://github.com/rhysd/actionlint) is the existing checksum-pinned
  local validator. No account/token or external source upload is required.
- Codecov, SonarQube Cloud, Lighthouse CI, Gitleaks and OSV services/actions are
  not activated or proposed as free-account integrations here. Native coverage,
  existing secret hygiene and pip-audit/npm audit fill the current reporting need;
  deeper SAST, browser and secret-history checks remain explicit coverage limits.
