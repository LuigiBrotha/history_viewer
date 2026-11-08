# Nog te verfijnen

Status: asked by the user on 2026-11-08, built without further questions. Branch: `uboat-verfijnen`.

## Asked

From the places an article names, take the 90% of the points with the smallest standard deviation among themselves; their centre of gravity is the Voorzet for the location. Sorting on "Nog te verfijnen" must be possible; the definitive location is set later by hand.

## Decided while building (the user can overturn these)

| Topic | Decision |
|---|---|
| Which Veldslagen | Automatic: every Veldslag with Plaatshints and neither a Wikipedia position nor an Eigen positie (1298 of 3382). Not a per-battle switch |
| Definitive location | The existing Positie aanpassen: the square starts on the Voorzet; Bewaar makes it an Eigen positie and the Veldslag leaves the group; wiping brings the Voorzet back |
| 90% | Rounded to the nearest whole place, halves down: 5 places keep 4, 2 keep both, 1 keeps itself |
| Smallest standard deviation | Repeat "take the nearest 90%, move to their mean" from the overall mean and up to 20 places; matches brute force on random samples |
| On the map | Drawn at the Voorzet with a dotted dark-red border |
| In the list | "nog te verfijnen" instead of "geen positie" |
| Sorting | Option "Nog te verfijnen" in the sort list: those first, each group by date (`sorteer=verfijnen`) |
| Filter | Also a label "Positie: nog te verfijnen" |
| No position, for the rest of the app | A Voorzet is no position: "Alleen zonder positie", Spoor and export treat these as without position |

## Checked on the data

For the 1763 Veldslagen with a Wikipedia position and Plaatshints the Voorzet lies a median 76 km from it (90th percentile 366 km); the plain mean of all places 97 km (383 km).
