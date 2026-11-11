// The symbol of a ship on the map: a six-armed star, a *, so ships stand apart from the round
// Bevrijdingen and the square Veldslagen. Drawn by Leaflet's SVG renderer like a circle marker,
// so clicks, tooltips and styles work as they did.

const ARMS = 6;
const NOTCH = 0.38;

// The corners of the star around (x, y): arm tips at `radius`, notches between them nearer the
// centre, starting straight up.
export function starPoints(x, y, radius) {
  const points = [];
  for (let i = 0; i < ARMS * 2; i += 1) {
    const angle = -Math.PI / 2 + (i * Math.PI) / ARMS;
    const r = i % 2 === 0 ? radius : radius * NOTCH;
    points.push([x + r * Math.cos(angle), y + r * Math.sin(angle)]);
  }
  return points;
}

export function starPath(x, y, radius) {
  const round = (v) => Math.round(v * 100) / 100;
  return `${starPoints(x, y, radius).map(([px, py], i) => `${i === 0 ? "M" : "L"}${round(px)} ${round(py)}`).join("")}Z`;
}

let StarMarker = null;
let base = null;

// A circle marker that draws a star where the circle would be.
export function starMarker(latlng, options) {
  if (base !== L.CircleMarker) {
    base = L.CircleMarker;
    StarMarker = base.extend({
    _updatePath() {
      if (!this._renderer?._setPath || !this._point) return;
      this._renderer._setPath(this, this._empty?.() ? "M0 0" : starPath(this._point.x, this._point.y, this._radius));
      },
    });
  }
  return new StarMarker(latlng, options);
}
