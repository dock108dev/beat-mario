from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys

from smb3_agent.commands import CommandParseError, parse_command, run_command
from smb3_agent.detection.state_detector import detect_state
from smb3_agent.fceux_harness import parse_fceux_log, run_fceux_1_1
from smb3_agent.fceux_images import convert_gd_directory, write_contact_sheet
from smb3_agent.goals import (
    ACTIVE_PRODUCT_GOAL_ID,
    GoalValidationError,
    load_goal_contract,
    resolve_goal_path,
    run_goal_contract,
)
from smb3_agent.lab import (
    LabError,
    add_note_to_latest,
    build_issue_ledger_latest,
    propose_variants_from_latest,
    review_latest_session,
    start_session,
    write_codex_task_latest,
    write_ui_summary_latest,
)
from smb3_agent.lab_ui import (
    LabUiError,
    default_companion_session,
    render_companion_ui,
    render_combined_catalog,
    render_lab_ui,
    run_lab_ui_server,
)
from smb3_agent.companion_catalog import (
    CatalogPreferenceStore,
    CatalogPreferences,
    CatalogSession,
    CompanionCatalogError,
    build_default_catalog_registry,
)
from smb3_agent.experimental_adapters import (
    ExperimentalAdapterError,
    default_install_root,
    default_scaffold_root,
    discover_installed_providers,
    inspect_contract,
    install_adapter,
    installation_status,
    load_contract as load_experimental_contract,
    run_conformance,
    scaffold_adapter,
    uninstall_adapter,
)
from smb3_agent.learning import LearningError, LocalLearningStore, backfill_run_library
from smb3_agent.metrics import LocalMetricsStore, MetricsError, metric_definitions
from smb3_agent.run_library import LocalRunLibrary
from smb3_agent.observe import ObserveError, run_observed_segment
from smb3_agent.recovery import RecoveryError, simulate_recovery
from smb3_agent.route_patch import (
    RoutePatchError,
    compare_route_patch,
    import_route_patch,
    prepare_route_patch,
    preview_route_patch,
    reject_route_patch,
    review_route_patch,
    rollback_route_patch,
    promote_route_patch,
    validate_route_patch,
)
from smb3_agent.reliability import (
    run_reliability_gate,
    run_watchable_playback,
)
from smb3_agent.review import compare_logs, review_log
from smb3_agent.segments import (
    SegmentValidationError,
    load_segment_catalog,
    render_goal_status,
    validate_goal_segments,
)
from smb3_agent.scenarios import (
    DEFAULT_CATALOG as DEFAULT_SCENARIO_CATALOG,
    ScenarioError,
    final_campaign_readiness,
    load_scenario_catalog,
    scenario_plan,
)
from smb3_agent.stardew_adapter import (
    ADAPTER_CONTRACT_PATH,
    InputOwner,
    OperatorLifecycle,
    OperatorView,
    StardewAdapterError,
    load_stardew_contract,
    render_stardew_operator,
)
from smb3_agent.unattended import (
    ACKNOWLEDGEMENT,
    DeclaredDisplayProvider,
    MarioUnattendedProvider,
    NoDisplayProvider,
    ProbedDisplayProvider,
    StardewUnattendedProvider,
    UnattendedError,
    UnattendedRunner,
    compare_attempts,
    load_manifest,
    source_identity,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smb3_agent",
        description="Game Companion Mario adapter and reliability tools",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe = subparsers.add_parser("probe", help="Run backend readiness probes")
    probe_subparsers = probe.add_subparsers(dest="backend", required=True)

    mednafen = probe_subparsers.add_parser("mednafen", help="Probe local Mednafen control/capture")
    mednafen.add_argument("--game-file", required=True, help="Path to the local game file")
    mednafen.add_argument(
        "--artifacts-dir",
        default="artifacts/probes",
        help="Directory for screenshots and probe metadata",
    )
    mednafen.add_argument("--startup-seconds", type=float, default=3.0)
    mednafen.add_argument("--after-start-seconds", type=float, default=3.0)

    detect = subparsers.add_parser("detect", help="Classify a captured game screenshot")
    detect.add_argument("--image", required=True, help="Path to a game screenshot")
    detect.add_argument(
        "--fixtures-dir",
        default="data/fixtures/state",
        help="Directory containing state fixture screenshots",
    )

    task = subparsers.add_parser("task", help="Run scripted game tasks")
    task_subparsers = task.add_subparsers(dest="task_name", required=True)

    start_game = task_subparsers.add_parser("start-game", help="Start a fresh game and capture evidence")
    start_game.add_argument("--game-file", required=True, help="Path to the local game file")
    start_game.add_argument(
        "--artifacts-dir",
        default="artifacts/tasks/start-game",
        help="Directory for screenshots and task metadata",
    )
    start_game.add_argument(
        "--fixtures-dir",
        default="data/fixtures/state",
        help="Directory for stable detector fixture screenshots",
    )
    start_game.add_argument("--startup-seconds", type=float, default=3.0)

    enter_1_1 = task_subparsers.add_parser("enter-1-1", help="Start a fresh game and enter World 1-1")
    enter_1_1.add_argument("--game-file", required=True, help="Path to the local game file")
    enter_1_1.add_argument(
        "--artifacts-dir",
        default="artifacts/tasks/enter-1-1",
        help="Directory for screenshots and task metadata",
    )
    enter_1_1.add_argument(
        "--fixtures-dir",
        default="data/fixtures/state",
        help="Directory for stable detector fixture screenshots",
    )
    enter_1_1.add_argument("--startup-seconds", type=float, default=3.0)

    checkpoint_1_1 = task_subparsers.add_parser(
        "checkpoint-1-1",
        help="Start a fresh game, enter World 1-1, and save Mednafen state slot 1",
    )
    checkpoint_1_1.add_argument("--game-file", required=True, help="Path to the local game file")
    checkpoint_1_1.add_argument(
        "--artifacts-dir",
        default="artifacts/tasks/checkpoint-1-1",
        help="Directory for screenshots and task metadata",
    )
    checkpoint_1_1.add_argument(
        "--fixtures-dir",
        default="data/fixtures/state",
        help="Directory for stable detector fixture screenshots",
    )
    checkpoint_1_1.add_argument("--startup-seconds", type=float, default=3.0)
    checkpoint_1_1.add_argument("--slot", type=int, default=0)

    load_checkpoint_1_1 = task_subparsers.add_parser(
        "load-checkpoint-1-1",
        help="Load saved Mednafen state slot 0 and verify World 1-1",
    )
    load_checkpoint_1_1.add_argument("--game-file", required=True, help="Path to the local game file")
    load_checkpoint_1_1.add_argument(
        "--artifacts-dir",
        default="artifacts/tasks/load-checkpoint-1-1",
        help="Directory for screenshots and task metadata",
    )
    load_checkpoint_1_1.add_argument(
        "--fixtures-dir",
        default="data/fixtures/state",
        help="Directory containing state fixture screenshots",
    )
    load_checkpoint_1_1.add_argument("--startup-seconds", type=float, default=3.0)
    load_checkpoint_1_1.add_argument("--slot", type=int, default=0)

    run_1_1_script = task_subparsers.add_parser(
        "run-1-1-script",
        help="Load the 1-1 checkpoint and execute a YAML input script",
    )
    run_1_1_script.add_argument("--game-file", required=True, help="Path to the local game file")
    run_1_1_script.add_argument(
        "--script",
        default="data/routes/scripts/world_1_1_draft.yaml",
        help="YAML input script to execute from the 1-1 checkpoint",
    )
    run_1_1_script.add_argument(
        "--artifacts-dir",
        default="artifacts/tasks/run-1-1-script",
        help="Directory for screenshots, input trace, and task metadata",
    )
    run_1_1_script.add_argument(
        "--fixtures-dir",
        default="data/fixtures/state",
        help="Directory containing state fixture screenshots",
    )
    run_1_1_script.add_argument("--startup-seconds", type=float, default=3.0)
    run_1_1_script.add_argument("--slot", type=int, default=0)
    run_1_1_script.add_argument(
        "--save-final-slot",
        type=int,
        default=None,
        help="Save the emulator state to this slot after the script and final capture",
    )
    run_1_1_script.add_argument(
        "--sample-interval-seconds",
        type=float,
        default=0.1,
        help="Seconds between captured evidence frames while the input script runs; use 0 to disable sampling",
    )

    fceux_1_1 = task_subparsers.add_parser(
        "fceux-1-1",
        help="Run the memory-aware FCEUX World 1-1 route",
    )
    fceux_1_1.add_argument("--game-file", required=True, help="Path to the local game file")
    fceux_1_1.add_argument(
        "--script",
        default="scripts/fceux_1_1_agent.lua",
        help="Lua route script to load in FCEUX",
    )
    fceux_1_1.add_argument(
        "--artifacts-dir",
        default="artifacts/fceux/cli_1_1",
        help="Directory for route logs and optional screenshots",
    )
    fceux_1_1.add_argument("--attempts", type=int, default=10)
    fceux_1_1.add_argument("--capture-images", action="store_true")
    fceux_1_1.add_argument("--capture-ticks", action="store_true")
    fceux_1_1.add_argument("--after-attempt-frames", type=int, default=None)
    fceux_1_1.add_argument(
        "--post-1-1-probe",
        choices=[
            "enter_1_2",
            "enter_1_3",
            "run_1_2_naive",
            "run_1_3_whistle",
            "run_1_3_whistle_to_castle",
            "run_1_fortress_whistle",
            "run_1_fortress_to_1_5_map",
            "run_1_5_clear_after_fortress",
            "run_1_6_after_1_5_clear",
            "run_1_fortress_map_sequence",
            "run_1_4_after_fortress",
            "run_1_4_map_sequence",
            "run_1_5_after_1_4",
            "run_1_5_map_sequence",
            "run_1_5_water_after_roamer",
            "run_1_5_water_map_sequence",
            "run_1_6_after_water",
            "run_1_castle_after_1_6",
            "run_1_castle_map_bridge_only",
            "run_1_5_water_bridge_only",
            "run_1_6_after_water_bridge",
            "run_1_castle_after_water_bridge_1_6",
            "run_1_fortress_second_lava_search",
            "run_1_fortress_mid_search",
            "run_1_fortress_flight_search",
        ],
        default=None,
        help="Optional probe to run after the final successful 1-1 clear",
    )
    fceux_1_1.add_argument(
        "--set-env",
        action="append",
        default=[],
        help="Set an environment override for the Lua route, formatted KEY=VALUE",
    )
    fceux_1_1.add_argument(
        "--require-perfect",
        action="store_true",
        help="Exit non-zero unless every attempt clears the level",
    )
    fceux_1_1.add_argument(
        "--require-post-probe-clear",
        action="store_true",
        help="Exit non-zero unless the optional post-1-1 probe reports a course clear",
    )

    review_fceux = task_subparsers.add_parser(
        "review-fceux-log",
        help="Summarize a FCEUX route log",
    )
    review_fceux.add_argument("--log", required=True, help="Path to a FCEUX route log")
    review_fceux.add_argument("--attempts", type=int, default=None)

    fceux_contact_sheet = task_subparsers.add_parser(
        "fceux-contact-sheet",
        help="Convert FCEUX screenshots to PNG and write a contact sheet",
    )
    fceux_contact_sheet.add_argument("--input-dir", required=True, help="Directory containing .gd screenshots")
    fceux_contact_sheet.add_argument(
        "--output-dir",
        default=None,
        help="Directory for converted PNG screenshots; defaults to INPUT_DIR/png",
    )
    fceux_contact_sheet.add_argument(
        "--sheet",
        default=None,
        help="Path for the contact sheet; defaults to OUTPUT_DIR/contact_sheet.png",
    )
    fceux_contact_sheet.add_argument("--columns", type=int, default=4)

    reliability = subparsers.add_parser(
        "reliability", help="Run the fresh-process product reliability gate or review playback"
    )
    reliability_subparsers = reliability.add_subparsers(
        dest="reliability_command", required=True
    )

    reliability_run = reliability_subparsers.add_parser(
        "run", help="Run independent fresh product-route executions"
    )
    reliability_run.add_argument(
        "--game-file", default=None, help="Path to the local game file"
    )
    reliability_run.add_argument(
        "--goal", default=ACTIVE_PRODUCT_GOAL_ID, help="Product goal reliability profile"
    )
    reliability_run.add_argument("--runs", type=int, default=None)
    reliability_run.add_argument(
        "--artifacts-root", default=None
    )
    reliability_run.add_argument("--timeout-seconds", type=int, default=None)

    reliability_watch = reliability_subparsers.add_parser(
        "watch", help="Run one throttled review-only product-route playback"
    )
    reliability_watch.add_argument(
        "--game-file", default=None, help="Path to the local game file"
    )
    reliability_watch.add_argument(
        "--goal", default=ACTIVE_PRODUCT_GOAL_ID, help="Product goal review profile"
    )
    reliability_watch.add_argument(
        "--artifacts-root", default=None
    )
    reliability_watch.add_argument(
        "--throttle-seconds", type=float, default=0.0035
    )
    reliability_watch.add_argument("--timeout-seconds", type=int, default=900)
    reliability_watch.add_argument("--columns", type=int, default=4)

    goal = subparsers.add_parser("goal", help="Validate and run goal contracts")
    goal_subparsers = goal.add_subparsers(dest="goal_command", required=True)

    goal_validate = goal_subparsers.add_parser("validate", help="Validate a goal contract file or id")
    goal_validate.add_argument("goal", help="Goal id or path to a goal YAML file")

    goal_run = goal_subparsers.add_parser("run", help="Run a goal contract")
    goal_run.add_argument("goal", help="Goal id or path to a goal YAML file")
    goal_run.add_argument("--game-file", default=None, help="Path to the local game file")
    goal_run.add_argument("--attempts", type=int, default=3)
    goal_run.add_argument(
        "--artifacts-dir",
        default=None,
        help="Directory for this goal attempt; defaults to a timestamped goal artifact directory",
    )
    goal_run.add_argument("--capture-images", action="store_true")
    goal_run.add_argument("--capture-ticks", action="store_true")

    goal_status = goal_subparsers.add_parser("status", help="Show a goal's route segment status")
    goal_status.add_argument("goal", help="Goal id or path to a goal YAML file")
    goal_status.add_argument(
        "--segments",
        default=None,
        help="Override the segment catalog declared by the goal contract",
    )

    segment = subparsers.add_parser("segment", help="Validate segment catalogs")
    segment_subparsers = segment.add_subparsers(dest="segment_command", required=True)

    segment_validate = segment_subparsers.add_parser("validate", help="Validate a segment catalog")
    segment_validate.add_argument("catalog", help="Path to a segment catalog YAML file")
    segment_validate.add_argument(
        "--goal",
        default=ACTIVE_PRODUCT_GOAL_ID,
        help="Optional goal id/path to cross-check against the catalog",
    )

    review = subparsers.add_parser("review", help="Review route logs and compare attempts")
    review_subparsers = review.add_subparsers(dest="review_command", required=True)

    review_log_parser = review_subparsers.add_parser("log", help="Review one route log")
    review_log_parser.add_argument("log", help="Path to a FCEUX route log")
    review_log_parser.add_argument("--attempts", type=int, default=None)

    review_compare = review_subparsers.add_parser("compare", help="Compare two route logs or artifact dirs")
    review_compare.add_argument("left", help="Left route log or artifact directory")
    review_compare.add_argument("right", help="Right route log or artifact directory")

    command = subparsers.add_parser("command", help="Parse and run user-facing game commands")
    command_subparsers = command.add_subparsers(dest="command_action", required=True)

    command_parse = command_subparsers.add_parser("parse", help="Parse a user command")
    command_parse.add_argument("text", help="User command text")

    command_run = command_subparsers.add_parser("run", help="Run a parsed user command")
    command_run.add_argument("text", help="User command text")
    command_run.add_argument("--game-file", default=None, help="Path to the local game file")
    command_run.add_argument(
        "--artifacts-dir",
        default=None,
        help="Directory for command trace and nested goal artifacts",
    )

    observe = subparsers.add_parser("observe", help="Run observed segments and write state traces")
    observe_subparsers = observe.add_subparsers(dest="observe_command", required=True)

    observe_segment = observe_subparsers.add_parser("run-segment", help="Run one segment with state tracing")
    observe_segment.add_argument("segment", help="Segment id or supported alias")
    observe_segment.add_argument("--game-file", default=None, help="Path to the local game file")
    observe_segment.add_argument("--sample-frames", type=int, default=15)
    observe_segment.add_argument(
        "--artifacts-dir",
        default=None,
        help="Directory for observed run artifacts",
    )

    recovery = subparsers.add_parser("recovery", help="Simulate recovery decisions from goal contracts")
    recovery_subparsers = recovery.add_subparsers(dest="recovery_command", required=True)

    recovery_simulate = recovery_subparsers.add_parser("simulate", help="Simulate a recovery scenario")
    recovery_simulate.add_argument("scenario", choices=["life_lost", "wrong_map_node"])
    recovery_simulate.add_argument("--goal", default=ACTIVE_PRODUCT_GOAL_ID, help="Goal id or path")

    lab = subparsers.add_parser("lab", help="Run attempt-lab sessions, notes, reviews, and variants")
    lab_subparsers = lab.add_subparsers(dest="lab_command", required=True)

    lab_start = lab_subparsers.add_parser("start", help="Start an attempt-lab session from a user command")
    lab_start.add_argument("text", help="User command text")
    lab_start.add_argument("--game-file", default=None, help="Path to the local game file")
    lab_start.add_argument("--attempts", type=int, default=1)
    lab_start.add_argument(
        "--artifacts-root",
        default="artifacts/sessions",
        help="Root directory for lab sessions",
    )
    lab_start.add_argument("--route-variant", default="world_1_baseline")
    lab_start.add_argument("--capture-images", action="store_true")
    lab_start.add_argument("--no-capture-ticks", action="store_true")

    lab_note = lab_subparsers.add_parser("note", help="Attach a human note to a lab session")
    lab_note.add_argument("target", choices=["latest"], help="Session target")
    lab_note.add_argument("text", help="Raw note text")
    lab_note.add_argument("--segment", default=None, help="Optional segment id")
    lab_note.add_argument("--attempt", type=int, default=None, help="Optional attempt number")
    lab_note.add_argument("--anchor-type", default=None, help="Optional anchor type")
    lab_note.add_argument("--anchor-value", default=None, help="Optional anchor value")
    lab_note.add_argument("--severity", default="note")

    lab_review = lab_subparsers.add_parser("review", help="Review a lab session")
    lab_review.add_argument("target", choices=["latest"], help="Session target")

    lab_issues = lab_subparsers.add_parser("issues", help="Build grouped issue ledger for a lab session")
    lab_issues.add_argument("target", choices=["latest"], help="Session target")

    lab_propose_many = lab_subparsers.add_parser(
        "propose-variants",
        help="Create route variant proposals for all actionable issues",
    )
    lab_propose_many.add_argument("target", choices=["latest"], help="Session target")

    lab_ui_summary = lab_subparsers.add_parser("ui-summary", help="Write UI-ready route map summary")
    lab_ui_summary.add_argument("target", choices=["latest"], help="Session target")

    lab_codex_task = lab_subparsers.add_parser("codex-task", help="Write a Codex-ready task packet")
    lab_codex_task.add_argument("target", choices=["latest"], help="Session target")
    lab_codex_task.add_argument("--issue", required=True, help="Issue id to package")

    lab_patch = lab_subparsers.add_parser(
        "patch", help="Import, isolate, validate, promote, and roll back exact route patches"
    )
    patch_subparsers = lab_patch.add_subparsers(dest="patch_command", required=True)

    patch_import = patch_subparsers.add_parser("import", help="Import a normalized route patch")
    patch_import.add_argument("patch_file")

    patch_review = patch_subparsers.add_parser("review", help="Review patch provenance and allowlist")
    patch_review.add_argument("patch_id")

    patch_preview = patch_subparsers.add_parser("preview", help="Preview the exact read-only diff")
    patch_preview.add_argument("patch_id")

    patch_prepare = patch_subparsers.add_parser("prepare", help="Apply patch in an isolated worktree")
    patch_prepare.add_argument("patch_id")

    patch_validate = patch_subparsers.add_parser("validate", help="Validate actual candidate content")
    patch_validate.add_argument("patch_id")
    patch_validate.add_argument("--game-file", default=None)
    patch_validate.add_argument("--timeout-seconds", type=int, default=900)

    patch_compare = patch_subparsers.add_parser("compare", help="Compare candidate and parent evidence")
    patch_compare.add_argument("patch_id")

    patch_promote = patch_subparsers.add_parser("promote", help="Promote the exact validated diff")
    patch_promote.add_argument("patch_id")
    patch_promote.add_argument(
        "--confirm",
        default=None,
        help="Exact patch ID confirmation; defaults to the explicit command target",
    )

    patch_rollback = patch_subparsers.add_parser("rollback", help="Apply the recorded inverse patch")
    patch_rollback.add_argument("patch_id")
    patch_rollback.add_argument(
        "--confirm",
        default=None,
        help="Exact patch ID confirmation; defaults to the explicit command target",
    )
    patch_rollback.add_argument("--reason", default="explicit CLI rollback")

    patch_reject = patch_subparsers.add_parser("reject", help="Reject an imported or reviewed patch")
    patch_reject.add_argument("patch_id")
    patch_reject.add_argument("--reason", required=True)

    lab_ui = lab_subparsers.add_parser("ui", help="Serve the local Game Companion UI")
    lab_ui.add_argument("--host", default="127.0.0.1")
    lab_ui.add_argument("--port", type=int, default=8765)
    lab_ui.add_argument("--open", action="store_true", help="Open the UI in the default browser")

    lab_ui_render = lab_subparsers.add_parser("ui-render", help="Render Game Companion HTML once")
    lab_ui_render.add_argument("--output", default="artifacts/ui/latest.html")
    lab_ui_render.add_argument(
        "--view", choices=("player", "lab"), default="player"
    )

    learning = subparsers.add_parser(
        "learning", help="Inspect and review local adaptive-assistance evidence"
    )
    learning_subparsers = learning.add_subparsers(dest="learning_command", required=True)
    learning_status = learning_subparsers.add_parser(
        "status", help="Show evidence classes and candidate lifecycle states"
    )
    learning_status.add_argument("--root", default="artifacts/learning")
    learning_recover = learning_subparsers.add_parser(
        "recover-index", help="Rebuild the derived index without rewriting raw evidence"
    )
    learning_recover.add_argument("--root", default="artifacts/learning")
    learning_export = learning_subparsers.add_parser(
        "export", help="Export a hash-bound candidate review packet"
    )
    learning_export.add_argument("candidate_id")
    learning_export.add_argument("--root", default="artifacts/learning")
    learning_review = learning_subparsers.add_parser(
        "review", help="Approve a candidate for validation or reject it"
    )
    learning_review.add_argument("candidate_id")
    learning_review.add_argument("decision", choices=("approve", "reject"))
    learning_review.add_argument("--reason", required=True)
    learning_review.add_argument("--root", default="artifacts/learning")
    learning_backfill = learning_subparsers.add_parser(
        "backfill-run-library",
        help="Idempotently wrap existing V2.6 runs as learning evidence",
    )
    learning_backfill.add_argument("--root", default="artifacts/learning")
    learning_backfill.add_argument("--run-library-root", default="artifacts/run-library")

    stardew = subparsers.add_parser(
        "stardew", help="Inspect the standalone Stardew companion implementation"
    )
    stardew_subparsers = stardew.add_subparsers(dest="stardew_command", required=True)
    stardew_render = stardew_subparsers.add_parser(
        "operator-render", help="Render the safe unconfigured companion surface without running Stardew"
    )
    stardew_render.add_argument("--output", default="artifacts/stardew-operator/operator.html")
    stardew_status = stardew_subparsers.add_parser(
        "status", help="Show adapter-owned capability truth without detecting or running the game"
    )
    stardew_status.add_argument("--contract", default=str(ADAPTER_CONTRACT_PATH))

    companion = subparsers.add_parser(
        "companion", help="Inspect the combined local Game Companion catalog"
    )
    companion_subparsers = companion.add_subparsers(dest="companion_command", required=True)
    companion_subparsers.add_parser(
        "catalog-status", help="Show provider-owned catalog truth without detecting or running a game"
    )
    companion_render = companion_subparsers.add_parser(
        "render", help="Render the safe unconfigured combined player surface"
    )
    companion_render.add_argument("--output", default="artifacts/companion/catalog.html")

    adapter = subparsers.add_parser(
        "adapter", help="Safely manage local Experimental game adapters"
    )
    adapter_subparsers = adapter.add_subparsers(dest="adapter_command", required=True)
    adapter_validate = adapter_subparsers.add_parser("validate", help="Validate a versioned declarative contract")
    adapter_validate.add_argument("contract")
    adapter_scaffold = adapter_subparsers.add_parser("scaffold", help="Generate a deterministic non-executable scaffold")
    adapter_scaffold.add_argument("adapter_id")
    adapter_scaffold.add_argument("--display-name", required=True)
    adapter_scaffold.add_argument("--root", default=str(default_scaffold_root()))
    adapter_inspect = adapter_subparsers.add_parser("inspect", help="Inspect declared truth and proof limits")
    adapter_inspect.add_argument("contract")
    adapter_conformance = adapter_subparsers.add_parser("conformance", help="Run deterministic fixture-only conformance")
    adapter_conformance.add_argument("source")
    adapter_install = adapter_subparsers.add_parser("install", help="Atomically install one conformant Experimental adapter")
    adapter_install.add_argument("source")
    adapter_install.add_argument("--install-root", default=None)
    adapter_status = adapter_subparsers.add_parser("status", help="Inspect installed Experimental adapters and integrity")
    adapter_status.add_argument("adapter_id", nargs="?")
    adapter_status.add_argument("--install-root", default=None)
    adapter_installed = adapter_subparsers.add_parser("installed", help="List provider-discoverable Experimental adapters")
    adapter_installed.add_argument("--install-root", default=None)
    adapter_remove = adapter_subparsers.add_parser("remove", help="Fail closed unless exact owned files and zero active state are proven")
    adapter_remove.add_argument("adapter_id")
    adapter_remove.add_argument("--install-root", default=None)

    scenario = subparsers.add_parser(
        "scenario", help="Inspect versioned local session-automation scenarios"
    )
    scenario_subparsers = scenario.add_subparsers(dest="scenario_command", required=True)
    for action, help_text in (
        ("list", "List classified scenario definitions and blockers"),
        ("status", "Show one scenario's implementation and capability status"),
        ("plan", "Show the dry execution plan without running it"),
    ):
        command = scenario_subparsers.add_parser(action, help=help_text)
        command.add_argument("scenario_id", nargs="?" if action == "list" else None)
        command.add_argument("--catalog", default=str(DEFAULT_SCENARIO_CATALOG))
    readiness = scenario_subparsers.add_parser(
        "final-campaign-readiness", help="Report classified final-campaign blockers"
    )
    readiness.add_argument("--catalog", default=str(DEFAULT_SCENARIO_CATALOG))

    unattended = subparsers.add_parser(
        "unattended", help="Inspect or run honestly labeled local unattended regression"
    )
    unattended_subparsers = unattended.add_subparsers(dest="unattended_command", required=True)
    unattended_capabilities = unattended_subparsers.add_parser(
        "capabilities", help="Inspect adapter and display eligibility without creating an attempt"
    )
    unattended_plan = unattended_subparsers.add_parser(
        "plan", help="Build a side-effect-free immutable-manifest preview"
    )
    unattended_run = unattended_subparsers.add_parser(
        "run", help="Execute a bounded regression-only attempt"
    )
    for command in (unattended_capabilities, unattended_plan, unattended_run):
        command.add_argument("--adapter", choices=("smb3", "stardew"), default="smb3")
        command.add_argument("--display-provider", default="none")
        command.add_argument("--display-backend", choices=("normal_desktop", "local_virtual_display", "none"), default="none")
        command.add_argument("--display-identity", default="unavailable")
        command.add_argument("--display-probe-executable", default=None)
        command.add_argument("--display-probe-arg", action="append", default=[])
        command.add_argument("--rom", default=None)
        command.add_argument("--fceux", default="/usr/local/bin/fceux")
        command.add_argument("--mario-goal", default="world_8_double_whistle")
        command.add_argument("--stardew-fixture", default=None)
        command.add_argument("--stardew-executable", default=None)
        command.add_argument("--owner-save-root", action="append", default=[])
        command.add_argument("--artifact-root", default="artifacts/unattended-regression")
    for command in (unattended_plan, unattended_run):
        command.add_argument("--scenario", default="regression.unattended")
        command.add_argument("--catalog", default=str(DEFAULT_SCENARIO_CATALOG))
        command.add_argument("--goal-version", required=True)
        command.add_argument("--profile-version", required=True)
        command.add_argument("--solution-version", required=True)
        command.add_argument("--runs", type=int, default=1)
        command.add_argument("--per-run-timeout", type=int, default=300)
        command.add_argument("--aggregate-timeout", type=int, default=600)
        command.add_argument("--concurrency", type=int, default=1)
        command.add_argument("--correlation-reference", default=None)
    unattended_run.add_argument("--acknowledgement", required=True, help=f"Must equal {ACKNOWLEDGEMENT}")
    unattended_manifest = unattended_subparsers.add_parser("manifest", help="Inspect and integrity-check an immutable attempt manifest")
    unattended_manifest.add_argument("path")
    unattended_status = unattended_subparsers.add_parser("status", help="Inspect one retained attempt")
    unattended_status.add_argument("attempt_id")
    unattended_status.add_argument("--artifact-root", default="artifacts/unattended-regression")
    unattended_cancel = unattended_subparsers.add_parser("cancel", help="Request cancellation of one exact retained/running attempt")
    unattended_cancel.add_argument("attempt_id")
    unattended_cancel.add_argument("--artifact-root", default="artifacts/unattended-regression")
    unattended_compare = unattended_subparsers.add_parser("compare", help="Compare exact compatible unattended attempts only")
    unattended_compare.add_argument("attempt_roots", nargs="+")

    metrics = subparsers.add_parser(
        "metrics", help="Inspect and maintain local classified product metrics"
    )
    metrics_subparsers = metrics.add_subparsers(dest="metrics_command", required=True)
    for action, help_text in (
        ("summarize", "Summarize exact local metrics without a blended score"),
        ("status", "Show schema, storage, corruption, and recovery status"),
        ("schema", "Show metric definitions, labels, numerators, and denominators"),
        ("rebuild", "Atomically rebuild derived indexes from raw local events"),
    ):
        command = metrics_subparsers.add_parser(action, help=help_text)
        command.add_argument("--root", default="artifacts/session-metrics")
    metrics_export = metrics_subparsers.add_parser(
        "export", help="Export local events with provenance and classification"
    )
    metrics_export.add_argument("output")
    metrics_export.add_argument("--root", default="artifacts/session-metrics")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "probe" and args.backend == "mednafen":
        _require_macos_mednafen(parser, "probe mednafen")
        from smb3_agent.probes.mednafen_probe import run_mednafen_probe

        run_mednafen_probe(
            game_path=Path(args.game_file),
            artifacts_dir=Path(args.artifacts_dir),
            startup_seconds=args.startup_seconds,
            after_start_seconds=args.after_start_seconds,
        )
        return

    if args.command == "detect":
        detection = detect_state(Path(args.image), Path(args.fixtures_dir))
        print(detection.to_json())
        return

    if args.command == "task" and args.task_name == "start-game":
        _require_macos_mednafen(parser, "task start-game")
        from smb3_agent.tasks.start_game import run_start_game_task

        run_start_game_task(
            game_path=Path(args.game_file),
            artifacts_dir=Path(args.artifacts_dir),
            fixtures_dir=Path(args.fixtures_dir),
            startup_seconds=args.startup_seconds,
        )
        return

    if args.command == "task" and args.task_name == "enter-1-1":
        _require_macos_mednafen(parser, "task enter-1-1")
        from smb3_agent.tasks.enter_1_1 import run_enter_1_1_task

        run_enter_1_1_task(
            game_path=Path(args.game_file),
            artifacts_dir=Path(args.artifacts_dir),
            fixtures_dir=Path(args.fixtures_dir),
            startup_seconds=args.startup_seconds,
        )
        return

    if args.command == "task" and args.task_name == "checkpoint-1-1":
        _require_macos_mednafen(parser, "task checkpoint-1-1")
        from smb3_agent.tasks.checkpoint_1_1 import run_checkpoint_1_1_task

        run_checkpoint_1_1_task(
            game_path=Path(args.game_file),
            artifacts_dir=Path(args.artifacts_dir),
            fixtures_dir=Path(args.fixtures_dir),
            startup_seconds=args.startup_seconds,
            slot=args.slot,
        )
        return

    if args.command == "task" and args.task_name == "load-checkpoint-1-1":
        _require_macos_mednafen(parser, "task load-checkpoint-1-1")
        from smb3_agent.tasks.load_checkpoint_1_1 import run_load_checkpoint_1_1_task

        run_load_checkpoint_1_1_task(
            game_path=Path(args.game_file),
            artifacts_dir=Path(args.artifacts_dir),
            fixtures_dir=Path(args.fixtures_dir),
            startup_seconds=args.startup_seconds,
            slot=args.slot,
        )
        return

    if args.command == "task" and args.task_name == "run-1-1-script":
        _require_macos_mednafen(parser, "task run-1-1-script")
        from smb3_agent.tasks.run_1_1_script import run_1_1_script_task

        run_1_1_script_task(
            game_path=Path(args.game_file),
            script_path=Path(args.script),
            artifacts_dir=Path(args.artifacts_dir),
            fixtures_dir=Path(args.fixtures_dir),
            startup_seconds=args.startup_seconds,
            slot=args.slot,
            save_final_slot=args.save_final_slot,
            sample_interval_seconds=args.sample_interval_seconds,
        )
        return

    if args.command == "task" and args.task_name == "fceux-1-1":
        summary = run_fceux_1_1(
            game_path=Path(args.game_file),
            script_path=Path(args.script),
            artifacts_dir=Path(args.artifacts_dir),
            attempts=args.attempts,
            capture_images=args.capture_images,
            capture_ticks=args.capture_ticks,
            after_attempt_frames=args.after_attempt_frames,
            post_1_1_probe=args.post_1_1_probe,
            env_overrides=tuple(args.set_env),
        )
        print(summary.to_text())
        if args.require_perfect and summary.success_count != summary.total:
            raise SystemExit(1)
        if args.require_post_probe_clear and not summary.post_probe_clear:
            raise SystemExit(1)
        return

    if args.command == "task" and args.task_name == "review-fceux-log":
        summary = parse_fceux_log(Path(args.log), expected_attempts=args.attempts)
        print(summary.to_text())
        return

    if args.command == "task" and args.task_name == "fceux-contact-sheet":
        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir) if args.output_dir else input_dir / "png"
        sheet_path = Path(args.sheet) if args.sheet else output_dir / "contact_sheet.png"
        converted = convert_gd_directory(input_dir, output_dir)
        write_contact_sheet(converted, sheet_path, columns=args.columns)
        print(f"converted={len(converted)}")
        print(f"sheet={sheet_path}")
        return

    if args.command == "reliability" and args.reliability_command == "run":
        game_file = args.game_file or os.environ.get("SMB3_GAME_FILE")
        if not game_file:
            parser.error("reliability run requires --game-file or SMB3_GAME_FILE")
        result = run_reliability_gate(
            game_path=Path(game_file),
            requested_runs=args.runs,
            artifacts_root=Path(args.artifacts_root) if args.artifacts_root else None,
            timeout_seconds=args.timeout_seconds,
            goal_id=args.goal,
            progress=lambda message: print(message, flush=True),
        )
        print(result.to_text())
        if not result.passed:
            raise SystemExit(1)
        return

    if args.command == "reliability" and args.reliability_command == "watch":
        game_file = args.game_file or os.environ.get("SMB3_GAME_FILE")
        if not game_file:
            parser.error("reliability watch requires --game-file or SMB3_GAME_FILE")
        result = run_watchable_playback(
            game_path=Path(game_file),
            artifacts_root=Path(args.artifacts_root) if args.artifacts_root else None,
            frame_sleep_seconds=args.throttle_seconds,
            timeout_seconds=args.timeout_seconds,
            contact_sheet_columns=args.columns,
            goal_id=args.goal,
            progress=lambda message: print(message, flush=True),
        )
        print(result.to_text())
        if not result.passed:
            raise SystemExit(1)
        return

    if args.command == "goal" and args.goal_command == "validate":
        try:
            contract = load_goal_contract(resolve_goal_path(args.goal))
        except GoalValidationError as exc:
            parser.error(str(exc))
        print("valid=true")
        print(f"goal_id={contract.id}")
        print(f"goal_type={contract.goal_type}")
        print(f"execution_status={contract.execution_status}")
        print(f"executable={str(contract.executable).lower()}")
        print(f"preset={contract.preset}")
        print(f"segments={len(contract.segments)}")
        print(f"bridged_segments={len(contract.bridged_segments)}")
        return

    if args.command == "goal" and args.goal_command == "run":
        try:
            contract = load_goal_contract(resolve_goal_path(args.goal))
        except GoalValidationError as exc:
            parser.error(str(exc))

        if not contract.executable:
            parser.error(
                f"Goal {contract.id} is planned and not yet executable; "
                "no diagnostic runner fallback is permitted"
            )

        game_file = args.game_file or os.environ.get("SMB3_GAME_FILE")
        if not game_file:
            parser.error("goal run requires --game-file or SMB3_GAME_FILE")

        try:
            result = run_goal_contract(
                contract,
                game_path=Path(game_file),
                attempts=args.attempts,
                artifacts_dir=Path(args.artifacts_dir) if args.artifacts_dir else None,
                capture_images=args.capture_images,
                capture_ticks=args.capture_ticks,
            )
        except GoalValidationError as exc:
            parser.error(str(exc))
        print(f"goal_id={result.contract.id}")
        print(f"artifacts_dir={result.artifacts_dir}")
        print(result.summary.to_text())
        print(f"metrics_passed={str(result.metrics_passed).lower()}")
        if result.contract.runner.get("require_perfect") and not result.metrics_passed:
            raise SystemExit(1)
        return

    if args.command == "goal" and args.goal_command == "status":
        try:
            contract = load_goal_contract(resolve_goal_path(args.goal))
            catalog = load_segment_catalog(Path(args.segments) if args.segments else contract.catalog_path)
            print(render_goal_status(contract, catalog))
        except (GoalValidationError, SegmentValidationError) as exc:
            parser.error(str(exc))
        return

    if args.command == "segment" and args.segment_command == "validate":
        try:
            catalog = load_segment_catalog(Path(args.catalog))
            if args.goal:
                contract = load_goal_contract(resolve_goal_path(args.goal))
                validate_goal_segments(contract, catalog)
        except (GoalValidationError, SegmentValidationError) as exc:
            parser.error(str(exc))
        print("valid=true")
        print(f"catalog_id={catalog.catalog_id}")
        print(f"segments={len(catalog.segments)}")
        if args.goal:
            print(f"goal_id={contract.id}")
            print(f"goal_segments={len(contract.segments)}")
        return

    if args.command == "review" and args.review_command == "log":
        print(review_log(Path(args.log), expected_attempts=args.attempts).to_text())
        return

    if args.command == "review" and args.review_command == "compare":
        print(compare_logs(_resolve_review_log(Path(args.left)), _resolve_review_log(Path(args.right))).to_text())
        return

    if args.command == "command" and args.command_action == "parse":
        try:
            print(parse_command(args.text).to_text())
        except (CommandParseError, GoalValidationError) as exc:
            parser.error(str(exc))
        return

    if args.command == "command" and args.command_action == "run":
        try:
            parsed_command = parse_command(args.text)
            if parsed_command.goal:
                parsed_contract = load_goal_contract(resolve_goal_path(parsed_command.goal))
                if not parsed_contract.executable:
                    parser.error(
                        f"Goal {parsed_contract.id} is planned and not yet executable; "
                        "no diagnostic runner fallback is permitted"
                    )
        except (CommandParseError, GoalValidationError) as exc:
            parser.error(str(exc))
        game_file = args.game_file or os.environ.get("SMB3_GAME_FILE")
        if not game_file:
            parser.error("command run requires --game-file or SMB3_GAME_FILE")
        try:
            result = run_command(
                args.text,
                game_path=Path(game_file),
                artifacts_dir=Path(args.artifacts_dir) if args.artifacts_dir else None,
            )
        except (CommandParseError, GoalValidationError) as exc:
            parser.error(str(exc))
        print(result.to_text())
        if not result.goal_result.metrics_passed:
            raise SystemExit(1)
        return

    if args.command == "observe" and args.observe_command == "run-segment":
        game_file = args.game_file or os.environ.get("SMB3_GAME_FILE")
        if not game_file:
            parser.error("observe run-segment requires --game-file or SMB3_GAME_FILE")
        try:
            result = run_observed_segment(
                args.segment,
                game_path=Path(game_file),
                sample_frames=args.sample_frames,
                artifacts_dir=Path(args.artifacts_dir) if args.artifacts_dir else None,
            )
        except ObserveError as exc:
            parser.error(str(exc))
        print(result.to_text())
        if result.summary.success_count != result.summary.total:
            raise SystemExit(1)
        return

    if args.command == "recovery" and args.recovery_command == "simulate":
        try:
            contract = load_goal_contract(resolve_goal_path(args.goal))
            print(simulate_recovery(contract, args.scenario).to_text())
        except (GoalValidationError, RecoveryError) as exc:
            parser.error(str(exc))
        return

    if args.command == "lab" and args.lab_command == "start":
        game_file = args.game_file or os.environ.get("SMB3_GAME_FILE")
        if not game_file:
            parser.error("lab start requires --game-file or SMB3_GAME_FILE")
        try:
            result = start_session(
                args.text,
                game_path=Path(game_file),
                attempts=args.attempts,
                artifacts_root=Path(args.artifacts_root),
                route_variant=args.route_variant,
                capture_images=args.capture_images,
                capture_ticks=not args.no_capture_ticks,
            )
        except (CommandParseError, GoalValidationError, LabError, FileNotFoundError) as exc:
            parser.error(str(exc))
        print(result.to_text())
        return

    if args.command == "lab" and args.lab_command == "note":
        try:
            print(
                add_note_to_latest(
                    args.text,
                    segment_id=args.segment,
                    attempt_number=args.attempt,
                    anchor_type=args.anchor_type,
                    anchor_value=args.anchor_value,
                    severity=args.severity,
                ).to_text()
            )
        except LabError as exc:
            parser.error(str(exc))
        return

    if args.command == "lab" and args.lab_command == "review":
        try:
            print(review_latest_session().to_text())
        except LabError as exc:
            parser.error(str(exc))
        return

    if args.command == "lab" and args.lab_command == "issues":
        try:
            print(build_issue_ledger_latest().to_text())
        except LabError as exc:
            parser.error(str(exc))
        return

    if args.command == "lab" and args.lab_command == "propose-variants":
        try:
            print(propose_variants_from_latest().to_text())
        except LabError as exc:
            parser.error(str(exc))
        return

    if args.command == "lab" and args.lab_command == "ui-summary":
        try:
            print(write_ui_summary_latest().to_text())
        except LabError as exc:
            parser.error(str(exc))
        return

    if args.command == "lab" and args.lab_command == "codex-task":
        try:
            print(write_codex_task_latest(args.issue).to_text())
        except LabError as exc:
            parser.error(str(exc))
        return

    if args.command == "lab" and args.lab_command == "patch":
        try:
            if args.patch_command == "import":
                result = import_route_patch(Path(args.patch_file))
            elif args.patch_command == "review":
                result = review_route_patch(args.patch_id)
            elif args.patch_command == "preview":
                result = preview_route_patch(args.patch_id)
            elif args.patch_command == "prepare":
                result = prepare_route_patch(args.patch_id)
            elif args.patch_command == "validate":
                game_file = args.game_file or os.environ.get("SMB3_GAME_FILE")
                result = validate_route_patch(
                    args.patch_id,
                    game_path=Path(game_file) if game_file else None,
                    timeout_seconds=args.timeout_seconds,
                )
            elif args.patch_command == "compare":
                result = compare_route_patch(args.patch_id)
            elif args.patch_command == "promote":
                result = promote_route_patch(
                    args.patch_id,
                    confirm_patch_id=args.confirm or args.patch_id,
                )
            elif args.patch_command == "rollback":
                result = rollback_route_patch(
                    args.patch_id,
                    confirm_patch_id=args.confirm or args.patch_id,
                    reason=args.reason,
                )
            elif args.patch_command == "reject":
                result = reject_route_patch(args.patch_id, args.reason)
            else:
                parser.error(f"Unsupported patch command: {args.patch_command}")
                return
        except (RoutePatchError, FileNotFoundError) as exc:
            parser.error(str(exc))
        print(result.to_text())
        return

    if args.command == "lab" and args.lab_command == "ui":
        try:
            run_lab_ui_server(host=args.host, port=args.port, open_browser=args.open)
        except (LabError, LabUiError, OSError) as exc:
            parser.error(str(exc))
        return

    if args.command == "lab" and args.lab_command == "ui-render":
        try:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            rendered = (
                render_lab_ui()
                if args.view == "lab"
                else render_companion_ui(default_companion_session())
            )
            output.write_text(rendered, encoding="utf-8")
        except (LabError, LabUiError) as exc:
            parser.error(str(exc))
        print(f"html={output}")
        return

    if args.command == "learning":
        store = LocalLearningStore(Path(args.root))
        try:
            if args.learning_command == "status":
                snapshot = store.snapshot()
                print(
                    json.dumps(
                        {
                            "schema_version": "game-companion-learning-status/v1",
                            "attempts": len(snapshot.attempts),
                            "patterns": len(snapshot.patterns),
                            "tactics": len(snapshot.tactics),
                            "candidate_states": {
                                item.candidate_id: item.lifecycle.value
                                for item in snapshot.candidates
                            },
                            "preferences": len(snapshot.preferences),
                            "accepted_executable_changes": len(snapshot.promotions),
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
                return
            if args.learning_command == "recover-index":
                print(json.dumps(store.recover_index(), indent=2, sort_keys=True))
                return
            if args.learning_command == "export":
                print(f"review_packet={store.export_review_packet(args.candidate_id)}")
                return
            if args.learning_command == "review":
                result = store.review(
                    args.candidate_id,
                    approve=args.decision == "approve",
                    reason=args.reason,
                    reviewer="local-owner-cli",
                )
                print(f"candidate_id={result.candidate_id}")
                print(f"decision={result.decision}")
                print("executable=false")
                return
            if args.learning_command == "backfill-run-library":
                sessions = backfill_run_library(
                    store,
                    LocalRunLibrary(Path(args.run_library_root)),
                    adapter_id="smb3",
                    adapter_version="smb3-live-observer/v1",
                )
                print(f"processed={len(sessions)}")
                print("automatic_promotion=false")
                return
        except LearningError as exc:
            parser.error(str(exc))

    if args.command == "stardew":
        try:
            contract = (
                load_stardew_contract(Path(args.contract))
                if args.stardew_command == "status"
                else load_stardew_contract()
            )
            capabilities = {
                str(item["id"]): str(item["status"])
                for item in contract.get("capabilities", ())
            }
            if args.stardew_command == "status":
                print(json.dumps({
                    "adapter_id": contract["adapter_id"],
                    "adapter_version": contract["adapter_version"],
                    "implementation_slice": contract["implementation_slice"],
                    "capabilities": capabilities,
                    "live_activity_run": False,
                }, indent=2, sort_keys=True))
                return
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(render_stardew_operator(OperatorView(
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
            )), encoding="utf-8")
            print(f"operator={output}")
            print("live_activity_run=false")
            return
        except StardewAdapterError as exc:
            parser.error(str(exc))

    if args.command == "companion":
        try:
            registry = build_default_catalog_registry()
            catalog = CatalogSession(registry, CatalogPreferenceStore())
            if args.companion_command == "catalog-status":
                print(json.dumps(catalog.inspection_payload(), indent=2, sort_keys=True))
                return
            catalog.preferences = CatalogPreferences()
            catalog.store.recovery_reason = None
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(render_combined_catalog(catalog), encoding="utf-8")
            print(f"catalog={output}")
            print("selected_adapter_id=none")
            print("live_activity_run=false")
            return
        except CompanionCatalogError as exc:
            parser.error(str(exc))

    if args.command == "adapter":
        try:
            install_root = Path(args.install_root) if getattr(args, "install_root", None) else default_install_root()
            if args.adapter_command == "validate":
                contract = load_experimental_contract(Path(args.contract))
                print(json.dumps({"valid": True, "adapter_id": contract["identity"]["adapter_id"], "schema_version": contract["schema_version"]}, indent=2, sort_keys=True))
                return
            if args.adapter_command == "scaffold":
                print(f"scaffold={scaffold_adapter(Path(args.root), args.adapter_id, args.display_name)}")
                print("generated_executable_code=false")
                return
            if args.adapter_command == "inspect":
                print(json.dumps(asdict(inspect_contract(Path(args.contract))), indent=2, sort_keys=True))
                return
            if args.adapter_command == "conformance":
                print(json.dumps(run_conformance(Path(args.source)).to_dict(), indent=2, sort_keys=True))
                return
            if args.adapter_command == "install":
                print(f"installed={install_adapter(Path(args.source), install_root)}")
                print("catalog_status=Experimental")
                return
            if args.adapter_command == "status":
                print(json.dumps(installation_status(install_root, args.adapter_id), indent=2, sort_keys=True))
                return
            if args.adapter_command == "installed":
                print(json.dumps([asdict(provider.catalog_entry()) for provider in discover_installed_providers(install_root)], indent=2, sort_keys=True))
                return
            if args.adapter_command == "remove":
                print(json.dumps(uninstall_adapter(install_root, args.adapter_id), indent=2, sort_keys=True))
                return
        except (ExperimentalAdapterError, OSError, json.JSONDecodeError) as exc:
            parser.error(str(exc))

    if args.command == "scenario":
        try:
            catalog = load_scenario_catalog(Path(args.catalog))
            selected = next(
                (item for item in catalog if item.scenario_id == getattr(args, "scenario_id", None)),
                None,
            )
            if args.scenario_command == "list":
                print(json.dumps([
                    {
                        "scenario_id": item.scenario_id,
                        "version": item.version,
                        "classification": item.classification.value,
                        "evidence_classification": item.evidence_classification.value,
                        "capability_status": item.capability_status,
                    }
                    for item in catalog
                ], indent=2, sort_keys=True))
                return
            if args.scenario_command == "final-campaign-readiness":
                print(json.dumps(final_campaign_readiness(catalog), indent=2, sort_keys=True))
                return
            if selected is None:
                parser.error(f"unknown scenario: {args.scenario_id}")
            if args.scenario_command == "plan":
                print(json.dumps(scenario_plan(selected).to_dict(), indent=2, sort_keys=True))
                return
            if args.scenario_command == "status":
                print(json.dumps({
                    "scenario_id": selected.scenario_id,
                    "version": selected.version,
                    "implementation": "defined",
                    "capability_status": selected.capability_status,
                    "owner_participation_required": selected.owner_participation_required,
                    "execution_deferred": True,
                }, indent=2, sort_keys=True))
                return
            parser.error(
                f"scenario {args.scenario_command} is fail-closed until the consolidated "
                "campaign activates execution and supplies an exact immutable attempt"
            )
        except ScenarioError as exc:
            parser.error(str(exc))

    if args.command == "metrics":
        store = LocalMetricsStore(Path(args.root))
        try:
            if args.metrics_command == "summarize":
                print(json.dumps(store.summarize(), indent=2, sort_keys=True))
                return
            if args.metrics_command == "status":
                print(json.dumps(store.status(), indent=2, sort_keys=True))
                return
            if args.metrics_command == "schema":
                print(json.dumps([
                    definition.__dict__ | {"label": definition.label.value}
                    for definition in metric_definitions()
                ], indent=2, sort_keys=True))
                return
            if args.metrics_command == "rebuild":
                print(json.dumps(store.rebuild(), indent=2, sort_keys=True))
                return
            if args.metrics_command == "export":
                print(f"metrics_export={store.export(Path(args.output))}")
                return
        except MetricsError as exc:
            parser.error(str(exc))

    if args.command == "unattended":
        try:
            if args.unattended_command == "manifest":
                print(json.dumps(load_manifest(Path(args.path)).to_dict(), indent=2, sort_keys=True))
                return
            if args.unattended_command == "compare":
                roots = [Path(item) for item in args.attempt_roots]
                manifests = [load_manifest(root / "manifest.json") for root in roots]
                reports = [json.loads((root / "repeatability.json").read_text(encoding="utf-8")) for root in roots]
                print(json.dumps(compare_attempts(manifests, reports), indent=2, sort_keys=True))
                return
            if args.unattended_command in {"status", "cancel"}:
                runner = UnattendedRunner([], [], artifact_root=Path(args.artifact_root))
                if args.unattended_command == "status":
                    print(json.dumps(runner.attempt_status(args.attempt_id), indent=2, sort_keys=True))
                else:
                    print(f"cancellation_request={runner.request_cancellation(args.attempt_id)}")
                return
            display = (
                NoDisplayProvider()
                if args.display_provider == "none"
                else ProbedDisplayProvider(
                    args.display_provider,
                    args.display_backend,
                    args.display_identity,
                    args.display_probe_executable,
                    tuple(args.display_probe_arg),
                    args.display_backend == "normal_desktop",
                )
                if args.display_probe_executable
                else DeclaredDisplayProvider(
                    args.display_provider,
                    args.display_backend,
                    args.display_identity,
                    False,
                    False,
                    args.display_backend == "normal_desktop",
                    "a live argument-vector display probe is required",
                )
            )
            provider = (
                MarioUnattendedProvider(
                    rom_path=Path(args.rom) if args.rom else None,
                    executable=Path(args.fceux),
                    goal_id=args.mario_goal,
                )
                if args.adapter == "smb3"
                else StardewUnattendedProvider(
                    fixture_path=Path(args.stardew_fixture) if args.stardew_fixture else None,
                    owner_save_roots=[Path(item) for item in args.owner_save_root],
                    executable=Path(args.stardew_executable) if args.stardew_executable else None,
                )
            )
            runner = UnattendedRunner([provider], [display], artifact_root=Path(args.artifact_root))
            if args.unattended_command == "capabilities":
                print(json.dumps(runner.capability_status(), indent=2, sort_keys=True))
                return
            catalog = load_scenario_catalog(Path(args.catalog))
            scenario = next((item for item in catalog if item.scenario_id == args.scenario), None)
            if scenario is None:
                raise UnattendedError(f"unknown unattended scenario: {args.scenario}")
            plan = runner.plan(
                scenario,
                adapter_id=args.adapter,
                display_provider_id=display.inspect().provider_id,
                source_identity=source_identity(),
                goal_version=args.goal_version,
                profile_version=args.profile_version,
                solution_version=args.solution_version,
                run_count=args.runs,
                per_run_timeout_seconds=args.per_run_timeout,
                aggregate_timeout_seconds=args.aggregate_timeout,
                concurrency=args.concurrency,
                correlation_reference=args.correlation_reference,
            )
            if args.unattended_command == "plan":
                print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
                return
            print(json.dumps(runner.execute(plan, acknowledgement=args.acknowledgement), indent=2, sort_keys=True))
            return
        except (UnattendedError, OSError, subprocess.SubprocessError) as exc:
            parser.error(str(exc))

    parser.error("Unsupported command")


def _resolve_review_log(path: Path) -> Path:
    if path.is_dir():
        return path / "fceux_1_1.log"
    return path


def _require_macos_mednafen(parser: argparse.ArgumentParser, command: str) -> None:
    if sys.platform != "darwin":
        parser.error(f"{command} is supported only on macOS; Linux CI validates ROM-free commands only")
