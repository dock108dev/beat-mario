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


def test_conversation_dom_retains_only_current_bounded_window():
    import subprocess
    from smb3_agent.minecraft_chat_script import CHAT_JS
    helper = CHAT_JS.split('function renderMessages(',1)[1].split('async function refresh()',1)[0]
    source = '''
const assert=require('node:assert/strict');
let known=new Set();
class Node {
 constructor(){this.children=[];this.dataset={};}
 append(...nodes){for(const n of nodes){n.parent=this;this.children.push(n);}}
 remove(){this.parent.children=this.parent.children.filter(n=>n!==this);}
}
const document={createElement:()=>new Node(),createTextNode:text=>({text})};
const box=new Node();
const placeholder=new Node();box.append(placeholder);
''' + 'function renderMessages(' + helper + '''
const messages=Array.from({length:700},(_,i)=>({id:String(i),role:'user',text:'message '+i}));
renderMessages(messages.slice(0,500),box);
const retained=box.children[251];
renderMessages(messages,box);
assert.equal(box.children.length,501);
assert.equal(known.size,500);
assert.equal(box.children[1].dataset.messageId,'200');
assert.equal(box.children[51],retained);
renderMessages(messages,box);
assert.equal(box.children.length,501);
renderMessages([],box);
assert.equal(box.children.length,1);
assert.equal(box.children[0],placeholder);
assert.equal(known.size,0);
'''
    subprocess.run(['node','-e',source],check=True,capture_output=True,text=True)


def test_preview_menu_consumes_server_policy_without_local_geometry_rules():
    from smb3_agent.minecraft_chat_script import CHAT_JS
    renderer = CHAT_JS.split('function renderDesign(s){', 1)[1].split('function loadDesignEditor()', 1)[0]
    assert 'new Set(s.design.preview_components||[])' in renderer
    assert 'previewComponents.has(c.name)' in renderer
    assert 'const hasSample=previewComponents.size>0' in renderer
    assert 'c.size[0]>=' not in renderer and 'w>=3' not in renderer
