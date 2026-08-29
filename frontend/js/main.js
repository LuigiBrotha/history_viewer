import { fetchBoats, fetchRoutes } from "./api.js";
import { activeBoatsOnDate, dateRange } from "./time-model.js";
import { createMap, renderActiveBoats, renderFollowedRoute, clearFollowedRoute } from "./map.js";
import { initTimeline } from "./timeline.js";
import { renderBoatList, updateDateLabel } from "./sidebar.js";

async function main() {
  const [boats, routes] = await Promise.all([fetchBoats(), fetchRoutes()]);

  const boatsBySlug = new Map(boats.map((boat) => [boat.slug, boat]));

  const routesBySlug = new Map();
  for (const patrol of routes) {
    if (!routesBySlug.has(patrol.boat_slug)) {
      routesBySlug.set(patrol.boat_slug, []);
    }
    routesBySlug.get(patrol.boat_slug).push(patrol);
  }

  const range = dateRange(routes);
  const labelEl = document.getElementById("boat-date-label");

  if (range === null) {
    labelEl.textContent = "Geen gedateerde routepunten beschikbaar.";
    return;
  }

  const mapState = createMap("map");

  const sliderEl = document.getElementById("date-slider");
  const playPauseEl = document.getElementById("play-pause");
  const dateDisplayEl = document.getElementById("date-display");
  const listEl = document.getElementById("boat-list");
  const resetButton = document.getElementById("reset-follow");
  const toggleSidebarButton = document.getElementById("toggle-sidebar");
  const sidebarEl = document.getElementById("sidebar");

  let followedSlug = null;
  let followedPatrol = null;
  let currentDate = range.min;

  function render(date) {
    currentDate = date;
    const active = activeBoatsOnDate(routes, date);
    updateDateLabel(labelEl, date);

    if (followedSlug !== null) {
      const followedBoatActive = active.find((boat) => boat.boatSlug === followedSlug);
      renderActiveBoats(mapState, [], onBoatSelect);
      renderFollowedRoute(
        mapState,
        followedPatrol,
        followedBoatActive ? { lat: followedBoatActive.lat, lng: followedBoatActive.lng } : null,
      );
    } else {
      clearFollowedRoute(mapState);
      renderActiveBoats(mapState, active, onBoatSelect);
    }

    renderBoatList({ listEl, activeBoats: active, followedSlug, onBoatSelect, boatsBySlug });
  }

  function onBoatSelect(slug) {
    followedSlug = slug;
    const boatRoutes = routesBySlug.get(slug) || [];
    followedPatrol = boatRoutes.length > 0 ? boatRoutes[0] : null;
    resetButton.hidden = false;
    render(currentDate);
  }

  resetButton.addEventListener("click", () => {
    followedSlug = null;
    followedPatrol = null;
    resetButton.hidden = true;
    clearFollowedRoute(mapState);
    render(currentDate);
  });

  toggleSidebarButton.addEventListener("click", () => {
    sidebarEl.classList.toggle("collapsed");
  });

  initTimeline({
    sliderEl,
    playPauseEl,
    dateDisplayEl,
    minDate: range.min,
    maxDate: range.max,
    onDateChange: render,
  });
}

main().catch((error) => {
  console.error(error);
  document.body.innerHTML = `<p style="padding: 20px; color: red;">Fout bij laden: ${error.message}</p>`;
});
