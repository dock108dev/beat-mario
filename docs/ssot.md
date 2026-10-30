# Module ownership

Each boundary has one authority. Presentation and saved records must not duplicate
permission, eligibility or execution policy.

Ordinary Minecraft, Mario and Stardew conversations receive the same provider
instance from `lab_ui.py`. `ai_provider.py` owns configuration and selection;
both accepted local provider names select `LocalHTTPProvider` in
`http_inference.py`. There is no CLI or hosted-chat fallback. Direct Minecraft
service construction uses that same factory only when no provider is injected.
An explicitly injected provider is retained even when it reports unavailable or
evaluates as false; construction never silently replaces it.
`tests/test_ai_provider.py` checks both names against the shared transport, and
`tests/test_provider_ownership.py` verifies one shared instance across the three
conversation services and standalone Minecraft factory selection. It also guards
shipped project text and filenames (including binary asset names) against retired
provider branding, and checks that production transport construction stays in the
provider factory. Ignored
runtime data and third-party dependencies are outside that source check.

| Domain | Authoritative module | Boundary |
|---|---|---|
| Minecraft session/action admission | `minecraft_chat.py` | Session/revision checks, inference, Stop and late-result rejection |
| Model contracts/context | `minecraft_planning.py` | Pure schemas, history filtering and movement geometry; no I/O or authority |
| World paths/eligibility | `minecraft_delivery.py` | Dynamic profile paths, game version and retained-world validation |
| Practice server | `minecraft_practice.py` | Java server lifecycle; uses delivery eligibility |
| Worker transport | `minecraft_bridge.py` | Replies, futures and events; canceling a Future is not gameplay Stop |
| Minecraft execution | `minecraft-worker/worker.cjs` and scheduler | Sole owner of headless actions; server-confirmed effects |
| Resource/construction goals | `minecraft_goals.py`, `minecraft_construction.py` | Bounded goals under coordinator authority |
| World brief/design/reference data | `minecraft_design.py` | Versions and reference blobs in the existing project database; called only through chat admission; no separate executor |
| Design requirements and provenance | `minecraft_requirements.py` | Pure parsing, constrained proposals and independent requirement checks; design persistence stays in `minecraft_design.py` |
| Architecture geometry and objects | `minecraft_architecture.py` | Pure terrain-bound compilation; reviews and execution remain owned by `minecraft_build.py` |
| Terrain geometry | `minecraft_terrain.py` | Pure compilation from retained requirements; manifests and execution remain owned by `minecraft_build.py` |
| Creative project transactions | `minecraft_build.py` | World/region identity, persisted designs, intents, verified receipts and explicit continuation; invoked by `minecraft_chat.py` |
| Creative state validation/execution | `minecraft-worker/build-service.cjs` | Registry-backed typed operations called only by the worker scheduler; no raw model commands |
| Delivery directory activation | `directory_migration.py` | Restartable hash-verified copy activation; called by the delivery migration script |
| Durable companion JSON | `minecraft_memory.py` | Validation, replacement, generation retention and explicit recovery |
| Minecraft presentation | `minecraft_chat_ui.py`, `minecraft_chat_script.py` | Document/styles and separately served script |
| Shared legacy page presentation | `lab_page.py`, `lab_page_styles.py`, `player_workspace_script.py` | Pure document/CSRF form rendering, ordered styles and browser refresh; no session authority |
| HTTP composition | `lab_ui.py` | Loopback routes, CSRF, service composition and asset serving |
| Desktop lifecycle | `app_runtime.py`, `delivery.py` | Entry point, owned processes and shutdown |
| AI configuration and selection | `ai_provider.py` | Shared factory for all ordinary game conversations; explicit local settings or unavailable |
| Local inference transport | `http_inference.py` | Model discovery, bounded HTTP requests, streaming, cancellation and usage |
| Model result validation | `inference_contract.py` | Closed-schema validation shared by Minecraft, Mario and Stardew |
| Engineering task packets | `lab.py` | Packet generation used by CLI/HTTP; `route_patch.py` validates reviewed proposals |

`memory.json` owns named structures and current selection. `construction.json` is
a compatibility mirror, not an independent source. Places/protections and conversation
have separate validated snapshots. Java world files remain server-owned. The
coordinator serializes writes; stored facts never restore live action authority.

## Older integrations

Mario controller/runtime modules own emulator execution and observations; its
conversation service owns volatile request/review state. Stardew runtime and
conversation services keep their own input authority, copied-save safety and
accounting. Shared language/provider code does not combine these authority owners.
Profile-based adapters and native Minecraft calibration are separate from headless
Minecraft eligibility. Disabled native activities still have setup/API callers;
removal must update those interfaces and declarations together.

`release_resources.py` owns packaged resource inventory and relocation. `paths.py`
and delivery helpers distinguish immutable resources from writable data. Route
patching owns reviewed source mutation and integrity checks. Goal, scenario,
unattended and reliability contracts retain their real schema/API versions.

See [architecture](agent-architecture.md), [runtime configuration](runtime-and-configuration.md)
and [development boundaries](development.md#module-boundaries).


## Enforced preview and delivery boundaries

Domain: Small component preview eligibility.
SSOT module/file: `minecraft_design.py::preview_problem`.
Why this is authoritative: it evaluates the compiled box used by
`WorldDesign.compile_component`, preserving the existing platform/pavilion and
footprint/height limits. `snapshot().preview_components` is derived from this same
rule on each read; it is not persisted permission.
Known callers: `WorldDesign.snapshot`, `WorldDesign.compile_component`, and
`minecraft_chat_script.py` through the snapshot. The browser uses the supplied
names for its menu, availability and preview-support text; it no longer implements
three separate size/kind policies. Missing choices disable the preview rather than
reconstructing eligibility locally. Session, planning, region, inspection and review
checks remain with their existing backend owners.

Domain: Retained-world directory naming.
SSOT module/file: `minecraft_delivery.py::world_directory` and `GAME_VERSION`.
Why this is authoritative: `world_home` adds the selected data root to this name;
the delivery migration uses the same name without consulting the active profile.
Known callers: `world_home` (practice server and setup), and
`scripts/migrate_minecraft_delivery.py`. The migration no longer pins a second
copy of the game version in its directory list. This does not authorize migration
or change the installed world version.

The construction snapshot mirror remains required by legacy-memory import,
recovery and delivery validation; `memory.json` remains the named-library owner.
Both accepted provider names remain supported configuration inputs to one factory
and transport. Neither is an alternate inference implementation.
Native Minecraft execution retirement is deferred: `player_setup.py`,
`minecraft_session.py` and `camera_practice.py` still reference its runtime,
limits and input owner. A separate removal must preserve supported calibration
and inspection responses while deleting disabled action declarations, executors
and their tests together. Disabled native gameplay is not newly supported.
