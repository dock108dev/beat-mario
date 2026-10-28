"""Summarize offline CI tests without requiring extra packages or GitHub permissions."""

from __future__ import annotations

import argparse
from collections import Counter
from html import escape
import json
import math
import os
import platform
import sys
from pathlib import Path
import xml.etree.ElementTree as ET


def _table_text(value: str) -> str:
    # Test names and skip reasons must not create HTML or extra Markdown cells.
    return escape(value[:300]).replace("|", "&#124;").replace("\n", " ")


def build_report(report: Path, gate_outcome: str) -> tuple[str, dict]:
    metrics = {"gate_outcome": gate_outcome, "test_report": "missing"}
    lines = [
        "## Repository validation",
        "",
        f"Canonical gate: **{escape(gate_outcome)}**",
        "",
    ]
    if not report.exists():
        lines.append(
            "No test report was produced. Tests may not have started or completed; inspect the failed step's log."
        )
    else:
        try:
            root = ET.parse(report).getroot()
            suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
            # Node's built-in JUnit reporter emits direct cases without suite counters.
            if root.tag == "testsuites" and root.findall("testcase") and not suites:
                cases = root.findall("testcase")
                suite = ET.Element("testsuite", {
                    "tests": str(len(cases)),
                    "failures": str(sum(c.find("failure") is not None for c in cases)),
                    "errors": str(sum(c.find("error") is not None for c in cases)),
                    "skipped": str(sum(c.find("skipped") is not None for c in cases)),
                    "time": str(sum(float(c.get("time", "0")) for c in cases)),
                })
                suites = [suite]
            # pytest emits leaf suites; ignore containers to avoid double counting.
            suites = [suite for suite in suites if suite.find("testsuite") is None]
            counts = {
                key: sum(int(suite.get(key, "0")) for suite in suites)
                for key in ("tests", "failures", "errors", "skipped")
            }
            duration = sum(float(suite.get("time", "0")) for suite in suites)
            counts["passed"] = (
                counts["tests"]
                - counts["failures"]
                - counts["errors"]
                - counts["skipped"]
            )
            cases = list(root.iter("testcase"))
            if (not suites or counts["tests"] <= 0 or counts["tests"] != len(cases)
                    or any(value < 0 for value in counts.values())
                    or not math.isfinite(duration) or duration < 0):
                raise ValueError("Empty or inconsistent report")
            for tag, key in (("failure", "failures"), ("error", "errors"), ("skipped", "skipped")):
                if sum(case.find(tag) is not None for case in cases) != counts[key]:
                    raise ValueError("Outcome counters disagree with cases")
            if any(not math.isfinite(float(case.get("time", "0"))) or float(case.get("time", "0")) < 0 for case in cases):
                raise ValueError("Invalid test duration")
            slowest = sorted(
                cases, key=lambda case: float(case.get("time", "0")), reverse=True
            )[:5]
            skips = Counter(
                skip.get("message", "Unspecified")
                for case in cases
                for skip in case.findall("skipped")
            )
            metrics.update(
                test_report="available", **counts, duration_seconds=round(duration, 3)
            )
            lines.extend(
                [
                    "| Tests | Passed | Failures | Errors | Skipped | Duration |",
                    "|---|---|---|---|---|---|",
                    f"| {counts['tests']} | {counts['passed']} | {counts['failures']} | {counts['errors']} | {counts['skipped']} | {duration:.2f}s |",
                    "",
                ]
            )
            if skips:
                lines.extend(
                    ["### Skipped tests", "", "| Count | Reason |", "|---|---|"]
                )
                for reason, count in skips.most_common(10):
                    lines.append(
                        f"| {count} | <code>{_table_text(reason)}</code> |"
                    )
                lines.append("")
            if slowest:
                lines.extend(
                    [
                        "### Slowest tests (including setup and teardown)",
                        "",
                        "| Test | Duration |",
                        "|---|---|",
                    ]
                )
                for case in slowest:
                    name = f"{case.get('classname', '')}.{case.get('name', '')}"
                    lines.append(
                        f"| <code>{_table_text(name)}</code> | {float(case.get('time', '0')):.2f}s |"
                    )
                lines.append("")
        except (ET.ParseError, ValueError) as exc:
            metrics["test_report"] = "invalid"
            lines.append(
                f"Test report could not be read ({type(exc).__name__}); inspect the test log. No passing result is inferred."
            )
    lines.extend(
        [
            "",
            "The gate also checks lint, whitespace, tracked credentials/local assets, goal/segment contracts, and static UI renders. A successful test report alone does not mean the whole gate passed.",
            "",
            "Security results are separate dependency-review and scheduled npm audit checks; unavailable scans are not zero findings. Python coverage is retained separately. Native gameplay is not measured here.",
            "",
        ]
    )
    return "\n".join(lines), metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--gate-outcome", required=True)
    args = parser.parse_args()
    summary, metrics = build_report(args.report, args.gate_outcome)
    coverage_path = args.report.parent / "coverage.json"
    if coverage_path.exists():
        coverage = json.loads(coverage_path.read_text())["totals"]
        metrics["coverage"] = coverage
        summary += f"\nPython line coverage: {coverage['covered_lines']}/{coverage['num_statements']}; branch coverage: {coverage['covered_branches']}/{coverage['num_branches']}. No comparable baseline.\n"
    identity = {key: os.environ.get(key) for key in (
        "GITHUB_SHA", "PR_HEAD_SHA", "GITHUB_REF", "GITHUB_EVENT_NAME", "GITHUB_RUN_ID",
        "GITHUB_RUN_ATTEMPT", "GITHUB_REPOSITORY", "GITHUB_JOB")}
    identity.update(platform=platform.platform(), python=platform.python_version())
    metrics["identity"] = identity
    summary += "\n### Candidate and environment\n\n" + "\n".join(
        f"- {key}: <code>{_table_text(str(value or 'unavailable'))}</code>"
        for key, value in identity.items()) + "\n"
    if identity["GITHUB_RUN_ID"]:
        summary += f"\n[Run and artifacts](https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{identity['GITHUB_RUN_ID']})\n"
    summary += "\nPR GITHUB_SHA identifies the tested merge commit; source head is available in the run. Missing or failed reports require inspection of the failing step. No comparable coverage baseline is established.\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.md").write_text(summary, encoding="utf-8")
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    with args.summary.open("a", encoding="utf-8") as stream:
        stream.write(summary)
    if (args.gate_outcome != "success" or metrics["test_report"] != "available"
            or metrics.get("failures", 0) or metrics.get("errors", 0)):
        sys.exit(1)


if __name__ == "__main__":
    main()
