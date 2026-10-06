from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci_report.py"
spec = importlib.util.spec_from_file_location("ci_report", SCRIPT)
assert spec is not None and spec.loader is not None
ci_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_report)


def test_reports_mixed_results_and_preserves_failed_gate(tmp_path: Path) -> None:
    report = tmp_path / "junit.xml"
    report.write_text("""<testsuites><testsuite tests="4" failures="1" errors="1" skipped="1" time="8.5">
    <testcase classname="a" name="pass" time="1"/>
    <testcase classname="a" name="fail" time="5"><failure/></testcase>
    <testcase name="error" time="2"><error/></testcase>
    <testcase name="skip" time="0.5"><skipped message="Mac only"/></testcase>
    </testsuite></testsuites>""")
    summary, metrics = ci_report.build_report(report, "failure")
    assert metrics == {
        "gate_outcome": "failure",
        "test_report": "available",
        "tests": 4,
        "failures": 1,
        "errors": 1,
        "skipped": 1,
        "passed": 1,
        "duration_seconds": 8.5,
    }
    assert "Canonical gate: **failure**" in summary
    assert "| 1 | <code>Mac only</code> |" in summary
    assert summary.index("a.fail") < summary.index("a.pass")


@pytest.mark.parametrize(
    "content, state",
    [(None, "missing"), ("broken", "invalid"), ('<testsuite tests="bad"/>', "invalid")],
)
def test_unavailable_results_never_imply_success(
    tmp_path: Path, content: str | None, state: str
) -> None:
    report = tmp_path / "junit.xml"
    if content is not None:
        report.write_text(content)
    summary, metrics = ci_report.build_report(report, "skipped")
    assert metrics["test_report"] == state
    assert "passed" not in metrics
    assert "inspect" in summary


def test_nested_suites_and_escaping(tmp_path: Path) -> None:
    report = tmp_path / "junit.xml"
    report.write_text(
        """<testsuites><testsuite tests="1"><testsuite tests="1" skipped="1" time="1"><testcase name="&lt;script&gt;|x"><skipped message="&lt;img&gt;| reason"/></testcase></testsuite></testsuite></testsuites>"""
    )
    summary, metrics = ci_report.build_report(report, "success")
    assert metrics["tests"] == 1
    assert "<script>" not in summary and "<img>" not in summary
    assert "&#124;" in summary


def test_cli_writes_artifacts_and_appends_github_summary(tmp_path: Path) -> None:
    summary_path = tmp_path / "github-summary"
    summary_path.write_text("Existing summary\n")
    out = tmp_path / "results"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--report",
            str(out / "missing.xml"),
            "--output-dir",
            str(out),
            "--summary",
            str(summary_path),
            "--gate-outcome",
            "skipped",
        ],
        check=True,
    )
    assert json.loads((out / "metrics.json").read_text())["test_report"] == "missing"
    assert (
        summary_path.read_text()
        == "Existing summary\n" + (out / "summary.md").read_text()
    )
