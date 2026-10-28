"""Incrementally updated product surface; polling never replaces the composer."""

from html import escape


def render_minecraft_chat(token, *, selected=False):
    return PAGE.replace("TOKEN_VALUE", escape(token, quote=True)).replace(
        "SELECTED_VALUE", "true" if selected else "false"
    )


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Game Companion</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#101916;color:#eaf0ec;font:16px system-ui}header{position:sticky;top:0;z-index:2;background:#101916;height:76px;display:flex;align-items:center;gap:22px;padding:16px 26px;border-bottom:1px solid #36443c}h1{font-size:20px;margin:0}button,select,textarea{font:inherit;color:inherit;background:#263a30;border:1px solid #4e6457;border-radius:9px;padding:10px 14px}button{cursor:pointer}button:disabled{opacity:.5}#stop{margin-left:auto;background:#efaa96;color:#29140e;font-weight:700}main{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(330px,1fr);height:calc(100vh - 76px);gap:20px;padding:22px}.world{min-width:0;display:flex;flex-direction:column;min-height:0}iframe{width:100%;flex:1;min-height:200px;border:1px solid #36443c;border-radius:12px;background:#17231c}.meta{font-size:14px;color:#b6c9bc}#activity{font-weight:600;min-height:24px}.toolbar{display:flex;gap:10px;margin:12px 0}.chat{min-width:0;display:flex;min-height:0;flex-direction:column;border:1px solid #36443c;border-radius:12px;padding:18px}h2{font-size:18px;margin:0 0 14px}#messages{overflow:auto;flex:1;min-height:100px;scroll-behavior:auto}.message{white-space:pre-wrap;line-height:1.5;margin:0 0 14px;padding:12px;border-radius:10px;background:#1b2a22}.user{background:#314b3c;margin-left:30px}.role{display:block;font-size:12px;color:#b9cbbd;margin-bottom:5px}textarea{width:100%;resize:vertical;min-height:80px}form{margin-top:12px}form button{margin-top:8px;background:#c2e3b5;color:#142217}#error{color:#ffbaaa;white-space:pre-wrap}#pending{min-height:22px}.status{display:flex;justify-content:space-between;gap:12px}a{color:#b6dbaa}@media(max-width:800px){main{display:flex;flex-direction:column;height:auto}.world{height:auto}.world iframe{height:42vh;flex:none}.chat{height:70vh}header{gap:8px;padding:10px;flex-wrap:wrap;height:auto}h1{font-size:15px}header select{max-width:140px}main{padding:12px}#stop{padding:10px}}
</style></head><body>
<header><h1>Game Companion</h1><select id="game" aria-label="Game"><option value="">Choose a game</option><option value="minecraft">Minecraft</option></select><select id="world" aria-label="World"><option value="creative">Creative practice</option><option value="survival">Survival practice</option></select><button id="stop">Stop</button></header>
<main><section class="world"><div class="status"><h2 id="identity">Minecraft</h2><span id="connection" class="meta">Not connected</span></div><iframe id="view" title="Live Minecraft world" src="about:blank"></iframe><div class="toolbar"><button id="toggle">Close view</button><button id="reconnect">Reconnect</button></div><div id="viewer-status" class="meta"></div><p id="activity" role="status">Choose Minecraft to connect.</p><div id="progress" class="meta"></div><div id="goal" class="meta"></div><details><summary>Session details</summary><pre id="details"></pre><a href="/legacy-games">Engineering & historical games</a></details></section>
<section class="chat"><div class="status"><h2>Chat</h2><span id="codex" class="meta">Checking Codex…</span></div><div id="messages" aria-label="Conversation"></div><div id="pending" class="meta" role="status"></div><div id="error" role="alert"></div><form id="compose"><label for="draft" class="meta">Message your companion</label><textarea id="draft" maxlength="2000" placeholder="Walk north, follow a player, or ask about the world…"></textarea><button id="send" type="submit">Send</button></form></section></main>
<script>
const token='TOKEN_VALUE', $=id=>document.getElementById(id);let sid=null,url=null,shown=true,known=new Set(),sending=false,localError='';
$('draft').value=sessionStorage.getItem('minecraft-draft')||'';
$('draft').oninput=()=>sessionStorage.setItem('minecraft-draft',$('draft').value);
async function command(action,extra={}){const r=await fetch('/api/minecraft/chat',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({csrf_token:token,action,session_id:sid||'',...extra})});const value=await r.json();if(!r.ok||value.error)throw Error(value.error||'Request failed');localError='';return value;}
function failure(e){localError=e.message;$('error').textContent=e.message;}
$('game').onchange=()=>{if($('game').value==='minecraft')command('connect',{world:$('world').value}).catch(failure);};
$('stop').onclick=()=>{ $('activity').textContent='Stopping…';command('stop').catch(failure);};
$('reconnect').onclick=()=>command('reconnect').catch(failure);
$('toggle').onclick=()=>{shown=!shown;$('view').src=shown?(url||'about:blank'):'about:blank';$('toggle').textContent=shown?'Close view':'Reopen view';};
$('compose').onsubmit=async e=>{e.preventDefault();if(sending)return;const text=$('draft').value;if(!text.trim())return;sending=true;try{await command('message',{text,request_id:crypto.randomUUID()});if($('draft').value===text){$('draft').value='';sessionStorage.removeItem('minecraft-draft');}$('error').textContent='';}catch(e){failure(e);}finally{sending=false;}};
async function refresh(){try{const r=await fetch('/api/minecraft/chat');if(!r.ok)throw Error('Connection status unavailable; use Stop and check the app.');const s=await r.json();sid=s.session_id;$('world').disabled=!!sid||s.connecting;if(sid)$('game').value='minecraft';const state=s.state;if(state.game_mode)$('world').value=state.game_mode;
$('connection').textContent=s.connecting?'Connecting…':state.ready?'Connected':'Disconnected';$('identity').textContent=state.character?state.character+' · '+(state.game_mode||'Practice')+' world':'Minecraft';$('activity').textContent=s.activity;$('progress').textContent=s.progress||'';$('goal').textContent=s.goal?'Goal: '+s.goal:'';
$('codex').textContent=s.codex.message;$('pending').textContent=s.busy?'Codex is thinking · gameplay continues':'';$('send').disabled=s.busy||!state.ready||s.connecting;$('reconnect').disabled=s.connecting;
$('error').textContent=s.error||localError;
if(state.viewer_url!==url){url=state.viewer_url;if(shown)$('view').src=url||'about:blank';}
$('viewer-status').textContent=!shown?'View closed · bot connection stays active':state.viewer_clients?'Live bot view':state.ready?'Viewer unavailable or loading · bot connection remains active':'';
$('details').textContent=JSON.stringify({session:sid,version:state.game_version,position:state.position,players:state.players,revision:state.revision},null,2);
const box=$('messages'),bottom=box.scrollHeight-box.scrollTop-box.clientHeight<50;
for(const m of s.messages){if(known.has(m.id))continue;known.add(m.id);const div=document.createElement('div');div.className='message '+m.role;const name=document.createElement('span');name.className='role';name.textContent=m.role==='user'?'You':'Companion';div.append(name,document.createTextNode(m.text));box.append(div);}if(bottom)box.scrollTop=box.scrollHeight;
}catch(e){failure(e);}setTimeout(refresh,400);}
if(SELECTED_VALUE){$('game').value='minecraft';command('connect',{world:$('world').value}).catch(failure);}refresh();
</script></body></html>"""


CHAT_JS = (
    PAGE.split("<script>", 1)[1]
    .split("</script>", 1)[0]
    .replace("const token='TOKEN_VALUE'", "const token=document.body.dataset.token")
    .replace("if(SELECTED_VALUE)", "if(document.body.dataset.selected==='true')")
)
PAGE = (
    PAGE.split("<script>", 1)[0].replace(
        "<body>", '<body data-token="TOKEN_VALUE" data-selected="SELECTED_VALUE">'
    )
    + '<script src="/assets/minecraft-chat.js" defer></script></body></html>'
)
