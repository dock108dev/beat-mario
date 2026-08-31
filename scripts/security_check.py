from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


SENSITIVE_SUFFIXES = {
    ".nes",
    ".fds",
    ".sav",
    ".state",
    ".fc0",
    ".fc1",
    ".fc2",
    ".fm2",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
}
HIGH_CONFIDENCE_SECRET_PATTERNS = {
    "private key": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    ),
    "AWS access key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "Google API key": re.compile(rb"AIza[0-9A-Za-z_-]{35}"),
    "Slack token": re.compile(rb"xox[baprs]-[0-9A-Za-z-]{20,}"),
}


def tracked_files() -> tuple[Path, ...]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return tuple(
        Path(raw.decode("utf-8", errors="strict"))
        for raw in completed.stdout.split(b"\0")
        if raw
    )


def matched_secret_labels(path: Path) -> tuple[str, ...]:
    labels: set[str] = set()
    tail = b""
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            window = tail + chunk
            labels.update(
                label
                for label, pattern in HIGH_CONFIDENCE_SECRET_PATTERNS.items()
                if pattern.search(window)
            )
            tail = window[-128:]
    return tuple(sorted(labels))


def main() -> int:
    has_findings = False
    for path in tracked_files():
        if path.suffix.lower() in SENSITIVE_SUFFIXES:
            has_findings = True
        try:
            matched = matched_secret_labels(path)
        except OSError:
            has_findings = True
            continue
        if matched:
            has_findings = True

    if has_findings:
        print(
            "Security hygiene check failed; review tracked files locally.",
            file=sys.stderr,
        )
        return 1
    print("Tracked credential and game-asset scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
