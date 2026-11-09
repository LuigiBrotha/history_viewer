function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

// One list of Onderwerpen in the column. Rows are built once for a set of items; a search, date
// or period only changes the rows whose state changed. Items are { key, title, meta, search }
// and only ever reach the page as text. The chosen row stays listed whatever the search says.
export function createSubjectList({ rootEl, emptyText, onPick, onCount }) {
  let rows = new Map();
  let query = "";
  let selected = null;
  let marks = { isActive: null, dim: false };

  const list = element("ul", "subject-list");
  const empty = element("p", "subject-empty", emptyText);
  empty.hidden = true;
  const scroll = element("div", "subject-scroll");
  scroll.append(empty, list);
  rootEl.replaceChildren(scroll);

  list.addEventListener("click", (event) => {
    const row = event.target.closest(".subject-row");
    if (row) onPick(rows.get(row.getAttribute("data-key")).item);
  });

  function buildRow(item) {
    const el = element("li", "subject-row");
    el.setAttribute("data-key", item.key);
    const name = element("button", "subject-row-title", item.title);
    name.setAttribute("type", "button");
    el.append(name, element("div", "subject-row-meta", item.meta));
    return { item, el, active: false, dimmed: false };
  }

  function applySearch() {
    let count = 0;
    for (const [key, row] of rows) {
      const matches = query === "" || row.item.search.includes(query);
      if (matches) count += 1;
      row.el.hidden = !matches && key !== selected;
    }
    empty.hidden = count > 0 || rows.size === 0;
    onCount(count);
  }

  function applyMarks() {
    for (const row of rows.values()) {
      const active = marks.isActive !== null && marks.isActive(row.item);
      const dimmed = marks.isActive !== null && marks.dim && !active;
      if (active !== row.active) {
        row.active = active;
        row.el.classList.toggle("active", active);
      }
      if (dimmed !== row.dimmed) {
        row.dimmed = dimmed;
        row.el.classList.toggle("dimmed", dimmed);
      }
    }
  }

  function select(key) {
    rows.get(selected)?.el.classList.toggle("selected", false);
    selected = key;
    rows.get(selected)?.el.classList.toggle("selected", true);
  }

  return {
    setItems(items) {
      rows = new Map(items.map((item) => [item.key, buildRow(item)]));
      list.replaceChildren(...[...rows.values()].map((row) => row.el));
      rows.get(selected)?.el.classList.toggle("selected", true);
      applySearch();
      applyMarks();
    },
    setSearch(text) {
      query = text.trim().toLowerCase();
      applySearch();
    },
    // isActive(item) marks the rows for the date or period, null marks none; with dim the
    // others are dimmed.
    setMarks(isActive, dim = false) {
      marks = { isActive, dim };
      applyMarks();
    },
    reveal(key) {
      select(key);
      applySearch();
      rows.get(key)?.el.scrollIntoView?.({ block: "center" });
    },
    clear() {
      select(null);
      applySearch();
    },
  };
}
