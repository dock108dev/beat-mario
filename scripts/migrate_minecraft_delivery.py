"""Copy retained source Minecraft state after shutdown, preserving originals and legacy data."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess

NAMES = ('minecraft-chat', 'minecraft-b1-practice-1.21.4', 'minecraft-b1-survival-1.21.4')


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def migrate(source, destination, backup):
    from smb3_agent.minecraft_delivery import retained_world
    from smb3_agent.minecraft_memory import places, construction, library
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 8765)) == 0:
            raise ValueError('Quit Game Companion before copying state')
    processes = subprocess.check_output(['ps', 'ax', '-o', 'command='], text=True)
    if any((Path(p.split()[0]).name == 'java' and 'server.jar' in p) or (Path(p.split()[0]).name == 'node' and 'worker.cjs' in p) for p in processes.splitlines() if p.split()):
        raise ValueError('Stop the practice server and worker cleanly before migration')
    receipt = destination / 'minecraft-migration.json'
    if receipt.exists():
        old = json.loads(receipt.read_text())
        if old['source'] != str(source):
            raise ValueError('Different migration source; refusing ambiguous merge')
        return old  # Never overwrite a subsequently used destination.
    if any((destination / 'artifacts' / n).exists() for n in NAMES):
        raise ValueError('Minecraft destination already exists; refusing conflicting histories')
    for n in NAMES[1:]:
        retained_world(source / n)
    for name, validate in [('places', places), ('construction', construction), ('memory', library)]:
        validate(json.loads((source / 'minecraft-chat' / (name + '.json')).read_text()))
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copytree(destination, backup / 'legacy-app-data')
    stage = backup / 'qualified-source'
    stage.mkdir()
    manifest = {}
    for name in NAMES:
        before = hashes(source / name)
        shutil.copytree(source / name, stage / name)
        if before != hashes(stage / name) or before != hashes(source / name):
            raise ValueError('Source changed or backup mismatch; nothing activated')
        manifest[name] = before
    pending = destination / 'minecraft-migration-staged'
    shutil.copytree(stage, pending)
    if any(hashes(pending / n) != manifest[n] for n in NAMES):
        raise ValueError('Copied state failed hash verification; nothing activated')
    (destination / 'artifacts').mkdir(exist_ok=True)
    for n in NAMES:
        (pending / n).rename(destination / 'artifacts' / n)
    pending.rmdir()
    result = {'source': str(source), 'backup': str(backup), 'destination': str(destination), 'files': manifest, 'originals_preserved': True, 'history_merge': False}
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('destination', type=Path)
    p.add_argument('backup', type=Path)
    a = p.parse_args()
    result = migrate(a.source.resolve(), a.destination.resolve(), a.backup.resolve())
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))
