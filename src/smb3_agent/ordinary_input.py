"""Thin reusable host interface over existing bounded native input ownership."""
from __future__ import annotations

import time

from smb3_agent.native_input import MacBoundedInputDriver, _KEY_CODES


class MacProfileInput(MacBoundedInputDriver):
    def close(self):
        self.neutralize()
        guardian = self.external_guard
        return (guardian is None or guardian.close()) and self.release_receipt()["confirmed"]

    def release_receipt(self) -> dict:
        """Read OS state after key-up; posting an event alone is not a receipt."""
        started = time.monotonic()
        try:
            q = self.q
            while True:
                with self._lock:
                    ledger_empty = not self._held
                keys = [key for key, code in _KEY_CODES.items()
                        if q.CGEventSourceKeyState(q.kCGEventSourceStateHIDSystemState, code)]
                buttons = [button for button in (q.kCGMouseButtonLeft, q.kCGMouseButtonRight)
                           if q.CGEventSourceButtonState(q.kCGEventSourceStateHIDSystemState, button)]
                confirmed = ledger_empty and not keys and not buttons
                # CGEventPost queues key-up. Observe its native acknowledgment
                # independently; never infer release from the emptied ledger.
                if confirmed or time.monotonic()-started >= .05:
                    break
                time.sleep(.001)
            return {"confirmed": confirmed, "ledger_empty": ledger_empty,
                    "held_keys": keys, "held_mouse_buttons": buttons,
                    "acknowledgment_seconds": time.monotonic()-started,
                    "method": "native_HID_state_and_pressed_ledger"}
        except Exception:
            return {"confirmed": False, "method": "unavailable"}
