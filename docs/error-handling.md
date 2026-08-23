# Error Handling and Operations

This document is the source of truth for failure handling outside the gameplay
observer contract. Gameplay success and failure rules remain in the goal,
catalog, and reliability documentation.

## Reliability execution

The reliability and watchable orchestrators deliberately catch ordinary
`Exception` values at process and artifact boundaries so a failed run leaves a
machine-readable report instead of disappearing. They do not catch
`BaseException`, `KeyboardInterrupt`, or `SystemExit`.

Every caught preflight or runner exception fails closed. Reports retain the
exception type, message, and Python traceback. Log-parsing, focused-screenshot,
and watchable contact-sheet failures also retain their own exception record and
are classified as `artifact-integrity` when no more specific gameplay failure
owns the result. A caught exception can never produce `passed=true`.

Source provenance is best-effort metadata rather than a gameplay prerequisite.
If Git cannot report the commit or dirty state, the report keeps those values
as `null` and records the command or launch problem in `source_state_error`.

For an incident, inspect in this order:

1. the aggregate `preflight`, `failure_classifications`, and `overall_pass`;
2. the failed run's `failure_classification`, `exception`, and
   `exception_traceback`;
3. `fceux_execution.json`, `fceux_stdout.log`, and `fceux_stderr.log`;
4. log, screenshot, or contact-sheet exception records for artifact failures;
5. the last accepted and first missing contract milestones.

Tracebacks contain code and local filesystem paths but not Python frame locals.
Reliability artifacts are local-only and must not be committed or uploaded.

## Route Lab HTTP service

Route Lab is a localhost operator surface. It refuses non-loopback bind
addresses because its actions can read local evidence and mutate reviewed route
patches. It also validates the loopback `Host`, requires a per-process CSRF
token on every POST, and permits only one state-changing action at a time. On
startup it enables timestamped standard-library logging. Completed
HTTP requests are logged at `INFO`.
Expected invalid requests are logged at `WARNING` with method, path, status,
error type, and detail. Unexpected handler defects are logged at `ERROR` with a
traceback and return a generic HTTP 500 page that does not expose the exception
detail to the browser.

The response mapping is:

- malformed forms and domain validation errors: HTTP 400;
- missing or invalid loopback authorization/CSRF: HTTP 403;
- a requested local record that does not exist: HTTP 404;
- an overlapping state-changing action: HTTP 409;
- an oversized artifact: HTTP 413;
- an unsupported form media type: HTTP 415;
- a bounded subprocess action that times out: HTTP 504;
- an unexpected handler failure: HTTP 500.

Form bodies are limited to 65,536 bytes, must use
`application/x-www-form-urlencoded`, declare a non-negative numeric
`Content-Length`, arrive completely, and decode as strict UTF-8. Artifact
responses use a passive content-type allowlist and a 50 MiB ceiling.
Unsupported paths remain HTTP 404. Server shutdown always closes the listening
socket. See [Security model and hardening](security.md) for the complete browser
policy and trust model.

## Route patches

Patch validation, promotion, and rollback remain transactional. Broad catches
around these transactions are intentional: they restore original bytes, verify
the restoration, preserve a failure artifact with the exception traceback, and
then re-raise. They never turn a failed mutation into success.

Patch discovery may encounter stale or corrupt ignored records. Those records
remain non-fatal to the Route Lab page, but each skipped record now emits a
warning containing its path and parse error. Temporary worktree removal and Git
pruning failures also emit warnings. Direct recursive cleanup refuses an empty,
current-directory, repository-root, or filesystem-root target.

## Deliberate best-effort behavior

- A missing optional Route Lab YAML document still renders as an empty section;
  missing required records raise their domain error.
- Watchable contact-sheet creation may fail after gameplay completes, but the
  review remains failed and non-promotable with the exception retained.
- The legacy Mednafen frame sampler records each per-frame exception and keeps
  sampling so a transient capture failure does not discard later diagnostic
  evidence. Missing course-clear evidence cannot become success.
- Mednafen application-focus commands are not best effort: either AppleScript
  command failing now raises and stops input execution before controls could be
  sent to an unintended application.

## Control, handback, and process termination

Show acknowledges `input_stopped` only after the owned process has exited.
Bounded `SIGTERM` then `SIGKILL` escalation is retained, but a lost process
handle, second timeout, or still-running process raises `ShowError`; the UI must
not claim that control returned in that state.

Stardew ordinary-input failures always enter the adapter's fail-closed terminal
path. If both input dispatch and neutralization fail, the retained failure names
both errors, clears authority, leaves the owner as `none`, and refuses confirmed
player handback. The companion controller reuses that first adapter failure
instead of neutralizing again and overwriting the original cause.

## Scenario and unattended artifacts

Scenario execution and cleanup boundaries deliberately catch ordinary
exceptions so immutable attempts can reach `failed` or `retained_for_review`.
Each caught failure now appends a structured record with phase, exception type,
message, and traceback to `failure_details`; cleanup failure never becomes
completion.

Unattended regression runs use the same structured fields in per-run reports
and aggregate `exceptions` and `cleanup_exceptions`. Process, environment,
keyboard-interrupt, fixture, prelaunch, and cleanup failures remain
regression-only retained evidence. Malformed manifests raise `UnattendedError`
instead of leaking implementation exceptions such as `KeyError`.

Live-observation state-sample image conversion remains non-fatal to clean
observer detach, but `reconciliation.json` records
`state_sample_conversion_exception` with type, message, and traceback. An empty
converted-image list therefore cannot be mistaken for successful conversion.

## Experimental adapter transactions

Scaffolding and installation still roll back their bounded temporary directory
when staging or atomic promotion fails. Cleanup errors are no longer ignored:
the operation raises `ExperimentalAdapterError` containing both the original
operation failure and cleanup failure and identifies the retained staging path
for inspection. Symlink roots are rejected before directory creation.

Tracked contracts, profiles, knowledge, and scripts resolve from the repository
installation rather than the process working directory. Runtime artifacts and
owner-selected files remain explicitly rooted by their owning operation. This
keeps localhost request threads deterministic even if another local caller
changes its working directory.

## Validation

Run the unchanged repository gate from the repository root:

```bash
PYTHON=.venv/bin/python scripts/validate_phase0.sh
```

This hardening changes orchestration and local operations only. It does not
change goal contracts, route inputs, gameplay observers, or the requirements
for live FCEUX acceptance.
