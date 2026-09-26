"""Versioned farm actions and transactional accounting from visible observations.

This contract does not qualify a recognizer. No plan, input, or expected outcome
can fill an observation. The v1 watering ledger remains a separate contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from uuid import uuid4

from smb3_agent.stardew_adapter import InputKind, StardewAdapterError, WateringLedger

FARM_CONTRACT = "selected-farm-actions/v2"
PURPOSES = {"harvest_crop": "harvest", "plant_seed": "plant", "clear_debris": "clear", "water_crop": "water"}
TOOLS = {"twig": "axe", "small_stone": "pickaxe", "weed": "scythe"}
DROPS = {"twig": "wood", "small_stone": "stone", "weed": "fiber"}


def require(condition, message):
    if not condition:
        raise StardewAdapterError(message)


@dataclass(frozen=True)
class FarmTarget:
    target_id: str
    tile_x: int
    tile_y: int
    state: str  # empty_tilled / immature / mature / regrowing / debris / cleared
    species: str | None = None
    watered: bool = False
    protected: bool = False
    evidence_reference: str = ""

    @property
    def planted(self):
        return self.state in {"immature", "mature", "regrowing"}


@dataclass(frozen=True)
class InventorySlot:
    slot: int
    item: str | None
    count: int
    evidence_reference: str


@dataclass(frozen=True)
class FarmObservation:
    targets: tuple[FarmTarget, ...]
    inventory: tuple[InventorySlot, ...]
    capacity: int
    selected_slot: int
    season: str
    day: int
    clock_minutes: int
    profile_id: str
    contract: str = FARM_CONTRACT

    def validate(self, screen):
        require(self.contract == FARM_CONTRACT and bool(self.profile_id), "unsupported farm observation contract")
        require(self.season in {"spring", "summer", "fall", "winter"} and 1 <= self.day <= 28,
                "farm season or day is unknown")
        require(360 <= self.clock_minutes < 1560, "visible farm clock is unknown")
        require(self.capacity in {12, 24, 36} and len(self.inventory) == self.capacity,
                "complete inventory capacity must be visible")
        require({s.slot for s in self.inventory} == set(range(self.capacity)), "inventory slots are incomplete or duplicated")
        require(0 <= self.selected_slot < self.capacity, "selected inventory slot is unknown")
        refs = set(screen.screenshot_references)
        for slot in self.inventory:
            require(slot.evidence_reference in refs and type(slot.count) is int
                    and ((slot.item is None and slot.count == 0) or (bool(slot.item) and 1 <= slot.count <= 999)),
                    "inventory identity/count must have current screen evidence")
        require(len({t.target_id for t in self.targets}) == len(self.targets)
                and len({(t.tile_x, t.tile_y) for t in self.targets}) == len(self.targets), "duplicate farm target")
        for target in self.targets:
            require(target.state in {"empty_tilled", "immature", "mature", "regrowing", "debris", "cleared", "protected"}
                    and target.evidence_reference in refs, "farm target state is unknown or lacks screen evidence")
            require(target.state != "protected" or target.protected, "protected scenery must remain protected")
            require(not target.planted or bool(target.species), "crop species is unknown")
        observed = {c.crop_id: c for c in screen.crops if c.planted}
        planted = {t.target_id: t for t in self.targets if t.planted}
        require(observed.keys() == planted.keys(), "farm targets and visible planted set disagree")
        for key, target in planted.items():
            crop = observed[key]
            require(not crop.occluded and crop.confidence == 1 and
                    (crop.tile_x, crop.tile_y, crop.watered) == (target.tile_x, target.tile_y, target.watered),
                    "farm crop facts are uncertain or inconsistent")

    def counts(self):
        result = {}
        for slot in self.inventory:
            if slot.item:
                result[slot.item] = result.get(slot.item, 0) + slot.count
        return result

    def can_receive(self, item):
        return any(s.item is None or (s.item == item and s.count < 999) for s in self.inventory)

    def selected(self):
        return next(s.item for s in self.inventory if s.slot == self.selected_slot)

    def task_state(self):
        return (tuple((t.target_id, t.tile_x, t.tile_y, t.state, t.species, t.watered, t.protected)
                      for t in self.targets), tuple((s.slot, s.item, s.count) for s in self.inventory),
                self.capacity, self.selected_slot, self.season, self.day, self.profile_id, self.contract)


@dataclass
class FarmLedger(WateringLedger):
    contract: str = FARM_CONTRACT
    steps: list[dict] = field(default_factory=list)
    confirmed_steps: list[dict] = field(default_factory=list)
    initial_planted_ids: tuple[str, ...] = ()
    current_planted_ids: tuple[str, ...] = ()
    initial_inventory: dict = field(default_factory=dict)
    current_inventory: dict = field(default_factory=dict)
    seed_consumed: int = 0
    harvested_ids: list[str] = field(default_factory=list)
    newly_planted_ids: list[str] = field(default_factory=list)
    cleared_ids: list[str] = field(default_factory=list)
    pending_result: object | None = field(default=None, repr=False)
    minimum_energy: int = 1
    maximum_seeds: int | None = None
    stop_minutes: int | None = None
    clearing_tool_uses: int = 0

    @classmethod
    def from_plan(cls, plan, screen):
        farm = screen.farm
        require(isinstance(farm, FarmObservation), "qualified farm action recognition is unavailable")
        farm.validate(screen)
        require(plan.stop_point == "farmhouse_entrance", "unsupported return point")
        targets = {t.target_id: t for t in farm.targets}
        steps, projected = [], dict(targets)
        counts = farm.counts().copy()
        for action in plan.actions:
            require(action.kind in {"harvest", "plant", "clear", "water"} and action.target_ids,
                    "unsupported or empty farm action")
            require(len(action.target_ids) == len(set(action.target_ids)), "duplicate targets in farm action")
            if action.kind == "plant":
                require(action.parameters.get("seed_count") == len(action.target_ids),
                        "planting count must equal explicitly selected plot count")
            for key in action.target_ids:
                require(key in projected, "selected farm target is not observed")
                target = projected[key]
                require(not target.protected, "selected farm target is protected")
                step = {"action_id": action.action_id, "kind": action.kind, "target_id": key,
                        "seed_type": action.parameters.get("seed_type"), "status": "pending"}
                if action.kind == "harvest":
                    require(target.state == "mature" and target.species == "parsnip", "only visibly mature nonregrowing parsnips are supported")
                    require(farm.can_receive("parsnip"), "inventory has no confirmed harvest capacity")
                    projected[key] = replace(target, state="empty_tilled", species=None)
                elif action.kind == "plant":
                    require(target.state == "empty_tilled", "planting requires an observed empty tilled plot or prior selected harvest")
                    require(step["seed_type"] == "parsnip" and farm.season == "spring" and farm.day <= 24,
                            "owned parsnip seeds require a supported spring planting day")
                    require(counts.get("parsnip_seeds", 0) > 0, "owned seed shortage")
                    counts["parsnip_seeds"] -= 1
                    projected[key] = replace(target, state="immature", species="parsnip")
                elif action.kind == "clear":
                    require(target.state == "debris" and target.species in TOOLS, "unsupported or uncertain selected debris")
                    require(counts.get(TOOLS[target.species], 0) == 1, "required owned clearing tool is missing")
                    require(farm.can_receive(DROPS[target.species]), "inventory has no confirmed resource capacity")
                    projected[key] = replace(target, state="cleared", species=None)
                else:
                    require(target.planted, "water after planting; selected target is not a crop")
                    projected[key] = replace(target, watered=True)
                steps.append(step)
        seed_count = sum(s["kind"] == "plant" for s in steps)
        maximum = plan.resource_limits.get("maximum_seeds")
        require(maximum is None or seed_count <= maximum, "reviewed seed limit would be crossed")
        minimum = plan.resource_limits.get("minimum_energy")
        require(minimum is None or type(minimum) is int and minimum >= 1, "energy reserve must be a positive integer")
        stop = plan.resource_limits.get("stop_time")
        stop_minutes = None
        if stop:
            import re
            match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", stop)
            require(match is not None, "unsupported reviewed stop time")
            hour, minute, suffix = int(match[1]), int(match[2] or 0), match[3]
            require(1 <= hour <= 12 and 0 <= minute < 60, "invalid reviewed stop time")
            stop_minutes = (hour % 12 + (12 if suffix == "pm" else 0)) * 60 + minute
            if stop_minutes < 360:
                stop_minutes += 1440
        base = WateringLedger.from_observation(screen)
        from dataclasses import asdict
        result = cls(**asdict(base), steps=steps, initial_planted_ids=base.initial_crop_ids,
                     current_planted_ids=base.initial_crop_ids, initial_inventory=farm.counts(),
                     current_inventory=farm.counts(), minimum_energy=minimum or 1,
                     maximum_seeds=maximum, stop_minutes=stop_minutes)
        result.final_position = screen.position
        result.task_id = f"farm-v2-{uuid4().hex}"
        result.check_limits(screen)
        return result

    @property
    def next_step(self):
        return next((s for s in self.steps if s["status"] == "pending"), None)

    def check_limits(self, screen, cost=0):
        require(screen.energy is not None and screen.energy - cost >= self.minimum_energy, "reviewed energy reserve would be crossed")
        require(screen.farm is not None and (self.stop_minutes is None or screen.farm.clock_minutes < self.stop_minutes), "reviewed stop time reached or unobservable")

    def skip_observed_water(self, screen):
        while self.next_step and self.next_step["kind"] == "water":
            target = next(t for t in screen.farm.targets if t.target_id == self.next_step["target_id"])
            if not target.planted or not target.watered:
                break
            self.next_step.update(status="already_satisfied", observation_id=screen.observation_id,
                                  attribution="observed wet; no watering action credited")

    def validate_command(self, command, screen):
        self.check_limits(screen)
        step = self.next_step
        if command.purpose == "navigate":
            require(command.kind is InputKind.KEYBOARD and command.control in {"w", "a", "s", "d"}
                    and 0 < command.duration_ms <= 100, "unsupported farm navigation")
            return
        require(step is not None and command.reviewed_crop_id == step["target_id"], "input is outside the next reviewed farm step")
        target = next((t for t in screen.farm.targets if t.target_id == step["target_id"]), None)
        require(target is not None and not target.protected, "selected target is unknown or protected")
        tool = {"water": "watering_can", "harvest": None, "plant": "parsnip_seeds",
                "clear": TOOLS.get(target.species)}[step["kind"]]
        if command.purpose == "select_farm_item":
            require(tool is not None and command.kind is InputKind.MOUSE and command.control == "left_button"
                    and command.action == "click" and command.duration_ms <= 100, "unsupported farm item selection")
            return
        require(PURPOSES.get(command.purpose) == step["kind"] and command.kind is InputKind.MOUSE
                and command.control == ("right_button" if step["kind"] == "harvest" else "left_button")
                and command.action == "click" and 0 < command.duration_ms <= 100, "input does not implement reviewed farm action")
        if tool:
            require(screen.farm.selected() == tool, "required owned item is not visibly selected")
        if step["kind"] == "harvest":
            require(target.state == "mature" and target.species == "parsnip" and screen.farm.can_receive("parsnip"), "crop is immature, uncertain or inventory is full")
        elif step["kind"] == "plant":
            require(target.state == "empty_tilled" and screen.farm.season == "spring"
                    and screen.farm.day <= 24 and screen.farm.counts().get("parsnip_seeds", 0) > 0, "planting plot, season or owned seeds are no longer eligible")
        elif step["kind"] == "clear":
            require(target.state == "debris" and target.species in TOOLS and screen.farm.can_receive(DROPS[target.species]), "clearing target or inventory is no longer eligible")
            self.check_limits(screen, 0 if target.species == "weed" else 2)
        else:
            require(target.planted and not target.watered and screen.tool.watering_can_units > 0, "watering target or can is no longer eligible")
            self.check_limits(screen, 2)

    def verify_postcondition(self, command, before, after):
        self.pending_result = None
        require(before.farm is not None and after.farm is not None, "farm action postcondition is unknown")
        a, b = before.farm, after.farm
        require((a.season, a.day, a.profile_id, a.capacity) == (b.season, b.day, b.profile_id, b.capacity)
                and a.clock_minutes <= b.clock_minutes, "farm observation context changed")
        old, new = {t.target_id: t for t in a.targets}, {t.target_id: t for t in b.targets}
        require(old.keys() == new.keys(), "selected plot identities changed")
        changed = {key for key in old if replace(old[key], evidence_reference="") != replace(new[key], evidence_reference="")}
        delta = {key: b.counts().get(key, 0)-a.counts().get(key, 0) for key in a.counts().keys() | b.counts().keys()
                 if b.counts().get(key, 0) != a.counts().get(key, 0)}
        energy = before.energy - after.energy
        water = before.tool.watering_can_units - after.tool.watering_can_units
        require(after.tool.refill_count == before.tool.refill_count, "unreviewed refill")
        if command.purpose != "navigate":
            p, q = before.position, after.position
            if p.world_pixel_x is not None:
                require(q.world_pixel_x is not None and q.world_pixel_y is not None
                        and max(abs(p.world_pixel_x-q.world_pixel_x), abs(p.world_pixel_y-q.world_pixel_y))
                        <= p.pixel_uncertainty+q.pixel_uncertainty, "player moved during selected farm action")
            else:
                require(p == q, "player moved during selected farm action")
        require(command.purpose == "select_farm_item" or a.selected_slot == b.selected_slot,
                "selected item slot changed during farm action")
        if command.purpose in {"navigate", "select_farm_item"}:
            require(not changed and not delta and energy == water == 0, "navigation or selection changed farm resources")
            require(command.purpose == "select_farm_item" or a.selected_slot == b.selected_slot, "item changed during navigation")
            if command.purpose == "select_farm_item":
                step = self.next_step
                expected = {"water": "watering_can", "plant": "parsnip_seeds", "clear": TOOLS.get(old[step["target_id"]].species)}.get(step["kind"])
                require(b.selected() == expected, "owned item selection not observed")
            return
        key = command.reviewed_crop_id
        require(changed == {key}, "farm action changed an unselected target or no target")
        left, right = old[key], new[key]
        require((left.tile_x, left.tile_y, left.protected) == (right.tile_x, right.tile_y, right.protected), "target geometry or protection changed")
        if command.purpose == "harvest_crop":
            require(left.state == "mature" and right.state == "empty_tilled" and right.species is None
                    and delta == {"parsnip": 1} and energy == water == 0
                    and left.watered == right.watered, "harvest crop and inventory gain do not reconcile")
        elif command.purpose == "plant_seed":
            require(left.state == "empty_tilled" and right.state == "immature" and right.species == "parsnip"
                    and delta == {"parsnip_seeds": -1} and energy == water == 0
                    and left.watered == right.watered, "seed consumption and new crop do not reconcile")
        elif command.purpose == "clear_debris":
            require(right.state == "cleared" and right.species is None and water == 0
                    and energy == (0 if left.species == "weed" else 2), "selected debris removal or energy does not reconcile")
            allowed = {DROPS[left.species]} | ({"mixed_seeds"} if left.species == "weed" else set())
            require(set(delta) <= allowed and all(0 < n <= 3 for n in delta.values()), "clearing inventory gain is unexpected")
            require(left.species == "weed" or delta.get(DROPS[left.species], 0) > 0, "clearing item collection remains unobserved")
        elif command.purpose == "water_crop":
            require(replace(left, watered=True, evidence_reference=right.evidence_reference) == right
                    and not left.watered and not delta and energy == 2 and water == 1, "farm watering postcondition does not reconcile")
        else:
            raise StardewAdapterError("unsupported farm postcondition")
        self.pending_result = (after.observation_id, {**self.next_step, "status": "confirmed", "inventory_delta": delta,
                               "energy_spent": energy, "water_consumed": water,
                               "before_observation_id": before.observation_id, "after_observation_id": after.observation_id})

    def reconcile(self, observation, *, allow_player_occlusion=False):
        if self.pending_result is not None:
            identity, record = self.pending_result
            require(identity == observation.observation_id, "farm postcondition observation changed")
            self.next_step.update(record)
            self.confirmed_steps.append(dict(record))
            key = record["target_id"]
            if record["kind"] == "harvest":
                self.harvested_ids.append(key)
            elif record["kind"] == "plant":
                self.newly_planted_ids.append(key)
                self.seed_consumed += 1
            elif record["kind"] == "clear":
                self.cleared_ids.append(key)
                self.clearing_tool_uses += 1
            if record["kind"] in {"water", "clear"}:
                self.tool_uses += 1
            self.can_water_consumed += record["water_consumed"]
            self.pending_result = None
        self.current_planted_ids = tuple(sorted(c.crop_id for c in observation.crops if c.planted))
        self.confirmed_watered_ids = {c.crop_id for c in observation.crops if c.planted and c.watered}
        self.current_inventory = observation.farm.counts()
        self.energy_current = observation.energy
        self.energy_spent = self.energy_start - observation.energy
        self.can_water_current = observation.tool.watering_can_units
        self.final_position = observation.position
        self.evidence_references.extend(observation.screenshot_references)

    @property
    def remaining_count(self):
        return sum(step["status"] == "pending" for step in self.steps)

    @property
    def complete(self):
        return self.remaining_count == 0 and self.final_position is not None and self.final_position.at_farmhouse_entrance is True
