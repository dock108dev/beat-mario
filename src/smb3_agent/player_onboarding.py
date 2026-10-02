"""Read-only first-use guidance from the actual Minecraft session state.

Saved configuration and a connected camera are useful setup steps. Neither
advertises an executable building task or restores observations/authority.
"""

TASK_LABELS = {
    "camera": "Small camera adjustments",
    "aim": "Aim at a reachable block face",
    "move": "Short movement on inspected flat ground",
    "place": "One observed block addition",
    "wall": "Finish the wall with its doorway",
}


def minecraft_onboarding(profile, native):
    if profile and profile.get("game") != "minecraft":
        return None
    native = native or {}
    features = native.get("features", {})
    saved = bool(profile)
    connected = bool(saved and native.get("connected"))
    region = bool(connected and native.get("scope"))
    wall_enabled = features.get("wall") is True
    steps = [
        {
            "label": "Save your Minecraft profile",
            "status": "done" if saved else "next",
            "detail": "Your settings and notes are saved locally."
            if saved
            else "Choose Minecraft Java Creative, name the setup and Save profile.",
        },
        {
            "label": "Connect and calibrate your game",
            "status": "done" if connected else "next" if saved else "pending",
            "detail": "Current window and calibration are connected; Start checks them again."
            if connected
            else "Follow the permissions and supported-settings steps below, select your game window, calibrate, then Connect current calibration.",
        },
        {
            "label": "Check your building region",
            "status": "done" if region else "next" if connected else "pending",
            "detail": "A visible region is selected; ground, reach, material and protected blocks are checked again during work."
            if region
            else "Prepare the flat practice area described below, select a supported block and point at the ground beneath the doorway. Check visible block and scope, mark any protected blocks, then save the checked region.",
        },
        {
            "label": "Review and run your first building task",
            "status": "next" if region and wall_enabled else "pending"
            if wall_enabled
            else "unavailable",
            "detail": "Ask to finish the 7 by 3 wall with its centered doorway, read the scope, Review, then Start. Afterwards use Stop or Take control and reopen the saved profile and outcome."
            if wall_enabled
            else "Wall building is unavailable in this build. Setup and camera practice remain available; a building-capable update is required for this step.",
        },
    ]
    if native.get("release_blocked"):
        status, title, next_action = (
            "release_blocked",
            "Confirm control has returned",
            "Choose Take control and wait for confirmed release before continuing setup.",
        )
    elif native.get("busy"):
        status, title, next_action = (
            "working",
            "Current setup or task is running",
            "Keep this page open and wait for the result. Stop and Take control remain available.",
        )
    elif not saved:
        status, title, next_action = "profile", steps[0]["label"], steps[0]["detail"]
    elif not connected:
        status, title, next_action = "connection", steps[1]["label"], steps[1]["detail"]
    elif not wall_enabled:
        status, title, next_action = (
            "setup_only",
            "Camera practice is available; building awaits an update",
            "You can review a small camera request. Continue the wall step with a building-capable app update.",
        )
    elif not region:
        status, title, next_action = "region", steps[2]["label"], steps[2]["detail"]
    else:
        status, title, next_action = "task_review", steps[3]["label"], steps[3]["detail"]
    return {
        "status": status,
        "title": title,
        "next_action": next_action,
        "steps": steps,
        "available_tasks": [label for kind, label in TASK_LABELS.items() if features.get(kind) is True],
        "blocked_tasks": [label for kind, label in TASK_LABELS.items() if features.get(kind) is not True],
    }
