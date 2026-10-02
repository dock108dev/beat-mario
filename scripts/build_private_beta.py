"""Build an offline review app. Bundles no game assets, saves or engineering receipts."""

from pathlib import Path
import json
import os
import plistlib
import shutil
import platform
import subprocess
import sys

from smb3_agent.beta_readiness import source_identity
from smb3_agent.player_store import VERSION
from smb3_agent.minecraft_session import CHECKED_FEATURES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/private-beta" / VERSION
WORK = ROOT / "build/private-beta" / VERSION
WORK.mkdir(parents=True, exist_ok=True)
manifest = source_identity(ROOT)
manifest.update(
    version=VERSION,
    architecture=platform.machine(),
    python=sys.version,
    native_minecraft=dict(CHECKED_FEATURES),
    native_smoke="See adjacent native-smoke-result.json and Owner Review.md for exact evidence",
    signing="local ad-hoc; not notarized",
)
manifest_path = WORK / "build-manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
entry = WORK / "entry.py"
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
    str(OUT),
    "--workpath",
    str(WORK / "pyinstaller"),
    "--specpath",
    str(WORK),
    "--paths",
    str(ROOT / "src"),
    "--collect-submodules",
    "smb3_agent",
    "--add-data",
    f"{ROOT / 'data'}:resources/data",
    "--add-data",
    f"{ROOT / 'public'}:resources/public",
    "--add-data",
    f"{manifest_path}:resources",
    "--add-data",
    f"{ROOT / 'docs/private-beta-quick-start.md'}:resources",
    "--add-binary",
    "/opt/homebrew/bin/tesseract:ocr",
    "--add-data",
    "/opt/homebrew/share/tessdata/eng.traineddata:ocr/tessdata",
    "--add-data",
    "/opt/homebrew/Cellar/tesseract/5.5.1/LICENSE:licenses/tesseract",
    str(entry),
]
build_env = dict(os.environ)
if Path("/Library/Developer/CommandLineTools").is_dir():
    build_env["DEVELOPER_DIR"] = "/Library/Developer/CommandLineTools"
subprocess.run(command, cwd=ROOT, env=build_env, check=True)
app = OUT / "Game Companion.app"
plist_path = app / "Contents/Info.plist"
info = plistlib.loads(plist_path.read_bytes())
info.update(
    CFBundleShortVersionString="0.2.0",
    CFBundleVersion="20002",
    NSHighResolutionCapable=True,
)
plist_path.write_bytes(plistlib.dumps(info))
subprocess.run(
    ["/usr/bin/codesign", "--force", "--sign", "-", str(app)], env=build_env, check=True
)
subprocess.run(
    ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)],
    env=build_env,
    check=True,
)
shutil.copy2(ROOT / "docs/private-beta-quick-start.md", OUT / "Quick Start.md")
shutil.copy2(manifest_path, OUT / "build-manifest.json")
print(app)
