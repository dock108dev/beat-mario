"""Synthetic audit evidence: known findings, missing records and tool outages."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

spec = importlib.util.spec_from_file_location(
    "ci_python_audit", Path(__file__).parents[1] / "scripts/ci_python_audit.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.mark.parametrize(
    "payload,code,status",
    [
        ({"dependencies": [{"name": "demo", "vulns": []}]}, 0, "PASS"),
        (
            {"dependencies": [{"name": "demo", "vulns": [{"id": "synthetic"}]}]},
            1,
            "FAIL",
        ),
        ({"dependencies": []}, 0, "UNAVAILABLE"),
        (
            {"dependencies": [{"name": "demo", "skip_reason": "unavailable"}]},
            0,
            "UNAVAILABLE",
        ),
        ({"dependencies": [{"name": "demo", "vulns": []}]}, 2, "UNAVAILABLE"),
        (None, 0, "UNAVAILABLE"),
    ],
)
def test_audit_scope_and_failure_reporting(
    tmp_path, monkeypatch, payload, code, status
):
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["audit", "--output", str(output)])
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    def run(command, **kwargs):
        if command[0] == "uvx":
            assert "--disable-pip" in command and "--require-hashes" in command
            if payload is None:
                raise subprocess.TimeoutExpired(command, 240)
            Path(command[-1]).write_text(json.dumps(payload))
        return subprocess.CompletedProcess(command, code)

    monkeypatch.setattr(audit.subprocess, "run", run)
    assert audit.main() == (0 if status == "PASS" else 1)
    result = json.loads(output.read_text())
    assert result["status"] == status
    if status == "UNAVAILABLE":
        assert result["findings"] is None
