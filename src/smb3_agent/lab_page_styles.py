"""Shared companion and Route Lab stylesheet, in cascade order."""

LAB_PAGE_CSS = """    :root {
      color-scheme: light;
      --app-bg: #f7f4ec;
      --surface: #ffffff;
      --surface-alt: #f8fafc;
      --text: #1f2937;
      --muted: #64748b;
      --line: #d6d3c8;
      --line-strong: #b8ad97;
      --screen: #1b2426;
      --screen-soft: #2f3a3d;
      --blue: #2563eb;
      --blue-soft: #eff6ff;
      --navy: #1e3a5f;
      --red: #c9362c;
      --red-soft: #fff1f0;
      --green: #1f7a4d;
      --green-soft: #edf9f1;
      --amber: #b7791f;
      --amber-soft: #fff7df;
      --badge: #f4ead3;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      overflow-x: hidden;
      background:
        linear-gradient(rgba(30,58,95,.026) 1px, transparent 1px),
        linear-gradient(90deg, rgba(30,58,95,.026) 1px, transparent 1px),
        var(--app-bg);
      background-size: 22px 22px;
      color: var(--text);
      font: 14px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    h1, h2, h3, p { margin-top: 0; }
    h1 { font-size: 26px; line-height: 1.05; margin-bottom: 4px; letter-spacing: 0; }
    h2 { font-size: 16px; margin-bottom: 2px; letter-spacing: 0; }
    h3 { font-size: 15px; margin-bottom: 4px; letter-spacing: 0; }
    a { color: inherit; }
    button {
      border: 1px solid var(--line-strong);
      background: var(--surface);
      color: var(--text);
      border-radius: 6px;
      padding: 7px 10px;
      font-weight: 750;
      cursor: pointer;
      min-height: 32px;
    }
    button:hover { background: var(--surface-alt); border-color: var(--navy); }
    button:disabled {
      cursor: not-allowed;
      opacity: .58;
      background: #eef0f2;
      border-color: var(--line);
    }
    .primary-button {
      border: 1px solid #8f251f;
      background: var(--red);
      color: #fff;
      min-height: 36px;
      padding: 8px 13px;
      box-shadow: 0 1px 0 rgba(31,41,55,.12);
    }
    .primary-button:hover { background: #b92f27; border-color: #7f211c; }
    .secondary-button {
      background: var(--surface);
      color: var(--text);
      border-color: var(--line-strong);
    }
    button.quiet, button.small {
      background: var(--surface);
      border-color: var(--line);
      color: var(--text);
    }
    button.quiet:hover, button.small:hover { border-color: var(--line-strong); background: var(--surface-alt); }
    button.small {
      min-height: 26px;
      padding: 4px 7px;
      font-size: 12px;
    }
    textarea, select, input {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      font: inherit;
      background: var(--surface);
      color: var(--text);
    }
    textarea { min-height: 118px; resize: vertical; }
    label { display: grid; gap: 4px; font-weight: 700; color: var(--text); }
    code {
      display: block;
      overflow-x: auto;
      color: var(--navy);
      white-space: nowrap;
    }
    .nav-link { display: inline-flex; align-items: center; text-decoration: none; }
    .companion-shell {
      min-height: 100vh;
      max-width: 1320px;
      margin: 0 auto;
      padding: 20px;
    }
    .companion-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      padding: 18px 20px;
      background: var(--navy);
      color: #fff;
      border-radius: 12px;
      box-shadow: 0 10px 28px rgba(31,41,55,.16);
    }
    .companion-top p { margin-bottom: 0; color: #dbeafe; }
    .companion-top .eyebrow {
      margin-bottom: 4px;
      color: #f8e8b0;
      font-size: 11px;
      font-weight: 900;
      letter-spacing: .12em;
      text-transform: uppercase;
    }
    .companion-top .nav-link { background: #fff; color: var(--navy); }
    .companion-main {
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 14px;
      margin-top: 14px;
    }
    .active-workspace { display: contents; }
    .session-card {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 16px;
      box-shadow: 0 8px 22px rgba(31,41,55,.07);
    }
    .identity-card, .observation-card { grid-column: span 6; }
    .learning-card, .live-observation-card, .objective-card, .session-more, .modes-card, .tell-request-card, .show-card, .handoff-card, .first-use-card, .product-overview, .recovery-card, [data-testid="session-history-metrics"] { grid-column: 1 / -1; }
    .safety-card { grid-column: span 7; }
    .activity-card { grid-column: span 5; }
    .game-name { font-size: 21px; font-weight: 850; margin-bottom: 4px; }
    .fact-grid, .handoff-list { margin: 0; display: grid; gap: 8px; }
    .fact-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .fact-grid div, .handoff-list div {
      border-top: 1px solid #e5e7eb;
      padding-top: 7px;
    }
    dt { color: var(--muted); font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }
    dd { margin: 2px 0 0; font-weight: 650; }
    .callout { margin: 12px 0 0; padding: 9px 10px; border-radius: 7px; background: var(--amber-soft); color: #744b14; }
    .status-fresh .callout { background: var(--green-soft); color: var(--green); }
    .control-line { margin: 6px 0 10px; padding: 8px 10px; border-radius: 7px; background: var(--amber-soft); color: #744b14; }
    .live-summary { display: grid; grid-template-columns: 1.2fr 2fr .6fr .8fr; gap: 8px; margin: 0; }
    .live-summary div { border-top: 1px solid #e5e7eb; padding-top: 7px; min-width: 0; }
    .live-summary dd { overflow-wrap: anywhere; }
    .status-message { margin: 9px 0; color: var(--muted); }
    .live-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
    .live-actions form { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
    label.inline-check { display: inline-flex; flex-direction: row; align-items: center; gap: 7px; }
    label.inline-check input { margin: 0; width: auto; }
    .live-indicator { color: var(--green); font-size: 12px; font-weight: 800; }
    .compact-link { display: inline-flex; align-items: center; min-height: 32px; text-decoration: none; }
    .technical-details, .session-more { margin-top: 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-alt); }
    .technical-details > summary, .session-more > summary { cursor: pointer; padding: 10px 12px; font-weight: 800; }
    .technical-details[open] { padding: 0 12px 12px; }
    .technical-details[open] > summary { margin: 0 -12px 10px; }
    .technical-facts { margin-bottom: 12px; }
    .selected-mode { margin: 2px 0 0; color: var(--muted); }
    .objective-controls { display: grid; grid-template-columns: 1.6fr 1fr 1.5fr auto; gap: 8px; align-items: end; margin: 12px 0; }
    .objective-controls label, .objective-tell-controls label { display: grid; gap: 4px; color: var(--muted); font-size: 12px; font-weight: 750; }
    .objective-controls select, .objective-tell-controls select { width: 100%; min-width: 0; }
    .objective-now { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .objective-now > div { border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: var(--surface-alt); }
    .objective-now p:last-child, .objective-now ul { margin-bottom: 0; }
    .objective-now ul { padding-left: 19px; }
    .inline-action { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
    .objective-tell-controls { display: grid; grid-template-columns: 2fr 1fr auto; gap: 8px; align-items: end; margin-top: 10px; }
    .compact-tell { margin-top: 10px; padding-top: 10px; }
    .compact-state { margin: 7px 0 0; color: var(--muted); font-size: 12px; font-weight: 750; }
    .session-more { background: transparent; }
    .session-more > summary { background: var(--surface); border-radius: 8px; box-shadow: 0 8px 22px rgba(31,41,55,.05); }
    .companion-more-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 14px; margin-top: 14px; }
    .mode-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
    .mode-grid a { display: grid; place-items: center; min-height: 38px; border: 1px solid var(--line); border-radius: 7px; background: var(--surface-alt); color: var(--navy); font-weight: 800; text-decoration: none; }
    .setup-steps, .capability-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; margin: 10px 0; }
    .first-use-card form { display: grid; gap: 9px; margin-top: 12px; }
    .first-use-card fieldset { display: grid; gap: 10px; border: 1px solid var(--line); border-radius: 8px; padding: 10px; }
    .first-use-card fieldset label { display: block; padding: 8px; border: 1px solid var(--line); border-radius: 7px; background: var(--surface-alt); }
    .first-use-card input[type="radio"], .first-use-card input[type="checkbox"] { width: auto; }
    .capability-item { border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: var(--surface-alt); }
    .capability-item > .status-pill { float: right; }
    .capability-item.unavailable { border-color: #e6d4aa; }
    .action-error, .recovery-card { border-color: #e8b3ae; background: var(--red-soft); color: #7f211c; }
    .persistent-reclaim { position: sticky; top: 8px; z-index: 20; display: grid; grid-template-columns: minmax(180px, .45fr) 1fr; gap: 10px; align-items: center; padding: 10px; margin-bottom: 10px; border: 2px solid var(--red); border-radius: 9px; background: #fff; box-shadow: 0 10px 30px rgba(127,33,28,.2); }
    .persistent-reclaim span { color: var(--red); font-weight: 800; }
    .mode-card { border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: var(--surface-alt); }
    .mode-card button { width: 100%; margin: 4px 0 8px; }
    .mode-reason { margin-bottom: 0; color: var(--muted); font-size: 12px; }
    .tell-request-card form { display: grid; gap: 12px; }
    .tell-request-card fieldset { display: grid; gap: 7px; border: 1px solid var(--line); border-radius: 7px; padding: 10px; }
    .tell-request-card fieldset label { display: flex; align-items: center; gap: 8px; }
    .tell-request-card input[type="checkbox"] { width: auto; }
    .tell-card { margin-top: 16px; border-top: 1px solid var(--line); padding-top: 16px; }
    .tell-card details { margin-top: 6px; color: var(--muted); font-size: 12px; }
    .tell-card details ul { margin: 5px 0; }
    .safety-card ul { padding-left: 19px; }
    .activity-list { min-height: 58px; padding-left: 20px; }
    .take-control { width: 100%; border-color: #8f251f; color: var(--red); }
    .handoff-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .state-completed { border-color: #86c7a4; }
    .state-failed { border-color: #e8b3ae; }
    .state-cancelled, .state-taken_over { border-color: #e3c987; }
    .route-lab {
      min-height: 100vh;
      padding: 14px;
      max-width: 1760px;
      margin: 0 auto;
    }
    .paper-panel, .route-index, .evidence-viewer, .teaching-panel {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 8px 22px rgba(31, 41, 55, .07);
    }
    .lab-top {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 14px;
      align-items: center;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      box-shadow: 0 8px 22px rgba(31, 41, 55, .06);
    }
    .lab-title, .run-strip, .route-step, .section-title, .location-head {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .lab-title p, .section-title p, .meta { margin: 0; color: var(--muted); font-size: 12px; }
    .goal-switcher {
      display: flex;
      gap: 4px;
      padding: 3px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--surface-alt);
    }
    .goal-choice {
      padding: 6px 10px;
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-decoration: none;
    }
    .goal-choice.goal-selected { background: var(--navy); color: #fff; }
    .section-title {
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 10px;
    }
    .asset-icon {
      width: 34px;
      height: 34px;
      display: inline-grid;
      place-items: center;
      flex: 0 0 auto;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: #f8edd0;
      color: var(--navy);
      font-weight: 900;
      font-size: 11px;
    }
    .asset-icon img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      border-radius: 5px;
    }
    .run-strip {
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .run-form {
      display: grid;
      grid-template-columns: 92px 92px 132px auto;
      gap: 8px;
      align-items: end;
    }
    .run-form label { font-size: 12px; }
    .last-result {
      display: grid;
      gap: 2px;
      min-width: 112px;
      padding-left: 10px;
      border-left: 1px solid var(--line);
    }
    .last-result span { color: var(--muted); font-size: 11px; }
    .last-result strong { font-size: 13px; }
    .lab-main {
      display: grid;
      grid-template-columns: 245px minmax(420px, 1fr) 340px;
      gap: 14px;
      margin-top: 14px;
      align-items: start;
    }
    .lab-main > *, .lab-bottom > * { min-width: 0; }
    .route-index, .evidence-viewer, .teaching-panel, .paper-panel {
      padding: 12px;
    }
    .route-list {
      display: grid;
      gap: 7px;
    }
    .route-step {
      min-height: 52px;
      padding: 8px;
      border: 1px solid #e5e7eb;
      border-radius: 7px;
      text-decoration: none;
      background: var(--surface);
    }
    .route-step:hover {
      border-color: var(--line-strong);
      background: var(--surface-alt);
    }
    .route-item-selected, .route-step:target {
      background: var(--blue-soft);
      border-color: #bfdbfe;
      box-shadow: inset 4px 0 0 var(--blue);
    }
    .route-copy { display: grid; gap: 1px; min-width: 0; }
    .route-copy small { color: var(--muted); font-size: 11px; }
    .clean, .passed, .status-clean, .status-learned { color: var(--green); }
    .status-validation { color: var(--amber); }
    .failed, .status-failed { color: var(--red); }
    .unknown, .status-unknown { color: var(--muted); }
    .screen-frame {
      min-height: 360px;
      display: grid;
      place-items: center;
      background:
        linear-gradient(135deg, rgba(255,255,255,.06) 25%, transparent 25%),
        linear-gradient(225deg, rgba(255,255,255,.06) 25%, transparent 25%),
        var(--screen);
      background-size: 18px 18px;
      border: 12px solid #293437;
      border-radius: 10px;
      box-shadow: inset 0 0 0 2px #101719;
      overflow: hidden;
    }
    .no-evidence-frame { min-height: 235px; }
    .screen-frame img {
      max-width: 100%;
      max-height: 620px;
      display: block;
      object-fit: contain;
      background: #000;
    }
    .empty-evidence {
      display: grid;
      gap: 6px;
      text-align: center;
      color: #e7f6ee;
      padding: 24px;
    }
    .empty-evidence span { color: #bdd4c9; }
    .evidence-notes {
      margin-top: 10px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--surface-alt);
      padding: 10px;
    }
    .evidence-notes h3 { color: var(--text); }
    .evidence-notes p { color: var(--text); }
    .evidence-notes ul {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 6px;
    }
    .evidence-notes li {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-top: 1px solid #e5e7eb;
      padding-top: 7px;
    }
    .evidence-notes li:first-child { border-top: 0; padding-top: 0; }
    .evidence-notes li span { color: var(--muted); text-align: right; }
    .evidence-notes li span { min-width: 0; overflow-wrap: anywhere; }
    .selected-location {
      background: var(--surface-alt);
      border: 1px solid #e5e7eb;
      border-radius: 7px;
      padding: 9px 10px;
      margin-bottom: 10px;
    }
    .selected-location p { margin: 4px 0 0; color: var(--muted); }
    .mode-tabs {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 4px;
      margin-bottom: 10px;
      padding: 4px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-alt);
    }
    .mode-tab {
      text-align: center;
      text-decoration: none;
      border-radius: 6px;
      padding: 6px 7px;
      font-weight: 800;
      font-size: 12px;
      color: var(--text);
      background: transparent;
    }
    .mode-tab:hover { background: #eef2f7; }
    .mode-tab.segment-active {
      background: var(--navy);
      color: #fff;
    }
    .mode-panel { display: grid; gap: 9px; }
    .note-tools { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
    .mini-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-top: 10px;
    }
    .lab-bottom {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr) minmax(0, .9fr);
      gap: 14px;
      margin-top: 14px;
    }
    .issue-list, .compact-list { display: grid; gap: 3px; }
    .compact-row {
      min-height: 34px;
      align-items: center;
      padding: 5px 0;
      border-top: 1px solid #e5e7eb;
    }
    .compact-row:first-child { border-top: 0; }
    .issue-summary-row {
      display: grid;
      grid-template-columns: 110px 72px 120px minmax(0, 1fr) 72px 58px;
      gap: 8px;
      font-size: 12px;
    }
    .observation-summary-row {
      display: grid;
      grid-template-columns: 48px 100px 76px minmax(0, 1fr) 76px 58px;
      gap: 8px;
      font-size: 12px;
    }
    .issue p, .note-row p { margin-bottom: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .selected-row { background: var(--blue-soft); }
    .compact-pick {
      display: grid;
      grid-template-columns: 78px minmax(0, 1fr) 62px;
      gap: 7px;
      align-items: center;
      text-decoration: none;
      padding: 6px 7px;
      border-radius: 6px;
      font-size: 12px;
    }
    .compact-pick strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .compact-pick:hover { background: var(--surface-alt); }
    .compact-pick.selected-row { background: var(--blue-soft); box-shadow: inset 3px 0 0 var(--blue); }
    .detail-panel {
      background: var(--surface-alt);
      border: 1px solid #e5e7eb;
      border-radius: 7px;
      padding: 10px;
      display: grid;
      gap: 8px;
    }
    .patch-workflow {
      display: grid;
      gap: 8px;
      border-top: 1px solid var(--line);
      margin-top: 4px;
      padding-top: 10px;
    }
    .patch-facts {
      display: grid;
      grid-template-columns: 90px minmax(0, 1fr);
      gap: 3px 8px;
      margin: 0;
      font-size: 12px;
    }
    .patch-facts dt { color: var(--muted); }
    .patch-facts dd { margin: 0; min-width: 0; }
    .patch-files, .patch-blockers { margin: 0; padding-left: 18px; font-size: 12px; }
    .patch-diff pre { max-height: 260px; font-size: 11px; }
    .patch-import-form, .patch-confirm-form { display: grid; gap: 6px; }
    .patch-actions { align-items: end; }
    .detail-head { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
    .row-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      align-items: center;
    }
    .row-actions details { position: relative; }
    .row-actions summary {
      cursor: pointer;
      border-radius: 6px;
      background: var(--surface);
      border: 1px solid var(--line);
      padding: 4px 7px;
      font-size: 12px;
      font-weight: 750;
    }
    .edit-form {
      display: grid;
      gap: 6px;
      margin-top: 6px;
      min-width: 220px;
    }
    .edit-form textarea { min-height: 80px; }
    .review-link {
      color: var(--blue);
      font-weight: 800;
      text-decoration: none;
    }
    .badges { display: flex; flex-wrap: wrap; gap: 5px; }
    .badge {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 7px;
      font-size: 12px;
      color: var(--text);
      background: var(--badge);
      font-weight: 750;
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 3px 7px;
      font-size: 12px;
      font-weight: 800;
    }
    .badge.high, .badge.failed, .status-pill.status-failed { color: var(--red); border-color: #e8b3ae; background: var(--red-soft); }
    .badge.medium, .badge.needs-validation, .status-pill.status-validation { color: var(--amber); border-color: #e5c989; background: var(--amber-soft); }
    .badge.none, .badge.clean, .badge.passed, .status-pill.status-learned { color: var(--green); border-color: #acd7b5; background: var(--green-soft); }
    .artifact-links {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin: 8px 0;
    }
    .artifact-links a {
      color: var(--blue);
      border: 1px solid var(--line);
      background: var(--surface);
      border-radius: 999px;
      padding: 4px 8px;
      text-decoration: none;
      font-size: 12px;
    }
    pre {
      max-height: 190px;
      overflow: auto;
      white-space: pre-wrap;
      background: var(--surface-alt);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px;
      color: var(--text);
    }
    .empty { color: var(--muted); margin-bottom: 0; }
    .error { border-color: #e8b3ae; color: var(--red); margin: 20px; padding: 14px; }
    @media (max-width: 1180px) {
      .lab-main { grid-template-columns: 220px minmax(0, 1fr); }
      .teaching-panel { grid-column: 1 / -1; }
      .lab-bottom { grid-template-columns: 1fr; }
    }
    @media (max-width: 760px) {
      .companion-shell { padding: 10px; }
      .companion-top { display: grid; }
      .companion-main { grid-template-columns: 1fr; }
      .live-observation-card, .objective-card, .session-more, .identity-card, .observation-card, .modes-card, .safety-card, .activity-card, .handoff-card, .first-use-card, .product-overview, .recovery-card, [data-testid="session-history-metrics"] { grid-column: 1; }
      .live-summary, .objective-controls, .objective-now, .objective-tell-controls, .companion-more-grid { grid-template-columns: 1fr; }
      .inline-action { align-items: stretch; flex-direction: column; }
      .mode-grid, .fact-grid, .handoff-list, .setup-steps, .capability-grid, .persistent-reclaim { grid-template-columns: 1fr; }
      .route-lab { padding: 10px; }
      .lab-top { display: grid; }
      .lab-main, .run-form { grid-template-columns: minmax(0, 1fr); }
      .goal-switcher { max-width: 100%; overflow-x: auto; }
      .run-strip { justify-content: flex-start; }
      .screen-frame { min-height: 280px; }
    }
    @media (max-width: 420px) {
      .companion-shell { padding: 6px; }
      .session-card { padding: 12px; }
      .live-actions, .takeover-panel form, .run-library-summary { min-width: 0; }
      .live-actions form, .takeover-panel button, .takeover-panel select,
      .takeover-panel input[type="number"] { width: 100%; }
      .section-title { align-items: flex-start; flex-direction: column; }
    }
"""
