"""Explicit disposable setup. Copying does not certify game loading or persistence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Callable

from smb3_agent.stardew_adapter import DisposableSaveManager, SaveIdentity, StardewAdapterError, WindowObservation


@dataclass(frozen=True)
class LoadingEvidence:
    """Trusted OS file-access diagnostic result, never browser-supplied claims.

    No production probe is supplied until the installed game's isolation workflow
    has been verified. A caller-injected test probe is fixture evidence only.
    """
    session_id: str
    process_id: int
    process_started_at: str
    window_id: str
    loaded_paths: tuple[str, ...]
    persisted_paths: tuple[str, ...]
    evidence_paths: tuple[str, ...]
    classification: str = "fixture"


@dataclass(frozen=True)
class SetupSession:
    save: SaveIdentity
    classification: str = "owner_copy"
    loading: LoadingEvidence | None = None

    @property
    def session_id(self) -> str:
        return self.save.nonce

    @property
    def input_ready(self) -> bool:
        return self.loading is not None and self.loading.classification == "actual_live"

    @property
    def blocker(self) -> str | None:
        return None if self.input_ready else "Game loading and persistence have not been verified."


class DisposableSessionSetup:
    def __init__(self, manager: DisposableSaveManager | None = None) -> None:
        self.manager = manager or DisposableSaveManager()
        self.session: SetupSession | None = None

    def create_owner_copy(self, source: Path, destination: Path, *, copy_authorized: bool) -> SetupSession:
        if copy_authorized is not True:
            raise StardewAdapterError("Explicit selected-source copying authorization is required")
        if self.session is not None:
            raise StardewAdapterError("Use reset for an existing disposable session")
        self.session = SetupSession(self.manager.create(source, destination))
        return self.session

    def create_engineering_copy(self, source: Path, destination: Path, *, copy_authorized: bool) -> SetupSession:
        """Explicitly selected dedicated engineering source; never discovers saves."""
        session = self.create_owner_copy(source, destination, copy_authorized=copy_authorized)
        self.session = SetupSession(session.save, "engineering_source")
        return self.session

    def status(self) -> dict:
        if self.session is None:
            return {"session_id": None, "input_ready": False, "blocker": "Select and authorize a disposable source; no primary saves are discovered."}
        return {"session_id": self.session.session_id, "save": asdict(self.session.save),
                "classification": self.session.classification, "input_ready": self.session.input_ready,
                "blocker": self.session.blocker}

    def verify_loading(self, window: WindowObservation, *, probe: Callable[[SetupSession, WindowObservation], LoadingEvidence]) -> SetupSession:
        if self.session is None or not window.trusted:
            raise StardewAdapterError("A disposable session and trusted window are required")
        session = self.session
        evidence = probe(session, window)
        if (evidence.session_id != session.session_id or
                evidence.process_id != window.process_id or
                evidence.process_started_at != window.process_started_at or
                evidence.window_id != window.window_id):
            raise StardewAdapterError("Loading evidence does not match this session/process/window")
        root = Path(session.save.disposable_real_path)
        if not evidence.loaded_paths or not evidence.persisted_paths or not evidence.evidence_paths:
            raise StardewAdapterError("Both actual loading and persistence evidence are required")
        for raw in (*evidence.loaded_paths, *evidence.persisted_paths):
            path = Path(raw).absolute()
            if path != path.resolve(strict=True) or root not in path.parents or not path.is_file():
                raise StardewAdapterError("Game file access is outside the disposable session")
        if any(not Path(path).is_file() for path in evidence.evidence_paths):
            raise StardewAdapterError("Retained loading/persistence evidence is missing")
        if not self.manager.verify_primary_unchanged(session.save):
            raise StardewAdapterError("Primary source changed")
        self.session = SetupSession(session.save, session.classification, evidence)
        return self.session

    def verify_engineering_launch(self, launch: EngineeringLaunch, window: WindowObservation) -> SetupSession:
        """Adopt only a retained, visibly reviewed reload in our own namespace.

        The browser supplies neither a verification boolean nor a proof path.
        The trusted engineering review is read at a fixed attempt-owned path.
        """
        import json
        import secrets
        from dataclasses import replace

        receipt_path = Path(launch.root) / "engineering-loading-review.json"
        if not receipt_path.is_file():
            raise StardewAdapterError("Prepare, persist and visibly reload the unique engineering farm; retained loading review is missing")
        _verify_engineering_launch_identity(launch, window)
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get("schema") != "stardew-engineering-load-review/v1" or
                receipt.get("classification") != "actual_live_setup_review" or
                receipt.get("launch_session_id") != launch.session_id or
                receipt.get("process_id") != window.process_id or
                receipt.get("process_started_at") != window.process_started_at or
                receipt.get("window_id") != window.window_id):
            raise StardewAdapterError("Engineering reload review belongs to another launch/process/window")
        farm = _engineering_farm(launch, receipt.get("save_name", ""))
        metadata = _engineering_save_metadata(farm)
        if metadata != receipt.get("persisted_files"):
            raise StardewAdapterError("Engineering persistence changed since the reviewed reload")
        for kind in ("load_menu", "loaded_game"):
            image_record = receipt.get("screenshots", {}).get(kind, {})
            if _engineering_image(launch, Path(image_record.get("path", ""))) != image_record:
                raise StardewAdapterError("Retained reload screenshots changed")
        seed = Path(launch.root) / "prepared-sources" / secrets.token_hex(12) / farm.name
        # Freeze a seed, leaving the already loaded live farm at its actual path.
        copied = self.manager.create(farm, seed)
        save = replace(copied, primary_path=str(seed), primary_real_path=str(seed.resolve()),
                       disposable_path=str(farm), disposable_real_path=str(farm.resolve()))
        evidence = LoadingEvidence(save.nonce, window.process_id, window.process_started_at,
                                   window.window_id, (str(farm / farm.name),),
                                   tuple(item["path"] for item in metadata),
                                   (str(receipt_path), str(Path(launch.root) / "launch.json"),
                                    receipt["screenshots"]["load_menu"]["path"],
                                    receipt["screenshots"]["loaded_game"]["path"]), "actual_live")
        self.session = SetupSession(save, "engineering_source", evidence)
        return self.session

    def verify_prepared_view(self, launch: EngineeringLaunch, window: WindowObservation,
                             *, profile, screenshot: Path) -> SetupSession:
        """Fresh visual verification of an explicitly registered engineering seed.

        This internal entry point accepts no browser facts. Persistence belongs to
        the immutable prepared seed; current loading is independently re-observed.
        Neither this check nor the new session nonce grants execution authority.
        """
        import json
        from PIL import Image
        from smb3_agent.stardew_adapter import _tree_identity

        _verify_engineering_launch_identity(launch, window)
        record = json.loads((Path(launch.root) / "prepared-source.json").read_text())
        registered = next((row for row in prepared_engineering_farms()
                           if row == record), None)
        if (registered is None or not profile.qualified()
                or profile.config.get("seed_sha256") != record["tree_sha256"]):
            raise StardewAdapterError("prepared farm lacks matching qualified visual calibration")
        source = Path(record["source"])
        farm = _engineering_farm(launch, source.name)
        if any(_tree_identity(path)[0] != record["tree_sha256"] for path in (source, farm)):
            raise StardewAdapterError("prepared seed or fresh working copy changed before verification")
        image = _engineering_image(launch, screenshot)
        frame = profile.decode(Image.open(screenshot).convert("RGB"))
        from smb3_agent.stardew_farm_perception import FarmPixelProfile
        if isinstance(profile, FarmPixelProfile):
            profile.verify_initial_view(frame)
        elif (len(frame["crops"]) != 15 or any(state is not False for state in frame["crops"].values())
                or frame["energy"] != 270 or frame["water"] != 40
                or max(map(abs, frame["player"])) + frame["uncertainty"] > 8):
            raise StardewAdapterError("show the complete dry prepared farm at the farmhouse with full resources")
        from dataclasses import replace
        import secrets
        frozen = Path(launch.root) / "prepared-sources" / secrets.token_hex(12) / farm.name
        copied = self.manager.create(farm, frozen)
        save = replace(copied, primary_path=str(frozen), primary_real_path=str(frozen.resolve()),
                       disposable_path=str(farm), disposable_real_path=str(farm.resolve()))
        receipt = Path(launch.root) / f"prepared-view-{save.nonce}.json"
        receipt.write_text(json.dumps({"classification": "actual_live_prepared_reopen",
            "session_id": save.nonce, "launch_session_id": launch.session_id,
            "process_id": window.process_id, "process_started_at": window.process_started_at,
            "window_id": window.window_id, "seed_sha256": record["tree_sha256"],
            "screenshot": image, "profile_id": profile.profile_id, "execution_authority": False}, indent=2))
        metadata = _engineering_save_metadata(farm)
        evidence = LoadingEvidence(save.nonce, window.process_id, window.process_started_at,
            window.window_id, (str(farm / farm.name),), tuple(item["path"] for item in metadata),
            (str(receipt), str(screenshot), str(Path(launch.root) / "prepared-source.json")), "actual_live")
        self.session = SetupSession(save, "engineering_source", evidence)
        return self.session

    def require_verified(self, window: WindowObservation) -> None:
        session = self.session
        evidence = session.loading if session else None
        if not session or not session.input_ready or evidence is None:
            raise StardewAdapterError("Game loading and persistence have not been verified")
        if (not window.trusted or evidence.process_id != window.process_id or
                evidence.process_started_at != window.process_started_at or evidence.window_id != window.window_id):
            raise StardewAdapterError("Disposable session process/window changed")
        if not self.manager.verify_primary_unchanged(session.save):
            raise StardewAdapterError("Primary source changed")
        from smb3_agent.stardew_adapter import _tree_identity
        disposable = Path(session.save.disposable_real_path)
        if disposable != disposable.resolve(strict=True) or _tree_identity(disposable)[0] != session.save.disposable_tree_sha256:
            raise StardewAdapterError("Disposable persistence identity changed; verify a fresh session")

    def reset(self, destination: Path) -> SetupSession:
        if self.session is None:
            raise StardewAdapterError("No disposable session to reset")
        previous = self.session
        # Invalidate verification even if copying subsequently fails.
        self.session = SetupSession(previous.save, previous.classification)
        fresh = self.manager.reset(previous.save, destination)
        self.session = SetupSession(fresh, previous.classification)
        return self.session


def discover_installations(steam_root: Path | None = None, applications: tuple[Path, ...] | None = None) -> dict:
    """Read application/Steam metadata only; never enumerate a save location."""
    steam_root = steam_root or Path.home() / "Library/Application Support/Steam"
    applications = applications if applications is not None else (Path('/Applications'), Path.home() / 'Applications')
    libraries = {steam_root}
    metadata = steam_root / 'steamapps/libraryfolders.vdf'
    inspected = [str(metadata)]
    if metadata.is_file():
        for value in re.findall(r'"path"\s+"([^"]+)"', metadata.read_text()):
            libraries.add(Path(value.replace('\\\\', '\\')))
    found = []
    for library in sorted(libraries):
        manifest = library / 'steamapps/appmanifest_413150.acf'
        inspected.append(str(manifest))
        if manifest.is_file():
            text = manifest.read_text()
            match = re.search(r'"installdir"\s+"([^"]+)"', text)
            if match and '/' not in match[1] and '..' not in match[1]:
                folder = library / 'steamapps/common' / match[1]
                if folder.is_dir():
                    found.append(str(folder))
    for folder in applications:
        candidate = folder / 'Stardew Valley.app'
        inspected.append(str(candidate))
        if candidate.is_dir():
            found.append(str(candidate))
    actual, shortcuts = [], []
    for raw in found:
        candidate = Path(raw)
        if ((candidate / "Contents/MacOS/Stardew Valley.dll").is_file() and
                (candidate / "Contents/MacOS/Stardew Valley").is_file()):
            canonical = str(candidate.resolve(strict=True))
            if canonical not in actual:
                actual.append(canonical)
        else:
            shortcuts.append(raw)
    return {"classification": "installation_metadata_only", "installations": actual,
            "launcher_shortcuts": shortcuts,
            "inspected_metadata": inspected, "save_directories_inspected": False,
            "blocker": None if actual else "Stardew Valley installation not found in configured Steam libraries or Applications."}


@dataclass
class EngineeringLaunch:
    """Fresh empty engineering namespace, distinct from a verified playable save."""
    session_id: str
    root: str
    installation: str
    executable: str
    config_root: str
    data_root: str
    sandbox_profile: str
    binary_hashes: dict[str, str]
    process_id: int | None = None
    process_started_at: str | None = None

    def status(self) -> dict:
        config = Path(self.config_root) / "StardewValley"
        # Metadata only inside our newly created namespace. Never parse save state.
        files = [{"path": str(path), "bytes": path.stat().st_size}
                 for path in config.glob('*') if path.is_file() and not path.is_symlink()]
        return {**asdict(self), "classification": "fresh_engineering_namespace",
                "created_config_metadata": files, "input_ready": False,
                "blocker": ("Prepared seed copied; choose Load and verify this fresh session. Game input remains disabled."
                            if (Path(self.root) / "prepared-source.json").is_file() else
                            "No prepared engineering farm has been persisted and reloaded; game input remains disabled.")}


def prepared_engineering_farms() -> list[dict]:
    """Read explicit local engineering registrations, never discover owner saves."""
    import json
    registry = Path("artifacts/stardew-prepared-farms.json")
    if not registry.is_file() or registry.is_symlink():
        return []
    try:
        rows = json.loads(registry.read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(rows, list):
        return []
    root = Path("artifacts/stardew-engineering").resolve()
    result = []
    for row in rows:
        if not isinstance(row, dict) or any(not isinstance(row.get(key), str) or not row[key]
                                            for key in ("id", "label", "source", "tree_sha256")):
            continue
        if any(item["id"] == row["id"] for item in result):
            continue
        source = Path(row["source"])
        if (root in source.parents and "prepared-sources" in source.parts
                and source.is_dir() and source == source.resolve()):
            result.append(dict(row))
    return result


def launch_fresh_engineering(installation: Path, destination: Path, *, prepared_id: str | None = None) -> tuple[EngineeringLaunch, object]:
    """Launch only to title, with verified .NET6 XDG routing and OS primary deny rules.

    This does not certify a loaded save or grant input. The executable and bundled
    runtime hashes bind the static path inspection to the launched installation.
    No save directories are searched or opened. HOME remains unchanged.
    """
    import hashlib
    import json
    import os
    import secrets
    import subprocess
    import time
    import shutil

    prepared = None
    if prepared_id is not None:
        from smb3_agent.stardew_adapter import _tree_identity
        prepared = next((row for row in prepared_engineering_farms() if row['id'] == prepared_id), None)
        if prepared is None or _tree_identity(Path(prepared['source']))[0] != prepared['tree_sha256']:
            raise StardewAdapterError("Registered engineering seed is missing or changed; it was not opened")

    installation = installation.expanduser().absolute()
    if installation != installation.resolve(strict=True):
        raise StardewAdapterError("Installation aliases are refused")
    executable = installation / 'Contents/MacOS/Stardew Valley'
    assembly = installation / 'Contents/MacOS/Stardew Valley.dll'
    runtime = installation / 'Contents/MacOS/System.Private.CoreLib.dll'
    runtime_config = installation / 'Contents/MacOS/Stardew Valley.runtimeconfig.json'
    config = json.loads(runtime_config.read_text())
    if config.get('runtimeOptions', {}).get('includedFrameworks') != [{'name': 'Microsoft.NETCore.App', 'version': '6.0.32'}]:
        raise StardewAdapterError("Installed runtime differs from the inspected .NET 6.0.32 path-routing contract")
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (executable, assembly, runtime, runtime_config)}
    inspected = {
        "Stardew Valley": "71017b92549b61e8dd434d7a0e8a4c880e5594836b43df629d2649d68ad6e465",
        "Stardew Valley.dll": "8937c582cad1c1127017944778c4102467bf299aea44869491f28ab0ec84cd73",
        "System.Private.CoreLib.dll": "c2106b6b39ebdbdbb37a283c296b4c1e660c2960217d3900fd2f91ba07bd38b8",
    }
    if any(hashes[str(path)] != inspected[path.name] for path in (executable, assembly, runtime)):
        raise StardewAdapterError("Installed game/runtime differs from the statically inspected isolation candidate")
    target = destination.expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise StardewAdapterError("Fresh engineering namespace must not already exist")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.parent != target.parent.resolve(strict=True):
        raise StardewAdapterError("Engineering namespace aliases are refused")
    target.mkdir()
    config_root, data_root = target / 'config', target / 'data'
    config_root.mkdir()
    data_root.mkdir()
    protected = [Path.home() / '.config/StardewValley', Path.home() / '.local/share/StardewValley',
                 Path.home() / 'Library/Application Support/StardewValley']
    profile = target / 'isolation.sb'
    profile.write_text('(version 1)\n(allow default)\n(deny network*)\n' + '\n'.join(
        f'(deny file-read* file-write* (subpath {json.dumps(str(path))}))' for path in protected) + '\n')
    env = dict(os.environ)
    env.update(XDG_CONFIG_HOME=str(config_root), XDG_DATA_HOME=str(data_root))
    launch = EngineeringLaunch(secrets.token_hex(16), str(target), str(installation), str(executable),
                               str(config_root), str(data_root), str(profile), hashes)
    with (target / 'launch.json').open('x') as stream:
        json.dump({**launch.status(), 'environment_overrides': {'XDG_CONFIG_HOME': str(config_root), 'XDG_DATA_HOME': str(data_root)},
                   'home_unchanged': True, 'primary_paths_accessed': False, 'network_denied': True}, stream, indent=2)
    if prepared is not None:
        source = Path(prepared['source'])
        destination_save = config_root / 'StardewValley/Saves' / source.name
        shutil.copytree(source, destination_save, copy_function=shutil.copy)
        if _tree_identity(source)[0] != prepared['tree_sha256'] or _tree_identity(destination_save)[0] != prepared['tree_sha256']:
            raise StardewAdapterError("Engineering seed changed during copying; launch refused")
        (target / 'prepared-source.json').write_text(json.dumps(prepared, indent=2))
    log = (target / 'game.log').open('xb')
    try:
        process = subprocess.Popen(['/usr/bin/sandbox-exec', '-f', str(profile), str(executable)],
                                   cwd=executable.parent, env=env, stdout=log, stderr=subprocess.STDOUT)
    finally:
        log.close()
    launch.process_id = process.pid
    # Metadata only; no input, hidden state or owner-save access.
    time.sleep(.2)
    launch.process_started_at = subprocess.run(['ps', '-p', str(process.pid), '-o', 'lstart='], capture_output=True, text=True, check=False).stdout.strip() or None
    with (target / 'process.json').open('x') as stream:
        json.dump({**launch.status(), 'returncode': process.poll()}, stream, indent=2)
    return launch, process


def _verify_engineering_launch_identity(launch: EngineeringLaunch, window: WindowObservation) -> None:
    """Check OS process metadata and retained launcher facts, never game internals."""
    import hashlib
    import json
    import subprocess
    root = Path(launch.root)
    if (root != root.resolve(strict=True) or not window.visible or not window.windowed or
            window.occluded or window.bounds is None or window.process_id is None or not window.process_started_at):
        raise StardewAdapterError("A canonical engineering namespace and visible identified window are required")
    if (launch.process_id != window.process_id or launch.process_started_at != window.process_started_at):
        raise StardewAdapterError("Engineering launch process identity changed")
    started = subprocess.run(["ps", "-p", str(window.process_id), "-o", "lstart="],
                             capture_output=True, text=True, check=False).stdout.strip()
    executable = subprocess.run(["ps", "-p", str(window.process_id), "-o", "comm="],
                                capture_output=True, text=True, check=False).stdout.strip()
    if started != launch.process_started_at or executable != launch.executable:
        raise StardewAdapterError("Engineering game process is absent, replaced or no longer the inspected executable")
    record = json.loads((root / 'launch.json').read_text())
    process = json.loads((root / 'process.json').read_text())
    if (record.get('session_id') != launch.session_id or process.get('process_id') != window.process_id or
            process.get('process_started_at') != window.process_started_at or
            record.get('environment_overrides') != {'XDG_CONFIG_HOME': launch.config_root, 'XDG_DATA_HOME': launch.data_root} or
            record.get('home_unchanged') is not True or record.get('network_denied') is not True or
            Path(launch.config_root) != root / 'config' or Path(launch.data_root) != root / 'data' or
            record.get('binary_hashes') != launch.binary_hashes):
        raise StardewAdapterError("Engineering launch isolation record does not match this process")
    if any(hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest for path, digest in launch.binary_hashes.items()):
        raise StardewAdapterError("Inspected game/runtime binaries changed after launch")
    profile = Path(launch.sandbox_profile)
    protected = [Path.home() / '.config/StardewValley', Path.home() / '.local/share/StardewValley',
                 Path.home() / 'Library/Application Support/StardewValley']
    expected = '(version 1)\n(allow default)\n(deny network*)\n' + '\n'.join(
        f'(deny file-read* file-write* (subpath {json.dumps(str(path))}))' for path in protected) + '\n'
    if profile != root / 'isolation.sb' or profile.read_text() != expected:
        raise StardewAdapterError("Engineering sandbox policy changed")


def _engineering_farm(launch: EngineeringLaunch, save_name: str) -> Path:
    if not save_name or Path(save_name).name != save_name or save_name in {'.', '..'}:
        raise StardewAdapterError("Exact engineering farm folder name is required")
    saves = Path(launch.config_root) / 'StardewValley/Saves'
    if not saves.is_dir() or saves != saves.resolve(strict=True):
        raise StardewAdapterError("No canonical persisted engineering save directory exists")
    farms = list(saves.iterdir())
    farm = saves / save_name
    if len(farms) != 1 or farms[0] != farm or farm != farm.resolve(strict=True):
        raise StardewAdapterError("Loading proof requires exactly one unaliased farm in this engineering namespace")
    return farm


def _engineering_save_metadata(farm: Path) -> list[dict]:
    # Save bytes are hashed only for identity/preservation, never parsed as game state.
    import hashlib
    result = []
    for name in (farm.name, 'SaveGameInfo'):
        path = farm / name
        if not path.is_file() or path.is_symlink() or path.stat().st_nlink != 1 or path.stat().st_size == 0:
            raise StardewAdapterError("Both nonempty game-created save files must be persisted")
        info = path.stat()
        result.append({'path': str(path), 'bytes': info.st_size, 'mtime_ns': info.st_mtime_ns,
                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return result


def _engineering_image(launch: EngineeringLaunch, path: Path) -> dict:
    import hashlib
    path = path.absolute()
    if Path(launch.root) not in path.parents or path != path.resolve(strict=True) or not path.is_file():
        raise StardewAdapterError("Reload screenshots must be retained inside this engineering attempt")
    from PIL import Image
    with Image.open(path) as image:
        if image.width < 100 or image.height < 100:
            raise StardewAdapterError("Reload evidence must show the visible game")
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'mtime_ns': path.stat().st_mtime_ns}


def retain_engineering_load_review(launch: EngineeringLaunch, window: WindowObservation, *,
                                   save_name: str, load_menu_screenshot: Path,
                                   loaded_screenshot: Path) -> Path:
    """Record trusted engineering review AFTER actually seeing selection and reload.

    This helper is not exposed to browser JSON. A human/engineering reviewer must
    inspect the two live captures and confirm the unique farm was loaded. It is
    setup evidence only, never automatic crop/resource perception qualification.
    """
    import json
    from datetime import datetime, timezone
    _verify_engineering_launch_identity(launch, window)
    farm = _engineering_farm(launch, save_name)
    metadata = _engineering_save_metadata(farm)
    menu = _engineering_image(launch, load_menu_screenshot)
    loaded = _engineering_image(launch, loaded_screenshot)
    if menu['sha256'] == loaded['sha256'] or menu['mtime_ns'] >= loaded['mtime_ns']:
        raise StardewAdapterError("Distinct ordered load-menu and loaded-game captures are required")
    if max(item['mtime_ns'] for item in metadata) > menu['mtime_ns']:
        raise StardewAdapterError("The engineering save must be persisted before the reviewed reload")
    if min(item['mtime_ns'] for item in metadata) < (Path(launch.root) / 'launch.json').stat().st_mtime_ns:
        raise StardewAdapterError("Engineering persistence predates the fresh launch")
    path = Path(launch.root) / 'engineering-loading-review.json'
    with path.open('x') as stream:
        json.dump({'schema': 'stardew-engineering-load-review/v1', 'classification': 'actual_live_setup_review',
                   'reviewed_at': datetime.now(timezone.utc).isoformat(), 'launch_session_id': launch.session_id,
                   'process_id': window.process_id, 'process_started_at': window.process_started_at,
                   'window_id': window.window_id, 'save_name': save_name, 'persisted_files': metadata,
                   'screenshots': {'load_menu': menu, 'loaded_game': loaded},
                   'automatic_target_perception': False, 'owner_source_access': False}, stream, indent=2)
    return path
