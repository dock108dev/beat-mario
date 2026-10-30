"""Browser refresh behavior for the retained player workspace."""

PLAYER_WORKSPACE_JS = r'''(() => {
  const workspace = document.getElementById("active-workspace");
  if (!workspace) return;
  let updating = false;
  const drafts = new Map();
  const draftKey = element => `${element.closest("form")?.getAttribute("action")}|${element.name}`;
  const rememberDraft = event => {
    const element = event.target;
    if (workspace.contains(element) && element.matches("input[name]:not([type=hidden]),select[name],textarea[name]")) {
      drafts.set(draftKey(element), {value:element.value,checked:element.checked});
    }
  };
  workspace.addEventListener("input", rememberDraft);
  workspace.addEventListener("change", rememberDraft);
  const detailKey = (details) =>
    details.dataset.testid || details.querySelector("summary")?.textContent?.trim() || "";
  const focusable = "a[href], button, input, select, textarea, summary, [tabindex]";
  const editingWorkspace = () => workspace.contains(document.activeElement) &&
    document.activeElement.matches("select, input, textarea");
  const focusKey = (element) => JSON.stringify([
    element.tagName, element.id, element.getAttribute("data-testid"),
    element.getAttribute("name"), element.getAttribute("type"),
    element.getAttribute("href"), element.closest("form")?.getAttribute("action"),
    element.closest("[id]")?.id, element.textContent.trim()
  ]);
  const showActionError = (message) => {
    let error = workspace.querySelector("[data-testid='live-action-error']");
    if (!error) {
      error = document.createElement("p");
      error.className = "callout action-error";
      error.dataset.testid = "live-action-error";
      error.setAttribute("role", "alert");
      workspace.prepend(error);
    }
    error.textContent = message;
  };
  async function refreshWorkspace(force = false) {
    if (updating) return;
    if (!force && editingWorkspace()) return;
    updating = true;
    try {
      const response = await fetch("/api/player-workspace", {cache: "no-store"});
      if (response.ok) {
        const html = await response.text();
        // Focus may move while the request is in flight. Preserve the current
        // editing session, not the element that was active before the fetch.
        if (!force && editingWorkspace()) return;
        const active = document.activeElement;
        const key = workspace.contains(active) && active.matches(focusable)
          ? focusKey(active) : null;
        const openDetails = new Set(
          Array.from(workspace.querySelectorAll("details[open]"), detailKey)
        );
        const playToolsOpen = Array.from(workspace.querySelectorAll("details"))
          .find(details => details.id === "other-play-tools")?.open;
        workspace.innerHTML = html;
        for (const element of workspace.querySelectorAll("input[name]:not([type=hidden]),select[name],textarea[name]")) {
          const draft = drafts.get(draftKey(element));
          if (draft) { element.value = draft.value; if (["checkbox","radio"].includes(element.type)) element.checked = draft.checked; }
        }
        for (const details of workspace.querySelectorAll("details")) {
          if (details.id === "other-play-tools" && playToolsOpen !== undefined) details.open = playToolsOpen;
          else if (openDetails.has(detailKey(details))) details.open = true;
        }
        if (key !== null) {
          const matches = Array.from(workspace.querySelectorAll(focusable)).filter(
            (element) => focusKey(element) === key && !element.disabled &&
              element.getClientRects().length > 0
          );
          // Never redirect focus to a different action or an ambiguous match.
          if (matches.length === 1) matches[0].focus({preventScroll: true});
        }
      }
    } finally {
      updating = false;
    }
  }
  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !workspace.contains(form)) return;
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        body: new URLSearchParams(new FormData(form)),
        redirect: "follow"
      });
      if (!response.ok) {
        const documentText = await response.text();
        const parsed = new DOMParser().parseFromString(documentText, "text/html");
        const message = parsed.querySelector("main p, body p")?.textContent?.trim();
        showActionError(message || `Start failed (${response.status}).`);
        return;
      }
      for (const element of form.querySelectorAll("input[name],select[name],textarea[name]")) drafts.delete(draftKey(element));
      await refreshWorkspace(true);
      history.replaceState(null, "", form.action.includes("objective") ? "#objective" : "#live");
    } catch (_error) {
      showActionError("Start failed. Check that the local game service is running.");
    } finally {
      if (button) button.disabled = false;
    }
  });
  window.setInterval(() => refreshWorkspace(false), 750);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshWorkspace(true);
  });
})();
'''
