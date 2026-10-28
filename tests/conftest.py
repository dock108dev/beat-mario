"""Tests never inherit the operator's inference server or credentials."""
import os

import pytest


@pytest.fixture(autouse=True)
def isolated_ai_settings(monkeypatch, tmp_path):
    for key in list(os.environ):
        if key.startswith('AI_'):
            monkeypatch.delenv(key)
    monkeypatch.setenv('AI_CONFIG_FILE', str(tmp_path / 'ai-provider.json'))
    monkeypatch.setenv('AI_PROVIDER', 'disabled')
