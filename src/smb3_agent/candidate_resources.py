"""Portable calibration assets and an explicit owner-selected prepared seed."""

import hashlib
import json
import secrets
import shutil
from pathlib import Path

from smb3_agent.paths import repository_path

SEED_SHA256 = "1a71568b81ebb901c5fc289d4c2bfb0972db8c05325463a7487dad549eae3128"


def resolve_resource_values(value):
    if isinstance(value, str) and value.startswith("gc-resource:"):
        relative = Path(value.removeprefix("gc-resource:"))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid bundled resource path")
        return str(repository_path(relative).resolve())
    if isinstance(value, list):
        return [resolve_resource_values(item) for item in value]
    if isinstance(value, dict):
        return {
            resolve_resource_values(key): resolve_resource_values(item)
            for key, item in value.items()
        }
    return value


def calibration_registration():
    manifest = repository_path("data/calibration/day2/profile.json")
    if not manifest.is_file():
        return None
    return {
        "manifest": str(manifest.resolve()),
        "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
    }


def import_day2_seed(source):
    """Copy only the explicitly selected exact seed; never search primary saves."""
    from smb3_agent.stardew_adapter import StardewAdapterError, _tree_identity

    selected = Path(source).expanduser().absolute()
    if (
        not selected.is_dir()
        or selected != selected.resolve()
        or any(p.is_symlink() for p in selected.rglob("*"))
    ):
        raise StardewAdapterError(
            "Choose the original prepared Day 2 seed directory; aliases are refused."
        )
    if _tree_identity(selected)[0] != SEED_SHA256:
        raise StardewAdapterError(
            "This is not the supported unchanged Day 2 seed. No copy was registered."
        )
    target = (
        Path("artifacts/stardew-engineering").resolve()
        / ("import-" + secrets.token_hex(12))
        / "prepared-sources"
        / selected.name
    )
    target.parent.mkdir(parents=True, exist_ok=False)
    shutil.copytree(selected, target)
    if _tree_identity(target)[0] != SEED_SHA256:
        raise StardewAdapterError(
            "Prepared seed changed while copying; retained copy is not registered."
        )
    registry = Path("artifacts/stardew-prepared-farms.json")
    rows = json.loads(registry.read_text()) if registry.is_file() else []
    rows = [row for row in rows if row.get("id") != "pilot-day2"]
    rows.append(
        {
            "id": "pilot-day2",
            "label": "Pilot / B3Test · Day 2 · 15 dry crops",
            "source": str(target),
            "tree_sha256": SEED_SHA256,
        }
    )
    temporary = registry.with_suffix("." + secrets.token_hex(8) + ".tmp")
    temporary.write_text(json.dumps(rows, indent=2) + "\n")
    temporary.replace(registry)
    return rows[-1]
