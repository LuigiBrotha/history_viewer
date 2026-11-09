# U-boot routes

Patrouilleroutes van U-boten uit de Tweede Wereldoorlog, op een kaart met tijdlijn. Overgeleverde posities gaan voor op volledigheid.

## Language

**Patrouille**:
Eén vaart van een boot, van vertrek tot aankomst.
_Avoid_: Route (als de vaart zelf wordt bedoeld), missie

**Routepunt**:
Een overgeleverde coördinaat met datum binnen een patrouille.
_Avoid_: Waypoint, positie

**Traject**:
Het stuk tussen twee opeenvolgende routepunten.
_Avoid_: Segment, leg

**Waterroute**:
De berekende kortste weg over water voor een traject. Een benadering, nooit een overgeleverde koers.
_Avoid_: Vaarroute, koers

**Onzeker traject**:
Een traject waarvoor geen geloofwaardige waterroute bestaat.
_Avoid_: Fout traject

**Verdacht traject**:
Een traject met een waterroute, maar waarvan de afstand voor het aantal dagen onwaarschijnlijk groot is. Wordt getoond, maar gemarkeerd.
_Avoid_: Onmogelijk traject, fout traject

**Uitgesloten punt**:
Een routepunt dat de gebruiker als onbetrouwbaar heeft aangemerkt en dat daarom niet meer meetelt in de patrouille. Kan weer worden hersteld.
_Avoid_: Verwijderd punt

**Gevolgde boot**:
De aangeklikte boot, gevolgd over al zijn patrouilles heen, zolang het Artikel over die boot of een van zijn schepen gaat.
_Avoid_: Gevolgde patrouille

**Schip**:
Een schip dat door een boot is geraakt, met zijn eigen gegevens. Staat één keer in de kolom Onderwerpen, ook als het meerdere Scheepstreffers heeft.
_Avoid_: Slachtoffer, doelwit

**Scheepstreffer**:
Een schip dat door een boot is gezonken, beschadigd of buitgemaakt, op een datum. Hetzelfde schip kan meerdere treffers hebben. De positie komt van de pagina van het schip en ontbreekt soms: dan telt de treffer mee in de totalen maar staat er geen punt op de kaart.
_Avoid_: Succes, slachtoffer

**Veldslag**:
Een militair conflict of operatie uit de Tweede Wereldoorlog-periode met een eigen artikel op een Wikipedia, met een begin- en einddatum en soms een positie. Artikelen in meerdere talen over dezelfde slag (verbonden door taallinks) vormen één Veldslag.
_Avoid_: Operatie, gevecht

**Onderwerp**:
Een Veldslag, boot of Schip: alles wat in de gelijknamige kolom staat en waarover het vak Artikel iets kan tonen.
_Avoid_: Item, topic

**Artikel**:
Wat de app over een Onderwerp toont in het vak Artikel: bij een Veldslag de tekst van het Wikipedia-artikel, bij een boot of Schip de gegevens van uboat.net. Er staat altijd maar één Onderwerp in.
_Avoid_: Wikipedia-pagina (als de weergave in de app wordt bedoeld), paneel

**Nederlandse versie**:
Het Artikel in het Nederlands: bij een Veldslag het artikel van de Nederlandse Wikipedia over dezelfde slag als dat er is, anders een machinevertaling van het origineel; bij een boot of Schip altijd een machinevertaling. Tegenover het origineel (het Artikel in zijn eigen taal).
_Avoid_: Vertaling (als het ook een Nederlands Wikipedia-artikel kan zijn)

**Kaartuitsnede**:
Het deel van de kaart dat in beeld is: middelpunt en zoomniveau.
_Avoid_: Viewport, view

**Pin**:
Een link waarin het hele beeld vastligt (datum of periode, geselecteerde Veldslag, Gevolgde boot, Kaartuitsnede), zodat precies dat moment later terug te halen is.
_Avoid_: Bookmark, favoriet

**Eigen positie**:
Een positie die de gebruiker zelf aan een Veldslag heeft gegeven. Gaat voor op de positie uit Wikipedia en kan weer worden gewist.
_Avoid_: handmatige locatie, override

**Kamp**:
Een van de vier groepen waarin de strijdende landen zijn ingedeeld: As, Westerse geallieerden, Sovjet-Unie en overig. Gelijk aan de indeling van de historische kaart, met een vierde groep voor de rest.
_Avoid_: Partij, zijde (als de groep wordt bedoeld)

**Winnaar**:
Het Kamp dat een Veldslag won, volgens de strategische uitkomst. Een onbesliste Veldslag heeft twee Kampen, een onbekende uitkomst geen.
_Avoid_: Overwinnaar

**Zoeken op de kaart**:
Het zoekveld linksboven op de kaartpagina's (Ctrl+K) om een boot, schip, Veldslag of plaats te kiezen; een keuze doet hetzelfde als erop klikken.
_Avoid_: kaartzoeker

**Zoeken in de onderwerpen**:
Het zoekveld boven de kolom Onderwerpen. Zoekt op naam en in de volledige tekst van elk Onderwerp, in alle talen, en laat een woord met een tikfout meetellen als het woord dat bedoeld was. De best passende Onderwerpen staan bovenaan.
_Avoid_: Fuzzy search (in de app), zoekfilter

**Eenheid**:
Een militaire eenheid met een eigen Wikipedia-artikel, zoals een divisie, brigade, leger, regiment of vloot. Gekoppeld aan een Veldslag wanneer de infobox van die Veldslag haar noemt.
_Avoid_: Krijgseenheid, troepen, unit

**Bevelhebber**:
Een generaal, admiraal of andere leider die in de infobox van een Veldslag als bevelhebber staat.
_Avoid_: Commandant (dat is de commandant van een boot), leider

**Land**:
Een land dat aan een Veldslag deelnam, aan welke kant dan ook. Elk Land hoort bij één Kamp.
_Avoid_: Natie, partij

**Spoor**:
De Veldslagen van één Eenheid of Bevelhebber op volgorde van datum, op de kaart verbonden door een lijn met pijlen. Een Veldslag die een kortere Veldslag uit hetzelfde Spoor helemaal omvat, telt niet mee.
_Avoid_: Route (dat is van een boot), pad

**Manschappen**:
Het aantal mensen dat een kant in een Veldslag inzette: soldaten plus de bemanning van tanks en vliegtuigen. Is het type tank of vliegtuig bekend, dan telt de bemanning van dat type; anders drie man per stuk.
_Avoid_: Troepen, sterkte, gewicht

**Manschappenband**:
Een band langs een Spoor waarvan de breedte de Manschappen van de eigen kant in elke Veldslag toont, naar het voorbeeld van Minard, met een wig voor de verliezen. Noemt een Veldslag geen soldaten, dan geldt het cijfer van de kleinste Veldslag eromheen die dat wel doet, mits dat geen hele veldtocht is; anders is dat stuk gestippeld.
_Avoid_: Minard-lijn, sterktelijn

**Label**:
Een filter boven de Veldslagenlijst, gekozen via het zoekveld, zoals 'Land: Polen' of 'Winnaar: As'. Met EN moet een Veldslag aan alle labels voldoen, met OF aan minstens één.
_Avoid_: Tag, chip

**Plaatshint**:
Een plaats die in een artikel over een Veldslag genoemd wordt, als driehoekje op de kaart zodra die Veldslag geselecteerd is. Komt uit het plaatsveld van de infobox (eigen kleur) of uit de tekst, gelinkt of niet. Een hint, geen positie: het vierkantje van de Veldslag blijft waar het is tot de gebruiker een Eigen positie bewaart.
_Avoid_: Locatie, kandidaat-positie

**Spreiding**:
Hoe ver de Plaatshints van een Veldslag uit elkaar liggen: hun standaardafwijking rond hun midden, in km. Een kleine Spreiding betekent dat de artikelen dicht bij elkaar liggende plaatsen noemen, dus dat de positie preciezer te bepalen is. Een Veldslag zonder Plaatshints heeft geen Spreiding.
_Avoid_: Spread, afwijking (dat is de afstand van de positie tot het midden)

**Voorzet**:
Een voorlopige positie voor een Veldslag: het zwaartepunt van de 90% van zijn Plaatshints die het dichtst bij elkaar liggen. Een voorstel, geen positie.
_Avoid_: Schatting, voorstel

**Nog te verfijnen**:
Een Veldslag die alleen een Voorzet heeft: geen positie uit Wikipedia en geen Eigen positie. Zodra de gebruiker een Eigen positie bewaart, is hij definitief geplaatst.
_Avoid_: Concept, voorlopig
