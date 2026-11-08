# All Wikipedias: ru, fr, it, ja by rules, the rest through Wikidata

Status: decided with the user on 2026-11-08 for the first group; decisions marked *(autonomous)*
were taken while the user said "ga zo ver mogelijk door zonder mijn interventie" and "pas als dat
alles klaar is wil ik weer vragen krijgen", and are open for review.

Branch: `uboat-world-languages`.

## Decided with the user

| Topic | Decision |
|---|---|
| Approach | Rules per language, as for nl/de/pl, for the first group |
| First group | ru, fr, it, ja |
| Order | Eigen positie > EN > NL > DE > PL > RU > FR > IT > JA for position, Winnaar and title |
| Titles | Every Veldslag not from the English Wikipedia gets an English title: its English article (through the language links), else its Wikidata label, else an offline Argos translation; the original stays in a tooltip, "(vertaald)" when Argos made it |
| Article | Stays in its own language, with a language label |

## Autonomous decisions

| Topic | Decision |
|---|---|
| Names | Bevelhebbers and Eenheden linked in another language get the title of their English article (redirects and language links of that Wikipedia), so one person is one Label (`tools/english_names.py`) |
| Argos | Only ctranslate2 and sentencepiece (group `translate`), not the Argos package with PyTorch; one model in memory at a time |
| Japanese dates | Written out by hand (年月日, Shōwa years); no unlinked place names in Japanese (no capitals to find them by) |
| The rest of the languages | Rules for ~300 Wikipedias do not scale, so every other language comes through Wikidata (`tools/wikidata_battles.py`): all items that are a battle, military operation, siege or naval battle, during the war |
| Wikidata as a source | Last in the order: it fills a missing position (its coordinates, else its location's) or Winnaar (its winners' Kamp) of a known Veldslag |
| New Veldslagen from Wikidata | Named after the article in the first Wikipedia of a fixed order (en, the languages above, then uk, es, pt, sv, cs, zh, fi, hu, sr, …), its wikitext fetched once and stored; Landen from its participants; English title from Wikidata |
| Query service | The SPARQL service was rate-limited (outage), so the search API (`haswbstatement`) and `wbgetentities` are used, one request every two seconds, waiting when told to |
| Any language | The Artikel endpoint and the Taal label accept any Wikipedia code; a language without a Dutch name shows its code (Taal: UK) |
| Articles of Wikidata Veldslagen | Every Veldslag with a Wikidata item whose article is not stored yet gets it fetched, English ones too (65 English articles about operations without a war infobox in the dump) |
| Winnaar and Landen of new Veldslagen | Their Winnaar comes from their article's infobox when Wikidata names none (only for a Veldslag without a Winnaar); Landen from Wikidata's participants stay when no article names any; articles in a language without rules give nothing |
| More Argos models | cs, et, fi, hu, lv, nb (for `no`), sk; the older models (cs, fi, hu) split words with Moses + BPE (`sacremoses`, `subword-nmt` in group `translate`) |
| Belarusian, Serbo-Croatian, Macedonian | No Argos model; the Russian model turns Belarusian into gibberish ("Abarona Breszkai Krapazzi"), so these 49 titles stay untranslated (accuracy before coverage) |
| Plaatshints of new Veldslagen | Not yet: tools.place_hints is rerun on master after the merge; languages without downloaded geo_tags get none |
