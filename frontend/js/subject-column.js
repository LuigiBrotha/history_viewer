import { loadState, saveState } from "./battle-split.js";

const STORAGE_KEY = "uboats.subjects";
const SECTIONS = [["battles", "Veldslagen"], ["boats", "U-boten"], ["ships", "Schepen"]];
// Without a choice of the user only the Veldslagen are open.
const OPEN_BY_DEFAULT = { battles: true, boats: false, ships: false };

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

// The column Onderwerpen: its head with the one search field, and a foldable section for each
// kind of Onderwerp. A section's body and the text of its head belong to whoever fills it.
export function createSubjectColumn({ rootEl, storage, onMinimize }) {
  const state = { ...OPEN_BY_DEFAULT, ...loadState(storage, STORAGE_KEY) };
  const listeners = [];

  const title = element("h2", "subject-column-title", "Onderwerpen");
  const search = element("input", "battle-search");
  search.setAttribute("type", "search");
  search.setAttribute("placeholder", "Zoek in de onderwerpen");
  search.setAttribute("aria-label", "Zoek een onderwerp");
  search.setAttribute("autocomplete", "off");
  const minimize = element("button", "battle-pane-minimize", "−");
  minimize.setAttribute("type", "button");
  minimize.setAttribute("aria-label", "Kolom minimaliseren");
  minimize.setAttribute("title", "Kolom minimaliseren; de knop Onderwerpen haalt hem terug");
  minimize.addEventListener("click", () => onMinimize?.());
  const head = element("div", "battle-pane-head");
  head.append(title, search, minimize);

  const notify = () => listeners.forEach((listener) => listener(search.value));
  search.addEventListener("input", notify);

  const sections = {};
  const sectionEls = SECTIONS.map(([id, label]) => {
    const section = element("section", "subject-section");
    const toggle = element("button", "subject-toggle");
    toggle.setAttribute("type", "button");
    const titleEl = element("span", id === "battles" ? "battle-pane-title" : "subject-toggle-text", label);
    toggle.append(titleEl, element("span", "subject-toggle-icon"));
    const bodyEl = element("div", "subject-body");
    section.append(toggle, bodyEl);

    function show() {
      section.classList.toggle("open", state[id]);
      toggle.setAttribute("aria-expanded", String(state[id]));
      bodyEl.hidden = !state[id];
    }
    toggle.addEventListener("click", () => {
      state[id] = !state[id];
      show();
      saveState(storage, state, STORAGE_KEY);
    });
    show();
    sections[id] = { bodyEl, titleEl, label };
    return section;
  });

  rootEl.replaceChildren(head, ...sectionEls);

  return {
    search,
    sections,
    // Says the number of rows found in a section's head.
    setCount: (id, count) => {
      sections[id].titleEl.textContent = `${sections[id].label} (${count})`;
    },
    onSearch: (listener) => listeners.push(listener),
    // For when the search field was changed from code.
    searchChanged: notify,
  };
}
