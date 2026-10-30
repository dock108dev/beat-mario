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
    result = subprocess.run(
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
        check=False,
    )
    assert result.returncode == 1
    assert json.loads((out / "metrics.json").read_text())["test_report"] == "missing"
    assert (
        summary_path.read_text()
        == "Existing summary\n" + (out / "summary.md").read_text()
    )


@pytest.mark.parametrize(
    "content",
    [
        "<testsuites/>",
        '<testsuite tests="0"/>',
        '<testsuite tests="5"><testcase/></testsuite>',
    ],
)
def test_empty_or_inconsistent_report_is_invalid(tmp_path, content):
    report = tmp_path / "report.xml"
    report.write_text(content)
    _, metrics = ci_report.build_report(report, "success")
    assert metrics["test_report"] == "invalid"


def test_node_direct_cases(tmp_path):
    report = tmp_path / "node.xml"
    report.write_text(
        '<testsuites><testcase name="pass" time="1"/><testcase name="fail"><failure/></testcase></testsuites>'
    )
    _, metrics = ci_report.build_report(report, "failure")
    assert metrics["tests"] == 2
    assert metrics["failures"] == 1


def test_failure_cannot_be_hidden_by_zero_counter(tmp_path):
    report = tmp_path / "report.xml"
    report.write_text(
        '<testsuite tests="1" failures="0"><testcase><failure/></testcase></testsuite>'
    )
    _, metrics = ci_report.build_report(report, "success")
    assert metrics["test_report"] == "invalid"


@pytest.mark.parametrize("outcome", ["failure", "skipped", "cancelled", "not run"])
def test_required_check_cannot_be_hidden_by_passing_junit(tmp_path, outcome):
    _, _, problems = ci_report.required_evidence(
        tmp_path, {"validate": {"outcome": outcome}}, ["validate"]
    )
    assert problems and outcome in problems[0]


def test_missing_and_malformed_required_artifacts_are_unavailable(tmp_path):
    checks = {name: {"outcome": "success"} for name in ("coverage", "build")}
    _, artifacts, problems = ci_report.required_evidence(tmp_path, checks, list(checks))
    assert len(problems) == 2 and artifacts == {"coverage": None, "build": None}
    (tmp_path / "coverage.json").write_text("{broken")
    (tmp_path / "build.json").write_text('{"status":"PASS","sizes_bytes":{}}')
    assert len(ci_report.required_evidence(tmp_path, checks, list(checks))[2]) == 2


def test_valid_required_evidence_and_intentional_unrequired_skip(tmp_path):
    totals = {
        "covered_lines": 3,
        "num_statements": 4,
        "covered_branches": 1,
        "num_branches": 2,
    }
    (tmp_path / "coverage.json").write_text(json.dumps({"totals": totals}))
    (tmp_path / "coverage.xml").write_text("<coverage/>")
    (tmp_path / "build.json").write_text(
        json.dumps({"status": "PASS", "sizes_bytes": {"app.whl": 123}})
    )
    checks = {name: {"outcome": "success"} for name in ("coverage", "build")}
    checks["scheduled_audit"] = {"outcome": "skipped"}
    outcomes, artifacts, problems = ci_report.required_evidence(
        tmp_path, checks, ["coverage", "build"]
    )
    assert not problems and "scheduled_audit" not in outcomes
    assert artifacts["coverage"] == totals


def test_cli_missing_build_still_writes_failed_summary(tmp_path, monkeypatch):
    report = tmp_path / "junit.xml"
    report.write_text('<testsuite tests="1"><testcase name="pass"/></testsuite>')
    monkeypatch.setenv("CHECK_OUTCOMES", '{"build":{"outcome":"success"}}')
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--report",
            str(report),
            "--output-dir",
            str(tmp_path),
            "--summary",
            str(tmp_path / "summary"),
            "--gate-outcome",
            "success",
            "--require-check",
            "build",
        ]
    )
    assert result.returncode == 1
    assert "required report missing" in (tmp_path / "summary.md").read_text()
    assert (
        json.loads((tmp_path / "metrics.json").read_text())["artifacts"]["build"]
        is None
    )


def test_all_skipped_cli_is_not_a_successful_behavior_gate(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuite tests="1" skipped="1"><testcase><skipped message="platform"/></testcase></testsuite>'
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--report",
            str(report),
            "--output-dir",
            str(tmp_path),
            "--summary",
            str(tmp_path / "summary"),
            "--gate-outcome",
            "success",
        ]
    )
    assert result.returncode == 1
    assert json.loads((tmp_path / "metrics.json").read_text())["overall"] == "FAIL"


def test_failed_names_and_reasons_are_escaped(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuite tests="1" failures="1"><testcase name="bad|name"><failure message="&lt;script&gt;"/></testcase></testsuite>'
    )
    summary, _ = ci_report.build_report(report, "failure")
    assert "### Failing tests" in summary
    assert "bad&#124;name" in summary and "<script>" not in summary
