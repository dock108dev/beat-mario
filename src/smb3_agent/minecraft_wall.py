"""Bounded wall composition, using the shared finite skills and cell inspection.

Every child observation/input consumes the one reviewed task budget. Each
addition is dispatched once and inspected independently; unknown effects are
terminal. Correct existing cells count separately and never terminate traversal.
"""

from dataclasses import dataclass
import math
import time

from smb3_agent.feedback_contracts import FeedbackError
from smb3_agent.minecraft_skills import wall_cells


@dataclass(frozen=True)
class WallScope:
    anchor: tuple
    axis: str
    material: str
    protected: tuple
    stop_point: tuple
    source: str

    def __post_init__(self):
        cells = wall_cells(self.anchor, self.axis)
        if (
            self.material
            not in {
                "minecraft:stone",
                "minecraft:bricks",
                "minecraft:oak_planks",
                "minecraft:cobblestone",
            }
            or not self.source
            or len(self.protected) > 64
            or any(
                len(v) != 3 or any(type(n) is not int for n in v)
                for v in self.protected
            )
            or set(cells).intersection(self.protected)
            or len(self.stop_point) != 3
            or not all(
                type(n) in {float, int} and math.isfinite(n) for n in self.stop_point
            )
            or math.dist(self.stop_point, self.anchor) > 10
            or not -0.05 <= self.stop_point[1] - self.anchor[1] <= 1.05
        ):
            raise FeedbackError(
                "Review a visible anchor, supported material, protected cells and nearby stop point"
            )

    @property
    def doorway(self):
        a = self.anchor
        return tuple(
            (
                a[0] + (3 if self.axis == "x" else 0),
                a[1] + y,
                a[2] + (3 if self.axis == "z" else 0),
            )
            for y in (0, 1)
        )


class CompositeBudget:
    def __init__(
        self,
        canceled,
        *,
        clock=time.monotonic,
        max_seconds=180,
        max_steps=512,
        max_input_ms=18000,
    ):
        self.canceled, self.clock = canceled, clock
        self.started = clock()
        self.max_seconds, self.max_steps, self.max_input_ms = (
            max_seconds,
            max_steps,
            max_input_ms,
        )
        self.steps = self.input_ms = 0

    def check(self):
        """Check authority and elapsed time without consuming additional work."""
        if self.canceled() or not 0 <= self.clock() - self.started < self.max_seconds:
            raise FeedbackError(
                "Composite task canceled or total work budget exhausted"
            )

    def consume(self, input_ms=0):
        self.check()
        if (
            type(input_ms) is not int
            or input_ms < 0
            or self.steps + 1 > self.max_steps
            or self.input_ms + input_ms > self.max_input_ms
        ):
            raise FeedbackError(
                "Composite task canceled or total work budget exhausted"
            )
        self.steps += 1
        self.input_ms += (
            input_ms  # consumed before capture/emission, including failed work
        )


class WallCoordinator:
    """Ports are existing skill/runtime owners, never a hidden world controller.

    inspect(cell,budget) must actively acquire a fresh reachable ray and return
    CellEvidence; place and approach account every child step through budget.
    The callable ports permit focused checks without posting native input.
    """

    def __init__(self, *, inspect, place, approach, observe_position, neutralize):
        self.inspect, self.place, self.approach = inspect, place, approach
        self.observe_position, self.neutralize = observe_position, neutralize

    def run(self, scope, budget):
        cells = wall_cells(scope.anchor, scope.axis)
        result = {
            "status": "partial",
            "existing": [],
            "placed": [],
            "unknown": list(cells),
            "doorway_empty": [],
            "protected_verified": [],
            "reason": "",
            "stop_point_observed": False,
            "final_verified": [],
        }
        baseline = {}
        identity = None
        final_inspection_started = False

        def inspect_cell(cell):
            nonlocal identity
            evidence = self.inspect(cell, budget)
            if evidence is None:
                return None
            if tuple(evidence.cell) != tuple(cell):
                raise FeedbackError("Inspection refers to a different cell")
            current = (evidence.window_identity, evidence.settings)
            if identity is None:
                identity = current
            elif current != identity:
                raise FeedbackError(
                    "Inspection window/settings changed during wall work"
                )
            return evidence

        try:
            for cell in scope.protected:
                e = inspect_cell(cell)
                if e is None or e.material is None:
                    raise FeedbackError(
                        "Protected surface is unobserved; no additions started"
                    )
                baseline[cell] = e.material
            for cell in scope.doorway:
                e = inspect_cell(cell)
                if e is None or e.material is not None:
                    raise FeedbackError(
                        "Doorway is unknown or occupied; breaking is unavailable"
                    )
                result["doorway_empty"].append(cell)
            for cell in cells:
                self.approach(cell, budget)
                before = inspect_cell(cell)
                if before is None:
                    raise FeedbackError(
                        "Cell is occluded or unreachable; remaining wall is unverified"
                    )
                if before.material == scope.material:
                    result["existing"].append(cell)
                elif before.material is None:
                    # Exactly one attempt, even if its receipt/outcome is lost.
                    self.place(cell, scope.material, budget)
                    after = inspect_cell(cell)
                    if (
                        after is None
                        or after.captured_at <= before.captured_at
                        or after.material != scope.material
                    ):
                        raise FeedbackError("Addition outcome unknown; no blind retry")
                    result["placed"].append(cell)
                else:
                    raise FeedbackError(
                        "A different block occupies a work cell; breaking is unavailable"
                    )
                result["unknown"].remove(cell)
            # Fresh independent final inspection includes all occupied/empty and protected cells.
            final_inspection_started = True
            result["doorway_empty"] = []
            for cell in cells + scope.doorway + scope.protected:
                e = inspect_cell(cell)
                expected = scope.material if cell in cells else baseline.get(cell)
                if e is None or e.material != expected:
                    if cell in cells and cell not in result["unknown"]:
                        result["unknown"].append(cell)
                    raise FeedbackError(
                        "Final wall/doorway/protected inspection is incomplete or contradictory"
                    )
                result["final_verified"].append(cell)
                if cell in scope.doorway:
                    result["doorway_empty"].append(cell)
                if cell in baseline:
                    result["protected_verified"].append(cell)
            self.approach(scope.stop_point, budget)
            budget.consume()
            position = self.observe_position()
            budget.check()
            if math.dist(position, scope.stop_point) > 0.12:
                raise FeedbackError("Nearby stop point was not independently observed")
            result["stop_point_observed"] = True
            result["status"] = "completed"
        except Exception as exc:
            result["reason"] = str(exc)
            if final_inspection_started:
                result["unknown"] = [
                    cell for cell in cells if cell not in result["final_verified"]
                ]
        finally:
            result["steps"], result["input_ms"] = budget.steps, budget.input_ms
            try:
                result["release"] = self.neutralize()
            except Exception as exc:
                result["release"] = {"confirmed": False, "reason": str(exc)}
            if not result["release"].get("confirmed"):
                result.update(
                    status="partial",
                    reason="Input release unconfirmed; new work blocked",
                )
        return result
