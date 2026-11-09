import { shipTotalsLine, shipsWithoutPosition } from "./ship-model.js";

export function boatsHeading(count) {
  return `Actieve boten (${count})`;
}

export function updateDateLabel(labelEl, date) {
  labelEl.textContent = `Actief op ${date.toISOString().slice(0, 10)}`;
}

// A followed boat also lists its ships that cannot be placed on the map.
export function renderShipSummary({ totalsEl, unknownEl }, ships, followed) {
  totalsEl.textContent = shipTotalsLine(ships);
  unknownEl.innerHTML = "";
  if (!followed) return;
  for (const ship of shipsWithoutPosition(ships)) {
    const item = document.createElement("li");
    item.textContent = `${ship.name} — positie onbekend`;
    unknownEl.appendChild(item);
  }
}

// Built from text nodes only: dates and coordinates are never parsed as HTML.
// onRestore is null when editing is not allowed; the list is still shown.
// isBusy(externalId, sequence) keeps a point with a running request disabled across rebuilds.
export function renderExcludedPoints({ listEl, patrol, onRestore, isBusy = () => false }) {
  listEl.replaceChildren();
  const points = patrol?.excluded_points ?? [];
  listEl.hidden = points.length === 0;
  if (points.length === 0) {
    return;
  }

  const heading = document.createElement("h3");
  heading.textContent = "Uitgesloten punten";
  listEl.appendChild(heading);

  const list = document.createElement("ul");
  for (const point of points) {
    const item = document.createElement("li");
    const text = document.createElement("span");
    text.textContent = `${point.date ?? "geen datum"} (${point.lat.toFixed(3)}, ${point.lng.toFixed(3)})`;
    item.appendChild(text);
    if (onRestore !== null) {
      const button = document.createElement("button");
      const busy = isBusy(patrol.external_id, point.sequence);
      button.textContent = busy ? "Bezig…" : "Herstellen";
      button.disabled = busy;
      button.addEventListener("click", () => onRestore(point, button));
      item.appendChild(button);
    }
    list.appendChild(item);
  }
  listEl.appendChild(list);
}
