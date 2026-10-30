"""Minecraft document renderer; behavior is served as a separate script."""

from html import escape

from smb3_agent.glass_ui import GLASS_CSS
from smb3_agent.minecraft_chat_script import CHAT_JS as CHAT_JS


def render_minecraft_chat(token, *, selected=False):
    return PAGE.replace("TOKEN_VALUE", escape(token, quote=True)).replace(
        "SELECTED_VALUE", "true" if selected else "false"
    )


MINECRAFT_CSS = """
.design-views figure {margin:0;min-width:0}
#design-components {display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin-block:12px}
.design-card {padding:12px;border:1px solid #b8c8d0;border-radius:10px;background:white}
.design-card.changed {border:2px solid #2768ba}
#design-references img {max-width:150px;max-height:120px}
#design-caption {width:100%;padding:10px}

* {
  box-sizing:border-box
}
[hidden] {
  display:none!important
}
body {
  min-height:100dvh;
  margin:0;
  color:var(--text);
  font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif
}
button,select,textarea {
  font:inherit;
  color:var(--text);
  background:#fff;
  border:1px solid var(--line-strong);
  padding:10px 14px;
  border-radius:12px
}
button,select,summary {
  min-height:44px
}
button {
  cursor:pointer;
  font-weight:600
}
button:hover:not(:disabled) {
  background:var(--blue-soft);
  border-color:var(--blue)
}
button:disabled {
  background:#edf1f7;
  color:var(--muted);
  border-color:#c4cedd;
  cursor:not-allowed
}
a {
  color:#075ac0
}
h1,h2,p {
  margin:0
}
h1 {
  font-size:20px;
  letter-spacing:-.5px
}
h2 {
  font-size:18px;
  line-height:1.4
}
header {
  position:sticky;
  top:0;
  z-index:2;
  display:flex;
  align-items:center;
  flex-wrap:wrap;
  gap:12px;
  padding:12px 24px;
  background:#f8fafff2;
  border-bottom:1px solid var(--line)
}
.selectors {
  display:flex;
  gap:8px;
  flex-wrap:wrap
}
.app-actions {
  margin-left:auto;
  display:flex;
  gap:8px
}
#stop {
  color:#a12435;
  background:#fff0f1;
  border-color:#d99aa3
}
#stop:hover {
  background:#ffe1e5
}
#quit {
  background:transparent;
  border-color:transparent;
  color:var(--muted)
}
main {
  display:grid;
  grid-template-columns:minmax(0,1.35fr) minmax(360px,1fr);
  gap:24px;
  padding:24px;
  max-width:1720px;
  margin:auto;
  align-items:start
}
.world {
  min-width:0
}
.status {
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  flex-wrap:wrap
}
.world>.status {
  margin-bottom:16px
}
.meta {
  font-size:14px;
  color:var(--muted)
}
#connection {
  display:flex;
  align-items:center;
  gap:8px
}
#connection::before {
  content:"";
  width:8px;
  height:8px;
  border-radius:50%;
  background:#718096
}
body[data-connected=true] #connection::before {
  background:#08725e
}
.scene {
  position:relative
}
iframe {
  display:block;
  width:100%;
  height:clamp(280px,53vh,620px);
  border:1px solid var(--line);
  border-radius:20px;
  background:#eaf0fb
}
.toolbar {
  display:flex;
  align-items:center;
  flex-wrap:wrap;
  gap:8px;
  margin-top:12px
}
.toolbar button {
  background:transparent
}
.toolbar #viewer-status {
  margin-left:auto
}
.activity-panel {
  padding:16px 0;
  border-bottom:1px solid var(--line);
  margin-bottom:8px
}
#activity {
  font-weight:650
}
#progress {
  margin-top:4px
}
#goal {
  margin-top:4px
}
summary {
  cursor:pointer;
  padding:10px 0;
  font-weight:600
}
details p {
  margin:8px 0 12px
}
pre {
  max-width:100%;
  white-space:pre-wrap;
  overflow-wrap:anywhere;
  font-size:13px
}
#session-details {
  font-size:14px
}
#memory-recovery label {
  display:flex;
  flex-wrap:wrap;
  align-items:center;
  gap:8px;
  margin:12px 0
}
#memory-recovery p {
  color:#a12435
}
#setup-panel {
  background:var(--surface);
  padding:24px;
  border:1px solid #fff;
  border-radius:22px;
  box-shadow:0 8px 32px #334d790b
}
#setup-panel[data-new=true] {display:flex;flex-direction:column}
#setup-panel[data-new=true] .setup-actions {order:4;margin:0;border-top:1px solid var(--line);padding-top:12px}
#setup-panel h2 {
  font-size:24px;
  margin-bottom:12px
}
#setup-status {
  margin-bottom:20px;
  overflow-wrap:anywhere
}
.setup-actions {
  display:flex;
  flex-wrap:wrap;
  gap:8px;
  margin-bottom:16px
}
.primary,#send {
  background:var(--blue);
  color:white;
  border-color:var(--blue)
}
#send:disabled,.primary:disabled {
  background:#edf1f7;
  color:var(--muted);
  border-color:#c4cedd
}
body[data-connected=false] .chat {
  height:auto;
  min-height:28em
}
.primary:hover:not(:disabled),#send:hover:not(:disabled) {
  background:#075ac0;
  color:white
}
#setup-panel details {
  border-top:1px solid var(--line)
}
.setup-links {
  display:flex;
  align-items:center;
  flex-wrap:wrap;
  gap:12px;
  padding:8px 0 16px
}
#create-world {
  display:block;
  margin:16px 0
}
#eula {
  width:18px;
  height:18px;
  vertical-align:middle
}
.chat {
  display:flex;
  min-width:0;
  flex-direction:column;
  height:calc(100dvh - 124px);
  min-height:32em;
  max-height:1000px;
  border:1px solid white;
  border-radius:22px;
  background:var(--surface);
  box-shadow:0 8px 32px #334d790b;
  padding:20px
}
@media (min-width:900px) {
  .chat {position:sticky;top:92px}
}
.chat>.status {
  padding-bottom:16px;
  border-bottom:1px solid var(--line)
}
#messages {
  flex:1;
  overflow:auto;
  min-height:100px;
  padding:20px 4px 0;
  scroll-behavior:auto;
  overflow-wrap:anywhere
}
.message {
  white-space:pre-wrap;
  line-height:1.55;
  margin:0 0 20px;
  padding:0 8px
}
.message.user {
  background:var(--blue-soft);
  border-radius:16px;
  padding:12px 16px;
  margin-left:24px
}
.role {
  display:block;
  font-size:13px;
  font-weight:600;
  color:var(--muted);
  margin-bottom:4px
}
#empty-chat {
  padding:28px 8px;
  color:var(--muted)
}
#empty-chat strong {
  display:block;
  color:var(--text);
  font-size:18px;
  margin-bottom:8px
}
form {
  border-top:1px solid var(--line);
  padding-top:16px;
  margin-top:12px
}
form label {
  display:block;
  margin-bottom:8px
}
textarea {
  display:block;
  width:100%;
  resize:vertical;
  min-height:96px;
  max-height:240px;
  line-height:1.5
}
textarea::placeholder {
  color:#59677b;
  opacity:1
}
.compose-actions {
  display:flex;
  align-items:center;
  gap:12px;
  justify-content:space-between;
  margin-top:12px
}
#send {
  min-width:88px;
  flex-shrink:0;
  margin-left:auto
}
#error:not(:empty) {
  color:#912336;
  background:#fff0f2;
  border:1px solid #e8b3bc;
  border-radius:12px;
  padding:12px;
  margin-top:12px;
  white-space:pre-wrap;
  overflow-wrap:anywhere
}
#pending:not(:empty) {
  padding:10px 4px 0
}
.beta-limits {
  margin-top:8px;
  color:var(--muted);
  font-size:14px
}
.beta-limits summary {
  font-weight:500
}
button:focus-visible,select:focus-visible,textarea:focus-visible,summary:focus-visible,a:focus-visible {
  outline:3px solid var(--blue);
  outline-offset:3px
}
@media(prefers-reduced-transparency:reduce) {
  header,.chat,#setup-panel {
    background:#f8faff
  }
}
@media(max-width:900px) {
  header {
    padding:12px 16px
  }
  main {
    grid-template-columns:minmax(0,1fr);
    padding:16px;
    gap:20px
  }
  .chat {
    height:650px;
    min-height:480px
  }
  iframe {
    height:38vh;
    min-height:240px
  }
  .toolbar #viewer-status {
    margin-left:0
  }
  #setup-panel {
    padding:20px
  }
}
@media(max-width:480px) {
  header {
    gap:8px
  }
  header h1 {
    font-size:18px
  }
  .selectors {
    order:3;
    width:100%
  }
  .selectors select {
    min-width:0;
    flex:1;
    width:40%;
    padding-inline:10px
  }
  .app-actions {
    gap:0
  }
  #quit {
    padding-inline:8px
  }
  main {
    padding:12px
  }
  .chat {
    padding:16px
  }
  .chat>.status {
    align-items:start
  }
  .chat #ai {
    max-width:60%
  }
  .message.user {
    margin-left:12px
  }
  .compose-actions {
    align-items:start
  }
  .chat {
    height:650px
  }
  #setup-panel {
    padding:20px
  }
}
/* Minecraft workspace: scene, conversation, then reviewed construction. */
.world {grid-column:1;grid-row:1}
main > .chat {grid-column:2;grid-row:1 / 4}
#design-panel {grid-column:1;grid-row:2}
.session-more {grid-column:1;grid-row:3;min-width:0}
h3 {font-size:17px;line-height:1.4;margin:0 0 12px}
input:not([type=checkbox]):not([type=radio]) {font:inherit;color:var(--text);padding:10px 12px;border:1px solid var(--line-strong);background:white;width:100%;min-width:0}
label,button,select {max-width:100%}
select {text-overflow:ellipsis;min-width:0}
#design-panel {padding:20px;background:var(--surface);border:1px solid white;border-radius:22px;margin:0}
#design-panel > h2 {font-size:22px}
#design-summary {color:var(--muted);margin:4px 0 12px;overflow-wrap:anywhere}
#project-next-step:not(:empty) {padding:10px 12px;margin:12px 0;background:var(--blue-soft);border-radius:12px}
#design-planning:empty,#design-planning[hidden] {display:none}
.design-views {display:block;margin-top:16px}
.design-views svg {width:100%;border-radius:12px;height:220px;background:#edf2f8}
.design-views figcaption {font-size:14px;color:var(--muted);margin-bottom:8px}
#design-palette span {display:inline-block;padding:6px 12px;border-radius:8px;background:var(--blue-soft);font-size:14px;margin:8px 6px 0 0}
.project-stage {border-top:1px solid var(--line);margin-top:16px;padding-top:20px}
.stage-actions {display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 0}
.design-fields {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:12px 0}
.design-fields label {display:flex;flex-direction:column;gap:6px;font-size:14px;color:var(--muted)}
.design-fields select {width:100%;font-size:16px}
#architecture-arrange {background:transparent}
#terrain-map {display:block;margin:12px 0}
#architecture-status {margin-top:12px;overflow-wrap:anywhere}
#architecture-status details {border-top:1px solid var(--line)}
#architecture-status summary {font-size:15px}
#terrain-summary,#architecture-next {margin-bottom:12px}
.setup-choice {display:block;margin-top:12px}
#ai-privacy {font-size:13px;margin:8px 0 0}
#design-mode-label {display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-weight:600}
#design-mode-label input {width:18px;height:18px;margin:0}
#design-mode-label .meta {margin-left:auto;font-weight:400}
#plan-guide {margin:8px 0 12px}
#draft {min-height:88px}
#activity-panel {padding:12px 0;margin:0}
@media(max-width:900px) {
  .world {grid-column:1;grid-row:auto}
  .world > .status {margin-bottom:12px}
  #session-tools {margin-top:12px}
  main > .chat {grid-column:1;grid-row:auto;height:560px;min-height:420px}
  #design-panel {grid-column:1;grid-row:auto;margin:0}
  .session-more {grid-column:1;grid-row:auto}
  #project-tools,#session-details,.beta-limits {margin:0}
  main {gap:16px}
}
@media(max-width:480px) {
  .design-fields {grid-template-columns:1fr}
  #design-panel {padding:16px}
  .stage-actions {display:grid;grid-template-columns:1fr}
  .stage-actions button {width:100%}
  .design-views svg {height:200px}
  #design-mode-label .meta {margin-left:26px}
}

"""


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Game Companion</title>
<style>PAGE_STYLE</style></head><body data-token="TOKEN_VALUE" data-selected="SELECTED_VALUE">
<header><h1>Game Companion</h1><div class="selectors"><select id="game" aria-label="Game"><option value="">Choose a game</option><option value="minecraft">Minecraft</option></select><select id="world" aria-label="World"><option value="creative">Creative practice</option><option value="survival">Survival practice</option></select></div><div class="app-actions"><button id="stop">Stop</button><button id="quit">Quit app</button></div></header>
<main><section class="world" aria-label="Minecraft session"><div class="status"><h2 id="identity">Minecraft</h2><span id="connection" class="meta">Not connected</span></div>
<div id="setup-panel"><h2 id="setup-title">Open your world</h2><p id="setup-status" role="status"></p><div class="setup-actions"><button id="open-world" class="primary">Open saved world</button><button id="check-setup">Check setup again</button></div><div id="setup-links" class="setup-links"><a id="get-java" href="https://adoptium.net/temurin/releases/?version=21" target="_blank" rel="noopener">Get Java 21</a></div><details id="new-world"><summary id="new-world-title">Create a new practice world</summary><p>Existing saved worlds are never replaced.</p><label><input type="checkbox" id="eula"> I accept the <a href="https://www.minecraft.net/en-us/eula" target="_blank" rel="noopener">Minecraft EULA</a> for this new world.</label><label class="setup-choice"><input type="checkbox" id="build-enabled"> Enable project building in this new Creative world.</label><button id="create-world" class="primary">Create new practice world</button></details></div>
<div id="live-panel" hidden><div class="scene"><iframe id="view" title="Live Minecraft world" src="about:blank"></iframe></div></div><div class="toolbar" id="session-tools"><button id="toggle">Close view</button><label>Camera <select id="view-mode"><option value="overview">Overview</option><option value="inside">Eye level</option></select></label><button id="reconnect">Reconnect</button><span id="viewer-status" class="meta"></span></div>
<div class="activity-panel" id="activity-panel"><p id="activity" role="status"></p><div id="progress" class="meta"></div><div id="goal" class="meta"></div></div>
</section>
<section class="chat" aria-label="Companion chat"><div class="status"><h2>Companion</h2><span id="ai" class="meta">Checking AI…</span></div><p id="ai-privacy" class="meta"></p><div id="messages" role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions"><div id="empty-chat"><strong>What shall we do?</strong>Open a world to explore, gather or build together.</div></div><div id="pending" class="meta" role="status"></div><div id="error" role="alert"></div><form id="compose"><label id="design-mode-label" hidden><input id="design-mode" type="checkbox"> Plan project <span class="meta">No world changes</span></label><p id="plan-guide" class="meta" hidden>Start with 192 × 192 or 256 × 256 blocks. Put each place on its own line: Guest Cabin: building 8 by 8, 5 blocks high.</p><label for="draft" class="meta">Message your companion</label><textarea id="draft" maxlength="2000" aria-describedby="send-status" placeholder="Ask a question or describe what to do…"></textarea><div class="compose-actions"><span id="send-status" class="meta"></span><button id="send" type="submit">Send</button></div></form></section><section id="design-panel" hidden aria-label="Project design"><h2>Your project</h2><p id="project-next-step" role="status"></p><p id="design-summary"></p><p id="design-planning" role="status"></p><details id="design-checklist"><summary>Requirements and source brief</summary><div id="design-checklist-items"></div></details><div class="design-views" id="design-views"><figure><figcaption>Layout · north at top · blocks</figcaption><svg id="design-map" role="img" aria-label="Top-down layout"></svg></figure><details><summary>Height preview</summary><figure><figcaption>Height and massing · interpretation</figcaption><svg id="design-mass" role="img" aria-label="Massing preview"></svg></figure></details></div><div id="design-palette"></div><details id="design-measurements"><summary>Measurements and map key</summary><p id="design-estimate"></p></details><details><summary>Places in this design</summary><div id="design-components"></div></details><section class="project-stage" aria-label="Terrain review"><h3>1. Landscape</h3><svg id="terrain-map" role="img" aria-label="Reviewed terrain elevation and water" style="width:100%;max-height:320px"></svg><p id="terrain-summary" role="status"></p><details id="terrain-details"><summary>Landscape details</summary><p id="terrain-status">Review the terrain before expanding construction beyond the sample site. Buildings and interiors use their own architecture review below.</p></details><div class="stage-actions"><button id="terrain-review">Review landscape</button><button id="terrain-refresh">Review path changes</button><button id="terrain-run" class="primary">Start / continue landscape</button></div></section><section class="project-stage" aria-label="Architecture review"><h3>2. Buildings</h3><p id="architecture-next" class="meta"></p><div class="design-fields"><label>Place <select id="architecture-component"><option value="">All supported places</option></select></label><label>Materials <select id="architecture-material"><option value="warm">Warm oak and dark roof</option><option value="coastal">Pale coastal walls</option><option value="natural">Spruce and stone</option><option value="industrial">Stone brick and dark roof</option><option value="glass">Glass walls and roof, stone floor</option></select></label></div><div class="stage-actions"><button id="architecture-review">Review buildings</button><button id="architecture-run" class="primary">Build / continue buildings</button><button id="architecture-arrange">Separate overlaps</button></div><div id="architecture-status" role="status"></div></section><details><summary>Edit a place</summary><div class="design-fields"><label>Place <select id="design-edit-name"></select></label><label>Shape <select id="design-edit-kind"><option value="pavilion">Open pavilion</option><option value="platform">Platform</option><option value="building">Building</option><option value="terrain">Terrain</option><option value="water">Water</option><option value="grove">Trees</option><option value="cave">Cave</option><option value="tower">Tower</option><option value="bridge">Bridge</option><option value="dock">Dock</option><option value="wreck">Decorative wreck</option><option value="path">Path</option><option value="decoration">Decoration</option></select></label><label>Width <input id="design-width" type="number" min="1" max="64"></label><label>Depth <input id="design-depth" type="number" min="1" max="64"></label><label>Height <input id="design-height" type="number" min="1" max="48"></label><label>Area <select id="design-zone"><option>north</option><option>south</option><option>east</option><option>west</option><option>center</option></select></label><label>Elevation <select id="design-level"><option value="shore">Ground / shore</option><option value="raised">Raised, 4 blocks</option><option value="ridge">Ridge, 24 blocks</option></select></label><label>Rotation <select id="design-turn"><option value="0">0°</option><option value="1">90°</option><option value="2">180°</option><option value="3">270°</option></select></label></div><button id="design-save-edit">Save design change</button></details><details><summary>Advanced: small preview at the test site</summary><label for="design-component">Small component to build</label><select id="design-component"></select><button id="design-prepare">Prepare selected preview</button><button id="design-build">Build selected preview</button><p>Preparing inspects the world but does not change blocks. This builds a component sample at the local preview site, not at its whole-project destination. Landscape construction has its own review and start controls. Build buildings and interiors at their reserved destinations using the architecture controls above. Review changes before continuing.</p></details><details><summary>Reference images and captions</summary><p id="design-vision">Image analysis unavailable. Images are retained for your comparison; the planner uses your captions only.</p><label>PNG or JPEG, up to 4 MB <input id="design-file" type="file" accept="image/png,image/jpeg"></label><label>How should this reference be used?<input id="design-caption" maxlength="500" placeholder="Use this roof shape; source: my photo"></label><button id="design-upload">Save reference</button><div id="design-references"></div></details></section><section class="session-more" aria-label="Session options"><details id="project-tools" hidden><summary>Construction engineering preview</summary><p>Advanced test controls. For ordinary projects, use the landscape and building controls above. Existing player edits are protected by conflict checks.</p><button id="project-prepare">Prepare test section</button><button id="project-run">Build / Continue</button><button id="project-undo">Undo latest design</button><button id="project-undo-unmodified">Undo unchanged cells only</button></details><details id="session-details"><summary>Session details &amp; recovery</summary><pre id="details"></pre><div id="memory-recovery"></div><a href="/legacy-games">Engineering &amp; historical games</a></details><details class="beta-limits"><summary>Practice limits and controls</summary><p>Stop ends companion work, not the Minecraft world. Reopening never resumes work automatically. Native functions need live verification; decorative objects do not simulate machinery or storage.</p><p>Peaceful practice: resource trips and revisions may be partial, and some sites are inaccessible. Creative projects support reviewed landscapes and buildings; some designs or sites need adjustment. Chat advice and recall can be incomplete. Hostile survival and stone-tool chains remain limited.</p></details></section></main>
<script src="/assets/minecraft-chat.js" defer></script></body></html>""".replace("PAGE_STYLE", GLASS_CSS + MINECRAFT_CSS)
