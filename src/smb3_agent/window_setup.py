"""Explicit selected-window sizing/placement; never a gameplay input primitive."""

import time

from smb3_agent.host_contracts import HostError
from smb3_agent.screen_host import MacSelectedWindowHost


def available_displays():
    import AppKit

    return [
        {"id": int(s.deviceDescription()["NSScreenNumber"]), "label": s.localizedName()}
        for s in AppKit.NSScreen.screens()
    ]


def arrange_selected(selection, *, display_id, viewport):
    import Quartz as q
    import ApplicationServices as ax

    host = MacSelectedWindowHost(
        selection["pid"],
        selection["started"],
        selection["window_id"],
        background_observation=True,
    )
    before = host.detect_window(require_foreground=False)
    screens = available_displays()
    if type(display_id) is not int or not any(s["id"] == display_id for s in screens):
        raise HostError("Choose a currently connected display")
    if not ax.AXIsProcessTrusted():
        raise HostError(
            "Accessibility permission is required to arrange the selected game"
        )
    display = q.CGDisplayBounds(display_id)
    width, height = viewport
    if display.size.width < width + 32 or display.size.height < height + 64:
        raise HostError("The selected display does not fit the supported window size")
    app = ax.AXUIElementCreateApplication(before.process_id)
    error, windows = ax.AXUIElementCopyAttributeValue(app, ax.kAXWindowsAttribute, None)
    if error:
        raise HostError("Selected game window cannot be inspected")
    matches = []
    for window in windows or ():
        error, size = ax.AXUIElementCopyAttributeValue(
            window, ax.kAXSizeAttribute, None
        )
        if error:
            continue
        valid, value = ax.AXValueGetValue(size, ax.kAXValueCGSizeType, None)
        if valid and tuple(round(v) for v in value) == before.bounds[2:]:
            matches.append(window)
    if len(matches) != 1:
        raise HostError("Exact native window is ambiguous; arrange it manually")
    if host.detect_window(require_foreground=False) != before:
        raise HostError("Selected process/window changed during setup")
    point = (int(display.origin.x + 16), int(display.origin.y + 40))
    error = ax.AXUIElementSetAttributeValue(
        matches[0],
        ax.kAXPositionAttribute,
        ax.AXValueCreate(ax.kAXValueCGPointType, point),
    )
    if error:
        raise HostError("Selected window placement was refused")
    end = time.monotonic() + 1
    while time.monotonic() < end:
        current = host.detect_window(require_foreground=False)
        if current.bounds[:2] == point:
            break
        time.sleep(0.02)
    else:
        raise HostError("Selected window placement was not confirmed")
    error = ax.AXUIElementSetAttributeValue(
        matches[0],
        ax.kAXSizeAttribute,
        ax.AXValueCreate(ax.kAXValueCGSizeType, (width, height)),
    )
    if error:
        raise HostError("Supported window size was refused")
    end = time.monotonic() + 1
    while time.monotonic() < end:
        current = host.detect_window(require_foreground=False)
        if current.bounds == (*point, width, height):
            return {
                "display_id": display_id,
                "bounds": current.bounds,
                "confirmed": True,
            }
        time.sleep(0.02)
    raise HostError(
        "Supported window size was not confirmed; reconnect only after fixing setup"
    )
