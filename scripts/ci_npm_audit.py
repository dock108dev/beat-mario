"""Retain npm audit findings and fail on high/critical findings or unavailable data."""

import argparse
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = subprocess.run(
            ["npm", "audit", "--prefix", "minecraft-worker", "--omit=dev", "--json"],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result = subprocess.CompletedProcess(
            [], 2, json.dumps({"error": {"type": type(exc).__name__}}), ""
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.stdout)
    try:
        report = json.loads(result.stdout)
        counts = report["metadata"]["vulnerabilities"]
        valid = (
            result.returncode in (0, 1)
            and not report.get("error")
            and all(
                isinstance(counts[k], int) and counts[k] >= 0
                for k in ("low", "moderate", "high", "critical")
            )
        )
    except (ValueError, KeyError, TypeError):
        valid = False
    summary = "## npm dependency audit\n\n"
    summary += (
        f"Findings: low {counts['low']}, moderate {counts['moderate']}, high {counts['high']}, critical {counts['critical']}.\n"
        if valid
        else "UNAVAILABLE: inspect audit output; no clean result is inferred.\n"
    )
    summary += "\nRegistry advisories at run time; no historical baseline. High/critical findings fail this scheduled/manual check.\n"
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
            stream.write(summary)
    else:
        print(summary)
    return 0 if valid and not counts["high"] and not counts["critical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
