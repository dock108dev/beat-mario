from __future__ import annotations

from dataclasses import replace

import pytest

from smb3_agent.learning import (
    AttemptContract,
    CandidateLifecycle,
    LearningError,
    LocalLearningStore,
    ProgressAnchor,
    build_compatible_set,
    compatibility,
    derive_trouble_patterns,
    process_attempt,
)


def attempt(run_id: str, **changes: object) -> AttemptContract:
    base = AttemptContract(
        run_id=run_id,
        game_id="smb3",
        adapter_id="smb3",
        adapter_version="smb3-live-observer/v1",
        level_id="world_1_1",
        segment_id="world_1_1_clear",
        objective_id="smb3.world_1_1.normal_clear",
        objective_version=1,
        actor="player",
        start_boundary="stable_observed_level_gameplay",
        terminal_boundary="game_owned_clear_return_map",
        timing_units="fceux_emulated_frames",
        start_time=0,
        terminal_time=100,
        complete_timing_interval=True,
        emulator_assumptions=("same_process",),
        allowed_techniques=("normal_gameplay",),
        resource_policy=("no_automatic_inventory_use",),
        required_observation_facts=("course_clear",),
        observed_facts=("course_clear",),
        evidence_integrity=True,
        completion="completed",
        deaths=1,
        recoveries=0,
        directional_corrections=2,
        hesitation_intervals=0,
        missed_requirements=(),
        lost_resources=(),
        anchors=(ProgressAnchor("x-10", "world_1_1:x-bucket:10", 40, {"death": True}, (f"evidence:{run_id}",)),),
        tactic_tags=("low_directional_correction",),
        input_trace_reference=f"trace:{run_id}",
        observation_evidence_reference=f"evidence:{run_id}",
        created_at="2026-08-22T00:00:00+00:00",
    )
    return replace(base, **changes)


def test_compatibility_excludes_objective_version_mismatch() -> None:
    decision = compatibility(attempt("a"), attempt("b", objective_version=2))
    assert not decision.compatible
    assert "objective_version" in decision.mismatches


def test_one_failure_is_not_a_repeated_pattern() -> None:
    source = attempt("a")
    assert derive_trouble_patterns(build_compatible_set((source,)), (source,)) == ()


def test_three_compatible_failures_retain_sources() -> None:
    attempts = tuple(attempt(run_id) for run_id in ("a", "b", "c"))
    patterns = derive_trouble_patterns(build_compatible_set(attempts), attempts)
    assert patterns[0].supporting_run_ids == ("a", "b", "c")


def test_reprocessing_is_idempotent_and_review_does_not_execute(tmp_path) -> None:
    store = LocalLearningStore(tmp_path)
    inputs = (
        attempt("a"),
        attempt("b"),
        attempt("c", tactic_tags=(), terminal_time=150, deaths=2),
    )
    for item in (*inputs, inputs[-1]):
        process_attempt(store, item)
    snapshot = store.snapshot()
    assert len(snapshot.attempts) == 3
    candidate = snapshot.candidates[0]
    assert candidate.lifecycle is CandidateLifecycle.REVIEW_REQUIRED
    store.review(candidate.candidate_id, approve=True, reason="prepare replay", reviewer="owner")
    assert store.snapshot().candidates[0].lifecycle is CandidateLifecycle.APPROVED_FOR_VALIDATION
    assert not store._accepted_solutions()


def test_candidate_cannot_skip_review(tmp_path) -> None:
    store = LocalLearningStore(tmp_path)
    with pytest.raises(LearningError, match="unknown learning candidate"):
        store.record_replay_validation("missing", passed=True, evidence_references=("replay",), actor="campaign")


def test_checksum_corruption_fails_without_touching_raw_run(tmp_path) -> None:
    store = LocalLearningStore(tmp_path / "learning")
    store.record_attempt(attempt("a"))
    raw_run = tmp_path / "runs.jsonl"
    raw_run.write_text("immutable raw run\n", encoding="utf-8")
    store.events_path.write_text(store.events_path.read_text().replace("player", "agent", 1))
    with pytest.raises(LearningError, match="checksum mismatch"):
        store.snapshot()
    assert raw_run.read_text(encoding="utf-8") == "immutable raw run\n"
