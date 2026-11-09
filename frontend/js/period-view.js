import { readLabels, writeLabels } from "./battle-labels.js";
import { readRange, writeRange } from "./spread.js";
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
  if (initial.labelMode !== undefined) {
    urlSync.update({ labelMode: initial.labelMode });
    battles.setLabelMode?.(initial.labelMode);
  }
  if (initial.showAll !== undefined) {
    urlSync.update({ showAll: initial.showAll });
    battles.setShowAll?.(initial.showAll);
  }
  if (initial.spread !== undefined) {
    urlSync.update({ spread: initial.spread });
    battles.setSpreadRange?.(readRange(initial.spread));
  }
  if (initial.bandWidth !== undefined) {
    urlSync.update({ bandWidth: initial.bandWidth });
    battles.setBandWidth?.(initial.bandWidth);
  }
  if (initial.version !== undefined) {
    urlSync.update({ version: initial.version });
    battles.setArticleVersion?.(initial.version);
  } else if (battles.articleVersion?.() === "nl") {
    urlSync.update({ version: "nl" });
  }
  battles.onArticleVersionChange?.((version) => urlSync.update({ version: version === "nl" ? "nl" : null }));
  battles.onLabelsChange?.((labels) => urlSync.update({ filter: writeLabels(labels) || null }));
  battles.onSpreadChange?.((range) => urlSync.update({ spread: writeRange(range) }));
  battles.onBandWidthChange?.((px) => urlSync.update({ bandWidth: px }));
  battles.onLabelModeChange?.((mode) => urlSync.update({ labelMode: mode === "of" ? "of" : null }));
  battles.onShowAllChange?.((on) => urlSync.update({ showAll: on || null }));
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
      // Not used on every period page, but kept for the way back to the page that does.
      if (initial.routesOff) urlSync.update({ routesOff: true });
      if (initial.boatsOff) urlSync.update({ boatsOff: true });
      if (initial.shipsOff) urlSync.update({ shipsOff: true });
      restoreLabels(initial, urlSync, battles);
      if (initial.battle !== undefined) {
        pinnedBattle = initial.battle;
        pinnedMap = initial.map ?? null;
        urlSync.update({ battle: initial.battle });
        battles.selectBattle(initial.battle, { onResolved: endPinnedBattle });
      }
      if (initial.map !== undefined) {
        const { lat, lng, zoom } = initial.map;
        // moveend is not listened to yet, and the next write must not lose the Kaartuitsnede.
        urlSync.update({ map: initial.map });
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
