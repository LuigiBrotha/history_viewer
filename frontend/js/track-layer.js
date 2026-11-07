// The Sporen of the chosen Eenheden and Bevelhebbers: per Spoor a line through its battles in
// date order, an arrow halfway each step that shows the way, and the number of each battle.

// Strong, well-separated colours, one per Spoor, readable on both base maps.
export const TRACK_COLORS = ["#d7191c", "#2b83ba", "#1a9641", "#7b3294", "#e66101", "#008080"];

const ARROW_SIZE = 16;
const NUMBER_SIZE = 18;

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

function icon(className, size, html) {
  return L.divIcon({ className, iconSize: [size, size], html });
}

export function createTrackLayer(map) {
  const group = L.layerGroup().addTo(map);
  let drawn = [];
  const add = (layer) => {
    group.addLayer(layer);
    drawn.push(layer);
  };
  return {
    // tracks: [{ battles (in order, with positions), color }]
    setTracks(tracks) {
      drawn.forEach((layer) => group.removeLayer(layer));
      drawn = [];
      for (const { battles, color } of tracks) {
        if (battles.length > 1) {
          add(L.polyline(battles.map((b) => [b.lat, b.lng]), { color, weight: 3, opacity: 0.9, interactive: false }));
        }
        for (const { mid, angle } of trackSegments(battles)) {
          const arrow = document.createElement("span");
          arrow.textContent = "▶";
          arrow.style.color = color;
          arrow.style.transform = `rotate(${angle}deg)`;
          add(L.marker(mid, { icon: icon("track-arrow", ARROW_SIZE, arrow), interactive: false, keyboard: false }));
        }
        battles.forEach((battle, index) => {
          const number = document.createElement("span");
          number.textContent = String(index + 1);
          number.style.background = color;
          number.title = battle.title;
          add(L.marker([battle.lat, battle.lng], {
            icon: icon("track-number", NUMBER_SIZE, number), interactive: false, keyboard: false,
          }));
        });
      }
    },
  };
}
