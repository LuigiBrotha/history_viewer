// A button in the row of map controls that switches something on the map on and off.
// `onChange` hears the state at once and after every change, so the page draws it and keeps
// it in the URL in one place.
function createMapToggle({ map, doc = document, id, label, title, visible = true, onChange }) {
  let shown = visible;
  const button = doc.createElement("button");
  button.id = id;
  button.textContent = label;
  button.setAttribute("type", "button");
  button.setAttribute("title", title);

  function apply() {
    button.setAttribute("aria-pressed", String(shown));
    onChange(shown);
  }

  function set(next) {
    if (next === shown) return;
    shown = next;
    apply();
  }

  button.addEventListener("click", () => set(!shown));
  const control = L.control({ position: "topleft" });
  control.onAdd = () => {
    L.DomEvent.disableClickPropagation(button);
    return button;
  };
  control.addTo(map);
  apply();

  return { show: () => set(true) };
}

export function createRouteToggle(options) {
  return createMapToggle({ ...options, id: "route-toggle", label: "Routes", title: "Routes van de U-boten aan of uit" });
}

export function createBoatToggle(options) {
  return createMapToggle({ ...options, id: "boat-toggle", label: "U-boten", title: "U-boten aan of uit; de gezonken schepen blijven staan" });
}

// The names beside the Veldslag squares; every page with Veldslagen has this one the same way.
export function createNamesToggle({ map, doc, battles, urlSync, shown }) {
  return createMapToggle({
    map,
    doc,
    id: "names-toggle",
    label: "Namen",
    title: "Namen van de veldslagen op de kaart aan of uit",
    visible: shown,
    onChange: (visible) => {
      battles.setNamesVisible(visible);
      urlSync.update({ namesOff: visible ? null : true });
    },
  });
}

// "Overige": the squares of the battles other than the selected one; off, only the selected
// battle stands on the map (all of them while none is selected).
export function createOthersToggle({ map, doc, battles, urlSync, shown }) {
  return createMapToggle({
    map,
    doc,
    id: "others-toggle",
    label: "Overige",
    title: "De andere veldslagen dan de geselecteerde aan of uit",
    visible: shown,
    onChange: (visible) => {
      battles.setOthersVisible(visible);
      urlSync.update({ othersOff: visible ? null : true });
    },
  });
}

// The ships that were hit; the same on every page that draws them.
export function createShipsToggle({ map, doc, shipLayer, urlSync, shown }) {
  return createMapToggle({
    map,
    doc,
    id: "ships-toggle",
    label: "Schepen",
    title: "Gezonken, beschadigde en buitgemaakte schepen op de kaart aan of uit",
    visible: shown,
    onChange: (visible) => {
      shipLayer.setVisible(visible);
      urlSync.update({ shipsOff: visible ? null : true });
    },
  });
}
