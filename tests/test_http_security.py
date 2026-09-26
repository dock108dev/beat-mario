"""Synthetic HTTP/parser security checks; no gameplay or owner state."""
from email.message import Message
import http.client
import io
import logging
from pathlib import Path
from types import SimpleNamespace
import threading
from urllib.parse import urlencode

import pytest

from smb3_agent.lab_ui import _Handler, LabUiError, LabUiForbidden, _new_lab_ui_server, _single


def handler(headers=(), body=b""):
    value = object.__new__(_Handler)
    value.headers = Message()
    for key, item in headers:
        value.headers[key] = item
    value.server = SimpleNamespace(server_port=8765, csrf_token="valid-token")
    value.rfile = io.BytesIO(body)
    return value


@pytest.mark.parametrize("host", [
    "attacker@localhost:8765", "localhost:8765/path", "localhost:8765?secret=x",
    "localhost:8765#fragment", "localhost:99999", "localhost:8766", "localhost",
    "localhost:8765,evil.invalid", "localhost:8765\\evil", "evil.invalid:8765",
])
def test_host_must_be_exact_loopback_authority_at_server_port(host):
    with pytest.raises(LabUiForbidden):
        handler([("Host", host)])._validate_host()


def test_duplicate_host_rejected():
    with pytest.raises(LabUiForbidden):
        handler([("Host", "localhost:8765"), ("Host", "localhost:8765")])._validate_host()


@pytest.mark.parametrize("host", ["localhost:8765", "LOCALHOST:8765", "127.0.0.1:8765", "[::1]:8765"])
def test_valid_loopback_hosts(host):
    handler([("Host", host)])._validate_host()


@pytest.mark.parametrize("origin", ["null", "https://localhost:8765", "http://localhost:8766",
    "http://evil.invalid", "http://attacker@localhost:8765", "http://localhost:8765/path"])
def test_foreign_or_opaque_origin_rejected(origin):
    with pytest.raises(LabUiForbidden):
        handler([("Host", "localhost:8765"), ("Origin", origin)])._validate_origin()


def test_duplicate_origin_rejected():
    with pytest.raises(LabUiForbidden):
        handler([("Host", "localhost:8765"), ("Origin", "http://localhost:8765"),
                 ("Origin", "http://localhost:8765")])._validate_origin()


@pytest.mark.parametrize("extra", [[("Content-Length", "3")], [("Transfer-Encoding", "chunked")],
                                   [("Content-Type", "application/x-www-form-urlencoded")]])
def test_ambiguous_framing_rejected(extra):
    request = handler([("Content-Length", "3"), ("Content-Type", "application/x-www-form-urlencoded"), *extra], b"a=b")
    with pytest.raises(LabUiError):
        request._read_form()
    assert request.rfile.tell() == 0


@pytest.mark.parametrize("body", [b"value=%FF", b"value=\xff", b"&".join([b"a=b"] * 129)])
def test_invalid_encoding_or_excessive_field_count(body):
    with pytest.raises(LabUiError):
        handler([("Content-Length", str(len(body))), ("Content-Type", "application/x-www-form-urlencoded")], body)._read_form()


def test_repeated_lists_supported_but_scalar_duplicates_rejected():
    body = b"locations=a&locations=b&action=stop&action=start"
    form = handler([("Content-Length", str(len(body))), ("Content-Type", "application/x-www-form-urlencoded")], body)._read_form()
    assert form["locations"] == ["a", "b"]
    with pytest.raises(LabUiError, match="exactly once"):
        _single(form, "action")


def test_non_ascii_and_duplicate_csrf_refused():
    with pytest.raises(LabUiForbidden):
        handler()._validate_csrf({"csrf_token": ["é"]})
    with pytest.raises(LabUiError):
        handler()._validate_csrf({"csrf_token": ["valid-token", "different"]})


def test_origin_gate_precedes_mutation_and_native_client_still_works(monkeypatch):
    calls = []
    server = _new_lab_ui_server("127.0.0.1", 0)
    monkeypatch.setattr(server.conversation_service, "dispatch", lambda action, payload: calls.append(action) or {"ok": True})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for origin, expected in [("http://evil.invalid", 403), (f"http://127.0.0.1:{server.server_port}", 200), (None, 200)]:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            if origin:
                headers["Origin"] = origin
            connection.request("POST", "/api/conversation", urlencode({"action": "stop", "csrf_token": server.csrf_token}), headers)
            response = connection.getresponse()
            response.read()
            connection.close()
            assert response.status == expected
        assert calls == ["stop", "stop"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_query_and_private_exception_never_enter_log(monkeypatch, caplog):
    def broken(_self):
        raise RuntimeError("private-exception-secret")
    monkeypatch.setattr(_Handler, "_handle_get", broken)
    server = _new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with caplog.at_level(logging.INFO, logger="smb3_agent.lab_ui"):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            connection.request("GET", "/api/delivery?csrf_token=private-query-secret")
            response = connection.getresponse()
            body = response.read().decode()
            connection.close()
        assert response.status == 500
        assert "private-query-secret" not in caplog.text
        assert "private-exception-secret" not in caplog.text + body
        assert "route=/api/delivery" in caplog.text and "error_type=RuntimeError" in caplog.text
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_artifact_growth_after_stat_cannot_exceed_response_limit(tmp_path, monkeypatch):
    import smb3_agent.lab_ui as module
    path = tmp_path / "growing.log"
    path.write_bytes(b"small")
    monkeypatch.setattr(module, "MAX_SERVED_FILE_BYTES", 8)
    original = Path.open
    def growing_open(value, mode="r", *args, **kwargs):
        if value == path and mode == "rb":
            return io.BytesIO(b"x" * 100)
        return original(value, mode, *args, **kwargs)
    monkeypatch.setattr(Path, "open", growing_open)
    request = handler()
    errors = []
    request.send_error = errors.append
    request._send_workspace_file(tmp_path, "growing.log", {".log": "text/plain"})
    assert errors == [413]
