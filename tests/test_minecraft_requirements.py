import json
from pathlib import Path
import pytest

from smb3_agent.minecraft_design import WorldDesign
from smb3_agent.minecraft_build import BuildProject
from smb3_agent.minecraft_requirements import (
    parse_request,
    proposal_schema,
    reconcile,
    checklist,
)
from test_minecraft_build import Bridge, REGION

BRIEFS = json.loads(
    (Path(__file__).parents[1] / "data/minecraft/design-briefs.json").read_text()
)


def proposed(requirements):
    return {
        key: {
            field: (rule["enum"][0] if "enum" in rule else rule["minimum"])
            for field, rule in value["properties"].items()
        }
        for key, value in proposal_schema(requirements)["properties"].items()
    }


def plan(design, text):
    current = design.current()
    parsed = parse_request(text, current)
    assert not parsed["issues"], parsed["issues"]
    assert not [r["issues"] for r in parsed["requirements"] if r["issues"]]
    result = design.begin_requirements(parsed, current["revision"] if current else 0)
    pending = {r["name"] for r in checklist(result) if r["status"] == "pending"}
    requirements = [r for r in parsed["requirements"] if r["name"] in pending]
    for start in range(0, len(requirements), 3):
        batch = requirements[start : start + 3]
        delta = {
            "title": parsed["title"],
            "extent": parsed["extent"],
            "palette": parsed["palette"],
            "reply": "",
            "remove": "",
            "components": reconcile(batch, proposed(batch)),
        }
        result = design.apply(delta, text, design.current()["revision"])
    design.planning_progress(1, 1)
    return design.current()


@pytest.fixture
def design(tmp_path):
    p = BuildProject(tmp_path, "world", REGION, Bridge())
    yield WorldDesign(p)
    p.close()


@pytest.mark.parametrize("scenario", ["island", "town"])
def test_complete_inventory_dimensions_rooms_and_source_quotes(design, scenario):
    fixture = BRIEFS[scenario]
    result = plan(design, fixture["brief"])
    assert result["extent"] == fixture["extent"]
    assert result["planning"]["state"] == "ready"
    assert len(result["components"]) == (19 if scenario == "island" else 13)
    by_name = {c["name"]: c for c in result["components"]}
    for name, expected in fixture["expected"].items():
        for key, value in expected.items():
            assert by_name[name][key] == value, (name, key)
    for r in result["requirements"]:
        quote = r["source"]
        assert fixture["brief"][quote["start"] : quote["end"]] == quote["quote"]
        assert r["source"] == by_name[r["name"]]["requirement_source"]
        assert by_name[r["name"]]["connections"] == r["connections"]
    if scenario == "island":
        assert by_name["Ocean Border"]["constraints"]["border"] == 16
        assert by_name["Woodland"]["constraints"]["count"] == 3
        assert len(by_name["Beach Camp"]["objects"]) == 8
    else:
        assert by_name["Terraces"]["constraints"]["count"] == 3
        assert by_name["Market"]["constraints"]["count"] == 4
        assert len(by_name["Market"]["objects"]) == 8


def test_model_cannot_change_explicit_numbers_or_omit_components(design):
    parsed = parse_request(BRIEFS["town"]["brief"], None)
    rows = parsed["requirements"][:3]
    bad = proposed(rows)
    bad["0"]["width"] = 256
    with pytest.raises(ValueError):
        reconcile(rows, bad)
    bad = proposed(rows)
    bad.pop("1")
    with pytest.raises(ValueError):
        reconcile(rows, bad)


def test_unseen_bridge_greenhouse_and_targeted_edits_preserve_other_places(design):
    before = plan(design, BRIEFS["town"]["brief"])
    after = plan(
        design,
        "Add a third pedestrian bridge 16 by 3, 2 blocks high and a rotated riverside Greenhouse 12 by 10, 6 blocks high; preserve all original buildings.",
    )
    old = {c["name"]: c for c in before["components"]}
    new = {c["name"]: c for c in after["components"]}
    assert all(new[name] == value for name, value in old.items())
    bridges = [c for c in new.values() if c["kind"] == "bridge"]
    assert len(bridges) == 3
    greenhouse = next(c for c in new.values() if "greenhouse" in c["name"].lower())
    assert greenhouse["turn"] == 1
    assert greenhouse["size"] == [12, 10, 6]
    assert greenhouse["connections"] == ["River"]
    rx,rz,rw,rd,*_ = new["River"]["box"]
    bridge = next(c for c in new.values() if c["kind"] == "bridge" and c["name"] not in old)
    bx,bz,bw,bd,*_ = bridge["box"]
    assert bridge["connections"] == ["River"]
    assert bx < rx and bx+bw > rx+rw and rz <= bz and bz+bd <= rz+rd
    gx,gz,gw,gd,*_ = greenhouse["box"]
    assert not (gx < rx+rw and gx+gw > rx and gz < rz+rd and gz+gd > rz)

    edited = plan(
        design, "Make Inn larger inside, 24 by 20. Preserve the rooms and other places."
    )
    edits = {c["name"]: c for c in edited["components"]}
    assert edits["Inn"]["size"][:2] == [24, 20]
    assert edits["Inn"]["rooms"] == old["Inn"]["rooms"]
    assert all(edits[n] == v for n, v in new.items() if n != "Inn")


def test_unknown_and_unsupported_requests_remain_visible(design):
    p = parse_request(
        "Plan a 192 by 192 place.\nAircraft: working aircraft 12 by 12.\nMake it magical in a new unspecified way.",
        None,
    )
    assert p["issues"]
    assert p["requirements"][0]["issues"]
    design.begin_requirements(p, 0)
    design.planning_progress(0, 0)
    assert design.current()["planning"]["state"] == "pending"
    with pytest.raises(ValueError, match="checklist"):
        design.compile_component(1, "Aircraft")


def test_pending_checklist_survives_reopen_without_authority(design):
    p = parse_request(BRIEFS["town"]["brief"], None)
    design.begin_requirements(p, 0)
    reopened = WorldDesign(design.project)
    assert len(reopened.current()["requirements"]) == 13
    assert reopened.current()["components"] == []
    assert reopened.project.state == "idle"


def test_move_selects_subject_not_longer_destination_name(design):
    before = plan(design, BRIEFS["island"]["brief"])
    old = {c["name"]: c for c in before["components"]}
    after = plan(design, "Move Dock nearer West Bay. Keep everything else unchanged.")
    new = {c["name"]: c for c in after["components"]}
    assert new["Dock"]["link"] == "West Bay"
    assert all(new[name] == value for name, value in old.items() if name != "Dock")


def test_conflicting_footprints_and_unrecognized_notes_survive_followup(design):
    parsed = parse_request(
        "Plan a 192 by 192 town.\nMuseum: building 20 by 12 but also 30 by 18.\nInvent something magical.",
        None,
    )
    assert parsed["requirements"][0]["issues"]
    design.begin_requirements(parsed, 0)
    followup = parse_request("Use a natural palette", design.current())
    assert "Invent something magical." in followup["issues"]
    assert followup["requirements"][0]["issues"]


def test_forward_connection_can_be_resolved_by_later_chat(design):
    parsed = parse_request(
        "Plan a 192 by 192 town.\nCamp: pavilion 8 by 6, 4 blocks high. Connects to Museum.",
        None,
    )
    assert parsed["requirements"][0]["issues"]
    design.begin_requirements(parsed, 0)
    final = plan(design, "Museum: building 20 by 12, 8 blocks high.")
    assert final["planning"]["state"] == "ready"
    assert final["components"][0]["connections"] == ["Museum"]


def test_explicit_shape_overrides_place_name(design):
    result = plan(
        design,
        "Plan a 192 by 192 town.\nRiver Valley: terrain 48 by 32, 12 blocks high.\nOld Mill: open pavilion 8 by 6, 4 blocks high.",
    )
    assert [c["kind"] for c in result["components"]] == ["terrain", "pavilion"]


def test_preview_edit_preserves_unresolved_project_notes(design, tmp_path):
    from test_minecraft_chat import Provider, service

    before = plan(design, "Plan a 192 by 192 town.\nCamp: pavilion 8 by 6, 4 blocks high.")
    parsed = parse_request("Invent something magical.", before)
    pending = design.begin_requirements(parsed, before["revision"])
    chat = service(tmp_path / "chat", Provider([]))
    chat.project, chat.designer = design.project, design
    try:
        chat.edit_design_component(
            pending["revision"], "Camp", [10, 8, 4], "pavilion", "south", "shore", 0
        )
        current = design.current()
        assert "Invent something magical." in current["planning"]["issues"]
        assert current["planning"]["state"] != "ready"
        with pytest.raises(ValueError, match="checklist"):
            design.compile_component(current["revision"], "Camp")
    finally:
        chat.project = None
        chat.designer = None
        chat.close()


def test_clarification_resolves_missing_extent_and_places(design):
    incomplete = parse_request('Create a welcoming camp with a warm palette.', None)
    design.begin_requirements(incomplete, 0)
    design.planning_progress(0, 0, state='needs_review')
    corrected = parse_request('Plan a 192 by 192 camp, warm palette.\nGuest Cabin: building 8 by 8, 5 blocks high, center.', design.current())
    assert corrected['extent'] == 192
    assert not corrected['issues']
    assert corrected['requirements'][0]['name'] == 'Guest Cabin'


def test_clarification_does_not_resize_accepted_project(design):
    plan(design, 'Plan a 256 by 256 camp.\nCabin: building 8 by 8, 5 blocks high.')
    corrected = parse_request('Plan a 192 by 192 camp.', design.current())
    assert 'Changing the project extent needs a new project' in corrected['issues']
    assert corrected['extent'] == 256
