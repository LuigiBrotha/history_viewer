# Artikelen renderen we zelf uit de wikitext van de dump

Naast de lijst met Veldslagen toont de app het Artikel van de geselecteerde Veldslag. De lijst
zelf komt al uit een lokale dump van de Engelse Wikipedia (`tools/extract_battles.py`). Die dump
bevat alleen wikitext, met sjablonen (infobox, `{{convert}}`, `{{flag}}`, …) die nog niet zijn
uitgewerkt.

We bewaren de wikitext van elke Veldslag, en de redirects ernaartoe, in `uboats.db`. Dat gebeurt
in dezelfde doorloop van de dump die `battles.json` maakt. De backend zet de wikitext bij een
verzoek om naar opgeschoonde HTML met een eigen renderer: koppen, alinea's, lijsten, links,
afbeeldingen en een eigen infobox op basis van de sjabloonvelden. Onbekende sjablonen worden
weggelaten of als platte tekst getoond. De backend haalt afbeeldingen de eerste keer op bij
Wikimedia en bewaart ze lokaal.

## Overwogen alternatieven

- **Gerenderde HTML van de Wikipedia-API ophalen en cachen.** Dat geeft de trouwste weergave,
  maar maakt de app voor elk nieuw Artikel afhankelijk van internet. Bovendien kan de tekst
  afwijken van de dump waaruit de lijst komt.
- **De Wikipedia-pagina in een iframe tonen.** Dat kost het minste werk, maar dan komen het
  menu en de zijbalk van Wikipedia mee, de pagina past niet bij de stijl van de app en links
  naar andere Veldslagen kunnen niet in de app openen.

## Gevolgen

Artikelen zien er eenvoudiger uit dan op Wikipedia, en sommige sjablonen ontbreken. Een betere
renderer werkt meteen voor alle Artikelen, zonder dat de dump opnieuw gelezen hoeft te worden.
Voor nieuwe tekst moet wel de hele dump opnieuw worden doorgelopen.
