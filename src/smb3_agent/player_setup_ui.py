"""Player-facing setup, guidance and local feedback, separate from contributor tools."""

import html
import json
from smb3_agent.player_store import VERSION


def render_player_setup(state, *, csrf_token="", minecraft=False):
    def esc(v):
        return html.escape(str(v), quote=True)
    initial = esc(json.dumps(state))
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Game Companion · Setup</title><style>
body{{font:16px/1.5 system-ui;color:#17392e;background:#eef3f1;margin:0}}main{{max-width:1050px;margin:auto;padding:24px}}section{{background:white;padding:22px;border-radius:16px;margin:16px 0}}h1,h2{{line-height:1.2}}label{{display:block;margin:10px 0}}input,textarea,select,button{{font:inherit;padding:10px;border:1px solid #a1b9ae;border-radius:8px}}textarea{{width:95%;min-height:80px}}button,a{{cursor:pointer}}button:disabled{{opacity:.5;cursor:default}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.controls{{position:sticky;top:0;background:#eef3f1;padding:12px;z-index:2}}.row{{display:flex;gap:12px;flex-wrap:wrap}}.warning{{color:#8b3122}}.primary{{background:#24583f;color:white}}#error{{color:#8b3122}}
</style></head><body><main id="player-setup" data-state="{initial}" data-csrf="{esc(csrf_token)}">
<header><a href="/">Games</a> · <a href="/setup">Setup & profiles</a> · <a href="/help">Guide & feedback</a><h1>{"Minecraft Creative workspace" if minecraft else "Welcome to Game Companion"}</h1><p>Private beta {VERSION} · local profiles and diagnostics · typed conversation</p></header>
<div class="controls"><button data-action="stop">Stop</button> <button data-action="reclaim">Take control</button> <strong>You control the game unless you explicitly review and Start supported work.</strong> <button id="quit">Quit Game Companion</button><p id="error" role="alert"></p><p id="reason" role="status"></p></div>
<section id="minecraft-onboarding" hidden><h2>Minecraft setup progress</h2><p id="mc-setup-title" role="status"></p><p id="mc-setup-next"></p><ol id="mc-setup-steps"></ol><h3>Available tasks</h3><ul id="mc-available-tasks"></ul><h3>Tasks still being completed</h3><ul id="mc-blocked-tasks"></ul></section>
<section><h2>1. Choose and save your setup</h2><p>Choose a supported template. Settings below describe implemented configurations. Editing a name or notes does not teach new skills.</p>
<label>Saved profiles <select id="saved"></select></label><button data-action="open">Open saved profile</button> <button data-action="duplicate">Duplicate</button>
<form id="save-form"><label>Game <select id="game"><option value="minecraft">Minecraft Java Creative</option><option value="openttd">OpenTTD</option></select></label>
<label>Profile name <input id="name" maxlength="80" value="My disposable practice"></label><label>Notes / future corrections <textarea id="notes" maxlength="2000"></textarea></label>
<label><input type="checkbox" id="update">Update the opened profile (otherwise save a new one)</label><button class="primary">Save profile</button></form><pre id="settings"></pre><p id="features"></p>
<details><summary>Profile transfer</summary><p>Export contains configuration and your notes. Inspect it before sharing. No live window, authority, credentials or screenshots are exported. Import creates a new local copy.</p><button data-action="export">Preview export</button><textarea id="transfer" placeholder="Paste exported profile JSON"></textarea><button data-action="import">Import as new profile</button></details></section>
<section><h2>2. Connect your game and permissions</h2><p>Install the game separately. Use a disposable save/world. Keep the exact window visible and unobscured. A saved profile never restores input permission, a window connection or a reviewed plan.</p>
<p>macOS System Settings → Privacy & Security → Screen & System Audio Recording, then Accessibility: enable Game Companion. Quit and reopen after changing permissions. The app checks capture/input readiness when you connect; it does not silently request permissions.</p>
<p>Minecraft: Java 26.3 vanilla; Creative; flat practice area; always-visible pose/target HUD; default font; window 854 × 508 points with native 1× or Retina 2× capture; sensitivity 50%; FOV 70; inversion off; smooth-camera binding unassigned; GUI scale Auto; fullscreen off. Other configurations remain unavailable.</p>
<p>For Minecraft block work, first quit Minecraft and choose <button data-action="minecraft_settings">Apply supported Minecraft settings</button>. This backs up your preferences, enables targeted-block HUD and advanced tooltips, and selects the controls above. Restart Minecraft afterward. Choose Building Blocks in the Creative inventory and put one supported full block in the selected hotbar slot.</p>
<p>OpenTTD: 15.3, English, paused disposable company, 1280 × 1024, Finances visible, initial loan and cash £100,000 each. Local Ollama with gemma3:4b must be installed and running.</p>
<div class="row"><a id="workspace" href="/minecraft">Open game workspace</a><span>Use the Minecraft connection controls below for calibration and disposable practice.</span></div>
<div id="minecraft-connection"><h3>Minecraft connection and practice</h3>
<button data-action="windows">Refresh Minecraft windows</button><select id="mc-window"></select><label>Display <select id="mc-display"></select></label><button data-action="arrange">Move and size selected window</button>
<label><input type="checkbox" id="mc-disposable"> This is a disposable Creative world and the Mac is available for exclusive input.</label>
<button data-action="calibrate" id="mc-calibrate">Calibrate camera</button>
<p>Calibration opens and closes the inventory to check Creative, then measures eight small directional camera responses. Every emitter is canceled and the visible view must settle. Keep this page open.</p>
<select id="mc-calibration"></select><button data-action="connect">Connect current calibration</button>
<h3>Choose your work region</h3><p>For the 7 × 3 wall, stand on a flat platform one block above the wall's ground, opposite its center. Keep all seven columns within reach. Practice away from animals, mobs and other moving objects; displacement stops work. Select stone, bricks, oak planks or cobblestone in your hotbar. Point at the ground block below the center doorway. The app inspects the selected slot's tooltip; it does not choose items for you.</p>
<label>Wall direction <select id="mc-axis"><option value="x">East / west (X)</option><option value="z">North / south (Z)</option></select></label>
<button data-action="scope">Check visible block and scope</button><button data-action="protect">Mark pointed block protected</button><button data-action="save_workspace">Save checked region in this profile</button>
<pre id="mc-status"></pre><p>Point at each exposed block of a structure and choose Mark pointed block protected. The marked blocks appear above. They are inspected before additions and again at the end.</p>
<details><summary>Advanced: edit protected coordinates</summary><p>This optional list describes protection intent. Coordinates alone do not prove protection; the app still inspects the blocks.</p><label>Protected cells (JSON list, for example [[3,-60,8]]) <input id="mc-protected" value="[]" maxlength="2000"></label></details>
</div><p class="warning" id="native-limit"></p><p>Captured-mouse automation competes with ordinary Mac input. Use it only when the Mac is available; do not type or move the mouse during work. Stop / Take control revoke input independently of the model.</p></section>
<section><h2>3. Ask, review, Start, recover</h2><p>Tell explains supported behavior without input. Show reviews the bounded proposal. Do starts only an executable reviewed plan. Corrections invalidate the earlier review and apply to future work. Uncertain outcomes remain partial.</p>
<p>Examples: “Repay exactly £10,000 once. Do not borrow.” “Move forward 0.25 blocks.” “Aim at the visible reachable face.” “Place one stone block.” “Finish a 7 by 3 wall with a centered doorway; leave the marked structure alone.” Only tasks shown as checked and available can Start. Unavailable requests remain proposals or ask for missing setup.</p>
<button data-action="chat">Enter chat safely</button><form id="request-form"><label>Your Minecraft request or question <textarea id="request" maxlength="2000" disabled></textarea></label><button>Send</button></form>
<ol id="messages"></ol><pre id="plan"></pre><button data-action="review">Review current scope</button><button data-action="start" id="mc-start" disabled>Start reviewed task</button><h3>Saved outcomes</h3><ol id="history"></ol>
<p>Recovery: Take control → wait for confirmed release → restore the disposable world if effects are unknown → reconnect the exact window → inspect fresh state → send and review a new request. Do not retry an unverified placement blindly.</p></section>
<section><h2>4. Help and report a problem</h2><p>Missing game: launch it and refresh its window list. Missing capture/input: enable the app permissions and reopen. Unknown HUD or target: restore the displayed settings and clear visibility. Model unavailable: start Ollama and install gemma3:4b. Unconfirmed handback: stop using automation and inspect diagnostics before another attempt.</p>
<p>Describe the build version, game/settings, request, expected result, actual result, whether Stop worked, and steps to repeat it. Use a disposable game. The report includes only selected configuration and recent sanitized outcomes plus your text. Review it here before manually sending it to the owner through your agreed channel; nothing is uploaded automatically.</p>
<form id="report-form"><label>Feedback <textarea id="feedback" maxlength="4000"></textarea></label><button>Save local report & preview</button></form><pre id="report"></pre><p id="report-path"></p><details><summary>Local diagnostics and data location</summary><pre id="diagnostics"></pre></details></section></main><script src="/assets/player-setup.js" defer></script></body></html>'''


PLAYER_SETUP_JS = r"""
(() => {
const root=document.getElementById('player-setup'), el=id=>document.getElementById(id);let state={},generation=0;const client=crypto.randomUUID();let polling=false,protectedDirty=false,protectedEditVersion=0,protectionPending=null;
function paint(s){state=s;
const mc=s.minecraft, c=mc?.camera;el('minecraft-connection').hidden=!mc||s.selected?.game!=='minecraft';
const onboarding=s.minecraft_onboarding;el('minecraft-onboarding').hidden=!onboarding||el('game').value!=='minecraft';
if(onboarding){el('mc-setup-title').textContent=onboarding.title;el('mc-setup-next').textContent=onboarding.next_action;
el('mc-setup-steps').replaceChildren(...onboarding.steps.map(step=>{const li=document.createElement('li'),status={done:'Complete',next:'Next',pending:'Later',unavailable:'Unavailable'}[step.status]||'Pending';li.textContent=`${step.label} · ${status}: ${step.detail}`;return li;}));
for(const [id,tasks] of [['mc-available-tasks',onboarding.available_tasks],['mc-blocked-tasks',onboarding.blocked_tasks]])el(id).replaceChildren(...tasks.map(task=>{const li=document.createElement('li');li.textContent=task;return li;}));}
function options(id,rows,encode,label){const old=el(id).value;el(id).replaceChildren(...rows.map(r=>{const o=document.createElement('option');o.value=encode(r);o.textContent=label(r);return o;}));if([...el(id).options].some(o=>o.value===old))el(id).value=old;}
options('mc-window',c?.windows||[],r=>JSON.stringify(r),r=>r.label+' · window '+r.window_id);
options('mc-display',mc?.displays||[],r=>r.id,r=>r.label);
options('mc-calibration',c?.sessions||[],r=>r.id,r=>r.world+' · PID '+r.process_id);
el('mc-calibrate').disabled=!mc?.features?.calibrate||mc.busy;
el('mc-start').disabled=!s.reviewed||!s.plan?.executable||mc?.busy;
const region=mc?.scope, progress=mc?.result;
if(protectionPending&&!mc?.busy){if(mc?.state==='connected'&&protectedEditVersion===protectionPending.editVersion&&(protectionPending.action==='scope'||!protectionPending.wasDirty))protectedDirty=false;protectionPending=null;}
if(region&&!protectedDirty)el('mc-protected').value=JSON.stringify(region.protected);
const scopeText=region?`Wall origin (${region.anchor.join(', ')}), direction ${region.axis.toUpperCase()}. Material: ${region.material.replace('minecraft:','').replaceAll('_',' ')}.\nProtected blocks: ${region.protected.map(v=>'('+v.join(', ')+')').join('; ')||'None marked'}. Stop point: (${region.stop_point.join(', ')}).`:'No live work region checked. Saved coordinates require a fresh inspection.';
const resultText=progress?`${progress.status}: ${progress.reason||'Observed task completed; input released.'}\n${progress.placed?`${progress.placed.length} new blocks; ${(progress.existing||[]).length} already correct; ${(progress.unknown||[]).length} unknown; ${(progress.final_verified||[]).length} cells in final inspection; ${(progress.doorway_empty||[]).length}/2 doorway cells observed empty; ${(progress.protected_verified||[]).length} protected blocks rechecked.`:''}`:'';
el('mc-status').textContent=mc?`${mc.state}: ${mc.reason}\n${c?.reason||''}\nAvailable: ${Object.entries(mc.features).filter(([k,v])=>v).map(([k])=>k).join(', ')}\nUnavailable: ${Object.entries(mc.features).filter(([k,v])=>!v).map(([k])=>k).join(', ')}\n${scopeText}\n${resultText}`:'';
el('reason').textContent=s.reason;el('native-limit').textContent=s.native_reason;
const selected=el('saved').value;el('saved').replaceChildren(...s.profiles.map(p=>{const o=document.createElement('option');o.value=p.id;o.textContent=p.name+' · '+p.game;return o;}));
if(s.profiles.some(p=>p.id===selected))el('saved').value=selected;
if(s.selected){el('saved').value=s.selected.id;el('workspace').href=s.templates[s.selected.game].surface;}
el('settings').textContent=el('game').value==='minecraft'?'Minecraft Java 26.3 vanilla · English, default font\n854 × 508 point window; native 1× or 2× capture\nSensitivity 50%, FOV 70, GUI Auto, inversion off\nAlways-visible pose/target HUD; advanced tooltips\nNo model installation required for bounded Minecraft requests.':'OpenTTD 15.3 · 1280 × 1024 window\nLocal Ollama model: gemma3:4b';
el('features').textContent=s.templates[el('game').value].supported.join(' ')+' Unavailable: '+s.templates[el('game').value].unavailable.join('; ');
el('messages').replaceChildren(...s.messages.map(m=>{const li=document.createElement('li');li.textContent=m.role+': '+m.text;return li;}));
el('plan').textContent=s.plan?`${s.plan.request}\nScope: ${s.plan.scope}\nExcluded: ${s.plan.exclusions.join(', ')}\nFuture corrections: ${s.plan.future_corrections||'None'}\n${s.plan.missing}
${s.plan.world_scope?`Work region: origin (${s.plan.world_scope.anchor.join(', ')}), direction ${s.plan.world_scope.axis.toUpperCase()}, ${s.plan.world_scope.material.replace('minecraft:','').replaceAll('_',' ')}.\nProtected blocks: ${s.plan.world_scope.protected.length}. Return near (${s.plan.world_scope.stop_point.join(', ')}).`:Object.entries(s.plan.parameters||{}).filter(([key])=>!['source','world_scope'].includes(key)).map(([key,value])=>key.replaceAll('_',' ')+': '+(Array.isArray(value)?value.join(', '):value)).join(' · ')}
Budget: ${(s.plan.total_budget||s.plan.skill).max_seconds}s, ${(s.plan.total_budget||s.plan.skill).max_steps} steps, ${(s.plan.total_budget||s.plan.skill).max_input_ms}ms input`:'No proposal. Questions and unsupported requests issue no input.';
el('history').replaceChildren(...s.history.map(h=>{const li=document.createElement('li');li.textContent=h.status+': '+(h.reason||'Observed task completed')+(h.placed?' · '+h.placed.length+' new, '+(h.existing||[]).length+' already present, '+(h.unknown||[]).length+' unknown, '+(h.doorway_empty||[]).length+' empty doorway cells':'');return li;}));
el('diagnostics').textContent=JSON.stringify({version:s.version,data_location:s.data_location,native_minecraft:s.native_reason,profile:s.selected?.id},null,2);
}
async function send(action,p={}){const ticket=++generation,editVersion=protectedEditVersion,wasDirty=protectedDirty;p={client_id:client,...p};if(['stop','reclaim','disconnect','start','calibrate','scope','protect'].includes(action)){el('request').disabled=true;el('request').blur();}
try{const r=await fetch('/api/player',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({csrf_token:root.dataset.csrf,action,payload:JSON.stringify(p)})});const s=await r.json();if(ticket!==generation)return;if(!r.ok)throw Error(s.error||'Action refused');el('error').textContent='';
if(s.export)el('transfer').value=JSON.stringify(s.export,null,2);else if(s.report){el('report').textContent=JSON.stringify(s.report,null,2);el('report-path').textContent=s.path;}else{if(['scope','protect'].includes(action))protectionPending={action,editVersion,wasDirty};paint(s);if(action==='chat'){el('request').disabled=false;el('request').focus();}if(['open','save','duplicate','import'].includes(action)){protectedDirty=false;protectionPending=null;protectedEditVersion++;el('game').value=s.selected.game;el('name').value=s.selected.name;el('notes').value=s.selected.notes;if(s.selected.workspace){el('mc-axis').value=s.selected.workspace.axis;el('mc-protected').value=JSON.stringify(s.selected.workspace.protected);}else{el('mc-protected').value='[]';}paint(s);}}
}catch(e){el('error').textContent=e.message;}}
root.addEventListener('click',e=>{const b=e.target.closest('button[data-action]');if(!b)return;
const action=b.dataset.action,p={};
// Immediate handback and chat must never depend on editable setup fields.
if(['stop','reclaim','disconnect','chat'].includes(action)){send(action);return;}
if(['open','duplicate','export'].includes(action))p.id=el('saved').value;
if(action==='import')p.json=el('transfer').value;
if(action==='review')p.plan_id=state.plan?.id;
if(['arrange','calibrate'].includes(action)){try{p.selection=el('mc-window').value?JSON.parse(el('mc-window').value):null;}catch(e){el('error').textContent='Refresh and choose the exact Minecraft window';return;}}
if(action==='arrange')p.display_id=Number(el('mc-display').value);
if(action==='connect')p.session_id=el('mc-calibration').value;
if(['calibrate','scope','protect','start'].includes(action))p.disposable_confirmation=el('mc-disposable').checked;
if(['scope','protect'].includes(action))p.axis=el('mc-axis').value;
if(action==='scope'){try{p.protected=JSON.parse(el('mc-protected').value);}catch(e){el('error').textContent='Protected cells must be a JSON list of coordinates';return;}}
send(action,p);});
el('save-form').addEventListener('submit',e=>{e.preventDefault();send('save',{id:el('update').checked?state.selected?.id:null,game:el('game').value,name:el('name').value,notes:el('notes').value});});
el('request-form').addEventListener('submit',e=>{e.preventDefault();send('message',{text:el('request').value});});
el('report-form').addEventListener('submit',e=>{e.preventDefault();send('report',{id:state.selected?.id,text:el('feedback').value});});
el('game').addEventListener('change',()=>{paint(state);send('edit');});
el('mc-protected').addEventListener('input',()=>{protectedDirty=true;protectedEditVersion++;});
el('quit').addEventListener('click',async()=>{try{const identity=await(await fetch('/api/delivery')).json();const r=await fetch('/api/delivery/shutdown',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({csrf_token:root.dataset.csrf,instance:identity.instance})});const result=await r.json();if(!r.ok||!result.cleanup_confirmed)throw Error('Shutdown is unconfirmed; inspect diagnostics');el('reason').textContent='Game Companion quit. Saved profiles and history remain.';}catch(e){el('error').textContent=e.message;}});
el('request').addEventListener('input',()=>{if(state.plan)send('edit');});
setInterval(async()=>{if(!state.minecraft||!state.selected||state.selected.game!=='minecraft')return;try{await fetch('/api/player',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({csrf_token:root.dataset.csrf,action:'heartbeat',payload:JSON.stringify({client_id:client})})});}catch(e){}},700);
setInterval(async()=>{if(polling)return;polling=true;const ticket=generation;try{const s=await(await fetch('/api/player',{cache:'no-store'})).json();if(ticket===generation)paint(s);}finally{polling=false;}},500);
window.addEventListener('pagehide',()=>navigator.sendBeacon('/api/player',new URLSearchParams({csrf_token:root.dataset.csrf,action:'disconnect',payload:JSON.stringify({client_id:client})})));
paint(JSON.parse(root.dataset.state));
})();
"""
