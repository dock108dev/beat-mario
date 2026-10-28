import hashlib
import json

import pytest
from smb3_agent.minecraft_practice import PracticeServer


def prepare_home(tmp_path):
    (tmp_path / "companion-practice.json").write_text(
        json.dumps({"schema": 1, "version": "1.21.4"})
    )
    (tmp_path / "eula.txt").write_text("eula=true\n")
    (tmp_path / "server.jar").write_bytes(b"test-only-server")
    (tmp_path / "server-download.json").write_text(
        json.dumps({"sha1": hashlib.sha1(b"test-only-server").hexdigest()})
    )


def test_retained_creative_cannot_be_converted(tmp_path):
    prepare_home(tmp_path)
    creative = PracticeServer(home=tmp_path)
    creative.prepare()
    before = (tmp_path / "server.properties").read_bytes()
    with pytest.raises(ValueError, match="world mode"):
        PracticeServer(home=tmp_path, survival=True).prepare()
    assert (tmp_path / "server.properties").read_bytes() == before


def test_survival_persists_identity_and_natural_generation(tmp_path):
    prepare_home(tmp_path)
    server = PracticeServer(home=tmp_path, survival=True)
    server.prepare()
    world = server.world_id
    server.prepare()
    assert server.world_id == world
    text = (tmp_path / "server.properties").read_text()
    assert "gamemode=survival" in text
    assert "level-type=minecraft:normal" in text
    assert "generator-settings" not in text
