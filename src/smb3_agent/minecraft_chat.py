"""Minecraft conversation coordinator. Only the worker scheduler executes actions."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import threading
import time
from uuid import uuid4

from smb3_agent.inference_contract import validate_object
from smb3_agent.ai_provider import create_provider
from smb3_agent.minecraft_goals import Goal, identity
from smb3_agent.minecraft_planning import (
    schema as schema,
    TEXT as TEXT,
    INTENT as INTENT,
    PLAN as PLAN,
    BUILD_PLAN as BUILD_PLAN,
    IDLE_PLAN as IDLE_PLAN,
    RULES as RULES,
    build_context,
    distance,
    resolve_movement,
)
from smb3_agent.minecraft_construction import ConstructionGoal, CraftGoal
from smb3_agent.minecraft_bridge import MinecraftBridge
from smb3_agent.minecraft_practice import PracticeServer
from smb3_agent.minecraft_memory import DurableJSON, places, construction, library


class MinecraftChat:
    def __init__(
        self,
        root,
        *,
        provider=None,
        bridge_factory=MinecraftBridge,
        practice_factory=PracticeServer,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.provider = provider or create_provider()
        self.bridge_factory, self.practice_factory = bridge_factory, practice_factory
        self.lock = threading.RLock()
        self.control = threading.Lock()
        self.bridge = self.practice = None
        self.epoch = 0
        self.cancel = threading.Event()
        self.busy = False
        self.stopping = False
        self.stop_failed = False
        self.opened_at_ms = time.time_ns() / 1e6
        self.connecting = False
        self.closed = False
        self.goal = None
        self.active_action = None
        self.activity = "Choose Minecraft to connect."
        self.error = None
        self.home = None
        self.supervisor = None
        self.site_offer = None
        self.places = {}
        self.protections = {}
        self.place_store = DurableJSON(self.root / "places.json", places)
        data = self.place_store.load({"places": {}, "protections": {}})
        self.places, self.protections = data["places"], data["protections"]
        self.construction_store = DurableJSON(
            self.root / "construction.json", construction
        )
        self.construction = self.construction_store.load(None)
        self.library_store = DurableJSON(self.root / "memory.json", library)
        self.memory = self.library_store.load(
            {"schema": 1, "structures": {}, "preferences": {}}
        )
        if (
            self.construction
            and not self.library_store.path.exists()
            and not self.library_store.problem
        ):
            self.memory["structures"][
                self.construction.get("structure_id", self.construction["goal_id"])
            ] = deepcopy(self.construction)
        if self.memory.get("current_id") and not self.construction_store.problem:
            self.construction = deepcopy(
                self.memory["structures"][self.memory["current_id"]]
            )
        self.setup = {}
        self.check_setup()
        self.connection_fault = False
        self.messages = []
        self.seen = set()
        self.events = []
        self.state = {}
        self.threads = []
        self.history = self.root / "conversation.json"
        if self.history.exists():
            try:
                data = json.loads(self.history.read_text())
                self.messages = data["messages"][-500:]
                self.seen = set(data.get("request_ids", []))
                self.activity = "Conversation restored. No work resumed."
            except (OSError, ValueError, KeyError, TypeError):
                self.error = "Conversation could not be read; original file preserved."
                self.history = self.root / f"conversation-recovery-{uuid4().hex}.json"

    def event(self, kind, **data):
        with self.lock:
            row = {"at_ms": time.time_ns() / 1e6, "kind": kind, **data}
            if kind in {"goal_outcome", "construction_outcome", "craft_outcome"}:
                start = next(
                    (
                        e
                        for e in reversed(self.events)
                        if e["kind"] == "goal_started"
                        and e.get("goal_id") == data.get("goal_id")
                    ),
                    {},
                )
                row["request"] = start.get(
                    "request", "Request not retained in current event window"
                )
                row["action"] = start.get("plan", {}).get("action")

            if kind == "construction_outcome":
                row["new_placement_count"] = len(row.get("new_placements", []))
                row["removed_count"] = len(row.get("removed", []))
            self.events.append(row)
            self.events[:] = self.events[-2000:]
            with (self.root / "events.jsonl").open("a") as out:
                out.write(json.dumps(row) + "\n")
            if kind in {
                "construction_outcome",
                "craft_outcome",
                "goal_outcome",
            } and data.get("world"):
                updated = deepcopy(self.memory)
                outcomes = updated.setdefault("outcomes", [])
                outcomes.append(
                    {
                        k: v
                        for k, v in row.items()
                        if k
                        in {
                            "kind",
                            "at_ms",
                            "world",
                            "goal_id",
                            "reason",
                            "complete",
                            "shortfall",
                            "inventory_gains",
                            "inventory_losses",
                            "request",
                            "action",
                            "returned",
                            "broken",
                            "new_placement_count",
                            "removed_count",
                        }
                    }
                )
                outcomes[:] = outcomes[-40:]
                try:
                    self.library_store.save(updated)
                    self.memory = updated
                except (OSError, ValueError) as exc:
                    self.library_store.problem = (
                        "Outcome memory could not be saved; event history preserved. "
                        + str(exc)
                    )
                    self.error = self.library_store.problem

    def message(self, role, text):
        with self.lock:
            self.messages.append(
                {
                    "id": uuid4().hex,
                    "role": role,
                    "text": text,
                    "at_ms": time.time_ns() / 1e6,
                }
            )
            self.messages[:] = self.messages[-500:]
            temp = self.history.with_suffix(".tmp")
            temp.write_text(
                json.dumps(
                    {"messages": self.messages, "request_ids": sorted(self.seen)}
                )
            )
            temp.replace(self.history)

    def spawn(self, fn):
        thread = threading.Thread(target=fn, daemon=True)
        self.threads = [t for t in self.threads if t.is_alive()]
        self.threads.append(thread)
        thread.start()

    def save_places(self):
        self.place_store.save({"places": self.places, "protections": self.protections})

    def memory_status(self):
        return {
            name: {"problem": store.problem, "generations": store.candidates()}
            for name, store in self.memory_stores().items()
        }

    def memory_stores(self):
        return {
            "places": self.place_store,
            "construction": self.construction_store,
            "library": self.library_store,
        }

    def recover_memory(self, name, generation):
        with self.control, self.lock:
            if self.goal or self.busy or self.connecting:
                raise ValueError(
                    "Stop work and wait for reasoning to finish before restoring memory."
                )
            if name not in self.memory_stores():
                raise ValueError("Unknown memory store")
            value = self.memory_stores()[name].restore(generation)
            if name == "places":
                self.places, self.protections = value["places"], value["protections"]
            elif name == "construction":
                self.construction = value
                if not self.library_store.problem:
                    updated = deepcopy(self.memory)
                    updated["structures"][
                        value.get("structure_id", value["goal_id"])
                    ] = deepcopy(value)
                    updated["current_id"] = value.get("structure_id", value["goal_id"])
                    self.library_store.save(updated)
                    self.memory = updated
            else:
                self.memory = value
                if value.get("current_id"):
                    self.construction = deepcopy(
                        value["structures"][value["current_id"]]
                    )
            self.event("memory_restored", store=name, generation=generation)
            self.message(
                "assistant",
                "Saved memory restored; damaged state preserved. No work resumed. Ask me to inspect the site before continuing.",
            )

    def persist_construction(self, record):
        key = record.setdefault("structure_id", record["goal_id"])
        updated = deepcopy(self.memory)
        updated["structures"][key] = deepcopy(record)
        updated["current_id"] = key
        # One canonical commit includes all records and the current selection.
        # A crash before the compatibility mirror cannot split named/latest state.
        self.library_store.save(updated)
        self.memory = updated
        self.construction_store.save(record)

    def remember_resource_constraint(
        self, world, target, reason, *, signature=None, cluster=None
    ):
        with self.lock:
            updated = deepcopy(self.memory)
            scope = json.dumps(world)
            records = updated.setdefault("resource_constraints", {}).setdefault(
                scope, []
            )
            records.append(
                {
                    "target": target,
                    "reason": reason,
                    "at_ms": time.time_ns() / 1e6,
                    "status": "historical failure; reinspection required",
                    "signature": signature,
                    "cluster": cluster,
                }
            )
            records[:] = records[-24:]
            self.library_store.save(updated)
            self.memory = updated

    def remember_details(self, plan, state):
        scope = json.dumps(identity(state))
        name = plan.get("structure_name", "")
        if name:
            if not self.construction or self.construction["world"] != identity(state):
                raise ValueError("No validated structure in this world to name.")
            record = deepcopy(self.construction)
            if any(
                r.get("name") == name
                and r["world"] == record["world"]
                and r.get("structure_id", r["goal_id"])
                != record.get("structure_id", record["goal_id"])
                for r in self.memory["structures"].values()
            ):
                raise ValueError(
                    "That structure name is already used. Choose another name."
                )
            record["name"] = name
            self.persist_construction(record)
            self.construction = record
        if plan.get("preference"):
            updated = deepcopy(self.memory)
            values = updated["preferences"].setdefault(scope, [])
            if plan["preference"] not in values:
                values.append(plan["preference"])
            self.library_store.save(updated)
            self.memory = updated
        return bool(name or plan.get("preference"))

    def check_setup(self):
        from smb3_agent.minecraft_delivery import setup_status

        self.setup = setup_status()
        self.provider.refresh() if hasattr(self.provider, "refresh") else None

    def connect(self, *, survival=False, create=False, accept_eula=False):
        with self.lock:
            if self.closed:
                raise ValueError("Session closed")
            if self.connecting or self.bridge:
                return
            if self.practice_factory is PracticeServer:
                from smb3_agent.minecraft_delivery import (
                    world_home,
                    retained_world,
                    java_runtime,
                    node_runtime,
                )

                home = world_home(survival)
                java_runtime()
                node_runtime()
                if create:
                    if home.exists() and any(home.iterdir()):
                        raise ValueError(
                            "A retained world already exists. Open it or restore its backup; creation will not overwrite it."
                        )
                    if not accept_eula:
                        raise ValueError(
                            "Read and accept the Minecraft EULA before creating a new practice world."
                        )
                else:
                    retained_world(home, survival=survival)
            self.create_world = create
            self.accept_eula = accept_eula
            self.connecting = True
            self.activity = "Opening practice world…"
        self.survival = survival
        self.spawn(self._connect)

    def _connect(self):
        try:
            with self.control:
                if self.closed:
                    return
                self.practice = (
                    self.practice_factory(survival=True)
                    if self.survival
                    else self.practice_factory()
                )
                self.practice.start(
                    accept_eula=True
                ) if self.create_world and self.accept_eula else self.practice.start()
                self.bridge = self.bridge_factory()
                state = self.bridge.connect(world_id=self.practice.world_id)
                with self.lock:
                    self.connection_fault = False
                    self.state = state
                    self.home = state["position"]
                    self.activity = "Ready. Where shall we go?"
                    self.error = None
                self.spawn(self._record_worker)
                self.event("connected", session_id=self.bridge.session_id, state=state)
        except Exception as exc:
            self.error = "Connection failed: " + str(exc)
            self.activity = "Disconnected"
            if self.bridge:
                self.bridge.close()
                self.bridge = None
            if self.practice:
                self.practice.close()
                self.practice = None
        finally:
            self.connecting = False

    def _record_worker(self):
        bridge = self.bridge
        sequence = 0
        while not self.closed and self.bridge is bridge:
            events = bridge.events_after(sequence)
            if events:
                with (self.root / "worker-events.jsonl").open("a") as out:
                    for event in events:
                        out.write(json.dumps(event) + "\n")
                        if event.get("session_id") != bridge.session_id:
                            continue
                        if event["type"] == "state":
                            with self.lock:
                                self.state = event["result"]
                        if event["type"] in {"disconnected", "safety_stopped"}:
                            self.connection_lost(
                                event.get("reason", "Game disconnected")
                            )
                sequence = events[-1]["seq"]
            if bridge.process.poll() is not None:
                self.connection_lost("Minecraft worker exited")
                return
            time.sleep(0.25)

    def connection_lost(self, reason):
        with self.lock:
            if self.connection_fault or self.connecting or self.closed:
                return
            self.connection_fault = True
            self.epoch += 1
            self.cancel.set()
            self.goal = self.supervisor = self.active_action = None
            self.state = {**self.state, "ready": False}
            self.error = (
                reason + ". Reconnect, inspect current state, and give a fresh request."
            )
            self.activity = "Work stopped; no automatic resumption."
            self.event("connection_authority_revoked", reason=reason)
            self.message("assistant", self.error)

    def snapshot(self):
        with self.lock:
            if self.bridge:
                events = self.bridge.events_after()
                latest = next(
                    (
                        e["result"]
                        for e in reversed(events)
                        if e["type"] == "state"
                        and e["session_id"] == self.bridge.session_id
                    ),
                    None,
                )
                if latest:
                    self.state = (
                        {**latest, "ready": False} if self.connection_fault else latest
                    )
                if events and any(
                    e["type"] == "disconnected"
                    and e["session_id"] == self.bridge.session_id
                    for e in events
                ):
                    self.state = {**self.state, "ready": False}
                    if not self.error:
                        self.error = (
                            "Game disconnected. Reconnect to start a fresh session."
                        )
            progress = ""
            if self.goal and self.active_action and self.state.get("active"):
                action, began = self.active_action
                if action["action"] == "move":
                    remaining = self.distance(self.state["position"], action["target"])
                    progress = f"{remaining:.0f} blocks to destination"
                elif action["action"] == "follow":
                    entity = next(
                        (
                            e
                            for e in self.state.get("entities", [])
                            if e["name"] == action["player"]
                        ),
                        None,
                    )
                    left = max(0, 25 - (time.monotonic() - began))
                    progress = f"Tracking · {left:.0f} seconds remaining"
                    if entity:
                        gap = self.distance(self.state["position"], entity["position"])
                        progress += f" · {gap:.0f} blocks from {action['player']}"
            return deepcopy(
                {
                    "setup": self.setup,
                    "session_id": self.bridge.session_id if self.bridge else None,
                    "state": self.state,
                    "messages": self.messages,
                    "goal": self.goal,
                    "activity": self.activity,
                    "progress": progress,
                    "error": self.error
                    or next(
                        (
                            store.problem
                            for store in self.memory_stores().values()
                            if store.problem
                        ),
                        None,
                    ),
                    "busy": self.busy,
                    "stopping": self.stopping,
                    "stop_failed": self.stop_failed,
                    "connecting": self.connecting,
                    "ai": self.provider.status,
                    "usage": self.provider.usage[-20:],
                    "memory": self.memory_status(),
                }
            )

    def authority(self):
        return (
            self.epoch,
            self.bridge.session_id if self.bridge else None,
            self.bridge.revision if self.bridge else None,
        )

    def valid(self, authority, cancel):
        return (
            not self.closed
            and not cancel.is_set()
            and not self.connection_fault
            and self.bridge
            and authority == self.authority()
        )

    def submit(self, text, request_id, session_id):
        text = text.strip()
        if (
            not text
            or len(text) > 2000
            or not isinstance(request_id, str)
            or not 1 <= len(request_id) <= 80
        ):
            raise ValueError("Message is empty or too long")
        with self.lock:
            if request_id in self.seen:
                raise ValueError("Duplicate message")
            if len(self.seen) >= 10000:
                raise ValueError("Conversation request budget reached")
            if (
                self.closed
                or not self.bridge
                or session_id != self.bridge.session_id
                or self.connecting
                or self.connection_fault
            ):
                raise ValueError("Connection changed; reconnect before sending")
            # Explicit emergency shorthand only. Ordinary intent is interpreted by the configured provider.
            direct_stop = text.lower().strip(".! ") in {"stop", "stop now"}
            if (self.stopping or self.stop_failed) and not direct_stop:
                self.event(
                    "request_rejected",
                    request_id=request_id,
                    reason="stop_pending" if self.stopping else "stop_unconfirmed",
                )
                raise ValueError(
                    "Stopping; your draft is retained. Send again after Stop is confirmed."
                    if self.stopping
                    else "Stop is unconfirmed. Your draft is retained; reconnect before sending."
                )
            if not direct_stop and not self.provider.status.get("available"):
                raise ValueError(self.provider.status.get("message") or "AI setup is not ready; check setup before sending.")
            if self.busy and not direct_stop:
                raise ValueError(
                    "The AI is answering. Your draft is retained; send it when ready."
                )
            if not direct_stop and any(
                store.problem for store in self.memory_stores().values()
            ):
                raise ValueError(
                    "Memory needs recovery in Session details before new requests. Stop remains available."
                )
            self.seen.add(request_id)
            self.message("user", text)
            self.event(
                "message", request_id=request_id, text=text, authority=self.authority()
            )
            if direct_stop:
                self.stop()
                return
            self.error = None
            self.busy = True
            cancel = self.cancel = threading.Event()
            authority = self.authority()
        self.spawn(lambda: self._reply(text, authority, cancel))

    def context(self, text, state):
        supervisor = self.supervisor
        progress = (
            None
            if supervisor is None
            else {
                "blocks_broken": supervisor.broken,
                "inventory_gains": dict(supervisor.gained),
                "inventory_losses": dict(supervisor.lost),
                "actions_left": supervisor.remaining,
            }
        )
        return build_context(
            text,
            state,
            memory=self.memory,
            opened_at_ms=self.opened_at_ms,
            goal=self.goal,
            active_goal_id=supervisor.id if supervisor else None,
            site_offer=self.site_offer,
            construction=self.construction,
            places=self.places,
            protections=self.protections,
            home=self.home,
            messages=self.messages,
            events=self.events,
            goal_progress=progress,
        )

    def infer(self, role, context, output, cancel, authority):
        self.event(
            "inference_started",
            role=role,
            authority=authority,
            active=context["observations"].get("active"),
        )
        value = self.provider.infer(role, context, output, cancel)
        validate_object(value, output)
        self.event(
            "inference_returned",
            role=role,
            authority=authority,
            proposal=value,
            usage=self.provider.usage[-1:],
        )
        return value

    def _reply(self, text, authority, cancel):
        started_at = time.monotonic()
        try:
            state = self.bridge.observe()
            idle = not (
                self.goal
                or self.supervisor
                or state.get("active")
                or state.get("queued")
            )
            initial_plan = None
            if idle:
                initial_plan = self.infer(
                    "gameplay", self.context(text, state), IDLE_PLAN, cancel, authority
                )
                action = initial_plan["action"]
                intent = {
                    "kind": action
                    if action in {"question", "stop", "clarify", "unavailable"}
                    else "goal",
                    "reply": initial_plan["reply"],
                }
            else:
                intent = self.infer(
                    "language", self.context(text, state), INTENT, cancel, authority
                )
            with self.lock:
                if not self.valid(authority, cancel):
                    self.event("stale_reply_discarded", authority=authority)
                    return
                if intent["kind"] in {"question", "clarify", "unavailable"}:
                    reply = intent["reply"]
                    current = self.snapshot()["state"]
                    if any(
                        state.get(k) != current.get(k)
                        for k in ("inventory", "held_item", "health", "food")
                    ):
                        reply += (
                            "\nState changed while I was answering. Current held item: "
                            + str(current.get("held_item") or "hand")
                            + "; inventory: "
                            + ", ".join(
                                f"{i['count']} {i['name']}"
                                for i in current.get("inventory", [])
                            )
                            + "."
                        )
                    if state.get("active") and not current.get("active"):
                        reply += (
                            "\nUpdate: that activity ended while I was answering. "
                            + self.activity
                        )
                    self.message("assistant", reply)
                    self.event(
                        "reply",
                        authority=authority,
                        active=self.snapshot()["state"].get("active"),
                    )
                    return
            if intent["kind"] == "stop":
                self.stop()
                return
            if not idle:
                # Transition first. An intent response never receives fresh execution authority.
                with self.control:
                    with self.lock:
                        if not self.valid(authority, cancel):
                            return
                    stopped = self.bridge.stop(session_id=authority[1])
                    with self.lock:
                        if cancel.is_set() or self.epoch != authority[0]:
                            return
                        if not stopped.get("controls_cleared") or not stopped.get(
                            "stopped_observed"
                        ):
                            raise ValueError(
                                "Previous motion cessation unconfirmed; no new goal started"
                            )
                        self.goal = self.supervisor = None
                        authority = self.authority()
                        self.activity = "Planning your destination…"
            # Fresh inference after the revision barrier; never relabel the first proposal.
            for attempt in range(2):
                if initial_plan is not None:
                    plan, initial_plan = initial_plan, None
                else:
                    state = self.bridge.observe()
                    plan = self.infer(
                        "gameplay",
                        self.context(text, state),
                        BUILD_PLAN,
                        cancel,
                        authority,
                    )
                fresh = self.bridge.observe()
                with self.control, self.lock:
                    if not self.valid(authority, cancel):
                        self.event("stale_plan_discarded", authority=authority)
                        return
                    if any(
                        state.get(k) != fresh.get(k)
                        for k in ("world_id", "dimension", "game_version")
                    ):
                        raise ValueError(
                            "World changed while planning; request did not start."
                        )
                    if idle and (
                        self.goal
                        or self.supervisor
                        or fresh.get("active")
                        or fresh.get("queued")
                    ):
                        raise ValueError(
                            "Activity changed while planning; request a fresh goal."
                        )
                    if self.distance(state["position"], fresh["position"]) > 1.5 or any(
                        state.get(k) != fresh.get(k)
                        for k in ("inventory", "health", "food")
                    ):
                        if attempt == 0:
                            continue
                        raise ValueError(
                            "Position changed while planning. Please try again from the current location."
                        )
                    if plan["action"] in {"clarify", "unavailable"}:
                        self.activity = "Ready"
                        self.message("assistant", plan["reply"])
                        return
                    if plan["action"] == "remember" and self.remember_details(
                        plan, fresh
                    ):
                        self.activity = "Memory saved. No construction started."
                        self.message("assistant", self.activity)
                        return
                    if plan["action"] in {
                        "remember",
                        "return",
                        "gather",
                        "build",
                        "craft",
                        "protect",
                        "visit",
                    }:
                        supervisor = (
                            ConstructionGoal
                            if plan["action"] == "build"
                            else CraftGoal
                            if plan["action"] == "craft"
                            else Goal
                        )(self, plan, fresh, authority, started_at=started_at)
                        if plan["protect_place"]:
                            name = plan["protect_place"]
                            if name == plan["remember"]:
                                center = fresh["position"]
                            else:
                                center = supervisor.place(name, fresh)
                            if not 1 <= plan["protect_radius"] <= 32:
                                raise ValueError(
                                    "Specify a protection radius of 1–32 blocks."
                                )
                            region = {
                                "center": center,
                                "radius": plan["protect_radius"],
                            }
                            if len(supervisor.regions) >= 16:
                                raise ValueError("Protected area limit reached")
                            supervisor.regions.append(region)
                            self.protections[json.dumps(identity(fresh))] = (
                                supervisor.regions
                            )
                            self.save_places()
                        self.supervisor = supervisor
                        self.goal = text
                        self.message("assistant", plan["reply"])
                        self.event(
                            "goal_started",
                            request=text,
                            goal_id=supervisor.id,
                            authority=authority,
                            plan=plan,
                            deadline_seconds=900
                            if plan["action"] in {"build", "craft"}
                            else 240,
                            actions=supervisor.remaining,
                        )
                        self.spawn(supervisor.run)
                        return
                    action = self.resolve(plan, fresh)
                    regions = self.protections.get(
                        json.dumps(
                            [
                                fresh.get("world_id"),
                                fresh.get("dimension"),
                                fresh.get("game_version"),
                            ]
                        ),
                        [],
                    )
                    if regions:
                        action["protected"] = regions
                    rid, future = self.bridge.submit(
                        "execute",
                        action,
                        timeout_ms=29000,
                        session_id=authority[1],
                        revision=authority[2],
                    )
                    self.goal = text
                    self.active_action = (action, time.monotonic())
                    self.activity = (
                        "Following " + plan["player"]
                        if plan["action"] == "follow"
                        else "Walking to your destination"
                    )
                    self.message("assistant", plan["reply"])
                    self.event(
                        "action_submitted",
                        authority=authority,
                        request_id=rid,
                        action=action,
                        before=fresh["position"],
                    )
                    self.spawn(lambda: self._outcome(future, authority, rid))
                    return
        except Exception as exc:
            with self.lock:
                if self.valid(authority, cancel):
                    self.error = str(exc)
                    self.message("assistant", str(exc))
                    if not self.goal:
                        self.activity = "Ready; request did not start"
                    self.event("request_failed", error=str(exc))
        finally:
            with self.lock:
                if self.cancel is cancel:
                    self.busy = False

    # Preserve the existing coordinator API; geometry owns no session state.
    distance = staticmethod(distance)

    def resolve(self, plan, state):
        return resolve_movement(plan, state, places=self.places, home=self.home)

    def _outcome(self, future, authority, rid):
        try:
            result = future.result(timeout=34)
            text = (
                "Arrived; position verified."
                if result.get("observed") == "position"
                else "Follow interval finished; tracking stopped."
            )
        except Exception as exc:
            result = {"error": str(exc)}
            text = "Movement ended: " + str(exc)
        with self.lock:
            self.event(
                "action_result", request_id=rid, result=result, authority=authority
            )
            if self.bridge and authority == self.authority() and not self.closed:
                self.goal = None
                self.activity = text
                self.message("assistant", text)

    def stop(self):
        with self.lock:
            if self.stopping:
                self.event("stop_coalesced")
                return
            self.stopping = True
            self.stop_failed = False
            self.epoch += 1
            epoch, bridge = self.epoch, self.bridge
            self.cancel.set()
            self.goal = self.supervisor = None
            self.activity = (
                "Stopping — new requests are blocked; your draft is retained."
            )
            self.event("stop_requested")
        self.spawn(lambda: self._stop(epoch, bridge))

    def _stop(self, epoch, bridge):
        try:
            with self.control:
                result = bridge.stop() if bridge and bridge.session_id else {}
                self.event("stop_completed", result=result)
                with self.lock:
                    if self.epoch != epoch or self.bridge is not bridge:
                        return
                    confirmed = result.get("controls_cleared") and result.get(
                        "stopped_observed"
                    )
                    self.stopping = False
                    self.stop_failed = not confirmed
                    self.activity = (
                        "Stopped — stationary position observed. You may send a new request."
                        if confirmed
                        else "Stop unconfirmed — reconnect before sending a new request."
                    )
                    if not confirmed:
                        self.error = self.activity
        except Exception as exc:
            with self.lock:
                if self.epoch == epoch and self.bridge is bridge:
                    self.stopping = False
                    self.stop_failed = True
                    self.error = (
                        "Stop unconfirmed: " + str(exc) + ". Reconnect before sending."
                    )

    def reconnect(self):
        with self.lock:
            if not self.bridge:
                self.connect(survival=getattr(self, "survival", False))
                return
            if self.connecting:
                return
            self.epoch += 1
            self.cancel.set()
            self.goal = self.supervisor = None
            self.connecting = True
            self.connection_fault = True
            self.state = {**self.state, "ready": False}
            self.activity = "Reconnecting; no work will resume…"

        def run():
            try:
                with self.control:
                    if self.bridge:
                        if (
                            self.practice
                            and self.practice.process
                            and self.practice.process.poll() is not None
                        ):
                            home = self.practice.home
                            from smb3_agent.minecraft_delivery import retained_world

                            retained_world(
                                home,
                                expected_id=self.practice.world_id,
                                survival=getattr(self.practice, "survival", None),
                            )
                            self.practice.close()
                            self.practice.start()
                        if (
                            hasattr(self.bridge, "process")
                            and self.bridge.process.poll() is not None
                        ):
                            self.bridge.close()
                            self.bridge = self.bridge_factory()
                            state = self.bridge.connect(world_id=self.practice.world_id)
                            self.spawn(self._record_worker)
                        else:
                            state = self.bridge.reconnect(
                                expected_session_id=self.bridge.session_id
                            )
                        with self.lock:
                            self.connection_fault = False
                            self.stopping = self.stop_failed = False
                            self.state, self.home = state, state["position"]
                            self.activity, self.error = (
                                "Reconnected. No work resumed.",
                                None,
                            )
                        self.event("reconnected", session_id=self.bridge.session_id)
            except Exception as exc:
                self.error = "Reconnect failed: " + str(exc)
                self.activity = "Disconnected; reconnect did not complete."
                self.event("reconnect_failed", error=str(exc))
            finally:
                self.connecting = False

        self.spawn(run)

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.epoch += 1
            self.cancel.set()
        with self.control:
            if self.bridge:
                self.bridge.close()
            if self.practice:
                self.practice.close()
