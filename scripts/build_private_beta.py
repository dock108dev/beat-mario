"""Build a local review candidate with explicit controllers and calibration provenance."""

import argparse
import hashlib
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
from importlib.metadata import version as distribution_version
from pathlib import Path

from smb3_agent.beta_readiness import source_identity
from smb3_agent.player_store import VERSION
from smb3_agent.release_resources import stage_resources


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=VERSION)
    parser.add_argument("--build", default="30035")
    parser.add_argument(
        "--sign-identity",
        required=True,
        help="Existing stable code-signing identity; ad-hoc delivery is refused",
    )
    args = parser.parse_args(argv)
    if args.sign_identity == "-":
        parser.error("Delivered updates require a stable certificate identity")
    version = args.version
    if not version or "/" in version or ".." in version or not args.build.isdigit():
        parser.error("Invalid version/build")
    root = Path(__file__).resolve().parents[1]
    output = root / "dist/private-beta" / version
    if output.exists():
        raise SystemExit(
            "Retained candidate output already exists; choose a successor version"
        )
    work = root / "build/private-beta" / version
    work.mkdir(parents=True, exist_ok=True)
    resources = work / "resources"
    if resources.exists():
        shutil.rmtree(resources)
    inventory = stage_resources(root, resources)
    ocr = Path(shutil.which("tesseract") or "/opt/homebrew/bin/tesseract").resolve(
        strict=True
    )
    ocr_prefix = ocr.parent.parent
    ocr_data = ocr_prefix / "share/tessdata/eng.traineddata"
    ocr_license = ocr_prefix / "LICENSE"
    for item in (ocr, ocr_data, ocr_license):
        if not item.is_file():
            raise SystemExit("OCR packaging prerequisite missing: " + str(item))
    manifest = source_identity(root)
    manifest.update(
        version=version,
        architecture=platform.machine(),
        python=sys.version,
        build=args.build,
        capability_contract="game-companion-local-candidate/v1",
        required_capabilities=[
            "mario-world1-1-adaptive-early-segment",
            "stardew-selected-session-watering-return",
        ],
        experimental_unavailable=["reconnaissance", "recording", "wider-gameplay"],
        qualification="reviewable candidate; packaged two-game qualification pending",
        resources=inventory,
        runtime_dependencies={
            name: distribution_version(name)
            for name in (
                "numpy",
                "Pillow",
                "PyYAML",
                "mss",
                "pyautogui",
                "pyobjc",
                "PyInstaller",
            )
        },
        ocr_resources={
            "tesseract": hashlib.sha256(ocr.read_bytes()).hexdigest(),
            "english_data": hashlib.sha256(ocr_data.read_bytes()).hexdigest(),
            "license": hashlib.sha256(ocr_license.read_bytes()).hexdigest(),
        },
        installed_app_path=str(Path.home() / "Applications/Game Companion.app"),
        update_policy="verified stable designated requirement; archive previous installation; retain versioned packages",
        external_prerequisites=[
            "owner-selected supported Mario ROM",
            "FCEUX",
            "Codex CLI and existing sign-in",
            "inspected Stardew installation",
            "game-created default-location save copied in isolation; frozen Day 2 seed for regression only",
            "macOS input and capture permissions",
        ],
        native_smoke="See adjacent qualification.json for exact candidate evidence",
        signing="local development identity; not notarized",
    )
    manifest_path = work / "build-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    entry = work / "entry.py"
    entry.write_text("from smb3_agent.app_runtime import main\nmain()\n")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "Game Companion",
        "--osx-bundle-identifier",
        "local.gamecompanion.privatebeta",
        "--distpath",
        str(output),
        "--workpath",
        str(work / "pyinstaller"),
        "--specpath",
        str(work),
        "--paths",
        str(root / "src"),
        "--collect-submodules",
        "smb3_agent",
        "--add-data",
        f"{resources}:resources",
        "--add-data",
        f"{manifest_path}:resources",
        "--add-data",
        f"{root / 'docs/private-beta-quick-start.md'}:resources",
        "--add-binary",
        f"{ocr}:ocr",
        "--add-data",
        f"{ocr_data}:ocr/tessdata",
        "--add-data",
        f"{ocr_license}:licenses/tesseract",
        str(entry),
    ]
    build_env = dict(os.environ)
    if Path("/Library/Developer/CommandLineTools").is_dir():
        build_env["DEVELOPER_DIR"] = "/Library/Developer/CommandLineTools"
    subprocess.run(command, cwd=root, env=build_env, check=True)
    app = output / "Game Companion.app"
    plist_path = app / "Contents/Info.plist"
    info = plistlib.loads(plist_path.read_bytes())
    info.update(
        CFBundleShortVersionString=version.split("-")[0],
        CFBundleVersion=args.build,
        NSHighResolutionCapable=True,
        NSAppleEventsUsageDescription="Game Companion selects your declared game window.",
    )
    plist_path.write_bytes(plistlib.dumps(info))
    subprocess.run(
        [
            "/usr/bin/codesign",
            "--force",
            "--sign",
            args.sign_identity,
            "--timestamp=none",
            str(app),
        ],
        env=build_env,
        check=True,
    )
    subprocess.run(
        ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)],
        env=build_env,
        check=True,
    )
    signature_result = subprocess.run(
        ["/usr/bin/codesign", "-d", "-r-", str(app)],
        capture_output=True,
        text=True,
        check=True,
    )
    requirement = signature_result.stdout + signature_result.stderr
    designated = next(
        line.split("designated => ", 1)[1]
        for line in requirement.splitlines()
        if line.startswith("designated => ")
    )
    if "cdhash" in designated or "anchor apple" not in designated:
        raise SystemExit(
            "Unstable delivered designated requirement; installation refused"
        )
    (output / "signing-receipt.json").write_text(
        json.dumps(
            {
                "designated_requirement": designated,
                "bundle_identifier": "local.gamecompanion.privatebeta",
                "stable": True,
            },
            indent=2,
        )
        + "\n"
    )
    shutil.copy2(root / "docs/private-beta-quick-start.md", output / "Quick Start.md")
    shutil.copy2(manifest_path, output / "build-manifest.json")
    print(app)


if __name__ == "__main__":
    main()
