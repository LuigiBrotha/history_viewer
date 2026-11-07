// The search field at the top left of the map: app data straight away, places after a pause.
const MIN_PLACE_CHARS = 3;
const PLACE_ZOOM = 10;
const PLACES = "Plaatsen";

export function createMapSearch({ map, sources, onPick, fetchPlaces, doc = document, win = window, delayMs = 400, markerMs = 30000 }) {
  let appGroups = [];
  let places = { state: "idle", items: [] };
  let rows = [];
  let active = -1;
  let open = false;
  let timer = null;
  let controller = null;
  let token = 0;
  let marker = null;
  let markerTimer = null;

  const el = (tag, className, content) => {
    const node = doc.createElement(tag);
    if (className) node.className = className;
    if (content != null) node.textContent = content;
    return node;
  };

  const input = el("input", "map-search-input");
  input.setAttribute("type", "search");
  input.setAttribute("placeholder", "Zoek plaats, boot, schip of veldslag (Ctrl+K)");
  input.setAttribute("autocomplete", "off");
  input.setAttribute("aria-label", "Zoeken op de kaart");
  const list = el("div", "map-search-list");
  list.hidden = true;
  const box = el("div", "map-search");
  box.append(input, list);

  const trimmed = () => input.value.trim();

  function cancelPending() {
    token += 1;
    if (timer !== null) win.clearTimeout(timer);
    timer = null;
    controller?.abort();
    controller = null;
  }

  // Stops a place fetch that is still waiting, so a late answer cannot come back on refocus.
  function dropPlaces() {
    cancelPending();
    if (places.state === "loading") places = { state: "idle", items: [] };
  }

  function render() {
    list.hidden = !open;
    if (!open) {
      list.replaceChildren();
      return;
    }
    rows = [];
    const nodes = [];
    const addGroup = (group, entries, note) => {
      if (!entries.length && !note) return;
      nodes.push(el("div", "map-search-group", group));
      for (const entry of entries) {
        const row = el("div", "map-search-row");
        row.append(el("span", "map-search-label", entry.label));
        if (entry.sub) row.append(el("span", "map-search-sub", entry.sub));
        const index = rows.length;
        row.addEventListener("click", () => choose(index));
        rows.push({ group, entry, node: row });
        nodes.push(row);
      }
      if (note) nodes.push(el("div", "map-search-note", note));
    };
    for (const { group, results } of appGroups) addGroup(group, results);
    const placeEntries = places.items.map((place) => ({ label: place.name, sub: place.sub, item: place }));
    const note = places.state === "loading" ? "Plaatsen zoeken…" : places.state === "error" ? "Plaatsen zoeken mislukt." : null;
    addGroup(PLACES, placeEntries, note);
    if (!nodes.length && places.state !== "loading") nodes.push(el("div", "map-search-note", "Niets gevonden."));
    rows.forEach((row, i) => row.node.classList.toggle("is-active", i === active));
    list.replaceChildren(...nodes);
    rows[active]?.node.scrollIntoView?.({ block: "nearest" });
  }

  function choose(index) {
    const row = rows[index];
    if (!row) return;
    open = false;
    active = -1;
    dropPlaces();
    render();
    onPick({ group: row.group, item: row.entry.item });
  }

  async function loadPlaces() {
    timer = null;
    controller?.abort();
    const mine = ++token;
    controller = new AbortController();
    places = { state: "loading", items: [] };
    render();
    try {
      const items = await fetchPlaces(trimmed(), { signal: controller.signal });
      if (mine !== token) return;
      places = { state: "done", items: items.slice(0, 5) };
    } catch {
      if (mine !== token) return;
      places = { state: "error", items: [] };
    }
    active = -1;
    render();
  }

  input.addEventListener("input", () => {
    cancelPending();
    const q = trimmed();
    places = { state: "idle", items: [] };
    active = -1;
    if (!q) {
      appGroups = [];
      open = false;
      render();
      return;
    }
    appGroups = sources.map(({ group, search }) => ({ group, results: search(q) })).filter((g) => g.results.length);
    open = true;
    if (q.length >= MIN_PLACE_CHARS) {
      places = { state: "loading", items: [] };
      timer = win.setTimeout(loadPlaces, delayMs);
    }
    render();
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      open = false;
      dropPlaces();
      removeMarker();
      render();
      input.blur();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!open && rows.length) open = true;
      if (!rows.length) return;
      event.preventDefault?.();
      const step = event.key === "ArrowDown" ? 1 : -1;
      active = active === -1 ? (step === 1 ? 0 : rows.length - 1) : (active + step + rows.length) % rows.length;
      render();
    } else if (event.key === "Enter") {
      if (active >= 0) choose(active);
      else if (timer !== null) {
        win.clearTimeout(timer);
        loadPlaces();
      }
    }
  });

  input.addEventListener("focus", () => {
    if (trimmed() && !open) {
      open = true;
      render();
    }
  });

  doc.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && String(event.key).toLowerCase() === "k") {
      event.preventDefault();
      input.focus();
      input.select?.();
    }
  });

  const control = L.control({ position: "topleft" });
  control.onAdd = () => {
    L.DomEvent.disableClickPropagation(box);
    L.DomEvent.disableScrollPropagation(box);
    return box;
  };
  control.addTo(map);

  function removeMarker() {
    if (markerTimer !== null) win.clearTimeout(markerTimer);
    markerTimer = null;
    marker?.remove();
    marker = null;
  }

  return {
    showPlace(place) {
      removeMarker();
      if (place.bbox) {
        const [south, north, west, east] = place.bbox;
        map.fitBounds([[south, west], [north, east]], { maxZoom: PLACE_ZOOM });
      } else {
        map.setView([place.lat, place.lng], PLACE_ZOOM);
      }
      marker = L.marker([place.lat, place.lng]).bindTooltip(place.name, { permanent: true }).addTo(map);
      markerTimer = win.setTimeout(removeMarker, markerMs);
    },
    clear: removeMarker,
  };
}
