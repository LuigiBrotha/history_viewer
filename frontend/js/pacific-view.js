// Longitudes past 180 are the next copy of the world, so Asia and America sit side by side.
export const PACIFIC_BOUNDS = [[-45, 100], [62, 260]];

const showing = new WeakSet();

export function isPacificShown(map) {
  return showing.has(map);
}

// Goes to the Pacific and, the next time, back to where the map was. Returns whether the
// map now shows the Pacific.
export function createPacificToggle(map) {
  let previous = null;
  return () => {
    if (previous === null) {
      previous = { center: map.getCenter(), zoom: map.getZoom() };
      showing.add(map);
      map.fitBounds(PACIFIC_BOUNDS);
      return true;
    }
    map.setView(previous.center, previous.zoom);
    previous = null;
    showing.delete(map);
    return false;
  };
}

export function addPacificButton(map) {
  const toggle = createPacificToggle(map);
  const control = L.control({ position: "topleft" });
  control.onAdd = () => {
    const button = L.DomUtil.create("button", "pacific-toggle");
    button.type = "button";
    button.textContent = "Stille Oceaan";
    button.setAttribute("aria-pressed", "false");
    L.DomEvent.disableClickPropagation(button);
    button.addEventListener("click", () => {
      const shown = toggle();
      button.textContent = shown ? "Terug" : "Stille Oceaan";
      button.setAttribute("aria-pressed", String(shown));
    });
    return button;
  };
  control.addTo(map);
}
