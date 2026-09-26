"""Versioned beta readiness, independent of the historical V2 campaign gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import yaml

from smb3_agent.paths import repository_path


CONTRACT_PATH = repository_path("data/scenarios/personal-beta-v3.yaml")
MANIFEST_SCHEMA = "game-companion-beta-evidence/v3"


def source_identity(root: Path | None = None) -> dict[str, Any]:
    root = root or repository_path("")
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=root, text=True)
    paths = set(git("ls-files", "-z").split("\0"))
    paths.update(git("ls-files", "--others", "--exclude-standard", "-z").split("\0"))
    files = {path: hashlib.sha256((root / path).read_bytes()).hexdigest()
             for path in sorted(paths) if path and (root / path).is_file()}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"head": git("rev-parse", "HEAD").strip(), "source_sha256": digest,
            "working_tree": git("status", "--short"), "files": files}


def inspect_beta(manifest: dict[str, Any] | None = None, *, evidence_root: Path | None = None,
                 candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = yaml.safe_load(CONTRACT_PATH.read_text())
    manifest = manifest or {}
    candidate = candidate or source_identity()
    failures: dict[str, list[str]] = {}
    records = manifest.get("checks", {})
    manifest_ok = (
        manifest.get("schema_version") == MANIFEST_SCHEMA
        and manifest.get("source_sha256") == candidate["source_sha256"]
        and manifest.get("head") == candidate["head"]
        and manifest.get("contract_sha256") == hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest()
    )
    root = (evidence_root or Path.cwd()).resolve()
    for stage, requirements in contract["stages"].items():
        missing = []
        for requirement in requirements:
            check_id = requirement["id"]
            record = records.get(check_id, {})
            valid = manifest_ok and record.get("status") == "pass"
            valid = valid and record.get("classification") == requirement["classification"]
            valid = valid and bool(record.get("artifacts"))
            for artifact in record.get("artifacts", []):
                try:
                    relative = Path(artifact["path"])
                    path = (root / relative).resolve()
                    valid = valid and not relative.is_absolute() and path.is_relative_to(root)
                    valid = valid and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
                except (KeyError, TypeError, OSError, ValueError):
                    valid = False
            if not valid:
                missing.append(check_id)
        failures[stage] = missing
    b2_failures = [f"{stage}: {item}" for stage, values in failures.items()
                   if stage.startswith("B2.") for item in values]
    b3_failures = [f"B3: {item}" for item in failures.get("B3", [])]
    all_failures = [f"{stage}: {item}" for stage, values in failures.items() for item in values]
    # A manifest cannot supply owner review via a unit test or an absent decision.
    owner_decision = manifest.get("owner_acceptance")
    owner_ok = owner_decision == "ACCEPT PERSONAL BETA" and not failures["B9"]
    return {
        "schema_version": "game-companion-beta-readiness/v3",
        "source_sha256": candidate["source_sha256"],
        "manifest_matches_candidate": manifest_ok,
        "b2_complete": not b2_failures,
        "ready_for_b3": not b2_failures,
        "b3_complete": not b3_failures,
        "ready_for_b4": not b3_failures,
        "first_unmet_b3_requirement": b3_failures[0] if b3_failures else None,
        "b6_technical_complete": not failures["B6"],
        "b7_guidance_complete": not failures["B7"],
        "b8_delivery_ready": not any(values for stage, values in failures.items() if stage != "B9"),
        "ready_for_b9": not any(values for stage, values in failures.items() if stage != "B9"),
        "beta_ready": not all_failures and owner_ok,
        "owner_usefulness": manifest.get("owner_usefulness"),
        "first_unmet_b2_requirement": b2_failures[0] if b2_failures else None,
        "remaining": failures,
        "owner_acceptance": owner_decision,
        "third_game_onboarding_required": False,
        "proof_limits": contract["proof_limits"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--gate-b2", action="store_true")
    parser.add_argument("--gate-b3", action="store_true")
    parser.add_argument("--identity", action="store_true")
    args = parser.parse_args()
    if args.identity:
        print(json.dumps(source_identity(), indent=2))
        return
    manifest = json.loads(args.manifest.read_text()) if args.manifest else None
    result = inspect_beta(manifest, evidence_root=args.evidence_root)
    print(json.dumps(result, indent=2))
    if args.gate_b2 and not result["b2_complete"]:
        raise SystemExit(1)
    if args.gate_b3 and not result["b3_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
