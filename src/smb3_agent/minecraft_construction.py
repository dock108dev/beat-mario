"""Parameterized construction composed through the existing goal and scheduler."""

from collections import Counter
from copy import deepcopy
import json
import time
import math

from smb3_agent.minecraft_goals import Goal, inventory


def geometry(spec):
    w, d, h = (spec[k] for k in ("width", "depth", "height"))
    if any(type(n) is not int for n in (w, d, h)) or not (
        3 <= w <= 7 and 3 <= d <= 7 and 2 <= h <= 4
    ):
        raise ValueError("Shelters support width/depth 3–7 and wall height 2–4.")
    origin = spec["origin"]
    if any(type(origin[k]) is not int for k in ("x", "y", "z")):
        raise ValueError("Site must use whole block coordinates.")
    if spec["doorway"] not in ("north", "south", "east", "west"):
        raise ValueError(
            "Name a cardinal doorway direction; no human position is assumed."
        )
    material = spec["material"]
    if material not in (
        "oak_planks",
        "birch_planks",
        "spruce_planks",
        "jungle_planks",
        "acacia_planks",
        "dark_oak_planks",
        "mangrove_planks",
        "cherry_planks",
        "pale_oak_planks",
    ):
        raise ValueError("Choose common wooden planks for construction.")
    cells = []
    for y in range(h + 1):
        for x in range(w):
            for z in range(d):
                wall = x in (0, w - 1) or z in (0, d - 1)
                door = {
                    "north": z == 0 and x == w // 2,
                    "south": z == d - 1 and x == w // 2,
                    "west": x == 0 and z == d // 2,
                    "east": x == w - 1 and z == d // 2,
                }[spec["doorway"]]
                window = (
                    spec["windows"]
                    and y == 1
                    and (
                        (z in (0, d - 1) and x == w // 2)
                        or (x in (0, w - 1) and z == d // 2)
                    )
                )
                if (y == h or wall) and not (y < 2 and door) and not (y < h and window):
                    cells.append(
                        {
                            "position": {
                                "x": origin["x"] + x,
                                "y": origin["y"] + y,
                                "z": origin["z"] + z,
                            },
                            "item": material,
                        }
                    )
    if len(cells) > 192:
        raise ValueError("Structure exceeds the 192-block construction budget.")
    return cells


def key(cell):
    return tuple(cell["position"][k] for k in ("x", "y", "z"))


class ConstructionGoal(Goal):
    def __init__(self, chat, plan, state, authority, *, started_at=None):
        super().__init__(chat, plan, state, authority, started_at=started_at)
        self.deadline += (
            660  # 15 minutes including planning, still one parent deadline.
        )
        self.remaining = 512
        self.placed = []
        self.new_placements = []
        self.removed = []
        self.spec = deepcopy(plan["structure"])
        old = getattr(chat, "construction", None)
        if self.spec["revise"] and plan.get("structure_name"):
            matches = [
                r
                for r in chat.memory["structures"].values()
                if r.get("name") == plan["structure_name"] and r["world"] == self.world
            ]
            if len(matches) != 1:
                raise ValueError("Name one saved structure in this world to revise.")
            old = matches[0]
        if (
            not self.spec["revise"]
            and plan.get("structure_name")
            and any(
                r.get("name") == plan["structure_name"] and r["world"] == self.world
                for r in chat.memory["structures"].values()
            )
        ):
            raise ValueError(
                "That name is already saved; request a revision or choose a new name."
            )
        if self.spec["revise"]:
            if not old or old["world"] != self.world:
                raise ValueError("No construction in this world to revise.")
            if self.spec["relocate"] and self.spec["site_place"]:
                base = self.place(self.spec["site_place"], state)
                self.spec["origin"] = {
                    k: math.floor(base[k]) + self.spec["offset"][k]
                    for k in ("x", "y", "z")
                }
            elif self.spec["relocate"]:
                self.spec["origin"] = {
                    k: math.floor(state["position"][k]) + self.spec["offset"][k]
                    for k in ("x", "y", "z")
                }
            else:
                self.spec["origin"] = old["spec"]["origin"]
        else:
            base = (
                self.place(self.spec["site_place"], state)
                if self.spec["site_place"]
                else state["position"]
            )
            self.spec["origin"] = {
                k: math.floor(base[k]) + self.spec["offset"][k] for k in ("x", "y", "z")
            }
        self.cells = geometry(self.spec)
        self.avoid = (
            deepcopy(old.get("cells", geometry(old["spec"])))
            if old and not self.spec["revise"] and old.get("placed")
            else []
        )
        if not self.spec["revise"]:
            for saved in chat.memory["structures"].values():
                if saved["world"] == self.world:
                    self.avoid.extend(
                        deepcopy(saved.get("cells", geometry(saved["spec"])))
                    )
        self.avoid = list({key(c): c for c in self.avoid}.values())
        self.previous = deepcopy(old["placed"]) if old and self.spec["revise"] else []
        self.previous_cells = (
            deepcopy(old.get("cells", geometry(old["spec"])))
            if old and self.spec["revise"]
            else []
        )
        prior_by_key = {key(c): c for c in self.previous}
        observed_keys = {key(c) for c in self.previous_cells}
        self.previous_cells += [
            deepcopy(c) for c in self.previous if key(c) not in observed_keys
        ]
        for c in self.previous_cells:
            if key(c) in prior_by_key:
                c["item"] = prior_by_key[key(c)]["item"]
        by_key = {key(c): c for c in self.cells}
        if self.spec["remaining_only"]:
            for c in self.previous:
                if key(c) in by_key:
                    by_key[key(c)]["item"] = c["item"]
        self.conflicts = [
            c
            for c in self.previous
            if key(c) not in by_key or by_key[key(c)]["item"] != c["item"]
        ]
        self.placed = deepcopy(self.previous)
        self.record = {
            "world": self.world,
            "spec": self.spec,
            "placed": self.placed,
            "goal_id": self.id,
            "structure_id": old.get("structure_id", old["goal_id"])
            if old and self.spec["revise"]
            else self.id,
            "name": plan.get("structure_name")
            or (old.get("name", "") if old and self.spec["revise"] else ""),
            "history": deepcopy(old.get("history", []))
            if old and self.spec["revise"]
            else [],
        }

    def publish(self):
        with self.chat.lock:
            self.check()
            self.record["cells"] = self.cells
            self.chat.persist_construction(self.record)
            self.chat.construction = self.record

    def save_record(self, initial=False):
        with self.chat.lock:
            if self.chat.construction is not self.record:
                return
            if not initial:
                self.check()
            self.record["cells"] = self.cells
            self.record["inventory_gains"] = dict(self.gained)
            self.record["inventory_losses"] = dict(self.lost)
            self.record["remaining_actions"] = self.remaining
            self.chat.persist_construction(self.record)

    def progress(self, action):
        if self.plan["action"] == "craft":
            return f"{action['action'].capitalize()} · preparing {self.plan['craft_item']} · {self.remaining} actions left"
        return f"{action['action'].capitalize()} · {len(self.placed)}/{len(self.cells)} recorded blocks · {self.remaining} actions left"

    def inspect(self, search=False, removable=None):
        result = self.child(
            {
                "action": "inspect_site",
                "cells": self.cells,
                "clearance": True,
                "avoid": self.avoid,
                "removable": removable or [],
                "search": search,
                "rejections": self.chat.memory.get("site_rejections", {}).get(
                    json.dumps(self.world), []
                )[-240:],
            }
        )
        if result.get("rejected"):
            with self.chat.lock:
                self.check()
                updated = deepcopy(self.chat.memory)
                records = updated.setdefault("site_rejections", {}).setdefault(
                    json.dumps(self.world), []
                )
                records.extend(
                    {**r, "at_ms": time.time_ns() / 1e6} for r in result["rejected"]
                )
                records[:] = records[-240:]
                self.chat.library_store.save(updated)
                self.chat.memory = updated
            self.chat.event(
                "site_alternatives",
                goal_id=self.id,
                inspected=result["inspected"],
                rejected=result["rejected"],
                selected=result.get("translation"),
            )
        if result.get("observed") == "site_search_exhausted":
            totals = Counter()
            for rejected in result["rejected"]:
                totals.update(k for k, v in rejected["reasons"].items() if v)
            alternative = self.offer_alternative()
            raise ValueError(
                f"No supported requested site: {result['inspected']} geometric candidates inspected, {result.get('reused', 0)} unchanged rejections reused; {dict(totals)}. "
                + alternative
            )
        if result.get("translation"):
            shift = result["translation"]
            self.spec["origin"] = {
                k: self.spec["origin"][k] + shift[k] for k in ("x", "y", "z")
            }
            self.cells = geometry(self.spec)
            self.save_record()
        for field in ("occupied", "protected", "unknown", "inaccessible"):
            if result.get(field):
                raise ValueError(
                    f"Site {field}: {len(result[field])} cells. No obstacles removed. "
                    + (
                        self.offer_alternative()
                        if not self.spec["revise"]
                        else "Saved footprint retained; request another design or explicitly resolve the obstruction."
                    )
                )
        # Roof cells may be supported sideways after the perimeter; floor-level walls must stand on terrain.
        unsupported = [
            c
            for c in result["unsupported"]
            if c["position"]["y"] == self.spec["origin"]["y"]
        ]
        if unsupported:
            raise ValueError(
                "Uneven or unsupported foundation; choose a level site. Terrain will not be cleared or filled."
            )
        return result

    def offer_alternative(self):
        spec = deepcopy(self.spec)
        spec.update(width=3, depth=3, height=2, windows=False)
        # Offer only; a changed footprint/location never becomes an accepted record.
        state = self.observe()
        spec["origin"] = {k: math.floor(state["position"][k]) for k in ("x", "y", "z")}
        result = self.child(
            {
                "action": "inspect_site",
                "cells": geometry(spec),
                "clearance": True,
                "avoid": self.avoid,
                "search": True,
                "offer_only": True,
                "rejections": self.chat.memory.get("site_rejections", {}).get(
                    json.dumps(self.world), []
                )[-240:],
            }
        )
        if (
            result.get("observed") == "site_search_exhausted"
            or not result.get("access", {}).get("known")
            or not result.get("origin")
        ):
            return "No reachable fully inspected smaller alternative found within the observed bounds. Choose a different area; accepted structures are unchanged."
        spec["origin"] = result["origin"]
        offer = {
            "goal_id": self.id,
            "world": self.world,
            "spec": spec,
            "at_ms": time.time_ns() / 1e6,
            "access": result["access"],
            "requires_new_request": True,
        }
        with self.chat.lock:
            self.check()
            self.chat.site_offer = offer
        self.chat.event("site_offer", goal_id=self.id, offer=offer)
        return f"Observed alternative: a 3 by 3, two-block-high {spec['material']} shelter with {spec['doorway']} doorway, no windows, at {spec['origin']}; full footprint and routes to placement positions checked. This changes location and possibly dimensions/design. Shall I build that alternative? Nothing built or cleared; saved structures unchanged."

    def gather_missing(self, name, quantity):
        if not name.endswith("_log") and name != "cobblestone":
            raise ValueError(
                f"Missing prerequisite {quantity} {name}; collection of this material is not supported yet."
            )
        if quantity > 32:
            self.gather_missing(name, 32)
            self.gather_missing(name, quantity - 32)
            return
        self.quantity = quantity
        self.resource, self.names, self.needed = name, [name], quantity
        baseline, broken = self.initial, self.broken
        self.initial = inventory(self.observe())
        self.broken = 0
        try:
            self.gather()
        finally:
            self.initial = baseline
            self.broken += broken

    def ensure(self, item, quantity, wood, trail=()):
        if item in trail or len(trail) > 8:
            raise ValueError("Cyclic prerequisite")
        station = (
            self.child({"action": "workstation"})
            if item.startswith(("wooden_", "stone_"))
            else None
        )
        request = {
            "action": "recipe",
            "item": item,
            "quantity": quantity,
            "wood": wood,
            "table_available": bool(station and station["existing"]),
        }
        recipe = self.child(request)
        if recipe["missing"].get("cobblestone"):
            state = self.observe()
            if not any(i["name"].endswith("_pickaxe") for i in state["inventory"]):
                self.ensure("wooden_pickaxe", 1, wood, trail + (item,))
        for name, amount in recipe["missing"].items():
            self.gather_missing(name, amount)
        recipe = self.child(request)
        if recipe["missing"]:
            raise ValueError(f"Material shortfall: {recipe['missing']}")
        table = station["target"] if station and station["existing"] else None
        for step in recipe["steps"]:
            if step.get("workstation"):
                site = self.child({"action": "workstation"})
                if not site["existing"]:
                    self.child(
                        {
                            "action": "place",
                            "target": site["target"],
                            "item": "crafting_table",
                        }
                    )
                table = site["target"]
                self.child({"action": "approach", "target": table})
            else:
                action = {
                    "action": "craft",
                    "item": step["item"],
                    "recipe": step["index"],
                    "times": step["times"],
                }
                if step["table"]:
                    if table is None:
                        raise ValueError("Workstation prerequisite unresolved")
                    self.child({"action": "approach", "target": table})
                    action["target"] = table
                self.child(action)

    def run(self):
        reason, complete = "", False
        try:
            self.observe()
            if self.previous_cells:
                actual = self.child(
                    {"action": "inspect_site", "cells": self.previous_cells}
                )
                known = {key(c): c for c in self.placed}
                self.placed[:] = [
                    known.get(
                        key(c),
                        {
                            "position": c["position"],
                            "item": c["actual"],
                            "consumed": None,
                        },
                    )
                    for c in actual["cells"]
                    if c["actual"] == c["item"]
                ]
                desired = {key(c): c for c in self.cells}
                if self.spec["remaining_only"]:
                    for c in self.placed:
                        if key(c) in desired:
                            desired[key(c)]["item"] = c["item"]
                self.conflicts = [
                    c
                    for c in self.placed
                    if key(c) not in desired or c["item"] != desired[key(c)]["item"]
                ]
                self.save_record()
            if self.conflicts and not self.spec.get("allow_removal", False):
                raise ValueError(
                    f"Revision needs removal/replacement of {len(self.conflicts)} completed blocks. They remain in place and materials are not refunded. Explicit permission is required before removing these completed blocks; choose a compatible revision or permit removal."
                )
            if self.conflicts:
                # Validate every conflicting cell before modifying any; no blanket terrain authority.
                from smb3_agent.minecraft_goals import protected

                if any(protected(c["position"], self.regions) for c in self.conflicts):
                    raise ValueError("Protected completed blocks cannot be removed.")
                self.inspect(removable=self.conflicts)
                self.publish()
                for cell in sorted(self.conflicts, key=lambda c: -c["position"]["y"]):
                    self.child({"action": "approach", "target": cell["position"]})
                    result = self.child(
                        {
                            "action": "remove",
                            "target": cell["position"],
                            "expected": cell["item"],
                            "allow_removal": True,
                        }
                    )
                    if result.get("observed") != "server_block_change":
                        raise ValueError("Removal unverified")
                    self.removed.append(deepcopy(cell))
                    self.placed[:] = [c for c in self.placed if key(c) != key(cell)]
                    self.save_record()
            site = self.inspect(
                search=self.spec.get("flexible_site", False) and not self.spec["revise"]
            )
            self.publish()
            pending = [c for c in site["cells"] if c["actual"] != c["item"]]
            required = Counter(c["item"] for c in pending)
            self.chat.message(
                "assistant",
                f"Site inspected. {len(pending)} placements remain; materials: {dict(required)}. Existing compatible blocks stay. Work is bounded to 15 minutes, 512 actions and three gathering failures.",
            )
            for item, amount in required.items():
                self.ensure(item, amount, item.removesuffix("_planks"))
            self.inspect()
            for cell in pending:
                result = self.child(
                    {
                        "action": "place",
                        "target": cell["position"],
                        "item": cell["item"],
                    }
                )
                if result["observed"] == "server_placement":
                    with self.chat.control, self.chat.lock:
                        self.check()
                        self.placed.append({**cell, "consumed": result["consumed"]})
                        self.new_placements.append(deepcopy(cell))
                        self.save_record()
            final = self.inspect()
            absent = [c for c in final["cells"] if c["actual"] != c["item"]]
            complete = not absent
            reason = (
                "Shelter verified against current server blocks."
                if complete
                else f"{len(absent)} blocks remain unverified."
            )
        except Exception as exc:
            reason = str(exc)
        with self.chat.lock:
            if self.chat.construction is self.record:
                self.record["outcome"] = {
                    "complete": complete,
                    "reason": reason,
                    "requires_inspection": True,
                }
                self.record["history"].append(
                    {
                        "goal_id": self.id,
                        "complete": complete,
                        "reason": reason,
                        "inventory_gains": dict(self.gained),
                        "inventory_losses": dict(self.lost),
                    }
                )
                # Persist historical partial work even after cancellation, never grant authority.
                try:
                    self.save_record(initial=True)
                except (OSError, ValueError) as exc:
                    self.chat.construction_store.problem = (
                        "Construction memory write failed; recover a saved generation. "
                        + str(exc)
                    )
                    self.chat.error = self.chat.construction_store.problem
            self.chat.event(
                "construction_outcome",
                goal_id=self.id,
                world=self.world,
                complete=complete,
                reason=reason,
                spec=self.spec,
                placed=self.placed,
                new_placements=self.new_placements,
                removed=self.removed,
                inventory_gains=dict(self.gained),
                inventory_losses=dict(self.lost),
                remaining_actions=self.remaining,
            )
            if (
                self.chat.supervisor is self
                and self.authority == self.chat.authority()
                and not self.chat.closed
            ):
                text = f"{'Completed' if complete else 'Construction incomplete'}: {reason} This goal placed {len(self.new_placements)} and removed {len(self.removed)} blocks; {len(self.placed)} recorded structure blocks remain. Inventory consumption: {dict(self.lost)}."
                self.chat.message("assistant", text)
                self.chat.activity = text
                self.chat.goal = self.chat.supervisor = self.chat.active_action = None


class CraftGoal(ConstructionGoal):
    """Ordinary conversational crafting; same parent budgets, skills and Stop barrier."""

    def __init__(self, chat, plan, state, authority, *, started_at=None):
        if not 1 <= plan["craft_quantity"] <= 64:
            raise ValueError("Crafting supports inventory targets from 1 to 64. Your requested target was not changed and no crafting started; choose a supported target.")
        Goal.__init__(self, chat, plan, state, authority, started_at=started_at)
        self.deadline += 660
        self.remaining = 512
        self.placed = []

    def run(self):
        complete = False
        try:
            self.ensure(
                self.plan["craft_item"],
                self.plan["craft_quantity"],
                self.plan["structure"]["material"].removesuffix("_planks"),
            )
            complete = True
            reason = (f"Inventory target {self.plan['craft_quantity']} {self.plan['craft_item']} verified. "
                      + ("Crafting consumed ingredients." if self.lost else "Target was already met; nothing crafted or consumed."))
        except Exception as exc:
            reason = str(exc)
        with self.chat.lock:
            self.chat.event(
                "craft_outcome",
                goal_id=self.id,
                world=self.world,
                complete=complete,
                reason=reason,
                inventory_gains=dict(self.gained),
                inventory_losses=dict(self.lost),
            )
            if (
                self.chat.supervisor is self
                and self.authority == self.chat.authority()
                and not self.chat.closed
            ):
                self.chat.message(
                    "assistant",
                    reason
                    + f" Observed gains: {dict(self.gained)}; consumption: {dict(self.lost)}.",
                )
                self.chat.activity = reason
                self.chat.goal = self.chat.supervisor = self.chat.active_action = None
