"""Minecraft document renderer; behavior is served as a separate script."""

from html import escape

from smb3_agent.glass_ui import GLASS_CSS
from smb3_agent.minecraft_chat_script import CHAT_JS as CHAT_JS


def render_minecraft_chat(token, *, selected=False):
    return PAGE.replace("TOKEN_VALUE", escape(token, quote=True)).replace(
        "SELECTED_VALUE", "true" if selected else "false"
    )


MINECRAFT_CSS = """

* {box-sizing:border-box}
[hidden] {display:none!important}
html,body {height:100%;margin:0}
body {color:var(--text);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f7fb;overflow:hidden}
button,select,textarea,input {font:inherit;color:inherit}
button,select {min-height:40px;padding:8px 12px;border:1px solid var(--line-strong);border-radius:10px;background:#fff;cursor:pointer}
button {font-weight:600}
button:hover:not(:disabled) {background:var(--blue-soft);border-color:var(--blue)}
button:disabled {color:var(--muted);background:#edf1f7;cursor:not-allowed}
button:focus-visible,select:focus-visible,textarea:focus-visible,input:focus-visible,summary:focus-visible,a:focus-visible {outline:3px solid var(--blue);outline-offset:3px}
a {color:#075ac0}
h1,h2,h3,p {margin:0}
h1,h2 {font-size:18px;line-height:1.4;letter-spacing:-.3px}
h3 {font-size:17px;margin-bottom:12px}
header {height:60px;padding:8px 20px;display:flex;align-items:center;gap:16px;background:#fff;border-bottom:1px solid var(--line)}
header h1 {white-space:nowrap}
.app-actions {margin-left:auto;display:flex;align-items:center;gap:8px}
.quiet {border-color:transparent;background:transparent}
#stop,#review-stop {color:#a12435;background:#fff0f1;border-color:#e4b6bd}
#connection {font-size:13px;display:flex;align-items:center;gap:7px;color:var(--muted)}
#connection::before {content:"";width:7px;height:7px;border-radius:50%;background:#718096}
body[data-connected=true] #connection::before {background:#08725e}
main {height:calc(100dvh - 60px);display:grid;grid-template-columns:minmax(0,1fr) 380px;overflow:hidden}
.world {position:relative;min-width:0;min-height:0;background:#dce9ee;overflow:hidden}
#live-panel,.scene,#view {width:100%;height:100%;min-height:0}
#view {display:block;border:0;background:#dce9ee}
.toolbar {position:absolute;left:16px;bottom:16px;display:flex;align-items:center;gap:8px;max-width:calc(100% - 32px);padding:6px;background:#ffffffed;border:1px solid #fff;border-radius:14px;box-shadow:0 4px 24px #18233820}
.toolbar label {display:flex;align-items:center;gap:8px;font-size:13px}
.toolbar select,.toolbar button {border-color:transparent;background:transparent}
#activity-panel {position:absolute;top:16px;left:16px;max-width:calc(100% - 32px);background:#fffffff2;border-radius:12px;padding:10px 14px;box-shadow:0 2px 16px #18233815;font-size:14px;overflow-wrap:anywhere;max-height:28%;overflow:auto}
#activity {font-weight:600}
#progress,#goal {font-size:13px;color:var(--muted)}
#progress:empty,#goal:empty {display:none}
#viewer-status:not(:empty) {position:absolute;bottom:82px;left:16px;right:16px;width:fit-content;padding:8px 12px;border-radius:10px;background:#fff;color:var(--muted);font-size:13px}
.chat {display:flex;flex-direction:column;min-width:0;min-height:0;background:#fff;border-left:1px solid var(--line);overflow:hidden}
.chat-heading {padding:16px 20px;display:flex;align-items:center;gap:8px;border-bottom:1px solid var(--line);flex-shrink:0}
.chat-heading h2 {flex:1}
#open-project {font-size:14px;min-height:36px}
#messages {flex:1;overflow:auto;min-height:60px;padding:20px;overflow-wrap:anywhere;overscroll-behavior:contain;scrollbar-gutter:stable}
.message {line-height:1.6;margin-bottom:24px;font-size:16px}
.message.user {background:#edf3fd;border-radius:16px 16px 4px 16px;padding:12px 14px;margin-left:24px}
.message .role {display:block;font-size:12px;font-weight:600;color:var(--muted);margin-bottom:6px}
.message p {margin:0 0 10px;white-space:pre-wrap}
.message p:last-child {margin-bottom:0}
.message ul {padding-left:20px;margin:8px 0 12px}
.message li {margin:6px 0}
.message.user .role {display:none}
#empty-chat {padding:28px 0;color:var(--muted)}
#empty-chat strong {display:block;font-size:20px;color:var(--text);margin-bottom:8px}
#compose {margin:0;padding:12px 16px 16px;border-top:1px solid var(--line);flex-shrink:0;background:#fff}
#draft {display:block;width:100%;resize:none;min-height:76px;height:76px;max-height:150px;padding:12px;border:1px solid #aab8ca;border-radius:12px;background:#fff;line-height:1.5}
#draft::placeholder {color:#637084;opacity:1}
.compose-actions {display:flex;align-items:center;gap:8px;margin-top:8px;min-height:40px}
#send {margin-left:auto;min-width:72px}
.primary,#send {background:var(--blue);color:#fff;border-color:var(--blue)}
.primary:hover:not(:disabled),#send:hover:not(:disabled) {background:#075ac0;color:#fff}
.primary:disabled,#send:disabled {background:#edf1f7;color:var(--muted);border-color:#c4cedd}
#design-mode-label {display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer;white-space:nowrap}
#design-mode {width:16px;height:16px;margin:0;accent-color:var(--blue)}
#plan-guide {margin:0 0 8px;font-size:13px;color:var(--muted)}
#send-status {font-size:12px;color:var(--muted);line-height:1.35}
#pending:not(:empty),#error:not(:empty) {padding:10px 16px;font-size:14px;flex-shrink:0;max-height:120px;overflow:auto;overflow-wrap:anywhere}
#pending {color:var(--muted)}
#error:not(:empty) {color:#912336;background:#fff0f2;border-top:1px solid #e8b3bc;white-space:pre-wrap}
#project-notice {display:block;text-align:left;border:0;border-radius:0;padding:10px 20px;background:var(--blue-soft);color:#075ac0;font-size:14px;flex-shrink:0}
.sr-only {position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.meta {font-size:14px;color:var(--muted)}
dialog {border:1px solid var(--line);border-radius:20px;padding:0;width:min(620px,calc(100vw - 32px));max-height:calc(100dvh - 40px);color:var(--text);background:#fff;box-shadow:0 24px 100px #18233840;overflow:auto;overscroll-behavior:contain}
dialog::backdrop {background:#18233866}
.dialog-heading {position:sticky;top:0;z-index:1;display:flex;align-items:center;gap:8px;padding:14px 20px;background:#fff;border-bottom:1px solid var(--line)}
.dialog-heading h2 {flex:1}
.dialog-body,#design-panel {padding:20px}
.panel-feedback:empty {display:none}
.panel-feedback:not(:empty) {padding:12px 20px;background:#fff0f2;color:#912336;white-space:pre-wrap;overflow-wrap:anywhere}
.dialog-body>details {border-top:1px solid var(--line);margin-top:16px}
.dialog-body>p {margin:8px 0 16px}
summary {cursor:pointer;padding:12px 0;font-weight:600;min-height:44px}
details p {margin:8px 0 12px}
pre {font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere}
#setup-panel {position:absolute;inset:24px;max-width:520px;max-height:calc(100% - 48px);overflow:auto;margin:auto;padding:24px;border:1px solid #fff;border-radius:20px;background:#fffffff5;height:fit-content;box-shadow:0 8px 32px #334d7910}
#setup-panel h2 {font-size:24px;margin-bottom:12px}
#setup-status {margin-bottom:20px;overflow-wrap:anywhere}
.setup-actions,.setup-links,.selectors {display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
.setup-choice {display:block;margin-top:12px}
#create-world {display:block;margin-top:16px}
#setup-panel details {border-top:1px solid var(--line)}
#identity {margin-bottom:12px}
#memory-recovery label {display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
#memory-recovery p {color:#a12435}
#design-panel>h2 {display:none}
#project-next-step:not(:empty) {margin-bottom:16px;font-size:15px}
#design-summary {font-size:14px;color:var(--muted);overflow-wrap:anywhere;margin-bottom:12px}
#design-planning:not(:empty) {background:var(--blue-soft);padding:12px;border-radius:10px;margin-bottom:12px}
.design-views figure {margin:0;min-width:0}
.design-views svg {width:100%;height:220px;background:#edf2f8;border-radius:12px}
.design-views figcaption {font-size:13px;color:var(--muted);margin-bottom:8px}
#design-palette span {display:inline-block;padding:4px 10px;border-radius:6px;background:var(--blue-soft);font-size:13px;margin:8px 6px 0 0}
#design-components {display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px}
.design-card {padding:12px;border:1px solid var(--line);border-radius:10px;font-size:14px}
.design-card.changed {border-color:var(--blue)}
.project-stage {border-top:1px solid var(--line);margin-top:20px;padding-top:20px}
.stage-actions {display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.design-fields {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:12px 0}
.design-fields label {display:flex;flex-direction:column;gap:6px;font-size:14px;color:var(--muted)}
input:not([type=checkbox]):not([type=radio]),.design-fields select {width:100%;min-width:0;border:1px solid var(--line-strong);background:#fff;border-radius:8px;padding:10px}
label,select,button {max-width:100%}
select {min-width:0;text-overflow:ellipsis}
#terrain-map {display:block;margin:12px 0}
#architecture-status {margin-top:12px;overflow-wrap:anywhere;font-size:14px}
#architecture-status details {border-top:1px solid var(--line)}
#design-references img {max-width:150px;max-height:120px}
#design-caption {width:100%}
#terrain-summary,#architecture-next {font-size:14px;color:var(--muted)}
body[data-theater=true] main {grid-template-columns:1fr}
body[data-theater=true] .chat {display:none}
@media(min-width:1400px) {main {grid-template-columns:minmax(0,1fr) 420px}}
@media(max-width:760px) {
 header {height:56px;padding:8px 12px;gap:10px}
 header h1 {font-size:16px}
 #connection {font-size:0;gap:0}
 .app-actions {gap:4px}
 main {height:calc(100dvh - 56px);grid-template-columns:minmax(0,1fr);grid-template-rows:minmax(140px,42%) minmax(0,1fr)}
 .chat {border-left:0;border-top:1px solid var(--line)}
 .chat-heading {padding:8px 16px}
 #messages {padding:12px 16px}
 #compose {padding:8px 12px}
 #draft {height:56px;min-height:56px}
 .toolbar {left:8px;bottom:8px;padding:2px;gap:4px}
 .toolbar button,.toolbar select {font-size:13px;min-height:36px;padding:6px 8px}
 #viewer-status:not(:empty) {bottom:60px;left:8px}
 #activity-panel {top:8px;left:8px;padding:6px 10px}
 body[data-theater=true] main {grid-template-rows:1fr}
 dialog {max-height:calc(100dvh - 16px);width:calc(100vw - 16px)}
 .dialog-heading {padding:10px 12px}
 .dialog-body,#design-panel {padding:16px}
 .design-fields {grid-template-columns:1fr}
 #setup-panel {inset:8px;max-height:calc(100% - 16px);padding:16px}
 #setup-panel h2 {font-size:18px}
}
@media(prefers-reduced-transparency:reduce) {.toolbar,#activity-panel,#setup-panel {background:#fff}}

"""


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Game Companion</title>
<style>PAGE_STYLE</style></head><body data-token="TOKEN_VALUE" data-selected="SELECTED_VALUE">
<header><h1>Minecraft</h1><span id="connection" class="meta" role="status">Not connected</span><div class="app-actions"><button id="stop">Stop</button><button id="open-settings" class="quiet" aria-haspopup="dialog">Settings</button></div></header>
<main><section class="world" aria-label="Minecraft world">
<div id="setup-panel"><h2 id="setup-title">Open your world</h2><p id="setup-status" role="status"></p><div class="setup-actions"><button id="open-world" class="primary">Open saved world</button><button id="check-setup">Check setup again</button></div><div id="setup-links" class="setup-links"><a id="get-java" href="https://adoptium.net/temurin/releases/?version=21" target="_blank" rel="noopener">Get Java 21</a></div><details id="new-world"><summary id="new-world-title">Create a new practice world</summary><p>Existing saved worlds are never replaced.</p><label><input type="checkbox" id="eula"> I accept the <a href="https://www.minecraft.net/en-us/eula" target="_blank" rel="noopener">Minecraft EULA</a> for this new world.</label><label class="setup-choice"><input type="checkbox" id="build-enabled"> Enable project building in this new Creative world.</label><button id="create-world" class="primary">Create new practice world</button></details></div>
<div id="live-panel" hidden><div class="scene"><iframe id="view" title="Live Minecraft world" src="about:blank"></iframe></div></div><div class="toolbar" id="session-tools"><label><span class="sr-only">Camera</span> <select id="view-mode"><option value="overview">Overview</option><option value="inside">Eye level</option></select></label><button id="theater" aria-pressed="false">Hide chat</button><button id="fullscreen">Full screen</button></div><span id="viewer-status" class="meta" role="status"></span>
<div class="activity-panel" id="activity-panel"><p id="activity" role="status"></p><div id="progress" class="meta"></div><div id="goal" class="meta"></div></div>
</section>
<section class="chat" aria-label="Companion chat"><div class="chat-heading"><h2>Companion</h2><button id="open-project" class="quiet" aria-haspopup="dialog" hidden>Project</button></div><button id="project-notice" hidden aria-haspopup="dialog"></button><div id="messages" role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions"><div id="empty-chat"><strong>What shall we do?</strong>Open a world to explore, gather or build together.</div></div><div id="pending" class="meta" role="status"></div><div id="error" role="alert"></div><form id="compose"><p id="plan-guide" class="meta" hidden>Start with 192 × 192 or 256 × 256 blocks. Put each place on its own line: Guest Cabin: building 8 by 8, 5 blocks high.</p><label for="draft" class="sr-only">Message your companion</label><textarea id="draft" maxlength="2000" aria-describedby="send-status" placeholder="What shall we build?"></textarea><div class="compose-actions"><label id="design-mode-label" hidden><input id="design-mode" type="checkbox"> Plan a build</label><span id="send-status" class="meta"></span><button id="send" type="submit">Send</button></div></form></section></main><dialog id="project-dialog" aria-labelledby="project-title"><div class="dialog-heading"><h2 id="project-title">Your project</h2><button id="review-stop">Stop</button><button id="close-project" autofocus class="quiet" aria-label="Close project">Done</button></div><p id="project-feedback" class="panel-feedback" role="alert"></p><section id="design-panel" hidden aria-label="Project design"><h2>Your project</h2><p id="project-next-step" role="status"></p><p id="design-summary"></p><p id="design-planning" role="status"></p><details id="design-checklist"><summary>Requirements and source brief</summary><div id="design-checklist-items"></div></details><div class="design-views" id="design-views"><figure><figcaption>Layout · north at top · blocks</figcaption><svg id="design-map" role="img" aria-label="Top-down layout"></svg></figure><details><summary>Height preview</summary><figure><figcaption>Height and massing · interpretation</figcaption><svg id="design-mass" role="img" aria-label="Massing preview"></svg></figure></details></div><div id="design-palette"></div><details id="design-measurements"><summary>Measurements and map key</summary><p id="design-estimate"></p></details><details><summary>Places in this design</summary><div id="design-components"></div></details><section class="project-stage" aria-label="Terrain review"><h3>1. Landscape</h3><svg id="terrain-map" role="img" aria-label="Reviewed terrain elevation and water" style="width:100%;max-height:320px"></svg><p id="terrain-summary" role="status"></p><details id="terrain-details"><summary>Landscape details</summary><p id="terrain-status">Review the terrain before expanding construction beyond the sample site. Buildings and interiors use their own architecture review below.</p></details><div class="stage-actions"><button id="terrain-review">Review landscape</button><button id="terrain-refresh">Review path changes</button><button id="terrain-run" class="primary">Start / continue landscape</button></div></section><section class="project-stage" aria-label="Architecture review"><h3>2. Buildings</h3><p id="architecture-next" class="meta"></p><div class="design-fields"><label>Place <select id="architecture-component"><option value="">All supported places</option></select></label><label>Materials <select id="architecture-material"><option value="warm">Warm oak and dark roof</option><option value="coastal">Pale coastal walls</option><option value="natural">Spruce and stone</option><option value="industrial">Stone brick and dark roof</option><option value="glass">Glass walls and roof, stone floor</option></select></label></div><div class="stage-actions"><button id="architecture-review">Review buildings</button><button id="architecture-run" class="primary">Build / continue buildings</button><button id="architecture-arrange">Separate overlaps</button></div><div id="architecture-status" role="status"></div></section><details><summary>Edit a place</summary><div class="design-fields"><label>Place <select id="design-edit-name"></select></label><label>Shape <select id="design-edit-kind"><option value="pavilion">Open pavilion</option><option value="platform">Platform</option><option value="building">Building</option><option value="terrain">Terrain</option><option value="water">Water</option><option value="grove">Trees</option><option value="cave">Cave</option><option value="tower">Tower</option><option value="bridge">Bridge</option><option value="dock">Dock</option><option value="wreck">Decorative wreck</option><option value="path">Path</option><option value="decoration">Decoration</option></select></label><label>Width <input id="design-width" type="number" min="1" max="64"></label><label>Depth <input id="design-depth" type="number" min="1" max="64"></label><label>Height <input id="design-height" type="number" min="1" max="48"></label><label>Area <select id="design-zone"><option>north</option><option>south</option><option>east</option><option>west</option><option>center</option></select></label><label>Elevation <select id="design-level"><option value="shore">Ground / shore</option><option value="raised">Raised, 4 blocks</option><option value="ridge">Ridge, 24 blocks</option></select></label><label>Rotation <select id="design-turn"><option value="0">0°</option><option value="1">90°</option><option value="2">180°</option><option value="3">270°</option></select></label></div><button id="design-save-edit">Save design change</button></details><details><summary>Advanced: small preview at the test site</summary><label for="design-component">Small component to build</label><select id="design-component"></select><button id="design-prepare">Prepare selected preview</button><button id="design-build">Build selected preview</button><p>Preparing inspects the world but does not change blocks. This builds a component sample at the local preview site, not at its whole-project destination. Landscape construction has its own review and start controls. Build buildings and interiors at their reserved destinations using the architecture controls above. Review changes before continuing.</p></details><details><summary>Reference images and captions</summary><p id="design-vision">Image analysis unavailable. Images are retained for your comparison; the planner uses your captions only.</p><label>PNG or JPEG, up to 4 MB <input id="design-file" type="file" accept="image/png,image/jpeg"></label><label>How should this reference be used?<input id="design-caption" maxlength="500" placeholder="Use this roof shape; source: my photo"></label><button id="design-upload">Save reference</button><div id="design-references"></div></details></section></dialog><dialog id="settings-dialog" aria-labelledby="settings-title"><div class="dialog-heading"><h2 id="settings-title">Settings</h2><button id="close-settings" autofocus class="quiet" aria-label="Close settings">Done</button></div><p id="settings-feedback" class="panel-feedback" role="alert"></p><section class="dialog-body" aria-label="Session options"><h3 id="identity">Minecraft</h3><div class="selectors"><select id="game" aria-label="Game"><option value="">Choose a game</option><option value="minecraft">Minecraft</option></select><select id="world" aria-label="World"><option value="creative">Creative practice</option><option value="survival">Survival practice</option></select></div><div class="stage-actions"><button id="toggle">Close view</button><button id="reconnect">Reconnect</button><button id="quit">Save and quit</button></div><details><summary>AI connection</summary><p id="ai" class="meta">Checking AI…</p><p id="ai-privacy" class="meta"></p></details><details id="project-tools" hidden><summary>Construction engineering preview</summary><p>Advanced test controls. For ordinary projects, use the landscape and building controls above. Existing player edits are protected by conflict checks.</p><button id="project-prepare">Prepare test section</button><button id="project-run">Build / Continue</button><button id="project-undo">Undo latest design</button><button id="project-undo-unmodified">Undo unchanged cells only</button></details><details id="session-details"><summary>Session details &amp; recovery</summary><pre id="details"></pre><div id="memory-recovery"></div><a href="/legacy-games">Engineering &amp; historical games</a></details><details class="beta-limits"><summary>Practice limits and controls</summary><p>Stop ends companion work, not the Minecraft world. Reopening never resumes work automatically. Native functions need live verification; decorative objects do not simulate machinery or storage.</p><p>Peaceful practice: resource trips and revisions may be partial, and some sites are inaccessible. Creative projects support reviewed landscapes and buildings; some designs or sites need adjustment. Chat advice and recall can be incomplete. Hostile survival and stone-tool chains remain limited.</p></details></section></dialog>
<script src="/assets/minecraft-chat.js" defer></script></body></html>""".replace("PAGE_STYLE", GLASS_CSS + MINECRAFT_CSS)
