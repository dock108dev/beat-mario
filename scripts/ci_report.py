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
import subprocess
from datetime import datetime, timezone
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
                suite = ET.Element(
                    "testsuite",
                    {
                        "tests": str(len(cases)),
                        "failures": str(
                            sum(c.find("failure") is not None for c in cases)
                        ),
                        "errors": str(sum(c.find("error") is not None for c in cases)),
                        "skipped": str(
                            sum(c.find("skipped") is not None for c in cases)
                        ),
                        "time": str(sum(float(c.get("time", "0")) for c in cases)),
                    },
                )
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
            if (
                not suites
                or counts["tests"] <= 0
                or counts["tests"] != len(cases)
                or any(value < 0 for value in counts.values())
                or not math.isfinite(duration)
                or duration < 0
            ):
                raise ValueError("Empty or inconsistent report")
            for tag, key in (
                ("failure", "failures"),
                ("error", "errors"),
                ("skipped", "skipped"),
            ):
                if sum(case.find(tag) is not None for case in cases) != counts[key]:
                    raise ValueError("Outcome counters disagree with cases")
            if any(
                not math.isfinite(float(case.get("time", "0")))
                or float(case.get("time", "0")) < 0
                for case in cases
            ):
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
            failed = [
                case
                for case in cases
                if case.find("failure") is not None or case.find("error") is not None
            ]
            if failed:
                lines.extend(
                    ["### Failing tests", "", "| Test | Reason |", "|---|---|"]
                )
                for case in failed[:10]:
                    issue = case.find("failure")
                    if issue is None:
                        issue = case.find("error")
                    name = f"{case.get('classname', '')}.{case.get('name', '')}"
                    lines.append(
                        f"| <code>{_table_text(name)}</code> | {_table_text(issue.get('message', 'See retained JUnit/log'))} |"
                    )
                lines.append("")
            if skips:
                lines.extend(
                    ["### Skipped tests", "", "| Count | Reason |", "|---|---|"]
                )
                for reason, count in skips.most_common(10):
                    lines.append(f"| {count} | <code>{_table_text(reason)}</code> |")
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


def required_evidence(folder, checks, required):
    """Check outcomes and artifact contents independently; absent is never success."""
    outcomes, problems = {}, []
    for name in required:
        outcome = checks.get(name, {}).get("outcome", "not run")
        outcomes[name] = outcome
        if outcome != "success":
            problems.append(f"{name}: {outcome}; inspect its step log")
    artifacts = {}
    for name in ("coverage", "build"):
        if name not in required:
            continue
        try:
            value = json.loads((folder / (name + ".json")).read_text())
            if name == "coverage":
                totals = value["totals"]
                for numerator, denominator in (
                    ("covered_lines", "num_statements"),
                    ("covered_branches", "num_branches"),
                ):
                    if (
                        type(totals[numerator]) is not int
                        or type(totals[denominator]) is not int
                        or not 0 <= totals[numerator] <= totals[denominator]
                    ):
                        raise ValueError("Invalid coverage totals")
                if totals["num_statements"] == 0:
                    raise ValueError("Empty coverage scope")
                if ET.parse(folder / "coverage.xml").getroot().tag != "coverage":
                    raise ValueError("Invalid coverage XML")
                artifacts[name] = totals
            else:
                sizes = value["sizes_bytes"]
                if (
                    value["status"] != "PASS"
                    or not sizes
                    or not all(type(n) is int and n > 0 for n in sizes.values())
                ):
                    raise ValueError("Invalid build result")
                artifacts[name] = value
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            ET.ParseError,
        ):
            problems.append(
                f"{name}: required report missing or invalid; inspect its step log"
            )
            artifacts[name] = None
    return outcomes, artifacts, problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--gate-outcome", required=True)
    parser.add_argument("--require-check", action="append", default=[])
    parser.add_argument(
        "--scope", choices=("repository", "worker"), default="repository"
    )
    args = parser.parse_args()
    summary, metrics = build_report(args.report, args.gate_outcome)
    try:
        checks = json.loads(os.environ.get("CHECK_OUTCOMES", "{}"))
        if not isinstance(checks, dict) or not all(
            isinstance(v, dict) for v in checks.values()
        ):
            raise ValueError("Invalid check outcomes")
    except (ValueError, TypeError):
        checks = {}
    outcomes, artifacts, problems = required_evidence(
        args.report.parent, checks, args.require_check
    )
    if metrics.get("test_report") == "available" and metrics.get("passed") == 0:
        problems.append(
            "No passing tests were recorded; inspect suite selection and skips"
        )
    metrics.update(
        schema_version=1,
        recorded_at=datetime.now(timezone.utc).isoformat(),
        checks=outcomes,
        artifacts=artifacts,
        problems=problems,
    )
    if args.scope == "worker":
        summary = summary.split("The gate also checks", 1)[0]
        summary += (
            "Worker behavior only; Python checks and dependency audit are separate.\n"
        )
    if outcomes:
        summary += "\n### Required checks\n\n| Check | Outcome |\n|---|---|\n"
        summary += (
            "\n".join(
                f"| {_table_text(k)} | {_table_text(str(v)).upper()} |"
                for k, v in outcomes.items()
            )
            + "\n"
        )
    if artifacts.get("coverage"):
        totals = artifacts["coverage"]
        summary += f"\nCoverage: {totals['covered_lines']}/{totals['num_statements']} lines; {totals['covered_branches']}/{totals['num_branches']} branches. No comparable baseline.\n"
    for problem in problems:
        summary += "\n- **Blocker:** " + _table_text(problem) + "\n"
    identity = {
        key: os.environ.get(key)
        for key in (
            "GITHUB_SHA",
            "PR_HEAD_SHA",
            "GITHUB_REF",
            "GITHUB_EVENT_NAME",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "GITHUB_REPOSITORY",
            "GITHUB_JOB",
            "SOURCE_WORKTREE_DIGEST",
        )
    }
    identity.update(platform=platform.platform(), python=platform.python_version())
    for tool in ("node", "uv"):
        try:
            version = subprocess.run(
                [tool, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            identity[tool] = version.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            identity[tool] = None
    identity["source_worktree_digest"] = os.environ.get("SOURCE_WORKTREE_DIGEST")
    metrics["identity"] = identity
    summary += (
        "\n### Candidate and environment\n\n"
        + "\n".join(
            f"- {key}: <code>{_table_text(str(value or 'unavailable'))}</code>"
            for key, value in identity.items()
        )
        + "\n"
    )
    if identity["GITHUB_RUN_ID"]:
        summary += f"\n[Run and artifacts](https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{identity['GITHUB_RUN_ID']})\n"
    summary += "\nPR GITHUB_SHA identifies the tested merge commit; source head is available in the run. Missing or failed reports require inspection of the failing step. No comparable coverage baseline is established.\n"
    metrics["overall"] = (
        "FAIL"
        if (
            problems
            or args.gate_outcome != "success"
            or metrics["test_report"] != "available"
            or metrics.get("failures", 0)
            or metrics.get("errors", 0)
        )
        else "PASS"
    )
    summary += "\nReported scope result: **" + metrics["overall"] + "**\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.md").write_text(summary, encoding="utf-8")
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    with args.summary.open("a", encoding="utf-8") as stream:
        stream.write(summary)
    if (
        problems
        or args.gate_outcome != "success"
        or metrics["test_report"] != "available"
        or metrics.get("failures", 0)
        or metrics.get("errors", 0)
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()
