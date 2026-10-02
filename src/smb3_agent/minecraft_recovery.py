"""Explicit selected-window key-up recovery; never starts movement."""

from smb3_agent.feedback_contracts import FeedbackError

MOVEMENT_KEYS = (0, 1, 2, 13, 49, 56)  # A, S, D, W, Space, Shift


def release_movement_keys(host, binding, *, quartz=None):
    if quartz is None:
        import Quartz as quartz
    if not quartz.CGPreflightPostEventAccess():
        raise FeedbackError("Accessibility permission needed for key release")
    posted = []
    for code in MOVEMENT_KEYS:
        # A focus/process/window transition prevents releases reaching another app.
        binding.require(host.detect_window(), execution=True)
        event = quartz.CGEventCreateKeyboardEvent(None, code, False)
        quartz.CGEventPost(quartz.kCGHIDEventTap, event)
        posted.append(code)
    return {
        "method": "selected-window movement key-up only",
        "released_codes": posted,
        "gameplay_stillness": "requires independent visible observation",
    }
