# Bevrijdingen

Status: asked by the user on 2026-11-11, built without further questions. Branch: `uboat-bevrijdingen`.

## Asked

Show when places were liberated, taken only from Wikipedia and Wikidata, with as few requests as possible and for the smallest possible areas (places, not regions), as points on the map.

## Decided while building (the user can overturn these)

| Topic | Decision |
|---|---|
| Sources | Three list articles: the nl list of liberated Dutch places, the ru list of Soviet towns occupied and liberated, the ru list of towns abroad taken by the Soviet Army (`tools/liberations.py`) |
| Positions and names | Wikipedia API (coordinates and Wikidata item of each linked article) and Wikidata (labels; coordinates when the article has none), 50 per request, all cached in `~/.cache/uboats/liberations/` |
| Namesakes | A position outside the country's rough 1939–1945 bounds is a namesake elsewhere and is dropped; its Wikidata name too (Пуппен → "YouTube Poop") |
| Name on the map | Dutch label > English label (Wikidata) > Dutch-style transliteration (Жлобин → Zjlobin) |
| Two days | Of "2 of 3 oktober" or "nacht van 28-29 oktober" the last counts; the list's words are kept for the tooltip |
| A row the list repeats | Counts once (Havelte, 13 april 1945, stands twice in the nl list) |
| Liberator | Soviet fronts, fleets and flotillas in Dutch (1e Oekraïense Front, Zwarte Zeevloot); smaller units keep their Russian names; the nl list's units as written |
| Taken, not liberated | Towns in Axis countries (Germany, Austria, Hungary, Romania, Bulgaria) are "ingenomen". The ru list sorts towns abroad by today's borders: a "Polish" town outside a rough outline of interwar Poland was German (Breslau, Danzig: 137 towns), a Czechoslovak one east of the Moravia–Slovakia line lay in the Axis state Slovakia (32); both count as taken, without an occupied state |
| Layer | Its own layer on the Tijdlijn (`/dag-tot-dag`) and Alle routes (`/`); button "Bevrijdingen", URL `bevrijdingen=uit` |
| Tijdlijn | Filled in the As's colour while occupied (first built as an open circle; changed after the browser check, "De bezetting door de Duitsers zie ik nu niet op de kaart terug"), filled in the liberator's Kamp colour (nl → Westerse geallieerden, ru → Sovjet-Unie) from the liberation date; a town occupied twice (Kharkov) turns As-grey again |
| Occupied since | The Soviet town's own date; otherwise per country: Nederland 1940-05-10, Polen 1939-09-01, Noorwegen 1940-04-09, Tsjechoslowakije 1939-03-15, Joegoslavië 1941-04-06. Axis countries, China and Korea have no occupied state |
| Alle routes | The Bevrijdingen in the selected period in the liberator's colour, and the places still occupied at the end of the period in the As's colour (the atlas also shows the end of the period); an open end shows no occupation |
| A place listed twice | A record with its own occupation date starts a new occupation (Kharkov); one without joins the occupation before it, so Gulpen and Meijel stay liberated from their first date. Only a place's first occupation takes the country's start |
| Colour | Liberated circles use the Veldslag squares' own Kamp colour variables (`win1-westers`, `win1-sovjet`), so the paper theme changes both; a 1px dark outline like the ships |
| Load | Once, after the first routes are drawn, like the ships; the map works without it |
| Tooltip | Dutch, in time order: name (with the list's own spelling when it differs), occupied since, "bevrijd op" or "ingenomen op" with the list's own words for two days, and by whom: "Charkiv (Харьков) — bezet sinds 16 maart 1943 — bevrijd op 23 augustus 1943 door Steppefront" |
| Click | Like a click in the list: opens the Veldslag and moves the Tijdlijn to its start. Opens the matching Veldslag when the operation's ru article, or the English article it links to, is a Veldslag |
| Requests | API calls go as POST: 50 Cyrillic titles make a GET URL too long (HTTP 414). Without contact in the User-Agent (`CRAWLER_CONTACT` is empty) Wikipedia answers 429 now and then; the tool waits as long as `Retry-After` says |

## Sources considered

- The three lists give about 2100 dates in 3 requests, with the place's article linked in nearly every row. Chosen.
- The articles of the places themselves: only the ru and uk articles mention liberation consistently (in a fixed form), and reading them costs a request per place. Not used.
- Wikidata: almost no liberation data at place level, about 25 liberation items and 17 settlements with a linked liberation event. Used only for names and missing coordinates.

## Checked on the data

`frontend/battles/bevrijdingen.json` after the build:

- 2101 Bevrijdingen of 2021 places, 2068 with a position: nl 867 (864), Soviet towns 744 (740), towns abroad 490 (464; by wartime country: Duitsland 218, Polen 112, Hongarije 57, Slowakije 32, Roemenië 24, China 13, Oostenrijk 12, Tsjechoslowakije 11, Korea 5, Bulgarije 4, Joegoslavië 1, Noorwegen 1). 347 are "ingenomen".
- Dates run from 1941-07-13 to 1945-08-22; none outside 1939-09-01..1945-09-02, and no liberation before or on its occupation date.
- 56 Soviet towns have more than one Bevrijding (occupied twice); 4 were only partly occupied (Naro-Fominsk, Voronezj, Wolgograd, Novorossiejsk).
- The only places with two Bevrijdingen on one day are two places sharing one article (Cadier and Keer, Groot and Klein Genhout).
- No nl place lies more than 40 km from every other place liberated on the same day by the same unit; by day alone 22 do, all checked as genuine (Zeeuws-Vlaanderen, Kornwerderzand, Arnhem).
- A Latin name sharing little with the transliteration of the Russian (103) is a renamed place (German names now Polish, Диршау → Tczew; Soviet names changed since, Калинин → Tver, Сталино → Donetsk), except one: the list links Аллендорф to the river Łyna, so it stands at the river's mouth in the Kaliningrad region. The map shows today's names, not the wartime ones.
- 1209 records name an operation (136 articles); 241 of them match a Veldslag in `battles.json` by the ru article, 1022 once the English article of the operation counts too.
