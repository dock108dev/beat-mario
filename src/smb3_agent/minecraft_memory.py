"""Validated atomic snapshots with retained generations; never execution authority."""

from copy import deepcopy
import json
import os
from pathlib import Path
import time
from uuid import uuid4


class MemoryUnavailable(ValueError):
    pass


class DurableJSON:
    def __init__(self, path, validate):
        self.path = Path(path)
        self.validate = validate
        self.archive = self.path.parent / (self.path.stem + "-generations")
        self.problem = None

    def decode(self, path):
        value = json.loads(path.read_text())
        self.validate(value)
        return value

    def load(self, default):
        if not self.path.exists():
            if self.archive.exists() or list(
                self.path.parent.glob(self.path.name + ".*.tmp")
            ):
                self.problem = f"{self.path.name} is missing but earlier write evidence exists. Restore a saved generation; no empty replacement was created."
            return deepcopy(default)
        try:
            return self.decode(self.path)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            self.problem = f"{self.path.name} could not be validated ({type(exc).__name__}). Original preserved. Restore a saved generation in Session details."
            return deepcopy(default)

    @staticmethod
    def write(path, data):
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def sync_directory(path):
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def save(self, value):
        if self.problem:
            raise MemoryUnavailable(self.problem)
        self.validate(value)
        blob = json.dumps(value, allow_nan=False).encode()
        self.archive.mkdir(exist_ok=True)
        # Archive the old committed state before replacing it. Interrupted temp files
        # are evidence, never candidates for automatic promotion.
        if self.path.exists():
            try:
                self.decode(self.path)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                self.problem = f"{self.path.name} changed or is damaged. Original preserved; restore a saved generation."
                raise MemoryUnavailable(self.problem) from exc
            self.write(
                self.archive / f"{time.time_ns()}-{uuid4().hex}.json",
                self.path.read_bytes(),
            )
            self.sync_directory(self.archive)
        temp = self.path.with_name(self.path.name + "." + uuid4().hex + ".tmp")
        self.write(temp, blob)
        os.replace(temp, self.path)
        self.sync_directory(self.path.parent)

    def candidates(self):
        result = []
        for path in sorted(self.archive.glob("*.json"), reverse=True):
            try:
                self.decode(path)
                result.append(path.name)
                if len(result) >= 30:
                    break
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                pass
        return result[:30]

    def restore(self, generation):
        if generation not in self.candidates():
            raise ValueError("Select an available validated generation.")
        value = self.decode(self.archive / generation)
        if self.path.exists():
            self.write(
                self.path.with_name(self.path.name + ".incident-" + uuid4().hex),
                self.path.read_bytes(),
            )
        self.problem = self.problem or (
            "Memory restoration is incomplete. Retry restoring the saved generation."
        )
        # The damaged primary is preserved, but must not be archived as valid.
        temp = self.path.with_name(self.path.name + "." + uuid4().hex + ".tmp")
        self.write(temp, json.dumps(value, allow_nan=False).encode())
        os.replace(temp, self.path)
        self.sync_directory(self.path.parent)
        self.problem = None
        return value


def world(value):
    if (
        not isinstance(value, list)
        or len(value) != 3
        or not all(isinstance(x, str) and x and x != "unknown" for x in value)
    ):
        raise ValueError("Invalid world identity")


def point(value):
    import math

    if not isinstance(value, dict) or not all(
        type(value.get(k)) in (int, float) and math.isfinite(value[k])
        for k in ("x", "y", "z")
    ):
        raise ValueError("Invalid coordinates")


def construction(value):
    from smb3_agent.minecraft_construction import geometry

    world(value["world"])
    geometry(value["spec"])
    if not isinstance(value["placed"], list):
        raise ValueError("Invalid placements")
    for c in value["placed"] + value.get("cells", []):
        point(c["position"])
        if not isinstance(c["item"], str):
            raise ValueError("Invalid material")


def places(value):
    for p in value["places"].values():
        world(p["world"])
        point(p["position"])
    for scope, regions in value["protections"].items():
        world(json.loads(scope))
        for r in regions:
            point(r["center"])
            if not 1 <= r["radius"] <= 32:
                raise ValueError("Invalid protection radius")


def library(value):
    if value["schema"] != 1 or not isinstance(value["structures"], dict):
        raise ValueError("Incompatible memory schema")
    if "current_id" in value and value["current_id"] not in value["structures"]:
        raise ValueError("Missing current structure")
    for record in value["structures"].values():
        construction(record)
    if not isinstance(value["preferences"], dict):
        raise ValueError("Invalid preferences")
    for scope, preferences in value["preferences"].items():
        world(json.loads(scope))
        if not isinstance(preferences, list) or not all(
            isinstance(p, str) and len(p) <= 400 for p in preferences
        ):
            raise ValueError("Invalid preference entries")
    for outcome in value.get("outcomes", []):
        world(outcome["world"])
        if not isinstance(outcome.get("reason"), str):
            raise ValueError("Invalid outcome")
    for scope, entries in value.get("resource_constraints", {}).items():
        world(json.loads(scope))
        for entry in entries:
            point(entry["target"])
            if not isinstance(entry["reason"], str):
                raise ValueError("Invalid resource constraint")
