"""Profile workspace within the ordinary catalog/conversation product."""
import html
import json

from smb3_agent.glass_ui import GLASS_CSS


def render_profile_workspace(state, *, csrf_token="", selected=True):
    from smb3_agent.conversation_ui import CONVERSATION_CSS
    encoded = html.escape(json.dumps(state), quote=True)
    token = html.escape(csrf_token, quote=True)
    gate = "" if selected else f'''<section class="card"><p>Select OpenTTD from Games before connecting.</p>
<form action="/catalog-switch" method="post"><input type="hidden" name="csrf_token" value="{token}">
<input type="hidden" name="adapter_id" value="openttd"><button>Switch to OpenTTD</button></form></section>'''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenTTD · Game Companion</title><style>{CONVERSATION_CSS}{GLASS_CSS}
body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui}}main{{max-width:1100px;margin:auto;padding:18px}}
.card{{border:1px solid var(--line);border-radius:16px;padding:16px;background:var(--surface)}}button,input,select,textarea{{font:inherit}}button{{padding:10px 14px;border:1px solid var(--line);border-radius:10px;cursor:pointer}}button:disabled{{opacity:.5;cursor:default}}label{{display:block;margin:8px 0}}select,textarea{{width:100%;box-sizing:border-box}}textarea{{min-height:100px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.setup-row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.conversation-controls{{position:sticky;top:0;z-index:2}}.danger{{color:#8b2222}}.status{{font-weight:650}}.primary{{background:#234e3d;color:white}}@media(max-width:700px){{.setup-row{{grid-template-columns:1fr}}}}
</style></head><body><main><header><a href="/">Choose a game</a> · <a href="/setup">Profiles & setup</a> · <a href="/help">Help & feedback</a><h1>OpenTTD</h1>
<p>One supported task: repay £10,000 from the paused test company, then verify both balances and return control.</p></header>{gate}
<div id="profile-workspace" data-csrf="{token}" data-selected="{str(selected).lower()}" data-initial-state="{encoded}">
<div class="conversation-controls"><strong id="profile-owner">You control the game</strong>
<button data-action="stop" id="profile-stop">Stop</button><button data-action="reclaim" id="profile-reclaim" class="danger">Take control</button>
<p id="profile-error" role="alert" hidden></p></div><p id="profile-status" class="status" role="status"></p><p id="profile-reason"></p>
<details id="profile-connection" open><summary>Game connection and readiness</summary><section class="card">
<p>Open a fresh paused test game. In the game, use the coin menu → Finances. Keep the game visible beside this app, then return here.</p>
<button data-action="launch" id="profile-launch">Open fresh paused test game (engineering setup)</button><button data-action="windows">Refresh window list</button>
<form data-action="connect"><div class="setup-row"><label>Supported profile<select id="profile-profile" name="profile_id"></select></label>
<label>Exact game window<select id="profile-window" name="window"></select></label></div><label><input type="checkbox" id="profile-disposable"> I confirm this is a paused disposable company with the displayed supported settings.</label><button type="submit" id="profile-connect">Connect selected window</button></form>
<label>Display for supported window size<select id="profile-display"></select></label><button data-action="arrange">Set supported size on selected display</button><p id="profile-permissions"></p><p id="profile-connection-state"></p></section></details>
<section class="conversation-workspace"><div class="card conversation-chat"><h2>What should Companion do?</h2>
<button data-action="chat" id="profile-chat">Enter chat safely</button><p>Enter chat releases game input before enabling the text field. Start focuses the selected game and disables typing here.</p>
<form data-action="message"><label for="profile-draft">Your request</label><textarea id="profile-draft" name="text" disabled placeholder="Repay exactly £10,000 once. Do not borrow money."></textarea>
<button type="submit" id="profile-send" class="primary">Send request</button></form><ul id="profile-messages" class="conversation-transcript"></ul></div>
<div class="card conversation-plan"><h2>Your proposed action</h2><p id="profile-plan">Describe one task.</p><p id="profile-values"></p>
<p id="profile-limits">One repayment only. No borrowing, building, selling, demolishing, unpausing, saving or network play.</p>
<button data-action="review" id="profile-review">Review scope</button><button data-action="start" id="profile-start" class="primary">Start reviewed work</button>
<p id="profile-review-state"></p><h3>Result and remaining work</h3><p id="profile-outcome">No attempt yet.</p>
<details><summary>Saved results</summary><ol id="profile-history"></ol></details></div></section>
<details><summary>Timing, backend and connection diagnostics</summary><pre id="profile-diagnostics"></pre></details></div></main>
<script src="/assets/profile-conversation.js" defer></script></body></html>'''


PROFILE_CONVERSATION_JS = r'''
(() => {
  "use strict";
  const root = document.getElementById("profile-workspace"); if (!root) return;
  const api = "/api/profile/conversation", client = crypto.randomUUID();
  const node = id => document.getElementById(`profile-${id}`);
  let state = {}, generation = 0, polling = false, dirty = false, optionsSignature = "", messageSignature = "", historySignature = "";
  const busy = new Set(), priority = new Set(["stop","reclaim","chat","edit","ui_disconnect","cancel_pending"]);
  const text = (id, value) => { const copy = String(value ?? ""); if (node(id).textContent !== copy) node(id).textContent = copy; };
  function render(next) {
    state = next; root.dataset.state = state.state;
    text("status", state.state); text("reason", state.reason);
    text("owner", state.runtime?.owner === "agent" ? "Companion is playing" : "You control the game");
    const signature = JSON.stringify([state.profiles,state.windows]);
    if (signature !== optionsSignature) {
      optionsSignature = signature;
      for (const [id, rows] of [["profile",state.profiles || []],["window",state.windows || []]]) {
        const selected = node(id).value;
        const options = rows.map(row => { const option = document.createElement("option");
          option.value = id === "profile" ? row.id : JSON.stringify({pid:row.pid,started:row.started,window_id:row.window_id});
          option.textContent = row.label; return option; });
        node(id).replaceChildren(...options); if (options.some(option => option.value === selected)) node(id).value = selected;
      }
    }
    if(node("display")) {
      const chosen=node("display").value;
      node("display").replaceChildren(...(state.displays||[]).map(row=>{const o=document.createElement("option");o.value=String(row.id);o.textContent=row.label;return o;}));
      if(chosen)node("display").value=chosen;
    }
    const connected = state.connected && state.client_matches === client;
    const plan = state.plan, permissions = state.runtime?.permissions;
    node("chat").disabled = !connected;
    node("send").disabled = !connected || state.busy || node("draft").disabled;
    node("review").disabled = dirty || !connected || state.busy || !state.proposal_current;
    node("start").disabled = dirty || !connected || state.busy || !state.reviewed || !permissions?.input || !state.runtime?.neutralized;
    node("connect").disabled = !node("window").value || state.busy || root.dataset.selected !== "true";
    node("launch").disabled = !state.engineering_launcher_available || state.busy || root.dataset.selected !== "true";
    text("permissions", permissions ? `Screen capture: ${permissions.capture ? "ready" : "unavailable"}. Game input: ${permissions.input ? "ready" : "unavailable"}.` : "Connect to check screen and input readiness.");
    text("connection-state", state.selection ? `Selected window ${state.selection.window_id}; reopening always requires fresh checks.` : "No connected window.");
    text("plan", plan?.actions?.length ? "Repay £10,000 once; verify loan and cash each fall by exactly £10,000, then release input." : "No executable proposal. Describe a supported task.");
    const values = state.runtime?.values;
    text("values", values ? `Last observed loan: £${values.loan.toLocaleString()}. Cash: £${values.cash.toLocaleString()}. Start checks these again.` : "Balances have not been observed.");
    text("review-state", state.reviewed ? "Scope reviewed. Start authorizes only this single action after a fresh check." : "Review the current proposal before Start.");
    const outcome = state.outcome;
    text("outcome", outcome ? `${outcome.status === "completed" ? "Completed" : "Partial / stopped"}. ${outcome.reason || "Both balances verified."} ${outcome.after_values ? `Observed loan £${outcome.after_values.loan.toLocaleString()}; cash £${outcome.after_values.cash.toLocaleString()}.` : "Effects remain unknown."} ${outcome.release?.confirmed ? "Input released; control returned." : "Input release is unconfirmed."}` : "No attempt yet.");
    const messages = JSON.stringify(state.messages || []);
    if (messages !== messageSignature) { messageSignature = messages; node("messages").replaceChildren(...(state.messages || []).map(m => { const li=document.createElement("li"); li.textContent=`${m.role === "user" ? "You" : "Companion"}: ${m.text}`; return li; })); }
    const histories = JSON.stringify(state.history || []);
    if (histories !== historySignature) { historySignature=histories; node("history").replaceChildren(...(state.history || []).map(h => {const li=document.createElement("li");li.textContent=`${h.status}: ${h.reason || "Verified exact balance changes"}`;return li;})); }
    text("diagnostics", JSON.stringify(state.runtime, null, 2));
  }
  function error(message) { text("error", message); node("error").hidden = !message; }
  async function post(action, payload={}) {
    const response = await fetch(api,{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded;charset=UTF-8"},
      body:new URLSearchParams({csrf_token:root.dataset.csrf,action,payload:JSON.stringify({...payload,client_id:client})})});
    const next = await response.json(); if (!response.ok) throw new Error(next.error || "Action refused"); return next;
  }
  async function dispatch(action, payload={}) {
    if (busy.has(action) || (!priority.has(action) && busy.size)) return false;
    busy.add(action); const current=++generation, started=performance.now();
    if (["review","start"].includes(action)) Object.assign(payload,{expected_plan_id:state.plan?.plan_id,expected_revision:state.plan?.revision});
    if (action === "start") { node("draft").disabled=true; node("draft").blur(); }
    if (action === "message") { dirty=false;node("review").disabled=true; node("start").disabled=true; }
    try {
      const next=await post(action,payload), elapsed=performance.now()-started;
      if (current === generation) {render(next);error("");}
      if (next.control_receipt && ["stop","reclaim","chat"].includes(action)) {
        root.dataset.lastControlMilliseconds=String(elapsed);
        post("ui_timing",{control_id:next.control_receipt.control_id,milliseconds:elapsed}).catch(()=>{});
      }
      if (action === "chat" && current === generation && next.control_receipt?.confirmed && state.connected) {
        node("draft").disabled=false; node("draft").focus({preventScroll:true}); node("send").disabled=state.busy;
      }
      return true;
    } catch(failure) { if(current===generation) error(failure.message); return false; }
    finally {busy.delete(action);}
  }
  root.addEventListener("click",event=>{const button=event.target.closest("button[data-action]");if(button) {const action=button.dataset.action;const p=action==="arrange"?{selection:JSON.parse(node("window").value||"{}"),display_id:Number(node("display").value)}:{};dispatch(action,p);}});
  root.addEventListener("submit",event=>{event.preventDefault();const form=event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if(form.dataset.action==="connect") {const chosen=node("window").value;if(chosen)dispatch("connect",{selection:JSON.parse(chosen),profile_id:node("profile").value,disposable_confirmation:!!node("disposable")?.checked});}
    else if(form.dataset.action==="message") dispatch("message",{text:node("draft").value});
  });
  let invalidating=false;
  for (const id of ["window","profile"]) node(id).addEventListener("change",()=> {
    dirty=true;
    node("review").disabled=true;node("start").disabled=true;
    if(state.connected) dispatch("edit");
  });
  node("draft").addEventListener("input",()=>{
    if(state.plan || state.busy) dirty=true;
    node("review").disabled=true;node("start").disabled=true;
    if (!invalidating && (state.plan || state.busy)) {invalidating=true;dispatch("edit").finally(()=>{invalidating=false;});}
  });
  async function refresh() {if(polling) return;polling=true;const current=generation;
    try{const response=await fetch(api,{cache:"no-store"});if(!response.ok)throw new Error();const next=await response.json();if(current===generation)render(next);}
    catch(_){error("Connection lost. The game watchdog cancels work; reconnect before starting again.");node("draft").disabled=true;}
    finally{polling=false;}}
  window.addEventListener("pagehide",()=>{
    const body=new URLSearchParams({csrf_token:root.dataset.csrf,action:"ui_disconnect",payload:JSON.stringify({client_id:client})});
    navigator.sendBeacon(api,body);
  });
  setInterval(()=>post("heartbeat").catch(()=>{}),750);
  setInterval(refresh,250);
  render(JSON.parse(root.dataset.initialState)); post("windows").then(render).catch(f=>error(f.message));
})();
'''
