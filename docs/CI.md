# Continuous integration

## Checks and events

The `CI` workflow runs on pull requests, pushes to `main`, manual dispatch and
Monday at 08:23 UTC. Scheduled runs use the default branch and may be delayed.
They do not establish results for a newer pull request. PR runs cancel superseded
work on the same ref. Other events are not cancelled. No path filters strand checks.

| Job / command | Purpose | Policy |
|---|---|---|
| `verify` / `scripts/validate_phase0.sh` | Lint, hygiene, Python suite, CLI and render contracts | Blocking job |
| `verify` / `scripts/check_actions.py` | Check Actions syntax and expressions | Blocking job |
| `verify` / focused coverage | Minecraft memory/bridge/delivery line and branch coverage | Report required; no percentage floor |
| `verify` / `scripts/ci_build.py` | Clean export, wheel build, locked runtime install, fresh imports | Blocking job |
| `minecraft-worker` / Node test runner | Worker routing, crafting, construction and cancellation | Blocking job |
| `dependency-review` | New dependencies with moderate-or-higher vulnerabilities | PR only |
| `scripts/ci_npm_audit.py` | Existing npm dependencies | Weekly/manual; high/critical findings fail |

Repository branch-protection settings are separate from workflow configuration.
There is no publishing, signing or deployment job. Native gameplay, full browser
accessibility, signed application installation and a comprehensive audit of existing
Python dependencies are not covered by these jobs. Dependency review is not an
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
python3 scripts/ci_build.py
```

The build check exports versionable source into a temporary directory, installs
locked runtime dependencies and checks imports. It is not the signed desktop app.
The workflow defines the exact coverage and report commands. Focused local checks
are sufficient for ordinary small changes; see [development](development.md).
