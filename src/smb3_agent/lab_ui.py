from __future__ import annotations

import html
import json
import logging
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import webbrowser
from dataclasses import asdict, replace
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlparse

import yaml

from smb3_agent.companion_session import (
    AdapterIdentity,
    CompanionSession,
    Freshness,
    GoalIdentity,
    ModeCapability,
    Observation,
    ObservationSource,
    SafetyBoundary,
    SessionLifecycle,
)
from smb3_agent.companion_catalog import (
    AdapterCatalogEntry,
    AdapterRuntimeState,
    CatalogPreferenceStore,
    CatalogSession,
    CompanionCatalogError,
    build_default_catalog_registry,
)
from smb3_agent.experimental_adapters import (
    ExperimentalAdapterError,
    PROOF_LIMITS as EXPERIMENTAL_PROOF_LIMITS,
    default_install_root,
    inspect_contract,
    install_adapter,
    installation_status,
    load_contract as load_experimental_contract,
    run_conformance,
    scaffold_adapter,
    uninstall_adapter,
)
from smb3_agent.lab import (
    LabError,
    add_batch_notes_to_latest,
    build_issue_ledger_latest,
    propose_variants_from_latest,
    start_session,
    write_codex_task_latest,
)
from smb3_agent.live_observation import (
    ConnectionState,
    LiveObservationError,
    LiveObservationManager,
    LiveObservationSnapshot,
    observed_level_id,
)
from smb3_agent.learning import (
    CandidateLifecycle,
    HelpPolicy,
    LearningError,
    LearningSnapshot,
    LocalLearningStore,
    OwnerLocalPreference,
    compatibility,
    learning_advice,
    utc_now,
)
from smb3_agent.metrics import LocalMetricsStore, MetricsError, metric_definitions
from smb3_agent.mario_product import (
    MarioCatalogProvider,
    MarioProductError,
    MarioProductSessionManager,
    ProductSessionView,
    ProductStage,
    load_owner_pilot_manifest,
)
from smb3_agent.objective_profiles import (
    CoachingPolicy,
    ObjectiveProfileError,
    ObjectiveSessionManager,
    ObjectiveView,
)
from smb3_agent.paths import repository_path
from smb3_agent.goals import (
    ACTIVE_PRODUCT_GOAL_ID,
    GoalContract,
    GoalValidationError,
    load_goal_contract,
    load_product_goal_contracts,
    resolve_goal_path,
)
from smb3_agent.segments import load_segment_catalog
from smb3_agent.tell import (
    GroundedText,
    ObservedFact,
    SpoilerLevel,
    TellCard,
    TellRequest,
    TellValidationError,
    generate_tell_card,
)
from smb3_agent.show import (
    ShowError,
    ShowLifecycle,
    ShowRequest,
    ShowSession,
    ShowSessionManager,
    show_capability,
)
from smb3_agent.route_patch import (
    PATCH_ARTIFACTS_ROOT,
    RoutePatchError,
    RoutePatchResult,
    compare_route_patch,
    import_route_patch,
    patch_summary_for_issue,
    prepare_route_patch,
    preview_route_patch,
    promote_route_patch,
    review_route_patch,
    rollback_route_patch,
    validate_route_patch,
)
from smb3_agent.run_library import LocalRunLibrary, RunLibraryError
from smb3_agent.takeover import TakeoverError, supported_solutions
from smb3_agent.scenarios import (
    ScenarioError,
    final_campaign_readiness,
    load_campaign_entry_manifest,
    load_scenario_catalog,
    scenario_plan,
)
from smb3_agent.stardew_adapter import InputOwner, OperatorLifecycle, OperatorView, load_stardew_contract, render_stardew_operator


WORLD_1_LOCATION_PATH = repository_path("data/worlds/world_1_locations.yaml")
LAST_COMMAND_PATH = Path("artifacts/ui/last_command.yaml")
LOCAL_ASSET_DIR = repository_path("public/assets/local")
PUBLIC_ASSET_DIR = repository_path("public/assets")
ARTIFACT_DIR = Path("artifacts")
EXPERIMENTAL_SCAFFOLD_ROOT = Path("experimental-adapters")
MAX_FORM_BYTES = 64 * 1024
MAX_SERVED_FILE_BYTES = 50 * 1024 * 1024
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
PLAYER_WORKSPACE_JS = r'''(() => {
  const workspace = document.getElementById("active-workspace");
  if (!workspace) return;
  let updating = false;
  const detailKey = (details) =>
    details.dataset.testid || details.querySelector("summary")?.textContent?.trim() || "";
  const focusable = "a[href], button, input, select, textarea, summary, [tabindex]";
  const editingWorkspace = () => workspace.contains(document.activeElement) &&
    document.activeElement.matches("select, input, textarea");
  const focusKey = (element) => JSON.stringify([
    element.tagName, element.id, element.getAttribute("data-testid"),
    element.getAttribute("name"), element.getAttribute("type"),
    element.getAttribute("href"), element.closest("form")?.getAttribute("action"),
    element.closest("[id]")?.id, element.textContent.trim()
  ]);
  const showActionError = (message) => {
    let error = workspace.querySelector("[data-testid='live-action-error']");
    if (!error) {
      error = document.createElement("p");
      error.className = "callout action-error";
      error.dataset.testid = "live-action-error";
      error.setAttribute("role", "alert");
      workspace.prepend(error);
    }
    error.textContent = message;
  };
  async function refreshWorkspace(force = false) {
    if (updating) return;
    if (!force && editingWorkspace()) return;
    updating = true;
    try {
      const response = await fetch("/api/player-workspace", {cache: "no-store"});
      if (response.ok) {
        const html = await response.text();
        // Focus may move while the request is in flight. Preserve the current
        // editing session, not the element that was active before the fetch.
        if (!force && editingWorkspace()) return;
        const active = document.activeElement;
        const key = workspace.contains(active) && active.matches(focusable)
          ? focusKey(active) : null;
        const openDetails = new Set(
          Array.from(workspace.querySelectorAll("details[open]"), detailKey)
        );
        workspace.innerHTML = html;
        for (const details of workspace.querySelectorAll("details")) {
          if (openDetails.has(detailKey(details))) details.open = true;
        }
        if (key !== null) {
          const matches = Array.from(workspace.querySelectorAll(focusable)).filter(
            (element) => focusKey(element) === key && !element.disabled &&
              element.getClientRects().length > 0
          );
          // Never redirect focus to a different action or an ambiguous match.
          if (matches.length === 1) matches[0].focus({preventScroll: true});
        }
      }
    } finally {
      updating = false;
    }
  }
  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !workspace.contains(form)) return;
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        body: new URLSearchParams(new FormData(form)),
        redirect: "follow"
      });
      if (!response.ok) {
        const documentText = await response.text();
        const parsed = new DOMParser().parseFromString(documentText, "text/html");
        const message = parsed.querySelector("main p, body p")?.textContent?.trim();
        showActionError(message || `Start failed (${response.status}).`);
        return;
      }
      await refreshWorkspace(true);
      history.replaceState(null, "", form.action.includes("objective") ? "#objective" : "#live");
    } catch (_error) {
      showActionError("Start failed. Check that the local game service is running.");
    } finally {
      if (button) button.disabled = false;
    }
  });
  window.setInterval(() => refreshWorkspace(false), 750);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshWorkspace(true);
  });
})();
'''
POST_PATHS = frozenset(
    {
        "/notes",
        "/observation-action",
        "/issue-action",
        "/refresh",
        "/run",
        "/test",
        "/tell",
        "/tell-live",
        "/observe-start",
        "/observe-stop",
        "/takeover-start",
        "/takeover-reclaim",
        "/objective-config",
        "/objective-advice",
        "/objective-dismiss",
        "/objective-tell",
        "/show-start",
        "/show-stop",
        "/show-takeover",
        "/codex-task",
        "/patch-action",
        "/learning-review",
        "/learning-preferences",
        "/learning-preferences-reset",
        "/learning-export",
        "/setup-game-file",
        "/setup-pick-game-file",
        "/setup-choice",
        "/setup-retry",
        "/catalog-switch",
        "/catalog-preferences",
        "/adapter-scaffold",
        "/adapter-validate",
        "/adapter-inspect",
        "/adapter-conformance",
        "/adapter-install",
        "/adapter-remove",
    }
)
SAFE_INLINE_TYPES = {
    ".diff": "text/plain; charset=utf-8",
    ".gif": "image/gif",
    ".html": "text/plain; charset=utf-8",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".json": "application/json; charset=utf-8",
    ".log": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
    ".patch": "text/plain; charset=utf-8",
    ".png": "image/png",
    ".txt": "text/plain; charset=utf-8",
    ".webp": "image/webp",
    ".yaml": "text/plain; charset=utf-8",
    ".yml": "text/plain; charset=utf-8",
}
LOCAL_ASSET_TYPES = {
    suffix: content_type
    for suffix, content_type in SAFE_INLINE_TYPES.items()
    if content_type.startswith("image/")
}
FAVICON_ASSET_TYPES = {".svg": "image/svg+xml; charset=utf-8"}
LOGGER = logging.getLogger(__name__)
SUPPORTED_SPEEDS = ("1", "2", "4", "10", "25", "50", "100")
SUPPORTED_ATTEMPTS = ("1", "3", "5", "10")


class LabUiError(ValueError):
    pass


class LabUiForbidden(LabUiError):
    pass


class LabUiConflict(LabUiError):
    pass


class LabUiUnsupportedMediaType(LabUiError):
    pass


class _ThreadingHTTPServerV6(ThreadingHTTPServer):
    address_family = socket.AF_INET6

    def server_close(self) -> None:
        _shutdown_session_managers(self)
        super().server_close()


class _ThreadingHTTPServer(ThreadingHTTPServer):
    def server_close(self) -> None:
        _shutdown_session_managers(self)
        super().server_close()


def _shutdown_session_managers(server: ThreadingHTTPServer) -> None:
    manager = getattr(server, "show_manager", None)
    if isinstance(manager, ShowSessionManager):
        manager.shutdown()
    live_manager = getattr(server, "live_observation_manager", None)
    if isinstance(live_manager, LiveObservationManager):
        live_manager.shutdown()


def run_lab_ui_server(host: str = "127.0.0.1", port: int = 8765, *, open_browser: bool = False) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s level=%(levelname)s logger=%(name)s message=%(message)s",
    )
    server = _new_lab_ui_server(host, port)
    url = _lab_ui_url(host, server.server_port)
    print(f"lab_ui_url={url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("lab_ui_stopped=true")
    finally:
        server.server_close()


def _lab_ui_url(host: str, port: int) -> str:
    # IPv6 literals require brackets when used as the host portion of a URL.
    url_host = f"[{host}]" if ":" in host else host
    return f"http://{url_host}:{port}"


def _new_lab_ui_server(host: str, port: int) -> ThreadingHTTPServer:
    if host not in LOOPBACK_HOSTS:
        raise LabUiError(
            "Game Companion Lab may bind only to 127.0.0.1, ::1, or localhost"
        )
    server_class = _ThreadingHTTPServerV6 if host == "::1" else _ThreadingHTTPServer
    server = server_class((host, port), _Handler)
    setattr(server, "csrf_token", secrets.token_urlsafe(32))
    setattr(server, "action_lock", threading.Lock())
    setattr(server, "show_manager", ShowSessionManager())
    learning_store = LocalLearningStore()
    setattr(server, "live_observation_manager", LiveObservationManager(learning_store=learning_store))
    setattr(server, "objective_session_manager", ObjectiveSessionManager())
    setattr(server, "learning_store", learning_store)
    product_manager = MarioProductSessionManager()
    setattr(server, "product_session_manager", product_manager)
    mario_provider = MarioCatalogProvider(
        availability=lambda: _mario_catalog_availability(product_manager),
        runtime=lambda: _mario_catalog_runtime(server),
        retain=lambda: _retain_mario_catalog_state(server),
        invalidate=lambda: _invalidate_mario_catalog_state(server),
    )
    setattr(server, "mario_catalog_provider", mario_provider)
    registry = build_default_catalog_registry(mario_provider=mario_provider)
    setattr(server, "catalog_session", CatalogSession(registry, CatalogPreferenceStore()))
    return server


def _refresh_catalog_registry(server: ThreadingHTTPServer) -> None:
    mario_provider = getattr(server, "mario_catalog_provider", None)
    current = getattr(server, "catalog_session", None)
    if mario_provider is None or not isinstance(current, CatalogSession):
        raise RuntimeError("Game Companion server is missing catalog provider state")
    setattr(
        server,
        "catalog_session",
        CatalogSession(
            build_default_catalog_registry(mario_provider=mario_provider),
            current.store,
        ),
    )


def _experimental_source(adapter_id: str) -> Path:
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", adapter_id):
        raise ExperimentalAdapterError("invalid Experimental adapter id")
    root = os.path.realpath(os.fspath(EXPERIMENTAL_SCAFFOLD_ROOT))
    source = os.path.realpath(os.path.join(root, adapter_id))
    if not source.startswith(root.rstrip(os.sep) + os.sep):
        raise ExperimentalAdapterError("Experimental adapter source escapes the bounded root")
    return Path(source)


def _mario_catalog_availability(
    manager: MarioProductSessionManager,
) -> tuple[str, str, str]:
    setup = manager.first_use_state()
    if setup.launch_ready:
        return "available", "Mario setup is ready for a new visible session.", setup.status.value
    if setup.error:
        reason = setup.error
    elif not setup.game_file.supported_identity:
        reason = setup.game_file.reason
    elif not setup.emulator.available:
        reason = setup.emulator.reason
    else:
        reason = setup.input_reason
    return "setup_required", reason, setup.status.value


def _mario_catalog_runtime(server: ThreadingHTTPServer) -> AdapterRuntimeState:
    live = getattr(server, "live_observation_manager").snapshot()
    show = getattr(server, "show_manager").snapshot()
    show_active = bool(
        show
        and show.lifecycle
        in {ShowLifecycle.STARTING, ShowLifecycle.ACTIVE, ShowLifecycle.STOP_REQUESTED}
    )
    owner = live.control_owner or "player"
    neutralizing = live.control_state == "neutralizing" or not live.input_neutralized
    agent_active = owner == "agent"
    product_failure = getattr(server, "product_session_manager").view(
        live,
        show_active=show_active,
    ).current_failure
    return AdapterRuntimeState(
        adapter_id="smb3",
        input_owner=owner,
        active_mode="show" if show_active else "do" if agent_active else "observe" if live.observation_active else None,
        active_agent_input=agent_active,
        active_show=show_active,
        active_do_authorization=agent_active or live.control_state in {"authorized", "active"},
        pending_reclaim=neutralizing,
        pending_neutralization=neutralizing,
        handback_confirmed=not neutralizing and owner == "player" and live.input_neutralized,
        ownership_ambiguous=owner not in {"player", "agent"},
        incomplete_failure_retention=bool(
            product_failure and not product_failure.evidence_retained
        ),
        unsafe_save_transition=False,
        continuity_known=live.state not in {ConnectionState.DISCONNECTED, ConnectionState.UNKNOWN}
        or live.session_id is None,
        volatile_observation_present=live.session_id is not None,
        volatile_authority_present=agent_active or neutralizing,
    )


def _retain_mario_catalog_state(server: ThreadingHTTPServer) -> bool:
    live = getattr(server, "live_observation_manager").snapshot()
    show = getattr(server, "show_manager").snapshot()
    if live.observation_active:
        return False
    if live.session_id is not None and (
        live.artifact_dir is None or not live.artifact_dir.is_dir()
    ):
        return False
    if show is not None and show.lifecycle in {
        ShowLifecycle.STARTING,
        ShowLifecycle.ACTIVE,
        ShowLifecycle.STOP_REQUESTED,
    }:
        return False
    if show is not None and show.artifacts_dir is not None and not show.artifacts_dir.is_dir():
        return False
    failure = getattr(server, "product_session_manager").view(
        live,
        show_active=False,
    ).current_failure
    return failure is None or failure.evidence_retained


def _invalidate_mario_catalog_state(server: ThreadingHTTPServer) -> bool:
    live_manager = getattr(server, "live_observation_manager")
    show_manager = getattr(server, "show_manager")
    if not live_manager.invalidate_volatile_state():
        return False
    if not show_manager.invalidate_volatile_state():
        return False
    getattr(server, "objective_session_manager").invalidate_volatile_state()
    product = getattr(server, "product_session_manager")
    product.clear_error()
    product.mark_stage(ProductStage.IDLE)
    return True


class _Handler(BaseHTTPRequestHandler):
    server_version = "SMB3ControlPanel/0.2"

    def do_GET(self) -> None:
        try:
            self._validate_host()
            self._handle_get()
        except (
            GoalValidationError,
            LabError,
            LabUiError,
            RoutePatchError,
            TellValidationError,
            ShowError,
            LiveObservationError,
            ObjectiveProfileError,
            LearningError,
            MarioProductError,
            TakeoverError,
            CompanionCatalogError,
            ExperimentalAdapterError,
        ) as exc:
            self._send_request_failure(exc)
        except Exception:
            self._send_internal_error()

    def _handle_get(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._send_html(
                render_combined_catalog(
                    self._catalog_session(),
                    csrf_token=self._csrf_token(),
                )
            )
            return
        if path == "/mario":
            query = parse_qs(parsed.query)
            goal_id = query.get("goal", [ACTIVE_PRODUCT_GOAL_ID])[0]
            if goal_id not in _product_goal_ids():
                self._send_html(
                    render_error(f"Unsupported Game Companion goal: {goal_id}"),
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            live_snapshot = self._live_observation_manager().snapshot()
            show_session = self._show_manager().snapshot()
            objective_view = self._objective_session_manager().view(live_snapshot)
            learning_snapshot = self._learning_store().snapshot()
            product_view = self._product_view(
                live_snapshot,
                show_session=show_session,
                objective_view=objective_view,
                learning_snapshot=learning_snapshot,
            )
            self._send_html(
                render_companion_ui(
                    default_companion_session(
                        goal_id=goal_id,
                        live_snapshot=live_snapshot,
                    ),
                    csrf_token=self._csrf_token(),
                    show_session=show_session,
                    show_request=_default_show_request(goal_id),
                    live_snapshot=live_snapshot,
                    objective_view=objective_view,
                    learning_snapshot=learning_snapshot,
                    product_view=product_view,
                )
            )
            return
        if path == "/stardew":
            self._send_html(render_safe_stardew_workspace())
            return
        if path == "/lab":
            query = parse_qs(parsed.query)
            goal_id = query.get("goal", [ACTIVE_PRODUCT_GOAL_ID])[0]
            if goal_id not in _product_goal_ids():
                self._send_html(
                    render_error(f"Unsupported Game Companion Lab goal: {goal_id}"),
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            lab_snapshot = self._live_observation_manager().snapshot()
            lab_show_session = self._show_manager().snapshot()
            lab_objective = self._objective_session_manager().view(lab_snapshot)
            lab_learning = self._learning_store().snapshot()
            self._send_html(
                render_lab_ui(
                    goal_id=goal_id,
                    selected_location_id=query.get("location", [""])[0] or None,
                    selected_note_id=query.get("note", [""])[0] or None,
                    selected_issue_id=query.get("issue", [""])[0] or None,
                    selected_mode=query.get("mode", [""])[0] or None,
                    csrf_token=self._csrf_token(),
                    learning_snapshot=lab_learning,
                    product_view=self._product_view(
                        lab_snapshot,
                        show_session=lab_show_session,
                        objective_view=lab_objective,
                        learning_snapshot=lab_learning,
                    ),
                    live_snapshot=lab_snapshot,
                )
            )
            return
        if path == "/onboarding":
            self._send_html(
                render_experimental_onboarding(
                    csrf_token=self._csrf_token(),
                    message=getattr(self.server, "onboarding_message", None),
                )
            )
            return
        if path == "/api/summary":
            query = parse_qs(parsed.query)
            goal_id = query.get("goal", [ACTIVE_PRODUCT_GOAL_ID])[0]
            if goal_id not in _product_goal_ids():
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            self._send_json(build_control_panel_summary(goal_id))
            return
        if path == "/api/player-workspace":
            snapshot = self._live_observation_manager().snapshot()
            show_session = self._show_manager().snapshot()
            objective_view = self._objective_session_manager().view(snapshot)
            learning_snapshot = self._learning_store().snapshot()
            self._send_html(
                _active_workspace(
                    default_companion_session(live_snapshot=snapshot),
                    snapshot,
                    objective_view,
                    csrf_token=self._csrf_token(),
                    learning_snapshot=learning_snapshot,
                    show_session=show_session,
                    show_request=_default_show_request(ACTIVE_PRODUCT_GOAL_ID),
                    product_view=self._product_view(
                        snapshot,
                        show_session=show_session,
                        objective_view=objective_view,
                        learning_snapshot=learning_snapshot,
                    ),
                )
            )
            return
        if path == "/assets/player-workspace.js":
            self._send_javascript(PLAYER_WORKSPACE_JS)
            return
        if path in {"/favicon.ico", "/assets/favicon.svg"}:
            self._send_workspace_file(
                PUBLIC_ASSET_DIR,
                "favicon.svg",
                FAVICON_ASSET_TYPES,
            )
            return
        if path.startswith("/assets/local/"):
            self._send_local_asset(path.removeprefix("/assets/local/"))
            return
        if path.startswith("/artifacts/"):
            self._send_artifact(path.removeprefix("/artifacts/"))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            self._validate_host()
            self._handle_post()
        except (
            GoalValidationError,
            LabError,
            LabUiError,
            RoutePatchError,
            TellValidationError,
            ShowError,
            LiveObservationError,
            ObjectiveProfileError,
            LearningError,
            MarioProductError,
            TakeoverError,
            CompanionCatalogError,
            ExperimentalAdapterError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ) as exc:
            self._send_request_failure(exc)
        except Exception:
            self._send_internal_error()

    def _handle_post(self) -> None:
        path = urlparse(self.path).path
        if path not in POST_PATHS:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = self._read_form()
        self._validate_csrf(data)
        action_lock = getattr(self.server, "action_lock", None)
        if not isinstance(action_lock, type(threading.Lock())):
            raise RuntimeError("Game Companion Lab server is missing its action lock")
        if not action_lock.acquire(blocking=False):
            raise LabUiConflict("Another Game Companion Lab action is already running")
        try:
            try:
                if path == "/catalog-switch":
                    event = self._catalog_session().switch(_single(data, "adapter_id"))
                    target = self._catalog_session().registry.entry(event.to_adapter_id)
                    self._redirect(target.standalone_surface)
                    return
                if path == "/catalog-preferences":
                    self._catalog_session().update_display_preferences(
                        compact_catalog=_single(data, "compact_catalog", default="") == "true",
                        catalog_expanded=_single(data, "catalog_expanded", default="") == "true",
                    )
                    self._redirect("/")
                    return
                if path.startswith("/adapter-"):
                    adapter_id = _single(data, "adapter_id")
                    source = _experimental_source(adapter_id)
                    if path == "/adapter-scaffold":
                        display_name = _single(data, "display_name")
                        result: object = {"scaffold": str(scaffold_adapter(EXPERIMENTAL_SCAFFOLD_ROOT, adapter_id, display_name)), "state": "scaffolded"}
                    elif path == "/adapter-validate":
                        contract = load_experimental_contract(source / "adapter.yaml")
                        result = {"valid": True, "adapter_id": contract["identity"]["adapter_id"], "schema_version": contract["schema_version"], "state": "declared"}
                    elif path == "/adapter-inspect":
                        result = asdict(inspect_contract(source / "adapter.yaml"))
                    elif path == "/adapter-conformance":
                        result = run_conformance(source).to_dict()
                    elif path == "/adapter-install":
                        result = {"installed": str(install_adapter(source, default_install_root())), "state": "installed", "status": "Experimental"}
                        _refresh_catalog_registry(self.server)
                    elif path == "/adapter-remove":
                        result = uninstall_adapter(default_install_root(), adapter_id)
                        _refresh_catalog_registry(self.server)
                    else:
                        raise LabUiError("Unknown Experimental adapter action")
                    setattr(self.server, "onboarding_message", result)
                    self._redirect("/onboarding")
                    return
                if path == "/notes":
                    notes = _notes_from_form(data)
                    if notes:
                        add_batch_notes_to_latest(notes)
                    build_issue_ledger_latest()
                    propose_variants_from_latest()
                    self._redirect(_location_url(_single(data, "return_location", default="")))
                    return
                if path == "/tell":
                    self._product_session_manager().mark_stage(ProductStage.TELL_COACHING)
                    live_snapshot = self._live_observation_manager().snapshot()
                    goal_id = _single(data, "goal_id", default=ACTIVE_PRODUCT_GOAL_ID)
                    try:
                        session, card = _player_tell_from_form(data)
                        if live_snapshot.observation_active:
                            session = replace(
                                session,
                                adapter=replace(
                                    session.adapter,
                                    status="You are playing · observing only",
                                ),
                            )
                        self._send_html(
                            render_companion_ui(
                                session,
                                tell_card=card,
                                csrf_token=self._csrf_token(),
                                selected_checkpoint=session.observation.checkpoint_id,
                                selected_spoiler=card.spoiler_level,
                                show_session=self._show_manager().snapshot(),
                                show_request=_default_show_request(goal_id),
                                live_snapshot=live_snapshot,
                            )
                        )
                    except TellValidationError as exc:
                        if goal_id not in _product_goal_ids():
                            goal_id = ACTIVE_PRODUCT_GOAL_ID
                        self._send_html(
                            render_companion_ui(
                                default_companion_session(
                                    goal_id,
                                    live_snapshot=live_snapshot,
                                ),
                                csrf_token=self._csrf_token(),
                                tell_unavailable_reason=str(exc),
                                selected_checkpoint=_single(data, "checkpoint_id", default=""),
                                selected_spoiler=_spoiler_from_value(
                                    _single(data, "spoiler_level", default="guided")
                                ),
                                show_session=self._show_manager().snapshot(),
                                show_request=_default_show_request(goal_id),
                                live_snapshot=live_snapshot,
                            ),
                            status=HTTPStatus.BAD_REQUEST,
                        )
                    return
                if path == "/tell-live":
                    self._product_session_manager().mark_stage(ProductStage.TELL_COACHING)
                    goal_id = _single(data, "goal_id", default=ACTIVE_PRODUCT_GOAL_ID)
                    snapshot = self._live_observation_manager().snapshot()
                    try:
                        session, card = _live_tell(snapshot, goal_id, data)
                    except TellValidationError as exc:
                        self._send_html(
                            render_companion_ui(
                                default_companion_session(
                                    goal_id,
                                    live_snapshot=snapshot,
                                ),
                                csrf_token=self._csrf_token(),
                                tell_unavailable_reason=str(exc),
                                selected_checkpoint=snapshot.checkpoint_id,
                                selected_spoiler=_spoiler_from_value(
                                    _single(data, "spoiler_level", default="guided")
                                ),
                                show_session=self._show_manager().snapshot(),
                                show_request=_default_show_request(goal_id),
                                live_snapshot=snapshot,
                            ),
                            status=HTTPStatus.BAD_REQUEST,
                        )
                        return
                    self._send_html(
                        render_companion_ui(
                            session,
                            tell_card=card,
                            csrf_token=self._csrf_token(),
                            selected_checkpoint=snapshot.checkpoint_id,
                            selected_spoiler=card.spoiler_level,
                            show_session=self._show_manager().snapshot(),
                            show_request=_default_show_request(goal_id),
                            live_snapshot=snapshot,
                        )
                    )
                    return
                if path == "/observe-start":
                    product = self._product_session_manager()
                    game_path = product.first_use_state().game_file.path
                    if game_path is None:
                        product.mark_failure("missing_game_file")
                        raise LiveObservationError(
                            "No local game file is configured."
                        )
                    product.mark_starting()
                    try:
                        started = self._live_observation_manager().start(
                            game_path,
                            allow_takeover=_single(
                                data, "allow_takeover", default=""
                            )
                            == "true",
                        )
                    except LiveObservationError as exc:
                        failure_id = "duplicate_session" if "already" in str(exc).lower() else "launch_failure"
                        product.mark_failure(failure_id, detail=str(exc))
                        raise
                    product.mark_started(started.session_id)
                    self._redirect("/#live")
                    return
                if path == "/observe-stop":
                    snapshot = self._live_observation_manager().stop()
                    self._objective_session_manager().finalize(snapshot)
                    self._product_session_manager().record(
                        "observation_stopped",
                        ProductStage.STOPPED,
                        "Observation stopped; the Mario process may still be running under player control.",
                        session_id=snapshot.session_id,
                        input_owner=snapshot.control_owner,
                        evidence_status="retained",
                    )
                    self._redirect("/#live")
                    return
                if path == "/takeover-start":
                    manager = self._live_observation_manager()
                    self._product_session_manager().mark_stage(ProductStage.DO_PREFLIGHT)
                    solution_id = _single(data, "solution_id")
                    solution = next(
                        (
                            item
                            for item in supported_solutions()
                            if item.solution_id == solution_id
                        ),
                        None,
                    )
                    if solution is None:
                        raise LiveObservationError("Unsupported executable solution")
                    try:
                        timeout_seconds = int(
                            _single(data, "timeout_seconds", default="120")
                        )
                    except ValueError as exc:
                        raise LiveObservationError("Takeover timeout must be an integer") from exc
                    try:
                        manager.begin_takeover(
                            solution,
                            profile_id=solution.profile_id,
                            profile_version=1,
                            scope=_single(data, "scope"),
                            stop_condition=_single(data, "stop_condition"),
                            timeout_seconds=timeout_seconds,
                            protected_resources=tuple(data.get("protected_resources", ())),
                            protected_decisions=tuple(data.get("protected_decisions", ())),
                        )
                    except (LiveObservationError, TakeoverError) as exc:
                        reason = str(exc).lower()
                        failure_id = (
                            "process_lost" if "process" in reason
                            else "stale_observation" if "fresh" in reason or "stale" in reason
                            else "protected_resource_conflict" if "protected" in reason
                            else "candidate_not_executable" if "executable" in reason
                            else "authorization_mismatch"
                        )
                        self._product_session_manager().mark_failure(
                            failure_id, detail=str(exc)
                        )
                        self._redirect("/#live")
                        return
                    self._product_session_manager().mark_stage(ProductStage.DO_AUTHORIZED)
                    self._redirect("/#live")
                    return
                if path == "/takeover-reclaim":
                    snapshot = self._live_observation_manager().snapshot()
                    try:
                        self._live_observation_manager().reclaim_takeover()
                    except (LiveObservationError, TakeoverError) as exc:
                        self._product_session_manager().mark_failure(
                            "handback_failure", detail=str(exc)
                        )
                        self._redirect("/#live")
                        return
                    self._product_session_manager().record(
                        "reclaim_requested",
                        ProductStage.RECLAIM,
                        "Take Control Now requested; neutral input and handback confirmation are pending.",
                        session_id=snapshot.session_id,
                        input_owner="agent",
                        evidence_status="retained",
                    )
                    self._redirect("/#live")
                    return
                if path == "/setup-game-file":
                    self._product_session_manager().select_game_file(
                        Path(_single(data, "game_file_path"))
                    )
                    self._redirect("/#setup")
                    return
                if path == "/setup-pick-game-file":
                    if sys.platform != "darwin":
                        raise MarioProductError(
                            "The native file picker is available on macOS; enter the local path instead"
                        )
                    selection = subprocess.run(
                        [
                            "osascript",
                            "-e",
                            'POSIX path of (choose file with prompt "Choose your local Mario game file")',
                        ],
                        capture_output=True,
                        text=True,
                        timeout=300,
                        check=False,
                    )
                    if selection.returncode != 0:
                        self._product_session_manager().mark_failure(
                            "configuration_error",
                            detail="Game-file selection was cancelled or could not be opened.",
                        )
                        self._redirect("/#setup")
                        return
                    self._product_session_manager().select_game_file(
                        Path(selection.stdout.strip())
                    )
                    self._redirect("/#setup")
                    return
                if path == "/setup-choice":
                    product = self._product_session_manager()
                    session_kind = _single(data, "session_kind")
                    try:
                        product.confirm_input_ready(
                            ready=_single(data, "input_ready", default="") == "true",
                            session_kind=session_kind,
                        )
                    except MarioProductError as exc:
                        product.mark_failure("configuration_error", detail=str(exc))
                        self._redirect("/#setup")
                        return
                    setup = product.first_use_state()
                    if not setup.launch_ready or setup.game_file.path is None:
                        raise MarioProductError("Mario setup is not ready to start")
                    product.mark_starting()
                    try:
                        started = self._live_observation_manager().start(
                            setup.game_file.path,
                            allow_takeover=session_kind == "takeover_capable",
                        )
                    except LiveObservationError as exc:
                        failure_id = "duplicate_session" if "already" in str(exc).lower() else "launch_failure"
                        product.mark_failure(failure_id, detail=str(exc))
                        self._redirect("/#setup")
                        return
                    product.mark_started(started.session_id)
                    self._redirect("/#live")
                    return
                if path == "/setup-retry":
                    self._product_session_manager().clear_error()
                    self._redirect("/#setup")
                    return
                if path == "/objective-config":
                    self._product_session_manager().mark_stage(ProductStage.TELL_COACHING)
                    snapshot = self._live_observation_manager().snapshot()
                    self._objective_session_manager().configure(
                        snapshot,
                        _single(data, "profile_id"),
                        _single(data, "coaching_policy", default="quiet"),
                        _single(data, "reference_id", default="") or None,
                    )
                    self._redirect("/#objective")
                    return
                if path == "/objective-advice":
                    self._product_session_manager().mark_stage(ProductStage.TELL_COACHING)
                    self._objective_session_manager().request_advice(
                        self._live_observation_manager().snapshot()
                    )
                    self._redirect("/#objective")
                    return
                if path == "/objective-dismiss":
                    self._objective_session_manager().dismiss(
                        self._live_observation_manager().snapshot()
                    )
                    self._redirect("/#objective")
                    return
                if path == "/objective-tell":
                    self._product_session_manager().mark_stage(ProductStage.TELL_COACHING)
                    self._objective_session_manager().ask(
                        self._live_observation_manager().snapshot(),
                        _single(data, "objective_question"),
                        _single(data, "objective_spoiler", default="guided"),
                    )
                    self._redirect("/#objective")
                    return
                if path == "/learning-review":
                    self._product_session_manager().mark_stage(ProductStage.HISTORICAL_REVIEW)
                    decision = _single(data, "decision")
                    if decision not in {"approve", "reject"}:
                        raise LearningError("candidate review decision must be approve or reject")
                    self._learning_store().review(
                        _single(data, "candidate_id"),
                        approve=decision == "approve",
                        reason=_single(data, "reason"),
                        reviewer="local-owner",
                    )
                    self._redirect("/#learning")
                    return
                if path == "/learning-preferences":
                    self._product_session_manager().mark_stage(ProductStage.HISTORICAL_REVIEW)
                    self._learning_store().set_preference(
                        OwnerLocalPreference(
                            game_id=_single(data, "game_id", default="smb3"),
                            objective_id=_single(data, "objective_id"),
                            help_policy=HelpPolicy(_single(data, "help_policy")),
                            preferred_solution_style=_single(
                                data, "preferred_solution_style", default="balanced"
                            ),
                            risk_tolerance=_single(data, "risk_tolerance", default="moderate"),
                            resource_preservation=tuple(data.get("resource_preservation", ())),
                            spoiler_level=_single(data, "spoiler_level", default="guided"),
                            dismissed_suggestion_types=tuple(
                                data.get("dismissed_suggestion_types", ())
                            ),
                            confirmed_helpful_suggestion_types=tuple(
                                data.get("confirmed_helpful_suggestion_types", ())
                            ),
                            preferred_comparison_target=_single(
                                data, "preferred_comparison_target", default="player_best"
                            ),
                            updated_at=utc_now(),
                        )
                    )
                    self._redirect("/#learning")
                    return
                if path == "/learning-preferences-reset":
                    self._product_session_manager().mark_stage(ProductStage.HISTORICAL_REVIEW)
                    self._learning_store().reset_preference(
                        _single(data, "game_id", default="smb3"),
                        _single(data, "objective_id"),
                    )
                    self._redirect("/#learning")
                    return
                if path == "/learning-export":
                    self._product_session_manager().mark_stage(ProductStage.HISTORICAL_REVIEW)
                    self._learning_store().export_review_packet(
                        _single(data, "candidate_id")
                    )
                    self._redirect("/#learning")
                    return
                if path == "/show-start":
                    self._product_session_manager().mark_stage(ProductStage.SHOW_ACTIVE_SEPARATELY)
                    goal_id = _single(data, "goal_id", default=ACTIVE_PRODUCT_GOAL_ID)
                    request = _default_show_request(goal_id)
                    capability = show_capability(request)
                    if request is None or not capability.available or capability.definition is None:
                        raise ShowError(capability.reason)
                    self._show_manager().start(request, capability.definition)
                    self._redirect(f"/?{urlencode({'goal': goal_id})}")
                    return
                if path in {"/show-stop", "/show-takeover"}:
                    self._show_manager().stop(takeover=path == "/show-takeover")
                    self._product_session_manager().mark_stage(ProductStage.PLAYER_OBSERVING)
                    self._redirect("/")
                    return
                if path == "/observation-action":
                    location_id = _single(data, "return_location", default="")
                    _update_observation_latest(
                        _single(data, "note_id"),
                        _single(data, "action"),
                        data,
                    )
                    self._redirect(_location_url(location_id))
                    return
                if path == "/issue-action":
                    location_id = _single(data, "return_location", default="")
                    _update_issue_latest(
                        _single(data, "issue_id"),
                        _single(data, "action"),
                    )
                    self._redirect(_location_url(location_id))
                    return
                if path == "/refresh":
                    build_issue_ledger_latest()
                    propose_variants_from_latest()
                    _write_last_command(
                        "refresh",
                        ("python", "-m", "smb3_agent", "lab", "issues", "latest"),
                        0,
                        "review artifacts refreshed",
                        "",
                    )
                    self._redirect("/")
                    return
                if path == "/run":
                    result = _run_world_1_from_form(data)
                    _write_last_command(
                        "run_world_1",
                        (
                            "python",
                            "-m",
                            "smb3_agent",
                            "lab",
                            "start",
                            result["command"],
                            "--attempts",
                            str(result["attempts"]),
                        ),
                        0,
                        result["summary"],
                        "",
                    )
                    self._redirect("/")
                    return
                if path == "/test":
                    action = _single(data, "action")
                    command = _test_command(action)
                    completed = _run_command_capture(action, command)
                    _write_last_command(
                        action,
                        command,
                        completed.returncode,
                        completed.stdout,
                        completed.stderr,
                    )
                    self._redirect("/")
                    return
                if path == "/codex-task":
                    issue_id = _issue_id_from_form(data)
                    write_codex_task_latest(issue_id)
                    self._redirect("/")
                    return
                result = run_patch_ui_action(data, repo_root=Path.cwd())
                _write_last_command(
                    f"patch_{_single(data, 'action')}",
                    ("route-lab-backend", result.patch_id, _single(data, "action")),
                    0,
                    result.to_text(),
                    "",
                )
                self._redirect(
                    _location_url(
                        _single(data, "return_location", default=""),
                        mode="issue",
                        issue_id=_single(data, "issue_id", default=""),
                        goal_id=_single(data, "return_goal", default=ACTIVE_PRODUCT_GOAL_ID),
                    )
                )
            except (
                GoalValidationError,
                LabError,
                LabUiError,
                RoutePatchError,
                TellValidationError,
                ShowError,
                LiveObservationError,
                TakeoverError,
                FileNotFoundError,
                subprocess.TimeoutExpired,
            ) as exc:
                self._send_request_failure(exc)
        finally:
            action_lock.release()

    def log_message(self, format: str, *args: object) -> None:
        LOGGER.info(
            "route_lab_access client=%s message=%s",
            self.client_address[0],
            format % args,
        )

    def end_headers(self) -> None:
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; base-uri 'none'; form-action 'self'; "
            "frame-ancestors 'none'; img-src 'self' data:; object-src 'none'; "
            "connect-src 'self'; script-src 'self'; style-src 'unsafe-inline'",
        )
        self.send_header("Cache-Control", "no-store")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), microphone=()")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        super().end_headers()

    def _read_form(self) -> dict[str, list[str]]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise LabUiError("Invalid Content-Length header") from exc
        if length < 0:
            raise LabUiError("Content-Length cannot be negative")
        if length > MAX_FORM_BYTES:
            raise LabUiError(f"Form body exceeds the {MAX_FORM_BYTES}-byte limit")
        if self.headers.get_content_type() != "application/x-www-form-urlencoded":
            raise LabUiUnsupportedMediaType(
                "Game Companion Lab forms require application/x-www-form-urlencoded"
            )
        payload = self.rfile.read(length)
        if len(payload) != length:
            raise LabUiError("Incomplete form body")
        try:
            body = payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise LabUiError("Form body must be valid UTF-8") from exc
        return parse_qs(body, keep_blank_values=True)

    def _validate_host(self) -> None:
        raw_host = self.headers.get("Host", "")
        try:
            hostname = urlparse(f"//{raw_host}").hostname
        except ValueError as exc:
            raise LabUiForbidden("Invalid Game Companion Lab Host header") from exc
        if hostname not in LOOPBACK_HOSTS:
            raise LabUiForbidden("Game Companion Lab requests require a loopback Host header")

    def _csrf_token(self) -> str:
        token = getattr(self.server, "csrf_token", None)
        if not isinstance(token, str) or not token:
            raise RuntimeError("Game Companion Lab server is missing its CSRF token")
        return token

    def _validate_csrf(self, data: dict[str, list[str]]) -> None:
        supplied = _single(data, "csrf_token", default="")
        if not supplied or not secrets.compare_digest(supplied, self._csrf_token()):
            raise LabUiForbidden("Invalid or missing Game Companion Lab CSRF token")

    def _show_manager(self) -> ShowSessionManager:
        manager = getattr(self.server, "show_manager", None)
        if not isinstance(manager, ShowSessionManager):
            raise RuntimeError("Game Companion server is missing its Show manager")
        return manager

    def _live_observation_manager(self) -> LiveObservationManager:
        manager = getattr(self.server, "live_observation_manager", None)
        if not isinstance(manager, LiveObservationManager):
            raise RuntimeError("Game Companion server is missing its live observation manager")
        return manager

    def _objective_session_manager(self) -> ObjectiveSessionManager:
        manager = getattr(self.server, "objective_session_manager", None)
        if not isinstance(manager, ObjectiveSessionManager):
            raise RuntimeError("Game Companion server is missing its objective session manager")
        return manager

    def _learning_store(self) -> LocalLearningStore:
        store = getattr(self.server, "learning_store", None)
        if not isinstance(store, LocalLearningStore):
            raise RuntimeError("Game Companion server is missing its local learning store")
        return store

    def _product_session_manager(self) -> MarioProductSessionManager:
        manager = getattr(self.server, "product_session_manager", None)
        if not isinstance(manager, MarioProductSessionManager):
            raise RuntimeError("Game Companion server is missing its Mario product manager")
        return manager

    def _catalog_session(self) -> CatalogSession:
        session = getattr(self.server, "catalog_session", None)
        if not isinstance(session, CatalogSession):
            raise RuntimeError("Game Companion server is missing its catalog session")
        return session

    def _product_view(
        self,
        snapshot: LiveObservationSnapshot,
        *,
        show_session: ShowSession | None,
        objective_view: ObjectiveView,
        learning_snapshot: LearningSnapshot,
    ) -> ProductSessionView:
        show_active = bool(
            show_session
            and show_session.lifecycle
            in {ShowLifecycle.STARTING, ShowLifecycle.ACTIVE, ShowLifecycle.STOP_REQUESTED}
        )
        return self._product_session_manager().view(
            snapshot,
            show_active=show_active,
            has_compatible_profile=objective_view.selected is not None,
            has_accepted_reference=objective_view.reference is not None,
            candidate_review_available=any(
                item.lifecycle is CandidateLifecycle.REVIEW_REQUIRED
                for item in learning_snapshot.candidates
            ),
        )

    def _send_request_failure(self, exc: Exception) -> None:
        status = (
            HTTPStatus.GATEWAY_TIMEOUT
            if isinstance(exc, subprocess.TimeoutExpired)
            else HTTPStatus.UNSUPPORTED_MEDIA_TYPE
            if isinstance(exc, LabUiUnsupportedMediaType)
            else HTTPStatus.CONFLICT
            if isinstance(exc, LabUiConflict)
            else HTTPStatus.FORBIDDEN
            if isinstance(exc, LabUiForbidden)
            else HTTPStatus.NOT_FOUND
            if isinstance(exc, FileNotFoundError)
            else HTTPStatus.BAD_REQUEST
        )
        LOGGER.warning(
            "route_lab_request_failed method=%s path=%s status=%d error_type=%s detail=%s",
            self.command,
            self.path,
            status,
            type(exc).__name__,
            exc,
        )
        self._send_html(render_error(str(exc)), status=status)

    def _send_internal_error(self) -> None:
        LOGGER.exception(
            "route_lab_request_crashed method=%s path=%s",
            self.command,
            self.path,
        )
        self._send_html(
            render_error(
                "Unexpected Game Companion Lab failure. "
                "Check the server log for the traceback."
            ),
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    def _send_html(self, body: str, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, data: dict[str, object]) -> None:
        encoded = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_javascript(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_local_asset(self, asset_path: str) -> None:
        self._send_workspace_file(LOCAL_ASSET_DIR, asset_path, LOCAL_ASSET_TYPES)

    def _send_artifact(self, artifact_path: str) -> None:
        self._send_workspace_file(ARTIFACT_DIR, artifact_path, SAFE_INLINE_TYPES)

    def _send_workspace_file(
        self,
        root: Path,
        requested_path: str,
        allowed_types: dict[str, str],
    ) -> None:
        try:
            relative = Path(unquote(requested_path))
            if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
                raise ValueError
            full_path = (root / relative).resolve()
            full_path.relative_to(root.resolve())
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not full_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = allowed_types.get(full_path.suffix.lower())
        if content_type is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_size = full_path.stat().st_size
        if file_size > MAX_SERVED_FILE_BYTES:
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        content = full_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()


def _configured_game_path() -> Path | None:
    identity = MarioProductSessionManager().detect_game_file()
    return identity.path if identity.supported_identity else None


def _default_show_request(goal_id: str) -> ShowRequest | None:
    if goal_id not in _product_goal_ids():
        return None
    contract = load_goal_contract(resolve_goal_path(goal_id))
    if "world_1_1_clear" not in contract.segments:
        return None
    game_path = _configured_game_path()
    if game_path is None:
        return None
    return ShowRequest(
        adapter_id="smb3",
        game_id=contract.game,
        goal_id=goal_id,
        segment_id="world_1_1_clear",
        observation=Observation(
            checkpoint="Fresh separate process at World 1-1",
            checkpoint_id="world_1_1_clear",
            observed_at=datetime.now(timezone.utc),
            freshness=Freshness.FRESH,
            confidence=1.0,
            evidence_references=("adapter-verifiable:fresh-process-power-on",),
            source=ObservationSource.ADAPTER,
            game_id=contract.game,
        ),
        game_path=game_path,
        trusted_starting_state="Fresh power-on; adapter must observe attempt_1_fresh_start",
        demonstration_stop_event="show_input_stopped",
        recovery_boundary="One attempt only; stop and retain evidence on mismatch, death, timeout, or request.",
        protected_decisions=(
            "Player's active game session",
            "Player saves and savestates",
            "Accepted route and reliability evidence",
        ),
    )


def default_companion_session(
    goal_id: str = ACTIVE_PRODUCT_GOAL_ID,
    *,
    live_snapshot: LiveObservationSnapshot | None = None,
) -> CompanionSession:
    if goal_id not in _product_goal_ids():
        raise GoalValidationError(f"Unsupported Game Companion goal: {goal_id}")
    contract = load_goal_contract(resolve_goal_path(goal_id))
    target = str(contract.objective.get("target", "declared goal boundary"))
    show_request = _default_show_request(goal_id)
    show = show_capability(show_request)
    observation = (
        live_snapshot.observation()
        if live_snapshot is not None and live_snapshot.observed_at is not None
        else Observation(
            checkpoint=None,
            observed_at=None,
            freshness=Freshness.UNKNOWN,
            confidence=None,
        )
    )
    session = CompanionSession(
        adapter=AdapterIdentity(
            adapter_id="smb3",
            game_name="Super Mario Bros. 3",
            adapter_name="Mario adapter",
            status=(
                "You are playing · observing only"
                if live_snapshot is not None
                and live_snapshot.observation_active
                else "Accepted route adapter · observation ready"
            ),
        ),
        goal=GoalIdentity(
            goal_id=contract.id,
            name=contract.display_name,
            objective=contract.user_directive,
        ),
        observation=observation,
        modes=(
            ModeCapability(
                "tell",
                bool(live_snapshot and live_snapshot.tell_ready),
                "Explain the next useful actions from a trusted observation.",
                None
                if live_snapshot and live_snapshot.tell_ready
                else live_snapshot.reason
                if live_snapshot
                else "No trusted live observation is connected.",
            ),
            ModeCapability(
                "show",
                show.available and observation.trusted,
                "Demonstrate one approved section and retain review evidence.",
                None
                if show.available and observation.trusted
                else "Use the separate Show panel below; it does not depend on or advance your live game."
                if show.available
                else show.reason,
            ),
            ModeCapability(
                "do",
                bool(
                    live_snapshot
                    and live_snapshot.takeover_capable
                    and live_snapshot.tell_ready
                ),
                "Complete one authorized, checkpoint-bounded objective.",
                None
                if live_snapshot
                and live_snapshot.takeover_capable
                and live_snapshot.tell_ready
                else "Start a session with Allow takeover later and reach a supported fresh state.",
            ),
        ),
        safety=SafetyBoundary(
            authorized=False,
            stop_point=target,
            protected_decisions=(
                "No savestates, memory mutation, route bypass, or hidden success claims",
                "No input outside an explicitly authorized companion session",
                "Existing full-route execution remains an advanced Lab action",
            ),
            recovery_boundary="Capture evidence and stop on unknown state, mismatch, or timeout.",
        ),
        lifecycle=SessionLifecycle.IDLE,
        activity=(
            live_snapshot.reason
            if live_snapshot
            else "Waiting for a trusted Mario observation.",
        ),
    )
    session.validate()
    return session


def _show_panel(
    show_session: ShowSession | None,
    *,
    show_request: ShowRequest | None,
    csrf_token: str | None,
) -> str:
    capability = show_capability(show_request)
    definition = capability.definition
    cues = show_session.cues if show_session is not None else definition.cues if definition else ()
    active = show_session is not None and show_session.lifecycle in {
        ShowLifecycle.STARTING,
        ShowLifecycle.ACTIVE,
        ShowLifecycle.STOP_REQUESTED,
    }
    lifecycle = show_session.lifecycle.value if show_session else "unavailable" if not capability.available else "ready"
    current = next((cue for cue in cues if cue.cue_id == (show_session.current_cue_id if show_session else None)), None)
    if current is None:
        current = next((cue for cue in cues if cue.status.value in {"active", "waiting"}), None)
    activity = show_session.activity if show_session else (capability.reason,)
    outcome = show_session.outcome if show_session else None
    artifacts = outcome.artifacts if outcome else ()
    artifact_links = "".join(
        f'<li><a href="/{_esc(reference.path)}">{_esc(reference.role)}</a>'
        f" · {_esc(reference.cue_id or reference.event_id or 'session evidence')}</li>"
        for reference in artifacts
        if reference.path.startswith("artifacts/")
    ) or "<li>No retained replay yet.</li>"
    goal_id = show_request.goal_id if show_request else ACTIVE_PRODUCT_GOAL_ID
    return f"""
      <section id="show" class="session-card show-card state-{_esc(lifecycle)}" data-testid="show-session" data-show-state="{_esc(lifecycle)}">
        <div class="section-title"><div><h2>Show</h2><p class="selected-mode">Demonstrate separately</p></div><span class="status-pill">Review only</span></div>
        <p class="callout"><strong>Your game is unchanged.</strong> Show uses a separate visible process and cannot claim your completion.</p>
        <form method="post" action="/show-start"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><input type="hidden" name="goal_id" value="{_esc(goal_id)}"><button type="submit" data-testid="show-start" {'disabled aria-disabled="true"' if not capability.available or active else ''}>Start Separate Demonstration</button></form>
        <form method="post" action="/show-stop"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><button type="submit" data-testid="show-stop" {'disabled aria-disabled="true"' if not active else ''}>Stop Demonstration</button></form>
        <p data-testid="current-show-cue"><strong>Current cue:</strong> {_esc(current.instruction if current else 'None')}</p>
        <p data-testid="show-outcome"><strong>Outcome:</strong> {_esc(outcome.explanation if outcome else 'No demonstration outcome.')}</p>
        <details class="technical-details" data-testid="show-details"><summary>Demonstration scope, cues, and evidence</summary>
        <dl class="fact-grid" data-testid="show-scope">
          <div><dt>Selected segment</dt><dd><code>world_1_1_clear</code></dd></div>
          <div><dt>Start</dt><dd>Fresh power-on process; adapter observes the 1-1 starting event.</dd></div>
          <div><dt>Stop</dt><dd>Game-owned 1-1 course clear, your stop/takeover request, failure, or timeout.</dd></div>
          <div><dt>Policy</dt><dd>review_only=true · promotable=false · counts_toward_reliability=false</dd></div>
        </dl>
        <h3>Protected decisions</h3><ul><li>Your active game and saves</li><li>Accepted route/reliability records</li><li>No retries or continuation beyond 1-1</li></ul>
        <h3>Demonstration cues</h3>
        <ol data-testid="show-cues">{''.join(f'<li data-testid="show-cue" data-status="{_esc(cue.status.value)}"><strong>{_esc(cue.instruction)}</strong><br>Look for: {_esc(cue.expected_visual_cue)}<br><span class="meta">Trigger: {_esc(cue.trigger_event)} · {_esc(cue.status.value)}</span></li>' for cue in cues) or '<li>Validated Show cues unavailable.</li>'}</ol>
        <ol class="activity-list" data-testid="show-activity">{''.join(f'<li>{_esc(item)}</li>' for item in activity)}</ol>
        <p class="meta">Stop Demonstration ends automation in the separate process. It is distinct from Take Control Now in a live Do session.</p>
        <div><p>Player completion: No · Authoritative acceptance: No</p></div>
        <div data-testid="show-replay"><h3>Replay &amp; evidence</h3><ul>{artifact_links}</ul></div>
        </details>
      </section>"""


def _live_observation_panel(
    snapshot: LiveObservationSnapshot | None,
    *,
    csrf_token: str | None,
    goal_id: str = ACTIVE_PRODUCT_GOAL_ID,
) -> str:
    current = snapshot or LiveObservationSnapshot(
        None,
        ConnectionState.IDLE,
        Freshness.UNKNOWN,
        "Start live observation to open a visible player-controlled game.",
    )
    active = current.observation_active
    level_id = observed_level_id(current.samples)
    run_summary = (
        LocalRunLibrary().summary("smb3", level_id)
        if level_id
        else {
            "run_count": 0,
            "fastest_overall": None,
            "fastest_player": None,
            "fastest_agent": None,
            "fastest_mixed": None,
            "most_recent": None,
        }
    )
    fastest = run_summary["fastest_overall"]
    player_best = run_summary["fastest_player"]
    agent_best = run_summary["fastest_agent"]
    mixed_best = run_summary["fastest_mixed"]
    companion_playing = current.control_owner == "agent"
    full_game_start = current.checkpoint_id == "fresh_power_on"
    takeover_available = (
        current.takeover_capable
        and current.tell_ready
        and current.checkpoint_id in {"world_1_1_clear", "fresh_power_on"}
        and not companion_playing
    )
    solution_id = (
        "world_8_finish_game_v1" if full_game_start else "world_1_1_remainder_v1"
    )
    scope_options = (
        '<option value="full_game">Full game</option><option value="world_or_route_goal">Accepted route goal</option><option value="until_reclaim">Until reclaim</option>'
        if full_game_start
        else '<option value="level_remainder">Current level remainder</option><option value="complete_level">Complete level</option><option value="until_reclaim">Until reclaim</option>'
    )
    stop_options = (
        '<option value="stable_game_owned_ending">Stable game-owned ending</option><option value="reclaim">Reclaim</option><option value="timeout">Timeout</option><option value="failure">Failure</option>'
        if full_game_start
        else '<option value="game_owned_level_clear">Game-owned level clear</option><option value="reclaim">Reclaim</option><option value="timeout">Timeout</option><option value="failure">Failure</option>'
    )
    input_items = "".join(
        f'<li data-testid="live-player-input"><strong>Player</strong> · frame '
        f'{item.provenance.frame} · {_esc(", ".join(item.buttons) or "neutral")} · '
        f'{item.provenance.confidence:.0%}</li>'
        for item in reversed(current.recent_inputs[-8:])
    ) or "<li>No player input observed yet.</li>"
    event_items = "".join(
        f'<li data-testid="live-event"><strong>{_esc(event.kind.value.replace("_", " ").title())}</strong> '
        f'· {_esc(event.detail)} · frame {event.provenance.frame}</li>'
        for event in reversed(current.events[-8:])
    ) or "<li>No game-owned transition observed yet.</li>"
    fact_items = "".join(
        f'<div><dt>{_esc(fact.fact_id.replace("_", " ").title())}</dt>'
        f'<dd>{_esc(fact.value)} · frame {fact.provenance.frame}</dd></div>'
        for fact in current.facts
    ) or "<div><dt>Resources</dt><dd>Unknown</dd></div>"
    artifact_link = (
        f'<a href="/{_esc(str(current.artifact_dir / "reconciliation.json"))}">Local session evidence</a>'
        if current.artifact_dir
        else "Created when observation starts"
    )
    live_tell_disabled = "" if current.tell_ready else 'disabled aria-disabled="true"'
    return f"""
      <section id="live" class="session-card live-observation-card compact-live-card state-{_esc(current.state.value)}" data-testid="live-observation" data-connection-state="{_esc(current.state.value)}">
        <div class="section-title"><h2>Live play</h2><span class="status-pill">{_esc(current.state.value.replace('_', ' ').title())}</span></div>
        <p class="control-line" data-testid="live-control-ownership"><strong>{'Companion is playing' if companion_playing else 'You play'}</strong> · control epoch {current.control_epoch} · Agent input <strong data-testid="agent-input-count">{current.agent_input_count}</strong></p>
        <dl class="live-summary" data-testid="live-status">
          <div><dt>Location</dt><dd>{_esc(current.checkpoint or 'Waiting for Mario')}</dd></div>
          <div><dt>Progress</dt><dd>{_esc(current.progress)}</dd></div>
          <div><dt>Deaths</dt><dd>{current.deaths}</dd></div>
          <div><dt>Signal</dt><dd>{_esc(current.freshness.value.title())}{f' · {current.age_seconds:.1f}s' if current.age_seconds is not None else ''}</dd></div>
        </dl>
        <p class="status-message" data-testid="live-state-reason">{_esc(current.reason)}</p>
        <div class="live-actions">
          <form method="post" action="/observe-start"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><label class="inline-check"><input type="checkbox" name="allow_takeover" value="true" {'disabled' if active else ''}><span>Allow takeover later</span></label><button type="submit" data-testid="observe-start" {'disabled aria-disabled="true"' if active else ''}>Start</button></form>
          <form method="post" action="/observe-stop"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><button type="submit" data-testid="observe-stop" {'disabled aria-disabled="true"' if not active else ''}>Stop</button></form>
          <span class="live-indicator" data-testid="refresh-live-status">● Live updates</span>
        </div>
        <details class="technical-details" data-testid="live-technical-details">
          <summary>Details</summary>
          <dl class="fact-grid technical-facts"><div><dt>Session</dt><dd>{_esc(current.session_id or 'None')}</dd></div><div><dt>Confidence</dt><dd>{f'{current.confidence:.0%}' if current.confidence is not None else 'Unknown'}</dd></div><div><dt>Recoveries</dt><dd>{current.recoveries}</dd></div><div><dt>Evidence</dt><dd>{artifact_link}</dd></div></dl>
          <h3>Resources</h3><dl class="fact-grid" data-testid="live-resources">{fact_items}</dl>
          <h3>Recent player inputs</h3><ol class="activity-list" data-testid="live-inputs">{input_items}</ol>
          <h3>Recent game events</h3><ol class="activity-list" data-testid="live-events">{event_items}</ol>
          <form method="post" action="/tell-live" data-testid="live-tell-request">
            <input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><input type="hidden" name="goal_id" value="{_esc(goal_id)}">
            <label>Legacy route Tell detail <select name="spoiler_level"><option value="minimal">Minimal</option><option value="guided" selected>Guided</option><option value="full">Full</option></select></label>
            <button type="submit" data-testid="live-tell" {live_tell_disabled}>Tell from live state</button>
          </form>
          <p class="meta" data-testid="live-tell-reason">{_esc(current.tell_unavailable_reason)}</p>
        </details>
        <section class="run-library-summary" data-testid="run-library-summary">
          <div class="section-title"><h3>Local run library</h3><span class="status-pill">Grows automatically</span></div>
          <dl class="live-summary"><div><dt>Current level runs</dt><dd>{run_summary['run_count']}</dd></div><div><dt>Fastest locally observed</dt><dd>{f'{fastest.elapsed_compatible_frames} frames' if fastest else 'No compatible completion yet'}</dd></div><div><dt>Player best</dt><dd>{f'{player_best.elapsed_compatible_frames} frames' if player_best else 'None'}</dd></div><div><dt>Agent best</dt><dd>{f'{agent_best.elapsed_compatible_frames} frames' if agent_best else 'None'}</dd></div><div><dt>Mixed best</dt><dd>{f'{mixed_best.elapsed_compatible_frames} frames' if mixed_best else 'None'}</dd></div></dl>
          <p class="meta">Captured completions are comparison evidence and candidate traces. They are not executable until replay safety and objective compatibility are proven.</p>
        </section>
        <section class="takeover-panel" data-testid="takeover-panel">
          <div class="section-title"><div><h3>Do</h3><p class="selected-mode">Take over my current game for this goal</p></div><span class="status-pill">{'Companion is playing' if companion_playing else 'Player control'}</span></div>
          <p data-testid="takeover-capability">{'This session can transfer the same visible emulator process.' if current.takeover_capable else 'Start a new session with Allow takeover later to enable an opt-in controller path.'}</p>
          <dl class="fact-grid" data-testid="do-preflight-summary"><div><dt>Current session</dt><dd>{_esc(current.session_id or 'None')}</dd></div><div><dt>Visible process</dt><dd>{current.emulator_pid if current.emulator_pid is not None else 'Not verified'}</dd></div><div><dt>Selected goal</dt><dd>{'Complete the accepted full-game route' if full_game_start else 'Complete the supported current level boundary'}</dd></div><div><dt>Executable solution</dt><dd>{_esc(solution_id)}</dd></div><div><dt>What Companion may do</dt><dd>Send only accepted-solution controller inputs inside the authorized scope.</dd></div><div><dt>What makes it stop</dt><dd>Selected stop point, Take Control Now, timeout, failure, stale state, protection conflict, or process loss.</dd></div></dl>
          <form method="post" action="/takeover-start" data-testid="takeover-preflight">
            <input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><input type="hidden" name="solution_id" value="{solution_id}">
            <label>Scope <select name="scope">{scope_options}</select></label>
            <label>Stop condition <select name="stop_condition">{stop_options}</select></label>
            <label>Timeout (seconds) <input type="number" name="timeout_seconds" min="1" max="3600" value="120"></label>
            <fieldset><legend>Protected resources and decisions</legend><label><input type="checkbox" name="protected_resources" value="p_wing"> P-Wing</label><label><input type="checkbox" name="protected_resources" value="warp_whistle"> Warp Whistles</label><label><input type="checkbox" name="protected_decisions" value="no_inventory_use" checked> No inventory use</label></fieldset>
            <p class="callout">Preflight: exact session, process, game file, current-state fingerprint, profile, accepted solution, scope, stop condition, timeout, protections, nonce, and new control epoch are bound at transfer.</p>
            <button type="submit" data-testid="hand-control" {'disabled aria-disabled="true"' if not takeover_available else ''}>Hand This Goal to Companion</button>
          </form>
          <form method="post" action="/takeover-reclaim"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><button type="submit" class="take-control" data-testid="take-control-now" {'disabled aria-disabled="true"' if not companion_playing else ''}>Take Control Now</button></form>
          <p class="meta" data-testid="takeover-state">State: {_esc(current.control_state)}. Reclaim is checked by the emulator controller every frame; neutral input is written before handback.</p>
          <div class="callout" data-testid="do-outcome"><strong>Current outcome</strong><p>{_esc(current.takeover_terminal_reason.replace('_', ' ').title() if current.takeover_terminal_reason else 'No terminal Do outcome yet.')}</p><p>Agent input stopped: {_yes_no(current.input_neutralized)} · Control returned: {_yes_no(current.control_owner == 'player' and current.input_neutralized)} · Observation resumed: {_yes_no(current.observation_resumed)} · Game process: {_esc('running' if current.process_alive is True else 'lost' if current.process_alive is False else 'not yet determined')}</p></div>
          <details><summary>Supported solution scopes</summary><ul><li>World 1-1: level remainder, complete level, or until reclaim from fresh supported gameplay.</li><li>Full accepted route: exact fresh compatible start, full game/world goal, or until reclaim; live acceptance is required before product completion.</li></ul></details>
        </section>
      </section>"""


def _objective_panel(
    view: ObjectiveView,
    *,
    csrf_token: str | None,
    learning_snapshot: LearningSnapshot | None = None,
) -> str:
    if view.selected is None:
        return """
      <section id="objective" class="session-card objective-card compact-objective-card" data-testid="objective-profile">
        <div class="section-title"><h2>Live objective</h2><span class="status-pill">Unavailable</span></div>
        <p data-testid="profile-unavailable">Enter World 1-1 to choose a profile.</p>
        <details class="technical-details"><summary>Why only World 1-1?</summary><p>Other levels do not yet expose enough passive facts for honest comparison or completion claims.</p></details>
      </section>"""
    return _configured_objective_panel(
        view,
        csrf_token=csrf_token,
        learning_snapshot=learning_snapshot,
    )


def _learning_panel(
    snapshot: LearningSnapshot,
    objective_view: ObjectiveView,
    *,
    csrf_token: str | None,
) -> str:
    objective_id = (
        objective_view.selected.profile_id
        if objective_view.selected is not None
        else "smb3.world_1_1.normal_clear"
    )
    attempts = tuple(
        attempt
        for attempt in snapshot.attempts
        if attempt.game_id == "smb3" and attempt.objective_id == objective_id
    )
    eligible = tuple(
        attempt for attempt in attempts if attempt.complete_timing_interval and attempt.evidence_integrity
    )
    compatible = (
        (eligible[0],)
        + tuple(item for item in eligible[1:] if compatibility(eligible[0], item).compatible)
        if eligible
        else ()
    )
    records: dict[str, object | None] = {"player": None, "agent": None, "mixed": None}
    for actor in records:
        candidates = [
            attempt
            for attempt in compatible
            if attempt.actor == actor and attempt.completion == "completed"
        ]
        records[actor] = min(candidates, key=lambda item: item.elapsed) if candidates else None
    overall_candidates = [
        attempt for attempt in compatible if attempt.completion == "completed"
    ]
    overall = min(overall_candidates, key=lambda item: item.elapsed) if overall_candidates else None
    patterns = tuple(
        pattern
        for pattern in snapshot.patterns
        if set(pattern.supporting_run_ids).intersection({attempt.run_id for attempt in attempts})
    )
    tactics = tuple(
        tactic
        for tactic in snapshot.tactics
        if set(tactic.supporting_run_ids).intersection({attempt.run_id for attempt in attempts})
    )
    candidates = tuple(
        candidate
        for candidate in snapshot.candidates
        if candidate.game_id == "smb3" and candidate.objective_id == objective_id
    )
    preference = next(
        (
            item
            for item in reversed(snapshot.preferences)
            if item.game_id == "smb3" and item.objective_id == objective_id
        ),
        OwnerLocalPreference("smb3", objective_id),
    )
    advice = learning_advice(snapshot, "smb3", objective_id, preference)

    def elapsed(item: object | None) -> str:
        value = getattr(item, "elapsed", None)
        return f"{value} frames" if value is not None else "None yet"

    attempt_rows = "".join(
        f'<li><strong>{_esc(attempt.actor.title())}</strong> · {_esc(attempt.completion)} · '
        f'{attempt.elapsed} {_esc(attempt.timing_units)} · <span class="meta">{_esc(attempt.run_id)}</span></li>'
        for attempt in reversed(compatible[-8:])
    ) or "<li>Learning starts after compatible completed attempts are available.</li>"
    pattern_rows = "".join(
        f'<li><strong>{_esc(pattern.summary)}</strong> · {len(pattern.supporting_run_ids)} supporting '
        f'· {len(pattern.counterexample_run_ids)} counterexamples</li>'
        for pattern in patterns
    ) or "<li>There is not enough compatible evidence to call any trouble recurring.</li>"
    tactic_rows = "".join(
        f'<li><strong>{_esc(tactic.tactic_tag.replace("_", " ").title())}</strong> · '
        f'{len(tactic.supporting_run_ids)} supporting attempts · {tactic.confidence:.0%} confidence</li>'
        for tactic in tactics
    ) or "<li>No successful tactic has enough comparative evidence yet.</li>"
    advice_rows = "".join(
        f'<li><strong>{_esc(item.classification.value.replace("_", " ").title())}</strong> · '
        f'{_esc(item.text)}<details><summary>Why?</summary><p>{_esc(", ".join(item.evidence_references) or "No evidence yet")}</p>'
        f'<p>{item.confidence:.0%} confidence</p></details></li>'
        for item in advice
    )
    candidate_rows = "".join(
        _learning_candidate_card(candidate, csrf_token=csrf_token) for candidate in candidates
    ) or '<p class="compact-state">No candidate improvement is available for review.</p>'
    policy_options = "".join(
        f'<option value="{policy.value}" {"selected" if policy is preference.help_policy else ""}>'
        f'{_esc(policy.value.replace("_", " ").title())}</option>'
        for policy in HelpPolicy
    )
    return f"""
      <section id="learning" class="session-card learning-card" data-testid="learning-surface">
        <div class="section-title"><div><h2>Learning from your runs</h2><p class="selected-mode">Local, inspectable, and review-first</p></div><span class="status-pill">Nothing changes silently</span></div>
        <dl class="live-summary" data-testid="learning-records">
          <div><dt>Fastest observed</dt><dd>{elapsed(overall)}</dd></div>
          <div><dt>Player best</dt><dd>{elapsed(records['player'])}</dd></div>
          <div><dt>Agent best</dt><dd>{elapsed(records['agent'])}</dd></div>
          <div><dt>Mixed completion</dt><dd>{elapsed(records['mixed'])}</dd></div>
        </dl>
        <div class="objective-now">
          <div><h3>Recurring trouble</h3><ul>{pattern_rows}</ul></div>
          <div><h3>Successful tactics</h3><ul>{tactic_rows}</ul></div>
        </div>
        <details data-testid="learning-attempts"><summary>Recent compatible attempts</summary><ul>{attempt_rows}</ul></details>
        <section data-testid="learning-advice"><h3>Tell me why</h3><ul>{advice_rows}</ul></section>
        <section data-testid="learning-candidates"><h3>Candidate improvements</h3>{candidate_rows}</section>
        <form method="post" action="/learning-preferences" data-testid="learning-preferences">
          <input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><input type="hidden" name="game_id" value="smb3"><input type="hidden" name="objective_id" value="{_esc(objective_id)}">
          <div class="objective-controls">
            <label>Help <select name="help_policy">{policy_options}</select></label>
            <label>Style <select name="preferred_solution_style"><option value="balanced" {'selected' if preference.preferred_solution_style == 'balanced' else ''}>Balanced</option><option value="safe" {'selected' if preference.preferred_solution_style == 'safe' else ''}>Safer</option><option value="fast" {'selected' if preference.preferred_solution_style == 'fast' else ''}>Faster</option></select></label>
            <label>Risk <select name="risk_tolerance"><option value="cautious" {'selected' if preference.risk_tolerance == 'cautious' else ''}>Cautious</option><option value="moderate" {'selected' if preference.risk_tolerance == 'moderate' else ''}>Moderate</option><option value="aggressive" {'selected' if preference.risk_tolerance == 'aggressive' else ''}>Aggressive</option></select></label>
            <label>Spoilers <select name="spoiler_level"><option value="minimal" {'selected' if preference.spoiler_level == 'minimal' else ''}>Minimal</option><option value="guided" {'selected' if preference.spoiler_level == 'guided' else ''}>Guided</option><option value="full" {'selected' if preference.spoiler_level == 'full' else ''}>Full</option></select></label>
            <label>Compare with <select name="preferred_comparison_target"><option value="player_best" {'selected' if preference.preferred_comparison_target == 'player_best' else ''}>Player best</option><option value="agent_best" {'selected' if preference.preferred_comparison_target == 'agent_best' else ''}>Agent best</option><option value="fastest_observed" {'selected' if preference.preferred_comparison_target == 'fastest_observed' else ''}>Fastest observed</option><option value="accepted_solution" {'selected' if preference.preferred_comparison_target == 'accepted_solution' else ''}>Accepted solution</option></select></label>
          </div>
          <fieldset><legend>Preserve resources</legend><label><input type="checkbox" name="resource_preservation" value="p_wing" {'checked' if 'p_wing' in preference.resource_preservation else ''}> P-Wing</label><label><input type="checkbox" name="resource_preservation" value="warp_whistle" {'checked' if 'warp_whistle' in preference.resource_preservation else ''}> Warp Whistles</label></fieldset>
          <fieldset><legend>Suggestion types</legend><label><input type="checkbox" name="dismissed_suggestion_types" value="speed" {'checked' if 'speed' in preference.dismissed_suggestion_types else ''}> Hide speed suggestions</label><label><input type="checkbox" name="dismissed_suggestion_types" value="high_risk" {'checked' if 'high_risk' in preference.dismissed_suggestion_types else ''}> Hide high-risk suggestions</label><label><input type="checkbox" name="confirmed_helpful_suggestion_types" value="split_comparison" {'checked' if 'split_comparison' in preference.confirmed_helpful_suggestion_types else ''}> Split comparisons help</label><label><input type="checkbox" name="confirmed_helpful_suggestion_types" value="recovery_cue" {'checked' if 'recovery_cue' in preference.confirmed_helpful_suggestion_types else ''}> Recovery cues help</label></fieldset>
          <button type="submit">Save preferences</button>
        </form>
        <form method="post" action="/learning-preferences-reset"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><input type="hidden" name="game_id" value="smb3"><input type="hidden" name="objective_id" value="{_esc(objective_id)}"><button type="submit" class="quiet">Reset local preferences</button></form>
        <p class="meta">Ignoring advice is not treated as a preference. Preferences never override protected resources, current-session choices, safety rules, or takeover authorization.</p>
      </section>"""


def _learning_candidate_card(candidate: object, *, csrf_token: str | None) -> str:
    lifecycle = getattr(candidate, "lifecycle")
    candidate_id = str(getattr(candidate, "candidate_id"))
    requirements = tuple(getattr(candidate, "validation_requirements"))
    requirement_rows = "".join(
        f'<li>{_esc(requirement.description)} · {requirement.required_replays} replay(s) · {_esc(requirement.status)}</li>'
        for requirement in requirements
    )
    review = ""
    if lifecycle is CandidateLifecycle.REVIEW_REQUIRED:
        review = f'''
          <form method="post" action="/learning-review"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><input type="hidden" name="candidate_id" value="{_esc(candidate_id)}"><label>Reason <input name="reason" required></label><button name="decision" value="approve" type="submit">Approve for later validation</button><button name="decision" value="reject" type="submit" class="quiet">Reject</button></form>'''
    return f'''
      <article class="callout" data-testid="learning-candidate" data-state="{_esc(lifecycle.value)}">
        <strong>{_esc(getattr(candidate, "expected_benefit"))}</strong>
        <p>{_esc(getattr(candidate, "why_improvement"))}</p>
        <p>Status: {_esc(lifecycle.value.replace("_", " ").title())}. Approval does not make this executable.</p>
        {review}
        <form method="post" action="/learning-export"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><input type="hidden" name="candidate_id" value="{_esc(candidate_id)}"><button type="submit" class="quiet">Export review packet</button></form>
        <details class="technical-details"><summary>Evidence and promotion requirements</summary><p>Candidate hash: <code>{_esc(getattr(candidate, "content_hash"))}</code></p><p>Sources: {_esc(", ".join(getattr(candidate, "provenance").source_run_ids))}</p><ul>{requirement_rows}</ul><p>Promotion additionally requires the existing exact-diff route-patch workflow and affected reliability gates.</p></details>
      </article>'''


def _configured_objective_panel(
    view: ObjectiveView,
    *,
    csrf_token: str | None,
    learning_snapshot: LearningSnapshot | None = None,
) -> str:
    selected = view.selected
    if selected is None:
        raise ObjectiveProfileError("configured objective panel requires a selected profile")
    profile_options = "".join(
        f'<option value="{_esc(profile.profile_id)}" {"selected" if profile.profile_id == selected.profile_id else ""}>{_esc(profile.name)}</option>'
        for profile in view.profiles
    )
    policy_options = "".join(
        f'<option value="{policy.value}" {"selected" if policy is view.policy else ""}>{_esc(policy.value.replace("_", " ").title())}</option>'
        for policy in CoachingPolicy
    )
    reference_option = (
        f'<option value="">No comparison target</option><option value="{_esc(view.reference.reference_id)}" selected>{_esc(view.reference.reference_id)} · {_esc(view.reference.classification.value.replace("_", " "))}</option>'
        if view.reference
        else '<option value="" selected>No compatible accepted reference</option>'
    )
    requirements = "".join(
        f'<li data-testid="objective-requirement" data-state="{item.state.value}"><strong>{_esc(item.name)}</strong> · {_esc(item.state.value.replace("_", " ").title())}{" · optional" if item.optional else ""}<br><span class="meta">{_esc(item.reason)}</span></li>'
        for item in (view.progress.requirements if view.progress else ())
    )
    comparison = view.comparison
    suggestion = view.suggestion
    suppression_label = {
        "quiet_policy": "Quiet",
        "not_requested": "Waiting for request",
        "stale_observation": "Waiting for live state",
        "duplicate_without_meaningful_change": "No new hint",
        "requirement_already_impossible": "Requirement missed",
        "no_actionable_requirement": "Nothing actionable",
    }.get(view.suppression_reason or "", "No hint")
    suggestion_html = (
        f'''<article class="callout" data-testid="coaching-hint"><strong>{_esc(suggestion.action)}</strong><form method="post" action="/objective-dismiss"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><button type="submit" data-testid="dismiss-hint">Dismiss</button></form><details><summary>Why?</summary><p>{_esc(suggestion.trigger)}</p><p>{_esc(suggestion.why)}</p><p>{suggestion.confidence:.0%} confidence · {_esc(", ".join(suggestion.provenance))}</p></details></article>'''
        if suggestion
        else f'<p class="compact-state" data-testid="coaching-suppression">{_esc(suppression_label)}</p>'
    )
    tell = view.tell_answer
    tell_html = ""
    if tell:
        groups = (
            ("Current live facts", tell.current_facts),
            ("Profile requirements", tell.profile_facts),
            ("Reference-run facts", tell.reference_facts),
            ("Inferences", tell.inferences),
            ("Unknown or unverifiable", tell.unknowns),
        )
        tell_html = f'<article class="tell-card compact-tell" data-testid="objective-tell-answer"><h3>{_esc(tell.answer)}</h3><details><summary>Why Companion said this</summary>' + "".join(
            f'<h4>{_esc(label)}</h4><ul>{"".join(f"<li>{_esc(item)}</li>" for item in items) or "<li>None</li>"}</ul>'
            for label, items in groups
        ) + "</details></article>"
    learned_items = learning_advice(
        learning_snapshot or LearningSnapshot((), (), (), (), (), (), (), (), ()),
        selected.game_id,
        selected.profile_id,
    )
    learning_tell_html = (
        '<details data-testid="objective-learning-tell"><summary>What local attempts add</summary><ul>'
        + "".join(
            f'<li><strong>{_esc(item.classification.value.replace("_", " ").title())}</strong> · {_esc(item.text)} · '
            f'<span class="meta">{_esc(", ".join(item.evidence_references) or "insufficient evidence")}</span></li>'
            for item in learned_items
        )
        + "</ul></details>"
    )
    return f"""
      <section id="objective" class="session-card objective-card compact-objective-card" data-testid="objective-profile" data-profile-id="{_esc(selected.profile_id)}">
        <div class="section-title"><div><h2>Live objective</h2><p class="selected-mode">{_esc(selected.name)} · Coaching: <strong>{_esc(view.policy.value.replace('_', ' ').title())}</strong></p></div><span class="status-pill">{_esc(view.progress.outcome.value.title() if view.progress else 'Unverifiable')}</span></div>
        <form class="objective-controls" method="post" action="/objective-config" data-testid="objective-config">
          <input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}">
          <label>Supported profile <select name="profile_id">{profile_options}</select></label>
          <label>Coaching policy <select name="coaching_policy">{policy_options}</select></label>
          <label>Comparison target <select name="reference_id">{reference_option}</select></label>
          <button type="submit">Apply</button>
        </form>
        <div class="objective-now">
          <div><h3>Progress</h3><ul data-testid="objective-progress">{requirements}</ul></div>
          <div data-testid="comparison-result" data-comparison="{comparison.state.value}"><h3>Comparison: {_esc(comparison.state.value.replace('_', ' ').title())}</h3><p>{_esc(comparison.reason)}</p><p>{f'You {comparison.player_elapsed} · reference {comparison.reference_elapsed} {selected.timing_units} · death difference {comparison.death_delta}' if comparison.player_elapsed is not None else ''}</p></div>
        </div>
        <form class="inline-action" method="post" action="/objective-advice"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><button type="submit" data-testid="request-objective-advice">Hint</button><span class="meta">Quiet · On request · Proactive</span></form>
        {suggestion_html}
        <form class="objective-tell-controls" method="post" action="/objective-tell" data-testid="objective-tell-request">
          <input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}">
          <label>Ask
            <select name="objective_question"><option>How am I doing against the reference?</option><option>What do I still need?</option><option>Did I miss anything?</option><option>What is the next speedrun action?</option><option>Can I still complete this objective?</option><option>Why am I behind?</option><option>Give me the full plan for this profile.</option></select>
          </label><label>Detail <select name="objective_spoiler"><option value="minimal">Minimal</option><option value="guided" selected>Guided</option><option value="full">Full</option></select></label><button type="submit">Ask</button>
        </form>
        {tell_html}
        {learning_tell_html}
        <details class="technical-details"><summary>What this profile exactly means</summary><p>{_esc(selected.description)}</p><dl class="fact-grid" data-testid="profile-contract"><div><dt>Profile</dt><dd><code>{_esc(selected.profile_id)}@{selected.version}</code></dd></div><div><dt>Timing</dt><dd>{_esc(selected.timing_boundary)} · {_esc(selected.timing_units)}</dd></div><div><dt>Control</dt><dd>Player-owned by default; an active takeover authorization is exclusive and epoch-bound.</dd></div><div><dt>Boundaries</dt><dd>Show is separate; captured traces remain non-executable candidates.</dd></div></dl><p class="meta">Show remains a separate review-only process. A takeover-capable live session exposes only replay-safe accepted solutions whose current-state preconditions match.</p></details>
      </section>"""


def _first_use_panel(view: ProductSessionView, *, csrf_token: str | None) -> str:
    setup = view.first_use
    game = setup.game_file
    emulator = setup.emulator
    status = setup.status.value.replace("_", " ").title()
    if setup.status.value == "ready" and view.stage not in {
        ProductStage.FIRST_USE,
        ProductStage.FAILURE,
        ProductStage.RECOVERY,
    }:
        return f'''
          <details id="setup" class="session-card first-use-card" data-testid="mario-first-use" data-setup-status="ready">
            <summary><strong>Mario setup ready</strong> · {_esc(game.display)} · FCEUX detected · {_esc((setup.selected_session_kind or 'session choice').replace('_', ' '))}</summary>
            <p>Game identity is verified locally; ROM contents are not copied. Input authority is not restored from setup.</p>
            {_capability_list(view)}
          </details>'''
    error = (
        f'''<div class="callout action-error" role="alert" data-testid="setup-error"><strong>Setup needs attention</strong><p>{_esc(setup.error or "Configuration could not be completed.")}</p><p>The error context and any evidence were retained.</p><form method="post" action="/setup-retry"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><button type="submit">Retry setup check</button></form></div>'''
        if setup.error
        else ""
    )
    return f'''
      <section id="setup" class="session-card first-use-card" data-testid="mario-first-use" data-setup-status="{_esc(setup.status.value)}">
        <div class="section-title"><div><h2>Mario setup</h2><p class="selected-mode">Game Companion does not provide the game file.</p></div><span class="status-pill">{_esc(status)}</span></div>
        {error}
        <div class="setup-steps">
          <article class="callout"><strong>1 · Local game file</strong><p>{_esc(game.reason)}</p><p class="meta">{_esc(game.display)} · {_esc(game.detected_from)}</p></article>
          <article class="callout"><strong>2 · FCEUX</strong><p>{_esc(emulator.reason)}</p><p class="meta">{"Detected locally" if emulator.available else "Not detected"}</p></article>
          <article class="callout"><strong>3 · Input</strong><p>{_esc(setup.input_reason)}</p></article>
        </div>
        <form method="post" action="/setup-game-file" data-testid="manual-game-file">
          <input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}">
          <label>Select a local game file <input type="text" name="game_file_path" required placeholder="/Users/you/Games/mario.nes" autocomplete="off"></label>
          <button type="submit">Verify Local Game File</button>
          <p class="meta">Only the local path, NES header, and SHA-256 identity are read. ROM contents are not copied, displayed, or stored.</p>
        </form>
        <form method="post" action="/setup-pick-game-file" data-testid="native-game-file-picker"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><button type="submit">Choose Game File…</button></form>
        <form method="post" action="/setup-choice" data-testid="first-use-session-choice">
          <input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}">
          <fieldset><legend>Start a visible session</legend>
            <label><input type="radio" name="session_kind" value="observe_only" checked> <strong>Observe only</strong><br><span>You play; Companion watches and tracks. This session has no agent-input path.</span></label>
            <label><input type="radio" name="session_kind" value="takeover_capable"> <strong>Observe with the option to allow Do later</strong><br><span>Adds a write-capable controller path, but sends no agent input until a fresh explicit goal authorization.</span></label>
          </fieldset>
          <label class="inline-check"><input type="checkbox" name="input_ready" value="true" required><span>My FCEUX keyboard or controller mapping is ready.</span></label>
          <button type="submit" {'disabled aria-disabled="true"' if not game.supported_identity or not emulator.available or view.stage not in {ProductStage.FIRST_USE, ProductStage.IDLE, ProductStage.STOPPED, ProductStage.FAILURE, ProductStage.RECOVERY} else ''}>Start Chosen Session</button>
        </form>
        <details><summary>Exactly what Mario support is available</summary>{_capability_list(view)}</details>
        <p class="meta">Retry never duplicates an active session. A launch error remains visible until you retry or resolve it.</p>
      </section>'''


def _capability_list(view: ProductSessionView) -> str:
    return '<div class="capability-grid" data-testid="mario-capabilities">' + "".join(
        f'''<article class="capability-item {'available' if item.available else 'unavailable'}" data-capability="{_esc(item.capability_id)}"><strong>{_esc(item.label)}</strong><span class="status-pill">{'Available' if item.available else 'Unavailable'}</span><p>{_esc(item.summary)}</p>{f'<p class="meta">Why: {_esc(item.unavailable_reason or "Unavailable")}</p>' if not item.available else ''}{f'<p class="meta">Supported: {_esc(", ".join(item.supported_scope))}</p>' if item.supported_scope else ''}</article>'''
        for item in view.capabilities
    ) + "</div>"


def _product_overview_panel(
    view: ProductSessionView,
    snapshot: LiveObservationSnapshot | None,
    objective_view: ObjectiveView,
    *,
    csrf_token: str | None,
) -> str:
    current = snapshot or LiveObservationSnapshot(
        None, ConnectionState.IDLE, Freshness.UNKNOWN, "No visible Mario session is connected."
    )
    selected = objective_view.selected
    progress = objective_view.progress
    requirements = progress.requirements if progress else ()
    remaining = sum(item.state.value != "completed" for item in requirements)
    elapsed = (
        current.samples[-1].frame - current.samples[0].frame
        if len(current.samples) >= 2
        else None
    )
    next_action = (
        "Take control immediately or watch the declared stop point."
        if current.control_owner == "agent"
        else "Wait for neutral input and confirmed handback."
        if current.control_state == "neutralizing"
        else "Ask for advice, start a separate demonstration, or review Do preflight."
        if current.tell_ready
        else "Start or reconnect a visible Mario observation."
    )
    reclaim = (
        f'''<form method="post" action="/takeover-reclaim" class="persistent-reclaim" data-testid="persistent-reclaim"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><button type="submit" class="take-control">Take Control Now</button><span>Companion is playing · input stops before handback.</span></form>'''
        if current.control_owner == "agent"
        else ""
    )
    return f'''
      <section class="session-card product-overview" data-testid="player-workspace-summary" data-product-stage="{_esc(view.stage.value)}">
        <div class="section-title"><div><h2>Super Mario Bros. 3</h2><p class="selected-mode">{_esc(view.stage.value.replace('_', ' ').title())}</p></div><span class="status-pill">{'Companion is playing' if current.control_owner == 'agent' else 'You control the game'}</span></div>
        {reclaim}
        <dl class="live-summary">
          <div><dt>Connection</dt><dd>{_esc(current.state.value.replace('_', ' ').title())}</dd></div>
          <div><dt>Input owner</dt><dd>{_esc(current.control_owner.title())}</dd></div>
          <div><dt>World / level / checkpoint</dt><dd>{_esc(current.checkpoint or 'Unknown')}</dd></div>
          <div><dt>Observation</dt><dd>{_esc(current.freshness.value.title())}{f' · {current.age_seconds:.1f}s old' if current.age_seconds is not None else ''}</dd></div>
          <div><dt>Objective</dt><dd>{_esc(selected.name if selected else 'Choose after a supported checkpoint')}</dd></div>
          <div><dt>Progress</dt><dd>{len(requirements) - remaining}/{len(requirements)} requirements · {remaining} remaining</dd></div>
          <div><dt>Run timing</dt><dd>{f'{elapsed} observed frames' if elapsed is not None else 'Starts with a compatible run boundary'}</dd></div>
          <div><dt>Comparison</dt><dd>{_esc(objective_view.comparison.reason)}</dd></div>
          <div><dt>Continuity</dt><dd>{'Resumed same verified product session' if view.resumable_session_id else 'No prior session authority restored'}</dd></div>
          <div><dt>Evidence status</dt><dd>Local classifications retained · final validation deferred</dd></div>
        </dl>
        <p class="callout"><strong>Next:</strong> {_esc(next_action)}</p>
        <nav class="mode-grid" aria-label="Player help modes"><a href="#live">Observe</a><a href="#objective">Tell</a><a href="#show">Show</a><a href="#live">Do</a><a href="#history">History</a></nav>
      </section>'''


def _recovery_panel(view: ProductSessionView, *, csrf_token: str | None) -> str:
    recovery = view.current_failure
    if recovery is None:
        return ""
    return f'''
      <section class="session-card recovery-card" data-testid="product-recovery" role="alert">
        <div class="section-title"><h2>{_esc(recovery.title)}</h2><span class="status-pill">Fail closed</span></div>
        <p>{_esc(recovery.what_happened)}</p>
        <dl class="fact-grid"><div><dt>Game may still be running</dt><dd>{_yes_no(recovery.game_may_be_running)}</dd></div><div><dt>Input owner</dt><dd>{_esc(recovery.input_owner.title())}</dd></div><div><dt>Agent input stopped</dt><dd>{_yes_no(recovery.agent_input_stopped)}</dd></div><div><dt>Evidence retained</dt><dd>{_yes_no(recovery.evidence_retained)}</dd></div><div><dt>Retry</dt><dd>{'Creates a fresh attempt' if recovery.retry_creates_fresh_attempt else 'Returns to the existing safe state'}</dd></div></dl>
        <p class="callout"><strong>Safe next action:</strong> {_esc(recovery.safe_next_action)}</p>
        <form method="post" action="/setup-retry"><input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}"><button type="submit">Retry Safely</button></form>
      </section>'''


def _active_workspace(
    session: CompanionSession,
    snapshot: LiveObservationSnapshot | None,
    objective_view: ObjectiveView,
    *,
    csrf_token: str | None,
    learning_snapshot: LearningSnapshot | None = None,
    show_session: ShowSession | None = None,
    show_request: ShowRequest | None = None,
    product_view: ProductSessionView | None = None,
) -> str:
    current_snapshot = snapshot or LiveObservationSnapshot(
        None, ConnectionState.IDLE, Freshness.UNKNOWN, "No live observation."
    )
    current_product = product_view or MarioProductSessionManager().view(
        current_snapshot,
        show_active=False,
        has_compatible_profile=objective_view.selected is not None,
        has_accepted_reference=objective_view.reference is not None,
        candidate_review_available=False,
    )
    return (
        _first_use_panel(current_product, csrf_token=csrf_token)
        + _recovery_panel(current_product, csrf_token=csrf_token)
        + _product_overview_panel(
            current_product,
            snapshot,
            objective_view,
            csrf_token=csrf_token,
        )
        + _live_observation_panel(
            snapshot,
            csrf_token=csrf_token,
            goal_id=session.goal.goal_id,
        )
        + _objective_panel(
            objective_view,
            csrf_token=csrf_token,
            learning_snapshot=learning_snapshot,
        )
        + _show_panel(show_session, show_request=show_request, csrf_token=csrf_token)
        + _learning_panel(
            learning_snapshot or LearningSnapshot((), (), (), (), (), (), (), (), ()),
            objective_view,
            csrf_token=csrf_token,
        )
    )


def render_safe_stardew_workspace() -> str:
    contract = load_stardew_contract()
    capabilities = {
        str(item["id"]): str(item["status"])
        for item in contract.get("capabilities", ())
    }
    return render_stardew_operator(
        OperatorView(
            lifecycle=OperatorLifecycle.UNCONFIGURED,
            save=None,
            window=None,
            input_owner=InputOwner.NONE,
            ledger=None,
            energy=None,
            can_units=None,
            failure=None,
            evidence_status="not started",
            capability_status=capabilities,
            current_mode="Observe",
            availability_reason="Configure a verified disposable save copy and a visible screen observation in the standalone Stardew flow.",
            observation_freshness="unknown",
            neutralization_status="neutral",
            handback_status="player ownership required before active modes",
        )
    )


def render_experimental_onboarding(
    *,
    csrf_token: str,
    message: object | None = None,
) -> str:
    installed = installation_status(default_install_root())
    installed_rows = "".join(
        f'''<article class="adapter-row" data-testid="installed-experimental-adapter"><div><strong>{_esc(str(item["adapter_id"]))}</strong><br><span>Experimental · installed · live-unproven · integrity {_esc(str(item["integrity"]))}</span></div><form method="post" action="/adapter-remove"><input type="hidden" name="csrf_token" value="{_esc(csrf_token)}"><input type="hidden" name="adapter_id" value="{_esc(str(item["adapter_id"]))}"><button class="danger" type="submit">Remove safely</button></form></article>'''
        for item in installed
    ) or '<p class="empty">No Experimental adapters are locally installed.</p>'
    result = (
        f'<section class="result" role="status" data-testid="onboarding-result"><h2>Latest result</h2><pre>{_esc(json.dumps(message, indent=2, sort_keys=True, default=str))}</pre></section>'
        if message is not None
        else ""
    )
    steps = (
        ("1", "Metadata", "Choose a non-reserved adapter ID, display name, game identity, version, and Experimental status."),
        ("2", "Detection", "Declare executable names, visible-window matching, and process/window/session continuity. Paths and commands are refused."),
        ("3", "Observation", "Declare a local read-only screen or accessibility envelope with freshness, facts, unknowns, and source."),
        ("4", "Input", "Name ordinary host-allowlisted actions only. Generated executable code and command dispatch are unavailable."),
        ("5", "Safety", "Player ownership, fresh same-process authorization, immediate reclaim, neutral handback, protected actions, and fail-closed ambiguity are required."),
        ("6", "Goals", "Define measurable fact/operator/value requirements and evidence fields."),
        ("7", "Capabilities", "Mark each capability declared or unsupported. Declared never means live-proven."),
        ("8", "Fixtures", "Provide only the bounded observation, neutral-input, reclaim, and goal fixtures."),
        ("9", "Scaffold review", "Inspect deterministic YAML, JSON, and README files beneath the Experimental scaffold root."),
        ("10", "Conformance", "Check schema, provider truth, envelopes, capability agreement, ownership, safety, goals, isolation, integrity, removal, labels, and core independence."),
        ("11", "Installation", "Install atomically with exact inventory and hashes; collisions and overwrites are refused."),
        ("12", "Removal", "Remove exact manifest-owned unmodified files only after zero process, authority, input, and session state is proven; evidence/history remain."),
    )
    step_html = "".join(f'<article class="step"><span>{number}</span><div><h2>{title}</h2><p>{description}</p></div></article>' for number, title, description in steps)
    limits = "".join(f"<li>{_esc(item)}</li>" for item in EXPERIMENTAL_PROOF_LIMITS)
    return _page(
        title="Game Companion — New Game Onboarding",
        csrf_token=csrf_token,
        body=f'''
        <style>
          .onboarding{{max-width:1160px;margin:auto;padding:20px}}.onboarding header{{background:var(--navy);color:#fff;border-radius:12px;padding:22px}}.onboarding header p{{color:#dbeafe}}.state-key,.steps,.actions{{display:grid;gap:12px;margin:16px 0}}.state-key{{grid-template-columns:repeat(6,minmax(0,1fr))}}.state-key span,.step,.action-card,.installed,.result,.proof-limits{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px}}.steps{{grid-template-columns:repeat(2,minmax(0,1fr))}}.step{{display:grid;grid-template-columns:34px 1fr;gap:10px}}.step>span{{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;background:var(--navy);color:#fff;font-weight:800}}.step h2{{font-size:17px;margin:0}}.step p{{margin:5px 0 0}}.actions{{grid-template-columns:repeat(3,minmax(0,1fr))}}.action-card form{{display:grid;gap:8px}}.adapter-row{{display:flex;justify-content:space-between;gap:10px;align-items:center;border-top:1px solid var(--line);padding:10px 0}}.adapter-row:first-of-type{{border-top:0}}.danger{{background:#9b2c2c}}pre{{max-height:360px}}@media(max-width:760px){{.onboarding{{padding:10px}}.state-key{{grid-template-columns:repeat(2,1fr)}}.steps,.actions{{grid-template-columns:1fr}}}}@media(max-width:390px){{.onboarding{{padding:6px}}.state-key{{grid-template-columns:1fr}}.step,.action-card,.installed,.proof-limits{{padding:11px}}.adapter-row{{align-items:stretch;flex-direction:column}}input,button{{width:100%}}}}
        </style>
        <div class="onboarding" data-testid="experimental-onboarding">
          <header><p class="eyebrow">V2.14 · local contributor kit</p><h1>New Game Onboarding</h1><p>Create a declarative fixture-only scaffold, inspect its truth, run local conformance, install it as Experimental, or remove only what its manifest owns.</p><nav><a class="secondary-button nav-link" href="/">Catalog</a> <a class="secondary-button nav-link" href="/lab">Lab</a></nav></header>
          <main>
          <section class="state-key" aria-label="Adapter states"><span>Declared</span><span>Conformant</span><span>Live-unproven</span><span>Unsupported</span><span>Scaffolded</span><span>Installed</span></section>
          {result}
          <section class="steps" aria-label="Onboarding steps">{step_html}</section>
          <section class="actions">
            <article class="action-card"><h2>Generate scaffold</h2><form method="post" action="/adapter-scaffold"><input type="hidden" name="csrf_token" value="{_esc(csrf_token)}"><label>Adapter ID<input name="adapter_id" required pattern="[a-z][a-z0-9-]*" placeholder="my-game"></label><label>Display name<input name="display_name" required placeholder="My Game"></label><button type="submit">Create bounded scaffold</button></form></article>
            <article class="action-card"><h2>Validate, inspect, and conform</h2><form method="post" action="/adapter-validate"><input type="hidden" name="csrf_token" value="{_esc(csrf_token)}"><label>Scaffolded adapter ID<input name="adapter_id" required></label><button type="submit">Validate contract</button></form><form method="post" action="/adapter-inspect"><input type="hidden" name="csrf_token" value="{_esc(csrf_token)}"><label>Scaffolded adapter ID<input name="adapter_id" required></label><button type="submit">Inspect declared truth</button></form><form method="post" action="/adapter-conformance"><input type="hidden" name="csrf_token" value="{_esc(csrf_token)}"><label>Scaffolded adapter ID<input name="adapter_id" required></label><button type="submit">Run fixture conformance</button></form></article>
            <article class="action-card"><h2>Install</h2><form method="post" action="/adapter-install"><input type="hidden" name="csrf_token" value="{_esc(csrf_token)}"><label>Conformant adapter ID<input name="adapter_id" required></label><button type="submit">Install as Experimental</button></form><p>Atomic manifest-owned install. No support promotion and no shared-core game-ID edit.</p></article>
          </section>
          <section class="installed"><h2>Installed Experimental adapters</h2>{installed_rows}</section>
          <section class="proof-limits"><h2>What conformance cannot prove</h2><ul>{limits}</ul><p><strong>Experimental providers cannot promote themselves to Supported.</strong> Mario and Stardew remain explicit trusted built-ins.</p></section>
          </main>
        </div>''',
    )


def render_combined_catalog(
    session: CatalogSession,
    *,
    csrf_token: str | None = None,
) -> str:
    selected_id = session.selected_adapter_id
    selected = session.registry.entry(selected_id) if selected_id else None
    runtime = session.registry.provider(selected_id).runtime_state() if selected_id else None
    recovery = session.store.recovery_reason
    compact_catalog = bool(session.preferences.display.get("compact_catalog", False))
    catalog_expanded = bool(session.preferences.display.get("catalog_expanded", False))
    cards = "".join(
        _catalog_card(
            entry,
            selected=entry.adapter_id == selected_id,
            switching=selected_id is not None,
            expanded=catalog_expanded,
        )
        for entry in session.registry.entries
    )
    workspace = (
        f'<section class="catalog-workspace" data-testid="selected-game-workspace" '
        f'data-adapter-id="{_esc(selected.adapter_id)}">'
        f'<div class="section-title"><div><p class="eyebrow">Selected game</p><h2>{_esc(selected.display_name)}</h2></div>'
        f'<a class="secondary-button nav-link" href="{_esc(selected.standalone_surface)}" target="_top">Open standalone surface</a></div>'
        f'<dl class="catalog-runtime"><div><dt>Input owner</dt><dd>{_esc(runtime.input_owner)}</dd></div>'
        f'<div><dt>Active mode</dt><dd>{_esc(runtime.active_mode or "none")}</dd></div>'
        f'<div><dt>Neutralization</dt><dd>{"pending" if runtime.pending_neutralization else "neutral"}</dd></div>'
        f'<div><dt>Handback</dt><dd>{"confirmed" if runtime.handback_confirmed else "unconfirmed"}</dd></div></dl>'
        f'<p class="callout">A game switch is allowed only after active Show/Do/input stops, input is neutral, player handback is confirmed, evidence is retained, and continuity is known. The new adapter requires a fresh observation.</p>'
        f'<p><strong>Recovery guidance:</strong> {_esc(selected.recovery_guidance)}</p>'
        f'<p><a class="primary-button nav-link" href="{_esc(selected.standalone_surface)}">Enter {_esc(selected.display_name)} workspace</a></p></section>'
        if selected and runtime
        else '<section class="catalog-empty" data-testid="safe-catalog-only"><h2>Select a game</h2><p>No game observation or authority is active. Choose an adapter to enter its existing player workspace.</p></section>'
    )
    recovery_panel = (
        f'<section class="catalog-recovery" role="alert" data-testid="catalog-recovery"><h2>Safe catalog recovery</h2><p>{_esc(recovery)}</p><p>Persisted selection was ignored. Player ownership is the default and every active mode remains disabled.</p></section>'
        if recovery
        else ""
    )
    preference_form = (
        f'<form class="catalog-preferences" method="post" action="/catalog-preferences">'
        f'<label class="inline-check"><input type="checkbox" name="compact_catalog" value="true" {"checked" if compact_catalog else ""}> Compact catalog</label>'
        f'<label class="inline-check"><input type="checkbox" name="catalog_expanded" value="true" {"checked" if catalog_expanded else ""}> Keep catalog details expanded</label>'
        f'<button type="submit">Save display preferences</button></form>'
        if selected_id
        else ""
    )
    return _page(
        title="Game Companion",
        csrf_token=csrf_token,
        body=f"""
        <style>
          .catalog-shell{{max-width:1320px;margin:auto;padding:20px}}.catalog-header{{display:flex;justify-content:space-between;gap:18px;align-items:center;padding:20px;background:var(--navy);color:#fff;border-radius:12px}}.catalog-header p{{margin:0;color:#dbeafe}}.catalog-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:14px 0}}.catalog-grid.compact .catalog-card details{{display:none}}.catalog-card,.catalog-workspace,.catalog-empty,.catalog-recovery,.catalog-preferences{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px;box-shadow:0 8px 22px rgba(31,41,55,.07)}}.catalog-card.selected{{border:2px solid var(--navy)}}.catalog-card h2{{font-size:20px}}.catalog-card details{{border-top:1px solid var(--line);padding-top:9px;margin-top:9px}}.catalog-card ul{{padding-left:20px}}.catalog-capabilities{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}}.catalog-capability{{min-width:0;overflow-wrap:anywhere;border:1px solid var(--line);border-radius:8px;padding:9px;background:var(--surface-alt)}}.catalog-capability .status-pill{{max-width:100%;white-space:normal;overflow-wrap:anywhere}}.catalog-card form button{{width:100%}}.catalog-runtime{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}}.catalog-runtime div{{border-top:1px solid var(--line);padding-top:7px}}.catalog-recovery{{border-color:#e8b3ae;background:var(--red-soft)}}.catalog-preferences{{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:14px}}.catalog-preferences input{{width:auto}}
          @media(max-width:700px){{.catalog-shell{{padding:10px}}.catalog-header{{align-items:flex-start;flex-direction:column}}.catalog-grid{{grid-template-columns:1fr}}.catalog-runtime{{grid-template-columns:repeat(2,minmax(0,1fr))}}.catalog-workspace{{padding:10px}}}}
          @media(max-width:390px){{.catalog-capabilities,.catalog-runtime{{grid-template-columns:1fr}}.catalog-card,.catalog-empty,.catalog-recovery{{padding:12px}}}}
        </style>
        <div class="catalog-shell" data-testid="combined-companion-catalog" data-selected-adapter="{_esc(selected_id or '')}">
          <header class="catalog-header"><div><p class="eyebrow">Local multi-game companion</p><h1>Game Companion</h1><p>Adapter-owned help and explicit player-controlled handoff.</p></div><a class="secondary-button nav-link" href="/lab">Engineering Lab</a></header>
          {recovery_panel}
          <main>{preference_form}<section aria-labelledby="games-heading"><div class="section-title"><div><p class="eyebrow">Trusted built-ins and locally installed Experimental adapters</p><h2 id="games-heading">Choose the adapter whose truth you want to use</h2></div><span class="status-pill">{len(session.registry.entries)} adapters</span></div><div class="catalog-grid{' compact' if compact_catalog else ''}">{cards}</div></section>{workspace}<p><a class="secondary-button nav-link" href="/onboarding">Onboard an Experimental game</a></p></main>
        </div>
        """,
    )


def _catalog_card(
    entry: AdapterCatalogEntry,
    *,
    selected: bool,
    switching: bool,
    expanded: bool,
) -> str:
    modes = ""
    for item in entry.capabilities:
        reason = f'<p class="meta">{_esc(item.unavailable_reason)}</p>' if item.unavailable_reason else ""
        modes += (
            f'<div class="catalog-capability" data-capability="{_esc(item.capability_id)}">'
            f'<strong>{_esc(item.label)}</strong><br><span class="status-pill">'
            f'{_esc(item.status.replace("_", " "))}</span><p>{_esc(item.summary)}</p>{reason}</div>'
        )
    goals = "".join(f'<li><strong>{_esc(item.label)}</strong> — {_esc(item.summary)}</li>' for item in entry.goals)
    profiles = "".join(f'<li><strong>{_esc(item.label)}</strong> · {_esc(item.profile_type)} — {_esc(item.summary)}</li>' for item in entry.profiles)
    scopes = "".join(f'<li><strong>{_esc(item.label)}</strong> — stop on {_esc(", ".join(item.stop_conditions))}</li>' for item in entry.scopes)
    if selected:
        button = '<button disabled aria-disabled="true">Selected</button>'
    else:
        disabled = 'disabled aria-disabled="true"' if entry.availability == "unavailable" else ""
        button = (
            f'<form method="post" action="/catalog-switch"><input type="hidden" '
            f'name="adapter_id" value="{_esc(entry.adapter_id)}"><button type="submit" '
            f'{disabled}>{"Switch to" if switching else "Select"} {_esc(entry.display_name)}</button></form>'
        )
    return f"""
      <article class="catalog-card{' selected' if selected else ''}" data-testid="catalog-card" data-adapter-id="{_esc(entry.adapter_id)}" data-game-id="{_esc(entry.game_id)}">
        <div class="section-title"><div><p class="eyebrow">{_esc(entry.adapter_id)} · {_esc(entry.adapter_version)}</p><h2>{_esc(entry.display_name)}</h2></div><span class="status-pill">{_esc(entry.availability.replace('_', ' '))}</span></div>
        <p>{_esc(entry.description)}</p><p class="callout"><strong>{_esc(entry.implementation_status)}</strong><br><strong>Setup:</strong> {_esc(entry.setup_state)}<br>{_esc(entry.availability_reason)}</p>
        <h3>Tell, Show, and Do</h3><div class="catalog-capabilities">{modes}</div>
        <details {'open' if expanded else ''}><summary>Observation, goals, and solution profiles</summary><p><strong>{_esc(entry.observation.label)}:</strong> {_esc(entry.observation.trust_boundary)}</p><h3>Goals</h3><ul>{goals}</ul><h3>Profiles</h3><ul>{profiles}</ul></details>
        <details><summary>Takeover, stop, and safety</summary><ul>{scopes}</ul><p><strong>Stop behavior:</strong> {_esc(entry.safety.stop_behavior)}</p><p><strong>Safety:</strong> {_esc(entry.safety.summary)}</p><ul>{''.join(f'<li>{_esc(item)}</li>' for item in entry.safety.protected_decisions)}</ul><p><strong>Reclaim:</strong> {_esc(entry.safety.reclaim_behavior)}</p><p><strong>Handback:</strong> {_esc(entry.safety.handback_behavior)}</p></details>
        <details><summary>Evidence and recovery</summary><p><strong>Namespace:</strong> <code>{_esc(entry.evidence.namespace)}</code></p><p>{_esc(', '.join(entry.evidence.classifications))}</p><p>{_esc(entry.evidence.trust_boundary)}</p><p><strong>Recovery:</strong> {_esc(entry.recovery_guidance)}</p></details>
        {button}
      </article>"""


def render_companion_ui(
    session: CompanionSession,
    *,
    tell_card: TellCard | None = None,
    csrf_token: str | None = None,
    tell_unavailable_reason: str | None = None,
    selected_checkpoint: str | None = None,
    selected_spoiler: SpoilerLevel = SpoilerLevel.GUIDED,
    show_session: ShowSession | None = None,
    show_request: ShowRequest | None = None,
    live_snapshot: LiveObservationSnapshot | None = None,
    objective_view: ObjectiveView | None = None,
    learning_snapshot: LearningSnapshot | None = None,
    product_view: ProductSessionView | None = None,
) -> str:
    session.validate()
    observation = session.observation
    observed_time = (
        observation.observed_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        if observation.observed_at
        else "Not observed"
    )
    confidence = (
        f"{observation.confidence:.0%}" if observation.confidence is not None else "Unknown"
    )
    evidence = observation.evidence_references or ("No trusted evidence reference",)
    lifecycle = session.lifecycle.value.replace("_", " ").title()
    takeover_reason = (
        "Request input stop and return control to you."
        if session.can_take_control
        else "Available only while a Show or Do session is active or stopping."
    )
    source_label = (
        observation.source.value.replace("_", " ").title()
        if observation.source
        else "Not connected"
    )
    observation_callout = (
        "Player-reported current context is eligible for advisory Tell only. Show and Do require stronger observation."
        if observation.source is ObservationSource.PLAYER
        else "The adapter can verify a fresh separate-process start for Show. This is not an observation of your active game."
        if any(reference.startswith("adapter-verifiable:fresh-process") for reference in observation.evidence_references)
        else "This is your live player-controlled session. Companion is observing only."
        if observation.source is ObservationSource.ADAPTER and observation.trusted
        else "Observation is trusted for bounded actions."
        if observation.trusted
        else "No trusted current observation. Show and Do are disabled until state is refreshed and verified."
    )
    tell_panel = _tell_panel(
        session,
        tell_card=tell_card,
        csrf_token=csrf_token,
        unavailable_reason=tell_unavailable_reason,
        selected_checkpoint=selected_checkpoint,
        selected_spoiler=selected_spoiler,
    )
    current_objective = objective_view or ObjectiveSessionManager().view(
        live_snapshot
        or LiveObservationSnapshot(None, ConnectionState.IDLE, Freshness.UNKNOWN, "No live observation.")
    )
    active_workspace = _active_workspace(
        session,
        live_snapshot,
        current_objective,
        csrf_token=csrf_token,
        learning_snapshot=learning_snapshot or LocalLearningStore().snapshot(),
        show_session=show_session,
        show_request=show_request,
        product_view=product_view,
    )
    return _page(
        title="Game Companion — Mario",
        body=f"""
        <div class="companion-shell" data-testid="companion-shell" data-session-state="{_esc(session.lifecycle.value)}">
          <header class="companion-top">
            <div>
              <p class="eyebrow">Local player session</p>
              <h1>Game Companion</h1>
              <p>Live Mario coaching.</p>
            </div>
            <nav aria-label="Game Companion views" data-testid="lab-navigation">
              <a class="secondary-button nav-link" href="/lab">Open Game Companion Lab</a>
            </nav>
          </header>

          <main class="companion-main">
            <div id="active-workspace" class="active-workspace">
              {active_workspace}
            </div>
            {_player_session_history_panel()}
            <details class="session-more" data-testid="more-companion-tools">
              <summary>More tools and technical evidence</summary>
              <div class="companion-more-grid">
            <section class="session-card identity-card" data-testid="game-identity">
              <div class="section-title"><h2>Game &amp; objective</h2><span class="status-pill">{_esc(session.adapter.status)}</span></div>
              <p class="game-name">{_esc(session.adapter.game_name)}</p>
              <p>{_esc(session.adapter.adapter_name)} · <code>{_esc(session.adapter.adapter_id)}</code></p>
              <h3>{_esc(session.goal.name)}</h3>
              <p>{_esc(session.goal.objective)}</p>
              <p class="meta">Goal contract: <code>{_esc(session.goal.goal_id)}</code></p>
            </section>

            <section class="session-card observation-card status-{_esc(observation.freshness.value)}" data-testid="observed-state">
              <div class="section-title"><h2>Observed state</h2><span class="status-pill">{_esc(observation.freshness.value.title())}</span></div>
              <dl class="fact-grid">
                <div><dt>Checkpoint / location</dt><dd>{_esc(observation.checkpoint or 'Unknown — refresh required')}</dd></div>
                <div><dt>Observed</dt><dd>{_esc(observed_time)}</dd></div>
                <div><dt>Confidence</dt><dd>{_esc(confidence)}</dd></div>
                <div><dt>Evidence</dt><dd>{'<br>'.join(_esc(item) for item in evidence)}</dd></div>
                <div data-testid="observation-source"><dt>Observation source</dt><dd>{_esc(source_label)}</dd></div>
              </dl>
              <p class="callout">{_esc(observation_callout)}</p>
            </section>

            <section class="session-card modes-card" aria-labelledby="modes-heading">
              <div class="section-title"><h2 id="modes-heading">Choose help</h2><span>Capability-aware</span></div>
              <div class="mode-grid">{''.join(_companion_mode(mode) for mode in session.modes)}</div>
            </section>

            {tell_panel}

            <section class="session-card safety-card">
              <div class="section-title"><h2>Scope &amp; safety</h2><span class="status-pill">{'Authorized' if session.safety.authorized else 'Not authorized'}</span></div>
              <div data-testid="stop-point"><h3>Declared stop point</h3><p>{_esc(session.safety.stop_point or 'Missing — execution is blocked')}</p></div>
              <div data-testid="protected-decisions"><h3>Protected decisions</h3><ul>{''.join(f'<li>{_esc(item)}</li>' for item in session.safety.protected_decisions)}</ul></div>
              <h3>Recovery / retry boundary</h3><p>{_esc(session.safety.recovery_boundary)}</p>
            </section>

            <section class="session-card activity-card" data-testid="activity">
              <div class="section-title"><h2>Activity</h2><span class="status-pill">{_esc(lifecycle)}</span></div>
              <ol class="activity-list">{''.join(f'<li>{_esc(item)}</li>' for item in session.activity) or '<li>No activity yet.</li>'}</ol>
              <button type="button" class="take-control" data-testid="take-control" {'disabled aria-disabled="true"' if not session.can_take_control else ''}>Take Control</button>
              <p class="meta">{_esc(takeover_reason)}</p>
              <p class="meta">Input stopped: {_yes_no(session.input_stopped)} · Control returned: {_yes_no(session.control_returned)}</p>
            </section>

            {_handoff_panel(session)}
              </div>
            </details>
          </main>
          <script src="/assets/player-workspace.js" defer></script>
        </div>
        """,
    )


def _player_tell_from_form(
    data: dict[str, list[str]],
) -> tuple[CompanionSession, TellCard]:
    goal_id = _single(data, "goal_id", default=ACTIVE_PRODUCT_GOAL_ID)
    if goal_id not in _product_goal_ids():
        raise TellValidationError("unsupported selected goal")
    contract = load_goal_contract(resolve_goal_path(goal_id))
    checkpoint_id = _single(data, "checkpoint_id", default="")
    if checkpoint_id not in contract.segments:
        raise TellValidationError("checkpoint is not part of the selected goal")
    catalog = load_segment_catalog(contract.catalog_path)
    segment = catalog.by_id[checkpoint_id]
    if _single(data, "checkpoint_confirmed", default="") != "true":
        raise TellValidationError("confirm the current checkpoint before requesting Tell")
    spoiler = _spoiler_from_value(_single(data, "spoiler_level", default="guided"))
    allowed_protections = {
        "preserve_warp_whistles",
        "preserve_p_wing",
        "preserve_super_leaf",
        "preserve_super_mushroom",
    }
    supplied = set(data.get("protected_decisions", ()))
    if not supplied.issubset(allowed_protections):
        raise TellValidationError("unsupported protected-decision value")
    observation = Observation(
        checkpoint=segment.name,
        checkpoint_id=checkpoint_id,
        source=ObservationSource.PLAYER,
        game_id=contract.game,
        observed_at=datetime.now(timezone.utc),
        freshness=Freshness.FRESH,
        confidence=1.0,
        evidence_references=(),
    )
    facts = [ObservedFact("checkpoint_confirmed", "true", ObservationSource.PLAYER)]
    bounded_facts = {
        "warp_whistle_count": {"0", "1", "2"},
        "p_wing_available": {"true", "false"},
        "super_leaf_available": {"true", "false"},
        "super_mushroom_available": {"true", "false"},
    }
    for fact_id, allowed_values in bounded_facts.items():
        value = _single(data, fact_id, default="unknown")
        if value == "unknown":
            continue
        if value not in allowed_values:
            raise TellValidationError(f"unsupported observed fact value: {fact_id}")
        facts.append(ObservedFact(fact_id, value, ObservationSource.PLAYER))
    request = TellRequest(
        game_id=contract.game,
        goal=contract,
        observation=observation,
        facts=tuple(facts),
        spoiler_level=spoiler,
        protected_decisions=tuple(sorted(supplied)),
    )
    card = generate_tell_card(request)
    base = default_companion_session(goal_id)
    session = replace(
        base,
        observation=observation,
        modes=(
            ModeCapability("tell", True, "Explain the next useful actions from this current player-reported checkpoint."),
            ModeCapability("show", False, "Demonstrate one approved section and retain review evidence.", "Show is a separate fresh demonstration and does not use player-reported state."),
            ModeCapability("do", False, "Complete one authorized checkpoint-bounded objective.", "Live-session takeover remains unavailable until V2.6."),
        ),
        activity=("Player reported and confirmed the current checkpoint.", "Grounded Tell card generated; no game input was sent."),
    )
    session.validate()
    return session, card


def _live_tell(
    snapshot: LiveObservationSnapshot,
    goal_id: str,
    data: dict[str, list[str]],
) -> tuple[CompanionSession, TellCard]:
    if goal_id not in _product_goal_ids():
        raise TellValidationError("unsupported selected goal")
    if not snapshot.tell_ready:
        raise TellValidationError(
            f"live Tell unavailable: {snapshot.tell_unavailable_reason}"
        )
    contract = load_goal_contract(resolve_goal_path(goal_id))
    if snapshot.checkpoint_id not in contract.segments:
        raise TellValidationError("live checkpoint is not part of the selected goal")
    allowed_protections = {
        "preserve_warp_whistles",
        "preserve_p_wing",
        "preserve_super_leaf",
        "preserve_super_mushroom",
    }
    supplied = set(data.get("protected_decisions", ()))
    if not supplied.issubset(allowed_protections):
        raise TellValidationError("unsupported protected-decision value")
    request = TellRequest(
        game_id=contract.game,
        goal=contract,
        observation=snapshot.observation(),
        facts=snapshot.tell_facts(),
        spoiler_level=_spoiler_from_value(
            _single(data, "spoiler_level", default="guided")
        ),
        protected_decisions=tuple(sorted(supplied)),
    )
    card = generate_tell_card(request)
    base = default_companion_session(goal_id, live_snapshot=snapshot)
    session = replace(
        base,
        activity=(
            "Fresh adapter-observed live state was used for Tell.",
            "Grounded Tell card generated; no game input was sent.",
        ),
    )
    session.validate()
    return session, card


def _spoiler_from_value(value: str) -> SpoilerLevel:
    try:
        return SpoilerLevel(value)
    except ValueError as exc:
        raise TellValidationError("unsupported spoiler level") from exc


def _tell_panel(
    session: CompanionSession,
    *,
    tell_card: TellCard | None,
    csrf_token: str | None,
    unavailable_reason: str | None,
    selected_checkpoint: str | None,
    selected_spoiler: SpoilerLevel,
) -> str:
    contract = load_goal_contract(resolve_goal_path(session.goal.goal_id))
    catalog = load_segment_catalog(contract.catalog_path)
    options = "".join(
        f"<option value=\"{_esc(segment_id)}\" "
        f"{'selected' if segment_id == selected_checkpoint else ''}>"
        f"{_esc(catalog.by_id[segment_id].name)}</option>"
        for segment_id in contract.segments
    )
    spoiler_options = "".join(
        f"<option value=\"{level.value}\" "
        f"{'selected' if level is selected_spoiler else ''}>"
        f"{level.value.title()}</option>"
        for level in SpoilerLevel
    )
    reason = unavailable_reason or (
        "Choose and confirm your current checkpoint. This context will be labeled player-reported."
        if tell_card is None
        else ""
    )
    card_html = _render_tell_card(tell_card) if tell_card else (
        f'<p class="callout" data-testid="tell-unavailable-reason">{_esc(reason)}</p>'
    )
    return f"""
      <section class="session-card tell-request-card" data-testid="tell-request">
        <div class="section-title"><h2>Tell me what to do next</h2><span class="status-pill">Advisory only</span></div>
        <form method="post" action="/tell">
          <input type="hidden" name="csrf_token" value="{_esc(csrf_token or '')}">
          <input type="hidden" name="goal_id" value="{_esc(contract.id)}">
          <label>Current checkpoint (player-reported)
            <select name="checkpoint_id" required>{options}</select>
          </label>
          <label data-testid="spoiler-selection">Spoiler level
            <select name="spoiler_level">{spoiler_options}</select>
          </label>
          <fieldset data-testid="observed-facts">
            <legend>Current inventory facts (player-reported)</legend>
            <label>Warp Whistles
              <select name="warp_whistle_count"><option value="unknown">Unknown</option><option value="0">0</option><option value="1">1</option><option value="2">2</option></select>
            </label>
            <label>P-Wing available
              <select name="p_wing_available"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select>
            </label>
            <label>Super Leaf available
              <select name="super_leaf_available"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select>
            </label>
            <label>Super Mushroom available
              <select name="super_mushroom_available"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select>
            </label>
          </fieldset>
          <fieldset data-testid="protected-decision-acknowledgement">
            <legend>Decisions Companion must protect</legend>
            <label><input type="checkbox" name="protected_decisions" value="preserve_warp_whistles"> Preserve Warp Whistles</label>
            <label><input type="checkbox" name="protected_decisions" value="preserve_p_wing"> Preserve the P-Wing</label>
            <label><input type="checkbox" name="protected_decisions" value="preserve_super_leaf"> Preserve Super Leaves</label>
            <label><input type="checkbox" name="protected_decisions" value="preserve_super_mushroom"> Preserve the Super Mushroom</label>
          </fieldset>
          <label><input type="checkbox" name="checkpoint_confirmed" value="true" required> I confirm this is my current checkpoint and understand it is player-reported.</label>
          <button type="submit">Tell</button>
        </form>
        {card_html}
      </section>"""


def _render_tell_card(card: TellCard) -> str:
    protected = card.protected_decisions_honored or ("No additional item decisions protected",)
    return f"""
      <article class="tell-card" data-testid="tell-card">
        <h3>Your next useful actions</h3>
        <p data-testid="current-state-summary"><strong>Companion believes:</strong> {_esc(card.state_summary.text)}</p>
        <p><strong>Selected objective:</strong> {_esc(card.objective.text)}</p>
        <p><strong>Spoiler level:</strong> {_esc(card.spoiler_level.value.title())}</p>
        <ol>{''.join(_tell_step(step, index) for index, step in enumerate(card.steps, 1))}</ol>
        {_tell_items('Resource / risk warnings', card.risks, 'risk-warning')}
        {_tell_items('Recovery guidance', card.recovery, 'recovery-guidance')}
        <div data-testid="protected-decision-acknowledgement"><h4>Protected decisions honored</h4><ul>{''.join(f'<li>{_esc(item)}</li>' for item in protected)}</ul></div>
        <p data-testid="uncertainty"><strong>Uncertainty:</strong> {_esc(card.uncertainty.text)}</p>
        <p data-testid="refresh-requirement"><strong>Refresh requirement:</strong> {_esc(card.refresh_requirement.text)}</p>
      </article>"""


def _tell_step(step: object, index: int) -> str:
    action = getattr(step, "action")
    cue = getattr(step, "expected_cue")
    return f"""
      <li data-testid="tell-step">
        <p>{_esc(action.text)}</p>
        <p data-testid="expected-cue"><strong>Look for:</strong> {_esc(cue.text)}</p>
        {_provenance(action)}
        {_provenance(cue)}
      </li>"""


def _tell_items(title: str, items: tuple[GroundedText, ...], hook: str) -> str:
    if not items:
        return ""
    return f'<div data-testid="{hook}"><h4>{_esc(title)}</h4><ul>' + "".join(
        f'<li>{_esc(item.text)}{_provenance(item)}</li>' for item in items
    ) + "</ul></div>"


def _provenance(item: GroundedText) -> str:
    return '<details data-testid="provenance-reference"><summary>Sources</summary><ul>' + "".join(
        f'<li><code>{_esc(reference.source_class)}</code> · {_esc(reference.record_id)} · {_esc(reference.label)}</li>'
        for reference in item.provenance
    ) + "</ul></details>"


def _companion_mode(mode: ModeCapability) -> str:
    reason = mode.unavailable_reason if not mode.available else "Available from this state."
    return f"""
      <article class="mode-card" data-testid="mode-{_esc(mode.mode)}" data-available="{str(mode.available).lower()}">
        <h3>{_esc(mode.mode.title())}</h3>
        <p>{_esc(mode.explanation)}</p>
        <button type="button" {'disabled aria-disabled="true"' if not mode.available else ''}>{_esc(mode.mode.title())}</button>
        <p class="mode-reason">{_esc(reason or '')}</p>
      </article>"""


def _handoff_panel(session: CompanionSession) -> str:
    outcome = session.outcome
    rows = (
        (
            ("Starting observation", session.observation.checkpoint or "Unknown"),
            ("What was attempted", outcome.attempted),
            ("What changed", outcome.changed),
            ("Resources consumed", outcome.resources_consumed),
            ("Verified outcome", outcome.verified_outcome),
            ("Unresolved uncertainty", outcome.unresolved_uncertainty),
            (
                "Final observed state",
                outcome.final_observation.checkpoint
                if outcome.final_observation and outcome.final_observation.checkpoint
                else "Unknown",
            ),
            ("Input stopped", _yes_no(session.input_stopped)),
            ("Control returned", _yes_no(session.control_returned)),
            (
                "Evidence references",
                ", ".join(outcome.evidence_references) or "None",
            ),
        )
        if outcome
        else (
            ("Starting observation", session.observation.checkpoint or "Unknown"),
            ("What was attempted", "Nothing yet"),
            ("What changed", "Nothing"),
            ("Resources consumed", "None"),
            ("Verified outcome", "No game-owned outcome"),
            ("Unresolved uncertainty", "Current game state is not trusted"),
            ("Final observed state", "Not available"),
            ("Input stopped", _yes_no(session.input_stopped)),
            ("Control returned", _yes_no(session.control_returned)),
            ("Evidence references", "None"),
        )
    )
    return f"""
      <section class="session-card handoff-card state-{_esc(session.lifecycle.value)}" data-testid="handoff">
        <div class="section-title"><h2>Handoff</h2><span>{_esc(session.lifecycle.value.replace('_', ' ').title())}</span></div>
        <dl class="handoff-list">{''.join(f'<div><dt>{_esc(label)}</dt><dd>{_esc(value)}</dd></div>' for label, value in rows)}</dl>
      </section>"""


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def render_lab_ui(
    *,
    goal_id: str = ACTIVE_PRODUCT_GOAL_ID,
    selected_location_id: str | None = None,
    selected_note_id: str | None = None,
    selected_issue_id: str | None = None,
    selected_mode: str | None = None,
    csrf_token: str | None = None,
    learning_snapshot: LearningSnapshot | None = None,
    product_view: ProductSessionView | None = None,
    live_snapshot: LiveObservationSnapshot | None = None,
) -> str:
    if goal_id not in _product_goal_ids():
        raise GoalValidationError(f"Unsupported Game Companion Lab goal: {goal_id}")
    summary = build_control_panel_summary(goal_id)
    last_command = _load_yaml(LAST_COMMAND_PATH)
    locations = _list_dicts(summary.get("locations", []))
    selected = _selected_location(locations, selected_location_id=selected_location_id)
    selected_notes = _notes_for_location(summary, selected)
    selected_issues = _issues_for_location(summary, selected)
    mode = _selected_mode(selected_mode, selected_notes, selected_issues, selected_note_id, selected_issue_id)
    selected_note = _selected_note(selected_notes, selected_note_id)
    selected_issue = _selected_issue(selected_issues, selected_issue_id)
    evidence = _latest_evidence(summary, last_command, selected)
    learning = learning_snapshot or LocalLearningStore().snapshot()
    return _page(
        title="Game Companion Lab — Mario",
        csrf_token=csrf_token,
        body=f"""
        <div class="route-lab">
          <header class="lab-top">
            <div class="lab-title">
              {_asset_icon('leaf_icon.png', 'LAB', 'Route lab local asset')}
              <div>
                <h1>Game Companion Lab</h1>
                <p>Mario adapter · Current session: {_esc(str(summary.get('session_label', 'No active session')))} · {_esc(_goal_subtitle(goal_id))}</p>
              </div>
            </div>
            <a class="secondary-button nav-link" href="/">Player session</a>
            {_goal_switcher(goal_id)}
            {_run_bar(last_command)}
          </header>

          <main class="lab-main">
            <aside class="route-index" aria-label="Route">
              <div class="section-title">
                <h2>Route</h2>
                <p>Observed Mario route state</p>
              </div>
              <nav class="route-list">
                {''.join(_route_item(location, selected, goal_id) for location in locations)}
              </nav>
            </aside>

            {_evidence_viewer(evidence, selected, last_command)}

            {_teaching_panel(selected, selected_notes, selected_issues, mode, selected_note, selected_issue, goal_id)}
          </main>

          <section class="lab-bottom">
            <section class="paper-panel">
              <div class="section-title">
                <h2>Latest Attempt</h2>
              </div>
              {_last_command_panel(last_command)}
            </section>
            <section class="paper-panel">
              <div class="section-title">
                <h2>Active Problems</h2>
              </div>
              <div class="issue-list">
                {''.join(_issue_row(issue, summary, selected) for issue in _sorted_issues(summary, selected)) or '<p class="empty">No active problems yet.</p>'}
              </div>
            </section>
            <section class="paper-panel">
              <div class="section-title">
                <h2>Observation History</h2>
              </div>
              {''.join(_note_row(note, summary, selected) for note in _sorted_notes(summary, selected)) or '<p class="empty">No observations yet.</p>'}
            </section>
            {_learning_engineering_panel(learning)}
            {_scenario_engineering_panel()}
            {_unattended_regression_panel()}
            {_experimental_onboarding_panel()}
            {_product_engineering_panel(product_view, live_snapshot)}
          </section>
        </div>
        """,
    )


def _experimental_onboarding_panel() -> str:
    installed = installation_status(default_install_root())
    rows = "".join(
        f'<li><strong>{_esc(str(item["adapter_id"]))}</strong> · Experimental · installed · live-unproven · integrity {_esc(str(item["integrity"]))}</li>'
        for item in installed
    ) or "<li>No Experimental adapters installed.</li>"
    return f'''
      <section class="paper-panel" id="experimental-onboarding" data-testid="lab-experimental-onboarding">
        <div class="section-title"><div><h2>New Game Onboarding</h2><p>V2.14 contributor and removal surface</p></div><span class="status-pill">Experimental only</span></div>
        <p>Validate contracts, create deterministic scaffolds, inspect provider truth, run fixture conformance, install atomically, inspect integrity, and remove exact manifest-owned files.</p>
        <ul>{rows}</ul>
        <p class="callout">Conformance is local and deterministic. It cannot prove live compatibility, effective input, reliability, completion, usefulness, owner acceptance, or Supported eligibility.</p>
        <a class="primary-button nav-link" href="/onboarding">Open onboarding flow</a>
      </section>'''


def _learning_engineering_panel(snapshot: LearningSnapshot) -> str:
    cards = "".join(
        f'''
          <article class="issue-row" data-testid="lab-learning-candidate">
            <strong>{_esc(candidate.candidate_id)}</strong><span class="status-pill">{_esc(candidate.lifecycle.value.replace("_", " ").title())}</span>
            <p>{_esc(candidate.why_improvement)}</p>
            <details><summary>Provenance, exact proposal, and gates</summary>
              <dl class="fact-grid"><div><dt>Hash</dt><dd><code>{_esc(candidate.content_hash)}</code></dd></div><div><dt>Boundary</dt><dd>{_esc(candidate.state_boundary)}</dd></div><div><dt>Objective</dt><dd>{_esc(candidate.objective_id)}@{candidate.objective_version}</dd></div><div><dt>Sources</dt><dd>{_esc(", ".join(candidate.provenance.source_run_ids))}</dd></div></dl>
              <h4>Exact proposed action</h4><ol>{''.join(f'<li>{_esc(step)}</li>' for step in candidate.action_sequence)}</ol>
              <h4>Replay and promotion</h4><ul>{''.join(f'<li>{_esc(item.description)} · {_esc(item.status)}</li>' for item in candidate.validation_requirements)}</ul>
              <p>Route patch: required · exact diff: required · affected reliability: required · automatic promotion: disabled.</p>
            </details>
          </article>'''
        for candidate in snapshot.candidates
    ) or '<p class="empty">No learning candidate has been derived yet.</p>'
    history = "".join(
        f'<li>{_esc(review.candidate_id)} · {_esc(review.decision)} · {_esc(review.reason)}</li>'
        for review in snapshot.reviews
    ) + "".join(
        f'<li>{_esc(rollback.candidate_id)} · rolled back to {_esc(rollback.restored_solution_id or "no prior solution")}</li>'
        for rollback in snapshot.rollbacks
    )
    return f'''
      <section class="paper-panel" data-testid="lab-learning-engineering">
        <div class="section-title"><h2>Learning candidates</h2><p>Engineering provenance and promotion readiness</p></div>
        {cards}
        <details><summary>Review, rejection, promotion, and rollback history</summary><ul>{history or '<li>No lifecycle decisions yet.</li>'}</ul></details>
      </section>'''


def _player_session_history_panel() -> str:
    try:
        summary = LocalMetricsStore().summarize()
    except MetricsError as exc:
        return f'''
          <section class="session-card" data-testid="session-history-metrics">
            <div class="section-title"><h2>Session history</h2><span class="status-pill">Recovery needed</span></div>
            <p>Local metric storage could not be read: {_esc(str(exc))}</p>
            <p class="meta">Raw evidence is retained for explicit recovery. No result was upgraded or hidden.</p>
          </section>'''
    counts = summary["event_type_counts"]
    try:
        runs = LocalRunLibrary().runs()
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, RunLibraryError) as exc:
        runs = []
        run_recovery = f'<p class="callout action-error">Run history needs explicit recovery: {_esc(str(exc))}. Raw evidence was not removed.</p>'
    else:
        run_recovery = ""
    learning = LocalLearningStore().snapshot()
    product_history = MarioProductSessionManager().history()
    completed = [item for item in runs if item.completion.value == "completed"]
    compatible = [item for item in completed if item.comparison_compatible]
    player_runs = [item for item in compatible if item.actor == "player"]
    agent_runs = [item for item in compatible if item.actor == "agent"]
    mixed_runs = [item for item in compatible if item.actor == "mixed"]
    fastest = min(compatible, key=lambda item: item.elapsed_compatible_frames) if compatible else None
    player_best = min(player_runs, key=lambda item: item.elapsed_compatible_frames) if player_runs else None
    agent_best = min(agent_runs, key=lambda item: item.elapsed_compatible_frames) if agent_runs else None
    recent_runs = "".join(
        f'<li><strong>{_esc(item.level_id)}</strong> · {_esc(item.actor.title())} · {_esc(item.completion.value)} · {item.elapsed_compatible_frames} frames · {_esc(item.solution_classification.value.replace("_", " "))}</li>'
        for item in reversed(runs[-10:])
    ) or "<li>No level run has been recorded yet.</li>"
    learning_history = "".join(
        f'<li><strong>{_esc(item.candidate_id)}</strong> · {_esc(item.decision)} · {_esc(item.reason)}</li>'
        for item in learning.reviews
    ) + "".join(
        f'<li><strong>{_esc(item.candidate_id)}</strong> · rolled back · restored {_esc(item.restored_solution_id or "no prior accepted solution")}</li>'
        for item in learning.rollbacks
    ) or "<li>No candidate rejection or rollback has been recorded.</li>"
    recovery_history = "".join(
        f'<li><strong>{_esc(item.event_type.replace("_", " ").title())}</strong> · {_esc(item.detail)} · evidence {_esc(item.evidence_status)}</li>'
        for item in reversed(product_history[-10:])
    ) or "<li>No product recovery or lifecycle event has been recorded.</li>"
    recent = "".join(
        f'''<article class="callout" data-testid="recent-classified-session">
          <strong>{_esc(item['game_id'])} · {_esc(item['scenario_id'])}@{_esc(item['scenario_version'])}</strong>
          <p>{_esc(item['ownership'])} ownership · {_esc(item['objective'])} · outcome {_esc(item['outcome'])}</p>
          <p>{_esc(item['evidence_classification'].replace('_', ' '))} · technical status {_esc(item['technical_status'])} · observation {_esc(item['observation_freshness'])}</p>
          <p>{item['suggestions']} suggestions / {item['suggestion_responses']} responses · {item['takeovers']} takeovers / {item['handbacks']} handbacks · {item['run_library_changes']} run-library changes · {item['learning_candidate_changes']} candidate changes · {item['missing_or_incompatible_evidence']} missing or incompatible evidence</p>
          <details class="technical-details"><summary>Technical identity</summary><code>{_esc(item['session_id'])}</code> · adapter <code>{_esc(item['adapter_id'])}</code></details>
        </article>'''
        for item in summary["recent_sessions"]
    ) or '<p class="compact-state">No classified V2.8 session events have been recorded.</p>'
    return f'''
      <section id="history" class="session-card" data-testid="session-history-metrics">
        <div class="section-title"><div><h2>History</h2><p class="selected-mode">Runs, comparisons, records, learning, and recovery</p></div><span class="status-pill">{summary['session_count']} sessions · {len(runs)} runs</span></div>
        {run_recovery}
        <dl class="live-summary" data-testid="history-records"><div><dt>Player best</dt><dd>{f'{player_best.elapsed_compatible_frames} frames' if player_best else 'None'}</dd></div><div><dt>Agent best</dt><dd>{f'{agent_best.elapsed_compatible_frames} frames' if agent_best else 'None'}</dd></div><div><dt>Fastest locally observed</dt><dd>{f'{fastest.elapsed_compatible_frames} frames' if fastest else 'None'}</dd></div><div><dt>Mixed runs</dt><dd>{len(mixed_runs)}</dd></div><div><dt>Deaths / recovery</dt><dd>{sum(item.deaths for item in runs)} deaths · {sum(item.recoveries for item in runs)} recoveries</dd></div><div><dt>Known incompatibilities</dt><dd>{sum(not item.comparison_compatible for item in runs)}</dd></div><div><dt>Candidate improvements</dt><dd>{len(learning.candidates)}</dd></div><div><dt>Rejected / rolled back</dt><dd>{sum(item.decision == 'rejected' for item in learning.reviews)} rejected · {len(learning.rollbacks)} rolled back</dd></div></dl>
        <p class="callout">Fastest locally observed is not a world record. A captured candidate is not executable. Approval means approved for later validation; only a separately promoted accepted executable solution may be used by Do. Deferred validation remains deferred.</p>
        <details><summary>Recent level runs and evidence classification</summary><ul>{recent_runs}</ul></details>
        <details><summary>Candidate decisions and rollback history</summary><ul>{learning_history}</ul></details>
        <details><summary>Failures, recovery, and product lifecycle</summary><ul>{recovery_history}</ul></details>
        <dl class="live-summary">
          <div><dt>Observation</dt><dd>{counts.get('observation_connected', 0)} connected · {counts.get('observation_disconnected', 0)} disconnects</dd></div>
          <div><dt>Ownership</dt><dd>{summary['player_input_count']} player · {summary['agent_input_count']} agent · {summary['ambiguous_ownership_count']} ambiguous</dd></div>
          <div><dt>Suggestions</dt><dd>{counts.get('suggestion_emitted', 0)} emitted · {counts.get('suggestion_response', 0)} responses</dd></div>
          <div><dt>Takeover &amp; handback</dt><dd>{counts.get('agent_control_started', 0)} transfers · {counts.get('handback_completed', 0)} handbacks</dd></div>
          <div><dt>Run library</dt><dd>{counts.get('run_created', 0)} runs · {counts.get('fastest_observed_updated', 0)} fastest updates</dd></div>
          <div><dt>Learning</dt><dd>{counts.get('learning_pattern', 0)} patterns · {counts.get('candidate_reviewed', 0)} reviews</dd></div>
          <div><dt>Missing evidence</dt><dd>{counts.get('artifact_missing', 0)} missing · {counts.get('integrity_failure', 0)} integrity failures</dd></div>
          <div><dt>Boundary violations</dt><dd>{summary['boundary_violation_count']} · required value 0</dd></div>
        </dl>
        <details data-testid="recent-classified-sessions"><summary>Recent classified sessions and scenarios</summary>{recent}</details>
        <p class="meta">Implemented, deterministic, technical, visible-live, reliability, review-only, unattended, owner-usefulness, owner-acceptance, and authoritative game outcomes remain separate. Technical event details stay collapsed.</p>
        <details class="technical-details"><summary>Technical event counts and classifications</summary><pre>{_esc(json.dumps({'event_types': counts, 'classifications': summary['classification_counts'], 'unknown_count': summary['unknown_count']}, indent=2, sort_keys=True))}</pre></details>
      </section>'''


def _scenario_engineering_panel() -> str:
    try:
        catalog = load_scenario_catalog()
        manifests = sorted(
            repository_path("artifacts/campaigns").glob("*/campaign-entry-manifest.json")
        )
        manifest = load_campaign_entry_manifest(manifests[-1]) if manifests else None
        readiness = final_campaign_readiness(
            catalog,
            manifest,
            verify_candidate_identity=manifest is not None,
        )
    except (ScenarioError, OSError, yaml.YAMLError) as exc:
        return f'''
          <section class="paper-panel" data-testid="lab-scenario-engineering">
            <div class="section-title"><h2>Scenario automation</h2><span class="status-pill">Catalog unavailable</span></div>
            <p>{_esc(str(exc))}</p>
          </section>'''
    scenario_rows = "".join(
        f'''<article class="issue-row" data-testid="lab-scenario-row">
          <strong>{_esc(item.title)}</strong><span class="status-pill">{_esc(item.capability_status.replace('_', ' ').title())}</span>
          <p><code>{_esc(item.identity)}</code> · {_esc(item.classification.value.replace('_', ' '))} · {_esc(item.evidence_classification.value.replace('_', ' '))}</p>
          <details><summary>Dry execution plan and proof boundary</summary><pre>{_esc(json.dumps(scenario_plan(item).to_dict(), indent=2, sort_keys=True))}</pre></details>
        </article>'''
        for item in catalog
    )
    labels = "".join(
        f"<li><strong>{_esc(item.metric_id)}</strong> · {_esc(item.label.value.replace('_', ' '))} · numerator: {_esc(item.numerator)} · denominator: {_esc(item.denominator)} · {_esc(item.unit)}</li>"
        for item in metric_definitions()
    )
    return f'''
      <section class="paper-panel" data-testid="lab-scenario-engineering">
        <div class="section-title"><div><h2>Scenario automation &amp; metrics</h2><p>Implementation, campaign entry, completion, proof limits, and owner boundaries remain separate</p></div><span class="status-pill">V2.14 readiness</span></div>
        <dl class="fact-grid"><div><dt>Catalog</dt><dd>{len(catalog)} versioned scenarios</dd></div><div><dt>Raw events</dt><dd>{LocalMetricsStore().status()['accepted_events']}</dd></div><div><dt>Implementation blockers</dt><dd>{len(readiness['implementation_blockers'])}</dd></div><div><dt>Candidate blockers</dt><dd>{len(readiness['candidate_blockers'])}</dd></div><div><dt>Campaign entry</dt><dd>{'Ready' if readiness['campaign_entry_ready'] else 'Not ready'}</dd></div><div><dt>Campaign complete</dt><dd>No — live and owner proof pending</dd></div></dl>
        <details><summary>Scenario catalog and dry plans</summary>{scenario_rows}</details>
        <details><summary>Metric definitions and classification filters</summary><ul>{labels}</ul><p>No combined success score exists. Unknown, failed, incompatible, and missing evidence stay visible.</p></details>
        <details><summary>Storage, reconciliation, and recovery</summary><p>Raw events are append-only and integrity hashed. Derived indexes are atomic and rebuildable. Malformed, contradictory, duplicate-content, out-of-order, unsupported, or classification-changing events are rejected or quarantined.</p><p>Failed attempts and artifacts are retained; retries create new immutable attempts. Deletion planning protects accepted route evidence.</p></details>
        <details><summary>Final-campaign readiness</summary><pre>{_esc(json.dumps(readiness, indent=2, sort_keys=True))}</pre></details>
      </section>'''


def _unattended_regression_panel() -> str:
    root = Path("artifacts/unattended-regression")
    attempts: list[dict[str, object]] = []
    if root.is_dir():
        for status_path in sorted(root.glob("*/status.json"), reverse=True)[:10]:
            try:
                status = json.loads(status_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                status = {
                    "attempt_id": status_path.parent.name,
                    "lifecycle": "retained_for_review",
                    "first_missing_requirement": "status artifact is unreadable",
                }
            attempts.append(status)
    rows = "".join(
        f'''<article class="issue-row" data-testid="lab-unattended-attempt">
          <strong>{_esc(str(item.get("attempt_id", "unknown")))}</strong>
          <span class="status-pill">{_esc(str(item.get("lifecycle", "unknown")).replace("_", " ").title())}</span>
          <p>First unmet requirement: {_esc(str(item.get("first_missing_requirement") or "none reported"))}</p>
        </article>'''
        for item in attempts
    ) or '<p class="empty">No unattended attempt has been created or executed.</p>'
    return f'''
      <section class="paper-panel" data-testid="lab-unattended-regression">
        <div class="section-title"><div><h2>Unattended regression</h2><p>Engineering-only, local, bounded, and adapter-declared</p></div><span class="status-pill">Regression only</span></div>
        <dl class="fact-grid">
          <div><dt>Adapter eligibility</dt><dd>Explicit provider required</dd></div>
          <div><dt>Display readiness</dt><dd>Declared rendered-pixel provider required</dd></div>
          <div><dt>Protected data</dt><dd>Primary saves, ROM content, accepted evidence, and owner history excluded</dd></div>
          <div><dt>Lifecycle</dt><dd>Immutable manifest · isolated runs · exact cancellation · retained cleanup</dd></div>
        </dl>
        <p class="callout"><strong>Exact proof limits:</strong> unattended output is not visible player proof, Show evidence, route reliability, authoritative completion, owner usefulness, owner acceptance, or a replacement for the consolidated campaign.</p>
        <details open><summary>Retained attempts, failures, cleanup, and first unmet requirements</summary>{rows}</details>
        <details><summary>Manifest, comparison, and cancellation surfaces</summary><p>Use the local unattended capability, plan, manifest, run, cancel, status, and compare commands. Execution requires the exact regression-only acknowledgement. Compatible comparisons report technical repeatability only; visible references remain correlation references, never equivalence or causation.</p></details>
      </section>'''


def _product_engineering_panel(
    view: ProductSessionView | None,
    snapshot: LiveObservationSnapshot | None,
) -> str:
    current_snapshot = snapshot or LiveObservationSnapshot(
        None, ConnectionState.IDLE, Freshness.UNKNOWN, "No live observation."
    )
    current = view or MarioProductSessionManager().view(current_snapshot)
    try:
        pilot = load_owner_pilot_manifest()
        pilot_status = str(pilot.get("status", "unknown"))
        pilot_version = str(pilot.get("pilot_version", "unknown"))
        required_evidence = tuple(str(item) for item in pilot.get("required_evidence", ()))
        missing_evidence = required_evidence
    except MarioProductError as exc:
        pilot = {"error": str(exc)}
        pilot_status = "unavailable"
        pilot_version = "unknown"
        missing_evidence = (str(exc),)
    capability_rows = "".join(
        f'<li><strong>{_esc(item.capability_id)}</strong> · {"available" if item.available else "blocked"}'
        f'{" · " + _esc(item.unavailable_reason or "unknown") if not item.available else ""}</li>'
        for item in current.capabilities
    )
    recovery = current.current_failure
    return f'''
      <section class="paper-panel" data-testid="lab-product-engineering">
        <div class="section-title"><div><h2>Mario product state</h2><p>V2.9 capabilities, setup, ownership, recovery, and pilot readiness</p></div><span class="status-pill">Implementation only</span></div>
        <dl class="fact-grid">
          <div><dt>Product stage</dt><dd>{_esc(current.stage.value)}</dd></div>
          <div><dt>First use</dt><dd>{_esc(current.first_use.status.value)}</dd></div>
          <div><dt>Active product process</dt><dd>{_esc(current_snapshot.session_id or 'none')}</dd></div>
          <div><dt>Input owner</dt><dd>{_esc(current_snapshot.control_owner)}</dd></div>
          <div><dt>Control state</dt><dd>{_esc(current_snapshot.control_state)}</dd></div>
          <div><dt>Unsafe state restored</dt><dd>{_yes_no(current.unsafe_state_restored)}</dd></div>
          <div><dt>Pilot</dt><dd>{_esc(pilot_version)} · {_esc(pilot_status)}</dd></div>
          <div><dt>Missing final evidence</dt><dd>{len(missing_evidence)} requirements · validation deferred</dd></div>
        </dl>
        <details><summary>Capability truth and unavailable reasons</summary><ul>{capability_rows}</ul></details>
        <details><summary>First-use identity and configuration</summary><pre>{_esc(json.dumps(asdict(current.first_use), indent=2, sort_keys=True, default=str))}</pre></details>
        <details><summary>Recovery state</summary><pre>{_esc(json.dumps(asdict(recovery) if recovery else {'status': 'none'}, indent=2, sort_keys=True))}</pre></details>
        <details><summary>Owner-pilot manifest and required evidence</summary><pre>{_esc(json.dumps(pilot, indent=2, sort_keys=True))}</pre></details>
        <p class="meta">Authorization, control epochs, process ownership, and reclaim are runtime-only. They are never restored from product preferences.</p>
      </section>'''


def _run_bar(last_command: dict[str, object]) -> str:
    return f"""
            <div class="run-strip">
              <form method="post" action="/run" class="run-form" aria-label="Run">
                <label>Speed <select name="speed">{_options(SUPPORTED_SPEEDS, "4", suffix="x")}</select></label>
                <label>Attempts <select name="attempts">{_options(SUPPORTED_ATTEMPTS, "1")}</select></label>
                <label>Mode
                  <select name="mode">
                    <option value="show">watch route</option>
                    <option value="gate">gate run</option>
                  </select>
                </label>
                <button type="submit" class="primary-button">Run World 8 Route</button>
              </form>
              <div class="last-result">
                <span>Last run result</span>
                <strong class="{_status_class(_last_command_status(last_command))}">{_esc(_title_status(_last_command_status(last_command)))}</strong>
              </div>
              <form method="post" action="/refresh" class="refresh-form">
                <button type="submit" class="secondary-button">Refresh Review</button>
              </form>
            </div>"""


def _route_item(
    location: dict[str, object], selected: dict[str, object], goal_id: str
) -> str:
    location_id = str(location["id"])
    label = str(location.get("label", location_id))
    state = _route_state(location)
    selected_class = " route-item-selected" if selected.get("id") == location_id else ""
    return f"""
                <a class="route-step route-item status-{_state_class(state)}{selected_class}" href="{_esc(_location_url(location_id, goal_id=goal_id))}">
                  {_asset_icon(_icon_name_for_location(location), _icon_fallback(location), f'{label} icon')}
                  <span class="route-copy">
                    <strong>{_esc(label)}</strong>
                    <small>{_esc(_route_role_label(str(location.get('classification', ''))))} · {_esc(_title_status(state))} · {location.get('open_issues', 0)} open</small>
                  </span>
                </a>"""


def _evidence_viewer(
    evidence: dict[str, object],
    selected: dict[str, object],
    last_command: dict[str, object],
) -> str:
    image_path = evidence.get("image")
    image_html = ""
    frame_class = "screen-frame"
    if isinstance(image_path, Path):
        image_html = f'<img src="{_esc(_artifact_url(image_path))}" alt="Latest route evidence">'
    else:
        frame_class = "screen-frame no-evidence-frame"
        image_html = """
                <div class="empty-evidence">
                  <strong>No screenshot captured yet</strong>
                  <span>Run the World 8 route to capture screenshot/contact-sheet evidence.</span>
                </div>"""
    detail_rows = "".join(
        f"<li><strong>{_esc(label)}</strong><span>{_esc(value)}</span></li>"
        for label, value in evidence.get("details", [])
    )
    return f"""
            <section class="evidence-viewer">
              <div class="section-title">
                <h2>Evidence</h2>
                <p>What went wrong?</p>
              </div>
              <div class="{frame_class}">
                {image_html}
              </div>
              <div class="evidence-notes">
                <h3>{_esc(str(selected.get('label', 'Route')))}</h3>
                <p>{_esc(str(selected.get('objective', 'Select a route step to review what Mario should do here.')))}</p>
                <ul>
                  {detail_rows}
                  <li><strong>Latest observed state</strong><span>{_esc(_latest_observed_state(last_command))}</span></li>
                </ul>
              </div>
            </section>"""


def _teaching_panel(
    selected: dict[str, object],
    observations: list[dict[str, object]],
    issues: list[dict[str, object]],
    mode: str,
    selected_note: dict[str, object] | None,
    selected_issue: dict[str, object] | None,
    goal_id: str,
) -> str:
    location_id = str(selected.get("id", ""))
    label = str(selected.get("label", "Route"))
    content = {
        "add": _add_observation_mode(selected),
        "notes": _review_notes_mode(location_id, observations, selected_note, goal_id),
        "issue": _fix_issue_mode(location_id, issues, selected_issue, goal_id),
    }.get(mode, _add_observation_mode(selected))
    return f"""
            <aside class="teaching-panel">
              <div class="section-title">
                <h2>Help &amp; Learn</h2>
              </div>
              <div class="selected-location">
                <strong>{_esc(label)}</strong>
                <span class="status-pill status-{_state_class(_route_state(selected))}">{_esc(_title_status(_route_state(selected)))}</span>
                <p>{_esc(str(selected.get('objective', '')))}</p>
              </div>
              <nav class="mode-tabs segmented-control" aria-label="Mario help and learning modes">
                {_mode_link(location_id, 'add', 'Add Observation', mode, goal_id)}
                {_mode_link(location_id, 'notes', 'Review Notes', mode, goal_id)}
                {_mode_link(location_id, 'issue', 'Fix Issue', mode, goal_id)}
              </nav>
              {content}
              <form method="post" action="/test" class="mini-actions">
                <button type="submit" name="action" value="phase_gate" class="quiet">Phase Gate</button>
                <button type="submit" name="action" value="unit_tests" class="quiet">Unit Tests</button>
                <button type="submit" name="action" value="render_check" class="quiet">HTML Render Check</button>
              </form>
            </aside>"""


def _mode_link(
    location_id: str,
    mode: str,
    label: str,
    selected_mode: str,
    goal_id: str,
) -> str:
    selected_class = " segment-active" if mode == selected_mode else ""
    return f'<a class="mode-tab{selected_class}" href="{_esc(_location_url(location_id, mode=mode, goal_id=goal_id))}">{_esc(label)}</a>'


def _add_observation_mode(selected: dict[str, object]) -> str:
    location_id = str(selected.get("id", ""))
    return f"""
              <section class="mode-panel">
                <form method="post" action="/notes">
                  <input type="hidden" name="return_location" value="{_esc(location_id)}">
                  <label>What happened?
                    <textarea name="note__{_esc(location_id)}" placeholder="Where did Mario fail, or what should he do here?"></textarea>
                  </label>
                  <div class="note-tools">
                    <label>Classification
                      <select name="severity__{_esc(location_id)}">
                        <option value="bug">failure</option>
                        <option value="objective">expected behavior</option>
                        <option value="map_action">route instruction</option>
                        <option value="harden">validation note</option>
                        <option value="guide_detail">positive evidence</option>
                      </select>
                    </label>
                    <label>Evidence anchor
                      <select name="anchor__{_esc(location_id)}">
                        <option value="">no anchor</option>
                        <option value="in_game_timer">timer</option>
                        <option value="frame">frame</option>
                        <option value="map_position">map position</option>
                      </select>
                    </label>
                  </div>
                  <button type="submit" class="secondary-button">Add Observation</button>
                </form>
              </section>"""


def _review_notes_mode(
    location_id: str,
    observations: list[dict[str, object]],
    selected_note: dict[str, object] | None,
    goal_id: str,
) -> str:
    selected_note = selected_note or (observations[0] if observations else None)
    return f"""
              <section class="mode-panel">
                <div class="compact-list">
                  {''.join(_observation_compact_row(note, location_id, selected_note, goal_id) for note in observations) or '<p class="empty">No observations for this location yet.</p>'}
                </div>
                {_observation_detail(selected_note, location_id) if selected_note else ''}
              </section>"""


def _fix_issue_mode(
    location_id: str,
    issues: list[dict[str, object]],
    selected_issue: dict[str, object] | None,
    goal_id: str,
) -> str:
    selected_issue = selected_issue or (issues[0] if issues else None)
    return f"""
              <section class="mode-panel">
                <div class="compact-list">
                  {''.join(_issue_compact_row(issue, location_id, selected_issue, goal_id) for issue in issues) or '<p class="empty">No open issues for this location.</p>'}
                </div>
                {_issue_detail(selected_issue, location_id) if selected_issue else ''}
              </section>"""


def _page(*, title: str, body: str, csrf_token: str | None = None) -> str:
    if csrf_token is not None:
        csrf_field = (
            '<input type="hidden" name="csrf_token" '
            f'value="{_esc(csrf_token)}">'
        )
        body = _inject_csrf_fields(body, csrf_field)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
  <title>{_esc(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --app-bg: #f7f4ec;
      --surface: #ffffff;
      --surface-alt: #f8fafc;
      --text: #1f2937;
      --muted: #64748b;
      --line: #d6d3c8;
      --line-strong: #b8ad97;
      --screen: #1b2426;
      --screen-soft: #2f3a3d;
      --blue: #2563eb;
      --blue-soft: #eff6ff;
      --navy: #1e3a5f;
      --red: #c9362c;
      --red-soft: #fff1f0;
      --green: #1f7a4d;
      --green-soft: #edf9f1;
      --amber: #b7791f;
      --amber-soft: #fff7df;
      --badge: #f4ead3;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      overflow-x: hidden;
      background:
        linear-gradient(rgba(30,58,95,.026) 1px, transparent 1px),
        linear-gradient(90deg, rgba(30,58,95,.026) 1px, transparent 1px),
        var(--app-bg);
      background-size: 22px 22px;
      color: var(--text);
      font: 14px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    h1, h2, h3, p {{ margin-top: 0; }}
    h1 {{ font-size: 26px; line-height: 1.05; margin-bottom: 4px; letter-spacing: 0; }}
    h2 {{ font-size: 16px; margin-bottom: 2px; letter-spacing: 0; }}
    h3 {{ font-size: 15px; margin-bottom: 4px; letter-spacing: 0; }}
    a {{ color: inherit; }}
    button {{
      border: 1px solid var(--line-strong);
      background: var(--surface);
      color: var(--text);
      border-radius: 6px;
      padding: 7px 10px;
      font-weight: 750;
      cursor: pointer;
      min-height: 32px;
    }}
    button:hover {{ background: var(--surface-alt); border-color: var(--navy); }}
    button:disabled {{
      cursor: not-allowed;
      opacity: .58;
      background: #eef0f2;
      border-color: var(--line);
    }}
    .primary-button {{
      border: 1px solid #8f251f;
      background: var(--red);
      color: #fff;
      min-height: 36px;
      padding: 8px 13px;
      box-shadow: 0 1px 0 rgba(31,41,55,.12);
    }}
    .primary-button:hover {{ background: #b92f27; border-color: #7f211c; }}
    .secondary-button {{
      background: var(--surface);
      color: var(--text);
      border-color: var(--line-strong);
    }}
    button.quiet, button.small {{
      background: var(--surface);
      border-color: var(--line);
      color: var(--text);
    }}
    button.quiet:hover, button.small:hover {{ border-color: var(--line-strong); background: var(--surface-alt); }}
    button.small {{
      min-height: 26px;
      padding: 4px 7px;
      font-size: 12px;
    }}
    textarea, select, input {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      font: inherit;
      background: var(--surface);
      color: var(--text);
    }}
    textarea {{ min-height: 118px; resize: vertical; }}
    label {{ display: grid; gap: 4px; font-weight: 700; color: var(--text); }}
    code {{
      display: block;
      overflow-x: auto;
      color: var(--navy);
      white-space: nowrap;
    }}
    .nav-link {{ display: inline-flex; align-items: center; text-decoration: none; }}
    .companion-shell {{
      min-height: 100vh;
      max-width: 1320px;
      margin: 0 auto;
      padding: 20px;
    }}
    .companion-top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      padding: 18px 20px;
      background: var(--navy);
      color: #fff;
      border-radius: 12px;
      box-shadow: 0 10px 28px rgba(31,41,55,.16);
    }}
    .companion-top p {{ margin-bottom: 0; color: #dbeafe; }}
    .companion-top .eyebrow {{
      margin-bottom: 4px;
      color: #f8e8b0;
      font-size: 11px;
      font-weight: 900;
      letter-spacing: .12em;
      text-transform: uppercase;
    }}
    .companion-top .nav-link {{ background: #fff; color: var(--navy); }}
    .companion-main {{
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 14px;
      margin-top: 14px;
    }}
    .active-workspace {{ display: contents; }}
    .session-card {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 16px;
      box-shadow: 0 8px 22px rgba(31,41,55,.07);
    }}
    .identity-card, .observation-card {{ grid-column: span 6; }}
    .live-observation-card, .objective-card, .session-more, .modes-card, .tell-request-card, .show-card, .handoff-card, .first-use-card, .product-overview, .recovery-card, [data-testid="session-history-metrics"] {{ grid-column: 1 / -1; }}
    .safety-card {{ grid-column: span 7; }}
    .activity-card {{ grid-column: span 5; }}
    .game-name {{ font-size: 21px; font-weight: 850; margin-bottom: 4px; }}
    .fact-grid, .handoff-list {{ margin: 0; display: grid; gap: 8px; }}
    .fact-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .fact-grid div, .handoff-list div {{
      border-top: 1px solid #e5e7eb;
      padding-top: 7px;
    }}
    dt {{ color: var(--muted); font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }}
    dd {{ margin: 2px 0 0; font-weight: 650; }}
    .callout {{ margin: 12px 0 0; padding: 9px 10px; border-radius: 7px; background: var(--amber-soft); color: #744b14; }}
    .status-fresh .callout {{ background: var(--green-soft); color: var(--green); }}
    .control-line {{ margin: 6px 0 10px; padding: 8px 10px; border-radius: 7px; background: var(--amber-soft); color: #744b14; }}
    .live-summary {{ display: grid; grid-template-columns: 1.2fr 2fr .6fr .8fr; gap: 8px; margin: 0; }}
    .live-summary div {{ border-top: 1px solid #e5e7eb; padding-top: 7px; min-width: 0; }}
    .live-summary dd {{ overflow-wrap: anywhere; }}
    .status-message {{ margin: 9px 0; color: var(--muted); }}
    .live-actions {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }}
    .live-actions form {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }}
    label.inline-check {{ display: inline-flex; flex-direction: row; align-items: center; gap: 7px; }}
    label.inline-check input {{ margin: 0; width: auto; }}
    .live-indicator {{ color: var(--green); font-size: 12px; font-weight: 800; }}
    .compact-link {{ display: inline-flex; align-items: center; min-height: 32px; text-decoration: none; }}
    .technical-details, .session-more {{ margin-top: 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-alt); }}
    .technical-details > summary, .session-more > summary {{ cursor: pointer; padding: 10px 12px; font-weight: 800; }}
    .technical-details[open] {{ padding: 0 12px 12px; }}
    .technical-details[open] > summary {{ margin: 0 -12px 10px; }}
    .technical-facts {{ margin-bottom: 12px; }}
    .selected-mode {{ margin: 2px 0 0; color: var(--muted); }}
    .objective-controls {{ display: grid; grid-template-columns: 1.6fr 1fr 1.5fr auto; gap: 8px; align-items: end; margin: 12px 0; }}
    .objective-controls label, .objective-tell-controls label {{ display: grid; gap: 4px; color: var(--muted); font-size: 12px; font-weight: 750; }}
    .objective-controls select, .objective-tell-controls select {{ width: 100%; min-width: 0; }}
    .objective-now {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .objective-now > div {{ border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: var(--surface-alt); }}
    .objective-now p:last-child, .objective-now ul {{ margin-bottom: 0; }}
    .objective-now ul {{ padding-left: 19px; }}
    .inline-action {{ display: flex; align-items: center; gap: 10px; margin-top: 10px; }}
    .objective-tell-controls {{ display: grid; grid-template-columns: 2fr 1fr auto; gap: 8px; align-items: end; margin-top: 10px; }}
    .compact-tell {{ margin-top: 10px; padding-top: 10px; }}
    .compact-state {{ margin: 7px 0 0; color: var(--muted); font-size: 12px; font-weight: 750; }}
    .session-more {{ background: transparent; }}
    .session-more > summary {{ background: var(--surface); border-radius: 8px; box-shadow: 0 8px 22px rgba(31,41,55,.05); }}
    .companion-more-grid {{ display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 14px; margin-top: 14px; }}
    .mode-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }}
    .mode-grid a {{ display: grid; place-items: center; min-height: 38px; border: 1px solid var(--line); border-radius: 7px; background: var(--surface-alt); color: var(--navy); font-weight: 800; text-decoration: none; }}
    .setup-steps, .capability-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; margin: 10px 0; }}
    .first-use-card form {{ display: grid; gap: 9px; margin-top: 12px; }}
    .first-use-card fieldset {{ display: grid; gap: 10px; border: 1px solid var(--line); border-radius: 8px; padding: 10px; }}
    .first-use-card fieldset label {{ display: block; padding: 8px; border: 1px solid var(--line); border-radius: 7px; background: var(--surface-alt); }}
    .first-use-card input[type="radio"], .first-use-card input[type="checkbox"] {{ width: auto; }}
    .capability-item {{ border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: var(--surface-alt); }}
    .capability-item > .status-pill {{ float: right; }}
    .capability-item.unavailable {{ border-color: #e6d4aa; }}
    .action-error, .recovery-card {{ border-color: #e8b3ae; background: var(--red-soft); color: #7f211c; }}
    .persistent-reclaim {{ position: sticky; top: 8px; z-index: 20; display: grid; grid-template-columns: minmax(180px, .45fr) 1fr; gap: 10px; align-items: center; padding: 10px; margin-bottom: 10px; border: 2px solid var(--red); border-radius: 9px; background: #fff; box-shadow: 0 10px 30px rgba(127,33,28,.2); }}
    .persistent-reclaim span {{ color: var(--red); font-weight: 800; }}
    .mode-card {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: var(--surface-alt); }}
    .mode-card button {{ width: 100%; margin: 4px 0 8px; }}
    .mode-reason {{ margin-bottom: 0; color: var(--muted); font-size: 12px; }}
    .tell-request-card form {{ display: grid; gap: 12px; }}
    .tell-request-card fieldset {{ display: grid; gap: 7px; border: 1px solid var(--line); border-radius: 7px; padding: 10px; }}
    .tell-request-card fieldset label {{ display: flex; align-items: center; gap: 8px; }}
    .tell-request-card input[type="checkbox"] {{ width: auto; }}
    .tell-card {{ margin-top: 16px; border-top: 1px solid var(--line); padding-top: 16px; }}
    .tell-card details {{ margin-top: 6px; color: var(--muted); font-size: 12px; }}
    .tell-card details ul {{ margin: 5px 0; }}
    .safety-card ul {{ padding-left: 19px; }}
    .activity-list {{ min-height: 58px; padding-left: 20px; }}
    .take-control {{ width: 100%; border-color: #8f251f; color: var(--red); }}
    .handoff-list {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .state-completed {{ border-color: #86c7a4; }}
    .state-failed {{ border-color: #e8b3ae; }}
    .state-cancelled, .state-taken_over {{ border-color: #e3c987; }}
    .route-lab {{
      min-height: 100vh;
      padding: 14px;
      max-width: 1760px;
      margin: 0 auto;
    }}
    .paper-panel, .route-index, .evidence-viewer, .teaching-panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 8px 22px rgba(31, 41, 55, .07);
    }}
    .lab-top {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 14px;
      align-items: center;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      box-shadow: 0 8px 22px rgba(31, 41, 55, .06);
    }}
    .lab-title, .run-strip, .route-step, .section-title, .location-head {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .lab-title p, .section-title p, .meta {{ margin: 0; color: var(--muted); font-size: 12px; }}
    .goal-switcher {{
      display: flex;
      gap: 4px;
      padding: 3px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--surface-alt);
    }}
    .goal-choice {{
      padding: 6px 10px;
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-decoration: none;
    }}
    .goal-choice.goal-selected {{ background: var(--navy); color: #fff; }}
    .section-title {{
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 10px;
    }}
    .asset-icon {{
      width: 34px;
      height: 34px;
      display: inline-grid;
      place-items: center;
      flex: 0 0 auto;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: #f8edd0;
      color: var(--navy);
      font-weight: 900;
      font-size: 11px;
    }}
    .asset-icon img {{
      width: 100%;
      height: 100%;
      object-fit: contain;
      border-radius: 5px;
    }}
    .run-strip {{
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .run-form {{
      display: grid;
      grid-template-columns: 92px 92px 132px auto;
      gap: 8px;
      align-items: end;
    }}
    .run-form label {{ font-size: 12px; }}
    .last-result {{
      display: grid;
      gap: 2px;
      min-width: 112px;
      padding-left: 10px;
      border-left: 1px solid var(--line);
    }}
    .last-result span {{ color: var(--muted); font-size: 11px; }}
    .last-result strong {{ font-size: 13px; }}
    .lab-main {{
      display: grid;
      grid-template-columns: 245px minmax(420px, 1fr) 340px;
      gap: 14px;
      margin-top: 14px;
      align-items: start;
    }}
    .lab-main > *, .lab-bottom > * {{ min-width: 0; }}
    .route-index, .evidence-viewer, .teaching-panel, .paper-panel {{
      padding: 12px;
    }}
    .route-list {{
      display: grid;
      gap: 7px;
    }}
    .route-step {{
      min-height: 52px;
      padding: 8px;
      border: 1px solid #e5e7eb;
      border-radius: 7px;
      text-decoration: none;
      background: var(--surface);
    }}
    .route-step:hover {{
      border-color: var(--line-strong);
      background: var(--surface-alt);
    }}
    .route-item-selected, .route-step:target {{
      background: var(--blue-soft);
      border-color: #bfdbfe;
      box-shadow: inset 4px 0 0 var(--blue);
    }}
    .route-copy {{ display: grid; gap: 1px; min-width: 0; }}
    .route-copy small {{ color: var(--muted); font-size: 11px; }}
    .clean, .passed, .status-clean, .status-learned {{ color: var(--green); }}
    .status-validation {{ color: var(--amber); }}
    .failed, .status-failed {{ color: var(--red); }}
    .unknown, .status-unknown {{ color: var(--muted); }}
    .screen-frame {{
      min-height: 360px;
      display: grid;
      place-items: center;
      background:
        linear-gradient(135deg, rgba(255,255,255,.06) 25%, transparent 25%),
        linear-gradient(225deg, rgba(255,255,255,.06) 25%, transparent 25%),
        var(--screen);
      background-size: 18px 18px;
      border: 12px solid #293437;
      border-radius: 10px;
      box-shadow: inset 0 0 0 2px #101719;
      overflow: hidden;
    }}
    .no-evidence-frame {{ min-height: 235px; }}
    .screen-frame img {{
      max-width: 100%;
      max-height: 620px;
      display: block;
      object-fit: contain;
      background: #000;
    }}
    .empty-evidence {{
      display: grid;
      gap: 6px;
      text-align: center;
      color: #e7f6ee;
      padding: 24px;
    }}
    .empty-evidence span {{ color: #bdd4c9; }}
    .evidence-notes {{
      margin-top: 10px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--surface-alt);
      padding: 10px;
    }}
    .evidence-notes h3 {{ color: var(--text); }}
    .evidence-notes p {{ color: var(--text); }}
    .evidence-notes ul {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 6px;
    }}
    .evidence-notes li {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-top: 1px solid #e5e7eb;
      padding-top: 7px;
    }}
    .evidence-notes li:first-child {{ border-top: 0; padding-top: 0; }}
    .evidence-notes li span {{ color: var(--muted); text-align: right; }}
    .evidence-notes li span {{ min-width: 0; overflow-wrap: anywhere; }}
    .selected-location {{
      background: var(--surface-alt);
      border: 1px solid #e5e7eb;
      border-radius: 7px;
      padding: 9px 10px;
      margin-bottom: 10px;
    }}
    .selected-location p {{ margin: 4px 0 0; color: var(--muted); }}
    .mode-tabs {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 4px;
      margin-bottom: 10px;
      padding: 4px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-alt);
    }}
    .mode-tab {{
      text-align: center;
      text-decoration: none;
      border-radius: 6px;
      padding: 6px 7px;
      font-weight: 800;
      font-size: 12px;
      color: var(--text);
      background: transparent;
    }}
    .mode-tab:hover {{ background: #eef2f7; }}
    .mode-tab.segment-active {{
      background: var(--navy);
      color: #fff;
    }}
    .mode-panel {{ display: grid; gap: 9px; }}
    .note-tools {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }}
    .mini-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-top: 10px;
    }}
    .lab-bottom {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr) minmax(0, .9fr);
      gap: 14px;
      margin-top: 14px;
    }}
    .issue-list, .compact-list {{ display: grid; gap: 3px; }}
    .compact-row {{
      min-height: 34px;
      align-items: center;
      padding: 5px 0;
      border-top: 1px solid #e5e7eb;
    }}
    .compact-row:first-child {{ border-top: 0; }}
    .issue-summary-row {{
      display: grid;
      grid-template-columns: 110px 72px 120px minmax(0, 1fr) 72px 58px;
      gap: 8px;
      font-size: 12px;
    }}
    .observation-summary-row {{
      display: grid;
      grid-template-columns: 48px 100px 76px minmax(0, 1fr) 76px 58px;
      gap: 8px;
      font-size: 12px;
    }}
    .issue p, .note-row p {{ margin-bottom: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .selected-row {{ background: var(--blue-soft); }}
    .compact-pick {{
      display: grid;
      grid-template-columns: 78px minmax(0, 1fr) 62px;
      gap: 7px;
      align-items: center;
      text-decoration: none;
      padding: 6px 7px;
      border-radius: 6px;
      font-size: 12px;
    }}
    .compact-pick strong {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .compact-pick:hover {{ background: var(--surface-alt); }}
    .compact-pick.selected-row {{ background: var(--blue-soft); box-shadow: inset 3px 0 0 var(--blue); }}
    .detail-panel {{
      background: var(--surface-alt);
      border: 1px solid #e5e7eb;
      border-radius: 7px;
      padding: 10px;
      display: grid;
      gap: 8px;
    }}
    .patch-workflow {{
      display: grid;
      gap: 8px;
      border-top: 1px solid var(--line);
      margin-top: 4px;
      padding-top: 10px;
    }}
    .patch-facts {{
      display: grid;
      grid-template-columns: 90px minmax(0, 1fr);
      gap: 3px 8px;
      margin: 0;
      font-size: 12px;
    }}
    .patch-facts dt {{ color: var(--muted); }}
    .patch-facts dd {{ margin: 0; min-width: 0; }}
    .patch-files, .patch-blockers {{ margin: 0; padding-left: 18px; font-size: 12px; }}
    .patch-diff pre {{ max-height: 260px; font-size: 11px; }}
    .patch-import-form, .patch-confirm-form {{ display: grid; gap: 6px; }}
    .patch-actions {{ align-items: end; }}
    .detail-head {{ display: flex; justify-content: space-between; gap: 8px; align-items: center; }}
    .row-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      align-items: center;
    }}
    .row-actions details {{ position: relative; }}
    .row-actions summary {{
      cursor: pointer;
      border-radius: 6px;
      background: var(--surface);
      border: 1px solid var(--line);
      padding: 4px 7px;
      font-size: 12px;
      font-weight: 750;
    }}
    .edit-form {{
      display: grid;
      gap: 6px;
      margin-top: 6px;
      min-width: 220px;
    }}
    .edit-form textarea {{ min-height: 80px; }}
    .review-link {{
      color: var(--blue);
      font-weight: 800;
      text-decoration: none;
    }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 5px; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 7px;
      font-size: 12px;
      color: var(--text);
      background: var(--badge);
      font-weight: 750;
    }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 3px 7px;
      font-size: 12px;
      font-weight: 800;
    }}
    .badge.high, .badge.failed, .status-pill.status-failed {{ color: var(--red); border-color: #e8b3ae; background: var(--red-soft); }}
    .badge.medium, .badge.needs-validation, .status-pill.status-validation {{ color: var(--amber); border-color: #e5c989; background: var(--amber-soft); }}
    .badge.none, .badge.clean, .badge.passed, .status-pill.status-learned {{ color: var(--green); border-color: #acd7b5; background: var(--green-soft); }}
    .artifact-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin: 8px 0;
    }}
    .artifact-links a {{
      color: var(--blue);
      border: 1px solid var(--line);
      background: var(--surface);
      border-radius: 999px;
      padding: 4px 8px;
      text-decoration: none;
      font-size: 12px;
    }}
    pre {{
      max-height: 190px;
      overflow: auto;
      white-space: pre-wrap;
      background: var(--surface-alt);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px;
      color: var(--text);
    }}
    .empty {{ color: var(--muted); margin-bottom: 0; }}
    .error {{ border-color: #e8b3ae; color: var(--red); margin: 20px; padding: 14px; }}
    @media (max-width: 1180px) {{
      .lab-main {{ grid-template-columns: 220px minmax(0, 1fr); }}
      .teaching-panel {{ grid-column: 1 / -1; }}
      .lab-bottom {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 760px) {{
      .companion-shell {{ padding: 10px; }}
      .companion-top {{ display: grid; }}
      .companion-main {{ grid-template-columns: 1fr; }}
      .live-observation-card, .objective-card, .session-more, .identity-card, .observation-card, .modes-card, .safety-card, .activity-card, .handoff-card, .first-use-card, .product-overview, .recovery-card, [data-testid="session-history-metrics"] {{ grid-column: 1; }}
      .live-summary, .objective-controls, .objective-now, .objective-tell-controls, .companion-more-grid {{ grid-template-columns: 1fr; }}
      .inline-action {{ align-items: stretch; flex-direction: column; }}
      .mode-grid, .fact-grid, .handoff-list, .setup-steps, .capability-grid, .persistent-reclaim {{ grid-template-columns: 1fr; }}
      .route-lab {{ padding: 10px; }}
      .lab-top {{ display: grid; }}
      .lab-main, .run-form {{ grid-template-columns: minmax(0, 1fr); }}
      .goal-switcher {{ max-width: 100%; overflow-x: auto; }}
      .run-strip {{ justify-content: flex-start; }}
      .screen-frame {{ min-height: 280px; }}
    }}
    @media (max-width: 420px) {{
      .companion-shell {{ padding: 6px; }}
      .session-card {{ padding: 12px; }}
      .live-actions, .takeover-panel form, .run-library-summary {{ min-width: 0; }}
      .live-actions form, .takeover-panel button, .takeover-panel select,
      .takeover-panel input[type="number"] {{ width: 100%; }}
      .section-title {{ align-items: flex-start; flex-direction: column; }}
    }}
  </style>
</head>
<body>{body}</body>
</html>"""


def _inject_csrf_fields(body: str, csrf_field: str) -> str:
    parts: list[str] = []
    cursor = 0
    while True:
        start = body.find("<form", cursor)
        if start < 0:
            parts.append(body[cursor:])
            return "".join(parts)
        end = body.find(">", start + 5)
        if end < 0:
            parts.append(body[cursor:])
            return "".join(parts)
        parts.append(body[cursor : end + 1])
        opening_tag = body[start : end + 1]
        close = body.find("</form>", end + 1)
        form_body = body[end + 1 : close] if close >= 0 else ""
        if 'method="post"' in opening_tag and 'name="csrf_token"' not in form_body:
            parts.append(csrf_field)
        cursor = end + 1


def render_error(message: str) -> str:
    return _page(
        title="Game Companion Lab Error",
        body=f"""
        <div class="route-lab">
          <section class="paper-panel error">
            <h1>Game Companion Lab Error</h1>
            <p>{_esc(message)}</p>
            <p><a href="/lab">Return to Game Companion Lab</a></p>
          </section>
        </div>
        """,
    )


def build_control_panel_summary(goal_id: str = ACTIVE_PRODUCT_GOAL_ID) -> dict[str, object]:
    contract = load_goal_contract(resolve_goal_path(goal_id))
    catalog = load_segment_catalog(contract.catalog_path)
    locations = _load_locations(contract)
    session_dir = _latest_session_dir_if_any()
    if session_dir is not None:
        session_manifest = _load_yaml(session_dir / "session.yaml")
        if str(session_manifest.get("goal_id", "")) != contract.id:
            session_dir = None
    if session_dir is None:
        notes: list[dict[str, object]] = []
        issues: list[dict[str, object]] = []
        proposals: list[dict[str, object]] = []
        session_label = "No active session"
        session_dir_value = ""
    else:
        notes = _list_dicts(_load_yaml(session_dir / "notes.yaml").get("notes", []))
        issues_path = session_dir / "issues.yaml"
        proposals_path = session_dir / "variant_proposals.yaml"
        issues = _list_dicts(_load_yaml(issues_path).get("issues", []))
        for issue in issues:
            issue["goal_id"] = contract.id
            task_path = session_dir / "codex_tasks" / f"{issue.get('id')}.yaml"
            issue["task_packet"] = str(task_path) if task_path.is_file() else None
            if PATCH_ARTIFACTS_ROOT.is_dir():
                issue["route_patch"] = patch_summary_for_issue(
                    str(issue.get("id", "")), repo_root=Path.cwd()
                )
        proposals = _list_dicts(_load_yaml(proposals_path).get("proposals", []))
        session_label = session_dir.name
        session_dir_value = str(session_dir)

    visible_notes = [note for note in notes if str(note.get("ui_state", "")) != "archived"]
    active_issues = [issue for issue in issues if _is_active_issue(issue)]
    proposal_issue_ids = {str(proposal.get("source_issue")) for proposal in proposals}
    location_rows = []
    for location in locations:
        location_id = str(location["id"])
        segment_id = str(location["segment_id"])
        segment = catalog.by_id[segment_id]
        catalog_default_status = _default_location_status(segment.status)
        location_notes = [
            note for note in visible_notes if _location_id_for_artifact(str(note.get("segment_id"))) == location_id
        ]
        location_issues = [issue for issue in active_issues if _location_id_for_artifact(str(issue.get("segment_id"))) == location_id]
        issue_ids = {str(issue.get("id")) for issue in location_issues}
        location_rows.append(
            {
                **location,
                "classification": next(
                    step.classification for step in contract.route_steps if step.id == segment_id
                ),
                "execution_mode": next(
                    step.execution_mode for step in contract.route_steps if step.id == segment_id
                ),
                "segment_status": segment.status,
                "default_status": catalog_default_status,
                "notes": len(location_notes),
                "issues": len(location_issues),
                "open_issues": len(location_issues),
                "proposals": len(issue_ids & proposal_issue_ids),
                "status": _location_status(
                    {**location, "default_status": catalog_default_status}, location_issues
                ),
            }
        )

    return {
        "session_label": session_label,
        "session_dir": session_dir_value,
        "goal_id": contract.id,
        "goal_type": contract.goal_type,
        "execution_status": contract.execution_status,
        "objective_target": contract.objective.get("target"),
        "locations": location_rows,
        "notes": visible_notes,
        "issues": issues,
        "recent_notes": visible_notes[-12:],
        "totals": {
            "notes": len(visible_notes),
            "issues": len(issues),
            "open_issues": len(active_issues),
            "proposals": len(proposals),
        },
    }


def _issue_row(issue: dict[str, object], summary: dict[str, object], selected: dict[str, object]) -> str:
    priority = str(issue.get("priority", "low"))
    location_label = _label_for_location(summary, str(issue.get("segment_id")))
    location_id = _location_id_for_artifact(str(issue.get("segment_id")))
    selected_mark = " selected-row" if location_id == selected.get("id") else ""
    return f"""
    <article class="issue compact-row issue-summary-row{selected_mark}">
      <strong>{_esc(location_label)}</strong>
      <span class="badge {priority}">{_esc(priority)}</span>
      <span>{_esc(_human_issue_type(str(issue.get('type', 'unknown'))))}</span>
      <p>{_esc(_short_text(str(issue.get('summary', '')), 120))}</p>
      <span class="meta">{_esc(str(issue.get('status', 'unknown')))}</span>
      <a class="review-link" href="{_esc(_location_url(location_id, mode='issue', issue_id=str(issue.get('id', '')), goal_id=str(summary.get('goal_id', ACTIVE_PRODUCT_GOAL_ID))))}">Review</a>
    </article>"""


def _note_row(note: dict[str, object], summary: dict[str, object], selected: dict[str, object]) -> str:
    location_label = _label_for_location(summary, str(note.get("segment_id")))
    location_id = _location_id_for_artifact(str(note.get("segment_id")))
    created_at = str(note.get("created_at", ""))
    time_label = created_at[11:16] if len(created_at) >= 16 else "latest"
    selected_mark = " selected-row" if location_id == selected.get("id") else ""
    return f"""
    <article class="note-row compact-row observation-summary-row{selected_mark}">
      <span class="meta">{_esc(time_label)}</span>
      <strong>{_esc(location_label)}</strong>
      <span>{_esc(str(note.get('severity')))}</span>
      <p>{_esc(_short_text(str(note.get('text', '')), 120))}</p>
      <span class="meta">{_esc(_title_status(str(note.get('ui_state', 'open'))))}</span>
      <a class="review-link" href="{_esc(_location_url(location_id, mode='notes', note_id=str(note.get('id', '')), goal_id=str(summary.get('goal_id', ACTIVE_PRODUCT_GOAL_ID))))}">Review</a>
    </article>"""


def _observation_compact_row(
    note: dict[str, object],
    location_id: str,
    selected_note: dict[str, object] | None,
    goal_id: str,
) -> str:
    note_id = str(note.get("id", ""))
    selected_class = " selected-row" if selected_note and selected_note.get("id") == note_id else ""
    return f"""
      <a class="compact-pick{selected_class}" href="{_esc(_location_url(location_id, mode='notes', note_id=note_id, goal_id=goal_id))}">
        <span>{_esc(str(note.get('severity', 'note')))}</span>
        <strong>{_esc(_short_text(str(note.get('text', '')), 76))}</strong>
        <small>{_esc(_title_status(str(note.get('ui_state', 'open'))))}</small>
      </a>"""


def _issue_compact_row(
    issue: dict[str, object],
    location_id: str,
    selected_issue: dict[str, object] | None,
    goal_id: str,
) -> str:
    issue_id = str(issue.get("id", ""))
    selected_class = " selected-row" if selected_issue and selected_issue.get("id") == issue_id else ""
    return f"""
      <a class="compact-pick{selected_class}" href="{_esc(_location_url(location_id, mode='issue', issue_id=issue_id, goal_id=goal_id))}">
        <span class="{_esc(str(issue.get('priority', 'low')))}">{_esc(str(issue.get('priority', 'low')))}</span>
        <strong>{_esc(_short_text(str(issue.get('summary', '')), 78))}</strong>
        <small>{_esc(str(issue.get('status', 'open')))}</small>
      </a>"""


def _observation_detail(note: dict[str, object], location_id: str) -> str:
    text = str(note.get("text", ""))
    state = str(note.get("ui_state", note.get("severity", "open")))
    return f"""
    <article class="detail-panel observation-detail">
      <div>
        <strong>{_esc(str(note.get('id', 'observation')))}</strong>
        <span class="badge">{_esc(_title_status(state))}</span>
      </div>
      <p>{_esc(text)}</p>
      {_observation_actions(note, location_id)}
    </article>"""


def _observation_actions(note: dict[str, object], location_id: str) -> str:
    note_id = str(note.get("id", ""))
    severity = str(note.get("severity", "note"))
    text = str(note.get("text", ""))
    return f"""
      <div class="row-actions">
        <details>
          <summary>Edit</summary>
          <form method="post" action="/observation-action" class="edit-form">
            <input type="hidden" name="return_location" value="{_esc(location_id)}">
            <input type="hidden" name="note_id" value="{_esc(note_id)}">
            <input type="hidden" name="action" value="edit">
            <textarea name="text">{_esc(text)}</textarea>
            <select name="severity">
              {_note_severity_options(severity)}
            </select>
            <button type="submit" class="quiet">Save Edit</button>
          </form>
        </details>
        {_observation_action_button(note_id, location_id, 'resolved', 'Mark Resolved')}
        {_observation_action_button(note_id, location_id, 'expected_behavior', 'Expected')}
        {_observation_action_button(note_id, location_id, 'convert_issue', 'Convert to Issue')}
        {_observation_action_button(note_id, location_id, 'archive', 'Archive')}
        {_observation_action_button(note_id, location_id, 'delete', 'Delete')}
      </div>"""


def _observation_action_button(note_id: str, location_id: str, action: str, label: str) -> str:
    return f"""
        <form method="post" action="/observation-action">
          <input type="hidden" name="return_location" value="{_esc(location_id)}">
          <input type="hidden" name="note_id" value="{_esc(note_id)}">
          <button type="submit" name="action" value="{_esc(action)}" class="quiet small">{_esc(label)}</button>
        </form>"""


def _issue_detail(issue: dict[str, object], location_id: str) -> str:
    return f"""
    <article class="detail-panel issue-detail">
      <div class="detail-head">
        <strong>{_esc(_human_issue_type(str(issue.get('type', 'issue'))))}</strong>
        <span class="badge {str(issue.get('priority', 'low'))}">{_esc(str(issue.get('priority', 'low')))}</span>
      </div>
      <p>{_esc(str(issue.get('summary', '')))}</p>
      <p class="meta">{_esc(str(issue.get('proposed_next_step', '')))}</p>
      {_issue_action_row(issue, location_id)}
      {_route_patch_panel(issue, location_id)}
    </article>"""


def _route_patch_panel(issue: dict[str, object], location_id: str) -> str:
    issue_id = str(issue.get("id", ""))
    goal_id = str(issue.get("goal_id", ACTIVE_PRODUCT_GOAL_ID))
    task_packet = issue.get("task_packet")
    patch = issue.get("route_patch")
    task_html = (
        f'<a class="review-link" href="{_esc(_artifact_url(Path(str(task_packet))))}">Task packet</a>'
        if task_packet
        else "Task packet not created"
    )
    if not isinstance(patch, dict):
        return f"""
      <section class="patch-workflow" data-issue-id="{_esc(issue_id)}">
        <div class="detail-head"><strong>Route patch</strong><span class="badge">not imported</span></div>
        <p class="meta">{task_html}</p>
        <form method="post" action="/patch-action" class="patch-import-form">
          {_patch_hidden_fields(issue_id, location_id, goal_id=goal_id)}
          <input type="hidden" name="action" value="import">
          <label>Patch YAML path <input name="patch_file" required placeholder="/path/to/reviewed-patch.yaml"></label>
          <button type="submit" class="quiet small">Import Patch</button>
        </form>
      </section>"""

    patch_id = str(patch.get("patch_id", ""))
    status = str(patch.get("status", "unknown"))
    changed_files = patch.get("changed_files", [])
    changed_html = "".join(f"<li><code>{_esc(str(path))}</code></li>" for path in changed_files)
    validation = patch.get("validation_result")
    validation_label = "not run" if validation is None else ("passed" if validation else "failed")
    blockers = patch.get("blockers", [])
    blocker_html = "".join(f"<li>{_esc(str(item))}</li>" for item in blockers)
    diff_text = str(patch.get("exact_diff", ""))
    return f"""
      <section class="patch-workflow" data-patch-id="{_esc(patch_id)}">
        <div class="detail-head">
          <strong>Route patch {_esc(patch_id)}</strong>
          <span class="badge">{_esc(status)}</span>
        </div>
        <p class="meta">{task_html}</p>
        <dl class="patch-facts">
          <dt>Base commit</dt><dd><code>{_esc(str(patch.get('base_commit', 'unknown')))}</code></dd>
          <dt>Review</dt><dd>{_esc(str(patch.get('review_state', 'not reviewed')))}</dd>
          <dt>Validation</dt><dd>{_esc(validation_label)}</dd>
          <dt>Profile</dt><dd>{_esc(str(patch.get('validation_profile', 'unknown')))}</dd>
          <dt>Promotion</dt><dd>{'eligible' if patch.get('promotion_eligible') else 'blocked'}</dd>
          <dt>Rollback</dt><dd>{'available' if patch.get('rollback_available') else 'unavailable'}</dd>
        </dl>
        <ul class="patch-files">{changed_html}</ul>
        <details class="patch-diff"><summary>Exact diff preview</summary><pre>{_esc(diff_text)}</pre></details>
        {f'<ul class="patch-blockers">{blocker_html}</ul>' if blocker_html else ''}
        <div class="row-actions patch-actions">
          {_patch_action_button(issue_id, location_id, patch_id, 'review', 'Review', status == 'imported', goal_id)}
          {_patch_action_button(issue_id, location_id, patch_id, 'preview', 'Preview', True, goal_id)}
          {_patch_action_button(issue_id, location_id, patch_id, 'prepare', 'Prepare', status == 'reviewed', goal_id)}
          {_patch_action_button(issue_id, location_id, patch_id, 'validate', 'Validate', status == 'applied_to_candidate', goal_id)}
          {_patch_action_button(issue_id, location_id, patch_id, 'compare', 'Compare', status == 'validated', goal_id)}
        </div>
        {_patch_confirmation_form(issue_id, location_id, patch_id, 'promote', 'Promote', status == 'validated', goal_id)}
        {_patch_confirmation_form(issue_id, location_id, patch_id, 'rollback', 'Rollback', status == 'promoted', goal_id)}
      </section>"""


def _patch_hidden_fields(
    issue_id: str,
    location_id: str,
    patch_id: str = "",
    goal_id: str = ACTIVE_PRODUCT_GOAL_ID,
) -> str:
    return f"""
          <input type="hidden" name="issue_id" value="{_esc(issue_id)}">
          <input type="hidden" name="return_location" value="{_esc(location_id)}">
          <input type="hidden" name="return_goal" value="{_esc(goal_id)}">
          {f'<input type="hidden" name="patch_id" value="{_esc(patch_id)}">' if patch_id else ''}"""


def _patch_action_button(
    issue_id: str,
    location_id: str,
    patch_id: str,
    action: str,
    label: str,
    enabled: bool,
    goal_id: str,
) -> str:
    return f"""
          <form method="post" action="/patch-action">
            {_patch_hidden_fields(issue_id, location_id, patch_id, goal_id)}
            <button type="submit" name="action" value="{_esc(action)}" class="quiet small"{' disabled' if not enabled else ''}>{_esc(label)}</button>
          </form>"""


def _patch_confirmation_form(
    issue_id: str,
    location_id: str,
    patch_id: str,
    action: str,
    label: str,
    enabled: bool,
    goal_id: str,
) -> str:
    return f"""
        <form method="post" action="/patch-action" class="patch-confirm-form">
          {_patch_hidden_fields(issue_id, location_id, patch_id, goal_id)}
          <input type="hidden" name="action" value="{_esc(action)}">
          <label>Type {_esc(patch_id)} to {action}
            <input name="confirmation" required placeholder="{_esc(patch_id)}"{' disabled' if not enabled else ''}>
          </label>
          <button type="submit" class="quiet small"{' disabled' if not enabled else ''}>{_esc(label)}</button>
        </form>"""


def run_patch_ui_action(
    data: dict[str, list[str]],
    *,
    repo_root: Path | None = None,
    artifacts_root: Path = PATCH_ARTIFACTS_ROOT,
) -> RoutePatchResult:
    action = _single(data, "action")
    if action == "import":
        return import_route_patch(
            Path(_single(data, "patch_file")),
            repo_root=repo_root,
            artifacts_root=artifacts_root,
            actor="route_lab",
        )
    patch_id = _single(data, "patch_id")
    if action == "review":
        return review_route_patch(
            patch_id, repo_root=repo_root, artifacts_root=artifacts_root, actor="route_lab"
        )
    if action == "preview":
        return preview_route_patch(patch_id, repo_root=repo_root, artifacts_root=artifacts_root)
    if action == "prepare":
        return prepare_route_patch(
            patch_id, repo_root=repo_root, artifacts_root=artifacts_root, actor="route_lab"
        )
    if action == "validate":
        game_file = os.environ.get("SMB3_GAME_FILE")
        return validate_route_patch(
            patch_id,
            repo_root=repo_root,
            artifacts_root=artifacts_root,
            game_path=Path(game_file) if game_file else None,
            actor="route_lab",
        )
    if action == "compare":
        return compare_route_patch(patch_id, repo_root=repo_root, artifacts_root=artifacts_root)
    confirmation = _single(data, "confirmation")
    if action == "promote":
        return promote_route_patch(
            patch_id,
            confirm_patch_id=confirmation,
            repo_root=repo_root,
            artifacts_root=artifacts_root,
            actor="route_lab",
        )
    if action == "rollback":
        return rollback_route_patch(
            patch_id,
            confirm_patch_id=confirmation,
            reason=_single(data, "reason", default="explicit Game Companion Lab rollback"),
            repo_root=repo_root,
            artifacts_root=artifacts_root,
            actor="route_lab",
        )
    raise LabUiError(f"Unsupported Game Companion Lab patch action: {action}")


def _issue_action_row(issue: dict[str, object], location_id: str) -> str:
    issue_id = str(issue.get("id", ""))
    return f"""
      <div class="row-actions">
        {_issue_action_button(issue_id, location_id, 'resolved', 'Mark Resolved')}
        {_issue_action_button(issue_id, location_id, 'expected_behavior', 'Not a Bug')}
        {_issue_action_button(issue_id, location_id, 'needs_rerun', 'Needs Rerun')}
        <form method="post" action="/codex-task">
          <input type="hidden" name="issue_id" value="{_esc(issue_id)}">
          <button type="submit" class="quiet small">Create Codex Task</button>
        </form>
        {_issue_action_button(issue_id, location_id, 'archive', 'Archive')}
        {_issue_action_button(issue_id, location_id, 'delete', 'Delete')}
      </div>"""


def _issue_action_button(issue_id: str, location_id: str, action: str, label: str) -> str:
    return f"""
        <form method="post" action="/issue-action">
          <input type="hidden" name="return_location" value="{_esc(location_id)}">
          <input type="hidden" name="issue_id" value="{_esc(issue_id)}">
          <button type="submit" name="action" value="{_esc(action)}" class="quiet small">{_esc(label)}</button>
        </form>"""


def _last_command_panel(last_command: dict[str, object]) -> str:
    if not last_command:
        return '<div class="last-command"><p>No command has run from this panel yet.</p></div>'
    status = _last_command_status(last_command)
    output = str(last_command.get("stdout") or last_command.get("stderr") or "").strip()
    command = " ".join(str(part) for part in last_command.get("command", []))
    return f"""
    <div class="last-command">
      <p><strong>Latest Output:</strong> {_esc(str(last_command.get('name', 'unknown')))} · {_esc(_title_status(status))}</p>
      <p class="meta">{_esc(str(last_command.get('ran_at', '')))}</p>
      {f'<p><code>{_esc(command)}</code></p>' if command else ''}
      {_artifact_links(output)}
      {f'<pre>{_esc(output[-4000:])}</pre>' if output else ''}
    </div>"""


def _selected_location(
    locations: list[dict[str, object]],
    *,
    selected_location_id: str | None = None,
) -> dict[str, object]:
    if selected_location_id:
        normalized = _location_id_for_artifact(selected_location_id)
        for location in locations:
            if location.get("id") == normalized:
                return location
    for location in locations:
        if location.get("open_issues"):
            return location
    for location in locations:
        if str(location.get("status")) == "blocked":
            return location
    return locations[0] if locations else {}


def _route_state(location: dict[str, object]) -> str:
    if str(location.get("segment_status", "")) == "planned":
        return "planned"
    status = str(location.get("status", "unknown"))
    if status == "works":
        return "learned"
    if status == "blocked" or location.get("open_issues"):
        return "failed"
    if status in {"needs review", "bridged", "flaky"}:
        return "needs validation"
    return "unknown"


def _latest_evidence(
    summary: dict[str, object],
    last_command: dict[str, object],
    selected: dict[str, object],
) -> dict[str, object]:
    output = str(last_command.get("stdout") or last_command.get("stderr") or "")
    candidates = _artifact_paths_from_output(output)
    session_dir = summary.get("session_dir")
    if isinstance(session_dir, str) and session_dir:
        candidates.append(Path(session_dir))

    image = _first_existing_image(candidates)
    details: list[tuple[str, str]] = [
        ("Selected location", str(selected.get("label", "Route"))),
        ("Route state", _title_status(_route_state(selected))),
    ]
    artifact_root = _first_existing_path(candidates)
    if artifact_root is not None:
        details.append(("Artifact", str(artifact_root)))
    return {"image": image, "details": details}


def _artifact_paths_from_output(output: str) -> list[Path]:
    paths = []
    interesting_keys = {
        "session_dir",
        "manifest",
        "review_file",
        "report",
        "html",
        "contact_sheet",
        "artifacts_dir",
    }
    for raw_line in output.splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        if key.strip() not in interesting_keys:
            continue
        path = Path(value.strip()).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        paths.append(path)
    return paths


def _first_existing_path(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _first_existing_image(paths: list[Path]) -> Path | None:
    preferred_names = ("contact_sheet.png", "latest.png", "screenshot.png")
    search_roots = []
    for path in paths:
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif"}:
            return path
        if path.is_dir():
            search_roots.append(path)
    for root in search_roots:
        for name in preferred_names:
            candidate = root / name
            if candidate.is_file():
                return candidate
        for candidate in sorted(root.rglob("*")):
            if candidate.is_file() and candidate.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif"}:
                return candidate
    return None


def _artifact_url(path: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ARTIFACT_DIR.resolve())
    except ValueError:
        return resolved.as_uri()
    return "/artifacts/" + "/".join(relative.parts)


def _latest_observed_state(last_command: dict[str, object]) -> str:
    output = str(last_command.get("stdout") or last_command.get("stderr") or "")
    if not output:
        return "No run has been captured from this panel yet."
    interesting = [
        line
        for line in output.splitlines()
        if any(token in line.lower() for token in ("failed", "success", "metrics_passed", "primary_segment", "session_dir"))
    ]
    return interesting[-1] if interesting else output.splitlines()[-1]


def _notes_for_location(summary: dict[str, object], selected: dict[str, object]) -> list[dict[str, object]]:
    selected_id = str(selected.get("id", ""))
    notes = _list_dicts(summary.get("notes", []))
    return [
        note
        for note in notes
        if _location_id_for_artifact(str(note.get("segment_id"))) == selected_id
        and str(note.get("ui_state", "")) != "archived"
    ]


def _selected_mode(
    requested: str | None,
    notes: list[dict[str, object]],
    issues: list[dict[str, object]],
    selected_note_id: str | None,
    selected_issue_id: str | None,
) -> str:
    if selected_issue_id:
        return "issue"
    if selected_note_id:
        return "notes"
    if requested in {"add", "notes", "issue"}:
        return requested
    return "issue" if issues else "add"


def _selected_note(notes: list[dict[str, object]], note_id: str | None) -> dict[str, object] | None:
    if note_id:
        for note in notes:
            if str(note.get("id")) == note_id:
                return note
    return notes[0] if notes else None


def _selected_issue(issues: list[dict[str, object]], issue_id: str | None) -> dict[str, object] | None:
    if issue_id:
        for issue in issues:
            if str(issue.get("id")) == issue_id:
                return issue
    return issues[0] if issues else None


def _issues_for_location(summary: dict[str, object], selected: dict[str, object]) -> list[dict[str, object]]:
    selected_id = str(selected.get("id", ""))
    return [
        issue
        for issue in _list_dicts(summary.get("issues", []))
        if _location_id_for_artifact(str(issue.get("segment_id"))) == selected_id
        and _is_active_issue(issue)
    ]


def _sorted_notes(summary: dict[str, object], selected: dict[str, object]) -> list[dict[str, object]]:
    selected_id = str(selected.get("id", ""))
    notes = [
        note
        for note in _list_dicts(summary.get("notes", []))
        if str(note.get("ui_state", "")) != "archived"
    ]
    return sorted(
        notes,
        key=lambda note: (
            _location_id_for_artifact(str(note.get("segment_id"))) != selected_id,
            str(note.get("created_at", "")),
        ),
        reverse=False,
    )


def _sorted_issues(summary: dict[str, object], selected: dict[str, object]) -> list[dict[str, object]]:
    selected_id = str(selected.get("id", ""))
    issues = [issue for issue in _list_dicts(summary.get("issues", [])) if _is_active_issue(issue)]
    return sorted(
        issues,
        key=lambda issue: (
            _location_id_for_artifact(str(issue.get("segment_id"))) != selected_id,
            _priority_rank_for_ui(str(issue.get("priority", "low"))),
            str(issue.get("id", "")),
        ),
    )


def _is_active_issue(issue: dict[str, object]) -> bool:
    return str(issue.get("status", "open")) in {"open", "needs_rerun"}


def _priority_rank_for_ui(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2, "none": 3}.get(priority, 4)


def _note_severity_options(selected: str) -> str:
    labels = (
        ("bug", "failure"),
        ("objective", "expected behavior"),
        ("map_action", "route instruction"),
        ("harden", "validation note"),
        ("guide_detail", "positive evidence"),
        ("note", "note"),
    )
    return "".join(
        f'<option value="{_esc(value)}"{" selected" if value == selected else ""}>{_esc(label)}</option>'
        for value, label in labels
    )


def _short_text(value: str, limit: int) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(0, limit - 1)].rstrip() + "..."


def _last_command_status(last_command: dict[str, object]) -> str:
    if not last_command:
        return "unknown"
    try:
        return "passed" if int(last_command.get("returncode", 1)) == 0 else "failed"
    except (TypeError, ValueError):
        return "unknown"


def _title_status(status: str) -> str:
    return status.replace("_", " ").replace("-", " ").title()


def _icon_name_for_location(location: dict[str, object]) -> str:
    location_type = str(location.get("type", "level"))
    location_id = str(location.get("id", ""))
    if location_type == "map":
        return "map_icon.png"
    if location_type == "fortress":
        return "fortress_icon.png"
    if location_type == "airship":
        return "airship_icon.png"
    if location_type == "world_clear":
        return "king_icon.png"
    if location_type == "inventory":
        return "whistle_icon.png"
    if location_type in {"warp_zone", "pipe"}:
        return "map_icon.png"
    if "toad" in location_id:
        return "toad_house_icon.png"
    if "spade" in location_id:
        return "spade_icon.png"
    if "hammer" in location_id:
        return "hammer_bro_icon.png"
    if location_id == "world_1_3":
        return "whistle_icon.png"
    return "level_icon.png"


def _icon_fallback(location: dict[str, object]) -> str:
    location_type = str(location.get("type", "level"))
    label = str(location.get("label", "?"))
    fallbacks = {
        "map": "MAP",
        "fortress": "FORT",
        "airship": "AIR",
        "world_clear": "KING",
        "map_event": "EVT",
        "map_enemy": "HB",
        "inventory": "ITEM",
        "warp_zone": "WARP",
        "pipe": "PIPE",
    }
    return fallbacks.get(location_type, label[:3].upper())


def _asset_icon(filename: str, fallback: str, alt: str) -> str:
    asset_path = LOCAL_ASSET_DIR / filename
    if asset_path.is_file():
        return (
            '<span class="asset-icon">'
            f'<img src="/assets/local/{_esc(filename)}" alt="{_esc(alt)}">'
            "</span>"
        )
    return f'<span class="asset-icon" aria-hidden="true">{_esc(fallback)}</span>'


def _artifact_links(output: str) -> str:
    links = []
    interesting_keys = {
        "session_dir",
        "manifest",
        "notes_file",
        "review_file",
        "report",
        "html",
        "proposal",
        "proposals_file",
        "issues_file",
        "ui_summary",
    }
    for raw_line in output.splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in interesting_keys or not value:
            continue
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        links.append((key.replace("_", " "), path))
        if len(links) >= 6:
            break
    if not links:
        return ""
    rendered = "".join(f'<a href="{_esc(_artifact_url(path))}">{_esc(label)}</a>' for label, path in links)
    return f'<div class="artifact-links">{rendered}</div>'


def _run_world_1_from_form(data: dict[str, list[str]]) -> dict[str, object]:
    game_file = os.environ.get("SMB3_GAME_FILE")
    if not game_file:
        raise LabUiError("Set SMB3_GAME_FILE before running from Game Companion Lab.")
    speed = _single(data, "speed", default="4")
    attempts = int(_single(data, "attempts", default="1"))
    mode = _single(data, "mode", default="show")
    if speed not in SUPPORTED_SPEEDS:
        raise LabUiError("Unsupported speed")
    if mode == "gate":
        command = f"run world 8 double whistle arrival {attempts} times at {speed}x"
    else:
        command = f"show me the route at {speed}x"
    result = start_session(
        command,
        game_path=Path(game_file),
        attempts=attempts,
        artifacts_root=Path("artifacts/sessions"),
        capture_images=False,
        capture_ticks=True,
    )
    return {
        "command": command,
        "attempts": attempts,
        "summary": result.to_text(),
    }


def _test_command(action: str) -> tuple[str, ...]:
    if action == "unit_tests":
        return (sys.executable, "-m", "pytest", "-q")
    if action == "phase_gate":
        return ("bash", "scripts/validate_phase0.sh")
    if action == "render_check":
        return (sys.executable, "-m", "smb3_agent", "lab", "ui-render", "--output", "artifacts/ui/latest.html")
    raise LabUiError(f"Unknown test action: {action}")


def _issue_id_from_form(data: dict[str, list[str]]) -> str:
    issue_id = _single(data, "issue_id", default="")
    if issue_id:
        return issue_id
    index = int(_single(data, "issue_index"))
    summary = build_control_panel_summary()
    issues = summary.get("issues", [])
    if not isinstance(issues, list) or index < 1 or index > len(issues):
        raise LabUiError("Issue selection is no longer available. Refresh the panel and try again.")
    issue = issues[index - 1]
    if not isinstance(issue, dict) or not issue.get("id"):
        raise LabUiError("Issue selection is invalid. Refresh the panel and try again.")
    return str(issue["id"])


def _run_command_capture(action: str, command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    timeout = 240 if action == "phase_gate" else 120
    env = dict(os.environ)
    env["PYTHON"] = sys.executable
    return subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )


def _update_observation_latest(
    note_id: str,
    action: str,
    data: dict[str, list[str]],
) -> None:
    session_dir = _latest_session_dir_required()
    notes_path = session_dir / "notes.yaml"
    notes_doc = _load_yaml(notes_path)
    notes = notes_doc.get("notes", [])
    if not isinstance(notes, list):
        raise LabUiError(f"Invalid notes file: {notes_path}")

    matched = None
    for note in notes:
        if isinstance(note, dict) and str(note.get("id")) == note_id:
            matched = note
            break
    if matched is None:
        raise LabUiError(f"Observation not found: {note_id}")

    if action == "delete":
        notes_doc["notes"] = [note for note in notes if not (isinstance(note, dict) and str(note.get("id")) == note_id)]
        _remove_note_from_issues(session_dir, note_id)
        _write_yaml(notes_path, notes_doc)
        return
    if action == "edit":
        text = _single(data, "text", default="").strip()
        if not text:
            raise LabUiError("Observation text is required")
        matched["text"] = text
        matched["severity"] = _single(data, "severity", default=str(matched.get("severity", "note")))
        matched["updated_at"] = _now()
        matched.setdefault("interpretation", {})["status"] = "pending_review"
    elif action == "resolved":
        matched["ui_state"] = "resolved"
        matched["resolved_at"] = _now()
        matched.setdefault("interpretation", {})["status"] = "resolved"
        _resolve_issues_for_note(session_dir, note_id)
    elif action == "expected_behavior":
        matched["ui_state"] = "expected_behavior"
        matched["severity"] = "guide_detail"
        matched["updated_at"] = _now()
        interpretation = matched.setdefault("interpretation", {})
        interpretation["status"] = "accepted"
        interpretation["classification"] = "expected_behavior"
        _accept_issues_for_note(session_dir, note_id)
    elif action == "convert_issue":
        matched["ui_state"] = "open"
        matched["severity"] = "bug"
        matched["updated_at"] = _now()
        matched.setdefault("interpretation", {})["status"] = "pending_review"
        _ensure_issue_for_note(session_dir, matched)
    elif action == "archive":
        matched["ui_state"] = "archived"
        matched["archived_at"] = _now()
    else:
        raise LabUiError(f"Unknown observation action: {action}")
    _write_yaml(notes_path, notes_doc)


def _update_issue_latest(issue_id: str, action: str) -> None:
    session_dir = _latest_session_dir_required()
    issues_path = session_dir / "issues.yaml"
    issues_doc = _load_yaml(issues_path)
    issues = issues_doc.get("issues", [])
    if not isinstance(issues, list):
        raise LabUiError(f"Invalid issues file: {issues_path}")

    matched = None
    for issue in issues:
        if isinstance(issue, dict) and str(issue.get("id")) == issue_id:
            matched = issue
            break
    if matched is None:
        raise LabUiError(f"Issue not found: {issue_id}")

    if action == "delete":
        issues_doc["issues"] = [issue for issue in issues if not (isinstance(issue, dict) and str(issue.get("id")) == issue_id)]
        _write_yaml(issues_path, issues_doc)
        return
    if action == "resolved":
        matched["status"] = "resolved"
        matched["actionable"] = False
        matched["resolved_at"] = _now()
    elif action == "expected_behavior":
        matched["status"] = "accepted"
        matched["actionable"] = False
        matched["type"] = "expected_behavior"
        matched["accepted_at"] = _now()
    elif action == "archive":
        matched["status"] = "archived"
        matched["actionable"] = False
        matched["archived_at"] = _now()
    elif action == "needs_rerun":
        matched["status"] = "needs_rerun"
        matched["actionable"] = True
        matched["updated_at"] = _now()
    else:
        raise LabUiError(f"Unknown issue action: {action}")
    _write_yaml(issues_path, issues_doc)


def _remove_note_from_issues(session_dir: Path, note_id: str) -> None:
    issues_path = session_dir / "issues.yaml"
    issues_doc = _load_yaml(issues_path)
    issues = issues_doc.get("issues", [])
    if not isinstance(issues, list):
        return
    kept = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        source_notes = [str(value) for value in issue.get("source_notes", [])]
        if note_id in source_notes:
            source_notes = [value for value in source_notes if value != note_id]
            issue["source_notes"] = source_notes
        if source_notes or note_id not in [str(value) for value in issue.get("source_notes", [])]:
            kept.append(issue)
    issues_doc["issues"] = [issue for issue in kept if issue.get("source_notes")]
    _write_yaml(issues_path, issues_doc)


def _resolve_issues_for_note(session_dir: Path, note_id: str) -> None:
    _update_issues_for_note(session_dir, note_id, status="resolved", actionable=False)


def _accept_issues_for_note(session_dir: Path, note_id: str) -> None:
    _update_issues_for_note(session_dir, note_id, status="accepted", actionable=False, issue_type="expected_behavior")


def _update_issues_for_note(
    session_dir: Path,
    note_id: str,
    *,
    status: str,
    actionable: bool,
    issue_type: str | None = None,
) -> None:
    issues_path = session_dir / "issues.yaml"
    issues_doc = _load_yaml(issues_path)
    issues = issues_doc.get("issues", [])
    if not isinstance(issues, list):
        return
    changed = False
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        if note_id in [str(value) for value in issue.get("source_notes", [])]:
            issue["status"] = status
            issue["actionable"] = actionable
            issue["updated_at"] = _now()
            if issue_type is not None:
                issue["type"] = issue_type
            changed = True
    if changed:
        _write_yaml(issues_path, issues_doc)


def _ensure_issue_for_note(session_dir: Path, note: dict[str, object]) -> None:
    issues_path = session_dir / "issues.yaml"
    issues_doc = _load_yaml(issues_path) or {"issues": []}
    issues = issues_doc.setdefault("issues", [])
    if not isinstance(issues, list):
        raise LabUiError(f"Invalid issues file: {issues_path}")
    note_id = str(note.get("id"))
    for issue in issues:
        if isinstance(issue, dict) and note_id in [str(value) for value in issue.get("source_notes", [])]:
            issue["status"] = "open"
            issue["actionable"] = True
            issue["type"] = "user_observation"
            issue["updated_at"] = _now()
            _write_yaml(issues_path, issues_doc)
            return
    segment_id = str(note.get("segment_id", "unknown"))
    issue_id = _next_issue_id(issues, segment_id)
    issues.append(
        {
            "id": issue_id,
            "segment_id": segment_id,
            "type": "user_observation",
            "priority": "medium",
            "status": "open",
            "actionable": True,
            "source_notes": [note_id],
            "summary": str(note.get("text", "")),
            "proposed_next_step": "Patch or validate this observed route behavior.",
            "created_at": _now(),
        }
    )
    _write_yaml(issues_path, issues_doc)


def _next_issue_id(issues: list[object], segment_id: str) -> str:
    prefix = f"issue_{segment_id}_"
    indexes = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        issue_id = str(issue.get("id", ""))
        if issue_id.startswith(prefix):
            try:
                indexes.append(int(issue_id.removeprefix(prefix)))
            except ValueError:
                continue
    return f"{prefix}{(max(indexes) + 1 if indexes else 1):03d}"


def _notes_from_form(data: dict[str, list[str]]) -> list[dict[str, object]]:
    notes: list[dict[str, object]] = []
    for key, values in data.items():
        if not key.startswith("note__"):
            continue
        location_id = key.removeprefix("note__")
        text = "\n".join(value.strip() for value in values if value.strip()).strip()
        if not text:
            continue
        severity = _single(data, f"severity__{location_id}", default="note")
        anchor_type = _single(data, f"anchor__{location_id}", default="") or None
        for chunk in _split_note_text(text):
            notes.append(
                {
                    "segment_id": location_id,
                    "text": chunk,
                    "severity": severity,
                    "anchor_type": anchor_type,
                }
            )
    return notes


def _split_note_text(text: str) -> list[str]:
    chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    return chunks or [text]


def _load_locations(contract: GoalContract) -> list[dict[str, object]]:
    data = _load_yaml(WORLD_1_LOCATION_PATH)
    locations = data.get("locations", [])
    if not isinstance(locations, list):
        raise LabUiError(f"Invalid location model: {WORLD_1_LOCATION_PATH}")
    by_segment = {
        str(location.get("segment_id")): location
        for location in locations
        if isinstance(location, dict) and location.get("id") and location.get("segment_id")
    }
    missing = [segment_id for segment_id in contract.segments if segment_id not in by_segment]
    if missing:
        raise LabUiError(
            f"Location model is missing active goal segment(s): {', '.join(missing)}"
        )
    return [by_segment[segment_id] for segment_id in contract.segments]


def _default_location_status(segment_status: str) -> str:
    if segment_status == "solved":
        return "works"
    if segment_status in {"flaky", "bridged"}:
        return "needs review"
    if segment_status in {"planned", "blocked"}:
        return "blocked"
    return "unknown"


def _route_role_label(classification: str) -> str:
    return {
        "objective_milestone": "goal milestone",
        "game_prerequisite": "required path",
        "optional": "optional",
        "recovery_only": "recovery only",
        "diagnostic_route": "diagnostic only",
    }.get(classification, "route step")


def _location_status(location: dict[str, object], issues: list[dict[str, object]]) -> str:
    if any(issue.get("priority") == "high" and _is_active_issue(issue) for issue in issues):
        return "blocked"
    if any(_is_active_issue(issue) for issue in issues):
        return "needs review"
    return str(location.get("default_status", "unknown"))


def _location_id_for_artifact(value: str) -> str:
    aliases = {
        "world_1_1_clear": "world_1_1",
        "world_1_2_clear": "world_1_2",
        "world_1_3_whistle": "world_1_3",
        "world_1_fortress_whistle": "world_1_fortress",
        "world_1_4_clear": "world_1_4",
        "world_1_5_clear": "world_1_5",
        "world_1_5_water_path": "world_1_5",
        "world_1_6_clear": "world_1_6",
        "world_1_airship_to_king": "world_1_airship",
        "world_2_map_arrival_with_two_whistles": "world_2_map",
        "world_2_first_whistle_use": "world_2_first_whistle",
        "warp_zone_5_6_7_tier": "warp_zone_5_6_7",
        "warp_zone_second_whistle_use": "warp_zone_second_whistle",
        "warp_zone_world_8_tier": "warp_zone_world_8",
        "world_8_pipe_entry": "world_8_pipe",
        "world_8_big_tanks_clear": "world_8_big_tanks",
        "world_8_battleships_clear": "world_8_battleships",
        "world_8_hand_trap_right_clear": "world_8_hand_trap_right",
        "world_8_hand_trap_center_clear": "world_8_hand_trap_center",
        "world_8_hand_trap_left_clear": "world_8_hand_trap_left",
        "world_8_jet_clear": "world_8_jet",
        "world_8_1_clear": "world_8_1",
        "world_8_2_clear": "world_8_2",
        "world_8_fortress_clear": "world_8_fortress",
        "world_8_super_tanks_clear": "world_8_super_tanks",
        "world_8_bowser_castle_finish": "world_8_bowser_castle",
        "world_8_map_arrival": "world_8_map",
        "fortress": "world_1_fortress",
        "castle": "world_1_airship",
        "airship": "world_1_airship",
        "map": "world_1_map",
    }
    return aliases.get(value, value)


def _label_for_location(summary: dict[str, object], artifact_id: str) -> str:
    location_id = _location_id_for_artifact(artifact_id)
    for location in summary.get("locations", []):
        if isinstance(location, dict) and location.get("id") == location_id:
            return str(location.get("label", location_id))
    return "World 1"


def _human_issue_type(issue_type: str) -> str:
    return issue_type.replace("_", " ")


def _status_class(status: str) -> str:
    return status.lower().replace(" ", "-")


def _state_class(status: str) -> str:
    normalized = _status_class(status)
    if normalized in {"needs-review", "needs-validation", "bridged", "flaky"}:
        return "validation"
    return normalized


def _options(values: tuple[str, ...], selected: str, *, suffix: str = "") -> str:
    rendered = []
    for value in values:
        selected_attr = " selected" if value == selected else ""
        rendered.append(f'<option value="{_esc(value)}"{selected_attr}>{_esc(value + suffix)}</option>')
    return "".join(rendered)


def _single(data: dict[str, list[str]], key: str, *, default: str | None = None) -> str:
    values = data.get(key)
    if not values:
        if default is not None:
            return default
        raise LabUiError(f"Missing form field: {key}")
    return values[0]


def _location_url(
    location_id: str,
    *,
    mode: str | None = None,
    note_id: str | None = None,
    issue_id: str | None = None,
    goal_id: str = ACTIVE_PRODUCT_GOAL_ID,
) -> str:
    params: list[tuple[str, str]] = []
    if goal_id != ACTIVE_PRODUCT_GOAL_ID:
        params.append(("goal", goal_id))
    if location_id:
        params.append(("location", _location_id_for_artifact(location_id)))
    if mode:
        params.append(("mode", mode))
    if note_id:
        params.append(("note", note_id))
    if issue_id:
        params.append(("issue", issue_id))
    return "/lab?" + urlencode(params) if params else "/lab"


def _goal_subtitle(goal_id: str) -> str:
    return load_goal_contract(resolve_goal_path(goal_id)).display_subtitle


def _goal_switcher(goal_id: str) -> str:
    links = []
    for contract in load_product_goal_contracts():
        selected = " goal-selected" if contract.id == goal_id else ""
        href = "/lab" if contract.id == ACTIVE_PRODUCT_GOAL_ID else f"/lab?goal={contract.id}"
        links.append(
            f'<a class="goal-choice{selected}" href="{_esc(href)}">'
            f"{_esc(contract.display_name)}</a>"
        )
    return '<nav class="goal-switcher" aria-label="Goal">' + "".join(links) + "</nav>"


def _product_goal_ids() -> frozenset[str]:
    return frozenset(contract.id for contract in load_product_goal_contracts())


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_yaml(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _write_last_command(
    name: str,
    command: tuple[str, ...],
    returncode: int,
    stdout: str,
    stderr: str,
) -> None:
    LAST_COMMAND_PATH.parent.mkdir(parents=True, exist_ok=True)
    _write_yaml(
        LAST_COMMAND_PATH,
        {
            "name": name,
            "command": list(command),
            "returncode": returncode,
            "stdout": stdout[-12000:],
            "stderr": stderr[-12000:],
            "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )


def _write_yaml(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _latest_session_dir_if_any() -> Path | None:
    latest = Path("artifacts/sessions/latest.txt")
    if not latest.is_file():
        return None
    value = latest.read_text(encoding="utf-8").strip()
    if not value:
        return None
    path = Path(value)
    return path if path.is_dir() else None


def _latest_session_dir_required() -> Path:
    session_dir = _latest_session_dir_if_any()
    if session_dir is None:
        raise LabUiError("No active lab session is available.")
    return session_dir


def _list_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _esc(value: str) -> str:
    return html.escape(value, quote=True)
