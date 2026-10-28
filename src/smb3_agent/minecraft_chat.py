"""Minecraft conversation coordinator. Only the worker scheduler executes actions."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import threading
import time
from uuid import uuid4

from smb3_agent.codex_provider import CodexProvider, validate_object
from smb3_agent.minecraft_goals import Goal, identity
from smb3_agent.minecraft_bridge import MinecraftBridge
from smb3_agent.minecraft_practice import PracticeServer


def schema(properties):
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


TEXT = {"type": "string", "maxLength": 1400}
INTENT = schema(
    {
        "kind": {
            "type": "string",
            "enum": ["question", "goal", "replace", "stop", "clarify", "unavailable"],
        },
        "reply": TEXT,
    }
)
PLAN = schema(
    {
        "action": {
            "type": "string",
            "enum": [
                "move",
                "follow",
                "remember",
                "return",
                "gather",
                "protect",
                "visit",
                "clarify",
                "unavailable",
            ],
        },
        "reply": TEXT,
        "direction": {
            "type": "string",
            "enum": [
                "north",
                "south",
                "east",
                "west",
                "forward",
                "back",
                "left",
                "right",
                "player",
                "home",
                "none",
            ],
        },
        "distance": {"type": "integer", "minimum": 0, "maximum": 30},
        "player": {"type": "string", "maxLength": 32},
        "remember": {"type": "string", "maxLength": 40},
        "return_place": {"type": "string", "maxLength": 40},
        "resource": {
            "type": "string",
            "enum": [
                "any_log",
                "oak_log",
                "birch_log",
                "spruce_log",
                "jungle_log",
                "acacia_log",
                "dark_oak_log",
                "mangrove_log",
                "cherry_log",
                "pale_oak_log",
                "none",
            ],
        },
        "quantity": {"type": "integer", "minimum": 0, "maximum": 32},
        "quantity_mode": {"type": "string", "enum": ["additional", "total"]},
        "protect_place": {"type": "string", "maxLength": 40},
        "protect_radius": {"type": "integer", "minimum": 0, "maximum": 32},
    }
)
RULES = """Minecraft 1.21.4 practice companion. Answer naturally and concisely from observations.
Distinguish a question (even during active play) from a new goal or replacement, Stop,
ambiguity, and unsupported requests. Questions NEVER change gameplay. Supported: walk
up to 30 blocks in cardinal/bot-relative directions, to saved places, or toward
an observed player; follow an observed player for up to 25 seconds within 32 blocks.
Do not claim already executed actions. No building, crafting or teleporting.
Visit an observed nearby tree with action=visit and its resource type; this only approaches it.
Supported multi-step actions: remember current spot (remember=name); return to saved
place (return_place=name); gather 1–32 common logs (resource=exact log name or any_log,
quantity, quantity_mode=additional by default, total only when explicitly requested).
Gather may remember the current spot and return to it in the same goal. Use action=gather.
Tools are selected from inventory; logs can validly use hand. Never call tools yourself.
Protected areas are cylinders around explicitly named saved places (protect_place,
protect_radius), retained for this world; action=protect can save them without gathering.
If 'those trees', 'by the house', or a boundary is ambiguous, clarify which saved place
and radius the user means BEFORE any work. Never invent a protected boundary.
A new remembered current spot can anchor protection. All unused string fields are empty
except resource=none, quantity=0, quantity_mode=additional, protect_radius=0.
Use observed resource variants; unavailable resources give honest partial outcomes.
Gathering is a multi-skill goal with 240 seconds/80 child actions/3 failures/32-block bounds.
If a request needs a tool we cannot supply, explain that crafting is not available.
Saved places must match current world and dimension; movement to saved places uses return.
Ordinary questions about progress do not replace a goal.
If 'me' is ambiguous ask which observed player. Player names must come from entities,
not just the player roster. Unknown landmarks need clarification. History is context,
not permission to resume. Only the latest user request grants intent. Never use tools.
For a plan use one direction plus distance (default 10 if unspecified). Follow uses
player and direction=player. Return clarify/unavailable when a destination is unknown.
"""


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
        self.provider = provider or CodexProvider(timeout=60, retries=0)
        self.bridge_factory, self.practice_factory = bridge_factory, practice_factory
        self.lock = threading.RLock()
        self.control = threading.Lock()
        self.bridge = self.practice = None
        self.epoch = 0
        self.cancel = threading.Event()
        self.busy = False
        self.connecting = False
        self.closed = False
        self.goal = None
        self.active_action = None
        self.activity = "Choose Minecraft to connect."
        self.error = None
        self.home = None
        self.supervisor = None
        self.places = {}
        self.protections = {}
        memory = self.root / "places.json"
        if memory.exists():
            data = json.loads(memory.read_text())
            self.places = data.get("places", {})
            self.protections = data.get("protections", {})
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
            self.events.append(row)
            self.events[:] = self.events[-2000:]
            with (self.root / "events.jsonl").open("a") as out:
                out.write(json.dumps(row) + "\n")

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
        temp = self.root / "places.tmp"
        temp.write_text(
            json.dumps({"places": self.places, "protections": self.protections})
        )
        temp.replace(self.root / "places.json")

    def connect(self, *, survival=False):
        with self.lock:
            if self.closed:
                raise ValueError("Session closed")
            if self.connecting or self.bridge:
                return
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
                self.practice.start()
                self.bridge = self.bridge_factory()
                state = self.bridge.connect(world_id=self.practice.world_id)
                with self.lock:
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
        sequence = 0
        while not self.closed and self.bridge:
            events = self.bridge.events_after(sequence)
            if events:
                with (self.root / "worker-events.jsonl").open("a") as out:
                    for event in events:
                        out.write(json.dumps(event) + "\n")
                sequence = events[-1]["seq"]
            time.sleep(0.25)

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
                    self.state = latest
                if events and any(
                    e["type"] == "disconnected"
                    and e["session_id"] == self.bridge.session_id
                    for e in events
                ):
                    self.state = {**self.state, "ready": False}
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
                    "session_id": self.bridge.session_id if self.bridge else None,
                    "state": self.state,
                    "messages": self.messages,
                    "goal": self.goal,
                    "activity": self.activity,
                    "progress": progress,
                    "error": self.error,
                    "busy": self.busy,
                    "connecting": self.connecting,
                    "codex": self.provider.status,
                    "usage": self.provider.usage[-20:],
                }
            )

    def authority(self):
        return (self.epoch, self.bridge.session_id, self.bridge.revision)

    def valid(self, authority, cancel):
        return (
            not self.closed
            and not cancel.is_set()
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
            ):
                raise ValueError("Connection changed; reconnect before sending")
            # Explicit emergency shorthand only. Ordinary intent is always Codex interpreted.
            direct_stop = text.lower().strip(".! ") in {"stop", "stop now"}
            if self.busy and not direct_stop:
                raise ValueError(
                    "Codex is answering. Your draft is retained; send it when ready."
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
        return {
            "instructions": RULES,
            "request": text,
            "observations": {**state, "resources": state.get("resources", [])[:24]},
            "active_goal": self.goal,
            "named_places": self.places,
            "protected_areas": self.protections,
            "session_start": self.home,
            "recent_conversation": [
                {"role": m["role"], "text": m["text"][:1000]}
                for m in self.messages[-10:]
            ],
            "recent_results": [
                e
                for e in self.events
                if e["kind"] in {"goal_outcome", "goal_recovery", "action_result"}
            ][-3:],
            "goal_progress": (
                {
                    "blocks_broken": self.supervisor.broken,
                    "inventory_gains": dict(self.supervisor.gained),
                    "inventory_losses": dict(self.supervisor.lost),
                    "actions_left": self.supervisor.remaining,
                }
                if self.supervisor
                else None
            ),
        }

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
                state = self.bridge.observe()
                plan = self.infer(
                    "gameplay", self.context(text, state), PLAN, cancel, authority
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
                    if self.distance(state["position"], fresh["position"]) > 1.5:
                        if attempt == 0:
                            continue
                        raise ValueError(
                            "Position changed while planning. Please try again from the current location."
                        )
                    if plan["action"] in {"clarify", "unavailable"}:
                        self.activity = "Ready"
                        self.message("assistant", plan["reply"])
                        return
                    if plan["action"] in {
                        "remember",
                        "return",
                        "gather",
                        "protect",
                        "visit",
                    }:
                        supervisor = Goal(
                            self, plan, fresh, authority, started_at=started_at
                        )
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
                            goal_id=supervisor.id,
                            authority=authority,
                            plan=plan,
                            deadline_seconds=240,
                            actions=80,
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

    @staticmethod
    def distance(a, b):
        return math.sqrt(sum((a[k] - b[k]) ** 2 for k in ("x", "y", "z")))

    def resolve(self, plan, state):
        p = state["position"]
        entities = {e["name"]: e for e in state.get("entities", [])}
        if plan["action"] == "follow" or plan["direction"] == "player":
            entity = entities.get(plan["player"])
            if not entity or self.distance(p, entity["position"]) > 32:
                raise ValueError(
                    "That player is not observed within 32 blocks. Move closer or name a visible player."
                )
            if plan["action"] == "follow":
                return {
                    "action": "follow",
                    "player": plan["player"],
                    "entity_id": entity["id"],
                    "duration_ms": 25000,
                }
            target = entity["position"]
        elif plan["direction"] == "home":
            place = self.places.get("home")
            if place and place["world"] != identity(state):
                raise ValueError("Home belongs to another world/dimension.")
            target = place["position"] if place else self.home
        else:
            d = plan["distance"]
            if not 1 <= d <= 30:
                raise ValueError("Choose a walking distance between 1 and 30 blocks.")
            yaw = state.get("yaw", 0)
            vectors = {
                "north": (0, -1),
                "south": (0, 1),
                "east": (1, 0),
                "west": (-1, 0),
                "forward": (-math.sin(yaw), -math.cos(yaw)),
                "back": (math.sin(yaw), math.cos(yaw)),
                "left": (math.cos(yaw), -math.sin(yaw)),
                "right": (-math.cos(yaw), math.sin(yaw)),
            }
            if plan["direction"] not in vectors:
                raise ValueError(
                    "Please name a direction, home, or an observed player."
                )
            x, z = vectors[plan["direction"]]
            target = {"x": p["x"] + d * x, "y": p["y"], "z": p["z"] + d * z}
        if self.distance(p, target) > 32:
            raise ValueError(
                "Destination is beyond this session's 32-block movement limit."
            )
        return {"action": "move", "target": target}

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
            self.epoch += 1
            self.cancel.set()
            self.goal = self.supervisor = None
            self.activity = "Stopping…"
            self.event("stop_requested")
        self.spawn(self._stop)

    def _stop(self):
        try:
            with self.control:
                result = (
                    self.bridge.stop() if self.bridge and self.bridge.session_id else {}
                )
                self.event("stop_completed", result=result)
                self.activity = (
                    "Stopped — stationary position observed."
                    if result.get("stopped_observed")
                    else "No active connection; cessation unconfirmed."
                )
        except Exception as exc:
            self.error = "Stop unconfirmed: " + str(exc)

    def reconnect(self):
        with self.lock:
            if not self.bridge:
                self.connect()
                return
            if self.connecting:
                return
            self.epoch += 1
            self.cancel.set()
            self.goal = self.supervisor = None
            self.connecting = True
            self.activity = "Reconnecting; no work will resume…"

        def run():
            try:
                with self.control:
                    if self.bridge:
                        state = self.bridge.reconnect(
                            expected_session_id=self.bridge.session_id
                        )
                        with self.lock:
                            self.state, self.home = state, state["position"]
                            self.activity, self.error = (
                                "Reconnected. No work resumed.",
                                None,
                            )
                        self.event("reconnected", session_id=self.bridge.session_id)
            except Exception as exc:
                self.error = "Reconnect failed: " + str(exc)
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
