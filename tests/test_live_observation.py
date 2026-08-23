from __future__ import annotations

import json
import http.client
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from smb3_agent.companion_session import Freshness
from smb3_agent.lab_ui import (
    _live_tell,
    _new_lab_ui_server,
    default_companion_session,
    render_companion_ui,
)
from smb3_agent.live_observation import (
    ConnectionState,
    LiveObservationError,
    LiveObservationManager,
    LiveSample,
    LiveSessionAccumulator,
    observed_level_id,
    parse_observer_line,
)
from smb3_agent.run_library import LocalRunLibrary, SolutionClassification
from smb3_agent.takeover import TakeoverController


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _sample(
    sequence: int = 1,
    *,
    frame: int | None = None,
    observed_at: datetime = NOW,
    actor: str = "player",
    buttons: tuple[str, ...] = ("right",),
    world: int = 0,
    object_set: int = 1,
    x: int = 120,
    lives: int = 4,
    dying: int = 0,
    return_map: int = 0,
    items: tuple[int, ...] = (12, 8, 3, 1, 0, 0, 0, 0, 0, 0),
    session_id: str = "session-1",
    token: str = "token-1",
) -> LiveSample:
    return LiveSample(
        session_id=session_id,
        observer_token=token,
        sequence=sequence,
        frame=frame if frame is not None else sequence * 15,
        observed_at=observed_at,
        world=world,
        object_set=object_set,
        map_page=0,
        map_cursor_x=32,
        map_cursor_y=64,
        x=x,
        y=368,
        form=0,
        lives=lives,
        player_is_dying=dying,
        return_map=return_map,
        items=items,
        buttons=buttons,
        actor=actor,
    )


def _accumulator(tmp_path: Path) -> LiveSessionAccumulator:
    return LiveSessionAccumulator("session-1", "token-1", tmp_path)


def test_parser_retains_direct_player_input_and_typed_provenance() -> None:
    line = (
        "schema=game-companion-live-v1 session=session-1 token=token-1 "
        "seq=7 frame=105 actor=player buttons=A,right world=0 object_set=1 "
        "map_page=0 map_cursor_x=32 map_cursor_y=64 x=440 y=368 form=3 "
        "lives=4 dying=0 return_map=0 "
        + " ".join(f"item_{index}={12 if index == 0 else 0}" for index in range(10))
    )
    sample = parse_observer_line(line, observed_at=NOW)

    assert sample.actor == "player"
    assert sample.buttons == ("A", "right")
    assert sample.provenance().source == "fceux-memory-and-joypad-read"
    assert sample.provenance().observed_at == NOW
    assert sample.provenance().sequence == 7
    assert sample.provenance().frame == 105
    assert sample.provenance().confidence == 1.0


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"actor": "unknown"}, "player or agent"),
        ({"buttons": ("A", "A")}, "duplicate"),
        ({"buttons": ("turbo",)}, "unsupported"),
    ],
)
def test_unknown_or_ambiguous_input_records_are_rejected(
    change: dict[str, object], match: str
) -> None:
    with pytest.raises(LiveObservationError, match=match):
        replace(_sample(), **change).validate()


def test_observe_only_rejects_agent_input_and_counts_violation(tmp_path: Path) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample())

    with pytest.raises(LiveObservationError, match="rejects agent input"):
        accumulator.ingest(_sample(2, actor="agent"))

    assert accumulator.agent_input_count == 1
    assert accumulator.connection_state is ConnectionState.DISCONNECTED


def test_valid_observe_only_trace_has_exactly_zero_agent_input(tmp_path: Path) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample())
    accumulator.ingest(_sample(2, buttons=("A", "right"), x=180))

    assert {item.actor for item in accumulator.inputs} == {"player"}
    assert accumulator.agent_input_count == 0


def test_fresh_to_stale_to_disconnected_is_fail_closed(tmp_path: Path) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample())

    fresh = accumulator.snapshot(now=NOW + timedelta(seconds=1))
    stale = accumulator.snapshot(now=NOW + timedelta(seconds=3))
    disconnected = accumulator.snapshot(now=NOW + timedelta(seconds=9))

    assert (fresh.state, fresh.freshness) == (
        ConnectionState.CONNECTED,
        Freshness.FRESH,
    )
    assert (stale.state, stale.freshness, stale.tell_ready) == (
        ConnectionState.STALE,
        Freshness.STALE,
        False,
    )
    assert disconnected.state is ConnectionState.DISCONNECTED
    assert "Tell is unavailable" in disconnected.reason


def test_reconnect_same_identity_and_continuity_resumes_logical_session(
    tmp_path: Path,
) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample())
    accumulator.mark_disconnect("temporary reader disconnect")
    accumulator.ingest(_sample(2, frame=30, observed_at=NOW + timedelta(seconds=1)))

    assert accumulator.connection_state is ConnectionState.CONNECTED
    assert len(accumulator.samples) == 2


def test_unexpected_session_replacement_fails_closed(tmp_path: Path) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample())

    with pytest.raises(LiveObservationError, match="replacement"):
        accumulator.ingest(_sample(2, session_id="different-session"))

    assert accumulator.connection_state is ConnectionState.DISCONNECTED


def test_ordered_sequence_and_frame_are_required(tmp_path: Path) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample(2, frame=30))
    with pytest.raises(LiveObservationError, match="sequence"):
        accumulator.ingest(_sample(2, frame=45))
    with pytest.raises(LiveObservationError, match="frame"):
        accumulator.ingest(_sample(3, frame=29))


def test_death_recovery_progress_transition_and_resources_are_tracked(
    tmp_path: Path,
) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample(x=100))
    accumulator.ingest(_sample(2, x=300, lives=3, dying=1, return_map=1))
    accumulator.ingest(_sample(3, x=0, lives=3, dying=0, object_set=0, return_map=0))
    snapshot = accumulator.snapshot(now=NOW)

    assert snapshot.deaths == 1
    assert snapshot.recoveries == 1
    assert {event.kind.value for event in snapshot.events} >= {
        "death",
        "recovery",
        "progress",
        "course_clear",
    }
    facts = {fact.fact_id: fact.value for fact in snapshot.facts}
    assert facts["warp_whistle_count"] == "1"
    assert facts["p_wing_available"] == "true"
    assert facts["super_leaf_available"] == "true"
    assert facts["super_mushroom_available"] == "true"


def test_uninitialized_lives_sentinel_is_not_a_gameplay_death(tmp_path: Path) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample(1, frame=0, world=255, object_set=0, lives=255))
    accumulator.ingest(_sample(2, frame=4, world=0, object_set=0, lives=0))

    assert accumulator.deaths == 0
    assert all(event.kind.value != "death" for event in accumulator.events)


def test_unknown_and_unsupported_states_block_live_tell(tmp_path: Path) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample(world=255, object_set=0))
    snapshot = accumulator.snapshot(now=NOW)

    assert snapshot.checkpoint_id is None
    assert not snapshot.tell_ready
    with pytest.raises(ValueError, match="live Tell unavailable"):
        _live_tell(snapshot, "world_8_finish_game", {"spoiler_level": ["guided"]})

    accumulator.mark_unsupported("Unsupported ROM identity")
    unsupported = accumulator.snapshot(now=NOW)
    assert unsupported.state is ConnectionState.UNSUPPORTED
    assert unsupported.freshness is Freshness.STALE


def test_unsupported_checkpoint_keeps_observation_active_and_start_disabled(
    tmp_path: Path,
) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample(world=1, object_set=2))
    snapshot = accumulator.snapshot(now=NOW)
    html = render_companion_ui(
        default_companion_session(live_snapshot=snapshot),
        live_snapshot=snapshot,
    )

    assert snapshot.state is ConnectionState.UNSUPPORTED
    assert snapshot.observation_active
    assert 'data-testid="observe-start" disabled' in html
    assert 'data-testid="observe-stop" disabled' not in html
    assert "This Mario checkpoint is not yet supported" in html


def test_live_observed_tell_is_adapter_labeled_and_stale_rejected(tmp_path: Path) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample())
    snapshot = accumulator.snapshot(now=NOW)
    session, card = _live_tell(
        snapshot,
        "world_8_finish_game",
        {"spoiler_level": ["guided"]},
    )

    assert session.observation.source.value == "adapter_observed"
    assert card.observation_source.value == "adapter_observed"
    stale = accumulator.snapshot(now=NOW + timedelta(seconds=3))
    with pytest.raises(ValueError, match="live Tell unavailable"):
        _live_tell(stale, "world_8_finish_game", {"spoiler_level": ["guided"]})


def test_player_ui_renders_live_observe_only_contract_and_narrow_css(tmp_path: Path) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample(buttons=("A", "right")))
    snapshot = accumulator.snapshot(now=NOW)
    html = render_companion_ui(
        default_companion_session(live_snapshot=snapshot),
        live_snapshot=snapshot,
    )

    for hook in (
        "live-observation",
        "live-control-ownership",
        "live-status",
        "live-resources",
        "live-inputs",
        "live-events",
        "observe-start",
        "observe-stop",
        "live-tell-request",
        "agent-input-count",
    ):
        assert f'data-testid="{hook}"' in html
    assert "You are playing" in html
    assert "observing only" in html
    assert "Allow takeover later" in html
    assert "Start a new session with Allow takeover later" in html
    assert 'data-testid="take-control-now" disabled' in html
    assert "separate demonstration" in html
    assert "player-reported" in html
    assert "@media (max-width: 760px)" in html
    assert "overflow-x: hidden" in html


def test_clean_stop_retains_game_and_artifact_reconciliation(tmp_path: Path) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample())
    manager = LiveObservationManager(artifacts_root=tmp_path)
    manager._accumulator = accumulator
    manager._finalize("clean_stop")
    accumulator.stop()
    snapshot = accumulator.snapshot(now=NOW)
    report = json.loads((tmp_path / "reconciliation.json").read_text())

    assert snapshot.state is ConnectionState.STOPPED
    assert "game was left running and unchanged" in snapshot.reason
    assert report["agent_input_count"] == 0
    assert report["agent_input_zero"] is True
    assert report["observation_stopped_without_game_process_termination"] is True
    assert report["not_route_reliability"] is True
    assert report["not_show"] is True
    assert report["not_takeover"] is True


def test_state_sample_conversion_failure_is_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample())
    manager = LiveObservationManager(artifacts_root=tmp_path)
    manager._accumulator = accumulator
    monkeypatch.setattr(
        "smb3_agent.live_observation.convert_gd_directory",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("decoder unavailable")),
    )

    manager._finalize("clean_stop")

    report = json.loads((tmp_path / "reconciliation.json").read_text())
    assert report["independently_readable_state_samples"] == []
    assert report["state_sample_conversion_exception"]["type"] == "OSError"
    assert "decoder unavailable" in report["state_sample_conversion_exception"]["traceback"]


def test_passive_lua_has_no_controller_or_game_write_path() -> None:
    source = Path("scripts/fceux_live_observer.lua").read_text()

    assert "joypad.get(1)" in source
    for prohibited in (
        "joypad.set",
        "memory.write",
        "emu.reset",
        "emu.poweron",
        "savestate.load",
        "savestate.save",
    ):
        assert prohibited not in source.replace(
            "-- joypad.set, memory.write, reset, power-on, savestate, or state-load path.",
            "",
        )


def test_takeover_lua_is_separate_and_reclaim_is_checked_inside_emulator_loop() -> None:
    passive = Path("scripts/fceux_live_observer.lua").read_text()
    takeover = Path("scripts/fceux_live_takeover.lua").read_text()
    accepted = Path("scripts/fceux_1_1_agent.lua").read_text()

    assert "joypad.set" not in passive.replace(
        "-- joypad.set, memory.write, reset, power-on, savestate, or state-load path.", ""
    )
    assert "joypad.set(1, {})" in takeover
    assert "GAME_COMPANION_RECLAIM_REQUESTED" in accepted
    assert "SMB3_TAKEOVER_RECLAIM_PATH" in accepted
    assert "savestate.load" not in takeover


def test_valid_completion_automatically_creates_candidate_run_and_profile(tmp_path: Path) -> None:
    library = LocalRunLibrary(tmp_path / "run-library")
    manager = LiveObservationManager(
        artifacts_root=tmp_path / "sessions", run_library=library
    )
    artifact_dir = tmp_path / "session"
    artifact_dir.mkdir()
    accumulator = LiveSessionAccumulator("session-1", "token-1", artifact_dir)
    manager._accumulator = accumulator
    start = _sample(1, frame=100, x=24)
    middle = _sample(2, frame=400, x=1200)
    terminal = _sample(3, frame=700, object_set=0, return_map=0, x=0)
    middle = replace(middle, return_map=1)
    accumulator.ingest(start)
    accumulator.ingest(middle)
    accumulator.ingest(terminal)
    manager._maybe_record_completion(middle, terminal)

    runs = library.runs()
    assert len(runs) == 1
    assert runs[0].actor == "player"
    assert runs[0].solution_classification is SolutionClassification.CANDIDATE
    assert len(library.profiles()) == 1
    assert library.summary("smb3", "world_1_1")["fastest_overall"].run_id == runs[0].run_id


def test_observed_level_identity_matches_dynamic_map_node_run_key() -> None:
    samples = (
        _sample(1, frame=100, object_set=0, x=0),
        replace(
            _sample(1, frame=100, object_set=0, x=0),
            sequence=2,
            map_page=0,
            map_cursor_x=64,
            map_cursor_y=32,
        ),
        _sample(3, frame=200, object_set=1, x=24),
        _sample(4, frame=700, object_set=1, x=2843, return_map=1),
        _sample(5, frame=718, object_set=0, x=8192),
    )
    assert (
        observed_level_id(samples)
        == "world_1_page_1_node_64_32_object_1"
    )


def test_mixed_player_agent_completion_is_not_pure_agent_speedrun(tmp_path: Path) -> None:
    library = LocalRunLibrary(tmp_path / "run-library")
    artifact_dir = tmp_path / "session"
    artifact_dir.mkdir()
    controller = TakeoverController(artifact_dir, artifact_dir / "control.request")
    accumulator = LiveSessionAccumulator(
        "session-1", "token-1", artifact_dir, takeover_controller=controller
    )
    manager = LiveObservationManager(run_library=library)
    manager._accumulator = accumulator
    start = _sample(1, frame=100, x=24)
    accumulator.ingest(start)
    # The completion recorder intentionally preserves ownership from the full interval.
    agent = replace(_sample(2, frame=650, x=2800), actor="agent", control_epoch=1)
    accumulator.samples.append(agent)
    terminal = replace(
        _sample(3, frame=700, object_set=0, return_map=0, x=0),
        actor="agent",
        control_epoch=1,
    )
    agent = replace(agent, return_map=1)
    accumulator.samples[-1] = agent
    accumulator.samples.append(terminal)
    manager._maybe_record_completion(agent, terminal)
    assert library.runs()[0].actor == "mixed"
    assert library.summary("smb3", "world_1_1")["fastest_agent"] is None


def test_takeover_capable_ui_shows_preflight_reclaim_and_390px_contract(tmp_path: Path) -> None:
    controller = TakeoverController(tmp_path, tmp_path / "control.request")
    accumulator = LiveSessionAccumulator(
        "session-1", "token-1", tmp_path, takeover_controller=controller
    )
    accumulator.ingest(_sample())
    snapshot = accumulator.snapshot(now=NOW)
    html = render_companion_ui(
        default_companion_session(live_snapshot=snapshot),
        live_snapshot=snapshot,
        csrf_token="token",
    )
    assert 'data-testid="takeover-preflight"' in html
    assert 'data-testid="hand-control" disabled' not in html
    assert 'data-testid="take-control-now" disabled' in html
    assert "same visible emulator process" in html
    assert "@media (max-width: 420px)" in html


def test_observer_parser_rejects_incomplete_evidence() -> None:
    with pytest.raises(LiveObservationError, match="incomplete"):
        parse_observer_line("schema=game-companion-live-v1 session=s token=t")


def test_configured_separate_show_does_not_masquerade_as_live_observation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    game_path = tmp_path / "configured.nes"
    game_path.write_bytes(b"ROM-free fixture")
    monkeypatch.setenv("SMB3_GAME_FILE", str(game_path))
    idle = default_companion_session(
        live_snapshot=LiveObservationManager().snapshot()
    )
    html = render_companion_ui(idle, live_snapshot=LiveObservationManager().snapshot())

    assert idle.observation.freshness is Freshness.UNKNOWN
    assert next(mode for mode in idle.modes if mode.mode == "show").available is False
    assert "Show uses a separate visible process" in html
    assert 'data-testid="show-start"' in html


def test_manager_clean_detach_releases_observer_without_terminating_game(
    tmp_path: Path,
) -> None:
    class FakeProcess:
        pid = 4242
        terminate_calls = 0
        kill_calls = 0

        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            self.terminate_calls += 1

        def kill(self) -> None:
            self.kill_calls += 1

    process = FakeProcess()
    launched: dict[str, object] = {}
    launch_count = 0

    def launcher(command: list[str], **kwargs: object) -> FakeProcess:
        nonlocal launch_count
        launch_count += 1
        launched["command"] = command
        launched["kwargs"] = kwargs
        return process

    game_path = tmp_path / "smb3.nes"
    game_path.write_bytes(b"fixture-rom-identity")
    manager = LiveObservationManager(artifacts_root=tmp_path / "artifacts", launcher=launcher)
    started = manager.start(game_path)
    duplicate_start = manager.start(game_path)
    stopped = manager.stop()
    assert manager._thread is not None
    manager._thread.join(timeout=2)

    assert started.state is ConnectionState.CONNECTING
    assert duplicate_start.session_id == started.session_id
    assert launch_count == 1
    assert stopped.state is ConnectionState.STOPPED
    assert process.terminate_calls == 0
    assert process.kill_calls == 0
    assert manager._thread.is_alive() is False
    command = launched["command"]
    assert isinstance(command, list)
    assert command[:2] == ["fceux", "--loadlua"]
    assert "--loadstate" not in command
    assert "--savestate" not in command
    assert stopped.artifact_dir is not None
    manifest = json.loads((stopped.artifact_dir / "session_manifest.json").read_text())
    connection = json.loads((stopped.artifact_dir / "connection.json").read_text())
    reconciliation = json.loads((stopped.artifact_dir / "reconciliation.json").read_text())
    assert manifest["controller_write_path"] is False
    assert manifest["savestate"] is False
    assert connection["process_id"] == 4242
    assert reconciliation["observation_stopped_without_game_process_termination"] is True
    assert reconciliation["agent_input_count"] == 0


def test_player_reported_tell_preserves_active_live_lifecycle(tmp_path: Path) -> None:
    server = _new_lab_ui_server("127.0.0.1", 0)
    manager = getattr(server, "live_observation_manager")
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(_sample(observed_at=datetime.now(timezone.utc)))
    manager._accumulator = accumulator
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = (
            f"csrf_token={getattr(server, 'csrf_token')}"
            "&goal_id=world_8_finish_game"
            "&checkpoint_id=world_1_1_clear"
            "&spoiler_level=guided&checkpoint_confirmed=true"
        )
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
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
    assert 'data-connection-state="connected"' in html
    assert 'data-testid="observe-start" disabled' in html
    assert 'data-testid="observe-stop" disabled' not in html
    assert "You are playing · observing only" in html
    assert "Player Reported" in html


def test_unavailable_live_tell_stays_on_coherent_player_page(tmp_path: Path) -> None:
    server = _new_lab_ui_server("127.0.0.1", 0)
    manager = getattr(server, "live_observation_manager")
    accumulator = _accumulator(tmp_path)
    accumulator.ingest(
        _sample(object_set=0, observed_at=datetime.now(timezone.utc))
    )
    manager._accumulator = accumulator
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = (
            f"csrf_token={getattr(server, 'csrf_token')}"
            "&goal_id=world_8_finish_game&spoiler_level=guided"
        )
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request(
            "POST",
            "/tell-live",
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

    assert response.status == 400
    assert 'data-testid="companion-shell"' in html
    assert 'data-connection-state="connected"' in html
    assert "Live Tell needs a supported checkpoint" in html
    assert "Game Companion Lab Error" not in html
