"""Minimal local MC-B1-01 harness, not the installed product interface."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import signal
import threading

from smb3_agent.minecraft_bridge import MinecraftBridge
from smb3_agent.minecraft_practice import PracticeServer

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Minecraft practice · Game Companion</title>
<style>body{font:16px system-ui;background:#18211e;color:#edf5ee;margin:24px}button{padding:12px;margin:6px;border:0;border-radius:7px;cursor:pointer}#stop{background:#faad9e;font-weight:bold}iframe{width:100%;height:65vh;border:0;background:#111}#status{white-space:pre-wrap}a{color:#a9e0bf}</style></head><body>
<h1>Minecraft practice</h1><p id="identity"></p>
<button id="stop">Stop</button><button id="move">Walk 5 blocks</button><button id="dig">Remove nearby ground block</button>
<button id="hide">Close view</button><button id="reconnect">Reconnect bot</button>
<p id="activity">Connecting…</p><p>Closing the view keeps the bot playing. Stop clears active and queued work. Reopening does not start work.</p>
<iframe id="view" title="Live Minecraft session"></iframe><p id="status"></p>
<script>
const stopButton=document.getElementById('stop'), statusText=document.getElementById('status');
const token='TOKEN_VALUE'; let sid=null, revision=0, frameUrl=null, shown=true, pending=null;
async function command(op,args={}){const response=await fetch('/command',{method:'POST',headers:{'Content-Type':'application/json','X-Companion-Token':token},body:JSON.stringify({op,args,session_id:sid,revision})});const result=await response.json(); if(!response.ok)throw Error(result.error);return result;}
stopButton.onclick=async()=>{activity.textContent='Stop dispatched locally; awaiting bot confirmation…';try{const r=await command('cancel');revision=r.revision;activity.textContent=r.stopped_observed?'Stopped — stationary position observed.':'Controls cleared; stationary state is not confirmed.';}catch(e){activity.textContent=e.message;}};
async function act(op){try{const r=await command(op);pending=r.request_id;activity.textContent='Action submitted…';}catch(e){activity.textContent=e.message;}}
move.onclick=()=>act('move');
dig.onclick=()=>act('dig');
hide.onclick=()=>{shown=!shown;view.src=shown?frameUrl:'about:blank';hide.textContent=shown?'Close view':'Reopen view';};
reconnect.onclick=()=>command('reconnect').catch(e=>activity.textContent=e.message);
async function refresh(){try{const response=await fetch('/state');if(!response.ok)throw Error('Disconnected');const r=await response.json();sid=r.session_id;revision=r.state.revision;identity.textContent=`${r.state.character} · Minecraft ${r.state.game_version} · practice-world · session ${sid}`;
const u=r.state.viewer_url;if(u!==frameUrl){frameUrl=u;if(shown)view.src=u||'about:blank';}
if(activity.textContent==='Connecting…')activity.textContent='Connected — ready.';
if(r.state.active)activity.textContent='Working'+(shown?'':' with view closed')+'…';
const outcome=r.outcomes.find(e=>e.request_id===pending);if(outcome){activity.textContent=outcome.type==='failed'?'Action ended: '+outcome.error:'Completed — '+outcome.result.observed;pending=null;}
statusText.textContent=JSON.stringify({connected:r.state.ready,position:r.state.position,active:r.state.active,queued:r.state.queued,players:r.state.players,viewer:!r.state.viewer_clients?'not connected — bot work continues':shown?'connected':'closed — bot work continues'},null,2);
}catch(e){statusText.textContent='Connection status unavailable. Do not assume the bot has stopped.';}setTimeout(refresh,500);}refresh();
</script></body></html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--accept-eula",
        action="store_true",
        help="Owner accepts Minecraft EULA for the NEW practice server",
    )
    parser.add_argument("--port", type=int, default=25575)
    parser.add_argument("--ui-port", type=int, default=8768)
    args = parser.parse_args()
    server = PracticeServer(port=args.port)
    bridge = None
    http = None
    token = secrets.token_urlsafe(32)
    done = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: done.set())
    try:
        server.start(accept_eula=args.accept_eula)
        bridge = MinecraftBridge()
        bridge.connect(port=args.port)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def respond(self, code, value, kind="application/json"):
                data = (
                    value.encode()
                    if isinstance(value, str)
                    else json.dumps(value).encode()
                )
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def allowed(self):
                host = f"127.0.0.1:{args.ui_port}"
                return (
                    self.headers.get("Host") == host
                    and self.headers.get("Origin", f"http://{host}") == f"http://{host}"
                )

            def do_GET(self):
                if not self.allowed():
                    return self.respond(403, {"error": "local_origin_required"})
                try:
                    if self.path == "/":
                        return self.respond(
                            200,
                            PAGE.replace("TOKEN_VALUE", token),
                            "text/html; charset=utf-8",
                        )
                    if self.path == "/state":
                        return self.respond(
                            200,
                            {
                                **bridge.snapshot(),
                                "outcomes": [
                                    e
                                    for e in bridge.events_after()
                                    if e["type"] == "failed"
                                    or e.get("result", {}).get("observed")
                                ][-20:],
                            },
                        )
                    if self.path == "/events":
                        return self.respond(200, bridge.events_after())
                    self.respond(404, {})
                except Exception as exc:
                    self.respond(503, {"error": str(exc)})

            def do_POST(self):
                if (
                    self.path != "/command"
                    or not self.allowed()
                    or not secrets.compare_digest(
                        self.headers.get("X-Companion-Token", ""), token
                    )
                ):
                    return self.respond(403, {"error": "local_authority_required"})
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= 8192:
                        return self.respond(400, {"error": "invalid_request_size"})
                    request = json.loads(self.rfile.read(size))
                    if request.get("session_id") != bridge.session_id:
                        raise ValueError("stale_session")
                    op = request["op"]
                    if op == "cancel":
                        result = bridge.stop(session_id=request["session_id"])
                    elif op == "reconnect":
                        result = bridge.reconnect(
                            expected_session_id=request["session_id"], port=args.port
                        )
                    elif op in {"move", "dig", "execute"}:
                        state = bridge.observe()
                        if op == "execute":
                            action = request["args"]
                        else:
                            target = dict(state["position"])
                            if op == "move":
                                target["x"] += 5
                            else:
                                target["x"] += 1
                                target["y"] -= 1
                            action = {"action": op, "target": target}
                        rid, _ = bridge.submit(
                            "execute",
                            action,
                            revision=request["revision"],
                            session_id=request["session_id"],
                            timeout_ms=15000,
                        )
                        result = {"request_id": rid, "status": "submitted"}
                    else:
                        raise ValueError("unknown_operation")
                    self.respond(200, result)
                except Exception as exc:
                    self.respond(400, {"error": str(exc)})

        http = ThreadingHTTPServer(("127.0.0.1", args.ui_port), Handler)
        threading.Thread(target=http.serve_forever, daemon=True).start()
        print(
            json.dumps(
                {
                    "url": f"http://127.0.0.1:{args.ui_port}",
                    "session_id": bridge.session_id,
                    "server_pid": server.process.pid,
                    "worker_pid": bridge.process.pid,
                    "world": str(server.home),
                }
            ),
            flush=True,
        )
        done.wait()
    finally:
        if http:
            http.shutdown()
            http.server_close()
        if bridge:
            bridge.close()
        server.close()


if __name__ == "__main__":
    main()
