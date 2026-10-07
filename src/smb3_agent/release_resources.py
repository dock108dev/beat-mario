"""Release allowlist: authored contracts/controllers and eligible calibration evidence."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

DAY2_PROFILE = "artifacts/b3-engineering/20260925-integrated/profile-qualified-v1.json"
LUA = (
    "fceux_1_1_agent.lua",
    "fceux_b2_plan.lua",
    "fceux_live_observer.lua",
    "fceux_live_takeover.lua",
    "fceux_demonstration.lua",
)


def _relocate_resource_values(value, mapping):
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [_relocate_resource_values(item, mapping) for item in value]
    if isinstance(value, dict):
        return {
            _relocate_resource_values(key, mapping): _relocate_resource_values(
                item, mapping
            )
            for key, item in value.items()
        }
    return value


def stage_resources(root: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=False)
    records = []

    def copy_resource(source, relative, role):
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Required resource unavailable: {source}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        records.append(
            {
                "path": str(relative),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "role": role,
            }
        )

    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "data", "public/assets/favicon.svg"],
        cwd=root,
        text=True,
    ).split("\0")
    for relative in tracked:
        if (
            not relative
            or relative.endswith(".gitkeep")
            or relative.startswith(
                ("data/experimental-adapters/fixture-quest/", "data/fixtures/")
            )
        ):
            continue
        copy_resource(root / relative, Path(relative), "app-owned tracked contract")
    contract = "data/companion/local-candidate.yaml"
    if contract not in tracked:
        copy_resource(
            root / contract, Path(contract), "current initial-beta capability contract"
        )
    for name in LUA:
        copy_resource(
            root / "scripts" / name,
            Path("scripts") / name,
            "required FCEUX controller/helper",
        )
    # Frozen farm and display features have different eligibility rules.
    # Share only value relocation; each profile gets its own path mapping.
    original = json.loads((root / DAY2_PROFILE).read_text())
    evidence = original["evidence_hashes"]
    mapping = {}
    for index, (name, digest) in enumerate(sorted(evidence.items())):
        source = Path(name)
        if not source.is_relative_to(
            root / "artifacts/b3-engineering"
        ) or source.suffix not in {".png", ".json", ".log"}:
            raise ValueError("Calibration eligibility refused: " + name)
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError("Calibration evidence changed: " + name)
        relative = Path("data/calibration/day2") / f"{index:03d}{source.suffix}"
        copy_resource(
            source,
            relative,
            "retained calibration evidence; no packaged gameplay acceptance",
        )
        mapping[name] = "gc-resource:" + str(relative)
    profile = destination / "data/calibration/day2/profile.json"
    profile.write_text(
        json.dumps(_relocate_resource_values(original, mapping), indent=2) + "\n"
    )
    records.append(
        {
            "path": "data/calibration/day2/profile.json",
            "sha256": hashlib.sha256(profile.read_bytes()).hexdigest(),
            "role": "portable retained Day 2 calibration",
        }
    )
    view_source = (
        root
        / "artifacts/gc-delivery/ordinary-session/20261006-recovery/view-feature-calibration/profile.json"
    )
    if view_source.is_file():
        original = json.loads(view_source.read_text())
        mapping = {}
        for index, (name, digest) in enumerate(
            sorted(original["evidence_hashes"].items())
        ):
            source = Path(name)
            if (
                not source.is_relative_to(
                    root / "artifacts/gc-delivery/ordinary-session/20261006-recovery"
                )
                or source.suffix not in {".png", ".json"}
                or (
                    source.suffix == ".json"
                    and source.name != "native-terrain-feature-probe.json"
                )
                or hashlib.sha256(source.read_bytes()).hexdigest() != digest
            ):
                raise ValueError("Visible display feature eligibility refused: " + name)
            relative = (
                Path("data/calibration/view-settings") / f"{index:03d}{source.suffix}"
            )
            copy_resource(
                source,
                relative,
                "ordinary native UI feature evidence; no packaged gameplay acceptance",
            )
            mapping[name] = "gc-resource:" + str(relative)
        profile = destination / "data/calibration/view-settings/profile.json"
        profile.write_text(
            json.dumps(_relocate_resource_values(original, mapping), indent=2) + "\n"
        )
        records.append(
            {
                "path": "data/calibration/view-settings/profile.json",
                "sha256": hashlib.sha256(profile.read_bytes()).hexdigest(),
                "role": "portable visible display-setting features",
            }
        )
    return records
