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
