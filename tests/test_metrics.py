from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from smb3_agent.metrics import (
    EVENT_SCHEMA_VERSION,
    EventEnvelope,
    LocalMetricsStore,
    MetricsError,
    event_from_dict,
    integrity_hash,
)


def fixture_event(**changes: object) -> EventEnvelope:
    values = {
        "event_id": "event-1", "schema_version": EVENT_SCHEMA_VERSION, "event_type": "observation_connected",
        "session_id": "session-1", "scenario_id": "observation.read_only_input_free", "scenario_version": "1",
        "attempt_id": "attempt-1", "correlation_id": "correlation-1", "causation_id": None,
        "game_id": "smb3", "adapter_id": "smb3", "adapter_version": "observer/v1",
        "objective_version": "objective/v1", "profile_version": "profile/v1", "solution_version": None,
        "actor": "adapter", "input_owner": "player", "control_epoch": 0, "lifecycle_state": "running",
        "source": "fixture", "provenance": ("fixture",), "evidence_classification": "deterministic_fixture_result",
        "monotonic_sequence": 1, "emulator_frame": None, "wall_clock_time": datetime.now(timezone.utc).isoformat(),
        "confidence": 1.0, "payload": {}, "artifact_references": (), "integrity_hash": "",
    }
    values.update(changes)
    unsigned = EventEnvelope(**values)
    return replace(unsigned, integrity_hash=integrity_hash(unsigned.canonical_content()))


def test_duplicate_ingestion_is_idempotent(tmp_path: Path) -> None:
    store = LocalMetricsStore(tmp_path)
    event = fixture_event()
    assert store.ingest(event) == "accepted"
    assert store.ingest(event) == "duplicate"
    assert store.summarize()["event_count"] == 1


def test_out_of_order_event_is_quarantined(tmp_path: Path) -> None:
    store = LocalMetricsStore(tmp_path)
    store.ingest(fixture_event(monotonic_sequence=2))
    assert store.ingest(fixture_event(event_id="event-2", monotonic_sequence=1)) == "quarantined"
    assert store.status()["quarantined_events"] == 1


def test_classification_upgrade_is_quarantined(tmp_path: Path) -> None:
    store = LocalMetricsStore(tmp_path)
    store.ingest(fixture_event())
    upgraded = fixture_event(event_id="event-2", monotonic_sequence=2, evidence_classification="owner_product_acceptance")
    assert store.ingest(upgraded) == "quarantined"


def test_actor_mismatch_is_rejected_before_metrics(tmp_path: Path) -> None:
    with pytest.raises(MetricsError, match="agent input actor mismatch"):
        fixture_event(event_type="agent_input", actor="player").validate()


def test_input_after_handback_remains_a_boundary_violation(tmp_path: Path) -> None:
    store = LocalMetricsStore(tmp_path)
    handback = fixture_event(event_type="handback_completed")
    post = fixture_event(event_id="event-2", event_type="player_input", actor="player", monotonic_sequence=2, payload={"boundary_violation": True})
    store.ingest(handback)
    store.ingest(post)
    assert store.summarize()["boundary_violation_count"] == 1


def test_corrupt_raw_storage_fails_rebuild_without_hiding_line(tmp_path: Path) -> None:
    store = LocalMetricsStore(tmp_path)
    store.root.mkdir(parents=True, exist_ok=True)
    store.raw_path.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(MetricsError, match="line 1"):
        store.rebuild()


def test_unsupported_schema_fails_explicitly() -> None:
    raw = fixture_event().to_dict()
    raw["schema_version"] = "game-companion-event/v99"
    raw["integrity_hash"] = integrity_hash({key: value for key, value in raw.items() if key != "integrity_hash"})
    with pytest.raises(MetricsError, match="unsupported event schema"):
        event_from_dict(raw)


def test_missing_or_incomplete_raw_evidence_is_not_silently_improved(tmp_path: Path) -> None:
    store = LocalMetricsStore(tmp_path)
    missing = fixture_event(event_type="artifact_missing", payload={"status": "unknown"})
    store.ingest(missing)
    summary = store.summarize()
    assert summary["event_type_counts"]["artifact_missing"] == 1
    assert summary["unknown_count"] == 1
    assert summary["combined_success_score"] is None
