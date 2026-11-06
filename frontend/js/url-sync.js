import { carriedView, writeView } from "./url-state.js";

// Keeps the address bar in step with the view of a map page. Always replaceState, so the
// back button leaves the page. Writes are throttled: a burst of updates (playback, panning)
// ends in one write of the latest view. Links to other map pages carry the view along.
export function createUrlSync({ kind, win = window, doc = document, delayMs = 250 }) {
  let view = {};
  let timer = null;
  // A link's own path, remembered the first time because its href is rewritten afterwards.
  const linkPaths = new Map();

  function linkPath(link) {
    if (!linkPaths.has(link)) linkPaths.set(link, link.getAttribute("href").split("?")[0]);
    return linkPaths.get(link);
  }

  function write() {
    timer = null;
    win.history.replaceState(null, "", win.location.pathname + writeView(view, kind));
    for (const link of doc.querySelectorAll("a[data-carry]")) {
      link.setAttribute("href", linkPath(link) + writeView(carriedView(view), link.getAttribute("data-carry")));
    }
  }

  function update(partial) {
    const next = { ...view };
    for (const [key, value] of Object.entries(partial)) {
      if (value === null || value === undefined) delete next[key];
      else next[key] = value;
    }
    view = next;
    if (timer === null) timer = setTimeout(write, delayMs);
  }

  return { update };
}
