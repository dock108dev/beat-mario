from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from smb3_agent.run_library import (
    CompletionClassification,
    LocalRunLibrary,
    RunRecord,
    SolutionClassification,
    DynamicObjectiveProfile,
)


def _run(
    run_id: str,
    elapsed: int,
    *,
    actor: str = "player",
    evidence: str | None = None,
    completion: CompletionClassification = CompletionClassification.COMPLETED,
    comparable: bool = True,
) -> RunRecord:
    profile_id = "smb3.world_1_1.normal_clear"
    return RunRecord(
        run_id=run_id,
        evidence_key=LocalRunLibrary.evidence_key(evidence or run_id, profile_id, 1),
        game_id="smb3",
        level_id="world_1_1",
        segment_id="world_1_1_clear",
        profile_id=profile_id,
        profile_version=1,
        actor=actor,
        session_actor=actor,
        start_state={"boundary": "stable_level_start", "x": 24},
        terminal_state={"boundary": "game_owned_clear", "return_map": 1},
        start_frame=100,
        terminal_frame=100 + elapsed,
        elapsed_compatible_frames=elapsed,
        timing_units="fceux_emulated_frames",
        emulator_assumptions=("ntsc", "no_frame_skip"),
        deaths=0,
        recoveries=0,
        resources={"lives_start": 4, "lives_end": 4},
        required_events=("stable_level_identity", "level_start", "game_owned_clear"),
        optional_events=(),
        input_trace_reference=f"evidence/{run_id}/inputs.jsonl",
        observation_evidence_reference=f"evidence/{run_id}/observations.jsonl",
        completion=completion,
        comparison_compatible=comparable,
        compatibility_reason="all comparison fields agree" if comparable else "emulator assumptions unknown",
        solution_classification=(
            SolutionClassification.CANDIDATE
            if completion is CompletionClassification.COMPLETED
            else SolutionClassification.FAILED_ATTEMPT
        ),
        provenance=(f"local-evidence:{run_id}",),
        created_at=f"2026-08-21T00:00:0{run_id[-1]}+00:00",
    )


def test_first_completion_creates_profile_and_fastest_observed_baseline(tmp_path: Path) -> None:
    library = LocalRunLibrary(tmp_path)
    decision = library.record(_run("run-1", 600))

    assert decision.created and decision.profile_created
    assert decision.previous_fastest_overall is None
    assert decision.resulting_fastest_overall == "run-1"
    assert library.summary("smb3", "world_1_1")["fastest_player"].run_id == "run-1"


def test_slower_preserves_best_and_faster_replaces_it_without_losing_history(tmp_path: Path) -> None:
    library = LocalRunLibrary(tmp_path)
    library.record(_run("run-1", 600))
    slower = library.record(_run("run-2", 700))
    faster = library.record(_run("run-3", 500))

    assert slower.resulting_fastest_overall == "run-1"
    assert faster.previous_fastest_overall == "run-1"
    assert faster.resulting_fastest_overall == "run-3"
    assert [run.run_id for run in library.runs()] == ["run-1", "run-2", "run-3"]


def test_player_agent_and_overall_bests_reconcile_and_mixed_is_not_agent(tmp_path: Path) -> None:
    library = LocalRunLibrary(tmp_path)
    library.record(_run("run-1", 600, actor="player"))
    library.record(_run("run-2", 550, actor="agent"))
    library.record(_run("run-3", 500, actor="mixed"))
    summary = library.summary("smb3", "world_1_1")

    assert summary["fastest_player"].run_id == "run-1"
    assert summary["fastest_agent"].run_id == "run-2"
    assert summary["fastest_overall"].run_id == "run-3"
    assert summary["fastest_overall"].actor == "mixed"


def test_incompatible_failed_and_incomplete_runs_are_retained_but_never_best(tmp_path: Path) -> None:
    library = LocalRunLibrary(tmp_path)
    library.record(_run("run-1", 600))
    library.record(_run("run-2", 400, comparable=False))
    library.record(_run("run-3", 300, completion=CompletionClassification.FAILED))
    library.record(_run("run-4", 200, completion=CompletionClassification.INCOMPLETE))

    assert len(library.runs()) == 4
    assert library.summary("smb3", "world_1_1")["fastest_overall"].run_id == "run-1"


def test_duplicate_evidence_is_idempotent(tmp_path: Path) -> None:
    library = LocalRunLibrary(tmp_path)
    first = library.record(_run("run-1", 600, evidence="same-evidence"))
    duplicate = library.record(_run("run-copy", 600, evidence="same-evidence"))

    assert first.created
    assert not duplicate.created
    assert duplicate.run.run_id == "run-1"
    assert len(library.runs()) == 1


def test_compatibility_includes_boundaries_timing_emulator_and_required_evidence() -> None:
    left = _run("run-1", 600)
    assert LocalRunLibrary.compatible(left, _run("run-2", 700))
    assert not LocalRunLibrary.compatible(
        left, replace(_run("run-2", 700), timing_units="wall_clock_ms")
    )
    assert not LocalRunLibrary.compatible(
        left, replace(_run("run-2", 700), emulator_assumptions=("pal",))
    )


def test_captured_completed_trace_defaults_to_candidate_non_executable() -> None:
    run = _run("run-1", 600)
    assert run.solution_classification is SolutionClassification.CANDIDATE
    assert "executable" not in run.solution_classification.value


def test_dynamic_profiles_are_not_limited_to_named_examples(tmp_path: Path) -> None:
    library = LocalRunLibrary(tmp_path)
    profile = DynamicObjectiveProfile(
        game_id="smb3",
        level_id="world_custom",
        profile_id="smb3.world_custom.challenge.no_powerups_v3",
        version=3,
        name="Owner-defined no-power-up challenge",
        start_boundary="stable_level_start",
        terminal_boundary="game_owned_clear",
        timing_units="fceux_emulated_frames",
        emulator_assumptions=("ntsc",),
        required_events=("clear", "powerup_count_equals_zero"),
        optional_events=("coins",),
        evidence_required=("level_identity", "input_trace", "game_owned_clear"),
        created_at="2026-08-21T00:00:00+00:00",
        provenance=("owner-defined-contract",),
    )
    assert library.record_profile(profile)
    assert not library.record_profile(profile)
    assert library.profiles() == [profile]
