# Nederlandse versie of each Artikel

Status: decided with the user on 2026-11-08. Branch: `uboat-dutch`.

## Decided with the user

| Topic | Decision |
|---|---|
| Source | The Dutch Wikipedia's article about the same battle when there is one, else a machine translation of the original |
| Languages | All languages to Dutch, Russian, Japanese and the rest too (through English) |
| When | A background run translates everything ahead; an Artikel not done yet is translated when the NL button asks for it, with a message, and kept |
| Default | The last choice is remembered (browser storage and `artikel=nl` in the URL) |
| What | Everything: text, headings, captions, infobox; names, dates and numbers stay, links keep working |
| No model (be, sh, mk) | The NL button is off, with "Geen vertaling beschikbaar voor deze taal" |
| Where from | A line above the Artikel: "Nederlandse Wikipedia: <title>" or "Machinevertaling uit het Russisch (via het Engels)" |

## Decisions while building

| Topic | Decision |
|---|---|
| Engine | Argos models through ctranslate2 (offline, free); en→nl model 1.8; other languages go xx→en→nl |
| Finding the Dutch article | Language links of the Dutch dump (a Dutch page linking to the original), plus the Dutch articles the scans already stored; fetched through the Wikipedia API. 425 found |
| What is translated | The rendered, sanitised HTML: the text between block elements, line by line; links, bold and italic are put back where their text or its translation returns (as a whole word), else dropped with their text still translated; lines of only links (commanders, places) and the Dutch infobox labels are not sent |
| Dashes | The models drop "–" (1–7 September became 17 september): dashes go in as hyphens and come back as dashes |
| Other infoboxes' labels | Their field names (Дата, Командир1) get fixed Dutch labels (Datum, Bevelhebber 1) instead of a translation without context ("Afspraakje") |
| Storage | Table `dutch_articles` (lang, title of the original; kind wikipedia/vertaald; Dutch title; wikitext or HTML) |
| Dutch Veldslagen | Need no Dutch version: no buttons |
