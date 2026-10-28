"""Explicit inference selection shared by source and desktop entry points."""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from smb3_agent.inference_contract import InferenceError


def config_path():
    return Path(os.environ.get('AI_CONFIG_FILE', str(
        Path.home() / 'Library/Application Support/Game Companion/ai-provider.json'))).expanduser()


def load_config():
    path = config_path()
    config = json.loads(path.read_text()) if path.is_file() else {}
    if not isinstance(config, dict):
        raise InferenceError('AI configuration must be an object')
    fields = {'provider': 'AI_PROVIDER', 'base_url': 'AI_BASE_URL', 'model': 'AI_MODEL',
              'api_key': 'AI_API_KEY', 'timeout_seconds': 'AI_TIMEOUT_SECONDS',
              'max_tokens': 'AI_MAX_TOKENS', 'temperature': 'AI_TEMPERATURE',
              'reasoning_effort': 'AI_REASONING_EFFORT', 'stream': 'AI_STREAM'}
    for key, env in fields.items():
        if env in os.environ:
            config[key] = os.environ[env]
    config.setdefault('provider', 'disabled')
    config.setdefault('app', 'game-companion')
    if config['app'] != 'game-companion':
        raise InferenceError('AI configuration belongs to another application')
    if config['provider'] not in {'disabled', 'ollama', 'openai-compatible'}:
        raise InferenceError('Unsupported AI provider; no fallback is enabled')
    if config['provider'] in {'ollama', 'openai-compatible'}:
        validate_url(config.get('base_url', ''))
        model = config.get('model')
        if not isinstance(model, str) or not model or 'cloud' in model.lower() or len(model) > 200:
            raise InferenceError('Set an explicit local AI_MODEL tag')
        key = config.get('api_key', '')
        if not isinstance(key, str) or '\n' in key or '\r' in key:
            raise InferenceError('Invalid AI_API_KEY')
        config['base_url'] = config['base_url'].rstrip('/')
        config['timeout_seconds'] = float(config.get('timeout_seconds', 240))
        config['max_tokens'] = int(config.get('max_tokens', 512))
        config['temperature'] = float(config.get('temperature', .3))
        config['reasoning_effort'] = config.get('reasoning_effort', 'none')
        stream = config.get('stream', True)
        if stream not in (True, False, 'true', 'false'):
            raise InferenceError('AI_STREAM must be true or false')
        config['stream'] = stream in (True, 'true')
        if not (1 <= config['timeout_seconds'] <= 240 and 1 <= config['max_tokens'] <= 512
                and 0 <= config['temperature'] <= 2 and config['reasoning_effort'] == 'none'):
            raise InferenceError('Invalid local inference bounds')
    return config


def validate_url(url):
    if not isinstance(url, str):
        raise InferenceError("AI_BASE_URL must be a URL string")
    parsed = urlsplit(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise InferenceError('AI_BASE_URL must be an explicit local HTTP(S) API URL')
    try:
        local = parsed.hostname == 'localhost' or ipaddress.ip_address(parsed.hostname).is_private
    except ValueError:
        local = False
    if not local:
        raise InferenceError('Only an explicitly selected loopback or private-network AI server is allowed')
    return parsed


class UnavailableProvider:
    def __init__(self, message):
        self.status = {'available': False, 'state': 'unavailable', 'provider': 'disabled',
                       'message': message, 'vision': False,
                       'inference': 'AI is disabled until explicitly configured; no fallback.'}
        self.usage = []

    def refresh(self):
        return dict(self.status)

    def lifecycle(self):
        return []

    def close(self):
        pass

    def infer(self, *args, **kwargs):
        raise InferenceError(self.status['message'])


def create_provider():
    try:
        config = load_config()
        if config['provider'] in {'openai-compatible', 'ollama'}:
            from smb3_agent.http_inference import LocalHTTPProvider
            return LocalHTTPProvider(config)
        return UnavailableProvider('Choose an AI provider in ai-provider.json or AI_PROVIDER, then restart.')
    except (OSError, ValueError, TypeError):
        return UnavailableProvider('AI configuration is invalid or unreadable. Check ai-provider.json and AI_* settings; no fallback was used.')
