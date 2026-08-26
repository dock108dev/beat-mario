from pathlib import Path

import pytest

from smb3_agent.commands import CommandParseError, parse_command, run_command
from smb3_agent.cli import build_parser
from smb3_agent.fceux_harness import AttemptSummary, BatchSummary
from smb3_agent.goals import GoalRunResult


def test_combined_catalog_cli_surfaces_are_additive_and_safe() -> None:
    status = build_parser().parse_args(["companion", "catalog-status"])
    render = build_parser().parse_args(
        ["companion", "render", "--output", "/tmp/game-companion.html"]
    )
    assert status.command == "companion"
    assert status.companion_command == "catalog-status"
    assert render.command == "companion"
    assert render.companion_command == "render"
    assert render.output == "/tmp/game-companion.html"


def test_parse_world_8_double_whistle_goal_command() -> None:
    command = parse_command("run world 8 double whistle arrival 3 times")

    assert command.action == "run_goal"
    assert command.goal == "world_8_double_whistle"
    assert command.attempts == 3
    assert command.validation_policy == "require_goal_metrics"


def test_reliability_cli_selects_big_tanks_as_an_explicit_separate_goal() -> None:
    args = build_parser().parse_args(
        ["reliability", "run", "--goal", "world_8_big_tanks"]
    )

    assert args.command == "reliability"
    assert args.reliability_command == "run"
    assert args.goal == "world_8_big_tanks"
    assert args.runs is None


def test_reliability_cli_selects_battleships_without_fallback() -> None:
    args = build_parser().parse_args(
        ["reliability", "run", "--goal", "world_8_battleships"]
    )

    assert args.goal == "world_8_battleships"
    assert args.runs is None


def test_reliability_cli_selects_hand_traps_jet_without_fallback() -> None:
    args = build_parser().parse_args(
        ["reliability", "run", "--goal", "world_8_hand_traps_jet"]
    )

    assert args.goal == "world_8_hand_traps_jet"
    assert args.runs is None


def test_reliability_cli_selects_world_8_8_2_without_fallback() -> None:
    args = build_parser().parse_args(
        ["reliability", "run", "--goal", "world_8_8_2"]
    )

    assert args.goal == "world_8_8_2"
    assert args.runs is None


def test_reliability_cli_selects_world_8_super_tanks_without_fallback() -> None:
    args = build_parser().parse_args(
        ["reliability", "run", "--goal", "world_8_super_tanks"]
    )

    assert args.goal == "world_8_super_tanks"
    assert args.runs is None
    assert args.timeout_seconds is None


def test_reliability_watch_allows_the_full_throttled_world_8_route() -> None:
    args = build_parser().parse_args(
        ["reliability", "watch", "--goal", "world_8_super_tanks"]
    )

    assert args.goal == "world_8_super_tanks"
    assert args.timeout_seconds == 900


def test_reliability_cli_selects_world_8_finish_game_without_fallback() -> None:
    args = build_parser().parse_args(
        ["reliability", "run", "--goal", "world_8_finish_game"]
    )

    assert args.goal == "world_8_finish_game"
    assert args.runs is None
    assert args.timeout_seconds is None


def test_parse_world_1_king_gate_command() -> None:
    command = parse_command("run world 1 king gate 3 times")

    assert command.action == "run_goal"
    assert command.goal == "world_1_king"
    assert command.attempts == 3
    assert command.run_mode == "gate"
    assert command.validation_policy == "require_goal_metrics"
    assert "goal=world_1_king" in command.to_text()


def test_parse_world_1_king_gate_defaults_to_one_attempt() -> None:
    command = parse_command("run world 1 king gate")

    assert command.attempts == 1


def test_parse_world_1_king_gate_with_speed() -> None:
    command = parse_command("run world 1 king gate 3 times at 4x")

    assert command.action == "run_goal"
    assert command.attempts == 3
    assert command.speed == 4


def test_parse_show_route_command() -> None:
    command = parse_command("show me the route at 4x")

    assert command.action == "show_route"
    assert command.goal == "world_8_double_whistle"
    assert command.speed == 4
    assert command.validation_policy == "review_only"


@pytest.mark.parametrize(
    "removed_command",
    (
        "review the latest failed run",
        "continue after losing a life if the route allows it",
    ),
)
def test_removed_parse_only_commands_are_unsupported(removed_command: str) -> None:
    with pytest.raises(CommandParseError, match="Unsupported command"):
        parse_command(removed_command)


@pytest.mark.parametrize("removed_action", ("run", "cancel"))
def test_removed_generic_scenario_actions_are_not_cli_paths(
    removed_action: str,
) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["scenario", removed_action, "fixture"])


def test_readiness_cli_has_distinct_inspection_gate_and_manifest_creation_paths() -> None:
    inspect = build_parser().parse_args(["scenario", "final-campaign-readiness"])
    gate = build_parser().parse_args([
        "scenario",
        "final-campaign-readiness",
        "--candidate-manifest",
        "artifacts/campaigns/candidate/campaign-entry-manifest.json",
        "--gate",
    ])
    manifest = build_parser().parse_args([
        "scenario",
        "candidate-manifest",
        "--output",
        "artifacts/campaigns/candidate/campaign-entry-manifest.json",
        "--focused-readiness-total",
        "10",
        "--focused-v2-total",
        "366",
        "--canonical-total",
        "666",
    ])
    assert inspect.gate is False
    assert gate.gate is True
    assert manifest.focused_readiness_total == 10
    assert manifest.focused_v2_total == 366
    assert manifest.canonical_total == 666


def test_parse_unsupported_command() -> None:
    with pytest.raises(CommandParseError, match="Unsupported command"):
        parse_command("please improvise a route")


def test_command_module_imports_path_for_future_trace_type() -> None:
    assert Path("artifacts/commands").parts[-1] == "commands"


def test_run_command_writes_trace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run_goal_contract(contract, *, game_path, attempts, artifacts_dir, capture_images=False, capture_ticks=False):
        return GoalRunResult(
            contract=contract,
            summary=BatchSummary(
                attempts=(
                    AttemptSummary(
                        attempt=1,
                        success=True,
                        bad_state=False,
                        reached_end=True,
                        goal_area=True,
                        max_x=2848,
                    ),
                ),
                post_probe_last_event="post_probe_1_airship_success_king",
                post_probe_clear=True,
            ),
            artifacts_dir=artifacts_dir,
            metrics_passed=True,
        )

    monkeypatch.setattr("smb3_agent.commands.run_goal_contract", fake_run_goal_contract)
    game_file = tmp_path / "local-game-file"
    game_file.write_text("placeholder")

    result = run_command(
        "run world 1 king gate",
        game_path=game_file,
        artifacts_dir=tmp_path / "command",
    )

    assert result.trace_path.is_file()
    assert result.goal_result.metrics_passed is True
    assert "trace_path=" in result.to_text()


def test_active_goal_run_uses_product_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run_goal_contract(
        contract, *, game_path, attempts, artifacts_dir, capture_images=False, capture_ticks=False
    ):
        assert contract.preset == "fceux_world_8_double_whistle"
        return GoalRunResult(
            contract=contract,
            summary=BatchSummary(
                attempts=(), post_probe_last_event="post_probe_world_8_map_arrival"
            ),
            artifacts_dir=artifacts_dir,
            metrics_passed=True,
        )

    monkeypatch.setattr("smb3_agent.commands.run_goal_contract", fake_run_goal_contract)
    game_file = tmp_path / "local-game-file"
    game_file.write_text("placeholder")

    result = run_command(
        "run world 8 double whistle arrival",
        game_path=game_file,
        artifacts_dir=tmp_path / "command",
    )

    assert result.goal_result.metrics_passed is True
