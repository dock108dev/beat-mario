"""Copy retained source Minecraft state after shutdown, preserving originals and legacy data."""
import argparse
import json
from pathlib import Path
import socket
import subprocess

from smb3_agent.minecraft_delivery import world_directory

NAMES = ('minecraft-chat', world_directory(), world_directory(survival=True))


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
    for n in NAMES[1:]:
        retained_world(source / n)
    for name, validate in [('places', places), ('construction', construction), ('memory', library)]:
        validate(json.loads((source / 'minecraft-chat' / (name + '.json')).read_text()))
    from smb3_agent.directory_migration import activate
    return activate(source, destination, backup, NAMES)



if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('destination', type=Path)
    p.add_argument('backup', type=Path)
    a = p.parse_args()
    result = migrate(a.source.resolve(), a.destination.resolve(), a.backup.resolve())
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))
