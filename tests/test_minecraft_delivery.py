import json
import pytest
from smb3_agent import minecraft_delivery as delivery
from smb3_agent.minecraft_chat import MinecraftChat
from test_minecraft_chat import Provider


def test_isolated_profile_never_uses_checkout(monkeypatch, tmp_path):
    monkeypatch.setenv('GAME_COMPANION_USER_DATA', str(tmp_path))
    assert delivery.world_home(True) == tmp_path / 'artifacts/minecraft-b1-survival-1.21.4'
    assert not delivery.setup_status()['worlds']['survival']['exists']


def test_missing_retained_world_does_not_create(monkeypatch, tmp_path):
    monkeypatch.setenv('GAME_COMPANION_USER_DATA', str(tmp_path))
    monkeypatch.setattr(delivery, 'java_runtime', lambda: '/java')
    monkeypatch.setattr(delivery, 'node_runtime', lambda: '/node')
    chat = MinecraftChat(tmp_path / 'chat', provider=Provider([]))
    with pytest.raises(ValueError, match='missing'):
        chat.connect(survival=True)
    assert not delivery.world_home(True).exists()
    with pytest.raises(ValueError, match='EULA'):
        chat.connect(create=True)
    assert not delivery.world_home().exists()


def test_create_never_overwrites_damaged_world(monkeypatch, tmp_path):
    monkeypatch.setenv('GAME_COMPANION_USER_DATA', str(tmp_path))
    monkeypatch.setattr(delivery, 'java_runtime', lambda: '/java')
    monkeypatch.setattr(delivery, 'node_runtime', lambda: '/node')
    home = delivery.world_home()
    home.mkdir(parents=True)
    (home / 'world-identity.json').write_text('{damaged')
    chat = MinecraftChat(tmp_path / 'chat', provider=Provider([]))
    with pytest.raises(ValueError, match='already exists'):
        chat.connect(create=True, accept_eula=True)
    assert (home / 'world-identity.json').read_text() == '{damaged'


def test_packaged_node_missing_has_reinstall_remedy(monkeypatch, tmp_path):
    monkeypatch.setattr(delivery, 'is_packaged', lambda: True)
    monkeypatch.setattr(delivery, 'repository_path', lambda p: tmp_path / p)
    with pytest.raises(ValueError, match='Reinstall'):
        delivery.node_runtime()


def test_retained_version_refused_without_write(tmp_path):
    for name in ['practice-world/level.dat', 'eula.txt']:
        p = tmp_path / name
        p.parent.mkdir(exist_ok=True)
        p.write_text('retained')
    (tmp_path / 'companion-practice.json').write_text(json.dumps({'schema': 1, 'version': 'old'}))
    (tmp_path / 'world-identity.json').write_text(json.dumps({'id': 'original'}))
    with pytest.raises(ValueError, match='incompatible'):
        delivery.retained_world(tmp_path)
    assert json.loads((tmp_path / 'world-identity.json').read_text()) == {'id': 'original'}


def test_oversized_craft_target_refused_before_authority(tmp_path):
    from smb3_agent.minecraft_construction import CraftGoal
    from test_minecraft_goals import setup
    from test_minecraft_chat import plan
    chat, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="not changed and no crafting"):
        CraftGoal(chat, plan(action="craft", craft_item="oak_planks", craft_quantity=84), chat.bridge.observe(), chat.authority())
    assert not chat.bridge.actions


def test_already_met_craft_is_not_claimed_as_crafting(tmp_path):
    from smb3_agent.minecraft_construction import CraftGoal
    from test_minecraft_goals import setup
    from test_minecraft_chat import plan
    chat, _ = setup(tmp_path)
    goal = CraftGoal(chat, plan(action="craft", craft_item="oak_planks", craft_quantity=4), chat.bridge.observe(), chat.authority())
    goal.ensure = lambda *args: None
    chat.supervisor = goal
    goal.run()
    assert "nothing crafted or consumed" in chat.messages[-1]["text"]


def test_migration_names_follow_delivery_version_without_active_profile_access(monkeypatch, tmp_path):
    import runpy
    from pathlib import Path
    monkeypatch.setenv('GAME_COMPANION_USER_DATA', str(tmp_path))
    monkeypatch.setattr(delivery, 'GAME_VERSION', 'synthetic-version')
    script = Path(__file__).parents[1] / 'scripts/migrate_minecraft_delivery.py'
    names = runpy.run_path(str(script))['NAMES']
    assert names == ('minecraft-chat', 'minecraft-b1-practice-synthetic-version', 'minecraft-b1-survival-synthetic-version')
    assert names[1:] == (delivery.world_home().name, delivery.world_home(True).name)
    assert not (tmp_path / 'artifacts').exists()
