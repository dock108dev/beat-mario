# Security model and hardening

## Model inference and local authority

App-user inference uses [explicit provider configuration](ai-provider.md).
Selected context and verified screenshot inputs go to the configured local/LAN
server. Game tools
run on the app machine. HTTP on a LAN is unencrypted; keep it on a trusted network.
No browser model requests, cloud fallback or image generation are enabled.

Local-server credentials stay in user-level
configuration/environment and are passed to disposable request workers over stdin,
not command arguments or public status. Client cancellation discards late replies
and terminates the request worker; it does not prove remote GPU work stopped.
Profile-qualified models are not silently substituted with another installed tag.

Game text, screenshots, imported notes and model replies are data, not permission.
Validated adapter dispatch checks current targets, preconditions, parameters,
reviewed finite scope and control generation independently of the model. Runtime
inference does not receive a source-editing or unrestricted native-input path.
Stop and release remain independent of provider requests; canceled or stale
output cannot recreate authority.

Game Companion is single-operator and local. It has no user accounts, authenticated
web sessions, database or hosted service. The HTTP UI must remain on loopback.
Raw diagnostic captures and local gameplay evidence require inspection before
sharing; inference transfer and explicit feedback export are separate operations.
Source controls do not qualify an older packaged app. The separate native-camera Minecraft path
keeps movement/placement/wall execution disabled; headless Minecraft uses its own worker.

## First use and product persistence

Mario setup remains loopback-only, CSRF-protected, form-encoded, body-limited,
escaped, and serialized by the privileged-action lock. Automatic detection and
the explicit macOS picker inspect only local supported paths. Identity checks
use a local fingerprint; the product does not copy or expose source contents.

The product preference file may retain the selected local path, fingerprint,
input-readiness confirmation, session choice, coaching/detail preferences, and
timestamps. It never persists or restores authorization, nonce, control epoch,
process ownership, reclaim state, or write capability. Every takeover still
requires fresh exact-process verification and explicit authorization.

## Ordinary player, model and native-input boundaries

- The Mac app opens only its local setup surface and verifies source identity
  before reusing an existing instance. Shutdown requires the current server token
  and matching instance identity. An unknown app/port owner is not killed.
- Player profiles use bounded, validated data schemas and controlled local IDs.
  Imports cannot carry code, live observations, window connection, reviewed plans
  or authority. The implemented OpenTTD executable profile is a finite declarative
  capability. Save/reopen/edit/duplicate/import preserve configuration without
  restoring execution permission.
- Minecraft setup writes supported options/debug preferences only after checking
  that the game is closed and preserving backups. It refuses concurrent settings
  changes and does not edit worlds. The user selects a disposable Creative world
  and manually prepares the supported visible region/material.
- Native input binds the selected process/window, compatible settings, current
  pixel observations, explicit review/Start and finite budgets. Camera/movement
  feedback, material/reach/occupancy and outcome checks supply facts independently
  of text or model confidence. Changed, missing, contradictory or expired evidence
  stops the affected task and retains partial work.
- Current source checks child/parent deadlines after observations and includes
  observation uncertainty in aiming completion. Inspection reuse requires the
  compatible pose/window/settings and unchanged position; stale reuse cannot
  replace a fresh check before an addition.
- Stop, Take control and safe chat revoke authority before blocking work. In the
  corrected setup UI they bypass unrelated draft/coordinate parsing; native work
  immediately locks drafting until successful safe-chat handback. Page heartbeat,
  cancellation epochs, bounded input workers and shutdown protect against stale
  execution. Unconfirmed input release blocks new authority. Key release alone
  does not establish gameplay stillness.
- OpenTTD's gateway sends a selected-window image and bounded task context only
  to local Ollama at `127.0.0.1:11434`, without proxies. The installed model identity
  must be local and multimodal. Structured proposals are constrained by finite
  profiles and independently read targets/values. Canceling kills the request
  worker and discards late replies; it cannot prove Ollama stopped GPU computation.
  Ordinary Mario/Stardew use the separate AI provider described above.
  Current Minecraft typed requests do not need model inference.
- Profiles, history, reports, settings backups and session diagnostics live outside
  installation in the user data root. Normal report export includes selected
  configuration, sanitized recent outcomes and the user's text; raw screenshots,
  credentials and unrelated save contents are excluded. Native diagnostic folders
  may contain game captures and must be inspected before manual sharing. Nothing
  is uploaded automatically.

## Trust boundaries

- Route Lab is an administrative surface even though it is local. It reads
  evidence, writes review state, runs bounded internal commands, and can
  promote or roll back an approved route patch.
- The CLI runs with the invoking operator's filesystem permissions. Paths
  supplied directly on the CLI are trusted operator choices, not remote input.
  Route-patch imports are narrower: the patch document must be a regular,
  non-symlinked file beneath the repository so the same backend remains safe
  when reached from Route Lab.
- Savestates, screenshots, traces, and generated session records are
  stored local runtime data. Repository and CI guards keep them out of tracked source. The AI provider transmits selected game captures/context for inference as disclosed above.
- Emulator processes use fixed argument vectors rather than a shell. Product
  FCEUX runs receive a sanitized environment; diagnostic overrides remain
  explicit operator-only CLI inputs.
- Route patches are untrusted until schema, repository-base, allowlist,
  preimage, and postimage checks pass. Validation runs in a detached candidate
  worktree. Promotion and rollback are exact, confirmation-gated, and atomic.
- Browser-derived goal, issue, session, adapter, validation-output, and patch
  identifiers use real-path normalization plus controlled-root prefix checks
  before filesystem access. Temporary adapter directories use fixed prefixes.
- Legacy Mednafen diagnostics retain whether process output existed and its
  length, but not raw emulator output or the private local game-file path.
  Accessibility permission is checked as a startup prerequisite but is not
  copied into persisted or printed result objects.
- Browser route-patch validation cannot supply a game-file argument. Live gate
  configuration comes only from the operator-owned `SMB3_GAME_FILE` process
  environment; injected form fields are ignored.

## Implemented controls

### Runtime authority invariants

Mario takeover, Show execution, Stardew Do authorization, and unattended
Stardew fixture preparation fail with explicit domain errors when their bound
session, controller, process identity, window identity, game identity, or
fixture is absent. These safety decisions do not use Python `assert`, so
optimized execution cannot remove them.

### Unattended regression

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

The configured Mario source is used only to establish local identity and is
never copied into artifacts. Accepted evidence, routes, reliability, records, learning, and owner
history are protected. Stardew requires a dedicated regression fixture whose
real path cannot overlap an owner-save root; every run uses a new disposable
copy and never opens, copies, inspects, resets, mutates, or deletes a primary
save. Protected actions remain forbidden. See the
[unattended operator guide](unattended-regression.md).

Route Lab accepts only loopback bind addresses and one syntactically valid
loopback `Host` authority at the actual listening port. Userinfo, paths, query
strings, fragments, duplicate Host fields and mismatched ports are refused.
A browser POST with an `Origin` must match the request Host's HTTP origin and
port exactly; foreign, opaque (`null`) and duplicate origins are refused before
reading the body. Origin-less local launcher/CLI calls remain supported, and
must still supply the CSRF token. Each server process generates an unpredictable CSRF token; every state-changing
form must return that token. POST requests must use
`application/x-www-form-urlencoded`, declare a complete body no larger than
65,536 bytes, and decode as strict UTF-8, including percent-encoded values.
Exactly one decimal Content-Length and one supported Content-Type are required;
Transfer-Encoding is unsupported. Forms are limited to 128 fields. Scalar
fields (including CSRF and action) must occur exactly once; declared list fields
retain their repeated-value behavior. A non-ASCII CSRF value is refused as an
invalid token. Only known POST routes are accepted.
New authority and ordinary mutations share the action lock; direct Stop/Take control,
safe-chat/edit/disconnect and heartbeat paths bypass that lock so an in-flight
operation cannot prevent revocation.

Responses use a restrictive Content Security Policy, deny framing, disable
MIME sniffing, prevent caching and referrer disclosure, isolate the browsing
context, and disable camera, microphone, and geolocation access. Route Lab does
not enable CORS. HSTS is intentionally absent because the service is HTTP on a
loopback interface and is never an internet HTTPS origin.

Artifact responses remain underneath the configured artifact root after path
resolution. Symlink escapes, unknown file types, SVG, and files larger than 50
MiB are refused. The actual file read is also bounded to the limit plus one
byte, so file growth after the metadata check cannot bypass the ceiling. HTML artifacts are rendered as plain text, not active same-
origin content. Redirect query parameters use percent encoding.

Expected request failures produce explicit 400, 403, 404, 409, 413, 415, or
504 responses. Unexpected failures produce a generic 500 without exposing a
traceback to the browser. HTTP logs retain the recognized route (artifact/asset
paths are grouped), method, status and failure type. They omit request query
strings, arbitrary path components, form bodies, protocol-error payloads and
exception messages. Unexpected failures retain file/line/function stack locations
without frame locals or source lines. Subprocess timeout pages omit command
arguments. This does not redact older log files or other subsystems' existing
local evidence.

CSRF-field injection and note artifact-path extraction use bounded linear
string scans rather than regular expressions over browser-controlled text.

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
- If Lua scripts or patches come from another person, assess emulator
  sandboxing and provenance on that actual distribution path. Status:
  **deferred**; current inputs are local-operator controlled.
- Inspect ignored evidence retention on the operator workstation. The repo can
  keep those files out of Git but cannot prove workstation backup, encryption,
  sharing, or deletion policy. Status: **needs manual verification**.

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
