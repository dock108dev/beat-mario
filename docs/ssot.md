# Module ownership

Each boundary has one authority. Presentation and saved records must not duplicate
permission, eligibility or execution policy.

| Domain | Authoritative module | Boundary |
|---|---|---|
| Minecraft session/action admission | `minecraft_chat.py` | Session/revision checks, inference, Stop and late-result rejection |
| Model contracts/context | `minecraft_planning.py` | Pure schemas, history filtering and movement geometry; no I/O or authority |
| World paths/eligibility | `minecraft_delivery.py` | Dynamic profile paths, game version and retained-world validation |
| Practice server | `minecraft_practice.py` | Java server lifecycle; uses delivery eligibility |
| Worker transport | `minecraft_bridge.py` | Replies, futures and events; canceling a Future is not gameplay Stop |
| Minecraft execution | `minecraft-worker/worker.cjs` and scheduler | Sole owner of headless actions; server-confirmed effects |
| Resource/construction goals | `minecraft_goals.py`, `minecraft_construction.py` | Bounded goals under coordinator authority |
| Durable companion JSON | `minecraft_memory.py` | Validation, replacement, generation retention and explicit recovery |
| Minecraft presentation | `minecraft_chat_ui.py`, `minecraft_chat_script.py` | Document/styles and separately served script |
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
