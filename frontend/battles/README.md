# Battles

`battles.json` lists World War II battles, operations and campaigns for the battle pane
and the squares on the maps.

Source: the English Wikipedia, text available under the
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) licence. Each record links
back to its article.

Dates and coordinates are parsed automatically from the infobox and `{{coord}}` of each
article, so they can be wrong or missing. An article whose date is only a year or is not
understood is left out; a battle without a coordinate is only listed, not drawn.

## Rebuilding

Download `enwiki-latest-pages-articles.xml.bz2` from <https://dumps.wikimedia.org/enwiki/latest/>
into `~/.cache/uboats/wikipedia/` (25.8 GB, never unpacked), then run:

```
poetry run python -m tools.extract_battles [dump.xml.bz2 | directory] [--output FILE]
```

The dump is streamed once, which takes a while. The command prints progress to stderr and
a count per reason for the articles it skipped.

The `battles.json` in the repository was first built from the twelve sample articles in
`tests/fixtures/wikipedia/battle_pages.json`, so that the pages work before the full run.
