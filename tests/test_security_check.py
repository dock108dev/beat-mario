from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SECURITY_CHECK_PATH = REPOSITORY_ROOT / "scripts/security_check.py"


def _load_security_check():
    spec = importlib.util.spec_from_file_location("security_check", SECURITY_CHECK_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_failure_output_does_not_disclose_secret_or_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    security_check = _load_security_check()
    secret_path = tmp_path / "sensitive-name.txt"
    secret_path.write_bytes(b"token=ghp_abcdefghijklmnopqrstuvwxyz1234567890")
    monkeypatch.setattr(security_check, "tracked_files", lambda: (secret_path,))

    assert security_check.main() == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "Security hygiene check failed; review tracked files locally.\n"
    )
    assert str(secret_path) not in captured.err
    assert "ghp_" not in captured.err


def test_inspection_error_output_does_not_disclose_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    security_check = _load_security_check()
    missing_path = tmp_path / "credential-secret.txt"
    monkeypatch.setattr(security_check, "tracked_files", lambda: (missing_path,))

    assert security_check.main() == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "Security hygiene check failed; review tracked files locally.\n"
    )
    assert str(missing_path) not in captured.err
