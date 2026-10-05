"""Synthetic cave contracts only; these do not qualify a native cave route."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest
from PIL import Image

from smb3_agent.stardew_cave import (
    CaveRoute,
    CaveNavigator,
    proposal,
    resolve_destination,
)
from smb3_agent.stardew_adapter import OrdinaryInputDriver, InputKind
from smb3_agent.conversation_service import StardewConversationService
from test_gc3_inspection import screen_at
from test_gc3_planting import PassiveRuntime
from test_stardew_conversation import request
from test_stardew_runtime import configured


def route(tmp_path):
    image = tmp_path / "reference.png"
    Image.new("RGB", (100, 100)).save(image)
    record = tmp_path / "qualification.json"
    record.write_text('{"evidence_class":"synthetic-test"}')
    patch = {
        "image": str(image),
        "reference_box": [20, 20, 25, 25],
        "world_origin": [20, 20],
    }
    config = {
        "schema": "stardew-cave-route/v1",
        "profile_id": "test",
        "destination": "farm-cave",
        "classification": "actual_live",  # Exercising validation, never a registered live profile.
        "qualified_roles": [
            "approach",
            "return",
            "exterior",
            "corridor",
            "resources",
            "handback",
        ],
        "poses": {"home": [0, 0], "turn": [0, 48], "entrance": [48, 48]},
        "edges": [["home", "turn"], ["turn", "entrance"]],
        "return_pose": "home",
        "qualification_record": str(record),
        "exterior": patch,
        "edge_records": [
            {
                "edge": edge,
                "approach": str(record),
                "return": str(record),
                "patches": [patch],
            }
            for edge in [["home", "turn"], ["turn", "entrance"]]
        ],
        "evidence_hashes": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (image, record)
        },
    }
    manifest = tmp_path / "route.json"
    manifest.write_text(json.dumps(config))
    return CaveRoute(manifest, profile_id="test")


def ready(tmp_path):
    runtime, _, state, commands = configured(tmp_path)
    state[0] = replace(state[0], position=screen_at(0, 0, True).position)
    runtime._cave_route = route(tmp_path)

    def emit(command):
        commands.append(command)
        p = state[0].position
        dx, dy = {"s": (0, 1), "w": (0, -1), "a": (-1, 0), "d": (1, 0)}[command.control]
        distance = min(10, command.duration_ms * 0.2)
        x, y = p.world_pixel_x + dx * distance, p.world_pixel_y + dy * distance
        state[0] = replace(
            state[0], position=screen_at(x, y, max(abs(x), abs(y)) <= 7).position
        )

    runtime.driver = OrdinaryInputDriver(keyboard=emit, neutralizer=lambda: None)
    runtime.driver.arm = lambda: None
    plan = runtime.propose_cave("Explore Farm Cave", "chat")
    runtime.review(plan)
    return runtime, state, commands, plan


def run(runtime, predicate):
    for _ in range(100):
        runtime.tick()
        if predicate():
            return
    pytest.fail("bounded cave loop did not reach expected state")


@pytest.mark.parametrize(
    "text,previous,expected",
    [
        ("Explore a cave", None, None),
        ("that cave", None, None),
        ("Farm Cave", None, "farm-cave"),
        ("the farm one", "farm-cave", "farm-cave"),
        ("that cave", "farm-cave", "farm-cave"),
        ("explore the Mines", "farm-cave", None),
        ("Skull cavern", None, None),
        ("return home", "farm-cave", "farm-cave"),
    ],
)
def test_resolution(text, previous, expected):
    assert resolve_destination(text, previous)[0] == expected


def test_reviewed_route_limits_and_start_outside_coverage(tmp_path):
    runtime, state, _, plan = ready(tmp_path)
    assert plan.actions[0].parameters["approach"] == ["home", "turn", "entrance"]
    assert plan.actions[0].parameters["return"] == ["entrance", "turn", "home"]
    assert (
        plan.effective_boundary == "exterior_only"
        and plan.resource_limits["tool_uses"] == 0
    )
    assert "hazards remain unknown" in plan.fallback_explanation
    assert not plan.authorization_scope["granted"]
    with pytest.raises(ValueError, match="outside"):
        proposal(
            replace(state[0], position=screen_at(100, 100).position),
            runtime._cave_route,
            "Farm Cave",
            "chat",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("effective_boundary", "interior"),
        ("stop_point", "cave"),
        ("resource_limits", {"maximum_seconds": 900}),
        ("requested_objective", "Mine resources"),
    ],
)
def test_tampered_review_cannot_authorize(tmp_path, field, value):
    runtime, _, commands, plan = ready(tmp_path)
    bad = replace(plan, **{field: value})
    runtime.review(bad)
    with pytest.raises(ValueError, match="scope"):
        runtime.start(bad, background=False)
    assert not commands and runtime.controller.authorization is None


def test_complete_round_trip_preserves_resources_and_distinct_gates(tmp_path):
    runtime, state, commands, plan = ready(tmp_path)
    runtime.start(plan, background=False)
    run(runtime, lambda: runtime.status != "running")
    result = runtime.cave_result
    assert result["status"] == "completed", runtime.reason
    assert (
        result["arrival_observation"]
        and result["return_observation"]
        and result["handback_confirmed"]
    )
    assert (
        result["arrival_observation"]["observation_id"]
        != result["findings"]["observation"]["observation_id"]
    )
    assert (
        result["findings"]["interior_access"] == "unknown"
        and result["findings"]["hazards"] == "unknown"
    )
    assert result["findings"]["observation"]["image"].startswith(
        "data:image/png;base64,"
    )
    assert all(
        c.kind is InputKind.KEYBOARD and c.purpose == "navigate" for c in commands
    )
    assert (
        state[0].energy == 20
        and state[0].tool.watering_can_units == 5
        and not state[0].crops[0].watered
    )


def test_stop_preserves_findings_then_new_approved_return_only(tmp_path):
    runtime, _, commands, plan = ready(tmp_path)
    runtime.start(plan, background=False)
    run(runtime, lambda: runtime.cave_result["findings"] is not None)
    findings = runtime.cave_result["findings"]
    runtime.control("stop")
    count = len(commands)
    runtime.tick()
    assert len(commands) == count and runtime.cave_result["handback_confirmed"]
    assert runtime.cave_result["return_observation"] is None
    with pytest.raises(ValueError, match="exact reviewed"):
        runtime.start(plan, background=False)
    revised = runtime.propose_cave("return home", "chat", return_only=True)
    runtime.review(revised)
    runtime.start(revised, background=False)
    run(runtime, lambda: runtime.status != "running")
    assert (
        runtime.cave_result["status"] == "completed"
        and runtime.cave_result["findings"] == findings
    )


def test_cancel_during_capture_preserves_arrival_without_findings(tmp_path):
    runtime, state, commands, plan = ready(tmp_path)
    runtime.start(plan, background=False)
    state[0] = replace(state[0], position=screen_at(48, 48).position)
    runtime.screen = state[0]
    runtime._cave_navigation._last_node = "entrance"
    original = runtime.observer
    calls = [0]

    def capture():
        calls[0] += 1
        if calls[0] == 2:
            runtime.control("stop")
        return original()

    runtime.observer = capture
    runtime.tick()
    assert (
        runtime.cave_result["arrival_observation"]
        and not runtime.cave_result["findings"]
    )
    assert not commands and runtime.snapshot()["handback_confirmed"]


@pytest.mark.parametrize(
    "change",
    [
        {"session_nonce": "other"},
        {"observation_id": "baseline"},
        {
            "observed_at": (
                datetime.now(timezone.utc) - timedelta(seconds=10)
            ).isoformat()
        },
    ],
)
def test_fresh_findings_guard(tmp_path, change):
    runtime, state, _, _ = ready(tmp_path)
    screen = (
        replace(
            state[0],
            position=screen_at(48, 48).position,
            observation_id="fresh",
            **change,
        )
        if "observation_id" not in change
        else replace(state[0], position=screen_at(48, 48).position, **change)
    )
    with pytest.raises(ValueError, match="fresh"):
        runtime._cave_route.findings(
            screen, session_id="session", baseline_id="baseline"
        )


def test_unknown_exterior_and_changed_corridor(tmp_path):
    runtime, state, commands, plan = ready(tmp_path)
    runtime._cave_route.config["exterior"] = {
        **runtime._cave_route.config["exterior"],
        "world_origin": [50, 50],
    }
    # Bind this separate synthetic calibration before exercising unknown appearance.
    runtime._cave_route.path.write_text(json.dumps(runtime._cave_route.config))
    runtime._cave_route.raw = runtime._cave_route.path.read_bytes()
    image = Image.open(state[0].screenshot_references[0])
    image.putpixel((50, 50), (255, 0, 0))
    image.save(state[0].screenshot_references[0])
    screen = replace(
        state[0], position=screen_at(48, 48).position, observation_id="fresh"
    )
    assert (
        runtime._cave_route.findings(screen, session_id="session", baseline_id="old")[
            "entrance"
        ]
        == "unknown"
    )
    image.putpixel((20, 20), (255, 0, 0))
    image.save(state[0].screenshot_references[0])
    with pytest.raises(ValueError, match="hidden or changed"):
        runtime._cave_route.validate_view(state[0])
    assert not commands


def test_manifest_and_evidence_mutation_refuse(tmp_path):
    calibrated = route(tmp_path)
    calibrated.path.write_text("{}")
    with pytest.raises(ValueError, match="changed"):
        calibrated.check()


def test_cave_navigation_stalls_and_has_no_interior_step(tmp_path):
    nav = CaveNavigator(route(tmp_path).navigator)
    with pytest.raises(ValueError, match="no observed progress"):
        for _ in range(6):
            nav.next_inspection_command(screen_at(0, 0, True))
    nav = CaveNavigator(route(tmp_path).navigator)
    nav._last_node = "entrance"
    assert nav.next_inspection_command(screen_at(48, 48)) == (None, "observe")


class CaveRuntime(PassiveRuntime):
    def propose_cave(self, *args, **kwargs):
        raise ValueError(
            "Farm Cave route is not qualified. Use fresh Day 2 setup; separate approach verification required."
        )


def test_conversational_ambiguity_refusal_and_saved_incomplete_return(tmp_path):
    runtime = CaveRuntime()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    first = request(service, "Explore a cave")
    assert first["plan"] is None and "Which cave" in first["messages"][-1]["text"]
    second = request(service, "Farm Cave")
    assert second["plan"] is None and "not qualified" in second["messages"][-1]["text"]
    with pytest.raises(ValueError, match="Approval"):
        request(service, "yes")
    runtime.state["cave_result"] = {
        "status": "running",
        "plan": {"original_request": "Farm Cave"},
        "arrival_observation": {"observation_id": "arrival"},
        "findings": {
            "message": "Exterior only",
            "observation": {"image": "retained-image"},
        },
        "return_observation": None,
        "handback_confirmed": False,
    }
    service.snapshot()
    reopened = StardewConversationService(
        runtime=CaveRuntime(), artifacts_root=tmp_path
    ).snapshot()
    assert (
        reopened["cave_result"]["historical"]
        and reopened["cave_result"]["status"] == "interrupted"
    )
    assert (
        reopened["cave_result"]["findings"]["observation"]["image"] == "retained-image"
    )
    assert reopened["plan"] is None and not reopened["reviewed"]


def test_expired_cave_authority_stops_without_pulse(tmp_path):
    runtime, _, commands, plan = ready(tmp_path)
    runtime.start(plan, background=False)
    runtime.controller.authorization = replace(
        runtime.controller.authorization,
        expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
    )
    runtime.tick()
    assert not commands and runtime.cave_result["status"] == "stopped"
    assert (
        runtime.cave_result["handback_confirmed"]
        and runtime.cave_result["return_observation"] is None
    )


def test_discussion_cancels_authority_and_plan_then_reopened_completed_result(tmp_path):
    runtime, _, commands, plan = ready(tmp_path)
    service = StardewConversationService(
        runtime=runtime, artifacts_root=tmp_path / "conversation"
    )
    service._plan = plan.to_dict()
    runtime.start(plan, background=False)
    run(runtime, lambda: runtime.cave_result["findings"] is not None)
    count = len(commands)
    request(service, "What did you find?")
    runtime.tick()
    assert len(commands) == count and runtime.controller.authorization is None
    assert service.snapshot()["plan"] is None and runtime.cave_result["findings"]
    revised = runtime.propose_cave("return home", "chat", return_only=True)
    runtime.review(revised)
    runtime.start(revised, background=False)
    run(runtime, lambda: runtime.status != "running")
    service.snapshot()
    reopened = StardewConversationService(
        runtime=CaveRuntime(), artifacts_root=tmp_path / "conversation"
    ).snapshot()
    assert (
        reopened["cave_result"]["status"] == "completed"
        and reopened["cave_result"]["historical"]
    )
    assert reopened["cave_result"]["plan"]["original_request"] == "return home"
    assert reopened["cave_result"]["initial_request"] == "Explore Farm Cave"
    assert not reopened["reviewed"] and reopened["plan"] is None


def test_missing_return_evidence_and_changed_file_refuse(tmp_path):
    calibrated = route(tmp_path)
    c = json.loads(calibrated.raw)
    del c["edge_records"][0]["return"]
    calibrated.path.write_text(json.dumps(c))
    with pytest.raises(ValueError, match="approach/return"):
        CaveRoute(calibrated.path, profile_id="test")
    calibrated = route(tmp_path)
    (tmp_path / "qualification.json").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        calibrated.check()


def test_entrance_capture_cannot_predate_arrival(tmp_path):
    runtime, state, _, _ = ready(tmp_path)
    screen = replace(
        state[0], position=screen_at(48, 48).position, observation_id="fresh"
    )
    with pytest.raises(ValueError, match="predates"):
        runtime._cave_route.findings(
            screen,
            session_id="session",
            baseline_id="arrival",
            baseline_time=(
                datetime.now(timezone.utc) + timedelta(seconds=1)
            ).isoformat(),
        )


def test_interior_scene_refuses_even_at_matching_geometry(tmp_path):
    runtime, state, commands, _ = ready(tmp_path)
    screen = replace(state[0], position=replace(state[0].position, location="FarmCave"))
    with pytest.raises(ValueError, match="exterior only"):
        runtime._cave_route.validate_view(screen)
    assert not commands


def test_urgent_stop_is_not_consumed_by_pending_clarification(tmp_path):
    runtime = CaveRuntime()
    service = StardewConversationService(runtime=runtime, artifacts_root=tmp_path)
    request(service, "Explore a cave")
    state = request(service, "stop")
    assert state["plan"] is None and not service._cave_pending
    assert ("stop",) in runtime.calls


def navigation_screen(screen, digest, *, hidden=True):
    from smb3_agent.stardew_cave import NavigationCoverage

    crops = tuple(
        replace(
            c,
            occluded=hidden,
            confidence=0 if hidden else 1,
            watered=False if hidden else c.watered,
        )
        for c in screen.crops
    )
    ids = tuple(c.crop_id for c in crops if c.occluded)
    return replace(
        screen,
        observation_id="navigation-" + screen.observation_id,
        crops=crops,
        scene_complete=not hidden,
        unknown_regions=tuple("navigation-hidden:" + k for k in ids),
        navigation_coverage=NavigationCoverage(digest, screen, ids),
    )


@pytest.mark.parametrize("distance,covered,accepted", [(51, True, True), (51, False, False), (97, True, False)])
def test_longer_cave_pulses_require_matching_route_coverage(tmp_path, distance, covered, accepted):
    from smb3_agent.stardew_adapter import InputCommand
    from smb3_agent.stardew_companion import StardewCompanionController
    _, state, _, _ = ready(tmp_path)
    before = state[0]
    after = replace(before, position=screen_at(distance, 0, False).position)
    if covered:
        before = navigation_screen(before, "qualified-route")
        after = navigation_screen(after, "qualified-route")
    command = InputCommand(InputKind.KEYBOARD, "d", "press", 200, purpose="navigate")
    if accepted:
        StardewCompanionController._verify_postcondition(command, before, after)
    else:
        with pytest.raises(ValueError, match="movement stalled"):
            StardewCompanionController._verify_postcondition(command, before, after)


def test_canceled_cave_resume_cannot_emit_navigation(tmp_path):
    runtime, state, commands, plan = ready(tmp_path)
    runtime.start(plan, background=False)
    def canceled():
        runtime.control("stop")
        runtime.require_authority()
    runtime._cave_resume_clock = canceled
    runtime.tick()
    assert not commands and runtime.snapshot()["handback_confirmed"]


def test_navigation_history_retains_identity_without_fresh_crop_claim(tmp_path):
    runtime, state, _, _ = ready(tmp_path)
    partial = navigation_screen(state[0], runtime._cave_route.digest)
    partial.validate(partial.save_tree_sha256)
    assert not partial.scene_complete and partial.crops[0].confidence == 0
    assert partial.crops[0].evidence_reference == state[0].crops[0].evidence_reference
    runtime._cave_route.validate_view(partial)
    assert runtime._task_unchanged(state[0], partial)
    assert runtime._task_unchanged(partial, state[0])


@pytest.mark.parametrize(
    "mutation", ["session", "resource", "identity", "labels", "freshness", "route"]
)
def test_navigation_coverage_rejects_reconciliation_changes(tmp_path, mutation):
    runtime, state, _, _ = ready(tmp_path)
    partial = navigation_screen(state[0], runtime._cave_route.digest)
    if mutation == "session":
        partial = replace(partial, session_nonce="other")
    if mutation == "resource":
        partial = replace(partial, energy=partial.energy - 1)
    if mutation == "identity":
        partial = replace(partial, crops=())
    if mutation == "labels":
        partial = replace(partial, unknown_regions=())
    if mutation == "freshness":
        partial = replace(partial, crops=(replace(partial.crops[0], confidence=1),))
    if mutation == "route":
        partial = replace(
            partial,
            navigation_coverage=replace(
                partial.navigation_coverage, route_digest="f" * 64
            ),
        )
    with pytest.raises(ValueError):
        partial.validate(partial.save_tree_sha256)
        runtime._cave_route.validate_view(partial)


def test_navigation_partial_view_cannot_use_tools(tmp_path):
    from smb3_agent.stardew_adapter import InputCommand

    runtime, state, _, plan = ready(tmp_path)
    runtime.start(plan, background=False)
    partial = navigation_screen(state[0], runtime._cave_route.digest)
    with pytest.raises(ValueError, match="cardinal movement only"):
        runtime.controller.operator.validate_input(
            InputCommand(
                InputKind.MOUSE, "left_button", "click", 40, purpose="water_crop"
            ),
            partial,
        )


def pixel_navigation(tmp_path):
    """Generated pixels exercise coverage mechanics, never route qualification."""
    from types import SimpleNamespace
    from PIL import ImageDraw
    from smb3_agent.stardew_cave import CavePerception
    from smb3_agent.stardew_farm_vision import PreparedFarmPixelProfile
    from smb3_agent.stardew_perception import CameraAlignment

    runtime, state, _, _ = ready(tmp_path)
    reference = Image.new("RGB", (1512, 949))
    a = Image.new("RGB", (12, 12), (19, 73, 31))
    b = Image.new("RGB", (12, 12), (193, 71, 17))
    ImageDraw.Draw(a).rectangle((2, 3, 6, 9), fill=(145, 27, 114))
    ImageDraw.Draw(b).rectangle((3, 2, 8, 7), fill=(115, 137, 179))
    reference.paste(a, (100, 100))
    reference.paste(b, (350, 30))
    path = tmp_path / "camera-reference.png"
    reference.save(path)
    profile = PreparedFarmPixelProfile.__new__(PreparedFarmPixelProfile)
    profile.viewport_size = (1512, 949)
    profile.origin_reference = (768, 456)
    profile.anchor_box = (100, 100, 112, 112)
    profile.anchor = CameraAlignment.calibrate(a)
    profile.tool_box = (0, 0, 5, 5)
    profile.tool_template = SimpleNamespace(matches=lambda _: True)
    profile.energy = SimpleNamespace(recognize=lambda _: 20)
    profile.water = SimpleNamespace(recognize=lambda _: 5)
    baseline = replace(
        state[0],
        energy=20,
        position=screen_at(0, 0, True).position,
        window=replace(state[0].window, bounds=(0, 0, 1512, 949)),
    )
    route = SimpleNamespace(
        digest="a" * 64,
        check=lambda: None,
        validate_view=lambda _: None,
        config={
            "camera_anchors": [
                {
                    "image": str(path),
                    "reference_box": [350, 30, 362, 42],
                    "origin_reference": [768, 456],
                }
            ]
        },
    )
    image = Image.new("RGB", (1512, 949))
    image.paste(b, (1282, 284))  # camera origin (1700,710); farmhouse is off-screen
    draw = ImageDraw.Draw(image)
    draw.rectangle((752, 440, 759, 446), fill=(43, 66, 146))
    draw.rectangle((752, 447, 759, 469), fill=(62, 25, 5))
    current = tmp_path / "camera-current.png"
    image.save(current)
    save = SimpleNamespace(disposable_tree_sha256="sha")
    return (
        CavePerception(profile, route, baseline),
        image,
        current,
        baseline.window,
        save,
    )


def test_second_camera_anchor_keeps_offscreen_crops_historical(tmp_path):
    observer, image, path, window, save = pixel_navigation(tmp_path)
    result = observer.recognize(path, window, save)
    assert result.position.camera_origin_x == 1700
    assert result.position.camera_origin_y == 710
    assert result.position.world_pixel_x == -944.5
    assert not result.scene_complete and result.crops[0].occluded
    assert (
        result.crops[0].evidence_reference
        == observer.baseline.crops[0].evidence_reference
    )
    assert result.screenshot_references == (str(path),)
    assert result.navigation_coverage.baseline is observer.baseline


@pytest.mark.parametrize(
    "failure", ["missing", "conflicting", "avatar", "resource", "visible_crop"]
)
def test_camera_and_current_pixels_refuse_unsupported_navigation(tmp_path, failure):
    from PIL import ImageDraw

    observer, image, path, window, save = pixel_navigation(tmp_path)
    draw = ImageDraw.Draw(image)
    if failure == "missing":
        draw.rectangle((1282, 284, 1293, 295), fill="black")
    elif failure == "conflicting":
        reference = Image.open(observer.route.config["camera_anchors"][0]["image"])
        image.paste(reference.crop((100, 100, 112, 112)), (1038, 354))
    elif failure == "avatar":
        draw.rectangle((752, 440, 759, 469), fill="black")
    elif failure == "resource":
        observer.profile.water.recognize = lambda _: 4
    else:
        # The seed is visibly in-frame at the original camera; unreadable pixels
        # cannot be excused by the historical baseline.
        reference = Image.open(observer.route.config["camera_anchors"][0]["image"])
        image = reference.copy()
        draw = ImageDraw.Draw(image)
        draw.rectangle((764, 440, 771, 446), fill=(43, 66, 146))
        draw.rectangle((764, 447, 771, 469), fill=(62, 25, 5))
    image.save(path)
    with pytest.raises(ValueError):
        observer.recognize(path, window, save)


def test_hidden_baseline_window_and_same_observation_refuse(tmp_path):
    runtime, state, _, _ = ready(tmp_path)
    partial = navigation_screen(state[0], runtime._cave_route.digest)
    for bad in (
        replace(partial, observation_id=state[0].observation_id),
        replace(partial, window=replace(partial.window, process_id=99)),
        replace(partial, scene_complete=True),
    ):
        with pytest.raises(ValueError):
            bad.validate("sha")


def test_cave_partial_coverage_cannot_authorize_other_farm_work(tmp_path):
    runtime, state, commands, plan = ready(tmp_path)
    partial = navigation_screen(state[0], runtime._cave_route.digest)
    runtime.screen = partial
    context = runtime.planning_context()
    assert not context.observation["complete_initial_set"]
    assert context.observation["targets"][0]["watered"] is None
    revised = replace(
        plan, normalized_intent="water", observation_id=partial.observation_id
    )
    runtime.review(revised)
    with pytest.raises(ValueError, match="complete farmhouse coverage"):
        runtime.start(revised, background=False)
    assert not commands


def test_hidden_watered_baseline_survives_cave_stop_without_farm_authority(tmp_path):
    runtime, state, commands, _ = ready(tmp_path)
    baseline = replace(state[0], crops=(replace(state[0].crops[0], watered=True),))
    runtime._cave_baseline = baseline
    state[0] = replace(
        navigation_screen(baseline, runtime._cave_route.digest),
        position=screen_at(48, 48).position,
    )
    runtime._cave_observer = runtime.observer
    runtime.screen = state[0]
    plan = runtime.propose_cave("Farm Cave", "chat")
    runtime.review(plan)
    runtime.start(plan, background=False)
    assert runtime.controller.operator.ledger.confirmed_watered_ids == {"crop"}
    runtime.control("stop", reason="player discussion")
    runtime.tick()
    assert not commands and runtime.controller.authorization is None
    assert runtime.snapshot()["handback_confirmed"]
    assert runtime.cave_result["return_observation"] is None


def test_cave_final_farmhouse_requires_original_crop_baseline(tmp_path):
    runtime, state, commands, plan = ready(tmp_path)
    runtime._cave_baseline = state[0]
    runtime.start(plan, background=False)
    run(runtime, lambda: runtime.cave_result["findings"] is not None)
    # Simulate an unrelated crop change hidden during travel. A complete final
    # farm view must expose it and cannot turn partial return into completion.
    state[0] = replace(state[0], crops=(replace(state[0].crops[0], watered=True),))
    run(runtime, lambda: runtime.status != "running")
    assert runtime.cave_result["status"] != "completed"
    assert runtime.cave_result["return_observation"] is None
    assert runtime.snapshot()["handback_confirmed"]


def test_cave_long_walk_has_own_finite_pulse_budget_without_changing_inspection():
    from smb3_agent.stardew_viewpoint_navigation import ViewpointNavigator
    from smb3_agent.stardew_inspection import InspectionNavigator
    source = ViewpointNavigator({'poses': {'home': [0, 0], 'one': [1500, 0], 'two': [3000, 0], 'entrance': [6000, 0]},
                                 'edges': [['home', 'one'], ['one', 'two'], ['two', 'entrance']], 'watering': {}, 'return_pose': 'home'})
    nav = CaveNavigator(source)
    x = 0
    for _ in range(500):
        command, event = nav.next_inspection_command(screen_at(x, 0, abs(x) <= 7))
        if event == 'observe':
            nav.observed = True
            continue
        if event == 'returned':
            break
        assert 15 <= command.duration_ms <= 250 and command.purpose == 'navigate'
        x += (1 if command.control == 'd' else -1)*command.duration_ms*.28
    else:
        pytest.fail('long route did not complete within finite budget')
    assert nav._total_pulses > 160
    assert InspectionNavigator.maximum_total_pulses == 160
    assert InspectionNavigator.maximum_pulse_ms == 40
    nav._total_pulses = 601
    nav.observed = False
    with pytest.raises(ValueError, match='budget'):
        nav.next_inspection_command(screen_at(200, 0))


def test_avatar_reference_is_hash_bound_to_route_evidence(tmp_path):
    qualified = route(tmp_path)
    config = json.loads(qualified.path.read_text())
    config['avatar_references'] = [{'image': str(tmp_path/'unbound.png'), 'foot_reference': [50, 50]}]
    qualified.path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='evidence'):
        CaveRoute(qualified.path, profile_id='test')


@pytest.mark.parametrize('age,covered,accepted', [(4, True, True), (6, True, False), (4, False, False)])
def test_cave_capture_processing_has_bounded_separate_freshness(tmp_path, age, covered, accepted):
    runtime, state, _, _ = ready(tmp_path)
    baseline = replace(state[0], observed_at=(datetime.now(timezone.utc)-timedelta(seconds=10)).isoformat())
    current = navigation_screen(baseline, runtime._cave_route.digest) if covered else baseline
    current = replace(current, observed_at=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat())
    if accepted:
        runtime._validate(current)
    else:
        with pytest.raises(ValueError, match='stale'):
            runtime._validate(current)


def test_retained_evidence_cache_rehashes_same_size_replacement(tmp_path):
    from smb3_agent.stardew_cave import _current_digest
    import hashlib
    path = tmp_path / "native.png"
    path.write_bytes(b"first")
    assert _current_digest(path) == hashlib.sha256(b"first").hexdigest()
    path.write_bytes(b"other")
    assert _current_digest(path) == hashlib.sha256(b"other").hexdigest()


@pytest.mark.parametrize('x,y,visible', [(1477,753,False), (1381,785,False), (1250,150,False), (1200,700,True), (1510,500,False), (900,825,False)])
def test_hud_and_partial_screen_never_claim_fresh_crop_truth(x, y, visible):
    from smb3_agent.stardew_cave import protected_crop_patch_visible
    assert protected_crop_patch_visible(x, y, (1512,949)) is visible


@pytest.mark.parametrize('mode,accepted', [('one_hidden',True), ('all_hidden',False), ('visible_changed',False)])
def test_corridor_checks_current_visible_references_without_using_offscreen_history(tmp_path, mode, accepted):
    r = route(tmp_path)
    config = json.loads(r.path.read_text())
    first = config['edge_records'][0]['patches'][0]
    second = {**first, 'world_origin':[60,60]}
    if mode == 'one_hidden':
        second['world_origin'] = [500,500]
    elif mode == 'all_hidden':
        first['world_origin'] = [500,500]
        second['world_origin'] = [600,600]
    config['edge_records'][0]['patches'] = [first,second]
    r.path.write_text(json.dumps(config))
    r = CaveRoute(r.path, profile_id='test')
    (tmp_path/'runtime').mkdir()
    runtime, state, _, _ = ready(tmp_path/'runtime')
    source = tmp_path/'current.png'
    image = Image.new('RGB',(100,100))
    if mode == 'visible_changed':
        image.putpixel((60,60),(255,0,0))
    image.save(source)
    s = replace(state[0], screenshot_references=(str(source),), navigation_coverage=None)
    if accepted:
        r.validate_view(s)
    else:
        with pytest.raises(ValueError, match='boundary is hidden or changed'):
            r.validate_view(s)
