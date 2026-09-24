from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from smb3_agent.stardew_adapter import (
    CropObservation,
    DisposableSaveManager,
    FailureCode,
    InputCommand,
    InputKind,
    InputOwner,
    OperatorLifecycle,
    OrdinaryInputDriver,
    PositionObservation,
    SaveIdentity,
    ScreenObservation,
    StardewAdapterError,
    StardewOperator,
    ToolObservation,
    WindowObservation,
    render_stardew_operator,
)


def save_identity(tmp_path: Path) -> SaveIdentity:
    primary = tmp_path / "primary"
    copied = tmp_path / "copied"
    primary.mkdir()
    copied.mkdir()
    return SaveIdentity(
        primary_path=str(primary),
        primary_real_path=str(primary.resolve()),
        disposable_path=str(copied),
        disposable_real_path=str(copied.resolve()),
        source_tree_sha256="fixture-save",
        disposable_tree_sha256="fixture-save",
        file_count=2,
        byte_count=20,
        created_at="2026-08-22T12:00:00+00:00",
        nonce="fixture-nonce",
        primary_unchanged=True,
        disposable_only=True,
    )


def observation(
    *,
    watered: tuple[bool, bool] = (False, True),
    at_entrance: bool = False,
    occluded: bool = False,
    scene_complete: bool = True,
    process_id: int = 4242,
    tool_uses: int = 0,
    energy: int = 270,
) -> ScreenObservation:
    window = WindowObservation(
        process_id=process_id,
        process_started_at="2026-08-22T12:00:00+00:00",
        window_id="fixture-window",
        title="Stardew Valley",
        bounds=(100, 100, 1280, 720),
        visible=True,
        windowed=True,
        foreground=True,
    )
    crops = tuple(
        CropObservation(
            crop_id=f"farm-{61 + index}-18",
            tile_x=61 + index,
            tile_y=18,
            planted=True,
            watered=is_watered,
            occluded=occluded and index == 0,
            confidence=1.0,
            evidence_reference=f"screens/crop-{index}.png",
        )
        for index, is_watered in enumerate(watered)
    )
    return ScreenObservation(
        observation_id="fixture-observation",
        observed_at="2026-08-22T12:00:01+00:00",
        save_tree_sha256="fixture-save",
        window=window,
        crops=crops,
        energy=energy,
        energy_maximum=270,
        tool=ToolObservation(
            selected_tool="watering_can",
            watering_can_units=40 - tool_uses,
            watering_can_capacity=40,
            refill_count=0,
            tool_uses=tool_uses,
        ),
        position=PositionObservation(
            location="Farm",
            tile_x=64,
            tile_y=14 if at_entrance else 18,
            at_farmhouse_entrance=at_entrance,
            confidence=1.0,
        ),
        screenshot_references=("screens/full.png",),
        scene_complete=scene_complete,
    )


def test_disposable_copy_has_exact_identity_and_preserves_primary(tmp_path: Path) -> None:
    primary = tmp_path / "owner" / "Farm_123"
    primary.mkdir(parents=True)
    (primary / "Farm_123").write_text("save", encoding="utf-8")
    (primary / "SaveGameInfo").write_text("info", encoding="utf-8")
    manager = DisposableSaveManager()
    identity = manager.create(primary, tmp_path / "attempt" / "Farm_123")
    assert identity.valid
    assert manager.verify_primary_unchanged(identity)
    assert (Path(identity.disposable_path) / "Farm_123").read_text(encoding="utf-8") == "save"


def test_disposable_copy_refuses_existing_or_nested_target(tmp_path: Path) -> None:
    primary = tmp_path / "primary"
    primary.mkdir()
    (primary / "save").write_text("save", encoding="utf-8")
    with pytest.raises(StardewAdapterError, match=FailureCode.PRIMARY_SAVE_RISK.value):
        DisposableSaveManager().create(primary, primary / "copy")


def test_screen_observation_refuses_unknown_or_occluded_crop(tmp_path: Path) -> None:
    expected = save_identity(tmp_path).disposable_tree_sha256
    with pytest.raises(StardewAdapterError, match=FailureCode.OCCLUDED_CROPS.value):
        observation(occluded=True).validate(expected)
    with pytest.raises(StardewAdapterError, match=FailureCode.UNKNOWN_STATE.value):
        observation(scene_complete=False).validate(expected)


def test_exact_crop_reconciliation_and_entrance_completion(tmp_path: Path) -> None:
    operator = StardewOperator(save_identity(tmp_path))
    first = observation()
    operator.attach_player_owned(first)
    ledger = operator.establish_task(first)
    assert ledger.planted_count == 2
    assert ledger.watered_count == 1
    operator.authorize_agent(expires_at="2099-08-22T12:00:00+00:00", owner_confirmation=True)
    operator.complete(observation(watered=(True, True), at_entrance=True, tool_uses=1, energy=268))
    assert operator.ledger is not None and operator.ledger.complete
    assert operator.ledger.energy_spent == 2
    assert operator.owner is InputOwner.PLAYER


def test_crop_set_change_fails_closed(tmp_path: Path) -> None:
    operator = StardewOperator(save_identity(tmp_path))
    first = observation()
    operator.attach_player_owned(first)
    operator.establish_task(first)
    operator.authorize_agent(expires_at="2099-08-22T12:00:00+00:00", owner_confirmation=True)
    changed = replace(observation(watered=(True, True)), crops=observation().crops[:1])
    with pytest.raises(StardewAdapterError, match=FailureCode.ACCOUNTING_MISMATCH.value):
        operator.record_post_input(changed)


def test_process_loss_and_protected_action_are_refused(tmp_path: Path) -> None:
    operator = StardewOperator(save_identity(tmp_path))
    first = observation()
    operator.attach_player_owned(first)
    operator.establish_task(first)
    operator.authorize_agent(expires_at="2099-08-22T12:00:00+00:00", owner_confirmation=True)
    with pytest.raises(StardewAdapterError, match=FailureCode.PROCESS_LOSS.value):
        operator.validate_input(
            InputCommand(InputKind.KEYBOARD, "w", "press", purpose="navigate"),
            observation(process_id=5151),
        )
    with pytest.raises(StardewAdapterError, match=FailureCode.PROTECTED_ACTION_RISK.value):
        operator.validate_input(
            InputCommand(InputKind.KEYBOARD, "x", "press purchase", purpose="water_crop"),
            first,
        )


def test_failure_neutralizes_returns_safe_owner_and_renders_narrow_contract(tmp_path: Path) -> None:
    operator = StardewOperator(save_identity(tmp_path))
    operator.attach_player_owned(observation())
    failure = operator.fail(FailureCode.MISSING_EVIDENCE, "Final screenshot is missing.")
    page = render_stardew_operator(operator.view())
    assert failure.input_neutralized
    assert operator.owner is InputOwner.PLAYER
    assert 'data-testid="input-owner">You control the game' in page
    assert 'data-testid="failure"' in page
    assert "@media(max-width:620px)" in page
    assert 'data-testid="tell-card"' in page
    assert 'data-testid="show-status"' in page
    assert 'data-testid="do-scope"' in page
    assert "@media(max-width:390px)" in page


def test_input_and_neutralization_double_failure_stays_failed_closed(tmp_path: Path) -> None:
    operator = StardewOperator(save_identity(tmp_path))
    current = observation()
    operator.attach_player_owned(current)
    operator.establish_task(current)
    operator.authorize_agent(
        expires_at="2099-08-22T12:00:00+00:00", owner_confirmation=True
    )
    broken = OrdinaryInputDriver(
        keyboard=lambda _command: (_ for _ in ()).throw(RuntimeError("send lost")),
        neutralizer=lambda: (_ for _ in ()).throw(OSError("neutral lost")),
    )

    with pytest.raises(StardewAdapterError, match=FailureCode.INPUT_REJECTED.value):
        operator.send_input(
            InputCommand(InputKind.KEYBOARD, "w", "press", purpose="navigate"),
            current,
            broken,
        )

    assert operator.lifecycle is OperatorLifecycle.FAILED
    assert operator.owner is InputOwner.NONE
    assert not operator.input_neutralized
    assert operator.failure is not None
    assert "send lost" in operator.failure.detail
    assert "neutral lost" in operator.failure.detail
