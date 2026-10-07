"""Bounded external executable discovery for source and Finder launches."""
import os
from pathlib import Path
import shutil


def discover_fceux(*, which=None, roots=(Path('/opt/homebrew/bin'), Path('/usr/local/bin'))) -> str | None:
    import json
    registration = Path("artifacts/executable-selection.json")
    if registration.is_file():
        try:
            selected = Path(json.loads(registration.read_text())["fceux"])
            if selected.is_absolute() and selected.is_file() and os.access(selected, os.X_OK):
                return str(selected)
            return None
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
    import json
    candidate = Path(path).expanduser().resolve(strict=True)
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise ValueError("Choose an executable FCEUX file")
    registration = Path("artifacts/executable-selection.json")
    registration.parent.mkdir(parents=True, exist_ok=True)
    temporary = registration.with_suffix(".tmp")
    temporary.write_text(json.dumps({"fceux": str(candidate)}) + "\n")
    temporary.replace(registration)
    return str(candidate)
