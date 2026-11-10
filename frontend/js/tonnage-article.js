// The Artikel of a ship beside the charts of the tonnage page: the same pane and contents as the
// vak Artikel on the map pages. onToggle hears the panel appear or go, as the charts get another width.
import { createArticlePane } from "./battle-article.js";
import { createBoatPanel } from "./boat-panel.js";
import { fetchBoat, fetchShip } from "./api.js";

export function createShipArticle({ rootEl, getShips, onToggle, load = { boat: fetchBoat, ship: fetchShip } }) {
  let current = null;
  rootEl.hidden = true;

  function setShown(shown) {
    if (rootEl.hidden === !shown) return;
    rootEl.hidden = !shown;
    onToggle?.();
  }

  function close() {
    current = null;
    setShown(false);
  }

  const pane = createArticlePane({ rootEl, onClose: close });
  const panel = createBoatPanel({
    article: pane,
    getShips,
    load,
    onOpenBoat: (slug) => panel.open(slug, getShips().find((ship) => ship.boat_slug === slug)?.boat_number ?? slug),
    onOpenShip: (ship) => open(ship),
  });

  function open(ship) {
    current = ship;
    setShown(true);
    return panel.openShip(ship);
  }

  return { open, close, current: () => current };
}
