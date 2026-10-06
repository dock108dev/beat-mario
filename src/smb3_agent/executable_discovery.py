"""Bounded external executable discovery for source and Finder launches."""
import os
from pathlib import Path
import shutil


def discover_fceux(*, which=None, roots=(Path('/opt/homebrew/bin'), Path('/usr/local/bin'))) -> str | None:
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
