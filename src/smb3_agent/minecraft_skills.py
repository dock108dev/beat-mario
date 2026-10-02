"""Creative-only visible-pose provider. No hidden world/API reads or destruction."""

from dataclasses import dataclass
import math
import re

from smb3_agent.feedback_contracts import FeedbackError, heading_delta
from smb3_agent.host_contracts import InputCommand, InputKind


@dataclass(frozen=True)
class SpatialObservation:
    captured_at: float
    window_identity: tuple
    settings: str
    position: tuple[float, float, float]
    heading: float
    pitch: float
    target: tuple[int, int, int] | None
    block: str | None
    face: tuple[int, int, int] | None
    material: str | None
    creative: bool
    ground_confirmed: bool
    source: str


def wall_cells(anchor, axis="x"):
    if (
        axis not in {"x", "z"}
        or len(anchor) != 3
        or any(type(v) is not int or abs(v) > 30000000 for v in anchor)
    ):
        raise FeedbackError("Invalid bounded wall anchor")
    return tuple(
        (
            anchor[0] + (x if axis == "x" else 0),
            anchor[1] + y,
            anchor[2] + (x if axis == "z" else 0),
        )
        for y in range(3)
        for x in range(7)
        if not (x == 3 and y < 2)
    )


def visible_spatial(
    texts,
    *,
    captured_at,
    window_identity,
    settings,
    orientation,
    material=None,
    creative=False,
    ground_confirmed=False,
    source="selected-window-ocr",
):
    """Exact visible HUD grammar; conflicting/absent rows refuse spatial work.

    Creative/material/flat-ground facts must come from separately declared visible
    detectors. This parser deliberately cannot infer them from a profile or request.
    """
    position, target, block = [], [], []
    for text in texts:
        match = re.fullmatch(
            r"XYZ: (-?\d{1,8}\.\d{1,5}) / (-?\d{1,8}\.\d{1,5}) / (-?\d{1,8}\.\d{1,5})",
            text,
        )
        if match:
            position.append(tuple(float(v) for v in match.groups()))
        match = re.fullmatch(
            r"Targeted Block: (-?\d{1,8}), (-?\d{1,8}), (-?\d{1,8})", text
        )
        if match:
            target.append(tuple(int(v) for v in match.groups()))
        if re.fullmatch(r"minecraft:[a-z_]{1,60}", text):
            block.append(text)
    if len(position) != 1 or len(target) > 1 or len(block) > 1:
        raise FeedbackError("Visible pose/block HUD is missing or ambiguous")
    face = (
        reached_face(position[0], orientation.heading, orientation.pitch, target[0])
        if target
        else None
    )
    return SpatialObservation(
        captured_at,
        window_identity,
        settings,
        position[0],
        orientation.heading,
        orientation.pitch,
        target[0] if target else None,
        block[0] if len(block) == 1 else None,
        face,
        material,
        creative,
        ground_confirmed,
        source,
    )


def reached_face(position, heading, pitch, block):
    """Ray/AABB intersection from visible feet pose; edge/long-reach rays refuse."""
    h, p = math.radians(heading), math.radians(pitch)
    ray = (-math.sin(h) * math.cos(p), -math.sin(p), math.cos(h) * math.cos(p))
    eye = (position[0], position[1] + 1.62, position[2])
    near, far, normal = -math.inf, math.inf, None
    for i in range(3):
        if abs(ray[i]) < 1e-8:
            if not block[i] <= eye[i] <= block[i] + 1:
                return None
            continue
        a, b = (block[i] - eye[i]) / ray[i], (block[i] + 1 - eye[i]) / ray[i]
        entry, leave = min(a, b), max(a, b)
        if entry > near:
            near = entry
            normal = tuple((-1 if ray[i] > 0 else 1) if j == i else 0 for j in range(3))
        far = min(far, leave)
    if normal is None or not 0 < near < min(far, 4.5):
        return None
    hit = tuple(eye[i] + near * ray[i] - block[i] for i in range(3))
    if any(not 0.08 < hit[i] < 0.92 for i in range(3) if normal[i] == 0):
        return None
    return normal


class MinecraftSkills:
    def __init__(self, binding, settings, protected=(), screen_center=None):
        self.binding, self.settings, self.protected = (
            binding,
            settings,
            frozenset(protected),
        )
        self.screen_center = screen_center

    def require_fresh(self, obs, now):
        if (
            not isinstance(obs, SpatialObservation)
            or not 0 <= now - obs.captured_at <= 0.8
            or obs.window_identity != self.binding
            or obs.settings != self.settings
            or not obs.creative
            or not obs.source
        ):
            raise FeedbackError(
                "Fresh compatible visible Creative observation required"
            )

    def validate(self, skill, p):
        if skill == "move":
            if (
                set(p) != {"direction", "distance"}
                or p["direction"] not in {"forward", "back", "left", "right"}
                or type(p["distance"]) not in {int, float}
                or not 0.05 <= p["distance"] <= 0.5
            ):
                raise FeedbackError(
                    "Movement supports only 0.05–0.5 blocks on visible flat ground"
                )
        elif skill == "wall":
            raise FeedbackError(
                "Use wall composition with independently inspected doorway and protected surfaces"
            )
        elif skill == "place":
            if set(p) != {"anchor", "axis", "material"} or not re.fullmatch(
                r"minecraft:(?:stone|bricks|oak_planks|cobblestone)", p["material"]
            ):
                raise FeedbackError(
                    "Choose a supported full cube material and reviewed work region"
                )
            cells = (
                wall_cells(p["anchor"], p["axis"])
                if skill == "wall"
                else (tuple(p["anchor"]),)
            )
            if self.protected.intersection(cells):
                raise FeedbackError("Work region intersects a protected structure")
        else:
            raise FeedbackError(
                "Camera/aim use the existing calibrated correction owner"
            )

    def next(self, skill, p, obs, result):
        if skill == "move":
            if not obs.ground_confirmed:
                raise FeedbackError(
                    "Flat ground and clear path are unverified; movement unavailable"
                )
            if sum(result["completed"]) >= p["distance"] - 0.02:
                return None
            return InputCommand(
                InputKind.KEYBOARD,
                {"forward": "w", "back": "s", "left": "a", "right": "d"}[
                    p["direction"]
                ],
                "hold",
                50 if p["distance"] - sum(result["completed"]) <= 0.3 else 100,
                purpose="nearby_translation",
            )
        cells = (
            wall_cells(p["anchor"], p["axis"])
            if skill == "wall"
            else (tuple(p["anchor"]),)
        )
        remaining = [cell for cell in cells if cell not in result["completed"]]
        result["unknown"] = remaining
        if not remaining:
            return None
        if obs.target in remaining and obs.block == p["material"]:
            result["completed"].append(obs.target)
            return None  # caller must inspect next target, never infer unseen cells
        if obs.target is None or obs.face is None or obs.material != p["material"]:
            raise FeedbackError(
                "Fresh reachable face and independently observed selected material required"
            )
        addition = tuple(a + b for a, b in zip(obs.target, obs.face))
        if addition not in remaining or addition in self.protected:
            raise FeedbackError("Aimed addition lies outside the reviewed work region")
        # No mouse relocation: captured crosshair must remain on this face.
        return InputCommand(
            InputKind.MOUSE,
            "right_button",
            "click",
            60,
            target=self.screen_center,
            purpose="creative_one_addition",
        )

    def reconcile(self, skill, p, before, after, result):
        if skill == "move":
            delta = tuple(b - a for a, b in zip(before.position, after.position))
            h = math.radians(before.heading)
            forward = (-math.sin(h), math.cos(h))
            right = (math.cos(h), math.sin(h))
            axis = forward if p["direction"] in {"forward", "back"} else right
            sign = -1 if p["direction"] in {"back", "left"} else 1
            along = (delta[0] * axis[0] + delta[2] * axis[1]) * sign
            cross = abs(delta[0] * axis[1] - delta[2] * axis[0])
            if (
                not 0.005 <= along <= 0.65
                or cross > 0.1
                or abs(delta[1]) > 0.05
                or abs(heading_delta(after.heading, before.heading)) > 0.2
                or abs(after.pitch - before.pitch) > 0.2
            ):
                raise FeedbackError(
                    "Blocked, unexpected translation or camera motion; remaining movement stopped"
                )
            total = sum(result["completed"]) + along
            if total > p["distance"] + 0.12:
                raise FeedbackError("Movement exceeded reviewed distance; stop")
            result["completed"].append(along)
        else:
            cell = tuple(a + b for a, b in zip(before.target, before.face))
            if (
                after.target != cell
                or after.block != p["material"]
                or before.target == after.target
                or math.dist(before.position, after.position) > 0.05
                or abs(heading_delta(after.heading, before.heading)) > 0.2
                or abs(after.pitch - before.pitch) > 0.2
            ):
                raise FeedbackError(
                    "Placement not independently observed at the expected cell; do not retry blindly"
                )
            result["completed"].append(cell)
            result["unknown"] = [v for v in result["unknown"] if v != cell]

    def complete(self, skill, p, result):
        if skill == "move":
            return sum(result["completed"]) >= p["distance"] - 0.02
        return len(result["completed"]) == (19 if skill == "wall" else 1)
