"""A window geometry race rejects pixels and retains bounded diagnostic evidence."""
from dataclasses import replace
from types import SimpleNamespace
import json
import subprocess
import pytest
from PIL import Image
from smb3_agent.native_host import capture_selected
from smb3_agent.host_contracts import WindowObservation, HostError


def test_capture_bounds_change_is_retained_and_never_accepted(tmp_path, monkeypatch):
    window = WindowObservation(123, 'start', '7', 'game', (0, 0, 100, 100), True, True, True)
    windows = iter([window, replace(window, bounds=(0, 0, 80, 80))])
    def capture(args, **kwargs):
        Image.new('RGB', (100, 100)).save(args[-1], format='TIFF')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(subprocess, 'run', capture)
    target = tmp_path/'frame.png'
    with pytest.raises(HostError, match='process/window changed'):
        capture_selected(window, target, detect_window=lambda: next(windows))
    assert not target.exists()
    record = json.loads(target.with_suffix('.capture-refusal.json').read_text())
    assert record['frame_accepted'] is False
    assert record['before']['bounds'] != record['after']['bounds']
    assert target.with_name('frame-capture.tiff').exists()
