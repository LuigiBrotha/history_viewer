// The Sporen of the chosen Eenheden and Bevelhebbers: per Spoor a line through its battles in
// date order, an arrow halfway each step that shows the way, and the number of each battle.

// Strong colours, one per Spoor, unlike those of the Kampen on the squares (grey, blue, red,
// green, amber), so a Spoor never looks like a Winnaar.
export const TRACK_COLORS = [
  "#6b2fbf", "#ff6a00", "#00838f", "#c2185b", "#111111", "#8d5524",
  "#d500f9", "#00bfa5", "#7a8b00", "#3949ab", "#ff4081", "#5d4037",
];

// How a Spoor is named on the map: its Wikipedia title without the part between brackets.
export function trackName(value) {
  return value.replace(/\s*\([^)]*\)\s*$/, "");
}

// The colour of a Spoor label: its place among the Spoor labels picks it, so the line on the
// map and the chip above the list agree. Null for a label that draws no Spoor.
export function trackColor(labels, label) {
  const tracked = labels.filter((l) => l.kind === "bevelhebber" || l.kind === "eenheid");
  const index = tracked.findIndex((l) => l.kind === label.kind && l.value === label.value);
  return index < 0 ? null : TRACK_COLORS[index % TRACK_COLORS.length];
}

const LINE = { weight: 3, opacity: 0.9 };
const LIT = { weight: 6, opacity: 1 };
const DIMMED = { weight: 3, opacity: 0.2 };
const HIT_WEIGHT = 16;
const ARROW_SIZE = 16;
const NUMBER_SIZE = 18;
// The number sits as a badge above and left of the square, so it covers neither the square's
// colour nor the name to its right.
export const NUMBER_ANCHOR = NUMBER_SIZE + 3;
// Above the squares, which are drawn again (and so on top) whenever the map moves.
const ABOVE_SQUARES = 1000;

function mercatorY(lat) {
  const radians = (lat * Math.PI) / 180;
  return (Math.log(Math.tan(Math.PI / 4 + radians / 2)) * 180) / Math.PI;
}

// For each step between two points: its middle, and the angle (degrees, clockwise from east,
// as the map shows it) to turn an arrow that points east.
export function trackSegments(points) {
  const segments = [];
  for (let i = 1; i < points.length; i++) {
    const from = points[i - 1];
    const to = points[i];
    const dx = to.lng - from.lng;
    const dy = mercatorY(to.lat) - mercatorY(from.lat);
    segments.push({
      mid: [(from.lat + to.lat) / 2, (from.lng + to.lng) / 2],
      angle: (-Math.atan2(dy, dx) * 180) / Math.PI || 0, // never -0
    });
  }
  return segments;
}

function icon(className, size, html, iconAnchor) {
  return L.divIcon({ className, iconSize: [size, size], html, ...(iconAnchor && { iconAnchor }) });
}

export function createTrackLayer(map) {
  const group = L.layerGroup().addTo(map);
  let drawn = [];
  // Per Spoor its line and markers, to light one up and dim the rest while the mouse is on it.
  let parts = [];
  const add = (layer) => {
    group.addLayer(layer);
    drawn.push(layer);
    return layer;
  };
  const highlight = (lit) => parts.forEach((part) => {
    const on = part === lit;
    part.line?.setStyle(lit === null ? LINE : on ? LIT : DIMMED);
    if (on) part.line?.bringToFront();
    part.markers.forEach((marker) => marker.setOpacity(lit === null || on ? 1 : DIMMED.opacity));
  });
  return {
    // tracks: [{ battles (in order, with positions), color, name (optional: shown and hoverable) }]
    setTracks(tracks) {
      drawn.forEach((layer) => group.removeLayer(layer));
      drawn = [];
      parts = [];
      for (const { battles, color, name } of tracks) {
        const points = battles.map((b) => [b.lat, b.lng]);
        const part = { line: null, markers: [] };
        parts.push(part);
        if (battles.length > 1) {
          part.line = add(L.polyline(points, { color, ...LINE, interactive: false }));
        }
        for (const { mid, angle } of trackSegments(battles)) {
          const arrow = document.createElement("span");
          arrow.textContent = "▶";
          arrow.style.color = color;
          arrow.style.transform = `rotate(${angle}deg)`;
          part.markers.push(add(L.marker(mid, {
            icon: icon("track-arrow", ARROW_SIZE, arrow), interactive: false, keyboard: false, zIndexOffset: ABOVE_SQUARES,
          })));
        }
        battles.forEach((battle, index) => {
          const number = document.createElement("span");
          number.textContent = String(index + 1);
          number.style.background = color;
          number.title = battle.title_en || battle.title;
          part.markers.push(add(L.marker([battle.lat, battle.lng], {
            icon: icon("track-number", NUMBER_SIZE, number, [NUMBER_ANCHOR, NUMBER_ANCHOR]),
            interactive: false, keyboard: false, zIndexOffset: ABOVE_SQUARES,
          })));
        });
        if (!name || battles.length < 2) continue;
        // The name at the end of the Spoor, and a wide invisible line to hover: the real one is thin.
        const label = document.createElement("span");
        label.textContent = trackName(name);
        label.style.color = color;
        part.markers.push(add(L.marker(points.at(-1), {
          icon: icon("track-name", 0, label), interactive: false, keyboard: false, zIndexOffset: ABOVE_SQUARES,
        })));
        const tip = document.createElement("span");
        tip.textContent = trackName(name);
        add(L.polyline(points, { className: "track-hit", color, weight: HIT_WEIGHT, opacity: 0 })
          .bindTooltip(tip, { sticky: true })
          .on({ mouseover: () => highlight(part), mouseout: () => highlight(null) }));
      }
    },
  };
}
