import { fetchBoat } from "./api.js";

const OUTCOME_TEXT = { sunk: "gezonken", damaged: "beschadigd", captured: "buitgemaakt" };
const SOURCE_URL = "https://uboat.net/boats/";

function dutchNumber(value) {
  return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

export function boatFacts(boat) {
  return [
    ["Type", boat.type],
    ["Werf", boat.builder],
    ["Kiel gelegd", boat.laid_down],
    ["Te water", boat.launched],
    ["In dienst", boat.commissioned],
    ["Lot", boat.fate],
  ].filter(([, value]) => value);
}

export function boatSummary(boat, ships) {
  const count = boat.patrols.length;
  const parts = [count === 0 ? "Geen patrouilles" : `${count} ${count === 1 ? "patrouille" : "patrouilles"}`];
  const tons = boat.patrols.reduce((sum, patrol) => sum + (patrol.tonnage ?? 0), 0);
  if (tons > 0) {
    parts.push(`${dutchNumber(tons)} ton`);
  }
  if (ships.length > 0) {
    parts.push(`${ships.length} ${ships.length === 1 ? "getroffen schip" : "getroffen schepen"}`);
  }
  return parts.join(" · ");
}

function place(port, date) {
  return [port, date].filter(Boolean).join(" ");
}

export function patrolLines(patrol) {
  const lines = [];
  if (patrol.commander) {
    lines.push(patrol.commander);
  }
  const from = place(patrol.departure_port, patrol.departure_date);
  const to = place(patrol.arrival_port, patrol.arrival_date);
  if (from || to) {
    lines.push([from, to].filter(Boolean).join(" → "));
  }
  const figures = [];
  if (patrol.days_at_sea) {
    figures.push(`${patrol.days_at_sea} ${patrol.days_at_sea === 1 ? "dag" : "dagen"} op zee`);
  }
  if (patrol.tonnage) {
    figures.push(`${dutchNumber(patrol.tonnage)} ton`);
  }
  if (figures.length > 0) {
    lines.push(figures.join(" · "));
  }
  return { title: `Patrouille ${patrol.patrol_number}`, lines };
}

export function boatShips(ships, slug) {
  return ships.filter((ship) => ship.boat_slug === slug).sort((a, b) => a.date.localeCompare(b.date));
}

export function shipLine(ship) {
  return `${ship.date} · ${ship.name} · ${dutchNumber(ship.tons)} ton · ${OUTCOME_TEXT[ship.outcome]}`;
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) {
    node.textContent = text;
  }
  if (className !== undefined) {
    node.className = className;
  }
  return node;
}

// Text from the source only ever goes in through textContent. `getShips` returns all
// loaded ship hits; `onShowPatrol`, when given, adds a button that shows a patrol on the map.
export function createBoatPanel({ rootEl, getShips, onShowPatrol = null }) {
  const closeEl = element("button", "×", "boat-panel-close");
  closeEl.type = "button";
  closeEl.setAttribute("aria-label", "Paneel sluiten");
  const bodyEl = element("div");
  rootEl.append(closeEl, bodyEl);

  let requested = null;

  function close() {
    requested = null;
    rootEl.hidden = true;
  }

  function render(boat) {
    const ships = boatShips(getShips(), boat.slug);
    const nodes = [element("h2", boat.number), element("p", boatSummary(boat, ships), "boat-panel-summary")];

    const facts = element("dl");
    for (const [label, value] of boatFacts(boat)) {
      facts.append(element("dt", label), element("dd", value));
    }
    nodes.push(facts);

    nodes.push(element("h3", "Patrouilles"));
    if (boat.patrols.length === 0) {
      nodes.push(element("p", "Geen patrouilles bekend."));
    }
    for (const patrol of boat.patrols) {
      const { title, lines } = patrolLines(patrol);
      const section = element("section", undefined, "boat-panel-patrol");
      section.append(element("h4", title));
      for (const line of lines) {
        section.append(element("p", line));
      }
      if (patrol.description) {
        const details = element("details");
        details.append(element("summary", "Beschrijving"), element("p", patrol.description));
        section.append(details);
      }
      if (onShowPatrol !== null && patrol.departure_date) {
        const show = element("button", "Toon op kaart");
        show.type = "button";
        show.addEventListener("click", () => onShowPatrol(patrol));
        section.append(show);
      }
      nodes.push(section);
    }

    if (ships.length > 0) {
      nodes.push(element("h3", "Getroffen schepen"));
      const list = element("ul");
      for (const ship of ships) {
        list.append(element("li", shipLine(ship)));
      }
      nodes.push(list);
    }

    const source = element("a", "Bron: uboat.net");
    source.href = `${SOURCE_URL}${encodeURIComponent(boat.slug)}.htm`;
    source.target = "_blank";
    source.rel = "noopener";
    nodes.push(source);

    bodyEl.replaceChildren(...nodes);
    rootEl.scrollTop = 0;
  }

  async function open(slug) {
    requested = slug;
    rootEl.hidden = false;
    bodyEl.replaceChildren(element("p", "Laden…"));
    try {
      const boat = await fetchBoat(slug);
      if (requested === slug) {
        render(boat);
      }
    } catch (error) {
      console.error(error);
      if (requested === slug) {
        bodyEl.replaceChildren(element("p", "Gegevens konden niet worden geladen."));
      }
    }
  }

  closeEl.addEventListener("click", close);
  rootEl.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      close();
    }
  });
  close();

  return { open, close };
}
