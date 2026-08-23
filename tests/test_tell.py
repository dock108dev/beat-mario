from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from smb3_agent.companion_session import Freshness, Observation, ObservationSource, SessionOutcome
from smb3_agent.goals import load_goal_contract, resolve_goal_path
from smb3_agent.tell import (
    ObservedFact,
    SpoilerLevel,
    TellRequest,
    TellValidationError,
    generate_tell_card,
    load_tell_knowledge,
)


CHECKPOINT = "world_8_bowser_castle_finish"


def _request(
    *,
    source: ObservationSource = ObservationSource.ADAPTER,
    spoiler: SpoilerLevel = SpoilerLevel.GUIDED,
    freshness: Freshness = Freshness.FRESH,
    checkpoint_id: str | None = CHECKPOINT,
    facts: tuple[ObservedFact, ...] | None = None,
    protected: tuple[str, ...] = (),
    game_id: str = "smb3",
) -> TellRequest:
    goal = load_goal_contract(resolve_goal_path("world_8_finish_game"))
    observation = Observation(
        checkpoint="Bowser's Castle start",
        checkpoint_id=checkpoint_id,
        source=source,
        game_id=game_id,
        observed_at=datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
        freshness=freshness,
        confidence=0.97,
        evidence_references=("current/frame.png",) if source is ObservationSource.ADAPTER else (),
    )
    return TellRequest(
        game_id="smb3",
        goal=goal,
        observation=observation,
        facts=facts
        if facts is not None
        else (ObservedFact("checkpoint_confirmed", "true", source),),
        spoiler_level=spoiler,
        protected_decisions=protected,
    )


def test_fresh_adapter_observation_produces_grounded_tell_card() -> None:
    card = generate_tell_card(_request())

    assert card.observation_source is ObservationSource.ADAPTER
    assert card.steps
    assert "adapter observed" in card.state_summary.text


def test_player_reported_card_never_claims_adapter_or_game_owned_state() -> None:
    card = generate_tell_card(_request(source=ObservationSource.PLAYER))
    rendered_text = " ".join(
        [card.state_summary.text, *(step.action.text for step in card.steps)]
    ).lower()

    assert card.observation_source is ObservationSource.PLAYER
    assert "player reported" in card.state_summary.text
    assert "adapter observed" not in rendered_text
    assert "game-owned success" not in rendered_text


def test_spoiler_levels_are_bounded_to_one_selected_segment() -> None:
    minimal = generate_tell_card(_request(spoiler=SpoilerLevel.MINIMAL))
    guided = generate_tell_card(_request(spoiler=SpoilerLevel.GUIDED))
    full = generate_tell_card(_request(spoiler=SpoilerLevel.FULL))

    assert len(minimal.steps) == 1
    assert not minimal.risks and not minimal.recovery
    assert len(guided.steps) == 2 and guided.risks and guided.recovery
    assert len(full.steps) == 3
    assert all("World 1" not in step.action.text for step in full.steps)


def test_every_factual_item_has_typed_provenance() -> None:
    card = generate_tell_card(_request(spoiler=SpoilerLevel.FULL))
    grounded = [
        card.state_summary,
        card.objective,
        card.uncertainty,
        card.refresh_requirement,
        *card.risks,
        *card.recovery,
        *(step.action for step in card.steps),
        *(step.expected_cue for step in card.steps),
    ]

    assert all(item.provenance for item in grounded)
    assert all(reference.source_class for item in grounded for reference in item.provenance)


def test_protected_decisions_are_carried_into_card() -> None:
    card = generate_tell_card(_request(protected=("preserve_warp_whistles",)))
    assert card.protected_decisions_honored == ("preserve_warp_whistles",)


def test_protected_action_conflict_fails_closed() -> None:
    request = _request(
        checkpoint_id="world_8_battleships_clear",
        facts=(
            ObservedFact("checkpoint_confirmed", "true", ObservationSource.ADAPTER),
            ObservedFact("p_wing_available", "true", ObservationSource.ADAPTER),
        ),
        protected=("preserve_p_wing",),
    )
    with pytest.raises(TellValidationError, match="protected decision conflicts"):
        generate_tell_card(request)


@pytest.mark.parametrize("freshness", (Freshness.STALE, Freshness.UNKNOWN))
def test_stale_or_unknown_observation_blocks_tell(freshness: Freshness) -> None:
    with pytest.raises(TellValidationError, match="fresh current observation"):
        generate_tell_card(_request(freshness=freshness))


def test_missing_checkpoint_blocks_tell() -> None:
    with pytest.raises(TellValidationError, match="stable checkpoint id"):
        generate_tell_card(_request(checkpoint_id=None))


def test_goal_checkpoint_mismatch_blocks_tell() -> None:
    goal = load_goal_contract(resolve_goal_path("world_8_double_whistle"))
    with pytest.raises(TellValidationError, match="not part of the selected goal"):
        generate_tell_card(replace(_request(), goal=goal))


def test_missing_required_fact_blocks_tell() -> None:
    with pytest.raises(TellValidationError, match="missing required observed fact"):
        generate_tell_card(_request(facts=()))


def test_missing_required_inventory_fact_blocks_dependent_segment() -> None:
    request = _request(checkpoint_id="world_8_battleships_clear")
    with pytest.raises(TellValidationError, match="p_wing_available"):
        generate_tell_card(request)


def test_contradictory_inventory_fact_blocks_dependent_segment() -> None:
    facts = (
        ObservedFact("checkpoint_confirmed", "true", ObservationSource.ADAPTER),
        ObservedFact("p_wing_available", "false", ObservationSource.ADAPTER),
    )
    with pytest.raises(TellValidationError, match="contradicts checkpoint: p_wing_available"):
        generate_tell_card(_request(checkpoint_id="world_8_battleships_clear", facts=facts))


def test_contradictory_fact_blocks_tell() -> None:
    facts = (ObservedFact("checkpoint_confirmed", "false", ObservationSource.ADAPTER),)
    with pytest.raises(TellValidationError, match="contradicts checkpoint"):
        generate_tell_card(_request(facts=facts))


def test_game_identity_mismatch_blocks_tell() -> None:
    with pytest.raises(TellValidationError, match="observation and goal game"):
        generate_tell_card(_request(game_id="not-smb3"))


def test_adapter_observation_requires_current_evidence() -> None:
    request = _request()
    observation = replace(request.observation, evidence_references=())
    with pytest.raises(TellValidationError, match="evidence reference"):
        generate_tell_card(replace(request, observation=observation))


def test_missing_and_orphaned_knowledge_fail_validation(tmp_path: Path) -> None:
    raw = yaml.safe_load(Path("data/tell/mario.yaml").read_text())
    missing = dict(raw)
    missing["records"] = list(raw["records"][:-1])
    missing_path = tmp_path / "missing.yaml"
    missing_path.write_text(yaml.safe_dump(missing, sort_keys=False))
    with pytest.raises(TellValidationError, match="missing"):
        load_tell_knowledge(missing_path)

    orphaned = dict(raw)
    orphaned["records"] = [*raw["records"], {**raw["records"][0], "segment_id": "orphan"}]
    orphaned_path = tmp_path / "orphaned.yaml"
    orphaned_path.write_text(yaml.safe_dump(orphaned, sort_keys=False))
    with pytest.raises(TellValidationError, match="orphaned"):
        load_tell_knowledge(orphaned_path)


def test_duplicate_knowledge_fails_validation(tmp_path: Path) -> None:
    raw = yaml.safe_load(Path("data/tell/mario.yaml").read_text())
    raw["records"].append(dict(raw["records"][0]))
    path = tmp_path / "duplicate.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    with pytest.raises(TellValidationError, match="duplicate"):
        load_tell_knowledge(path)


def test_knowledge_coverage_exactly_matches_supported_segment_scope() -> None:
    records = load_tell_knowledge()
    assert len(records) == 26
    assert set(records) == set(load_goal_contract(resolve_goal_path("world_8_finish_game")).segments)


def test_tell_output_is_structurally_separate_from_session_outcome() -> None:
    card = generate_tell_card(_request())
    assert not isinstance(card, SessionOutcome)
    assert not hasattr(card, "verified_outcome")


def test_tell_copy_never_claims_player_or_companion_execution() -> None:
    card = generate_tell_card(_request(spoiler=SpoilerLevel.FULL))
    copy = " ".join(
        [
            card.state_summary.text,
            card.objective.text,
            card.uncertainty.text,
            *(step.action.text for step in card.steps),
        ]
    ).lower()
    assert "companion completed" not in copy
    assert "you completed" not in copy
    assert "companion performed" not in copy
