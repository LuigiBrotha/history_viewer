export function boatsHeading(count) {
  return `Actieve boten (${count})`;
}

export function renderBoatList({ listEl, activeBoats, followedSlug, onBoatSelect, boatsBySlug }) {
  listEl.innerHTML = "";

  for (const boat of activeBoats) {
    const item = document.createElement("li");
    const meta = boatsBySlug ? boatsBySlug.get(boat.boatSlug) : undefined;
    const typeLabel = meta && meta.type ? ` — ${meta.type}` : "";
    item.textContent = `${boat.boatNumber}${typeLabel} (${boat.externalId})`;
    if (boat.boatSlug === followedSlug) {
      item.classList.add("following");
    }
    item.addEventListener("click", () => onBoatSelect(boat.boatSlug));
    listEl.appendChild(item);
  }

  if (activeBoats.length === 0) {
    const empty = document.createElement("li");
    empty.textContent = "Geen boten actief op deze datum.";
    empty.style.cursor = "default";
    listEl.appendChild(empty);
  }
}

export function updateDateLabel(labelEl, date) {
  labelEl.textContent = `Actief op ${date.toISOString().slice(0, 10)}`;
}
