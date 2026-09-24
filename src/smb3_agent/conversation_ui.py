"""Mario's ordinary conversation surface; no parsing or runtime authority lives here."""

from __future__ import annotations

import html
import json
from collections.abc import Mapping


CONVERSATION_CSS = """
.conversation-workspace{grid-column:1/-1;min-width:0;display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:16px;scroll-margin-top:12px}
.conversation-workspace>header,.conversation-controls,.conversation-alert{grid-column:1/-1}.conversation-workspace>header{display:flex;justify-content:space-between;gap:16px;align-items:center}.conversation-workspace h2{font-size:24px;margin:0}.conversation-workspace h3{font-size:17px;margin:0 0 12px}.conversation-workspace p{overflow-wrap:anywhere}.conversation-workspace header p{margin:6px 0 0}
.conversation-controls{align-self:start;position:sticky;top:8px;z-index:5;display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:12px;background:rgba(248,251,255,.97);border:1px solid #cad7ed;border-radius:18px;box-shadow:0 5px 18px #334d7918}.conversation-controls strong{margin-right:auto}.conversation-controls button{min-height:44px}.conversation-controls .danger{background:#ac2944;border-color:#ac2944;color:white}
.conversation-chat,.conversation-plan{min-width:0;padding:20px}.conversation-chat{display:flex;flex-direction:column;gap:12px}.conversation-workspace form{margin:0}.conversation-workspace label{display:block;font-weight:650;font-size:13px;margin-bottom:6px}.conversation-workspace textarea,.conversation-workspace input,.conversation-workspace select{width:100%;box-sizing:border-box;font:inherit}.conversation-workspace textarea{resize:vertical;min-height:110px;line-height:1.5}.conversation-inline{display:flex;flex-wrap:wrap;gap:8px;align-items:end}.conversation-inline>div{flex:1;min-width:180px}.conversation-inline button{flex:none}.conversation-workspace button{white-space:normal}.conversation-workspace .meta{font-size:12px;line-height:1.45;color:#54647b}.conversation-transcript{list-style:none;padding:0;margin:0;max-height:280px;overflow:auto;display:flex;flex-direction:column;gap:8px}.conversation-transcript li{background:#edf3ff;border-radius:14px;padding:10px 12px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.45;font-size:14px}.conversation-transcript li[data-role=user]{background:#e1edff}.conversation-transcript strong{display:block;font-size:12px;margin-bottom:4px}.conversation-empty{color:#54647b}.conversation-status{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:0 0 16px}.conversation-status dt{font-size:12px;color:#54647b}.conversation-status dd{margin:4px 0 0;overflow-wrap:anywhere;font-size:14px}.conversation-status .wide{grid-column:1/-1}.conversation-plan ol{padding-left:22px;font-size:14px;line-height:1.5}.conversation-plan ol li+li{margin-top:6px}.conversation-plan .callout{margin:12px 0}.conversation-plan details{margin-top:14px}.conversation-plan summary{cursor:pointer;min-height:32px}.conversation-plan pre{max-height:260px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.conversation-workspace [hidden]{display:none!important}.conversation-alert{flex-basis:100%;overflow-wrap:anywhere;margin:0;padding:12px 16px;border-radius:12px;background:#fff0f2;border:1px solid #c66679;color:#861c33}.conversation-outcome{border-top:1px solid #d8e1ef;padding-top:16px;margin-top:16px}.conversation-history{font-size:13px;line-height:1.5;padding-left:20px}.conversation-launch{border-top:1px solid #d8e1ef;padding-top:14px}.conversation-launch p{margin:0 0 8px}.conversation-buttons{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.conversation-speed{margin-top:16px}.conversation-plan .conversation-subtitle{font-size:12px;color:#54647b;margin:8px 0}.conversation-workspace .conversation-boundary{color:#314763;font-weight:550}
.conversation-workspace{align-items:start;gap:12px}.conversation-intent-choice{grid-column:1/-1}.conversation-intent-choice>div{flex:0 1 400px}.conversation-workspace h2{font-size:20px;margin-bottom:12px}.conversation-chat,.conversation-plan{padding:16px}.conversation-workspace .meta,.conversation-workspace label,.conversation-status dt{font-size:14px;line-height:1.5}.conversation-workspace p{margin:8px 0}.conversation-status{margin:12px 0;gap:8px}.conversation-status dt{text-transform:none;letter-spacing:0}.conversation-status dd{margin-top:2px}.conversation-workspace textarea{min-height:96px;font:inherit}.conversation-workspace .conversation-transcript{max-height:none;overflow:visible}.conversation-launch{padding-top:0;border-top:0;margin-top:12px!important}.conversation-launch p{margin:6px 0}.conversation-outcome{padding-top:12px;margin-top:12px}.conversation-saved,.conversation-records{grid-column:1/-1;min-width:0}.conversation-workspace summary{cursor:pointer;min-height:44px;display:list-item;padding:10px 0;font-weight:650}.conversation-workspace details>form{margin-top:12px}.conversation-records pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px}.conversation-chat .conversation-outcome{margin-top:0}.conversation-controls{padding:8px 12px}.conversation-status .wide{grid-column:1/-1}
@media(max-width:820px){.conversation-workspace{grid-template-columns:minmax(0,1fr)}.conversation-workspace>header{align-items:start}.conversation-controls{top:0}.conversation-controls strong{flex-basis:100%}.conversation-chat,.conversation-plan{padding:16px}.conversation-inline button{flex:0 1 auto}.conversation-transcript{max-height:210px}}
@media(prefers-reduced-transparency:reduce){.conversation-controls{background:#f8fbff}}
"""


def render_conversation_workspace(
    state: Mapping[str, object] | None = None, *, csrf_token: str | None = None
) -> str:
    """Render a stable DOM shell; polling only patches noneditable status nodes."""
    encoded = html.escape(json.dumps(dict(state or {})), quote=True)
    token = html.escape(csrf_token or "", quote=True)
    return f'''
  <div id="conversation-controls" class="conversation-controls" aria-label="Persistent Mario controls">
    <strong id="conversation-owner">Mario · You control the game</strong>
    <button type="button" data-conversation-action="pause" data-testid="conversation-pause">Pause</button>
    <button type="button" data-conversation-action="resume" data-testid="conversation-resume">Resume</button>
    <button type="button" data-conversation-action="stop" class="danger" data-testid="conversation-stop">Stop</button>
    <button type="button" data-conversation-action="reclaim" class="danger" data-testid="conversation-reclaim">Take control</button>
    <p id="conversation-error" class="conversation-alert" role="alert" hidden></p>
  </div>
<section id="mario-conversation" class="conversation-workspace" data-testid="mario-conversation" data-initial-state="{encoded}" data-csrf="{token}" aria-label="Mario conversation and plan">
    <form data-conversation-form="select_intent" class="conversation-inline conversation-intent-choice">
      <div><label for="conversation-intent">Route objective</label><select id="conversation-intent" name="intent"><option value="existing base route">Existing route</option><option value="faster">Faster</option><option value="fastest">Fastest</option><option value="quickest">Quickest</option><option value="100% clear">100% clear</option></select></div>
      <button type="submit">Review plan</button>
    </form>
  <section class="session-card conversation-chat" aria-labelledby="conversation-chat-heading">
    <h2 id="conversation-chat-heading">Plan with Companion</h2>
    <form data-conversation-form="message" id="conversation-message-form">
      <label for="conversation-draft">Ask a question or describe a change</label>
      <textarea id="conversation-draft" name="text" maxlength="4000" placeholder="Take the opening hop, then stop after the opening section." required aria-describedby="conversation-typing-note"></textarea>
      <p class="meta" id="conversation-typing-note">Mario can play while you type. Questions give advice; supported edits can change upcoming steps.</p>
      <button type="submit" class="primary-button" data-testid="conversation-send">Send</button>
      <div class="conversation-buttons" aria-label="Suggested supported edits"><button type="button" data-conversation-draft="Take the opening hop, then stop after the opening section">Try the opening hop</button><button type="button" data-conversation-draft="Use the base path and stop at the end of World 1-1">Base path to level exit</button></div>
    </form>
    <ol id="conversation-messages" class="conversation-transcript" aria-label="Latest messages" role="log" aria-live="polite" aria-relevant="additions"></ol>
    <details id="conversation-earlier"><summary>Earlier messages</summary><ol id="conversation-older-messages" class="conversation-transcript" aria-label="Earlier messages"></ol></details>
  </section>
  <section class="session-card conversation-plan" aria-labelledby="conversation-plan-heading">
    <h2 id="conversation-plan-heading">Your Mario plan</h2>
    <dl class="conversation-status">
      <div><dt>You asked for</dt><dd id="conversation-requested">Existing base route</dd></div>
      <div><dt>Route loaded</dt><dd id="conversation-loaded">Existing route to the game ending</dd></div>
    </dl>
    <p id="conversation-fallback" class="callout">Faster and 100% routes are not available. These choices load the existing route.</p>
    <p id="conversation-plan-label" class="conversation-subtitle">Review a plan to begin.</p>
    <ol id="conversation-actions"></ol>
    <p id="conversation-unsupported" class="callout" hidden></p>
    <form method="post" action="/observe-start" id="conversation-launch" class="conversation-launch">
      <input type="hidden" name="csrf_token" value="{token}"><input type="hidden" name="allow_takeover" value="true"><input type="hidden" name="pause_for_plan" value="true">
      <button type="submit" data-testid="conversation-open-game">Open Mario for companion play</button>
      <p id="conversation-live-reason" class="meta"></p>
      <a href="#setup">Mario setup</a>
    </form>
    <div class="conversation-buttons">
      <button type="button" class="primary-button" data-conversation-action="start" data-testid="conversation-start">Start reviewed plan</button>
      <button type="button" data-conversation-action="apply" data-testid="conversation-apply">Apply change</button>
    </div>
    <p id="conversation-eligibility" class="meta"></p>
    <p class="meta">Mario opens in a separate window. Start permits this plan and its supported edits to play.</p>
    <div id="conversation-playing" class="conversation-outcome">
      <h3>Now playing</h3>
      <p id="conversation-current">No plan is running.</p>
      <p id="conversation-pending">No pending change.</p>
      <p id="conversation-boundary" class="conversation-boundary"></p>
      <p id="conversation-ack" role="status" aria-live="polite"></p>
      <button type="button" data-conversation-action="cancel_pending" data-testid="conversation-cancel">Cancel pending change</button>
    </div>
    <form data-conversation-form="speed" class="conversation-inline conversation-speed">
      <div><label for="conversation-speed">Playback speed</label><select id="conversation-speed" name="rate"><option value="1">1× · Normal</option><option value="turbo">Faster · Uncapped</option></select></div>
      <button type="submit">Set speed</button>
    </form>
    <p id="conversation-speed-status" class="meta">Requested 1× · Applied rate not yet acknowledged</p>
    <p id="conversation-performance" class="meta"></p>
    <div class="conversation-outcome"><h3>Result</h3><p id="conversation-outcome">No attempt yet.</p><p id="conversation-coverage" class="meta">Full-completion coverage is unknown.</p></div>
  </section>
  <details class="session-card conversation-saved"><summary>Save or reopen a route</summary>
    <form data-conversation-form="save_variant" class="conversation-inline"><div><label for="conversation-variant-name">Route name</label><input id="conversation-variant-name" name="name" maxlength="100" required placeholder="My opening hop"></div><button type="submit">Save route</button></form>
    <form data-conversation-form="load_variant" class="conversation-inline conversation-speed"><div><label for="conversation-variant">Saved route</label><select id="conversation-variant" name="variant_id"><option value="">No saved routes</option></select></div><button type="submit">Reopen</button></form>
    <p class="meta">Reopening requires your permission to play again. Saving does not establish route reliability or a fastest time.</p>
  </details>
  <details class="session-card conversation-records"><summary>Plan history and technical details</summary>
    <form data-conversation-form="revert" class="conversation-inline conversation-speed"><div><label for="conversation-revision">Earlier plan version</label><select id="conversation-revision" name="revision" required><option value="">No earlier version</option></select></div><button type="submit">Revert future steps</button></form>
    <p class="meta">Reverting changes upcoming steps. It cannot undo completed game actions.</p>
    <p>Session: <span id="conversation-session">No live session</span></p>
    <ol id="conversation-revisions" class="conversation-history"></ol><ol id="conversation-history" class="conversation-history"></ol><pre id="conversation-details"></pre>
  </details>
  <noscript><p class="conversation-alert">JavaScript is required for live conversation, status updates and these controls. Existing game controls are available below.</p></noscript>
</section>'''


CONVERSATION_JS = r'''(() => {
  "use strict";
  const root = document.getElementById("mario-conversation");
  if (!root) return;
  const node = name => document.getElementById(`conversation-${name}`);
  const text = (name, value) => { const el = node(name); const next = String(value ?? ""); if (el.textContent !== next) el.textContent = next; };
  const label = value => String(value ?? "").replace(/_/g, " ");
  const speed = value => value === "turbo" ? "Faster (uncapped)" : value == null ? "not yet acknowledged" : `${value}×`;
  const stopLabel = value => ({world_1_1_opening_end:"after the World 1-1 opening",world_1_1_exit:"after clearing World 1-1",full_route:"at the existing route's ending"}[value] || label(value));
  const boundaryLabel = value => ({world_1_1_opening:"World 1-1 opening",world_1_1_exit:"World 1-1 exit",next_supported_boundary:"Next supported boundary"}[value] || label(value));
  const eligibilityLabel = value => ({requires_runtime_validation:"Requires a compatible live game and fresh authorization",clarification_required:"Clarification needed",planning_only:"Plan only; execution is unavailable",blocked:"Cannot execute from this plan",unsupported:"Unsupported plan",executable:"Ready for fresh runtime checks"}[value] || label(value));
  const displayCopy = value => {
    const copy = String(value ?? "");
    if (copy === "Select a route intent, then review the actual base and supported edit scope.") return "Choose an objective and review your plan.";
    if (copy === "Start live observation to open a visible player-controlled game.") return "";
    if (copy === "No optimized variant is available. The loaded route is world_8_finish_game; playback speed does not establish a faster game-frame route.") return "A quicker route is not available; this loads the existing route. Playback speed does not shorten the route.";
    return copy.replaceAll("No optimized variant is available. The loaded route is world_8_finish_game; playback speed does not establish a faster game-frame route.", "A quicker route is not available; this loads the existing route. Playback speed does not shorten the route.").replaceAll("No full-completion variant is available. The loaded route is world_8_finish_game; finishing it does not establish 100% completion, and coverage remains unknown.", "No 100% route is available. This loads the existing route; finishing it does not prove 100% completion. Coverage is unknown.").replaceAll("Requested a quicker game-frame route; loaded the existing base route.", "You asked for a quicker route.").replaceAll("world_8_finish_game", "existing route to the game ending").replaceAll("same-game-frame", "same game speed");
  };
  const printable = value => typeof value === "object" && value !== null ? JSON.stringify(value) : label(value);
  let state = {};
  let generation = 0;
  let polling = false;
  let errorSource = "";
  const busy = new Set();
  const signatures = new Map();
  const token = root.dataset.csrf;
  const list = (name, items, create) => {
    const signature = JSON.stringify(items);
    if (signatures.get(name) === signature) return;
    signatures.set(name, signature);
    const el = node(name);
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 32;
    el.replaceChildren(...items.map(create));
    if (atBottom) el.scrollTop = el.scrollHeight;
  };
  const item = value => { const li = document.createElement("li"); li.textContent = value; return li; };
  const summarizePlan = plan => !plan ? "None" : `Version ${plan.revision ?? "?"} · ${(Array.isArray(plan.change_summary) ? plan.change_summary.join(" ") : plan.change_summary) || stopLabel(plan.stop_point) || "Reviewed route"}`;
  function render(next) {
    state = next || {};
    const plan = state.plan || {};
    const current = state.current_plan;
    const pending = state.pending_plan;
    const runtime = state.runtime || {};
    const live = state.live || {};
    text("owner", `Mario · ${runtime.owner === "agent" ? "Companion is playing" : "You control the game"}${runtime.status && runtime.status !== "idle" ? ` · ${label(runtime.status)}` : ""}`);
    text("session", runtime.session_id || live.session_id || "No live session");
    text("requested", plan.requested_objective || "Existing base route");
    const loadedVariant = (state.variants || []).find(variant => variant.variant_id === plan.variant_id);
    text("loaded", `${plan.base_route_id === "world_8_finish_game" || !plan.base_route_id ? "Existing route to the game ending" : label(plan.base_route_id)}${plan.variant_id ? ` · ${loadedVariant?.name || "Custom variant"}` : " · Base"}`);
    text("fallback", displayCopy(plan.fallback_explanation) || "Faster and 100% routes are not available. These choices load the existing route.");
    text("plan-label", plan.revision ? `Plan version ${plan.revision}` : "");
    list("actions", plan.actions || [], action => {
      const parameters = action.parameters || {};
      if (["mario_traverse", "mario_path", "traverse_route", "follow_route"].includes(action.kind)) {
        const path = parameters.path_choice === "opening_hop" ? "Take the opening hop in World 1-1." : "Use the default World 1-1 opening.";
        return item(`Follow the existing route. ${path} Stop ${stopLabel(parameters.stop_point || plan.stop_point)}.`);
      }
      if (["mario_stop", "stop", "stop_at"].includes(action.kind)) return item(`Stop ${stopLabel(parameters.stop_point || plan.stop_point)}.`);
      if (["mario_speed", "set_speed"].includes(action.kind)) return item(`Set playback to ${speed(parameters.speed || plan.requested_speed)}.`);
      return item(label(action.kind));
    });
    text("eligibility", !state.plan ? "Choose an objective and review the plan before starting." : !live.observation_active ? "Open Mario before starting. The game must match the plan’s starting point." : eligibilityLabel(plan.execution_eligibility));
    const issues = [...(plan.ambiguities || []), ...(plan.unsupported_parts || [])];
    text("unsupported", issues.map(printable).join(" · ")); node("unsupported").hidden = !issues.length;
    node("playing").hidden = !current && !pending;
    text("current", current ? `Current: ${summarizePlan(current)}` : "No plan is running.");
    text("pending", pending ? `Pending: ${summarizePlan(pending)}` : "No pending change.");
    text("boundary", `Change takes effect at: ${boundaryLabel(runtime.pending?.effective_boundary || pending?.effective_boundary || runtime.effective_boundary || plan.effective_boundary || "Not selected")}`); node("boundary").hidden = !pending;
    text("ack", displayCopy(state.message) || runtime.acknowledgment || (runtime.revision ? `Game confirmed plan version ${runtime.revision}.` : ""));
    node("ack").hidden = Boolean(state.message && state.messages?.at(-1)?.text === state.message);
    text("speed-status", `Requested ${speed(runtime.requested_speed ?? plan.requested_speed ?? 1)} · Applied ${speed(runtime.applied_speed)}`);
    const measured = [...(runtime.speed_intervals || [])].reverse().find(interval => interval.measured_multiplier != null);
    text("performance", [measured ? `Last completed speed interval: ${Number(measured.measured_multiplier).toFixed(2)}× measured` : "", runtime.performance_limitation || ""].filter(Boolean).join(" · "));
    text("live-reason", live.observation_active ? `Mario is already open. ${displayCopy(live.reason)}` : displayCopy(live.reason));
    const launch = root.querySelector("[data-testid='conversation-open-game']");
    launch.disabled = Boolean(live.observation_active || busy.has("launch"));
    const messageItem = message => {
      const li = item(""); const by = document.createElement("strong"); by.textContent = message.role === "user" ? "You" : "Companion";
      const copy = document.createElement("span");
      const planSummary = [...(plan.change_summary || []), plan.fallback_explanation].filter(Boolean).join(" ");
      copy.textContent = message.kind === "proposal" && message.text === planSummary
        ? "Plan ready to review. Check the route and stop point before starting."
        : displayCopy(message.text) || "";
      li.dataset.role = message.role; li.append(by, copy); return li;
    };
    list("messages", (state.messages || []).slice(-2), messageItem);
    list("older-messages", (state.messages || []).slice(0, -2), messageItem);
    node("earlier").hidden = (state.messages || []).length <= 2;
    const variants = state.variants || [];
    const variantSignature = JSON.stringify(variants.map(v => [v.variant_id || v.id, v.name, v.saved_revision ?? v.revision]));
    if (signatures.get("variants") !== variantSignature) {
      signatures.set("variants", variantSignature);
      const select = node("variant"); const selected = select.value;
      const options = variants.map(v => { const option = document.createElement("option"); option.value = v.variant_id || v.id; option.textContent = `${v.name || "Unnamed route"}${v.saved_revision || v.revision ? ` · version ${v.saved_revision || v.revision}` : ""}`; return option; });
      if (!options.length) { const option = document.createElement("option"); option.value = ""; option.textContent = "No saved routes"; options.push(option); }
      select.replaceChildren(...options);
      if (options.some(option => option.value === selected)) select.value = selected;
    }
    const revisions = state.revisions || [];
    const revisionSignature = JSON.stringify(revisions.map(v => v.revision));
    if (signatures.get("revision-options") !== revisionSignature) {
      signatures.set("revision-options", revisionSignature);
      const select = node("revision"); const selected = select.value;
      const options = revisions.map(v => { const option = document.createElement("option"); option.value = String(v.revision); option.textContent = summarizePlan(v); return option; });
      if (!options.length) { const option = document.createElement("option"); option.value = ""; option.textContent = "No earlier version"; options.push(option); }
      select.replaceChildren(...options);
      if (options.some(option => option.value === selected)) select.value = selected;
    }
    list("revisions", revisions, revision => item(summarizePlan(revision)));
    const outcome = state.outcome;
    text("outcome", !outcome ? "No attempt yet." : typeof outcome === "string" ? label(outcome) : `${label(outcome.status || "Unknown result")} · ${label(outcome.actor || "unknown")} play${outcome.elapsed_game_frames != null ? ` · ${outcome.elapsed_game_frames} game frames` : ""} · Input ${outcome.neutralized ? "stopped" : "not confirmed stopped"} · ${outcome.controller_owner === "player" ? "Control returned to you" : "Handback not confirmed"}`);
    text("coverage", `Full-completion coverage: ${label(plan.completion_coverage || "unknown")}.`);
    list("history", state.history || [], entry => item(typeof entry === "string" ? entry : `${entry.revision ? `Revision ${entry.revision} · ` : ""}${entry.summary || label(entry.status) || "Unknown outcome"}${entry.actor ? ` · ${label(entry.actor)} play` : ""}${entry.elapsed_game_frames != null ? ` · ${entry.elapsed_game_frames} game frames` : ""}`));
    text("details", JSON.stringify({plan, current_plan: current, pending_plan: pending, runtime, outcome}, null, 2));
  }
  function error(message, source = "action") { errorSource = message ? source : ""; text("error", message); node("error").hidden = !message; }
  async function responseError(response) {
    if ((response.headers.get("Content-Type") || "").includes("application/json")) {
      const failure = await response.json(); return failure.error || failure.message || `Request failed (${response.status}).`;
    }
    const parsed = new DOMParser().parseFromString(await response.text(), "text/html");
    return parsed.querySelector("main p, body p")?.textContent?.trim() || `Request failed (${response.status}).`;
  }
  async function refresh() {
    if (polling || busy.size) return;
    polling = true; const started = generation;
    try {
      const response = await fetch("/api/conversation", {cache:"no-store"});
      if (!response.ok) throw new Error(await responseError(response));
      const next = await response.json();
      if (started === generation) { render(next); if (errorSource === "refresh") error(""); }
    } catch (failure) { if (started === generation) error(`Live updates unavailable. Check that Game Companion is running; this page will retry. ${failure.message}`, "refresh"); }
    finally { polling = false; }
  }
  async function dispatch(action, payload = {}, source = null) {
    const priority = ["stop", "reclaim", "pause"].includes(action);
    if (busy.has(action) || (!priority && busy.size)) return false;
    busy.add(action); const started = ++generation;
    const buttons = source ? Array.from(source.querySelectorAll("button[type=submit]")) : [];
    for (const button of buttons) button.disabled = true;
    payload.request_id = crypto.randomUUID();
    if (action === "start" || action === "apply") {
      payload.expected_plan_id = state.plan?.plan_id ?? null;
      payload.expected_revision = state.plan?.revision ?? null;
    }
    error("");
    try {
      const response = await fetch("/api/conversation", {method:"POST", headers:{"Content-Type":"application/x-www-form-urlencoded;charset=UTF-8"}, body:new URLSearchParams({csrf_token:token, action, payload:JSON.stringify(payload)})});
      if (!response.ok) throw new Error(await responseError(response));
      const next = await response.json();
      if (started === generation) render(next);
      return true;
    } catch (failure) { if (started === generation) error(failure.message); return false; }
    finally { busy.delete(action); for (const button of buttons) button.disabled = false; }
  }
  node("controls").addEventListener("click", event => {
    const button = event.target.closest("[data-conversation-action]");
    if (button) dispatch(button.dataset.conversationAction);
  });
  root.addEventListener("click", event => {
    const suggestion = event.target.closest("[data-conversation-draft]");
    if (suggestion && root.contains(suggestion)) { node("draft").value = suggestion.dataset.conversationDraft; node("draft").focus(); return; }
    const button = event.target.closest("[data-conversation-action]");
    if (button && root.contains(button)) dispatch(button.dataset.conversationAction);
  });
  root.addEventListener("submit", async event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    event.preventDefault();
    if (form.id === "conversation-launch") {
      if (busy.size) return;
      busy.add("launch"); ++generation; const button = form.querySelector("button[type=submit]"); button.disabled = true; error("");
      try { const response = await fetch(form.action, {method:"POST", body:new URLSearchParams(new FormData(form)), redirect:"follow"}); if (!response.ok) throw new Error(await responseError(response)); }
      catch (failure) { error(failure.message); }
      finally { busy.delete("launch"); button.disabled = false; await refresh(); }
      return;
    }
    const action = form.dataset.conversationForm;
    if (!action) return;
    const payload = Object.fromEntries(new FormData(form));
    if (action === "speed" && payload.rate !== "turbo") payload.rate = Number(payload.rate);
    if (action === "revert") payload.revision = Number(payload.revision);
    const draft = node("draft"); const submitted = draft.value;
    const succeeded = await dispatch(action, payload, form);
    // Never erase text typed after the submitted request, or move focus/selection.
    if (succeeded && action === "message" && draft.value === submitted) draft.value = "";
  });
  try { render(JSON.parse(root.dataset.initialState || "{}")); } catch (_failure) { render({}); }
  refresh();
  window.setInterval(refresh, 750);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
})();
'''


def render_stardew_conversation_workspace(state: Mapping[str, object] | None = None,
                                           *, csrf_token: str | None = None) -> str:
    """Ordinary watering workspace; editable nodes remain stable across polling."""
    encoded = html.escape(json.dumps(dict(state or {})), quote=True)
    token = html.escape(csrf_token or "", quote=True)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Stardew · Game Companion</title>
<style>{CONVERSATION_CSS}
body{{margin:0;background:#f5f8f4;color:#203626;font:16px/1.5 system-ui}}main{{max-width:1080px;margin:auto;padding:20px}}button,input,textarea{{font:inherit}}button{{padding:10px 14px;border:1px solid #7b987e;border-radius:10px;background:#fff;cursor:pointer}}button:disabled{{opacity:.55;cursor:default}}.card{{background:white;border:1px solid #d3dfd4;border-radius:16px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}label{{display:block}}input[type=checkbox]{{width:auto!important}}.setup-fields{{display:grid;gap:10px}}.conversation-controls{{margin:16px 0}}a{{color:#245c38}}</style></head><body><main>
<a href="/">Games</a><h1>Stardew Valley</h1><p>Water the complete initial crop set, then return to the farmhouse entrance. Harvesting, planting and clearing are not yet supported.</p>
<div id="stardew-workspace" data-initial-state="{encoded}" data-csrf="{token}">
<div class="conversation-controls" aria-label="Persistent Stardew controls"><strong id="stardew-owner">You control the game</strong>
<button data-action="pause">Pause</button><button data-action="stop">Stop</button><button data-action="reclaim" class="danger">Take control</button>
<p id="stardew-error" class="conversation-alert" role="alert" hidden></p></div>
<p id="stardew-status" role="status"></p>
<section class="conversation-workspace" aria-label="Stardew conversation and plan">
<div class="conversation-chat card"><h2>1. Open an engineering session</h2><p>Open the installed game in a fresh isolated folder. This starts at the title screen; a prepared and verified farm is still required before watering.</p>
<button data-action="launch_engineering">Open isolated engineering game</button>
<details><summary>Advanced: copy a selected existing save</summary><p>No save is discovered automatically. Choose the exact source and a new destination. Copying alone does not verify where the game loads or saves.</p>
<form data-action="setup" class="setup-fields"><label>Source kind<select name="setup_source_kind"><option value="engineering_source">Dedicated engineering save</option><option value="owner_copy">Selected owner save</option></select></label><label>Selected source directory<input name="source" required autocomplete="off"></label>
<label>New disposable destination<input name="destination" required autocomplete="off"></label>
<label><input type="checkbox" name="copy_authorized" required> I authorize copying this selected source to this destination.</label>
<button type="submit">Create disposable copy</button></form></details>
<p id="stardew-setup"></p>
<h3>Verify the farm session</h3><p>Opening the title screen is the first step. A prepared engineering farm must have retained proof of saving and loading in this isolated folder. Verification checks that evidence; it does not prepare a farm or perform gameplay.</p>
<button data-action="verify_engineering_session">Check isolated farm session</button>
<ol id="stardew-setup-steps" aria-label="Setup evidence checklist"></ol>
<h3>Connect screen recognition</h3><p id="stardew-profile-status">No qualified screen profile is available. Unverified calibration cannot enable watering.</p>
<form data-action="connect_profile"><label for="stardew-profile">Qualified profile for this session</label><select id="stardew-profile" name="profile_id"><option value="">No qualified profile available</option></select><button id="stardew-connect" type="submit" disabled>Connect qualified screen profile</button></form>
<details><summary>Reset to a fresh disposable attempt</summary><form data-action="reset"><label>New destination<input name="destination" required autocomplete="off"></label><button type="submit">Create fresh attempt</button></form></details><button data-action="observe">Focus game and observe</button>
<h2>2. Request watering</h2><form data-action="message"><label for="stardew-draft">What would you like to do?</label><textarea id="stardew-draft" name="text" placeholder="Water all initially planted crops" required></textarea><button type="submit">Send request</button></form>
<p class="meta">Task requests and Observe focus the verified game to refresh its view. Questions and control requests do not change focus. Start returns focus to the reviewed Stardew window. Switching away pauses input and requires a fresh observation, review and explicit Start.</p>
<ul id="stardew-messages" class="conversation-transcript" aria-live="polite"></ul></div>
<div class="conversation-plan card"><h2>Observed targets</h2><p id="stardew-observation"></p><form data-action="select_targets"><div id="stardew-targets"></div><button type="submit">Use selected targets</button></form>
<h2>3. Review watering scope</h2><p id="stardew-plan">Request a task to prepare a proposal.</p><ol id="stardew-actions"></ol><p id="stardew-limits"></p><p id="stardew-issues"></p>
<div class="conversation-buttons"><button data-action="apply" id="stardew-review">Review scope</button><button data-action="start" id="stardew-start">Start reviewed watering</button></div>
<p id="stardew-review-status"></p><section class="conversation-outcome"><h2>Outcome and remaining work</h2><p id="stardew-outcome">No attempt yet.</p><pre id="stardew-ledger"></pre></section>
<details><summary>Session and evidence details</summary><pre id="stardew-details"></pre></details></div>
</section></div></main><script src="/assets/stardew-conversation.js" defer></script></body></html>'''


STARDEW_CONVERSATION_JS = r'''
(() => {
  "use strict";
  const root = document.getElementById("stardew-workspace"); if (!root) return;
  const node = id => document.getElementById(`stardew-${id}`);
  const text = (id, value) => { const target = node(id); const copy = value ?? ""; if (target.textContent !== String(copy)) target.textContent = copy; };
  const api = "/api/stardew/conversation";
  let state = {}, generation = 0, polling = false, targetsSignature = "", messagesSignature = "", profilesSignature = "", setupStepsSignature = "";
  const busy = new Set();
  function render(next) {
    state = next;
    const run = state.runtime || {}, plan = state.plan, observation = run.observation || {}, planningObservation = run.planning_observation || observation;
    text("owner", run.owner === "agent" || run.input_owner === "agent" ? "Companion controls watering" : run.handback_confirmed === false ? "Handback not confirmed" : "You control the game");
    text("status", run.reason || run.status || "Setup required");
    const setup = run.setup?.session_id ? run.setup : (run.engineering_launches || []).at(-1) || run.setup || {}, save = setup.save || {};
    text("setup", setup.classification === "fresh_engineering_namespace" ? `Engineering session ${setup.session_id.slice(0, 8)} · ${setup.blocker || ""} Folder and process identity are in Session and evidence details.` : setup.session_id ? `Session ${setup.session_id} · ${setup.classification === "engineering_source" ? "Engineering source" : "Selected owner copy"}. Source: ${save.primary_path || save.source_path || "unknown"}. Disposable: ${save.disposable_path || "unknown"}. ${setup.blocker || ""}` : "No disposable session selected.");
    const steps = run.setup_steps || [];
    const stepsSignature = JSON.stringify(steps);
    if (stepsSignature !== setupStepsSignature) {
      setupStepsSignature = stepsSignature;
      node("setup-steps").replaceChildren(...steps.map(step => {
        const item = document.createElement("li");
        item.textContent = `${step.label || step.id}: ${step.status || "unknown"}${step.reason ? ` — ${step.reason}` : ""}`;
        return item;
      }));
    }
    const profiles = run.qualified_profiles || [];
    const profileSignature = JSON.stringify(profiles);
    if (profileSignature !== profilesSignature) {
      profilesSignature = profileSignature;
      const select = node("profile"), previous = select.value;
      const options = profiles.map(profile => { const option = document.createElement("option"); option.value = profile.profile_id; option.textContent = profile.label || profile.profile_id; return option; });
      if (!options.length) { const option = document.createElement("option"); option.value = ""; option.textContent = "No qualified profile available"; options.push(option); }
      select.replaceChildren(...options);
      if (profiles.some(profile => profile.profile_id === previous)) select.value = previous;
    }
    node("connect").disabled = !profiles.length;
    node("profile").disabled = !profiles.length;
    text("profile-status", profiles.length ? "Only retained, qualified profiles for this session are listed. Connection rechecks their evidence and game identity." : "No qualified screen profile is available. Unverified calibration cannot enable watering.");
    text("observation", observation.observation_id ? `Observation ${observation.observation_id} · ${observation.source || "unknown source"}` : "No validated automatic observation. Targets and resources remain unknown.");
    const targets = planningObservation.targets || (observation.crops || []).filter(item => item.planted).map(item => ({...item,id:item.crop_id}));
    const signature = JSON.stringify(targets.map(item => item.id));
    if (signature !== targetsSignature) {
      targetsSignature = signature;
      const checked = new Set([...node("targets").querySelectorAll("input:checked")].map(item => item.value));
      node("targets").replaceChildren(...targets.map(item => {
        const label = document.createElement("label"), input = document.createElement("input");
        input.type = "checkbox"; input.name = "target_ids"; input.value = item.id;
        input.checked = checked.has(item.id) || (state.selected_target_ids || []).includes(item.id);
        const copy = document.createElement("span"); copy.dataset.targetId = item.id;
        label.append(input, copy); return label;
      }));
    }
    for (const copy of node("targets").querySelectorAll("[data-target-id]")) {
      const item = targets.find(target => target.id === copy.dataset.targetId);
      if (item) copy.textContent = ` ${item.label || item.id} · ${item.watered === true ? "watered" : item.watered === false ? "needs water" : "water state unknown"}`;
    }
    text("plan", plan ? `Version ${plan.revision} · ${plan.original_request}` : "Request a task to prepare a proposal.");
    const actions = (plan?.actions || []).map(action => `${action.kind}: ${(action.target_ids || []).join(", ") || "targets unresolved"}`);
    if (node("actions").textContent !== actions.join("")) node("actions").replaceChildren(...actions.map(copy => { const item = document.createElement("li"); item.textContent = copy; return item; }));
    text("limits", plan ? `Return: ${plan.stop_point === "farmhouse_entrance" ? "farmhouse entrance" : "not confirmed"}. ${plan.resource_limits?.minimum_energy != null ? `Keep at least ${plan.resource_limits.minimum_energy} energy. ` : ""}Stop if resources are insufficient or uncertain. No purchases.` : "");
    text("issues", [...(plan?.ambiguities || []), ...(plan?.unsupported_parts || []), plan?.fallback_explanation || ""].join(" "));
    node("review").disabled = plan?.execution_eligibility !== "requires_runtime_validation";
    node("start").disabled = !state.reviewed;
    text("review-status", state.reviewed ? "Exact scope reviewed. Start grants new Do permission only if current game conditions pass." : "No input permission. Review is separate from Start.");
    const messageSignature = JSON.stringify(state.messages || []);
    if (messageSignature !== messagesSignature) {
      messagesSignature = messageSignature;
      node("messages").replaceChildren(...(state.messages || []).slice(-8).map(message => { const li = document.createElement("li"); li.dataset.role = message.role; li.textContent = `${message.role === "user" ? "You" : "Companion"}: ${message.text}`; return li; }));
    }
    const outcome = state.outcome, ledger = run.ledger, tool = observation.tool || {};
    text("outcome", outcome ? `${outcome.status || "Partial"} · ${outcome.stop_reason || run.reason || ""} · Input ${run.neutralized === true ? "neutral" : "neutrality unconfirmed"} · ${run.handback_confirmed ? "Control returned to you" : "Handback unconfirmed"}` : "No attempt yet.");
    text("ledger", ledger ? `${ledger.watered_count ?? "Unknown"} watered · ${ledger.remaining_count ?? "Unknown"} remaining\nEnergy: ${ledger.energy_current ?? "Unknown"} · Water in can: ${tool.watering_can_units ?? "Unknown"}\nTool uses: ${ledger.tool_uses ?? "Unknown"} · Refills: ${ledger.refills ?? "Unknown"}\nReturn point: ${ledger.final_position?.at_farmhouse_entrance === true ? "Reached" : "Not confirmed"}` : "Crop, energy, can-water and refill accounting remain unknown.");
    text("details", JSON.stringify({runtime:run,plan,history:state.history},null,2));
  }
  function error(message) { text("error", message); node("error").hidden = !message; }
  async function dispatch(action, payload = {}) {
    const priority = ["pause", "stop", "reclaim", "focus_lost"].includes(action);
    if (busy.has(action) || (!priority && busy.size)) return false;
    busy.add(action); const started = ++generation;
    payload.request_id = crypto.randomUUID();
    if (["apply", "start"].includes(action)) Object.assign(payload, {expected_plan_id:state.plan?.plan_id,expected_revision:state.plan?.revision});
    try {
      const response = await fetch(api, {method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded;charset=UTF-8"},body:new URLSearchParams({csrf_token:root.dataset.csrf,action,payload:JSON.stringify(payload)})});
      const next = await response.json(); if (!response.ok) throw new Error(next.error || "Action failed");
      if (started === generation) { render(next); error(""); } return true;
    } catch (failure) { if (started === generation) error(failure.message); return false; }
    finally { busy.delete(action); }
  }
  async function refresh() {
    if (polling || busy.size) return; polling = true; const started = generation;
    try { const response = await fetch(api,{cache:"no-store"}); if (!response.ok) throw new Error("Live updates unavailable"); const next = await response.json(); if (started === generation) render(next); }
    catch(failure) { if (started === generation) error(failure.message); }
    finally { polling = false; }
  }
  root.addEventListener("click", event => { const button = event.target.closest("button[data-action]"); if (button) dispatch(button.dataset.action); });
  root.addEventListener("submit", async event => {
    const form = event.target; if (!(form instanceof HTMLFormElement)) return; event.preventDefault();
    const data = new FormData(form), payload = Object.fromEntries(data), action = form.dataset.action;
    if (action === "setup") payload.copy_authorized = data.has("copy_authorized");
    if (action === "select_targets") payload.target_ids = data.getAll("target_ids");
    const draft = node("draft"), submitted = draft.value;
    if (await dispatch(action,payload) && action === "message" && draft.value === submitted) draft.value = "";
  });
  // Native foreground checks remain authoritative; this is an additional prompt handback.
  root.addEventListener("focusin", () => { if ((state.runtime?.owner || state.runtime?.input_owner) === "agent") dispatch("focus_lost"); });
  try { render(JSON.parse(root.dataset.initialState || "{}")); } catch (_) { render({}); }
  refresh(); window.setInterval(refresh,750);
})();
'''
