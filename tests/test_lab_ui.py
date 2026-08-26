from __future__ import annotations

import http.client
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from smb3_agent.fceux_harness import AttemptSummary, BatchSummary
from smb3_agent.companion_session import (
    AdapterIdentity,
    CompanionSession,
    CompanionSessionError,
    Freshness,
    GoalIdentity,
    ModeCapability,
    Observation,
    SafetyBoundary,
    SessionLifecycle,
    SessionOutcome,
)
from smb3_agent.goals import GoalRunResult, load_goal_contract
from smb3_agent.lab import add_batch_notes_to_latest, build_issue_ledger_latest, start_session
from smb3_agent.lab_ui import (
    _Handler,
    _configured_game_path,
    _lab_ui_url,
    _location_url,
    _new_lab_ui_server,
    _selected_location,
    _update_issue_latest,
    _update_observation_latest,
    build_control_panel_summary,
    default_companion_session,
    render_companion_ui,
    render_lab_ui,
    run_lab_ui_server,
)


def test_server_routes_player_shell_and_secondary_lab() -> None:
    server = _new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request("GET", "/")
        catalog_response = connection.getresponse()
        catalog = catalog_response.read().decode("utf-8")
        connection.close()

        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request("GET", "/mario")
        player_response = connection.getresponse()
        player = player_response.read().decode("utf-8")
        connection.close()

        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request("GET", "/assets/player-workspace.js")
        script_response = connection.getresponse()
        script = script_response.read().decode("utf-8")
        script_content_type = script_response.getheader("Content-Type")
        connection.close()

        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request("GET", "/lab")
        lab_response = connection.getresponse()
        lab = lab_response.read().decode("utf-8")
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert catalog_response.status == 200
    assert 'data-testid="combined-companion-catalog"' in catalog
    assert 'data-adapter-id="smb3"' in catalog
    assert 'data-adapter-id="stardew"' in catalog
    assert player_response.status == 200
    assert 'data-testid="companion-shell"' in player
    assert "Open Game Companion Lab" in player
    assert '<script src="/assets/player-workspace.js" defer></script>' in player
    assert script_response.status == 200
    assert script_content_type == "text/javascript; charset=utf-8"
    assert 'fetch("/api/player-workspace"' in script
    assert "event.preventDefault()" in script
    assert "window.setInterval" in script
    assert "live-action-error" in script
    assert "if (!response.ok)" in script
    assert lab_response.status == 200
    assert "Game Companion Lab" in lab
    assert "Run World 8 Route" in lab


def test_server_catalog_switch_invalidates_mario_volatile_presentation_state(
    tmp_path: Path,
) -> None:
    server = _new_lab_ui_server("127.0.0.1", 0)
    try:
        catalog = getattr(server, "catalog_session")
        catalog.store.path = tmp_path / "catalog-preferences.json"
        catalog.switch_event_path = tmp_path / "catalog-switch-events.jsonl"
        catalog.preferences.selected_adapter_id = None
        catalog.preferences.display = {}
        catalog.preferences.adapters = {}
        objective = getattr(server, "objective_session_manager")
        objective.profile_id = "smb3.world-1-1.fastest-accepted-clear"
        objective.reference_id = "accepted-world-1-1"
        catalog.select_initial("smb3")
        event = catalog.switch("stardew")
        assert event.new_observation_required is True
        assert objective.profile_id is None
        assert objective.reference_id is None
        assert getattr(server, "live_observation_manager").snapshot().session_id is None
        assert getattr(server, "show_manager").snapshot() is None
    finally:
        server.server_close()


def test_player_start_rejects_unsupported_repo_local_game_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SMB3_GAME_FILE", raising=False)
    local_game = tmp_path / "roms" / "smb3.nes"
    local_game.parent.mkdir()
    local_game.write_bytes(b"local fixture")

    assert _configured_game_path() is None


def test_default_player_shell_is_truthful_and_semantic() -> None:
    html = render_companion_ui(default_companion_session())

    for hook in (
        "companion-shell",
        "game-identity",
        "observed-state",
        "mode-tell",
        "mode-show",
        "mode-do",
        "protected-decisions",
        "stop-point",
        "activity",
        "take-control",
        "handoff",
        "lab-navigation",
        "tell-request",
        "spoiler-selection",
        "observation-source",
        "tell-unavailable-reason",
    ):
        assert f'data-testid="{hook}"' in html
    assert "Unknown — refresh required" in html
    assert 'data-testid="mode-do" data-available="false"' in html
    assert "No game-owned outcome" in html
    assert "@media (max-width: 760px)" in html


def test_player_reported_tell_post_renders_grounded_card_and_keeps_show_do_unavailable() -> None:
    server = _new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = (
            f"csrf_token={getattr(server, 'csrf_token')}"
            "&goal_id=world_8_finish_game"
            "&checkpoint_id=world_8_bowser_castle_finish"
            "&spoiler_level=guided&checkpoint_confirmed=true"
        )
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request(
            "POST",
            "/tell",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = connection.getresponse()
        html = response.read().decode("utf-8")
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 200
    for hook in (
        "tell-card",
        "tell-step",
        "expected-cue",
        "risk-warning",
        "recovery-guidance",
        "protected-decision-acknowledgement",
        "provenance-reference",
        "uncertainty",
        "refresh-requirement",
    ):
        assert f'data-testid="{hook}"' in html
    assert "Player Reported" in html
    assert 'data-testid="mode-tell" data-available="true"' in html
    assert 'data-testid="mode-show" data-available="false"' in html
    assert 'data-testid="mode-do" data-available="false"' in html
    assert "no game input was sent" in html


def test_player_tell_rejects_unconfirmed_and_protected_conflict_without_traceback() -> None:
    server = _new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = (
            f"csrf_token={getattr(server, 'csrf_token')}"
            "&goal_id=world_8_finish_game"
            "&checkpoint_id=world_8_battleships_clear"
            "&spoiler_level=guided&checkpoint_confirmed=true"
            "&p_wing_available=true"
            "&protected_decisions=preserve_p_wing"
        )
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("POST", "/tell", body=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
        response = connection.getresponse()
        html = response.read().decode("utf-8")
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 400
    assert "protected decision conflicts" in html
    assert "Traceback" not in html
    assert 'data-testid="tell-unavailable-reason"' in html


def test_checkpoint_options_come_from_selected_goal_contract() -> None:
    html = render_companion_ui(default_companion_session("world_8_double_whistle"))
    goal = load_goal_contract(Path("data/goals/world_8_double_whistle.yaml"))

    assert html.count('<option value="') >= len(goal.segments) + 3
    assert 'value="world_8_map_arrival"' in html
    assert 'value="world_8_bowser_castle_finish"' not in html
    assert 'data-testid="observed-facts"' in html


def test_player_tell_missing_inventory_fact_fails_closed() -> None:
    data = {
        "goal_id": ["world_8_finish_game"],
        "checkpoint_id": ["world_8_battleships_clear"],
        "spoiler_level": ["guided"],
        "checkpoint_confirmed": ["true"],
    }
    with pytest.raises(ValueError, match="p_wing_available"):
        from smb3_agent.lab_ui import _player_tell_from_form

        _player_tell_from_form(data)


def test_known_checkpoint_renders_capabilities_and_unavailable_reason() -> None:
    session = _companion_fixture(
        modes=(
            _mode("tell"),
            _mode("show"),
            _mode("do", available=False, reason="Do is not proven for this checkpoint."),
        )
    )

    html = render_companion_ui(session)

    assert "World 8 map at Bowser&#x27;s Castle" in html
    assert 'data-testid="mode-tell" data-available="true"' in html
    assert 'data-testid="mode-show" data-available="true"' in html
    assert 'data-testid="mode-do" data-available="false"' in html
    assert "Do is not proven for this checkpoint." in html


def test_unknown_or_stale_observation_rejects_execution_capability() -> None:
    stale_observation = Observation(
        checkpoint="World 8 map",
        observed_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        freshness=Freshness.STALE,
        confidence=0.9,
    )
    safe_stale = _companion_fixture(
        observation=stale_observation,
        modes=(
            _mode("tell"),
            _mode("show", available=False, reason="Refresh required."),
            _mode("do", available=False, reason="Refresh required."),
        ),
    )
    html = render_companion_ui(safe_stale)
    assert 'data-testid="mode-show" data-available="false"' in html
    assert 'data-testid="mode-do" data-available="false"' in html

    unsafe_stale = _companion_fixture(
        observation=stale_observation,
        modes=(_mode("tell"), _mode("show"), _mode("do")),
    )

    with pytest.raises(CompanionSessionError, match="Show and Do"):
        render_companion_ui(unsafe_stale)


def test_take_control_is_idle_disabled_and_active_enabled() -> None:
    idle_html = render_companion_ui(_companion_fixture())
    active_html = render_companion_ui(
        _companion_fixture(lifecycle=SessionLifecycle.ACTIVE)
    )

    assert 'data-testid="take-control" disabled' in idle_html
    assert 'data-testid="take-control" disabled' not in active_html
    assert 'data-session-state="active"' in active_html


@pytest.mark.parametrize(
    "lifecycle",
    (
        SessionLifecycle.FAILED,
        SessionLifecycle.CANCELLED,
        SessionLifecycle.TAKEN_OVER,
    ),
)
def test_terminal_handoffs_render_distinctly(lifecycle: SessionLifecycle) -> None:
    html = render_companion_ui(
        _companion_fixture(
            lifecycle=lifecycle,
            outcome=_outcome(game_owned=False),
            input_stopped=True,
            control_returned=True,
        )
    )

    assert f'data-session-state="{lifecycle.value}"' in html
    assert f"state-{lifecycle.value}" in html
    assert "Attempted the bounded section" in html


def test_completed_handoff_requires_game_owned_outcome_and_safe_handback() -> None:
    base = dict(
        lifecycle=SessionLifecycle.COMPLETED,
        outcome=_outcome(),
        input_stopped=True,
        control_returned=True,
    )
    completed = render_companion_ui(_companion_fixture(**base))
    assert 'data-session-state="completed"' in completed
    assert "Verified game-owned checkpoint" in completed

    with pytest.raises(CompanionSessionError, match="game-owned outcome"):
        render_companion_ui(
            _companion_fixture(**{**base, "outcome": _outcome(game_owned=False)})
        )
    with pytest.raises(CompanionSessionError, match="input to be stopped"):
        render_companion_ui(_companion_fixture(**{**base, "input_stopped": False}))
    with pytest.raises(CompanionSessionError, match="control to be returned"):
        render_companion_ui(_companion_fixture(**{**base, "control_returned": False}))
    with pytest.raises(CompanionSessionError, match="known final observation"):
        render_companion_ui(
            _companion_fixture(
                **{
                    **base,
                    "outcome": _outcome(
                        final_observation=Observation(
                            checkpoint=None,
                            observed_at=None,
                            freshness=Freshness.UNKNOWN,
                            confidence=None,
                        )
                    ),
                }
            )
        )


def _mode(mode: str, available: bool = True, reason: str | None = None) -> ModeCapability:
    return ModeCapability(mode, available, f"{mode.title()} explanation.", reason)


def _known_observation() -> Observation:
    return Observation(
        checkpoint="World 8 map at Bowser's Castle",
        observed_at=datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
        freshness=Freshness.FRESH,
        confidence=0.98,
        evidence_references=("evidence/start.png",),
    )


def _outcome(
    *,
    game_owned: bool = True,
    final_observation: Observation | None = None,
) -> SessionOutcome:
    return SessionOutcome(
        game_owned=game_owned,
        attempted="Attempted the bounded section.",
        changed="Mario reached the declared checkpoint.",
        resources_consumed="No items consumed.",
        verified_outcome="Verified game-owned checkpoint.",
        unresolved_uncertainty="None.",
        final_observation=final_observation or _known_observation(),
        evidence_references=("evidence/final.png",),
    )


def _companion_fixture(
    *,
    observation: Observation | None = None,
    modes: tuple[ModeCapability, ...] | None = None,
    lifecycle: SessionLifecycle = SessionLifecycle.IDLE,
    outcome: SessionOutcome | None = None,
    input_stopped: bool = False,
    control_returned: bool = False,
) -> CompanionSession:
    return CompanionSession(
        adapter=AdapterIdentity("smb3", "Super Mario Bros. 3", "Mario adapter", "Ready"),
        goal=GoalIdentity("world_8_finish_game", "Finish game", "Reach the stable ending."),
        observation=observation or _known_observation(),
        modes=modes or (_mode("tell"), _mode("show"), _mode("do")),
        safety=SafetyBoundary(
            authorized=True,
            stop_point="Stable game-owned ending",
            protected_decisions=("No route bypass",),
            recovery_boundary="Stop on mismatch.",
        ),
        lifecycle=lifecycle,
        activity=("Observation verified.",),
        outcome=outcome,
        input_stopped=input_stopped,
        control_returned=control_returned,
    )


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", "http://127.0.0.1:8765"),
        ("localhost", "http://localhost:8765"),
        ("::1", "http://[::1]:8765"),
    ],
)
def test_route_lab_formats_loopback_urls(host: str, expected: str) -> None:
    assert _lab_ui_url(host, 8765) == expected


def test_route_lab_refuses_non_loopback_bind() -> None:
    with pytest.raises(ValueError, match="may bind only"):
        run_lab_ui_server(host="0.0.0.0", port=0)


def test_route_lab_rejects_malformed_form_and_logs_client_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = _new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with caplog.at_level(logging.WARNING, logger="smb3_agent.lab_ui"):
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=5
            )
            connection.putrequest("POST", "/notes")
            connection.putheader("Content-Length", "invalid")
            connection.endheaders()
            response = connection.getresponse()
            body = response.read().decode("utf-8")
            connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 400
    assert "Invalid Content-Length header" in body
    assert "route_lab_request_failed" in caplog.text
    assert "error_type=LabUiError" in caplog.text


def test_route_lab_returns_generic_500_and_logs_unexpected_traceback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def crash(_handler: _Handler) -> None:
        raise RuntimeError("private unexpected detail")

    monkeypatch.setattr(_Handler, "_handle_get", crash)
    server = _new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with caplog.at_level(logging.ERROR, logger="smb3_agent.lab_ui"):
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=5
            )
            connection.request("GET", "/")
            response = connection.getresponse()
            body = response.read().decode("utf-8")
            connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 500
    assert "Unexpected Game Companion Lab failure" in body
    assert "private unexpected detail" not in body
    assert "RuntimeError: private unexpected detail" in caplog.text


def test_route_lab_rejects_untrusted_host_and_missing_csrf() -> None:
    server = _new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.putrequest("GET", "/api/summary", skip_host=True)
        connection.putheader("Host", "attacker.example")
        connection.endheaders()
        host_response = connection.getresponse()
        host_response.read()
        connection.close()

        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request(
            "POST",
            "/refresh",
            body="",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        csrf_response = connection.getresponse()
        csrf_body = csrf_response.read().decode("utf-8")
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert host_response.status == 403
    assert csrf_response.status == 403
    assert "Invalid or missing Game Companion Lab CSRF token" in csrf_body


def test_route_lab_sets_security_headers_and_renders_csrf_token() -> None:
    csrf_token = "fixed-test-csrf-token"
    html = render_lab_ui(csrf_token=csrf_token)

    post_forms = html.count('<form method="post"')
    assert post_forms >= 1
    assert html.count(f'name="csrf_token" value="{csrf_token}"') == post_forms

    server = _new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request("GET", "/api/summary")
        response = connection.getresponse()
        response.read()
        headers = dict(response.getheaders())
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 200
    assert headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert "connect-src 'self'" in headers["Content-Security-Policy"]
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"


def test_route_lab_rejects_wrong_content_type() -> None:
    server = _new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request(
            "POST",
            "/refresh",
            body='{"csrf_token":"unused"}',
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 415
    assert "application/x-www-form-urlencoded" in body


def test_route_lab_rejects_overlapping_state_change() -> None:
    server = _new_lab_ui_server("127.0.0.1", 0)
    action_lock = getattr(server, "action_lock")
    action_lock.acquire()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request(
            "POST",
            "/refresh",
            body=f"csrf_token={getattr(server, 'csrf_token')}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        connection.close()
    finally:
        action_lock.release()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 409
    assert "Another Game Companion Lab action is already running" in body


def test_route_lab_serves_html_as_text_and_blocks_unsafe_artifact_type(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    artifacts.joinpath("report.html").write_text("<script>alert(1)</script>")
    artifacts.joinpath("unsafe.svg").write_text("<svg></svg>")
    server = _new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request("GET", "/artifacts/report.html")
        html_response = connection.getresponse()
        html_response.read()
        html_content_type = html_response.getheader("Content-Type")
        connection.close()

        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request("GET", "/artifacts/unsafe.svg")
        svg_response = connection.getresponse()
        svg_response.read()
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert html_response.status == 200
    assert html_content_type == "text/plain; charset=utf-8"
    assert svg_response.status == 404


def test_route_lab_rejects_oversized_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("smb3_agent.lab_ui.MAX_SERVED_FILE_BYTES", 4)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    artifacts.joinpath("large.log").write_text("12345")
    server = _new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request("GET", "/artifacts/large.log")
        response = connection.getresponse()
        response.read()
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 413


def test_location_url_percent_encodes_untrusted_parameters() -> None:
    location = _location_url("route\r\nInjected: value", issue_id="issue/one")

    assert "\r" not in location
    assert "\n" not in location
    assert "%0D%0A" in location
    assert "issue%2Fone" in location


def test_route_lab_renders_route_evidence_and_teaching_workflow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _prepare_ui_lab(monkeypatch, tmp_path)
    start_session(
        "show me the route at 4x",
        game_path=tmp_path / "local-game-file",
        attempts=1,
        artifacts_root=tmp_path / "artifacts/sessions",
    )
    add_batch_notes_to_latest(
        [{"segment_id": "world_1_1", "text": "1-1 falls into hole.", "severity": "harden"}]
    )
    build_issue_ledger_latest()

    html = render_lab_ui()

    assert "Game Companion Lab" in html
    assert "Mario adapter" in html
    assert "Run World 8 Route" in html
    assert "World 2-first double-whistle route to World 8" in html
    assert "Route" in html
    assert "Evidence" in html
    assert "Help &amp; Learn" in html
    assert "Active Problems" in html
    assert "Observation History" in html
    assert "Fix Issue" in html
    assert "No screenshot captured yet" in html
    assert "Mark Resolved" in html
    assert "Needs Rerun" in html
    assert "Create Codex Task" in html
    assert "V2.14 readiness" in html
    assert "Implementation blockers" in html
    assert "Candidate blockers" in html
    assert "Campaign entry" in html
    assert "Campaign complete" in html
    assert "1-1" in html
    assert "1-3" in html
    assert "Fortress" in html
    assert "Airship / King" in html
    assert "King" in html
    assert "World 2 Map" in html
    assert "World 8 Map" in html
    assert "1-4" not in html
    assert "Unit Tests" in html
    assert "Phase Gate" in html
    assert 'href="/lab?location=world_1_fortress"' in html
    assert html.count('class="primary-button"') == 1
    assert "secondary-button" in html
    assert "segmented-control" in html
    assert "segment-active" in html
    assert "route-item-selected" in html
    assert "status-failed" in html
    assert "status-learned" in html
    assert "status-validation" in html
    assert html.count("Mark Resolved") == 1
    assert html.count("Needs Rerun") == 1
    assert html.count("Create Codex Task") == 1
    assert "issue-summary-row" in html
    assert "observation-summary-row" in html
    assert "World 1 Control Panel" not in html
    assert "World 1 Mission Control" not in html
    assert "Run Controls" not in html
    assert "World 1 Notes" not in html
    assert "Route Health" not in html
    assert "Teach This Section" not in html
    assert "Things Mario Still Gets Wrong" not in html
    assert "World 1-3 Whistle" not in html
    assert "World 1 Fortress Whistle" not in html

    notes_html = render_lab_ui(selected_location_id="world_1_1", selected_mode="notes")
    assert "Convert to Issue" in notes_html
    assert notes_html.count("Convert to Issue") == 1
    assert "detail-panel observation-detail" in notes_html

    add_html = render_lab_ui(selected_location_id="world_1_1", selected_mode="add")
    assert 'name="note__world_1_1"' in add_html
    assert add_html.count('name="note__') == 1
    assert "Add Observation" in add_html


def test_control_panel_groups_notes_by_human_location(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _prepare_ui_lab(monkeypatch, tmp_path)
    start_session(
        "show me the route at 4x",
        game_path=tmp_path / "local-game-file",
        attempts=1,
        artifacts_root=tmp_path / "artifacts/sessions",
    )
    add_batch_notes_to_latest(
        [
            {
                "segment_id": "world_1_1",
                "text": "1-1 falls into hole at 283 on clock.",
                "severity": "harden",
            },
            {
                "segment_id": "world_1_fortress",
                "text": "Fortress needs Raccoon flight, not fire form.",
                "severity": "guide_detail",
            },
        ]
    )
    build_issue_ledger_latest()

    summary = build_control_panel_summary()
    locations = {location["id"]: location for location in summary["locations"]}

    assert locations["world_1_1"]["notes"] == 1
    assert locations["world_1_1"]["open_issues"] == 1
    assert locations["world_1_fortress"]["notes"] == 1
    assert locations["world_1_fortress"]["issues"] == 0
    assert locations["world_1_fortress"]["open_issues"] == 0
    assert summary["totals"]["notes"] == 2


def test_route_lab_defaults_to_first_open_issue_location(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _prepare_ui_lab(monkeypatch, tmp_path)
    start_session(
        "show me the route at 4x",
        game_path=tmp_path / "local-game-file",
        attempts=1,
        artifacts_root=tmp_path / "artifacts/sessions",
    )
    add_batch_notes_to_latest(
        [{"segment_id": "world_1_1", "text": "1-1 falls into hole.", "severity": "harden"}]
    )
    build_issue_ledger_latest()

    summary = build_control_panel_summary()
    selected = _selected_location(summary["locations"])

    assert selected["id"] == "world_1_1"


def test_route_lab_uses_active_goal_contract_order() -> None:
    contract = load_goal_contract(Path("data/goals/world_8_double_whistle.yaml"))

    summary = build_control_panel_summary()
    displayed_segments = tuple(str(location["segment_id"]) for location in summary["locations"])
    labels = tuple(str(location["label"]) for location in summary["locations"])

    assert summary["goal_id"] == "world_8_double_whistle"
    assert displayed_segments == contract.segments
    assert "1-4" not in labels
    assert "World 2 Map" in labels
    assert "World 8 Map" in labels


def test_route_lab_surfaces_big_tanks_without_changing_the_default_goal() -> None:
    default = build_control_panel_summary()
    big_tanks = build_control_panel_summary("world_8_big_tanks")
    html = render_lab_ui(goal_id="world_8_big_tanks")

    assert default["goal_id"] == "world_8_double_whistle"
    assert len(default["locations"]) == 15
    assert big_tanks["goal_id"] == "world_8_big_tanks"
    assert len(big_tanks["locations"]) == 16
    assert big_tanks["locations"][-1]["label"] == "World 8 Big Tanks"
    assert "World 8 Big Tanks" in html
    assert 'href="/lab?goal=world_8_big_tanks&amp;location=world_8_big_tanks"' in html
    assert "World 2-first double-whistle route through World 8 Big Tanks" in html


def test_route_lab_renders_and_switches_to_battleships() -> None:
    default = build_control_panel_summary()
    big_tanks = build_control_panel_summary("world_8_big_tanks")
    battleships = build_control_panel_summary("world_8_battleships")
    html = render_lab_ui(goal_id="world_8_battleships")

    assert len(default["locations"]) == 15
    assert len(big_tanks["locations"]) == 16
    assert battleships["goal_id"] == "world_8_battleships"
    assert len(battleships["locations"]) == 17
    assert battleships["locations"][-1]["label"] == "World 8-Battleships"
    assert 'href="/lab?goal=world_8_battleships&amp;location=world_8_battleships"' in html
    assert "World 2-first double-whistle route through World 8-Battleships" in html


def test_route_lab_renders_exactly_21_hand_traps_jet_locations() -> None:
    summary = build_control_panel_summary("world_8_hand_traps_jet")
    html = render_lab_ui(goal_id="world_8_hand_traps_jet")

    assert summary["goal_id"] == "world_8_hand_traps_jet"
    assert len(summary["locations"]) == 21
    assert [location["id"] for location in summary["locations"][-4:]] == [
        "world_8_hand_trap_right",
        "world_8_hand_trap_center",
        "world_8_hand_trap_left",
        "world_8_jet",
    ]
    assert "World 8 Right Hand Trap" in html
    assert "World 8 Center Hand Trap" in html
    assert "World 8 Left Hand Trap" in html
    assert "World 8-Jet" in html
    assert 'href="/lab?goal=world_8_hand_traps_jet&amp;location=world_8_jet"' in html


def test_route_lab_renders_and_switches_to_exactly_23_world_8_8_2_locations() -> None:
    summary = build_control_panel_summary("world_8_8_2")
    html = render_lab_ui(goal_id="world_8_8_2")

    assert summary["goal_id"] == "world_8_8_2"
    assert len(summary["locations"]) == 23
    assert [location["id"] for location in summary["locations"][-2:]] == [
        "world_8_1",
        "world_8_2",
    ]
    assert "World 8-1" in html
    assert "World 8-2" in html
    assert "World 2-first double-whistle route through World 8-2 and Fortress access" in html
    assert 'href="/lab?goal=world_8_8_2&amp;location=world_8_2"' in html


def test_route_lab_renders_exactly_25_world_8_super_tanks_locations() -> None:
    summary = build_control_panel_summary("world_8_super_tanks")
    html = render_lab_ui(goal_id="world_8_super_tanks")

    assert summary["goal_id"] == "world_8_super_tanks"
    assert len(summary["locations"]) == 25
    assert [location["id"] for location in summary["locations"][-2:]] == [
        "world_8_fortress",
        "world_8_super_tanks",
    ]
    assert "World 8-Fortress" in html
    assert "World 8-Super Tanks" in html
    assert "through Super Tanks and Bowser&#x27;s Castle access" in html
    assert (
        'href="/lab?goal=world_8_super_tanks&amp;location=world_8_super_tanks"'
        in html
    )


def test_route_lab_renders_exactly_26_finish_game_locations() -> None:
    summary = build_control_panel_summary("world_8_finish_game")
    html = render_lab_ui(goal_id="world_8_finish_game")

    assert summary["goal_id"] == "world_8_finish_game"
    assert len(summary["locations"]) == 26
    assert summary["locations"][-1]["id"] == "world_8_bowser_castle"
    assert "World 8-Bowser&#x27;s Castle and Ending" in html
    assert "Princess rescue, credits, and ending" in html
    assert (
        'href="/lab?goal=world_8_finish_game&amp;location=world_8_bowser_castle"'
        in html
    )


def test_observation_lifecycle_delete_and_resolve(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _prepare_ui_lab(monkeypatch, tmp_path)
    start_session(
        "show me the route at 4x",
        game_path=tmp_path / "local-game-file",
        attempts=1,
        artifacts_root=tmp_path / "artifacts/sessions",
    )
    add_batch_notes_to_latest(
        [
            {"segment_id": "world_1_1", "text": "delete me", "severity": "harden"},
            {"segment_id": "world_1_fortress", "text": "resolve me", "severity": "harden"},
        ]
    )
    build_issue_ledger_latest()

    _update_observation_latest("note_001", "delete", {})
    _update_observation_latest("note_002", "resolved", {})

    notes = yaml.safe_load(_latest_session_file("notes.yaml").read_text())["notes"]
    issues = yaml.safe_load(_latest_session_file("issues.yaml").read_text())["issues"]

    assert [note["id"] for note in notes] == ["note_002"]
    assert notes[0]["ui_state"] == "resolved"
    assert all("note_001" not in issue.get("source_notes", []) for issue in issues)
    assert any(issue["status"] == "resolved" for issue in issues)


def test_issue_lifecycle_resolved_and_expected_behavior(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _prepare_ui_lab(monkeypatch, tmp_path)
    start_session(
        "show me the route at 4x",
        game_path=tmp_path / "local-game-file",
        attempts=1,
        artifacts_root=tmp_path / "artifacts/sessions",
    )
    add_batch_notes_to_latest(
        [
            {"segment_id": "world_1_1", "text": "1-1 falls into hole.", "severity": "harden"},
            {"segment_id": "world_1_fortress", "text": "Fortress fails.", "severity": "bug"},
        ]
    )
    build_issue_ledger_latest()

    issues = yaml.safe_load(_latest_session_file("issues.yaml").read_text())["issues"]
    first_issue_id = issues[0]["id"]
    second_issue_id = issues[1]["id"]

    _update_issue_latest(first_issue_id, "resolved")
    _update_issue_latest(second_issue_id, "expected_behavior")

    updated = {issue["id"]: issue for issue in yaml.safe_load(_latest_session_file("issues.yaml").read_text())["issues"]}
    assert updated[first_issue_id]["status"] == "resolved"
    assert updated[first_issue_id]["actionable"] is False
    assert updated[second_issue_id]["status"] == "accepted"
    assert updated[second_issue_id]["type"] == "expected_behavior"
    assert updated[second_issue_id]["actionable"] is False


def _prepare_ui_lab(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    tmp_path.joinpath("data/worlds").mkdir(parents=True)
    tmp_path.joinpath("data/segments").mkdir(parents=True)
    tmp_path.joinpath("artifacts/sessions").mkdir(parents=True)
    tmp_path.joinpath("local-game-file").write_text("placeholder")
    tmp_path.joinpath("data/worlds/world_1_locations.yaml").write_text(
        yaml.safe_dump(
            {
                "world": 1,
                "name": "Grass Land",
                "locations": [
                    {
                        "id": "world_1_1",
                        "segment_id": "world_1_1_clear",
                        "label": "1-1",
                        "default_status": "works",
                        "objective": "Clear the level.",
                    },
                    {
                        "id": "world_1_3",
                        "segment_id": "world_1_3_whistle",
                        "label": "1-3",
                        "default_status": "works",
                        "objective": "Get the hidden item route.",
                    },
                    {
                        "id": "world_1_fortress",
                        "segment_id": "world_1_fortress_whistle",
                        "label": "Fortress",
                        "default_status": "blocked",
                        "objective": "Use flight above the ceiling.",
                    },
                    {
                        "id": "world_1_airship",
                        "segment_id": "world_1_airship_to_king",
                        "label": "Airship / King",
                        "default_status": "needs review",
                        "objective": "Complete the moving stage.",
                    },
                    {
                        "id": "world_2_map",
                        "segment_id": "world_2_map_arrival_with_two_whistles",
                        "label": "World 2 Map",
                        "default_status": "blocked",
                        "objective": "Arrive with both whistles.",
                    },
                    {
                        "id": "world_8_map",
                        "segment_id": "world_8_map_arrival",
                        "label": "World 8 Map",
                        "default_status": "blocked",
                        "objective": "Confirm genuine World 8 arrival.",
                    },
                ],
            }
        )
    )
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
    route_steps = (
        SimpleNamespace(id="world_1_1_clear", classification="game_prerequisite", execution_mode="normal_gameplay"),
        SimpleNamespace(id="world_1_3_whistle", classification="objective_milestone", execution_mode="normal_gameplay"),
        SimpleNamespace(id="world_1_fortress_whistle", classification="objective_milestone", execution_mode="normal_gameplay"),
        SimpleNamespace(id="world_1_airship_to_king", classification="game_prerequisite", execution_mode="planned"),
        SimpleNamespace(id="world_2_map_arrival_with_two_whistles", classification="objective_milestone", execution_mode="planned"),
        SimpleNamespace(id="world_8_map_arrival", classification="objective_milestone", execution_mode="planned"),
    )
    fake_contract = SimpleNamespace(
        id="world_8_double_whistle",
        display_name="World 8 Arrival",
        display_subtitle="World 2-first double-whistle route to World 8",
        catalog_path=Path("data/segments/world_8_double_whistle.yaml"),
        segments=tuple(step.id for step in route_steps),
        route_steps=route_steps,
        goal_type="product_goal",
        execution_status="planned",
        objective={"target": "world_8_map_arrival"},
    )
    fake_catalog = SimpleNamespace(
        by_id={
            "world_1_1_clear": SimpleNamespace(status="solved"),
            "world_1_3_whistle": SimpleNamespace(status="solved"),
            "world_1_fortress_whistle": SimpleNamespace(status="bridged"),
            "world_1_airship_to_king": SimpleNamespace(status="bridged"),
            "world_2_map_arrival_with_two_whistles": SimpleNamespace(status="planned"),
            "world_8_map_arrival": SimpleNamespace(status="planned"),
        }
    )
    monkeypatch.setattr("smb3_agent.lab_ui.load_goal_contract", lambda path: fake_contract)
    monkeypatch.setattr(
        "smb3_agent.lab_ui.load_product_goal_contracts",
        lambda: (fake_contract,),
    )
    monkeypatch.setattr("smb3_agent.lab_ui.resolve_goal_path", lambda goal: Path(f"data/goals/{goal}.yaml"))
    monkeypatch.setattr("smb3_agent.lab_ui.load_segment_catalog", lambda path: fake_catalog)


def _latest_session_file(name: str) -> Path:
    session_dir = Path("artifacts/sessions/latest.txt").read_text().strip()
    return Path(session_dir) / name


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
    artifacts_dir.joinpath("fceux_1_1.log").write_text(
        "\n".join(
            [
                "frame=10 event=attempt_1_start x=24 y=384",
                "frame=50 event=attempt_1_success_course_clear x=8192 y=0",
                "frame=80 event=post_probe_1_airship_success_king x=432 y=4192",
            ]
        )
    )
    return GoalRunResult(
        contract=contract,
        summary=BatchSummary(
            attempts=(
                AttemptSummary(
                    attempt=1,
                    success=True,
                    bad_state=False,
                    reached_end=True,
                    goal_area=True,
                    max_x=2848,
                ),
            ),
            post_probe_last_event="post_probe_1_airship_success_king",
            post_probe_clear=True,
        ),
        artifacts_dir=artifacts_dir,
        metrics_passed=True,
    )
