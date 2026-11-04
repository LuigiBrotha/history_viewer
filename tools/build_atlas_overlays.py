"""Build the historical map overlays in frontend/atlas from Wikimedia Commons maps.

The "Ww2 allied axis" maps are drawn in Robinson with a central meridian near 10°E
and have no georeferencing. POSITION_FIT was fitted against Natural Earth land data
and holds for both source sizes (1480x625 and 1480x628). Each map is resampled to Web
Mercator so Leaflet can show it as one image, and recoloured so that thin route lines
stay readable on top. Run with the source files in a directory:

    poetry run python -m tools.build_atlas_overlays <source-dir>
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "atlas"
COMMONS_FILE_URL = "https://commons.wikimedia.org/wiki/File:"

NORTH = 84.0
SOUTH = -60.0
OUTPUT_WIDTH = 3000
# In source pixels: closes one-pixel white borders, keeps straits wider than a few pixels.
SMOOTHING_SIGMA = 1.0

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
MONTH_NAMES = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
               "augustus", "september", "oktober", "november", "december"]

TRANSPARENT = 0
SOURCE_WHITE = (255, 255, 255)
LEGEND = [
    {"name": "As", "source": (0x00, 0x00, 0x00), "color": (0x55, 0x55, 0x55)},
    {"name": "Westerse geallieerden", "source": (0x2a, 0xac, 0xf6), "color": (0x8f, 0xc1, 0xe3)},
    {"name": "Sovjet-Unie", "source": (0xf2, 0x0d, 0x0d), "color": (0xe5, 0x9a, 0x92)},
    {"name": "Neutraal", "source": (0xe0, 0xe0, 0xe0), "color": (0xd6, 0xd2, 0xc4)},
]

ROBINSON_X = np.array([1, .9986, .9954, .99, .9822, .973, .96, .9427, .9216, .8962, .8679, .835,
                       .7986, .7597, .7186, .6732, .6213, .5722, .5322])
ROBINSON_Y = np.array([0, .062, .124, .186, .248, .31, .372, .434, .4958, .5571, .6176, .6769,
                       .7346, .7903, .8435, .8936, .9394, .9761, 1])
ROBINSON_LAT = np.arange(0, 91, 5.0)

POSITION_FIT = {
    "central_meridian": 9.7, "scale_x": 281.3, "scale_y": 269.6, "origin_x": 736.2, "origin_y": 366.6,
    "x_terms": (-0.6, 0.6), "y_terms": (1.2, 1.8),
}


def map_date(file_name: str) -> date:
    match = re.search(r"(\d{4})_([a-z]{3})", file_name.lower())
    return date(int(match.group(1)), MONTHS[match.group(2)], 1)


def source_position(lat: np.ndarray, lng: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The pixel position of each coordinate on a source map."""
    fit = POSITION_FIT
    relative = (lng - fit["central_meridian"] + 180) % 360 - 180
    abs_lat = np.abs(lat)
    x = 0.8487 * np.interp(abs_lat, ROBINSON_LAT, ROBINSON_X) * np.radians(relative)
    y = 1.3523 * np.interp(abs_lat, ROBINSON_LAT, ROBINSON_Y) * np.sign(lat)
    u, v = relative / 180, lat / 90
    return (
        fit["origin_x"] + fit["scale_x"] * x + fit["x_terms"][0] * u * v + fit["x_terms"][1] * v * v,
        fit["origin_y"] - fit["scale_y"] * y + fit["y_terms"][0] * u * v + fit["y_terms"][1] * u * u,
    )


def recolor(source: np.ndarray) -> np.ndarray:
    """Indexes into the output palette: TRANSPARENT, or 1 + a LEGEND position."""
    anchors = np.array([SOURCE_WHITE] + [entry["source"] for entry in LEGEND], dtype=float)
    distances = np.linalg.norm(source[..., None, :].astype(float) - anchors, axis=-1)
    return np.argmin(distances, axis=-1)


def sample_smoothed(indexes: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Sample palette indexes at fractional positions, with smooth edges between areas.

    Each area is blurred and interpolated on its own and the strongest wins, which
    removes the source's pixel steps and its thin white borders within a bloc.
    """
    best_value = np.full(x.shape, -1.0)
    best_index = np.full(x.shape, TRANSPARENT, dtype=int)
    for index in range(len(LEGEND) + 1):
        mask = gaussian_filter((indexes == index).astype(float), SMOOTHING_SIGMA, mode="constant")
        value = map_coordinates(mask, [y, x], order=1, mode="constant")
        stronger = value > best_value
        best_value[stronger] = value[stronger]
        best_index[stronger] = index
    inside = (x >= 0) & (x < indexes.shape[1]) & (y >= 0) & (y < indexes.shape[0])
    best_index[~inside] = TRANSPARENT
    return best_index


def _mercator_y(lat: float) -> float:
    return np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def _output_grid() -> tuple[np.ndarray, np.ndarray]:
    top, bottom = _mercator_y(NORTH), _mercator_y(SOUTH)
    height = round(OUTPUT_WIDTH * (top - bottom) / (2 * np.pi))
    ys = top - (np.arange(height) + 0.5) / height * (top - bottom)
    lats = np.degrees(2 * np.arctan(np.exp(ys)) - np.pi / 2)
    lngs = -180 + (np.arange(OUTPUT_WIDTH) + 0.5) / OUTPUT_WIDTH * 360
    return np.meshgrid(lats, lngs, indexing="ij")


def build_overlay(path: Path, output: Path) -> None:
    source = np.asarray(Image.open(path).convert("RGB"))
    lat, lng = _output_grid()
    x, y = source_position(lat, lng)
    warped = sample_smoothed(recolor(source), x, y).astype(np.uint8)

    image = Image.fromarray(warped, mode="P")
    palette = [255, 255, 255] + [channel for entry in LEGEND for channel in entry["color"]]
    image.putpalette(palette)
    image.save(output, optimize=True, transparency=TRANSPARENT)


def main(source_dir: str) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    maps = []
    for path in sorted(Path(source_dir).iterdir(), key=lambda p: map_date(p.name)):
        when = map_date(path.name)
        file_name = f"{when:%Y-%m}.png"
        build_overlay(path, OUTPUT_DIR / file_name)
        maps.append({
            "date": when.isoformat(),
            "file": f"atlas/{file_name}",
            "label": f"{MONTH_NAMES[when.month - 1]} {when.year}",
            "source": COMMONS_FILE_URL + path.name,
        })
        print(file_name, (OUTPUT_DIR / file_name).stat().st_size // 1024, "KB")
    manifest = {
        "bounds": [[SOUTH, -180], [NORTH, 180]],
        "legend": [{"name": e["name"], "color": "#%02x%02x%02x" % e["color"]} for e in LEGEND],
        "maps": maps,
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
