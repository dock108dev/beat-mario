"""Disposable qualification copies retain execution inputs without duplicating logs."""
import importlib.util
from pathlib import Path


def test_copy_preserves_source_logs_and_all_execution_state(tmp_path):
    spec = importlib.util.spec_from_file_location('qualification', Path(__file__).parents[1] / 'scripts/qualify_minecraft_sustained.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source, destination = tmp_path/'source', tmp_path/'copy'
    files = ['profile/artifacts/minecraft-chat/events.jsonl',
             'profile/artifacts/minecraft-chat/worker-events.jsonl',
             'profile/artifacts/minecraft-chat/build-project/project.sqlite',
             'profile/artifacts/minecraft-chat/conversation.json',
             'world/practice-world/region/world.mca', 'world/events.jsonl']
    for name in files:
        p = source/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(name)
    retained = module.copy_trial_state(source, destination)
    assert len(retained) == 2
    for name in files:
        assert (source/name).read_text() == name
        if str((source/name).resolve()) in retained:
            assert not (destination/name).exists()
        else:
            assert (destination/name).read_text() == name


def test_restart_checkpoint_uses_selected_components_latest_material():
    import json
    import sqlite3
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location('qualification', Path(__file__).parents[1] / 'scripts/qualify_minecraft_sustained.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    db = sqlite3.connect(':memory:')
    try:
        db.executescript('CREATE TABLE architecture_reviews(id INTEGER, body TEXT); CREATE TABLE architecture_stages(component TEXT, review INTEGER);')
        for revision, name, material in [(1, 'Inn', 'glass'), (2, 'Inn', 'natural'), (3, 'Lodge', 'glass')]:
            db.execute('INSERT INTO architecture_reviews VALUES(?,?)', (revision, json.dumps({'components':[{'name':name,'material':material}]})))
            db.execute('INSERT INTO architecture_stages VALUES(?,?)', (name, revision))
        project = SimpleNamespace(db=db)
        assert module.checkpoint_material(project, 'Inn') == 'glass'
        assert module.checkpoint_material(project, 'Lodge') == 'natural'
    finally:
        db.close()


def test_question_call_reservation_counts_previous_sessions_not_current_snapshot(tmp_path):
    import json
    import pytest
    spec = importlib.util.spec_from_file_location('qualification', Path(__file__).parents[1] / 'scripts/qualify_minecraft_sustained.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for session, calls in enumerate([30, 40, 77]):
        (tmp_path/f'session-{session}.json').write_text(json.dumps({'provider_calls': calls}))
    current = tmp_path/'session-2.json'
    assert module.reserve_question_calls(tmp_path, current, 6) == 4
    with pytest.raises(ValueError, match='80-call'):
        module.reserve_question_calls(tmp_path, current, 7)
