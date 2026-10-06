"""Shared emulator policy using disposable files and intercepted launches only."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

import pytest

from smb3_agent import executable_discovery, fceux_harness, reliability, show
from smb3_agent.companion_session import Freshness, Observation, ObservationSource
from smb3_agent.goals import ACTIVE_PRODUCT_GOAL_ID
from smb3_agent.live_observation import LiveObservationError, LiveObservationManager


def test_shell_path_precedes_finder_roots(tmp_path):
    binary = tmp_path / "fceux"
    binary.write_text("fixture")
    binary.chmod(0o700)
    assert executable_discovery.discover_fceux(
        which=lambda name: "/shell/" + name, roots=(tmp_path,)
    ) == "/shell/fceux"


def test_finder_roots_require_executable_files(tmp_path):
    binary = tmp_path / "fceux"
    binary.write_text("fixture")
    binary.chmod(0o600)
    assert executable_discovery.discover_fceux(which=lambda _: None, roots=(tmp_path,)) is None
    binary.chmod(0o700)
    assert executable_discovery.discover_fceux(which=lambda _: None, roots=(tmp_path,)) == str(binary)


def _launch(path, game, artifacts):
    if path == "live":
        return LiveObservationManager(artifacts_root=artifacts, launcher=subprocess.Popen).start(game)
    if path == "harness":
        return fceux_harness.run_fceux_1_1(
            game_path=game, script_path=Path("scripts/fceux_1_1_agent.lua"),
            artifacts_dir=artifacts, attempts=1,
        )
    request = show.ShowRequest(
        adapter_id="mario", game_id="smb3", goal_id="world_1_1_clear", segment_id="world_1_1_clear",
        observation=Observation(
            checkpoint="World 1-1", checkpoint_id="world_1_1_clear",
            observed_at=datetime.now(timezone.utc), freshness=Freshness.FRESH, confidence=1.0,
            evidence_references=("fixture:fresh",), source=ObservationSource.ADAPTER, game_id="smb3",
        ),
        game_path=game, trusted_starting_state="fresh power-on",
        demonstration_stop_event="show_input_stopped", recovery_boundary="stop on mismatch",
        protected_decisions=("player game",),
    )
    return show.run_show_demonstration(request, show.load_show_definition(), artifacts, show.ShowProcessController())


@pytest.mark.parametrize("path", ["live", "harness", "show"])
def test_launch_uses_shared_finder_resolution(path, tmp_path, monkeypatch):
    game = tmp_path / "fixture.nes"
    game.write_bytes(b"synthetic")
    commands = []
    monkeypatch.setattr(executable_discovery, "discover_fceux", lambda: "/finder/fceux")

    def intercepted(command, **kwargs):
        commands.append(command)
        raise OSError("intercepted synthetic launch")

    monkeypatch.setattr("subprocess.Popen", intercepted)
    monkeypatch.setattr("subprocess.run", intercepted)
    with pytest.raises((OSError, LiveObservationError), match="intercepted synthetic launch"):
        _launch(path, game, tmp_path / "artifacts")
    assert len(commands) == 1
    assert commands[0][0] == "/finder/fceux"


@pytest.mark.parametrize("path", ["live", "harness", "show"])
def test_missing_emulator_never_launches_by_name(path, tmp_path, monkeypatch):
    game = tmp_path / "fixture.nes"
    game.write_bytes(b"synthetic")
    monkeypatch.setattr(executable_discovery, "discover_fceux", lambda: None)

    def forbidden(*args, **kwargs):
        pytest.fail("No child may launch when discovery refuses")

    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    artifacts = tmp_path / "artifacts"
    with pytest.raises((FileNotFoundError, LiveObservationError), match="FCEUX was not found"):
        _launch(path, game, artifacts)
    if path == "harness":
        receipt = json.loads((artifacts / "fceux_execution.json").read_text())
        assert receipt["returncode"] is None
        assert "FCEUX was not found" in receipt["launch_error"]
    else:
        assert not artifacts.exists()


@pytest.mark.parametrize("available", [True, False])
def test_reliability_default_preflight_uses_shared_discovery(available, tmp_path, monkeypatch):
    game = tmp_path / "fixture.nes"
    game.write_bytes(b"synthetic")
    calls = []

    def discovery():
        calls.append(True)
        return "/finder/fceux" if available else None

    monkeypatch.setattr(executable_discovery, "discover_fceux", discovery)
    kwargs = dict(game_path=game, emulator_resolver=None, requested_runs=1,
                  profile=reliability._reliability_profile(ACTIVE_PRODUCT_GOAL_ID))
    if available:
        contract, _, _ = reliability._load_product_contract(**kwargs)
        assert contract.id == ACTIVE_PRODUCT_GOAL_ID
    else:
        with pytest.raises(FileNotFoundError, match="FCEUX was not found"):
            reliability._load_product_contract(**kwargs)
    assert calls == [True]
