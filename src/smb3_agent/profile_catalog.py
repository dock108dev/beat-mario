"""Explicit prototype registration through the existing catalog provider seam."""

from smb3_agent.companion_catalog import (
    AdapterCatalogEntry,
    AdapterRuntimeState,
    CatalogCapability,
    CatalogEvidence,
    CatalogGoal,
    CatalogObservation,
    CatalogProfile,
    CatalogSafety,
    CatalogScope,
)


class ProfileCatalogProvider:
    def __init__(self, profile, runtime=None):
        profile.validate()
        self.profile, self.runtime = profile, runtime

    def catalog_entry(self):
        p = self.profile
        rt = self._runtime()
        return AdapterCatalogEntry(
            adapter_id=p.game_id,
            game_id=p.game_id,
            display_name="OpenTTD" if p.game_id == "openttd" else p.game_id,
            description="Experimental bounded text-button skills with observed integer outcomes",
            adapter_version=p.version,
            implementation_status="experimental",
            availability="available"
            if rt and rt.release["confirmed"]
            else "setup_required",
            availability_reason="Verified disposable session and fresh profile review required",
            setup_state="prototype",
            observation=CatalogObservation(
                "selected-window-ocr",
                "Selected window and local OCR",
                "Model proposes; independent text and integer sensors constrain input and verify outcomes",
            ),
            capabilities=tuple(
                CatalogCapability(
                    mode,
                    mode.title(),
                    "setup_required",
                    "Prototype profile mode",
                    "Verify session and review exact task",
                )
                for mode in ("tell", "show", "do")
            )
            + tuple(
                CatalogCapability(
                    s.skill_id,
                    s.description,
                    "setup_required",
                    "Declared executable skill; consult exact attempt evidence",
                    "Requires practice qualification",
                )
                for s in p.skills
            ),
            goals=tuple(
                CatalogGoal(s.skill_id, s.description, s.description, (p.profile_id,))
                for s in p.skills
            ),
            profiles=(
                CatalogProfile(
                    p.profile_id,
                    p.profile_id,
                    "experimental",
                    "Versioned executable profile data",
                ),
            ),
            scopes=(
                CatalogScope(
                    "one-action",
                    "One verified action",
                    ("unknown target", "focus loss", "Stop", "outcome mismatch"),
                ),
            ),
            safety=CatalogSafety(
                "Player-owned unless exact current plan is reviewed and started",
                p.protected_actions,
                "Direct epoch revocation and neutralization",
                "Independent of inference",
                "Native HID state plus pressed ledger receipt",
            ),
            evidence=CatalogEvidence(
                "private-beta/pb1",
                ("fixture", "technical", "authoritative_gameplay"),
                "Installation and fixtures never qualify useful gameplay",
            ),
            standalone_surface="/openttd"
            if p.game_id == "openttd"
            else "scripts/pb1_feasibility.py",
            recovery_guidance="Reopen verified disposable checkpoint; refresh and review",
        )

    def _runtime(self):
        return self.runtime() if callable(self.runtime) else self.runtime

    def runtime_state(self):
        rt = self._runtime()
        return AdapterRuntimeState(
            self.profile.game_id,
            input_owner="agent" if rt and rt._authority else "player",
            active_mode="do" if rt and rt._authority else None,
            active_agent_input=bool(rt and rt._authority),
            active_do_authorization=bool(rt and rt._authority),
            handback_confirmed=not rt or rt.release["confirmed"],
            volatile_observation_present=bool(rt and rt.frame),
            volatile_authority_present=bool(rt and rt._authority),
        )

    def retain_for_switch(self):
        rt = self._runtime()
        return not rt or (not rt._authority and not rt._events.failed)

    def invalidate_volatile_state(self):
        rt = self._runtime()
        return not rt or rt.invalidate_volatile_state()


class MinecraftCatalogProvider:
    """Expose player setup without claiming the incomplete native skill path."""

    def __init__(self, camera=None, session=None):
        self.camera = camera
        self.session = session

    def catalog_entry(self):
        return AdapterCatalogEntry(
            adapter_id="minecraft",
            game_id="minecraft",
            display_name="Minecraft Java",
            description="Disposable Creative calibration and checked bounded tasks through Review/Start. Availability is shown in the workspace.",
            adapter_version="creative-player-session/v2",
            implementation_status="experimental",
            availability="setup_required",
            availability_reason="Choose the supported window, calibrate and review a currently checked task",
            setup_state="setup_required",
            observation=CatalogObservation(
                "visible-debug-hud",
                "Visible F3 pose and reachable target",
                "Unknown or occluded world cells cannot establish completion",
            ),
            capabilities=(
                CatalogCapability(
                    "tell",
                    "Explain supported work",
                    "available",
                    "No input",
                    "Open saved setup",
                ),
                CatalogCapability(
                    "show",
                    "Review a bounded proposal",
                    "available",
                    "Actual bounded scope; no input",
                    "Save a Minecraft profile",
                ),
                CatalogCapability(
                    "do",
                    "Creative gameplay",
                    "setup_required",
                    "Only checked gameplay families shown in the workspace can Start",
                    "Current calibration, fresh review and exclusive input required",
                ),
            ),
            goals=(
                CatalogGoal(
                    "creative-wall",
                    "Small wall with doorway",
                    "19 target cells; two doorway cells remain empty",
                    ("creative-practice",),
                ),
            ),
            profiles=(
                CatalogProfile(
                    "creative-practice",
                    "Disposable Creative practice",
                    "experimental",
                    "Supported vanilla HUD/settings template",
                ),
            ),
            scopes=(
                CatalogScope(
                    "bounded-creative",
                    "Checked tasks within reviewed scope",
                    ("Stop", "Take control", "edits", "unknown observations"),
                ),
            ),
            safety=CatalogSafety(
                "Player owns input until a checked task is reviewed and explicitly started",
                ("destruction", "survival", "protected-structures"),
                "Existing camera epoch revocation",
                "Direct controls independent of inference",
                "No restored authority",
            ),
            evidence=CatalogEvidence(
                "private-beta/minecraft",
                ("fixture", "technical", "authoritative_gameplay"),
                "The build review identifies exact focused native evidence; fixture checks alone never qualify gameplay",
            ),
            standalone_surface="/minecraft",
            recovery_guidance="Take control, restore disposable world, reconnect and review fresh state",
        )

    def runtime_state(self):
        if not self.camera:
            return AdapterRuntimeState("minecraft")
        state = self.session.snapshot() if self.session else self.camera.snapshot()
        return AdapterRuntimeState(
            "minecraft",
            input_owner="agent" if state["busy"] else "player",
            active_agent_input=state["busy"],
            active_do_authorization=state["busy"],
            handback_confirmed=not state["busy"]
            and not state.get("release_blocked", False),
            volatile_authority_present=bool(
                self.session.review if self.session else state["review"]
            ),
        )

    def retain_for_switch(self):
        return not (
            self.session.snapshot()["busy"]
            if self.session
            else self.camera and self.camera.snapshot()["busy"]
        )

    def invalidate_volatile_state(self):
        if self.session:
            self.session.revoke("Game selection changed", disconnect=True)
        elif self.camera:
            self.camera.revoke("Game selection changed")
        return self.retain_for_switch()
