"""Revision-bound Mario plans. Planner output is data, never controller code.

Only the adapter-owned opening traversal and explicit stop primitives are accepted.
The accepted route remains a separate authority and is never promoted from a plan.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading
import time
from typing import Any

PATHS = {"default", "opening_hop"}
STOPS = {"full_route", "world_1_1_exit", "world_1_1_opening_end"}
SPEEDS = (1, "turbo")
BOUNDARIES = {"world_1_1_opening", "world_1_1_exit"}
PRIMITIVES = {
    "world_1_1_default_v1": "default",
    "world_1_1_opening_hop_v1": "opening_hop",
}


def write_fields(path: Path, fields: dict[str, Any]) -> None:
    """Atomic, non-executable wire data; reject line/key injection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for key, value in fields.items():
        if not re.fullmatch(r"[a-z_]+", key) or not re.fullmatch(
            r"[A-Za-z0-9_.:-]+", str(value)
        ):
            raise ValueError("Invalid runtime protocol value")
    fd, temporary = tempfile.mkstemp(prefix=".command-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(
                "".join(f"{key}={value}\n" for key, value in sorted(fields.items()))
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_runtime_fields(fields: dict[str, Any]) -> None:
    if fields.get("path_choice") not in PATHS:
        raise ValueError("Unsupported Mario traversal primitive")
    if fields.get("stop_point") not in STOPS:
        raise ValueError("Unsupported Mario stop point")
    if (
        fields.get("path_choice") == "opening_hop"
        and fields.get("stop_point") != "world_1_1_opening_end"
    ):
        raise ValueError(
            "The opening hop is validated only to the opening stop; later traversal is unsupported"
        )
    if fields.get("speed") not in SPEEDS:
        raise ValueError(
            "Supported playback is 1× or turbo (uncapped faster); 2×/4× are unavailable"
        )
    if type(fields.get("revision")) is not int or fields["revision"] < 1:
        raise ValueError("A positive plan revision is required")
    if not fields.get("session_id"):
        raise ValueError("A live session identity is required")


def _plan_data(plan: Any) -> dict[str, Any]:
    if isinstance(plan, dict):
        return dict(plan)
    if hasattr(plan, "to_dict"):
        return plan.to_dict()
    if is_dataclass(plan):
        return asdict(plan)
    raise ValueError("A typed Mario plan is required")


def runtime_fields(plan: Any) -> dict[str, Any]:
    data = _plan_data(plan)
    if data.get("game_id", data.get("game")) not in {"mario", "smb3"}:
        raise ValueError("Mario execution rejects a plan for another game")
    if (
        data.get("base_route_id") != "world_8_finish_game"
        or str(data.get("base_version")) != "1"
    ):
        raise ValueError("The plan's base route or version is incompatible")
    if len(data.get("actions", [])) != 1:
        raise ValueError(
            "A Mario plan must contain one implemented traversal primitive"
        )
    path = data.get("path_choice", "default")
    for action in data.get("actions", []):
        if is_dataclass(action):
            action = asdict(action)
        parameters = action.get("parameters", {})
        primitive = parameters.get(
            "primitive_id",
            action.get(
                "primitive_id",
                action.get("kind") if action.get("kind") in PRIMITIVES else None,
            ),
        )
        if primitive not in PRIMITIVES:
            raise ValueError("Unvalidated primitives cannot execute")
        path = PRIMITIVES[primitive]
        if (
            parameters.get("path_choice", path) != path
            or data.get("path_choice", path) != path
        ):
            raise ValueError("Traversal and primitive disagree")
        if parameters.get("stop_point") != data.get("stop_point"):
            raise ValueError("Action and plan stop points disagree")
        if parameters.get("base_route_id") != data["base_route_id"]:
            raise ValueError("Action and plan base routes disagree")
        if parameters.get("base_solution_id") != "world_8_finish_game_v1":
            raise ValueError("Action has an incompatible base solution")
        path = parameters.get("path_choice", path)
        if action.get("kind") not in set(PRIMITIVES) | {"mario_traverse"}:
            raise ValueError(f"Unsupported Mario action: {action.get('kind')}")
    speed = data.get("requested_speed", data.get("speed", 1))
    if isinstance(speed, dict):
        speed = speed.get("requested", 1)
    if speed == 1:
        speed = 1
    fields = {
        "session_id": data.get("session_id"),
        "revision": data.get("revision", 1),
        "path_choice": path,
        "stop_point": data.get("stop_point", "full_route"),
        "speed": speed or 1,
    }
    if data.get("ambiguities") or data.get("unsupported_parts"):
        raise ValueError(
            "Resolve plan ambiguities and unsupported parts before starting"
        )
    validate_runtime_fields(fields)
    return fields


class MarioPlanRuntime:
    """One volatile process/session authority with an append-only command ledger."""

    def __init__(self, live_manager: Any) -> None:
        self.live = live_manager
        self._lock = threading.RLock()
        self._state: dict[str, Any] = {
            "state": "idle",
            "owner": "player",
            "revision": None,
            "pending": None,
            "requested_speed": 1,
            "applied_speed": None,
            "speed_intervals": [],
            "events": [],
            "outcome": None,
            "start_frame": None,
            "terminal_frame": None,
            "terminal_wall": None,
            "handback_frame": None,
            "native_neutral_ack": False,
            "supported_speeds": [1, "turbo"],
            "speed_limitation": "Turbo is uncapped; actual rate depends on this machine.",
            "authority_restored_from_storage": False,
        }
        self._directory: Path | None = None
        self._sequence = 0
        self._event_lines = 0
        self._ids: set[str] = set()
        self._pending_plans: dict[str, dict[str, Any]] = {}
        self._epoch: int | None = None
        self._requested_stop = False

    def _record(self, event: str, **fields: Any) -> None:
        row = {"event": event, "at": datetime.now(timezone.utc).isoformat(), **fields}
        self._state["events"].append(row)
        if self._directory:
            with (self._directory / "runtime_history.jsonl").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    def _sync(self) -> None:
        if self._directory is None:
            return
        path = self._directory / "events.log"
        if path.is_file():
            lines = path.read_text().splitlines(keepends=True)
            for line in lines[self._event_lines :]:
                if not line.endswith("\n"):
                    break
                self._event_lines += 1
                row = dict(part.split("=", 1) for part in line.split() if "=" in part)
                if row.get("epoch") != str(self._epoch):
                    continue
                event = row.get("event")
                self._record(
                    str(event),
                    **{key: value for key, value in row.items() if key != "event"},
                )
                if event == "applied":
                    self._state["applied_command_id"] = row.get("command_id")
                    self._state["revision"] = int(row["revision"])
                    self._state["path_choice"] = row["path_choice"]
                    self._state["stop_point"] = row["stop_point"]
                    self._state["effective_boundary"] = row.get("boundary")
                    self._state["plan"] = self._pending_plans.get(
                        row.get("command_id"), self._state.get("plan")
                    )
                    self._state["pending"] = None
                elif event == "queued":
                    pass
                elif event == "cancelled":
                    self._state["pending"] = None
                elif event in {"paused", "resumed"} and not self._requested_stop:
                    self._state["state"] = "paused" if event == "paused" else "playing"
                elif event == "speed_ack":
                    wall = float(row["wall"])
                    frame = int(row["frame"])
                    intervals = self._state["speed_intervals"]
                    if intervals:
                        prior = intervals[-1]
                        prior.update(end_frame=frame, end_wall=wall)
                        seconds = wall - prior["start_wall"]
                        prior["measured_multiplier"] = (
                            round(
                                (frame - prior["start_frame"]) / (60.0988 * seconds), 3
                            )
                            if seconds > 0
                            else None
                        )
                    intervals.append(
                        {
                            "requested": self._state["requested_speed"],
                            "acknowledged": row["speed"],
                            "start_frame": frame,
                            "start_wall": wall,
                        }
                    )
                    self._state["applied_speed"] = (
                        1 if row["speed"] == "1" else row["speed"]
                    )
                elif event == "rejected":
                    if (self._state.get("pending") or {}).get("command_id") == row.get(
                        "command_id"
                    ):
                        self._state["pending"] = None
                    self._state["last_rejection"] = row.get("reason")
                elif event == "neutral_ack":
                    self._state["native_neutral_ack"] = True
                    self._state["handback_frame"] = int(row["frame"])
                elif event == "neutralization_failed":
                    self._state.update(
                        native_neutral_ack=False,
                        input_neutralized=False,
                        outcome="neutralization_failed",
                    )
                elif event == "terminal":
                    self._state["terminal_frame"] = int(row["frame"])
                    self._state["terminal_wall"] = float(row["wall"])
                    if self._state["speed_intervals"]:
                        interval = self._state["speed_intervals"][-1]
                        wall, frame = float(row["wall"]), int(row["frame"])
                        seconds = wall - interval["start_wall"]
                        interval.update(
                            end_frame=frame,
                            end_wall=wall,
                            measured_multiplier=round(
                                (frame - interval["start_frame"]) / (60.0988 * seconds),
                                3,
                            )
                            if seconds > 0
                            else None,
                        )
                    self._state.update(
                        state="stopping",
                        pending=None,
                        outcome=self._state.get("outcome") or row.get("reason"),
                        speed_restored=row.get("speed_restored") == "1",
                        applied_speed=1 if row.get("speed_restored") == "1" else None,
                    )
                    if row.get("speed_restored") != "1":
                        self._state["speed_limitation"] = (
                            "Normal playback restoration failed; use FCEUX speed control before player handback."
                        )
        live = self.live.snapshot()
        if (
            self._state.get("session_id")
            and live.session_id != self._state["session_id"]
        ):
            self._state.update(
                state="finished",
                owner="player",
                pending=None,
                outcome="session_replaced",
            )
        elif self._state["state"] in {"playing", "paused", "starting", "stopping"}:
            if getattr(live, "emulator_pid", None) != self._state.get("emulator_pid"):
                self._state.update(
                    state="finished",
                    owner="player",
                    pending=None,
                    outcome="process_loss",
                    speed_restored=False,
                )
            elif live.control_owner == "player" and live.takeover_terminal_reason:
                outcome = self._state.get("outcome")
                if outcome in {None, "reclaimed"}:
                    outcome = live.takeover_terminal_reason
                self._state.update(
                    state="finished",
                    owner="player",
                    pending=None,
                    outcome=outcome,
                    input_neutralized=live.input_neutralized
                    and self._state["native_neutral_ack"],
                )
        pending = self._state.get("pending")
        if (
            pending
            and time.time() > pending["deadline"]
            and self._state["state"] in {"playing", "paused"}
        ):
            self.control("stop")
            self._state["outcome"] = "boundary_wait_expired"
        self._state["observation"] = {
            "session_id": live.session_id,
            "freshness": getattr(live.freshness, "value", live.freshness),
            "frame": live.samples[-1].frame if live.samples else None,
            "x": live.samples[-1].x if live.samples else None,
            "y": live.samples[-1].y if live.samples else None,
            "pid": getattr(live, "emulator_pid", None),
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._sync()
            return json.loads(json.dumps(self._state))

    def start(self, plan: Any) -> dict[str, Any]:
        with self._lock:
            self._sync()
            if self._state["state"] in {"starting", "playing", "paused", "stopping"}:
                raise ValueError("A plan already owns this session")
            fields = runtime_fields(plan)
            live = self.live.snapshot()
            if live.session_id != fields["session_id"]:
                raise ValueError("The plan belongs to another session")
            start_frame = live.samples[-1].frame if live.samples else None
            authorization = self.live.begin_session_plan(fields)
            self._directory = live.artifact_dir / "b2"
            self._directory.mkdir(exist_ok=True)
            self._epoch = authorization.control_epoch
            self._sequence = 0
            self._event_lines = 0
            self._ids.clear()
            self._pending_plans.clear()
            self._requested_stop = False
            self._state.update(
                state="playing",
                owner="agent",
                **fields,
                emulator_pid=live.emulator_pid,
                plan=_plan_data(plan),
                pending=None,
                requested_speed=fields["speed"],
                applied_speed=None,
                speed_intervals=[],
                outcome=None,
                start_frame=start_frame,
                terminal_frame=None,
                terminal_wall=None,
                handback_frame=None,
                native_neutral_ack=False,
                events=[],
                input_neutralized=False,
                speed_restored=False,
                authority_kind="bounded_session_plan",
                authorized_stop_point=fields["stop_point"],
                applied_command_id=None,
                last_rejection=None,
            )
            self._record(
                "start_authorized", revision=fields["revision"], epoch=self._epoch
            )
            return self.snapshot()

    def _send(self, action: str, command_id: str | None = None, **fields: Any) -> str:
        if self._requested_stop or self._state["state"] not in {"playing", "paused"}:
            raise ValueError(
                "Control was reclaimed or execution is inactive; fresh Start authority is required"
            )
        command_id = command_id or secrets.token_hex(12)
        if command_id in self._ids:
            raise ValueError("Duplicate command was already submitted")
        sequence = self._sequence + 1
        wire = {
            "action": action,
            "command_id": command_id,
            "sequence": sequence,
            "session_id": self._state["session_id"],
            "epoch": self._epoch,
            "expected_revision": self._state["revision"],
            **fields,
        }
        assert self._directory is not None
        write_fields(self._directory / f"{self._epoch}-{sequence:06d}.request", wire)
        self._sequence = sequence
        self._ids.add(command_id)
        self._record("command_submitted", **wire)
        return command_id

    def queue_edit(
        self,
        plan: Any,
        *,
        expected_revision: int | None = None,
        command_id: str | None = None,
        replace_pending: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            self._sync()
            fields = runtime_fields(plan)
            current = self._state["revision"]
            expected = current if expected_revision is None else expected_revision
            data = _plan_data(plan)
            if (
                expected != current
                or data.get("parent_revision", expected) != current
                or fields["revision"] <= current
            ):
                raise ValueError("Stale or out-of-order plan revision")
            if fields["session_id"] != self._state.get("session_id"):
                raise ValueError("Edit belongs to another game session")
            stop_order = {
                "world_1_1_opening_end": 0,
                "world_1_1_exit": 1,
                "full_route": 2,
            }
            if (
                stop_order[fields["stop_point"]]
                > stop_order[self._state["authorized_stop_point"]]
            ):
                raise ValueError(
                    "This destination exceeds the started session's scope; review it with fresh Start authority"
                )
            if self._state["pending"] and not replace_pending:
                raise ValueError(
                    "Cancel or explicitly replace the pending change first"
                )
            live = self.live.snapshot()
            if (
                getattr(live.freshness, "value", live.freshness) != "fresh"
                or not live.samples
            ):
                raise ValueError("Applying an edit needs a fresh game observation")
            sample = live.samples[-1]
            path_changed = fields["path_choice"] != self._state.get("path_choice")
            boundary = (
                "world_1_1_opening"
                if path_changed or fields["stop_point"] == "world_1_1_opening_end"
                else "world_1_1_exit"
            )
            # The authenticated paused power-on sample predates game RAM
            # initialization. Its opening is upcoming, not already missed.
            fresh_boot = getattr(live, "checkpoint_id", None) == "fresh_power_on"
            if (sample.world != 0 and not fresh_boot) or (
                path_changed and sample.object_set == 1 and sample.x > 64
            ):
                self._state["outcome"] = "boundary_missed"
                self.control("stop")
                raise ValueError(
                    "The editable opening boundary has been missed; completed actions cannot be undone"
                )
            if sample.object_set == 0 and sample.frame > 1200:
                self._state["outcome"] = "boundary_missed"
                self.control("stop")
                raise ValueError(
                    "World 1-1 has already ended; this stop boundary is unavailable"
                )
            if path_changed and fields["stop_point"] == "full_route":
                raise ValueError(
                    "The alternate path is bounded to World 1-1; choose its course-clear stop"
                )
            deadline = int(time.time()) + 90
            ident = self._send(
                "edit",
                command_id,
                **{key: value for key, value in fields.items() if key != "speed"},
                boundary=boundary,
                replace_pending=int(replace_pending),
                deadline=deadline,
            )
            data["effective_boundary"] = boundary
            self._pending_plans[ident] = data
            self._state["pending"] = {
                "command_id": ident,
                "revision": fields["revision"],
                "effective_boundary": boundary,
                "path_choice": fields["path_choice"],
                "stop_point": fields["stop_point"],
                "deadline": deadline,
            }
            return self.snapshot()

    def cancel_pending(self, command_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            self._sync()
            if not self._state["pending"]:
                raise ValueError("There is no pending change to cancel")
            self._send(
                "cancel", command_id, target_id=self._state["pending"]["command_id"]
            )
            return self.snapshot()

    def control(
        self, action: str, *, speed: Any = None, command_id: str | None = None
    ) -> dict[str, Any]:
        with self._lock:
            if action in {"reclaim", "stop"}:
                if self._requested_stop:
                    return self.snapshot()
                live = self.live.snapshot()
                if live.control_owner != "agent":
                    if live.session_id:
                        # Opening for plan review pauses native emulation before
                        # agent ownership. Reclaim must release that pause too.
                        self.live.stop()
                        self._state.update(
                            state="finished", owner="player", outcome="detached"
                        )
                        return self.snapshot()
                    raise ValueError("The player already owns Mario control")
                self.live.reclaim_takeover()
                self._requested_stop = True
                self._state.update(state="stopping", pending=None)
                self._record("reclaim_requested", cause=action)
                return self.snapshot()
            self._sync()
            if action == "speed":
                if speed not in SPEEDS:
                    raise ValueError(
                        "Supported playback is 1× or turbo (uncapped faster); requested rate unavailable"
                    )
                self._send(action, command_id, speed=speed)
                self._state["requested_speed"] = speed
            elif action in {"pause", "resume"}:
                self._send(action, command_id)
            else:
                raise ValueError("Unsupported runtime control")
            return self.snapshot()
