import base64
from copy import deepcopy
from io import BytesIO

from PIL import Image
import pytest
from smb3_agent.minecraft_build import BuildProject
from smb3_agent.minecraft_design import WorldDesign
from test_minecraft_build import Bridge, REGION


def delta(name="Camp Pavilion", **changes):
    component = {
        "name": name,
        "kind": "pavilion",
        "size": [6, 5, 4],
        "zone": "south",
        "level": "shore",
        "turn": 0,
        "link": "",
        "detail": "Open timber shelter; decorative seating.",
    }
    component.update(changes)
    return {
        "title": "Coastal project",
        "extent": 256,
        "palette": "warm",
        "reply": "A small camp shelter.",
        "remove": "",
        "components": [component],
    }


@pytest.fixture
def design(tmp_path):
    project = BuildProject(tmp_path, "world", REGION, Bridge())
    yield WorldDesign(project)
    project.close()


def test_versions_persist_and_edits_preserve_other_components(design):
    first = design.apply(delta(), "island brief", 0)
    design.apply(
        delta("Dock", kind="dock", size=[24, 5, 2], zone="east"), "add dock", 1
    )
    before = deepcopy(design.current())
    after = design.apply(delta(size=[8, 7, 4]), "larger inside", 2)
    assert after["brief"] == "island brief"
    assert before["components"][1] == after["components"][1]
    assert after["changed"] == ["Camp Pavilion"]
    assert after["components"][0]["box"][2:4] == [8, 7]
    assert first["components"][0]["size"] == [6, 5, 4]
    restored = WorldDesign(design.project)
    assert restored.snapshot() == design.snapshot()
    assert not design.project.bridge.cells
    with pytest.raises(ValueError, match="changed"):
        design.apply(delta(), "stale", 1)


def test_rotation_and_boundary_validation(design):
    d = design.apply(delta(turn=1), "rotated", 0)
    assert d["components"][0]["box"][2:4] == [5, 6]
    invalid = delta()
    invalid["components"][0]["size"] = [512, 4, 4]
    with pytest.raises(ValueError):
        design.apply(invalid, "invalid", 1)
    assert design.current()["revision"] == 1


def test_selected_preview_uses_existing_transaction_and_reopen_idle(design):
    design.apply(delta(), "camp", 0)
    count = design.compile_component(1, "Camp Pavilion")
    assert count > 0 and not design.project.bridge.cells
    assert design.snapshot()["bound"][0]["revision"] == 1
    assert design.project.run()["state"] == "complete"
    assert len(design.project.bridge.cells) == count
    with pytest.raises(ValueError):
        design.compile_component(0, "Camp Pavilion")


def test_full_plan_is_not_full_write_authority(design):
    design.apply(delta(kind="building", size=[24, 16, 6]), "station", 0)
    with pytest.raises(ValueError, match="planning previews"):
        design.compile_component(1, "Camp Pavilion")
    assert not design.project.bridge.cells


def test_references_scoped_bounded_and_persistent(design):
    image = BytesIO()
    Image.new("RGB", (2, 2)).save(image, format="PNG")
    encoded = base64.b64encode(image.getvalue()).decode()
    key = design.add_reference(
        "roof.png", "Use the shape; synthetic test image", encoded
    )
    assert design.reference(key)[1] == image.getvalue()
    assert (
        WorldDesign(design.project)
        .references()[0]["caption"]
        .startswith("Use the shape")
    )
    with pytest.raises(ValueError, match="already"):
        design.add_reference("again.png", "caption", encoded)
    with pytest.raises(ValueError):
        design.add_reference(
            "bad.png", "caption", base64.b64encode(b"not png").decode()
        )
    with pytest.raises(ValueError):
        design.reference("../other-world")


def test_world_identity_remains_authoritative(design):
    with pytest.raises(ValueError, match="world/region"):
        BuildProject(design.project.root, "different-world", REGION, Bridge())


def test_stop_discards_late_design_result(tmp_path):
    import threading
    from test_minecraft_chat import Provider, service, wait

    gate = threading.Event()
    provider = Provider([delta()], gate)
    chat = service(tmp_path / "chat", provider)
    project = BuildProject(tmp_path / "project", "world", REGION, Bridge())
    chat.project = project
    chat.designer = WorldDesign(project)
    try:
        chat.submit(
            "Plan a 256 by 256 island.\nCamp: open pavilion 8 by 6, 4 blocks high.",
            "request",
            "one",
            design=True,
        )
        assert provider.entered.wait(2)
        chat.stop()
        gate.set()
        wait(lambda: not chat.busy and not chat.stopping)
        assert chat.designer.current()["components"] == []
        assert chat.designer.current()["planning"]["state"] == "stopped"
        assert not chat.bridge.actions
    finally:
        gate.set()
        chat.close()


def test_changed_design_cannot_resume_old_prepared_cells(tmp_path):
    from test_minecraft_chat import Provider, service

    chat = service(tmp_path / "chat", Provider([]))
    project = BuildProject(tmp_path / "project", "world", REGION, Bridge())
    chat.project = project
    chat.designer = WorldDesign(project)
    try:
        chat.designer.apply(delta(), "brief", 0)
        chat.project_action(
            "design_prepare", design_revision=1, component="Camp Pavilion"
        )
        chat.designer.apply(delta(size=[8, 7, 4]), "larger", 1)
        with pytest.raises(ValueError, match="Design changed"):
            chat.project_action("project_run")
        assert not project.bridge.cells
    finally:
        chat.close()


def test_manual_preview_editor_is_versioned_and_never_executes(tmp_path):
    from test_minecraft_chat import Provider, service

    chat = service(tmp_path / "chat", Provider([]))
    project = BuildProject(tmp_path / "project", "world", REGION, Bridge())
    chat.project = project
    chat.designer = WorldDesign(project)
    try:
        chat.designer.apply(delta(), "brief", 0)
        chat.edit_design_component(
            1, "Camp Pavilion", [8, 7, 4], "pavilion", "south", "shore", 1
        )
        current = chat.designer.current()
        assert current["revision"] == 2
        assert current["components"][0]["box"][2:4] == [7, 8]
        assert not project.bridge.cells
        with pytest.raises(ValueError, match="changed"):
            chat.edit_design_component(
                1, "Camp Pavilion", [8, 7, 4], "pavilion", "south", "shore", 1
            )
    finally:
        chat.close()


def test_palette_revision_preserves_geometry_and_marks_affected_places(design):
    before = design.apply(delta(), "brief", 0)
    change = delta()
    change.update(components=[], palette="natural")
    after = design.apply(change, "less industrial", 1)
    assert after["components"] == before["components"]
    assert after["changed"] == ["Camp Pavilion"]


def test_explicit_extent_cannot_be_changed_by_model(design):
    with pytest.raises(ValueError, match="requested project extent"):
        design.apply(delta(), "Plan a 192 by 192 town", 0)
    assert design.current() is None


def test_reference_limit_and_image_validation(design):
    for i in range(6):
        data = BytesIO()
        Image.new("RGB", (2, 2), (i, 0, 0)).save(data, format="PNG")
        design.add_reference(
            str(i) + ".png",
            "Synthetic reference",
            base64.b64encode(data.getvalue()).decode(),
        )
    data = BytesIO()
    Image.new("RGB", (2, 2), (9, 0, 0)).save(data, format="PNG")
    with pytest.raises(ValueError, match="six"):
        design.add_reference(
            "seventh.png", "Synthetic", base64.b64encode(data.getvalue()).decode()
        )


def test_selected_build_rejects_stale_connection_and_wrong_component(tmp_path):
    from test_minecraft_chat import Provider, service

    chat = service(tmp_path / "chat", Provider([]))
    chat.project = BuildProject(tmp_path / "project", "world", REGION, Bridge())
    chat.designer = WorldDesign(chat.project)
    try:
        chat.designer.apply(delta(), "brief", 0)
        with pytest.raises(ValueError, match="Connection changed"):
            chat.project_action(
                "design_prepare",
                design_revision=1,
                component="Camp Pavilion",
                session_id="stale",
            )
        chat.project_action(
            "design_prepare",
            design_revision=1,
            component="Camp Pavilion",
            session_id="one",
        )
        with pytest.raises(ValueError, match="selected current design"):
            chat.project_action(
                "design_run",
                design_revision=1,
                component="Wrong place",
                session_id="one",
            )
        assert not chat.project.bridge.cells
    finally:
        chat.close()


def test_recipe_answer_uses_registry_example_not_model_claim(tmp_path):
    from test_minecraft_chat import Provider, service, wait

    chat = service(
        tmp_path,
        Provider(
            [
                {
                    "kind": "question",
                    "reply": "You need stone and another crafting table.",
                }
            ]
        ),
    )
    chat.bridge.call = lambda op, args: {
        "item": "crafting_table",
        "recipes": [
            {
                "yield": 1,
                "table": False,
                "ingredients": [{"item": "oak_planks", "count": 4}],
            }
        ],
    }
    try:
        chat.submit(
            "What ingredients are required for a crafting table?", "recipe", "one"
        )
        wait(lambda: not chat.busy)
        answer = chat.messages[-1]["text"]
        assert "4 oak planks" in answer
        assert "no existing crafting table is required" in answer
        assert "stone" not in answer
        assert not chat.bridge.actions
    finally:
        chat.close()


@pytest.mark.parametrize('kind,size,allowed', [
    ('platform', [3, 3, 3], True),
    ('pavilion', [12, 12, 8], True),
    ('pavilion', [13, 12, 8], False),
    ('pavilion', [12, 2, 8], False),
    ('platform', [3, 3, 9], False),
    ('building', [6, 5, 4], False),
])
def test_preview_choices_and_compilation_share_geometry_policy(design, kind, size, allowed):
    assert design.snapshot()['preview_components'] == []
    design.apply(delta(kind=kind, size=size), 'synthetic preview', 0)
    assert design.snapshot()['preview_components'] == (['Camp Pavilion'] if allowed else [])
    if allowed:
        assert design.compile_component(1, 'Camp Pavilion') > 0
    else:
        with pytest.raises(ValueError):
            design.compile_component(1, 'Camp Pavilion')
        assert design.project.revision == 0
    assert not design.project.bridge.cells


def test_preview_uses_compiled_box_not_descriptive_size(design):
    import json
    value = design.apply(delta(), 'synthetic preview', 0)
    # A mismatched descriptive size must not create a second eligibility policy.
    value['components'][0]['size'] = [30, 30, 30]
    design.project.db.execute('UPDATE world_designs SET body=? WHERE revision=1', (json.dumps(value),))
    design.project.db.commit()
    assert design.snapshot()['preview_components'] == ['Camp Pavilion']
    assert design.compile_component(1, 'Camp Pavilion') > 0


def test_preview_policy_is_rechecked_not_saved_as_permission(design, monkeypatch):
    import smb3_agent.minecraft_design as module
    design.apply(delta(), 'synthetic preview', 0)
    assert design.snapshot()['preview_components'] == ['Camp Pavilion']
    monkeypatch.setattr(module, 'preview_problem', lambda component: 'Preview unavailable')
    assert design.snapshot()['preview_components'] == []
    with pytest.raises(ValueError, match='Preview unavailable'):
        design.compile_component(1, 'Camp Pavilion')
    assert design.project.revision == 0
