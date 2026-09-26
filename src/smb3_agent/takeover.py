from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class TakeoverError(ValueError):
    pass


class ControlOwner(str, Enum):
    PLAYER = "player"
    AGENT = "agent"


class TakeoverState(str, Enum):
    PLAYER_CONTROL = "player_control"
    AUTHORIZED = "authorized"
    AGENT_CONTROL = "agent_control"
    NEUTRALIZING = "neutralizing"
    RETURNED = "returned"
    FAILED = "failed"


class TakeoverTerminal(str, Enum):
    SUCCESS = "success"
    RECLAIMED = "reclaimed"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PROCESS_LOSS = "process_loss"
    STALE_STATE = "stale_state"
    CONFLICT = "ownership_conflict"
    UNSUPPORTED = "unsupported_state"


@dataclass(frozen=True)
class ExecutableSolution:
    solution_id: str
    version: int
    game_id: str
    profile_id: str
    scopes: tuple[str, ...]
    state_preconditions: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    replay_safe: bool
    accepted: bool
    policy_id: str
    evidence: tuple[str, ...]

    def validate(self) -> None:
        if not all((self.solution_id, self.game_id, self.profile_id, self.policy_id)):
            raise TakeoverError("solution identity is required")
        if self.version < 1 or not self.scopes or not self.stop_conditions:
            raise TakeoverError(
                "solution version, scope, and stop conditions are required"
            )

    @property
    def executable(self) -> bool:
        return self.replay_safe and self.accepted and bool(self.evidence)


@dataclass(frozen=True)
class TakeoverAuthorization:
    authorization_id: str
    nonce: str
    control_epoch: int
    session_id: str
    emulator_pid: int
    game_file_sha256: str
    state_fingerprint: str
    game_id: str
    profile_id: str
    profile_version: int
    solution_id: str
    solution_version: int
    scope: str
    stop_condition: str
    timeout_seconds: int
    protected_resources: tuple[str, ...]
    protected_decisions: tuple[str, ...]
    issued_at: str
    expires_at: str
    authority_kind: str = "accepted_solution"


@dataclass(frozen=True)
class ControlSnapshot:
    owner: ControlOwner = ControlOwner.PLAYER
    state: TakeoverState = TakeoverState.PLAYER_CONTROL
    control_epoch: int = 0
    authorization: TakeoverAuthorization | None = None
    terminal_reason: TakeoverTerminal | None = None
    agent_inputs_before: int = 0
    agent_inputs_during: int = 0
    agent_inputs_after: int = 0
    neutralized: bool = True
    observation_resumed: bool = True
    handback_latency_ms: float | None = None
    final_state_fingerprint: str | None = None
    process_alive: bool | None = None


def state_fingerprint(session_id: str, emulator_pid: int, sample: Any) -> str:
    fields = (
        session_id,
        emulator_pid,
        getattr(sample, "sequence"),
        getattr(sample, "frame"),
        getattr(sample, "world"),
        getattr(sample, "object_set"),
        getattr(sample, "map_page"),
        getattr(sample, "x"),
        getattr(sample, "y"),
        getattr(sample, "lives"),
        tuple(getattr(sample, "items")),
    )
    return hashlib.sha256(repr(fields).encode()).hexdigest()


class TakeoverController:
    """Fail-closed authorization and same-process control ownership state machine."""

    def __init__(
        self,
        artifact_dir: Path,
        command_path: Path,
        reclaim_path: Path | None = None,
    ) -> None:
        self.artifact_dir = artifact_dir
        self.command_path = command_path
        self.reclaim_path = reclaim_path or command_path.with_name("reclaim.request")
        self.snapshot = ControlSnapshot()
        self._used_nonces: set[str] = set()
        self._pending_reason: TakeoverTerminal | None = None
        self._handback_requested_at: datetime | None = None

    def authorize(
        self,
        *,
        session_id: str,
        emulator_pid: int,
        game_file_sha256: str,
        current_fingerprint: str,
        game_id: str,
        profile_id: str,
        profile_version: int,
        solution: ExecutableSolution,
        scope: str,
        stop_condition: str,
        timeout_seconds: int,
        protected_resources: tuple[str, ...] = (),
        protected_decisions: tuple[str, ...] = (),
        now: datetime | None = None,
        _bounded_plan: bool = False,
    ) -> TakeoverAuthorization:
        solution.validate()
        if (
            self.snapshot.owner is not ControlOwner.PLAYER
            or self.snapshot.state
            not in {
                TakeoverState.PLAYER_CONTROL,
                TakeoverState.RETURNED,
            }
        ):
            raise TakeoverError("control ownership is not exclusively player")
        if _bounded_plan and solution.policy_id not in {
            "b2_world_1_1_plan_v1",
            "b2_full_route_plan_v1",
        }:
            raise TakeoverError("unsupported bounded session policy")
        if not _bounded_plan and not solution.executable:
            raise TakeoverError(
                "only replay-safe accepted solutions can drive takeover"
            )
        if solution.game_id != game_id or solution.profile_id != profile_id:
            raise TakeoverError("solution objective does not match authorization")
        if (
            scope not in solution.scopes
            or stop_condition not in solution.stop_conditions
        ):
            raise TakeoverError("unsupported solution scope or stop condition")
        if timeout_seconds < 1 or timeout_seconds > 3600:
            raise TakeoverError("takeover timeout must be between 1 and 3600 seconds")
        issued = now or datetime.now(timezone.utc)
        nonce = secrets.token_hex(16)
        authorization = TakeoverAuthorization(
            secrets.token_hex(16),
            nonce,
            self.snapshot.control_epoch + 1,
            session_id,
            emulator_pid,
            game_file_sha256,
            current_fingerprint,
            game_id,
            profile_id,
            profile_version,
            solution.solution_id,
            solution.version,
            scope,
            stop_condition,
            timeout_seconds,
            tuple(sorted(set(protected_resources))),
            tuple(sorted(set(protected_decisions))),
            issued.isoformat(),
            (issued + timedelta(seconds=timeout_seconds)).isoformat(),
            "bounded_session_plan" if _bounded_plan else "accepted_solution",
        )
        self.snapshot = replace(
            self.snapshot,
            state=TakeoverState.AUTHORIZED,
            control_epoch=authorization.control_epoch,
            authorization=authorization,
            terminal_reason=None,
            neutralized=True,
            observation_resumed=False,
            handback_latency_ms=None,
            final_state_fingerprint=None,
            process_alive=None,
        )
        self._write("authorization_manifest.json", asdict(authorization))
        self._event("authorized", {"control_epoch": authorization.control_epoch})
        return authorization

    def transfer(
        self,
        authorization: TakeoverAuthorization,
        *,
        session_id: str,
        emulator_pid: int,
        game_file_sha256: str,
        current_fingerprint: str,
        now: datetime | None = None,
    ) -> None:
        active = self.snapshot.authorization
        current = now or datetime.now(timezone.utc)
        if active is None or authorization != active:
            raise TakeoverError("authorization is stale or mismatched")
        if authorization.nonce in self._used_nonces:
            raise TakeoverError("authorization nonce has already been used")
        if current >= datetime.fromisoformat(authorization.expires_at):
            raise TakeoverError("authorization has expired")
        if (
            authorization.session_id != session_id
            or authorization.emulator_pid != emulator_pid
            or authorization.game_file_sha256 != game_file_sha256
            or authorization.state_fingerprint != current_fingerprint
            or authorization.control_epoch != self.snapshot.control_epoch
        ):
            raise TakeoverError(
                "authorization no longer matches the live process and state"
            )
        self._used_nonces.add(authorization.nonce)
        self.reclaim_path.unlink(missing_ok=True)
        self._write_command(
            {
                "action": "start",
                "epoch": authorization.control_epoch,
                "nonce": authorization.nonce,
                "policy": authorization.solution_id,
                "scope": authorization.scope,
                "stop_condition": authorization.stop_condition,
                "expires_at": authorization.expires_at,
            }
        )
        self.snapshot = replace(
            self.snapshot,
            owner=ControlOwner.AGENT,
            state=TakeoverState.AGENT_CONTROL,
            neutralized=False,
        )
        self._event(
            "ownership_transferred",
            {"owner": "agent", "control_epoch": authorization.control_epoch},
        )

    def record_agent_input(self, epoch: int, buttons: tuple[str, ...]) -> None:
        active = self.snapshot.authorization
        bounded_inflight = (
            active is not None
            and active.authority_kind == "bounded_session_plan"
            and self.snapshot.state is TakeoverState.NEUTRALIZING
        )
        if (
            self.snapshot.owner is not ControlOwner.AGENT
            or (
                self.snapshot.state is not TakeoverState.AGENT_CONTROL
                and not bounded_inflight
            )
            or active is None
            or epoch != active.control_epoch
        ):
            field = (
                "agent_inputs_after"
                if self.snapshot.state is TakeoverState.RETURNED
                else "agent_inputs_before"
            )
            self.snapshot = replace(
                self.snapshot, **{field: getattr(self.snapshot, field) + 1}
            )
            raise TakeoverError("agent input is outside active authorization")
        self.snapshot = replace(
            self.snapshot, agent_inputs_during=self.snapshot.agent_inputs_during + 1
        )
        self._event(
            "agent_input",
            {
                "control_epoch": epoch,
                "buttons": list(buttons),
                "actor": "agent",
                **({"observed_while_neutralizing": True} if bounded_inflight else {}),
            },
        )

    def reclaim(
        self,
        epoch: int,
        *,
        final_state_fingerprint: str,
        process_alive: bool,
        requested_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> ControlSnapshot:
        if (
            self.snapshot.owner is not ControlOwner.AGENT
            or epoch != self.snapshot.control_epoch
        ):
            raise TakeoverError("reclaim does not target the active control epoch")
        started = requested_at or datetime.now(timezone.utc)
        self.snapshot = replace(self.snapshot, state=TakeoverState.NEUTRALIZING)
        self._pending_reason = TakeoverTerminal.RECLAIMED
        self._handback_requested_at = started
        self._write_command({"action": "neutralize", "epoch": epoch})
        self.reclaim_path.touch(exist_ok=True)
        self._event("reclaim_requested", {"control_epoch": epoch})
        if completed_at is not None:
            return self.confirm_handback(
                final_state_fingerprint=final_state_fingerprint,
                process_alive=process_alive,
                completed_at=completed_at,
            )
        return self.snapshot

    def confirm_handback(
        self,
        *,
        final_state_fingerprint: str,
        process_alive: bool,
        completed_at: datetime | None = None,
    ) -> ControlSnapshot:
        if self.snapshot.state is not TakeoverState.NEUTRALIZING:
            raise TakeoverError("no neutralization handback is pending")
        ended = completed_at or datetime.now(timezone.utc)
        latency = (
            max(0.0, (ended - self._handback_requested_at).total_seconds() * 1000)
            if self._handback_requested_at
            else None
        )
        reason = self._pending_reason or TakeoverTerminal.CANCELLED
        self._pending_reason = None
        self._handback_requested_at = None
        return self._return_control(
            reason, final_state_fingerprint, process_alive, latency
        )

    def request_terminal(self, reason: TakeoverTerminal) -> ControlSnapshot:
        if self.snapshot.owner is not ControlOwner.AGENT:
            raise TakeoverError("Companion does not own the active control epoch")
        self.snapshot = replace(self.snapshot, state=TakeoverState.NEUTRALIZING)
        self._pending_reason = reason
        self._handback_requested_at = datetime.now(timezone.utc)
        self._write_command(
            {"action": "neutralize", "epoch": self.snapshot.control_epoch}
        )
        self.reclaim_path.touch(exist_ok=True)
        self._event(
            "terminal_stop_requested",
            {"reason": reason.value, "control_epoch": self.snapshot.control_epoch},
        )
        return self.snapshot

    def finish(
        self,
        reason: TakeoverTerminal,
        *,
        final_state_fingerprint: str,
        process_alive: bool,
    ) -> ControlSnapshot:
        if self.snapshot.owner is ControlOwner.AGENT:
            self._write_command(
                {"action": "neutralize", "epoch": self.snapshot.control_epoch}
            )
            self.reclaim_path.touch(exist_ok=True)
        return self._return_control(
            reason, final_state_fingerprint, process_alive, None
        )

    def _return_control(
        self,
        reason: TakeoverTerminal,
        final_state_fingerprint: str,
        process_alive: bool,
        latency_ms: float | None,
    ) -> ControlSnapshot:
        # Conversation control cannot infer neutral input from a lost process. Retain the legacy
        # accepted-solution reconciliation schema for historical consumers.
        neutralized = process_alive or not (
            self.snapshot.authorization is not None
            and self.snapshot.authorization.authority_kind == "bounded_session_plan"
        )
        self.snapshot = replace(
            self.snapshot,
            owner=ControlOwner.PLAYER,
            state=TakeoverState.RETURNED if process_alive else TakeoverState.FAILED,
            terminal_reason=reason,
            neutralized=neutralized,
            observation_resumed=process_alive,
            handback_latency_ms=latency_ms,
            final_state_fingerprint=final_state_fingerprint,
            process_alive=process_alive,
        )
        self._event(
            "control_returned",
            {
                "control_epoch": self.snapshot.control_epoch,
                "reason": reason.value,
                "neutralized": neutralized,
                "observation_resumed": process_alive,
                "process_alive": process_alive,
                "final_state_fingerprint": final_state_fingerprint,
            },
        )
        self._write("takeover_reconciliation.json", self._snapshot_payload())
        return self.snapshot

    def _snapshot_payload(self) -> dict[str, Any]:
        payload = asdict(self.snapshot)
        payload["owner"] = self.snapshot.owner.value
        payload["state"] = self.snapshot.state.value
        payload["terminal_reason"] = (
            self.snapshot.terminal_reason.value
            if self.snapshot.terminal_reason
            else None
        )
        payload["zero_agent_input_before"] = self.snapshot.agent_inputs_before == 0
        payload["zero_agent_input_after"] = self.snapshot.agent_inputs_after == 0
        return payload

    def _event(self, event: str, payload: dict[str, Any]) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        with (self.artifact_dir / "ownership_events.jsonl").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write(
                json.dumps(
                    {
                        "event": event,
                        "at": datetime.now(timezone.utc).isoformat(),
                        **payload,
                    },
                    sort_keys=True,
                )
                + "\n"
            )

    def _write(self, name: str, payload: dict[str, Any]) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        (self.artifact_dir / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def _write_command(self, payload: dict[str, Any]) -> None:
        self.command_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix=".control.", dir=self.command_path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                for key, value in sorted(payload.items()):
                    handle.write(f"{key}={value}\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.command_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def supported_solutions() -> tuple[ExecutableSolution, ...]:
    return (
        ExecutableSolution(
            "world_1_1_remainder_v1",
            1,
            "smb3",
            "smb3.world_1_1.normal_clear",
            ("level_remainder", "complete_level", "until_reclaim"),
            ("same_process", "world_1_1_gameplay", "fresh_observation"),
            ("game_owned_level_clear", "reclaim", "timeout", "failure"),
            True,
            True,
            "world_1_1_remainder_v1",
            ("accepted World 1-1 executable controller",),
        ),
        ExecutableSolution(
            "world_8_finish_game_v1",
            1,
            "smb3",
            "smb3.full_game.normal_clear",
            ("full_game", "world_or_route_goal", "until_reclaim"),
            ("same_process", "exact_fresh_power_on", "fresh_observation"),
            ("stable_game_owned_ending", "reclaim", "timeout", "failure"),
            True,
            True,
            "world_8_finish_game",
            ("accepted 26-segment world_8_finish_game route",),
        ),
    )
