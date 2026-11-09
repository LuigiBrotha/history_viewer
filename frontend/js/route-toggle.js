// The button in the row of map controls that switches the routes of the U-boats on and off.
// `onChange` hears the state at once and after every change, so the page draws it and keeps
// it in the URL in one place.
export function createRouteToggle({ map, doc = document, visible = true, onChange }) {
  let shown = visible;
  const button = doc.createElement("button");
  button.id = "route-toggle";
  button.textContent = "Routes";
  button.setAttribute("type", "button");
  button.setAttribute("title", "Routes van de U-boten aan of uit");

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
