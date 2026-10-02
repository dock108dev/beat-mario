"""Explicit 1x/2x capture interpretation, retaining original selected-window pixels."""

import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4

from PIL import Image

from smb3_agent.feedback_contracts import FeedbackError
from smb3_agent.native_host import capture_selected
from smb3_agent.screen_host import Frame

CAPTURE_VERSION = "minecraft-capture-scale/v1"


def decode_pixels(raw, decoded):
    """Replicate 1x pixels exactly; interpolation never invents glyph edges."""
    with Image.open(raw) as image:
        size = image.size
        if size not in {(854, 508), (1708, 1016)}:
            raise FeedbackError(
                "Unsupported native Minecraft capture size; arrange the supported window"
            )
        if size == (854, 508):
            image.resize((1708, 1016), Image.Resampling.NEAREST).save(decoded)
            return size, Path(decoded), "exact 2x nearest pixel replication"
    return size, Path(raw), "native 2x; no pixel transformation"


def capture_frame(host, root, *, execution, expected_pixels=None):
    window = host.detect_window(require_foreground=execution)
    if window.bounds[2:] != (854, 508):
        raise FeedbackError("Use the supported 854 × 508 point window")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    identity = uuid4().hex
    raw = root / (identity + "-native.png")
    decoded = root / (identity + "-decoded.png")
    at = time.monotonic()
    capture_selected(
        window,
        raw,
        detect_window=lambda: host.detect_window(require_foreground=execution),
        require_foreground=execution,
        normalize=False,
    )
    native_size, path, transform = decode_pixels(raw, decoded)
    if expected_pixels is not None and native_size != expected_pixels:
        raise FeedbackError(
            "Display/capture scale changed; recalibrate the current window"
        )
    raw_sha = hashlib.sha256(raw.read_bytes()).hexdigest()
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    record = {
        "schema": CAPTURE_VERSION,
        "captured_at": at,
        "raw": str(raw),
        "raw_sha256": raw_sha,
        "native_size": list(native_size),
        "decoded": str(path),
        "decoded_sha256": sha,
        "transform": transform,
        "process_id": window.process_id,
        "started": window.process_started_at,
        "window_id": window.window_id,
        "bounds": list(window.bounds),
    }
    evidence = root / (identity + "-capture.json")
    evidence.write_text(json.dumps(record, indent=2) + "\n")
    return (
        Frame(identity, at, window, path, sha, ()),
        native_size,
        (str(raw), "native-sha256:" + raw_sha, str(evidence)),
    )
