"""Finite executable profile data. Configuration selects implemented sensors/skills."""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass

from smb3_agent.screen_host import Frame, TextRegion


class ProfileError(ValueError):
    pass


@dataclass(frozen=True)
class NumberSensor:
    sensor_id: str
    pattern: str
    region: tuple[float, float, float, float]

    detector_id: str = "strict-integer/v1"

    def read(self, frame: Frame) -> int:
        matches = []
        for item in frame.text:
            if item.confidence < .9 or not contains(self.region, item.box):
                continue
            match = re.fullmatch(self.pattern, item.text)
            if match:
                digits = match.group(1)
                if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)", digits):
                    raise ProfileError("Malformed integer grouping: " + self.sensor_id)
                matches.append(int(digits.replace(",", "")))
        if len(matches) != 1:
            raise ProfileError("Number sensor unknown or ambiguous: " + self.sensor_id)
        return matches[0]


def contains(outer, inner):
    x, y, w, h = outer
    ix, iy, iw, ih = inner
    return x <= ix and y <= iy and ix+iw <= x+w and iy+ih <= y+h


def valid_box(box):
    return (isinstance(box, (tuple, list)) and len(box) == 4
            and all(type(n) in {int, float} and math.isfinite(n) for n in box)
            and 0 <= box[0] < 1 and 0 <= box[1] < 1 and 0 < box[2] <= 1
            and 0 < box[3] <= 1 and box[0]+box[2] <= 1 and box[1]+box[3] <= 1)


@dataclass(frozen=True)
class ClickSkill:
    skill_id: str
    target_id: str
    target_text: str
    target_region: tuple[float, float, float, float]
    # Every observed sensor is reconciled; missing/contradictory outcomes fail.
    deltas: tuple[tuple[str, int], ...]
    required_before: tuple[tuple[str, int], ...]
    description: str
    pulse_ms: int = 80
    click_anchor: str = "label_center"
    request_verbs: tuple[str, ...] = ()
    detector_id: str = "unique-text/v1"
    skill_contract: str = "text-click/v1"
    verifier_contract: str = "exact-deltas/v1"
    observation_region: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class ExecutableProfile:
    profile_id: str
    game_id: str
    game_build: str
    settings_id: str
    backend_id: str
    viewport: tuple[int, int]
    sensors: tuple[NumberSensor, ...]
    skills: tuple[ClickSkill, ...]
    protected_actions: tuple[str, ...]
    version: str = "game-companion-executable-profile/v2"
    frame_max_age: float = 2
    capabilities: tuple[str, ...] = ("strict-integer/v1", "unique-text/v1", "text-click/v1", "exact-deltas/v1")

    def validate(self):
        if self.version != "game-companion-executable-profile/v2":
            raise ProfileError("Unsupported executable profile version")
        if not all(isinstance(x, str) and 0 < len(x) <= 160 for x in
                   (self.profile_id, self.game_id, self.game_build, self.settings_id, self.backend_id)):
            raise ProfileError("Missing profile compatibility identity")
        if (len(self.viewport) != 2 or any(type(n) is not int or not 100 <= n <= 4000 for n in self.viewport)
                or type(self.frame_max_age) not in {int, float} or not 0 < self.frame_max_age <= 3):
            raise ProfileError("Unsupported viewport or freshness bound")
        from smb3_agent.skill_registry import validate_capabilities
        validate_capabilities(self)
        sensor_ids = {s.sensor_id for s in self.sensors}
        if (not 1 <= len(self.protected_actions) <= 32 or any(
                not isinstance(s, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,79}", s)
                for s in (*sensor_ids, *self.protected_actions))):
            raise ProfileError("Invalid sensor or protected-action identity")
        if not 1 <= len(self.sensors) <= 16 or len(sensor_ids) != len(self.sensors):
            raise ProfileError("Invalid sensor inventory")
        if not 1 <= len(self.skills) <= 16 or len({s.skill_id for s in self.skills}) != len(self.skills):
            raise ProfileError("Invalid skill inventory")
        for sensor in self.sensors:
            if not valid_box(sensor.region) or len(sensor.pattern) > 160:
                raise ProfileError("Invalid number sensor")
            # Only a fixed integer capture surrounded by literal text. No
            # arbitrary regex/backtracking language is configurable.
            literal = sensor.pattern.replace("([0-9,]+)", "")
            if sensor.pattern.count("([0-9,]+)") != 1 or re.search(r"[^\w\s£$,:-]", literal):
                raise ProfileError("Unsupported number pattern")
            if re.compile(sensor.pattern).groups != 1:
                raise ProfileError("Number sensor needs exactly one capture")
        for skill in self.skills:
            if skill.observation_region is not None and (not valid_box(skill.observation_region)
                    or not contains(skill.target_region, skill.observation_region)):
                raise ProfileError("Label observation must lie inside the reviewed hit region")
            if (not isinstance(skill.description, str) or not 1 <= len(skill.description) <= 1000
                    or any(not isinstance(s, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,79}", s)
                           for s in (skill.skill_id, skill.target_id))):
                raise ProfileError("Invalid skill signature")
            if (not valid_box(skill.target_region) or type(skill.pulse_ms) is not int
                    or not 1 <= skill.pulse_ms <= 250 or skill.skill_id in self.protected_actions
                    or skill.click_anchor not in {"label_center", "label_left_gutter"}
                    or not skill.target_id or not skill.target_text or len(skill.target_text) > 160):
                raise ProfileError("Invalid or protected click skill")
            if (not 1 <= len(skill.request_verbs) <= 8 or any(
                    not isinstance(v, str) or not re.fullmatch(r"[a-z]+(?: [a-z]+){0,3}", v)
                    for v in skill.request_verbs)):
                raise ProfileError("Skill needs a finite explicit action vocabulary")
            if (set(dict(skill.deltas)) != sensor_ids or set(dict(skill.required_before)) != sensor_ids
                    or len(skill.deltas) != len(sensor_ids) or len(skill.required_before) != len(sensor_ids)
                    or not any(delta for _, delta in skill.deltas)
                    or any(type(n) is not int for _, n in (*skill.deltas, *skill.required_before))):
                raise ProfileError("Skill needs complete integer entry/outcome reconciliation")

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

    def values(self, frame):
        return {s.sensor_id: s.read(frame) for s in self.sensors}

    def skill(self, skill_id):
        candidates = [s for s in self.skills if s.skill_id == skill_id]
        if len(candidates) != 1 or skill_id in self.protected_actions:
            raise ProfileError("Unknown or protected skill")
        return candidates[0]

    def target(self, frame: Frame, skill: ClickSkill) -> TextRegion:
        targets = [t for t in frame.text if t.text.casefold() == skill.target_text.casefold()
                   and t.confidence >= .9 and contains(skill.target_region, t.box)]
        if len(targets) != 1:
            raise ProfileError("Target unknown or ambiguous; clarification required")
        return targets[0]

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) - set(cls.__dataclass_fields__):
            raise ProfileError("Unknown profile fields; executable content refused")
        try:
            value = dict(data)
            value["sensors"] = tuple(NumberSensor(**{**s, "region": tuple(s["region"])}) for s in value["sensors"])
            value["skills"] = tuple(ClickSkill(**{**s, "target_region": tuple(s["target_region"]),
                "deltas": tuple(tuple(p) for p in s["deltas"]),
                "required_before": tuple(tuple(p) for p in s["required_before"]),
                "request_verbs": tuple(s.get("request_verbs", ())),
                "observation_region": tuple(s["observation_region"]) if s.get("observation_region") is not None else None}) for s in value["skills"])
            value["viewport"] = tuple(value["viewport"])
            value["protected_actions"] = tuple(value["protected_actions"])
            value["capabilities"] = tuple(value["capabilities"])
            if any("detector_id" not in s for s in data["sensors"]) or any(
                    not {"detector_id", "skill_contract", "verifier_contract"} <= set(s) for s in data["skills"]):
                raise ProfileError("Profiles must explicitly reference implemented capability contracts")
            profile = cls(**value)
            profile.validate()
            return profile
        except (TypeError, KeyError, re.error) as exc:
            raise ProfileError("Invalid executable profile") from exc
