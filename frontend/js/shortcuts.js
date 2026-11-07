// Keyboard shortcuts of the map pages. One listener in the capture phase, so the arrow keys
// reach it before the map would pan. Keys typed into a field, or pressed on a slider or a
// divider (which use the arrows themselves), are left alone.

export const SHORTCUTS = [
  { keys: ["↑", "↓"], text: "Vorige / volgende Veldslag in de lijst" },
  { keys: ["←", "→"], text: "Dag terug / vooruit (tijdlijn)" },
  { keys: ["P"], text: "Positie aanpassen van de geselecteerde Veldslag" },
  { keys: ["Enter"], text: "Bewaar de positie" },
  { keys: ["Shift+Enter"], text: "Bewaar en ga naar de volgende Veldslag zonder positie" },
  { keys: ["Esc"], text: "Annuleer het aanpassen, of sluit de zoeklijst" },
  { keys: ["W"], text: "Eigen positie wissen (na bevestiging)" },
  { keys: ["A"], text: "Artikel open / dicht" },
  { keys: ["V"], text: "Veldslagenlijst open / dicht" },
  { keys: ["/", "Ctrl+K"], text: "Zoeken op de kaart" },
  { keys: ["?"], text: "Dit overzicht" },
];

const TYPING = new Set(["INPUT", "TEXTAREA", "SELECT"]);
const ACTIVATING = new Set(["BUTTON", "A", "SUMMARY"]);

function ignored(event) {
  if (event.ctrlKey || event.altKey || event.metaKey) return true;
  const target = event.target;
  if (!target) return false;
  if (TYPING.has(target.tagName) || target.isContentEditable) return true;
  return Boolean(target.closest?.('[role="slider"], [role="separator"]'));
}

function actionFor(event) {
  switch (event.key) {
    case "ArrowDown":
      return "next";
    case "ArrowUp":
      return "previous";
    case "Enter":
      if (ACTIVATING.has(event.target?.tagName)) return null;
      return event.shiftKey ? "saveAndNext" : "save";
    case "/":
      return "focusSearch";
    case "?":
      return "toggleHelp";
    default:
      return { p: "editPosition", w: "clearPosition", a: "toggleArticle", v: "togglePane" }[String(event.key).toLowerCase()] ?? null;
  }
}

export function installShortcuts({ doc = document, actions }) {
  doc.addEventListener(
    "keydown",
    (event) => {
      if (event.defaultPrevented || ignored(event)) return;
      const action = actionFor(event);
      if (action === null) return;
      event.preventDefault();
      event.stopPropagation();
      actions[action]();
    },
    { capture: true },
  );
}

// The actions of a map page: the battles and the search field are looked up when a key is
// pressed, since a page may create them later.
export function pageActions({ battles, search, help }) {
  // Before a page has its battles, a key does nothing.
  const call = (name, ...args) => battles()?.[name]?.(...args);
  return {
    next: () => call("step", 1),
    previous: () => call("step", -1),
    editPosition: () => call("editSelected"),
    save: () => call("save"),
    saveAndNext: () => call("saveAndNext"),
    clearPosition: () => call("clearSelected"),
    toggleArticle: () => call("toggleArticle"),
    togglePane: () => call("togglePane"),
    focusSearch: () => search()?.focus(),
    toggleHelp: () => help.toggle(),
  };
}
