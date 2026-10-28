import threading
import pytest
from test_minecraft_chat import Provider, plan, service, wait


def stopping(tmp_path, confirmed=True):
    chat = service(tmp_path, Provider([plan()]))
    entered, release = threading.Event(), threading.Event()
    original = chat.bridge.stop

    def stop(**kw):
        entered.set()
        release.wait(3)
        result = original(**kw)
        result["stopped_observed"] = confirmed
        return result

    chat.bridge.stop = stop
    chat.stop()
    assert entered.wait(1)
    return chat, release


def test_stop_rejects_before_consuming_request_or_draft_then_fresh_authority(tmp_path):
    chat, release = stopping(tmp_path)
    try:
        with pytest.raises(ValueError, match="draft is retained"):
            chat.submit("Walk north", "retained", "one")
        assert "retained" not in chat.seen
        assert not chat.provider.calls
        epoch = chat.epoch
        chat.stop()
        assert chat.epoch == epoch
    finally:
        release.set()
    wait(lambda: not chat.stopping)
    chat.submit("Walk north", "retained", "one")
    wait(lambda: not chat.busy)
    assert chat.bridge.actions[0][1]["revision"] == 1
    assert len(chat.provider.calls) == 1
    chat.bridge.future.set_result({"observed": "position"})


def test_failed_stop_blocks_intent_until_confirmed_reconnect(tmp_path):
    chat, release = stopping(tmp_path, False)
    release.set()
    wait(lambda: not chat.stopping)
    assert chat.stop_failed
    with pytest.raises(ValueError, match="unconfirmed"):
        chat.submit("Go north", "r", "one")
    chat.reconnect()
    wait(lambda: not chat.connecting)
    assert not chat.stop_failed and not chat.stopping
    assert not chat.bridge.actions


def test_reconnect_during_stop_never_promotes_queued_authority(tmp_path):
    chat, release = stopping(tmp_path)
    chat.reconnect()
    with pytest.raises(ValueError):
        chat.submit("Go north", "r", "one")
    release.set()
    wait(lambda: not chat.connecting)
    assert not chat.stopping
    assert not chat.provider.calls and not chat.bridge.actions
