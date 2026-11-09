# Manschappenband Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kies je het Label `Bevelhebber: Erwin Rommel`, dan loopt langs zijn Spoor een Minard-achtige band met de breedte van zijn Manschappen.

**Architecture:** Een nagekeken bestand `frontend/battles/manschappen.json` levert de cijfers. Een puur model (`manpower.js`) maakt daar per Spoor een rij stops van; een Leaflet-laag (`manpower-layer.js`) tekent die in vaste pixels onder de Spoorlijn. `battles.js` voedt de laag vanuit `drawTracks()`.

**Tech Stack:** Vanilla ES-modules, Leaflet, `node --test`.

**Spec:** `docs/superpowers/specs/2026-11-09-manschappenband-design.md`

## Global Constraints

- Alleen `Erwin Rommel`; andere Sporen veranderen niet.
- Tank en vliegtuig: 3 man per stuk, tenzij het type bekend is; dan de bemanning van dat type.
- Bij een bereik het midden; bij "initially … later" het eerste cijfer.
- Lenen alleen van `Siege of Tobruk` en `Battle of Gazala`, nooit van een hele veldtocht.
- Breedte lineair in vaste pixels; standaard 48 px voor het hoogste cijfer.
- Eén kleur per band: de Spoorkleur.
- Code en commentaar in het Engels, zichtbare tekst en sleutels in het cijferbestand in het Nederlands, zoals de rest van het project.
- Eigen branch `uboat-manschappenband` in een worktree. Pas op `master` na browsercheck door de gebruiker.
- Commitberichten eindigen met `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- Een Veldslag in het Spoor die niet in het bestand staat (nieuwe Eigen positie): stippellijn, geen fout. Test in Task 2.
- Twee opeenvolgende Veldslagen op exact dezelfde plek: geen NaN, geen polygoon voor die stap. Test in Task 3.
- `manschappen.json` laadt niet: het Spoor werkt gewoon door, zonder band. Test in Task 3.
- `banddikte=0`, `banddikte=9999`, `banddikte=abc` in de URL: begrensd of genegeerd. Test in Task 4.
- Verlies groter dan de band, of verlies bij een gestippelde slag: wig nooit dieper dan de band, geen wig zonder band. Test in Task 3.

---

### Task 1: Cijferbestand

**Files:**
- Create: `frontend/battles/manschappen.json`
- Test: `frontend/tests/manpower-data.test.js`

**Interfaces:**
- Produces: JSON `{ "Erwin Rommel": { "<titel>": { kolom, soldaten, tanks, vliegtuigen, verliezen, tekst, bron, overgenomen_van } } }`.
  - `soldaten`: getal of `null`. `tanks`/`vliegtuigen`: lijst `{ type, aantal, bemanning, bron }` (`type: null`, `bemanning: 3` als het type onbekend is).
  - `verliezen`: `{ manschappen, tanks, vliegtuigen }` of `null`.
  - `tekst`: de oorspronkelijke infoboxtekst, zonder voetnoten. `overgenomen_van`: titel of `null`.
  - Het bestand bevat de 20 slagen uit de spec plus de leners `Siege of Tobruk` en `Battle of Gazala`.

- [ ] **Step 1: Maak de worktree en neem de documenten mee**

Maak branch en worktree `uboat-manschappenband` vanaf `master`. Kopieer `CONTEXT.md`, de spec en dit plan vanuit de hoofdmap: ze zijn daar nog niet gecommit. `README.md` in de hoofdmap heeft een eigen wijziging: niet meenemen.

- [ ] **Step 2: Schrijf de falende test**

`manpower-data.test.js` leest het JSON-bestand en `battles.json` met `readFileSync` en controleert:

```js
test("every step of Rommel's Spoor is in the file and names a real Veldslag", ...); // de 20 titels uit de spec; elke titel staat in battles.json
test("own figures are as in the infobox", () => {
  // Arras 7500, Lille 160000, Crusader 119000, Bir Hakeim 41000,
  // First El Alamein 96000, Second El Alamein 116000, El Agheila 60000, Kasserine 22000
});
test("only these battles borrow, and only from real battles", () => {
  // Bardia, Brevity, Battleaxe, Flipper -> "Siege of Tobruk" (soldaten 35000)
  // Axis capture of Tobruk -> "Battle of Gazala" (soldaten 90000)
});
test("dotted battles have no soldiers and do not borrow", ...); // Pont-de-l'Arche, Mersa Matruh, Alam el Halfa, Tripoli, Medenine, Achse, Lądowanie
test("every tank and aircraft line has a crew and every Veldslag its original text", ...);
```

- [ ] **Step 3: Draai de test**

Run: `cd frontend && node --test tests/manpower-data.test.js`
Expected: FAIL, bestand ontbreekt.

- [ ] **Step 4: Vul het bestand**

Lees de velden `strengthN` en `casualtiesN` van elke slag uit `battle_articles` in `/home/scout/PycharmProjects/uboats/uboats.db` (alleen-lezen), met N de kolom van Rommel. Vul regel voor regel in, inclusief de typeverdeling uit voetnoten (Crusader, Second El Alamein). Zoek de bemanning per genoemd type in het `crew`-veld van het Engelse artikel: index en multistream staan in `~/.cache/uboats/wikipedia/`, het hulpscript blijft in de sessie-scratchpad, niet in de repo.

Voorbeeldwaarden die vastliggen:

| Slag | soldaten | tanks | vliegtuigen | verlies |
|---|---|---|---|---|
| Arras | 7500 | 225 | 0 | man 750, 37 tanks |
| Lille | 160000 | 882 | 0 | geen |
| Bir Hakeim | 41000 | 0 | 0 | man 3836, 49 vliegtuigen |

- [ ] **Step 5: Draai de test en controleer het bestand zelf**

Run: `cd frontend && node --test tests/manpower-data.test.js`
Expected: PASS. Lees daarna elke regel nog één keer naast de infobox.

- [ ] **Step 6: Commit**

```bash
git add frontend/battles/manschappen.json frontend/tests/manpower-data.test.js CONTEXT.md docs/superpowers/specs/2026-11-09-manschappenband-design.md docs/superpowers/plans/2026-11-09-manschappenband.md
git commit -m "Manschappen of Erwin Rommel per Veldslag, checked line by line against the infobox"
```

---

### Task 2: Model

**Files:**
- Create: `frontend/js/manpower.js`
- Test: `frontend/tests/manpower.test.js`

**Interfaces:**
- Consumes: de vorm van het bestand uit Task 1, per Bevelhebber als `table`.
- Produces:
  - `manpowerOf(title, table) -> { total, soldiers, tanks, aircraft, borrowedFrom } | null`
  - `lossesOf(title, table) -> number | null`
  - `bandStops(battles, table) -> [{ battle, manpower, loss, entry }]` (`entry` is `null` als de titel ontbreekt)
  - `bandSteps(stops) -> [{ from, to, solid }]`
  - `highestManpower(stops) -> number` (0 zonder cijfers)
  - `widthOf(manpower, highest, maxPx) -> number`
  - `stopText(stop) -> string`

- [ ] **Step 1: Schrijf de falende test**

```js
const table = {
  A: { soldaten: 7500, tanks: [{ type: null, aantal: 225, bemanning: 3 }], vliegtuigen: [],
       verliezen: { manschappen: 750, tanks: [{ type: null, aantal: 37, bemanning: 3 }], vliegtuigen: [] },
       tekst: "225 tanks; 5,000-10,000 infantry", overgenomen_van: null },
  L: { soldaten: 160000, tanks: [{ type: null, aantal: 882, bemanning: 3 }], vliegtuigen: [], verliezen: null, tekst: "x", overgenomen_van: null },
  B: { soldaten: null, tanks: [], vliegtuigen: [], verliezen: null, tekst: "y", overgenomen_van: "L" },
  M: { soldaten: null, tanks: [{ type: null, aantal: 100, bemanning: 3 }], vliegtuigen: [], verliezen: null, tekst: "100 tanks", overgenomen_van: null },
};
test("Manschappen are soldiers plus crews", () => assert.equal(manpowerOf("A", table).total, 8175));
test("tanks alone are not a figure", () => assert.equal(manpowerOf("M", table), null));
test("a borrowed figure names its source", () => assert.deepEqual(
  [manpowerOf("B", table).total, manpowerOf("B", table).borrowedFrom], [162646, "L"]));
test("losses are counted with crews and never borrowed", () => {
  assert.equal(lossesOf("A", table), 861);
  assert.equal(lossesOf("B", table), null);
});
test("a step needs a figure on both ends to be solid", ...); // A -> L solid, L -> M niet
test("a Veldslag that is not in the file becomes a dotted stop", ...); // bandStops met onbekende titel: manpower null, entry null, geen fout
test("the highest figure gets the full width and the rest is linear", () => {
  assert.equal(widthOf(162646, 162646, 48), 48);
  assert.ok(Math.abs(widthOf(8175, 162646, 48) - 2.4126) < 0.001);
  assert.equal(widthOf(100, 0, 48), 0);
});
test("the tooltip gives the build-up, the original text and the source of a borrowed figure", ...);
// stopText bevat de naam (title_en || title), "8.175", "225 tanks × 3", de tekst; bij B "cijfer van L"
```

- [ ] **Step 2: Draai de test**

Run: `cd frontend && node --test tests/manpower.test.js`
Expected: FAIL, module ontbreekt.

- [ ] **Step 3: Implementeer `frontend/js/manpower.js`**

Getallen in `stopText` met `toLocaleString("nl-NL")`. Geen cijfer: de eerste regel is de naam, daarna "Geen aantal soldaten" en de oorspronkelijke tekst.

- [ ] **Step 4: Draai de test**

Run: `cd frontend && node --test tests/manpower.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/js/manpower.js frontend/tests/manpower.test.js
git commit -m "Work out the Manschappen, losses and width of each step of a Spoor"
```

---

### Task 3: Band op de kaart

**Files:**
- Create: `frontend/js/manpower-layer.js`
- Modify: `frontend/js/battles.js` (`loadBattles` ernaast een lader; `drawTracks()` rond regel 283; `createTrackLayer` rond regel 248)
- Test: `frontend/tests/manpower-layer.test.js`, `frontend/tests/battles.test.js`

**Interfaces:**
- Consumes: alles uit Task 2.
- Produces:
  - `bandPolygon(a, b, widthA, widthB) -> [p, p, p, p] | null` (punten `{x, y}`; `null` als `a` en `b` samenvallen)
  - `lossWedge(point, tangent, width, lossPx) -> [p, p, p]`
  - `createManpowerLayer(map) -> { setBands(bands), setMaxWidth(px), maxWidth(), highest() }` met `bands: [{ stops, color }]`

- [ ] **Step 1: Schrijf de falende test**

Volg de nep-Leaflet uit `frontend/tests/track-layer.test.js`, uitgebreid met `polygon`, `circleMarker`, `createPane`, `getPane`, `on`, `latLngToLayerPoint`, `layerPointToLatLng`.

```js
test("bandPolygon runs from the width of one end to the width of the other", () => {
  const [p1, p2, p3, p4] = bandPolygon({ x: 0, y: 0 }, { x: 10, y: 0 }, 4, 8);
  // p1 (0, 2)-ish, p2 (10, 4), p3 (10, -4), p4 (0, -2), in die volgorde (teken volgens de normaal)
});
test("two battles on the same spot draw no polygon", () =>
  assert.equal(bandPolygon({ x: 1, y: 1 }, { x: 1, y: 1 }, 4, 8), null));
test("a wedge is never deeper than the band", ...); // lossWedge met lossPx > width: diepte === width
test("a step without figures is dashed and a battle without a band has no wedge", ...);
test("the width follows the slider and every part is redrawn on zoom", ...);
test("setBands([]) removes everything", ...);
```

In `battles.test.js`:

```js
test("without the figures file the Spoor is drawn as before and no band appears", ...); // fetch van manschappen.json faalt
test("only the Label of Erwin Rommel gets a band", ...); // een andere Bevelhebber: setBands([])
```

- [ ] **Step 2: Draai de tests**

Run: `cd frontend && node --test tests/manpower-layer.test.js tests/battles.test.js`
Expected: de nieuwe tests FAIL.

- [ ] **Step 3: Implementeer `frontend/js/manpower-layer.js`**

Panes: `manpower` met z-index 395 en `opacity: 0.55` op de pane, zodat overlappende delen niet donkerder worden; `manpower-losses` met z-index 396 voor de wiggen. Beide onder de Spoorlijn (`overlayPane`, 400).

- Rekenen in layer points (`map.latLngToLayerPoint`), terug met `layerPointToLatLng`, opnieuw tekenen op `zoomend`.
- Elke stop met cijfer krijgt een cirkel met diameter gelijk aan de breedte, zodat de hoeken dicht zijn.
- Elke stap is een `L.polygon` in de Spoorkleur, zonder rand. Een niet-solide stap is een `L.polyline` met `dashArray: "4 6"`, `weight: 2`.
- Wig: `#2a2521`, aan de linkerrand van de band, basis 12 px langs de band, diepte `widthOf(loss, …)` begrensd op de bandbreedte, minimaal 1 px.
- Tooltip met `stopText`: een cirkel en een wig tonen hun stop; een stap toont beide stops onder elkaar. Vul tooltips via `textContent`, niet via HTML.

- [ ] **Step 4: Koppel aan `battles.js`**

Laad `battles/manschappen.json` naast `battles.json`; een fout wordt met `console.error` gelogd en laat `table` leeg. In `drawTracks()`: voor elk `tracked` Label met `label.kind === "bevelhebber"` en een eigen deel in `table`, `{ stops: bandStops(track(battles, label), table[label.value]), color: trackColor(labels, label) }`, en roep `manpowerLayer.setBands` aan. Teken opnieuw zodra het bestand binnen is.

- [ ] **Step 5: Draai alle frontend-tests**

Run: `cd frontend && node --test tests/`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/js/manpower-layer.js frontend/js/battles.js frontend/tests/manpower-layer.test.js frontend/tests/battles.test.js
git commit -m "Draw the Manschappenband along the Spoor of Erwin Rommel, with a wedge for the losses"
```

---

### Task 4: Dikte-schuif, legenda en URL

**Files:**
- Modify: `frontend/js/manpower-layer.js`, `frontend/js/url-state.js:66,99`, `frontend/js/period-view.js:29-40`, `frontend/js/battles.js:92-93,611-616`, `frontend/css/style.css`
- Test: `frontend/tests/manpower-layer.test.js`, `frontend/tests/url-state.test.js`, `frontend/tests/period-view.test.js`

**Interfaces:**
- Consumes: `createManpowerLayer`.
- Produces:
  - `clampBandWidth(value) -> number | undefined` (geheel 8–96, anders `undefined`)
  - `scaleBar(highest, maxPx) -> { men: 50000, px }`
  - `battles.setBandWidth(px)`, `battles.onBandWidthChange(listener)`
  - URL-veld `bandWidth` ↔ `banddikte=`, weggelaten bij de standaard 48

- [ ] **Step 1: Schrijf de falende test**

```js
test("the width of the band can be read from and written to the URL", () => {
  assert.equal(writeView({ bandWidth: 64 }, "date"), "?banddikte=64");
  assert.deepEqual(readView("?banddikte=64", "date"), { bandWidth: 64 });
  assert.deepEqual(carriedView({ date: "1942-01-01", bandWidth: 64 }), { bandWidth: 64 });
});
test("a width outside the slider is ignored", () => {
  for (const value of ["0", "9999", "abc"]) assert.deepEqual(readView(`?banddikte=${value}`, "date"), {});
});
test("the default width stays out of the URL", ...); // writeView({ bandWidth: 48 }, "date") === ""
test("the scale bar shows 50.000 Manschappen on the scale of the band", () =>
  assert.ok(Math.abs(scaleBar(162646, 48).px - 14.756) < 0.001));
test("the slider and the legend only show while there is a band", ...);
test("moving the slider sets the width and reports it", ...);
```

Pas in `url-state.js` ook `carriedView` aan als die velden per naam meeneemt.

- [ ] **Step 2: Draai de tests**

Run: `cd frontend && node --test tests/manpower-layer.test.js tests/url-state.test.js tests/period-view.test.js`
Expected: de nieuwe tests FAIL.

- [ ] **Step 3: Implementeer**

Een `L.Control` linksonder in `createManpowerLayer`, zichtbaar zolang er een band is, met: `<input type="range" min="8" max="96" step="1">` (label "Dikte band"), een schaalstreepje met "50.000 Manschappen" en de zin "Cijfer per kant, niet per Bevelhebber". Blokkeer kaartsleep in de control met `L.DomEvent.disableClickPropagation`. Stijl in het Archief-blok aan het eind van `style.css`. Koppel in `period-view.js` zoals `spread`: bij laden `battles.setBandWidth?.(initial.bandWidth)` als die er is, bij wijziging `urlSync.update({ bandWidth })` (bij 48 `undefined`). Geef de lege stub in `battles.js` rond regel 92 dezelfde twee methodes.

- [ ] **Step 4: Draai alle tests**

Run: `cd frontend && node --test tests/ && cd .. && poetry run pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/js/manpower-layer.js frontend/js/url-state.js frontend/js/period-view.js frontend/js/battles.js frontend/css/style.css frontend/tests/manpower-layer.test.js frontend/tests/url-state.test.js frontend/tests/period-view.test.js
git commit -m "A slider for the width of the Manschappenband, with a scale, kept in the URL"
```

- [ ] **Step 6: Browsercheck door de gebruiker**

Start de server vanuit de worktree op :8002 met de `uboats.db`-symlink. Laat op `/`, `/dag-tot-dag` en `/heatmap` controleren: Label Rommel kiezen, band met wiggen, gestippelde stukken, tooltip, schuif, inzoomen, Pin met `banddikte`. Merge pas na akkoord.
