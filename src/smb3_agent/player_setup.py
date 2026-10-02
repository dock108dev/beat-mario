"""Ordinary setup/configuration owner alongside existing catalog and controls."""

from dataclasses import asdict
from uuid import uuid4

from smb3_agent.player_store import PlayerStore, TEMPLATES, VERSION
from smb3_agent.minecraft_skills import wall_cells
from smb3_agent.skill_runtime import SIGNATURES
from smb3_agent.player_onboarding import minecraft_onboarding


class PlayerSetupService:
    def __init__(
        self,
        *,
        store=None,
        neutralize=lambda: True,
        open_profile=lambda p: None,
        minecraft=None,
    ):
        self.store = store or PlayerStore()
        self.minecraft = minecraft
        self.neutralize, self.open_profile = neutralize, open_profile
        self.selected = None
        self.messages = []
        self.plan = None
        self.reviewed = False
        self.revision = 0
        self.reason = "Choose a game template and save your setup. Opening a profile never starts gameplay."

    def snapshot(self):
        native = self.minecraft.snapshot() if self.minecraft else None
        return {
            "version": VERSION,
            "templates": TEMPLATES,
            "profiles": self.store.list(),
            "selected": self.selected,
            "reason": self.reason,
            "messages": self.messages[-30:],
            "plan": self.plan,
            "reviewed": self.reviewed,
            "history": self.store.history(self.selected["id"]) if self.selected else [],
            "minecraft": native,
            "minecraft_onboarding": minecraft_onboarding(self.selected, native),
            "native_minecraft_available": bool(
                native and native["features"].get("camera")
            ),
            "native_reason": self.minecraft.reason
            if self.minecraft
            else "Native Minecraft input is disabled; a current app-created calibration and checked native provider are required.",
            "data_location": str(self.store.root),
        }

    def _revoke(self):
        # Direct existing control owners run before persistence or planning.
        native_safe = (
            self.minecraft.revoke("Player edit or direct control")
            if self.minecraft
            else True
        )
        if not self.neutralize() or not native_safe:
            raise ValueError(
                "Input release is unconfirmed. Take control and inspect diagnostics before changing setup."
            )
        self.plan, self.reviewed = None, False
        self.revision += 1

    def dispatch(self, action, p=None):
        p = p or {}
        if action in {
            "windows",
            "arrange",
            "calibrate",
            "connect",
            "scope",
            "protect",
            "heartbeat",
        }:
            if (
                not self.minecraft
                or not self.selected
                or self.selected["game"] != "minecraft"
            ):
                raise ValueError("Open a Minecraft profile first")
            if action != "heartbeat":
                self._revoke()
            self.minecraft.dispatch(action, p)
        elif action == "save_workspace":
            self._revoke()
            if not self.minecraft or not self.selected or not self.minecraft.scope:
                raise ValueError("Check a fresh visible scope first")
            self.minecraft.require_idle()
            config = asdict(self.minecraft.scope)
            config.pop("source")
            self.selected = self.store.save(
                game="minecraft",
                name=self.selected["name"],
                notes=self.selected["notes"],
                identity=self.selected["id"],
                workspace=config,
            )
            self.reason = "Work region saved as configuration. Reopening requires fresh inspection and review."
        elif action in {"stop", "reclaim", "chat", "edit", "disconnect"}:
            self._revoke()
            self.reason = "Control returned. Requests and saved profiles grant no gameplay authority."
        elif action in {"save", "open", "duplicate", "import"}:
            self._revoke()
            if self.minecraft:
                self.minecraft.require_idle()
                self.minecraft.revoke(
                    "Profile reopened; no authority restored", disconnect=True
                )
            if action == "save":
                value = self.store.save(
                    game=p.get("game"),
                    name=p.get("name"),
                    notes=p.get("notes", ""),
                    identity=p.get("id") or None,
                )
            elif action == "import":
                value = self.store.import_profile(p.get("json"))
            elif action == "duplicate":
                value = self.store.duplicate(p.get("id"))
            else:
                value = self.store.load(p.get("id"))
            self.open_profile(value)
            self.selected = value
            self.messages = []
            self.reason = "Saved setup opened. Connect the exact current game window; repeat checks after settings changes."
        elif action == "minecraft_settings":
            self._revoke()
            from smb3_agent.minecraft_settings import apply_supported_settings

            applied = apply_supported_settings(
                backups=self.store.root / "settings-backups"
            )
            self.reason = (
                applied["message"] + " Previous settings saved at " + applied["backup"]
            )
        elif action == "export":
            return {"export": self.store.load(p.get("id"))}
        elif action == "report":
            return self.store.report(
                text=p.get("text"),
                profile_id=p.get("id") or None,
                checks={
                    "native_minecraft": self.minecraft.snapshot()["features"]
                    if self.minecraft
                    else "disabled",
                    "automatic_telemetry": False,
                },
            )
        elif action == "message":
            self._revoke()
            if not self.selected or self.selected["game"] != "minecraft":
                raise ValueError(
                    "Open a Minecraft profile here; use the game conversation for other games."
                )
            text = p.get("text")
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
                raise ValueError("Enter a request up to 2000 characters")
            self.messages.append({"role": "user", "text": text})
            if not self._save_correction(text):
                self._propose(text)
            self.messages.append({"role": "assistant", "text": self.reason})
        elif action == "review":
            if not self.plan or p.get("plan_id") != self.plan["id"]:
                raise ValueError("Review the current request again")
            if self.minecraft and self.plan.get("executable"):
                self.minecraft.bind_review(self.plan)
            self.reviewed = True
            self.reason = "Scope reviewed. Start grants only this bounded task; questions and saved configuration grant no input authority."
        elif action == "start":
            if not self.minecraft or not self.plan or not self.plan.get("executable"):
                raise ValueError(
                    "Native Start is disabled for this request; check setup and feature availability"
                )
            if not self.reviewed:
                raise ValueError("Review this request before Start")
            self.minecraft.start(self.plan, self.selected["id"], p)
            self.reviewed = False
            self.reason = "Bounded task started. Stop and Take control remain direct."
        else:
            raise ValueError("Unknown setup action")
        return self.snapshot()

    def _save_correction(self, text):
        """Persist narrow player intent; it never supplies live material/protection."""
        import re

        words = text.casefold().strip()
        material = re.fullmatch(
            r"(?:actually[, ]+)?use (stone|bricks|oak planks|cobblestone)(?: instead)?[.!]?",
            words,
        )
        protection = re.fullmatch(
            r"(?:actually[, ]+)?(?:leave the marked structure alone|protect the marked structure)[.!]?",
            words,
        )
        if not material and not protection:
            return False
        prefix = (
            "Preferred building material:"
            if material
            else "Require marked protection for builds."
        )
        notes = [
            line
            for line in self.selected["notes"].splitlines()
            if not line.startswith(prefix)
        ]
        value = "minecraft:" + material[1].replace(" ", "_") if material else ""
        notes.append(prefix + (" " + value if material else ""))
        self.selected = self.store.save(
            game="minecraft",
            name=self.selected["name"],
            identity=self.selected["id"],
            notes="\n".join(notes),
        )
        self.reason = (
            "Future build preference saved. Choose the block manually and check fresh scope, then send a new request."
            if material
            else "Future builds require marked protection. Mark the relevant exposed blocks and send a new request."
        )
        return True

    def _propose(self, text):
        import re
        from smb3_agent.request_planning import is_negated

        words = text.casefold().strip()
        if any(v in words for v in ("?", "what can", "how do", "explain", "tell me")):
            self.reason = "Tell: camera correction uses F3; short movement is limited to flat ground; building adds full blocks inside a reviewed region. Current feature availability is shown in setup. Questions never issue input."
            return
        candidates = []
        for kind, verbs in {
            "camera": ("look", "turn", "camera"),
            "move": ("move", "walk", "step"),
            "aim": ("aim",),
            "place": ("place",),
            "wall": ("wall",),
        }.items():
            for verb in verbs:
                matches = list(re.finditer(r"\b" + verb + r"\b", words))
                if any(not is_negated(words, m.start()) for m in matches):
                    candidates.append(kind)
                    break
        if "wall" in candidates:
            candidates = (
                ["wall"] if set(candidates) <= {"wall", "place"} else candidates
            )
        if len(candidates) != 1:
            self.reason = "Specify one bounded camera, move, aim, placement or wall request. Survival, breaking blocks and exploration are unavailable. Nothing will run."
            return
        kind = candidates[0]
        unavailable = (
            "survival",
            "break",
            "breaking",
            "destroy",
            "fly",
            "flying",
            "mine",
            "mining",
            "explore",
        )
        if any(
            not is_negated(words, m.start())
            for verb in unavailable
            for m in re.finditer(r"\b" + verb + r"\b", words)
        ):
            self.reason = "That request includes an unavailable action. Use additions in a disposable Creative world; nothing will run."
            return
        if kind == "wall":
            dimensions = re.search(
                r"(\d+)\s*(?:by|x|×)\s*(\d+)(?:\s*(?:by|x|×)\s*(\d+))?", words
            )
            if dimensions and (
                int(dimensions[1]),
                int(dimensions[2]),
                int(dimensions[3] or 1),
            ) != (7, 3, 1):
                self.reason = "The available wall is 7 wide, 3 high and 1 thick, with a centered 1 by 2 doorway. Send that scope or choose another available task."
                return
        examples = {
            "camera": "Look slightly right, then stop.",
            "move": "Move forward 0.25 blocks.",
            "aim": "Aim at the visible reachable full-block face.",
            "place": "Place one stone block inside the reviewed region.",
            "wall": "Finish a 7 by 3 wall with a centered 1 by 2 doorway; leave the marked structure alone.",
        }
        self.plan = {
            "id": uuid4().hex,
            "revision": self.revision,
            "profile_id": self.selected["id"],
            "request": text,
            "skill": asdict(SIGNATURES[kind]),
            "example": examples[kind],
            "scope": "19 target cells; two doorway cells remain empty; unknown cells are unverified"
            if kind == "wall"
            else "One bounded task, independent observation after each material action",
            "cells": [list(v) for v in wall_cells((0, 0, 0))] if kind == "wall" else [],
            "cell_coordinates": "Relative geometry preview only; a fresh visible anchor is still required",
            "exclusions": [
                "breaking blocks",
                "inventory changes",
                "protected structures",
                "unreviewed input",
            ],
            "future_corrections": self.selected["notes"],
            "executable": False,
            "missing": self.snapshot()["native_reason"],
        }
        self.reason = "Proposal saved for review. Setup records and requests cannot enable missing gameplay capabilities."

        if self.minecraft:
            try:
                native_request = text
                if kind in {"wall", "place"}:
                    preferred = re.search(
                        r"^Preferred building material: minecraft:(stone|bricks|oak_planks|cobblestone)$",
                        self.selected["notes"],
                        re.MULTILINE,
                    )
                    if preferred and not re.search(
                        r"\b(stone|bricks|oak|cobblestone)\b", words
                    ):
                        native_request += ". Use " + preferred[1].replace("_", " ")
                    if (
                        "Require marked protection for builds."
                        in self.selected["notes"]
                    ):
                        native_request += ". Leave the marked structure alone"
                parameters = self.minecraft.parameters(kind, native_request)
                self.plan.update(
                    kind=kind,
                    parameters=parameters,
                    executable=bool(self.minecraft.snapshot()["features"].get(kind)),
                    initial_pose=asdict(self.minecraft.last_pose)
                    if self.minecraft.last_pose
                    else None,
                )
                from smb3_agent.minecraft_native import TOTAL_LIMITS

                self.plan["total_budget"] = TOTAL_LIMITS[kind]
                if self.plan["initial_pose"] is None:
                    from smb3_agent.camera_practice import calibration_from

                    cal = calibration_from(
                        self.minecraft.camera.selected["calibration"]
                    )
                    self.plan["initial_pose"] = asdict(cal.samples[-1].after)
                if self.minecraft.scope:
                    self.plan["world_scope"] = asdict(self.minecraft.scope)
                    self.plan["cell_coordinates"] = (
                        "World coordinates from the visible selected ground block; fresh Start inspection required"
                    )
                    if kind == "wall":
                        self.plan["cells"] = [
                            list(v)
                            for v in wall_cells(
                                self.minecraft.scope.anchor, self.minecraft.scope.axis
                            )
                        ]
                self.plan["missing"] = (
                    ""
                    if self.plan["executable"]
                    else "This task remains unavailable until its focused native check passes."
                )
                self.reason = (
                    "Read the actual bounded scope, then Review and Start."
                    if self.plan["executable"]
                    else self.plan["missing"]
                )
            except ValueError as exc:
                self.plan = None
                self.reason = str(exc)
