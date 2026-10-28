"""Failure/retry regressions using disposable JSON and synthetic worker streams."""

from concurrent.futures import Future
from io import StringIO
import json
from types import SimpleNamespace
import threading
from collections import deque

import pytest

from smb3_agent.minecraft_bridge import MinecraftBridge
from smb3_agent.minecraft_memory import DurableJSON, MemoryUnavailable, library
from test_minecraft_chat import service, Provider, wait


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_COMPANION_USER_DATA", str(tmp_path / "app-data"))


@pytest.mark.parametrize("failure", ["write", "replace", "sync_directory"])
def test_failed_restore_stays_blocked_and_can_be_retried(
    tmp_path, monkeypatch, failure
):
    store = DurableJSON(tmp_path / "memory.json", library)
    original = {"schema": 1, "structures": {}, "preferences": {}}
    store.save(original)
    store.save({**original, "outcomes": []})
    generation = store.candidates()[0]
    store.path.write_text("{damaged")
    assert store.load(None) is None
    with monkeypatch.context() as patch:

        def fail(*args):
            raise OSError("synthetic restore failure")

        if failure == "replace":
            patch.setattr("smb3_agent.minecraft_memory.os.replace", fail)
        elif failure == "write":
            real_write = store.write

            def fail_temp(path, data):
                if path.suffix == ".tmp":
                    fail()
                real_write(path, data)

            patch.setattr(store, "write", fail_temp)
        else:
            patch.setattr(store, failure, fail)
        with pytest.raises(OSError, match="synthetic"):
            store.restore(generation)
    assert store.problem
    with pytest.raises(MemoryUnavailable):
        store.save(original)
    assert any(p.read_text() == "{damaged" for p in tmp_path.glob("*.incident-*"))
    assert store.restore(generation) == original
    assert store.problem is None
    assert store.load(None) == original


def test_archive_sync_failure_preserves_previous_commit(tmp_path, monkeypatch):
    store = DurableJSON(tmp_path / "memory.json", library)
    value = {"schema": 1, "structures": {}, "preferences": {}}
    store.save(value)
    before = store.path.read_bytes()
    sync = store.sync_directory

    def fail_archive(path):
        if path == store.archive:
            raise OSError("archive directory sync failed")
        sync(path)

    monkeypatch.setattr(store, "sync_directory", fail_archive)
    with pytest.raises(OSError, match="archive"):
        store.save({**value, "outcomes": []})
    assert store.path.read_bytes() == before
    assert store.candidates()


def reader_with(events, pending):
    bridge = MinecraftBridge.__new__(MinecraftBridge)
    bridge.process = SimpleNamespace(
        stdout=StringIO("".join(json.dumps(e) + "\n" for e in events)),
        poll=lambda: 0,
    )
    bridge.condition = threading.Condition()
    bridge.events = deque(maxlen=2000)
    bridge.pending = pending
    return bridge


def test_canceled_future_does_not_abort_later_replies():
    canceled, other = Future(), Future()
    canceled.cancel()
    events = [
        {
            "v": 1,
            "type": "completed",
            "session_id": "s",
            "request_id": rid,
            "result": {"position": 7},
        }
        for rid in ("canceled", "other")
    ]
    bridge = reader_with(events, {"canceled": ("s", canceled), "other": ("s", other)})
    bridge._read()
    assert canceled.cancelled()
    assert other.result() == {"position": 7}
    assert not bridge.pending
    assert len(bridge.events) == 2


def test_worker_exit_resolves_all_pending_even_after_caller_cancellation():
    canceled, other = Future(), Future()
    canceled.cancel()
    bridge = reader_with([], {"canceled": ("s", canceled), "other": ("s", other)})
    bridge._read()
    assert canceled.cancelled()
    with pytest.raises(RuntimeError, match="worker exited"):
        other.result()
    assert not bridge.pending


def test_memory_rejection_does_not_consume_request_or_add_message(tmp_path):
    chat = service(tmp_path, Provider([{"kind": "question", "reply": "Ready"}]))
    chat.library_store.problem = "synthetic corruption"
    with pytest.raises(ValueError, match="Memory needs recovery"):
        chat.submit("Where are you?", "retryable", "one")
    assert "retryable" not in chat.seen
    assert not chat.messages
    assert not chat.history.exists()
    chat.library_store.problem = None
    chat.submit("Where are you?", "retryable", "one")
    wait(lambda: not chat.busy)
    assert "retryable" in chat.seen
    assert len(chat.provider.calls) == 1


def test_direct_chat_stop_remains_available_with_memory_problem(tmp_path):
    chat = service(tmp_path, Provider([]))
    chat.library_store.problem = "synthetic corruption"
    chat.submit("Stop", "stop", "one")
    wait(lambda: not chat.stopping)
    assert chat.bridge.stops == 1
    assert not chat.provider.calls
