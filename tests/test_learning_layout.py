"""Fast CSS contract; real geometry is checked by check_learning_layout.py."""
import re
from pathlib import Path

import pytest

from smb3_agent.lab_ui import default_companion_session, render_companion_ui


def test_learning_card_spans_all_columns_including_single_column_mobile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    html = render_companion_ui(default_companion_session())
    desktop_css, mobile_css = html.split('@media (max-width: 760px)', 1)
    assert re.search(r'\.learning-card[^{}]*\{\s*grid-column:\s*1 / -1;', desktop_css)
    assert '.companion-main { grid-template-columns: 1fr; }' in mobile_css
    assert 'class="session-card learning-card"' in html
