"""Selected-window native ports for shared Minecraft skills.

Configuration chooses scope; only current selected-window pixels supply facts.
The supported scene contains full cubes on flat Creative ground. Unknown shapes,
missing HUD, lost capture or contradictory motion stop the task without retry.
"""

from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import time
from uuid import uuid4

from smb3_agent.camera_native_input import CameraMotionGuard
from smb3_agent.camera_practice import (
    activate_practice,
    resume_practice,
    native_hid_receipt,
)
from smb3_agent.camera_readiness import acquire_readiness
from smb3_agent.feedback_contracts import FeedbackError, heading_delta
from smb3_agent.minecraft_camera_observation import MinecraftCameraObserver
from smb3_agent.minecraft_camera_skill import MinecraftCameraSkill
from smb3_agent.minecraft_inventory import inspect_creative
from smb3_agent.minecraft_scene import (
    HudGlyphDetector,
    CellEvidence,
    FULL_CUBES,
    observed_spatial,
    ray_interval,
)
from smb3_agent.minecraft_settings import require_supported_scene
from smb3_agent.minecraft_skills import MinecraftSkills
from smb3_agent.minecraft_wall import CompositeBudget, WallCoordinator
from smb3_agent.ordinary_input import MacProfileInput
from smb3_agent.input_guardian import InputGuardian
from smb3_agent.skill_runtime import FiniteSkillRuntime


TOTAL_LIMITS = {
    "camera": {"max_seconds": 30, "max_steps": 192, "max_input_ms": 4000},
    "aim": {"max_seconds": 90, "max_steps": 640, "max_input_ms": 20000},
    "move": {"max_seconds": 180, "max_steps": 1024, "max_input_ms": 40000},
    "place": {"max_seconds": 120, "max_steps": 768, "max_input_ms": 24000},
    "wall": {"max_seconds": 240, "max_steps": 1536, "max_input_ms": 60000},
}


def movement_cells(start, end):
    floor, body = set(), set()
    y = round(start[1])
    for x in range(
        math.floor(min(start[0], end[0]) - 0.3),
        math.floor(max(start[0], end[0]) + 0.3) + 1,
    ):
        for z in range(
            math.floor(min(start[2], end[2]) - 0.3),
            math.floor(max(start[2], end[2]) + 0.3) + 1,
        ):
            floor.add((x, y - 1, z))
            body.update(((x, y, z), (x, y + 1, z)))
    return floor, body


def floor_inspection_points(position, heading, cells):
    """Visit every swept floor cell using its nearest interior top-face point.

    Opposite corners under the player caused nearly full turns between adjacent
    cells. Interior clamping permits a straight downward ray for the current
    cell; nearest-heading ordering avoids alternating sides of the sweep.
    This chooses viewpoints only. Each ground/body fact still needs fresh pixels.
    """
    pending = []
    for cell in sorted(cells):
        x = max(cell[0] + 0.2, min(cell[0] + 0.8, position[0]))
        z = max(cell[2] + 0.2, min(cell[2] + 0.8, position[2]))
        dx, dz = x - position[0], z - position[2]
        yaw = heading if math.hypot(dx, dz) < 0.01 else math.degrees(math.atan2(-dx, dz))
        pending.append((cell, (x, cell[1] + 0.999, z), yaw))
    ordered = []
    while pending:
        index = min(range(len(pending)), key=lambda i: abs(heading_delta(pending[i][2], heading)))
        cell, point, heading = pending.pop(index)
        ordered.append((cell, point))
    return ordered


class InventoryInputOwner:
    def __init__(self, driver):
        self.driver = driver

    def cancel(self):
        self.driver.neutralize()
        receipt = self.driver.release_receipt()
        receipt["guardian_closed"] = self.driver.close()
        receipt["confirmed"] &= receipt["guardian_closed"]
        return receipt


class MinecraftNativeRuntime:
    def __init__(
        self, calibration, epoch, canceled, root, *, publish=lambda owner: None
    ):
        self.cal, self.epoch, self.canceled = calibration, epoch, canceled
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.publish = publish
        self.owner = None
        self.host = None
        self.scene_settings = require_supported_scene()
        self.reference = None
        self.creative_receipt = None
        self.detector = HudGlyphDetector.installed()
        self.events = []
        self.target_hud_verified = False
        self.last_view = self.last_spatial = None
        self.latest_inspection = None
        self.budget = CompositeBudget(
            canceled.is_set, max_seconds=240, max_steps=1536, max_input_ms=60000
        )

    def _publish(self, owner):
        self.owner = owner
        self.publish(owner)
        if self.canceled.is_set():
            owner.cancel()
            raise FeedbackError("Control was revoked while arming")

    def authority(self):
        if self.canceled.is_set() or require_supported_scene() != self.scene_settings:
            raise FeedbackError("Task canceled or Minecraft settings changed")
        self.cal.binding.require(self.host.detect_window(), execution=True)
        self.budget.consume()

    def prepare(self, *, material, expected=None):
        self.host = activate_practice(self.cal.binding)
        import Quartz as q

        if q.CGCursorIsVisible():
            self.budget.consume(30)
        resume_practice(self.host, self.cal.binding, self.root, self.canceled)
        self.observer = MinecraftCameraObserver(
            self.host,
            self.cal.environment,
            self.cal.calibration_id,
            self.root / "frames",
        )
        current = self.view()
        if expected:
            if (
                max(
                    abs(heading_delta(current.heading, expected["heading"])),
                    abs(current.pitch - expected["pitch"]),
                )
                > 0.2
            ):
                raise FeedbackError(
                    "View changed after review; inspect and review again"
                )
            if "position" in expected:
                pose = observed_spatial(
                    current.frame.evidence_reference,
                    view=current,
                    detector=self.detector,
                    now=time.monotonic(),
                )
                if math.dist(pose.position, expected["position"]) > 0.05:
                    raise FeedbackError(
                        "Player moved after review; inspect and review again"
                    )
        self.reference, self.creative_receipt = inspect_creative(
            self.host,
            self.cal.binding,
            self.root / "inventory",
            self.canceled,
            material=material,
            budget=self.budget,
            expected_settings=self.scene_settings,
            publish_driver=lambda d: self._publish(InventoryInputOwner(d)),
        )
        self.owner = None
        # Readiness has its own finite contract; reserve its maximum up front.
        self.budget.consume(240)
        self.readiness = acquire_readiness(
            self.observer,
            self.cal.binding,
            self.cal.environment.controls_id,
            self.epoch,
            self.canceled,
            self.root / "readiness",
            publish_guard=self._publish,
            neutral_receipt=native_hid_receipt,
            feedback_identity=(self.cal.environment.sha256, self.cal.calibration_id),
        )
        self.owner = None
        self.initial = self.spatial() if material else self.view()
        if material:
            # Positive targeted-block pixels prove this HUD entry is actually
            # loaded before any later qualified miss may establish clearance.
            if self.initial.target is not None and self.initial.block in FULL_CUBES:
                self.target_hud_verified = True
            else:
                initial = self.initial
                self.aim(initial.heading, 65)
                positive = self.spatial()
                if positive.target is None or positive.block not in FULL_CUBES:
                    raise FeedbackError(
                        "Targeted-block HUD not positively observed; no empty-cell inference permitted"
                    )
                self.target_hud_verified = True
                self.aim(initial.heading, initial.pitch)
                self.initial = self.spatial()
        return self.initial

    def view(self):
        self.authority()
        obs = self.observer.observe(execution=True)
        obs.require(time.monotonic(), 0.8, 0.1)
        self.last_view = obs
        return obs

    def spatial(self):
        view = self.view()
        obs = observed_spatial(
            view.frame.evidence_reference,
            view=view,
            detector=self.detector,
            now=time.monotonic(),
        )
        if not self.creative_receipt or not self.creative_receipt["accepted"]:
            raise FeedbackError("Current Creative inventory inspection required")
        # A current selected-slot icon must agree with the independently read tooltip.
        material = (
            self.reference.observe(view.frame.evidence_reference)
            if self.reference
            else None
        )
        self.last_spatial = replace(
            obs,
            creative=True,
            material=material,
            settings=self.scene_settings,
            source=obs.source
            + "|creative:"
            + self.creative_receipt["creative_source"]
            + (
                "|material:" + self.reference.inventory_sha256 if self.reference else ""
            ),
        )
        return self.last_spatial

    def neutralize(self):
        receipts = []
        if self.owner:
            receipts.append(self.owner.cancel())
            self.owner = None
        hid = native_hid_receipt()
        safe = hid["confirmed"] and all(
            r.get("confirmed", r.get("motion_worker_reaped", False)) for r in receipts
        )
        return {"confirmed": safe, "owners": receipts, "hid": hid}

    def aim(self, heading, pitch, budget=None):
        """Split large rotations into finite observed goals under the same budget."""
        obs = self.view()
        if not -90 <= pitch <= 90:
            raise FeedbackError(
                "Target needs unsupported steep aiming; reposition manually"
            )
        start_position = observed_spatial(
            obs.frame.evidence_reference,
            view=obs,
            detector=self.detector,
            now=time.monotonic(),
        ).position

        def stationary(current):
            position = observed_spatial(
                current.frame.evidence_reference,
                view=current,
                detector=self.detector,
                now=time.monotonic(),
            ).position
            if math.dist(position, start_position) > 0.02:
                raise FeedbackError(
                    "Player position changed during aiming; input stopped, inspect again"
                )
            return current

        for _ in range(24):
            stationary(obs)
            dh, dp = heading_delta(heading, obs.heading), pitch - obs.pitch
            if max(abs(dh), abs(dp)) + obs.uncertainty_degrees <= 0.35:
                return obs
            # One axis per child keeps each <=24-degree turn within the
            # child's 192-unit budget and avoids repeated worker setup/settling.
            horizontal = abs(dh) >= abs(dp)
            goal = {
                "heading": (
                    obs.heading + (max(-24, min(24, dh)) if horizontal else 0) + 180
                )
                % 360
                - 180,
                "pitch": obs.pitch + (0 if horizontal else max(-24, min(24, dp))),
            }
            guard = CameraMotionGuard(
                self.cal.binding,
                self.epoch,
                self.cal.environment.controls_id,
                self.root / "motion" / uuid4().hex,
            )
            self._publish(guard)

            def emit(action):
                self.authority()
                if not native_hid_receipt()["confirmed"]:
                    raise FeedbackError(
                        "Keyboard or mouse button is held; Take control, release it and inspect again"
                    )
                receipt = guard.pulse(action)
                if self.canceled.wait(
                    max(0, receipt["delivered_at"] + 0.14 - time.monotonic())
                ):
                    raise FeedbackError("Canceled after motion; outcome retained")
                return receipt

            first_capture = True

            def observe_child():
                nonlocal first_capture
                current = stationary(self.view())
                if first_capture:
                    first_capture = False
                    if (
                        max(
                            abs(heading_delta(current.heading, obs.heading)),
                            abs(current.pitch - obs.pitch),
                        )
                        > 0.1
                    ):
                        raise FeedbackError(
                            "View changed before the first task pulse; inspect and review again"
                        )
                return current

            runtime = FiniteSkillRuntime(
                observe=observe_child,
                emit=emit,
                neutralize=self.neutralize,
                canceled=self.canceled.is_set,
            )
            result = runtime.run(
                "aim",
                MinecraftCameraSkill(self.cal, self.epoch),
                goal,
                budget=self.budget,
            )
            self.events.append({"skill": "aim", "goal": goal, "result": result})
            if result["status"] != "completed":
                raise FeedbackError(result.get("reason", "Camera goal unverified"))
            first = stationary(self.view())
            if self.canceled.wait(0.2):
                raise FeedbackError("Canceled during observed settling")
            obs = stationary(self.view())
            if (
                max(
                    abs(heading_delta(obs.heading, first.heading)),
                    abs(obs.pitch - first.pitch),
                )
                > 0.1
            ):
                raise FeedbackError(
                    "Unexplained motion after worker release; camera disabled for this session"
                )
        raise FeedbackError("Finite aiming composition exhausted")

    def aim_point(self, point):
        obs = self.spatial()
        eye = (obs.position[0], obs.position[1] + 1.62, obs.position[2])
        dx, dy, dz = (b - a for a, b in zip(eye, point))
        if math.sqrt(dx * dx + dy * dy + dz * dz) > 19:
            raise FeedbackError("Inspection target is outside visible HUD reach")
        return self.aim(
            obs.heading
            if math.hypot(dx, dz) < 0.01
            else math.degrees(math.atan2(-dx, dz)),
            math.degrees(math.atan2(-dy, math.hypot(dx, dz))),
        )

    def inspect(self, cell, budget=None):
        cell = tuple(cell)
        self.aim_point(tuple(v + 0.5 for v in cell))
        obs = self.spatial()
        if obs.target == cell and obs.block in FULL_CUBES:
            evidence = CellEvidence(
                cell,
                obs.block,
                obs.captured_at,
                obs.source,
                obs.window_identity,
                obs.settings,
            )
            self.latest_inspection = (evidence, obs.position)
            return evidence
        hit = ray_interval(obs.position, obs.heading, obs.pitch, cell)
        if hit is None:
            return None
        if obs.target is None:
            # Always-visible HUD configuration and complete pose/FPS are checked
            # above. Missing default F3 rows are never accepted as a ray miss.
            clear = self.target_hud_verified and hit[1] < 19
        elif obs.block in FULL_CUBES:
            target = ray_interval(obs.position, obs.heading, obs.pitch, obs.target)
            clear = target is not None and hit[1] <= target[0] + 1e-7
        else:
            clear = False  # Partial/unknown blocks cannot establish volume clearance.
        if not clear:
            return None
        # Additional separated rays reject common partial geometry and occlusion.
        for offset in (
            (0.2, 0.2, 0.2),
            (0.8, 0.8, 0.8),
            (0.2, 0.8, 0.8),
            (0.8, 0.2, 0.2),
        ):
            self.aim_point(tuple(a + b for a, b in zip(cell, offset)))
            check = self.spatial()
            interval = ray_interval(check.position, check.heading, check.pitch, cell)
            if interval is None or (check.target == cell):
                return None
            if check.target is None and not self.target_hud_verified:
                return None
            if check.target is not None:
                target = ray_interval(
                    check.position, check.heading, check.pitch, check.target
                )
                if (
                    check.block not in FULL_CUBES
                    or target is None
                    or interval[1] > target[0] + 1e-7
                ):
                    return None
            obs = check
        evidence = CellEvidence(
            cell, None, obs.captured_at, obs.source, obs.window_identity, obs.settings
        )
        self.latest_inspection = (evidence, obs.position)
        return evidence

    def approach(self, cell, budget=None):
        """Use at most two audited nearby translations; never jump or fly."""
        returning = any(type(v) is float for v in cell)
        for _ in range(2):
            recent = getattr(self, "last_spatial", None)
            obs = (
                recent
                if recent and 0 <= time.monotonic() - recent.captured_at <= 0.8
                else self.spatial()
            )
            point = (
                tuple(cell) if returning else (cell[0] + 0.5, cell[1], cell[2] + 0.5)
            )
            eye = (obs.position[0], obs.position[1] + 1.62, obs.position[2])
            if returning and math.dist(obs.position, point) <= 0.12:
                return
            if not returning and math.dist(eye, point) <= 4.4:
                return
            dx, dz = point[0] - obs.position[0], point[2] - obs.position[2]
            horizontal = math.hypot(dx, dz)
            if returning and (horizontal > 1 or abs(obs.position[1] - point[1]) > 0.05):
                raise FeedbackError(
                    "Stop point needs unsupported travel; return manually and review"
                )
            if horizontal < 0.15:
                raise FeedbackError(
                    "A raised flat platform is needed to reach this face"
                )
            distance = (
                min(0.5, horizontal)
                if returning
                else min(0.5, max(0.15, math.dist(eye, point) - 4.2))
            )
            from smb3_agent.minecraft_session import CHECKED_FEATURES

            if not CHECKED_FEATURES["move"]:
                raise FeedbackError(
                    "Nearby movement remains unavailable; reposition manually and check scope"
                )
            self.aim(math.degrees(math.atan2(-dx, dz)), obs.pitch)
            moved = self.move({"direction": "forward", "distance": distance})
            if moved["status"] != "completed":
                raise FeedbackError(moved.get("reason", "Nearby approach unverified"))
        raise FeedbackError(
            "Cell or stop point still out of reach after bounded approach"
        )

    def _driver(self):
        driver = MacProfileInput(
            window_provider=self.host.detect_window,
            authority_guard=self.authority,
            isolation_guard=lambda w: self.cal.binding.require(w, execution=True),
            external_guard=InputGuardian(self.root / (uuid4().hex + "-input.jsonl")),
        )
        self._publish(InventoryInputOwner(driver))
        driver.arm()
        return driver

    def place(self, cell, material, budget=None):
        self.approach(cell)
        cached = getattr(self, "latest_inspection", None)
        current = getattr(self, "last_spatial", None)
        now = time.monotonic()
        before = (
            cached[0]
            if cached
            and current is not None
            and cached[0].cell == tuple(cell)
            and 0 <= now - cached[0].captured_at <= 0.8
            and 0 <= now - current.captured_at <= 0.8
            and current.captured_at >= cached[0].captured_at
            and current.window_identity == cached[0].window_identity
            and current.settings == cached[0].settings
            and math.dist(current.position, cached[1]) <= 0.02
            else self.inspect(cell)
        )
        if before is not None and before.material == material:
            result = {
                "status": "completed",
                "completed": [list(cell)],
                "existing": [list(cell)],
                "placed": [],
                "reason": "Requested cell already has the chosen full block; no addition posted",
            }
            self.events.append({"skill": "place", "cell": cell, "result": result})
            return result
        if before is None or before.material is not None:
            raise FeedbackError(
                "Addition cell is not independently clear; inspect remaining work"
            )
        # The doorway lintel has no block underneath. Try six bounded
        # adjacent support faces; only actual first-hit pixels can qualify one.
        supports = ((0, 1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0))
        supported = False
        for face in supports:
            support = tuple(a - n for a, n in zip(cell, face))
            point = tuple(a + 0.5 + n * 0.499 for a, n in zip(support, face))
            self.aim_point(point)
            obs = self.spatial()
            if obs.target == cell:
                raise FeedbackError(
                    "Work cell became occupied before placement; no addition posted"
                )
            if obs.target == support and obs.face == face and obs.block in FULL_CUBES:
                supported = True
                break
        if not supported:
            raise FeedbackError(
                "No independently reachable support face; reposition manually and inspect"
            )
        if obs.material != material:
            raise FeedbackError("Selected material changed")
        import Quartz as q

        location = q.CGEventGetLocation(q.CGEventCreate(None))
        point = (round(location.x), round(location.y))
        driver = self._driver()

        def emit(command):
            driver.send(command)
            if self.canceled.wait(0.15):
                raise FeedbackError("Canceled after addition; do not retry blindly")

        provider = MinecraftSkills(
            obs.window_identity, self.scene_settings, screen_center=point
        )
        result = FiniteSkillRuntime(
            observe=self.spatial,
            emit=emit,
            neutralize=self.neutralize,
            canceled=self.canceled.is_set,
        ).run(
            "place",
            provider,
            {"anchor": list(cell), "axis": "x", "material": material},
            budget=self.budget,
        )
        self.latest_inspection = None
        self.events.append({"skill": "place", "cell": cell, "result": result})
        if result["status"] != "completed":
            raise FeedbackError(
                result.get("reason", "Addition not verified; no blind retry")
            )
        return result

    def move(self, parameters):
        obs = self.spatial()
        h = math.radians(obs.heading)
        sign = -1 if parameters["direction"] in {"back", "left"} else 1
        vector = (
            (-math.sin(h), math.cos(h))
            if parameters["direction"] in {"forward", "back"}
            else (math.cos(h), math.sin(h))
        )
        finish = (
            obs.position[0] + vector[0] * sign * parameters["distance"],
            obs.position[1],
            obs.position[2] + vector[1] * sign * parameters["distance"],
        )
        if abs(obs.position[1] - round(obs.position[1])) > 0.02:
            raise FeedbackError("Movement needs grounded integer-height feet")
        # Include the executor's permitted 0.12-block overshoot and the full
        # swept width, including diagonal rectangle corners between endpoints.
        end = (
            finish[0] + vector[0] * sign * 0.12,
            finish[1],
            finish[2] + vector[1] * sign * 0.12,
        )
        floor, body = movement_cells(obs.position, end)
        # Fresh first-hit ground rays also inspect the body cells they cross.
        # If a supported full cube occupied any crossed cell, it would precede
        # the ground hit. This avoids repeatedly rotating inside each body cell.
        clearance = {}
        ground = {}
        for cell, point in floor_inspection_points(obs.position, obs.heading, floor):
            self.aim_point(point)
            current = self.spatial()
            if math.dist(current.position, obs.position) > 0.02:
                raise FeedbackError(
                    "Player moved during path inspection; inspect again"
                )
            if (
                current.target != cell
                or current.block not in FULL_CUBES
                or current.face != (0, 1, 0)
            ):
                raise FeedbackError(
                    "Swept floor or intervening clearance is unknown; movement stopped"
                )
            target = ray_interval(
                current.position, current.heading, current.pitch, cell
            )
            if target is None:
                raise FeedbackError("Ground ray is ambiguous; movement stopped")
            ground[cell] = CellEvidence(
                cell,
                current.block,
                current.captured_at,
                current.source,
                current.window_identity,
                current.settings,
            )
            for air in body:
                segment = ray_interval(
                    current.position, current.heading, current.pitch, air
                )
                if segment is not None and segment[1] <= target[0] + 1e-7:
                    clearance[air] = CellEvidence(
                        air,
                        None,
                        current.captured_at,
                        current.source,
                        current.window_identity,
                        current.settings,
                    )
        if set(clearance) != body:
            raise FeedbackError(
                "Swept body clearance is not independently observed; movement stopped"
            )
        self.events.append(
            {
                "skill": "movement_path_inspection",
                "floor": list(ground.values()),
                "body": list(clearance.values()),
            }
        )
        self.aim(obs.heading, obs.pitch)
        if math.dist(self.spatial().position, obs.position) > 0.02:
            raise FeedbackError("Player moved during path inspection; inspect again")
        driver = self._driver()

        def observe():
            return replace(self.spatial(), ground_confirmed=True)

        def emit(command):
            driver.send(command)
            if self.canceled.wait(0.25):
                raise FeedbackError("Canceled during movement settling")

        provider = MinecraftSkills(obs.window_identity, self.scene_settings)
        result = FiniteSkillRuntime(
            observe=observe,
            emit=emit,
            neutralize=self.neutralize,
            canceled=self.canceled.is_set,
        ).run("move", provider, parameters, budget=self.budget)
        self.events.append({"skill": "move", "result": result})
        return result

    def run(self, kind, parameters, scope=None, *, expected=None):
        result = {"status": "partial", "reason": "", "completed": []}
        try:
            if kind not in TOTAL_LIMITS:
                raise FeedbackError("Unsupported native task")
            self.budget = CompositeBudget(self.canceled.is_set, **TOTAL_LIMITS[kind])
            self.prepare(material=kind not in {"camera", "aim"}, expected=expected)
            if kind in {"camera", "aim"}:
                final = self.aim(parameters["heading"], parameters["pitch"])
                if kind == "aim" and "target" in parameters:
                    observed = self.spatial()
                    if observed.target != tuple(
                        parameters["target"]
                    ) or observed.face != tuple(parameters["face"]):
                        raise FeedbackError(
                            "Requested block face is not independently observed after aiming"
                        )
                result = {
                    "status": "completed",
                    "completed": [{"heading": final.heading, "pitch": final.pitch}],
                }
            elif kind == "move":
                result = self.move(parameters)
            elif kind == "place":
                result = self.place(tuple(parameters["anchor"]), parameters["material"])
            elif kind == "wall":
                result = WallCoordinator(
                    inspect=self.inspect,
                    place=self.place,
                    approach=self.approach,
                    observe_position=lambda: self.spatial().position,
                    neutralize=self.neutralize,
                ).run(scope, self.budget)
            else:
                raise FeedbackError("Unsupported native task")
        except Exception as exc:
            result["reason"] = str(exc)
        finally:
            release = self.neutralize()
            result["release"] = release
            if not release["confirmed"]:
                result.update(status="partial", reason="Input release unconfirmed")
            result["steps_used"] = self.budget.steps
            result["input_ms"] = self.budget.input_ms
            result = json.loads(json.dumps(result, default=lambda value: asdict(value)))
            try:
                (self.root / "result.json").write_text(
                    json.dumps(result, indent=2) + "\n"
                )
                (self.root / "events.json").write_text(
                    json.dumps(self.events, default=lambda v: asdict(v), indent=2)
                    + "\n"
                )
            except OSError as exc:
                # Gameplay cannot be repeated to repair a local file-write failure.
                result["diagnostics_saved"] = False
                result["diagnostics_reason"] = "Local diagnostic save failed: " + str(
                    exc
                )
        return result
