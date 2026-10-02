"""Selected material from a verified inventory tooltip and fresh hotbar pixels."""

from dataclasses import dataclass, replace
import hashlib
import io
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from PIL import Image

from smb3_agent.feedback_contracts import FeedbackError


def sprite(name):
    jar = Path.home() / "Library/Application Support/minecraft/versions/26.3/26.3.jar"
    with ZipFile(jar) as archive:
        return np.asarray(
            Image.open(
                io.BytesIO(
                    archive.read(
                        "assets/minecraft/textures/gui/sprites/" + name + ".png"
                    )
                )
            ).convert("RGBA")
        )


def pixels(path):
    with Image.open(path) as image:
        if image.size != (1708, 1016):
            raise FeedbackError("Restore the supported window and capture scale")
        return np.asarray(image.convert("RGB"))


def selected_slot(path):
    rgb = pixels(path)
    ref = np.repeat(np.repeat(sprite("hud/hotbar_selection"), 4, 0), 4, 1)
    opaque = ref[:, :, 3] == 255
    height, width = ref.shape[:2]
    slots = set()
    for slot in range(9):
        for y in range(920, 937, 2):
            if y + height > 1016:
                continue
            for x in range(482 + slot * 80, 493 + slot * 80, 2):
                actual = rgb[y : y + height, x : x + width]
                if (
                    actual.shape == ref[:, :, :3].shape
                    and (
                        np.abs(
                            actual[opaque].astype(int)
                            - ref[:, :, :3][opaque].astype(int)
                        )
                        <= 4
                    ).all()
                ):
                    slots.add(slot)
    if len(slots) != 1:
        raise FeedbackError("Selected hotbar slot is unavailable or ambiguous")
    return slots.pop()


@dataclass(frozen=True)
class MaterialReference:
    material: str
    slot: int
    inventory_sha256: str
    icon: np.ndarray
    mask: np.ndarray

    @classmethod
    def from_inventory(cls, path, evidence):
        rgb = pixels(path)
        x, y = 464 + (9 + 18 * evidence.slot) * 4, 264 + 112 * 4
        icon = rgb[y : y + 64, x : x + 64].copy()
        mask = (icon != 192).any(2) & (icon != 139).any(2) & (icon.max(2) > 40)
        if mask.sum() < 100:
            raise FeedbackError("Hotbar slot is empty or the item image is uncertain")
        icon.flags.writeable = False
        mask.flags.writeable = False
        return cls(
            evidence.material,
            evidence.slot,
            hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            icon,
            mask,
        )

    def bind_resumed_world(self, path):
        """Reconcile Creative GUI lighting with the independently captured HUD.

        E only closes the inspected inventory. The selected slot must remain
        identical and each foreground texture colour must map bijectively to
        one HUD colour, at the same pixel. Freeze that actual HUD, rather than
        claiming Creative GUI RGB is identical to gameplay lighting.
        """
        if selected_slot(path) != self.slot:
            raise FeedbackError("Selected slot changed while closing inventory")
        rgb = pixels(path)
        actual = rgb[940:1004, 500 + self.slot * 80 : 564 + self.slot * 80].copy()
        original = self.icon[self.mask]
        resumed = actual[self.mask]
        _, left = np.unique(original, axis=0, return_inverse=True)
        _, right = np.unique(resumed, axis=0, return_inverse=True)
        pairs = np.unique(np.stack((left, right), axis=1), axis=0)
        if (
            len(pairs) < 8
            or len(pairs) != len(np.unique(left))
            or len(pairs) != len(np.unique(right))
        ):
            raise FeedbackError("Selected item texture changed during inventory close")
        actual.flags.writeable = False
        return replace(self, icon=actual)

    def observe(self, path):
        slot = selected_slot(path)
        if slot != self.slot:
            raise FeedbackError(
                "Selected hotbar slot changed; inspect your block again"
            )
        rgb = pixels(path)
        x, y = 500 + slot * 80, 940
        actual = rgb[y : y + 64, x : x + 64]
        if not np.array_equal(actual[self.mask], self.icon[self.mask]):
            raise FeedbackError(
                "Selected block changed or its icon is not stable; inspect your block again"
            )
        return self.material
