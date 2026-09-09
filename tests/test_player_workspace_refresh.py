"""Exercise the shipped refresh script against controlled DOM transitions."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from smb3_agent.lab_ui import PLAYER_WORKSPACE_JS


NODE = shutil.which("node")

HARNESS = r"""
const vm = require('node:vm');
const assert = require('node:assert/strict');
let input = '';
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', async () => {
  const {script, scenario} = JSON.parse(input);
  const body = {tagName: 'BODY', matches: () => false};
  const document = {activeElement: body, hasFocus: () => true,
    addEventListener: () => {}};
  const control = (tag, text, disabled = false) => ({
    tagName: tag, id: '', textContent: text, disabled,
    getAttribute: () => null,
    closest: selector => selector === '[id]' ? {id: 'live'} : null,
    getClientRects: () => [{}],
    matches: selector => selector.includes(tag.toLowerCase()),
    focus(options) {
      assert.equal(options.preventScroll, true);
      document.activeElement = this;
    }
  });
  const old = control('SUMMARY', 'Details');
  const replacement = control('SUMMARY', 'Details');
  const newAction = control('BUTTON', 'Start');
  const newActionReplacement = control('BUTTON', 'Start');
  const editor = control('INPUT', '');
  let children = [old, newAction, editor];
  let next = [replacement, newActionReplacement];
  let replacements = 0;
  const workspace = {
    contains: element => children.includes(element),
    querySelectorAll: selector => selector.startsWith('details') ? [] : children,
    set innerHTML(html) {
      assert.equal(html, '<replacement>');
      replacements++;
      children = next;
      document.activeElement = body;
    }
  };
  document.getElementById = () => workspace;
  document.activeElement = old;
  let expected = replacement;
  let expectedReplacements = 1;
  if (scenario === 'button') {
    document.activeElement = newAction;
    expected = newActionReplacement;
  }
  if (scenario === 'removed') {next = []; expected = body;}
  if (scenario === 'disabled') {replacement.disabled = true; expected = body;}
  if (scenario === 'ambiguous') {
    next.push(control('SUMMARY', 'Details')); expected = body;
  }
  if (scenario === 'editing') {
    document.activeElement = editor;
    expected = editor; expectedReplacements = 0;
  }
  const fetch = async () => ({ok: true, text: async () => {
    if (scenario === 'focus_moved') {
      document.activeElement = newAction; expected = newActionReplacement;
    }
    if (scenario === 'editing_during_fetch') {
      document.activeElement = editor;
      expected = editor; expectedReplacements = 0;
    }
    return '<replacement>';
  }});
  let refresh;
  vm.runInNewContext(script, {document, fetch,
    window: {setInterval: callback => {refresh = callback;}}});
  await refresh();
  assert.equal(replacements, expectedReplacements);
  assert.equal(document.activeElement, expected);
});
"""


@pytest.mark.skipif(NODE is None, reason="Node.js is needed for the browser-script regression")
@pytest.mark.parametrize(
    "scenario",
    ["summary", "button", "removed", "disabled", "ambiguous", "editing",
     "focus_moved", "editing_during_fetch"],
)
def test_workspace_refresh_preserves_only_current_unambiguous_focus(scenario: str) -> None:
    result = subprocess.run(
        [NODE, "-e", HARNESS],
        input=json.dumps({"script": PLAYER_WORKSPACE_JS, "scenario": scenario}),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
