from __future__ import annotations

import difflib
import hashlib
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml


LOGGER = logging.getLogger(__name__)
PATCH_SCHEMA_VERSION = "beat-mario.route-patch/v1"
PATCH_ARTIFACTS_ROOT = Path("artifacts/route-patches")
PATCH_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
MAX_FILE_BYTES = 1_000_000
MAX_PATCH_BYTES = 2_000_000
MAX_CHANGED_FILES = 24
MAX_RECORD_BYTES = 4_000_000
VALIDATION_SIDES = {"parent", "candidate"}
VALIDATION_GATE_NAMES = {
    "documentation_static",
    "canonical_phase",
    "rank27_5_of_5",
    "rank28_3_of_3",
}
WORKTREE_NAMES = {"candidate-worktree", "parent-worktree"}

SUPPORTED_TEXT_SUFFIXES = {
    ".json",
    ".lua",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
DENIED_SUFFIXES = {
    ".7z",
    ".bin",
    ".fc0",
    ".fc1",
    ".fm2",
    ".gif",
    ".gz",
    ".jpeg",
    ".jpg",
    ".log",
    ".nes",
    ".png",
    ".rom",
    ".sav",
    ".state",
    ".tar",
    ".zip",
}
DENIED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "artifacts",
    "caches",
    "screenshots",
}
DENIED_PREFIXES = (
    "data/attempts/",
    "data/fixtures/state/",
    "data/screenshots/",
    "public/assets/local/",
)
PROTECTED_VALIDATION_FILES = {"scripts/validate_phase0.sh"}
FORBIDDEN_DECLARATION_KEYS = {
    "approval",
    "approval_result",
    "approved",
    "argv",
    "command",
    "review_result",
    "reviewed",
    "reviewed_at",
    "shell",
    "validated",
    "validated_at",
    "validation_command",
    "validation_result",
}
LIFECYCLE_TRANSITIONS = {
    "imported": {"reviewed", "rejected"},
    "reviewed": {"prepared", "rejected", "failed"},
    "prepared": {"applied_to_candidate", "failed"},
    "applied_to_candidate": {"validated", "failed"},
    "validated": {"promoted", "failed"},
    "promoted": {"rolled_back"},
    "rolled_back": set(),
    "rejected": set(),
    "failed": set(),
}


class RoutePatchError(ValueError):
    pass


@dataclass(frozen=True)
class RoutePatchResult:
    patch_id: str
    status: str
    patch_dir: Path
    artifact_path: Path
    details: dict[str, Any]

    def to_text(self) -> str:
        lines = [
            f"patch_id={self.patch_id}",
            f"status={self.status}",
            f"patch_dir={self.patch_dir}",
            f"artifact={self.artifact_path}",
        ]
        for key in (
            "variant_id",
            "validation_profile",
            "base_commit",
            "diff_sha256",
            "candidate_path",
            "source_session",
            "source_issue",
            "application_allowed",
            "recommendation",
            "promotion_eligible",
            "rollback_available",
        ):
            if key in self.details:
                value = self.details[key]
                if isinstance(value, bool):
                    value = str(value).lower()
                lines.append(f"{key}={value}")
        changed_files = self.details.get("changed_files")
        if isinstance(changed_files, list):
            lines.append(f"changed_files={','.join(str(item) for item in changed_files)}")
        for label in ("preimage_sha256", "expected_postimage_sha256", "postimage_sha256"):
            hashes = self.details.get(label)
            if isinstance(hashes, dict):
                lines.extend(f"{label}[{path}]={value}" for path, value in hashes.items())
        blockers = self.details.get("blockers")
        if isinstance(blockers, list):
            lines.extend(f"blocker={item}" for item in blockers)
        exact_diff = self.details.get("exact_diff")
        if isinstance(exact_diff, str):
            lines.extend(("diff_begin", exact_diff.rstrip("\n"), "diff_end"))
        return "\n".join(lines)


def import_route_patch(
    patch_path: Path,
    *,
    repo_root: Path | None = None,
    artifacts_root: Path = PATCH_ARTIFACTS_ROOT,
    actor: str = "cli",
) -> RoutePatchResult:
    repo_root = _repo_root(repo_root)
    artifacts_root = _artifact_root(repo_root, artifacts_root)
    patch_path = _safe_input_path(repo_root, patch_path, "patch document")
    raw = _read_patch_yaml(patch_path)
    contract = _normalize_contract(raw, repo_root)
    patch_id = contract["patch_id"]
    patch_dir = artifacts_root / patch_id
    if patch_dir.exists():
        raise RoutePatchError(f"Patch already imported: {patch_id}")

    contract_path = patch_dir / "contract.yaml"
    state_path = patch_dir / "state.yaml"
    imported_at = _now()
    contract["lifecycle"] = {"status": "imported", "imported_at": imported_at}
    state = {
        "schema_version": "beat-mario.route-patch-state/v1",
        "patch_id": patch_id,
        "status": "imported",
        "updated_at": imported_at,
        "history": [
            {
                "from": None,
                "to": "imported",
                "at": imported_at,
                "actor": actor,
                "artifact": "contract.yaml",
            }
        ],
    }
    _atomic_write_yaml(contract_path, contract)
    _atomic_write_yaml(state_path, state)
    return _result(contract, state, patch_dir, contract_path)


def review_route_patch(
    patch_id: str,
    *,
    repo_root: Path | None = None,
    artifacts_root: Path = PATCH_ARTIFACTS_ROOT,
    sessions_root: Path = Path("artifacts/sessions"),
    actor: str = "cli",
) -> RoutePatchResult:
    repo_root, patch_dir, contract, state = _load_record(patch_id, repo_root, artifacts_root)
    _require_status(state, "imported")
    sessions_root = _artifact_root(repo_root, sessions_root)
    source_evidence = _verify_reviewed_source(contract, repo_root, sessions_root)
    reviewed_at = _now()
    review = {
        "schema_version": "beat-mario.route-patch-review/v1",
        "patch_id": patch_id,
        "decision": "reviewed",
        "reviewed_at": reviewed_at,
        "reviewed_by": actor,
        "source_evidence": source_evidence,
        "allowed_files": contract["allowed_files"],
        "validation_profile": contract["validation_profile"],
        "contract_sha256": _sha256_file(patch_dir / "contract.yaml"),
    }
    review_path = patch_dir / "review.yaml"
    _atomic_write_yaml(review_path, review)
    _transition(state, "reviewed", actor=actor, artifact=review_path.name)
    _atomic_write_yaml(patch_dir / "state.yaml", state)
    return _result(contract, state, patch_dir, review_path)


def reject_route_patch(
    patch_id: str,
    reason: str,
    *,
    repo_root: Path | None = None,
    artifacts_root: Path = PATCH_ARTIFACTS_ROOT,
    actor: str = "cli",
) -> RoutePatchResult:
    if not reason.strip():
        raise RoutePatchError("A rejection reason is required")
    repo_root, patch_dir, contract, state = _load_record(patch_id, repo_root, artifacts_root)
    if state["status"] not in {"imported", "reviewed"}:
        raise RoutePatchError(f"Patch cannot be rejected from state: {state['status']}")
    rejection_path = patch_dir / "rejection.yaml"
    _atomic_write_yaml(
        rejection_path,
        {
            "schema_version": "beat-mario.route-patch-rejection/v1",
            "patch_id": patch_id,
            "reason": reason.strip(),
            "rejected_at": _now(),
            "rejected_by": actor,
        },
    )
    _transition(state, "rejected", actor=actor, artifact=rejection_path.name)
    _atomic_write_yaml(patch_dir / "state.yaml", state)
    return _result(contract, state, patch_dir, rejection_path)


def preview_route_patch(
    patch_id: str,
    *,
    repo_root: Path | None = None,
    artifacts_root: Path = PATCH_ARTIFACTS_ROOT,
) -> RoutePatchResult:
    repo_root, patch_dir, contract, state = _load_record(patch_id, repo_root, artifacts_root)
    diff_text = _contract_diff(contract, repo_root)
    blockers = _promotion_blockers(contract, state, repo_root, patch_dir)
    details = {
        "variant_id": contract["variant_id"],
        "source_session": contract["source"]["session_id"],
        "source_issue": contract["source"]["issue_id"],
        "base_commit": contract["repository_base_commit"],
        "changed_files": _changed_files(contract),
        "preimage_sha256": contract["preimage_sha256"],
        "expected_postimage_sha256": contract["expected_postimage_sha256"],
        "validation_profile": contract["validation_profile"],
        "diff_sha256": _sha256_bytes(diff_text.encode("utf-8")),
        "exact_diff": diff_text,
        "application_allowed": state["status"] == "reviewed",
        "promotion_eligible": not blockers,
        "rollback_available": state["status"] == "promoted",
        "blockers": blockers,
    }
    return RoutePatchResult(patch_id, state["status"], patch_dir, patch_dir / "contract.yaml", details)


def prepare_route_patch(
    patch_id: str,
    *,
    repo_root: Path | None = None,
    artifacts_root: Path = PATCH_ARTIFACTS_ROOT,
    actor: str = "cli",
) -> RoutePatchResult:
    repo_root, patch_dir, contract, state = _load_record(patch_id, repo_root, artifacts_root)
    _require_status(state, "reviewed")
    _verify_review_artifact(patch_dir)
    candidate_path = _worktree_path(patch_dir, "candidate-worktree")
    if candidate_path.exists() or candidate_path.is_symlink():
        raise RoutePatchError("Candidate worktree path already exists")
    try:
        _git(repo_root, "worktree", "add", "--detach", str(candidate_path), contract["repository_base_commit"])
        _transition(state, "prepared", actor=actor, artifact="candidate.yaml")
        _atomic_write_yaml(patch_dir / "state.yaml", state)
        _apply_contract_to_tree(contract, candidate_path)
        changed_files = _git_lines(candidate_path, "diff", "--name-only", "--")
        expected_files = _changed_files(contract)
        if changed_files != expected_files:
            raise RoutePatchError(
                "Candidate changed files do not exactly match the reviewed patch: "
                f"expected={expected_files} actual={changed_files}"
            )
        diff_text = _diff_from_tree(contract, candidate_path)
        expected_diff = _contract_diff(contract, repo_root)
        if diff_text != expected_diff:
            raise RoutePatchError("Candidate diff does not match the normalized reviewed diff")
        candidate = {
            "schema_version": "beat-mario.route-patch-candidate/v1",
            "patch_id": patch_id,
            "candidate_path": str(candidate_path),
            "base_commit": contract["repository_base_commit"],
            "changed_files": expected_files,
            "diff_sha256": _sha256_bytes(diff_text.encode("utf-8")),
            "preimage_sha256": contract["preimage_sha256"],
            "postimage_sha256": _tree_hashes(candidate_path, expected_files),
            "prepared_at": _now(),
            "isolation": "detached temporary git worktree",
        }
        candidate_path_record = patch_dir / "candidate.yaml"
        _atomic_write_yaml(candidate_path_record, candidate)
        (patch_dir / "candidate.diff").write_text(diff_text, encoding="utf-8")
        _transition(state, "applied_to_candidate", actor=actor, artifact=candidate_path_record.name)
        _atomic_write_yaml(patch_dir / "state.yaml", state)
        return _result(contract, state, patch_dir, candidate_path_record, candidate)
    except Exception as exc:
        _remove_worktree(repo_root, candidate_path, patch_dir=patch_dir)
        diagnostic_path = patch_dir / "prepare-failure.yaml"
        _atomic_write_yaml(
            diagnostic_path,
            {
                "patch_id": patch_id,
                "failed_at": _now(),
                "error": str(exc),
                "exception": _exception_record(exc),
                "candidate_removed": not candidate_path.exists(),
            },
        )
        if state["status"] in {"reviewed", "prepared"}:
            _transition(state, "failed", actor=actor, artifact=diagnostic_path.name)
            _atomic_write_yaml(patch_dir / "state.yaml", state)
        if isinstance(exc, RoutePatchError):
            raise
        raise RoutePatchError(f"Candidate preparation failed: {exc}") from exc


def validate_route_patch(
    patch_id: str,
    *,
    repo_root: Path | None = None,
    artifacts_root: Path = PATCH_ARTIFACTS_ROOT,
    game_path: Path | None = None,
    python_executable: Path | None = None,
    timeout_seconds: int = 900,
    actor: str = "cli",
) -> RoutePatchResult:
    repo_root, patch_dir, contract, state = _load_record(patch_id, repo_root, artifacts_root)
    _require_status(state, "applied_to_candidate")
    candidate_path_record = patch_dir / "candidate.yaml"
    candidate = _read_yaml(candidate_path_record)
    candidate_path = _candidate_path_from_record(candidate, patch_dir)
    _verify_candidate(contract, candidate, candidate_path, repo_root, patch_dir)
    python_executable = _trusted_python_executable(python_executable)

    parent_path = _worktree_path(patch_dir, "parent-worktree")
    if parent_path.exists() or parent_path.is_symlink():
        raise RoutePatchError("Parent validation worktree path already exists")
    gate_root = patch_dir / "validation"
    try:
        _git(repo_root, "worktree", "add", "--detach", str(parent_path), contract["repository_base_commit"])
        gates = _validation_gates(contract["validation_profile"])
        parent_results = _run_gates(
            "parent",
            gates,
            parent_path,
            gate_root,
            python_executable,
            game_path,
            timeout_seconds,
        )
        candidate_results = _run_gates(
            "candidate",
            gates,
            candidate_path,
            gate_root,
            python_executable,
            game_path,
            timeout_seconds,
        )
    finally:
        _remove_worktree(repo_root, parent_path, patch_dir=patch_dir)

    candidate_passed = all(bool(result["passed"]) for result in candidate_results)
    execution_proof = contract["validation_profile"] != "documentation_static"
    validation = {
        "schema_version": "beat-mario.route-patch-validation/v1",
        "patch_id": patch_id,
        "validated_at": _now(),
        "validated_by": actor,
        "candidate_path": str(candidate_path),
        "base_commit": contract["repository_base_commit"],
        "diff_sha256": candidate["diff_sha256"],
        "preimage_sha256": contract["preimage_sha256"],
        "postimage_sha256": contract["expected_postimage_sha256"],
        "validation_profile": contract["validation_profile"],
        "execution_proof": execution_proof,
        "candidate_environment": {
            "cwd": str(candidate_path),
            "python": str(python_executable),
            "pythonpath": str(candidate_path / "src"),
            "game_file_configured": game_path is not None,
            "isolation": "detached temporary git worktree",
        },
        "parent_results": parent_results,
        "candidate_results": candidate_results,
        "parent_outcome": _gate_outcome(parent_results),
        "candidate_outcome": _gate_outcome(candidate_results),
        "passed": candidate_passed,
        "contract_sha256": _sha256_file(patch_dir / "contract.yaml"),
        "candidate_record_sha256": _sha256_file(candidate_path_record),
        "candidate_diff_artifact_sha256": _sha256_file(patch_dir / "candidate.diff"),
        "output_artifact_sha256": _validation_output_hashes(
            parent_results + candidate_results, gate_root
        ),
    }
    validation_path = patch_dir / "validation.yaml"
    _atomic_write_yaml(validation_path, validation)
    state["validation_record_sha256"] = _sha256_file(validation_path)
    if candidate_passed:
        _transition(state, "validated", actor=actor, artifact=validation_path.name)
    else:
        _transition(state, "failed", actor=actor, artifact=validation_path.name)
    _atomic_write_yaml(patch_dir / "state.yaml", state)
    result = _result(contract, state, patch_dir, validation_path, validation)
    if not candidate_passed:
        raise RoutePatchError(
            f"Candidate validation failed; diagnostics preserved at {validation_path}"
        )
    return result


def compare_route_patch(
    patch_id: str,
    *,
    repo_root: Path | None = None,
    artifacts_root: Path = PATCH_ARTIFACTS_ROOT,
) -> RoutePatchResult:
    repo_root, patch_dir, contract, state = _load_record(patch_id, repo_root, artifacts_root)
    _require_status(state, "validated")
    validation_path = patch_dir / "validation.yaml"
    _verify_record_hash(validation_path, state.get("validation_record_sha256"), "validation record")
    validation = _read_yaml(validation_path)
    if validation.get("contract_sha256") != _sha256_file(patch_dir / "contract.yaml"):
        raise RoutePatchError("Patch contract changed after validation")
    if validation.get("candidate_diff_artifact_sha256") != _sha256_file(
        patch_dir / "candidate.diff"
    ):
        raise RoutePatchError("Candidate diff artifact changed after validation")
    candidate = _read_yaml(patch_dir / "candidate.yaml")
    if validation.get("candidate_record_sha256") != _sha256_file(patch_dir / "candidate.yaml"):
        raise RoutePatchError("Candidate record changed after validation")
    candidate_path = _candidate_path_from_record(candidate, patch_dir)
    _verify_candidate(contract, candidate, candidate_path, repo_root, patch_dir)

    parent_by_gate = {item["gate"]: item for item in validation["parent_results"]}
    regressions = [
        item["gate"]
        for item in validation["candidate_results"]
        if not item["passed"] and bool(parent_by_gate.get(item["gate"], {}).get("passed"))
    ]
    new_failure_classes = [
        item["failure_class"]
        for item in validation["candidate_results"]
        if item.get("failure_class")
        and item["failure_class"]
        not in {parent.get("failure_class") for parent in validation["parent_results"]}
    ]
    bounded_intent = set(_changed_files(contract)).issubset(set(contract["allowed_files"]))
    recommendation_allowed = (
        bool(validation["passed"])
        and bool(validation["execution_proof"])
        and not regressions
        and bounded_intent
    )
    report = {
        "schema_version": "beat-mario.route-patch-comparison/v1",
        "patch_id": patch_id,
        "compared_at": _now(),
        "parent_variant": contract["parent_variant"],
        "changed_files": _changed_files(contract),
        "exact_diff": _contract_diff(contract, repo_root),
        "diff_sha256": candidate["diff_sha256"],
        "parent_outcome": validation["parent_outcome"],
        "candidate_outcome": validation["candidate_outcome"],
        "new_failure_classes": new_failure_classes,
        "regressions": regressions,
        "bounded_intent_match": bounded_intent,
        "promotion_recommended": recommendation_allowed,
        "recommendation": (
            "promote_exact_validated_patch"
            if recommendation_allowed
            else "do_not_promote"
        ),
    }
    comparison_path = patch_dir / "comparison.yaml"
    _atomic_write_yaml(comparison_path, report)
    state["comparison_record_sha256"] = _sha256_file(comparison_path)
    _atomic_write_yaml(patch_dir / "state.yaml", state)
    return _result(contract, state, patch_dir, comparison_path, report)


def promote_route_patch(
    patch_id: str,
    *,
    confirm_patch_id: str,
    repo_root: Path | None = None,
    artifacts_root: Path = PATCH_ARTIFACTS_ROOT,
    actor: str = "cli",
    _fail_after_writes: int | None = None,
) -> RoutePatchResult:
    if confirm_patch_id != patch_id:
        raise RoutePatchError("Promotion confirmation must exactly match the patch ID")
    repo_root, patch_dir, contract, state = _load_record(patch_id, repo_root, artifacts_root)
    _require_status(state, "validated")
    blockers = _promotion_blockers(contract, state, repo_root, patch_dir)
    if blockers:
        raise RoutePatchError("Promotion refused: " + "; ".join(blockers))

    operations = contract["operations"]
    originals = {operation["path"]: (repo_root / operation["path"]).read_bytes() for operation in operations}
    promotion_path = patch_dir / "promotion.yaml"
    inverse_path = patch_dir / "inverse-patch.yaml"
    baseline_path = repo_root / "data/variants/world_1_baseline.yaml"
    baseline_snapshot_path = patch_dir / "baseline-before-promotion.yaml"
    if baseline_path.is_file():
        baseline_snapshot_path.write_bytes(baseline_path.read_bytes())

    try:
        _atomic_replace_operations(repo_root, operations, fail_after=_fail_after_writes)
        actual_hashes = _tree_hashes(repo_root, _changed_files(contract))
        if actual_hashes != contract["expected_postimage_sha256"]:
            raise RoutePatchError("Promoted postimage hashes do not match the validated candidate")
        promoted_diff = _diff_from_tree(contract, repo_root)
        candidate = _read_yaml(patch_dir / "candidate.yaml")
        if _sha256_bytes(promoted_diff.encode("utf-8")) != candidate["diff_sha256"]:
            raise RoutePatchError("Promoted diff hash does not match the validated candidate")

        inverse = {
            "schema_version": "beat-mario.route-patch-inverse/v1",
            "patch_id": patch_id,
            "diff_sha256": candidate["diff_sha256"],
            "operations": _inverse_operations(contract, repo_root),
        }
        _atomic_write_yaml(inverse_path, inverse)
        promotion = {
            "schema_version": "beat-mario.route-patch-promotion/v1",
            "patch_id": patch_id,
            "variant_id": contract["variant_id"],
            "promoted_at": _now(),
            "promoted_by": actor,
            "source": contract["source"],
            "base_commit": contract["repository_base_commit"],
            "candidate_record": str(patch_dir / "candidate.yaml"),
            "validation_record": str(patch_dir / "validation.yaml"),
            "comparison_record": str(patch_dir / "comparison.yaml"),
            "diff_sha256": candidate["diff_sha256"],
            "preimage_sha256": contract["preimage_sha256"],
            "postimage_sha256": actual_hashes,
            "inverse_patch": str(inverse_path),
            "previous_baseline_metadata": {
                "path": str(baseline_path.relative_to(repo_root)),
                "present": baseline_path.is_file(),
                "snapshot": str(baseline_snapshot_path) if baseline_snapshot_path.is_file() else None,
                "sha256": _sha256_file(baseline_path) if baseline_path.is_file() else None,
            },
            "automatic_commit": False,
            "automatic_push": False,
            "automatic_pull_request": False,
        }
        _atomic_write_yaml(promotion_path, promotion)
        state["promotion_record_sha256"] = _sha256_file(promotion_path)
        _transition(state, "promoted", actor=actor, artifact=promotion_path.name)
        _atomic_write_yaml(patch_dir / "state.yaml", state)
    except Exception as exc:
        _restore_bytes(repo_root, originals)
        if _tree_hashes(repo_root, list(originals)) != contract["preimage_sha256"]:
            raise RoutePatchError(
                f"Promotion failed and atomic restoration could not be verified: {exc}"
            ) from exc
        failure_path = patch_dir / "promotion-failure.yaml"
        _atomic_write_yaml(
            failure_path,
            {
                "patch_id": patch_id,
                "failed_at": _now(),
                "error": str(exc),
                "exception": _exception_record(exc),
                "restored_atomically": True,
            },
        )
        if isinstance(exc, RoutePatchError):
            raise
        raise RoutePatchError(f"Promotion failed; original files restored: {exc}") from exc

    candidate = _read_yaml(patch_dir / "candidate.yaml")
    candidate_path = _candidate_path_from_record(candidate, patch_dir)
    _remove_worktree(repo_root, candidate_path, patch_dir=patch_dir)
    promotion = _read_yaml(promotion_path)
    promotion["candidate_worktree_removed"] = not candidate_path.exists()
    _atomic_write_yaml(promotion_path, promotion)
    state["promotion_record_sha256"] = _sha256_file(promotion_path)
    _atomic_write_yaml(patch_dir / "state.yaml", state)
    return _result(contract, state, patch_dir, promotion_path, promotion)


def rollback_route_patch(
    patch_id: str,
    *,
    confirm_patch_id: str,
    reason: str = "explicit operator rollback",
    repo_root: Path | None = None,
    artifacts_root: Path = PATCH_ARTIFACTS_ROOT,
    actor: str = "cli",
) -> RoutePatchResult:
    if confirm_patch_id != patch_id:
        raise RoutePatchError("Rollback confirmation must exactly match the patch ID")
    if not reason.strip():
        raise RoutePatchError("A rollback reason is required")
    repo_root, patch_dir, contract, state = _load_record(patch_id, repo_root, artifacts_root)
    _require_status(state, "promoted")
    promotion_path = patch_dir / "promotion.yaml"
    _verify_record_hash(promotion_path, state.get("promotion_record_sha256"), "promotion record")
    promotion = _read_yaml(promotion_path)
    current_hashes = _tree_hashes(repo_root, _changed_files(contract))
    if current_hashes != promotion["postimage_sha256"]:
        raise RoutePatchError("Rollback refused: promoted files contain later conflicting edits")
    inverse = _read_yaml(patch_dir / "inverse-patch.yaml")
    operations = _inverse_operations(contract, repo_root)
    if inverse.get("patch_id") != patch_id or inverse.get("operations") != operations:
        raise RoutePatchError("Inverse patch record does not match the reviewed contract")
    originals = {operation["path"]: (repo_root / operation["path"]).read_bytes() for operation in operations}
    try:
        _atomic_replace_operations(repo_root, operations)
        restored_hashes = _tree_hashes(repo_root, _changed_files(contract))
        if restored_hashes != contract["preimage_sha256"]:
            raise RoutePatchError("Rollback restoration hashes do not match the recorded preimage")
        rollback = {
            "schema_version": "beat-mario.route-patch-rollback/v1",
            "patch_id": patch_id,
            "rolled_back_at": _now(),
            "rolled_back_by": actor,
            "reason": reason.strip(),
            "promotion_record": str(promotion_path),
            "validation_record": str(patch_dir / "validation.yaml"),
            "diff_sha256": promotion["diff_sha256"],
            "restored_sha256": restored_hashes,
        }
        rollback_path = patch_dir / "rollback.yaml"
        _atomic_write_yaml(rollback_path, rollback)
        _transition(state, "rolled_back", actor=actor, artifact=rollback_path.name)
        _atomic_write_yaml(patch_dir / "state.yaml", state)
        return _result(contract, state, patch_dir, rollback_path, rollback)
    except Exception as exc:
        _restore_bytes(repo_root, originals)
        _atomic_write_yaml(
            patch_dir / "rollback-failure.yaml",
            {
                "patch_id": patch_id,
                "failed_at": _now(),
                "error": str(exc),
                "exception": _exception_record(exc),
                "promoted_files_restored": (
                    _tree_hashes(repo_root, list(originals))
                    == promotion["postimage_sha256"]
                ),
            },
        )
        if isinstance(exc, RoutePatchError):
            raise
        raise RoutePatchError(f"Rollback failed; promoted files restored: {exc}") from exc


def patch_summary_for_issue(
    issue_id: str,
    *,
    repo_root: Path | None = None,
    artifacts_root: Path = PATCH_ARTIFACTS_ROOT,
) -> dict[str, Any] | None:
    repo_root = _repo_root(repo_root)
    root = _artifact_root(repo_root, artifacts_root)
    if not root.is_dir():
        return None
    matches: list[tuple[str, dict[str, Any], Path]] = []
    for contract_path in root.glob("*/contract.yaml"):
        try:
            contract = _read_yaml(contract_path)
            if contract.get("source", {}).get("issue_id") != issue_id:
                continue
            state = _read_yaml(contract_path.parent / "state.yaml")
            matches.append((str(state.get("updated_at", "")), contract, contract_path.parent))
        except (OSError, RoutePatchError) as exc:
            LOGGER.warning(
                "route_patch_record_skipped path=%s error_type=%s detail=%s",
                contract_path,
                type(exc).__name__,
                exc,
            )
            continue
    if not matches:
        return None
    _, contract, patch_dir = sorted(matches, key=lambda item: item[0])[-1]
    state = _read_yaml(patch_dir / "state.yaml")
    preview = preview_route_patch(
        str(contract["patch_id"]), repo_root=repo_root, artifacts_root=root
    )
    summary = dict(preview.details)
    summary.update(
        {
            "patch_id": contract["patch_id"],
            "status": state["status"],
            "task_packet": contract["source"].get("task_packet"),
            "review_state": "reviewed" if (patch_dir / "review.yaml").is_file() else "not reviewed",
            "validation_result": (
                _read_yaml(patch_dir / "validation.yaml").get("passed")
                if (patch_dir / "validation.yaml").is_file()
                else None
            ),
        }
    )
    return summary


def _normalize_contract(raw: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    _reject_forbidden_declarations(raw)
    allowed_top_level = {
        "schema_version",
        "patch_id",
        "variant_id",
        "source",
        "parent_variant",
        "repository_base_commit",
        "allowed_files",
        "preimage_sha256",
        "operations",
        "expected_postimage_sha256",
        "summary",
        "validation_profile",
        "rollback_description",
        "lifecycle",
        "timestamps",
        "provenance",
    }
    unknown = set(raw) - allowed_top_level
    if unknown:
        raise RoutePatchError(f"Unsupported patch fields: {sorted(unknown)}")
    if raw.get("schema_version") != PATCH_SCHEMA_VERSION:
        raise RoutePatchError(f"Unsupported patch schema: {raw.get('schema_version')}")
    patch_id = _validate_id(raw.get("patch_id"), "patch ID")
    variant_id = _validate_id(raw.get("variant_id"), "variant ID")
    base_commit = str(raw.get("repository_base_commit", ""))
    if not COMMIT_PATTERN.fullmatch(base_commit):
        raise RoutePatchError("repository_base_commit must be a full lowercase git commit SHA")
    try:
        _git(repo_root, "cat-file", "-e", f"{base_commit}^{{commit}}")
    except RoutePatchError as exc:
        raise RoutePatchError(f"Stale base commit or invalid git object: {base_commit}") from exc
    current_head = _git_text(repo_root, "rev-parse", "HEAD").strip()
    if base_commit != current_head:
        raise RoutePatchError(
            f"Stale base commit: patch={base_commit} repository_head={current_head}"
        )

    source = _normalize_source(raw.get("source"))
    allowed_files = _normalize_allowed_files(raw.get("allowed_files"), repo_root)
    operations_raw = raw.get("operations")
    if not isinstance(operations_raw, list) or not operations_raw:
        raise RoutePatchError("Patch operations must be a non-empty list")
    if len(operations_raw) > MAX_CHANGED_FILES:
        raise RoutePatchError(f"Patch changes too many files; maximum is {MAX_CHANGED_FILES}")
    operations: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    total_bytes = 0
    for raw_operation in operations_raw:
        operation = _normalize_operation(raw_operation, repo_root, base_commit, allowed_files)
        path = operation["path"]
        if path in seen_paths:
            raise RoutePatchError(f"Overlapping or duplicate operation for path: {path}")
        seen_paths.add(path)
        total_bytes += len(operation["content"].encode("utf-8"))
        operations.append(operation)
    if total_bytes > MAX_PATCH_BYTES:
        raise RoutePatchError(f"Patch content exceeds {MAX_PATCH_BYTES} bytes")

    supplied_preimages = raw.get("preimage_sha256")
    supplied_postimages = raw.get("expected_postimage_sha256")
    preimages = {operation["path"]: operation["preimage_sha256"] for operation in operations}
    postimages = {
        operation["path"]: operation["expected_postimage_sha256"] for operation in operations
    }
    if supplied_preimages is not None and supplied_preimages != preimages:
        raise RoutePatchError("Top-level preimage hashes do not match normalized operations")
    if supplied_postimages is not None and supplied_postimages != postimages:
        raise RoutePatchError("Top-level postimage hashes do not match normalized operations")
    profile = _select_validation_profile(list(seen_paths))
    supplied_profile = raw.get("validation_profile")
    if supplied_profile is not None and supplied_profile != profile:
        raise RoutePatchError(
            f"Patch cannot select its validation profile; internal policy selected {profile}"
        )
    lifecycle = raw.get("lifecycle")
    if lifecycle not in (None, "imported", {"status": "imported"}):
        raise RoutePatchError("Imported patches cannot self-declare review or validation state")
    summary = str(raw.get("summary", "")).strip()
    rollback_description = str(raw.get("rollback_description", "")).strip()
    if not summary or not rollback_description:
        raise RoutePatchError("Patch summary and rollback description are required")
    parent_variant = str(raw.get("parent_variant", "")).strip()
    if not parent_variant:
        raise RoutePatchError("parent_variant is required")
    provenance = raw.get("provenance")
    if not isinstance(provenance, dict) or not provenance:
        raise RoutePatchError("Patch provenance is required")

    raw_timestamps = raw.get("timestamps")
    if raw_timestamps is not None and not isinstance(raw_timestamps, dict):
        raise RoutePatchError("timestamps must be a mapping")
    contract = {
        "schema_version": PATCH_SCHEMA_VERSION,
        "patch_id": patch_id,
        "variant_id": variant_id,
        "source": source,
        "parent_variant": parent_variant,
        "repository_base_commit": base_commit,
        "allowed_files": allowed_files,
        "preimage_sha256": preimages,
        "operations": operations,
        "expected_postimage_sha256": postimages,
        "summary": summary,
        "validation_profile": profile,
        "rollback_description": rollback_description,
        "timestamps": {
            "created_at": str((raw_timestamps or {}).get("created_at", _now()))
        },
        "provenance": provenance,
    }
    diff_text = _contract_diff(contract, repo_root)
    if not diff_text.strip():
        raise RoutePatchError("Patch is already applied or contains no effective change")
    if len(diff_text.encode("utf-8")) > MAX_PATCH_BYTES:
        raise RoutePatchError(f"Normalized diff exceeds {MAX_PATCH_BYTES} bytes")
    return contract


def _normalize_source(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RoutePatchError("Patch source must be a mapping")
    allowed = {"kind", "session_id", "issue_id", "note_ids", "task_id", "task_packet"}
    unknown = set(raw) - allowed
    if unknown:
        raise RoutePatchError(f"Unsupported source fields: {sorted(unknown)}")
    kind = raw.get("kind")
    if kind not in {"route_lab_issue", "codex_task"}:
        raise RoutePatchError("source.kind must be route_lab_issue or codex_task")
    session_id = _validate_id(raw.get("session_id"), "source session ID")
    issue_id = _validate_id(raw.get("issue_id"), "source issue ID")
    note_ids = raw.get("note_ids")
    if not isinstance(note_ids, list) or not note_ids:
        raise RoutePatchError("source.note_ids must be a non-empty list")
    normalized_notes = [_validate_id(note_id, "source note ID") for note_id in note_ids]
    if len(normalized_notes) != len(set(normalized_notes)):
        raise RoutePatchError("source.note_ids contains duplicates")
    task_packet = raw.get("task_packet")
    if task_packet is not None:
        task_packet = _validate_relative_path(task_packet)
    if kind == "codex_task" and not task_packet:
        raise RoutePatchError("Codex task patches require source.task_packet")
    return {
        "kind": kind,
        "session_id": session_id,
        "issue_id": issue_id,
        "note_ids": normalized_notes,
        "task_id": str(raw.get("task_id", "")).strip() or None,
        "task_packet": task_packet,
    }


def _normalize_allowed_files(raw: Any, repo_root: Path) -> list[str]:
    if not isinstance(raw, list) or not raw:
        raise RoutePatchError("allowed_files must be a non-empty list")
    normalized = [_validate_patch_path(path, repo_root) for path in raw]
    if len(normalized) != len(set(normalized)):
        raise RoutePatchError("allowed_files contains duplicates")
    return sorted(normalized)


def _normalize_operation(
    raw: Any,
    repo_root: Path,
    base_commit: str,
    allowed_files: list[str],
) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise RoutePatchError("Each patch operation must be a mapping")
    expected_fields = {
        "kind",
        "path",
        "preimage_sha256",
        "expected_postimage_sha256",
        "content",
    }
    if set(raw) != expected_fields:
        raise RoutePatchError(
            "Each operation must contain exactly kind, path, preimage_sha256, "
            "expected_postimage_sha256, and content; raw hunks and commands are unsupported"
        )
    if raw.get("kind") != "replace_text":
        raise RoutePatchError("Only normalized replace_text operations are supported")
    path = _validate_patch_path(raw.get("path"), repo_root)
    if path not in allowed_files:
        raise RoutePatchError(f"Changed file is absent from allowed_files: {path}")
    preimage = str(raw.get("preimage_sha256", ""))
    postimage = str(raw.get("expected_postimage_sha256", ""))
    if not SHA256_PATTERN.fullmatch(preimage) or not SHA256_PATTERN.fullmatch(postimage):
        raise RoutePatchError(f"Missing or malformed SHA-256 for {path}")
    base_bytes = _git_blob(repo_root, base_commit, path)
    try:
        base_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RoutePatchError(f"Binary or malformed UTF-8 preimage is unsupported: {path}") from exc
    if _sha256_bytes(base_bytes) != preimage:
        raise RoutePatchError(f"Stale preimage SHA-256 for {path}")
    content = raw.get("content")
    if not isinstance(content, str):
        raise RoutePatchError(f"Replacement content must be UTF-8 text: {path}")
    content_bytes = content.encode("utf-8")
    if b"\x00" in content_bytes:
        raise RoutePatchError(f"Binary patch content is unsupported: {path}")
    if len(content_bytes) > MAX_FILE_BYTES:
        raise RoutePatchError(f"Replacement file is unexpectedly large: {path}")
    if _sha256_bytes(content_bytes) != postimage:
        raise RoutePatchError(f"Expected postimage SHA-256 does not match content: {path}")
    if preimage == postimage:
        raise RoutePatchError(f"Patch operation is already applied or has no effect: {path}")
    return {
        "kind": "replace_text",
        "path": path,
        "preimage_sha256": preimage,
        "expected_postimage_sha256": postimage,
        "content": content,
    }


def _validate_patch_path(raw: Any, repo_root: Path) -> str:
    path = _validate_relative_path(raw)
    candidate = Path(path)
    if candidate.suffix.lower() in DENIED_SUFFIXES:
        raise RoutePatchError(f"ROM, savestate, image, log, archive, or binary file is forbidden: {path}")
    if candidate.suffix.lower() not in SUPPORTED_TEXT_SUFFIXES:
        raise RoutePatchError(f"Unsupported route-patch file type: {path}")
    if any(part.lower() in DENIED_PARTS for part in candidate.parts):
        raise RoutePatchError(f"Generated, cache, or artifact path is forbidden: {path}")
    if path.startswith(DENIED_PREFIXES):
        raise RoutePatchError(f"Generated evidence path is forbidden: {path}")
    if path in PROTECTED_VALIDATION_FILES:
        raise RoutePatchError(f"Validation gate definitions cannot be changed by a route patch: {path}")
    lexical_path = repo_root / candidate
    if lexical_path.is_symlink():
        raise RoutePatchError(f"Symlink patch targets are forbidden: {path}")
    full_path = _confined_path(repo_root, candidate.as_posix(), "route-patch target")
    if not full_path.exists():
        raise RoutePatchError(f"Changed file does not exist at repository base: {path}")
    try:
        full_path.resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise RoutePatchError(f"Symlink escape outside repository: {path}") from exc
    return candidate.as_posix()


def _validate_relative_path(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise RoutePatchError("Patch paths must be non-empty strings")
    value = raw.strip()
    path = Path(value)
    if path.is_absolute() or re.match(r"^[A-Za-z]:[\\/]", value):
        raise RoutePatchError(f"Absolute paths are forbidden: {value}")
    if "\\" in value or any(part in {"", ".", ".."} for part in path.parts):
        raise RoutePatchError(f"Path traversal or ambiguous path is forbidden: {value}")
    return path.as_posix()


def _select_validation_profile(paths: list[str]) -> str:
    if not paths:
        raise RoutePatchError("Cannot select a validation profile without changed files")
    if all(path == "README.md" or path.startswith("docs/") for path in paths):
        return "documentation_static"
    big_tanks_markers = (
        "big_tanks",
        "scripts/fceux_1_1_agent.lua",
        "data/segments/world_8_double_whistle",
        "src/smb3_agent/goals.py",
        "src/smb3_agent/reliability.py",
        "src/smb3_agent/presets.py",
    )
    if any(any(marker in path for marker in big_tanks_markers) for path in paths):
        return "canonical_rank27_rank28"
    arrival_markers = (
        "world_8_double_whistle",
    )
    if any(any(marker in path for marker in arrival_markers) for path in paths):
        return "canonical_rank27"
    canonical_prefixes = (
        "src/",
        "src/smb3_agent/",
        "tests/",
        "data/lab/",
        "data/goals/",
        "data/routes/",
        "data/segments/",
        "data/worlds/",
        "scripts/",
    )
    if all(path.startswith(canonical_prefixes) or path == "pyproject.toml" for path in paths):
        return "canonical_phase"
    raise RoutePatchError(f"No safe validation profile exists for changed files: {paths}")


def _validation_gates(
    profile: str,
) -> list[str]:
    if profile == "documentation_static":
        return ["documentation_static"]
    gates = ["canonical_phase"]
    if profile in {"canonical_rank27", "canonical_rank27_rank28"}:
        gates.append("rank27_5_of_5")
    if profile == "canonical_rank27_rank28":
        gates.append("rank28_3_of_3")
    return gates


def _validation_argv(
    gate_name: str,
    python_executable: Path,
    game_path: Path | None,
) -> list[str]:
    if gate_name not in VALIDATION_GATE_NAMES:
        raise RoutePatchError(f"Unsupported validation gate: {gate_name}")
    if gate_name == "documentation_static":
        return ["git", "diff", "--check", "HEAD", "--"]
    if gate_name == "canonical_phase":
        return ["bash", "scripts/validate_phase0.sh"]
    if game_path is None:
        raise RoutePatchError(f"Validation gate {gate_name} requires a local game file")
    goal, runs = {
        "rank27_5_of_5": ("world_8_double_whistle", "5"),
        "rank28_3_of_3": ("world_8_big_tanks", "3"),
    }[gate_name]
    return [
        str(python_executable),
        "-m",
        "smb3_agent",
        "reliability",
        "run",
        "--goal",
        goal,
        "--runs",
        runs,
        "--game-file",
        os.fspath(game_path),
    ]


def _run_gates(
    side: str,
    gates: Sequence[str],
    cwd: Path,
    artifact_root: Path,
    python_executable: Path,
    game_path: Path | None,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    if side not in VALIDATION_SIDES:
        raise RoutePatchError(f"Unsupported validation side: {side}")
    results: list[dict[str, Any]] = []
    env = os.environ.copy()
    env["PYTHON"] = str(python_executable)
    env["PYTHONPATH"] = str(cwd / "src")
    env["BEAT_MARIO_PATCH_CANDIDATE"] = "1" if side == "candidate" else "0"
    for gate_name in gates:
        argv = _validation_argv(gate_name, python_executable, game_path)
        output_dir = artifact_root / side
        output_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = output_dir / f"{gate_name}.stdout.log"
        stderr_path = output_dir / f"{gate_name}.stderr.log"
        started = time.monotonic()
        try:
            completed = subprocess.run(
                argv,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=timeout_seconds,
                shell=False,
                check=False,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            exit_code = completed.returncode
            failure_class = None if exit_code == 0 else _failure_class(stdout, stderr, exit_code)
        except subprocess.TimeoutExpired as exc:
            stdout = _coerce_output(exc.stdout)
            stderr = _coerce_output(exc.stderr) + f"\nTimed out after {timeout_seconds} seconds.\n"
            exit_code = 124
            failure_class = "timeout"
        except UnicodeError as exc:
            stdout = ""
            stderr = f"Malformed command output encoding: {exc}\n"
            exit_code = 65
            failure_class = "malformed_encoding"
        elapsed = time.monotonic() - started
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        counts = _extract_success_failure_counts(stdout + "\n" + stderr, exit_code)
        results.append(
            {
                "side": side,
                "gate": gate_name,
                "argv": list(argv),
                "cwd": str(cwd),
                "exit_code": exit_code,
                "elapsed_seconds": round(elapsed, 6),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "passed": exit_code == 0,
                "failure_class": failure_class,
                **counts,
            }
        )
    return results


def _promotion_blockers(
    contract: dict[str, Any],
    state: dict[str, Any],
    repo_root: Path,
    patch_dir: Path,
) -> list[str]:
    blockers: list[str] = []
    if state.get("status") != "validated":
        blockers.append(f"lifecycle state is {state.get('status')}, not validated")
        return blockers
    required = ("review.yaml", "candidate.yaml", "candidate.diff", "validation.yaml", "comparison.yaml")
    for name in required:
        if not (patch_dir / name).is_file():
            blockers.append(f"missing lab-owned artifact: {name}")
    if blockers:
        return blockers
    try:
        _verify_review_artifact(patch_dir)
        validation_path = patch_dir / "validation.yaml"
        _verify_record_hash(validation_path, state.get("validation_record_sha256"), "validation record")
        comparison_path = patch_dir / "comparison.yaml"
        _verify_record_hash(comparison_path, state.get("comparison_record_sha256"), "comparison record")
        validation = _read_yaml(validation_path)
        comparison = _read_yaml(comparison_path)
        if not validation.get("passed"):
            blockers.append("required validation gates did not pass")
        if not validation.get("execution_proof"):
            blockers.append("documentation-only validation is not route execution proof")
        if not comparison.get("promotion_recommended"):
            blockers.append("comparison does not recommend promotion")
        if validation.get("contract_sha256") != _sha256_file(patch_dir / "contract.yaml"):
            blockers.append("patch contract changed after validation")
        candidate_path_record = patch_dir / "candidate.yaml"
        if validation.get("candidate_record_sha256") != _sha256_file(candidate_path_record):
            blockers.append("candidate record changed after validation")
        if validation.get("candidate_diff_artifact_sha256") != _sha256_file(patch_dir / "candidate.diff"):
            blockers.append("candidate diff artifact changed after validation")
        output_hashes = validation.get("output_artifact_sha256", {})
        if not isinstance(output_hashes, dict):
            blockers.append("validation output hashes are malformed")
            return blockers
        validation_root = patch_dir / "validation"
        for raw_path, expected_hash in output_hashes.items():
            relative = _validate_relative_path(raw_path)
            path = _confined_path(validation_root, relative, "validation output")
            if not path.is_file() or _sha256_file(path) != expected_hash:
                blockers.append(f"validation output artifact changed: {path.name}")
        candidate = _read_yaml(candidate_path_record)
        candidate_path = _candidate_path_from_record(candidate, patch_dir)
        _verify_candidate(contract, candidate, candidate_path, repo_root, patch_dir)
    except (OSError, RoutePatchError) as exc:
        blockers.append(str(exc))

    if _git_text(repo_root, "rev-parse", "HEAD").strip() != contract["repository_base_commit"]:
        blockers.append("repository HEAD no longer matches the reviewed base commit")
    if _git_text(repo_root, "status", "--porcelain", "--untracked-files=all").strip():
        blockers.append("accepted working tree is not clean")
    try:
        current_hashes = _tree_hashes(repo_root, _changed_files(contract))
        if current_hashes != contract["preimage_sha256"]:
            blockers.append("current preimage hashes no longer match the reviewed patch")
    except OSError as exc:
        blockers.append(f"cannot read promotion preimage: {exc}")
    return blockers


def _verify_candidate(
    contract: dict[str, Any],
    candidate: dict[str, Any],
    candidate_path: Path,
    repo_root: Path,
    patch_dir: Path,
) -> None:
    if candidate_path != _worktree_path(patch_dir, "candidate-worktree"):
        raise RoutePatchError("Candidate worktree is outside the patch artifact root")
    if not candidate_path.is_dir():
        raise RoutePatchError("Candidate worktree is missing")
    if _git_text(candidate_path, "rev-parse", "HEAD").strip() != contract["repository_base_commit"]:
        raise RoutePatchError("Candidate base commit changed")
    changed_files = _git_lines(candidate_path, "diff", "--name-only", "--")
    if changed_files != _changed_files(contract):
        raise RoutePatchError("Candidate contains unreviewed or missing file changes")
    hashes = _tree_hashes(candidate_path, _changed_files(contract))
    if hashes != contract["expected_postimage_sha256"]:
        raise RoutePatchError("Candidate content no longer matches expected postimage hashes")
    diff_text = _diff_from_tree(contract, candidate_path)
    diff_hash = _sha256_bytes(diff_text.encode("utf-8"))
    if diff_hash != candidate.get("diff_sha256"):
        raise RoutePatchError("Candidate diff changed after application")
    expected_diff = _contract_diff(contract, repo_root)
    if diff_text != expected_diff:
        raise RoutePatchError("Candidate diff no longer matches the normalized patch")


def _worktree_path(patch_dir: Path, name: str) -> Path:
    if name not in WORKTREE_NAMES:
        raise RoutePatchError(f"Unsupported route-patch worktree: {name}")
    return (patch_dir / name).resolve()


def _candidate_path_from_record(candidate: Mapping[str, Any], patch_dir: Path) -> Path:
    expected = _worktree_path(patch_dir, "candidate-worktree")
    recorded = candidate.get("candidate_path")
    if not isinstance(recorded, str) or recorded != str(expected):
        raise RoutePatchError("Candidate record contains an unexpected worktree path")
    return expected


def _trusted_python_executable(requested: Path | None) -> Path:
    trusted = Path(sys.executable).resolve(strict=True)
    if requested is not None:
        try:
            supplied = requested.expanduser().resolve(strict=True)
        except OSError as exc:
            raise RoutePatchError("Requested Python executable does not exist") from exc
        if supplied != trusted:
            raise RoutePatchError("Route-patch validation must use the current Python executable")
    if not trusted.is_file():
        raise RoutePatchError("Current Python executable is not a regular file")
    return trusted


def _verify_reviewed_source(
    contract: dict[str, Any], repo_root: Path, sessions_root: Path
) -> dict[str, Any]:
    source = contract["source"]
    session_dir = sessions_root / source["session_id"]
    if not session_dir.is_dir():
        raise RoutePatchError(f"Source session not found: {source['session_id']}")
    session = _read_yaml(session_dir / "session.yaml")
    if session.get("session_id") != source["session_id"]:
        raise RoutePatchError("Source session manifest does not match patch provenance")
    review_path = session_dir / "review.yaml"
    if not review_path.is_file():
        raise RoutePatchError("Source session has no separate lab review record")
    review = _read_yaml(review_path)
    if review.get("session_id") != source["session_id"]:
        raise RoutePatchError("Source review does not match the patch session")
    issues = _read_yaml(session_dir / "issues.yaml").get("issues", [])
    issue = next(
        (item for item in issues if isinstance(item, dict) and item.get("id") == source["issue_id"]),
        None,
    )
    if issue is None or not issue.get("actionable", True) or issue.get("status", "open") not in {
        "open",
        "needs_rerun",
    }:
        raise RoutePatchError("Source issue is missing, inactive, or not actionable")
    notes = _read_yaml(session_dir / "notes.yaml").get("notes", [])
    available_note_ids = {item.get("id") for item in notes if isinstance(item, dict)}
    if not set(source["note_ids"]).issubset(available_note_ids):
        raise RoutePatchError("Patch source references missing session notes")

    reviewed_allowlist = issue.get("relevant_files", [])
    task_packet_path: Path | None = None
    if source.get("task_packet"):
        task_packet_path = repo_root / source["task_packet"]
        try:
            task_packet_path.resolve().relative_to(repo_root.resolve())
        except ValueError as exc:
            raise RoutePatchError("Task packet escapes the repository") from exc
        task = _read_yaml(task_packet_path)
        if task.get("session_id") != source["session_id"] or task.get("issue_id") != source["issue_id"]:
            raise RoutePatchError("Task packet does not match source session and issue")
        if source.get("task_id") and task.get("task_id") != source["task_id"]:
            raise RoutePatchError("Task packet ID does not match patch source")
        reviewed_allowlist = task.get("inputs", {}).get("relevant_files", [])
    if not isinstance(reviewed_allowlist, list) or not reviewed_allowlist:
        raise RoutePatchError("Reviewed issue or task packet has no relevant-file allowlist")
    reviewed_paths = {_validate_patch_path(path, repo_root) for path in reviewed_allowlist}
    undeclared = set(_changed_files(contract)) - reviewed_paths
    if undeclared:
        raise RoutePatchError(f"Patch changes files absent from reviewed allowlist: {sorted(undeclared)}")
    return {
        "session_manifest": str(session_dir / "session.yaml"),
        "session_review": str(review_path),
        "issue_ledger": str(session_dir / "issues.yaml"),
        "notes": str(session_dir / "notes.yaml"),
        "task_packet": str(task_packet_path) if task_packet_path else None,
        "reviewed_relevant_files": sorted(reviewed_paths),
    }


def _verify_review_artifact(patch_dir: Path) -> None:
    review_path = patch_dir / "review.yaml"
    if not review_path.is_file():
        raise RoutePatchError("Patch has no lab-owned review record")
    review = _read_yaml(review_path)
    if review.get("decision") != "reviewed":
        raise RoutePatchError("Patch review decision is not reviewed")
    if review.get("contract_sha256") != _sha256_file(patch_dir / "contract.yaml"):
        raise RoutePatchError("Patch contract changed after review")


def _load_record(
    patch_id: str, repo_root: Path | None, artifacts_root: Path
) -> tuple[Path, Path, dict[str, Any], dict[str, Any]]:
    patch_id = _validate_id(patch_id, "patch ID")
    repo_root = _repo_root(repo_root)
    root = _artifact_root(repo_root, artifacts_root)
    patch_dir = root / patch_id
    contract_path = patch_dir / "contract.yaml"
    state_path = patch_dir / "state.yaml"
    if not contract_path.is_file() or not state_path.is_file():
        raise RoutePatchError(f"Imported patch not found: {patch_id}")
    contract = _read_yaml(contract_path)
    state = _read_yaml(state_path)
    if contract.get("patch_id") != patch_id or state.get("patch_id") != patch_id:
        raise RoutePatchError("Patch artifact identity mismatch")
    _validate_loaded_contract_paths(contract, repo_root)
    return repo_root, patch_dir, contract, state


def _validate_loaded_contract_paths(contract: Mapping[str, Any], repo_root: Path) -> None:
    operations = contract.get("operations")
    allowed_files = contract.get("allowed_files")
    if not isinstance(operations, list) or not isinstance(allowed_files, list):
        raise RoutePatchError("Stored patch contract has malformed path declarations")
    normalized_allowed = [_validate_patch_path(path, repo_root) for path in allowed_files]
    normalized_operations = [
        _validate_patch_path(operation.get("path"), repo_root)
        for operation in operations
        if isinstance(operation, dict)
    ]
    if len(normalized_operations) != len(operations):
        raise RoutePatchError("Stored patch contract has malformed operations")
    if (
        len(normalized_allowed) != len(set(normalized_allowed))
        or len(normalized_operations) != len(set(normalized_operations))
        or not set(normalized_operations).issubset(normalized_allowed)
    ):
        raise RoutePatchError("Stored patch contract paths no longer match their allowlist")


def _result(
    contract: dict[str, Any],
    state: dict[str, Any],
    patch_dir: Path,
    artifact_path: Path,
    extra: Mapping[str, Any] | None = None,
) -> RoutePatchResult:
    details: dict[str, Any] = {
        "variant_id": contract["variant_id"],
        "validation_profile": contract["validation_profile"],
        "base_commit": contract["repository_base_commit"],
        "changed_files": _changed_files(contract),
        "rollback_available": state["status"] == "promoted",
    }
    if extra:
        details.update(extra)
    return RoutePatchResult(contract["patch_id"], state["status"], patch_dir, artifact_path, details)


def _transition(
    state: dict[str, Any], new_status: str, *, actor: str, artifact: str
) -> None:
    old_status = str(state.get("status"))
    if new_status not in LIFECYCLE_TRANSITIONS.get(old_status, set()):
        raise RoutePatchError(f"Invalid patch lifecycle transition: {old_status} -> {new_status}")
    at = _now()
    state["status"] = new_status
    state["updated_at"] = at
    state.setdefault("history", []).append(
        {"from": old_status, "to": new_status, "at": at, "actor": actor, "artifact": artifact}
    )


def _require_status(state: dict[str, Any], expected: str) -> None:
    if state.get("status") != expected:
        raise RoutePatchError(
            f"Patch must be {expected}; current lifecycle state is {state.get('status')}"
        )


def _contract_diff(contract: dict[str, Any], repo_root: Path) -> str:
    parts = []
    for operation in contract["operations"]:
        before = _git_blob(repo_root, contract["repository_base_commit"], operation["path"]).decode(
            "utf-8"
        )
        parts.append(_unified_diff(operation["path"], before, operation["content"]))
    return "".join(parts)


def _diff_from_tree(contract: dict[str, Any], tree: Path) -> str:
    parts = []
    for operation in contract["operations"]:
        before = _git_blob(tree, contract["repository_base_commit"], operation["path"]).decode("utf-8")
        after = (tree / operation["path"]).read_text(
            encoding="utf-8"
        )
        parts.append(_unified_diff(operation["path"], before, after))
    return "".join(parts)


def _unified_diff(path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="\n",
        )
    )


def _apply_contract_to_tree(contract: dict[str, Any], tree: Path) -> None:
    current_hashes = _tree_hashes(tree, _changed_files(contract))
    if current_hashes != contract["preimage_sha256"]:
        raise RoutePatchError("Candidate preimage does not match the reviewed patch")
    _atomic_replace_operations(tree, contract["operations"])
    if _tree_hashes(tree, _changed_files(contract)) != contract["expected_postimage_sha256"]:
        raise RoutePatchError("Candidate postimage verification failed")


def _atomic_replace_operations(
    root: Path,
    operations: Sequence[Mapping[str, str]],
    *,
    fail_after: int | None = None,
) -> None:
    originals = {
        operation["path"]: (root / operation["path"]).read_bytes()
        for operation in operations
    }
    written = 0
    try:
        for operation in operations:
            target = root / operation["path"]
            if target.is_symlink():
                raise RoutePatchError(f"Symlink target appeared during application: {operation['path']}")
            _atomic_write_bytes(target, operation["content"].encode("utf-8"))
            written += 1
            if fail_after is not None and written >= fail_after:
                raise OSError("injected partial-write failure")
    except Exception:
        _restore_bytes(root, originals)
        raise


def _inverse_operations(
    contract: Mapping[str, Any], repo_root: Path
) -> list[dict[str, str]]:
    operations: list[dict[str, str]] = []
    for operation in contract["operations"]:
        path = _validate_patch_path(operation["path"], repo_root)
        original = _git_blob(repo_root, contract["repository_base_commit"], path)
        operations.append(
            {
                "kind": "replace_text",
                "path": path,
                "preimage_sha256": operation["expected_postimage_sha256"],
                "expected_postimage_sha256": operation["preimage_sha256"],
                "content": original.decode("utf-8"),
            }
        )
    return operations


def _restore_bytes(root: Path, originals: Mapping[str, bytes]) -> None:
    for path, content in originals.items():
        _atomic_write_bytes(root / path, content)


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temp_path = Path(raw_temp)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _tree_hashes(root: Path, paths: Iterable[str]) -> dict[str, str]:
    return {path: _sha256_file(root / path) for path in paths}


def _changed_files(contract: Mapping[str, Any]) -> list[str]:
    return sorted(str(operation["path"]) for operation in contract["operations"])


def _gate_outcome(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "passed": all(bool(result["passed"]) for result in results),
        "gates_passed": sum(1 for result in results if result["passed"]),
        "gates_failed": sum(1 for result in results if not result["passed"]),
        "successes": sum(int(result.get("successes", 0)) for result in results),
        "failures": sum(int(result.get("failures", 0)) for result in results),
        "failure_classes": sorted(
            {str(result["failure_class"]) for result in results if result.get("failure_class")}
        ),
    }


def _extract_success_failure_counts(output: str, exit_code: int) -> dict[str, int]:
    success_patterns = (r"successful_runs=(\d+)", r"successes=(\d+)(?:/\d+)?")
    failure_patterns = (r"failed_runs=(\d+)", r"failures=(\d+)")
    successes = next((int(match.group(1)) for pattern in success_patterns if (match := re.search(pattern, output))), None)
    failures = next((int(match.group(1)) for pattern in failure_patterns if (match := re.search(pattern, output))), None)
    return {
        "successes": successes if successes is not None else int(exit_code == 0),
        "failures": failures if failures is not None else int(exit_code != 0),
    }


def _failure_class(stdout: str, stderr: str, exit_code: int) -> str:
    text = (stdout + "\n" + stderr).lower()
    if "assert" in text or "failed" in text:
        return "assertion_failure"
    if "not found" in text or "no such file" in text:
        return "missing_dependency"
    return f"exit_{exit_code}"


def _validation_output_hashes(
    results: list[dict[str, Any]], artifact_root: Path
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for result in results:
        for key in ("stdout_path", "stderr_path"):
            path = Path(result[key])
            try:
                relative = path.resolve(strict=True).relative_to(artifact_root.resolve(strict=True))
            except (OSError, ValueError) as exc:
                raise RoutePatchError("Validation output escaped its artifact root") from exc
            hashes[relative.as_posix()] = _sha256_file(path)
    return hashes


def _remove_worktree(repo_root: Path, path: Path, *, patch_dir: Path) -> None:
    raw_path = str(path)
    if path.is_symlink():
        raise RoutePatchError("Refusing symlinked worktree cleanup target")
    resolved_path = path.resolve()
    expected_paths = {
        _worktree_path(patch_dir, "candidate-worktree"),
        _worktree_path(patch_dir, "parent-worktree"),
    }
    protected_paths = {repo_root.resolve(), Path.cwd().resolve(), Path(resolved_path.anchor)}
    if (
        raw_path in {"", "."}
        or resolved_path in protected_paths
        or resolved_path not in expected_paths
    ):
        raise RoutePatchError(f"Refusing unsafe worktree cleanup target: {path}")
    try:
        removal = subprocess.run(
            ["git", "worktree", "remove", "--force", str(resolved_path)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if removal.returncode != 0 and resolved_path.exists():
            LOGGER.warning(
                "route_patch_worktree_remove_failed path=%s returncode=%d stderr=%s",
                resolved_path,
                removal.returncode,
                removal.stderr.strip(),
            )
    finally:
        if resolved_path.exists():
            try:
                shutil.rmtree(resolved_path)
            except OSError:
                LOGGER.exception(
                    "route_patch_worktree_cleanup_failed path=%s", resolved_path
                )
        prune = subprocess.run(
            ["git", "worktree", "prune"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if prune.returncode != 0:
            LOGGER.warning(
                "route_patch_worktree_prune_failed returncode=%d stderr=%s",
                prune.returncode,
                prune.stderr.strip(),
            )


def _git_blob(repo_root: Path, commit: str, path: str) -> bytes:
    mode_line = _git_text(repo_root, "ls-tree", commit, "--", path).strip()
    if not mode_line:
        raise RoutePatchError(f"File is absent from repository base: {path}")
    if mode_line.startswith("120000 "):
        raise RoutePatchError(f"Symlink patch targets are forbidden: {path}")
    completed = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RoutePatchError(f"Cannot read repository preimage for {path}")
    return completed.stdout


def _git(repo_root: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RoutePatchError(f"git {' '.join(args)} failed: {detail}")


def _git_text(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RoutePatchError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout


def _git_lines(repo_root: Path, *args: str) -> list[str]:
    return sorted(line for line in _git_text(repo_root, *args).splitlines() if line)


def _repo_root(path: Path | None) -> Path:
    resolved = (path or Path.cwd()).resolve()
    top = _git_text(resolved, "rev-parse", "--show-toplevel").strip()
    return Path(top).resolve()


def _confined_path(root: Path, relative: str, label: str) -> Path:
    normalized = _validate_relative_path(relative)
    return _safe_input_path(root, root / normalized, label)


def _safe_input_path(root: Path, candidate: Path, label: str) -> Path:
    root_real = os.path.realpath(os.fspath(root))
    safe_prefix = root_real.rstrip(os.sep) + os.sep
    candidate_absolute = os.path.abspath(os.path.expanduser(os.fspath(candidate)))
    if not candidate_absolute.startswith(safe_prefix):
        raise RoutePatchError(f"{label} escapes its allowed root")
    if Path(candidate_absolute).is_symlink():
        raise RoutePatchError(f"{label} must not be a symlink")
    candidate_real = os.path.realpath(candidate_absolute)
    if not candidate_real.startswith(safe_prefix):
        raise RoutePatchError(f"{label} escapes its allowed root")
    return Path(candidate_real)


def _artifact_root(repo_root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else repo_root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise RoutePatchError("Route-patch artifact roots must stay inside the repository") from exc
    return resolved


def _read_patch_yaml(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RoutePatchError("Patch document must be a regular non-symlink file")
    if path.stat().st_size > MAX_PATCH_BYTES:
        raise RoutePatchError(f"Patch document exceeds {MAX_PATCH_BYTES} bytes")
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise RoutePatchError("Patch document has malformed UTF-8 encoding") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RoutePatchError(f"Malformed patch YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise RoutePatchError("Patch document must contain a mapping")
    return data


def _read_yaml(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RoutePatchError(f"Required artifact is missing: {path}")
    if path.stat().st_size > MAX_RECORD_BYTES:
        raise RoutePatchError(f"YAML artifact is unexpectedly large: {path}")
    try:
        data = yaml.safe_load(
            path.read_text(encoding="utf-8", errors="strict")
        )
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise RoutePatchError(f"Malformed YAML artifact: {path}") from exc
    if not isinstance(data, dict):
        raise RoutePatchError(f"YAML artifact must contain a mapping: {path}")
    return data


def _atomic_write_yaml(path: Path, data: Mapping[str, Any]) -> None:
    content = yaml.safe_dump(dict(data), sort_keys=False, allow_unicode=True).encode("utf-8")
    _atomic_write_bytes(path, content)


def _reject_forbidden_declarations(value: Any, path: str = "patch") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_DECLARATION_KEYS:
                raise RoutePatchError(
                    f"Patch contains forbidden approval, validation, or command declaration: {path}.{key}"
                )
            _reject_forbidden_declarations(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden_declarations(nested, f"{path}[{index}]")


def _validate_id(raw: Any, label: str) -> str:
    value = str(raw or "")
    if not PATCH_ID_PATTERN.fullmatch(value):
        raise RoutePatchError(f"Invalid {label}: {value!r}")
    return value


def _verify_record_hash(path: Path, expected: Any, label: str) -> None:
    if not isinstance(expected, str) or _sha256_file(path) != expected:
        raise RoutePatchError(f"{label} changed after it was recorded")


def _sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise RoutePatchError(f"Cannot hash non-regular artifact: {path}")
    return _sha256_bytes(path.read_bytes())


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _exception_record(exc: Exception) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }


def _coerce_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
