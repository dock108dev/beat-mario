"""Trusted shared visual styles, embedded to preserve the UI CSP."""

GLASS_CSS = """
/* Shared Glass UI Starter 02; task-first local adaptation. See docs/ui-design.md. */
:root{--app-bg:#edf3fc;--surface:rgba(255,255,255,.8);--surface-alt:#eaf0fb;--text:#182338;--muted:#54647b;--line:rgba(83,108,150,.2);--line-strong:#9daec8;--navy:#0969df;--blue:#0969df;--blue-soft:#e6efff;--badge:#e6efff}
body{background:radial-gradient(ellipse at 0 0,#d4e6ff,transparent 55%),radial-gradient(ellipse at 100% 35%,#e3dcfa,transparent 50%),#edf3fc;background-size:auto;background-attachment:fixed;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
h1{letter-spacing:-.8px;line-height:1.15}h2{letter-spacing:-.3px}.companion-top,.catalog-header,.onboarding header,.lab-top{background:#ffffffbb;color:var(--text);border:1px solid white;border-radius:24px;box-shadow:0 12px 36px #334d7914;backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px)}.companion-top p,.catalog-header p,.onboarding header p,.lab-top p,.companion-top .eyebrow{color:var(--muted)}
.session-card,.catalog-card,.catalog-workspace,.catalog-empty,.catalog-preferences,.step,.action-card,.installed,.result,.proof-limits{background:var(--surface);border:1px solid white;border-radius:22px;box-shadow:0 12px 36px #334d7910,inset 0 1px 0 white;backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}.catalog-card.selected{border:2px solid #69aaff}.catalog-capability{border-radius:14px}.primary-button{background:linear-gradient(#2588fc,#0969df);border-color:#1472de;box-shadow:0 4px 12px #1575e626}.primary-button:hover{background:#075ac0;border-color:#075ac0}button,button.small,button.quiet,.primary-button,.secondary-button,.nav-link,textarea,select,input{border-radius:13px}button,.primary-button,.secondary-button,button.small,button.quiet{min-height:44px}input:not([type=checkbox]):not([type=radio]):not([type=hidden]),select{min-height:44px}.persistent-reclaim button,.danger{background:var(--red);color:white;border-color:var(--red)}.persistent-reclaim button:hover,.danger:hover{background:#982c27}.mode-grid a{border-radius:13px;min-height:44px}*:focus-visible{outline:3px solid #0969df;outline-offset:3px}
#setup{scroll-margin-top:160px}
/* Keep routine content compact without shrinking text or controls. */
.companion-top,.catalog-header{padding:12px 16px}.companion-top nav{display:flex;flex-wrap:wrap;gap:8px}.companion-top h1{font-size:24px}.app-context{font-size:16px;font-weight:500;color:var(--muted)}.catalog-shell main{margin-top:16px}.catalog-card .section-title{align-items:start}.catalog-card .callout{margin:10px 0 12px}.catalog-card summary,.catalog-workspace summary,.catalog-display>summary{min-height:44px;padding:10px 0;cursor:pointer}.catalog-card details{padding-top:0;margin-top:4px}.catalog-card p,.catalog-workspace p{overflow-wrap:anywhere}.catalog-workspace{margin-bottom:16px}.catalog-workspace dd{margin-left:0}.catalog-runtime{font-size:14px}.catalog-runtime dt{text-transform:none;letter-spacing:0}.catalog-shell .meta{font-size:14px}.session-more>.companion-more-grid{padding:12px}.companion-main>.session-more{margin-top:0}.catalog-capability .status-pill{text-transform:none;letter-spacing:0}
/* Working content carries emphasis; setup and optional tools use quieter surfaces. */
body{background:radial-gradient(ellipse at 0 0,#e0ecfc,transparent 65%),#f1f4fa}
.companion-top,.catalog-header{box-shadow:none;border-radius:18px}
.catalog-setup{display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:24px;align-items:center;margin-top:16px;box-shadow:none;border:1px solid var(--line);border-radius:18px}
.catalog-setup h2,.catalog-setup .catalog-permissions,.catalog-setup #backend-status,.catalog-setup>.meta{grid-column:1}
.catalog-shell .catalog-setup p{margin:4px 0}.catalog-setup>form{grid-column:2;grid-row:1/5}.catalog-setup>details{grid-column:1/-1}
.catalog-card{box-shadow:0 4px 16px #334d7908}.catalog-card .callout{background:transparent;padding:0;color:var(--text);border:0;min-height:48px}.catalog-card .section-title{gap:12px}.catalog-card .section-title h2{line-height:1.3}
.catalog-card details{border-top:0}.catalog-card details+details{margin-top:0}.catalog-shell .catalog-card button{font-size:16px}.catalog-shell #games-heading{font-size:22px;margin:16px 0 8px}
.conversation-workspace summary,.catalog-card summary,.catalog-setup summary{box-sizing:border-box}
.conversation-workspace textarea{padding:12px;border:1px solid var(--line-strong);background:#fff;color:var(--text);border-radius:12px;line-height:1.5}
.conversation-workspace textarea::placeholder{color:#59677b;opacity:1}
.conversation-workspace textarea+button{margin-top:8px}
.conversation-workspace .conversation-transcript li,.conversation-workspace .conversation-status dd,.conversation-workspace .conversation-plan ol{font-size:16px}
.conversation-workspace .conversation-transcript li{border-radius:12px;background:#edf2fa}
.conversation-workspace .conversation-transcript li[data-role=user]{background:#e4edfc}
.conversation-workspace>.conversation-tools,.conversation-workspace>.conversation-saved,.conversation-workspace>.conversation-records{background:transparent;box-shadow:none;border:0;border-top:1px solid var(--line);border-radius:0;backdrop-filter:none;padding:0 16px}
.conversation-workspace>.conversation-tools>summary{padding:12px 0}
.conversation-workspace button:disabled{opacity:1;background:#edf1f7;color:#54647b;border-color:#bccde5;box-shadow:none;cursor:not-allowed}
.conversation-workspace button:not(:disabled):not(.primary-button):not(.danger):hover,.conversation-controls button:not(:disabled):not(.danger):hover{background:#e6efff;border-color:#7799c9}
#stardew-target-editor{padding-top:16px;border-top:1px solid var(--line)}
#stardew-targets label{box-sizing:border-box;padding:6px 10px;border:1px solid var(--line);border-radius:10px;background:#f4f7fc}
#stardew-targets label:has(input:checked){background:var(--blue-soft);border-color:var(--blue)}
#stardew-target-editor button{margin-top:8px}
@media(max-width:700px){.catalog-setup{display:block}.catalog-setup>form{margin:8px 0}.catalog-card .callout{min-height:0}.conversation-workspace>.conversation-tools,.conversation-workspace>.conversation-saved,.conversation-workspace>.conversation-records{padding-inline:4px}}
@media(max-width:760px){.companion-shell,.catalog-shell,.onboarding{padding:14px}.companion-top,.catalog-header,.onboarding header{border-radius:22px;gap:14px}.catalog-header{flex-wrap:wrap}.session-card{border-radius:20px}}
@media(prefers-reduced-transparency:reduce){.companion-top,.catalog-header,.onboarding header,.lab-top,.session-card,.catalog-card,.catalog-workspace,.step,.action-card{background:#f8faff;backdrop-filter:none;-webkit-backdrop-filter:none}}
@supports not (backdrop-filter:blur(1px)){.session-card,.catalog-card,.companion-top,.catalog-header{background:#f8faff}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
"""

STARDEW_GLASS_CSS = """
:root{--bg:#edf3fc;--panel:rgba(255,255,255,.82);--ink:#182338;--muted:#54647b;--accent:#0969df;--safe:#08725e;--danger:#b32c46}
main[data-testid=stardew-operator]>header,main[data-testid=stardew-operator] section{border:1px solid white;border-radius:24px;box-shadow:0 12px 36px #334d7910;background:var(--panel);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}main[data-testid=stardew-operator]>section{margin-top:16px}main[data-testid=stardew-operator] .grid{grid-template-columns:repeat(5,minmax(0,1fr));background:#dce5f4;border-color:white;border-radius:24px}main[data-testid=stardew-operator] .metric{background:#f5f8ff}main[data-testid=stardew-operator] button{background:#ffffffd9;border:1px solid #bccde5;color:#184779;min-height:44px;border-radius:13px}main[data-testid=stardew-operator] .failure{border-color:var(--danger)}
main[data-testid=stardew-operator]>header,main[data-testid=stardew-operator] section{padding:16px}main[data-testid=stardew-operator] h1{font-size:26px;margin-bottom:8px}main[data-testid=stardew-operator] h2{font-size:20px;margin-bottom:8px}main[data-testid=stardew-operator] p{margin-bottom:8px}main[data-testid=stardew-operator] nav{float:right;margin:0 0 12px 16px}main[data-testid=stardew-operator] a{color:#075ac0}main[data-testid=stardew-operator] summary{min-height:44px;padding:10px 0;cursor:pointer;font-weight:600}main[data-testid=stardew-operator] .stardew-progress{margin-top:12px}main[data-testid=stardew-operator] .metric{padding:12px}main[data-testid=stardew-operator] button[disabled]{opacity:1;color:#54647b;background:#edf1f7;cursor:not-allowed}main[data-testid=stardew-operator] .actions{margin-top:12px}
@media(max-width:650px){main[data-testid=stardew-operator] .mode-grid,main[data-testid=stardew-operator] .grid{grid-template-columns:1fr}main[data-testid=stardew-operator] nav{float:none;margin:0 0 12px}main[data-testid=stardew-operator] p{overflow-wrap:anywhere}}
@media(prefers-reduced-transparency:reduce){main[data-testid=stardew-operator]>header,main[data-testid=stardew-operator] section{background:#f8faff;backdrop-filter:none;-webkit-backdrop-filter:none}}
"""
