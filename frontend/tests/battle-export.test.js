import { test } from "node:test";
import assert from "node:assert/strict";

import { backupText, readBackup, restorePlan, toCsv, toGeoJson } from "../js/battle-export.js";

const battles = [
  { title: 'Slag om "K", oost', start: "1940-05-12", end: "1940-05-14", lat: 53.07, lng: 5.33, own: true, lang: "nl",
    url: "https://nl.wikipedia.org/wiki/K", place: "Kornwerderzand", winner: ["westers"], countries: ["Nederland", "Duitsland"],
    commanders: [], units: [] },
  { title: "Unplaced", start: "1941-01-01", end: "1941-01-02", lat: null, lng: null, winner: [], url: "u" },
];

test("CSV has a header, quotes where needed and one row per battle", () => {
  const lines = toCsv(battles).trim().split("\r\n");
  assert.equal(lines[0], "titel,taal,begin,einde,breedte,lengte,eigen_positie,plaats,winnaar,landen,bevelhebbers,eenheden,url");
  assert.equal(lines[1], '"Slag om ""K"", oost",nl,1940-05-12,1940-05-14,53.07,5.33,ja,Kornwerderzand,westers,Nederland; Duitsland,,,https://nl.wikipedia.org/wiki/K');
  assert.equal(lines[2], "Unplaced,en,1941-01-01,1941-01-02,,,nee,,,,,,u");
});

test("GeoJSON holds only battles with a position, as points", () => {
  const data = JSON.parse(toGeoJson(battles));
  assert.equal(data.type, "FeatureCollection");
  assert.equal(data.features.length, 1);
  assert.deepEqual(data.features[0].geometry, { type: "Point", coordinates: [5.33, 53.07] });
  assert.equal(data.features[0].properties.titel, 'Slag om "K", oost');
  assert.equal(data.features[0].properties.eigen_positie, true);
});

test("a backup round trips and a bad file is refused", () => {
  const positions = [{ title: "A", lat: 1, lng: 2 }];
  assert.deepEqual(readBackup(backupText(positions)), positions);
  assert.throws(() => readBackup("not json"));
  assert.throws(() => readBackup(JSON.stringify({ positions: [{ title: "A", lat: 100, lng: 2 }] })));
  assert.throws(() => readBackup(JSON.stringify({ something: [] })));
});

test("restorePlan sets what is missing or different and leaves the rest", () => {
  const current = [{ title: "A", lat: 1, lng: 2 }, { title: "B", lat: 3, lng: 4 }, { title: "Only here", lat: 0, lng: 0 }];
  const backup = [{ title: "A", lat: 1, lng: 2 }, { title: "B", lat: 5, lng: 6 }, { title: "C", lat: 7, lng: 8 }];
  assert.deepEqual(restorePlan(current, backup), {
    set: [{ title: "B", lat: 5, lng: 6 }, { title: "C", lat: 7, lng: 8 }],
    unchanged: 1,
  });
});
