# Power-user options: shortcuts, labels, Sporen, export

Status: decided with the user on 2026-11-07. Decisions marked *(autonomous)* were taken while
the user was away ("werk zo ver mogelijk door zonder vragen") and are open for review.

Branches: `uboat-shortcuts` (step 2) and `uboat-filters` (steps 3–5, on top of
`uboat-more-languages` and `uboat-shortcuts`).

## Step 2: keyboard

| Topic | Decision |
|---|---|
| Keys | ↑/↓ previous/next Veldslag in the visible list (a click on that row), P Positie aanpassen, Enter Bewaar, Shift+Enter Bewaar en volgende, Esc annuleer, W Eigen positie wissen (asks first), A Artikel, V Veldslagenlijst, / or Ctrl+K search, ? overview. |
| Map focus | ↑/↓ always choose Veldslagen, also when the map has focus (Leaflet no longer pans with them). |
| Ignored | While typing in a field, on sliders and dividers, with Ctrl/Alt/Meta; Enter on a button keeps its own meaning. |
| Bewaar en volgende | A button in the edit bar and Shift+Enter: save, then edit the next battle without a position in the visible list. |
| Coordinates | Typed into the search field (`52.37, 4.89`, `51°59′N 5°55′E`, `N 52.5 E 13.4`), offered first as "Coördinaten" and picked like a place; never sent to Nominatim. |

## Step 3: labels and sorting

| Topic | Decision |
|---|---|
| Choosing | Through the search field, group "Filters": Land, Winnaar (Kamp / onbeslist / onbekend), Taal, Positie (eigen / Wikipedia), Eenheid, Bevelhebber. |
| Combining | All labels must match (AND), also two of one kind. |
| Checkbox | "Alleen zonder positie (N)" stays as it is (list only). |
| Map | Labels narrow the list and the squares on the map *(autonomous: a filter on the list only would hide nothing on the map and confuse)*. |
| Sorting | A select under the search field: date (default), name, duration. |
| URL | `filter=land:Polen,winnaar:as` and `sorteer=naam|duur`, carried by the links between map pages. |
| Land | Taken part on either side; one Dutch name per country, from flag templates, country codes and links in every language (`tools/countries.py`). |

## Step 4: Eenheden, Bevelhebbers and Sporen

| Topic | Decision |
|---|---|
| Sources | The Veldslag's infobox (`units1..3`, `commander1..3`, `BEFEHLSHABER1/2`, `dowódca1/2`; linked names only) and the `battles` field of the English articles of units and people (`tools/extract_unit_battles.py`), with their redirects as other names. |
| Clean-up | *(autonomous)* Ranks linked beside a name (Admiral, Major (rank), Kapitänleutnant…) are dropped; units named in a commander field (fronts, army groups, Stavka) count as Eenheden. |
| Spoor | The Veldslagen of the Eenheid or Bevelhebber with a position, by start date, joined by a line with an arrow per step and numbered; shown whole whatever the date or period. A battle that holds a shorter battle of the same Spoor is left out. Each Spoor has its own colour. |

## Step 5: export and back-up

| Topic | Decision |
|---|---|
| Export | Under the list: the visible battles (labels and search applied) as CSV or GeoJSON. |
| Back-up | All Eigen posities as JSON; restoring only on the laptop: the back-up wins where it differs, what it lacks stays, after a confirmation with the number of changes. |

## Colours

*(autonomous, after "kleuren strakker, meer contrast")* The Kampen keep the hues of the atlas
legend but strong: As #404040, westers #1f6fd1, sovjet #d62020, overig #1e9e3a; unknown stays
amber. The Sporen use colours unlike those: purple, orange, teal, magenta, black, brown. The
atlas layer itself (ready-made map images) is unchanged.
