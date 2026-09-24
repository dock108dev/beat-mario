# B2 implementation ownership and seams

B2 engineering completed on the exact retained candidate recorded in `artifacts/b2-engineering/20260924T010558Z/B2-handoff.md`. The ownership list below records that implementation. Current B3 interfaces are in [B3 integration contract](b3-integration-contract.md). No owner verdict is inferred.

- Planning agent owns `request_planning.py`, `mario_route_plan.py`, `stardew_planning.py` and matching new tests. Typed JSON-serializable plans expose request/conversation/game/session/observation identity; original objective, normalized intent, real base route, revision/parent; typed actions and preconditions/outcomes; protection/resources/stop/effective boundary; speed; eligibility/evidence/authority. Pure planning never emits input.
- Runtime agent owns `mario_plan_runtime.py`, the Python/Lua control seams in `live_observation.py`, `takeover.py`, `fceux_live_takeover.lua`, `fceux_1_1_agent.lua`, any new Lua controller file and matching runtime tests. It validates adapter-owned primitives, process/session/state, revisions and commands independently of planner claims.
- Interface agent owns `conversation_ui.py`, integration edits in `lab_ui.py` and matching browser/render tests. Keep planner/execution logic in their modules and expose ordinary `/mario` conversation with stable draft/focus, persistent control and visible revision/speed/outcome.
- Lead owns `conversation_service.py`, `custom_variants.py`, beta readiness/scenario additions, remaining tests, tracker/docs, final review and isolated integration evidence.

Integration surface: UI calls `ConversationService(live_manager, artifacts_root=...)`; `snapshot()` yields JSON-safe state; `dispatch(action, payload)` yields JSON-safe state or raises ValueError. Actions: select_intent, message, start, apply, cancel_pending, revert, speed, pause, resume, stop, reclaim, save_variant, load_variant. No endpoint starts or resets an emulator implicitly; existing explicit launch remains. Service shares the server live manager.

Runtime design and exact typed planner API are communicated by owners before integration. Runtime must offer snapshot/start/edit/cancel/control operations and never rely on stored or planner-supplied execution authority. UI treats returned plan/runtime dictionaries as presentation data, text only. CSRF and loopback protections remain mandatory.
