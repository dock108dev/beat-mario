"""Shared emulator policy using disposable files and intercepted launches only."""
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import subprocess
import threading
from urllib.parse import urlencode

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


@pytest.fixture
def trusted_fceux(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "trusted-bin"
    root.mkdir()
    binary = root / "fceux"
    binary.write_text("synthetic executable; never launched")
    binary.chmod(0o700)
    monkeypatch.setattr(executable_discovery, "FCEUX_ROOTS", (root,))
    monkeypatch.setattr(executable_discovery.shutil, "which", lambda _: None)
    return binary


def test_selection_registers_trusted_binary_and_discovers_it(trusted_fceux):
    expected = str(trusted_fceux)
    assert executable_discovery.select_fceux(expected) == expected
    assert executable_discovery.discover_fceux() == expected
    assert json.loads(Path("artifacts/executable-selection.json").read_text()) == {"fceux": expected}


def test_selection_accepts_trusted_homebrew_style_symlink(trusted_fceux, tmp_path):
    cellar = tmp_path / "Cellar" / "fceux" / "1" / "bin" / "fceux"
    cellar.parent.mkdir(parents=True)
    trusted_fceux.rename(cellar)
    trusted_fceux.symlink_to(cellar)
    assert executable_discovery.select_fceux(str(trusted_fceux)) == str(cellar)
    assert executable_discovery.discover_fceux() == str(cellar)
    assert executable_discovery.select_fceux(str(cellar)) == str(cellar)


def test_selection_accepts_custom_install_only_when_discovered_on_path(trusted_fceux, tmp_path, monkeypatch):
    custom = tmp_path / "custom-bin" / "fceux"
    custom.parent.mkdir()
    custom.write_text("synthetic")
    custom.chmod(0o700)
    monkeypatch.setattr(executable_discovery.shutil, "which", lambda _: str(custom))
    assert executable_discovery.select_fceux(str(custom)) == str(custom)
    assert executable_discovery.discover_fceux() == str(custom)


@pytest.mark.parametrize("value", ["../../etc/passwd", "/etc/passwd", "fceux", "", "/tmp/fceux", "/tmp/fceux\x00"])
def test_untrusted_selection_never_reaches_filesystem_checks(value, trusted_fceux, monkeypatch):
    registration = Path("artifacts/executable-selection.json")
    executable_discovery.select_fceux(str(trusted_fceux))
    before = registration.read_bytes()
    original = Path.resolve

    def checked_resolve(path, *args, **kwargs):
        assert path == trusted_fceux
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", checked_resolve)
    with pytest.raises(ValueError, match="Choose FCEUX from PATH"):
        executable_discovery.select_fceux(value)
    assert registration.read_bytes() == before


def test_arbitrary_executable_and_alias_cannot_be_registered(trusted_fceux, tmp_path):
    other = tmp_path / "untrusted" / "fceux"
    other.parent.mkdir()
    other.write_text("synthetic")
    other.chmod(0o700)
    alias = tmp_path / "untrusted-link"
    alias.symlink_to(trusted_fceux)
    for path in (other, alias, trusted_fceux.parent / ".." / "trusted-bin" / "fceux"):
        with pytest.raises(ValueError):
            executable_discovery.select_fceux(str(path))
    assert not Path("artifacts").exists()


@pytest.mark.parametrize("payload", [{"fceux": "/tmp/fceux"}, {"fceux": "../../etc/passwd"}, {"fceux": None}, {"fceux": []}, {}])
def test_invalid_registration_refuses_without_fallback(payload, trusted_fceux):
    registration = Path("artifacts/executable-selection.json")
    registration.parent.mkdir()
    registration.write_text(json.dumps(payload))
    assert executable_discovery.discover_fceux(which=lambda _: str(trusted_fceux)) is None


def test_nonexecutable_or_missing_trusted_selection_is_refused(trusted_fceux):
    trusted_fceux.chmod(0o600)
    with pytest.raises(ValueError):
        executable_discovery.select_fceux(str(trusted_fceux))
    trusted_fceux.unlink()
    with pytest.raises(ValueError):
        executable_discovery.select_fceux(str(trusted_fceux))


@pytest.mark.parametrize("accepted", [True, False])
def test_emulator_setup_form_reports_selection_result(accepted, trusted_fceux):
    from smb3_agent.lab_ui import _new_lab_ui_server

    server = _new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request(
            "POST", "/setup-emulator",
            body=urlencode({"csrf_token": server.csrf_token,
                            "executable": str(trusted_fceux) if accepted else "/etc/passwd"}),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = connection.getresponse()
        body = response.read().decode()
        if accepted:
            assert response.status == 303
            assert response.getheader("Location") == "/mario#setup"
            assert executable_discovery.discover_fceux() == str(trusted_fceux)
        else:
            assert response.status == 400
            assert "Choose FCEUX from PATH" in body
            assert "Traceback" not in body
            assert not Path("artifacts/executable-selection.json").exists()
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
