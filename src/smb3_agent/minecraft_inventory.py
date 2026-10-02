"""Finite, read-only Creative inventory inspection through the existing input owner."""

from dataclasses import asdict
import json
from pathlib import Path
import time

from smb3_agent.feedback_contracts import FeedbackError
from smb3_agent.host_contracts import InputCommand, InputKind
from smb3_agent.input_guardian import InputGuardian
from smb3_agent.minecraft_hotbar import MaterialReference, selected_slot
from smb3_agent.minecraft_scene import (
    HudGlyphDetector,
    creative_inventory,
    inspect_inventory,
)
from smb3_agent.minecraft_settings import require_supported_scene
from smb3_agent.ordinary_input import MacProfileInput


def wait_visible(capture, accept, canceled, *, timeout=2, clock=time.monotonic):
    """Observe a toggle's result without posting another toggle.

    Capture/authority failures propagate immediately. Only an as-yet absent
    visible transition is polled under the caller's total work budget.
    """
    deadline = clock() + timeout
    while True:
        frame = capture()
        try:
            accept(frame)
            return frame
        except FeedbackError:
            if clock() >= deadline:
                raise
            if canceled.wait(0.1):
                raise FeedbackError("Visible transition canceled")


def inspect_creative(
    host,
    binding,
    root,
    canceled,
    *,
    material=False,
    publish_driver=lambda driver: None,
    budget=None,
    expected_settings=None,
):
    """Two E pulses and optionally one hover; no inventory selection or item changes.

    The selected slot comes from visible HUD pixels before opening inventory. The
    mode comes from Creative-specific inventory pixels; material comes from its
    advanced tooltip and the actual item icon. Input is revoked before return.
    """
    import Quartz as q

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 15
    scene_settings = require_supported_scene()
    if expected_settings and expected_settings != scene_settings:
        raise FeedbackError("Minecraft setup changed; reconnect")
    record = {
        "schema": "visible-creative-inspection/v1",
        "accepted": False,
        "input_ms": 0,
        "captures": [],
    }
    driver = None

    def authority():
        if (
            canceled.is_set()
            or time.monotonic() > deadline
            or require_supported_scene() != scene_settings
        ):
            raise FeedbackError(
                "Inventory inspection canceled, expired or settings changed"
            )

    def isolation(window):
        binding.require(window, execution=True)
        if window.title != "Minecraft 26.3 - Singleplayer":
            raise FeedbackError(
                "Only vanilla single-player disposable worlds are supported"
            )

    def capture():
        authority()
        if budget:
            budget.consume()
        from smb3_agent.minecraft_capture import capture_frame

        frame, _, _ = capture_frame(
            host, root, execution=True, expected_pixels=binding.pixel_size
        )
        isolation(frame.window)
        record["captures"].append(
            {
                "path": str(frame.path),
                "sha256": frame.sha256,
                "captured_at": frame.captured_at,
            }
        )
        return frame

    def press_e():
        if budget:
            budget.consume(80)
        record["input_ms"] += 80
        driver.send(
            InputCommand(
                InputKind.KEYBOARD,
                "e",
                "press",
                80,
                purpose="read_only_creative_inventory",
            )
        )
        if canceled.wait(0.08):
            raise FeedbackError("Inventory inspection canceled")

    try:
        if q.CGCursorIsVisible():
            raise FeedbackError("Resume the paused game before inspecting the block")
        before = capture()
        slot = selected_slot(before.path)
        driver = MacProfileInput(
            window_provider=host.detect_window,
            authority_guard=authority,
            isolation_guard=isolation,
            external_guard=InputGuardian(root / "input-guardian.jsonl"),
        )
        publish_driver(driver)
        driver.arm()
        press_e()

        # WindowServer can return the last drawn world frame briefly after
        # the E callback. Observe the transition; never resend a toggle.
        def accept_inventory(frame):
            creative_inventory(frame.path)
            if not q.CGCursorIsVisible():
                raise FeedbackError("Creative inventory capture not established")

        inventory = wait_visible(capture, accept_inventory, canceled)
        reference = None
        if material:
            # Hover only after the current inventory frame is positively verified.
            if not q.CGCursorIsVisible():
                raise FeedbackError("Inventory did not acquire a visible cursor")
            if not 0 <= time.monotonic() - inventory.captured_at <= 0.8:
                raise FeedbackError(
                    "Inventory geometry observation expired before hover"
                )
            px, py = 464 + (9 + 18 * slot + 8) * 4, 264 + (112 + 8) * 4
            x, y, _, _ = binding.bounds
            point = (round(x + px / 2), round(y + py / 2))
            if budget:
                budget.consume()
            driver.send(
                InputCommand(
                    InputKind.MOUSE,
                    "move",
                    "move",
                    0,
                    target=point,
                    purpose="inspect_selected_slot_tooltip",
                )
            )
            if canceled.wait(0.12):
                raise FeedbackError("Inventory inspection canceled after hover")
            inventory = capture()
            evidence = inspect_inventory(
                inventory,
                detector=HudGlyphDetector.installed(),
                now=time.monotonic(),
                settings=scene_settings,
                pointer=(px, py),
                selected_slot=slot,
            )
            reference = MaterialReference.from_inventory(inventory.path, evidence)
            record["material"] = {k: v for k, v in asdict(evidence).items()}
        press_e()

        def accept_gameplay(frame):
            nonlocal reference
            if q.CGCursorIsVisible():
                raise FeedbackError(
                    "Gameplay capture did not resume after inventory inspection"
                )
            selected_slot(frame.path)
            try:
                creative_inventory(frame.path)
            except FeedbackError:
                pass
            else:
                raise FeedbackError("Inventory is still visibly open")
            if reference:
                reference = reference.bind_resumed_world(frame.path)
                reference.observe(frame.path)

        wait_visible(capture, accept_gameplay, canceled)
        record.update(
            accepted=True,
            creative_source=inventory.sha256,
            slot=slot,
            settings=scene_settings,
        )
        return reference, record
    except Exception as exc:
        record["reason"] = str(exc)
        raise
    finally:
        if driver:
            driver.neutralize()
            record["release"] = driver.release_receipt()
            record["guardian_closed"] = driver.close()
            if not record["release"]["confirmed"] or not record["guardian_closed"]:
                record["accepted"] = False
        else:
            record["release"] = {"confirmed": True, "method": "no input owner created"}
        (root / "inspection.json").write_text(json.dumps(record, indent=2) + "\n")
        if not record["release"]["confirmed"] or record.get("guardian_closed") is False:
            raise FeedbackError("Inventory input release unconfirmed; new work blocked")
