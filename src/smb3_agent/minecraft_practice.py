"""Owned, isolated Java practice server. Never opens or migrates owner saves."""

from __future__ import annotations

import hashlib
import json
import shutil
from uuid import uuid4
from pathlib import Path
import socket
import subprocess
import time
import urllib.request

from smb3_agent.delivery import OwnedGameProcesses

from smb3_agent.minecraft_delivery import world_home, java_runtime, GAME_VERSION as VERSION


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


class PracticeServer:
    def __init__(self, home=None, port=25575, *, survival=False):
        self.survival = survival
        self.home = Path(world_home(survival) if home is None else home).resolve()
        self.port = port
        self.owned = OwnedGameProcesses()
        self.process = None
        self.log = None

    def prepare(self, *, accept_eula=False):
        marker = self.home / "companion-practice.json"
        self.home.mkdir(parents=True, exist_ok=True)
        if not marker.exists():
            if any(self.home.iterdir()):
                raise ValueError(
                    "Refusing to adopt a nonempty unmarked world directory"
                )
            marker.write_text(json.dumps({"schema": 1, "version": VERSION}))
        if json.loads(marker.read_text()) != {"schema": 1, "version": VERSION}:
            raise ValueError("Practice world version/ownership mismatch")
        identity = self.home / "world-identity.json"
        if not identity.exists():
            identity.write_text(
                json.dumps({"id": uuid4().hex, "survival": self.survival})
            )
        world = json.loads(identity.read_text())
        if world["survival"] != self.survival:
            raise ValueError("Refusing to change retained world mode")
        self.world_id = world["id"]
        eula = self.home / "eula.txt"
        if self.survival and not eula.exists():
            creative_home = world_home()
            accepted = creative_home / "eula.txt"
            if accepted.exists() and "eula=true" in accepted.read_text().splitlines():
                shutil.copy2(accepted, eula)
                for name in ("server.jar", "server-download.json"):
                    shutil.copy2(creative_home / name, self.home / name)
        if accept_eula:
            eula.write_text(
                "# Accepted explicitly by owner for this isolated practice server\neula=true\n"
            )
        if not eula.exists() or "eula=true" not in eula.read_text().splitlines():
            raise ValueError(
                "Owner must accept https://www.minecraft.net/en-us/eula first"
            )
        jar = self.home / "server.jar"
        manifest = self.home / "server-download.json"
        if not manifest.exists():
            versions = fetch_json(
                "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
            )
            url = next(v["url"] for v in versions["versions"] if v["id"] == VERSION)
            info = fetch_json(url)["downloads"]["server"]
            manifest.write_text(json.dumps(info, indent=2))
        info = json.loads(manifest.read_text())
        if not jar.exists():
            with urllib.request.urlopen(info["url"], timeout=120) as source:
                blob = source.read()
            if hashlib.sha1(blob).hexdigest() != info["sha1"]:
                raise ValueError("Official server download digest mismatch")
            jar.write_bytes(blob)
        if hashlib.sha1(jar.read_bytes()).hexdigest() != info["sha1"]:
            raise ValueError("Server digest mismatch; refusing to launch")
        # Only this app-owned new practice server uses offline identities.
        (self.home / "server.properties").write_text(
            f"server-ip=127.0.0.1\nserver-port={self.port}\n"
            "online-mode=false\nenforce-secure-profile=false\n"
            "level-name=practice-world\nlevel-type=minecraft:flat\n"
            'generator-settings={"layers":[{"block":"minecraft:bedrock","height":1},{"block":"minecraft:dirt","height":2},{"block":"minecraft:grass_block","height":1}],"biome":"minecraft:plains"}\n'
            "gamemode=creative\nforce-gamemode=true\ndifficulty=peaceful\n"
            "spawn-protection=0\nview-distance=4\nsimulation-distance=4\n"
            "max-players=4\nenable-rcon=false\nenable-query=false\n"
            "sync-chunk-writes=true\nmotd=Game Companion isolated practice\n"
        )
        if self.survival:
            props = self.home / "server.properties"
            text = (
                props.read_text()
                .replace("level-type=minecraft:flat", "level-type=minecraft:normal")
                .replace("gamemode=creative", "gamemode=survival")
            )
            text = (
                "\n".join(
                    line
                    for line in text.splitlines()
                    if not line.startswith("generator-settings=")
                )
                + "\nlevel-seed=8675309\n"
            )
            props.write_text(text)
        return jar

    def start(self, *, accept_eula=False):
        jar = self.prepare(accept_eula=accept_eula)
        with socket.socket() as probe:
            # A stopped server may leave TIME_WAIT sockets; they are not a listener.
            # SO_REUSEADDR permits that case while an active listener still conflicts.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", self.port))
            except OSError as exc:
                raise OSError("Minecraft’s local port is occupied. Quit the other practice server, then connect again. No other process was stopped.") from exc
        self.log = (self.home / "server.log").open("w")
        self.process = self.owned.launch(
            [java_runtime(), "-Xms512M", "-Xmx1536M", "-jar", str(jar), "nogui"],
            cwd=self.home,
            stdin=subprocess.PIPE,
            stdout=self.log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.monotonic() + 120
        try:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError(
                        "Practice server exited; inspect its local server.log"
                    )
                if "Done (" in (self.home / "server.log").read_text():
                    self.command("gamerule doDaylightCycle false")
                    self.command("time set day")
                    self.command("gamerule doMobSpawning false")
                    return self
                time.sleep(0.2)
            raise TimeoutError("Practice server did not become ready")
        except BaseException:
            self.close()
            raise

    def command(self, command):
        """Trusted setup only, never exposed through the bot/application protocol."""
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError("Practice server is not running")
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def close(self):
        if self.process and self.process.poll() is None:
            self.command("stop")
            try:
                self.process.wait(timeout=30)  # Allow the owned world to save.
            except subprocess.TimeoutExpired:
                pass
        self.owned.close()
        if self.log:
            self.log.close()
