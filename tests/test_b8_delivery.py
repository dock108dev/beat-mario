import json
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest
import yaml

from smb3_agent.beta_readiness import CONTRACT_PATH, inspect_beta
from smb3_agent.lab_ui import _new_lab_ui_server
from smb3_agent.stardew_runtime import StardewRuntime


def test_delivery_identity_and_shutdown_require_csrf_and_instance():
    server = _new_lab_ui_server('127.0.0.1', 0)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        identity = json.load(urlopen(base + '/api/delivery'))
        assert len(identity['source_sha256']) == 64
        assert identity['csrf_token'] == server.csrf_token
        assert identity['root'].endswith('beat-mario')
        for payload in ({'instance': identity['instance']},
                        {'instance': 'obsolete', 'csrf_token': server.csrf_token}):
            with pytest.raises(HTTPError):
                urlopen(Request(base + '/api/delivery/shutdown', data=urlencode(payload).encode()))
        assert not server.delivery_stopping
        result = json.load(urlopen(Request(base + '/api/delivery/shutdown', data=urlencode(
            {'instance': identity['instance'], 'csrf_token': server.csrf_token}).encode())))
        assert result['cleanup_confirmed']
        worker.join(5)
        assert not worker.is_alive()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_runtime_close_neutralizes_before_closing_only_owned_processes():
    events = []
    class Process:
        def poll(self): return None
        def terminate(self): events.append('terminate')
        def wait(self, timeout): events.append('wait')
    runtime = StardewRuntime.__new__(StardewRuntime)
    runtime.control = lambda *a, **kw: events.append('neutralize')
    runtime._engineering_launches = [(object(), Process())]
    runtime.close()
    assert events == ['neutralize', 'terminate', 'wait']


def test_b8_does_not_fill_owner_judgment_or_enable_campaign():
    contract = yaml.safe_load(CONTRACT_PATH.read_text())
    assert contract['execution_enabled'] is False
    assert all(r['classification'] == 'visible_live_result' for r in contract['stages']['B6'])
    assert len(contract['stages']['B8']) == 6
    report = inspect_beta(candidate={'source_sha256': 'test', 'head': 'test'})
    assert not report['ready_for_b9'] and not report['beta_ready']
    assert report['owner_usefulness'] is None and report['owner_acceptance'] is None


def test_owned_child_survives_detach_but_is_closed_by_delivery():
    import subprocess
    import sys
    from smb3_agent.delivery import OwnedGameProcesses
    owned = OwnedGameProcesses()
    child = owned.launch([sys.executable, "-c", "import time; time.sleep(60)"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert child.poll() is None
        owned.close()
        assert child.poll() is not None
        owned.close()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
