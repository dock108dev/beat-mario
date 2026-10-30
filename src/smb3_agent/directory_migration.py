"""Restartable copy activation: originals remain, changed destinations refuse recovery."""

import hashlib
import json
import os
from pathlib import Path
import shutil


def hashes(root):
    root = Path(root)
    if root.is_symlink() or any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("Migration refuses symlinks")
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(path, value):
    temp = path.with_suffix(".pending")
    with temp.open("w") as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    sync_dir(path.parent)


def activate(source, destination, backup, names, *, fault=lambda point: None):
    source, destination, backup = map(Path, (source, destination, backup))
    if any(p.is_symlink() for p in (source, destination, backup)):
        raise ValueError("Migration refuses symlink roots")
    if any(not n or Path(n).name != n for n in names):
        raise ValueError("Invalid migration directory")
    journal = destination / "minecraft-migration-journal.json"
    receipt = destination / "minecraft-migration.json"
    if receipt.exists():
        prior = json.loads(receipt.read_text())
        if prior["source"] != str(source):
            raise ValueError("Different migration source")
        return (
            prior  # Used destinations are never overwritten by a completed migration.
        )
    stage = backup / "qualified-source"
    if journal.exists():
        data = json.loads(journal.read_text())
        if (
            data["source"] != str(source)
            or data["backup"] != str(backup)
            or list(data["files"]) != sorted(names)
        ):
            raise ValueError("Migration identity mismatch")
    else:
        if any((destination / "artifacts" / n).exists() for n in names):
            raise ValueError("Destination already exists")
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copytree(destination, backup / "legacy-app-data")
        stage.mkdir()
        manifest = {}
        for n in names:
            manifest[n] = hashes(source / n)
            shutil.copytree(source / n, stage / n)
            if hashes(stage / n) != manifest[n] or hashes(source / n) != manifest[n]:
                raise ValueError("Source changed while staging")
            for p in (stage / n).rglob("*"):
                if p.is_file():
                    with p.open("rb") as stream:
                        os.fsync(stream.fileno())
            sync_dir(stage / n)
        data = {
            "source": str(source),
            "destination": str(destination),
            "backup": str(backup),
            "files": manifest,
            "originals_preserved": True,
            "history_merge": False,
        }
        save(journal, data)
        fault("journal")
    target = destination / "artifacts"
    target.mkdir(exist_ok=True)
    for n in names:
        expected = data["files"][n]
        if hashes(source / n) != expected:
            raise ValueError("Source changed; preserve staged copy and inspect")
        out = target / n
        if out.exists():
            if hashes(out) != expected:
                raise ValueError(
                    "Activated destination changed; recovery refuses overwrite"
                )
        else:
            if hashes(stage / n) != expected:
                raise ValueError("Staged directory changed")
            fault("before:" + n)
            os.rename(stage / n, out)
            sync_dir(stage)
            sync_dir(target)
            fault("activated:" + n)
        save(journal, data)
        fault("recorded:" + n)
    if any(hashes(target / n) != data["files"][n] for n in names):
        raise ValueError("Destination changed before receipt")
    fault("before_receipt")
    save(receipt, data)
    fault("receipt")
    return data
