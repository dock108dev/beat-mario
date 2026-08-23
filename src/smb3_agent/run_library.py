from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class RunLibraryError(ValueError):
    pass


class CompletionClassification(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    RECLAIMED = "reclaimed"
    CANCELLED = "cancelled"


class SolutionClassification(str, Enum):
    CANDIDATE = "candidate_captured_trace"
    EXECUTABLE = "replay_safe_executable"
    ACCEPTED = "accepted_executable_solution"
    SAFE_REFERENCE = "safe_reference_solution"
    FAILED_ATTEMPT = "failed_or_incomplete_attempt"


@dataclass(frozen=True)
class DynamicObjectiveProfile:
    game_id: str
    level_id: str
    profile_id: str
    version: int
    name: str
    start_boundary: str
    terminal_boundary: str
    timing_units: str
    emulator_assumptions: tuple[str, ...]
    required_events: tuple[str, ...]
    optional_events: tuple[str, ...]
    evidence_required: tuple[str, ...]
    created_at: str
    provenance: tuple[str, ...]

    def validate(self) -> None:
        if not all((self.game_id, self.level_id, self.profile_id, self.name)):
            raise RunLibraryError("profile identity is required")
        if self.version < 1 or not self.start_boundary or not self.terminal_boundary:
            raise RunLibraryError("profile version and boundaries are required")
        if not self.timing_units or not self.required_events or not self.evidence_required:
            raise RunLibraryError("profile timing, finite requirements, and evidence are required")


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    evidence_key: str
    game_id: str
    level_id: str
    segment_id: str
    profile_id: str
    profile_version: int
    actor: str
    session_actor: str
    start_state: dict[str, Any]
    terminal_state: dict[str, Any]
    start_frame: int
    terminal_frame: int
    elapsed_compatible_frames: int
    timing_units: str
    emulator_assumptions: tuple[str, ...]
    deaths: int
    recoveries: int
    resources: dict[str, Any]
    required_events: tuple[str, ...]
    optional_events: tuple[str, ...]
    input_trace_reference: str
    observation_evidence_reference: str
    completion: CompletionClassification
    comparison_compatible: bool
    compatibility_reason: str
    solution_classification: SolutionClassification
    provenance: tuple[str, ...]
    created_at: str

    def validate(self) -> None:
        if self.actor not in {"player", "agent", "mixed"}:
            raise RunLibraryError("run actor must be player, agent, or mixed")
        if self.session_actor not in {"player", "agent", "mixed"}:
            raise RunLibraryError("session actor must be player, agent, or mixed")
        if not all(
            (
                self.run_id,
                self.evidence_key,
                self.game_id,
                self.level_id,
                self.segment_id,
                self.profile_id,
                self.input_trace_reference,
                self.observation_evidence_reference,
            )
        ):
            raise RunLibraryError("run identity and evidence references are required")
        if self.profile_version < 1 or self.start_frame < 0:
            raise RunLibraryError("profile version and start frame are invalid")
        if self.terminal_frame < self.start_frame:
            raise RunLibraryError("terminal frame precedes start frame")
        if self.elapsed_compatible_frames != self.terminal_frame - self.start_frame:
            raise RunLibraryError("elapsed frames do not reconcile")
        if self.deaths < 0 or self.recoveries < 0 or not self.provenance:
            raise RunLibraryError("run counts and provenance are invalid")
        if (
            self.solution_classification is SolutionClassification.ACCEPTED
            and self.completion is not CompletionClassification.COMPLETED
        ):
            raise RunLibraryError("only completed runs can identify accepted solutions")


@dataclass(frozen=True)
class RunDecision:
    run: RunRecord
    created: bool
    previous_fastest_overall: str | None
    resulting_fastest_overall: str | None
    previous_fastest_actor: str | None
    resulting_fastest_actor: str | None
    profile_created: bool


class LocalRunLibrary:
    """Deterministic, append-only, local run/profile storage."""

    def __init__(self, root: Path = Path("artifacts/run-library")) -> None:
        self.root = root
        self.profiles_path = root / "profiles.jsonl"
        self.runs_path = root / "runs.jsonl"
        self.index_path = root / "index.json"

    def record(self, run: RunRecord) -> RunDecision:
        run.validate()
        self.root.mkdir(parents=True, exist_ok=True)
        runs = self.runs()
        duplicate = next((item for item in runs if item.evidence_key == run.evidence_key), None)
        if duplicate is not None:
            index = self._index(runs)
            return RunDecision(
                duplicate,
                False,
                index["fastest_overall"].get(self._profile_key(duplicate)),
                index["fastest_overall"].get(self._profile_key(duplicate)),
                index["fastest_by_actor"].get(self._actor_key(duplicate)),
                index["fastest_by_actor"].get(self._actor_key(duplicate)),
                False,
            )
        profiles = self.profiles()
        profile_created = False
        if not any(
            profile.profile_id == run.profile_id and profile.version == run.profile_version
            for profile in profiles
        ):
            if run.profile_id != self.normal_clear_profile_id(run.game_id, run.level_id):
                raise RunLibraryError("unknown profiles require an explicit measurable contract")
            profile = self._normal_clear_profile(run)
            self._append(self.profiles_path, asdict(profile))
            profile_created = True
        previous = self._index(runs)
        self._append(self.runs_path, self._serialize_run(run))
        resulting = self._index([*runs, run])
        self._atomic_json(self.index_path, resulting)
        profile_key = self._profile_key(run)
        actor_key = self._actor_key(run)
        return RunDecision(
            run,
            True,
            previous["fastest_overall"].get(profile_key),
            resulting["fastest_overall"].get(profile_key),
            previous["fastest_by_actor"].get(actor_key),
            resulting["fastest_by_actor"].get(actor_key),
            profile_created,
        )

    def record_profile(self, profile: DynamicObjectiveProfile) -> bool:
        """Append any adapter-defined measurable objective; names are not enumerated."""
        profile.validate()
        self.root.mkdir(parents=True, exist_ok=True)
        if any(
            item.profile_id == profile.profile_id and item.version == profile.version
            for item in self.profiles()
        ):
            return False
        self._append(self.profiles_path, asdict(profile))
        return True

    def profiles(self) -> list[DynamicObjectiveProfile]:
        tuple_fields = {
            "emulator_assumptions",
            "required_events",
            "optional_events",
            "evidence_required",
            "provenance",
        }
        profiles: list[DynamicObjectiveProfile] = []
        for item in self._records(self.profiles_path):
            for field in tuple_fields:
                item[field] = tuple(item[field])
            profiles.append(DynamicObjectiveProfile(**item))
        return profiles

    def runs(self) -> list[RunRecord]:
        records: list[RunRecord] = []
        for item in self._records(self.runs_path):
            item["completion"] = CompletionClassification(item["completion"])
            item["solution_classification"] = SolutionClassification(
                item["solution_classification"]
            )
            for field in (
                "emulator_assumptions",
                "required_events",
                "optional_events",
                "provenance",
            ):
                item[field] = tuple(item[field])
            records.append(RunRecord(**item))
        return records

    def summary(self, game_id: str, level_id: str, profile_id: str | None = None) -> dict[str, Any]:
        selected = [
            run
            for run in self.runs()
            if run.game_id == game_id
            and run.level_id == level_id
            and (profile_id is None or run.profile_id == profile_id)
        ]
        index = self._index(selected)
        return {
            "run_count": len(selected),
            "completed_count": sum(run.completion is CompletionClassification.COMPLETED for run in selected),
            "fastest_overall": self._resolve(index["fastest_overall"], selected),
            "fastest_player": self._resolve_actor(index["fastest_by_actor"], selected, "player"),
            "fastest_agent": self._resolve_actor(index["fastest_by_actor"], selected, "agent"),
            "fastest_mixed": self._resolve_mixed(selected),
            "most_recent": selected[-1] if selected else None,
        }

    @staticmethod
    def normal_clear_profile_id(game_id: str, level_id: str) -> str:
        return f"{game_id}.{level_id}.normal_clear"

    @staticmethod
    def evidence_key(reference: str, profile_id: str, profile_version: int) -> str:
        return hashlib.sha256(
            f"{reference}\0{profile_id}\0{profile_version}".encode()
        ).hexdigest()

    def _normal_clear_profile(self, run: RunRecord) -> DynamicObjectiveProfile:
        return DynamicObjectiveProfile(
            run.game_id,
            run.level_id,
            run.profile_id,
            run.profile_version,
            "Normal clear",
            str(run.start_state.get("boundary", "level_start")),
            str(run.terminal_state.get("boundary", "game_owned_clear")),
            run.timing_units,
            run.emulator_assumptions,
            run.required_events,
            run.optional_events,
            ("stable_level_identity", "complete_timing_interval", "game_owned_completion", "actor_ownership", "evidence_provenance"),
            run.created_at,
            run.provenance,
        )

    def _index(self, runs: list[RunRecord]) -> dict[str, Any]:
        comparable = [
            run
            for run in runs
            if run.comparison_compatible and run.completion is CompletionClassification.COMPLETED
        ]
        overall: dict[str, str] = {}
        actors: dict[str, str] = {}
        recent: dict[str, str] = {}
        by_id = {run.run_id: run for run in runs}
        for run in runs:
            recent[self._profile_key(run)] = run.run_id
        for run in comparable:
            profile_key = self._profile_key(run)
            current = by_id.get(overall.get(profile_key, ""))
            if current is None or (run.elapsed_compatible_frames, run.created_at, run.run_id) < (
                current.elapsed_compatible_frames,
                current.created_at,
                current.run_id,
            ):
                overall[profile_key] = run.run_id
            if run.actor in {"player", "agent"}:
                actor_key = self._actor_key(run)
                current = by_id.get(actors.get(actor_key, ""))
                if current is None or (run.elapsed_compatible_frames, run.created_at, run.run_id) < (
                    current.elapsed_compatible_frames,
                    current.created_at,
                    current.run_id,
                ):
                    actors[actor_key] = run.run_id
        return {
            "schema": "game-companion-run-library-index/v1",
            "fastest_overall": overall,
            "fastest_by_actor": actors,
            "most_recent": recent,
            "run_count": len(runs),
        }

    @staticmethod
    def compatible(left: RunRecord, right: RunRecord) -> bool:
        return (
            left.game_id,
            left.level_id,
            left.profile_id,
            left.profile_version,
            left.start_state.get("boundary"),
            left.terminal_state.get("boundary"),
            left.timing_units,
            left.emulator_assumptions,
            left.required_events,
        ) == (
            right.game_id,
            right.level_id,
            right.profile_id,
            right.profile_version,
            right.start_state.get("boundary"),
            right.terminal_state.get("boundary"),
            right.timing_units,
            right.emulator_assumptions,
            right.required_events,
        )

    def _resolve(self, mapping: dict[str, str], runs: list[RunRecord]) -> RunRecord | None:
        ids = set(mapping.values())
        candidates = [run for run in runs if run.run_id in ids]
        return min(candidates, key=lambda run: run.elapsed_compatible_frames) if candidates else None

    def _resolve_actor(self, mapping: dict[str, str], runs: list[RunRecord], actor: str) -> RunRecord | None:
        ids = set(mapping.values())
        candidates = [run for run in runs if run.run_id in ids and run.actor == actor]
        return min(candidates, key=lambda run: run.elapsed_compatible_frames) if candidates else None

    @staticmethod
    def _resolve_mixed(runs: list[RunRecord]) -> RunRecord | None:
        candidates = [
            run
            for run in runs
            if run.actor == "mixed"
            and run.comparison_compatible
            and run.completion is CompletionClassification.COMPLETED
        ]
        return min(candidates, key=lambda run: run.elapsed_compatible_frames) if candidates else None

    @staticmethod
    def _profile_key(run: RunRecord) -> str:
        return f"{run.game_id}:{run.level_id}:{run.profile_id}@{run.profile_version}"

    def _actor_key(self, run: RunRecord) -> str:
        return f"{self._profile_key(run)}:{run.actor}"

    @staticmethod
    def _serialize_run(run: RunRecord) -> dict[str, Any]:
        payload = asdict(run)
        payload["completion"] = run.completion.value
        payload["solution_classification"] = run.solution_classification.value
        return payload

    @staticmethod
    def _records(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    @staticmethod
    def _append(path: Path, payload: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def utc_created_at() -> str:
    return datetime.now(timezone.utc).isoformat()
