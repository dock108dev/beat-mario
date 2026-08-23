from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from smb3_agent.companion_catalog import (
    AdapterCatalogEntry,
    AdapterRuntimeState,
    CatalogCapability,
    CatalogEvidence,
    CatalogGoal,
    CatalogObservation,
    CatalogProfile,
    CatalogSafety,
    CatalogScope,
)


CONTRACT_VERSION = "game-companion-experimental-adapter/v1"
INSTALL_MANIFEST_VERSION = "game-companion-experimental-install/v1"
CONFORMANCE_VERSION = "game-companion-experimental-conformance/v1"
EXPERIMENTAL_STATUS = "Experimental"
PROOF_LIMITS = (
    "real-game compatibility",
    "live observation correctness",
    "effective input",
    "reliability",
    "authoritative completion",
    "usefulness",
    "owner acceptance",
    "supported-catalog eligibility",
)
RESERVED_IDS = frozenset(
    {
        "mario",
        "smb3",
        "super-mario-bros-3",
        "stardew",
        "stardew-valley",
        "game-companion",
        "core",
        "lab",
        "experimental",
    }
)
ALLOWED_FILES = frozenset(
    {
        "adapter.yaml",
        "README.md",
        "fixtures/observation-idle.json",
        "fixtures/observation-progress.json",
        "fixtures/input-neutral.json",
        "fixtures/reclaim.json",
        "fixtures/goal-complete.json",
    }
)
ACTIVE_STATE_FILES = frozenset(
    {"active-process.json", "active-authority.json", "active-input.json", "active-session.json"}
)
ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
TOKEN_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MAX_CONTRACT_BYTES = 256 * 1024
MAX_FIXTURE_BYTES = 1024 * 1024
MAX_INSTALL_MANIFEST_BYTES = 256 * 1024


class ExperimentalAdapterError(ValueError):
    pass


class InstallationRefused(ExperimentalAdapterError):
    pass


class RemovalRefused(ExperimentalAdapterError):
    pass


@dataclass(frozen=True)
class ContractInspection:
    adapter_id: str
    display_name: str
    state: str
    installed: bool
    conformant: bool
    live_proven: bool
    supported: bool
    contract_hash: str
    proof_limits: tuple[str, ...] = PROOF_LIMITS


@dataclass(frozen=True)
class ConformanceCheck:
    check_id: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ConformanceReport:
    schema_version: str
    adapter_id: str
    contract_hash: str
    overall_pass: bool
    classification: str
    checks: tuple[ConformanceCheck, ...]
    proof_limits: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_scaffold_root() -> Path:
    return Path("experimental-adapters")


def default_install_root() -> Path:
    configured = os.environ.get("GAME_COMPANION_EXPERIMENTAL_ROOT")
    if configured:
        return Path(configured)
    return Path.home() / "Library" / "Application Support" / "Game Companion" / "Experimental Adapters"


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _read_bounded_text(path: Path, *, limit: int, field: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise ExperimentalAdapterError(f"{field} must be a regular non-symlinked file")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ExperimentalAdapterError(f"cannot inspect {field}: {exc}") from exc
    if size > limit:
        raise ExperimentalAdapterError(f"{field} exceeds the {limit}-byte limit")
    try:
        return path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise ExperimentalAdapterError(f"cannot read {field}: {exc}") from exc


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExperimentalAdapterError(f"{field} must be a non-empty string")
    if any(ord(character) < 32 for character in value):
        raise ExperimentalAdapterError(f"{field} contains control characters")
    return value.strip()


def _require_mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExperimentalAdapterError(f"{field} must be an object")
    return dict(value)


def _require_list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ExperimentalAdapterError(f"{field} must be a non-empty list")
    return list(value)


def _validate_identifier(value: object, field: str, *, adapter: bool = False) -> str:
    text = _require_string(value, field)
    pattern = ID_PATTERN if adapter else TOKEN_PATTERN
    if not pattern.fullmatch(text):
        raise ExperimentalAdapterError(f"{field} has an invalid identifier")
    if adapter and text in RESERVED_IDS:
        raise ExperimentalAdapterError(f"reserved or built-in adapter id: {text}")
    return text


def _validate_relative_path(value: object, field: str) -> str:
    text = _require_string(value, field)
    candidate = Path(text)
    if candidate.is_absolute() or ".." in candidate.parts or text.startswith(("~", "/")):
        raise ExperimentalAdapterError(f"{field} must be a bounded relative path")
    if any(part in {"", "."} for part in candidate.parts):
        raise ExperimentalAdapterError(f"{field} has an ambiguous path")
    return candidate.as_posix()


def _reject_executable_content(payload: object, field: str = "contract") -> None:
    forbidden_keys = {
        "command",
        "commands",
        "shell",
        "script",
        "code",
        "module",
        "python",
        "javascript",
        "url",
        "network",
        "dependency",
        "dependencies",
    }
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in forbidden_keys:
                raise ExperimentalAdapterError(f"{field} cannot declare executable or network content: {key}")
            _reject_executable_content(value, f"{field}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _reject_executable_content(value, f"{field}[{index}]")
    elif isinstance(payload, str):
        lowered = payload.lower()
        markers = ("#!", "<script", "$(", "`", " /bin/sh", "python -c", "pip install", "npm install", "http://", "https://")
        if any(marker in lowered for marker in markers):
            raise ExperimentalAdapterError(f"{field} contains executable or network content")


def validate_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    contract = dict(payload)
    _reject_executable_content(contract)
    allowed_top = {
        "schema_version",
        "identity",
        "detection",
        "observation",
        "input",
        "ownership",
        "capabilities",
        "goals",
        "solution_profiles",
        "protected_actions",
        "takeover_scopes",
        "fixtures",
        "evidence",
        "proof_limits",
        "installation",
        "removal",
    }
    unknown = sorted(set(contract) - allowed_top)
    if unknown:
        raise ExperimentalAdapterError(f"unknown contract fields: {', '.join(unknown)}")
    if contract.get("schema_version") != CONTRACT_VERSION:
        raise ExperimentalAdapterError(f"schema_version must be {CONTRACT_VERSION}")

    identity = _require_mapping(contract.get("identity"), "identity")
    allowed_identity = {"adapter_id", "game_id", "display_name", "adapter_version", "description", "status"}
    if set(identity) - allowed_identity:
        raise ExperimentalAdapterError("identity contains unknown fields")
    adapter_id = _validate_identifier(identity.get("adapter_id"), "identity.adapter_id", adapter=True)
    game_id = _validate_identifier(identity.get("game_id"), "identity.game_id", adapter=True)
    if adapter_id in {"mario", "smb3", "stardew"} or game_id in {"mario", "smb3", "stardew"}:
        raise ExperimentalAdapterError("Mario and Stardew identities are reserved built-ins")
    _require_string(identity.get("display_name"), "identity.display_name")
    _validate_identifier(identity.get("adapter_version"), "identity.adapter_version")
    _require_string(identity.get("description"), "identity.description")
    if identity.get("status") != EXPERIMENTAL_STATUS:
        raise ExperimentalAdapterError("Experimental adapters cannot promote their status")

    detection = _require_mapping(contract.get("detection"), "detection")
    if set(detection) != {"executable_names", "window_title_contains", "continuity_fields"}:
        raise ExperimentalAdapterError("detection fields must be exact and declarative")
    for index, name in enumerate(_require_list(detection["executable_names"], "detection.executable_names")):
        text = _require_string(name, f"detection.executable_names[{index}]")
        if Path(text).name != text or any(symbol in text for symbol in ("/", "\\", ";", "|", "&", "$", "`")):
            raise ExperimentalAdapterError("executable detection accepts names only, not paths or commands")
    for index, title in enumerate(_require_list(detection["window_title_contains"], "detection.window_title_contains")):
        _require_string(title, f"detection.window_title_contains[{index}]")
    continuity = tuple(_require_list(detection["continuity_fields"], "detection.continuity_fields"))
    if set(continuity) != {"process_id", "window_id", "executable_identity", "session_nonce"}:
        raise ExperimentalAdapterError("detection must bind all continuity fields")

    observation = _require_mapping(contract.get("observation"), "observation")
    if observation.get("method") not in {"screen_capture", "accessibility_read_only"}:
        raise ExperimentalAdapterError("observation.method must be a declared read-only method")
    if observation.get("transport") != "local_only" or observation.get("mutation") != "none":
        raise ExperimentalAdapterError("observation must remain local-only and read-only")
    envelope = _require_list(observation.get("envelope_fields"), "observation.envelope_fields")
    if not {"observed_at", "freshness", "facts", "unknowns", "source"}.issubset(envelope):
        raise ExperimentalAdapterError("observation envelope is incomplete")

    input_contract = _require_mapping(contract.get("input"), "input")
    if input_contract.get("method") not in {"ordinary_keyboard", "ordinary_controller"}:
        raise ExperimentalAdapterError("input.method must use ordinary local input")
    if input_contract.get("dispatch") != "host_owned_allowlist":
        raise ExperimentalAdapterError("input dispatch must use the host-owned allowlist")
    actions = _require_list(input_contract.get("allowed_actions"), "input.allowed_actions")
    if any(not TOKEN_PATTERN.fullmatch(_require_string(item, "input action")) for item in actions):
        raise ExperimentalAdapterError("input actions must be declarative tokens")
    if "neutral" not in actions:
        raise ExperimentalAdapterError("input actions must include neutral")

    ownership = _require_mapping(contract.get("ownership"), "ownership")
    required_ownership = {
        "default_owner": "player",
        "authorization": "fresh_same_process",
        "reclaim": "immediate",
        "handback": "neutral_then_confirmed",
        "ambiguity": "fail_closed",
    }
    if any(ownership.get(key) != value for key, value in required_ownership.items()):
        raise ExperimentalAdapterError("ownership, reclaim, and handback must use the fail-closed contract")

    capabilities = _require_list(contract.get("capabilities"), "capabilities")
    capability_ids: set[str] = set()
    for index, item in enumerate(capabilities):
        capability = _require_mapping(item, f"capabilities[{index}]")
        capability_id = _validate_identifier(capability.get("id"), "capability id")
        if capability_id in capability_ids:
            raise ExperimentalAdapterError("duplicate capability id")
        capability_ids.add(capability_id)
        if capability.get("state") not in {"declared", "unsupported"}:
            raise ExperimentalAdapterError("capabilities may be declared or unsupported before live proof")
        _require_string(capability.get("description"), "capability description")
    if {"tell", "show", "do"} - capability_ids:
        raise ExperimentalAdapterError(
            "capabilities must explicitly declare Tell, Show, and Do"
        )

    goals = _require_list(contract.get("goals"), "goals")
    goal_ids: set[str] = set()
    for index, item in enumerate(goals):
        goal = _require_mapping(item, f"goals[{index}]")
        goal_id = _validate_identifier(goal.get("id"), "goal id")
        goal_ids.add(goal_id)
        requirements = _require_list(goal.get("requirements"), "goal requirements")
        if not all(isinstance(req, dict) and req.get("fact") and req.get("operator") in {"eq", "gte", "lte"} and "value" in req for req in requirements):
            raise ExperimentalAdapterError("goals require measurable fact/operator/value requirements")
        _require_list(goal.get("evidence_fields"), "goal evidence_fields")

    profiles = _require_list(contract.get("solution_profiles"), "solution_profiles")
    for item in profiles:
        profile = _require_mapping(item, "solution profile")
        _validate_identifier(profile.get("id"), "solution profile id")
        if profile.get("goal_id") not in goal_ids:
            raise ExperimentalAdapterError("solution profile references an unknown goal")
        if profile.get("execution") not in {"fixture_only", "unsupported"}:
            raise ExperimentalAdapterError("generated solution profiles cannot contain executable code")

    protected = _require_list(contract.get("protected_actions"), "protected_actions")
    for item in protected:
        _validate_identifier(item, "protected action")
    scopes = _require_list(contract.get("takeover_scopes"), "takeover_scopes")
    for item in scopes:
        scope = _require_mapping(item, "takeover scope")
        _validate_identifier(scope.get("id"), "takeover scope id")
        _require_list(scope.get("stop_conditions"), "takeover scope stop_conditions")
        if scope.get("state") not in {"declared", "unsupported"}:
            raise ExperimentalAdapterError("takeover scope state is invalid")

    fixtures = _require_mapping(contract.get("fixtures"), "fixtures")
    for name, value in fixtures.items():
        _validate_identifier(name, "fixture id")
        path = _validate_relative_path(value, f"fixtures.{name}")
        if path not in ALLOWED_FILES:
            raise ExperimentalAdapterError(f"unknown fixture file: {path}")

    evidence = _require_mapping(contract.get("evidence"), "evidence")
    namespace = _validate_identifier(evidence.get("namespace"), "evidence.namespace")
    if namespace != f"experimental.{adapter_id}":
        raise ExperimentalAdapterError("evidence namespace must be adapter-owned and isolated")
    if evidence.get("storage") != "local_adapter_namespace" or evidence.get("promotion") != "never_automatic":
        raise ExperimentalAdapterError("evidence must be isolated and never automatically promoted")
    _require_list(evidence.get("classifications"), "evidence.classifications")

    limits = tuple(_require_list(contract.get("proof_limits"), "proof_limits"))
    if set(limits) != set(PROOF_LIMITS):
        raise ExperimentalAdapterError("proof_limits must state every conformance limitation")

    installation = _require_mapping(contract.get("installation"), "installation")
    if installation.get("owner") != "local_manifest" or installation.get("atomic") is not True or installation.get("overwrite") != "refuse":
        raise ExperimentalAdapterError("installation ownership must be atomic, manifest-owned, and collision-refusing")
    inventory = tuple(_require_list(installation.get("inventory"), "installation.inventory"))
    if set(inventory) != ALLOWED_FILES:
        raise ExperimentalAdapterError("installation inventory must exactly match the bounded scaffold")

    removal = _require_mapping(contract.get("removal"), "removal")
    if removal.get("policy") != "exact_manifest_owned_only" or removal.get("modified_files") != "refuse" or removal.get("preserve") != ["evidence", "history"]:
        raise ExperimentalAdapterError("removal must be exact, fail closed, and preserve evidence/history")
    if set(_require_list(removal.get("zero_residual_proofs"), "removal.zero_residual_proofs")) != {"process", "authority", "input", "session"}:
        raise ExperimentalAdapterError("removal requires zero process, authority, input, and session proof")
    return contract


def load_contract(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(
        _read_bounded_text(
            path,
            limit=MAX_CONTRACT_BYTES,
            field="adapter contract",
        )
    )
    if not isinstance(raw, dict):
        raise ExperimentalAdapterError("adapter contract must be a mapping")
    return validate_contract(raw)


def inspect_contract(path: Path, *, installed: bool = False, conformant: bool = False) -> ContractInspection:
    contract = load_contract(path)
    identity = contract["identity"]
    state = "installed" if installed else "conformant" if conformant else "declared"
    return ContractInspection(
        adapter_id=identity["adapter_id"],
        display_name=identity["display_name"],
        state=state,
        installed=installed,
        conformant=conformant,
        live_proven=False,
        supported=False,
        contract_hash=_sha256_bytes(_canonical_bytes(contract)),
    )


def scaffold_payload(adapter_id: str, display_name: str) -> dict[str, Any]:
    _validate_identifier(adapter_id, "adapter_id", adapter=True)
    _require_string(display_name, "display_name")
    return {
        "schema_version": CONTRACT_VERSION,
        "identity": {
            "adapter_id": adapter_id,
            "game_id": adapter_id,
            "display_name": display_name,
            "adapter_version": "v1",
            "description": "Fixture-only Experimental adapter scaffold.",
            "status": EXPERIMENTAL_STATUS,
        },
        "detection": {
            "executable_names": [f"{adapter_id}-game"],
            "window_title_contains": [display_name],
            "continuity_fields": ["process_id", "window_id", "executable_identity", "session_nonce"],
        },
        "observation": {
            "method": "screen_capture",
            "transport": "local_only",
            "mutation": "none",
            "envelope_fields": ["observed_at", "freshness", "facts", "unknowns", "source"],
        },
        "input": {
            "method": "ordinary_keyboard",
            "dispatch": "host_owned_allowlist",
            "allowed_actions": ["neutral", "up", "down", "left", "right", "confirm", "cancel"],
        },
        "ownership": {
            "default_owner": "player",
            "authorization": "fresh_same_process",
            "reclaim": "immediate",
            "handback": "neutral_then_confirmed",
            "ambiguity": "fail_closed",
        },
        "capabilities": [
            {"id": "observe", "state": "declared", "description": "Fixture observation only."},
            {"id": "tell", "state": "declared", "description": "Fixture-grounded guidance only."},
            {"id": "show", "state": "unsupported", "description": "No executable solution is generated."},
            {"id": "do", "state": "unsupported", "description": "No live input implementation is generated."},
        ],
        "goals": [{
            "id": "fixture-goal",
            "label": "Reach fixture progress",
            "requirements": [{"fact": "progress", "operator": "gte", "value": 1}],
            "evidence_fields": ["observed_at", "facts.progress", "source"],
        }],
        "solution_profiles": [{"id": "fixture-normal", "goal_id": "fixture-goal", "execution": "fixture_only"}],
        "protected_actions": ["purchase", "delete-save", "multiplayer", "account-change", "permanent-choice"],
        "takeover_scopes": [{"id": "fixture-step", "state": "unsupported", "stop_conditions": ["goal-complete", "reclaim", "timeout", "observation-unknown"]}],
        "fixtures": {
            "observation-idle": "fixtures/observation-idle.json",
            "observation-progress": "fixtures/observation-progress.json",
            "input-neutral": "fixtures/input-neutral.json",
            "reclaim": "fixtures/reclaim.json",
            "goal-complete": "fixtures/goal-complete.json",
        },
        "evidence": {
            "namespace": f"experimental.{adapter_id}",
            "storage": "local_adapter_namespace",
            "promotion": "never_automatic",
            "classifications": ["fixture", "technical", "owner_feedback"],
        },
        "proof_limits": list(PROOF_LIMITS),
        "installation": {"owner": "local_manifest", "atomic": True, "overwrite": "refuse", "inventory": sorted(ALLOWED_FILES)},
        "removal": {"policy": "exact_manifest_owned_only", "modified_files": "refuse", "preserve": ["evidence", "history"], "zero_residual_proofs": ["process", "authority", "input", "session"]},
    }


def _fixture_payloads(adapter_id: str) -> dict[str, Mapping[str, Any]]:
    base = {"schema_version": "game-companion-observation/v1", "adapter_id": adapter_id, "freshness": "fixture", "source": "fixture", "unknowns": []}
    return {
        "fixtures/observation-idle.json": base | {"observed_at": "fixture:idle", "facts": {"progress": 0}},
        "fixtures/observation-progress.json": base | {"observed_at": "fixture:progress", "facts": {"progress": 1}},
        "fixtures/input-neutral.json": {"schema_version": "game-companion-input/v1", "adapter_id": adapter_id, "actor": "none", "action": "neutral"},
        "fixtures/reclaim.json": {"schema_version": "game-companion-reclaim/v1", "adapter_id": adapter_id, "owner_before": "agent", "neutralized": True, "owner_after": "player", "handback_confirmed": True},
        "fixtures/goal-complete.json": {"schema_version": "game-companion-goal-evidence/v1", "adapter_id": adapter_id, "goal_id": "fixture-goal", "facts": {"progress": 1}, "authoritative": False},
    }


def _bounded_child(root: Path, child: str) -> Path:
    root_resolved = root.resolve(strict=False)
    target = root / child
    target_resolved = target.resolve(strict=False)
    if target_resolved.parent != root_resolved:
        raise ExperimentalAdapterError("adapter target escapes the bounded root")
    return target


def _cleanup_failed_staging(
    temporary: Path,
    operation: str,
    operation_error: Exception,
) -> None:
    if not temporary.exists():
        return
    try:
        shutil.rmtree(temporary)
    except OSError as cleanup_error:
        raise ExperimentalAdapterError(
            f"{operation} failed ({type(operation_error).__name__}: {operation_error}); "
            f"staging cleanup also failed ({type(cleanup_error).__name__}: "
            f"{cleanup_error}); inspect retained path: {temporary}"
        ) from operation_error


def scaffold_adapter(root: Path, adapter_id: str, display_name: str) -> Path:
    payload = validate_contract(scaffold_payload(adapter_id, display_name))
    if root.is_symlink():
        raise ExperimentalAdapterError("scaffold root symlinks are refused")
    target = _bounded_child(root, adapter_id)
    if target.exists() or target.is_symlink():
        raise ExperimentalAdapterError("scaffold target already exists; overwrite refused")
    root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{adapter_id}-", dir=root))
    try:
        (temporary / "fixtures").mkdir()
        (temporary / "adapter.yaml").write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        readme = (
            f"# {display_name}\n\nExperimental fixture-only Game Companion adapter.\n\n"
            "Generated files are declarative and non-executable. Conformance does not prove live compatibility or support.\n"
        )
        (temporary / "README.md").write_text(readme, encoding="utf-8")
        for relative, fixture in _fixture_payloads(adapter_id).items():
            (temporary / relative).write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, target)
    except Exception as exc:
        _cleanup_failed_staging(temporary, "adapter scaffold", exc)
        raise
    return target


def _source_inventory(source: Path) -> dict[str, str]:
    if source.is_symlink() or not source.is_dir():
        raise ExperimentalAdapterError("adapter source must be a real directory")
    inventory: dict[str, str] = {}
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ExperimentalAdapterError("adapter source cannot contain symlinks")
        if path.is_dir():
            continue
        relative = path.relative_to(source).as_posix()
        if relative not in ALLOWED_FILES:
            raise ExperimentalAdapterError(f"unknown adapter file: {relative}")
        inventory[relative] = _sha256_file(path)
    if set(inventory) != ALLOWED_FILES:
        missing = sorted(ALLOWED_FILES - set(inventory))
        raise ExperimentalAdapterError(f"adapter inventory is incomplete: {', '.join(missing)}")
    return inventory


def run_conformance(source: Path) -> ConformanceReport:
    contract = load_contract(source / "adapter.yaml")
    inventory = _source_inventory(source)
    adapter_id = contract["identity"]["adapter_id"]
    fixtures = {
        path: json.loads(
            _read_bounded_text(
                source / path,
                limit=MAX_FIXTURE_BYTES,
                field=f"adapter fixture {path}",
            )
        )
        for path in sorted(ALLOWED_FILES)
        if path.endswith(".json")
    }
    checks = (
        ConformanceCheck("schema", True, "versioned contract and exact fields validate"),
        ConformanceCheck("provider_truth", contract["identity"]["status"] == EXPERIMENTAL_STATUS, "provider cannot self-promote"),
        ConformanceCheck("observation_envelopes", all(item.get("adapter_id") == adapter_id for path, item in fixtures.items() if "observation" in path), "fixtures stay adapter-bound"),
        ConformanceCheck("capability_agreement", all(item["state"] in {"declared", "unsupported"} for item in contract["capabilities"]), "declared is not live-proven"),
        ConformanceCheck("ownership_reclaim", fixtures["fixtures/reclaim.json"].get("neutralized") is True and fixtures["fixtures/reclaim.json"].get("owner_after") == "player", "neutral player handback fixture agrees"),
        ConformanceCheck("protected_action_refusal", bool(contract["protected_actions"]), "protected actions are declarative host refusals"),
        ConformanceCheck("measurable_goals", bool(contract["goals"][0]["requirements"]), "goal uses measurable facts"),
        ConformanceCheck("evidence_isolation", contract["evidence"]["namespace"] == f"experimental.{adapter_id}", "adapter evidence namespace is isolated"),
        ConformanceCheck("persistence_isolation", contract["installation"]["owner"] == "local_manifest", "installation is manifest-owned"),
        ConformanceCheck("installation_integrity", set(inventory) == ALLOWED_FILES and all(HASH_PATTERN.fullmatch(value) for value in inventory.values()), "exact inventory hashes prepared"),
        ConformanceCheck("removal", contract["removal"]["policy"] == "exact_manifest_owned_only", "removal is exact and fail closed"),
        ConformanceCheck("catalog_labeling", contract["identity"]["status"] == EXPERIMENTAL_STATUS, "catalog eligibility remains Experimental"),
        ConformanceCheck("no_shared_core_edit", True, "provider discovery reads only the installed adapter root"),
    )
    overall = all(item.passed for item in checks)
    return ConformanceReport(CONFORMANCE_VERSION, adapter_id, _sha256_bytes(_canonical_bytes(contract)), overall, "conformant" if overall else "declared", checks, PROOF_LIMITS)


def install_adapter(source: Path, install_root: Path) -> Path:
    report = run_conformance(source)
    if not report.overall_pass:
        raise InstallationRefused("adapter is not conformant")
    contract = load_contract(source / "adapter.yaml")
    adapter_id = contract["identity"]["adapter_id"]
    inventory = _source_inventory(source)
    if install_root.is_symlink():
        raise InstallationRefused("installation root symlinks are refused")
    install_root.mkdir(parents=True, exist_ok=True)
    target = _bounded_child(install_root, adapter_id)
    if target.exists() or target.is_symlink():
        raise InstallationRefused("installation collision; overwrite refused")
    temporary = Path(tempfile.mkdtemp(prefix=f".{adapter_id}-install-", dir=install_root))
    try:
        for relative in sorted(inventory):
            destination = temporary / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, destination, follow_symlinks=False)
            if _sha256_file(destination) != inventory[relative]:
                raise InstallationRefused(f"staged installation hash mismatch: {relative}")
        manifest = {
            "schema_version": INSTALL_MANIFEST_VERSION,
            "adapter_id": adapter_id,
            "status": EXPERIMENTAL_STATUS,
            "contract_hash": report.contract_hash,
            "files": inventory,
            "owned_state_files": sorted(ACTIVE_STATE_FILES),
            "preserved_namespaces": [f"evidence/experimental.{adapter_id}", f"history/experimental.{adapter_id}"],
        }
        (temporary / ".installation.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, target)
    except Exception as exc:
        _cleanup_failed_staging(temporary, "adapter installation", exc)
        raise
    return target


def load_install_manifest(target: Path) -> dict[str, Any]:
    path = target / ".installation.json"
    if target.is_symlink() or path.is_symlink():
        raise InstallationRefused("installed adapter or manifest symlink refused")
    raw = json.loads(
        _read_bounded_text(
            path,
            limit=MAX_INSTALL_MANIFEST_BYTES,
            field="installation manifest",
        )
    )
    if raw.get("schema_version") != INSTALL_MANIFEST_VERSION or not isinstance(raw.get("files"), dict):
        raise InstallationRefused("invalid installation manifest")
    if set(raw) != {"schema_version", "adapter_id", "status", "contract_hash", "files", "owned_state_files", "preserved_namespaces"}:
        raise InstallationRefused("installation manifest fields are ambiguous")
    adapter_id = _validate_identifier(raw.get("adapter_id"), "manifest adapter_id", adapter=True)
    if raw.get("status") != EXPERIMENTAL_STATUS or not HASH_PATTERN.fullmatch(str(raw.get("contract_hash", ""))):
        raise InstallationRefused("installation manifest identity or contract hash is invalid")
    if set(raw["files"]) != ALLOWED_FILES or any(not HASH_PATTERN.fullmatch(str(value)) for value in raw["files"].values()):
        raise InstallationRefused("installation manifest inventory or hashes are invalid")
    if set(raw.get("owned_state_files", ())) != ACTIVE_STATE_FILES:
        raise InstallationRefused("installation active-state ownership is invalid")
    if raw.get("preserved_namespaces") != [f"evidence/experimental.{adapter_id}", f"history/experimental.{adapter_id}"]:
        raise InstallationRefused("installation evidence/history ownership is invalid")
    return raw


def installation_status(install_root: Path, adapter_id: str | None = None) -> list[dict[str, Any]]:
    if not install_root.exists():
        return []
    if install_root.is_symlink():
        raise InstallationRefused("installation root symlink refused")
    targets = [_bounded_child(install_root, adapter_id)] if adapter_id else sorted(path for path in install_root.iterdir() if path.is_dir() and not path.name.startswith("."))
    result = []
    for target in targets:
        if not target.exists():
            continue
        manifest = load_install_manifest(target)
        modified = []
        for relative, expected in manifest["files"].items():
            path = target / _validate_relative_path(relative, "manifest file")
            if not path.is_file() or path.is_symlink() or _sha256_file(path) != expected:
                modified.append(relative)
        expected_directories = {Path(relative).parent.as_posix() for relative in manifest["files"] if Path(relative).parent != Path(".")}
        unknown = sorted(
            path.relative_to(target).as_posix()
            for path in target.rglob("*")
            if (
                path.relative_to(target).as_posix() not in manifest["files"]
                and path.relative_to(target).as_posix() not in expected_directories
                and path.name != ".installation.json"
                and path.name not in ACTIVE_STATE_FILES
            )
        )
        result.append({"adapter_id": manifest["adapter_id"], "state": "installed", "status": EXPERIMENTAL_STATUS, "integrity": "clean" if not modified and not unknown else "refused", "modified": modified, "unknown": unknown, "live_proven": False, "supported": False})
    return result


def uninstall_adapter(install_root: Path, adapter_id: str) -> dict[str, Any]:
    _validate_identifier(adapter_id, "adapter_id", adapter=True)
    target = _bounded_child(install_root, adapter_id)
    manifest = load_install_manifest(target)
    if manifest.get("adapter_id") != adapter_id:
        raise RemovalRefused("installation ownership is ambiguous")
    status = installation_status(install_root, adapter_id)[0]
    if status["modified"] or status["unknown"]:
        raise RemovalRefused("modified, missing, or unknown files refuse removal")
    active = sorted(name for name in ACTIVE_STATE_FILES if (target / name).exists() or (target / name).is_symlink())
    if active:
        raise RemovalRefused(f"active process, authority, input, or session proof remains: {', '.join(active)}")
    owned = [target / _validate_relative_path(relative, "manifest file") for relative in manifest["files"]]
    for path in owned:
        path.unlink()
    (target / ".installation.json").unlink()
    for directory in sorted((path for path in target.rglob("*") if path.is_dir()), reverse=True):
        directory.rmdir()
    target.rmdir()
    return {"adapter_id": adapter_id, "removed": True, "zero_residual": {"process": True, "authority": True, "input": True, "session": True}, "preserved": ["evidence", "history"]}


class ExperimentalCatalogProvider:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.contract = load_contract(directory / "adapter.yaml")

    def catalog_entry(self) -> AdapterCatalogEntry:
        contract = self.contract
        identity = contract["identity"]
        capabilities = tuple(
            CatalogCapability(
                item["id"],
                item["id"].replace("-", " ").title(),
                "implementation_validation_deferred"
                if item["state"] == "declared"
                else "unavailable",
                item["description"],
                "Declared by an Experimental adapter; live validation is deferred."
                if item["state"] == "declared"
                else "Adapter declares this capability unsupported.",
            )
            for item in contract["capabilities"]
        )
        goals = tuple(CatalogGoal(item["id"], item.get("label", item["id"]), "Experimental measurable goal; fixture conformance only.", tuple(profile["id"] for profile in contract["solution_profiles"] if profile["goal_id"] == item["id"])) for item in contract["goals"])
        profiles = tuple(CatalogProfile(item["id"], item["id"].replace("-", " ").title(), item["execution"], "Experimental profile; not live-proven or executable unless separately implemented and accepted.") for item in contract["solution_profiles"])
        scopes = tuple(CatalogScope(item["id"], item["id"].replace("-", " ").title(), tuple(item["stop_conditions"])) for item in contract["takeover_scopes"])
        return AdapterCatalogEntry(
            adapter_id=identity["adapter_id"], game_id=identity["game_id"], display_name=identity["display_name"],
            description=f"Experimental · installed · live-unproven. {identity['description']}", adapter_version=identity["adapter_version"],
            implementation_status="experimental_installed_live_unproven", availability="setup_required",
            availability_reason="Installed locally as Experimental; real-game compatibility and owner acceptance are unproven.", setup_state="installed_experimental",
            observation=CatalogObservation(contract["observation"]["method"], contract["observation"]["method"].replace("_", " ").title(), "Declared local observation; fixture conformance only."),
            capabilities=capabilities, goals=goals, profiles=profiles, scopes=scopes,
            safety=CatalogSafety("Experimental fail-closed ownership policy.", tuple(contract["protected_actions"]), "Stop on ambiguity, unknown observation, timeout, or reclaim.", "Player reclaim is immediate.", "Neutral input before confirmed player handback."),
            evidence=CatalogEvidence(contract["evidence"]["namespace"], tuple(contract["evidence"]["classifications"]), "Experimental evidence is isolated and cannot promote support."),
            standalone_surface="/lab#experimental-onboarding", recovery_guidance="Inspect installation integrity; remove only when zero active state is proven.",
        )

    def runtime_state(self) -> AdapterRuntimeState:
        return AdapterRuntimeState(adapter_id=self.contract["identity"]["adapter_id"])

    def retain_for_switch(self) -> bool:
        return True

    def invalidate_volatile_state(self) -> bool:
        return True


def discover_installed_providers(install_root: Path | None = None) -> tuple[ExperimentalCatalogProvider, ...]:
    root = install_root or default_install_root()
    if not root.exists():
        return ()
    if root.is_symlink():
        raise InstallationRefused("installation root symlink refused")
    providers = []
    for directory in sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")):
        manifest = load_install_manifest(directory)
        status = installation_status(root, manifest["adapter_id"])[0]
        if status["integrity"] != "clean":
            raise InstallationRefused(f"installed adapter integrity refused: {manifest['adapter_id']}")
        providers.append(ExperimentalCatalogProvider(directory))
    return tuple(providers)
