"""The frozen app must dispatch the same HTTP worker as source launches."""
from types import SimpleNamespace
import importlib
import sys
import pytest
from smb3_agent import app_runtime


@pytest.mark.parametrize('name', ['http_inference', 'model_gateway', 'process_watchdog'])
def test_frozen_helper_dispatches_allowed_worker(name, monkeypatch):
    calls = []
    module = SimpleNamespace(__name__='smb3_agent.' + name, _worker=lambda: calls.append(name))
    monkeypatch.setattr(sys, 'argv', ['Game Companion', '--gc-helper', module.__name__, '--worker'])
    monkeypatch.setattr(importlib, 'import_module', lambda value: module)
    app_runtime.main()
    assert calls == [name]


def test_http_helper_rejects_unexpected_arguments(monkeypatch):
    module = SimpleNamespace(__name__='smb3_agent.http_inference', _worker=lambda: pytest.fail('Unexpected dispatch'))
    monkeypatch.setattr(sys, 'argv', ['Game Companion', '--gc-helper', module.__name__, '--unexpected'])
    monkeypatch.setattr(importlib, 'import_module', lambda value: module)
    with pytest.raises(SystemExit, match='Invalid helper invocation'):
        app_runtime.main()
