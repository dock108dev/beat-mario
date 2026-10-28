"""Audit outages and vulnerability findings cannot become clean results."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

spec = importlib.util.spec_from_file_location('ci_npm_audit', Path(__file__).resolve().parents[1] / 'scripts/ci_npm_audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.mark.parametrize('payload, code, expected', [
    ({'metadata': {'vulnerabilities': {'low': 0, 'moderate': 0, 'high': 0, 'critical': 0}}}, 0, 0),
    ({'metadata': {'vulnerabilities': {'low': 0, 'moderate': 0, 'high': 1, 'critical': 0}}}, 1, 1),
    ({'error': 'registry unavailable'}, 1, 1),
    ({'metadata': {'vulnerabilities': {'low': 0, 'moderate': 0, 'high': 0, 'critical': 0}}}, 2, 1),
])
def test_audit_result_is_explicit(tmp_path, monkeypatch, payload, code, expected):
    output = tmp_path / 'audit.json'
    summary = tmp_path / 'summary.md'
    monkeypatch.setattr(sys, 'argv', ['audit', '--output', str(output)])
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary))
    monkeypatch.setattr(audit.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, code, json.dumps(payload), ''))
    assert audit.main() == expected
    assert json.loads(output.read_text()) == payload
    assert summary.exists()
