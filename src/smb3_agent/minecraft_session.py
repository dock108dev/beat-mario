"""Ordinary Minecraft lifecycle on the existing player/setup server."""

from dataclasses import asdict, replace
import math
import re
import threading
import time
from uuid import uuid4

from smb3_agent.camera_practice import calibration_from
from smb3_agent.feedback_contracts import FeedbackError
from smb3_agent.minecraft_native import MinecraftNativeRuntime
from smb3_agent.minecraft_wall import WallScope
from smb3_agent.player_store import VERSION

# Enable a gameplay family only after its focused native check. This candidate's
# calibration has native evidence; gameplay checks are still in progress.
CHECKED_FEATURES = {
    "calibrate": True,
    "camera": True,
    "aim": False,
    "move": False,
    "place": False,
    "wall": False,
}


class MinecraftPlayerSession:
    def __init__(self, camera, store, *, runtime_factory=MinecraftNativeRuntime):
        self.camera, self.store, self.factory = camera, store, runtime_factory
        self.cancel = threading.Event()
        self.epoch = 0
        self.owner = None
        self.worker = None
        self.client = None
        self.lease = 0
        self.closed = threading.Event()
        self.last_pose = None
        self.scope = None
        self.review = None
        self.result = None
        self.release_blocked = False
        self.displays = []
        self.reason = (
            "Choose a Minecraft window, confirm disposable practice and calibrate."
        )
        self.state = "disconnected"
        self.watchdog = threading.Thread(target=self._watch, daemon=True)
        self.watchdog.start()

    @property
    def busy(self):
        return (
            bool(self.worker and self.worker.is_alive())
            or self.camera.snapshot()["busy"]
        )

    def snapshot(self):
        return {
            "state": self.state,
            "reason": self.reason,
            "busy": self.busy,
            "features": dict(CHECKED_FEATURES),
            "camera": self.camera.snapshot(),
            "scope": asdict(self.scope) if self.scope else None,
            "pose": asdict(self.last_pose) if self.last_pose else None,
            "result": self.result,
            "displays": self.displays,
            "release_blocked": self.release_blocked,
            "connected": bool(self.camera.selected) and not self.release_blocked,
        }

    def _client(self, payload):
        client = payload.get("client_id")
        if not isinstance(client, str) or not 1 <= len(client) <= 100:
            raise ValueError("Keep this workspace page open during native work")
        if self.client and self.client != client and self.busy:
            raise ValueError("Take control on the owning page first")
        self.client = client
        self.lease = time.monotonic()

    def revoke(self, reason, *, disconnect=False):
        self.cancel.set()  # before task/state locks or disk work
        self.epoch += 1
        self.review = None
        receipt = self.owner.cancel() if self.owner else {"confirmed": True}
        camera_receipt = self.camera.revoke(reason)
        safe = receipt.get(
            "confirmed", receipt.get("motion_worker_reaped", False)
        ) and camera_receipt.get(
            "confirmed",
            all(
                camera_receipt.get(k, False)
                for k in (
                    "epoch_revoked",
                    "pending_motion_revoked",
                    "motion_worker_reaped",
                )
            ),
        )
        self.release_blocked = not safe
        self.reason = reason
        if disconnect:
            self.camera.selected = None
            self.last_pose = None
            self.scope = None
            self.state = "disconnected"
        elif not self.busy:
            self.state = "stopped"
        return safe

    def require_idle(self):
        if self.closed.is_set() or self.busy or self.release_blocked:
            raise ValueError(
                "Wait for neutral handback before changing profiles or granting new authority"
            )

    def dispatch(self, action, p):
        self._client(p)
        if action == "heartbeat":
            if self.camera.client == self.client:
                self.camera.lease = time.monotonic()
            return
        self.require_idle()
        if action == "arrange":
            from smb3_agent.window_setup import arrange_selected

            selection = p.get("selection")
            if not any(
                selection and {**w, "bounds": list(w["bounds"])} == selection
                for w in self.camera.window_rows
            ):
                raise ValueError("Refresh and choose the exact Minecraft window")
            self.revoke("Window arranged; recalibration required", disconnect=True)
            arrange_selected(
                selection, display_id=p.get("display_id"), viewport=(854, 508)
            )
            self.camera.dispatch("windows", p)
            self.reason = "Window arranged. Confirm disposable practice and calibrate."
            return
        if action in {"windows", "calibrate", "connect"}:
            self.revoke("New Minecraft setup; fresh review required")
            if action in {"calibrate", "connect"}:
                self.last_pose = self.scope = None
            if action == "calibrate":
                self.camera.selected = None
            self.camera.dispatch(action, p)
            if action == "windows":
                from smb3_agent.window_setup import available_displays

                self.displays = available_displays()
            self.state = self.camera.state
            self.reason = self.camera.reason
            return
        if action in {"scope", "protect"}:
            if not self.camera.selected:
                raise ValueError("Connect your current app-created calibration first")
            if action == "protect" and self.scope is None:
                raise ValueError(
                    "Check a wall work region before marking protected blocks"
                )
            if p.get("disposable_confirmation") is not True:
                raise ValueError("Confirm this is a disposable Creative world")
            if p.get("axis") not in {"x", "z"}:
                raise ValueError("Choose the wall direction")
            self.revoke("Checking visible block and world scope")
            self.cancel = threading.Event()
            epoch = self.epoch
            self.state = "checking"
            self.worker = threading.Thread(
                target=self._scope,
                args=({**p, "protect_only": action == "protect"}, epoch, self.cancel),
                daemon=True,
            )
            self.worker.start()
            return
        raise ValueError("Unknown Minecraft setup action")

    def _publish(self, owner, epoch, cancel):
        self.owner = owner
        if epoch != self.epoch or cancel.is_set():
            owner.cancel()
            raise FeedbackError("Input authority revoked while arming")

    def _runtime(self, root, epoch, cancel):
        if not self.camera.selected:
            raise ValueError("Connect a current calibration")
        cal = calibration_from(self.camera.selected["calibration"])
        self.camera._require_calibration(cal)
        return self.factory(
            cal, epoch, cancel, root, publish=lambda o: self._publish(o, epoch, cancel)
        )

    def _scope(self, p, epoch, cancel):
        native = None
        try:
            native = self._runtime(
                self.store.root / "sessions/minecraft" / uuid4().hex, epoch, cancel
            )
            obs = native.prepare(material=True)
            if p.get("protect_only"):
                if obs.target is None or obs.block not in {
                    "minecraft:grass_block",
                    "minecraft:dirt",
                    "minecraft:stone",
                    "minecraft:bricks",
                    "minecraft:oak_planks",
                    "minecraft:cobblestone",
                }:
                    raise FeedbackError(
                        "Point at a visible reachable full block to protect"
                    )
                if obs.target in self.scope.doorway:
                    raise FeedbackError(
                        "A doorway cell cannot also be a protected structure"
                    )
                protected = tuple(dict.fromkeys(self.scope.protected + (obs.target,)))
                scope = replace(self.scope, protected=protected, source=obs.source)
                if epoch != self.epoch or cancel.is_set():
                    raise FeedbackError("Protection check canceled")
                self.scope, self.last_pose = scope, obs
                self.state = "connected"
                self.reason = "Pointed block marked protected. Mark each relevant exposed block; Start and final inspection recheck them."
                return
            if (
                obs.target is None
                or obs.block
                not in {
                    "minecraft:grass_block",
                    "minecraft:dirt",
                    "minecraft:stone",
                    "minecraft:bricks",
                    "minecraft:oak_planks",
                    "minecraft:cobblestone",
                }
                or obs.face != (0, 1, 0)
            ):
                raise FeedbackError(
                    "Point at a nearby full ground block top, then check scope again"
                )
            target = obs.target
            axis = p["axis"]
            anchor = (
                target[0] - (3 if axis == "x" else 0),
                target[1] + 1,
                target[2] - (3 if axis == "z" else 0),
            )
            # Protected scope is intent, not a claim that its cells are observed.
            protected = tuple(tuple(v) for v in p.get("protected", []))
            scope = WallScope(
                anchor, axis, obs.material, protected, tuple(obs.position), obs.source
            )
            if epoch != self.epoch or cancel.is_set():
                raise FeedbackError("Scope check canceled")
            self.last_pose, self.scope = obs, scope
            self.state = "connected"
            self.reason = "Visible scope checked. Save it as configuration, then request and review work. Start rechecks live state."
        except Exception as exc:
            self.state = "partial"
            self.reason = str(exc)
        finally:
            if native:
                release = native.neutralize()
                if not release["confirmed"]:
                    self.release_blocked = True
                    self.state, self.reason = (
                        "partial",
                        "Input release unconfirmed; Take control before new work",
                    )
            self.owner = None

    def parameters(self, kind, text):
        obs = self.last_pose
        if not self.camera.selected:
            raise ValueError(
                "Connect a current calibration before requesting native work"
            )
        words = text.casefold()
        if kind in {"camera", "aim"}:
            if obs is None:
                # Camera-only requests may use the last calibration's measured
                # final observation as a preview; Start must bind fresh state.
                cal = calibration_from(self.camera.selected["calibration"])
                obs = cal.samples[-1].after
            heading, pitch = obs.heading, obs.pitch
            if kind == "aim":
                if (
                    not hasattr(obs, "position")
                    or obs.target is None
                    or obs.face is None
                ):
                    raise ValueError(
                        "Point at a nearby full block top and Check visible block and scope before aiming"
                    )
                position = obs.position
                point = tuple(v + 0.5 + n * 0.499 for v, n in zip(obs.target, obs.face))
                dx, dy, dz = (
                    point[0] - position[0],
                    point[1] - (position[1] + 1.62),
                    point[2] - position[2],
                )
                heading = math.degrees(math.atan2(-dx, dz))
                pitch = math.degrees(math.atan2(-dy, math.hypot(dx, dz)))
                return {
                    "heading": heading,
                    "pitch": pitch,
                    "target": list(obs.target),
                    "face": list(obs.face),
                }
            else:
                match = re.search(r"(\d+(?:\.\d+)?)\s*(?:degrees?|°)", words)
                amount = float(match[1]) if match else 2
                if not 0.3 <= amount <= 15:
                    raise ValueError("Choose 0.3–15 degrees for one camera request")
                directions = [
                    v
                    for v in ("left", "right", "up", "down")
                    if re.search(r"\b" + v + r"\b", words)
                ]
                if len(directions) != 1:
                    raise ValueError("Say look left/right/up/down by a small angle")
                if directions[0] in {"left", "right"}:
                    heading = (
                        heading + amount * (1 if directions[0] == "right" else -1) + 180
                    ) % 360 - 180
                else:
                    pitch += amount * (1 if directions[0] == "down" else -1)
            return {"heading": heading, "pitch": pitch}
        if kind == "move":
            match = re.search(
                r"\b(?:move|walk|step)\s+(forward|back|left|right)\s+(0\.\d+)\s+blocks?\b",
                words,
            )
            if not match or not 0.05 <= float(match[2]) <= 0.5:
                raise ValueError("Say move forward/back/left/right 0.05–0.5 blocks")
            return {"direction": match[1], "distance": float(match[2])}
        if not self.scope:
            raise ValueError("Check a visible work scope and selected block first")
        if any(v in words for v in ("stone", "bricks", "oak", "cobblestone")):
            requested = (
                "cobblestone"
                if "cobblestone" in words
                else "oak_planks"
                if "oak" in words
                else "bricks"
                if "bricks" in words
                else "stone"
            )
            if self.scope.material != "minecraft:" + requested:
                raise ValueError(
                    "Choose that block manually and inspect the scope again; inventory changes are unavailable"
                )
        if (
            kind == "wall"
            and any(
                v in words
                for v in ("marked", "protected", "structure alone", "preserve")
            )
            and not self.scope.protected
        ):
            raise ValueError(
                "Point at the structure and mark its exposed blocks protected before reviewing this wall"
            )
        anchor = self.scope.anchor
        if kind == "place":
            if not hasattr(self.last_pose, "position"):
                raise ValueError(
                    "Check a visible work region again before one addition"
                )
            from smb3_agent.minecraft_skills import wall_cells

            base = [
                cell
                for cell in wall_cells(self.scope.anchor, self.scope.axis)
                if cell[1] == self.scope.anchor[1]
            ]
            anchor = min(
                base,
                key=lambda cell: math.dist(
                    self.last_pose.position, tuple(v + 0.5 for v in cell)
                ),
            )
        return {
            "anchor": list(anchor),
            "axis": self.scope.axis,
            "material": self.scope.material,
        }

    def bind_review(self, plan):
        self.require_idle()
        if not CHECKED_FEATURES.get(plan["kind"]):
            raise ValueError(
                "This gameplay family has not passed its focused native check; Start remains disabled"
            )
        if not self.camera.selected:
            raise ValueError("Reconnect a current calibration")
        self.review = {
            "plan": plan,
            "epoch": self.epoch,
            "at": time.monotonic(),
            "calibration": self.camera.selected["id"],
            "scope": self.scope,
        }

    def start(self, plan, profile_id, p):
        self._client(p)
        self.require_idle()
        review = self.review
        if (
            not review
            or review["plan"]["id"] != plan["id"]
            or review["epoch"] != self.epoch
            or time.monotonic() - review["at"] > 30
            or not self.camera.selected
            or review["calibration"] != self.camera.selected["id"]
        ):
            raise ValueError("Review the current bounded scope again before Start")
        if not CHECKED_FEATURES.get(plan["kind"]):
            raise ValueError("This task remains unavailable")
        if p.get("disposable_confirmation") is not True:
            raise ValueError(
                "Confirm disposable practice and exclusive Mac input before Start"
            )
        self.cancel = threading.Event()
        self.review = None
        self.state = "executing"
        epoch = self.epoch
        self.worker = threading.Thread(
            target=self._run,
            args=(plan, profile_id, review["scope"], epoch, self.cancel),
            daemon=True,
        )
        self.worker.start()

    def _run(self, plan, profile_id, scope, epoch, cancel):
        native = None
        try:
            native = self._runtime(
                self.store.root / "sessions/minecraft" / uuid4().hex, epoch, cancel
            )
            result = native.run(
                plan["kind"],
                plan["parameters"],
                scope,
                expected=plan.get("initial_pose"),
            )
            self.last_pose = native.last_spatial or native.last_view or self.last_pose
        except Exception as exc:
            result = {"status": "partial", "reason": str(exc), "completed": []}
        finally:
            if native:
                result["release"] = native.neutralize()
            self.owner = None
            if not result.get("release", {}).get("confirmed", True):
                self.release_blocked = True
                result.update(
                    status="partial",
                    reason="Input release unconfirmed; Take control before new work",
                )
        if any(
            v in result.get("reason", "").casefold()
            for v in ("contradictory camera", "unexplained", "view changed before")
        ):
            if self.camera.selected:
                cal = calibration_from(self.camera.selected["calibration"])
                self.camera._invalidate_calibration(cal, result["reason"])
            self.camera.selected = None
            self.last_pose = None
        result.update(request=plan["request"], version=VERSION)
        try:
            self.store.record(profile_id, result)
        except OSError as exc:
            result["history_saved"] = False
            result["history_reason"] = (
                "Observed outcome retained on screen; history save failed: " + str(exc)
            )
        self.result = result
        self.state = result["status"]
        self.reason = (
            result.get("history_reason")
            or result.get("diagnostics_reason")
            or result.get("reason")
            or (
                "Task completed with independent observations and confirmed release."
                if result["status"] == "completed"
                else "Partial work retained; review fresh state before another task."
            )
        )

    def _watch(self):
        while not self.closed.wait(0.1):
            if self.busy and self.client and time.monotonic() - self.lease > 3:
                self.revoke("Workspace disconnected or paused; input stopped")

    def close(self):
        self.closed.set()
        safe = self.revoke("Game Companion closing", disconnect=True)
        if self.worker:
            self.worker.join(2)
        self.watchdog.join(0.5)
        if not safe or (self.worker and self.worker.is_alive()):
            raise ValueError("Minecraft cleanup unconfirmed")
