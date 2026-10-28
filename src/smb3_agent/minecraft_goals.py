"""Bounded composition over the existing worker scheduler; never owns inputs."""

from collections import Counter
from copy import deepcopy
import json
import math
import time
from uuid import uuid4

LOGS = [
    n + "_log"
    for n in (
        "oak",
        "birch",
        "spruce",
        "jungle",
        "acacia",
        "dark_oak",
        "mangrove",
        "cherry",
        "pale_oak",
    )
]


def inventory(state):
    result = Counter()
    for item in state.get("inventory", []):
        result[item["name"]] += item["count"]
    return result


def identity(state):
    key = [state.get("world_id"), state.get("dimension"), state.get("game_version")]
    if not all(key) or key[0] == "unknown":
        raise ValueError(
            "World identity unavailable; reconnect before using saved places."
        )
    return key


def protected(position, regions):
    return any(
        math.hypot(position["x"] - r["center"]["x"], position["z"] - r["center"]["z"])
        <= r["radius"]
        for r in regions
    )


class Goal:
    def __init__(self, chat, plan, state, authority, *, started_at=None):
        self.chat, self.plan, self.authority = chat, plan, authority
        self.id = uuid4().hex
        self.world = identity(state)
        self.origin = deepcopy(state["position"])
        self.deadline = (time.monotonic() if started_at is None else started_at) + 240
        self.remaining = 80
        self.failures = 0
        self.broken = 0
        self.drops = set()
        self.initial = self.last = inventory(state)
        self.gained = Counter()
        self.lost = Counter()
        self.skipped = set()
        self.regions = deepcopy(chat.protections.get(json.dumps(self.world), []))
        self.resource = plan["resource"]
        self.names = LOGS if self.resource == "any_log" else [self.resource]
        self.quantity = plan["quantity"]
        self.needed = (
            self.quantity
            if plan["quantity_mode"] == "additional"
            else max(0, self.quantity - self.count(self.initial))
        )
        self.destination = None

    def count(self, items):
        return sum(items[n] for n in self.names)

    def check(self, state=None):
        if (
            self.chat.closed
            or not self.chat.bridge
            or self.authority != self.chat.authority()
            or self.chat.supervisor is not self
        ):
            raise ValueError("Goal canceled or replaced")
        if time.monotonic() >= self.deadline or self.remaining <= 0:
            raise ValueError("Goal deadline/action budget reached")
        if (
            state is not None
            and self.chat.distance(self.origin, state["position"]) > 32
        ):
            raise ValueError("Goal distance limit reached")
        if state is not None and (
            not state.get("ready") or identity(state) != self.world
        ):
            raise ValueError("World changed; goal cannot continue")

    def observe(self):
        self.check()
        state = self.chat.bridge.observe()
        self.check(state)
        now = inventory(state)
        self.gained.update(now - self.last)
        self.lost.update(self.last - now)
        self.last = now
        self.drops.update(
            d["id"] for d in state.get("drops", []) if d.get("item") in self.names
        )
        return state

    def child(self, action):
        with self.chat.control, self.chat.lock:
            self.check()
            if (
                "target" in action
                and self.chat.distance(self.origin, action["target"]) > 32
            ):
                raise ValueError("Target outside goal distance budget")
            self.remaining -= 1
            timeout = min(15000, int((self.deadline - time.monotonic()) * 1000))
            if timeout < 100:
                raise ValueError("Goal deadline reached")
            action = {
                **action,
                "protected": self.regions,
                "goal_id": self.id,
                "world": self.world,
                "goal_origin": self.origin,
            }
            rid, future = self.chat.bridge.submit(
                "execute",
                action,
                timeout_ms=timeout,
                session_id=self.authority[1],
                revision=self.authority[2],
            )
            self.chat.active_action = (action, time.monotonic())
            self.chat.activity = f"{action['action'].capitalize()} · {self.count(self.gained)} collected, {self.broken} blocks broken"
            self.chat.event(
                "goal_child",
                goal_id=self.id,
                authority=self.authority,
                request_id=rid,
                remaining=self.remaining,
                action=action,
            )
        result = future.result(timeout=timeout / 1000 + 4)
        self.check()
        self.chat.event(
            "goal_child_result", goal_id=self.id, request_id=rid, result=result
        )
        self.observe()
        return result

    def place(self, name, state):
        place = self.chat.places.get(name)
        if not place or place["world"] != self.world:
            raise ValueError(
                f"Place '{name}' is missing or belongs to another world/dimension."
            )
        if self.chat.distance(state["position"], place["position"]) > 32:
            raise ValueError(
                f"Place '{name}' is beyond the 32-block goal area; move closer first."
            )
        # Worker rechecks current terrain/hazards and path, never trusts stored reachability.
        return place["position"]

    def run(self):
        reason = ""
        returned = False
        try:
            state = self.observe()
            if self.plan["remember"]:
                with self.chat.control, self.chat.lock:
                    self.check(state)
                    self.chat.places[self.plan["remember"]] = {
                        "world": self.world,
                        "position": state["position"],
                    }
                    self.chat.save_places()
            if self.plan["return_place"]:
                self.destination = self.place(self.plan["return_place"], state)
            if self.plan["action"] == "remember":
                if not self.plan["remember"]:
                    raise ValueError("Specify the name to remember.")
                reason = "Place saved with this world's identity."
            elif self.plan["action"] == "return":
                if not self.destination:
                    raise ValueError("Name a saved destination.")
            elif self.plan["action"] == "protect":
                reason = "Protected area saved for this world."
            elif self.plan["action"] == "visit":
                candidates = [
                    b
                    for b in state.get("resources", [])
                    if b["name"] in self.names
                    and not protected(b["position"], self.regions)
                ]
                if not candidates:
                    raise ValueError("No matching unprotected tree observed nearby.")
                target = min(
                    candidates,
                    key=lambda b: self.chat.distance(state["position"], b["position"]),
                )
                self.child({"action": "approach", "target": target["position"]})
                reason = "Reached an observed tree without modifying it."
            elif self.plan["action"] == "gather":
                if (
                    self.resource not in LOGS + ["any_log"]
                    or not 1 <= self.quantity <= 32
                ):
                    raise ValueError(
                        "Choose 1–32 common logs; crafting and other materials are not available yet."
                    )
                self.chat.message(
                    "assistant",
                    f"Starting with {self.count(self.initial)} matching logs. Collecting {self.needed} additional logs ({self.plan['quantity_mode']} request).",
                )
                while self.count(self.last) - self.count(self.initial) < self.needed:
                    state = self.observe()
                    if self.broken >= self.needed + 2:
                        raise ValueError(
                            "Block budget exhausted without requested inventory gain"
                        )
                    candidates = [
                        b
                        for b in state.get("resources", [])
                        if b["name"] in self.names
                        and not protected(b["position"], self.regions)
                        and tuple(b["position"].values()) not in self.skipped
                        and math.floor(state["position"]["y"])
                        <= b["position"]["y"]
                        <= math.floor(state["position"]["y"]) + 3
                        and self.chat.distance(state["position"], b["position"]) <= 30
                    ]
                    candidates.sort(
                        key=lambda b: self.chat.distance(
                            state["position"], b["position"]
                        )
                    )
                    if not candidates:
                        raise ValueError(
                            "No matching unprotected reachable candidates observed within 30 blocks. Move closer to another tree or choose another resource."
                        )
                    block = candidates[0]
                    target = block["position"]
                    prior_count = self.count(self.last)
                    self.skipped.add(tuple(target.values()))
                    try:
                        self.child({"action": "approach", "target": target})
                        tool = self.child(
                            {
                                "action": "equip",
                                "target": target,
                                "expected": block["name"],
                            }
                        )
                        self.chat.event("goal_tool", goal_id=self.id, result=tool)
                        result = self.child(
                            {
                                "action": "dig",
                                "target": target,
                                "expected": block["name"],
                            }
                        )
                        if result.get("observed") != "server_block_change":
                            raise ValueError("Server did not verify the broken block")
                        self.broken += 1
                        # Drops may arrive a few ticks after the block update.
                        for _ in range(10):
                            state = self.observe()
                            if any(
                                d.get("item") in self.names
                                for d in state.get("drops", [])
                            ):
                                break
                            time.sleep(0.1)
                        drops = [
                            d
                            for d in state.get("drops", [])
                            if d.get("item") in self.names
                            and not protected(d["position"], self.regions)
                        ]
                        for drop in sorted(
                            drops,
                            key=lambda d: self.chat.distance(
                                state["position"], d["position"]
                            ),
                        )[:3]:
                            self.child(
                                {
                                    "action": "pickup",
                                    "target": drop["position"],
                                    "entity_id": drop["id"],
                                }
                            )
                        self.observe()
                        if (
                            self.count(self.last) <= prior_count
                            and state.get("game_mode") != "creative"
                        ):
                            raise ValueError(
                                "No inventory gain after digging and pickup; trying another reachable target"
                            )
                        if (
                            state.get("game_mode") == "creative"
                            and self.count(self.gained) == 0
                        ):
                            raise ValueError(
                                "Creative removal produced no collected logs; use the separate Survival world."
                            )
                    except Exception as exc:
                        self.check()
                        self.failures += 1
                        self.chat.event(
                            "goal_recovery",
                            goal_id=self.id,
                            reason=str(exc),
                            failures=self.failures,
                            skipped=target,
                        )
                        if (
                            self.failures >= 3
                            or "Creative" in str(exc)
                            or "inventory_full" in str(exc)
                        ):
                            raise
                        self.chat.activity = (
                            "Trying another observed target after: " + str(exc)
                        )
                reason = "Requested inventory gain verified."
        except Exception as exc:
            reason = str(exc)
        try:
            self.check()
            if self.destination:
                self.child({"action": "move", "target": self.destination})
                returned = True
                if not reason:
                    reason = "Arrived at the saved place."
        except Exception as exc:
            reason += " Return incomplete: " + str(exc)
        with self.chat.lock:
            outcome = {
                "goal_id": self.id,
                "reason": reason,
                "broken": self.broken,
                "drops_observed": len(self.drops),
                "inventory_gains": dict(self.gained),
                "inventory_losses": dict(self.lost),
                "net_matching": self.count(self.last) - self.count(self.initial),
                "returned": returned,
                "remaining_actions": self.remaining,
                "shortfall": max(
                    0, self.needed - (self.count(self.last) - self.count(self.initial))
                ),
            }
            self.chat.event("goal_outcome", **outcome)
            if (
                self.chat.supervisor is self
                and self.authority == self.chat.authority()
                and not self.chat.closed
            ):
                display_reason = reason
                if "path" in reason.lower() or "obstructed" in reason.lower():
                    display_reason = "Route blocked or path search exhausted its limit. No obstacles were modified."
                text = f"{display_reason} Still needed: {outcome['shortfall']}. Server-verified breaks: {self.broken}; matching drop entities observed: {len(self.drops)}; matching inventory gain: {self.count(self.gained)}; net change: {outcome['net_matching']}."
                if self.plan["action"] != "gather":
                    text = reason
                if self.destination:
                    text += (
                        " Returned to the saved place; current route and position verified."
                        if returned
                        else " Did not return to the saved place."
                    )
                self.chat.message("assistant", text)
                self.chat.activity = text
                self.chat.goal = self.chat.supervisor = self.chat.active_action = None
