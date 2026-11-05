import { durationText, labelsToShow, squaresToDraw, visibleLngs, wrapLng } from "./battle-model.js";

const MAX_SQUARES = 1500;
const SQUARE_SIZE = 10;
const LABEL_OFFSET_PX = 12;

function text(tag, className, content) {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = content;
  return node;
}

// Titles are source data: they only ever reach the page as text content.
function tooltipContent(battle) {
  const root = document.createElement("div");
  root.className = "battle-tooltip";
  root.appendChild(text("div", "battle-tooltip-name", battle.title));
  root.appendChild(text("div", "battle-tooltip-dates", battle.date_text));
  root.appendChild(text("div", "battle-tooltip-duration", durationText(battle)));
  return root;
}

function squareIcon(selected) {
  return L.divIcon({
    className: selected ? "battle-square selected" : "battle-square",
    iconSize: [SQUARE_SIZE, SQUARE_SIZE],
    html: document.createElement("span"),
  });
}

function labelIcon(battle) {
  return L.divIcon({
    className: "battle-label",
    iconSize: [0, 0],
    iconAnchor: [-LABEL_OFFSET_PX, 0],
    html: text("span", "battle-label-text", battle.title),
  });
}

// Small amber squares, unlike the round boat and ship markers, for the battles given
// to setBattles that have a position and lie in view. They sit in the marker pane,
// above the historical map.
export function createBattleLayer(map, { onBattleClick }) {
  const group = L.layerGroup().addTo(map);
  const squares = new Map();
  let labels = [];
  let battles = [];
  let selected = null;

  function redraw() {
    const bounds = map.getBounds();
    const view = { south: bounds.getSouth(), west: bounds.getWest(), north: bounds.getNorth(), east: bounds.getEast() };
    const wanted = squaresToDraw(battles, view, MAX_SQUARES);
    const copies = (battle) => visibleLngs(battle.lng, view.west, view.east);
    const key = (battle, lng) => `${battle.title}@${lng}`;
    const wantedKeys = new Set(wanted.flatMap((battle) => copies(battle).map((lng) => key(battle, lng))));

    for (const [squareKey, marker] of squares) {
      if (!wantedKeys.has(squareKey)) {
        group.removeLayer(marker);
        squares.delete(squareKey);
      }
    }
    for (const battle of wanted) {
      for (const lng of copies(battle)) {
        if (squares.has(key(battle, lng))) continue;
        const marker = L.marker([battle.lat, lng], {
          icon: squareIcon(selected === battle.title),
          battleTitle: battle.title,
          keyboard: false,
          riseOnHover: true,
        });
        marker.bindTooltip(tooltipContent(battle), { direction: "top", offset: [0, -SQUARE_SIZE / 2] });
        marker.on("click", () => onBattleClick?.(battle));
        group.addLayer(marker);
        squares.set(key(battle, lng), marker);
      }
    }

    for (const label of labels) {
      group.removeLayer(label);
    }
    labels = labelsToShow(wanted, map.getZoom()).flatMap((battle) =>
      copies(battle).map((lng) =>
        L.marker([battle.lat, lng], { icon: labelIcon(battle), interactive: false, keyboard: false }),
      ),
    );
    for (const label of labels) {
      group.addLayer(label);
    }
  }

  map.on("moveend zoomend", redraw);

  return {
    setBattles(next) {
      battles = next;
      redraw();
    },
    // Marks the square of one battle (or none) as the one the pane points at.
    setSelected(battle) {
      selected = battle === null ? null : battle.title;
      for (const marker of squares.values()) {
        marker.setIcon(squareIcon(marker.options.battleTitle === selected));
      }
    },
    // Pans without touching the zoom: the square stays at the zoom the user chose.
    showBattle(battle) {
      if (battle.lat != null && battle.lng != null) {
        const bounds = map.getBounds();
        map.panTo([battle.lat, wrapLng(battle.lng, (bounds.getWest() + bounds.getEast()) / 2)]);
      }
    },
  };
}
