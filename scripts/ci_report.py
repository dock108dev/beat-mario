"""Summarize offline CI tests without requiring extra packages or GitHub permissions."""

from __future__ import annotations

import argparse
from collections import Counter
from html import escape
import json
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
            "Security results: see the separate dependency-review and managed CodeQL checks. Line/branch coverage and native Mac/gameplay acceptance are not measured here.",
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
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.md").write_text(summary, encoding="utf-8")
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    with args.summary.open("a", encoding="utf-8") as stream:
        stream.write(summary)


if __name__ == "__main__":
    main()
