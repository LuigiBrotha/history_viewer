# Manschappenband: eerst voor Erwin Rommel

Gegrild met de gebruiker op 2026-11-09. Termen staan in `CONTEXT.md` (Manschappen, Manschappenband, Spoor).

## Doel

Kies je het Label `Bevelhebber: Erwin Rommel`, dan loopt langs zijn Spoor een band waarvan de breedte het aantal Manschappen van zijn kant toont, naar het voorbeeld van Minards kaart van de veldtocht naar Moskou.

## Buiten deze stap

- Andere Bevelhebbers en Eenheden: hun Spoor blijft zoals het is. Uitzondering: Bernard Montgomery zit ook in het cijferbestand, als tweede proef met dezelfde regels.
- Een band voor de tegenstander.
- Kleur naar Winnaar of richting: de band heeft één kleur.
- Een parser voor de sterktevelden van alle Veldslagen. Het cijferbestand is wel zo opgezet dat die het later kan vullen.

## Besluiten

### Wat de breedte betekent

- **Manschappen** = soldaten + bemanning van tanks en vliegtuigen.
- Bemanning per stuk: 3 man voor een tank en 3 man voor een vliegtuig, tenzij het type bekend is. Dan telt de bemanning van dat type uit het Wikipedia-artikel erover.
- Alleen de **eigen kant**: de kolom van de infobox waarin Rommel staat. Het cijfer geldt voor de hele kant (bij Gazala ook de Italianen), niet voor zijn eigen troepen. De tooltip zegt dat.
- Bij een bereik telt het midden (37.000–45.000 wordt 41.000). Bij "initially … later" telt het eerste cijfer. Soldaten worden niet gecorrigeerd voor tankbemanningen die misschien al meetellen.

### Veldslagen zonder aantal soldaten

Een Veldslag zonder aantal soldaten, ook als er alleen tanks of vliegtuigen staan, neemt het cijfer over van de kleinste Veldslag eromheen die wel soldaten noemt, **mits dat geen hele veldtocht is**. Anders is dat stuk gestippeld en toont de tooltip de oorspronkelijke tekst.

Een overgenomen cijfer staat in de tooltip als "cijfer van …". Een Veldslag mag zijn cijfer alleen uitlenen aan Veldslagen in hetzelfde gebied.

| # | Veldslag | Manschappen komen uit |
|---|---|---|
| 1 | Battle of Arras (1940) | eigen cijfer |
| 2 | Siege of Lille (1940) | eigen cijfer |
| 3 | Combat de Pont-de-l'Arche | gestippeld (alleen Westfront eromheen) |
| 4 | Raid on Bardia | beleg van Tobruk |
| 5 | Operation Brevity | beleg van Tobruk |
| 6 | Operation Battleaxe | beleg van Tobruk |
| 7 | Operation Flipper | beleg van Tobruk |
| 8 | Operation Crusader | eigen cijfer |
| 9 | Battle of Bir Hakeim | eigen cijfer |
| 10 | Axis capture of Tobruk | Gazala |
| 11 | Battle of Mersa Matruh | gestippeld (alleen tanks) |
| 12 | First Battle of El Alamein | eigen cijfer |
| 13 | Battle of Alam el Halfa | gestippeld (alleen divisies) |
| 14 | Second Battle of El Alamein | eigen cijfer |
| 15 | Battle of El Agheila | eigen cijfer |
| 16 | Battle of Tripoli (1943) | gestippeld (alleen Tunesië eromheen) |
| 17 | Battle of Kasserine Pass | eigen cijfer |
| 18 | Battle of Medenine | gestippeld (alleen divisies, Tunesië eromheen) |
| 19 | Operation Achse | gestippeld (alleen divisies) |
| 20 | Lądowanie w Normandii | eigen cijfer |

Dit zijn de 20 Veldslagen die het Spoor nu tekent: met een positie uit Wikipedia of een Eigen positie, en zonder een kortere Veldslag van hetzelfde Spoor erin. Een Voorzet telt niet als positie.

### Hoe de band eruitziet

- De breedte loopt **vloeiend** van het cijfer van de ene Veldslag naar dat van de volgende.
- Bij een Veldslag met eigen verliescijfer staat een **donkere wig** op dezelfde schaal aan de rand van de band. Verlies = doden, gewonden, vermisten en gevangenen, plus verloren tanks en vliegtuigen omgerekend naar bemanning. Verliezen worden niet overgenomen van een omvattende slag.
- De band is **hoekig**: rechte uiteinden en scherpe hoeken (bij een scherpe bocht een schuine kant in plaats van een lange punt). Een Veldslag met cijfer zonder band ernaast is een kort rechthoekje.
- De kleur is de **Spoorkleur**, half doorzichtig.
- Een stap waarvan een van beide uiteinden geen cijfer heeft, is een fijne stippellijn.
- Bij een Bevelhebber met band vervangt de band de Spoorlijn; pijlen en nummers blijven.
- De band ligt onder de bestaande Spoorlijn, pijlen en nummers, en onder de vierkantjes.

### Schaal en bediening

- De breedte is **lineair** in vaste pixels: gelijk bij elke zoom. Geen enkel deel is dunner dan 4 px.
- Een **schuif voor de dikte** zet de breedte van het hoogste cijfer (standaard 48 px, Lille, 163.000 Manschappen). De rest schaalt mee.
- De band verschijnt **automatisch** met het Label, op elke pagina die het Spoor tekent. Geen aparte aan/uit-knop.
- Een kleine legenda bij de schuif geeft een schaalstreepje en de zin "cijfer per kant, niet per Bevelhebber".
- Keuze zelf ingevuld: de schuifstand staat in de URL (`banddikte=`), zodat een Pin dezelfde dikte terugbrengt.

### Tooltip

Bij hover op een stuk band of wig staan: naam van de Veldslag, Manschappen, de opbouw (soldaten, tanks × bemanning, vliegtuigen × bemanning), de oorspronkelijke infoboxtekst en, als het zo is, "cijfer van …".

## Gegevens

Eén gecontroleerd bestand `frontend/battles/manschappen.json`, naast `battles.json`, per Bevelhebber en Veldslagtitel. Per slag:

- kolom van de eigen kant;
- soldaten (getal of leeg), tanks en vliegtuigen als lijst `{type, aantal, bemanning, bron}`;
- verliezen in dezelfde vorm;
- oorspronkelijke tekst van de infobox en een bronverwijzing;
- `overgenomen_van` als het cijfer van een omvattende slag komt.

Het bestand wordt één keer gevuld vanuit de wikitext in `uboats.db`, regel voor regel nagekeken, en daarna met de hand bijgehouden. Bemanningen per type komen uit de `crew`-velden van de Wikipedia-artikelen over die types, in de lokale dump.

## Uitvoering

Op een eigen branch; pas op `master` na een browsercheck door de gebruiker.
