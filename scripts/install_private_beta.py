"""Install a verified retained package at one stable path; archive old updates."""

import argparse
import json
import plistlib
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def verify(app):
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    result = subprocess.run(
        ["codesign", "-d", "-r-", str(app)], capture_output=True, text=True, check=True
    )
    requirement = next(
        row.split("designated => ", 1)[1]
        for row in (result.stdout + result.stderr).splitlines()
        if row.startswith("designated => ")
    )
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    if (
        info["CFBundleIdentifier"] != "local.gamecompanion.privatebeta"
        or "cdhash" in requirement
        or "anchor apple" not in requirement
    ):
        raise RuntimeError("Stable certificate app identity required")
    return requirement


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    args = parser.parse_args(argv)
    package = args.package.resolve(strict=True)
    source = package / "Game Companion.app"
    destination = Path.home() / "Applications/Game Companion.app"
    manifest = json.loads((package / "build-manifest.json").read_text())

    requirement = verify(source)
    running = subprocess.run(
        ["pgrep", "-f", str(destination / "Contents/MacOS/Game Companion")],
        capture_output=True,
    )
    if running.returncode == 0:
        raise SystemExit("Quit the installed companion before updating")
    destination.parent.mkdir(exist_ok=True)
    staged = destination.parent / (
        "Game Companion.update-" + manifest["build"] + ".app"
    )
    if staged.exists():
        raise SystemExit("Staged update exists; retain and inspect it before retrying")
    shutil.copytree(source, staged, symlinks=True)
    if verify(staged) != requirement:
        raise RuntimeError(
            "Staged identity differs; update withheld and staged copy retained"
        )
    archive = None
    if destination.exists():
        if verify(destination) != requirement:
            raise SystemExit(
                "Installed identity differs; update withheld for supported permission migration"
            )
        archive = (
            destination.parent
            / "Game Companion retained updates"
            / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            / "Game Companion.app"
        )
        archive.parent.mkdir(parents=True)
        destination.rename(archive)
    try:
        staged.rename(destination)
    except Exception:
        if archive:
            archive.rename(destination)
        raise
    receipt = {
        "version": manifest["version"],
        "build": manifest["build"],
        "installed_path": str(destination),
        "designated_requirement": requirement,
        "previous_app": str(archive) if archive else None,
        "data_modified": False,
        "permission_access_verified": False,
    }
    (package / "installation-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )
    print(destination)


if __name__ == "__main__":
    main()
