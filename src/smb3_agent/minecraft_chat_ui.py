"""Minecraft document renderer; behavior is served as a separate script."""

from html import escape

from smb3_agent.glass_ui import GLASS_CSS
from smb3_agent.minecraft_chat_script import CHAT_JS as CHAT_JS


def render_minecraft_chat(token, *, selected=False):
    return PAGE.replace("TOKEN_VALUE", escape(token, quote=True)).replace(
        "SELECTED_VALUE", "true" if selected else "false"
    )


MINECRAFT_CSS = """
* {
  box-sizing:border-box
}
[hidden] {
  display:none!important
}
body {
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
#sign-in[hidden] {
  display:none
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
  .chat #codex {
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
"""


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Game Companion</title>
<style>PAGE_STYLE</style></head><body data-token="TOKEN_VALUE" data-selected="SELECTED_VALUE">
<header><h1>Game Companion</h1><div class="selectors"><select id="game" aria-label="Game"><option value="">Choose a game</option><option value="minecraft">Minecraft</option></select><select id="world" aria-label="World"><option value="creative">Creative practice</option><option value="survival">Survival practice</option></select></div><div class="app-actions"><button id="stop">Stop</button><button id="quit">Quit app</button></div></header>
<main><section class="world" aria-label="Minecraft session"><div class="status"><h2 id="identity">Minecraft</h2><span id="connection" class="meta">Not connected</span></div>
<div id="setup-panel"><h2>Open your world</h2><p id="setup-status" role="status"></p><div class="setup-actions"><button id="open-world" class="primary">Open retained world</button><button id="check-setup">Check setup again</button></div><div id="setup-links" class="setup-links"><button id="sign-in">Sign in to Codex</button><a id="get-codex" href="https://developers.openai.com/codex/cli" target="_blank" rel="noopener">Get Codex CLI</a><a id="get-java" href="https://adoptium.net/temurin/releases/?version=21" target="_blank" rel="noopener">Get Java 21</a></div><details><summary>Create a new practice world</summary><p>Creates the selected Creative or peaceful Survival world only when no retained world exists.</p><label><input type="checkbox" id="eula"> I accept the <a href="https://www.minecraft.net/en-us/eula" target="_blank" rel="noopener">Minecraft EULA</a> for this new world.</label><button id="create-world">Create new practice world</button></details></div>
<div id="live-panel" hidden><div class="scene"><iframe id="view" title="Live Minecraft world" src="about:blank"></iframe></div></div><div class="toolbar" id="session-tools"><button id="toggle">Close view</button><button id="reconnect">Reconnect</button><span id="viewer-status" class="meta"></span></div>
<div class="activity-panel" id="activity-panel"><p id="activity" role="status"></p><div id="progress" class="meta"></div><div id="goal" class="meta"></div></div>
<details id="session-details"><summary>Session details &amp; recovery</summary><pre id="details"></pre><div id="memory-recovery"></div><a href="/legacy-games">Engineering &amp; historical games</a></details><details class="beta-limits"><summary>Practice-world limits</summary><p>Peaceful practice: resource trips and revisions may be partial, and some sites are inaccessible. Stone-tool chains, hostile survival and broader building are not verified. Recall can be incomplete.</p></details></section>
<section class="chat" aria-label="Companion chat"><div class="status"><h2>Companion</h2><span id="codex" class="meta">Checking Codex…</span></div><div id="messages" role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions"><div id="empty-chat"><strong>What shall we do?</strong>Open a world to explore, gather or build together.</div></div><div id="pending" class="meta" role="status"></div><div id="error" role="alert"></div><form id="compose"><label for="draft" class="meta">Message your companion</label><textarea id="draft" maxlength="2000" aria-describedby="send-status" placeholder="Gather eight oak logs and return to camp…"></textarea><div class="compose-actions"><span id="send-status" class="meta"></span><button id="send" type="submit">Send</button></div></form></section></main>
<script src="/assets/minecraft-chat.js" defer></script></body></html>""".replace("PAGE_STYLE", GLASS_CSS + MINECRAFT_CSS)
