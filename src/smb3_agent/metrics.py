from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import secrets
from typing import Any, Iterable, Mapping


EVENT_SCHEMA_VERSION = "game-companion-event/v1"
INDEX_SCHEMA_VERSION = "game-companion-metrics-index/v1"
EXPORT_SCHEMA_VERSION = "game-companion-metrics-export/v1"
DEFAULT_METRICS_ROOT = Path("artifacts/session-metrics")


class MetricsError(ValueError):
    pass


class MetricLabel(str, Enum):
    TECHNICAL_OPERATION = "technical_operation"
    ROUTE_RELIABILITY = "route_reliability"
    PRODUCT_BEHAVIOR = "product_behavior"
    OWNER_USEFULNESS = "owner_usefulness"
    OWNER_ACCEPTANCE = "owner_acceptance"
    VISIBLE_LIVE_EVIDENCE = "visible_live_evidence"
    UNATTENDED_REGRESSION = "unattended_regression"
    AUTHORITATIVE_GAME_OUTCOME = "authoritative_game_outcome"


EVENT_TYPES = frozenset(
    {
        "first_use_started", "game_file_detected", "game_file_selected", "game_identity_verified",
        "emulator_detected", "input_readiness_confirmed", "session_choice_selected", "first_use_completed",
        "configuration_failed", "session_started", "history_updated", "owner_feedback_prompted",
        "observation_connected", "observation_freshness", "observation_disconnected", "observation_recovered",
        "state_fact", "progress_fact", "player_input", "agent_input", "ownership_transition", "ownership_conflict",
        "tell_request", "coaching_policy", "suggestion_emitted", "suggestion_suppressed", "suggestion_response",
        "comparison", "profile_created", "run_created", "fastest_observed_updated", "learning_pattern",
        "candidate_reviewed", "candidate_rejected", "candidate_promotion_state", "show_started", "show_stopped",
        "takeover_authorized", "agent_control_started", "reclaim_requested", "input_neutralized", "handback_completed",
        "objective_outcome", "failure", "recovery", "process_lost", "cleanup", "adapter_switched", "evidence_reconciled",
        "artifact_missing", "integrity_failure", "owner_usefulness_feedback", "owner_acceptance_decision",
    }
)


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    schema_version: str
    event_type: str
    session_id: str
    scenario_id: str
    scenario_version: str
    attempt_id: str
    correlation_id: str
    causation_id: str | None
    game_id: str
    adapter_id: str
    adapter_version: str
    objective_version: str
    profile_version: str
    solution_version: str | None
    actor: str
    input_owner: str
    control_epoch: int
    lifecycle_state: str
    source: str
    provenance: tuple[str, ...]
    evidence_classification: str
    monotonic_sequence: int
    emulator_frame: int | None
    wall_clock_time: str
    confidence: float | None
    payload: Mapping[str, Any]
    artifact_references: tuple[str, ...]
    integrity_hash: str

    def canonical_content(self) -> dict[str, Any]:
        content = self.to_dict()
        content.pop("integrity_hash", None)
        return content

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id, "schema_version": self.schema_version, "event_type": self.event_type,
            "session_id": self.session_id, "scenario_id": self.scenario_id, "scenario_version": self.scenario_version,
            "attempt_id": self.attempt_id, "correlation_id": self.correlation_id, "causation_id": self.causation_id,
            "game_id": self.game_id, "adapter_id": self.adapter_id, "adapter_version": self.adapter_version,
            "objective_version": self.objective_version, "profile_version": self.profile_version,
            "solution_version": self.solution_version, "actor": self.actor, "input_owner": self.input_owner,
            "control_epoch": self.control_epoch, "lifecycle_state": self.lifecycle_state, "source": self.source,
            "provenance": list(self.provenance), "evidence_classification": self.evidence_classification,
            "monotonic_sequence": self.monotonic_sequence, "emulator_frame": self.emulator_frame,
            "wall_clock_time": self.wall_clock_time, "confidence": self.confidence, "payload": dict(self.payload),
            "artifact_references": list(self.artifact_references), "integrity_hash": self.integrity_hash,
        }

    def validate(self) -> None:
        if self.schema_version != EVENT_SCHEMA_VERSION:
            raise MetricsError(f"unsupported event schema: {self.schema_version}")
        if self.event_type not in EVENT_TYPES:
            raise MetricsError(f"unknown event type: {self.event_type}")
        if self.actor not in {"player", "agent", "owner", "adapter", "system", "unknown"}:
            raise MetricsError(f"unknown actor: {self.actor}")
        if self.input_owner not in {"player", "agent", "none", "ambiguous", "unknown"}:
            raise MetricsError(f"invalid input owner: {self.input_owner}")
        if self.monotonic_sequence < 0 or self.control_epoch < 0:
            raise MetricsError("sequence and control epoch must be non-negative")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise MetricsError("confidence must be between zero and one")
        if self.event_type == "player_input" and self.actor != "player":
            raise MetricsError("player input actor mismatch")
        if self.event_type == "agent_input" and self.actor != "agent":
            raise MetricsError("agent input actor mismatch")
        expected = integrity_hash(self.canonical_content())
        if self.integrity_hash != expected:
            raise MetricsError("event integrity hash mismatch")


def integrity_hash(content: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def event_from_dict(raw: Mapping[str, Any]) -> EventEnvelope:
    try:
        event = EventEnvelope(
            event_id=str(raw["event_id"]), schema_version=str(raw["schema_version"]), event_type=str(raw["event_type"]),
            session_id=str(raw["session_id"]), scenario_id=str(raw["scenario_id"]), scenario_version=str(raw["scenario_version"]),
            attempt_id=str(raw["attempt_id"]), correlation_id=str(raw["correlation_id"]),
            causation_id=str(raw["causation_id"]) if raw.get("causation_id") is not None else None,
            game_id=str(raw["game_id"]), adapter_id=str(raw["adapter_id"]), adapter_version=str(raw["adapter_version"]),
            objective_version=str(raw["objective_version"]), profile_version=str(raw["profile_version"]),
            solution_version=str(raw["solution_version"]) if raw.get("solution_version") is not None else None,
            actor=str(raw["actor"]), input_owner=str(raw["input_owner"]), control_epoch=int(raw["control_epoch"]),
            lifecycle_state=str(raw["lifecycle_state"]), source=str(raw["source"]),
            provenance=tuple(str(item) for item in raw.get("provenance", ())),
            evidence_classification=str(raw["evidence_classification"]), monotonic_sequence=int(raw["monotonic_sequence"]),
            emulator_frame=int(raw["emulator_frame"]) if raw.get("emulator_frame") is not None else None,
            wall_clock_time=str(raw["wall_clock_time"]), confidence=float(raw["confidence"]) if raw.get("confidence") is not None else None,
            payload=dict(raw.get("payload") or {}), artifact_references=tuple(str(item) for item in raw.get("artifact_references", ())),
            integrity_hash=str(raw["integrity_hash"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MetricsError(f"malformed event: {exc}") from exc
    event.validate()
    return event


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    label: MetricLabel
    numerator: str
    denominator: str
    unit: str
    filters: tuple[str, ...]
    unknown_policy: str


def metric_definitions() -> tuple[MetricDefinition, ...]:
    technical = MetricLabel.TECHNICAL_OPERATION
    product = MetricLabel.PRODUCT_BEHAVIOR
    definitions = {
        "first_use_completion": (product, "first_use_completed events", "first_use_started events", "sessions"),
        "configuration_failures": (technical, "configuration_failed events", "first-use and launch attempts", "failures"),
        "product_session_starts": (product, "session_started events", "completed first-use and resume requests", "sessions"),
        "history_updates": (product, "history_updated events", "reconciled product outcomes and state changes", "updates"),
        "observation_sessions": (product, "distinct sessions with observation_connected", "all ingested sessions", "sessions"),
        "fresh_duration": (product, "fresh observation milliseconds", "observed milliseconds", "milliseconds"),
        "stale_duration": (product, "stale observation milliseconds", "observed milliseconds", "milliseconds"),
        "supported_state": (product, "supported state facts", "all state facts", "facts"),
        "unsupported_state": (product, "unsupported state facts", "all state facts", "facts"),
        "observation_disconnects": (technical, "observation_disconnected events", "observation sessions", "events"),
        "observation_recoveries": (technical, "observation_recovered events", "observation disconnects", "events"),
        "reconciled_observation_facts": (product, "independently reconciled facts", "all observation facts", "facts"),
        "unknown_observation_facts": (product, "unknown or unverifiable facts", "all observation facts", "facts"),
        "player_inputs": (product, "player_input events", "all input events", "inputs"),
        "agent_inputs": (product, "agent_input events", "all input events", "inputs"),
        "inputs_before_authorization": (technical, "agent inputs before takeover_authorized", "agent inputs", "inputs"),
        "inputs_during_authorization": (technical, "agent inputs inside active authorization", "agent inputs", "inputs"),
        "inputs_after_handback": (technical, "inputs after handback_completed", "all inputs", "inputs"),
        "ownership_conflicts": (technical, "ownership_conflict events", "ownership transitions", "events"),
        "ambiguous_ownership": (technical, "events with ambiguous input owner", "all input events", "inputs"),
        "input_neutralization_latency": (technical, "milliseconds reclaim_requested to input_neutralized", "completed reclaim pairs", "milliseconds"),
        "input_after_terminal_handback": (technical, "input events after terminal handback", "all input events", "inputs"),
        "boundary_violations": (technical, "authorization, ownership, protected decision, and post-handback violations", "all sessions", "violations"),
        "tell_requests": (product, "tell_request events", "observation sessions", "requests"),
        "suggestions_emitted": (product, "suggestion_emitted events", "suggestion decisions", "suggestions"),
        "suggestions_suppressed": (product, "suggestion_suppressed events", "suggestion decisions", "suggestions"),
        "suggestion_responses": (product, "accepted dismissed ignored corrected or unverifiable responses", "suggestions emitted", "responses"),
        "compatible_comparisons": (product, "compatible comparison events", "all comparisons", "comparisons"),
        "incompatible_comparisons": (product, "incompatible comparison events", "all comparisons", "comparisons"),
        "objective_requirements": (product, "completed missed recoverable or unknown requirements", "all objective requirements", "requirements"),
        "authorization_attempts": (technical, "takeover authorization decisions", "takeover requests", "attempts"),
        "successful_transfers": (technical, "agent_control_started events", "authorized takeovers", "transfers"),
        "rejected_preflights": (technical, "blocked takeover preflights", "takeover preflights", "attempts"),
        "takeover_outcomes": (product, "success reclaim timeout failure cancellation or process loss", "takeovers started", "outcomes"),
        "reclaim_latency": (technical, "milliseconds reclaim requested to neutralization", "completed reclaim pairs", "milliseconds"),
        "handback_latency": (technical, "milliseconds neutralization to handback", "completed handbacks", "milliseconds"),
        "process_continuity": (technical, "sessions without process loss", "technical sessions", "sessions"),
        "final_state_readability": (product, "readable final states", "terminal sessions", "sessions"),
        "run_actor_counts": (product, "player agent and mixed runs", "all local runs", "runs"),
        "fastest_observed_replacements": (product, "compatible fastest updates", "completed compatible runs", "updates"),
        "candidate_traces": (product, "candidate traces", "eligible observed traces", "candidates"),
        "derived_patterns": (product, "learning patterns", "compatible evidence groups", "patterns"),
        "candidate_review_states": (product, "review rejection validation promotion rollback supersession states", "all candidates", "candidates"),
        "evidence_compatibility_failures": (technical, "incompatible evidence events", "evidence comparisons", "failures"),
        "required_artifacts_present": (technical, "reconciled present artifacts", "required artifacts", "artifacts"),
        "missing_artifacts": (technical, "artifact_missing events", "required artifacts", "artifacts"),
        "integrity_failures": (technical, "integrity_failure events", "events and artifacts checked", "failures"),
        "classification_mismatches": (technical, "classification mismatch events", "classified results", "mismatches"),
        "duplicate_processing": (technical, "duplicate event attempts", "ingestion attempts", "duplicates"),
        "reconciliation_completeness": (technical, "reconciled required artifacts", "required artifacts", "ratio"),
    }
    return tuple(
        MetricDefinition(key, value[0], value[1], value[2], value[3], ("exact source, adapter, profile, scenario, and version",), "retain and report unknowns")
        for key, value in definitions.items()
    ) + (
        MetricDefinition("owner_usefulness_feedback", MetricLabel.OWNER_USEFULNESS, "explicit owner usefulness responses", "owner feedback prompts answered", "responses", ("final campaign only",), "silence and missing feedback remain unknown"),
        MetricDefinition("owner_product_acceptance", MetricLabel.OWNER_ACCEPTANCE, "explicit owner acceptance decisions", "owner acceptance decisions requested", "decisions", ("final campaign only",), "technical success never supplies this value"),
        MetricDefinition("visible_live_results", MetricLabel.VISIBLE_LIVE_EVIDENCE, "visible live results", "visible scenarios", "results", (), "not inferred from deterministic or unattended results"),
        MetricDefinition("route_reliability_results", MetricLabel.ROUTE_RELIABILITY, "promotable route results", "fresh isolated reliability runs", "results", (), "failed and unknown runs stay in denominator"),
        MetricDefinition("unattended_regression_results", MetricLabel.UNATTENDED_REGRESSION, "unattended regression outcomes", "unattended regression attempts", "results", (), "cannot count as owner acceptance"),
        MetricDefinition("authoritative_game_outcomes", MetricLabel.AUTHORITATIVE_GAME_OUTCOME, "game-owned outcomes", "objective attempts", "outcomes", (), "self-declared outcomes remain unverifiable"),
    )


class LocalMetricsStore:
    def __init__(self, root: Path = DEFAULT_METRICS_ROOT, *, maximum_events: int | None = None):
        self.root = root
        self.raw_path = root / "events.jsonl"
        self.index_path = root / "index.json"
        self.quarantine_path = root / "quarantine.jsonl"
        self.maximum_events = maximum_events

    def ingest(self, event: EventEnvelope) -> str:
        event.validate()
        index = self._load_index()
        existing = index["events"].get(event.event_id)
        if existing:
            if existing == event.integrity_hash:
                index["duplicates_detected"] += 1
                self._write_index(index)
                return "duplicate"
            return self._reject(event.to_dict(), "event id reused with different content")
        key = f"{event.session_id}:{event.scenario_id}:{event.attempt_id}"
        last = index["last_sequence"].get(key)
        if last is not None and event.monotonic_sequence <= last:
            return self._reject(event.to_dict(), "out-of-order monotonic sequence")
        binding = index["bindings"].get(event.attempt_id)
        current = [event.scenario_version, event.game_id, event.adapter_id, event.adapter_version, event.objective_version, event.profile_version, event.evidence_classification]
        if binding and binding != current:
            return self._reject(event.to_dict(), "attempt binding or classification changed")
        if event.event_type in {"player_input", "agent_input"} and event.input_owner not in {event.actor, "ambiguous", "unknown"}:
            return self._reject(event.to_dict(), "actor and input owner contradict")
        self.root.mkdir(parents=True, exist_ok=True)
        self._append(self.raw_path, event.to_dict())
        index["events"][event.event_id] = event.integrity_hash
        index["last_sequence"][key] = event.monotonic_sequence
        index["bindings"][event.attempt_id] = current
        index["accepted_events"] += 1
        self._write_index(index)
        return "accepted"

    def events(self) -> tuple[EventEnvelope, ...]:
        if not self.raw_path.exists():
            return ()
        events: list[EventEnvelope] = []
        for line_number, line in enumerate(self.raw_path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                events.append(event_from_dict(json.loads(line)))
            except (json.JSONDecodeError, MetricsError) as exc:
                raise MetricsError(f"raw event corruption at line {line_number}: {exc}") from exc
        return tuple(events)

    def rebuild(self) -> dict[str, Any]:
        rebuilt = self._empty_index()
        for event in self.events():
            if event.event_id in rebuilt["events"]:
                rebuilt["duplicates_detected"] += 1
                continue
            key = f"{event.session_id}:{event.scenario_id}:{event.attempt_id}"
            prior = rebuilt["last_sequence"].get(key)
            if prior is not None and event.monotonic_sequence <= prior:
                raise MetricsError("cannot rebuild from out-of-order raw evidence")
            rebuilt["events"][event.event_id] = event.integrity_hash
            rebuilt["last_sequence"][key] = event.monotonic_sequence
            rebuilt["bindings"][event.attempt_id] = [event.scenario_version, event.game_id, event.adapter_id, event.adapter_version, event.objective_version, event.profile_version, event.evidence_classification]
            rebuilt["accepted_events"] += 1
        rebuilt["rebuilt_at"] = datetime.now(timezone.utc).isoformat()
        self._write_index(rebuilt)
        return rebuilt

    def summarize(self) -> dict[str, Any]:
        events = self.events()
        counts: dict[str, int] = {}
        for event in events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        inputs = [item for item in events if item.event_type in {"player_input", "agent_input"}]
        boundaries = sum(1 for item in inputs if item.payload.get("boundary_violation") is True) + counts.get("ownership_conflict", 0)
        sessions = {item.session_id for item in events}
        session_events: dict[str, list[EventEnvelope]] = {}
        for item in events:
            session_events.setdefault(item.session_id, []).append(item)
        recent_sessions = []
        for session_id, items in sorted(
            session_events.items(), key=lambda pair: pair[1][-1].wall_clock_time, reverse=True
        )[:10]:
            actors = {item.actor for item in items if item.event_type in {"player_input", "agent_input"}}
            ownership = "mixed" if {"player", "agent"}.issubset(actors) else next(iter(actors), "none")
            last = items[-1]
            recent_sessions.append({
                "session_id": session_id,
                "scenario_id": last.scenario_id,
                "scenario_version": last.scenario_version,
                "game_id": last.game_id,
                "adapter_id": last.adapter_id,
                "ownership": ownership,
                "objective": last.payload.get("objective", last.objective_version),
                "outcome": last.payload.get("outcome", "unknown"),
                "evidence_classification": last.evidence_classification,
                "technical_status": last.lifecycle_state,
                "observation_freshness": next((item.payload.get("freshness") for item in reversed(items) if item.event_type == "observation_freshness"), "unknown"),
                "suggestions": sum(item.event_type == "suggestion_emitted" for item in items),
                "suggestion_responses": sum(item.event_type == "suggestion_response" for item in items),
                "takeovers": sum(item.event_type == "agent_control_started" for item in items),
                "handbacks": sum(item.event_type == "handback_completed" for item in items),
                "run_library_changes": sum(item.event_type in {"run_created", "fastest_observed_updated"} for item in items),
                "learning_candidate_changes": sum(item.event_type in {"candidate_reviewed", "candidate_rejected", "candidate_promotion_state"} for item in items),
                "missing_or_incompatible_evidence": sum(item.event_type in {"artifact_missing", "integrity_failure"} or item.payload.get("compatible") is False for item in items),
            })
        classifications: dict[str, int] = {}
        for item in events:
            classifications[item.evidence_classification] = classifications.get(item.evidence_classification, 0) + 1
        return {
            "schema_version": "game-companion-metrics-summary/v1",
            "filters": {"source": "all local raw events", "unknowns_dropped": False},
            "event_count": len(events), "session_count": len(sessions), "event_type_counts": counts,
            "classification_counts": classifications, "player_input_count": counts.get("player_input", 0),
            "agent_input_count": counts.get("agent_input", 0), "ambiguous_ownership_count": sum(item.input_owner == "ambiguous" for item in inputs),
            "boundary_violation_count": boundaries, "boundary_violation_required_value": 0,
            "unknown_count": sum(1 for item in events if item.confidence is None or item.input_owner == "unknown" or item.payload.get("status") in {"unknown", "unverifiable"}),
            "metric_definitions": [definition.__dict__ | {"label": definition.label.value} for definition in metric_definitions()],
            "combined_success_score": None,
            "recent_sessions": recent_sessions,
            "duplicate_processing_count": self._load_index()["duplicates_detected"],
        }

    def export(self, destination: Path) -> Path:
        payload = {"schema_version": EXPORT_SCHEMA_VERSION, "exported_at": datetime.now(timezone.utc).isoformat(), "local_only": True, "summary": self.summarize(), "events": [event.to_dict() for event in self.events()]}
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._atomic(destination, payload)
        return destination

    def status(self) -> dict[str, Any]:
        index = self._load_index()
        return {"schema_version": INDEX_SCHEMA_VERSION, "raw_path": str(self.raw_path), "raw_exists": self.raw_path.exists(), "accepted_events": index["accepted_events"], "duplicates_detected": index["duplicates_detected"], "quarantined_events": index["quarantined_events"], "supported_event_schema": EVENT_SCHEMA_VERSION, "retention": {"maximum_events": self.maximum_events, "automatic_deletion": False}, "recovery": "rebuild index from append-only raw events"}

    def deletion_plan(self, *, game_id: str | None = None, adapter_id: str | None = None) -> dict[str, Any]:
        return {"schema_version": "game-companion-metrics-deletion-plan/v1", "filters": {"game_id": game_id, "adapter_id": adapter_id}, "execute": False, "protected": ["accepted route evidence", "reliability artifacts", "owner acceptance records"], "eligible": ["derived metric indexes", "raw product-session events matching explicit filters"], "requires_explicit_confirmation": True}

    def _reject(self, raw: Mapping[str, Any], reason: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        self._append(self.quarantine_path, {"reason": reason, "received_at": datetime.now(timezone.utc).isoformat(), "event": raw})
        index = self._load_index()
        index["quarantined_events"] += 1
        if reason.startswith("event id reused"):
            index["duplicates_detected"] += 1
        self._write_index(index)
        return "quarantined"

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return self._empty_index()
        try:
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MetricsError("derived index is corrupt; rebuild from raw events") from exc
        if raw.get("schema_version") != INDEX_SCHEMA_VERSION:
            raise MetricsError("unsupported metrics index schema")
        return raw

    @staticmethod
    def _empty_index() -> dict[str, Any]:
        return {"schema_version": INDEX_SCHEMA_VERSION, "events": {}, "last_sequence": {}, "bindings": {}, "accepted_events": 0, "duplicates_detected": 0, "quarantined_events": 0, "rebuilt_at": None}

    @staticmethod
    def _append(path: Path, payload: Mapping[str, Any]) -> None:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _write_index(self, payload: Mapping[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._atomic(self.index_path, payload)

    @staticmethod
    def _atomic(path: Path, payload: Mapping[str, Any]) -> None:
        temporary = path.with_suffix(f".{secrets.token_hex(4)}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
