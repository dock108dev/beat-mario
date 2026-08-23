from __future__ import annotations

import json
import http.client
import threading
import urllib.parse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from smb3_agent.companion_session import Freshness
from smb3_agent.lab_ui import _new_lab_ui_server, default_companion_session, render_companion_ui
from smb3_agent.live_observation import ConnectionState, LiveSample, LiveSessionAccumulator
from smb3_agent.objective_profiles import (
    CoachingPolicy,
    ComparisonState,
    ObjectiveOutcome,
    ObjectiveProfileError,
    ObjectiveSessionManager,
    ProfileClassification,
    RequirementState,
    choose_suggestion,
    compare_progress,
    compatible_reference,
    evaluate_progress,
    load_profile_catalog,
    load_reference_catalog,
    objective_tell_answer,
    profiles_for_level,
)


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _sample(
    sequence: int,
    *,
    frame: int,
    x: int,
    object_set: int = 1,
    return_map: int = 0,
    lives: int = 4,
    dying: int = 0,
) -> LiveSample:
    return LiveSample(
        session_id="session-1",
        observer_token="token-1",
        sequence=sequence,
        frame=frame,
        observed_at=NOW,
        world=0,
        object_set=object_set,
        map_page=0,
        map_cursor_x=32,
        map_cursor_y=64,
        x=x,
        y=368,
        form=0,
        lives=lives,
        player_is_dying=dying,
        return_map=return_map,
        items=(0,) * 10,
        buttons=("right",),
    )


def _profile(profile_id: str = "smb3.world-1-1.fastest-accepted-clear"):
    return next(item for item in load_profile_catalog() if item.profile_id == profile_id)


def _progress(*samples: LiveSample, fresh: bool = True, profile_id: str = "smb3.world-1-1.fastest-accepted-clear"):
    return evaluate_progress(_profile(profile_id), samples, fresh=fresh)


def _snapshot(tmp_path: Path, *samples: LiveSample, now: datetime = NOW):
    accumulator = LiveSessionAccumulator("session-1", "token-1", tmp_path)
    for sample in samples:
        accumulator.ingest(sample)
    return accumulator.snapshot(now=now)


def test_profile_schema_has_stable_ids_versions_and_distinct_classifications() -> None:
    profiles = load_profile_catalog()

    assert {(item.profile_id, item.version) for item in profiles} == {
        ("smb3.world-1-1.fastest-accepted-clear", 1),
        ("smb3.world-1-1.observable-progress-checklist", 1),
    }
    assert {item.classification for item in profiles} == {
        ProfileClassification.ACCEPTED_AGENT_BEST,
        ProfileClassification.ACCEPTED_SAFE_REFERENCE,
    }
    assert len(ProfileClassification) == 6
    assert all(set(item.outcome_states) == set(ObjectiveOutcome) for item in profiles)


def test_only_supported_level_profile_combinations_are_returned() -> None:
    assert len(profiles_for_level("smb3", "world_1_1")) == 2
    assert profiles_for_level("smb3", "world_3_2") == ()
    assert profiles_for_level("smb3", "world_4_1") == ()


def test_profile_has_exact_start_terminal_required_optional_and_capability_contracts() -> None:
    fastest, checklist = load_profile_catalog()

    assert fastest.start_condition.fact == "level_identity"
    assert fastest.terminal_condition.fact == "course_clear"
    assert [item.requirement_id for item in fastest.required] == ["clear"]
    assert fastest.optional == ()
    assert [item.requirement_id for item in checklist.required] == [
        "midpoint",
        "late_level",
        "clear",
    ]
    assert [item.requirement_id for item in checklist.optional] == ["keep_life"]
    assert fastest.comparison_supported and fastest.hints_supported and fastest.show_supported
    assert not fastest.future_takeover_supported


def test_required_progress_is_recoverable_complete_and_terminal_success() -> None:
    active = _progress(
        _sample(1, frame=100, x=24),
        _sample(2, frame=600, x=1200),
        profile_id="smb3.world-1-1.observable-progress-checklist",
    )
    completed = _progress(
        _sample(1, frame=100, x=24),
        _sample(2, frame=800, x=2100, return_map=1),
        _sample(3, frame=1000, x=8192, object_set=0, return_map=0),
        profile_id="smb3.world-1-1.observable-progress-checklist",
    )

    assert [item.state for item in active.requirements[:3]] == [
        RequirementState.COMPLETE,
        RequirementState.STILL_RECOVERABLE,
        RequirementState.STILL_RECOVERABLE,
    ]
    assert completed.outcome is ObjectiveOutcome.SUCCESS
    assert all(item.state is RequirementState.COMPLETE for item in completed.requirements)


def test_unknown_observation_marks_every_requirement_unverifiable() -> None:
    progress = _progress(_sample(1, frame=100, x=24), fresh=False)

    assert progress.outcome is ObjectiveOutcome.UNVERIFIABLE
    assert {item.state for item in progress.requirements} == {RequirementState.UNVERIFIABLE}


def test_irreversible_boundary_marks_missed_and_stops_obsolete_hint() -> None:
    profile = _profile("smb3.world-1-1.observable-progress-checklist")
    requirement = replace(
        profile.required[0],
        condition=replace(profile.required[0].condition, value=500),
        irreversible_after_x=500,
    )
    profile = replace(profile, required=(requirement, *profile.required[1:]))
    progress = evaluate_progress(profile, (_sample(1, frame=100, x=600),), fresh=True)
    comparison = compare_progress(progress, None, (_sample(1, frame=100, x=600),), fresh=True)

    assert progress.requirements[0].state is RequirementState.COMPLETE
    missed_condition = replace(requirement.condition, value=1000)
    missed_profile = replace(profile, required=(replace(requirement, condition=missed_condition), *profile.required[1:]))
    missed = evaluate_progress(missed_profile, (_sample(1, frame=100, x=600),), fresh=True)
    suggestion, reason = choose_suggestion(missed, comparison, CoachingPolicy.PROACTIVE, requested=False, fresh=True, emitted_keys=set())
    assert missed.requirements[0].state is RequirementState.MISSED
    assert suggestion is None and reason == "requirement_already_impossible"


def test_reference_manifest_reconciles_and_show_is_not_promoted() -> None:
    reference = load_reference_catalog()[0]

    assert reference.elapsed == 2060 == reference.terminal_frame - reference.start_frame
    assert reference.classification is ProfileClassification.ACCEPTED_AGENT_BEST
    assert all("artifacts/show/" not in item for item in reference.provenance)
    assert compatible_reference(_profile()) == reference
    assert compatible_reference(_profile("smb3.world-1-1.observable-progress-checklist")) is None


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"profile_version": 2}, "No compatible"),
        ({"timing_boundary": "wall_clock"}, "No compatible"),
        ({"timing_units": "seconds"}, "No compatible"),
    ],
)
def test_incompatible_reference_is_not_used(change: dict[str, object], reason: str) -> None:
    profile = _profile()
    reference = replace(load_reference_catalog()[0], **change)
    progress = _progress(_sample(1, frame=100, x=24))
    compatible = reference if (
        reference.profile_version == profile.version
        and reference.timing_boundary == profile.timing_boundary
        and reference.timing_units == profile.timing_units
    ) else None

    result = compare_progress(progress, compatible, (_sample(1, frame=100, x=24),), fresh=True)
    assert result.state is ComparisonState.NOT_COMPARABLE
    assert reason in result.reason


@pytest.mark.parametrize(
    ("frame", "expected"),
    [(600, ComparisonState.AHEAD), (705, ComparisonState.TIED), (900, ComparisonState.BEHIND)],
)
def test_comparison_ahead_tied_and_behind_at_compatible_anchor(frame: int, expected: ComparisonState) -> None:
    samples = (_sample(1, frame=100, x=24), _sample(2, frame=frame, x=1100))
    result = compare_progress(_progress(*samples), load_reference_catalog()[0], samples, fresh=True)

    assert result.state is expected
    assert result.anchor_id == "midpoint"


def test_death_difference_is_reported_and_paused_wall_clock_is_ignored() -> None:
    samples = (
        _sample(1, frame=100, x=24, lives=4),
        replace(_sample(2, frame=705, x=1100, lives=3, dying=1), observed_at=NOW + timedelta(minutes=20)),
    )
    result = compare_progress(_progress(*samples), load_reference_catalog()[0], samples, fresh=True)

    assert result.state is ComparisonState.TIED
    assert result.death_delta == 1
    assert result.player_elapsed == 605


def test_stale_or_missing_start_is_not_comparable() -> None:
    samples = (_sample(1, frame=100, x=24),)
    stale = compare_progress(_progress(*samples), load_reference_catalog()[0], samples, fresh=False)
    missing = compare_progress(_progress(fresh=True), load_reference_catalog()[0], (), fresh=True)

    assert stale.state is ComparisonState.NOT_COMPARABLE
    assert missing.state is ComparisonState.NOT_COMPARABLE


def test_fastest_and_full_completion_claims_are_rejected_without_contract() -> None:
    fastest = _profile()
    with pytest.raises(ObjectiveProfileError, match="fastest/best"):
        replace(fastest, classification=ProfileClassification.UNREVIEWED_CANDIDATE).validate()
    with pytest.raises(ObjectiveProfileError, match="100%"):
        replace(fastest, name="World 1-1 100%").validate()


def test_coaching_policies_deduplicate_and_state_change_allows_new_hint() -> None:
    progress = _progress(
        _sample(1, frame=100, x=24),
        profile_id="smb3.world-1-1.observable-progress-checklist",
    )
    comparison = compare_progress(progress, None, (_sample(1, frame=100, x=24),), fresh=True)
    quiet = choose_suggestion(progress, comparison, CoachingPolicy.QUIET, requested=True, fresh=True, emitted_keys=set())
    on_request_suppressed = choose_suggestion(progress, comparison, CoachingPolicy.ON_REQUEST, requested=False, fresh=True, emitted_keys=set())
    hint, emitted = choose_suggestion(progress, comparison, CoachingPolicy.PROACTIVE, requested=False, fresh=True, emitted_keys=set())
    duplicate = choose_suggestion(progress, comparison, CoachingPolicy.PROACTIVE, requested=False, fresh=True, emitted_keys={hint.deduplication_key})
    advanced = _progress(
        _sample(1, frame=100, x=24),
        _sample(2, frame=700, x=1200),
        profile_id="smb3.world-1-1.observable-progress-checklist",
    )
    next_hint, _ = choose_suggestion(advanced, comparison, CoachingPolicy.PROACTIVE, requested=False, fresh=True, emitted_keys={hint.deduplication_key})

    assert quiet == (None, "quiet_policy")
    assert on_request_suppressed == (None, "not_requested")
    assert hint is not None and emitted == "emitted"
    assert duplicate == (None, "duplicate_without_meaningful_change")
    assert next_hint is not None and next_hint.deduplication_key != hint.deduplication_key


@pytest.mark.parametrize("fresh", [False])
def test_stale_observation_suppresses_advice(fresh: bool) -> None:
    progress = _progress(_sample(1, frame=100, x=24), profile_id="smb3.world-1-1.observable-progress-checklist")
    suggestion, reason = choose_suggestion(progress, compare_progress(progress, None, (), fresh=False), CoachingPolicy.PROACTIVE, requested=False, fresh=fresh, emitted_keys=set())
    assert suggestion is None and reason == "stale_observation"


def test_objective_tell_separates_current_profile_reference_inference_and_unknown() -> None:
    snapshot = _snapshot(Path("/tmp"), _sample(1, frame=100, x=24), _sample(2, frame=900, x=1100))
    manager = ObjectiveSessionManager()
    view = manager.configure(snapshot, _profile().profile_id, "on_request", load_reference_catalog()[0].reference_id)
    answer = objective_tell_answer(view, "Why am I behind?", fresh=True)

    assert "behind" in answer.answer.lower()
    assert answer.current_facts and answer.profile_facts and answer.reference_facts
    assert answer.inferences
    assert not answer.unknowns
    assert "performed" not in answer.answer.lower()
    assert "best achieved" not in answer.answer.lower()
    minimal = objective_tell_answer(view, "What do I still need?", fresh=True, spoiler_level="minimal")
    full = objective_tell_answer(view, "What do I still need?", fresh=True, spoiler_level="full")
    assert minimal.spoiler_level == "minimal" and not minimal.reference_facts
    assert full.spoiler_level == "full" and "Full profile plan" in full.answer


def test_objective_ui_keeps_player_control_show_separate_and_takeover_explicit(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, _sample(1, frame=100, x=24), _sample(2, frame=705, x=1100))
    manager = ObjectiveSessionManager()
    view = manager.configure(snapshot, _profile().profile_id, "proactive", load_reference_catalog()[0].reference_id)
    html = render_companion_ui(default_companion_session(live_snapshot=snapshot), live_snapshot=snapshot, objective_view=view, csrf_token="token")

    for hook in ("objective-profile", "objective-config", "objective-progress", "comparison-result", "coaching-hint", "objective-tell-request"):
        assert f'data-testid="{hook}"' in html
    assert "Player-owned by default" in html
    assert "Show remains a separate review-only process" in html
    assert "captured traces remain non-executable candidates" in html
    assert "overflow-x: hidden" in html
    assert "@media (max-width: 760px)" in html
    assert 'id="live"' in html and 'id="objective"' in html
    assert 'class="objective-controls"' in html
    assert 'data-testid="live-technical-details"' in html
    assert 'data-testid="more-companion-tools"' in html
    assert "More tools and technical evidence" in html
    assert "● Live updates" in html
    assert '<script src="/assets/player-workspace.js" defer></script>' in html


def test_objective_actions_redirect_back_to_the_active_workspace(tmp_path: Path) -> None:
    server = _new_lab_ui_server("127.0.0.1", 0)
    live_manager = getattr(server, "live_observation_manager")
    accumulator = LiveSessionAccumulator("session-1", "token-1", tmp_path)
    accumulator.ingest(replace(_sample(1, frame=100, x=24), observed_at=datetime.now(timezone.utc)))
    live_manager._accumulator = accumulator
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = urllib.parse.urlencode(
            {
                "csrf_token": getattr(server, "csrf_token"),
                "profile_id": _profile().profile_id,
                "coaching_policy": "on_request",
                "reference_id": load_reference_catalog()[0].reference_id,
            }
        )
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request(
            "POST",
            "/objective-config",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = connection.getresponse()
        response.read()
        location = response.getheader("Location")
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 303
    assert location == "/#objective"


def test_live_workspace_endpoint_returns_compact_current_state(tmp_path: Path) -> None:
    server = _new_lab_ui_server("127.0.0.1", 0)
    live_manager = getattr(server, "live_observation_manager")
    accumulator = LiveSessionAccumulator("session-1", "token-1", tmp_path)
    accumulator.ingest(replace(_sample(1, frame=100, x=24), observed_at=datetime.now(timezone.utc)))
    live_manager._accumulator = accumulator
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("GET", "/api/player-workspace")
        response = connection.getresponse()
        html = response.read().decode("utf-8")
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 200
    assert 'id="live"' in html and 'id="objective"' in html
    assert "<html" not in html
    assert "● Live updates" in html


def test_objective_artifacts_reconcile_policy_events_and_zero_agent_input(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, _sample(1, frame=100, x=24), _sample(2, frame=705, x=1100))
    manager = ObjectiveSessionManager()
    manager.configure(snapshot, _profile().profile_id, "on_request", load_reference_catalog()[0].reference_id)
    manager.request_advice(snapshot)
    manager.ask(snapshot, "What do I still need?")
    manager.dismiss(snapshot)
    manager.finalize(snapshot)
    report = json.loads((tmp_path / "objective_reconciliation.json").read_text())
    events = (tmp_path / "objective_events.jsonl").read_text()

    assert report["profile"]["version"] == 1
    assert report["profile_definition"]["required"]
    assert report["reference"]["provenance"]
    assert report["coaching_policy"] == "on_request"
    assert report["agent_input_count"] == 0
    assert report["reconciliation"]["agent_input_zero"] is True
    assert report["reconciliation"]["not_route_reliability"] is True
    for event in ("configuration", "objective_progress", "comparison", "requested_advice", "objective_tell", "dismissed_advice"):
        assert f'"event": "{event}"' in events


def test_unsupported_observation_renders_exact_capability_boundary(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, replace(_sample(1, frame=100, x=24), world=1, object_set=2))
    view = ObjectiveSessionManager().view(snapshot)
    html = render_companion_ui(default_companion_session(live_snapshot=snapshot), live_snapshot=snapshot, objective_view=view)

    assert view.selected is None
    assert "Enter World 1-1 to choose a profile" in html
    assert "Enter World 1-1 to choose a profile" in html
    assert "Why only World 1-1?" in html


def test_quiet_mode_never_emits_unsolicited_hint(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, _sample(1, frame=100, x=24))
    manager = ObjectiveSessionManager()
    view = manager.configure(snapshot, _profile().profile_id, "quiet", None)

    assert view.suggestion is None
    assert view.policy is CoachingPolicy.QUIET
    assert view.suppression_reason == "quiet_policy"
    assert snapshot.agent_input_count == 0
    assert snapshot.freshness is Freshness.FRESH
    assert snapshot.state is ConnectionState.CONNECTED


def test_stale_state_clears_proactive_hint_and_preserves_last_fresh_result(tmp_path: Path) -> None:
    fresh = _snapshot(tmp_path, _sample(1, frame=100, x=24))
    manager = ObjectiveSessionManager()
    view = manager.configure(fresh, _profile().profile_id, "proactive", None)
    assert view.suggestion is not None
    stale = replace(fresh, state=ConnectionState.STOPPED, freshness=Freshness.STALE)

    stopped = manager.view(stale)
    manager.finalize(stale)
    report = json.loads((tmp_path / "objective_reconciliation.json").read_text())

    assert stopped.suggestion is None
    assert stopped.suppression_reason == "stale_observation"
    assert stopped.comparison.state is ComparisonState.NOT_COMPARABLE
    assert report["final_objective_classification"] == "incomplete"
    assert report["post_stop_objective_availability"] == "unverifiable"
