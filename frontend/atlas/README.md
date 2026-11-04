# Historical map overlays

These images are adapted from the "Ww2 allied axis" world maps on Wikimedia Commons,
listed in the "The world" section of
<https://commons.wikimedia.org/wiki/Atlas_of_World_War_II>. Each entry in
`manifest.json` links to its source file page, which names its authors.

- **Licence:** CC BY-SA 3.0, <https://creativecommons.org/licenses/by-sa/3.0/>. These
  adapted images are released under the same licence. The rest of this project is not
  covered by that licence.
- **Changes:** resampled from Robinson to Web Mercator, areas smoothed and thin borders
  within a bloc removed, recoloured to soft tints, background made transparent.
- **Rebuild:** `poetry run python -m tools.build_atlas_overlays <directory with the source files>`.

The sources are about 25 km per pixel and were fitted to modern coastlines by eye and
by overlap score, so they show the broad situation per month, not exact borders.
