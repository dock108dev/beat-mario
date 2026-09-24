from copy import deepcopy
import json

import pytest

from smb3_agent.custom_variants import CustomVariantStore, PlanAttemptHistory


def plan():
    return {"game_id": "mario", "base_route_id": "world_8_finish_game", "base_version": "1",
            "revision": 2, "parent_revision": 1, "variant_id": None,
            "session_id": "active", "observation_id": "active:42",
            "actions": [{"kind": "mario_traverse", "parameters": {"path_choice": "opening_hop"}}],
            "authorization_scope": {"granted": True, "nonce": "secret"},
            "control_epoch": 7, "applied_speed": "turbo"}


def test_saved_revisions_preserve_original_steps_and_discard_authority(tmp_path):
    store = CustomVariantStore(tmp_path)
    original = plan()
    first = store.save("Opening hop", original)
    assert original["authorization_scope"]["granted"] is True
    before = (tmp_path / first["variant_id"] / "revision-000001.json").read_bytes()
    edited = deepcopy(original)
    edited["actions"][0]["parameters"]["path_choice"] = "default"
    second = store.save("Opening hop revised", edited, variant_id=first["variant_id"])
    assert second["saved_revision"] == 2
    assert second["parent_saved_revision"] == 1
    assert (tmp_path / first["variant_id"] / "revision-000001.json").read_bytes() == before
    loaded = store.load(first["variant_id"], revision=1, game_id="mario")
    assert loaded["plan"]["actions"][0]["parameters"]["path_choice"] == "opening_hop"
    assert loaded["plan"]["authorization_scope"]["granted"] is False
    assert "nonce" not in loaded["plan"]["authorization_scope"]
    assert "control_epoch" not in loaded["plan"]
    assert loaded["plan"]["session_id"] is None
    assert loaded["plan"]["applied_speed"] is None
    assert loaded["status"] == "saved"
    assert not loaded["accepted"] and not loaded["fastest"]
    assert loaded["completion_coverage"] == "unknown"


def test_reopen_revalidates_game_integrity_and_adapter_compatibility(tmp_path):
    store = CustomVariantStore(tmp_path)
    saved = store.save("Hop", plan())
    with pytest.raises(ValueError, match="different game"):
        store.load(saved["variant_id"], game_id="stardew")
    def unavailable(_plan):
        raise ValueError("Primitive version no longer available")
    with pytest.raises(ValueError, match="Primitive version"):
        store.load(saved["variant_id"], validate=unavailable)
    path = tmp_path / saved["variant_id"] / "revision-000001.json"
    changed = json.loads(path.read_text())
    changed["plan"]["actions"][0]["parameters"]["path_choice"] = "teleport"
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="integrity"):
        store.load(saved["variant_id"])
    assert store.list()[0]["status"] == "unavailable"


@pytest.mark.parametrize("status", ["failed", "reclaimed", "cancelled", "partial", "completed_stop"])
def test_all_outcomes_remain_immutable_and_unaccepted(tmp_path, status):
    history = PlanAttemptHistory(tmp_path)
    path = history.record("attempt-1", {"status": status, "actor": "mixed",
                                      "elapsed_game_frames": 400, "speed_intervals": [{"acknowledged": "turbo"}]})
    result = json.loads(path.read_text())
    assert result["status"] == status
    assert result["owner_acceptance"] is None
    assert result["reliability_accepted"] is False
    assert result["fastest"] is False
    assert result["completion_coverage"] == "unknown"
    with pytest.raises(FileExistsError):
        history.record("attempt-1", {"status": "completed"})


def test_history_selects_latest_recorded_outcomes_before_applying_limit(monkeypatch, tmp_path):
    # UUID-like attempt filenames are independent of creation order. A new
    # result must stay visible even when its filename sorts before older ones.
    ticks = iter(f"2026-09-24T01:00:{second:02d}+00:00" for second in range(22))
    monkeypatch.setattr("smb3_agent.custom_variants._now", lambda: next(ticks))
    history = PlanAttemptHistory(tmp_path)
    for index in range(22):
        history.record(f"attempt-{22-index:02d}", {"status": "partial", "ordinal": index})
    records = history.list(limit=20)
    assert [record["ordinal"] for record in records] == list(range(21, 1, -1))
    assert records[0]["attempt_id"] == "attempt-01"
    assert len(list(tmp_path.glob("*.json"))) == 22
