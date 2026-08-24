from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from smb3_agent.fceux_harness import AttemptSummary, BatchSummary
from smb3_agent.goals import GoalRunResult
from smb3_agent.lab import (
    LabError,
    add_note_to_latest,
    build_issue_ledger_latest,
    propose_variants_from_latest,
    review_latest_session,
    start_session,
    write_codex_task_latest,
    write_ui_summary_latest,
)


def test_lab_start_writes_session_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _prepare_lab(monkeypatch, tmp_path)

    result = start_session(
        "show me the route at 4x",
        game_path=tmp_path / "local-game-file",
        attempts=1,
        artifacts_root=tmp_path / "artifacts/sessions",
    )

    manifest = yaml.safe_load(result.manifest_path.read_text())
    assert manifest["goal_id"] == "world_8_double_whistle"
    assert manifest["requested_speed"] == 4
    assert manifest["run_settings"]["speed_mode"] == "normal"
    assert manifest["run_settings"]["frame_sleep_seconds"] == 0.004167
    assert manifest["outputs"]["route_log"] == "goal/fceux_1_1.log"
    assert result.session_dir.joinpath("notes.yaml").is_file()


def test_lab_note_latest_preserves_raw_text_and_infers_anchor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _prepare_lab(monkeypatch, tmp_path)
    start_session(
        "show me the route at 4x",
        game_path=tmp_path / "local-game-file",
        attempts=1,
        artifacts_root=tmp_path / "artifacts/sessions",
    )

    text = "1-1 around 320 timer: falls into the hole and usually gets lucky"
    result = add_note_to_latest(text)

    assert result.note["text"] == text
    assert result.note["segment_id"] == "world_1_1_clear"
    assert result.note["anchor"] == {"type": "in_game_timer", "value": 320}
    notes = yaml.safe_load(result.notes_path.read_text())
    assert notes["notes"][0]["text"] == text


def test_latest_session_pointer_cannot_escape_artifact_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _prepare_lab(monkeypatch, tmp_path)
    outside = tmp_path / "outside-session"
    outside.mkdir()
    latest = tmp_path / "artifacts/sessions/latest.txt"
    latest.write_text(str(outside), encoding="utf-8")

    with pytest.raises(LabError, match="escapes the lab artifact root"):
        add_note_to_latest("must fail before reading outside session data")


def test_lab_note_extracts_artifact_evidence_without_creating_actionable_issue(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _prepare_lab(monkeypatch, tmp_path)
    start_session(
        "show me the route at 4x",
        game_path=tmp_path / "local-game-file",
        attempts=1,
        artifacts_root=tmp_path / "artifacts/sessions",
    )

    result = add_note_to_latest(
        "Captured guidance sheet: artifacts/fceux/1_5_capture/plant_wait.png",
        segment_id="world_1_5",
    )
    ledger = build_issue_ledger_latest()

    assert result.note["evidence_paths"] == ["artifacts/fceux/1_5_capture/plant_wait.png"]
    assert ledger.issues[0]["type"] == "evidence_attachment"
    assert ledger.issues[0]["actionable"] is False
    assert ledger.issues[0]["evidence_paths"] == ["artifacts/fceux/1_5_capture/plant_wait.png"]


def test_lab_review_and_variant_proposals_link_note_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _prepare_lab(monkeypatch, tmp_path)
    start_session(
        "show me the route at 4x",
        game_path=tmp_path / "local-game-file",
        attempts=1,
        artifacts_root=tmp_path / "artifacts/sessions",
    )
    add_note_to_latest("1-1 around 320 timer: falls into the hole and usually gets lucky")

    review = review_latest_session()
    proposals = propose_variants_from_latest()
    proposal = proposals.proposals[0]

    assert review.review["primary_segment"] == "world_1_1_clear"
    assert review.review["classification"] == "input_timing"
    assert proposal["variant_id"].startswith("world_1_1_clear_harden_320_")
    assert proposal["source_notes"] == ["note_001"]
    assert proposal["changes"][0]["file"] == "data/routes/scripts/world_1_1_clear_v0.yaml"


def test_issue_ledger_groups_batch_notes_and_prioritizes_recovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _prepare_lab(monkeypatch, tmp_path)
    start_session(
        "show me the route at 4x",
        game_path=tmp_path / "local-game-file",
        attempts=1,
        artifacts_root=tmp_path / "artifacts/sessions",
    )
    add_note_to_latest(
        "1-1 falls into hole at 283 on clock.",
        segment_id="world_1_1_clear",
        severity="harden",
    )
    add_note_to_latest(
        "1-2 and 1-3 are perfect. 1-3 is technically not complete because getting the whistle is expected.",
        segment_id="world_1_3_whistle",
        severity="note",
    )
    add_note_to_latest(
        "Castle dies first try every time. After death, carry-over inputs seem to send the route to 1-4.",
        segment_id="world_1_fortress_whistle",
        severity="harden",
    )

    result = build_issue_ledger_latest()

    assert len(result.issues) == 3
    assert result.actionable_count == 2
    assert result.issues[0]["segment_id"] == "world_1_fortress_whistle"
    assert result.issues[0]["type"] == "recovery_bug"
    assert result.issues[0]["priority"] == "high"
    assert [issue for issue in result.issues if issue["type"] == "expected_behavior"][0]["actionable"] is False


def test_multi_proposals_skip_non_actionable_issues(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _prepare_lab(monkeypatch, tmp_path)
    start_session(
        "show me the route at 4x",
        game_path=tmp_path / "local-game-file",
        attempts=1,
        artifacts_root=tmp_path / "artifacts/sessions",
    )
    add_note_to_latest("1-1 falls into hole at 283 on clock.", segment_id="world_1_1_clear", severity="harden")
    add_note_to_latest("1-3 whistle exit is expected.", segment_id="world_1_3_whistle")
    add_note_to_latest(
        "Castle dies first try and carry-over inputs send the route to 1-4.",
        segment_id="world_1_fortress_whistle",
        severity="harden",
    )

    issues = build_issue_ledger_latest()
    proposals = propose_variants_from_latest()

    assert issues.actionable_count == 2
    assert len(proposals.proposals) == 2
    assert proposals.proposals[0]["source_issue"] == issues.issues[0]["id"]
    assert proposals.proposals[0]["variant_id"].startswith("world_1_fortress_whistle_recovery_")
    assert all("source_issue" in proposal for proposal in proposals.proposals)


def test_issue_ledger_respects_explicit_failure_and_positive_severity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _prepare_lab(monkeypatch, tmp_path)
    start_session(
        "show me the route at 4x",
        game_path=tmp_path / "local-game-file",
        attempts=1,
        artifacts_root=tmp_path / "artifacts/sessions",
    )
    add_note_to_latest(
        "Expected: cross the gap without falling or relying on recovery.",
        segment_id="world_1_1_clear",
        severity="harden",
    )
    add_note_to_latest(
        "1-1 and 1-2 are good.",
        segment_id="world_1_2_clear",
        severity="positive",
    )
    add_note_to_latest(
        "Fortress falls in fire. Expected: fail cleanly without leaking inputs toward 1-4.",
        segment_id="world_1_fortress_whistle",
        severity="failure",
    )

    result = build_issue_ledger_latest()
    by_segment = {issue["segment_id"]: issue for issue in result.issues}

    assert by_segment["world_1_1_clear"]["type"] == "route_hardening"
    assert by_segment["world_1_1_clear"]["actionable"] is True
    assert by_segment["world_1_2_clear"]["type"] == "positive_evidence"
    assert by_segment["world_1_2_clear"]["actionable"] is False
    assert by_segment["world_1_fortress_whistle"]["type"] == "recovery_bug"
    assert by_segment["world_1_fortress_whistle"]["priority"] == "high"


def test_ui_summary_and_codex_task_packet(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _prepare_lab(monkeypatch, tmp_path)
    start_session(
        "show me the route at 4x",
        game_path=tmp_path / "local-game-file",
        attempts=1,
        artifacts_root=tmp_path / "artifacts/sessions",
    )
    add_note_to_latest(
        "Castle dies first try and carry-over inputs send the route to 1-4.",
        segment_id="world_1_fortress_whistle",
        severity="harden",
    )

    issues = build_issue_ledger_latest()
    proposals = propose_variants_from_latest()
    summary = write_ui_summary_latest()
    task = write_codex_task_latest(issues.issues[0]["id"])

    assert proposals.proposals
    assert summary.summary["totals"]["notes"] == 1
    assert summary.summary["totals"]["issues"] == 1
    assert summary.summary["highest_priority_issue"] == issues.issues[0]["id"]
    assert task.task_path.is_file()
    assert task.excerpt_path.is_file()
    task_yaml = yaml.safe_load(task.task_path.read_text())
    assert task_yaml["issue_id"] == issues.issues[0]["id"]
    assert "scripts/fceux_1_1_agent.lua" in task_yaml["inputs"]["relevant_files"]
    assert task_yaml["expected_output"]["artifact"].endswith("route-patch/v1.")
    assert "validation_command" not in task_yaml["expected_output"]
    assert task_yaml["expected_output"]["source"]["task_packet"] == str(task.task_path)


def _prepare_lab(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    tmp_path.joinpath("data/variants").mkdir(parents=True)
    tmp_path.joinpath("data/segments").mkdir(parents=True)
    tmp_path.joinpath("artifacts/sessions").mkdir(parents=True)
    tmp_path.joinpath("local-game-file").write_text("placeholder")
    tmp_path.joinpath("data/segments/world_1.yaml").write_text(
        yaml.safe_dump(
            {
                "catalog_id": "world_1",
                "segments": [
                    {"id": "world_1_1_clear", "name": "World 1-1", "status": "solved"},
                    {"id": "world_1_3_whistle", "name": "World 1-3 Whistle", "status": "solved"},
                    {
                        "id": "world_1_fortress_whistle",
                        "name": "World 1 Fortress Whistle",
                        "status": "bridged",
                    },
                ],
            }
        )
    )
    monkeypatch.setattr(
        "smb3_agent.lab.load_goal_contract",
        lambda path: SimpleNamespace(
            id="world_8_double_whistle",
            catalog_path=Path("data/segments/world_1.yaml"),
        ),
    )
    monkeypatch.setattr("smb3_agent.lab.resolve_goal_path", lambda goal: Path(f"data/goals/{goal}.yaml"))
    monkeypatch.setattr("smb3_agent.lab.run_goal_contract", _fake_run_goal_contract)


def _fake_run_goal_contract(
    contract,
    *,
    game_path,
    attempts,
    artifacts_dir,
    capture_images=False,
    capture_ticks=False,
    env_overrides=(),
):
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for attempt in range(1, attempts + 1):
        lines.extend(
            [
                f"frame=10 event=attempt_{attempt}_start x=24 y=384",
                f"frame=50 event=attempt_{attempt}_success_course_clear x=8192 y=0",
            ]
        )
    lines.append("frame=80 event=post_probe_1_airship_success_king x=432 y=4192")
    artifacts_dir.joinpath("fceux_1_1.log").write_text("\n".join(lines))
    return GoalRunResult(
        contract=contract,
        summary=BatchSummary(
            attempts=tuple(
                AttemptSummary(
                    attempt=attempt,
                    success=True,
                    bad_state=False,
                    reached_end=True,
                    goal_area=True,
                    max_x=2848,
                )
                for attempt in range(1, attempts + 1)
            ),
            post_probe_last_event="post_probe_1_airship_success_king",
            post_probe_clear=True,
        ),
        artifacts_dir=artifacts_dir,
        metrics_passed=True,
    )
