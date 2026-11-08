import { durationText, labelsToShow, squaresToDraw, winnerClasses, wrapLng } from "./battle-model.js";

const SHOW_ZOOM = 8;

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

function squareIcon(battle, selected, outside = false, size = SQUARE_SIZE) {
  const classes = ["battle-square", ...winnerClasses(battle.winner)];
  if (outside) classes.push("outside-filter");
  if (battle.own) classes.push("own");
  if (selected) classes.push("selected");
  const span = document.createElement("span");
  if (size !== SQUARE_SIZE) {
    span.style.width = `${size}px`;
    span.style.height = `${size}px`;
  }
  return L.divIcon({ className: classes.join(" "), iconSize: [size, size], html: span });
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
  // The side of each battle's square (see spread.js); the plain size unless told otherwise.
  let sizeOf = () => SQUARE_SIZE;
  // Titles of the squares outside the labels, drawn dimmed ("Toon alle").
  let outside = new Set();
  let selected = null;
  let editing = null;

  function addSquare(battle) {
    const marker = L.marker([battle.lat, battle.lng], {
      icon: squareIcon(battle, selected === battle.title, outside.has(battle.title), sizeOf(battle)),
      battleTitle: battle.title,
      keyboard: false,
      riseOnHover: true,
    });
    marker.bindTooltip(tooltipContent(battle), { direction: "top", offset: [0, -SQUARE_SIZE / 2] });
    marker.on("click", () => onBattleClick?.(battle));
    group.addLayer(marker);
    marker.drawnFor = battle;
    marker.drawnOutside = outside.has(battle.title);
    marker.drawnSize = sizeOf(battle);
    squares.set(battle.title, marker);
    return marker;
  }

  function redraw() {
    const bounds = map.getBounds();
    const view = { south: bounds.getSouth(), west: bounds.getWest(), north: bounds.getNorth(), east: bounds.getEast() };
    const drawn = squaresToDraw(battles, view).filter((battle) => battle.title !== editing?.battle.title);
    // The square being edited is always drawn, wherever it is.
    const wanted = editing ? [...drawn, editing.battle] : drawn;
    const wantedByTitle = new Map(wanted.map((battle) => [battle.title, battle]));

    // A square is also redrawn when its battle has moved or changed hands since it was drawn.
    const stale = (marker, battle) => marker.drawnFor.lat !== battle.lat || marker.drawnFor.lng !== battle.lng
      || marker.drawnFor.own !== battle.own || marker.drawnOutside !== outside.has(battle.title)
      || marker.drawnSize !== sizeOf(battle);
    for (const [title, marker] of squares) {
      const battle = wantedByTitle.get(title);
      if (!battle || stale(marker, battle)) {
        group.removeLayer(marker);
        squares.delete(title);
      }
    }
    for (const battle of wanted) {
      if (squares.has(battle.title)) continue;
      addSquare(battle);
    }

    for (const label of labels) {
      group.removeLayer(label);
    }
    labels = labelsToShow(drawn.filter((battle) => !outside.has(battle.title)), map.getZoom()).map((battle) =>
      L.marker([battle.lat, battle.lng], { icon: labelIcon(battle), interactive: false, keyboard: false }),
    );
    for (const label of labels) {
      group.addLayer(label);
    }
  }

  map.on("moveend zoomend", redraw);

  function battleByTitle(title) {
    if (editing?.battle.title === title) return editing.battle;
    return battles.find((battle) => battle.title === title);
  }

  function stopEditing() {
    if (!editing) return;
    const { battle, marker } = editing;
    editing = null;
    marker.dragging.disable();
    // Drop the square so redraw puts it back where the battles say it is.
    group.removeLayer(marker);
    if (squares.get(battle.title) === marker) squares.delete(battle.title);
    redraw();
  }

  return {
    // How large each battle's square is drawn: a function of the battle.
    setSizes(next) {
      sizeOf = next;
      redraw();
    },
    setBattles(next, outsideTitles = new Set()) {
      battles = next;
      outside = outsideTitles;
      redraw();
    },
    // Marks the square of one battle (or none) as the one the pane points at.
    setSelected(battle) {
      selected = battle === null ? null : battle.title;
      for (const [title, marker] of squares) {
        const battle = battleByTitle(title);
        marker.setIcon(squareIcon(battle, title === selected, outside.has(title), sizeOf(battle)));
      }
    },
    // Makes one battle's square draggable; a battle without a position gets one at the
    // centre of the map. The square stays drawn until stop(), whatever setBattles gives.
    startEdit(battle, { onMove }) {
      stopEditing();
      const start = battle.lat != null && battle.lng != null ? battle : { ...battle, ...map.getCenter() };
      const session = { battle: { ...battle, lat: start.lat, lng: start.lng }, marker: null, position: null };
      editing = session;
      session.position = { lat: start.lat, lng: wrapLng(start.lng) };
      const existing = squares.get(battle.title);
      if (existing) group.removeLayer(existing);
      squares.delete(battle.title);
      session.marker = addSquare(session.battle);
      session.marker.dragging.enable();
      session.marker.on("dragend", () => {
        const { lat, lng } = session.marker.getLatLng();
        session.position = { lat, lng: wrapLng(lng) };
        onMove?.(session.position);
      });
      redraw();
      return {
        position: () => session.position,
        // Puts the square at a place found elsewhere, such as a search result, and pans to it.
        moveTo(lat, lng) {
          if (editing !== session) return;
          session.marker.setLatLng([lat, lng]);
          session.position = { lat, lng: wrapLng(lng) };
          map.panTo([lat, lng]);
        },
        stop() {
          if (editing === session) stopEditing();
        },
      };
    },
    // Pans without touching the zoom: the square stays at the zoom the user chose.
    // Centres the battle and zooms in to at least SHOW_ZOOM, never out.
    showBattle(battle) {
      if (battle.lat != null && battle.lng != null) {
        map.setView([battle.lat, battle.lng], Math.max(map.getZoom(), SHOW_ZOOM));
      }
    },
  };
}
