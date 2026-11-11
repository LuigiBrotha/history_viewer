# Battles

`battles.json` lists World War II battles, operations and campaigns for the battle pane
and the squares on the maps.

Source: the English Wikipedia, text available under the
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) licence. Each record links
back to its article.

Dates and coordinates are parsed automatically from the infobox and `{{coord}}` of each
article, so they can be wrong or missing. An article whose date is only a year or is not
understood is left out; a battle without a coordinate is only listed, not drawn.

`winner` is the Kamp that won, read from the infobox `result` (strategic before tactical):
a list of `as`, `westers`, `sovjet` or `overig`. `[]` means unknown, two Kampen an undecided
battle (one per side).

## Rebuilding

Download `enwiki-latest-pages-articles.xml.bz2` from <https://dumps.wikimedia.org/enwiki/latest/>
into `~/.cache/uboats/wikipedia/` (25.8 GB, never unpacked), then run:

```
poetry run python -m tools.extract_battles [dump.xml.bz2 | directory] [--output FILE]
```

The dump is streamed once, which takes a while. The command prints progress to stderr and
a count per reason for the articles it skipped.

The same run also fills the tables `battle_articles` (the wikitext of each battle) and
`battle_redirects` (the redirects to those battles) in `uboats.db`; pass `--database URL` to
choose another database.

The `battles.json` in the repository was first built from the twelve sample articles in
`tests/fixtures/wikipedia/battle_pages.json`, so that the pages work before the full run.

## Articles and winners from the multistream dump

The Artikelen and the `winner` of the battles already in `battles.json` can be filled without
reading the whole dump. Download these three files from
<https://dumps.wikimedia.org/enwiki/20261001/> into `~/.cache/uboats/wikipedia/`:

- `enwiki-20261001-pages-articles-multistream.xml.bz2`
- `enwiki-20261001-pages-articles-multistream-index.txt.bz2`
- `enwiki-20261001-redirect.sql.gz`

Then run:

```
poetry run python -m tools.fill_battle_articles [--dir DIR] [--database URL] [--battles FILE]
```

Only the bz2 streams that hold a battle are read (peak memory about 60 MB). A rerun replaces
the articles and redirects and rewrites `winner` in `battles.json`, keeping everything else.

## Bevrijdingen

`bevrijdingen.json` lists when places were liberated (and, for Soviet towns, occupied), one
Bevrijding per line. It is harvested from three list articles:

- nl: *Chronologisch overzicht van de bevrijding van Nederlandse plaatsen in de Tweede
  Wereldoorlog* (date, place, who liberated it);
- ru: *Список городов СССР, оккупированных и освобождённых во время Великой Отечественной войны*
  (occupied and liberated, fronts, operation; a town occupied twice has two records);
- ru: *Список зарубежных городов, освобождённых Советской Армией во время Великой Отечественной
  войны* (the date a town abroad was taken, per country; Axis countries get `verb: "ingenomen"`).

Positions and the Dutch or English names come from the Wikipedia API (coordinates and the Wikidata
item of each linked article) and Wikidata (labels, and coordinates when the article has none). A
position outside the country's rough 1939–1945 bounds belongs to a namesake and is dropped, and
then so is its Wikidata name. The map name is the Dutch label, else the English label, else a
Dutch-style transliteration of the Russian. Soviet fronts and fleets are translated; smaller units
keep their Russian names. Of two days ("2 of 3 oktober") the last counts; the list's own words stay
in `date_text`.

Licence: the text of the lists is from Wikipedia, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/);
the labels and coordinates from Wikidata are [CC0](https://creativecommons.org/publicdomain/zero/1.0/).

### Rebuilding

```
poetry run python -m tools.liberations [--output FILE] [--refresh]
```

The lists and every place looked up are cached in `~/.cache/uboats/liberations/`, so a rerun makes
no requests at all. `--refresh` fetches the three lists again (3 requests); only places not yet in
the cache are then looked up, one request per 50 places on Wikipedia and one per 50 Wikidata items.
A build from an empty cache takes about 85 requests: 3 lists, 41 for the 2016 linked
places (850 nl, 1166 ru) and at most as many for their Wikidata items. The command prints how many
places have no position.
