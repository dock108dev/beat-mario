"""Adapter-owned experimental opening-jump guidance, separate from accepted routes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile

COMPATIBILITY = "smb3/world-1-1/opening-hop/v1"
MAX_DELAY = 12


def urgent_control(text: str) -> str | None:
    value = re.sub(r"[^a-z0-9' ]", " ", text.lower())
    value = " ".join(value.split())
    if re.search(r"\b(?:don't|do not|never|not|why|what|when|how|if)\b", value):
        return None
    value = re.sub(r"^(?:(?:please|okay|ok) |(?:can|could|would|will) you (?:please )?)+", "", value)
    if re.fullmatch(r"stop(?: (?:right|now|immediately|playing|wait|please|the game|the agent))+|stop", value):
        return "stop"
    if re.fullmatch(r"(?:take control|give me (?:back )?control|let me (?:play|take over)|hand (?:it |control )?back)(?: (?:right now|now|please|immediately))?", value):
        return "reclaim"
    return None


def timing_adjustment(text: str) -> int | None:
    value = text.lower().replace("’", "'")
    if not re.search(r"\b(?:jump|jumping|hop)\b", value):
        return None
    if re.search(r"\b(?:don't|do not|never)\b", value):
        return None
    later = bool(re.search(r"\b(?:early|later|delay|wait)\b", value))
    earlier = bool(re.search(r"\b(?:late|earlier|sooner)\b", value))
    if later == earlier:
        return None
    number = re.search(r"\b(\d+)\s*(?:more |fewer )?frames?\b", value)
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "few": 3}
    if number:
        amount = int(number[1])
    else:
        amount = next((n for word, n in words.items() if re.search(rf"\b{word}\b", value)), 3)
    return amount if later else -amount


class CoachingStore:
    def __init__(self, path: Path):
        self.path = path

    def read(self) -> dict:
        if not self.path.exists():
            return {"schema_version": 1, "compatibility": COMPATIBILITY, "jump_delay_frames": 0, "coaching": []}
        data = json.loads(self.path.read_text())
        if data.get("schema_version") != 1 or data.get("compatibility") != COMPATIBILITY:
            raise ValueError("Saved coaching is incompatible; reset future guidance to continue")
        delay = data.get("jump_delay_frames")
        if type(delay) is not int or not 0 <= delay <= MAX_DELAY or not isinstance(data.get("coaching"), list):
            raise ValueError("Saved coaching is invalid; reset future guidance to continue")
        return data

    def write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".coaching-")
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(data, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def reset(self) -> None:
        self.write({"schema_version": 1, "compatibility": COMPATIBILITY, "jump_delay_frames": 0, "coaching": []})

    def adjust(self, text: str, delta: int) -> dict:
        data = self.read()
        prior = data["jump_delay_frames"]
        updated = prior + delta
        if not 0 <= updated <= MAX_DELAY:
            raise ValueError(f"Opening jump delay must remain between 0 and {MAX_DELAY} frames; current delay is {prior}.")
        data["jump_delay_frames"] = updated
        data["coaching"].append({"original_words": text, "prior_delay_frames": prior,
                                 "new_delay_frames": updated, "application": "next_compatible_attempt"})
        self.write(data)
        return data
