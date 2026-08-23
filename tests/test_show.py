from __future__ import annotations

import http.client
import json
import threading
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from smb3_agent.companion_session import Freshness, Observation, ObservationSource
from smb3_agent.lab_ui import _new_lab_ui_server, default_companion_session, render_companion_ui
from smb3_agent.review import LogEvent
from smb3_agent.show import (
    ShowCueStatus,
    ShowError,
    ShowLifecycle,
    ShowOutcome,
    ShowProcessController,
    ShowRequest,
    ShowSession,
    ShowSessionManager,
    load_show_definition,
    reconcile_show_cues,
    run_show_demonstration,
    show_capability,
    validate_show_definition,
)


def _request(tmp_path: Path, *, source: ObservationSource = ObservationSource.ADAPTER, segment: str = "world_1_1_clear") -> ShowRequest:
    game = tmp_path / "game.nes"
    game.write_bytes(b"test game")
    return ShowRequest(
        adapter_id="smb3", game_id="smb3", goal_id="world_8_double_whistle",
        segment_id=segment,
        observation=Observation(
            checkpoint="World 1-1", checkpoint_id=segment, observed_at=datetime.now(timezone.utc),
            freshness=Freshness.FRESH, confidence=1.0, evidence_references=("adapter:fresh",),
            source=source, game_id="smb3",
        ),
        game_path=game, trusted_starting_state="fresh power-on",
        demonstration_stop_event="show_input_stopped", recovery_boundary="stop on mismatch",
        protected_decisions=("player game",),
    )


def _event(frame: int, name: str) -> LogEvent:
    return LogEvent(frame, name, {}, f"frame={frame} event={name}")


def _success_events() -> tuple[LogEvent, ...]:
    return (
        _event(10, "attempt_1_fresh_start"),
        _event(100, "attempt_1_reached_end_x"),
        _event(140, "attempt_1_success_course_clear"),
    )


def test_supported_segment_exposes_show(tmp_path: Path) -> None:
    capability = show_capability(_request(tmp_path))
    assert capability.available
    assert capability.definition is not None


def test_unsupported_segment_is_unavailable_with_reason(tmp_path: Path) -> None:
    capability = show_capability(_request(tmp_path, segment="world_1_2_clear"))
    assert not capability.available
    assert "supports only world_1_1_clear" in capability.reason


def test_player_reported_context_cannot_start_show(tmp_path: Path) -> None:
    with pytest.raises(ShowError, match="adapter-observed"):
        _request(tmp_path, source=ObservationSource.PLAYER).validate()


def test_missing_game_file_blocks_show(tmp_path: Path) -> None:
    request = replace(_request(tmp_path), game_path=tmp_path / "missing.nes")
    assert not show_capability(request).available


def test_invalid_show_definition_fails_closed() -> None:
    definition = load_show_definition()
    with pytest.raises(ShowError, match="unknown event"):
        validate_show_definition(replace(definition, success_event="invented_success"))


def test_show_definition_rejects_duplicates_and_wrong_terminal() -> None:
    definition = load_show_definition()
    duplicate = replace(definition.cues[1], cue_id=definition.cues[0].cue_id)
    with pytest.raises(ShowError, match="unique"):
        validate_show_definition(replace(definition, cues=(definition.cues[0], duplicate, definition.cues[2])))
    with pytest.raises(ShowError, match="exact terminal"):
        validate_show_definition(replace(definition, cues=definition.cues[:-1]))


def test_show_request_and_outcome_policy_cannot_be_promoted(tmp_path: Path) -> None:
    for request in (
        replace(_request(tmp_path), review_only=False),
        replace(_request(tmp_path), promotable=True),
        replace(_request(tmp_path), counts_toward_reliability=True),
    ):
        with pytest.raises(ShowError, match="review-only"):
            request.validate()
    for outcome in (
        ShowOutcome(False, player_completion=True),
        ShowOutcome(False, authoritative_acceptance=True),
        ShowOutcome(False, counts_toward_reliability=True),
    ):
        with pytest.raises(ShowError):
            outcome.validate()


def test_cue_triggers_reconcile_in_exact_order_and_map_images(tmp_path: Path) -> None:
    images = tuple(tmp_path / name for name in ("000010_tick.png", "000100_tick.png", "000140_tick.png"))
    for image in images:
        image.write_bytes(b"png")
    result = reconcile_show_cues(load_show_definition(), _success_events(), images)
    assert result.passed
    assert [cue.status for cue in result.cues] == [ShowCueStatus.OBSERVED] * 3
    assert [item.cue_id for item in result.manifest] == ["opening", "final_run", "course_clear"]
    assert all(item.path for item in result.manifest)


@pytest.mark.parametrize(
    ("events", "problem"),
    [
        ((_event(10, "attempt_1_fresh_start"), _event(140, "attempt_1_success_course_clear")), "missing cue"),
        ((_event(100, "attempt_1_reached_end_x"), _event(10, "attempt_1_fresh_start"), _event(140, "attempt_1_success_course_clear")), "out-of-order"),
        ((_event(10, "attempt_1_fresh_start"), _event(100, "attempt_1_reached_end_x")), "missing terminal"),
    ],
)
def test_missing_out_of_order_or_terminal_cue_fails(events: tuple[LogEvent, ...], problem: str) -> None:
    result = reconcile_show_cues(load_show_definition(), events)
    assert not result.passed
    assert problem in (result.first_problem or "")


def test_process_exit_alone_cannot_pass() -> None:
    result = reconcile_show_cues(load_show_definition(), ())
    assert not result.passed
    assert not result.success_event_observed


def test_timeout_stops_owned_process_and_retains_failure_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeProcess:
        pid = 424242

        def __init__(self) -> None:
            self.returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def wait(self, timeout: float | None = None) -> int:
            self.returncode = -15
            return self.returncode

    process = FakeProcess()
    monkeypatch.setattr("smb3_agent.show.subprocess.Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr("smb3_agent.show.os.killpg", lambda pid, sig: None)
    artifacts = tmp_path / "timeout"
    outcome = run_show_demonstration(
        _request(tmp_path), load_show_definition(), artifacts,
        ShowProcessController(), timeout_seconds=0,
    )
    report = json.loads((artifacts / "show_report.json").read_text())
    execution = json.loads((artifacts / "fceux_execution.json").read_text())
    assert not outcome.demonstration_game_owned_success
    assert outcome.input_stopped and outcome.process_relinquished
    assert execution["timed_out"] is True
    assert report["failure_classification"] == "timeout"
    assert report["review_only"] is True and report["player_completion"] is False


def test_unverified_process_termination_never_claims_input_stopped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StuckProcess:
        pid = 424243

        @staticmethod
        def poll() -> None:
            return None

        @staticmethod
        def wait(timeout: float | None = None) -> int:
            raise TimeoutError("still running")

    controller = ShowProcessController()
    controller.attach(StuckProcess())  # type: ignore[arg-type]
    monkeypatch.setattr("smb3_agent.show.os.killpg", lambda pid, sig: None)
    monkeypatch.setattr(
        "smb3_agent.show.subprocess.TimeoutExpired", TimeoutError
    )

    with pytest.raises(ShowError, match="did not stop"):
        controller.request_stop()
    assert not controller.input_stopped.is_set()


def test_lifecycle_invalid_transition_fails_closed(tmp_path: Path) -> None:
    definition = load_show_definition()
    session = ShowSession("s", _request(tmp_path), definition, cues=definition.cues)
    with pytest.raises(ShowError, match="invalid Show lifecycle"):
        session.transition(ShowLifecycle.DEMONSTRATED)


def _blocking_runner(request: ShowRequest, definition: object, artifacts: Path, controller: ShowProcessController, progress: object) -> ShowOutcome:
    artifacts.mkdir(parents=True)
    (artifacts / "partial.log").write_text("partial")
    getattr(progress, "__call__")("runner active")
    assert controller.stop_requested.wait(3)
    controller.mark_natural_stop()
    return ShowOutcome(
        False, input_stopped=True, process_relinquished=True,
        explanation="Stopped; your game was not advanced.",
    )


def _wait_terminal(manager: ShowSessionManager) -> ShowSession:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        session = manager.snapshot()
        if session is not None and session.lifecycle in {ShowLifecycle.CANCELLED, ShowLifecycle.TAKEN_OVER, ShowLifecycle.FAILED, ShowLifecycle.DEMONSTRATED}:
            return session
        time.sleep(0.01)
    raise AssertionError("Show session did not finish")


def test_conflicting_start_rejected_and_stop_reaches_owned_runner(tmp_path: Path) -> None:
    manager = ShowSessionManager(runner=_blocking_runner, artifacts_root=tmp_path / "show")
    manager.start(_request(tmp_path))
    with pytest.raises(ShowError, match="already active"):
        manager.start(_request(tmp_path))
    stopped = manager.stop()
    assert stopped.lifecycle is ShowLifecycle.STOP_REQUESTED
    terminal = _wait_terminal(manager)
    assert terminal.lifecycle is ShowLifecycle.CANCELLED
    assert terminal.control_returned
    assert (terminal.artifacts_dir / "partial.log").is_file()  # type: ignore[operator]


def test_takeover_stops_input_and_records_control_return(tmp_path: Path) -> None:
    manager = ShowSessionManager(runner=_blocking_runner, artifacts_root=tmp_path / "show")
    manager.start(_request(tmp_path))
    manager.stop(takeover=True)
    terminal = _wait_terminal(manager)
    assert terminal.lifecycle is ShowLifecycle.TAKEN_OVER
    assert terminal.outcome is not None and terminal.outcome.input_stopped
    assert not terminal.outcome.demonstration_game_owned_success


def test_unexpected_exception_retains_traceback_and_policy_report(tmp_path: Path) -> None:
    def broken(request: ShowRequest, definition: object, artifacts: Path, controller: ShowProcessController, progress: object) -> ShowOutcome:
        raise RuntimeError("boom")
    manager = ShowSessionManager(runner=broken, artifacts_root=tmp_path / "show")
    manager.start(_request(tmp_path))
    terminal = _wait_terminal(manager)
    assert terminal.lifecycle is ShowLifecycle.FAILED
    assert "RuntimeError: boom" in (terminal.error or "")
    report = yaml.safe_load((terminal.artifacts_dir / "show_report.json").read_text())  # type: ignore[operator]
    assert report["review_only"] is True
    assert report["promotable"] is False
    assert (terminal.artifacts_dir / "failure_traceback.txt").is_file()  # type: ignore[operator]


def test_http_server_remains_responsive_during_active_show(tmp_path: Path) -> None:
    server = _new_lab_ui_server("127.0.0.1", 0)
    manager = ShowSessionManager(runner=_blocking_runner, artifacts_root=tmp_path / "show")
    setattr(server, "show_manager", manager)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    manager.start(_request(tmp_path))
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        connection.request("GET", "/mario")
        response = connection.getresponse()
        html = response.read().decode()
        connection.close()
        assert response.status == 200
        assert 'data-testid="show-session"' in html
    finally:
        manager.stop()
        _wait_terminal(manager)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_ui_renders_show_scope_controls_cues_and_truthful_outcome(tmp_path: Path) -> None:
    request = _request(tmp_path)
    definition = load_show_definition()
    outcome = ShowOutcome(False, input_stopped=True, process_relinquished=True, explanation="Stopped. Your game was not advanced.")
    session = ShowSession("s", request, definition, ShowLifecycle.TAKEN_OVER, definition.cues, activity=("Take Control requested.",), outcome=outcome, control_returned=True)
    html = render_companion_ui(default_companion_session(), show_session=session, show_request=request)
    for hook in ("show-session", "show-scope", "show-cues", "current-show-cue", "show-activity", "show-start", "show-stop", "show-outcome", "show-replay"):
        assert f'data-testid="{hook}"' in html
    assert "Your game is unchanged" in html
    assert "Player completion: No" in html
    assert 'data-testid="mode-do" data-available="false"' in html
    assert 'data-testid="tell-request"' in html


def test_default_ui_keeps_show_unavailable_without_game_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMB3_GAME_FILE", raising=False)
    html = render_companion_ui(default_companion_session())
    assert 'data-testid="mode-show" data-available="false"' in html
    assert "configured game file" in html
    assert "Open Game Companion Lab" in html
