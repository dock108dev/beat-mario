import http.client
import json
import threading
from urllib.parse import urlencode

from smb3_agent import lab_ui


def test_shell_serves_script_and_protects_commands(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = lab_ui._new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        c.request(method, path, body, headers or {})
        r = c.getresponse()
        data = r.read().decode()
        result = r.status, dict(r.getheaders()), data
        c.close()
        return result

    try:
        status, headers, page = request("GET", "/")
        assert status == 200 and "/assets/minecraft-chat.js" in page
        assert "script-src 'self'" in headers["Content-Security-Policy"]
        assert "frame-src http://127.0.0.1:*" in headers["Content-Security-Policy"]
        status, _, script = request("GET", "/assets/minecraft-chat.js")
        assert status == 200 and "TOKEN_VALUE" not in script
        status, _, guide = request("GET", "/help")
        assert status == 200 and "Minecraft companion" in guide
        assert "MC-B1" not in guide
        status, _, state = request("GET", "/api/minecraft/chat")
        assert status == 200 and json.loads(state)["session_id"] is None
        status, _, _ = request(
            "POST",
            "/api/minecraft/chat",
            urlencode({"action": "connect"}),
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert status == 403 and server.minecraft_chat.practice is None
        status, _, _ = request(
            "POST",
            "/api/minecraft/chat",
            urlencode({"action": "connect", "csrf_token": server.csrf_token}),
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://foreign.example",
            },
        )
        assert status == 403 and server.minecraft_chat.practice is None
        status, _, state = request(
            "POST",
            "/api/minecraft/chat",
            urlencode(
                {
                    "action": "message",
                    "csrf_token": server.csrf_token,
                    "text": "go",
                    "request_id": "test",
                    "session_id": "old",
                }
            ),
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert status == 409 and "Connection changed" in state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
