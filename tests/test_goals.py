from pathlib import Path

import pytest
import yaml

from smb3_agent.fceux_harness import AttemptSummary, BatchSummary
from smb3_agent.goals import (
    GoalValidationError,
    evaluate_success_metrics,
    load_goal_contract,
    load_product_goal_contracts,
    resolve_goal_path,
    run_goal_contract,
)
from smb3_agent.presets import EXECUTABLE_PRESETS, environment_for_preset
from smb3_agent.reliability import RELIABILITY_PROFILES


def test_load_world_1_king_goal_contract() -> None:
    contract = load_goal_contract(Path("data/goals/world_1_king.yaml"))

    assert contract.id == "world_1_king"
    assert contract.goal_type == "diagnostic_route"
    assert contract.preset == "fceux_world_1_king"
    assert "world_1_fortress_whistle" not in contract.bridged_segments
    assert contract.segments[0] == "fresh_start_to_1_1"


def test_product_goal_contracts_are_authoritative_for_supported_product_catalog() -> None:
    contracts = load_product_goal_contracts()

    assert contracts[0].id == "world_8_double_whistle"
    assert [len(contract.route_steps) for contract in contracts] == sorted(
        len(contract.route_steps) for contract in contracts
    )
    assert {contract.id for contract in contracts} == set(RELIABILITY_PROFILES)
    assert all(contract.display_name and contract.display_subtitle for contract in contracts)
    assert {contract.preset for contract in contracts}.issubset(EXECUTABLE_PRESETS)


def test_preset_environment_policy_has_one_authoritative_mapping() -> None:
    contract_presets = {
        load_goal_contract(contract_path).preset
        for contract_path in Path("data/goals").glob("*.yaml")
    }

    assert contract_presets == EXECUTABLE_PRESETS
    assert environment_for_preset("fceux_world_8_double_whistle") == ()
    assert all(
        "=" in setting
        for preset in EXECUTABLE_PRESETS
        for setting in environment_for_preset(preset)
    )
    with pytest.raises(ValueError, match="Unsupported executable preset"):
        environment_for_preset("removed_preset")


def test_goal_contract_reports_missing_required_fields(tmp_path: Path) -> None:
    bad_contract = tmp_path / "bad.yaml"
    bad_contract.write_text(yaml.safe_dump({"id": "bad_goal"}))

    with pytest.raises(GoalValidationError, match="Missing required field"):
        load_goal_contract(bad_contract)


def test_goal_contract_rejects_bridge_not_in_route(tmp_path: Path) -> None:
    raw = yaml.safe_load(Path("data/goals/world_1_king.yaml").read_text())
    raw["bridged_segments"] = ["not_in_route"]
    bad_contract = tmp_path / "bad_bridge.yaml"
    bad_contract.write_text(yaml.safe_dump(raw))

    with pytest.raises(GoalValidationError, match="bridged_segments not present"):
        load_goal_contract(bad_contract)


def test_goal_contract_rejects_duplicate_runner_environment_policy(tmp_path: Path) -> None:
    raw = yaml.safe_load(Path("data/goals/world_8_double_whistle.yaml").read_text())
    raw["runner"]["env"] = ["SMB3_WORLD_8_EXTENSION_MODE=shadow_path"]
    bad_contract = tmp_path / "duplicate-runner-policy.yaml"
    bad_contract.write_text(yaml.safe_dump(raw))

    with pytest.raises(GoalValidationError, match="runner.env is unsupported"):
        load_goal_contract(bad_contract)


def test_goal_success_metrics_pass_for_king_summary() -> None:
    contract = load_goal_contract(Path("data/goals/world_1_king.yaml"))
    summary = BatchSummary(
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
        post_probe_max_x=432,
        post_probe_last_event="post_probe_1_airship_success_king",
        post_probe_clear=True,
        post_probe_events=(
            "post_probe_1_fortress_whistle_room_success",
            "post_probe_1_airship_success_king",
        ),
    )

    assert evaluate_success_metrics(contract, summary) is True


def test_goal_success_metrics_fail_without_final_event() -> None:
    contract = load_goal_contract(Path("data/goals/world_1_king.yaml"))
    summary = BatchSummary(
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
        post_probe_last_event="post_probe_1_4_after",
        post_probe_clear=False,
    )

    assert evaluate_success_metrics(contract, summary) is False


def test_goal_success_metrics_reject_fortress_whistle_bridge() -> None:
    contract = load_goal_contract(Path("data/goals/world_1_king.yaml"))
    summary = BatchSummary(
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
        post_probe_events=(
            "post_probe_1_fortress_bridge_second_whistle",
            "post_probe_1_airship_success_king",
        ),
    )

    assert evaluate_success_metrics(contract, summary) is False


def test_resolve_goal_path_accepts_id() -> None:
    assert resolve_goal_path("world_1_king") == Path("data/goals/world_1_king.yaml").resolve()


@pytest.mark.parametrize("goal_id", ("../world_1_king", "/tmp/goal", "world-1-king"))
def test_resolve_goal_path_rejects_non_catalog_identifiers(goal_id: str) -> None:
    with pytest.raises(GoalValidationError, match="Invalid goal id"):
        resolve_goal_path(goal_id)


def test_active_product_goal_is_world_2_first_double_whistle_world_8_arrival() -> None:
    contract = load_goal_contract(Path("data/goals/world_8_double_whistle.yaml"))
    roles = {step.id: step.classification for step in contract.route_steps}

    assert contract.goal_type == "product_goal"
    assert contract.objective["target"] == "world_8_map_arrival"
    assert contract.execution_status == "executable"
    assert contract.executable is True
    assert contract.preset == "fceux_world_8_double_whistle"
    assert "world_1_3_whistle" in contract.segments
    assert "world_1_fortress_whistle" in contract.segments
    assert roles["world_1_3_whistle"] == "objective_milestone"
    assert roles["world_1_fortress_whistle"] == "objective_milestone"


def test_active_route_matches_owner_corrected_world_2_boundary() -> None:
    contract = load_goal_contract(Path("data/goals/world_8_double_whistle.yaml"))
    roles = {step.id: step for step in contract.route_steps}

    assert "world_1_4_clear" not in contract.segments
    assert roles["world_1_5_water_path"].classification == "game_prerequisite"
    assert roles["world_1_5_water_path"].evidence
    assert roles["world_1_6_clear"].classification == "game_prerequisite"
    assert roles["world_1_6_clear"].evidence
    assert roles["world_1_airship_to_king"].classification == "game_prerequisite"
    assert contract.segments.index("world_1_airship_to_king") < contract.segments.index(
        "world_2_map_arrival_with_two_whistles"
    )
    assert contract.segments.index("world_2_map_arrival_with_two_whistles") < contract.segments.index(
        "world_2_first_whistle_use"
    )
    assert "world_2_first_whistle_use" in contract.segments
    assert "world_7_entry" not in contract.segments


def test_active_route_orders_distinct_whistle_and_warp_zone_transitions() -> None:
    contract = load_goal_contract(Path("data/goals/world_8_double_whistle.yaml"))

    ordered = (
        "world_2_first_whistle_use",
        "warp_zone_5_6_7_tier",
        "warp_zone_second_whistle_use",
        "warp_zone_world_8_tier",
        "world_8_pipe_entry",
        "world_8_map_arrival",
    )
    assert tuple(sorted(ordered, key=contract.segments.index)) == ordered


def test_active_goal_only_passes_on_world_8_map_arrival() -> None:
    contract = load_goal_contract(Path("data/goals/world_8_double_whistle.yaml"))
    attempts = (
        AttemptSummary(
            attempt=1,
            success=True,
            bad_state=False,
            reached_end=True,
            goal_area=True,
            max_x=2848,
        ),
    )
    required_events = (
        "post_probe_1_3_whistle_room_success",
        "post_probe_1_fortress_whistle_room_success",
        "post_probe_world_2_map_two_whistles",
        "post_probe_world_2_first_whistle_used",
        "post_probe_warp_zone_second_whistle_used",
    )
    king_summary = BatchSummary(
        attempts=attempts,
        post_probe_last_event="post_probe_1_airship_success_king",
        post_probe_clear=True,
        post_probe_events=required_events + ("post_probe_1_airship_success_king",),
    )
    world_8_summary = BatchSummary(
        attempts=attempts,
        post_probe_last_event="post_probe_world_8_map_arrival",
        post_probe_clear=True,
        post_probe_events=required_events + ("post_probe_world_8_map_arrival",),
    )

    assert evaluate_success_metrics(contract, king_summary) is False
    assert evaluate_success_metrics(contract, world_8_summary) is True


def test_world_8_big_tanks_is_a_separate_one_segment_extension() -> None:
    prefix = load_goal_contract(Path("data/goals/world_8_double_whistle.yaml"))
    extension = load_goal_contract(Path("data/goals/world_8_big_tanks.yaml"))

    assert len(prefix.segments) == 15
    assert prefix.segments[-1] == "world_8_map_arrival"
    assert extension.prefix_goal == prefix.id
    assert extension.segments[:15] == prefix.segments
    assert extension.segments[15:] == ("world_8_big_tanks_clear",)
    assert extension.preset == "fceux_world_8_big_tanks"
    assert extension.execution_status == "executable"


def test_world_8_battleships_is_the_seventeenth_cumulative_segment() -> None:
    arrival = load_goal_contract(Path("data/goals/world_8_double_whistle.yaml"))
    big_tanks = load_goal_contract(Path("data/goals/world_8_big_tanks.yaml"))
    battleships = load_goal_contract(Path("data/goals/world_8_battleships.yaml"))

    assert len(arrival.segments) == 15
    assert len(big_tanks.segments) == 16
    assert len(battleships.segments) == 17
    assert battleships.prefix_goal == big_tanks.id
    assert battleships.segments[:16] == big_tanks.segments
    assert battleships.segments[16:] == ("world_8_battleships_clear",)
    assert battleships.bridged_segments == ()
    assert battleships.preset == "fceux_world_8_battleships"
    assert arrival.segments[-1] == "world_8_map_arrival"
    assert big_tanks.segments[-1] == "world_8_big_tanks_clear"


def test_world_8_hand_traps_jet_is_exact_21_segment_zero_bridge_extension() -> None:
    arrival = load_goal_contract(Path("data/goals/world_8_double_whistle.yaml"))
    big_tanks = load_goal_contract(Path("data/goals/world_8_big_tanks.yaml"))
    battleships = load_goal_contract(Path("data/goals/world_8_battleships.yaml"))
    goal = load_goal_contract(Path("data/goals/world_8_hand_traps_jet.yaml"))

    assert (len(arrival.segments), len(big_tanks.segments), len(battleships.segments)) == (
        15,
        16,
        17,
    )
    assert goal.prefix_goal == battleships.id
    assert goal.segments[:17] == battleships.segments
    assert goal.segments[17:] == (
        "world_8_hand_trap_right_clear",
        "world_8_hand_trap_center_clear",
        "world_8_hand_trap_left_clear",
        "world_8_jet_clear",
    )
    assert len(goal.segments) == 21
    assert goal.bridged_segments == ()
    assert goal.preset == "fceux_world_8_hand_traps_jet"
    assert goal.constraints["start_from_power_on"] is True
    assert goal.constraints["stop_before_world_8_1_gameplay"] is True
    assert goal.allowed_tactics["runtime_search"] is False
    assert goal.allowed_tactics["savestate"] is False


def test_hand_traps_jet_goal_requires_jet_clear_and_rejects_world_8_1_entry() -> None:
    contract = load_goal_contract(Path("data/goals/world_8_hand_traps_jet.yaml"))
    attempts = (AttemptSummary(1, True, False, True, True, 3090),)
    required = (
        "post_probe_world_8_battleships_post_clear",
        "post_probe_world_8_battleships_p_wing_preserved",
        "post_probe_world_8_battleships_star_used",
        "post_probe_world_8_battleships_swim_started",
        "post_probe_world_8_battleships_stern_wait",
        "post_probe_world_8_hand_trap_right_post_clear",
        "post_probe_world_8_hand_trap_center_post_clear",
        "post_probe_world_8_hand_trap_left_post_clear",
        "post_probe_world_8_jet_p_wing_used",
        "post_probe_world_8_jet_entered",
        "post_probe_world_8_jet_gameplay",
        "post_probe_world_8_jet_boss_defeated",
        "post_probe_world_8_jet_clear",
        "post_probe_world_8_jet_post_clear",
    )
    accepted = BatchSummary(
        attempts=attempts,
        post_probe_last_event="post_probe_world_8_jet_post_clear",
        post_probe_clear=True,
        post_probe_events=required,
    )
    entered_later_level = BatchSummary(
        attempts=attempts,
        post_probe_last_event="post_probe_world_8_jet_post_clear",
        post_probe_clear=True,
        post_probe_events=required + ("post_probe_world_8_jet_world_8_1_entered",),
    )

    assert evaluate_success_metrics(contract, accepted) is True
    assert evaluate_success_metrics(contract, entered_later_level) is False


def test_world_8_8_2_is_exact_23_segment_zero_bridge_extension() -> None:
    arrival = load_goal_contract(Path("data/goals/world_8_double_whistle.yaml"))
    big_tanks = load_goal_contract(Path("data/goals/world_8_big_tanks.yaml"))
    battleships = load_goal_contract(Path("data/goals/world_8_battleships.yaml"))
    hand_traps_jet = load_goal_contract(
        Path("data/goals/world_8_hand_traps_jet.yaml")
    )
    goal = load_goal_contract(Path("data/goals/world_8_8_2.yaml"))

    assert tuple(
        len(contract.segments)
        for contract in (arrival, big_tanks, battleships, hand_traps_jet, goal)
    ) == (15, 16, 17, 21, 23)
    assert goal.prefix_goal == hand_traps_jet.id
    assert goal.segments[:21] == hand_traps_jet.segments
    assert goal.segments[21:] == ("world_8_1_clear", "world_8_2_clear")
    assert goal.bridged_segments == ()
    assert goal.preset == "fceux_world_8_8_2"
    assert goal.constraints["start_from_power_on"] is True
    assert goal.constraints["require_distinct_goal_cards"] is True
    assert goal.constraints["stop_before_world_8_fortress_gameplay"] is True
    assert goal.allowed_tactics["runtime_search"] is False
    assert goal.allowed_tactics["savestate"] is False


def test_world_8_8_2_metrics_require_both_levels_and_reject_fortress_entry() -> None:
    contract = load_goal_contract(Path("data/goals/world_8_8_2.yaml"))
    attempts = (AttemptSummary(1, True, False, True, True, 3709),)
    required = (
        "post_probe_world_8_jet_post_clear",
        "post_probe_world_8_1_entered",
        "post_probe_world_8_1_gameplay",
        "post_probe_world_8_1_goal_card",
        "post_probe_world_8_1_course_clear",
        "post_probe_world_8_1_post_clear",
        "post_probe_world_8_2_entered",
        "post_probe_world_8_2_gameplay",
        "post_probe_world_8_2_goal_card",
        "post_probe_world_8_2_course_clear",
        "post_probe_world_8_2_post_clear",
    )
    accepted = BatchSummary(
        attempts=attempts,
        post_probe_last_event="post_probe_world_8_2_post_clear",
        post_probe_clear=True,
        post_probe_events=required,
    )
    missing_world_8_1_goal = BatchSummary(
        attempts=attempts,
        post_probe_last_event="post_probe_world_8_2_post_clear",
        post_probe_clear=True,
        post_probe_events=tuple(
            event for event in required if event != "post_probe_world_8_1_goal_card"
        ),
    )
    fortress_entered = BatchSummary(
        attempts=attempts,
        post_probe_last_event="post_probe_world_8_2_post_clear",
        post_probe_clear=True,
        post_probe_events=required + ("post_probe_world_8_fortress_entered",),
    )

    assert resolve_goal_path("world_8_8_2") == Path("data/goals/world_8_8_2.yaml").resolve()
    assert evaluate_success_metrics(contract, accepted) is True
    assert evaluate_success_metrics(contract, missing_world_8_1_goal) is False
    assert evaluate_success_metrics(contract, fortress_entered) is False


def test_world_8_8_2_uses_its_exact_product_preset_without_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake_run_fceux_1_1(**kwargs):
        captured.update(kwargs)
        return BatchSummary(
            attempts=(AttemptSummary(1, True, False, True, True, 3709),),
            post_probe_last_event="post_probe_world_8_2_post_clear",
            post_probe_clear=True,
            post_probe_events=(),
        )

    monkeypatch.setattr("smb3_agent.goals.run_fceux_1_1", fake_run_fceux_1_1)
    contract = load_goal_contract(Path("data/goals/world_8_8_2.yaml"))
    game_path = tmp_path / "local-game.nes"
    game_path.write_bytes(b"local")

    run_goal_contract(
        contract,
        game_path=game_path,
        attempts=1,
        artifacts_dir=tmp_path / "artifacts",
    )

    assert captured["env_overrides"] == (
        "SMB3_WORLD_8_EXTENSION_MODE=world_8_8_2",
        "SMB3_WORLD_8_FOCUSED_CAPTURE=1",
    )
    assert captured["post_1_1_probe"] == "run_1_castle_after_1_6"
    assert captured["allow_bridges"] is False


def test_world_8_super_tanks_is_exact_25_segment_zero_bridge_extension() -> None:
    goal_ids = (
        "world_8_double_whistle",
        "world_8_big_tanks",
        "world_8_battleships",
        "world_8_hand_traps_jet",
        "world_8_8_2",
        "world_8_super_tanks",
    )
    contracts = tuple(
        load_goal_contract(Path(f"data/goals/{goal_id}.yaml"))
        for goal_id in goal_ids
    )
    prefix = contracts[-2]
    goal = contracts[-1]

    assert tuple(len(contract.segments) for contract in contracts) == (
        15, 16, 17, 21, 23, 25
    )
    assert goal.prefix_goal == prefix.id
    assert goal.segments[:23] == prefix.segments
    assert goal.segments[23:] == (
        "world_8_fortress_clear",
        "world_8_super_tanks_clear",
    )
    assert goal.bridged_segments == ()
    assert goal.preset == "fceux_world_8_super_tanks"
    assert goal.constraints["start_from_power_on"] is True
    assert goal.constraints["stop_before_bowser_castle_gameplay"] is True
    assert goal.allowed_tactics["runtime_search"] is False
    assert goal.allowed_tactics["savestate"] is False


def test_world_8_super_tanks_metrics_require_both_magic_balls_and_reject_castle() -> None:
    contract = load_goal_contract(Path("data/goals/world_8_super_tanks.yaml"))
    required = tuple(
        metric["value"]
        for metric in contract.success_metrics
        if metric["type"] == "event_present"
    )
    attempts = (AttemptSummary(1, True, False, True, True, 3709),)
    accepted = BatchSummary(
        attempts=attempts,
        post_probe_last_event="post_probe_world_8_super_tanks_post_clear",
        post_probe_clear=True,
        post_probe_events=required,
    )
    missing_fortress_ball = BatchSummary(
        attempts=attempts,
        post_probe_last_event="post_probe_world_8_super_tanks_post_clear",
        post_probe_clear=True,
        post_probe_events=tuple(
            event
            for event in required
            if event != "post_probe_world_8_fortress_magic_ball"
        ),
    )
    castle_entered = BatchSummary(
        attempts=attempts,
        post_probe_last_event="post_probe_world_8_super_tanks_post_clear",
        post_probe_clear=True,
        post_probe_events=required + ("post_probe_world_8_bowser_castle_entered",),
    )

    assert resolve_goal_path("world_8_super_tanks") == Path(
        "data/goals/world_8_super_tanks.yaml"
    ).resolve()
    assert evaluate_success_metrics(contract, accepted) is True
    assert evaluate_success_metrics(contract, missing_fortress_ball) is False
    assert evaluate_success_metrics(contract, castle_entered) is False


def test_world_8_super_tanks_uses_exact_product_preset_without_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake_run_fceux_1_1(**kwargs):
        captured.update(kwargs)
        return BatchSummary(
            attempts=(AttemptSummary(1, True, False, True, True, 3709),),
            post_probe_last_event="post_probe_world_8_super_tanks_post_clear",
            post_probe_clear=True,
            post_probe_events=(),
        )

    monkeypatch.setattr("smb3_agent.goals.run_fceux_1_1", fake_run_fceux_1_1)
    contract = load_goal_contract(Path("data/goals/world_8_super_tanks.yaml"))
    game_path = tmp_path / "local-game.nes"
    game_path.write_bytes(b"local")

    run_goal_contract(
        contract,
        game_path=game_path,
        attempts=1,
        artifacts_dir=tmp_path / "artifacts",
    )

    assert captured["env_overrides"] == (
        "SMB3_WORLD_8_EXTENSION_MODE=world_8_super_tanks",
        "SMB3_WORLD_8_FOCUSED_CAPTURE=1",
        "SMB3_FCEUX_TIMEOUT_SECONDS=600",
    )
    assert captured["allow_bridges"] is False


def test_world_8_finish_game_is_exact_26_segment_zero_bridge_extension() -> None:
    prefix = load_goal_contract(Path("data/goals/world_8_super_tanks.yaml"))
    goal = load_goal_contract(Path("data/goals/world_8_finish_game.yaml"))

    assert len(goal.segments) == 26
    assert goal.prefix_goal == prefix.id
    assert goal.segments[:25] == prefix.segments
    assert goal.segments[-1] == "world_8_bowser_castle_finish"
    assert goal.bridged_segments == ()
    assert goal.preset == "fceux_world_8_finish_game"
    assert goal.constraints["require_princess_rescue"] is True
    assert goal.constraints["require_complete_credits"] is True
    assert goal.constraints["require_stable_game_owned_ending"] is True
    assert goal.allowed_tactics["runtime_search"] is False
    assert goal.allowed_tactics["savestate"] is False



def test_world_8_finish_game_uses_exact_product_preset_without_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake_run_fceux_1_1(**kwargs):
        captured.update(kwargs)
        return BatchSummary(
            attempts=(AttemptSummary(1, True, False, True, True, 3709),),
            post_probe_last_event="post_probe_world_8_bowser_castle_stable_ending",
            post_probe_clear=True,
            post_probe_events=(),
        )

    monkeypatch.setattr("smb3_agent.goals.run_fceux_1_1", fake_run_fceux_1_1)
    contract = load_goal_contract(Path("data/goals/world_8_finish_game.yaml"))
    game_path = tmp_path / "local-game.nes"
    game_path.write_bytes(b"local")

    run_goal_contract(
        contract,
        game_path=game_path,
        attempts=1,
        artifacts_dir=tmp_path / "artifacts",
    )

    assert captured["env_overrides"] == (
        "SMB3_WORLD_8_EXTENSION_MODE=world_8_finish_game",
        "SMB3_WORLD_8_FOCUSED_CAPTURE=1",
        "SMB3_FCEUX_TIMEOUT_SECONDS=900",
    )
    assert captured["allow_bridges"] is False


def test_battleships_goal_cannot_pass_on_prefix_or_entry_alone() -> None:
    contract = load_goal_contract(Path("data/goals/world_8_battleships.yaml"))
    attempts = (
        AttemptSummary(1, True, False, True, True, 3136),
    )
    summary = BatchSummary(
        attempts=attempts,
        post_probe_last_event="post_probe_world_8_battleships_entered",
        post_probe_clear=False,
        post_probe_events=(
            "post_probe_world_8_big_tanks_post_clear",
            "post_probe_world_8_battleships_entered",
        ),
    )

    assert evaluate_success_metrics(contract, summary) is False


def test_goal_contract_rejects_prefix_cycles(tmp_path: Path) -> None:
    cycle = tmp_path / "cycle.yaml"
    cycle.write_text(Path("data/goals/world_8_big_tanks.yaml").read_text())

    with pytest.raises(GoalValidationError, match="prefix cycle"):
        load_goal_contract(cycle, _seen=frozenset({cycle.resolve()}))


def test_big_tanks_goal_cannot_pass_on_prefix_or_entry_alone() -> None:
    contract = load_goal_contract(Path("data/goals/world_8_big_tanks.yaml"))
    attempts = (
        AttemptSummary(
            attempt=1,
            success=True,
            bad_state=False,
            reached_end=True,
            goal_area=True,
            max_x=3136,
        ),
    )
    prefix_only = BatchSummary(
        attempts=attempts,
        post_probe_last_event="post_probe_world_8_map_arrival",
        post_probe_clear=True,
        post_probe_events=("post_probe_world_8_map_arrival",),
    )
    entry_only = BatchSummary(
        attempts=attempts,
        post_probe_last_event="post_probe_world_8_big_tanks_entered",
        post_probe_clear=False,
        post_probe_events=(
            "post_probe_world_8_map_arrival",
            "post_probe_world_8_big_tanks_entered",
        ),
    )

    assert evaluate_success_metrics(contract, prefix_only) is False
    assert evaluate_success_metrics(contract, entry_only) is False
