import { readLabels, writeLabels } from "./battle-labels.js";
import { readView } from "./url-state.js";

// The view of a period page (/status, /heatmap) in its URL: the period, the Veldslag, the
// Kaartuitsnede and "Alleen zonder positie". restore() applies the URL once the slider and
// the battles exist; the on* hooks report changes. Showing the restored battle pans the
// map, so a pinned Kaartuitsnede is applied again when that battle shows.
// Applies the labels and sort order of a URL view, and keeps their later changes in the URL.
// Shared by the map page (main.js) and the period pages.
export function restoreLabels(initial, urlSync, battles) {
  if (initial.filter !== undefined) {
    urlSync.update({ filter: initial.filter });
    battles.setLabels?.(readLabels(initial.filter));
  }
  if (initial.sort !== undefined) {
    urlSync.update({ sort: initial.sort });
    battles.setSort?.(initial.sort);
  }
  battles.onLabelsChange?.((labels) => urlSync.update({ filter: writeLabels(labels) || null }));
  battles.onSortChange?.((sort) => urlSync.update({ sort: sort === "datum" ? null : sort }));
}

export function createPeriodView({ search, urlSync, map }) {
  const initial = readView(search, "period");
  let pinnedBattle = null;
  let pinnedMap = null;

  function applyPinnedMap() {
    const { lat, lng, zoom } = pinnedMap;
    pinnedMap = null;
    map.setView([lat, lng], zoom, { animate: false });
  }

  function endPinnedBattle(found) {
    if (!found) urlSync.update({ battle: null });
    pinnedBattle = null;
    pinnedMap = null;
  }

  return {
    // Whether the URL fixes the map, so the page should not fit it to its data.
    mapPinned: () => initial.map !== undefined,
    restore({ slider, battles }) {
      if (initial.from !== undefined || initial.to !== undefined) {
        urlSync.update({ from: initial.from ?? null, to: initial.to ?? null });
        slider.setPeriod(initial.from ?? null, initial.to ?? null);
      }
      if (initial.nopos) {
        urlSync.update({ nopos: true });
        battles.setOnlyWithoutPosition(true);
      }
      restoreLabels(initial, urlSync, battles);
      if (initial.battle !== undefined) {
        pinnedBattle = initial.battle;
        pinnedMap = initial.map ?? null;
        urlSync.update({ battle: initial.battle });
        battles.selectBattle(initial.battle, { onResolved: endPinnedBattle });
      }
      if (initial.map !== undefined) {
        const { lat, lng, zoom } = initial.map;
        map.setView([lat, lng], zoom, { animate: false });
      }
      map.on("moveend", () => {
        const center = map.getCenter();
        urlSync.update({ map: { lat: center.lat, lng: center.lng, zoom: map.getZoom() } });
      });
    },
    onPeriod: ({ from, to }) => urlSync.update({ from, to }),
    onBattleChange(title) {
      urlSync.update({ battle: title });
      if (pinnedMap !== null && title === pinnedBattle) applyPinnedMap();
    },
    onNoposChange: (on) => urlSync.update({ nopos: on || null }),
  };
}
