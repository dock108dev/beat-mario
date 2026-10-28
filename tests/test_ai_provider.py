"""Offline transport checks with a disposable loopback model server."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

import pytest

from smb3_agent.ai_provider import create_provider, load_config
from smb3_agent.http_inference import LocalHTTPProvider
from smb3_agent.inference_contract import InferenceError
from smb3_agent.minecraft_planning import INTENT


@pytest.fixture
def model_server():
    state = {"mode": "valid", "requests": [], "started": threading.Event()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, value, status=200):
            data = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == '/apps/game-companion/v1/models':
                self.send({'data': [{'id': 'fixture:local'}]})
            elif self.path == '/api/tags':
                self.send({'models': [{'name': 'fixture:local', 'digest': 'fixture-digest'}]})
            else:
                self.send({}, 404)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path == '/api/show':
                self.send({}, 404)
                return
            assert self.path == '/apps/game-companion/v1/chat/completions'
            state['requests'].append(body)
            state['started'].set()
            if state['mode'] == 'delay':
                time.sleep(3)
                return
            value = {'kind': 'question', 'reply': 'Hello from the fixture model.'}
            if state['mode'] == 'extra':
                value['execute'] = 'untrusted'
            delta = {'content': json.dumps(value)}
            if state['mode'] == 'tools':
                delta['tool_calls'] = [{'id': 'forbidden'}]
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            rows = [
                {'model': 'other' if state['mode'] == 'wrong_model' else 'fixture:local',
                 'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]},
                {'model': 'fixture:local', 'choices': [{'index': 0, 'delta': {},
                 'finish_reason': 'length' if state['mode'] == 'truncated' else 'stop'}],
                 'usage': {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30}},
            ]
            for row in rows:
                self.wfile.write(b'data: ' + json.dumps(row).encode() + b'\n\n')
            self.wfile.write(b'data: [DONE]\n\n')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = {'provider': 'openai-compatible', 'app': 'game-companion',
              'base_url': f'http://127.0.0.1:{server.server_port}/apps/game-companion/v1',
              'api_key': 'fixture', 'model': 'fixture:local', 'timeout_seconds': 5,
              'max_tokens': 512, 'temperature': .3, 'reasoning_effort': 'none', 'stream': True}
    provider = LocalHTTPProvider(config)
    with provider._discovery_lock:
        assert provider.status['available']
    try:
        yield provider, state, config
    finally:
        provider.close()
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_streamed_completion_uses_configured_app_path_and_budgets(model_server):
    provider, state, config = model_server
    result = provider.infer('language', {'text': 'hello'}, INTENT, threading.Event())
    assert result['kind'] == 'question'
    assert len(state['requests']) == 1
    request = state['requests'][0]
    for key in ('model', 'max_tokens', 'temperature', 'reasoning_effort', 'stream'):
        assert request[key] == config[key]
    assert request['response_format']['json_schema']['schema'] == INTENT
    assert provider.usage[-1]['tokens']['completion_tokens'] == 20
    assert provider.usage[-1]['usage_known']
    assert provider.lifecycle() == []


@pytest.mark.parametrize('mode', ['extra', 'truncated', 'wrong_model', 'tools'])
def test_invalid_replies_fail_closed_without_retry(model_server, mode):
    provider, state, _ = model_server
    state['mode'] = mode
    with pytest.raises(InferenceError):
        provider.infer('language', {}, INTENT, threading.Event())
    assert len(state['requests']) == 1
    assert provider.lifecycle() == []
    assert provider.usage[-1]['status'] == 'failed_or_canceled'


def test_missing_vision_metadata_refuses_images_before_request(model_server, tmp_path):
    provider, state, _ = model_server
    assert provider.status['vision'] is False
    with pytest.raises(InferenceError, match='Screenshot understanding unavailable'):
        provider.infer('language', {}, INTENT, threading.Event(), images=[tmp_path/'image.png'])
    assert state['requests'] == []


def test_cancel_reaps_request_worker(model_server):
    provider, state, _ = model_server
    state['mode'] = 'delay'
    cancel = threading.Event()
    errors = []

    def infer():
        try:
            provider.infer('language', {}, INTENT, cancel)
        except InferenceError as exc:
            errors.append(str(exc))

    worker = threading.Thread(target=infer)
    worker.start()
    assert state['started'].wait(3)
    assert provider.lifecycle()[0]['child_running']
    cancel.set()
    worker.join(3)
    assert not worker.is_alive() and errors
    assert provider.lifecycle() == []


def test_deadline_reaps_request_worker(model_server):
    provider, state, _ = model_server
    state['mode'] = 'delay'
    provider.config['timeout_seconds'] = 1
    with pytest.raises(InferenceError):
        provider.infer('language', {}, INTENT, threading.Event())
    assert provider.lifecycle() == []


def test_factory_reads_only_selected_config_and_rejects_unknown_provider(monkeypatch, tmp_path):
    for key in list(__import__('os').environ):
        if key.startswith('AI_'):
            monkeypatch.delenv(key)
    path = tmp_path/'provider.json'
    monkeypatch.setenv('AI_CONFIG_FILE', str(path))
    path.write_text(json.dumps({'provider': 'unsupported-cli'}))
    provider = create_provider()
    assert not provider.status['available']
    assert provider.status['provider'] == 'disabled'
    path.write_text(json.dumps({'provider': 'disabled'}))
    assert load_config()['provider'] == 'disabled'


def test_factory_selects_authoritative_transport(model_server, monkeypatch, tmp_path):
    _, _, config = model_server
    for key in list(__import__('os').environ):
        if key.startswith('AI_'):
            monkeypatch.delenv(key)
    path = tmp_path/'provider.json'
    path.write_text(json.dumps(config))
    monkeypatch.setenv('AI_CONFIG_FILE', str(path))
    provider = create_provider()
    try:
        assert isinstance(provider, LocalHTTPProvider)
        with provider._discovery_lock:
            assert provider.status['available']
    finally:
        provider.close()
