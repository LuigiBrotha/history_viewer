import { fetchBoat, fetchShip } from "./api.js";

export const OUTCOME_TEXT = { sunk: "gezonken", damaged: "beschadigd", captured: "buitgemaakt" };
const SOURCE_URL = "https://uboat.net/boats/";
const NOT_FETCHED = "Meer gegevens zijn nog niet opgehaald.";
const FETCH_FAILED = "Meer gegevens konden niet worden geladen.";
const SHIP_SOURCE_URL = "https://uboat.net/allies/merchants/ship/";

export function dutchNumber(value) {
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

function coordinate(value, positive, negative) {
  return `${Math.abs(value).toFixed(3).replace(".", ",")}° ${value < 0 ? negative : positive}`;
}

// What is known of a hit; `details` is the ship's page, or null while it is missing.
export function hitSummary(ship) {
  return `${dutchNumber(ship.tons)} ton · ${OUTCOME_TEXT[ship.outcome]} op ${ship.date}`;
}

export function shipFacts(ship, details) {
  const d = details ?? {};
  const position =
    ship.lat == null || ship.lng == null
      ? "onbekend"
      : `${coordinate(ship.lat, "N", "S")}, ${coordinate(ship.lng, "E", "W")}`;
  return [
    ["Tonnage", `${dutchNumber(ship.tons)} ton`],
    ["Datum", ship.date],
    ["Uitkomst", OUTCOME_TEXT[ship.outcome]],
    ["Positie", position],
    ["Type", d.ship_type],
    ["Gebouwd", d.completed],
    ["Eigenaar", d.owner],
    ["Thuishaven", d.homeport],
    ["Nationaliteit", d.nationality ?? ship.nationality],
    ["Lot", d.fate],
    ["Bemanning", d.complement],
    ["Konvooi", d.convoy ?? ship.convoy],
    ["Route", d.route],
    ["Lading", d.cargo],
    ["Geschiedenis", d.history],
  ].filter(([, value]) => value);
}

export function hitBy(ship) {
  return `Getroffen door ${ship.boat_number}`;
}

export function hitLine(ship) {
  return `${ship.date} · ${ship.boat_number} · ${OUTCOME_TEXT[ship.outcome]}`;
}

function sameHit(a, b) {
  return a.boat_slug === b.boat_slug && a.date === b.date && a.ship_external_id === b.ship_external_id;
}

// The other times this ship was hit, oldest first.
export function otherHits(ship, hits) {
  return hits.filter((hit) => !sameHit(hit, ship)).sort((a, b) => a.date.localeCompare(b.date));
}

export function sourceUrl(shipExternalId) {
  return `${SHIP_SOURCE_URL}${encodeURIComponent(shipExternalId)}.html`;
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

// Inner controls, such as the foldable details, keep their own behaviour.
function makeClickable(section, action) {
  section.classList.add("clickable");
  section.tabIndex = 0;
  section.setAttribute("role", "button");
  section.setAttribute("aria-label", "Toon deze route op de kaart");
  section.addEventListener("click", (event) => {
    if (!event.target.closest("details")) {
      action();
    }
  });
  section.addEventListener("keydown", (event) => {
    if (event.target === section && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      action();
    }
  });
}

// What the vak Artikel shows of a boat or ship. Text from the source only ever goes in through
// textContent. `getShips` returns all loaded ship hits; `onShowPatrol`, when given, makes each
// patrol clickable to show its route on the map. `article.showSubject` puts it in the vak.
export function createBoatPanel({ article, getShips, onShowPatrol = null, onOpenBoat = null, onOpenShip = null, load = { boat: fetchBoat, ship: fetchShip } }) {
  function articleRoot(nodes) {
    const root = element("div", undefined, "subject-article");
    root.append(...nodes);
    return [root];
  }

  function boatNodes(boat) {
    const ships = boatShips(getShips(), boat.slug);
    const nodes = [element("p", boatSummary(boat, ships), "boat-panel-summary")];

    const facts = element("dl");
    for (const [label, value] of boatFacts(boat)) {
      facts.append(element("dt", label), element("dd", value));
    }
    nodes.push(facts);

    nodes.push(element("h3", "Patrouilles"));
    if (boat.patrols.length === 0) {
      nodes.push(element("p", "Geen patrouilles bekend."));
    }
    const sections = [];
    for (const patrol of boat.patrols) {
      const { title, lines } = patrolLines(patrol);
      const section = element("section", undefined, "boat-panel-patrol");
      section.append(element("h4", title));
      if (patrol.description) {
        section.append(element("p", patrol.description));
      }
      if (lines.length > 0) {
        const details = element("details");
        details.append(element("summary", "Gegevens"), ...lines.map((line) => element("p", line)));
        section.append(details);
      }
      if (onShowPatrol !== null && patrol.departure_date) {
        makeClickable(section, () => {
          for (const other of sections) {
            other.classList.remove("selected");
          }
          section.classList.add("selected");
          onShowPatrol(patrol, boat);
        });
      }
      sections.push(section);
      nodes.push(section);
    }

    if (ships.length > 0) {
      nodes.push(element("h3", "Getroffen schepen"));
      const list = element("ul");
      for (const ship of ships) {
        const item = element("li");
        const button = element("button", shipLine(ship), "boat-panel-ship");
        button.type = "button";
        button.addEventListener("click", () => onOpenShip?.(ship));
        item.append(button);
        list.append(item);
      }
      nodes.push(list);
    }

    const source = element("a", "Bron: uboat.net");
    source.href = `${SOURCE_URL}${encodeURIComponent(boat.slug)}.htm`;
    source.target = "_blank";
    source.rel = "noopener";
    nodes.push(source);
    return articleRoot(nodes);
  }

  // `more` is what the ship's own page adds: its details and the other hits, or a message
  // when they are missing or could not be loaded.
  function shipNodes(ship, more) {
    const nodes = [element("p", hitSummary(ship), "boat-panel-summary")];

    if (more.details?.notes) {
      nodes.push(element("h3", "Wat er gebeurde"), element("p", more.details.notes));
    }
    if (more.message) {
      nodes.push(element("p", more.message));
    }

    const by = element("button", hitBy(ship), "boat-panel-ship");
    by.type = "button";
    by.addEventListener("click", () => onOpenBoat?.(ship.boat_slug));
    nodes.push(by);

    const facts = element("dl");
    for (const [label, value] of shipFacts(ship, more.details ?? null)) {
      facts.append(element("dt", label), element("dd", value));
    }
    const factsBox = element("details");
    factsBox.append(element("summary", "Gegevens"), facts);
    nodes.push(factsBox);

    const others = otherHits(ship, more.hits ?? []);
    if (others.length > 0) {
      nodes.push(element("h3", "Ook getroffen"));
      const list = element("ul");
      for (const hit of others) {
        list.append(element("li", hitLine(hit)));
      }
      nodes.push(list);
    }

    const source = element("a", "Bron: uboat.net");
    source.href = sourceUrl(ship.ship_external_id);
    source.target = "_blank";
    source.rel = "noopener";
    nodes.push(source);
    return articleRoot(nodes);
  }

  async function loadShip(ship, version) {
    try {
      const { details, hits, translated } = await load.ship(ship.ship_external_id, version);
      return { details, hits, translated: translated === true, message: details ? null : NOT_FETCHED };
    } catch (error) {
      console.error(error);
      return { details: null, hits: [], translated: false, message: FETCH_FAILED };
    }
  }

  return {
    // `number` is the title while the boat is still loading.
    open(slug, number) {
      return article.showSubject({
        title: number,
        load: async (version) => {
          const boat = await load.boat(slug, version);
          return { title: boat.number, nodes: boatNodes(boat), translated: boat.translated === true };
        },
      });
    },
    openShip(ship) {
      return article.showSubject({
        title: ship.name,
        load: async (version) => {
          const more = await loadShip(ship, version);
          return { title: ship.name, nodes: shipNodes(ship, more), translated: more.translated };
        },
      });
    },
  };
}
