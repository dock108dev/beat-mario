"""Explicit isolated engineering checkpoint launch; no personal-save discovery."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import time
from uuid import uuid4

from smb3_agent.paths import repository_path
from smb3_agent.host_contracts import HostError


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def start_identity(pid):
    return subprocess.run(["ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True, text=True, timeout=1).stdout.strip()


def visible_windows():
    import Quartz as q
    records = q.CGWindowListCopyWindowInfo(q.kCGWindowListOptionOnScreenOnly, 0) or []
    result = []
    for record in records:
        if record.get(q.kCGWindowLayer) != 0 or "openttd" not in str(record.get(q.kCGWindowOwnerName, "")).lower():
            continue
        pid = int(record[q.kCGWindowOwnerPID])
        bounds = record.get(q.kCGWindowBounds, {})
        # macOS can publish separate tiny native traffic-light windows.
        if min(bounds.get("Width", 0), bounds.get("Height", 0)) < 100:
            continue
        result.append({"pid": pid, "started": start_identity(pid),
            "window_id": str(record[q.kCGWindowNumber]), "title": str(record.get(q.kCGWindowName) or "OpenTTD"),
            "bounds": dict(record.get(q.kCGWindowBounds, {}))})
    return result


class PreparedGame:
    def __init__(self, root):
        self.root = Path(root)
        self.owned = {}

    def windows(self):
        result = visible_windows()
        for item in result:
            owned = self.owned.get(item["pid"])
            item["verified_test"] = bool(owned and item["started"] == owned["started"])
            item["label"] = ("Paused test " + owned["id"][:6] if item["verified_test"] else "Unverified game") + " · " + item["title"]
        return result

    def launch(self):
        source = repository_path("artifacts/private-beta/pb1/preflight/game-v2")
        manifest = json.loads(repository_path("artifacts/private-beta/pb1/candidate.json").read_text())
        app = Path("/Applications/OpenTTD.app")
        checkpoint = source / "save/Unnamed, 1950-01-01.sav"
        if (sha(checkpoint) != manifest["checkpoint_sha256"]
                or sha(source/"openttd.cfg") != manifest["settings_sha256"]
                or sha(app/"Contents/MacOS/openttd") != manifest["game_executable_sha256"]):
            raise HostError("The prepared game or settings changed; this test setup needs a new check")
        identity = uuid4().hex
        folder = (self.root / identity).resolve()
        folder.mkdir(parents=True, exist_ok=False)
        for name in ("baseset", "lang", "save"):
            shutil.copytree(source/name, folder/name)
        shutil.copy2(source/"openttd.cfg", folder/"openttd.cfg")
        before = {w["pid"] for w in visible_windows()}
        subprocess.run(["open", "-n", str(app), "--args", "-v", "cocoa", "-c", str(folder/"openttd.cfg"),
            "-X", "-x", "-g", str(folder/"save/Unnamed, 1950-01-01.sav"), "-r", "1280x1024",
            "-m", "null", "-s", "null", "-S", "NoSound", "-M", "NoMusic"], check=True, timeout=3)
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            for w in visible_windows():
                if w["pid"] in before:
                    continue
                args = subprocess.run(["ps", "-p", str(w["pid"]), "-o", "command="],
                    capture_output=True, text=True, timeout=1).stdout
                if str(folder/"openttd.cfg") not in args:
                    continue
                owned = {**w, "id": identity, "folder": str(folder), "checkpoint_sha256": sha(checkpoint),
                         "settings_sha256": sha(folder/"openttd.cfg"), "game_build": "15.3"}
                self.owned[w["pid"]] = owned
                (folder/"launch.json").write_text(json.dumps(owned, indent=2))
                self.arrange(owned)
                return owned
            time.sleep(.1)
        raise HostError("Game launch was not confirmed; no unknown process was selected")

    def arrange(self, selection):
        """Place only our isolated test window; keep its exact size/settings.

        This is preparation before connection, never a gameplay skill. The
        selected PID/start/window and one matching native window must agree.
        """
        import ApplicationServices as ax
        import Quartz as q
        owned = self.binding(selection)
        live = [w for w in visible_windows() if (w["pid"], w["started"], w["window_id"]) ==
                (owned["pid"], owned["started"], owned["window_id"])]
        if len(live) != 1 or not ax.AXIsProcessTrusted():
            raise HostError("Test-window placement is unavailable; place the game visibly beside this app")
        before = live[0]["bounds"]
        application = ax.AXUIElementCreateApplication(owned["pid"])
        error, windows = ax.AXUIElementCopyAttributeValue(application, ax.kAXWindowsAttribute, None)
        if error:
            raise HostError("The owned test window could not be inspected")
        matching = []
        for window in windows:
            error, size = ax.AXUIElementCopyAttributeValue(window, ax.kAXSizeAttribute, None)
            if error:
                continue
            valid, value = ax.AXValueGetValue(size, ax.kAXValueCGSizeType, None)
            if valid and tuple(round(v) for v in value) == (before["Width"], before["Height"]):
                matching.append(window)
        if len(matching) != 1:
            raise HostError("Exact owned native window was not unique; placement refused")
        displays = q.CGGetActiveDisplayList(8, None, None)[1]
        fits = [q.CGDisplayBounds(display) for display in displays]
        fits = [rect for rect in fits if rect.size.width >= before["Width"]+32
                and rect.size.height >= before["Height"]+64]
        if not fits:
            raise HostError("No display fits the tested window; preparation needs attention")
        screen = min(fits, key=lambda rect: rect.origin.x)
        point = (int(screen.origin.x+16), int(screen.origin.y+40))
        self.binding(selection)  # recheck process identity immediately before moving
        error = ax.AXUIElementSetAttributeValue(matching[0], ax.kAXPositionAttribute,
            ax.AXValueCreate(ax.kAXValueCGPointType, point))
        if error:
            raise HostError("Owned test-window placement was refused")
        # AX placement completes asynchronously. Confirmation is bounded and
        # still requires the exact original window and unchanged dimensions.
        deadline = time.monotonic()+.75
        while True:
            after = [w for w in visible_windows() if w["window_id"] == owned["window_id"]
                     and w["pid"] == owned["pid"] and w["started"] == owned["started"]]
            if (len(after) == 1 and tuple(after[0]["bounds"][k] for k in ("X", "Y")) == point
                    or time.monotonic() >= deadline):
                break
            time.sleep(.02)
        if (len(after) != 1 or any(after[0]["bounds"][k] != before[k] for k in ("Width", "Height"))
                or tuple(after[0]["bounds"][k] for k in ("X", "Y")) != point):
            raise HostError("Test-window position or geometry was not confirmed")
        (Path(owned["folder"])/"placement.json").write_text(json.dumps({
            "selection": {k: owned[k] for k in ("pid", "started", "window_id")},
            "before": before, "after": after[0]["bounds"], "scope": "owned engineering preparation"}, indent=2))

    def binding(self, selection):
        owned = self.owned.get(selection.get("pid"))
        if not owned or any(selection.get(k) != owned[k] for k in ("started", "window_id")):
            raise HostError("Select an exact paused test window opened by this app")
        if start_identity(owned["pid"]) != owned["started"]:
            raise HostError("The selected test process ended")
        return owned

    def close(self):
        for owned in self.owned.values():
            if start_identity(owned["pid"]) != owned["started"]:
                continue
            args = subprocess.run(["ps", "-p", str(owned["pid"]), "-o", "command="],
                capture_output=True, text=True, timeout=1).stdout
            if str(Path(owned["folder"])/"openttd.cfg") not in args:
                raise HostError("Owned process identity changed; process closure was refused")
            os.kill(owned["pid"], 15)
            deadline = time.monotonic()+2
            while start_identity(owned["pid"]) == owned["started"] and time.monotonic() < deadline:
                time.sleep(.02)
            if start_identity(owned["pid"]) == owned["started"]:
                raise HostError("Test game closure is unconfirmed")
