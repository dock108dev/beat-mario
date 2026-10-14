"""Bounded external executable discovery for source and Finder launches."""
import json
import os
from pathlib import Path
import shutil


FCEUX_ROOTS = (Path('/opt/homebrew/bin'), Path('/usr/local/bin'))


def _selected_fceux(path: str | Path) -> str | None:
    """Match an input to trusted discovery paths without accessing the input path."""
    known_paths = [root / 'fceux' for root in FCEUX_ROOTS]
    found = shutil.which('fceux')
    if found:
        known_paths.insert(0, Path(found))
    for known in known_paths:
        if not known.is_absolute():
            continue
        try:
            candidate = known.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        # Only trusted discovery paths reach filesystem checks, including symlinks.
        if str(path) in (str(known), str(candidate)):
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return None


def discover_fceux(*, which=None, roots=FCEUX_ROOTS) -> str | None:
    registration = Path("artifacts/executable-selection.json")
    if registration.is_file():
        try:
            return _selected_fceux(json.loads(registration.read_text())["fceux"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
    found = (which or shutil.which)('fceux')
    if found:
        return found
    for root in roots:
        candidate = root / 'fceux'
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def require_fceux(*, resolver=None) -> str:
    """Resolve the same executable advertised by setup, or refuse launch."""
    executable = resolver("fceux") if resolver is not None else discover_fceux()
    if executable is None:
        raise FileNotFoundError("FCEUX was not found. Install it locally and retry setup.")
    return executable


def select_fceux(path):
    candidate = _selected_fceux(path)
    if candidate is None:
        raise ValueError(
            "Choose FCEUX from PATH, /opt/homebrew/bin/fceux, or /usr/local/bin/fceux"
        )
    registration = Path("artifacts/executable-selection.json")
    registration.parent.mkdir(parents=True, exist_ok=True)
    temporary = registration.with_suffix(".tmp")
    temporary.write_text(json.dumps({"fceux": str(candidate)}) + "\n")
    temporary.replace(registration)
    return str(candidate)
