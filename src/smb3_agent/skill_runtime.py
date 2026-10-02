"""Shared finite composition: fresh observations and independent outcomes per step."""

from dataclasses import dataclass
import time

from smb3_agent.feedback_contracts import FeedbackError


@dataclass(frozen=True)
class SkillSignature:
    name: str
    version: str
    max_steps: int
    max_seconds: float
    max_input_ms: int


SIGNATURES = {
    "camera": SkillSignature("camera", "camera-feedback/v1", 12, 12, 1440),
    "move": SkillSignature("move", "nearby-translation/v1", 4, 8, 600),
    "aim": SkillSignature("aim", "reachable-face/v1", 12, 12, 1440),
    "place": SkillSignature("place", "one-addition/v1", 1, 8, 80),
    "wall": SkillSignature("wall", "creative-wall/v2", 1536, 240, 60000),
}


class FiniteSkillRuntime:
    """Provider owns semantics; this owner accounts input before emitting it.

    The emitter must retain exact-window guards, cancellation and its independent
    native watchdog. Model replies cannot create a signature or an observation.
    """

    def __init__(self, *, observe, emit, neutralize, canceled, clock=time.monotonic):
        self.observe, self.emit, self.neutralize = observe, emit, neutralize
        self.canceled, self.clock = canceled, clock

    def run(self, signature, provider, parameters, *, budget=None):
        if signature not in SIGNATURES:
            raise FeedbackError("Unimplemented shared skill")
        contract = SIGNATURES[signature]
        started, input_ms, steps = self.clock(), 0, []
        result = {"status": "partial", "completed": [], "unknown": [], "steps": steps}
        try:
            provider.validate(signature, parameters)
            for _ in range(contract.max_steps):
                self._guard(started, contract)
                if budget is not None:
                    budget.consume()
                before = self.observe()
                self._guard(started, contract)
                if budget is not None:
                    budget.check()
                provider.require_fresh(before, self.clock())
                decision = provider.next(signature, parameters, before, result)
                if decision is None:
                    result["status"] = (
                        "completed"
                        if provider.complete(signature, parameters, result)
                        else "partial"
                    )
                    break
                duration = decision.duration_ms
                if (
                    type(duration) is not int
                    or not 0 < duration <= 250
                    or input_ms + duration > contract.max_input_ms
                ):
                    raise FeedbackError("Finite input budget exhausted")
                if budget is not None:
                    budget.consume(duration)
                input_ms += duration  # consumed even if posting fails
                self._guard(started, contract)
                steps.append({"command": decision, "before": before, "verified": False})
                steps[-1]["delivery"] = self.emit(decision)
                delivered = self.clock()
                self._guard(started, contract)
                if budget is not None:
                    budget.consume()
                after = self.observe()
                self._guard(started, contract)
                if budget is not None:
                    budget.check()
                provider.require_fresh(after, self.clock())
                if (
                    self._captured_at(after) <= self._captured_at(before)
                    or self._captured_at(after) < delivered
                ):
                    raise FeedbackError("Independent post-input observation required")
                steps[-1]["after"] = after
                provider.reconcile(signature, parameters, before, after, result)
                steps[-1]["verified"] = True
                if provider.complete(signature, parameters, result):
                    result["status"] = "completed"
                    break
            else:
                result["reason"] = "Step budget exhausted; remaining work is unverified"
        except Exception as exc:
            result["reason"] = str(exc)
        finally:
            result["input_ms"] = input_ms
            try:
                release = self.neutralize()
            except Exception as exc:
                release = {"confirmed": False, "reason": str(exc)}
            result["release"] = release
            if not release.get("confirmed"):
                result["status"], result["reason"] = (
                    "partial",
                    "Input release unconfirmed; new work blocked",
                )
        return result

    @staticmethod
    def _captured_at(observation):
        return (
            observation.frame.captured_at
            if hasattr(observation, "frame")
            else observation.captured_at
        )

    def _guard(self, started, contract):
        if self.canceled() or not 0 <= self.clock() - started < contract.max_seconds:
            raise FeedbackError("Task canceled or time budget exhausted")
