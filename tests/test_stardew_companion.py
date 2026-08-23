from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from smb3_agent.companion_session import Freshness
from smb3_agent.stardew_adapter import (
    CropObservation,
    DisposableSaveManager,
    FailureCode,
    InputCommand,
    InputKind,
    InputOwner,
    OrdinaryInputDriver,
    PositionObservation,
    SaveIdentity,
    ScreenObservation,
    StardewAdapterError,
    ToolObservation,
    WindowObservation,
    render_stardew_operator,
)
from smb3_agent.stardew_companion import (
    StardewAttemptStatus,
    StardewCompanionController,
    StardewCompanionError,
    StardewCompanionProvider,
    StardewMode,
    convert_stardew_observation,
)


def save_identity(tmp_path: Path, nonce: str = "fresh-copy") -> SaveIdentity:
    primary = tmp_path / "primary"
    copied = tmp_path / "attempt" / "copied"
    primary.mkdir(parents=True, exist_ok=True)
    copied.mkdir(parents=True, exist_ok=True)
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
        nonce=nonce,
        primary_unchanged=True,
        disposable_only=True,
    )


def observation(
    observation_id: str = "observation-1",
    *,
    watered: tuple[bool, bool] = (False, True),
    selected_tool: str = "watering_can",
    can_units: int = 40,
    tool_uses: int = 0,
    refills: int = 0,
    energy: int = 270,
    at_entrance: bool = False,
    process_started_at: str = "2026-08-22T12:00:00+00:00",
    window_id: str = "fixture-window",
    evidence: tuple[str, ...] = ("screens/full.png",),
    scene_complete: bool = True,
) -> ScreenObservation:
    return ScreenObservation(
        observation_id=observation_id,
        observed_at="2026-08-22T12:00:01+00:00",
        save_tree_sha256="fixture-save",
        window=WindowObservation(
            process_id=4242,
            process_started_at=process_started_at,
            window_id=window_id,
            title="Stardew Valley",
            bounds=(100, 100, 1280, 720),
            visible=True,
            windowed=True,
            foreground=True,
        ),
        crops=tuple(
            CropObservation(
                crop_id=f"farm-{61 + index}-18",
                tile_x=61 + index,
                tile_y=18,
                planted=True,
                watered=value,
                occluded=False,
                confidence=1.0,
                evidence_reference=f"screens/crop-{index}.png",
            )
            for index, value in enumerate(watered)
        ),
        energy=energy,
        energy_maximum=270,
        tool=ToolObservation(selected_tool, can_units, 40, refills, tool_uses),
        position=PositionObservation(
            "Farm", 64, 14 if at_entrance else 18, at_entrance, 1.0
        ),
        screenshot_references=evidence,
        scene_complete=scene_complete,
    )


def driver(events: list[str], kind: InputKind = InputKind.KEYBOARD) -> OrdinaryInputDriver:
    kwargs = {kind.value: lambda command: events.append(f"send:{command.purpose}")}
    return OrdinaryInputDriver(
        **kwargs,
        neutralizer=lambda: events.append("neutralize"),
    )


def test_observe_conversion_preserves_adapter_identity_facts_without_mario_fields(tmp_path: Path) -> None:
    screen = observation()
    envelope = convert_stardew_observation(
        screen, save_identity(tmp_path), input_owner=InputOwner.PLAYER
    )
    assert envelope.trusted
    assert envelope.observation.freshness is Freshness.FRESH
    assert envelope.observation.confidence == 1.0
    assert envelope.session_identity["process_started_at"] == screen.window.process_started_at
    assert envelope.session_identity["window_id"] == screen.window.window_id
    assert envelope.facts["screenshot_evidence"] == screen.screenshot_references
    assert envelope.facts["input_owner"] == "player"
    assert not {"world", "object_set", "map_page", "emulator_pid"}.intersection(envelope.facts)


@pytest.mark.parametrize(
    ("changed", "reason"),
    [
        ({"process_started_at": "2026-08-22T12:10:00+00:00"}, "process_loss"),
        ({"window_id": "replacement-window"}, "process_loss"),
        ({"evidence": ()}, "missing_evidence"),
        ({"scene_complete": False}, "unknown_state"),
    ],
)
def test_observe_becomes_stale_on_continuity_or_evidence_loss(
    tmp_path: Path, changed: dict[str, object], reason: str
) -> None:
    initial = observation()
    current = observation("changed", **changed)
    envelope = convert_stardew_observation(
        current,
        save_identity(tmp_path),
        input_owner=InputOwner.PLAYER,
        expected_window=initial.window,
    )
    assert not envelope.trusted
    assert envelope.observation.freshness is Freshness.STALE
    assert any(reason in item for item in envelope.stale_reasons)


def test_tell_is_contextual_grounded_and_sends_no_input(tmp_path: Path) -> None:
    provider = StardewCompanionProvider()
    envelope = provider.observe(
        observation(), save_identity(tmp_path), input_owner=InputOwner.PLAYER
    )
    card = provider.tell(envelope)
    assert "farm-61-18" in card.steps[0].expected_cue.text
    assert all(item.provenance for item in (card.state_summary, card.objective, *card.risks))
    classes = {
        reference.source_class
        for item in (card.state_summary, card.objective, *card.risks)
        for reference in item.provenance
    }
    assert {"adapter_observation", "watering_ledger", "adapter_safety_policy"} <= classes


def test_standalone_desktop_and_390_presentation_exposes_every_mode_boundary(tmp_path: Path) -> None:
    controller = StardewCompanionController(save_identity(tmp_path))
    controller.tell(observation())
    page = render_stardew_operator(controller.view())
    for test_id in (
        "current-mode", "observation-freshness", "tell-card", "show-status",
        "do-scope", "input-owner", "neutralization-status", "handback-status",
        "reset-status", "crop-progress", "refill-count", "final-position",
        "protected-action-refusal",
    ):
        assert f'data-testid="{test_id}"' in page
    assert "Review only" in page
    assert "@media(max-width:390px)" in page


def test_tell_refuses_unknown_or_stale_observation(tmp_path: Path) -> None:
    provider = StardewCompanionProvider()
    stale = provider.observe(
        observation(evidence=()), save_identity(tmp_path), input_owner=InputOwner.PLAYER
    )
    with pytest.raises(StardewCompanionError, match="Tell disabled"):
        provider.tell(stale)
    assert all(not mode.available for mode in provider.mode_capabilities(stale))


def test_show_is_one_task_review_only_and_never_player_or_acceptance_evidence(tmp_path: Path) -> None:
    controller = StardewCompanionController(save_identity(tmp_path))
    attempt = controller.start_show(
        observation(),
        input_driver=InputKind.KEYBOARD,
        expires_at="2099-08-22T12:00:00+00:00",
    )
    assert attempt.mode is StardewMode.SHOW
    assert attempt.review_only
    assert not attempt.player_completion
    assert not attempt.authoritative_evidence
    assert not attempt.owner_acceptance
    with pytest.raises(StardewCompanionError, match="fresh disposable copy"):
        controller.reclaim(driver([]))
        controller.start_show(
            observation("second-show"),
            input_driver=InputKind.KEYBOARD,
            expires_at="2099-08-22T12:00:00+00:00",
        )


def test_do_authorization_binds_exact_live_session_and_revalidates_each_input(tmp_path: Path) -> None:
    events: list[str] = []
    controller = StardewCompanionController(save_identity(tmp_path))
    initial = observation()
    authorization = controller.authorize_do(
        initial,
        owner_confirmation=True,
        input_driver=InputKind.KEYBOARD,
        expires_at="2099-08-22T12:00:00+00:00",
    )
    assert authorization.observation_id == initial.observation_id
    assert authorization.copied_save_nonce == controller.save.nonce
    assert authorization.process_started_at == initial.window.process_started_at
    assert authorization.window_id == initial.window.window_id
    after = observation(
        "observation-2", watered=(True, True), can_units=39, tool_uses=1, energy=268
    )
    result = controller.perform_input(
        InputCommand(InputKind.KEYBOARD, "x", "press", purpose="water_crop"),
        initial,
        driver(events),
        lambda: after,
    )
    assert result is after
    assert controller.operator.ledger is not None
    assert controller.operator.ledger.watered_count == 2
    assert controller.active_attempt is not None
    assert controller.active_attempt.inputs[0].actor == "agent"


def test_do_rejects_stale_live_observation_and_neutralizes_before_failure(tmp_path: Path) -> None:
    events: list[str] = []
    controller = StardewCompanionController(save_identity(tmp_path))
    initial = observation()
    controller.authorize_do(
        initial,
        owner_confirmation=True,
        input_driver=InputKind.KEYBOARD,
        expires_at="2099-08-22T12:00:00+00:00",
    )
    with pytest.raises(StardewCompanionError, match="authorization no longer matches"):
        controller.perform_input(
            InputCommand(InputKind.KEYBOARD, "x", "press", purpose="water_crop"),
            replace(initial, observation_id="unobserved-state"),
            driver(events),
            lambda: observation("never-used"),
        )
    assert "neutralize" in events
    assert controller.active_attempt is not None
    assert controller.active_attempt.status is StardewAttemptStatus.FAILED
    assert controller.active_attempt.first_unmet_requirement


def test_do_preserves_send_and_neutralization_double_failure(tmp_path: Path) -> None:
    controller = StardewCompanionController(save_identity(tmp_path))
    initial = observation()
    controller.authorize_do(
        initial,
        owner_confirmation=True,
        input_driver=InputKind.KEYBOARD,
        expires_at="2099-08-22T12:00:00+00:00",
    )
    broken = OrdinaryInputDriver(
        keyboard=lambda _command: (_ for _ in ()).throw(RuntimeError("send lost")),
        neutralizer=lambda: (_ for _ in ()).throw(OSError("neutral lost")),
    )

    with pytest.raises(StardewAdapterError, match=FailureCode.INPUT_REJECTED.value):
        controller.perform_input(
            InputCommand(InputKind.KEYBOARD, "w", "press", purpose="navigate"),
            initial,
            broken,
            lambda: observation("never-used"),
        )

    attempt = controller.active_attempt
    assert attempt is not None and attempt.status is StardewAttemptStatus.FAILED
    assert not attempt.input_neutralized and not attempt.player_ownership_restored
    assert "send lost" in (attempt.first_unmet_requirement or "")
    assert "neutral lost" in (attempt.first_unmet_requirement or "")


@pytest.mark.parametrize(
    "phase",
    ["authorized", "navigation", "watering", "refill", "return", "completion_pending"],
)
def test_reclaim_neutralizes_invalidates_epoch_and_preserves_partial_attempt(
    tmp_path: Path, phase: str
) -> None:
    events: list[str] = []
    controller = StardewCompanionController(save_identity(tmp_path, phase))
    controller.authorize_do(
        observation(),
        owner_confirmation=True,
        input_driver=InputKind.KEYBOARD,
        expires_at="2099-08-22T12:00:00+00:00",
    )
    attempt = controller.reclaim(driver(events), reason=f"reclaim during {phase}")
    assert events[0] == "neutralize"
    assert attempt.status is StardewAttemptStatus.RECLAIMED
    assert attempt.input_neutralized and attempt.player_ownership_restored
    assert controller.authorization is None
    assert controller.operator.epoch is None
    assert controller.operator.owner is InputOwner.PLAYER


@pytest.mark.parametrize(
    ("reason", "code"),
    [
        ("show timeout", None),
        ("owner cancellation", None),
        ("process lost", FailureCode.PROCESS_LOSS),
        ("window lost", FailureCode.WINDOW_LOSS),
        ("ordinary input driver lost", FailureCode.INPUT_REJECTED),
        ("ownership became ambiguous", FailureCode.AMBIGUOUS_OWNERSHIP),
    ],
)
def test_every_terminal_stop_neutralizes_and_returns_player(
    tmp_path: Path, reason: str, code: FailureCode | None
) -> None:
    events: list[str] = []
    controller = StardewCompanionController(save_identity(tmp_path, reason.replace(" ", "-")))
    controller.start_show(
        observation(),
        input_driver=InputKind.KEYBOARD,
        expires_at="2099-08-22T12:00:00+00:00",
    )
    attempt = controller.stop_active(driver(events), reason=reason, failure_code=code)
    assert "neutralize" in events
    assert attempt.input_neutralized and attempt.player_ownership_restored
    assert attempt.stop_reason
    assert controller.authorization is None


def test_unverifiable_neutralization_reports_no_player_handback(tmp_path: Path) -> None:
    controller = StardewCompanionController(save_identity(tmp_path))
    controller.authorize_do(
        observation(),
        owner_confirmation=True,
        input_driver=InputKind.KEYBOARD,
        expires_at="2099-08-22T12:00:00+00:00",
    )
    broken = OrdinaryInputDriver(
        keyboard=lambda _command: None,
        neutralizer=lambda: (_ for _ in ()).throw(RuntimeError("driver lost")),
    )
    attempt = controller.reclaim(broken)
    assert attempt.status is StardewAttemptStatus.FAILED
    assert not attempt.input_neutralized
    assert not attempt.player_ownership_restored
    assert controller.operator.owner is InputOwner.NONE


@pytest.mark.parametrize(
    "purpose",
    ["purchase", "sell", "discard", "trash", "gift", "dialogue", "story", "sleep", "save overwrite"],
)
def test_stardew_protected_actions_fail_closed(tmp_path: Path, purpose: str) -> None:
    events: list[str] = []
    controller = StardewCompanionController(save_identity(tmp_path, purpose.replace(" ", "-")))
    initial = observation()
    controller.authorize_do(
        initial,
        owner_confirmation=True,
        input_driver=InputKind.KEYBOARD,
        expires_at="2099-08-22T12:00:00+00:00",
    )
    with pytest.raises(StardewCompanionError, match="protected action"):
        controller.perform_input(
            InputCommand(InputKind.KEYBOARD, "x", purpose, purpose="water_crop"),
            initial,
            driver(events),
            lambda: observation("after-protected"),
        )
    assert "neutralize" in events
    assert controller.operator.owner is InputOwner.PLAYER


def test_reset_creates_fresh_copy_preserves_primary_and_invalidates_all_mode_state(tmp_path: Path) -> None:
    primary = tmp_path / "primary-save"
    primary.mkdir()
    (primary / "Farm_123").write_text("primary", encoding="utf-8")
    manager = DisposableSaveManager()
    original = manager.create(primary, tmp_path / "attempt-1" / "Farm_123")
    controller = StardewCompanionController(original, manager=manager)
    initial = replace(
        observation(), save_tree_sha256=original.disposable_tree_sha256
    )
    controller.authorize_do(
        initial,
        owner_confirmation=True,
        input_driver=InputKind.KEYBOARD,
        expires_at="2099-08-22T12:00:00+00:00",
    )
    replacement = controller.reset_disposable(
        tmp_path / "attempt-2" / "Farm_123", driver=driver([])
    )
    assert replacement.nonce != original.nonce
    assert Path(original.disposable_real_path).is_dir()
    assert manager.verify_primary_unchanged(original)
    assert manager.verify_primary_unchanged(replacement)
    assert controller.authorization is None
    assert controller.last_tell_card is None
    assert controller.reset_status == "fresh_attempt_ready_previous_attempt_preserved"
    assert controller.attempts[0].status is StardewAttemptStatus.INVALIDATED_BY_RESET
    assert controller.attempts[0].invalidated_by_reset
    with pytest.raises(StardewCompanionError, match="no active"):
        controller.perform_input(
            InputCommand(InputKind.KEYBOARD, "x", "press", purpose="water_crop"),
            initial,
            driver([]),
            lambda: initial,
        )


def test_completion_requires_exact_crops_resources_position_primary_and_hashed_evidence(tmp_path: Path) -> None:
    primary = tmp_path / "primary-save"
    primary.mkdir()
    (primary / "Farm_123").write_text("primary", encoding="utf-8")
    manager = DisposableSaveManager()
    identity = manager.create(primary, tmp_path / "attempt" / "Farm_123")
    controller = StardewCompanionController(identity, manager=manager)
    initial = replace(observation(), save_tree_sha256=identity.disposable_tree_sha256)
    controller.authorize_do(
        initial,
        owner_confirmation=True,
        input_driver=InputKind.KEYBOARD,
        expires_at="2099-08-22T12:00:00+00:00",
    )
    after_water = replace(
        observation("after-water", watered=(True, True), can_units=39, tool_uses=1, energy=268),
        save_tree_sha256=identity.disposable_tree_sha256,
    )
    io = driver([])
    controller.perform_input(
        InputCommand(InputKind.KEYBOARD, "x", "press", purpose="water_crop"),
        initial,
        io,
        lambda: after_water,
    )
    final = replace(
        observation("at-entrance", watered=(True, True), can_units=39, tool_uses=1, energy=268, at_entrance=True),
        save_tree_sha256=identity.disposable_tree_sha256,
    )
    controller.perform_input(
        InputCommand(InputKind.KEYBOARD, "w", "press", purpose="return_to_entrance"),
        after_water,
        io,
        lambda: final,
    )
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "report.json").write_text("{}", encoding="utf-8")
    attempt = controller.complete(
        final, io, evidence_root=evidence, required_evidence=("report.json",)
    )
    assert attempt.status is StardewAttemptStatus.COMPLETED
    assert attempt.primary_save_unchanged
    assert attempt.evidence_hashes["report.json"]
    assert attempt.input_neutralized and attempt.player_ownership_restored
    assert not attempt.owner_acceptance
