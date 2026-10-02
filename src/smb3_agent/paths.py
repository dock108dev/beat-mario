from __future__ import annotations

from pathlib import Path
import sys


REPOSITORY_ROOT = (Path(sys._MEIPASS) / "resources" if getattr(sys, "frozen", False)
                   else Path(__file__).resolve().parents[2])


def repository_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPOSITORY_ROOT / candidate
