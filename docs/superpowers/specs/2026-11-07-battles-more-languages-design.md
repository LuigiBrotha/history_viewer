# Veldslagen from the Dutch, German and Polish Wikipedia

Status: decisions made with the user on 2026-11-07. Later, the other Wikipedia languages
follow the same way, so every language-specific rule lives in one table per language.

## Goal

1. English Veldslagen without a position get one from their Dutch, German or Polish article.
2. English Veldslagen with an unknown Winnaar get one the same way.
3. Battles that have no English article become new Veldslagen.

## Decisions

| Topic | Decision |
|---|---|
| Sources | The nl, de and pl dumps of one date (multistream, index, redirect.sql, langlinks.sql) in `~/.cache/uboats/wikipedia/other/`. Each dump is streamed once; memory stays small. |
| Recognising a battle | A conflict infobox of that language and a date overlapping 1 Sep 1939 – 2 Sep 1945: every battle that starts, ends or takes place during the war counts, whether or not the article names World War II. This applies to English too, so the English extraction runs again without that requirement. |
| Same battle | Only the language links decide. An article with a link to an English Veldslag belongs to it. Articles linked to each other but not to an English Veldslag form one new Veldslag. A finer-grained German battle without a link becomes its own Veldslag. |
| Position | Eigen positie, then English, then nl, then de, then pl: the first that has one. The source of the position is not shown. |
| Winnaar | English first; when unknown, nl, then de, then pl. A new Veldslag reads its own languages in that order. |
| New Veldslag | Title, dates, place and Artikel come from the first language in the order nl, de, pl that has the battle. The title gets a small language label (`NL`, `DE`, `PL`) in the list and the Artikel. Its link goes to that Wikipedia. |
| Artikel | The app renders nl, de and pl wikitext itself, like English. Internal links go to the same language's Wikipedia; links to another Veldslag stay inside the app. An infobox of another language is shown as a plain table of its fields. |
| Storage | `battles.json` records get `lang` (`en` when missing). The wikitext of other languages goes into the article table keyed by language and title, so a re-extract replaces it. |

## Per-language table

| | nl | de | pl |
|---|---|---|---|
| Infobox | `Infobox militair conflict` | `Infobox Militärischer Konflikt` | `Wojna infobox`, `Bitwa infobox` |
| Date | `date` | `DATUM` (+ `DATUMBIS`) | `czas` |
| Place | `place` | `ORT` | `miejsce` |
| Part of | `partof` | `TEILVON` | `konflikt` |
| Result | `result` | `AUSGANG` | `wynik` |
| Sides | `combatant1/2` (flag files, links) | `KONTRAHENT1/2` (country code templates such as `{{DEU-1935}}`) | `strona1/2` (`{{państwo|…}}`) |
| Coordinates | `{{Coor title dms|…}}`, `{{Coor dms|…}}` | `{{Coordinate|NS=…|EW=…}}` | `współrzędne` field |

Dates are translated to English month names (Polish genitive forms included, German
`5. Juli 1943` becomes `5 July 1943`) and then read by the existing English date parser.
Result words per language: victory (`overwinning`, `Sieg`, `zwycięstwo`), defeat
(`nederlaag`, `Niederlage`, `klęska`/`porażka`), undecided (`onbeslist`, `unentschieden`,
`nierozstrzygnięta`), plus the demonyms and country names of each language.

## Testing

Fixtures: real wikitext of a few articles per language (Slag om Arnhem, Slag om Den Haag,
Schlacht um Narvik, Kesselschlacht bei Uman, Bitwa nad Bzurą, Obrona Westerplatte). A tiny
dump per language with a langlinks file tests linking, merging and the position order.
