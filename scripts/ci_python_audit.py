"""Audit locked Python dependencies without installing the project or changing its lock."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

VERSION = "2.9.0"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "tool": f"pip-audit {VERSION}",
        "status": "UNAVAILABLE",
        "findings": None,
        "severity": "not supplied by tool",
        "baseline": None,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "scope": "uv.lock all extras; current runner platform markers",
    }
    code = 1
    with tempfile.TemporaryDirectory(prefix="gc-python-audit-") as folder:
        requirements = Path(folder) / "requirements.txt"
        report = Path(folder) / "audit.json"
        try:
            subprocess.run(
                [
                    "uv",
                    "export",
                    "--locked",
                    "--all-extras",
                    "--no-emit-project",
                    "--output-file",
                    str(requirements),
                ],
                check=True,
                timeout=120,
                stdout=subprocess.DEVNULL,
            )
            process = subprocess.run(
                [
                    "uvx",
                    "--python",
                    sys.executable,
                    "--from",
                    f"pip-audit=={VERSION}",
                    "pip-audit",
                    "--require-hashes",
                    "--no-deps",
                    "--disable-pip",
                    "-r",
                    str(requirements),
                    "--format",
                    "json",
                    "--output",
                    str(report),
                ],
                timeout=240,
                check=False,
            )
            raw = json.loads(report.read_text())
            dependencies = raw["dependencies"]
            if process.returncode not in (0, 1) or not dependencies:
                raise ValueError("Incomplete audit")
            if any(
                "vulns" not in d or not isinstance(d["vulns"], list)
                for d in dependencies
            ):
                raise ValueError("Skipped or malformed dependency result")
            count = sum(len(d["vulns"]) for d in dependencies)
            if (process.returncode == 0) != (count == 0):
                raise ValueError("Audit outcome mismatch")
            result.update(
                status="FAIL" if count else "PASS", findings=count, report=raw
            )
            code = 1 if count else 0
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            subprocess.SubprocessError,
        ) as exc:
            result["reason"] = type(exc).__name__
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    summary = (
        f"\n## Python dependency audit\n\n{result['status']}: "
        f"{result['findings'] if result['findings'] is not None else 'unavailable'} findings. "
        "All known findings fail; severity is not supplied. No historical baseline. "
        "PyPI advisory data at request time; current platform only.\n"
    )
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
            stream.write(summary)
    else:
        print(summary)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
