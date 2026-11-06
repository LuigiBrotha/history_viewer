# Filter: Veldslagen zonder positie

Date: 2026-11-06. Agreed with the user, one question at a time.

## Goal

The user wants to find quickly which Veldslagen still need an Eigen positie, so the work of placing them goes fast.

## Behaviour

- Under the search field of the Veldslagenlijst there is a checkbox: `Alleen zonder positie (N)`. It appears on `/`, `/status` and `/heatmap`, because all three use `createBattlePane`.
- **Zonder positie** means no position at all: no Wikipedia position and no Eigen positie. In code, that is `lat == null || lng == null` after `applyPositions`. A Veldslag the user has just placed drops out of the filtered list.
- With the box ticked, the list shows only Veldslagen that are:
  - without a position,
  - active on the chosen date (mode `date`: `activeOn`) or overlapping the chosen period (mode `period`: `overlaps`; with no period set, all of them count),
  - matching the search text.
- The filter follows the date and period: when they change (playback, period bar), the shown rows update.
- `N` is the number of rows that would be shown with the box ticked, under the current date or period and search text. It is also shown while the box is unticked. The title `Veldslagen (M)` keeps counting the rows actually shown.
- `reveal(battle)` of a row the filter hides clears the search text and unticks the box, just as it already clears the search.
- The box starts unticked. It is not remembered, and it is not part of the URL.
- With nothing matching, the existing text `Geen veldslagen gevonden.` shows.

## Out of scope

- Ordering or grouping by place name.
- Showing the hidden Veldslagen on the map (they have no position).

## Tests

`node --test` covers the following:
- a pure function in `battle-model.js` that selects the rows, combining position, date or period, and query;
- in `battle-pane`:
  - ticking the box hides the positioned and inactive rows;
  - a new date updates the shown rows;
  - the count `N` is correct;
  - `reveal` unticks the box;
  - a Veldslag that gets an Eigen positie (`setBattles` with new data) drops out.
