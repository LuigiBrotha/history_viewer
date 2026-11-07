import { SHORTCUTS } from "./shortcuts.js";

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

// The overview of the keyboard shortcuts that "?" opens and closes.
export function createShortcutHelp({ parentEl = document.body } = {}) {
  const box = element("div", "shortcut-help");
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-label", "Sneltoetsen");
  box.hidden = true;
  const head = element("div", "shortcut-help-head");
  const close = element("button", "shortcut-help-close", "✕");
  close.setAttribute("type", "button");
  close.setAttribute("aria-label", "Sluit overzicht");
  close.addEventListener("click", () => (box.hidden = true));
  head.append(element("h2", "shortcut-help-title", "Sneltoetsen"), close);
  const list = element("div", "shortcut-list");
  for (const { keys, text } of SHORTCUTS) {
    const row = element("div", "shortcut-row");
    row.append(element("span", "shortcut-keys", keys.join(" / ")), element("span", "shortcut-text", text));
    list.appendChild(row);
  }
  box.append(head, list);
  parentEl.appendChild(box);
  return {
    toggle() {
      box.hidden = !box.hidden;
    },
  };
}
