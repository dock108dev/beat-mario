"""Experimental panel in ordinary Companion; direct control stays available."""

import html
import json


def render_camera_practice(state, *, csrf_token):
    token = html.escape(csrf_token, quote=True)
    initial = html.escape(json.dumps(state), quote=True)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Camera practice · Game Companion</title>
<style>body{{font:16px/1.5 system-ui;background:#eef3f1;color:#16372b;margin:0}}main{{max-width:850px;margin:auto;padding:24px}}section{{background:white;border-radius:16px;padding:20px;margin:16px 0}}button,input,select,textarea{{font:inherit;padding:10px;margin:4px}}button{{cursor:pointer}}button:disabled{{opacity:.5}}.controls{{position:sticky;top:0;background:#eef3f1;padding:12px;z-index:2}}pre{{white-space:pre-wrap}}label{{display:block}}textarea{{width:90%}}</style></head>
<body><main id="camera-practice" data-csrf="{token}" data-state="{initial}"><a href="/">Choose a game</a><h1>Minecraft camera practice</h1>
<p>Experimental · disposable Creative world only. Native practice is disabled pending a brief focused smoke and unresolved motion review. Setup and profiles remain usable.</p><a href="/setup">Setup & saved profiles</a> · <a href="/help">Help & feedback</a>
<div class="controls"><button id="camera-stop" data-action="stop">Stop</button><button id="camera-reclaim" data-action="reclaim">Take control</button>
<strong id="camera-state"></strong><p id="camera-error" role="alert"></p></div>
<section><h2>Calibrate your disposable world</h2><p>Restore the supported settings in Setup, stand on flat ground, show F3, and choose the exact current Minecraft window. Calibration measures eight short directional pulses plus separate capture preparation. It grants no future input authority.</p><button data-action="windows">Refresh game windows</button><select id="camera-window"></select><label><input type="checkbox" id="camera-disposable"> This is a disposable Creative world; the Mac is available for exclusive input.</label><button data-action="calibrate" disabled>Start calibration (currently unavailable)</button></section>
<section><h2>Saved calibration in the current session</h2><label>Exact practice session<select id="camera-session"></select></label><button id="camera-connect" data-action="connect">Connect practice</button><p id="camera-reason"></p></section>
<section><h2>Camera goal</h2><label>Heading (−180° to 180°)<input type="number" id="camera-heading" value="3" min="-180" max="180" step="0.1"></label>
<label>Pitch (−90° to 90°)<input type="number" id="camera-pitch" value="0" min="-90" max="90" step="0.1"></label>
<p>Review and Start focus the selected practice window and may resume its visible pause menu. Start includes a separate capture preparation: up to two four-unit yaw probes, 240 ms of reserved input and 8 seconds total. This may turn the view up to 1.2° before the goal begins. Every probe and any partial rotation are saved. Failed preparation stops safely.</p>
<p>The absolute camera goal then has up to 12 small pulses. Preparation and correction are reported separately. No movement, placement or building.</p>
<button id="camera-review" data-action="review">Review preparation and goal</button><button id="camera-start" data-action="start" disabled>Start reviewed preparation and goal</button>
<button id="camera-chat" data-action="chat">Enter chat safely</button><textarea id="camera-notes" disabled placeholder="Practice notes"></textarea></section>
<section><h2>Result and saved attempts</h2><p id="camera-result"></p><ol id="camera-history"></ol><details><summary>Evidence and limits</summary><pre id="camera-details"></pre></details></section></main>
<script src="/assets/camera-practice.js" defer></script></body></html>'''


CAMERA_PRACTICE_JS = r"""
(() => {
  const root=document.getElementById('camera-practice'), client=crypto.randomUUID();
  const el=id=>document.getElementById('camera-'+id);
  let generation=0, state={}, busy=false, sessions='';
  function paint(s) {
    state=s; el('state').textContent=s.stage==='readiness_preparation'?'Preparing camera capture':s.state; el('reason').textContent=s.reason;
    const signature=JSON.stringify(s.sessions);
    if (signature!==sessions) { sessions=signature; el('session').replaceChildren(...s.sessions.map(r=>{
      const o=document.createElement('option'); o.value=r.id; o.textContent=`${r.world} · PID ${r.process_id} · window ${r.window_id}`;return o;
    })); if(s.selected)el('session').value=s.selected; }
    el('start').disabled=s.busy||!s.review||!s.native_enabled;
    el('review').disabled=s.busy||!s.native_enabled;
    const chosen=el('window').value;
    el('window').replaceChildren(...(s.windows||[]).map(r=>{const o=document.createElement('option');o.value=JSON.stringify(r);o.textContent=r.label;return o;}));
    if(chosen)el('window').value=chosen;
    for(const id of ['heading','pitch','connect'])el(id).disabled=s.busy;
    const prep=s.result?.readiness_preparation;
    el('result').textContent=s.result ? `${s.result.status}; visible handback ${s.result.neutral_handback_confirmed?'confirmed':'unconfirmed'}${prep?`; separate preparation: ${prep.pulses} probes, observed rotation ${JSON.stringify(prep.observed_rotation)}°`:''}`:'No attempt yet';
    el('history').replaceChildren(...s.history.map(r=>{const li=document.createElement('li');li.textContent=`${r.attempt_id}: ${r.status}`;return li;}));
    el('details').textContent=JSON.stringify({review:s.review,readiness:s.readiness,release:s.release,result:s.result},null,2);
  }
  async function send(action, extra={}) {
    const priority=['stop','reclaim','chat','edit','disconnect'].includes(action);
    const controlStarted=performance.now();
    const ticket=priority?++generation:generation;
    if(priority)el('start').disabled=true;
    const payload={client_id:client,session_id:el('session').value,heading:el('heading').value,pitch:el('pitch').value,selection:el('window').value?JSON.parse(el('window').value):null,disposable_confirmation:el('disposable').checked,...extra};
    const response=await fetch('/api/camera-practice',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:new URLSearchParams({csrf_token:root.dataset.csrf,action,payload:JSON.stringify(payload)})});
    const s=await response.json(); if(ticket!==generation)return s;
    if(!response.ok||s.error)throw Error(s.error||'Practice action failed');
    paint(s);
    if(priority){root.dataset.controlAcknowledgment=JSON.stringify({action,ui_ack_ms:performance.now()-controlStarted,epoch:s.epoch,busy:s.busy,native_release:s.release,wall_ack_ms:Date.now()});}
    return s;
  }
  root.addEventListener('click',async event=>{
    const button=event.target.closest('[data-action]'); if(!button)return;
    try {el('error').textContent=''; const s=await send(button.dataset.action);
      if(button.dataset.action==='chat'&&!s.busy&&s.release?.motion_worker_reaped){el('notes').disabled=false;el('notes').focus();}
      if(button.dataset.action==='start')el('notes').disabled=true;
    }catch(error){el('error').textContent=error.message;}
  });
  for(const id of ['heading','pitch'])el(id).addEventListener('input',()=>send('edit').catch(e=>el('error').textContent=e.message));
  setInterval(()=>send('heartbeat').catch(()=>{}),700);
  setInterval(async()=>{if(busy)return;busy=true;const ticket=generation;try{const s=await(await fetch('/api/camera-practice',{cache:'no-store'})).json();if(ticket===generation)paint(s);}finally{busy=false;}},250);
  window.addEventListener('pagehide',()=>navigator.sendBeacon('/api/camera-practice',new URLSearchParams({csrf_token:root.dataset.csrf,action:'disconnect',payload:JSON.stringify({client_id:client})})));
  paint(JSON.parse(root.dataset.state));
})();
"""
