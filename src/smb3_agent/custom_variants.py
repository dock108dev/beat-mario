"""Local custom plans and attempts; saved data never carries control permission."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
from typing import Any, Callable
from uuid import uuid4


SCHEMA = "game-companion-custom-variant/v1"
_ID = re.compile(r"variant-[a-f0-9]{32}\Z")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _write_new(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def without_authority(plan: dict[str, Any]) -> dict[str, Any]:
    """Keep provenance, but never a nonce, live identity or executable permission."""
    result = deepcopy(plan)
    result["source_observation"] = {
        "session_id": result.get("session_id"),
        "observation_id": result.get("observation_id"),
    }
    result["session_id"] = None
    result["observation_id"] = None
    result["authorization_scope"] = {
        "granted": False,
        "reason": "Reopening requires a fresh compatible observation and explicit Start.",
    }
    result["execution_eligibility"] = "requires_fresh_validation"
    result["applied_speed"] = None
    for key in ("authorization", "nonce", "control_epoch", "runtime", "controller"):
        result.pop(key, None)
    return result


class CustomVariantStore:
    """Append-only revisions separate from accepted route and run registries."""

    def __init__(self, root: Path = Path("artifacts/custom-variants")) -> None:
        self.root = Path(root)
        self._lock = threading.RLock()

    def _directory(self, variant_id: str) -> Path:
        if not _ID.fullmatch(variant_id):
            raise ValueError("Unknown custom variant identity")
        path = self.root / variant_id
        if path.is_symlink():
            raise ValueError("Custom variant directory cannot be a symbolic link")
        return path

    def save(self, name: str, plan: dict[str, Any], *, variant_id: str | None = None,
             source_outcome_reference: str | None = None,
             runtime_evidence_reference: str | None = None) -> dict[str, Any]:
        name = name.strip()
        if not name or len(name) > 100:
            raise ValueError("Give the variant a name between 1 and 100 characters")
        if not plan.get("actions") or not plan.get("base_route_id"):
            raise ValueError("A custom variant needs a base route and actual planned actions")
        with self._lock:
            identity = variant_id or "variant-" + uuid4().hex
            directory = self._directory(identity)
            previous = self.load(identity) if variant_id else None
            directory.mkdir(parents=True, exist_ok=bool(variant_id))
            revision = previous["saved_revision"] + 1 if previous else 1
            saved_plan = without_authority(plan)
            saved_plan["variant_id"] = identity
            record = {
                "schema_version": SCHEMA,
                "variant_id": identity,
                "name": name,
                "created_at": _now(),
                "game_id": plan.get("game_id"),
                "base_route_id": plan["base_route_id"],
                "base_version": plan.get("base_version"),
                "parent_variant_id": plan.get("variant_id") if not previous else identity,
                "saved_revision": revision,
                "parent_saved_revision": previous["saved_revision"] if previous else None,
                "plan_revision": plan.get("revision"),
                "status": "saved",
                "route_classification": "custom_candidate",
                "accepted": False,
                "fastest": False,
                "completion_coverage": "unknown",
                "plan": saved_plan,
                "plan_sha256": hashlib.sha256(_canonical(saved_plan)).hexdigest(),
                "source_outcome_reference": source_outcome_reference,
                "runtime_evidence_reference": runtime_evidence_reference,
            }
            _write_new(directory / f"revision-{revision:06d}.json", record)
            return deepcopy(record)

    def load(
        self,
        variant_id: str,
        *,
        revision: int | None = None,
        game_id: str | None = None,
        validate: Callable[[dict[str, Any]], Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            directory = self._directory(variant_id)
            files = sorted(directory.glob("revision-*.json"))
            if not files:
                raise ValueError("Saved variant was not found")
            if revision is not None and (type(revision) is not int or revision < 1):
                raise ValueError("Invalid saved revision")
            path = directory / f"revision-{revision:06d}.json" if revision else files[-1]
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
                raise ValueError("Saved revision is unavailable or invalid")
            try:
                record = json.loads(path.read_text())
                plan = record["plan"]
                valid = (
                    record["schema_version"] == SCHEMA
                    and record["variant_id"] == variant_id
                    and record["saved_revision"] == int(path.stem.split("-")[1])
                    and record["plan_sha256"] == hashlib.sha256(_canonical(plan)).hexdigest()
                    and record["status"] == "saved"
                    and record["route_classification"] == "custom_candidate"
                    and record["accepted"] is False
                    and record["fastest"] is False
                    and plan.get("authorization_scope", {}).get("granted") is False
                    and plan.get("session_id") is None
                    and plan.get("observation_id") is None
                )
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError("Saved variant is corrupt; previous revisions are retained") from exc
            if not valid:
                raise ValueError("Saved variant integrity or permission check failed")
            if game_id and record.get("game_id") != game_id:
                raise ValueError("Saved variant belongs to a different game")
            if validate:
                validate(deepcopy(plan))
            return deepcopy(record)

    def list(self) -> list[dict[str, Any]]:
        records = []
        with self._lock:
            for directory in sorted(self.root.glob("variant-*")):
                try:
                    record = self.load(directory.name)
                    records.append({key: record[key] for key in (
                        "variant_id", "name", "saved_revision", "plan_revision", "status",
                        "base_route_id", "created_at", "route_classification",
                    )})
                except ValueError:
                    records.append({"variant_id": directory.name, "name": directory.name,
                                    "status": "unavailable", "reason": "Invalid saved record"})
        return records


class PlanAttemptHistory:
    """Retains every terminal outcome without promoting a partial run to success."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._lock = threading.RLock()

    def record(self, attempt_id: str, value: dict[str, Any]) -> Path:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", attempt_id):
            raise ValueError("Invalid attempt identity")
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            record = deepcopy(value)
            record.update({
                "schema_version": "game-companion-plan-outcome/v1",
                "attempt_id": attempt_id,
                "recorded_at": _now(),
                "owner_acceptance": None,
                "reliability_accepted": False,
                "fastest": False,
                "completion_coverage": "unknown",
            })
            path = self.root / f"{attempt_id}.json"
            _write_new(path, record)
            return path

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        records = []
        for path in self.root.glob("*.json"):
            try:
                record = json.loads(path.read_text())
                record["evidence_path"] = str(path)
                records.append(record)
            except (OSError, ValueError):
                records.append({"status": "unavailable", "evidence_path": str(path)})
        records.sort(key=lambda item: item.get("recorded_at", ""), reverse=True)
        return records[:limit]
