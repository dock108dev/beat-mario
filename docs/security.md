# Security model and hardening

Game Companion is a single-operator, local game-assistance and automation tool.
It has no user accounts, authenticated web sessions, database, cloud service,
webhook, or third-party callback.
Its important trust boundaries are the local Route Lab HTTP server, ignored
gameplay artifacts, emulator subprocesses, and reviewed route-patch workflow.

## V2.9 first use and product persistence

Mario setup remains loopback-only, CSRF-protected, form-encoded, body-limited,
escaped, and serialized by the privileged-action lock. Automatic detection and
the explicit macOS picker inspect only local supported paths. Identity checks
read the NES header and SHA-256 fingerprint; the product does not copy, expose,
or upload ROM contents.

The product preference file may retain the selected local path, fingerprint,
input-readiness confirmation, session choice, coaching/detail preferences, and
timestamps. It never persists or restores authorization, nonce, control epoch,
process ownership, reclaim state, or write capability. Every takeover still
requires fresh exact-process verification and explicit authorization.

## Trust boundaries

- Route Lab is an administrative surface even though it is local. It reads
  evidence, writes review state, runs bounded internal commands, and can
  promote or roll back an approved route patch.
- The CLI runs with the invoking operator's filesystem permissions. Paths
  supplied directly on the CLI are trusted operator choices, not remote input.
- ROMs, savestates, screenshots, traces, and generated session records are
  local-only data. Repository and CI guards keep them out of tracked source.
- Emulator processes use fixed argument vectors rather than a shell. Product
  FCEUX runs receive a sanitized environment; diagnostic overrides remain
  explicit operator-only CLI inputs.
- Route patches are untrusted until schema, repository-base, allowlist,
  preimage, and postimage checks pass. Validation runs in a detached candidate
  worktree. Promotion and rollback are exact, confirmation-gated, and atomic.

## Implemented controls

### Runtime authority invariants

Mario takeover, Show execution, Stardew Do authorization, and unattended
Stardew fixture preparation fail with explicit domain errors when their bound
session, controller, process identity, window identity, game identity, or
fixture is absent. These safety decisions do not use Python `assert`, so
optimized execution cannot remove them.

### V2.13 unattended regression

Unattended regression is local-only and opt-in. It accepts only an explicit
provider, eligible scenario, supported rendered-pixel display, bounded counts
and timeouts, safe non-symlinked paths, and the exact regression-only
acknowledgement. Invocation uses argument arrays with `shell=False`; inherited
environment values are discarded unless allowlisted, and credential-like keys
are rejected.

Each run owns a fresh process group and isolated directory. Cancellation or
failure may signal only that exact group. Broad cleanup targets, path escapes,
symlinks, ambiguous data ownership, remote display/execution, network
telemetry, and background upload are refused. Failures and incomplete cleanup
are retained.

The Mario ROM is read only to establish local identity and never copied into
artifacts. Accepted evidence, routes, reliability, records, learning, and owner
history are protected. Stardew requires a dedicated regression fixture whose
real path cannot overlap an owner-save root; every run uses a new disposable
copy and never opens, copies, inspects, resets, mutates, or deletes a primary
save. Protected actions remain forbidden. See the
[unattended operator guide](unattended-regression.md).

Route Lab accepts only loopback bind addresses and loopback `Host` headers.
Each server process generates an unpredictable CSRF token; every state-changing
form must return that token. POST requests must use
`application/x-www-form-urlencoded`, declare a complete body no larger than
65,536 bytes, and decode as strict UTF-8. Only known POST routes are accepted,
and one state-changing action may execute at a time.

Responses use a restrictive Content Security Policy, deny framing, disable
MIME sniffing, prevent caching and referrer disclosure, isolate the browsing
context, and disable camera, microphone, and geolocation access. Route Lab does
not enable CORS. HSTS is intentionally absent because the service is HTTP on a
loopback interface and is never an internet HTTPS origin.

Artifact responses remain underneath the configured artifact root after path
resolution. Symlink escapes, unknown file types, SVG, and files larger than 50
MiB are refused. HTML artifacts are rendered as plain text, not active same-
origin content. Redirect query parameters use percent encoding.

Expected request failures produce explicit 400, 403, 404, 409, 413, 415, or
504 responses. Unexpected failures produce a generic 500 without exposing a
traceback to the browser. Server logs retain request path, status, and failure
type but do not log form bodies or the CSRF token.

## Confirmed vulnerabilities

| Title | Category | Affected area | Severity | Confidence | Why it matters and realistic scenario | Current-code evidence | Fix / status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cross-site mutation and DNS-rebinding exposure | Authorization | Route Lab HTTP actions | Medium | High | A malicious web page could submit localhost forms that mutate review state or attempt a reviewed patch promotion. | The server accepted POSTs without an origin-bound secret and accepted any `Host`. | Per-process CSRF token on every POST plus loopback bind and `Host` enforcement. **Fixed.** |
| Active artifact content | Content handling / XSS | Route Lab artifact responses | Medium | High | A generated or imported HTML/SVG artifact could execute with Route Lab's same-origin authority when an operator opened it. | Response type came from unrestricted MIME guessing for every file below the artifact root. | Extension/content-type allowlist, HTML served as plain text, SVG and unknown types refused. **Fixed.** |
| Concurrent privileged actions | Integrity / race condition | Route Lab mutation and patch actions | Medium | High | Overlapping validation, promotion, rollback, or note writes could race against shared files and produce inconsistent state. | A threaded HTTP server dispatched every POST without shared action coordination. | Non-blocking per-server mutation lock with HTTP 409 on overlap. **Fixed.** |
| Optimized-away authority invariants | Authorization / fail-closed behavior | Mario takeover, Show, Stardew Do, unattended Stardew | Medium | High | Running Python with optimization could remove `assert` checks that guarded controller, session, process/window identity, or fixture state. A corrupted or incomplete runtime state could then proceed past its intended refusal boundary or fail without a classified domain error. | Safety-relevant runtime invariants in these paths used `assert`. | Explicit domain checks now remain active under normal and optimized Python execution. **Fixed.** |
| Unsafe redirect parameter construction | HTTP response integrity | Route Lab `Location` responses | Low | High | Control characters or delimiters in a selected identifier could create an ambiguous or malformed response header. | Query values were HTML-escaped rather than URL-encoded before use in `Location`. | Standards-based percent encoding. **Fixed.** |

## Hardening opportunities

| Title | Category | Affected area | Severity | Confidence | Why it matters and realistic scenario | Current-code evidence | Fix / status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Missing browser isolation policy | Browser security | All Route Lab responses | Low | High | Framing, MIME sniffing, caching, referrer disclosure, and browser features unnecessarily widened impact if another content defect existed. | The handler emitted no explicit browser security policy. | CSP, frame denial, no-sniff, no-store, no-referrer, cross-origin isolation, permissions policy, and noindex headers. **Fixed.** |
| Unbounded artifact reads | Resource exhaustion | Route Lab artifact responses | Low | High | A very large ignored artifact could consume substantial memory because the server read the entire file before responding. | Artifact size was not checked before `read_bytes`. | 50 MiB response ceiling with HTTP 413. **Fixed.** |
| Unbounded Experimental descriptor parsing | Resource exhaustion / input validation | Experimental contract, fixture, and installation-manifest reads | Low | High | A very large local descriptor reachable through an onboarding action could consume excessive memory during parsing. | The onboarding loaders read entire YAML and JSON files without byte limits. | Regular non-symlinked UTF-8 files are required; contracts/manifests are capped at 256 KiB and fixtures at 1 MiB before parsing. **Fixed.** |
| Ambiguous POST parser input | Input validation | Route Lab form parser | Low | High | Non-form bodies reached a parser designed for one encoding, making request behavior less predictable. | The parser did not require its supported media type. | Strict `application/x-www-form-urlencoded` enforcement with HTTP 415. **Fixed.** |

No tracked credential, private-key marker, ROM, or savestate was found during
this review. No SQL, template-expression, shell interpolation, external URL
fetch, session-cookie, or role boundary exists in the current architecture.

## Accepted design decisions

Loopback restriction is the network authorization boundary; there is no second
user identity or role model in this single-operator application. If Route Lab
is ever exposed through a non-loopback bind, proxy, tunnel, shared host, or
container port, this decision becomes invalid: authenticated users,
authorization checks, HTTPS, trusted-proxy handling, and session security must
be designed before exposure.

CLI-selected input and output paths are accepted as operator authority. Route
Lab does not turn those into arbitrary browser-controlled paths. Notes are
stored as YAML data and HTML-escaped at render time. YAML reads use
`safe_load`. Subprocesses use fixed argument arrays with no shell.

The static scan's low-severity PATH/subprocess notices are accepted. Executable
selection from the invoking operator's PATH is part of the local CLI contract;
all arguments are discrete, no shell is used, and browser-selected test actions
map to internal command tuples. Its one medium, low-confidence SQL-injection
notice is also a false positive: the cited expression constructs fixed HTML
`<option>` strings and does not interact with a database. Status: **accepted**,
confidence: **high**.

## Manual verification outside the repository

- If Route Lab is placed behind any proxy or tunnel, verify the real bind,
  forwarded-host behavior, TLS termination, and authenticated-user boundary.
  Status: **needs decision**; it is not a supported deployment today.
- If ROMs, Lua scripts, or patches come from another person, assess emulator
  sandboxing and provenance on that actual distribution path. Status:
  **deferred**; current inputs are local-operator controlled.
- Inspect ignored evidence retention on the operator workstation. The repo can
  keep those files out of Git but cannot prove workstation backup, encryption,
  sharing, or deletion policy. Status: **needs manual verification**.

## Deferred roadmap

1. Evaluate an OS sandbox and a dedicated low-privilege account for emulator
   execution if the tool begins consuming untrusted ROMs, Lua scripts, or
   externally supplied patches.
2. Define retention and deletion policy for ignored screenshots, traces, and
   session evidence if the workstation becomes shared or those artifacts gain
   sensitive annotations.
3. Expand the canonical high-confidence credential scanner only with reviewed
   patterns or a pinned dedicated scanner; broad entropy checks need an
   allowlist policy to avoid hiding real failures in fixture noise.

## Verification

Run the focused web tests and the canonical ROM-free gate:

```bash
.venv/bin/python -m pytest -q tests/test_lab_ui.py tests/test_route_patch.py
PYTHON=.venv/bin/python scripts/validate_phase0.sh
```

Manual browser verification should use the exact loopback URL printed by the
server. Confirm that normal forms work, a copied POST without its token receives
403, an untrusted `Host` receives 403, and browser developer tools show the
document security headers. No live FCEUX proof is required for these HTTP-only
changes.

For the 2026-08-23 hardening review, 203 focused security/CI-relevant tests and
all 647 tests in the complete ROM-free repository gate passed. The canonical
high-confidence tracked credential/game-asset scan found zero candidates.
Bandit found zero high-confidence medium/high issues; its single medium,
low-confidence HTML false positive is documented above. `pip-audit` found no
known vulnerabilities in the dependency graph exported from `uv.lock`; it
skipped only this unpublished local package because it has no PyPI release to
audit. Hosted pull requests now also run the immutable-pinned GitHub dependency
review action and reject newly introduced moderate-or-higher vulnerabilities;
weekly Dependabot updates cover both `uv` and GitHub Actions dependencies.

## Experimental adapter onboarding

Browser actions address adapter IDs only beneath fixed scaffold and installation
roots. Contracts accept executable basenames, window-title fragments,
declarative facts, and ordinary action tokens—not paths or commands. Reserved
IDs, Mario/Stardew collisions, absolute or traversing paths, symlinks, unknown
files, executable content, URLs/dependencies, collisions, and overwrites fail
closed.

Atomic installation retains exact hashes and manifest ownership. Uninstallation
requires exact integrity plus zero active process, authority, input, and session
state, removes only exact owned files, and preserves external evidence/history.
Conformance and installation cannot grant Supported status or live proof.

Contracts, fixtures, and installation manifests must be regular non-symlinked
UTF-8 files. Contracts and manifests are limited to 256 KiB; each JSON fixture
is limited to 1 MiB. Oversized content is refused before YAML or JSON parsing.
