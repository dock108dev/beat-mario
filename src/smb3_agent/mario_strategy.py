"""Model choices at frozen native skill boundaries; no model owns joypad frames."""

from copy import deepcopy
import threading
import time

from smb3_agent.companion_ai import STRING, closed_schema
from smb3_agent.codex_provider import validate_object

CONTRACT = "smb3/world-1-1/opening-strategy/v1"
SCHEMA = closed_schema(
    {
        "skill": {"type": "string", "enum": ["hop", "walk_right", "inspect", "stop"]},
        "frames": {"type": "integer", "minimum": 1, "maximum": 26},
        "delay_frames": {"type": "integer", "minimum": 0, "maximum": 12},
        "reason": STRING,
        "expected_effect": STRING,
    }
)
GUIDANCE = {
    "objective": "Reach the observed World 1-1 opening stop x >= 160, then hand back.",
    "skills": {
        "hop": "Walk right without B; delay 0..12 frames, hold A 1..26 frames.",
        "walk_right": "Walk without A/B for 1..24 frames; useful for positioning or landing.",
        "inspect": "Re-read native state while paused; no game frame or input.",
        "stop": "Release control; this does not imply arrival.",
    },
    "mechanics": "Longer A hold changes jump height. Inference freezes emulation. Frame motion stays local.",
    "limits": "At most 6 model decisions, 180 skill frames and 120 seconds per attempt. Stop on death, level change, uncertain state or budget expiry. No reset/retry inside a decision. Existing separately approved retry budget applies.",
    "rules": "The app approved this scope through Review and Start. authority.review_and_start_observed records current approval; model_owns_input=false means the local controller emits input, not that approval is missing. Historical intent messages do not revoke this volatile approval. Choose parameters using current grounded/air state, nearby enemy distance and player preferences. Do not jump repeatedly while airborne. Use observed effects to adjust the next skill. Never infer completion from expected_effect. Full levels, flight, rewards and coin optimization are outside this skill scope.",
}


def validate_choice(choice, *, expanded=False):
    from smb3_agent.mario_segment import SCHEMA as SEGMENT_SCHEMA
    validate_object(choice, SEGMENT_SCHEMA if expanded else SCHEMA)
    if choice['skill'] in {'hop', 'run_hop', 'retreat_hop'} and choice['frames'] > 26:
        raise ValueError('Hop hold is bounded to 26 frames')
    if choice['skill']=='retreat_hop' and choice['delay_frames']:
        raise ValueError('Retreat jump lifts off immediately')
    if choice['skill'] in {'land_right', 'land_run_right', 'retreat', 'run_right', 'build_run', 'wait'} and choice['delay_frames']:
        raise ValueError('Landing and retreat have no jump delay')
    if choice["skill"] == "walk_right" and (
        choice["frames"] > (48 if expanded else 24) or choice["delay_frames"]
    ):
        raise ValueError("Walking permits 1..24 frames with no jump delay")
    if choice["skill"] in {"inspect", "stop"} and (
        choice["frames"] != 1 or choice["delay_frames"]
    ):
        raise ValueError("Passive choices require frames=1 and delay_frames=0")
    return choice


class MarioStrategyAgent:
    def __init__(self, service, provider):
        self.service, self.provider = service, provider
        self.cancel = threading.Event()
        self.worker = None

    def stop(self):
        self.cancel.set()

    def start(self, plan):
        self.stop()
        cancel = self.cancel = threading.Event()
        runtime = self.service.runtime
        initial = runtime.snapshot()
        identity = (initial["session_id"], initial["revision"], initial["emulator_pid"])
        generation = self.service._control_generation
        goal = deepcopy(plan.get("model_intent") or {})
        # Stored guidance is descriptive and never restores volatile authority.
        goal["coaching"] = deepcopy(plan.get("coaching", []))
        from smb3_agent import mario_segment
        expanded = plan.get('strategy_contract') == mario_segment.CONTRACT
        schema = mario_segment.SCHEMA if expanded else SCHEMA
        guidance = mario_segment.GUIDANCE if expanded else GUIDANCE
        maximum = mario_segment.MAX_DECISIONS if expanded else 6
        if expanded:
            cartridge = getattr(self.service.live_manager, '_game_file_sha256', None)
            goal['coaching'], goal['incompatible_guidance_ids'] = mario_segment.compatible_guidance(goal['coaching'], cartridge)
        deadline = time.monotonic() + (mario_segment.MAX_SECONDS if expanded else 120)

        def active():
            if cancel.is_set() or generation != self.service._control_generation:
                return None
            state = runtime.snapshot()
            if (
                state.get("owner") != "agent"
                or state.get("state") not in {"playing", "paused"}
                or (
                    state.get("session_id"),
                    state.get("revision"),
                    state.get("emulator_pid"),
                )
                != identity
            ):
                return None
            return state

        def work():
            seen = None
            records = []
            try:
                while time.monotonic() < deadline:
                    state = active()
                    if state is None:
                        return
                    boundary = state.get("strategy_boundary")
                    if (
                        not boundary
                        or boundary["boundary_id"] == seen
                        or state["state"] != "paused"
                    ):
                        cancel.wait(0.05)
                        continue
                    seen = boundary["boundary_id"]
                    if records:
                        records[-1]["effect"] = deepcopy(boundary)
                    if len(records) >= maximum:
                        raise ValueError("Mario gameplay decision budget exhausted")
                    supplied = {
                        "guidance": guidance,
                        "progress": {"target_x": 700 if expanded else 160,
                                     "current_x": int(boundary['x']),
                                     "grounded": int(boundary.get('air', 1)) == 0},
                        "goal": goal,
                        "observation": deepcopy(boundary),
                        "previous_attempt_outcome": (
                            {
                                "status": self.service._outcome.get("status"),
                                "handback_confirmed": self.service._outcome.get(
                                    "controller_owner"
                                )
                                == "player"
                                and self.service._outcome.get("neutralized") is True,
                                "skills": deepcopy(
                                    (
                                        self.service._outcome.get("strategy_result")
                                        or {}
                                    ).get("skills", [])[-6:]
                                ),
                                "opening_stop_observed": (
                                    self.service._outcome.get("strategy_result") or {}
                                ).get("opening_stop_observed"),
                            }
                            if self.service._outcome
                            else None
                        ),
                        "prior_effects": [
                            {
                                "decision": deepcopy(row["decision"]),
                                "effect": deepcopy(row["effect"]),
                            }
                            for row in records[-4:]
                        ],
                        "authority": {
                            "session_id": identity[0],
                            "revision": identity[1],
                            "review_and_start_observed": True,
                            "model_owns_input": False,
                        },
                    }
                    if expanded:
                        if int(boundary.get("dying", 0)) != 0:
                            raise ValueError("Unsafe player animation observed; control released")
                        supplied["observed_state"] = mario_segment.observed_state(boundary)
                        images = (mario_segment.boundary_image(self.service, boundary),)
                        result = self.provider.infer('gameplay', supplied, schema, cancel, images=images)
                    else:
                        result = self.provider.infer('gameplay', supplied, schema, cancel)
                    if time.monotonic() >= deadline:
                        raise ValueError("Mario strategy wall-clock budget expired")
                    validate_choice(result, expanded=expanded)
                    if expanded:
                        ids = {r['id'] for r in goal['coaching']}
                        if result['guidance_id'] and result['guidance_id'] not in ids:
                            raise ValueError('Gameplay selected incompatible or unknown remembered guidance')
                        if result['skill'] in {'hop', 'run_hop', 'retreat_hop'} and int(boundary.get('air', 1)) != 0:
                            raise ValueError('Land and observe before another jump')
                        recent = [r['supplied']['observation'] for r in records[-3:]] + [boundary]
                        if len(recent) == 4 and all(int(r.get('air', 1)) == 0 for r in recent) and max(int(r['x']) for r in recent)-min(int(r['x']) for r in recent) <= 3:
                            raise ValueError('Repeated grounded lack of progress; control released')
                    if active() is None:
                        return
                    # The controller re-reads memory on accepting the exact boundary.
                    # Changed frame/session/epoch, canceled ownership and bad scope reject.
                    runtime.strategy_skill(result, boundary)
                    row = {
                        "role": "mario_gameplay",
                        "supplied": supplied,
                        "decision": result,
                        "effect": None,
                        "evidence_class": "native_skill_boundary",
                    }
                    records.append(row)
                    with self.service._lock:
                        if (
                            cancel.is_set()
                            or generation != self.service._control_generation
                        ):
                            return
                        if self.service.ai:
                            self.service.ai.records.append(row)
                            self.service.ai._persist()
                        self.service._message(
                            "assistant",
                            result["reason"]
                            + " Expected: "
                            + result["expected_effect"],
                            "gameplay_decision",
                        )
                    if result["skill"] == "stop":
                        return
                raise ValueError("Mario strategy wall-clock budget expired")
            except Exception as exc:
                if active() is not None:
                    detail = str(exc)
                    reason = ("decision_budget_exhausted" if "decision budget" in detail else
                              "wall_budget_exhausted" if "wall-clock budget" in detail else
                              "no_progress" if "lack of progress" in detail else
                              "unsafe_player_state" if "Unsafe player animation" in detail else
                              "decision_refused" if isinstance(exc, ValueError) else "inference_failed")
                    from smb3_agent.codex_provider import InferenceError
                    if isinstance(exc, InferenceError):
                        reason = "inference_failed"
                    runtime.abort_strategy(reason, detail)
                    with self.service._lock:
                        self.service._message(
                            "assistant",
                            str(exc)
                            if isinstance(exc, ValueError)
                            else "Gameplay inference failed; control released.",
                            "error",
                        )

        self.worker = threading.Thread(target=work, daemon=True, name="mario-gameplay")
        self.worker.start()
